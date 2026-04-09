# Phase 1: Core Provider - Research

**Researched:** 2026-04-09
**Domain:** Claude Code CLI subprocess integration as nanobot LLMProvider
**Confidence:** HIGH

## Summary

Phase 1 implements a new `ClaudeCodeProvider` that subclasses `LLMProvider`, sends user prompts to the Claude Code CLI via `asyncio.create_subprocess_exec`, and returns responses as `LLMResponse` objects. The provider registers as a `ProviderSpec` in the existing registry and integrates into both `_make_provider()` call sites (CLI commands and SDK facade).

**Critical discovery during live testing:** The `--bare` flag (D-08 in CONTEXT.md) breaks subscription OAuth authentication. The `--bare` documentation explicitly states "OAuth and keychain are never read." For Max/Pro subscription users -- which is the entire target audience -- `--bare` causes "Not logged in" errors. The alternative `--setting-sources ""` achieves most of the same overhead reduction (skips CLAUDE.md, project/local settings) while preserving keychain-based OAuth auth. This directly contradicts locked decision D-08 and CORE-06. The planner must address this -- either by replacing `--bare` with `--setting-sources ""` or by requiring users to run `claude setup-token` and export `CLAUDE_CODE_OAUTH_TOKEN` (which restores bare-mode auth).

**Primary recommendation:** Use `asyncio.create_subprocess_exec` with `--setting-sources ""` instead of `--bare` for subscription users. Implement `--bare` as a fallback for API-key users who set `ANTHROPIC_API_KEY`. Detect auth method at startup via `claude auth status` JSON output.

<user_constraints>

## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Use raw `asyncio.create_subprocess_exec` to call the user's system-installed `claude` binary -- not the `claude-agent-sdk` package
- **D-02:** Always use list args (never `shell=True`) to prevent shell injection
- **D-03:** Always set `stdin=asyncio.subprocess.DEVNULL` to prevent TTY hang (GitHub #9026)
- **D-04:** Drain stdout and stderr concurrently via separate async tasks to prevent pipe buffer deadlock
- **D-05:** Use the user's system-installed `claude` binary which inherits their existing subscription login -- no API key required for this provider
- **D-06:** Do not use `claude-agent-sdk` or `CLAUDE_CODE_OAUTH_TOKEN` workaround -- subscription auth via SDK is undocumented and LOW confidence
- **D-07:** CLI path configurable via config (`claude_code.cli_path`, default: `claude` from PATH)
- **D-08:** Always pass `--bare` to skip hooks/MCP/CLAUDE.md discovery -- reduces per-turn token overhead from ~50K to ~5K **(RESEARCH CONFLICT: see Summary)**
- **D-09:** Use `-p` flag for non-interactive (print) mode
- **D-10:** Use `--output-format json` for structured response parsing
- **D-11:** Pass the user's prompt as the positional argument to `claude -p`
- **D-12:** Three-channel error detection: exit code (non-zero = error), stdout JSON (parse `result` field), stderr text (capture for diagnostics)
- **D-13:** Map CLI errors to `LLMResponse(finish_reason="error")` with `error_kind`, `error_status_code`, `error_type` fields -- consistent with existing provider error model
- **D-14:** Check for `claude` binary at startup using `shutil.which()` -- fail with clear install instructions if missing
- **D-15:** Add `ProviderSpec(name="claude_code", backend="claude_code", ...)` to the `PROVIDERS` tuple in `nanobot/providers/registry.py`
- **D-16:** Create `nanobot/providers/claude_code_provider.py` implementing `LLMProvider` ABC
- **D-17:** Provider returns `LLMResponse(content=..., tool_calls=[])` -- tool_calls always empty because Claude Code handles tools internally (Agent Proxy architecture)
- **D-18:** Add config field to `ProvidersConfig` in `nanobot/config/schema.py`

### Claude's Discretion
- Exact error message wording for CLI-not-found and auth-failure cases
- Whether to validate auth status at startup vs first use
- Internal structure of the provider class (helper methods, etc.)

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope

</user_constraints>

<phase_requirements>

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| CORE-01 | User can send a prompt through nanobot that gets executed via `claude -p` and returns the response | Subprocess invocation pattern verified live. JSON output schema confirmed. `asyncio.create_subprocess_exec` with list args, stdin=DEVNULL, concurrent stdout/stderr drain. |
| CORE-02 | Claude Code CLI provider is registered as a ProviderSpec in the provider registry with auto-detection | Registry pattern documented below. ProviderSpec with `backend="claude_code"`, `is_direct=True`. Config matching via `_match_provider`. |
| CORE-03 | User can select "Claude Code (Bypass)" as a provider in config like any other provider | ProvidersConfig field addition pattern documented. `_make_provider()` branch in both `commands.py` and `nanobot.py`. |
| CORE-04 | Nanobot checks for `claude` binary at startup and fails with clear install instructions if missing | `shutil.which()` check at provider init. `claude auth status` returns JSON with `loggedIn`, `subscriptionType`. |
| CORE-05 | Auth failures, rate limits, and CLI errors propagate as user-friendly error messages | Three-channel error detection documented. JSON output has `is_error`, `result` fields. `LLMResponse` error metadata fields mapped. |
| CORE-06 | All CLI invocations use `--bare` flag to reduce token overhead | **CONFLICT**: `--bare` breaks subscription auth. Alternative: `--setting-sources ""` preserves auth, reduces overhead. See Architecture Patterns section. |

</phase_requirements>

## Project Constraints (from CLAUDE.md)

- GSD workflow enforcement: no direct repo edits outside GSD workflow unless user explicitly asks
- Formatting: `ruff` with `line-length = 100`, target `py311`
- Linting: `ruff` rules `E`, `F`, `I`, `N`, `W`; `E501` ignored
- Testing: `pytest` with `asyncio_mode = "auto"`, test paths `["tests"]`
- Type annotations on all function signatures
- All imports use absolute `nanobot.*` paths
- Error handling: provider errors become `LLMResponse(finish_reason="error")` via `_safe_chat`/`_safe_chat_stream` wrappers
- `asyncio.CancelledError` always re-raised, never swallowed
- Logging: `from loguru import logger`; template-style placeholders

## Standard Stack

### Core (No new dependencies)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `asyncio` | stdlib | Subprocess management, concurrent I/O | Project already uses asyncio throughout; `create_subprocess_exec` is the correct async subprocess API |
| `shutil` | stdlib | `which()` for binary detection | Standard approach for finding executables on PATH |
| `json` | stdlib | Parse CLI JSON output | CLI returns structured JSON via `--output-format json` |
| `pydantic` | `>=2.12.0` | Config schema for `ClaudeCodeProviderConfig` | Existing config pattern; all config models extend `Base(BaseModel)` |
| `loguru` | `>=0.7.3` | Structured logging | Project-wide standard |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `asyncio.create_subprocess_exec` | `claude-agent-sdk` (`query()`) | SDK handles transport but adds ~50MB dependency, alpha (0.1.x), and has unclear subscription auth support. Per D-01/D-06, use raw subprocess. |
| `asyncio.create_subprocess_exec` | `subprocess.Popen` | Blocking; would freeze the event loop. Not viable in async codebase. |
| `json.loads` | `json-repair` | `json-repair` masks real bugs. CLI JSON output is well-formed; use `json.loads` as primary, log raw output on parse failure. |
| `shutil.which` | `subprocess.run(["which", "claude"])` | `shutil.which` is cross-platform, no subprocess overhead, and already used idiomatically in Python. |

**Installation:** No new packages required. All dependencies are stdlib or already in the project.

## Architecture Patterns

### Recommended File Structure

```
nanobot/providers/
    claude_code_provider.py    # NEW: ClaudeCodeProvider (LLMProvider subclass)
nanobot/providers/registry.py  # MODIFIED: Add ProviderSpec entry
nanobot/config/schema.py       # MODIFIED: Add ClaudeCodeProviderConfig + ProvidersConfig field
nanobot/cli/commands.py        # MODIFIED: Add elif backend == "claude_code" branch
nanobot/nanobot.py             # MODIFIED: Add elif backend == "claude_code" branch
nanobot/providers/__init__.py  # MODIFIED: Add lazy import for ClaudeCodeProvider
tests/providers/
    test_claude_code_provider.py  # NEW: Unit tests
```

### Pattern 1: Subprocess Provider (Core Pattern)

**What:** `ClaudeCodeProvider` subclasses `LLMProvider`, implements `chat()` and `chat_stream()` using `asyncio.create_subprocess_exec` to run `claude -p`.

**When to use:** This is the only pattern for Phase 1. All Claude Code interaction goes through subprocess.

**Key implementation details from live testing:**

```python
"""Claude Code CLI provider."""

from __future__ import annotations

import asyncio
import json
import shutil
from collections.abc import Awaitable, Callable
from typing import Any

from loguru import logger

from nanobot.providers.base import LLMProvider, LLMResponse


class ClaudeCodeProvider(LLMProvider):
    """Routes prompts through the Claude Code CLI subprocess."""

    def __init__(
        self,
        cli_path: str | None = None,
        default_model: str = "claude_code/claude-sonnet-4-20250514",
    ) -> None:
        super().__init__(api_key=None, api_base=None)
        self._cli_path = cli_path or shutil.which("claude")
        if not self._cli_path:
            raise RuntimeError(
                "Claude Code CLI not found. Install it with:\n"
                "  npm install -g @anthropic-ai/claude-code\n\n"
                "Then authenticate:\n"
                "  claude\n"
                "  # Follow the login prompts"
            )
        self._default_model = default_model

    def _build_command(self, prompt: str) -> list[str]:
        """Build the CLI command as a list of arguments."""
        return [
            self._cli_path,
            "-p",
            "--output-format", "json",
            "--setting-sources", "",
            prompt,
        ]

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        reasoning_effort: str | None = None,
        tool_choice: str | dict[str, Any] | None = None,
    ) -> LLMResponse:
        prompt = self._extract_latest_user_content(messages)
        cmd = self._build_command(prompt)

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        # Drain stdout and stderr concurrently to prevent pipe buffer deadlock
        stdout_bytes, stderr_bytes = await proc.communicate()
        await proc.wait()

        return self._parse_result(stdout_bytes, stderr_bytes, proc.returncode)

    def _extract_latest_user_content(self, messages: list[dict[str, Any]]) -> str:
        """Extract the latest user message content for the CLI prompt."""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                content = msg.get("content", "")
                if isinstance(content, str):
                    return content
                if isinstance(content, list):
                    parts = []
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "text":
                            parts.append(block.get("text", ""))
                    return "\n".join(parts)
        return ""

    def _parse_result(
        self,
        stdout_bytes: bytes,
        stderr_bytes: bytes,
        returncode: int | None,
    ) -> LLMResponse:
        """Parse CLI JSON output into LLMResponse."""
        stderr_text = stderr_bytes.decode("utf-8", errors="replace").strip()
        if stderr_text:
            logger.debug("Claude Code stderr: {}", stderr_text[:500])

        stdout_text = stdout_bytes.decode("utf-8", errors="replace").strip()
        if not stdout_text:
            return LLMResponse(
                content=f"Claude Code CLI returned no output. Exit code: {returncode}. "
                        f"stderr: {stderr_text[:200]}",
                finish_reason="error",
                tool_calls=[],
            )

        try:
            data = json.loads(stdout_text)
        except json.JSONDecodeError as exc:
            return LLMResponse(
                content=f"Failed to parse Claude Code JSON output: {exc}. "
                        f"Raw: {stdout_text[:200]}",
                finish_reason="error",
                tool_calls=[],
            )

        is_error = data.get("is_error", False)
        result_text = data.get("result", "")
        usage = data.get("usage", {})

        if is_error:
            return self._build_error_response(result_text, stderr_text, usage)

        return LLMResponse(
            content=result_text or None,
            tool_calls=[],
            finish_reason="stop",
            usage={
                "prompt_tokens": usage.get("input_tokens", 0),
                "completion_tokens": usage.get("output_tokens", 0),
            },
        )

    def get_default_model(self) -> str:
        return self._default_model
```

### Pattern 2: Three-Channel Error Detection

**What:** Check exit code, stdout JSON `is_error` field, and stderr text for comprehensive error capture.

**When to use:** In `_parse_result()` after every subprocess completes.

**Verified JSON error schema (from live testing):**
```json
{
  "type": "result",
  "subtype": "success",
  "is_error": true,
  "result": "Not logged in - Please run /login",
  "session_id": "uuid-string",
  "total_cost_usd": 0,
  "usage": { "input_tokens": 0, "output_tokens": 0 }
}
```

Key observation: `is_error: true` can coexist with `"subtype": "success"` -- always check `is_error` explicitly.

**Error classification for retry logic:**

| Error Pattern | Classification | `error_should_retry` |
|---------------|---------------|---------------------|
| `"Not logged in"` in result | Auth failure | `False` |
| `"rate limit"` / `"too many requests"` in result or stderr | Rate limit | `True` |
| `"overloaded"` in result | Overloaded | `True` |
| Non-zero exit code + empty stdout | Process crash | `False` |
| `"timeout"` in stderr | Timeout | `True` |

### Pattern 3: Provider Registration (3 Touchpoints)

**What:** Register the provider in the existing system via exactly 3 code changes.

**Touchpoint 1 -- Registry (`nanobot/providers/registry.py`):**
```python
ProviderSpec(
    name="claude_code",
    keywords=("claude-code", "claude_code", "bypass"),
    env_key="",
    display_name="Claude Code (Bypass)",
    backend="claude_code",
    is_direct=True,
)
```

Note: `is_direct=True` skips API key validation (no API key needed for subscription auth). `env_key=""` because auth comes from the CLI's keychain, not an env var.

**Touchpoint 2 -- Config schema (`nanobot/config/schema.py`):**
```python
class ClaudeCodeProviderConfig(Base):
    """Configuration for Claude Code CLI bypass provider."""
    cli_path: str = ""  # Empty = auto-detect via shutil.which("claude")

# In ProvidersConfig:
claude_code: ClaudeCodeProviderConfig = Field(
    default_factory=ClaudeCodeProviderConfig,
    exclude=True,  # Match pattern of other non-API-key providers
)
```

Use a dedicated `ClaudeCodeProviderConfig` rather than the generic `ProviderConfig` because this provider has different config fields (no `api_key`/`api_base`, has `cli_path`).

**Touchpoint 3 -- Provider instantiation (`commands.py` + `nanobot.py`):**
```python
elif backend == "claude_code":
    from nanobot.providers.claude_code_provider import ClaudeCodeProvider
    cli_path = (
        getattr(config.providers, "claude_code", None)
        and config.providers.claude_code.cli_path
    ) or None
    provider = ClaudeCodeProvider(cli_path=cli_path, default_model=model)
```

This branch goes in both `nanobot/cli/commands.py:_make_provider()` and `nanobot/nanobot.py:_make_provider()`.

### Pattern 4: Lazy Import in `__init__.py`

**What:** Add `ClaudeCodeProvider` to the lazy import registry.

```python
# nanobot/providers/__init__.py additions:
__all__ = [
    # ... existing ...
    "ClaudeCodeProvider",
]

_LAZY_IMPORTS = {
    # ... existing ...
    "ClaudeCodeProvider": ".claude_code_provider",
}

if TYPE_CHECKING:
    from nanobot.providers.claude_code_provider import ClaudeCodeProvider
```

### Anti-Patterns to Avoid

- **Using `--bare` with subscription auth:** `--bare` skips keychain reads, breaking OAuth. Use `--setting-sources ""` instead.
- **Using `shell=True` or `create_subprocess_shell`:** Shell injection risk. Always use `create_subprocess_exec` with list args (D-02).
- **Sequential stdout/stderr reads:** Causes pipe buffer deadlock on long responses. Use `proc.communicate()` or concurrent async tasks (D-04).
- **Passing nanobot's full message history as prompt:** Only pass the latest user message. Claude Code manages its own context via `--resume` (Phase 2).
- **Routing through `ExecTool`:** Don't use nanobot's `ExecTool` for the Claude subprocess -- it has deny-list patterns that may block `claude` invocations.

## Critical Research Finding: `--bare` vs Subscription Auth

### The Problem (Verified Empirically)

| Flag Combination | Auth Status | Result |
|------------------|-------------|--------|
| `claude -p "prompt"` | Max subscription | Works -- uses keychain OAuth |
| `claude -p --bare "prompt"` | Max subscription | **FAILS** -- "Not logged in" |
| `claude -p --setting-sources "" "prompt"` | Max subscription | Works -- uses keychain OAuth |
| `claude -p --bare "prompt"` + `ANTHROPIC_API_KEY` | API key | Works -- reads env var |

**Root cause:** The `--bare` flag documentation states: "Anthropic auth is strictly ANTHROPIC_API_KEY or apiKeyHelper via --settings (OAuth and keychain are never read)."

### Impact on CORE-06

CORE-06 states "All CLI invocations use `--bare` flag." This is incompatible with the project's core value ("subscription users can keep using nanobot"). The requirement needs modification.

### Recommended Resolution

**Option A (Recommended): Replace `--bare` with `--setting-sources ""`**
- Preserves subscription OAuth auth (keychain is still read)
- Skips project/local/user settings (CLAUDE.md, hooks, plugins)
- Overhead: 3 input tokens for simple prompts (verified), ~$0.035 per turn
- Simple, no user action required

**Option B: Keep `--bare` but require `CLAUDE_CODE_OAUTH_TOKEN`**
- User runs `claude setup-token` once to generate a long-lived token
- Provider sets `CLAUDE_CODE_OAUTH_TOKEN` env var in subprocess environment
- Restores `--bare` auth compatibility
- Drawback: extra setup step, token may expire

**Option C: Auto-detect auth method**
- Run `claude auth status` at provider init -- parse `authMethod` field
- If `authMethod == "api_key"`: use `--bare` (safe, API key in env)
- If `authMethod == "claude.ai"`: use `--setting-sources ""` (subscription, needs keychain)
- Most robust but adds init-time subprocess call

### Token Overhead Comparison (Verified)

| Flag | Input Tokens (simple prompt) | Cost (simple prompt) | Auth Compatible |
|------|------|------|------|
| No flags | 3 | $0.20 (loads CLAUDE.md context) | Subscription + API key |
| `--setting-sources ""` | 3 | $0.035 | Subscription + API key |
| `--bare` | N/A | N/A (auth fails) | API key only |

`--setting-sources ""` provides nearly identical overhead reduction to `--bare` without breaking subscription auth.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Pipe buffer deadlock prevention | Custom concurrent stream readers | `proc.communicate()` | `communicate()` handles concurrent drain of stdout+stderr internally; eliminates the deadlock. For Phase 1 non-streaming, this is sufficient. |
| CLI binary detection | Custom PATH walking | `shutil.which("claude")` | Handles PATH, extensions, symlinks correctly on all platforms |
| JSON response parsing | Regex extraction from output | `json.loads()` on `--output-format json` stdout | CLI guarantees well-formed JSON with this flag |
| Auth status checking | Parsing config files or keychain | `claude auth status` subprocess | Returns clean JSON: `{"loggedIn": true, "authMethod": "claude.ai", "subscriptionType": "max"}` |
| Retry-after extraction | Custom text parsing | Inherit from `LLMProvider._extract_retry_after()` | Base class already handles "retry after N seconds" patterns in error text |

**Key insight:** The CLI provides structured JSON output that eliminates most parsing complexity. The base `LLMProvider` class provides retry logic, error wrapping, and safe-call wrappers that the new provider inherits for free.

## Common Pitfalls

### Pitfall 1: `--bare` Breaks Subscription Auth
**What goes wrong:** Using `--bare` causes "Not logged in" for Max/Pro subscription users because it skips keychain OAuth token reads.
**Why it happens:** `--bare` is documented to use "strictly ANTHROPIC_API_KEY or apiKeyHelper." Subscription auth tokens live in the system keychain, not env vars.
**How to avoid:** Use `--setting-sources ""` instead. Achieves comparable overhead reduction while preserving keychain auth.
**Warning signs:** `is_error: true` with `result: "Not logged in"` in the JSON response.

### Pitfall 2: Pipe Buffer Deadlock
**What goes wrong:** Subprocess hangs when response exceeds OS pipe buffer (64KB Linux, 16KB macOS).
**Why it happens:** Reading stdout in a loop without draining stderr fills the stderr pipe buffer.
**How to avoid:** Use `proc.communicate()` which drains both streams concurrently. For streaming (Phase 2), use separate async tasks.
**Warning signs:** Hangs only on long responses; short responses work fine.

### Pitfall 3: stdin Hang Without DEVNULL
**What goes wrong:** Claude Code CLI hangs waiting for TTY input even with `-p` flag.
**Why it happens:** CLI performs shell detection that can consume stdin (GitHub #9026).
**How to avoid:** Always pass `stdin=asyncio.subprocess.DEVNULL` for one-shot mode (D-03).
**Warning signs:** Process starts but produces no output for 10+ seconds.

### Pitfall 4: `is_error` Can Be True Even With `subtype: "success"`
**What goes wrong:** Code checks `subtype` field instead of `is_error` and misses actual errors.
**Why it happens:** The CLI JSON schema has `is_error: true` alongside `subtype: "success"` for auth errors.
**How to avoid:** Always check `is_error` as the primary error indicator, not `subtype`.
**Warning signs:** Auth errors silently treated as successful responses with error text as content.

### Pitfall 5: Zombie Process Accumulation
**What goes wrong:** Killed Claude Code processes leave orphaned children.
**Why it happens:** `process.kill()` only kills the direct process, not its process group.
**How to avoid:** For Phase 1 with `communicate()`, this is handled automatically -- `communicate()` waits for process exit. For Phase 4 (robustness), use `start_new_session=True` and process group kill.
**Warning signs:** `pgrep -c claude` count increasing over time.

### Pitfall 6: Shell Injection via Prompt
**What goes wrong:** User prompt containing shell metacharacters executes arbitrary commands.
**Why it happens:** Using `create_subprocess_shell` or string-formatting the command.
**How to avoid:** Always use `create_subprocess_exec` with list args (D-02). Prompt is passed as a positional argument in the list, never interpolated into a shell string.
**Warning signs:** Code review finds any `shell=True` or string formatting in CLI command construction.

## Code Examples

### Verified CLI JSON Output Schema (from live testing)

**Success response:**
```json
{
  "type": "result",
  "subtype": "success",
  "is_error": false,
  "result": "hello",
  "duration_ms": 8543,
  "duration_api_ms": 7200,
  "num_turns": 1,
  "stop_reason": "end_turn",
  "session_id": "uuid-string",
  "total_cost_usd": 0.034810999,
  "usage": {
    "input_tokens": 3,
    "cache_creation_input_tokens": 0,
    "cache_read_input_tokens": 0,
    "output_tokens": 4,
    "server_tool_use": {"web_search_requests": 0, "web_fetch_requests": 0},
    "service_tier": "standard"
  }
}
```

**Auth error response:**
```json
{
  "type": "result",
  "subtype": "success",
  "is_error": true,
  "result": "Not logged in \u00b7 Please run /login",
  "session_id": "uuid-string",
  "total_cost_usd": 0,
  "usage": {"input_tokens": 0, "output_tokens": 0}
}
```

**Auth status output (`claude auth status`):**
```json
{
  "loggedIn": true,
  "authMethod": "claude.ai",
  "apiProvider": "firstParty",
  "email": "user@example.com",
  "subscriptionType": "max"
}
```

### Provider Registration Template (from existing codebase patterns)

**ProviderSpec entry:**
```python
# In PROVIDERS tuple, after github_copilot entry:
ProviderSpec(
    name="claude_code",
    keywords=("claude-code", "claude_code", "bypass"),
    env_key="",
    display_name="Claude Code (Bypass)",
    backend="claude_code",
    is_direct=True,
),
```

**Config field:**
```python
class ClaudeCodeProviderConfig(Base):
    """Configuration for Claude Code CLI bypass provider."""
    cli_path: str = ""  # Empty = auto-detect via shutil.which

# In ProvidersConfig:
claude_code: ClaudeCodeProviderConfig = Field(
    default_factory=ClaudeCodeProviderConfig,
    exclude=True,
)
```

### Test Pattern (from existing provider tests)

```python
import asyncio
import pytest
from nanobot.providers.base import LLMResponse

class FakeProcess:
    def __init__(self, stdout: bytes, stderr: bytes, returncode: int):
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode

    async def communicate(self):
        return self.stdout, self.stderr

    async def wait(self):
        return self.returncode

@pytest.mark.asyncio
async def test_parse_success_response():
    from nanobot.providers.claude_code_provider import ClaudeCodeProvider
    # Test with mock -- no real subprocess
    ...

@pytest.mark.asyncio
async def test_parse_auth_error_response():
    ...

@pytest.mark.asyncio
async def test_cli_not_found_raises():
    ...
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `claude-code-sdk` package | `claude-agent-sdk` package | Sept 2025 | Old package deprecated; renamed |
| No `--bare` flag | `--bare` available | ~2025 | Reduces startup overhead but breaks subscription auth |
| `--output-format text` | `--output-format json` / `stream-json` | Stable | Structured parsing replaces regex |
| `claude auth login` (browser) | `claude setup-token` (headless) | 2026 | Long-lived tokens for CI/headless use |

**Claude Code CLI version on this machine:** 2.1.97

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `claude` CLI | All CORE requirements | Yes | 2.1.97 | None -- required |
| Node.js | Claude Code CLI runtime | Yes | v25.8.1 | None -- required by CLI |
| Python 3.11+ | nanobot runtime | Yes | 3.11.1 | None -- project requirement |
| npm | CLI installation | Yes | 11.11.0 | Used for `npm install -g` instructions |

**Missing dependencies with no fallback:** None -- all required tools available.

**Auth status:** Logged in as Max subscriber (`authMethod: "claude.ai"`, `subscriptionType: "max"`). Subscription auth works via keychain (non-bare mode) but NOT with `--bare` flag.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest >= 9.0.0 with pytest-asyncio >= 1.3.0 |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run command | `pytest tests/providers/test_claude_code_provider.py -x` |
| Full suite command | `pytest tests/ -x` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CORE-01 | Send prompt, receive response via CLI | unit (mocked subprocess) | `pytest tests/providers/test_claude_code_provider.py::test_chat_returns_response -x` | Wave 0 |
| CORE-02 | ProviderSpec registered in PROVIDERS | unit | `pytest tests/providers/test_claude_code_provider.py::test_provider_spec_registered -x` | Wave 0 |
| CORE-03 | Provider selectable via config | unit | `pytest tests/providers/test_claude_code_provider.py::test_config_matches_provider -x` | Wave 0 |
| CORE-04 | CLI binary check at startup | unit | `pytest tests/providers/test_claude_code_provider.py::test_missing_cli_raises -x` | Wave 0 |
| CORE-05 | Error propagation | unit | `pytest tests/providers/test_claude_code_provider.py::test_auth_error_propagated -x` | Wave 0 |
| CORE-06 | Overhead reduction flags | unit | `pytest tests/providers/test_claude_code_provider.py::test_command_includes_setting_sources -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/providers/test_claude_code_provider.py -x`
- **Per wave merge:** `pytest tests/ -x`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/providers/test_claude_code_provider.py` -- covers CORE-01 through CORE-06
- Framework install: already available (`pytest` in dev dependencies)

## Open Questions

1. **`--bare` vs `--setting-sources ""` for CORE-06**
   - What we know: `--bare` breaks subscription auth; `--setting-sources ""` works but is less aggressive at overhead reduction
   - What's unclear: Whether the user considers the `--bare` decision (D-08) locked hard enough to require `CLAUDE_CODE_OAUTH_TOKEN` workaround, or if replacing with `--setting-sources ""` is acceptable
   - Recommendation: Use `--setting-sources ""` as default. Add `--bare` as opt-in for API-key users via config flag. Planner should surface this to user if needed.

2. **Auth validation: startup vs first use**
   - What we know: `claude auth status` returns JSON with `loggedIn` field; takes ~0.5s
   - What's unclear: Whether the startup cost of a `claude auth status` subprocess is acceptable
   - Recommendation: Validate at first use (lazy). Cache the result. Only `shutil.which()` at init for binary existence.

## Sources

### Primary (HIGH confidence)
- Claude Code CLI v2.1.97 `--help` output -- `--bare` flag documentation, all flag details
- Live testing on this machine -- Verified `--bare` breaks subscription auth, `--setting-sources ""` works, JSON output schema confirmed
- Nanobot codebase `nanobot/providers/base.py` -- LLMProvider ABC, LLMResponse dataclass, retry logic
- Nanobot codebase `nanobot/providers/registry.py` -- ProviderSpec, PROVIDERS tuple, registration pattern
- Nanobot codebase `nanobot/config/schema.py` -- ProvidersConfig, ProviderConfig, config field patterns
- Nanobot codebase `nanobot/cli/commands.py` -- `_make_provider()` backend switch pattern
- Nanobot codebase `nanobot/nanobot.py` -- `_make_provider()` duplicate for SDK facade
- Nanobot codebase `nanobot/providers/openai_codex_provider.py` -- OAuth provider pattern reference

### Secondary (MEDIUM confidence)
- [Claude Code CLI Reference](https://code.claude.com/docs/en/cli-reference) -- Official flag documentation
- [Run Claude Code Programmatically](https://code.claude.com/docs/en/headless) -- `-p` flag, `--bare` usage
- `.planning/research/PITFALLS.md` -- Pipe deadlock, stdin hang, zombie processes

### Tertiary (LOW confidence)
- `.planning/research/STACK.md` SDK analysis -- Useful context but SDK is not used per D-01/D-06

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- No new dependencies; all stdlib + existing project deps
- Architecture: HIGH -- Provider registration pattern is well-documented in codebase with explicit instructions in registry.py docstring; subprocess patterns are standard asyncio
- Pitfalls: HIGH -- Key pitfall (`--bare` auth) verified empirically on this machine; pipe deadlock and stdin hang are well-documented in upstream issues
- `--bare` replacement: HIGH -- `--setting-sources ""` tested and verified on this machine

**Research date:** 2026-04-09
**Valid until:** 2026-05-09 (30 days -- Claude Code CLI is fast-moving; verify `--setting-sources` behavior if CLI updates)
