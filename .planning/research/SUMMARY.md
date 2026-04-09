# Research Summary: Nanobot Harness Bypass

**Synthesized:** 2026-04-09
**Sources:** STACK.md, FEATURES.md, ARCHITECTURE.md, PITFALLS.md

## Executive Summary

This project adds a new `LLMProvider` subclass to nanobot that routes completions through the Claude Code CLI subprocess rather than making direct Anthropic API calls. The primary use case is Claude Max/Pro subscription users who want to leverage subscription billing from within nanobot's multi-channel agent framework. The recommended architecture is an **Agent Proxy model**: nanobot sends a prompt and receives a final result; all tool execution runs inside the CLI subprocess.

The recommended transport is the official `claude-agent-sdk` Python package. Its `query()` function is a thin async iterator wrapping JSON-lines over stdin/stdout with the CLI child process. A raw `asyncio.create_subprocess_exec` fallback must exist for subscription auth where the SDK's bundled CLI binary may lack the user's OAuth login.

## Key Findings

### Stack

- **One new dependency:** `claude-agent-sdk>=0.1.56,<0.2.0` (optional extra `nanobot[bypass]`)
- Use `query()` with `resume` for MVP; `ClaudeSDKClient` for persistent sessions later
- Use `--bare` on all subprocess invocations to reduce per-turn token overhead from ~50K to ~5K

### Features

- **Must-have:** One-shot chat, text streaming, provider registration, CLI availability check, error propagation
- **Should-have:** Session continuity via `--resume`, persona passthrough toggle, output verbosity control, `--bypass` CLI flag, menu integration
- **Defer:** `ClaudeSDKClient` persistent mode, bash wrapper script, interrupt support
- **Never build:** Dual agent loop, `--dangerously-skip-permissions` in gateway mode, auto-install CLI

### Architecture

- **Agent Proxy model** — Claude Code handles all tool execution; `LLMResponse.tool_calls` always empty
- Three integration touchpoints: `ProviderSpec` entry, pydantic config field, backend branch in `commands.py`
- Session continuity: store `ResultMessage.session_id` per nanobot session key; pass as `resume` on next call

### Top Pitfalls

1. **Pipe buffer deadlock** — concurrent stderr drain mandatory
2. **CLI hangs without stdin** — always `stdin=DEVNULL` + `--bare`
3. **Dual agent loop** — locked decision: Claude Code is sole tool authority
4. **Security: `--dangerously-skip-permissions` in gateway** — startup guard required
5. **Shell injection** — always `create_subprocess_exec` with list args, never `shell=True`
6. **Session ID format mismatch** — use `uuid.uuid5()` for deterministic mapping
7. **Zombie process accumulation** — process group management + idle timeout
8. **50K token overhead** — `--bare` flag on every invocation

## Critical Risk

**Subscription OAuth auth is the single biggest unresolved risk.** The SDK officially supports only API key auth. OAuth token support via `CLAUDE_CODE_OAUTH_TOKEN` is an undocumented community workaround (LOW confidence). Must validate empirically in Phase 1. If it fails, raw subprocess fallback using the user's system-installed `claude` binary is the guaranteed path.

## Suggested Phases

1. **Core Provider + Auth Validation** — MVP one-shot, validate subscription auth works
2. **Streaming + Session Continuity** — text streaming, `--resume` session mapping
3. **Robustness + Error Handling** — error classification, retry, process lifecycle
4. **UX + Polish** — persona toggle, output verbosity, `--bypass` flag, menu integration
5. **Advanced Session Mode (Optional)** — `ClaudeSDKClient` persistent subprocess

## Research Flags

| Phase | Needs Research? | Reason |
|-------|----------------|--------|
| Phase 1 | YES | OAuth auth validation — LOW confidence |
| Phase 2 | No | Standard SDK streaming patterns |
| Phase 3 | No | Standard asyncio process lifecycle |
| Phase 4 | No | Follow existing nanobot patterns |
| Phase 5 | YES | Undocumented `--input-format stream-json` protocol |

---
*Research synthesized: 2026-04-09*
