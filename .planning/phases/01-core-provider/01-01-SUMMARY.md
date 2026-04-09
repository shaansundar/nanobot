---
phase: 01-core-provider
plan: 01
subsystem: providers
tags: [asyncio, subprocess, cli, claude-code, llm-provider]

# Dependency graph
requires: []
provides:
  - ClaudeCodeProvider class implementing LLMProvider ABC
  - CLI subprocess routing via asyncio.create_subprocess_exec
  - Error classification (auth, rate limit, overloaded, cli_error)
  - 18-test unit test suite for the provider
affects: [01-core-provider/02, streaming, provider-registry]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Agent Proxy: CLI subprocess routing instead of direct API calls"
    - "Error classification with retry hints (error_should_retry, error_kind)"
    - "--setting-sources '' instead of --bare to preserve subscription OAuth"

key-files:
  created:
    - nanobot/providers/claude_code_provider.py
    - tests/providers/test_claude_code_provider.py
  modified: []

key-decisions:
  - "Used --setting-sources '' instead of --bare to preserve subscription OAuth keychain auth"
  - "tool_calls always empty per Agent Proxy architecture (Claude Code handles all tools internally)"
  - "Error classification: auth=not retryable, rate_limit/overloaded=retryable, cli_error=not retryable"

patterns-established:
  - "CLI subprocess provider pattern: _build_command -> create_subprocess_exec -> _parse_result"
  - "FakeProcess test helper for asyncio subprocess mocking"

requirements-completed: [CORE-01, CORE-04, CORE-05, CORE-06]

# Metrics
duration: 3min
completed: 2026-04-09
---

# Phase 01 Plan 01: ClaudeCodeProvider Summary

**Async subprocess provider routing prompts through Claude Code CLI with --setting-sources flag for subscription-safe OAuth auth**

## Performance

- **Duration:** 3 min
- **Started:** 2026-04-09T10:09:58Z
- **Completed:** 2026-04-09T10:13:00Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- ClaudeCodeProvider class subclassing LLMProvider, routing prompts via asyncio subprocess to the claude CLI binary
- Error classification pipeline: auth errors (not retryable), rate limits (retryable), overloaded (retryable), parse failures, empty output
- 18 unit tests covering happy path, error propagation, CLI flag verification, message extraction, and subprocess configuration
- Uses --setting-sources "" (not --bare) to reduce overhead while preserving subscription OAuth keychain auth

## Task Commits

Each task was committed atomically:

1. **Task 1: Create test scaffold for ClaudeCodeProvider** - `4402201` (test)
2. **Task 2: Implement ClaudeCodeProvider** - `b0792f1` (feat)

_TDD workflow: Task 1 = RED (18 failing tests), Task 2 = GREEN (all 18 pass)_

## Files Created/Modified
- `nanobot/providers/claude_code_provider.py` - ClaudeCodeProvider class implementing LLMProvider ABC with CLI subprocess routing
- `tests/providers/test_claude_code_provider.py` - 18 unit tests covering chat round-trip, error handling, CLI flags, and message extraction

## Decisions Made
- Used `--setting-sources ""` instead of `--bare` flag -- research proved `--bare` breaks subscription auth for Max/Pro users, while `--setting-sources ""` achieves the same overhead reduction (D-08 intent) while preserving keychain OAuth (D-05 requirement)
- `tool_calls` always returns empty list -- Agent Proxy architecture means Claude Code handles all tool execution internally; nanobot only sees final text output
- Error classification maps CLI responses to retry semantics: auth errors and unknown CLI errors are not retryable, rate limits and overload are retryable

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- pytest and pytest-asyncio needed installation in uv-managed virtual environment (resolved by `uv pip install pytest pytest-asyncio`)

## Known Stubs

None - all functionality is fully wired.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- ClaudeCodeProvider is self-contained and ready to be wired into the provider registry (Plan 02)
- All 1286 existing tests continue to pass (no regressions)
- Provider module imports cleanly: `from nanobot.providers.claude_code_provider import ClaudeCodeProvider`

## Self-Check: PASSED

- FOUND: nanobot/providers/claude_code_provider.py
- FOUND: tests/providers/test_claude_code_provider.py
- FOUND: commit 4402201 (Task 1 test scaffold)
- FOUND: commit b0792f1 (Task 2 implementation)
- FOUND: 01-01-SUMMARY.md

---
*Phase: 01-core-provider*
*Completed: 2026-04-09*
