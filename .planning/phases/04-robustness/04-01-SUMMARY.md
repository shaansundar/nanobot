---
phase: 04-robustness
plan: 01
subsystem: providers
tags: [asyncio, subprocess, semaphore, process-group, env-isolation, sigterm, sigkill]

# Dependency graph
requires:
  - phase: 01-core-provider
    provides: ClaudeCodeProvider with _run_cli subprocess execution
provides:
  - Hardened _run_cli with process group management, timeout, semaphore, env isolation
  - ClaudeCodeProviderConfig with max_concurrent, env_isolation, timeout fields
  - _kill_process_group with SIGTERM/SIGKILL escalation
  - _build_isolated_env for gateway mode key stripping
affects: [04-02, streaming, gateway-deployment]

# Tech tracking
tech-stack:
  added: []
  patterns: [process-group-lifecycle, semaphore-concurrency-gate, env-isolation-pattern]

key-files:
  created: []
  modified:
    - nanobot/config/schema.py
    - nanobot/providers/claude_code_provider.py
    - tests/providers/test_claude_code_provider.py

key-decisions:
  - "Used start_new_session=True (not preexec_fn) for cross-platform process group creation"
  - "SIGTERM then SIGKILL with 5s grace period matches ExecTool._kill_process pattern"
  - "Semaphore initialized per-provider instance, not globally, to support multi-provider concurrency"
  - "env_isolation=False passes env=None (full inherit) for CLI mode where user owns the machine"

patterns-established:
  - "Process group lifecycle: start_new_session=True + SIGTERM + SIGKILL escalation + proc.wait() reap"
  - "Semaphore gating: async with self._subprocess_semaphore wraps subprocess lifetime"
  - "Env isolation: minimal dict with HOME/PATH/LANG/TERM/USER/SHELL strips API keys"

requirements-completed: [ROBU-01, ROBU-02, ROBU-03]

# Metrics
duration: 8min
completed: 2026-04-09
---

# Phase 4 Plan 1: Subprocess Lifecycle Hardening Summary

**Process group management with SIGTERM/SIGKILL escalation, semaphore-based concurrency limiting, and environment isolation for gateway mode**

## Performance

- **Duration:** 8 min
- **Started:** 2026-04-09T12:49:27Z
- **Completed:** 2026-04-09T12:57:00Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- ClaudeCodeProvider._run_cli hardened with start_new_session=True, asyncio.wait_for timeout, SIGTERM/SIGKILL process group kill, zombie reaping in finally block
- Semaphore-based concurrency gate (default 5, configurable 1-20) prevents resource exhaustion
- Environment isolation mode strips API keys and secrets from subprocess environment in gateway mode
- 15 new robustness tests covering all three ROBU requirements pass alongside 40 existing tests

## Task Commits

Each task was committed atomically:

1. **Task 1: Extend config schema and harden ClaudeCodeProvider** - `07b3897` (test: RED) + `04e0c0c` (feat: GREEN)
2. **Task 2: Add robustness test suite** - `617f904` (test: SIGKILL escalation test)

_Note: TDD tasks have multiple commits (test -> feat -> refactor)_

## Files Created/Modified
- `nanobot/config/schema.py` - Added max_concurrent, env_isolation, timeout fields to ClaudeCodeProviderConfig
- `nanobot/providers/claude_code_provider.py` - Hardened _run_cli, added _kill_process_group, _build_isolated_env, semaphore, timeout
- `tests/providers/test_claude_code_provider.py` - 15 new tests for ROBU-01/02/03, extended FakeProcess with pid

## Decisions Made
- Used start_new_session=True (not preexec_fn with os.setsid) for clean cross-platform process group creation
- SIGTERM then SIGKILL with 5s grace follows the established ExecTool._kill_process pattern from shell.py
- Semaphore is per-provider-instance (not global) to allow different limits per provider
- env_isolation=False passes env=None to inherit full environment, matching subprocess default behavior
- Added pid attribute to existing FakeProcess to avoid breaking existing tests with the new logger.debug call

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Added pid attribute to existing FakeProcess**
- **Found during:** Task 1 GREEN phase
- **Issue:** Existing FakeProcess lacked pid attribute; new logger.debug("pid={}") in _run_cli crashed existing tests
- **Fix:** Added pid: int = 12345 parameter and self.pid to FakeProcess.__init__
- **Files modified:** tests/providers/test_claude_code_provider.py
- **Verification:** All 40 existing tests pass with the change
- **Committed in:** 04e0c0c (Task 1 GREEN commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Necessary fix for backward compatibility. No scope creep.

## Issues Encountered
- pytest in worktree required `uv sync` to discover the newly merged claude_code_provider.py module (editable install needed rebuild)

## Known Stubs
None - all functionality is fully wired.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Provider subprocess lifecycle is production-hardened
- Ready for Plan 04-02 (streaming, if applicable) or gateway deployment
- env_isolation=None (auto-detect) can be wired to channels config in a future plan

---
*Phase: 04-robustness*
*Completed: 2026-04-09*
