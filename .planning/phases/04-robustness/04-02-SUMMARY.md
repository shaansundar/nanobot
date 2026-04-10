---
phase: 04-robustness
plan: 02
subsystem: providers
tags: [config-wiring, gateway-detection, env-isolation, construction-site]

# Dependency graph
requires:
  - phase: 04-robustness
    plan: 01
    provides: ClaudeCodeProvider __init__ accepts max_concurrent, env_isolation, timeout
provides:
  - Both _make_provider sites wire max_concurrent, env_isolation, timeout from config
  - _has_active_channels gateway detection helper in nanobot.py and cli/commands.py
  - Auto-detection of env_isolation based on ChannelsConfig active channels
affects: [gateway-deployment, security]

# Tech tracking
tech-stack:
  added: []
  patterns: [gateway-mode-auto-detection, config-to-constructor-wiring]

# Files
key-files:
  created: []
  modified:
    - nanobot/nanobot.py
    - nanobot/cli/commands.py

# Decisions
decisions:
  - Duplicated _has_active_channels in both files to avoid circular imports (10-line pure function)
  - Auto-detect env_isolation from ChannelsConfig extras when config value is None

# Metrics
metrics:
  duration: 4min
  completed: "2026-04-09T13:07:31Z"
---

# Phase 04 Plan 02: Wire Robustness Config to Construction Sites Summary

Config-to-constructor wiring for ClaudeCodeProvider with ChannelsConfig gateway auto-detection for env_isolation

## What Was Done

Updated both ClaudeCodeProvider construction sites (nanobot.py SDK facade and cli/commands.py CLI entry point) to pass max_concurrent, env_isolation, and timeout from ClaudeCodeProviderConfig. Added _has_active_channels helper that inspects ChannelsConfig.model_extra for enabled channel sections to auto-detect gateway mode.

## Tasks Completed

| Task | Name | Commit | Files |
| ---- | ---- | ------ | ----- |
| 1 | Add gateway detection helper and wire construction sites | b6d43f7 | nanobot/nanobot.py, nanobot/cli/commands.py |

## Key Implementation Details

### Gateway Detection Helper

Both `nanobot/nanobot.py` and `nanobot/cli/commands.py` contain a `_has_active_channels()` helper that:
- Returns False for None input or empty ChannelsConfig
- Inspects `model_extra` (Pydantic's extra="allow" storage) for channel sections
- Returns True if any channel section has `enabled: True`
- Handles both dict and object-style access patterns

### Construction Site Wiring

Both `_make_provider()` functions now:
1. Extract `max_concurrent` and `timeout` from `ClaudeCodeProviderConfig` (default 5 and 300)
2. Extract `env_isolation` -- if explicitly set (True/False), use it; if None, auto-detect
3. Auto-detection: `_has_active_channels(config.channels)` returns True in gateway mode
4. Pass all 5 params to `ClaudeCodeProvider(cli_path, default_model, max_concurrent, env_isolation, timeout)`

### Behavior Matrix

| Config env_isolation | Active Channels | Result |
|---------------------|-----------------|--------|
| True | any | True (explicit override) |
| False | any | False (explicit override) |
| None (default) | Yes | True (gateway auto-detect) |
| None (default) | No | False (CLI mode) |

## Deviations from Plan

None -- plan executed exactly as written.

## Verification Results

- Gateway detection returns False for empty ChannelsConfig: PASSED
- Gateway detection returns True for config with enabled channel: PASSED
- Gateway detection returns False for config with disabled channel: PASSED
- Gateway detection returns False for None input: PASSED
- Config fields flow through (max_concurrent=3, timeout=600, env_isolation overrides): PASSED
- Both construction sites contain max_concurrent, env_isolation, timeout: PASSED (grep verified)
- Provider tests (55 tests): PASSED
- Full test suite: 1330 passed, 1 pre-existing failure (test_web_fetch_security unrelated)

## Known Stubs

None -- all config values are fully wired to the provider constructor.

## Self-Check: PASSED

- nanobot/nanobot.py: FOUND
- nanobot/cli/commands.py: FOUND
- 04-02-SUMMARY.md: FOUND
- Commit b6d43f7: FOUND
