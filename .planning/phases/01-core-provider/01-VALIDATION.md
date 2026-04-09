---
phase: 1
slug: core-provider
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-09
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.x with pytest-asyncio |
| **Config file** | `pyproject.toml` [tool.pytest.ini_options] |
| **Quick run command** | `python -m pytest tests/test_claude_code_provider.py -x -q` |
| **Full suite command** | `python -m pytest tests/ -x -q` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/test_claude_code_provider.py -x -q`
- **After every plan wave:** Run `python -m pytest tests/ -x -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 1-01-01 | 01 | 1 | CORE-01 | unit | `pytest tests/test_claude_code_provider.py::test_one_shot_chat` | ❌ W0 | ⬜ pending |
| 1-01-02 | 01 | 1 | CORE-04 | unit | `pytest tests/test_claude_code_provider.py::test_cli_not_found` | ❌ W0 | ⬜ pending |
| 1-01-03 | 01 | 1 | CORE-05 | unit | `pytest tests/test_claude_code_provider.py::test_error_propagation` | ❌ W0 | ⬜ pending |
| 1-01-04 | 01 | 1 | CORE-06 | unit | `pytest tests/test_claude_code_provider.py::test_bare_flag_used` | ❌ W0 | ⬜ pending |
| 1-02-01 | 02 | 1 | CORE-02 | unit | `pytest tests/test_claude_code_provider.py::test_provider_registered` | ❌ W0 | ⬜ pending |
| 1-02-02 | 02 | 1 | CORE-03 | unit | `pytest tests/test_claude_code_provider.py::test_provider_selectable` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_claude_code_provider.py` — test stubs for CORE-01 through CORE-06
- [ ] Test fixtures for mocking subprocess execution

*Existing pytest infrastructure covers framework needs.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| End-to-end Claude Code CLI round-trip | CORE-01 | Requires real `claude` binary and subscription auth | Run `nanobot chat --bypass`, send "hello", verify response |
| Auth failure error message quality | CORE-05 | Requires intentionally broken auth state | Rename `~/.claude` temporarily, verify error message |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
