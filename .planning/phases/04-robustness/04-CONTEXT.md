# Phase 4: Robustness - Context

**Gathered:** 2026-04-09
**Status:** Ready for planning

<domain>
## Phase Boundary

Harden subprocess lifecycle for production use: prevent zombie processes, limit concurrent subprocesses, and isolate environment in gateway/multi-user mode.

</domain>

<decisions>
## Implementation Decisions

### Process Lifecycle Management
- **D-01:** Use `start_new_session=True` in `create_subprocess_exec` to create a process group, enabling group-level signal delivery
- **D-02:** Add `asyncio.wait_for(proc.communicate(), timeout=300)` with 5-minute default timeout (configurable via config)
- **D-03:** On timeout: send SIGTERM to process group, wait 5s, then SIGKILL if still alive
- **D-04:** Always `await proc.wait()` after process completes to reap the child and prevent zombies
- **D-05:** Register an `atexit` handler or use `try/finally` to kill any in-flight subprocess on provider shutdown

### Concurrent Session Limiting
- **D-06:** Add `asyncio.Semaphore` to `ClaudeCodeProvider` with configurable max concurrent subprocesses
- **D-07:** Config field `max_concurrent: int` on `ClaudeCodeProviderConfig` (default: `5`)
- **D-08:** Acquire semaphore before subprocess spawn, release in `finally` block after completion
- **D-09:** When semaphore is full, new requests queue (asyncio.Semaphore blocks awaiting coroutines) — no rejection, just backpressure

### Environment Isolation (Gateway Mode)
- **D-10:** In gateway mode (detected via `config.channels` having active channels), pass a minimal env dict to `create_subprocess_exec`
- **D-11:** Minimal env: `HOME`, `PATH`, `LANG`, `TERM`, `USER`, `SHELL` — strips all API keys (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `OPENROUTER_API_KEY`, etc.)
- **D-12:** In CLI-only mode (no channels), inherit full env (user's own machine, no isolation needed)
- **D-13:** Config field `env_isolation: bool` on `ClaudeCodeProviderConfig` (default: `true` when channels active, `false` otherwise) — user can override

### Claude's Discretion
- Exact timeout value (5 minutes is the default, but may need tuning)
- Whether to log subprocess PIDs for debugging
- Whether semaphore limit applies per-session or globally

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Provider Implementation
- `nanobot/providers/claude_code_provider.py` — Provider to extend with lifecycle hardening
- `nanobot/providers/base.py` — LLMProvider ABC
- `nanobot/config/schema.py` — ClaudeCodeProviderConfig to extend

### Security Patterns
- `nanobot/security/network.py` — Existing security patterns
- `nanobot/agent/tools/shell.py` — ExecTool._build_env() pattern for environment isolation

### Concurrency Patterns
- `nanobot/agent/loop.py` — Existing asyncio.Semaphore pattern for global concurrency

### Tests
- `tests/providers/test_claude_code_provider.py` — Extend with robustness tests

### Research
- `.planning/research/PITFALLS.md` — Process lifecycle, zombie prevention, env isolation pitfalls

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `ExecTool._build_env()` in `nanobot/agent/tools/shell.py`: Existing minimal env builder pattern
- `AgentLoop._global_semaphore` pattern: Existing concurrency limiting
- `ClaudeCodeProvider._run_cli()`: Current subprocess execution to harden

### Established Patterns
- `asyncio.Semaphore` used in AgentLoop for cross-session concurrency
- `start_new_session=True` for process group management is standard Python asyncio
- Environment filtering follows the ExecTool pattern

### Integration Points
- `ClaudeCodeProvider._run_cli()` — Add timeout, process group, semaphore
- `ClaudeCodeProvider.__init__()` — Initialize semaphore, detect gateway mode
- `ClaudeCodeProviderConfig` — Add max_concurrent and env_isolation fields

</code_context>

<specifics>
## Specific Ideas

- This is production hardening — correctness matters more than features
- Gateway mode is the highest-risk scenario (untrusted channel users)
- The semaphore should prevent runaway resource usage without rejecting requests

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 04-robustness*
*Context gathered: 2026-04-09*
