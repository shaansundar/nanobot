---
phase: 01-core-provider
plan: 02
subsystem: providers
tags: [provider-registry, config-schema, lazy-imports, cli-bypass]

# Dependency graph
requires:
  - phase: 01-core-provider/01
    provides: ClaudeCodeProvider class (LLMProvider implementation)
provides:
  - ProviderSpec entry for claude_code in PROVIDERS registry
  - ClaudeCodeProviderConfig with cli_path field in config schema
  - ProvidersConfig.claude_code field (exclude=True)
  - _make_provider() routing for backend="claude_code" in CLI and SDK facade
  - Lazy import wiring for ClaudeCodeProvider in providers __init__.py
affects: [02-bridge-script, 03-integration, 04-polish]

# Tech tracking
tech-stack:
  added: []
  patterns: [is_direct provider registration, dedicated config class for non-API-key providers]

key-files:
  created: []
  modified:
    - nanobot/providers/registry.py
    - nanobot/config/schema.py
    - nanobot/providers/__init__.py
    - nanobot/cli/commands.py
    - nanobot/nanobot.py
    - tests/providers/test_claude_code_provider.py
    - tests/providers/test_providers_init.py

key-decisions:
  - "Used ClaudeCodeProviderConfig (not generic ProviderConfig) because claude_code uses cli_path instead of api_key/api_base"
  - "Set exclude=True on claude_code field in ProvidersConfig, matching openai_codex and github_copilot pattern for non-API-key providers"
  - "Placed ProviderSpec after github_copilot and before deepseek in registry, grouping with other non-API-key providers"

patterns-established:
  - "is_direct=True provider: skips API key validation, uses cli_path instead of api_key"
  - "Dedicated *ProviderConfig class for providers with unique config shape"

requirements-completed: [CORE-02, CORE-03]

# Metrics
duration: 5min
completed: 2026-04-09
---

# Phase 01 Plan 02: Provider Registration Summary

**Registered ClaudeCodeProvider in provider registry with config schema, _make_provider routing, and lazy imports across 5 integration points**

## Performance

- **Duration:** 5 min
- **Started:** 2026-04-09T10:16:52Z
- **Completed:** 2026-04-09T10:22:01Z
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments
- ProviderSpec for "claude_code" registered with backend="claude_code", is_direct=True, and keywords for auto-detection
- ClaudeCodeProviderConfig class with cli_path field added to config schema
- Both _make_provider() functions (CLI and SDK facade) route backend="claude_code" to ClaudeCodeProvider
- 8 new registration/config tests added and passing (26 total in test file)
- Full test suite green: 1294 passed, 0 failed

## Task Commits

Each task was committed atomically:

1. **Task 1: Register ProviderSpec and config schema** - `1e997d8` (feat)
2. **Task 2: Wire provider instantiation and add registration tests** - `ff51901` (feat)

## Files Created/Modified
- `nanobot/providers/registry.py` - Added ProviderSpec entry for claude_code
- `nanobot/config/schema.py` - Added ClaudeCodeProviderConfig class and ProvidersConfig.claude_code field
- `nanobot/providers/__init__.py` - Added ClaudeCodeProvider to __all__, _LAZY_IMPORTS, and TYPE_CHECKING
- `nanobot/cli/commands.py` - Added elif backend == "claude_code" branch in _make_provider()
- `nanobot/nanobot.py` - Added elif backend == "claude_code" branch in _make_provider()
- `tests/providers/test_claude_code_provider.py` - Added 8 registration and config tests
- `tests/providers/test_providers_init.py` - Updated __all__ assertion to include ClaudeCodeProvider

## Decisions Made
- Used ClaudeCodeProviderConfig (not generic ProviderConfig) because this provider has cli_path instead of api_key/api_base
- Set exclude=True on claude_code ProvidersConfig field, matching the pattern used by openai_codex and github_copilot (non-API-key providers hidden from serialization)
- Placed ProviderSpec after github_copilot, grouping with other non-API-key providers

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated lazy import test to include ClaudeCodeProvider**
- **Found during:** Task 2 (registration tests)
- **Issue:** test_providers_init.py::test_importing_providers_package_is_lazy checks exact __all__ list, which now includes ClaudeCodeProvider
- **Fix:** Added claude_code_provider to monkeypatch delitem list, added laziness assertion, and updated __all__ expected list
- **Files modified:** tests/providers/test_providers_init.py
- **Verification:** Full test suite passes (1294 passed, 0 failed)
- **Committed in:** ff51901 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 bug fix)
**Impact on plan:** Necessary fix for test correctness after adding lazy import. No scope creep.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Known Stubs
None - all integration points are fully wired with real data sources.

## Next Phase Readiness
- Phase 01 (core-provider) is complete: ClaudeCodeProvider exists and is fully registered
- Provider can be selected via config `provider: "claude_code"` or model keyword matching
- Ready for Phase 02 (bridge-script) which adds the bash/zsh CLI session management layer

## Self-Check: PASSED

All 8 files verified present. Both commit hashes (1e997d8, ff51901) confirmed in git log.

---
*Phase: 01-core-provider*
*Completed: 2026-04-09*
