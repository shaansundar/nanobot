---
phase: 01-core-provider
verified: 2026-04-09T11:00:00Z
status: passed
score: 9/9 must-haves verified
re_verification: false
gaps: []
---

# Phase 1: Core Provider Verification Report

**Phase Goal:** Users can send prompts through nanobot and receive responses via Claude Code CLI, with the provider fully integrated into nanobot's existing provider system
**Verified:** 2026-04-09
**Status:** passed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

Success criteria from ROADMAP.md, evaluated against the codebase:

| # | Truth | Status | Evidence |
|---|-------|--------|---------|
| 1 | User can send a prompt in nanobot and receive a complete response routed through Claude Code CLI | VERIFIED | `ClaudeCodeProvider.chat()` builds CLI command, spawns asyncio subprocess, parses JSON result into `LLMResponse(finish_reason="stop")`. 26 tests pass including `test_chat_returns_response`. |
| 2 | User can select "Claude Code (Bypass)" from nanobot's provider configuration like any other provider | VERIFIED | `ProviderSpec(name="claude_code", display_name="Claude Code (Bypass)")` registered in `PROVIDERS` tuple. Both `_make_provider()` call sites route `backend="claude_code"` to `ClaudeCodeProvider`. |
| 3 | Nanobot refuses to start in bypass mode when `claude` binary is not found, with clear install instructions | VERIFIED | `__init__` raises `RuntimeError` containing "Claude Code CLI not found" and "npm install -g @anthropic-ai/claude-code". Tested by `test_cli_not_found_raises` and `test_cli_not_found_message_contains_install_instructions`. |
| 4 | Auth failures and CLI errors surface as readable messages in the chat, not stack traces | VERIFIED | `_build_error_response()` returns `LLMResponse(finish_reason="error", content=result_text)` classifying auth/rate-limit/overloaded/cli_error. `test_auth_error_propagated`, `test_rate_limit_retryable`, `test_empty_stdout_returns_error`, `test_invalid_json_returns_error` all pass. |
| 5 | All CLI invocations use `--setting-sources ""` flag to reduce overhead while preserving subscription auth | VERIFIED | `_build_command()` returns `[..., "--setting-sources", "", prompt]`. `--bare` is absent. `test_command_includes_setting_sources` and `test_command_does_not_include_bare` pass. |

**Score:** 5/5 success criteria verified

---

### Plan 01 Must-Haves (truths)

| # | Truth | Status | Evidence |
|---|-------|--------|---------|
| 1 | `ClaudeCodeProvider.chat()` sends a prompt to the Claude Code CLI subprocess and returns an LLMResponse with the result text | VERIFIED | `chat()` calls `asyncio.create_subprocess_exec`, `communicate()`, then `_parse_result()` returning `LLMResponse`. |
| 2 | `ClaudeCodeProvider` raises RuntimeError with install instructions when the claude binary is not found on PATH | VERIFIED | `shutil.which("claude") or ""` check; empty string triggers `raise RuntimeError(_CLI_NOT_FOUND_MESSAGE)`. |
| 3 | CLI auth errors and process failures are returned as `LLMResponse(finish_reason='error')` with descriptive content, not as raised exceptions | VERIFIED | `_parse_result` returns error responses for empty stdout, JSON parse failure, and `is_error=True` cases. No exceptions raised. |
| 4 | All CLI invocations include `--setting-sources` `""` flags to reduce overhead while preserving subscription auth | VERIFIED | `_build_command` line 71-78 in `claude_code_provider.py` confirms this. `--bare` not present. |

**Score:** 4/4 truths verified

### Plan 02 Must-Haves (truths)

| # | Truth | Status | Evidence |
|---|-------|--------|---------|
| 1 | User can select 'Claude Code (Bypass)' as a provider in nanobot config and it resolves to the ClaudeCodeProvider | VERIFIED | `find_by_name("claude_code")` returns spec; both `_make_provider()` functions instantiate `ClaudeCodeProvider`. |
| 2 | ProviderSpec for claude_code exists in the PROVIDERS tuple with backend='claude_code' and is_direct=True | VERIFIED | `registry.py` lines 227-235 confirm `name="claude_code"`, `backend="claude_code"`, `is_direct=True`. |
| 3 | ProvidersConfig has a claude_code field so config file can include claude_code settings | VERIFIED | `schema.py` line 132: `claude_code: ClaudeCodeProviderConfig = Field(default_factory=ClaudeCodeProviderConfig, exclude=True)` |
| 4 | Both `_make_provider()` call sites (CLI commands and SDK facade) instantiate ClaudeCodeProvider when backend is 'claude_code' | VERIFIED | `commands.py` line 451-456 and `nanobot.py` lines 145-150 both have matching `elif backend == "claude_code":` branches. |

**Score:** 4/4 truths verified

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|---------|--------|---------|
| `nanobot/providers/claude_code_provider.py` | ClaudeCodeProvider class implementing LLMProvider ABC | VERIFIED | 237 lines (min_lines: 100). Exports `ClaudeCodeProvider`. Subclasses `LLMProvider`. All required methods present. |
| `tests/providers/test_claude_code_provider.py` | Unit tests covering chat, error handling, CLI-not-found, and flag verification | VERIFIED | 426 lines (min_lines: 80). 26 test functions (plan required 16+). |
| `nanobot/providers/registry.py` | ProviderSpec entry for claude_code | VERIFIED | Contains `name="claude_code"` at line 229. |
| `nanobot/config/schema.py` | ClaudeCodeProviderConfig and ProvidersConfig.claude_code field | VERIFIED | `ClaudeCodeProviderConfig` at line 97. Field at line 132. `exclude=True` present. |
| `nanobot/cli/commands.py` | elif backend == 'claude_code' branch in _make_provider | VERIFIED | Lines 451-456. Reads `cc_cfg.cli_path` from config. |
| `nanobot/nanobot.py` | elif backend == 'claude_code' branch in _make_provider | VERIFIED | Lines 145-150. Identical pattern to commands.py. |
| `nanobot/providers/__init__.py` | Lazy import for ClaudeCodeProvider | VERIFIED | Present in `__all__` (line 18), `_LAZY_IMPORTS` (line 27), and `TYPE_CHECKING` block (line 33). |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `claude_code_provider.py` | `nanobot/providers/base.py` | `class ClaudeCodeProvider(LLMProvider)` | WIRED | Line 34: `class ClaudeCodeProvider(LLMProvider):` |
| `claude_code_provider.py` | `asyncio.create_subprocess_exec` | subprocess invocation in `chat()` | WIRED | Lines 100-105: `proc = await asyncio.create_subprocess_exec(...)` |
| `tests/test_claude_code_provider.py` | `claude_code_provider.py` | import and test | WIRED | Line 80: `from nanobot.providers.claude_code_provider import ClaudeCodeProvider` |
| `registry.py` | `commands.py` | `find_by_name` returns spec with `backend='claude_code'` | WIRED | `backend="claude_code"` in registry; `elif backend == "claude_code":` in commands.py |
| `commands.py` | `claude_code_provider.py` | `from nanobot.providers.claude_code_provider import ClaudeCodeProvider` | WIRED | Line 452 in commands.py |
| `config/schema.py` | `commands.py` | `config.providers.claude_code.cli_path` read in `_make_provider` | WIRED | Line 454-455: `cc_cfg = getattr(config.providers, "claude_code", None); cli_path = cc_cfg.cli_path if cc_cfg and cc_cfg.cli_path else None` |

All key links WIRED.

---

### Data-Flow Trace (Level 4)

Not applicable. This phase produces a CLI subprocess provider, not a UI component that renders dynamic data from a backend. The data flow is: `chat(messages)` → `_extract_latest_user_content()` → `_build_command()` → `asyncio.create_subprocess_exec()` → `_parse_result()` → `LLMResponse`. This is a synchronous transformation chain, not a render path requiring Level 4 analysis.

---

### Behavioral Spot-Checks

| Behavior | Command / Check | Result | Status |
|----------|----------------|--------|--------|
| `ClaudeCodeProvider` imports cleanly | `uv run python -c "from nanobot.providers.claude_code_provider import ClaudeCodeProvider; print(ClaudeCodeProvider.__name__)"` | `ClaudeCodeProvider` | PASS |
| Registry lookup returns correct spec | `find_by_name("claude_code").backend == "claude_code"` and `is_direct is True` | Both true | PASS |
| Config schema fields exist with correct defaults | `ProvidersConfig().claude_code.cli_path == ""` | True | PASS |
| Lazy import works | `from nanobot.providers import ClaudeCodeProvider` | No error | PASS |
| All 26 tests pass | `uv run pytest tests/providers/test_claude_code_provider.py -x -q` | 26 passed | PASS |
| `--bare` not present in provider | `grep '"--bare"' claude_code_provider.py` | 0 matches | PASS |

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|---------|
| CORE-01 | 01-01-PLAN.md | User can send a prompt through nanobot that gets executed via `claude -p` and returns the response | SATISFIED | `chat()` builds `-p --output-format json --setting-sources ""` command, parses JSON result. `test_chat_returns_response` passes. |
| CORE-02 | 01-02-PLAN.md | Claude Code CLI provider is registered as a ProviderSpec in the provider registry with auto-detection | SATISFIED | ProviderSpec with `name="claude_code"`, `keywords=("claude-code", "claude_code", "bypass")` present in `PROVIDERS` tuple. |
| CORE-03 | 01-02-PLAN.md | User can select "Claude Code (Bypass)" as a provider in config like any other provider | SATISFIED | `display_name="Claude Code (Bypass)"`, `ClaudeCodeProviderConfig` in schema, both `_make_provider()` functions handle `backend="claude_code"`. |
| CORE-04 | 01-01-PLAN.md | Nanobot checks for `claude` binary at startup and fails with clear install instructions if missing | SATISFIED | `__init__` raises `RuntimeError(_CLI_NOT_FOUND_MESSAGE)` where message contains install instructions. |
| CORE-05 | 01-01-PLAN.md | Auth failures, rate limits, and CLI errors propagate as user-friendly error messages | SATISFIED | `_build_error_response()` classifies errors with `error_kind` and `error_should_retry`. Returns `LLMResponse(finish_reason="error")`, never raises. |
| CORE-06 | 01-01-PLAN.md | All CLI invocations use `--setting-sources ""` flag to reduce token overhead from ~50K to ~5K per turn while preserving subscription auth | SATISFIED | `_build_command()` uses `"--setting-sources", ""`. `--bare` is absent. Verified by `test_command_includes_setting_sources` and `test_command_does_not_include_bare`. |

All 6 requirements satisfied. No orphaned requirements for Phase 1 in REQUIREMENTS.md.

---

### Anti-Patterns Found

| File | Pattern | Severity | Impact |
|------|---------|----------|--------|
| None found | — | — | — |

Checked both implementation files for: TODO/FIXME comments, placeholder returns (`return null`, `return []`), console.log-only handlers, hardcoded empty data flowing to rendering. None found. The `tool_calls=[]` return is intentional per the Agent Proxy architecture (documented in both the class docstring and the plan), not a stub.

---

### Human Verification Required

The following behaviors require a live environment with the Claude Code CLI installed and authenticated:

1. **End-to-end prompt round-trip**
   - Test: Set `provider: "claude_code"` in nanobot config; send a message in nanobot chat
   - Expected: Response arrives from Claude via `claude -p` subprocess; no stack traces
   - Why human: Requires `claude` binary installed, subscription auth, and live nanobot chat UI

2. **Auth error display**
   - Test: Set `ANTHROPIC_API_KEY` to nothing; run with `provider: "claude_code"`; send a prompt
   - Expected: Error message containing "Not logged in" appears in chat; no Python traceback visible to user
   - Why human: Requires triggering actual CLI auth failure

3. **Provider appears in nanobot status / picker**
   - Test: Run `nanobot status` or open the interactive provider picker
   - Expected: "Claude Code (Bypass)" appears as a selectable option
   - Why human: Requires running nanobot with UI; display_name wiring is confirmed in code but picker rendering is not verified here

---

### Gaps Summary

No gaps. All must-haves verified, all 6 requirements satisfied, all 26 tests pass, all key links confirmed wired, and no anti-patterns detected.

---

_Verified: 2026-04-09_
_Verifier: Claude (gsd-verifier)_
