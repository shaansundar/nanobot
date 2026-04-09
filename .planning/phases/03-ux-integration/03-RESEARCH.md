# Phase 3: UX Integration - Research

**Researched:** 2026-04-09
**Domain:** CLI UX, provider configuration, system prompt injection, output filtering
**Confidence:** HIGH

## Summary

Phase 3 adds four user-facing capabilities to the Claude Code bypass provider: persona passthrough via `--append-system-prompt`, output verbosity filtering in `_parse_result()`, a `--bypass` CLI flag on the `agent` command, and a "Claude Code (Bypass)" entry in the interactive provider picker.

The existing codebase provides strong integration points. `ClaudeCodeProvider._build_command()` can be extended to conditionally append `--append-system-prompt`. `_parse_result()` already parses the JSON output and can filter the `result` field based on a verbosity setting. The `agent` command in `commands.py` already uses `typer.Option` patterns identical to what `--bypass` needs. The interactive provider picker in `onboard.py` needs defensive handling for `ClaudeCodeProviderConfig` which lacks the `api_key` attribute that `_configure_providers()` assumes all providers have.

**Primary recommendation:** Implement each requirement as a focused change to existing integration points -- `_build_command()` for persona, `_parse_result()` for verbosity, `agent()` for `--bypass`, and `_configure_providers()` for the menu entry. All changes are additive with no breaking changes to existing behavior.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Use `--append-system-prompt "<persona>"` CLI flag to inject nanobot's active persona into Claude Code without overriding its own system prompt
- **D-02:** Config field `persona_passthrough: bool` on `ClaudeCodeProviderConfig` (default: `false` -- raw Claude Code by default)
- **D-03:** When enabled, extract the system prompt from `ContextBuilder.build_messages()` output and pass it via `--append-system-prompt`
- **D-04:** Add to `_build_command()` conditionally based on config + per-session override
- **D-05:** Config field `output_verbosity: str` on `ClaudeCodeProviderConfig` with values `"full"`, `"final"`, `"summarized"` (default: `"full"`)
- **D-06:** In `"full"` mode: return entire `result` field from Claude Code JSON as-is
- **D-07:** In `"final"` mode: strip tool call descriptions, return only the final text response
- **D-08:** In `"summarized"` mode: include brief one-line summaries of tool actions (e.g., "Edited file.py") followed by the final response
- **D-09:** Filtering happens in `_parse_result()` -- the provider already parses JSON output
- **D-10:** Add `--bypass` option to `nanobot agent` typer command (note: the actual command is `agent`, not `chat` -- see Architecture Patterns section) that sets provider to `claude_code` for that session
- **D-11:** Flag is a `typer.Option(False, "--bypass", help="Route through Claude Code CLI")` boolean
- **D-12:** When active, overrides whatever provider is configured -- no config file change needed
- **D-13:** Add "Claude Code (Bypass)" to the interactive provider picker in `_configure_providers()` in `nanobot/cli/onboard.py`
- **D-14:** Selection sets `providers.claude_code` in config with sensible defaults
- **D-15:** Show Claude Code CLI availability status (installed/not installed) next to the option

### Claude's Discretion
- Exact persona extraction logic from ContextBuilder output
- Summarized mode formatting (one-line tool action descriptions)
- Provider picker UI wording and ordering

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| UX-01 | User can choose to pass nanobot's active persona/system prompt to Claude Code or run raw | `--append-system-prompt` flag confirmed in official CLI docs; `ContextBuilder.build_messages()` returns system prompt as first message; `_build_command()` is the integration point |
| UX-02 | User can choose output verbosity: full tool output, final response only, or summarized actions | `_parse_result()` receives the full JSON `result` field; Claude Code's `result` field contains the complete text including tool action descriptions; filtering is string processing on existing data |
| UX-03 | User can activate bypass mode via `--bypass` CLI flag | The `agent` command (not `chat`) is the interactive CLI entry; `_make_provider()` already has `claude_code` backend branch; `typer.Option` pattern established |
| UX-04 | "Claude Code (Bypass)" appears as an option in nanobot's interactive provider picker menu | `_configure_providers()` in `onboard.py` already lists all non-OAuth providers; `claude_code` spec passes the filter but `ClaudeCodeProviderConfig` lacks `api_key` causing an AttributeError that must be fixed |
</phase_requirements>

## Standard Stack

### Core (Existing -- No New Dependencies)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| typer | >=0.20.0 | CLI `--bypass` flag | Already used for all CLI options |
| pydantic | >=2.12.0 | `ClaudeCodeProviderConfig` field additions | Already used for all config schema |
| questionary | >=2.0.0 | Interactive provider picker | Already used in onboard wizard |
| rich | >=14.0.0 | Console output for status indicators | Already used for all CLI output |
| shutil | stdlib | `shutil.which("claude")` for CLI detection | Already used by provider constructor |

### Supporting (No New Dependencies)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| re | stdlib | Regex for output verbosity filtering | Parsing tool action patterns from `result` text |
| loguru | >=0.7.3 | Debug logging for persona injection | Already used throughout provider |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `--append-system-prompt` flag | `--system-prompt` (replace) | Replacement loses Claude Code's built-in capabilities; append preserves them (official docs recommend append for most use cases) |
| String regex for verbosity filtering | Structured JSON parsing | Claude Code `--output-format json` only returns a `result` string, not structured tool call data; regex is the only option for non-streaming mode |
| `hasattr` guard for api_key | Union type config | `hasattr` is simpler and follows existing codebase patterns; Union type adds complexity |

**Installation:** No new packages needed. All requirements met by existing dependencies.

## Architecture Patterns

### Critical Discovery: Command Name Mismatch

The CONTEXT.md references `nanobot chat --bypass`, but the actual CLI command is `nanobot agent`. There is no `chat` command in the codebase. The `agent` command at line 871 of `commands.py` is the interactive chat interface. The `--bypass` flag MUST be added to the `agent` command function.

### Recommended Changes Structure

```
nanobot/config/schema.py        # Add persona_passthrough, output_verbosity to ClaudeCodeProviderConfig
nanobot/providers/claude_code_provider.py  # Extend __init__, _build_command, _parse_result
nanobot/cli/commands.py          # Add --bypass to agent(), modify _make_provider() call path
nanobot/cli/onboard.py           # Fix _configure_providers() for ClaudeCodeProviderConfig
tests/providers/test_claude_code_provider.py  # Extend with persona + verbosity + bypass tests
tests/cli/test_commands.py       # Add --bypass flag tests (if not covered elsewhere)
```

### Pattern 1: Config Field Extension (D-02, D-05)

**What:** Add two fields to `ClaudeCodeProviderConfig` in `schema.py`.
**When to use:** When adding provider-specific settings.
**Example:**
```python
# Source: nanobot/config/schema.py existing pattern
class ClaudeCodeProviderConfig(Base):
    """Configuration for Claude Code CLI bypass provider."""
    cli_path: str = ""
    session_mode: str = "session"
    persona_passthrough: bool = False  # UX-01
    output_verbosity: str = "full"     # UX-02: "full" | "final" | "summarized"
```

### Pattern 2: Conditional CLI Flag Injection (D-01, D-04)

**What:** `_build_command()` conditionally adds `--append-system-prompt` with persona text.
**When to use:** When a provider-level config flag controls CLI argument generation.
**Example:**
```python
# Source: nanobot/providers/claude_code_provider.py existing _build_command pattern
def _build_command(
    self,
    prompt: str,
    session_id: str | None = None,
    no_session_persistence: bool = False,
    system_prompt: str | None = None,  # NEW: persona injection
) -> list[str]:
    cmd = [self._cli_path, "-p", "--output-format", "json", "--setting-sources", ""]
    if session_id:
        cmd.extend(["--resume", session_id])
    if no_session_persistence:
        cmd.append("--no-session-persistence")
    if system_prompt:
        cmd.extend(["--append-system-prompt", system_prompt])
    cmd.append(prompt)
    return cmd
```

### Pattern 3: Provider Override via CLI Flag (D-10, D-12)

**What:** `--bypass` flag on `agent()` overrides the provider to `claude_code` before `_make_provider()`.
**When to use:** When a CLI flag should temporarily override config-level provider selection.
**Example:**
```python
# Source: nanobot/cli/commands.py agent() function pattern
@app.command()
def agent(
    # ... existing params ...
    bypass: bool = typer.Option(False, "--bypass", help="Route through Claude Code CLI"),
):
    config = _load_runtime_config(config, workspace)
    if bypass:
        config.agents.defaults.provider = "claude_code"
        config.agents.defaults.model = "claude_code/claude-sonnet-4-20250514"
    # ... rest unchanged, _make_provider(config) picks up override ...
```

### Pattern 4: Defensive Attribute Access for Mixed Config Types (D-13)

**What:** Guard `api_key` access in `_configure_providers()` since `ClaudeCodeProviderConfig` has no `api_key`.
**When to use:** When iterating over providers with heterogeneous config types.
**Example:**
```python
# Source: nanobot/cli/onboard.py _configure_providers pattern
def get_provider_choices() -> list[str]:
    choices = []
    for name, display in _get_provider_names().items():
        provider = getattr(config.providers, name, None)
        if provider and hasattr(provider, "api_key") and provider.api_key:
            choices.append(f"{display} *")
        elif provider and hasattr(provider, "cli_path"):
            # Claude Code: check CLI availability
            import shutil
            cli_available = bool(shutil.which("claude"))
            status = "installed" if cli_available else "not installed"
            choices.append(f"{display} ({status})")
        else:
            choices.append(display)
    return choices + ["<- Back"]
```

### Pattern 5: System Prompt Extraction from ContextBuilder (D-03)

**What:** Extract persona from `ContextBuilder.build_messages()` output for injection.
**When to use:** When the provider needs the nanobot persona/system prompt.
**Example:**
```python
# Source: nanobot/agent/context.py ContextBuilder.build_messages() (line 135-136)
# The system prompt is always the FIRST message with role="system"
messages = [
    {"role": "system", "content": self.build_system_prompt(skill_names, channel=channel)},
    *history,
]
# Extraction in provider or caller:
system_prompt = messages[0]["content"] if messages and messages[0].get("role") == "system" else None
```

### Anti-Patterns to Avoid

- **Modifying config on disk for --bypass:** The flag is session-scoped. Mutate the in-memory config object only, never write it back.
- **Replacing system prompt instead of appending:** `--system-prompt` replaces Claude Code's built-in prompt. Use `--append-system-prompt` to preserve built-in capabilities.
- **Hard-coding tool action patterns in verbosity filter:** Claude Code's output format may change. Use loose pattern matching, not rigid parsing.
- **Accessing .api_key without hasattr guard:** `ClaudeCodeProviderConfig` does not inherit from `ProviderConfig` and has no `api_key`. Always guard with `hasattr`.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| CLI argument construction | Custom shell escaping for system prompt | Python list args to `create_subprocess_exec` | `create_subprocess_exec` handles argument passing safely; no shell injection risk |
| Provider detection in picker | Custom file-exists check | `shutil.which("claude")` | Standard library, handles PATH resolution, cross-platform |
| Config field validation | Manual value checking | Pydantic `Literal` type for output_verbosity | `Literal["full", "final", "summarized"]` gives automatic validation at config load time |
| System prompt extraction | Custom message parsing | Check `messages[0]["role"] == "system"` | ContextBuilder always puts system as first message (line 135-136 of context.py) |

**Key insight:** All integration points already exist in the codebase. This phase is purely additive extension of existing patterns.

## Common Pitfalls

### Pitfall 1: AttributeError on provider.api_key for ClaudeCodeProviderConfig

**What goes wrong:** `_configure_providers()` (onboard.py:707) and `status()` (commands.py:1322) access `provider.api_key` on all provider configs. `ClaudeCodeProviderConfig` does not have this field.
**Why it happens:** `ClaudeCodeProviderConfig` extends `Base` (not `ProviderConfig`), so it has `cli_path` and `session_mode` but no `api_key`/`api_base`.
**How to avoid:** Use `hasattr(provider, "api_key")` before accessing, or check the spec's `is_direct` flag.
**Warning signs:** `AttributeError: 'ClaudeCodeProviderConfig' object has no attribute 'api_key'` when opening the provider picker or running `nanobot status`.

### Pitfall 2: Command Name is `agent`, Not `chat`

**What goes wrong:** CONTEXT.md references `nanobot chat --bypass`. No `chat` command exists.
**Why it happens:** The interactive CLI command is registered as `agent` (line 871-872 of commands.py).
**How to avoid:** Add `--bypass` to the `agent` function definition. If desired, add a `chat` alias or clarify in docs that the command is `nanobot agent --bypass`.
**Warning signs:** User runs `nanobot chat --bypass` and gets "No such command 'chat'".

### Pitfall 3: Shell Quoting of System Prompt in --append-system-prompt

**What goes wrong:** If the system prompt contains quotes, newlines, or special characters, it could break the CLI invocation.
**Why it happens:** `asyncio.create_subprocess_exec` passes arguments as a list, NOT through a shell. Each list element is a separate argument.
**How to avoid:** Since the codebase uses `create_subprocess_exec` (not `create_subprocess_shell`), the prompt is passed as a single argv element. No shell escaping needed. The prompt can contain any characters.
**Warning signs:** This is a non-issue with the current implementation but would be critical if anyone switches to shell execution.

### Pitfall 4: Verbosity Filtering Fragility

**What goes wrong:** The `result` field from Claude Code JSON contains free-form text. Regex patterns for extracting "tool actions" vs "final response" may break across Claude Code versions.
**Why it happens:** Claude Code's `result` field format is not formally specified. Tool action descriptions are embedded inline.
**How to avoid:** Implement `"final"` mode conservatively (e.g., take the last paragraph/block after the last tool reference). Implement `"summarized"` mode as a best-effort extraction. Default to `"full"` which has zero risk.
**Warning signs:** Test with real Claude Code output to validate patterns.

### Pitfall 5: _get_provider_info LRU Cache Invalidation

**What goes wrong:** `_get_provider_info()` is decorated with `@lru_cache(maxsize=1)`. If the function is modified to include dynamic state (like CLI availability), the cache will return stale data.
**Why it happens:** `shutil.which("claude")` check is dynamic, but `lru_cache` memoizes the result forever.
**How to avoid:** Either (a) check CLI availability outside of `_get_provider_info()`, in `get_provider_choices()` where it's called dynamically, or (b) don't cache the CLI-availability check.
**Warning signs:** User installs `claude` after opening the picker, but the picker still shows "not installed".

## Code Examples

### Example 1: Provider Construction with Persona (D-01, D-03, D-04)

```python
# In ClaudeCodeProvider.__init__, accept new config fields
def __init__(
    self,
    cli_path: str | None = None,
    default_model: str = _DEFAULT_MODEL,
    persona_passthrough: bool = False,
    output_verbosity: str = "full",
) -> None:
    super().__init__(api_key=None, api_base=None)
    self._cli_path = cli_path or shutil.which("claude") or ""
    if not self._cli_path:
        raise RuntimeError(_CLI_NOT_FOUND_MESSAGE)
    self._default_model = default_model
    self._persona_passthrough = persona_passthrough
    self._output_verbosity = output_verbosity
    # ... session state ...
```

### Example 2: System Prompt Extraction in chat() (D-03)

```python
# In ClaudeCodeProvider.chat(), extract system prompt from messages
async def chat(self, messages, ...):
    prompt = self._extract_latest_user_content(messages)

    # Extract system prompt if persona passthrough enabled
    system_prompt = None
    if self._persona_passthrough:
        for msg in messages:
            if msg.get("role") == "system":
                system_prompt = msg.get("content")
                break

    cmd = self._build_command(
        prompt,
        session_id=session_id,
        no_session_persistence=no_persist,
        system_prompt=system_prompt,
    )
    # ...
```

### Example 3: Verbosity Filtering in _parse_result() (D-06, D-07, D-08)

```python
# In _parse_result, after extracting result_text:
result_text = data.get("result", "") or ""

if self._output_verbosity == "final":
    result_text = self._strip_tool_descriptions(result_text)
elif self._output_verbosity == "summarized":
    result_text = self._summarize_tool_actions(result_text)
# "full" mode: no filtering, result_text used as-is
```

### Example 4: --bypass Flag on agent Command (D-10, D-11, D-12)

```python
# In commands.py agent() function signature
@app.command()
def agent(
    message: str = typer.Option(None, "--message", "-m", help="Message to send"),
    session_id: str = typer.Option("cli:direct", "--session", "-s", help="Session ID"),
    workspace: str | None = typer.Option(None, "--workspace", "-w", help="Workspace directory"),
    config: str | None = typer.Option(None, "--config", "-c", help="Config file path"),
    markdown: bool = typer.Option(True, "--markdown/--no-markdown", help="Render as Markdown"),
    logs: bool = typer.Option(False, "--logs/--no-logs", help="Show runtime logs"),
    bypass: bool = typer.Option(False, "--bypass", help="Route through Claude Code CLI"),
):
    config = _load_runtime_config(config, workspace)
    if bypass:
        config.agents.defaults.provider = "claude_code"
        config.agents.defaults.model = "claude_code/claude-sonnet-4-20250514"
    # ... rest of function unchanged
```

### Example 5: CLI Availability in Provider Picker (D-13, D-15)

```python
# In onboard.py, modify get_provider_choices within _configure_providers
def get_provider_choices() -> list[str]:
    choices = []
    for name, display in _get_provider_names().items():
        provider = getattr(config.providers, name, None)
        if not provider:
            choices.append(display)
            continue
        # ClaudeCodeProviderConfig has no api_key
        if hasattr(provider, "api_key"):
            if provider.api_key:
                choices.append(f"{display} *")
            else:
                choices.append(display)
        else:
            # is_direct provider (Claude Code) -- show CLI status
            import shutil
            cli_ok = bool(shutil.which("claude"))
            tag = "installed" if cli_ok else "not installed"
            choices.append(f"{display} ({tag})")
    return choices + ["<- Back"]
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `--system-prompt` (replace) | `--append-system-prompt` (preserve default) | Claude Code docs current | Append preserves Claude Code's built-in SWE capabilities |
| `--bare` flag | `--setting-sources ""` | Phase 1 discovery | Preserves subscription OAuth keychain auth; `--bare` breaks Max/Pro login |

**Deprecated/outdated:**
- `--bare`: Breaks subscription auth. Phase 1 established `--setting-sources ""` as the standard.
- `claude-code-sdk`: Renamed to `claude-agent-sdk`. Not relevant to Phase 3 (raw subprocess approach already implemented in Phase 1).

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest >=9.0.0 with pytest-asyncio >=1.3.0 |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run command | `python -m pytest tests/providers/test_claude_code_provider.py -x -q` |
| Full suite command | `python -m pytest tests/ -x -q` |

### Phase Requirements to Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| UX-01 | persona_passthrough config field; --append-system-prompt in command | unit | `python -m pytest tests/providers/test_claude_code_provider.py -x -k "persona"` | No -- Wave 0 |
| UX-01 | System prompt extracted from messages when passthrough enabled | unit | `python -m pytest tests/providers/test_claude_code_provider.py -x -k "system_prompt"` | No -- Wave 0 |
| UX-02 | output_verbosity "full" returns result as-is | unit | `python -m pytest tests/providers/test_claude_code_provider.py -x -k "verbosity_full"` | No -- Wave 0 |
| UX-02 | output_verbosity "final" strips tool descriptions | unit | `python -m pytest tests/providers/test_claude_code_provider.py -x -k "verbosity_final"` | No -- Wave 0 |
| UX-02 | output_verbosity "summarized" provides action summaries | unit | `python -m pytest tests/providers/test_claude_code_provider.py -x -k "verbosity_summarized"` | No -- Wave 0 |
| UX-03 | --bypass flag creates ClaudeCodeProvider | unit | `python -m pytest tests/cli/test_commands.py -x -k "bypass"` | No -- Wave 0 |
| UX-04 | Provider picker shows Claude Code with availability status | unit | `python -m pytest tests/cli/test_onboard.py -x -k "claude_code_picker"` | No -- Wave 0 (file may need creation) |

### Sampling Rate

- **Per task commit:** `python -m pytest tests/providers/test_claude_code_provider.py -x -q`
- **Per wave merge:** `python -m pytest tests/ -x -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] Tests for persona passthrough in `test_claude_code_provider.py` -- covers UX-01
- [ ] Tests for output verbosity filtering in `test_claude_code_provider.py` -- covers UX-02
- [ ] Tests for `--bypass` CLI flag in `tests/cli/test_commands.py` -- covers UX-03
- [ ] Tests for provider picker Claude Code entry -- covers UX-04

## Open Questions

1. **Verbosity filtering: What does Claude Code's `result` field actually look like with tool actions?**
   - What we know: The `result` field is a plain string. In the test fixtures, it's just `"hello world"`.
   - What's unclear: Real Claude Code output with tool calls may contain multi-line descriptions like "I read file X and found Y, then edited Z." The exact format varies.
   - Recommendation: Implement `"final"` mode conservatively -- split on known separator patterns or take the last significant paragraph. `"summarized"` mode should use regex to identify action verbs (read, edited, wrote, ran, searched) and file paths. Test with real CLI output during implementation.

2. **Should `--bypass` also be available on the `serve` and `gateway` commands?**
   - What we know: The CONTEXT only specifies adding it to the chat command (which is `agent`).
   - What's unclear: Whether server-mode users also need a quick bypass toggle.
   - Recommendation: Start with `agent` only per CONTEXT. Defer `serve`/`gateway` until requested.

3. **Provider picker: Should selecting Claude Code open a sub-config for persona/verbosity?**
   - What we know: D-14 says "selection sets `providers.claude_code` in config with sensible defaults."
   - What's unclear: Whether the picker should also offer persona_passthrough and output_verbosity configuration, or just set defaults.
   - Recommendation: Set sensible defaults on selection. If the user wants to tweak persona/verbosity, they edit `config.json` directly. Keep the picker simple.

## Sources

### Primary (HIGH confidence)
- [Claude Code CLI Reference](https://code.claude.com/docs/en/cli-reference) -- Confirmed `--append-system-prompt` flag, `--output-format json`, all system prompt flags
- Codebase files: `nanobot/providers/claude_code_provider.py`, `nanobot/cli/commands.py`, `nanobot/cli/onboard.py`, `nanobot/config/schema.py`, `nanobot/agent/context.py`
- `.planning/research/STACK.md` -- CLI flags reference, JSON output schema

### Secondary (MEDIUM confidence)
- [Claude Code System Prompt Clarification (GitHub Issue #6973)](https://github.com/anthropics/claude-code/issues/6973) -- `--append-system-prompt` vs CLAUDE.md interaction

### Tertiary (LOW confidence)
- Verbosity filtering patterns -- no official documentation on `result` field format with tool actions; based on observed CLI output patterns

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all existing dependencies, no new packages
- Architecture: HIGH -- all integration points identified, patterns verified in codebase
- Pitfalls: HIGH -- five concrete issues identified with code-level evidence
- Verbosity filtering: MEDIUM -- `result` field format not formally documented

**Research date:** 2026-04-09
**Valid until:** 2026-05-09 (stable -- all integration points are in the existing codebase)
