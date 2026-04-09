# Phase 3: UX Integration - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.

**Date:** 2026-04-09
**Phase:** 03-ux-integration
**Areas discussed:** Persona passthrough, Output verbosity, CLI flag, Menu integration
**Mode:** --auto

---

## Persona Passthrough

| Option | Description | Selected |
|--------|-------------|----------|
| --append-system-prompt | Inject without overriding Claude Code's own prompt | ✓ |
| --system-prompt | Override entirely | |
| No passthrough | Never pass persona | |

**User's choice:** [auto] --append-system-prompt (recommended default)

---

## Output Verbosity

| Option | Description | Selected |
|--------|-------------|----------|
| Post-process JSON with config enum | full/final/summarized modes | ✓ |
| Always full output | No filtering | |
| Separate endpoint for each mode | Over-engineered | |

**User's choice:** [auto] Post-process JSON with config enum (recommended default)

---

## CLI Flag

| Option | Description | Selected |
|--------|-------------|----------|
| --bypass on nanobot chat | Simple boolean flag | ✓ |
| nanobot bypass subcommand | Separate command | |
| --provider claude_code | Generic provider override | |

**User's choice:** [auto] --bypass on nanobot chat (recommended default)

---

## Menu Integration

| Option | Description | Selected |
|--------|-------------|----------|
| Add to _configure_providers | Interactive picker with availability status | ✓ |
| Config file only | No interactive option | |

**User's choice:** [auto] Add to _configure_providers (recommended default)

---

## Claude's Discretion

- Persona extraction logic, summarized mode formatting, picker UI wording

## Deferred Ideas

None
