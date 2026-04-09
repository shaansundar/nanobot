# Technology Stack

**Project:** Nanobot Harness Bypass (Claude Code CLI Proxy Provider)
**Researched:** 2026-04-09
**Previous version corrected:** Earlier draft rejected `claude-agent-sdk` based on a misconception. See "Correcting the Prior Analysis" below.

## Correcting the Prior Analysis

The prior STACK.md stated:

> `claude_agent_sdk` (PyPI) -- Runs its own agent loop; conflicts with nanobot's AgentRunner. We shell out to CLI instead.

This is incorrect. The `claude-agent-sdk` does NOT run an agent loop in the Python process. Its `query()` function spawns the Claude Code CLI as a subprocess and communicates via JSON-lines over stdin/stdout. The "agent loop" runs inside the CLI child process (Node.js), completely isolated from nanobot's `AgentRunner`. The SDK is a thin async transport layer, not a competing agent framework.

The recommendation below uses the SDK because it provides exactly the subprocess management, streaming, and session handling that the prior draft proposed to build from scratch using `asyncio.create_subprocess_exec`.

## Recommended Stack

### Primary: Claude Agent SDK (Python)

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| `claude-agent-sdk` | `>=0.1.56,<0.2.0` | Python SDK wrapping Claude Code CLI | Official Anthropic package. Bundles the CLI binary. Async iterator streaming, session management, bidirectional `ClaudeSDKClient`, hooks. Eliminates all raw subprocess management. | HIGH |

**What it does internally:** Spawns the Claude Code CLI as a child process, communicates via JSON-lines over stdin/stdout using `--input-format stream-json` / `--output-format stream-json`. The transport layer (`_internal/transport/subprocess_cli.py`) uses `anyio.open_process()` with a 1MB buffer, write locking, and structured error handling. Nanobot code never touches this -- it consumes `AsyncIterator[Message]` objects.

**Why not raw `asyncio.create_subprocess_exec`:** The SDK handles process lifecycle, stream buffering, JSON-lines parsing, control message multiplexing (permission requests, hook callbacks), error recovery, and cleanup. Reimplementing this is approximately 2000 lines of transport code for zero benefit. The SDK is the officially supported interface.

### Core Framework (Existing -- No Changes)

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Python | 3.11+ | Runtime | Existing project requirement; SDK needs >=3.10, fully compatible |
| `asyncio` | stdlib | Async runtime | Existing project uses asyncio throughout; SDK is asyncio-compatible (uses anyio internally, which wraps asyncio) |

### New Dependencies

| Library | Version | Purpose | Confidence |
|---------|---------|---------|------------|
| `claude-agent-sdk` | `>=0.1.56,<0.2.0` | Claude Code CLI interface | HIGH |

Transitive dependencies pulled in by the SDK: `anyio>=4.0`, `sniffio`. Do NOT add these directly.

### Existing Dependencies (Reused, No Changes)

| Library | Version | Relevance to Bypass |
|---------|---------|---------------------|
| `loguru` | `>=0.7.3` | Log bypass provider events, SDK errors, session lifecycle |
| `pydantic` | `>=2.12.0` | New config fields: bypass toggle, verbosity, persona passthrough |
| `typer` | `>=0.20.0` | New `--bypass` CLI flag in provider selection |
| `rich` | `>=14.0.0` | Stream bypass responses in CLI mode |
| `json-repair` | `>=0.57.0` | Not needed -- SDK handles all JSON parsing internally |

## Two SDK Integration Approaches

### Approach A: `query()` for One-Shot Mode (Recommended for MVP)

```python
from claude_agent_sdk import query, ClaudeAgentOptions, ResultMessage, AssistantMessage, TextBlock

async def bypass_chat(prompt: str, system_prompt: str | None, session_id: str | None) -> tuple[str, str]:
    """Returns (response_text, session_id)."""
    options = ClaudeAgentOptions(
        allowed_tools=["Read", "Edit", "Bash", "Glob", "Grep"],
        permission_mode="acceptEdits",
        append_system_prompt=system_prompt,
        resume=session_id,  # None for new session, session_id for continuation
        bare=True,  # Skip hooks/MCP/CLAUDE.md for faster startup
    )

    result_text = ""
    new_session_id = ""

    async for message in query(prompt=prompt, options=options):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    result_text += block.text
        if isinstance(message, ResultMessage):
            new_session_id = message.session_id

    return result_text, new_session_id
```

**Characteristics:**
- Creates a new subprocess per call (cleaned up automatically)
- Session continuity via `resume=session_id` on subsequent calls
- Maps directly to nanobot's `LLMProvider.chat()` interface
- Simplest integration path

### Approach B: `ClaudeSDKClient` for Persistent Session Mode

```python
from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions, AssistantMessage, TextBlock, ResultMessage

class BypassSession:
    def __init__(self):
        self._client: ClaudeSDKClient | None = None

    async def start(self, options: ClaudeAgentOptions) -> None:
        self._client = ClaudeSDKClient(options=options)
        await self._client.connect()

    async def send(self, prompt: str) -> str:
        await self._client.query(prompt)
        result = ""
        async for message in self._client.receive_response():
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        result += block.text
        return result

    async def stop(self) -> None:
        if self._client:
            await self._client.disconnect()
```

**Characteristics:**
- Single long-lived subprocess for entire conversation
- Full context retained between turns (no `resume` needed)
- Supports `interrupt()` mid-generation
- Must drain message buffer after interrupts
- More complex lifecycle management

### Recommendation: Approach A for Phase 1, Approach B for Phase 2

Use `query()` with `resume` for the MVP. It maps cleanly onto nanobot's `LLMProvider` contract where each `chat()`/`chat_stream()` call is independent. The `resume` parameter provides session continuity without managing a persistent subprocess.

`ClaudeSDKClient` is the better fit for interactive session mode (PROJECT.md requirement) but requires lifecycle management that doesn't align with nanobot's per-turn provider call pattern. Add it in Phase 2 once the basic provider works.

## Claude Code CLI Flags Reference

The SDK abstracts these, but they matter for understanding behavior and for the bash script fallback.

### Flags Mapped to SDK Options

| CLI Flag | SDK Option | Purpose |
|----------|------------|---------|
| `-p` / `--print` | Always used by SDK | Non-interactive mode |
| `--output-format stream-json` | `include_partial_messages=True` | NDJSON streaming |
| `--output-format json` | Default SDK mode | Single JSON response |
| `--input-format stream-json` | Used by `ClaudeSDKClient` | Bidirectional stdin |
| `--bare` | No direct option; use `setting_sources=[]` | Skip auto-discovery |
| `--allowedTools "Read,Edit,Bash"` | `allowed_tools=["Read","Edit","Bash"]` | Tool permissions |
| `--permission-mode acceptEdits` | `permission_mode="acceptEdits"` | Auto-approve edits |
| `--append-system-prompt "..."` | `system_prompt="..."` | Custom instructions |
| `--resume SESSION_ID` | `resume="SESSION_ID"` | Session continuity |
| `--max-turns N` | `max_turns=N` | Limit iterations |
| `--verbose` | Implicit with streaming | Full event details |

### Output JSON Schema (`--output-format json`)

```json
{
  "result": "The text response",
  "session_id": "uuid-string",
  "duration_ms": 1234,
  "duration_api_ms": 1100,
  "is_error": false,
  "num_turns": 3,
  "total_cost_usd": 0.05,
  "usage": {
    "input_tokens": 500,
    "output_tokens": 200,
    "cache_creation_input_tokens": 0,
    "cache_read_input_tokens": 0
  }
}
```

### SDK Message Types (What the Provider Receives)

| Type | Class | Key Fields | Provider Use |
|------|-------|------------|-------------|
| Assistant | `AssistantMessage` | `content: list[ContentBlock]`, `model`, `usage` | Extract text, tool use blocks |
| Result | `ResultMessage` | `session_id`, `result`, `is_error`, `usage`, `total_cost_usd` | Final response, session tracking |
| User | `UserMessage` | `content`, `tool_use_result` | Tool results (internal to CLI, usually not needed) |
| Stream | `StreamEvent` | `event: dict` | Raw token deltas (when `include_partial_messages=True`) |
| Rate Limit | `RateLimitEvent` | `rate_limit_info` | Backoff/retry signaling |

## Authentication: Critical Constraint

### The Problem

The project's core purpose is routing subscription users (Max/Pro) through Claude Code CLI. The SDK's authentication situation as of April 2026:

| Auth Method | CLI (`claude -p`) | Agent SDK (`query()`) | Status |
|-------------|--------------------|-----------------------|--------|
| API Key (`ANTHROPIC_API_KEY`) | Works | Works | Officially supported |
| OAuth Token (subscription) | Works | Community workaround | NOT officially supported |
| Interactive login | Works | N/A | Not programmatic |

**Community workaround for subscription auth:**
```bash
claude setup-token
export CLAUDE_CODE_OAUTH_TOKEN=<token>
# SDK then uses subscription billing
```

Reported working in [GitHub issue #559](https://github.com/anthropics/claude-agent-sdk-python/issues/559) but NOT officially documented. Anthropic's docs explicitly state SDK requires API key auth.

**Confidence:** LOW -- This is the single biggest risk. Requires validation in Phase 1.

### Mitigation: Dual-Path Architecture

```
IF subscription auth works with SDK:
    Use claude-agent-sdk (full streaming, sessions, hooks)
ELSE:
    Fall back to raw asyncio.create_subprocess_exec with claude -p
    (Uses the user's existing CLI login, always works with subscriptions)
```

The raw subprocess fallback is simpler but loses structured message types, hooks, and the `ClaudeSDKClient` bidirectional mode. It still provides streaming via `--output-format stream-json` parsed line-by-line.

### Raw Subprocess Fallback Implementation

```python
import asyncio
import json

async def bypass_raw(prompt: str, on_delta=None) -> dict:
    proc = await asyncio.create_subprocess_exec(
        "claude", "-p", prompt,
        "--output-format", "stream-json",
        "--verbose",
        "--bare",
        "--permission-mode", "acceptEdits",
        "--allowedTools", "Read,Edit,Bash,Glob,Grep",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    result = {}
    async for line in proc.stdout:
        event = json.loads(line.decode())
        if event.get("type") == "assistant":
            # Extract text content
            for block in event.get("message", {}).get("content", []):
                if block.get("type") == "text" and on_delta:
                    await on_delta(block["text"])
        elif event.get("type") == "result":
            result = event

    await proc.wait()
    return result
```

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| CLI interface | `claude-agent-sdk` | Raw `asyncio.create_subprocess_exec` | SDK handles transport, buffering, error recovery, JSON parsing, session management. Raw subprocess requires reimplementing all of this. Keep as fallback only. |
| CLI interface | `claude-agent-sdk` | `claude-code-sdk` (old name) | Deprecated since Sept 2025. Renamed to `claude-agent-sdk`. |
| CLI interface | `claude-agent-sdk` | `pexpect` | `pexpect` is for interactive terminal emulation. Claude Code's `-p` flag provides clean programmatic interface. `pexpect` adds complexity for no benefit. |
| Subprocess API | `asyncio.create_subprocess_exec` | `asyncio.create_subprocess_shell` | `exec` is safer (no shell injection), more explicit arg passing. Only relevant for fallback path. |
| Async runtime | `asyncio` (existing) | Import `anyio` directly | Don't introduce anyio as a direct dependency. SDK uses it internally; nanobot uses asyncio. They are compatible. |
| CLI output format | `stream-json` | `json` (non-streaming) | `stream-json` enables real-time text streaming; `json` waits for completion |
| CLI output format | `stream-json` | `text` (plain) | `text` requires regex parsing, no structured tool data, format unstable |
| Session continuity | `resume` parameter | Re-serialize full history | `resume` is more efficient; avoids prompt length limits; managed by CLI |
| Startup speed | `--bare` / `setting_sources=[]` | Default mode | `--bare` skips hooks/skills/plugins/MCP/CLAUDE.md discovery; significantly faster startup for programmatic use |

## What NOT to Use

| Technology | Why Not |
|------------|---------|
| `pexpect` / `pty` | Claude Code's `-p` flag provides clean non-interactive output. Terminal emulation is unnecessary overhead. |
| `subprocess.Popen` (sync) | Nanobot is fully async. Blocking calls require thread pool wrappers and lose streaming. |
| `claude-code-sdk` | Deprecated. Package renamed to `claude-agent-sdk`. |
| `anthropic` SDK directly | This IS the existing nanobot provider. Bypass mode's purpose is to NOT use direct API calls. |
| `trio` / `curio` | Nanobot uses asyncio. Don't introduce alternative async runtimes. |
| Custom `Transport` subclass | SDK docs mark `Transport` ABC as "low-level internal API whose interface may change." Don't implement custom transports. |
| `anyio` as direct import | SDK's internal dependency. Let it stay transitive. Don't couple nanobot code to anyio. |

## Installation

```toml
# pyproject.toml -- add as optional dependency
[project.optional-dependencies]
bypass = [
    "claude-agent-sdk>=0.1.56,<0.2.0",
]
```

```bash
# Install with bypass support
uv add "nanobot[bypass]"
# OR
pip install "nanobot[bypass]"
```

**Why optional:** Not all users need bypass mode. The SDK adds ~50MB (bundled CLI + Node.js modules), requires Node.js 18+ on the system, and is alpha (0.1.x). Isolating it as an optional extra limits blast radius.

**User prerequisite (if NOT using SDK-bundled CLI):**
```bash
# Install Claude Code CLI globally
npm install -g @anthropic-ai/claude-code

# Authenticate interactively (one-time)
claude
# Follow login prompts

# Verify
claude auth status
```

**SDK-bundled CLI note:** The SDK bundles its own CLI binary. To use the user's system-installed `claude` (which has their subscription login), set:
```python
ClaudeAgentOptions(cli_path="/path/to/system/claude")
```
This is important for subscription auth -- the bundled CLI may not have the user's login credentials.

## Provider Integration Pattern

The bypass provider fits as a new `LLMProvider` subclass. Key mapping:

| Nanobot Interface | SDK Equivalent |
|-------------------|-----------------------------|
| `LLMProvider.chat()` | `query()` collecting `ResultMessage.result` |
| `LLMProvider.chat_stream()` | `query()` with `include_partial_messages=True`, calling `on_content_delta` per `TextBlock` |
| `LLMResponse.content` | `ResultMessage.result` or assembled `TextBlock.text` from `AssistantMessage` messages |
| `LLMResponse.tool_calls` | NOT applicable -- Claude Code executes tools internally; nanobot receives final result only |
| `LLMResponse.usage` | `ResultMessage.usage` dict (`input_tokens`, `output_tokens`, `cache_*`) |
| `LLMResponse.finish_reason` | Map `ResultMessage.subtype`: "success" -> "stop", "error_during_execution" -> "error" |
| Session continuity | Save `ResultMessage.session_id` per nanobot session key; pass as `resume` on next call |

### Critical Architecture Note: Tool Execution

In bypass mode, Claude Code runs its OWN tools (Read, Edit, Bash, etc.) internally. Nanobot's `ToolRegistry` is NOT used. This is fundamentally different from other providers where nanobot receives `ToolCallRequest` objects and executes them via `AgentRunner`.

In bypass mode: **prompt in -> final result out**. All tool execution happens inside the CLI subprocess.

This means `LLMResponse.tool_calls` will always be empty. The `AgentRunner` tool loop is bypassed entirely. The provider returns a complete response, not intermediate tool call requests.

## Dependency Impact

| Metric | Value |
|--------|-------|
| New direct dependencies | 1 (`claude-agent-sdk`) |
| Transitive dependencies | `anyio>=4.0`, `sniffio` |
| Install size impact | ~50MB (bundled CLI binary + Node.js modules) |
| Python version impact | None (SDK >=3.10, project >=3.11) |
| Breaking change risk | HIGH -- SDK is alpha (0.1.x), API may change |
| Node.js requirement | Node.js 18+ must be available at runtime |

## Confidence Assessment

| Recommendation | Confidence | Rationale |
|----------------|------------|-----------|
| Use `claude-agent-sdk` | HIGH | Official package, actively maintained, documented API |
| `query()` for one-shot | HIGH | Well-documented, simple pattern, maps to LLMProvider |
| `ClaudeSDKClient` for sessions | MEDIUM | API is stable but lifecycle management adds complexity |
| Subscription auth via SDK | LOW | Community workaround only; not officially supported |
| Raw subprocess fallback | HIGH | Standard asyncio pattern, always works with CLI login |
| Optional dependency strategy | HIGH | Isolates alpha SDK risk, reduces default install size |
| `--bare` for startup speed | HIGH | Officially recommended for scripted/SDK calls |

## Sources

- [Run Claude Code Programmatically](https://code.claude.com/docs/en/headless) -- Official docs on `-p` flag, `--bare`, CLI options (HIGH confidence)
- [Agent SDK Overview](https://code.claude.com/docs/en/agent-sdk/overview) -- Architecture, capabilities, comparison with Client SDK (HIGH confidence)
- [Agent SDK Python Reference](https://code.claude.com/docs/en/agent-sdk/python) -- Full API: `query()`, `ClaudeSDKClient`, `ClaudeAgentOptions`, message types, hooks, tools, error handling (HIGH confidence)
- [claude-agent-sdk on PyPI](https://pypi.org/project/claude-agent-sdk/) -- v0.1.58, Python >=3.10, alpha status (HIGH confidence)
- [claude-code-sdk on PyPI](https://pypi.org/project/claude-code-sdk/) -- Deprecated v0.0.25, renamed to claude-agent-sdk (HIGH confidence)
- [GitHub Issue #559: SDK Max plan billing](https://github.com/anthropics/claude-agent-sdk-python/issues/559) -- Subscription auth workaround via `CLAUDE_CODE_OAUTH_TOKEN` (LOW confidence)
- [GitHub Issue #24594: --input-format stream-json](https://github.com/anthropics/claude-code/issues/24594) -- Undocumented bidirectional protocol (MEDIUM confidence)
- [Inside the Claude Agent SDK: stdin/stdout Communication](https://buildwithaws.substack.com/p/inside-the-claude-agent-sdk-from) -- Transport internals: anyio, JSON-lines, 1MB buffer (MEDIUM confidence)
- [Python asyncio subprocess docs](https://docs.python.org/3/library/asyncio-subprocess.html) -- Fallback approach reference (HIGH confidence)
- [AnyIO subprocess docs](https://anyio.readthedocs.io/en/stable/subprocesses.html) -- SDK internal transport library (HIGH confidence)

---

*Stack analysis: 2026-04-09*
