# Architecture

**Analysis Date:** 2026-04-09

## Pattern Overview

**Overall:** Event-driven, layered agent framework with async message bus

**Key Characteristics:**
- A central `MessageBus` (async queue pair) decouples all chat channels from the agent core
- The `AgentLoop` is the sole consumer of inbound messages and drives the LLM iteration cycle
- LLM providers are abstracted behind a uniform `LLMProvider` ABC; all concrete providers implement `chat()` and `chat_stream()`
- Tool execution, session persistence, memory, and scheduling are independent subsystems wired together inside `AgentLoop.__init__`
- A hook system (`AgentHook` / `CompositeHook`) gives callers lifecycle callbacks at each iteration without coupling to the loop internals

## Layers

**CLI / Entry Layer:**
- Purpose: User-facing interface; starts the asyncio event loop, initializes all subsystems, prints responses
- Location: `nanobot/cli/commands.py`
- Contains: typer commands (`chat`, `run`, `serve`, `status`, `config`), streaming renderers
- Depends on: config loader, `AgentLoop`, `ChannelManager`, `MessageBus`
- Used by: End users via `nanobot` script entry point; `nanobot/__main__.py`

**Channel Layer:**
- Purpose: Adapts chat platform messages (Telegram, Discord, Slack, WhatsApp, etc.) to/from bus events
- Location: `nanobot/channels/`
- Contains: `BaseChannel` ABC + 15 concrete implementations; `ChannelManager`; plugin registry
- Depends on: `MessageBus`, `nanobot/bus/events.py`
- Used by: `AgentLoop.run()` dispatches outbound; channels push inbound

**Bus / Events:**
- Purpose: Async decoupling layer — two asyncio queues (inbound / outbound)
- Location: `nanobot/bus/queue.py`, `nanobot/bus/events.py`
- Contains: `MessageBus`, `InboundMessage`, `OutboundMessage` dataclasses
- Depends on: nothing (pure asyncio)
- Used by: `AgentLoop`, `ChannelManager`, `SubagentManager`, `MessageTool`

**Agent Core:**
- Purpose: Drives the LLM tool-use loop; manages sessions; calls providers; executes tools
- Location: `nanobot/agent/`
- Contains: `AgentLoop`, `AgentRunner`, `ContextBuilder`, `SubagentManager`, `AgentHook`, `MemoryStore`, `Consolidator`, `Dream`, `SkillsLoader`
- Depends on: providers, tools, session, config, bus, memory
- Used by: CLI, API server, programmatic `Nanobot` facade

**Provider Layer:**
- Purpose: Abstract LLM access; normalize responses; retry transient failures
- Location: `nanobot/providers/`
- Contains: `LLMProvider` ABC (`nanobot/providers/base.py`), concrete providers (anthropic, openai_compat, azure, codex, copilot, openai_responses), `ProviderSpec` registry (`nanobot/providers/registry.py`)
- Depends on: external HTTP libs (anthropic SDK, httpx, openai SDK)
- Used by: `AgentLoop`, `AgentRunner`, `SubagentManager`, `Consolidator`, `Dream`

**Tool Layer:**
- Purpose: Executable capabilities the LLM can invoke; all tools conform to `Tool` base class
- Location: `nanobot/agent/tools/`
- Contains: `ToolRegistry`, `ReadFileTool`, `WriteFileTool`, `EditFileTool`, `ListDirTool`, `GlobTool`, `GrepTool`, `ExecTool`, `WebSearchTool`, `WebFetchTool`, `MessageTool`, `SpawnTool`, `CronTool`, MCP connector
- Depends on: security module for SSRF protection, config, bus
- Used by: `AgentRunner` during tool execution phase

**Session Layer:**
- Purpose: Persist per-conversation history across turns; manage session keys
- Location: `nanobot/session/manager.py`
- Contains: `Session` dataclass, `SessionManager` (JSON file persistence under workspace)
- Depends on: filesystem
- Used by: `AgentLoop._process_message()`, `AgentLoop._save_turn()`

**Command Layer:**
- Purpose: Slash-command routing (`/stop`, `/clear`, `/skills`, etc.) short-circuiting normal agent dispatch
- Location: `nanobot/command/`
- Contains: `CommandRouter` (priority / exact / prefix / interceptor tiers), `CommandContext`, `register_builtin_commands()`
- Depends on: session, bus events
- Used by: `AgentLoop.run()` (priority commands before lock) and `_process_message()` (other commands inside lock)

**Config Layer:**
- Purpose: Load and validate `~/.nanobot/config.json`; provide typed access to all settings
- Location: `nanobot/config/`
- Contains: `Config` Pydantic model, `AgentDefaults`, `ProviderConfig`, `ChannelsConfig`, `ToolsConfig`; `load_config()`, `resolve_config_env_vars()`
- Depends on: pydantic, pydantic-settings
- Used by: CLI startup, `Nanobot.from_config()`, all subsystems

**API Server (optional):**
- Purpose: Expose an OpenAI-compatible `/v1/chat/completions` HTTP endpoint
- Location: `nanobot/api/server.py`
- Contains: aiohttp routes mapping to `AgentLoop.process_direct()`
- Depends on: `AgentLoop`, aiohttp (optional dep)
- Used by: `nanobot serve` CLI command

**Bridge (Node.js, optional):**
- Purpose: WebSocket server that bridges the Python agent to WhatsApp Web via `whatsapp-web.js`
- Location: `bridge/src/`
- Contains: `BridgeServer` (TypeScript), `WhatsAppClient`, `server.ts` entry point
- Depends on: ws, whatsapp-web.js
- Used by: WhatsApp channel implementation (`nanobot/channels/whatsapp.py`)

## Data Flow

**Normal chat turn (channel → agent → channel):**

1. Chat channel (e.g. Telegram) receives a platform event and calls `bus.publish_inbound(InboundMessage(...))`
2. `AgentLoop.run()` dequeues the message from `bus.inbound`
3. Priority slash commands are dispatched immediately; all other messages are dispatched as asyncio tasks
4. `_dispatch()` acquires per-session lock + optional global concurrency gate, then calls `_process_message()`
5. `_process_message()` resolves the `Session`, runs non-priority slash commands, and calls `ContextBuilder.build_messages()` to assemble history + system prompt + current user message
6. `_run_agent_loop()` delegates to `AgentRunner.run(AgentRunSpec(...))` with all iteration parameters
7. Inside `AgentRunner.run()`: call `provider.chat_stream_with_retry()` → receive `LLMResponse` → check for tool calls → execute tools in parallel → append results → repeat up to `max_iterations`
8. After the loop, `AgentLoop._save_turn()` persists the new messages into the session; `consolidator.maybe_consolidate_by_tokens()` is scheduled as a background task
9. `_process_message()` returns an `OutboundMessage`; `_dispatch()` calls `bus.publish_outbound()`
10. `ChannelManager` dispatches the outbound message to the appropriate channel's `send()` method

**Subagent (background task) flow:**

1. Agent calls `spawn` tool → `SpawnTool.call()` → `SubagentManager.spawn(task, ...)`
2. `SubagentManager` creates a fresh `ToolRegistry`, starts an `AgentRunner` in a new asyncio task
3. On completion, the subagent publishes a `system`-channel `InboundMessage` back onto the bus with `sender_id="subagent"`
4. The main `AgentLoop` processes the system message and sends the result to the originating channel

**Direct / SDK flow:**

1. Caller creates `Nanobot.from_config()` or constructs `AgentLoop` directly
2. Calls `loop.process_direct(content, session_key=...)` or `Nanobot.run(message)`
3. Bypasses bus; goes straight to `_process_message()`

**State Management:**
- Conversation history is stored as JSON files under `{workspace}/sessions/`
- Long-term memory (`MEMORY.md`, `history.jsonl`) is stored under `{workspace}/memory/`
- `Consolidator` monitors token counts and triggers summarization when `context_window_tokens` is exceeded
- `Dream` runs on a cron schedule to synthesize `history.jsonl` entries into `MEMORY.md`
- Runtime checkpoints (in-flight tool calls) are stored in `session.metadata` and restored on restart

## Key Abstractions

**LLMProvider (`nanobot/providers/base.py`):**
- Purpose: Uniform interface to all LLM backends
- Pattern: Abstract base class; subclasses implement `chat()` and optionally override `chat_stream()`; retry logic (`chat_stream_with_retry`, `chat_with_retry`) lives in the base class

**Tool (`nanobot/agent/tools/base.py`):**
- Purpose: Single executable capability with a JSON schema definition
- Pattern: ABC with `name`, `description`, `parameters`, and `call()` async method; `ToolRegistry` holds instances by name

**AgentHook (`nanobot/agent/hook.py`):**
- Purpose: Lifecycle observer inserted at `before_iteration`, `before_execute_tools`, `after_iteration`, and `finalize_content`
- Pattern: Null-object base class; `CompositeHook` fans out to multiple hooks with per-hook error isolation; `_LoopHook` is the internal implementation for streaming + progress

**BaseChannel (`nanobot/channels/base.py`):**
- Purpose: Adapter for a single chat platform
- Pattern: ABC requiring `start()`, `stop()`, and `send()`; platform-specific subclasses in `nanobot/channels/`; discovered at runtime via `pkgutil` scan + `entry_points` plugins

**ProviderSpec (`nanobot/providers/registry.py`):**
- Purpose: Metadata record describing one LLM provider (keywords, env key, backend type, API base URL)
- Pattern: Frozen dataclass in a global `PROVIDERS` tuple; `find_by_name()` does lookup; config auto-detects provider from model name keywords

**Session (`nanobot/session/manager.py`):**
- Purpose: Isolated conversation state keyed by `"{channel}:{chat_id}"`
- Pattern: Dataclass with `messages: list[dict]`; serialized to/from JSON by `SessionManager`; `get_history()` returns a legal tool-call-boundary-aligned slice

## Entry Points

**CLI (`nanobot chat`):**
- Location: `nanobot/cli/commands.py` → `@app.command("chat")`
- Triggers: User runs `nanobot chat` in terminal
- Responsibilities: Load config, construct `AgentLoop` + channels, run asyncio event loop, render responses

**Module entry point:**
- Location: `nanobot/__main__.py`
- Triggers: `python -m nanobot`
- Responsibilities: Delegates to `nanobot.cli.commands:app`

**SDK facade (`Nanobot`):**
- Location: `nanobot/nanobot.py`
- Triggers: `await Nanobot.from_config().run("...")`
- Responsibilities: Creates provider + `AgentLoop` from config; exposes single `run()` coroutine returning `RunResult`

**HTTP API server:**
- Location: `nanobot/api/server.py`; started by `nanobot serve` command
- Triggers: POST `/v1/chat/completions`
- Responsibilities: Validate request, call `AgentLoop.process_direct()`, return OpenAI-compatible JSON

## Error Handling

**Strategy:** Catch-at-boundary, log-and-continue; transient LLM errors are retried with exponential backoff in `LLMProvider._run_with_retry()`

**Patterns:**
- `AgentRunner` catches tool execution exceptions and returns an error string as the tool result
- `AgentLoop._dispatch()` wraps each message task in a broad `except Exception` that logs and publishes an error outbound message
- `CompositeHook._for_each_hook_safe()` catches per-hook exceptions so a faulty hook cannot crash the loop
- The `_safe_chat` / `_safe_chat_stream` wrappers convert unexpected provider exceptions to `LLMResponse(finish_reason="error")`
- Non-transient provider errors (quota exhausted, 4xx non-429) are NOT retried; structured error metadata (`error_should_retry`, `error_status_code`) takes precedence over text matching

## Cross-Cutting Concerns

**Logging:** `loguru` used throughout; all modules import `from loguru import logger`; structured messages via `logger.info("... {} {}", arg1, arg2)` format
**Validation:** Pydantic v2 models for all config; tool parameter validation via `Schema.validate_json_schema_value()` in `nanobot/agent/tools/base.py`
**Authentication:** Per-channel API tokens from config; LLM API keys from config or env vars; SSRF protection for web tools in `nanobot/security/network.py`
**Concurrency:** Per-session `asyncio.Lock` serializes turns within a session; global `asyncio.Semaphore` (default 3) limits cross-session concurrency; tool calls within a turn run in parallel via `asyncio.gather()`

---

*Architecture analysis: 2026-04-09*
