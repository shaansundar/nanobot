# Phase 1: Core Provider - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-09
**Phase:** 01-core-provider
**Areas discussed:** Transport mechanism, Auth strategy, CLI invocation flags, Error detection
**Mode:** --auto (all decisions auto-selected from recommended defaults)

---

## Transport Mechanism

| Option | Description | Selected |
|--------|-------------|----------|
| Raw asyncio.create_subprocess_exec | Direct subprocess, always works with subscription auth | ✓ |
| claude-agent-sdk query() | Official SDK, structured messages, but auth concerns | |
| Bash/zsh wrapper script | User-customizable, but extra indirection | |

**User's choice:** [auto] Raw asyncio.create_subprocess_exec (recommended default)
**Notes:** User originally requested bash/zsh script; raw subprocess is the foundation that script support builds on. SDK rejected due to LOW confidence on subscription auth.

---

## Auth Strategy

| Option | Description | Selected |
|--------|-------------|----------|
| User's system-installed claude binary | Inherits existing subscription login | ✓ |
| claude-agent-sdk with CLAUDE_CODE_OAUTH_TOKEN | SDK workaround, undocumented | |
| API key passthrough | Direct API key, not for subscription users | |

**User's choice:** [auto] User's system-installed claude binary (recommended default)
**Notes:** The entire project exists because subscriptions won't work with third-party harnesses. Using the user's own CLI binary is the guaranteed path.

---

## CLI Invocation Flags

| Option | Description | Selected |
|--------|-------------|----------|
| --bare -p --output-format json | Minimal overhead, structured output | ✓ |
| -p --output-format stream-json | Streaming output, higher overhead | |
| -p only | Simplest, but unstructured text output | |

**User's choice:** [auto] --bare -p --output-format json (recommended default)
**Notes:** --bare reduces token overhead 10x (50K→5K). JSON output enables structured parsing. Streaming deferred to Phase 2.

---

## Error Detection

| Option | Description | Selected |
|--------|-------------|----------|
| Three-channel (exit code + stdout + stderr) | Comprehensive, maps to existing error model | ✓ |
| Exit code only | Simple but loses diagnostic info | |
| Stderr parsing only | Misses structured error info from stdout | |

**User's choice:** [auto] Three-channel detection (recommended default)
**Notes:** Maps cleanly to existing LLMResponse error fields (error_kind, error_status_code, error_type).

---

## Claude's Discretion

- Error message wording for CLI-not-found and auth-failure
- Auth validation timing (startup vs first use)
- Internal provider class structure

## Deferred Ideas

None
