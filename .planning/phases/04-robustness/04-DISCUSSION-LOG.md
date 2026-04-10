# Phase 4: Robustness - Discussion Log

> **Audit trail only.**

**Date:** 2026-04-09
**Phase:** 04-robustness
**Areas discussed:** Process lifecycle, Concurrent limiting, Env isolation
**Mode:** --auto

---

## Process Lifecycle

| Option | Description | Selected |
|--------|-------------|----------|
| Process group + SIGTERM/SIGKILL + timeout | Full lifecycle management | ✓ |
| Just proc.wait() | Minimal, no timeout protection | |
| External process monitor | Over-engineered for v1 | |

**User's choice:** [auto] Process group + SIGTERM/SIGKILL + timeout (recommended default)

---

## Concurrent Limiting

| Option | Description | Selected |
|--------|-------------|----------|
| asyncio.Semaphore in provider | Backpressure, no rejection | ✓ |
| Hard reject over limit | Errors on excess requests | |
| No limit | Unbounded spawning | |

**User's choice:** [auto] asyncio.Semaphore (recommended default)

---

## Environment Isolation

| Option | Description | Selected |
|--------|-------------|----------|
| Minimal env in gateway mode | Strip API keys, keep essentials | ✓ |
| Always minimal env | Too restrictive for CLI users | |
| No isolation | Security risk in gateway | |

**User's choice:** [auto] Minimal env in gateway mode (recommended default)

## Claude's Discretion

- Timeout value, PID logging, semaphore scope

## Deferred Ideas

None
