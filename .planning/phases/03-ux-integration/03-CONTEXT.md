# Phase 3: UX Integration - Context

**Gathered:** 2026-04-09
**Status:** Ready for planning

<domain>
## Phase Boundary

Add user-facing configuration and activation for the Claude Code bypass mode: persona passthrough toggle, output verbosity control, `--bypass` CLI flag, and interactive provider picker menu entry.

</domain>

<decisions>
## Implementation Decisions

### Persona Passthrough
- **D-01:** Use `--append-system-prompt "<persona>"` CLI flag to inject nanobot's active persona into Claude Code without overriding its own system prompt
- **D-02:** Config field `persona_passthrough: bool` on `ClaudeCodeProviderConfig` (default: `false` — raw Claude Code by default)
- **D-03:** When enabled, extract the system prompt from `ContextBuilder.build_messages()` output and pass it via `--append-system-prompt`
- **D-04:** Add to `_build_command()` conditionally based on config + per-session override

### Output Verbosity Control
- **D-05:** Config field `output_verbosity: str` on `ClaudeCodeProviderConfig` with values `"full"`, `"final"`, `"summarized"` (default: `"full"`)
- **D-06:** In `"full"` mode: return entire `result` field from Claude Code JSON as-is
- **D-07:** In `"final"` mode: strip tool call descriptions, return only the final text response
- **D-08:** In `"summarized"` mode: include brief one-line summaries of tool actions (e.g., "Edited file.py") followed by the final response
- **D-09:** Filtering happens in `_parse_result()` — the provider already parses JSON output

### CLI Flag
- **D-10:** Add `--bypass` option to `nanobot chat` typer command that sets provider to `claude_code` for that session
- **D-11:** Flag is a `typer.Option(False, "--bypass", help="Route through Claude Code CLI")` boolean
- **D-12:** When active, overrides whatever provider is configured — no config file change needed

### Menu Integration
- **D-13:** Add "Claude Code (Bypass)" to the interactive provider picker in `_configure_providers()` (or equivalent flow in `nanobot/cli/commands.py`)
- **D-14:** Selection sets `providers.claude_code` in config with sensible defaults
- **D-15:** Show Claude Code CLI availability status (installed/not installed) next to the option

### Claude's Discretion
- Exact persona extraction logic from ContextBuilder output
- Summarized mode formatting (one-line tool action descriptions)
- Provider picker UI wording and ordering

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Provider Implementation
- `nanobot/providers/claude_code_provider.py` — Provider to extend with persona + verbosity
- `nanobot/providers/base.py` — LLMProvider ABC, chat() signature
- `nanobot/config/schema.py` — ClaudeCodeProviderConfig to extend

### CLI
- `nanobot/cli/commands.py` — `chat` command, `_make_provider()`, `_configure_providers()` interactive flow
- `nanobot/agent/context.py` — ContextBuilder.build_messages() for persona extraction

### Tests
- `tests/providers/test_claude_code_provider.py` — Extend with persona + verbosity tests

### Research
- `.planning/research/STACK.md` — Claude Code CLI flags (--append-system-prompt)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `ClaudeCodeProvider._build_command()` — Extend to add `--append-system-prompt` conditionally
- `ClaudeCodeProvider._parse_result()` — Extend with verbosity filtering
- `ContextBuilder.build_messages()` — System prompt is the first message in the returned list
- `_configure_providers()` in commands.py — Interactive provider setup with questionary

### Established Patterns
- Typer options follow `typer.Option(default, "--flag", help="...")` pattern
- Config fields use pydantic with env var support
- Interactive config uses `questionary.select()` for choices

### Integration Points
- `nanobot/cli/commands.py` chat command — add `--bypass` parameter
- `nanobot/cli/commands.py` _configure_providers — add Claude Code option
- `ClaudeCodeProvider.__init__()` — accept persona_passthrough and output_verbosity config
- `ClaudeCodeProvider._build_command()` — conditional `--append-system-prompt`
- `ClaudeCodeProvider._parse_result()` — verbosity-based filtering

</code_context>

<specifics>
## Specific Ideas

- The `--bypass` flag should feel like a shortcut — just one flag and you're using Claude Code
- Provider picker should make it clear this requires Claude Code CLI installed
- Persona passthrough defaults to off — most users want raw Claude Code behavior in bypass mode

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 03-ux-integration*
*Context gathered: 2026-04-09*
