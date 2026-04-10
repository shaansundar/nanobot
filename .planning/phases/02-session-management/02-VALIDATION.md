---
phase: 2
slug: session-management
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-09
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.x with pytest-asyncio |
| **Config file** | `pyproject.toml` [tool.pytest.ini_options] |
| **Quick run command** | `python3 -m pytest tests/providers/test_claude_code_provider.py -x -q` |
| **Full suite command** | `python3 -m pytest tests/ -x -q` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python3 -m pytest tests/providers/test_claude_code_provider.py -x -q`
- **After every plan wave:** Run `python3 -m pytest tests/ -x -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 2-01-01 | 01 | 1 | SESS-01 | unit | `pytest tests/providers/test_claude_code_provider.py::test_session_resume` | ❌ W0 | ⬜ pending |
| 2-01-02 | 01 | 1 | SESS-02 | unit | `pytest tests/providers/test_claude_code_provider.py::test_oneshot_no_resume` | ❌ W0 | ⬜ pending |
| 2-01-03 | 01 | 1 | SESS-03 | unit | `pytest tests/providers/test_claude_code_provider.py::test_mode_toggle` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] Session-specific tests in `tests/providers/test_claude_code_provider.py`

*Existing pytest infrastructure covers framework needs.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Multi-turn conversation retains context | SESS-01 | Requires live Claude Code CLI | Send 2+ messages in session mode, verify context carries |
| One-shot truly stateless | SESS-02 | Requires live CLI to verify no state | Send message in one-shot, verify no prior context |
| /session and /oneshot commands work | SESS-03 | Requires live channel interaction | Toggle modes, verify behavior changes |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
