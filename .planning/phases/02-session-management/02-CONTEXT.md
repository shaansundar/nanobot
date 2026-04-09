# Phase 2: Session Management - Context

**Gathered:** 2026-04-09
**Status:** Ready for planning

<domain>
## Phase Boundary

Add persistent session mode and one-shot mode to the ClaudeCodeProvider, with a user-facing toggle. In session mode, Claude Code retains context from prior turns via `--resume`. In one-shot mode, each prompt is independent. Users can switch modes per conversation.

</domain>

<decisions>
## Implementation Decisions

### Session Persistence Mechanism
- **D-01:** Use Claude Code's native `--resume <session_id>` flag to maintain context across turns — do not re-serialize nanobot's conversation history
- **D-02:** Parse `session_id` from the JSON output of each `claude -p` call (available in `ResultMessage`)
- **D-03:** On the first message in session mode, omit `--resume` (new session). On subsequent messages, pass `--resume <session_id>` from the stored mapping

### Session ID Mapping
- **D-04:** Store a `dict[str, str]` in the `ClaudeCodeProvider` instance mapping nanobot session keys (`channel:chat_id`) to Claude Code session UUIDs
- **D-05:** The mapping is in-memory only — it does not need filesystem persistence (Claude Code manages its own session storage under `~/.claude/projects/`)
- **D-06:** If a `--resume` call fails (session not found), fall back to starting a new session and log a warning

### Mode Toggle UX
- **D-07:** Add `session_mode` field to `ClaudeCodeProviderConfig` in config schema (values: `"session"` or `"oneshot"`, default: `"session"`)
- **D-08:** Add slash commands `/session` and `/oneshot` to switch modes per conversation (registers via nanobot's existing `CommandRouter`)
- **D-09:** Mode is per-session (stored in nanobot's session metadata), not global — different channels can use different modes

### Session Lifecycle
- **D-10:** New Claude Code session created on first message in session mode (no `--resume` passed)
- **D-11:** No explicit session expiry for v1 — Claude Code manages its own session storage
- **D-12:** When user runs `/clear`, clear the session ID mapping for that conversation (next message starts fresh)

### Claude's Discretion
- How to thread session_key through the provider's `chat()` method (may need to add parameter or use instance state)
- Whether to show session_id to user in verbose output mode
- Internal implementation of the session ID dict (plain dict vs weakref vs bounded cache)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Provider Implementation (from Phase 1)
- `nanobot/providers/claude_code_provider.py` — Current provider class to extend with session support
- `nanobot/providers/base.py` — LLMProvider ABC, `chat()` method signature
- `tests/providers/test_claude_code_provider.py` — Existing tests to extend

### Session System
- `nanobot/session/manager.py` — SessionManager, Session dataclass, session key format
- `nanobot/agent/loop.py` — AgentLoop._process_message() — where session key is available

### Command System
- `nanobot/command/builtin.py` — Existing slash command implementations
- `nanobot/command/router.py` — CommandRouter, CommandContext, registration pattern

### Config
- `nanobot/config/schema.py` — ClaudeCodeProviderConfig (add session_mode field)

### Research
- `.planning/research/STACK.md` — Claude Code CLI flags reference (`--resume`, session IDs)
- `.planning/research/ARCHITECTURE.md` — Session continuity architecture

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `ClaudeCodeProvider._build_command()` in `claude_code_provider.py`: Extend to conditionally add `--resume <session_id>`
- `CommandRouter.register()` in `nanobot/command/router.py`: Use existing pattern to register `/session` and `/oneshot` commands
- `Session.metadata` dict in `nanobot/session/manager.py`: Can store mode preference per session

### Established Patterns
- Provider `chat()` receives `messages` list and `generation_settings` — session key is NOT currently passed. May need to add it as a parameter or thread through `generation_settings.extra`
- Slash commands are registered in `nanobot/command/builtin.py:register_builtin_commands()` — follow the same pattern
- Config fields use pydantic with `env_prefix="NANOBOT_"` — `session_mode` would be configurable via `NANOBOT_PROVIDERS__CLAUDE_CODE__SESSION_MODE`

### Integration Points
- `ClaudeCodeProvider.chat()` — needs session key to look up/store session IDs
- `AgentLoop._process_message()` — where the session key is available before calling the provider
- `nanobot/command/builtin.py` — register new slash commands

</code_context>

<specifics>
## Specific Ideas

- Session mode should feel seamless — user just talks and context carries forward without explicit management
- One-shot mode should be truly stateless — no Claude Code session created, no `--resume`
- The `/clear` command already exists for clearing nanobot sessions — extend it to also clear the Claude Code session mapping

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 02-session-management*
*Context gathered: 2026-04-09*
