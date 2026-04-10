# Pitfalls Research

**Domain:** CLI subprocess proxy / Claude Code CLI wrapper
**Researched:** 2026-04-09
**Confidence:** HIGH (based on documented real-world failures from Claude Code wrapper projects, official bug reports, and codebase-specific analysis)

## Critical Pitfalls

### Pitfall 1: Pipe Buffer Deadlock on Simultaneous stdout/stderr

**What goes wrong:**
The Claude Code CLI writes to both stdout (response data / stream-json events) and stderr (diagnostic messages, progress). When both streams are piped (`stdout=PIPE, stderr=PIPE`), the OS pipe buffers (typically 64KB on Linux, 16KB on macOS) can fill. If the reader is blocked waiting on one stream while the other fills up, the child process blocks on write, creating a deadlock. Neither side makes progress. The subprocess appears to "hang" indefinitely.

**Why it happens:**
Developers read stdout in a loop (to stream response tokens) but neglect to concurrently drain stderr. The pipe buffer fills on stderr, Claude Code blocks trying to write a diagnostic message, and the reader never gets the next stdout line because the child is suspended.

**How to avoid:**
Use `asyncio.create_subprocess_exec` with both `stdout=PIPE` and `stderr=PIPE`, then read both streams concurrently using separate `asyncio.Task` coroutines -- one for `process.stdout` and one for `process.stderr`. Never use a sequential read pattern like `for line in process.stdout` followed by `process.stderr.read()`. The existing `ExecTool._spawn` uses `process.communicate()` which handles this correctly but buffers everything in memory. For streaming, replace `communicate()` with concurrent `readline()` loops on both streams.

**Warning signs:**
- Subprocess appears to hang after producing some output
- Hang only occurs with longer responses (short responses fit in pipe buffer)
- Adding `stderr=DEVNULL` "fixes" the hang (confirms the buffer-full diagnosis)
- Hang is intermittent and depends on response length

**Phase to address:**
Phase 1 (Core subprocess infrastructure). This must be correct from the first implementation or every test will be unreliable.

---

### Pitfall 2: Claude Code CLI Hangs Without Explicit stdin Connection

**What goes wrong:**
Claude Code has a known issue (GitHub issue #9026) where it hangs when spawned as a subprocess without proper stdin handling, even with the `-p` (print) flag. The CLI performs TTY detection and shell environment probing that can consume stdin or block waiting for terminal input. The subprocess times out after 30 seconds or hangs indefinitely depending on the invocation pattern.

**Why it happens:**
Claude Code spawns child processes for shell environment detection (detecting default shell, sourcing profiles) that inherit the parent's stdin file descriptor. These children can consume stdin bytes meant for the main process, or the TTY detection logic blocks when `/dev/tty` is not available. On HPC/container environments (issue #12507), stdin is consumed entirely by shell detection subprocesses.

**How to avoid:**
Always pass `stdin=asyncio.subprocess.PIPE` and explicitly close the write end after sending input (or immediately if using `-p` with arguments). Use `--bare` flag to skip shell detection, plugin loading, and MCP initialization. If the process will not receive interactive stdin, pipe `/dev/null` or close stdin immediately after process creation:
```python
process = await asyncio.create_subprocess_exec(
    "claude", "-p", "--bare", "--output-format", "stream-json",
    prompt,
    stdin=asyncio.subprocess.DEVNULL,  # for one-shot mode
    stdout=asyncio.subprocess.PIPE,
    stderr=asyncio.subprocess.PIPE,
)
```
For persistent session mode (using `--input-format stream-json`), keep stdin open but send an explicit newline-terminated JSON message and flush.

**Warning signs:**
- Subprocess starts but produces no output for 10+ seconds on simple prompts
- Process works in manual terminal testing but hangs in automated contexts
- Works on developer machines but fails in CI/Docker/remote SSH
- `ps` shows multiple child processes of `claude` consuming no CPU

**Phase to address:**
Phase 1 (Core subprocess infrastructure). Gate all development on a working spawn-and-read cycle before building streaming or session management.

---

### Pitfall 3: Dual Agent Loop -- Two Tool Executors Competing on One Workspace

**What goes wrong:**
Without `--tools ""`, Claude Code runs its own agent loop that executes file edits, bash commands, and web fetches on the host file system. Nanobot's `AgentRunner` also has a tool execution loop (`ToolRegistry`). If both systems modify files concurrently -- or if nanobot sends a tool result back to Claude Code that references a file state Claude Code has already changed -- the conversation state and file system diverge. Claude Code thinks a file contains version A; nanobot's tool system reports version B.

**Why it happens:**
The bypass mode creates a double-agent problem: two systems (nanobot's agent loop and Claude Code's agent loop) are both trying to manage the same workspace. Claude Code is designed as a full agent, not a completion backend. Its default behavior includes tool execution. Developers test the happy path without realizing both systems are making changes.

**How to avoid:**
Choose one of two clean architectures and do not mix them:
- **Option A (Passthrough -- recommended for bypass mode):** Let Claude Code handle all tool execution internally. Nanobot becomes a thin wrapper that sends prompts and receives final text results. Always pass `--tools ""` to disable Claude Code's built-in tools, making the CLI a pure LLM completion proxy with all tool execution flowing through nanobot's `ToolRegistry`. Or let Claude Code handle everything and only consume its final result text.
- **Option B (Full delegation):** Let Claude Code execute all tools. Use `--output-format stream-json` to observe what it does, but do not re-execute any tool calls through nanobot.

Never do both: never let Claude Code execute tools while also having nanobot execute tools on the same workspace without explicit coordination.

**Warning signs:**
- Claude Code logs file edits or bash executions in stderr while nanobot is also running tools
- File contents in conversation history don't match actual file contents
- Tests about file state pass intermittently

**Phase to address:**
Phase 1 (Architecture decision). This is a design-level choice that must be made before any tool integration code is written. The PROJECT.md lists "Full tool use passthrough (file edits, bash, etc. flow through Claude Code)" as a requirement, pointing toward full delegation to Claude Code.

---

### Pitfall 4: 50K Token Per-Turn Overhead from Configuration Reininjection

**What goes wrong:**
Each one-shot subprocess invocation of `claude -p` re-reads the entire configuration stack: `CLAUDE.md` files (walked up to home directory), all enabled plugins, MCP server tool descriptions, skill directories. A single subprocess turn consumes approximately 50,000 tokens before any actual work begins. Over a 10-turn conversation, this means 500K tokens wasted on repeated system prompt injection -- a 10x cost multiplier versus an optimized approach.

**Why it happens:**
Claude Code is designed for interactive use where configuration loads once. When wrapped as one-shot subprocesses, each invocation is a fresh process that must rediscover its context. The `--resume` flag helps with conversation continuity but still reloads configuration per process start. Projects with large CLAUDE.md files, many plugins, or MCP servers exacerbate this dramatically.

**How to avoid:**
Use `--bare` flag for all subprocess invocations to skip hooks, LSP, plugin sync, skill walks, and auto-discovery. This reduces per-turn overhead from ~50K to ~5K tokens (10x reduction). For multi-turn conversations, use a persistent subprocess with `--input-format stream-json` and `--output-format stream-json` to send the system prompt once and keep the process alive across turns. Isolate the working directory to prevent `CLAUDE.md` walk-up behavior:
- Set working directory to a temp directory without a `.git` directory (prevents git-boundary walking)
- Use `--system-prompt` to provide nanobot's persona explicitly rather than relying on file discovery
- Use `--settings` to provide a minimal settings file that disables plugins

**Warning signs:**
- Response latency is 3-5 seconds even for trivial prompts
- Token usage reported in JSON output (`total_cost_usd`, `usage.input_tokens`) is disproportionately high relative to prompt size
- Users on subscription plans hit rate limits faster than expected
- Adding conversation history increases cost non-linearly

**Phase to address:**
Phase 2 (Session management / optimization). Phase 1 can use `--bare` one-shot mode. Persistent session mode is the Phase 2 optimization that eliminates repeated overhead.

---

### Pitfall 5: Zombie Process Accumulation from Ungraceful Subprocess Termination

**What goes wrong:**
When nanobot cancels a request (user sends new message, timeout, channel disconnects), the Claude Code subprocess and its child processes (bash tools, MCP servers spawned by Claude Code) are not properly terminated. The parent `claude` process may exit, but its children become orphans. Alternatively, the `claude` process is killed with `SIGKILL` but its entry remains in the process table (zombie) because `wait()` was never called. Over time, the system accumulates zombie or orphan processes that consume PIDs and potentially file descriptors.

**Why it happens:**
`process.kill()` sends SIGKILL to the direct process, not to its process group. Claude Code spawns child processes that are not in the same process group by default. `process.terminate()` may be ignored if the process is in a blocking I/O call. The existing `ExecTool._kill_process` handles this for simple commands but a long-running persistent `claude` subprocess has its own subprocess tree.

**How to avoid:**
Spawn the subprocess with `start_new_session=True` (Unix) to create a new process group. On termination, kill the entire process group:
```python
process = await asyncio.create_subprocess_exec(
    *cmd, stdin=PIPE, stdout=PIPE, stderr=PIPE,
    start_new_session=True,
)
# On cleanup:
import signal, os
os.killpg(os.getpgid(process.pid), signal.SIGTERM)
# Grace period, then:
os.killpg(os.getpgid(process.pid), signal.SIGKILL)
await process.wait()  # reap zombie
```
Always call `process.wait()` after kill to reap the zombie entry. Implement a structured shutdown: SIGTERM first, wait 3 seconds, SIGKILL if still alive, then wait. Register an `atexit` handler to clean up on nanobot's own shutdown.

**Warning signs:**
- `ps aux | grep claude` shows increasing process count over time
- PID exhaustion warnings on long-running nanobot instances
- Orphaned MCP server processes after nanobot restart

**Phase to address:**
Phase 1 (Core subprocess infrastructure). Process lifecycle management is foundational.

---

### Pitfall 6: `--dangerously-skip-permissions` in Multi-Channel Server Mode

**What goes wrong:**
To avoid interactive permission prompts in headless subprocess mode, developers use `--dangerously-skip-permissions`. This grants Claude Code unrestricted access to the file system, bash execution, and network -- appropriate for a local developer but catastrophic when nanobot runs as a multi-user gateway serving Telegram/Discord/Slack channels. Any user on any channel can effectively execute arbitrary commands on the host machine through Claude Code's tool system.

**Why it happens:**
During development, `--dangerously-skip-permissions` makes everything work without interruption. It gets committed into the default configuration. When nanobot is deployed as a gateway, the flag is still present. The developer forgets that gateway mode means untrusted users control the prompt.

**How to avoid:**
Never use `--dangerously-skip-permissions` in gateway/server mode. Instead:
1. Use `--permission-mode plan` which allows Claude to plan tool use but requires approval
2. Use `--allowedTools` to whitelist only safe tools: `--allowedTools "Read" "Bash(git log *)" "Bash(git diff *)"`
3. Use `--permission-prompt-tool` to delegate permission decisions to an MCP tool nanobot controls
4. When `restrict_to_workspace` is set in nanobot's config, pass `--tools "Read"` to limit to read-only
5. Add a startup check: if nanobot is in gateway mode AND bypass mode is configured with `--dangerously-skip-permissions`, refuse to start and log a security warning

**Warning signs:**
- `--dangerously-skip-permissions` appears in any configuration file or environment variable
- The bypass provider constructor accepts a `skip_permissions` parameter with default `True`
- No differentiation between CLI mode and gateway mode in permission handling

**Phase to address:**
Phase 1 (Core subprocess infrastructure). Security model must be defined before any tool execution is enabled.

---

### Pitfall 7: Shell Injection via Prompt Passed as CLI Argument

**What goes wrong:**
Constructing the CLI command by concatenating user prompt text into a shell string (`create_subprocess_shell(f"claude -p '{user_input}'")`) or passing through a bash wrapper script without proper quoting. Malicious or accidental special characters in the prompt (`'`, `"`, `;`, `$`, backticks) break out of the intended command.

**Why it happens:**
Using `create_subprocess_shell` instead of `create_subprocess_exec`, or building command strings manually. The PROJECT.md specifies "Bash/zsh script that manages Claude Code CLI sessions" -- if this wrapper script receives the user message as a positional parameter and does not quote it, injection is possible.

**How to avoid:**
Always use `asyncio.create_subprocess_exec()` which passes arguments as a list, not a shell string. Never use `shell=True`. If using a bash/zsh wrapper script, ensure the script uses `"$@"` (quoted) not `$*` (unquoted), and passes the message via stdin rather than as a positional argument. For very long prompts, always use stdin piping:
```python
process = await asyncio.create_subprocess_exec(
    "claude", "-p", "--bare", "--output-format", "stream-json",
    stdin=asyncio.subprocess.PIPE,
    stdout=asyncio.subprocess.PIPE,
    stderr=asyncio.subprocess.PIPE,
)
process.stdin.write(prompt.encode("utf-8"))
process.stdin.close()
```

**Warning signs:**
- Code review finds any `shell=True`, `create_subprocess_shell`, or string formatting in CLI command construction
- Bash wrapper script uses `$1` or `$*` without quoting
- Tests never include prompts with shell metacharacters

**Phase to address:**
Phase 1 (Core subprocess infrastructure). Security-critical from first implementation.

---

### Pitfall 8: Error Propagation Loss Across Process Boundary

**What goes wrong:**
When Claude Code encounters an error (API rate limit, authentication expiry, internal crash, tool execution failure), the error information is encoded differently depending on the output format. In `--output-format json`, errors appear as `{"is_error": true, "result": "error message"}`. In `stream-json` mode, errors may appear as specific event types, or the process may crash with a non-zero exit code and error text only in stderr. If the wrapper only checks exit codes or only checks stdout, entire categories of errors are silently swallowed.

**Why it happens:**
CLI tools encode errors in multiple channels simultaneously: exit code (coarse: 0 or 1), stdout (structured error in JSON), stderr (diagnostic text, stack traces), and sometimes the absence of expected output. Developers implement the happy path and handle only one error channel. Claude Code's exit codes are minimally informative, so relying on exit code alone loses the detailed error type needed for retry logic.

**How to avoid:**
Implement a three-channel error detection strategy:
1. **Exit code**: Non-zero means something failed, but check stdout/stderr for specifics
2. **stdout JSON**: Parse `is_error` field; extract `result` field for error message
3. **stderr**: Capture and log always; parse for authentication failures, rate limits, crash stack traces

Map Claude Code errors to nanobot's existing `LLMResponse` error model:
- Rate limit errors -> `finish_reason="error"`, `error_status_code=429`
- Auth failures -> non-retryable error with user-facing message
- Tool failures -> report in tool result, do not crash the turn
- Process crash -> `finish_reason="error"` with diagnostic context

The existing `LLMProvider._is_transient_response` logic must work with the CLI proxy's error format. Parse stderr for rate-limit indicators ("rate limit", "too many requests", "try again") to trigger the retry-with-backoff logic already in `chat_with_retry`.

**Warning signs:**
- Users see generic "Error executing command" instead of "Rate limit exceeded, retrying in 30s"
- Retry logic never triggers because errors are not classified as transient
- Auth expiry causes repeated failures without a "please re-authenticate" message

**Phase to address:**
Phase 1 (basic detection), Phase 3 (retry classification and user-facing messages that match the existing provider error model).

---

### Pitfall 9: Session ID Format Mismatch Causes Silent Session Loss

**What goes wrong:**
Claude Code requires session IDs to be valid UUIDs. Passing an arbitrary string (e.g., nanobot's `channel:chat_id` session key format) as `--session-id` causes a silent failure or error. The conversation history is not persisted to Claude Code's session store, meaning the next `--resume` call starts fresh without context. Users experience "amnesia" where Claude forgets their conversation.

**Why it happens:**
Nanobot uses composite session keys like `telegram:12345` or `discord:guild_channel`. Claude Code's `--session-id` flag validates that the value is a UUID. Developers test with hardcoded valid UUIDs during development but the mapping breaks in production.

**How to avoid:**
Maintain a mapping layer between nanobot session keys and Claude Code session UUIDs. Generate a deterministic UUID from the nanobot session key using `uuid.uuid5(uuid.NAMESPACE_URL, session_key)` for consistent mapping without a persistent lookup table. Store the Claude Code session UUID alongside the nanobot session metadata. Always validate the JSON response's `is_error` field and `session_id` return value after each invocation.

**Warning signs:**
- Conversation context lost between turns despite using `--resume`
- `session_id` in JSON output does not match what was passed in
- Error messages mentioning invalid UUID format in stderr
- Tests pass with hardcoded UUIDs but fail with real session keys

**Phase to address:**
Phase 2 (Session management). Must be designed correctly before multi-turn conversations work.

---

### Pitfall 10: Unbounded Process Accumulation Under Concurrent Load

**What goes wrong:**
Each chat turn spawns a new `claude` subprocess. Under concurrent load (multiple channels, multiple users, group chats), dozens of processes accumulate. Each process loads the Node.js runtime (~50-100MB), making the system memory-bound. Without concurrency limiting, the host machine can run out of memory or PIDs.

**Why it happens:**
No concurrency limiting on subprocess spawning. Each `chat_stream()` call spawns independently. Group chats can trigger many simultaneous requests.

**How to avoid:**
Use an `asyncio.Semaphore` to bound concurrent CLI processes (recommended: 3-5 max). Queue excess requests. Implement per-session subprocess reuse for persistent mode so that multi-turn conversations use a single long-lived process instead of spawning per turn.

**Warning signs:**
- Monitor process count: `pgrep -c claude` increasing without bound
- OOM kills in system logs
- Response latency increasing under moderate load as processes compete for resources

**Phase to address:**
Phase 1 (Core subprocess infrastructure) for the semaphore. Phase 2 (Session management) for persistent subprocess reuse.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| One-shot subprocess per turn (no persistent session) | Simple implementation, no state management | 10x token overhead from config reininjection, 1-2s startup latency per turn | MVP / Phase 1 only; must migrate to persistent session in Phase 2 |
| Capturing full stdout/stderr with `communicate()` instead of streaming | Avoids deadlock, simple error handling | No real-time streaming -- user sees nothing until Claude finishes entire response | Never for production; acceptable only for initial integration testing |
| Passing user message as CLI argument instead of stdin pipe | Avoids stdin encoding issues | Shell injection risk if message contains metacharacters; argument length limits (~128KB Linux, ~256KB macOS) | Only with `create_subprocess_exec` (not shell) and only for short one-shot prompts; use stdin for persistent mode |
| Merging stderr into stdout (`stderr=STDOUT`) | One stream to read, no deadlock risk | Cannot distinguish errors from response data; breaks JSON parsing when stderr diagnostic lands mid-JSON | Never; always keep streams separate |
| Hardcoding `claude` binary path | Quick local development | Fails in container, CI, or systems where claude is installed to a non-standard path | Never; use `shutil.which("claude")` with fallback and clear error message |
| Using `json_repair.loads()` as primary parser | Handles malformed JSON from edge cases | Masks real parsing bugs; may silently "fix" data into incorrect structures | Only as a last-resort fallback after `json.loads()` fails, never as the primary parser |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Claude Code `--resume` with nanobot session keys | Passing nanobot's composite session key (e.g., `telegram:12345`) directly as `--session-id` | Generate UUID v5 from session key via `uuid.uuid5(uuid.NAMESPACE_URL, session_key)`; store mapping in session metadata |
| Claude Code `--system-prompt` with nanobot personas | Passing multi-line persona text as a CLI argument with embedded quotes/newlines | Use `--system-prompt-file` with a temp file, or `--append-system-prompt-file`; clean up temp file after process exits |
| Claude Code `--output-format json` cost tracking | Ignoring the `total_cost_usd` and `usage` fields in the JSON response | Extract and propagate to nanobot's usage tracking; useful for per-user budget enforcement |
| Claude Code auth status | Assuming auth is always valid; no check before spawning subprocess | Run `claude auth status` on provider initialization; cache result; re-check on 401-like errors |
| Claude Code version compatibility | Hardcoding flag names that may change between versions | Run `claude --version` on startup; log warning if below tested minimum; wrap flag construction for version differences |
| Routing through `ExecTool` | Using nanobot's `ExecTool` to spawn the `claude` process, subjecting it to deny-list pattern matching | Create a dedicated subprocess manager for the bypass provider that is not subject to `ExecTool` deny patterns |
| Existing sandbox (`bwrap`) | Applying nanobot's `bwrap` sandbox to the `claude` subprocess, which then cannot spawn its own child processes | Do not sandbox `claude` itself; Claude Code has its own permission system. For host isolation, containerize nanobot + Claude Code together |
| `--input-format stream-json` protocol | Treating this as a documented stable API | This format is currently undocumented (GitHub issue #24594); the message envelope format was reverse-engineered from third-party projects. Expect breaking changes. |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Spawning a new `claude` process per message | 1-2s response latency per message, PID accumulation, token waste | Use persistent session subprocess for active conversations; expire idle sessions after timeout | Immediately in any group chat with rapid back-and-forth |
| Not using `--bare` flag | ~50K input tokens per turn, 3-5 second startup delay | Always pass `--bare`; provide system prompt explicitly | Noticeable from the very first request; compounds rapidly |
| Synchronous `process.wait()` in the async event loop | Entire nanobot event loop blocks; other channels freeze | Always use `await process.wait()` via asyncio. Existing `ExecTool` uses `asyncio.create_subprocess_exec` correctly -- follow that pattern | Immediately with any concurrent user |
| Reading stream-json output without backpressure | Memory growth when Claude produces output faster than downstream channel can deliver (Telegram/Discord rate limits) | Buffer a max of stream events; if buffer exceeds threshold, switch to final-result-only mode | Under load with slow downstream channels |
| No idle subprocess timeout | Persistent session subprocesses accumulate for users who leave and never return | Expire persistent subprocesses after N minutes of inactivity (recommended: 5-10 minutes); terminate process group on expiry | After hours/days of operation with many unique users |

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Passing user message as shell argument without escaping | Shell injection: arbitrary command execution on host | Use `create_subprocess_exec` (not shell); pass arguments as list. Bash wrapper must use `"$@"` and receive message via stdin |
| Leaking API keys through subprocess environment | Claude Code inherits nanobot's env, which may contain `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, etc. | Use same minimal env approach as `ExecTool._build_env()`: only `HOME`, `LANG`, `TERM`. Set `CLAUDE_CODE_SUBPROCESS_ENV_SCRUB=1` |
| Multi-user session sharing | User B reads user A's conversation history including secrets | Always use per-user, per-channel sessions. Session-to-UUID mapping must include user identity, not just channel |
| Unrestricted `--max-budget-usd` in gateway mode | Single user triggers unbounded API spending | Always set `--max-budget-usd`; enforce per-user or per-session budget via nanobot config |
| Running Claude Code as root | Full host access via bash tool | Run as unprivileged user. Non-root user in Dockerfile for container deployments |

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| No streaming -- user waits for full response | 10-30 second perceived hang on complex prompts; users resend thinking bot is broken | Stream partial responses using `--output-format stream-json` with `--verbose`; deliver content deltas via `on_content_delta` |
| Raw Claude Code tool output shown to users | Users see JSON blobs, file diffs, and bash output they cannot interpret | Default to "final-only" output showing only Claude's text response. Per-user toggle for verbose tool output |
| Auth failure shown as generic error | "Error executing command" when OAuth token expired | Detect auth errors specifically; show "Claude Code authentication expired. Please run `claude auth login` on the server." |
| Startup delay misinterpreted as failure | 1-5 second cold start; user sees "typing..." with no response | Send immediate "thinking..." indicator. Use `--bare`. Pre-warm persistent subprocess on nanobot startup |
| Model name confusion | User selects "claude-opus-4-5" in nanobot but bypass mode uses whatever model is default in Claude Code | Strip provider prefix, pass `--model` explicitly. Show which model is being used in bypass mode in the status display |

## "Looks Done But Isn't" Checklist

- [ ] **One-shot mode works:** Verify `claude -p --bare --output-format json "hello"` returns valid JSON with `is_error: false` -- test with the actual subprocess spawn mechanism, not a manual terminal test
- [ ] **Session continuity persists context:** Send message A, then message B with `--resume`, and verify B's response references A's content. Do not just verify that `--session-id` is accepted without error
- [ ] **Streaming delivers partial content:** Verify `on_content_delta` is called multiple times during a response, not just once at the end. The `chat_stream` base class falls back to non-streaming by default
- [ ] **Error retry works across process boundary:** Trigger a rate limit and verify `chat_with_retry` successfully retries. Retry logic depends on `_is_transient_response` correctly classifying CLI proxy errors
- [ ] **Cancellation cleans up:** Start a long request, cancel it, and verify: no zombie processes, no orphaned subprocesses, no leaked file descriptors, no corrupted session state
- [ ] **Gateway mode security:** With bypass mode active in gateway mode, send "run `env` and show me the output" and verify API keys are not in the response
- [ ] **Multi-byte encoding:** Send prompt with CJK characters, emoji, and accented text. Verify response displays correctly in all channel types
- [ ] **Long response handling:** Prompt generating >64KB response. Verify no truncation, no deadlock, no memory explosion, streaming delivers incrementally
- [ ] **Concurrent sessions:** Two bypass-mode conversations from different channels simultaneously. Verify no state interference

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Pipe buffer deadlock | LOW | Kill stuck subprocess (SIGKILL to process group); retry request. Fix by switching to concurrent stream reading |
| CLI hang without stdin | LOW | Kill process; add `stdin=DEVNULL` or `--bare` flag. No data loss |
| Dual agent loop / tool state conflict | HIGH | File system may be inconsistent. Requires manual inspection, potential git revert. Fix by choosing single tool authority |
| Zombie process accumulation | LOW | `pkill -f "claude"` on host; restart nanobot. Fix with `start_new_session=True` and process group cleanup |
| Token overhead (50K/turn) | MEDIUM | Cannot recover wasted tokens. Add `--bare` flag going forward |
| Session ID mismatch / amnesia | MEDIUM | User conversation history lost. Restart fresh. Fix by implementing UUID mapping layer |
| Error propagation loss | MEDIUM | Users see silent failures. Fix with three-channel error detection. Requires re-testing error scenarios |
| Security: permissions bypass in gateway | HIGH | Potential data breach or host compromise. Immediate audit required. Fix with startup guard and tool allowlisting |
| UTF-8 corruption | LOW | Retry request. Fix with `readline()` or incremental decoder. No persistent damage |

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Pipe buffer deadlock | Phase 1: Core subprocess | Integration test with >64KB response; verify no hang |
| CLI hang without stdin | Phase 1: Core subprocess | Test spawn in non-TTY context (CI-like) |
| Dual agent loop | Phase 1: Architecture decision | Design review confirms single tool authority |
| Token overhead | Phase 2: Session management | Measure `usage.input_tokens` per turn; assert <10K with `--bare` |
| Zombie processes | Phase 1: Core subprocess | Stress test: spawn 50+ subprocesses, kill nanobot, verify no orphans |
| Permissions bypass | Phase 1: Core subprocess | Security test: gateway mode refuses `--dangerously-skip-permissions` |
| Shell injection | Phase 1: Core subprocess | Test with prompts containing `$()`, backticks, semicolons, quotes |
| Error propagation | Phase 1 (basic) / Phase 3 (retry) | Simulate rate limit, auth failure, crash; verify `LLMResponse` fields |
| Session ID mismatch | Phase 2: Session management | Round-trip: 3 messages, verify context continuity |
| Process accumulation | Phase 1 (semaphore) / Phase 2 (reuse) | Load test: 20 concurrent requests; verify max N subprocesses |
| Stream JSON parsing | Phase 1: Core subprocess | Fuzz test: partial lines, empty lines, malformed JSON |
| UTF-8 encoding | Phase 1: Core subprocess | Test with CJK, emoji, RTL text in prompt and response |

## Nanobot-Specific Concerns

Pitfalls that interact with existing codebase issues documented in CONCERNS.md.

| Existing Concern | Interaction with Bypass Mode | Mitigation |
|------------------|------------------------------|------------|
| Session files lack write locking (`SessionManager.save`) | Bypass mode adds Claude Code session UUID to session metadata; concurrent saves could corrupt the mapping | Use `filelock.FileLock` (already a project dependency) around session saves that include bypass metadata |
| `_active_tasks` list per session not cleaned up | Persistent bypass subprocesses are long-lived tasks that must be tracked | Register persistent subprocess as a managed task; clean up on session clear/expiry |
| `except Exception: pass` in TTY setup and MCP cleanup | Silent failures in startup could mask Claude Code binary-not-found or auth failures | Replace bare `except` with logged exceptions in bypass provider initialization |
| `_snip_history` discards history without warning | In bypass mode, nanobot does not manage conversation history (Claude Code does). If nanobot also stores history for display, snipping desynchronizes displayed history from Claude Code's actual context | Separate "display history" (nanobot's store) from "conversation context" (Claude Code's session). Do not attempt context windowing for bypass mode |
| Shell command deny-list bypass in `ExecTool` | If bypass mode uses a bash wrapper script via `ExecTool`, the deny-list may block legitimate `claude` invocations | Do not route `claude` subprocess through `ExecTool`. Create a dedicated subprocess manager |
| Unbounded `_session_locks` dict grows forever | Bypass mode adds per-session subprocess tracking; both the lock dict and subprocess dict grow without bound | Prune both dicts when sessions are cleared. Use idle timeout to terminate and remove stale bypass subprocesses |

## Sources

- [Claude Code CLI Reference (official docs)](https://code.claude.com/docs/en/cli-reference)
- [Why Claude Code Subagents Waste 50K Tokens Per Turn (DEV Community, Feb 2026)](https://dev.to/jungjaehoon/why-claude-code-subagents-waste-50k-tokens-per-turn-and-how-to-fix-it-41ma)
- [Wrapping Claude CLI for Agentic Applications (avasdream.com)](https://avasdream.com/blog/claude-cli-agentic-wrapper)
- [Using Claude Code Programmatically (GitHub gist by JacobFV)](https://gist.github.com/JacobFV/2c4a75bc6a835d2c1f6c863cfcbdfa5a)
- [Claude CLI Hangs Without TTY (GitHub issue #9026)](https://github.com/anthropics/claude-code/issues/9026)
- [Claude Code exits on HPC -- stdin consumed (GitHub issue #12507)](https://github.com/anthropics/claude-code/issues/12507)
- [`--input-format stream-json` undocumented (GitHub issue #24594)](https://github.com/anthropics/claude-code/issues/24594)
- [Python asyncio subprocess documentation](https://docs.python.org/3/library/asyncio-subprocess.html)
- [Python subprocess deadlock (CPython issue #14872)](https://bugs.python.org/issue14872)
- [asyncio proc.kill() counterintuitive (CPython issue #119710)](https://github.com/python/cpython/issues/119710)
- [How to Safely Kill Python Subprocesses Without Zombies (DEV Community)](https://dev.to/generatecodedev/how-to-safely-kill-python-subprocesses-without-zombies-3h9g)
- [pip-audit stdout UTF-8 corruption at buffer boundary (GitHub issue #573)](https://github.com/pypa/pip-audit/issues/573)
- [Claude Code Releases / Changelog](https://github.com/anthropics/claude-code/releases)

---
*Pitfalls research for: CLI subprocess proxy wrapping Claude Code CLI*
*Researched: 2026-04-09*
