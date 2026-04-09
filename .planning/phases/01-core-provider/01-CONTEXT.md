# Phase 1: Core Provider - Context

**Gathered:** 2026-04-09
**Status:** Ready for planning

<domain>
## Phase Boundary

Implement a new LLM provider (`ClaudeCodeProvider`) that sends prompts to Claude Code CLI via subprocess and returns responses. Register it in nanobot's provider system so users can select it like any other provider. Validate that the CLI is available and surface errors clearly.

</domain>

<decisions>
## Implementation Decisions

### Transport Mechanism
- **D-01:** Use raw `asyncio.create_subprocess_exec` to call the user's system-installed `claude` binary — not the `claude-agent-sdk` package
- **D-02:** Always use list args (never `shell=True`) to prevent shell injection
- **D-03:** Always set `stdin=asyncio.subprocess.DEVNULL` to prevent TTY hang (GitHub #9026)
- **D-04:** Drain stdout and stderr concurrently via separate async tasks to prevent pipe buffer deadlock

### Auth Strategy
- **D-05:** Use the user's system-installed `claude` binary which inherits their existing subscription login — no API key required for this provider
- **D-06:** Do not use `claude-agent-sdk` or `CLAUDE_CODE_OAUTH_TOKEN` workaround — subscription auth via SDK is undocumented and LOW confidence
- **D-07:** CLI path configurable via config (`claude_code.cli_path`, default: `claude` from PATH)

### CLI Invocation Flags
- **D-08:** Always pass `--bare` to skip hooks/MCP/CLAUDE.md discovery — reduces per-turn token overhead from ~50K to ~5K
- **D-09:** Use `-p` flag for non-interactive (print) mode
- **D-10:** Use `--output-format json` for structured response parsing
- **D-11:** Pass the user's prompt as the positional argument to `claude -p`

### Error Detection
- **D-12:** Three-channel error detection: exit code (non-zero = error), stdout JSON (parse `result` field), stderr text (capture for diagnostics)
- **D-13:** Map CLI errors to `LLMResponse(finish_reason="error")` with `error_kind`, `error_status_code`, `error_type` fields — consistent with existing provider error model
- **D-14:** Check for `claude` binary at startup using `shutil.which()` — fail with clear install instructions if missing

### Provider Registration
- **D-15:** Add `ProviderSpec(name="claude_code", backend="claude_code", ...)` to the `PROVIDERS` tuple in `nanobot/providers/registry.py`
- **D-16:** Create `nanobot/providers/claude_code_provider.py` implementing `LLMProvider` ABC
- **D-17:** Provider returns `LLMResponse(content=..., tool_calls=[])` — tool_calls always empty because Claude Code handles tools internally (Agent Proxy architecture)
- **D-18:** Add config field to `ProvidersConfig` in `nanobot/config/schema.py`

### Claude's Discretion
- Exact error message wording for CLI-not-found and auth-failure cases
- Whether to validate auth status at startup vs first use
- Internal structure of the provider class (helper methods, etc.)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Provider System
- `nanobot/providers/base.py` — LLMProvider ABC, LLMResponse dataclass, retry logic
- `nanobot/providers/registry.py` — ProviderSpec dataclass, PROVIDERS tuple, adding a new provider instructions in docstring
- `nanobot/config/schema.py` — ProvidersConfig pydantic model, config field patterns

### Existing Provider Examples
- `nanobot/providers/openai_codex_provider.py` — OAuth-based provider pattern (closest to bypass — no API key, subprocess-like)
- `nanobot/providers/github_copilot_provider.py` — Another OAuth-based provider for reference
- `nanobot/providers/anthropic_provider.py` — Direct Anthropic SDK provider (what bypass replaces)

### CLI Integration
- `nanobot/cli/commands.py` — CLI commands, provider selection, `chat` command entry point
- `nanobot/agent/runner.py` — AgentRunner that calls provider.chat_stream() and handles tool_calls

### Research
- `.planning/research/STACK.md` — Claude Code CLI flags reference, SDK analysis
- `.planning/research/ARCHITECTURE.md` — Agent Proxy architecture decision, data flow
- `.planning/research/PITFALLS.md` — Process lifecycle, pipe deadlock, security pitfalls

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `LLMProvider` ABC in `nanobot/providers/base.py`: Subclass and implement `chat()` and `chat_stream()`
- `ProviderSpec` in `nanobot/providers/registry.py`: Copy-paste template pattern for adding new providers
- `LLMResponse` dataclass: Standardized response format; use `finish_reason="error"` for CLI errors
- Retry logic in `LLMProvider._run_with_retry()`: May need to be skipped or adapted since CLI has its own retry behavior

### Established Patterns
- All providers implement `chat()` (sync-style) and optionally `chat_stream()` (async generator)
- Provider construction: `if backend == "xxx":` branch in CLI commands creates the provider instance
- Error handling: `_safe_chat` / `_safe_chat_stream` wrappers convert exceptions to `LLMResponse(finish_reason="error")`
- Naming: `snake_case` files, `PascalCase` classes, `_` prefix for private methods

### Integration Points
- `nanobot/providers/registry.py` PROVIDERS tuple — add new ProviderSpec entry
- `nanobot/config/schema.py` ProvidersConfig — add config field
- `nanobot/cli/commands.py` — add `elif backend == "claude_code":` branch for provider instantiation

</code_context>

<specifics>
## Specific Ideas

- User specifically requested a bash/zsh script as intermediary — implementation should support optional script path in config
- Side-by-side with existing providers — "Claude Code (Bypass)" as an additional option, not a replacement
- Agent Proxy architecture — Claude Code is the sole tool authority; nanobot receives final results only

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 01-core-provider*
*Context gathered: 2026-04-09*
