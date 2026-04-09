# Roadmap: Nanobot Harness Bypass

## Overview

This roadmap delivers a Claude Code CLI proxy provider for nanobot in four phases. Phase 1 establishes the core provider with auth validation (the single biggest risk). Phase 2 adds session management so conversations persist across turns. Phase 3 layers in user-facing configuration and nanobot integration. Phase 4 hardens subprocess lifecycle for production reliability. Each phase delivers a complete, verifiable capability that builds on the previous one.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3, 4): Planned milestone work
- Decimal phases (e.g., 2.1): Urgent insertions (marked with INSERTED)

- [ ] **Phase 1: Core Provider** - Working Claude Code CLI round-trip registered in nanobot's provider system
- [ ] **Phase 2: Session Management** - Persistent and one-shot conversation modes
- [ ] **Phase 3: UX Integration** - Persona control, output verbosity, CLI flag, and menu entry
- [ ] **Phase 4: Robustness** - Subprocess lifecycle hardening for production use

## Phase Details

### Phase 1: Core Provider
**Goal**: Users can send prompts through nanobot and receive responses via Claude Code CLI, with the provider fully integrated into nanobot's existing provider system
**Depends on**: Nothing (first phase)
**Requirements**: CORE-01, CORE-02, CORE-03, CORE-04, CORE-05, CORE-06
**Success Criteria** (what must be TRUE):
  1. User can send a prompt in nanobot and receive a complete response routed through Claude Code CLI
  2. User can select "Claude Code (Bypass)" from nanobot's provider configuration like any other provider
  3. Nanobot refuses to start in bypass mode when `claude` binary is not found, with clear install instructions
  4. Auth failures and CLI errors surface as readable messages in the chat, not stack traces
  5. All CLI invocations use `--setting-sources ""` flag to reduce overhead while preserving subscription auth
**Plans**: 2 plans

Plans:
- [x] 01-01-PLAN.md -- Implement ClaudeCodeProvider class with tests (CORE-01, CORE-04, CORE-05, CORE-06)
- [x] 01-02-PLAN.md -- Register provider in registry, config, and instantiation wiring (CORE-02, CORE-03)

### Phase 2: Session Management
**Goal**: Users can have multi-turn conversations with persistent context, or use independent one-shot prompts, with the ability to switch between modes
**Depends on**: Phase 1
**Requirements**: SESS-01, SESS-02, SESS-03
**Success Criteria** (what must be TRUE):
  1. User can send multiple messages in session mode and Claude Code retains context from prior turns
  2. User can send a message in one-shot mode and it has no awareness of previous messages
  3. User can toggle between session and one-shot modes within a conversation and the behavior changes accordingly
**Plans**: TBD

Plans:
- [ ] 02-01: TBD

### Phase 3: UX Integration
**Goal**: Users can control persona passthrough, output verbosity, and activate bypass mode through familiar nanobot interfaces
**Depends on**: Phase 2
**Requirements**: UX-01, UX-02, UX-03, UX-04
**Success Criteria** (what must be TRUE):
  1. User can toggle persona passthrough on/off and observe Claude Code responses with or without the nanobot persona
  2. User can switch output verbosity between full tool output, final-only, and summarized, and see the difference in response content
  3. User can launch bypass mode via `nanobot chat --bypass` from the command line
  4. User sees "Claude Code (Bypass)" as a selectable option in nanobot's interactive provider picker menu
**Plans**: TBD

Plans:
- [ ] 03-01: TBD

### Phase 4: Robustness
**Goal**: Subprocess lifecycle is hardened so the provider is reliable under sustained use, concurrent requests, and gateway deployments
**Depends on**: Phase 1
**Requirements**: ROBU-01, ROBU-02, ROBU-03
**Success Criteria** (what must be TRUE):
  1. After many consecutive interactions, no orphaned or zombie `claude` processes remain (verifiable via `ps` inspection)
  2. When multiple concurrent requests arrive, excess requests queue rather than spawning unbounded subprocesses
  3. In gateway mode, subprocess environment does not leak host API keys or sensitive environment variables
**Plans**: TBD

Plans:
- [ ] 04-01: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> 3 -> 4

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Core Provider | 0/2 | Not started | - |
| 2. Session Management | 0/1 | Not started | - |
| 3. UX Integration | 0/1 | Not started | - |
| 4. Robustness | 0/1 | Not started | - |
