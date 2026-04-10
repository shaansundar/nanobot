# Phase 4: Robustness - Research

**Researched:** 2026-04-09
**Domain:** Subprocess lifecycle hardening (process groups, concurrency, env isolation)
**Confidence:** HIGH

## Summary

Phase 4 hardens the `ClaudeCodeProvider._run_cli()` subprocess execution for production use. The three requirements address distinct failure modes: zombie process accumulation (ROBU-01), resource exhaustion from unbounded concurrency (ROBU-02), and API key leakage in gateway/multi-user mode (ROBU-03).

The codebase already contains proven patterns for all three concerns. `ExecTool._kill_process()` demonstrates zombie prevention via kill-then-wait, `ExecTool._build_env()` provides the exact environment isolation pattern needed, and `AgentLoop._concurrency_gate` implements the semaphore-based concurrency limiting pattern. The work is primarily adapting these established patterns to `ClaudeCodeProvider`, adding `start_new_session=True` for process-group-level signal delivery, and extending `ClaudeCodeProviderConfig` with two new fields.

**Primary recommendation:** Follow the existing codebase patterns exactly. Use `start_new_session=True` + `os.killpg()` for process group management, `asyncio.Semaphore` as the concurrency gate, and a minimal env dict modeled on `ExecTool._build_env()`. All three changes converge on `_run_cli()` and `__init__()`.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Use `start_new_session=True` in `create_subprocess_exec` to create a process group, enabling group-level signal delivery
- **D-02:** Add `asyncio.wait_for(proc.communicate(), timeout=300)` with 5-minute default timeout (configurable via config)
- **D-03:** On timeout: send SIGTERM to process group, wait 5s, then SIGKILL if still alive
- **D-04:** Always `await proc.wait()` after process completes to reap the child and prevent zombies
- **D-05:** Register an `atexit` handler or use `try/finally` to kill any in-flight subprocess on provider shutdown
- **D-06:** Add `asyncio.Semaphore` to `ClaudeCodeProvider` with configurable max concurrent subprocesses
- **D-07:** Config field `max_concurrent: int` on `ClaudeCodeProviderConfig` (default: `5`)
- **D-08:** Acquire semaphore before subprocess spawn, release in `finally` block after completion
- **D-09:** When semaphore is full, new requests queue (asyncio.Semaphore blocks awaiting coroutines) -- no rejection, just backpressure
- **D-10:** In gateway mode (detected via `config.channels` having active channels), pass a minimal env dict to `create_subprocess_exec`
- **D-11:** Minimal env: `HOME`, `PATH`, `LANG`, `TERM`, `USER`, `SHELL` -- strips all API keys (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `OPENROUTER_API_KEY`, etc.)
- **D-12:** In CLI-only mode (no channels), inherit full env (user's own machine, no isolation needed)
- **D-13:** Config field `env_isolation: bool` on `ClaudeCodeProviderConfig` (default: `true` when channels active, `false` otherwise) -- user can override

### Claude's Discretion
- Exact timeout value (5 minutes is the default, but may need tuning)
- Whether to log subprocess PIDs for debugging
- Whether semaphore limit applies per-session or globally

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| ROBU-01 | Subprocess processes are properly managed with no zombie accumulation (process group kill + wait) | D-01 through D-05; `ExecTool._kill_process()` pattern; `start_new_session=True` + `os.killpg()` |
| ROBU-02 | Concurrent Claude Code subprocesses are limited via asyncio.Semaphore to prevent resource exhaustion | D-06 through D-09; `AgentLoop._concurrency_gate` pattern; `asyncio.Semaphore` best practices |
| ROBU-03 | In gateway mode, subprocess environment is isolated (strip API keys, sensitive env vars) | D-10 through D-13; `ExecTool._build_env()` pattern; `ChannelsConfig` extra-allow detection |
</phase_requirements>

## Standard Stack

### Core

No new dependencies are needed. All required APIs are in Python's standard library.

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `asyncio` | stdlib (3.11+) | `create_subprocess_exec`, `wait_for`, `Semaphore` | Python's native async subprocess and sync primitives |
| `os` | stdlib | `killpg`, `getpgid`, `waitpid`, `environ` | POSIX process group management |
| `signal` | stdlib | `SIGTERM`, `SIGKILL` constants | Signal delivery to process groups |
| `atexit` | stdlib | Shutdown hook registration | Cleanup on interpreter exit |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `pydantic` | >=2.12.0 (project dep) | `ClaudeCodeProviderConfig` field extension | Schema for `max_concurrent` and `env_isolation` fields |
| `loguru` | >=0.7.3 (project dep) | Subprocess PID logging | Debug logging for process lifecycle events |

### Alternatives Considered

None -- all decisions are locked. No alternative approaches apply.

## Architecture Patterns

### Modification Points

```
nanobot/
├── config/
│   └── schema.py               # Extend ClaudeCodeProviderConfig (+2 fields)
├── providers/
│   └── claude_code_provider.py  # Harden _run_cli(), extend __init__()
├── nanobot.py                   # Pass config to provider constructor
├── cli/
│   └── commands.py              # Pass config to provider constructor (2 sites)
└── tests/providers/
    └── test_claude_code_provider.py  # Add robustness tests
```

### Pattern 1: Process Group Lifecycle (ROBU-01)

**What:** Spawn subprocess in its own session/process group, apply timeout with graceful-then-forceful termination, always reap.

**When to use:** Every `_run_cli()` invocation.

**Key insight:** `start_new_session=True` makes the subprocess the leader of a new process group. `os.killpg(pgid, signal)` sends signals to all processes in that group, including any children Claude Code spawns internally. Without this, `proc.kill()` only terminates the direct child -- Claude Code's internal subprocesses become orphans.

**Example:**
```python
# Source: Python 3.11+ asyncio-subprocess docs + ExecTool._kill_process pattern
import os
import signal

proc = await asyncio.create_subprocess_exec(
    *cmd,
    stdin=asyncio.subprocess.DEVNULL,
    stdout=asyncio.subprocess.PIPE,
    stderr=asyncio.subprocess.PIPE,
    start_new_session=True,  # D-01: new process group
)

try:
    stdout_bytes, stderr_bytes = await asyncio.wait_for(
        proc.communicate(), timeout=timeout  # D-02: configurable timeout
    )
except asyncio.TimeoutError:
    # D-03: graceful then forceful
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
    except (ProcessLookupError, PermissionError):
        pass
    try:
        await asyncio.wait_for(proc.wait(), timeout=5.0)
    except asyncio.TimeoutError:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
    await proc.wait()  # D-04: always reap
    # Return timeout error response
```

**Critical detail -- `os.killpg` exception handling:** After sending SIGTERM/SIGKILL, the process may have already exited. `os.killpg()` raises `ProcessLookupError` if the process group no longer exists. Always catch `ProcessLookupError` and `PermissionError` around signal delivery calls.

### Pattern 2: Semaphore Concurrency Gate (ROBU-02)

**What:** Wrap subprocess spawning in an asyncio.Semaphore to bound concurrent processes.

**When to use:** Every `_run_cli()` invocation.

**Existing codebase pattern (AgentLoop lines 206-209):**
```python
# Source: nanobot/agent/loop.py lines 206-209
_max = int(os.environ.get("NANOBOT_MAX_CONCURRENT_REQUESTS", "3"))
self._concurrency_gate: asyncio.Semaphore | None = (
    asyncio.Semaphore(_max) if _max > 0 else None
)
```

**For ClaudeCodeProvider:**
```python
# In __init__:
self._subprocess_semaphore = asyncio.Semaphore(max_concurrent)

# In _run_cli:
async with self._subprocess_semaphore:
    proc = await asyncio.create_subprocess_exec(...)
    # ... timeout handling, cleanup ...
```

**Key decision (Claude's discretion):** The semaphore should be **global** (per-provider-instance), not per-session. Rationale: the concern is host resource exhaustion (PIDs, memory from Node.js processes), which is a machine-level constraint regardless of which session triggers the spawn. The existing `AgentLoop._concurrency_gate` is also global for the same reason.

### Pattern 3: Environment Isolation Gateway (ROBU-03)

**What:** In gateway mode, pass a minimal environment dict to the subprocess that strips API keys. In CLI mode, inherit the full environment.

**When to use:** Whenever `_run_cli()` spawns a subprocess and `env_isolation` is enabled.

**Existing codebase pattern (ExecTool._build_env, lines 199-233):**
```python
# Source: nanobot/agent/tools/shell.py lines 228-233
# Unix minimal env (ExecTool uses this for ALL shell executions)
home = os.environ.get("HOME", "/tmp")
return {
    "HOME": home,
    "LANG": os.environ.get("LANG", "C.UTF-8"),
    "TERM": os.environ.get("TERM", "dumb"),
}
```

**Adaptation for ClaudeCodeProvider (D-11):**
```python
def _build_isolated_env(self) -> dict[str, str]:
    """Build a minimal env for gateway mode -- strips API keys."""
    return {
        "HOME": os.environ.get("HOME", "/tmp"),
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "LANG": os.environ.get("LANG", "C.UTF-8"),
        "TERM": os.environ.get("TERM", "dumb"),
        "USER": os.environ.get("USER", ""),
        "SHELL": os.environ.get("SHELL", "/bin/sh"),
    }
```

**Key difference from ExecTool:** ClaudeCodeProvider must include `PATH` explicitly because `claude` is invoked directly via `create_subprocess_exec` with a resolved path, but Claude Code itself spawns subprocesses (Node.js, npm) that need `PATH` to find their dependencies. ExecTool uses `bash -l` which sources the profile for PATH, but our provider does not.

**Gateway mode detection (D-10):** `ChannelsConfig` uses `model_config = ConfigDict(extra="allow")`, meaning channel configs (telegram, discord, slack, etc.) are stored as extra fields. A channel is active when its config dict has `enabled: true`. The detection is: iterate `ChannelsConfig` extra fields, check for any with `enabled=True`.

### Anti-Patterns to Avoid

- **Using `proc.kill()` without `start_new_session`:** Only kills the direct child. Claude Code's internal subprocesses (Node.js workers, MCP servers) become orphaned.
- **Forgetting `await proc.wait()` after kill:** The process entry stays in the process table as a zombie.
- **Using `os.kill(proc.pid, signal)` instead of `os.killpg()`:** Only signals the group leader, not its children.
- **Using `atexit` with async cleanup:** `atexit` handlers cannot run async code. Use `try/finally` in the async context, and `atexit` only as a last-resort synchronous fallback.
- **Passing `env=None` (inherit) in gateway mode:** Leaks `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, and all other secrets to the subprocess environment, accessible to any channel user.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Process group management | Custom child-process tracking | `start_new_session=True` + `os.killpg()` | OS-level process groups handle all descendants automatically |
| Concurrency limiting | Custom queue with worker pool | `asyncio.Semaphore` | Built-in, battle-tested, handles cancellation correctly |
| Environment stripping | Regex-based key filtering | Explicit allowlist dict | Allowlist is safer -- you cannot accidentally miss a new secret |
| Timeout enforcement | Manual timer task | `asyncio.wait_for()` | Handles cancellation propagation correctly |

**Key insight:** Every component here is a stdlib primitive. The complexity is in the composition (timeout + kill + wait + semaphore + env), not in any individual piece.

## Common Pitfalls

### Pitfall 1: `os.killpg` After Process Already Exited

**What goes wrong:** The subprocess exits normally before the timeout. Code then calls `os.killpg()` in a finally block and gets `ProcessLookupError`, which propagates up and masks the actual result.

**Why it happens:** The kill logic is in a finally block that runs on both normal and timeout paths.

**How to avoid:** Always wrap `os.killpg()` in `try/except (ProcessLookupError, PermissionError): pass`. Only call kill functions when you know the process needs termination (i.e., on the timeout path, not on the normal exit path).

**Warning signs:** Sporadic `ProcessLookupError` in logs after successful responses.

### Pitfall 2: `proc.wait()` Hangs When Pipes Are Open

**What goes wrong:** After `os.killpg(SIGKILL)`, `await proc.wait()` hangs because stdout/stderr pipes are still open (held by child processes that did not receive the signal).

**Why it happens:** This is a documented CPython behavior (issue #119710). `proc.wait()` blocks until pipes are closed, not just until the process exits.

**How to avoid:** Use `asyncio.wait_for(proc.wait(), timeout=5.0)` even after SIGKILL. If that times out, log a warning and move on -- the zombie will eventually be reaped by the OS init process. The existing `ExecTool._kill_process` uses this exact pattern.

**Warning signs:** `_run_cli` appears to hang indefinitely after a timeout kill.

### Pitfall 3: Semaphore Not Released on CancelledError

**What goes wrong:** If the calling task is cancelled while waiting inside `async with semaphore`, the semaphore slot is leaked and never released.

**Why it happens:** `asyncio.CancelledError` can interrupt the `await` inside the semaphore `__aenter__`. If not properly handled, the acquire count never decrements.

**How to avoid:** Use `async with self._subprocess_semaphore:` which correctly handles cancellation in Python 3.11+. The `async with` statement ensures release even on `CancelledError`. Do NOT manually acquire/release with try/finally -- the context manager handles edge cases correctly.

**Warning signs:** After several cancellations, all requests start queueing indefinitely because semaphore slots are exhausted.

### Pitfall 4: Gateway Mode Detection Misses CLI-Only Mode

**What goes wrong:** The `env_isolation` default is computed at provider construction time, but the provider is constructed before channels are started. If detection checks something that is only populated later, isolation is never enabled.

**Why it happens:** Provider construction happens early in startup. Channel configs exist in the YAML but channel objects have not been instantiated yet.

**How to avoid:** Detect gateway mode from `ChannelsConfig` data (the Pydantic model), not from running `ChannelManager` instances. Check for any extra field in `ChannelsConfig` that has `enabled: true`. This data is available at config-load time, before channels start.

**Warning signs:** Gateway mode running without env isolation; API keys visible to channel users.

### Pitfall 5: macOS vs Linux Signal Behavior

**What goes wrong:** On macOS, `os.killpg()` may fail with `PermissionError` for certain process group configurations.

**Why it happens:** macOS has stricter process group signal delivery rules. Processes that have changed their own session ID may not be reachable via the original PGID.

**How to avoid:** Always catch both `ProcessLookupError` and `PermissionError` around `os.killpg()`. Fall back to `proc.kill()` (single-process kill) if group kill fails.

**Warning signs:** Tests pass on Linux CI but fail on developer macOS machines.

## Code Examples

### Complete `_run_cli` with All Three Hardening Layers

```python
# Source: Composition of D-01 through D-13, existing ExecTool patterns
import os
import signal

async def _run_cli(self, cmd: list[str]) -> LLMResponse:
    """Execute a CLI command with lifecycle hardening."""
    async with self._subprocess_semaphore:  # ROBU-02
        env = self._build_isolated_env() if self._env_isolation else None  # ROBU-03
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            start_new_session=True,  # ROBU-01: process group
            env=env,
        )
        logger.debug("Claude Code subprocess started, pid={}", proc.pid)
        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(), timeout=self._timeout
            )
        except asyncio.TimeoutError:
            self._kill_process_group(proc)
            return LLMResponse(
                content=f"Claude Code CLI timed out after {self._timeout}s",
                tool_calls=[],
                finish_reason="error",
            )
        except asyncio.CancelledError:
            self._kill_process_group(proc)
            raise
        finally:
            # D-04: always reap
            if proc.returncode is None:
                try:
                    await asyncio.wait_for(proc.wait(), timeout=2.0)
                except asyncio.TimeoutError:
                    pass
        return self._parse_result(stdout_bytes, stderr_bytes, proc.returncode)
```

### Config Extension

```python
# Source: nanobot/config/schema.py pattern
class ClaudeCodeProviderConfig(Base):
    """Configuration for Claude Code CLI bypass provider."""

    cli_path: str = ""
    session_mode: str = "session"
    max_concurrent: int = Field(default=5, ge=1, le=20)  # D-07
    env_isolation: bool | None = None  # D-13: None = auto-detect
    timeout: int = Field(default=300, ge=30, le=1800)  # D-02: 5 min default
```

### Gateway Mode Detection

```python
# Source: ChannelsConfig extra="allow" pattern from schema.py
def _has_active_channels(channels_config) -> bool:
    """Return True if any channel is enabled in the config."""
    if channels_config is None:
        return False
    # ChannelsConfig uses extra="allow" -- channel configs are extra fields
    extras = channels_config.model_extra or {}
    for _name, section in extras.items():
        enabled = (
            section.get("enabled", False)
            if isinstance(section, dict)
            else getattr(section, "enabled", False)
        )
        if enabled:
            return True
    return False
```

### Provider Constructor Extension

```python
# Provider __init__ needs: config object or individual params
def __init__(
    self,
    cli_path: str | None = None,
    default_model: str = _DEFAULT_MODEL,
    max_concurrent: int = 5,
    env_isolation: bool = False,
    timeout: int = 300,
) -> None:
    # ... existing init ...
    self._subprocess_semaphore = asyncio.Semaphore(max_concurrent)
    self._env_isolation = env_isolation
    self._timeout = timeout
```

### Construction Sites Update

Both `nanobot.py` and `cli/commands.py` need updating:

```python
# In _make_provider (nanobot.py and cli/commands.py)
elif backend == "claude_code":
    from nanobot.providers.claude_code_provider import ClaudeCodeProvider

    cc_cfg = getattr(config.providers, "claude_code", None)
    cli_path = cc_cfg.cli_path if cc_cfg and cc_cfg.cli_path else None
    max_concurrent = cc_cfg.max_concurrent if cc_cfg else 5
    timeout = cc_cfg.timeout if cc_cfg else 300

    # D-13: auto-detect env_isolation from channel config
    env_isolation = cc_cfg.env_isolation if (cc_cfg and cc_cfg.env_isolation is not None) else None
    if env_isolation is None:
        env_isolation = _has_active_channels(config.channels)

    provider = ClaudeCodeProvider(
        cli_path=cli_path,
        default_model=model,
        max_concurrent=max_concurrent,
        env_isolation=env_isolation,
        timeout=timeout,
    )
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `proc.kill()` on single PID | `os.killpg()` on process group | Always best practice | Prevents orphaned child processes |
| `proc.communicate()` with no timeout | `asyncio.wait_for(proc.communicate(), timeout)` | Python 3.11 stabilized | Prevents infinite hangs |
| Inheriting full env in subprocess | Explicit minimal env dict | Security best practice | Prevents secret leakage |

**No deprecated/outdated patterns apply.** All APIs used are current Python 3.11+ stdlib.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 + pytest-asyncio |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` with `asyncio_mode = "auto"` |
| Quick run command | `pytest tests/providers/test_claude_code_provider.py -x -q` |
| Full suite command | `pytest tests/ -x -q` |

### Phase Requirements -> Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| ROBU-01 | `start_new_session=True` passed to `create_subprocess_exec` | unit | `pytest tests/providers/test_claude_code_provider.py::test_start_new_session_enabled -x` | Wave 0 |
| ROBU-01 | On timeout, SIGTERM sent to process group | unit | `pytest tests/providers/test_claude_code_provider.py::test_timeout_sends_sigterm -x` | Wave 0 |
| ROBU-01 | After SIGTERM grace period, SIGKILL sent | unit | `pytest tests/providers/test_claude_code_provider.py::test_timeout_escalates_to_sigkill -x` | Wave 0 |
| ROBU-01 | `proc.wait()` always called (zombie prevention) | unit | `pytest tests/providers/test_claude_code_provider.py::test_proc_wait_always_called -x` | Wave 0 |
| ROBU-01 | Timeout returns error LLMResponse | unit | `pytest tests/providers/test_claude_code_provider.py::test_timeout_returns_error -x` | Wave 0 |
| ROBU-01 | CancelledError kills process and re-raises | unit | `pytest tests/providers/test_claude_code_provider.py::test_cancelled_kills_and_reraises -x` | Wave 0 |
| ROBU-02 | Semaphore limits concurrent subprocesses | unit | `pytest tests/providers/test_claude_code_provider.py::test_semaphore_limits_concurrency -x` | Wave 0 |
| ROBU-02 | Semaphore released after subprocess completes | unit | `pytest tests/providers/test_claude_code_provider.py::test_semaphore_released_on_success -x` | Wave 0 |
| ROBU-02 | Semaphore released on error | unit | `pytest tests/providers/test_claude_code_provider.py::test_semaphore_released_on_error -x` | Wave 0 |
| ROBU-02 | Config `max_concurrent` controls semaphore size | unit | `pytest tests/providers/test_claude_code_provider.py::test_max_concurrent_config -x` | Wave 0 |
| ROBU-03 | Gateway mode uses minimal env | unit | `pytest tests/providers/test_claude_code_provider.py::test_gateway_mode_minimal_env -x` | Wave 0 |
| ROBU-03 | CLI mode inherits full env | unit | `pytest tests/providers/test_claude_code_provider.py::test_cli_mode_full_env -x` | Wave 0 |
| ROBU-03 | Minimal env contains HOME, PATH, LANG, TERM, USER, SHELL only | unit | `pytest tests/providers/test_claude_code_provider.py::test_minimal_env_keys -x` | Wave 0 |
| ROBU-03 | API keys stripped in gateway mode | unit | `pytest tests/providers/test_claude_code_provider.py::test_api_keys_stripped -x` | Wave 0 |
| ROBU-03 | Config `env_isolation` overrides auto-detect | unit | `pytest tests/providers/test_claude_code_provider.py::test_env_isolation_config_override -x` | Wave 0 |

### Sampling Rate

- **Per task commit:** `pytest tests/providers/test_claude_code_provider.py -x -q`
- **Per wave merge:** `pytest tests/ -x -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- All 15 tests listed above are new -- they will be added in the test wave
- No new test infrastructure needed -- existing `FakeProcess` and `_make_provider` helpers in `test_claude_code_provider.py` cover the mocking pattern
- The `FakeProcess` mock will need extension to support: `pid` attribute, `returncode` as property that can be None initially, and a `wait()` that can be timed

## Open Questions

1. **Semaphore scope: global vs per-session**
   - What we know: The AgentLoop semaphore is global (per-instance). D-09 says "backpressure" which implies global.
   - What's unclear: Whether a single user session should be able to exhaust all slots.
   - Recommendation: Use global (per-provider-instance). Per-session would require tracking sessions in the semaphore logic, adding complexity for minimal benefit. The concern is machine-level resource exhaustion, not fairness.

2. **atexit handler vs try/finally for shutdown cleanup**
   - What we know: D-05 says "Register an `atexit` handler or use `try/finally`". atexit cannot run async code.
   - What's unclear: Whether nanobot has a clean shutdown hook where async cleanup runs.
   - Recommendation: Use `try/finally` in `_run_cli()` for per-call cleanup. For provider-level shutdown (killing all in-flight subprocesses), track active processes in a set and provide an `async def close()` method. Skip `atexit` -- it cannot properly await subprocess cleanup.

3. **Timeout value tuning**
   - What we know: D-02 says 5 minutes default, configurable.
   - What's unclear: Whether Claude Code CLI ever legitimately takes >5 minutes on a single turn.
   - Recommendation: 5 minutes (300s) is generous. Complex tool-use turns with file edits and bash commands could take 2-3 minutes. 5 minutes provides safety margin. The config field allows users to adjust.

## Sources

### Primary (HIGH confidence)

- Python 3.11+ `asyncio` subprocess documentation: https://docs.python.org/3/library/asyncio-subprocess.html
- Python `subprocess` module docs (for `start_new_session`): https://docs.python.org/3/library/subprocess.html
- Python `asyncio` synchronization primitives docs: https://docs.python.org/3/library/asyncio-sync.html
- Codebase: `nanobot/agent/tools/shell.py` `ExecTool._build_env()` (lines 199-233) and `_kill_process()` (lines 185-197)
- Codebase: `nanobot/agent/loop.py` `AgentLoop._concurrency_gate` (lines 206-209)
- Codebase: `nanobot/config/schema.py` `ChannelsConfig` (lines 18-30) and `ClaudeCodeProviderConfig` (lines 97-101)
- Codebase: `.planning/research/PITFALLS.md` -- Pitfalls 5 (zombie processes), 10 (process accumulation)

### Secondary (MEDIUM confidence)

- CPython issue #119710 -- `asyncio proc.kill()` and `proc.wait()` counter-intuitive behavior: https://github.com/python/cpython/issues/119710
- CPython issue #88050 -- Cannot cleanly kill a subprocess using high-level asyncio APIs: https://github.com/python/cpython/issues/88050
- How to Safely Kill Python Subprocesses Without Zombies: https://dev.to/generatecodedev/how-to-safely-kill-python-subprocesses-without-zombies-3h9g
- Kill a Python subprocess and its children on timeout: https://alexandra-zaharia.github.io/posts/kill-subprocess-and-its-children-on-timeout-python/

### Tertiary (LOW confidence)

None -- all findings verified against official docs or codebase.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all stdlib, no new dependencies
- Architecture: HIGH -- all three patterns exist in the codebase already, decisions are locked
- Pitfalls: HIGH -- verified against CPython issues, PITFALLS.md, and official docs

**Research date:** 2026-04-09
**Valid until:** 2026-05-09 (stable -- stdlib APIs do not change)
