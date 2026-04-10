# Feature Landscape

**Domain:** CLI-based LLM provider proxy (Claude Code CLI bypass for subscription users)
**Researched:** 2026-04-09

## Table Stakes

Features users expect. Missing = product feels incomplete.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Send prompt, get response | Core function of a provider | Low | `claude -p` with --output-format stream-json |
| Text streaming | All other nanobot providers stream; inconsistency is jarring | Medium | Parse text_delta events from stream-json |
| Tool use passthrough | Nanobot's key feature is its agent loop with tools; losing it defeats the purpose | Medium | CLI returns tool_call suggestions; nanobot's AgentRunner executes them |
| Provider selection in config | Must be selectable like any other provider; not a hidden hack | Low | ProviderSpec entry + config field + backend switch |
| Error propagation | Users need to know why something failed (auth, rate limit, CLI missing) | Medium | Map CLI errors to LLMResponse error fields |
| CLI availability check | Must fail clearly if claude binary not installed or not authenticated | Low | shutil.which + auth status check at startup |

## Differentiators

Features that set product apart. Not expected, but valued.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Session continuity via --resume | Multi-turn conversations keep full Claude Code context; avoids re-processing history | Medium | Map nanobot session keys to Claude Code session IDs |
| Persona passthrough toggle | User chooses: nanobot personality (via --append-system-prompt) or raw Claude Code behavior | Low | Config boolean; conditionally pass system prompt |
| Output verbosity control | User picks: full tool output, final-only, or summarized | Low | Config enum; filter what gets rendered |
| --bypass CLI flag | Quick one-step activation from command line | Low | Typer option that sets provider to claude_code |
| Menu item in provider picker | Discoverable in nanobot's interactive config/onboard flow | Low | Add to _configure_providers choices |
| One-shot AND session modes | Different use cases need different approaches; flexibility matters | Medium | Config toggle; one-shot skips session tracking |
| Bash wrapper script option | Power users can customize CLI invocation without touching Python | Low | Config points to optional script path instead of direct claude binary |
| Cost/usage tracking from CLI | Surface Claude Code's cost reporting through nanobot's UI | Low | Parse ResultMessage.total_cost_usd and model_usage |
| Concurrent session limiting | Prevent spawning too many CLI processes when multiple channels are active | Low | asyncio.Semaphore (nanobot already has this pattern) |

## Anti-Features

Features to explicitly NOT build.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Claude Code tool execution | Dual agent loops cause conflicts; nanobot already has superior tool management with its ToolRegistry, AgentHook system, and checkpoint callbacks | Disable tools with `--tools ""`; nanobot's AgentRunner handles all tool execution |
| Claude Code session as nanobot session | Two session stores causes data inconsistency and confusion | Nanobot manages its own sessions; Claude Code sessions are an internal implementation detail for context continuity |
| Modifying claude binary | Out of scope per PROJECT.md; we only call it as-is | Shell out to unmodified CLI |
| Non-Claude model support | This mode is Claude Code specific; other models have direct API providers | Clearly document this is Claude-only |
| Replacing direct API providers | This is an additional option, not a replacement | Side-by-side in provider menu; both work |
| Auto-installing claude CLI | Users should control what gets installed on their machine | Clear error message with install instructions |
| Interactive CLI mode | We only need -p (print/SDK) mode; interactive mode requires TTY and can't be piped | Always use -p flag |
| Using claude_agent_sdk Python package | SDK runs its own agent loop with tool execution, session management, and streaming -- all of which nanobot already handles | Spawn CLI subprocess directly via asyncio; parse stdout JSON |
| Response reformatting via second LLM | Rewriting responses wastes tokens and adds latency | Pass through as-is; use --append-system-prompt for persona injection at generation time |

## Feature Dependencies

```
CLI availability check --> Provider instantiation --> Provider registration
Provider registration --> Config schema field --> Menu integration
Provider registration --> Backend switch --> Basic chat (one-shot)
Basic chat (one-shot) --> Text streaming
Basic chat (one-shot) --> Tool call parsing --> AgentRunner tool loop
Basic chat (one-shot) --> Error handling
Basic chat (one-shot) --> Session ID capture --> Session continuity (--resume)
Session continuity --> Session mode config
Text streaming + Tool call parsing + Error handling --> Production-ready provider
Production-ready provider --> Persona passthrough
Production-ready provider --> Output verbosity control
Production-ready provider --> --bypass CLI flag
Production-ready provider --> Menu item in provider picker
```

## MVP Recommendation

Prioritize:
1. **Basic one-shot chat** -- Send prompt via `claude -p`, get response. This alone proves the concept.
2. **Text streaming** -- Critical for UX parity with other providers.
3. **Tool call parsing** -- Without this, nanobot is just a chat relay, not an agent.
4. **Error handling** -- Must fail gracefully when CLI is missing, auth expired, or rate limited.
5. **Provider registration** -- ProviderSpec + config + backend switch to make it selectable.

Defer:
- **Session continuity**: Nice to have but one-shot mode works fine for v1. Can add later.
- **Bash wrapper script**: Power user feature; not needed for core functionality.
- **Menu integration**: Can be selected via config file; interactive menu is polish.
- **Output verbosity control**: Default behavior (return everything) is acceptable.

## Sources

- [Claude Code CLI Reference](https://code.claude.com/docs/en/cli-reference) -- Capabilities available via CLI flags
- [Run Claude Code Programmatically](https://code.claude.com/docs/en/headless) -- Headless mode capabilities
- Nanobot PROJECT.md -- Active requirements and out-of-scope items
- Nanobot codebase analysis -- Existing provider patterns and integration points

---

*Feature analysis: 2026-04-09*
