# Requirements: Nanobot Harness Bypass

**Defined:** 2026-04-09
**Core Value:** Subscription users can keep using nanobot by proxying through Claude Code CLI

## v1 Requirements

Requirements for initial release. Each maps to roadmap phases.

### Core Provider

- [x] **CORE-01**: User can send a prompt through nanobot that gets executed via `claude -p` and returns the response
- [x] **CORE-02**: Claude Code CLI provider is registered as a ProviderSpec in the provider registry with auto-detection
- [x] **CORE-03**: User can select "Claude Code (Bypass)" as a provider in config like any other provider
- [x] **CORE-04**: Nanobot checks for `claude` binary at startup and fails with clear install instructions if missing
- [x] **CORE-05**: Auth failures, rate limits, and CLI errors propagate as user-friendly error messages
- [x] **CORE-06**: All CLI invocations use `--setting-sources ""` flag to reduce token overhead from ~50K to ~5K per turn while preserving subscription auth

### Session Management

- [ ] **SESS-01**: User can use session mode where conversation context persists across turns
- [ ] **SESS-02**: User can use one-shot mode where each prompt is independent
- [ ] **SESS-03**: User can toggle between session and one-shot modes per conversation

### UX / Configuration

- [ ] **UX-01**: User can choose to pass nanobot's active persona/system prompt to Claude Code or run raw
- [ ] **UX-02**: User can choose output verbosity: full tool output, final response only, or summarized actions
- [ ] **UX-03**: User can activate bypass mode via `--bypass` CLI flag (e.g. `nanobot chat --bypass`)
- [ ] **UX-04**: "Claude Code (Bypass)" appears as an option in nanobot's interactive provider picker menu

### Robustness

- [ ] **ROBU-01**: Subprocess processes are properly managed with no zombie accumulation (process group kill + wait)
- [ ] **ROBU-02**: Concurrent Claude Code subprocesses are limited via asyncio.Semaphore to prevent resource exhaustion
- [ ] **ROBU-03**: In gateway mode, subprocess environment is isolated (strip API keys, sensitive env vars)

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Streaming

- **STRM-01**: Text responses stream incrementally via `--output-format stream-json` text_delta events
- **STRM-02**: Streaming provides UX parity with all other nanobot providers

### Advanced Sessions

- **ADVS-01**: Session continuity uses Claude Code's native `--resume` flag with session ID mapping
- **ADVS-02**: Persistent subprocess mode via `ClaudeSDKClient` for near-zero per-turn latency

### Power User

- **PWRU-01**: User can configure a custom bash/zsh wrapper script path instead of direct `claude` binary
- **PWRU-02**: Cost/usage tracking surfaced from Claude Code's `ResultMessage.total_cost_usd`

## Out of Scope

| Feature | Reason |
|---------|--------|
| Dual agent loop (nanobot + Claude Code tools) | Causes file state conflicts; Claude Code is sole tool authority in bypass mode |
| Modifying Claude Code CLI | We only call it as-is per PROJECT.md |
| Non-Claude model support through bypass | This mode is Claude Code specific; other models have direct API providers |
| Replacing existing direct API providers | Side-by-side option, not a replacement |
| Auto-installing claude CLI binary | Users should control what gets installed |
| Interactive CLI mode | Requires TTY, can't be piped; always use `-p` flag |
| `--dangerously-skip-permissions` in gateway mode | Critical security hole; any channel user could run arbitrary host commands |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| CORE-01 | Phase 1 | Complete |
| CORE-02 | Phase 1 | Complete |
| CORE-03 | Phase 1 | Complete |
| CORE-04 | Phase 1 | Complete |
| CORE-05 | Phase 1 | Complete |
| CORE-06 | Phase 1 | Complete |
| SESS-01 | Phase 2 | In Progress (engine: 02-01) |
| SESS-02 | Phase 2 | In Progress (engine: 02-01) |
| SESS-03 | Phase 2 | Pending |
| UX-01 | Phase 3 | Pending |
| UX-02 | Phase 3 | Pending |
| UX-03 | Phase 3 | Pending |
| UX-04 | Phase 3 | Pending |
| ROBU-01 | Phase 4 | Pending |
| ROBU-02 | Phase 4 | Pending |
| ROBU-03 | Phase 4 | Pending |

**Coverage:**
- v1 requirements: 16 total
- Mapped to phases: 16
- Unmapped: 0

---
*Requirements defined: 2026-04-09*
*Last updated: 2026-04-09 after roadmap phase mapping*
