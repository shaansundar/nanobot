# Phase 2: Session Management - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-09
**Phase:** 02-session-management
**Areas discussed:** Session persistence, Session ID mapping, Mode toggle UX, Session lifecycle
**Mode:** --auto (all decisions auto-selected from recommended defaults)

---

## Session Persistence Mechanism

| Option | Description | Selected |
|--------|-------------|----------|
| --resume <session_id> | Claude Code's native session persistence | ✓ |
| Re-serialize history | Nanobot manages context, sends full history each turn | |
| Hybrid | --resume when possible, fallback to history re-serialization | |

**User's choice:** [auto] --resume <session_id> (recommended default)
**Notes:** Preserves full agent context without re-serializing. session_id available in JSON output.

---

## Session ID Mapping

| Option | Description | Selected |
|--------|-------------|----------|
| In-memory dict | Store mapping in provider instance | ✓ |
| Filesystem persistence | Write mapping to disk for durability | |
| uuid.uuid5 deterministic | Generate predictable UUID from session key | |

**User's choice:** [auto] In-memory dict (recommended default)
**Notes:** Claude Code manages its own session storage. Mapping only needed during runtime.

---

## Mode Toggle UX

| Option | Description | Selected |
|--------|-------------|----------|
| Config field + slash command | Default in config, toggle per conversation | ✓ |
| Config only | Global setting, no per-conversation override | |
| Slash command only | No default, must explicitly set per conversation | |

**User's choice:** [auto] Config field + slash command (recommended default)
**Notes:** Follows existing nanobot patterns for config + command.

---

## Session Lifecycle

| Option | Description | Selected |
|--------|-------------|----------|
| Create on first message, no expiry | Lightweight, Claude Code manages storage | ✓ |
| Create on first message, expiry after N minutes | Active cleanup | |
| Explicit create/destroy commands | User manages lifecycle | |

**User's choice:** [auto] Create on first message, no expiry (recommended default)
**Notes:** Sessions are lightweight. No expiry needed for v1.

---

## Claude's Discretion

- Session key threading through chat() method
- Session ID visibility in verbose output
- Internal dict implementation details

## Deferred Ideas

None
