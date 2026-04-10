# Phase 2: Session Management - Research

**Researched:** 2026-04-09
**Domain:** Claude Code CLI session persistence and mode toggling within an async Python agent framework
**Confidence:** HIGH

## Summary

Phase 2 adds session persistence (via Claude Code's `--resume <session_id>` flag) and mode toggling (`/session` and `/oneshot` slash commands) to the existing `ClaudeCodeProvider`. The core mechanism is well-documented: every `claude -p` invocation returns a `session_id` in its JSON output, and passing `--resume <session_id>` on subsequent calls restores full conversation context inside the CLI subprocess. This eliminates the need to re-serialize nanobot's conversation history.

The implementation touches four areas: (1) extending `_build_command()` to conditionally include `--resume`, (2) maintaining an in-memory `dict[str, str]` mapping nanobot session keys to Claude Code session UUIDs, (3) adding a `session_mode` config field to `ClaudeCodeProviderConfig`, and (4) registering two new slash commands that flip the mode per-session via `Session.metadata`. All four areas use existing, well-understood patterns already present in the codebase.

**Primary recommendation:** Implement session management using raw subprocess with `--resume` flag (matching the Phase 1 approach), storing mode preference in `Session.metadata` and session ID mapping in the provider instance. Do not introduce `claude-agent-sdk` dependency in this phase.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Use Claude Code's native `--resume <session_id>` flag to maintain context across turns -- do not re-serialize nanobot's conversation history
- **D-02:** Parse `session_id` from the JSON output of each `claude -p` call (available in `ResultMessage`)
- **D-03:** On the first message in session mode, omit `--resume` (new session). On subsequent messages, pass `--resume <session_id>` from the stored mapping
- **D-04:** Store a `dict[str, str]` in the `ClaudeCodeProvider` instance mapping nanobot session keys (`channel:chat_id`) to Claude Code session UUIDs
- **D-05:** The mapping is in-memory only -- it does not need filesystem persistence (Claude Code manages its own session storage under `~/.claude/projects/`)
- **D-06:** If a `--resume` call fails (session not found), fall back to starting a new session and log a warning
- **D-07:** Add `session_mode` field to `ClaudeCodeProviderConfig` in config schema (values: `"session"` or `"oneshot"`, default: `"session"`)
- **D-08:** Add slash commands `/session` and `/oneshot` to switch modes per conversation (registers via nanobot's existing `CommandRouter`)
- **D-09:** Mode is per-session (stored in nanobot's session metadata), not global -- different channels can use different modes
- **D-10:** New Claude Code session created on first message in session mode (no `--resume` passed)
- **D-11:** No explicit session expiry for v1 -- Claude Code manages its own session storage
- **D-12:** When user runs `/clear`, clear the session ID mapping for that conversation (next message starts fresh)

### Claude's Discretion
- How to thread session_key through the provider's `chat()` method (may need to add parameter or use instance state)
- Whether to show session_id to user in verbose output mode
- Internal implementation of the session ID dict (plain dict vs weakref vs bounded cache)

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SESS-01 | User can use session mode where conversation context persists across turns | `--resume <session_id>` flag verified in official CLI docs; `session_id` present in JSON output envelope; session files stored at `~/.claude/projects/<encoded-cwd>/` |
| SESS-02 | User can use one-shot mode where each prompt is independent | Omitting `--resume` creates a fresh session each time; adding `--no-session-persistence` prevents even writing session files to disk |
| SESS-03 | User can toggle between session and one-shot modes per conversation | `Session.metadata` dict already exists for per-session state; `CommandRouter.exact()` pattern handles new slash commands |
</phase_requirements>

## Standard Stack

### Core (No New Dependencies)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python stdlib `asyncio` | 3.11+ | Subprocess management | Already used by Phase 1 `ClaudeCodeProvider.chat()` |
| Python stdlib `json` | 3.11+ | Parse CLI JSON output | Already used by Phase 1 `_parse_result()` |
| `pydantic` | >=2.12.0 | Config schema (`ClaudeCodeProviderConfig`) | Already in project; all config fields use pydantic |
| `loguru` | >=0.7.3 | Logging session lifecycle events | Already in project; all modules use loguru |

### Supporting (Existing, No Changes)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `nanobot.session.manager.Session` | n/a | `metadata` dict for per-session mode storage | Storing `session_mode` preference per conversation |
| `nanobot.command.router.CommandRouter` | n/a | Slash command registration | Registering `/session` and `/oneshot` commands |
| `nanobot.config.schema` | n/a | Pydantic config models | Adding `session_mode` to `ClaudeCodeProviderConfig` |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| In-memory dict | `claude-agent-sdk` with `ClaudeSDKClient` | SDK provides automatic session tracking but requires new dependency, different transport (stdin/stdout JSON-lines), and lifecycle management. Deferred to v2 per STACK.md recommendation. |
| In-memory dict | SQLite/file persistence | Unnecessary -- Claude Code manages its own session files. In-memory mapping is sufficient since sessions restart cleanly if the mapping is lost. |
| Plain `dict` | `cachetools.LRUCache` | Bounded cache prevents unbounded growth but adds a dependency. Plain dict with `/clear` cleanup is simpler and sufficient for v1. |

## Architecture Patterns

### Recommended Changes to Existing Files

```
nanobot/
├── providers/
│   └── claude_code_provider.py  # Add session ID mapping + --resume to _build_command()
├── config/
│   └── schema.py                # Add session_mode to ClaudeCodeProviderConfig
├── command/
│   └── builtin.py               # Register /session and /oneshot commands
└── agent/
    └── loop.py                  # Thread session_key to provider before chat() calls
```

No new files required. All changes extend existing modules.

### Pattern 1: Session Key Threading via Provider Instance State

**What:** Before each `chat()` call, `AgentLoop` sets the current session key on the provider instance so the provider can look up/store session IDs.

**When to use:** This is the recommended approach because `LLMProvider.chat()` does not accept a `session_key` parameter, and modifying the ABC signature would impact all providers.

**Why not modify `chat()` signature:** The `LLMProvider` ABC defines `chat()` with a fixed signature used by 8+ provider implementations. Adding `session_key` to this signature for the benefit of one provider is the wrong design choice. Instance state set before the call is the idiomatic pattern.

**Example:**
```python
# In ClaudeCodeProvider
class ClaudeCodeProvider(LLMProvider):
    def __init__(self, ...):
        ...
        self._session_map: dict[str, str] = {}  # nanobot_key -> claude_session_id
        self._current_session_key: str | None = None
        self._current_session_mode: str = "session"  # or "oneshot"

    def set_session_context(
        self,
        session_key: str,
        session_mode: str = "session",
    ) -> None:
        """Set session context before a chat() call."""
        self._current_session_key = session_key
        self._current_session_mode = session_mode
```

```python
# In AgentLoop._process_message(), before _run_agent_loop()
if isinstance(self.provider, ClaudeCodeProvider):
    mode = session.metadata.get("claude_code_session_mode", "session")
    self.provider.set_session_context(
        session_key=key,
        session_mode=mode,
    )
```

### Pattern 2: Conditional --resume in Command Building

**What:** Extend `_build_command()` to accept an optional `session_id` parameter and include `--resume <id>` when present.

**When to use:** Every `chat()` call in session mode after the first message.

**Example:**
```python
def _build_command(
    self,
    prompt: str,
    session_id: str | None = None,
) -> list[str]:
    cmd = [
        self._cli_path,
        "-p",
        "--output-format", "json",
        "--setting-sources", "",
        prompt,
    ]
    if session_id:
        # Insert --resume before the prompt (last element)
        cmd[-1:] = ["--resume", session_id, prompt]
    return cmd
```

### Pattern 3: Session ID Extraction from JSON Output

**What:** Extract `session_id` from the CLI JSON response envelope and store it in the mapping.

**When to use:** After every successful `chat()` call in session mode.

**Example:**
```python
def _parse_result(self, stdout_bytes, stderr_bytes, returncode):
    # ... existing parsing ...
    data = json.loads(stdout_text)
    session_id = data.get("session_id", "")

    # Store session mapping if in session mode
    if (
        self._current_session_mode == "session"
        and self._current_session_key
        and session_id
    ):
        self._session_map[self._current_session_key] = session_id

    # ... rest of existing parsing ...
```

### Pattern 4: Slash Command Registration (Follow Existing Pattern)

**What:** Register `/session` and `/oneshot` as exact-match commands following the same pattern as `/new`, `/status`, etc.

**Example:**
```python
# In builtin.py
async def cmd_session(ctx: CommandContext) -> OutboundMessage:
    """Switch to session mode (persistent context)."""
    session = ctx.session or ctx.loop.sessions.get_or_create(ctx.key)
    session.metadata["claude_code_session_mode"] = "session"
    ctx.loop.sessions.save(session)
    return OutboundMessage(
        channel=ctx.msg.channel,
        chat_id=ctx.msg.chat_id,
        content="Switched to session mode. Context will persist across messages.",
        metadata=dict(ctx.msg.metadata or {}),
    )

async def cmd_oneshot(ctx: CommandContext) -> OutboundMessage:
    """Switch to one-shot mode (independent prompts)."""
    session = ctx.session or ctx.loop.sessions.get_or_create(ctx.key)
    session.metadata["claude_code_session_mode"] = "oneshot"
    ctx.loop.sessions.save(session)
    return OutboundMessage(
        channel=ctx.msg.channel,
        chat_id=ctx.msg.chat_id,
        content="Switched to one-shot mode. Each message is independent.",
        metadata=dict(ctx.msg.metadata or {}),
    )

# In register_builtin_commands()
router.exact("/session", cmd_session)
router.exact("/oneshot", cmd_oneshot)
```

### Anti-Patterns to Avoid

- **Modifying LLMProvider.chat() signature:** Adding session_key to the abstract method would break all provider implementations. Use instance state instead.
- **Re-serializing full message history:** The `--resume` flag restores full context inside Claude Code. Do not pass history as a prompt string.
- **Persisting the session map to disk:** Claude Code already persists sessions at `~/.claude/projects/`. The in-memory map is a lookup index, not a source of truth. If lost, next message simply starts a fresh Claude Code session.
- **Global mode setting:** Mode MUST be per-session (stored in `Session.metadata`), not a global provider flag. Different channels can use different modes simultaneously.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Session file persistence | Custom session file format | Claude Code's built-in `~/.claude/projects/` | Claude Code manages session JSONL files, garbage collection, and context loading. Trying to replicate this is fragile. |
| Session ID generation | UUID generation | CLI's returned `session_id` | The CLI generates and tracks its own session IDs. We just store the mapping. |
| Conversation history replay | Serializing nanobot messages into prompt | `--resume <session_id>` flag | The `--resume` flag loads full agent context (tool calls, results, decisions) which is richer than our message history. |
| Mode persistence | Custom file-based mode store | `Session.metadata` dict | Session metadata is already persisted to disk by `SessionManager.save()`. No new persistence mechanism needed. |

## Common Pitfalls

### Pitfall 1: Working Directory Mismatch with --resume

**What goes wrong:** `--resume` fails silently if the working directory differs from when the session was created. Claude Code stores sessions under `~/.claude/projects/<encoded-cwd>/` where `<encoded-cwd>` is the absolute path with non-alphanumeric characters replaced by `-`.

**Why it happens:** Nanobot may be started from different working directories across restarts, or the subprocess may inherit a different cwd.

**How to avoid:** Ensure `asyncio.create_subprocess_exec` does NOT set a different `cwd` (it inherits the parent process cwd by default, which is correct). If nanobot changes cwd at startup, ensure it happens before any Claude Code calls.

**Warning signs:** `--resume` returns a fresh session instead of the expected history (no error raised, just silent new session creation).

### Pitfall 2: Race Condition on Session Map with Concurrent Channels

**What goes wrong:** Two concurrent messages for different sessions could interleave `set_session_context()` calls, causing the wrong session_key to be active during `chat()`.

**Why it happens:** `_current_session_key` is mutable instance state on a shared provider object. AgentLoop uses per-session locks, but if two sessions are active simultaneously, the provider state could be overwritten.

**How to avoid:** AgentLoop already serializes per-session via `self._session_locks`, so within a single session the flow is serial. Cross-session concurrent calls are the risk. Solution: read `_current_session_key` immediately at the start of `chat()` and use the local copy throughout. Alternatively, pass session context as a `dict` parameter to a private method rather than relying on instance state.

**Warning signs:** Session context "leaks" between channels -- a Telegram user gets Discord session history.

### Pitfall 3: Stale Session After /clear

**What goes wrong:** User runs `/clear` (which calls `session.clear()` and resets nanobot history), but the Claude Code session mapping is not cleared. Next message resumes the old Claude Code session with stale context.

**Why it happens:** The existing `cmd_new` handler clears the nanobot session but does not know about the Claude Code session map on the provider.

**How to avoid:** Extend `cmd_new` (which handles `/new`) to also clear the session ID from the provider's `_session_map`. This requires access to the provider from the command handler, which is available via `ctx.loop.provider`.

**Warning signs:** After `/new` or `/clear`, Claude Code still has context from the previous conversation.

### Pitfall 4: --resume with Non-Existent Session ID

**What goes wrong:** If the Claude Code session file has been cleaned up (e.g., user ran `claude session clear`), `--resume` with a stale ID may create a fresh session silently or return an error.

**Why it happens:** Claude Code stores sessions as JSONL files. If deleted, the resume target is gone.

**How to avoid:** Decision D-06 covers this: if a `--resume` call fails, fall back to starting a new session and log a warning. Check `is_error` in the JSON response and specifically look for session-not-found indicators.

**Warning signs:** Unexpected error responses or empty context in what should be a continuation.

### Pitfall 5: One-Shot Mode Still Creating Session Files

**What goes wrong:** In one-shot mode, each `claude -p` call still creates a session file on disk, leading to disk accumulation.

**Why it happens:** By default, `claude -p` persists every session to `~/.claude/projects/`.

**How to avoid:** In one-shot mode, add `--no-session-persistence` to the command to prevent writing session files. This flag is documented in the CLI reference and is specifically designed for stateless/one-shot usage.

**Warning signs:** Growing number of session files under `~/.claude/projects/` even when using one-shot mode.

## Code Examples

### Example 1: Extended _build_command with Session Support

```python
# Source: Pattern derived from CLI reference at https://code.claude.com/docs/en/cli-reference
def _build_command(
    self,
    prompt: str,
    session_id: str | None = None,
    no_session_persistence: bool = False,
) -> list[str]:
    cmd = [
        self._cli_path,
        "-p",
        "--output-format", "json",
        "--setting-sources", "",
    ]
    if session_id:
        cmd.extend(["--resume", session_id])
    if no_session_persistence:
        cmd.append("--no-session-persistence")
    cmd.append(prompt)
    return cmd
```

### Example 2: Session-Aware chat() Method

```python
# Source: Extends existing ClaudeCodeProvider.chat() from Phase 1
async def chat(self, messages, tools=None, model=None, **kw) -> LLMResponse:
    prompt = self._extract_latest_user_content(messages)

    # Determine session behavior based on current mode
    session_id = None
    no_persist = False
    if self._current_session_mode == "session" and self._current_session_key:
        session_id = self._session_map.get(self._current_session_key)
    elif self._current_session_mode == "oneshot":
        no_persist = True

    cmd = self._build_command(prompt, session_id=session_id, no_session_persistence=no_persist)

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout_bytes, stderr_bytes = await proc.communicate()
    await proc.wait()

    return self._parse_result(stdout_bytes, stderr_bytes, proc.returncode)
```

### Example 3: Session ID Extraction in _parse_result

```python
# Source: Extends existing _parse_result with session_id extraction
def _parse_result(self, stdout_bytes, stderr_bytes, returncode):
    # ... existing error handling for empty/invalid output ...
    data = json.loads(stdout_text)

    # Extract and store session_id for future --resume calls
    session_id = data.get("session_id", "")
    if (
        session_id
        and self._current_session_mode == "session"
        and self._current_session_key
    ):
        self._session_map[self._current_session_key] = session_id

    # ... rest of existing parsing ...
```

### Example 4: Clearing Session Mapping on /new

```python
# Source: Extends cmd_new in builtin.py
async def cmd_new(ctx: CommandContext) -> OutboundMessage:
    """Start a fresh session."""
    loop = ctx.loop
    session = ctx.session or loop.sessions.get_or_create(ctx.key)

    # Clear Claude Code session mapping if provider supports it
    if hasattr(loop.provider, "clear_session"):
        loop.provider.clear_session(ctx.key)

    snapshot = session.messages[session.last_consolidated:]
    session.clear()
    loop.sessions.save(session)
    loop.sessions.invalidate(session.key)
    if snapshot:
        loop._schedule_background(loop.consolidator.archive(snapshot))
    return OutboundMessage(
        channel=ctx.msg.channel, chat_id=ctx.msg.chat_id,
        content="New session started.",
        metadata=dict(ctx.msg.metadata or {}),
    )
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `--bare` flag for reduced overhead | `--setting-sources ""` | Phase 1 (2026-04-09) | `--bare` breaks subscription OAuth keychain auth. `--setting-sources ""` preserves auth while reducing overhead. |
| `claude-code-sdk` package | `claude-agent-sdk` package | Sept 2025 | Old name deprecated. New name is `claude-agent-sdk>=0.1.56`. Not used in this phase but relevant for v2. |
| Manual session file management | `--resume <session_id>` | Available since early Claude Code | CLI manages its own session persistence. No need to implement custom session storage. |
| `--output-format text` | `--output-format json` | Standard | JSON output provides structured `session_id`, `usage`, `is_error` fields. Text output requires fragile regex parsing. |

**Deprecated/outdated:**
- `claude-code-sdk` (PyPI): Renamed to `claude-agent-sdk` as of Sept 2025. Do not use the old name.
- `--bare` flag: Breaks subscription auth. Use `--setting-sources ""` instead.

## Open Questions

1. **Session ID stability across CLI updates**
   - What we know: `session_id` is a UUID present in every JSON response envelope. It is stable within a CLI version.
   - What's unclear: Whether Claude Code CLI updates change the session file format in ways that break `--resume` with old session IDs.
   - Recommendation: This is LOW risk. Claude Code maintains backward compatibility for sessions. If a session cannot be resumed, D-06 handles the fallback gracefully.

2. **Thread safety of set_session_context()**
   - What we know: AgentLoop uses per-session locks, preventing concurrent calls for the same session. Different sessions can run concurrently.
   - What's unclear: Whether the provider instance state pattern is safe when two different sessions call `chat()` concurrently through the same provider instance.
   - Recommendation: Capture `_current_session_key` and `_current_session_mode` into local variables at the top of `chat()`, so concurrent calls from different sessions do not interfere. This is the safest approach.

3. **Slash commands only relevant for Claude Code provider**
   - What we know: `/session` and `/oneshot` commands are meaningful only when the Claude Code provider is active. With other providers, they are meaningless.
   - What's unclear: Whether to register them unconditionally or conditionally.
   - Recommendation: Register unconditionally but return a clear "not applicable" message when a non-Claude-Code provider is active. This avoids coupling command registration to provider type and is simpler to maintain.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | Runtime | Yes | 3.12+ | -- |
| `claude` CLI | Provider | Yes | 2.1.97 | -- |
| `pytest` | Tests | Yes | 9.0.3 (via uv) | -- |
| `pytest-asyncio` | Async tests | Yes | (bundled) | -- |

**Missing dependencies with no fallback:** None.
**Missing dependencies with fallback:** None.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 + pytest-asyncio |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` with `asyncio_mode = "auto"` |
| Quick run command | `uv run pytest tests/providers/test_claude_code_provider.py -x` |
| Full suite command | `uv run pytest tests/ -x` |

### Phase Requirements -> Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SESS-01 | Session mode: chat with --resume includes session_id, subsequent calls pass --resume | unit | `uv run pytest tests/providers/test_claude_code_provider.py::test_session_mode_stores_and_resumes_id -x` | Wave 0 |
| SESS-01 | Session mode: first call omits --resume, second call includes it | unit | `uv run pytest tests/providers/test_claude_code_provider.py::test_session_first_call_no_resume -x` | Wave 0 |
| SESS-01 | Session mode: session_id extracted from JSON output | unit | `uv run pytest tests/providers/test_claude_code_provider.py::test_session_id_extracted_from_result -x` | Wave 0 |
| SESS-02 | One-shot mode: --resume never included, --no-session-persistence flag present | unit | `uv run pytest tests/providers/test_claude_code_provider.py::test_oneshot_mode_no_resume -x` | Wave 0 |
| SESS-02 | One-shot mode: no session_id stored in map | unit | `uv run pytest tests/providers/test_claude_code_provider.py::test_oneshot_mode_no_session_stored -x` | Wave 0 |
| SESS-03 | /session command sets metadata, /oneshot command sets metadata | unit | `uv run pytest tests/providers/test_claude_code_provider.py::test_slash_commands_toggle_mode -x` | Wave 0 |
| SESS-03 | Mode change affects subsequent chat() calls | unit | `uv run pytest tests/providers/test_claude_code_provider.py::test_mode_toggle_changes_behavior -x` | Wave 0 |
| D-06 | Resume failure falls back to new session | unit | `uv run pytest tests/providers/test_claude_code_provider.py::test_resume_failure_fallback -x` | Wave 0 |
| D-12 | /new clears session mapping | unit | `uv run pytest tests/providers/test_claude_code_provider.py::test_clear_session_mapping -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/providers/test_claude_code_provider.py -x`
- **Per wave merge:** `uv run pytest tests/ -x`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] New test functions in `tests/providers/test_claude_code_provider.py` -- covers SESS-01, SESS-02, SESS-03
- [ ] Test fixtures for session_id in JSON responses (extend existing `SUCCESS_JSON` fixture)
- [ ] Test fixtures for FakeProcess that captures command args (extend existing helper)

(No new test files needed -- existing test file is the correct location. No framework install needed.)

## Project Constraints (from CLAUDE.md)

The following directives from CLAUDE.md and project conventions apply to this phase:

- **Immutability:** Create new objects, never mutate existing ones. Session map updates should create new entries, not mutate values.
- **Type annotations:** All function signatures must carry full type annotations using modern Python 3.10+ union syntax (`str | None`).
- **`from __future__ import annotations`:** Used in `claude_code_provider.py` already. Maintain this.
- **Ruff formatting:** `line-length = 100`, target `py311`. Run after edits.
- **Error handling:** Use `LLMResponse(finish_reason="error")` for provider errors. Never propagate raw exceptions from chat().
- **Logging:** Use loguru throughout. Template-style placeholders: `logger.warning("msg {}", arg)`.
- **File size:** Functions < 50 lines, files < 800 lines.
- **Config pattern:** Pydantic `BaseModel` with `alias_generator=to_camel`, `populate_by_name=True`.
- **Test pattern:** pytest with `asyncio_mode = "auto"`, AAA (Arrange-Act-Assert) structure.
- **GSD workflow:** Do not make direct repo edits outside a GSD workflow unless explicitly asked.

## Sources

### Primary (HIGH confidence)
- [Claude Code CLI Reference](https://code.claude.com/docs/en/cli-reference) -- `--resume`, `--no-session-persistence`, `-p`, `--output-format json`, `--setting-sources` flags. Verified April 2026.
- [Work with sessions - Agent SDK Docs](https://code.claude.com/docs/en/agent-sdk/sessions) -- Session persistence mechanism, `session_id` in `ResultMessage`, resume semantics, working directory encoding, fork behavior.
- [Python Agent SDK Reference](https://code.claude.com/docs/en/agent-sdk/python) -- `ClaudeAgentOptions` fields including `resume`, `setting_sources`, `continue_conversation`. `ResultMessage` schema with `session_id`.
- Nanobot codebase: `nanobot/providers/claude_code_provider.py` -- Current Phase 1 implementation to extend.
- Nanobot codebase: `nanobot/session/manager.py` -- `Session.metadata` dict for per-session state.
- Nanobot codebase: `nanobot/command/builtin.py` -- Existing slash command registration pattern.
- Nanobot codebase: `nanobot/command/router.py` -- `CommandRouter.exact()` API.
- Nanobot codebase: `nanobot/agent/loop.py` -- `AgentLoop._process_message()` where session key is available.
- Nanobot codebase: `nanobot/config/schema.py` -- `ClaudeCodeProviderConfig` and `ProvidersConfig` patterns.
- Nanobot codebase: `tests/providers/test_claude_code_provider.py` -- Existing test infrastructure.

### Secondary (MEDIUM confidence)
- [Claude Code Session Management - Steve Kinney](https://stevekinney.com/courses/ai-development/claude-code-session-management) -- Practical usage of `--resume` flag with session IDs.
- [Claude Code Cheat Sheet](https://devoriales.com/post/400/claude-code-cheat-sheet-the-reference-guide) -- Community reference for CLI flags.
- `.planning/research/STACK.md` -- SDK integration approaches, `ResultMessage` schema, CLI flags table.
- `.planning/research/ARCHITECTURE.md` -- Session ID mapping pattern, data flow diagrams.

### Tertiary (LOW confidence)
- None. All findings verified against official documentation.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- No new dependencies. All patterns use existing project libraries and conventions.
- Architecture: HIGH -- Extending existing `ClaudeCodeProvider` with well-understood patterns. Session ID extraction from JSON is documented in official CLI reference.
- Pitfalls: HIGH -- Working directory sensitivity documented in official SDK docs. Concurrency concerns mitigated by existing per-session locks.
- Slash commands: HIGH -- Following exact same pattern as existing `/new`, `/status`, `/dream` commands.

**Research date:** 2026-04-09
**Valid until:** 2026-05-09 (stable -- CLI flags and session mechanism are core features unlikely to change)
