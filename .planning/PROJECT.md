# Nanobot Harness Bypass

## What This Is

A new mode for nanobot that routes all AI interactions through the official Claude Code CLI instead of direct API calls. This lets subscription users (Max, Pro) continue using nanobot's multi-channel UI and tooling after Anthropic restricts third-party harness access. Nanobot becomes a wrapper that pipes prompts to `claude` CLI and streams responses back.

## Core Value

Subscription users can keep using nanobot's full feature set by transparently proxying through Claude Code CLI — the one harness that always works with subscriptions.

## Requirements

### Validated

- Multi-provider LLM support (Anthropic, OpenAI, Azure, Groq, DeepSeek, Gemini, etc.) — existing
- Multi-channel chat (Telegram, Discord, Slack, WhatsApp, Matrix, etc.) — existing
- Tool use system (file ops, bash, web search, MCP) — existing
- Session persistence and history — existing
- CLI chat interface with streaming — existing
- Subagent spawning — existing
- Provider registry with auto-detection — existing
- Persona/system prompt support — existing
- Slash command routing — existing

### Active

- [x] Claude Code CLI proxy mode ("Bypass claude harness rules" option) — Validated in Phase 1
- [ ] Bash/zsh script that manages Claude Code CLI sessions
- [ ] Full tool use passthrough (file edits, bash, etc. flow through Claude Code)
- [ ] Interactive session mode (persistent context across turns)
- [ ] One-shot message mode (independent prompts)
- [ ] User choice: full output vs final-only vs summarized tool output
- [ ] User choice: pass nanobot persona to Claude Code or run raw
- [ ] Menu item in provider/model selection
- [ ] CLI flag (`nanobot --bypass` or similar)
- [ ] Response streaming back to nanobot UI

### Out of Scope

- Modifying Claude Code CLI itself — we only call it as-is
- Bypassing API authentication — this uses the user's existing Claude Code login
- Supporting non-Claude models through this mode — it's Claude Code specific
- Replacing the existing direct API providers — this is an additional option alongside them

## Context

Anthropic announced that subscriptions won't work with third-party harnesses. Nanobot is a third-party harness that calls Claude's API directly. The bypass routes through `claude` CLI (the official Anthropic harness) which always works with subscriptions. The user's messages get passed as parameters to a bash/zsh script, the script executes them via Claude Code CLI, and responses are piped back to nanobot.

The existing codebase has a clean provider abstraction (`LLMProvider` ABC) and a provider registry (`ProviderSpec`). The new Claude Code CLI mode fits as a new provider implementation that shells out to `claude` instead of making API calls.

## Constraints

- **Runtime**: Claude Code CLI (`claude`) must be installed and authenticated on the user's machine
- **Platform**: macOS/Linux only (Claude Code CLI requirement)
- **Latency**: Extra overhead from process spawning; streaming mitigates perceived delay
- **Concurrency**: Claude Code CLI may have its own session/concurrency limits

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Use bash/zsh script as intermediary | User requirement — script manages CLI interaction, easy to modify | — Pending |
| Both session and one-shot modes | User wants flexibility for different use cases | — Pending |
| User-configurable output verbosity | Some users want full tool output, others want clean responses | — Pending |
| Optional persona passthrough | Some conversations need nanobot personality, others need raw Claude Code | — Pending |
| Side-by-side with existing providers | Not a replacement — an additional option in the provider menu | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd:transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd:complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-04-09 after Phase 1 completion — Core Provider implemented and verified*
