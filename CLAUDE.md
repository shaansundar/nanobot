<!-- GSD:project-start source:PROJECT.md -->
## Project

**Nanobot Harness Bypass**

A new mode for nanobot that routes all AI interactions through the official Claude Code CLI instead of direct API calls. This lets subscription users (Max, Pro) continue using nanobot's multi-channel UI and tooling after Anthropic restricts third-party harness access. Nanobot becomes a wrapper that pipes prompts to `claude` CLI and streams responses back.

**Core Value:** Subscription users can keep using nanobot's full feature set by transparently proxying through Claude Code CLI — the one harness that always works with subscriptions.

### Constraints

- **Runtime**: Claude Code CLI (`claude`) must be installed and authenticated on the user's machine
- **Platform**: macOS/Linux only (Claude Code CLI requirement)
- **Latency**: Extra overhead from process spawning; streaming mitigates perceived delay
- **Concurrency**: Claude Code CLI may have its own session/concurrency limits
<!-- GSD:project-end -->

<!-- GSD:stack-start source:codebase/STACK.md -->
## Technology Stack

## Languages
- Python 3.11+ - Core framework (`nanobot/` package, all agent/channel/provider logic)
- TypeScript 5.4 - WhatsApp bridge (`bridge/src/`)
- Shell (sh/bash) - Docker entrypoint and skills scripts (`entrypoint.sh`, `nanobot/skills/**/*.sh`)
## Runtime
- CPython 3.11+ (requires `>=3.11`, tested against 3.11 and 3.12)
- Node.js 20+ (required for WhatsApp bridge; installed in Docker image from NodeSource)
- Python: `uv` (Astral) — base Docker image is `ghcr.io/astral-sh/uv:python3.12-bookworm-slim`
- Node: npm (for `bridge/` only)
- Lockfile: `pyproject.toml` (no separate lockfile committed; uv resolves at build time)
## Frameworks
- `typer>=0.20.0` — CLI entrypoint (`nanobot/cli/commands.py`)
- `pydantic>=2.12.0` + `pydantic-settings>=2.12.0` — config schema and validation (`nanobot/config/schema.py`)
- `aiohttp>=3.9.0` (optional `api` extra) — OpenAI-compatible HTTP API server (`nanobot/api/server.py`)
- `websockets>=16.0` + `websocket-client>=1.9.0` — gateway WebSocket transport (`nanobot/bus/`)
- `python-socketio>=5.16.0` — Socket.IO transport layer
- `pytest>=9.0.0` with `pytest-asyncio>=1.3.0` — all tests async-native
- `pytest-cov>=6.0.0` — coverage reporting
- Config: `[tool.pytest.ini_options]` in `pyproject.toml`, `asyncio_mode = "auto"`
- `hatchling` — Python package build backend
- `ruff>=0.1.0` — linting and import sorting; line length 100, targets py311
- `typescript^5.4` — compiled with `tsc`
- `@whiskeysockets/baileys 7.0.0-rc.9` — WhatsApp Web API client
- `ws^8.17.1` — WebSocket server for bridge ↔ Python IPC
- `pino^9.0.0` — structured logging
## Key Dependencies
- `anthropic>=0.45.0` — native Anthropic SDK used by `AnthropicProvider` (`nanobot/providers/anthropic_provider.py`); handles prompt caching, streaming, extended thinking
- `openai>=2.8.0` — OpenAI SDK used by `OpenAICompatProvider` (`nanobot/providers/openai_compat_provider.py`); covers all non-Anthropic providers
- `mcp>=1.26.0` — Model Context Protocol client for external tool servers (`nanobot/agent/tools/mcp.py`)
- `jinja2>=3.1.0` — agent system prompt and template rendering (`nanobot/templates/`)
- `python-telegram-bot[socks]>=22.6` — Telegram channel (`nanobot/channels/telegram.py`)
- `slack-sdk>=3.39.0` + `slackify-markdown>=0.2.0` — Slack Socket Mode (`nanobot/channels/slack.py`)
- `dingtalk-stream>=0.24.0` — DingTalk channel (`nanobot/channels/dingtalk.py`)
- `lark-oapi>=1.5.0` — Feishu/Lark channel (`nanobot/channels/feishu.py`)
- `qq-botpy>=1.2.0` — QQ channel (`nanobot/channels/qq.py`)
- `matrix-nio[e2e]>=0.25.2` (optional `matrix` extra) — Matrix/Element channel (`nanobot/channels/matrix.py`)
- `discord.py>=2.5.2` (optional `discord` extra) — Discord channel (`nanobot/channels/discord.py`)
- `wecom-aibot-sdk-python>=0.1.5` (optional `wecom` extra) — WeCom channel (`nanobot/channels/wecom.py`)
- `qrcode[pil]>=8.0` + `pycryptodome>=3.20.0` (optional `weixin` extra) — WeChat/Weixin channel (`nanobot/channels/weixin.py`)
- `httpx>=0.28.0` — async HTTP client used throughout (search, transcription, providers)
- `loguru>=0.7.3` — structured logging framework used project-wide
- `croniter>=6.0.0` — cron schedule parsing for heartbeat and scheduled tasks (`nanobot/cron/`)
- `tiktoken>=0.12.0` — token counting for context window management
- `rich>=14.0.0` — terminal output formatting (`nanobot/cli/`)
- `prompt_toolkit>=3.0.50` + `questionary>=2.0.0` — interactive CLI (`nanobot/cli/commands.py`)
- `dulwich>=0.22.0` — pure-Python Git operations (workspace template sync)
- `filelock>=3.25.2` — file-level locking for concurrent access
- `json-repair>=0.57.0` — robust JSON parsing from LLM outputs
- `readability-lxml>=0.8.4` — web page content extraction (`nanobot/agent/tools/web.py`)
- `msgpack>=1.1.0` — binary serialization
- `socksio>=1.0.0` + `python-socks[asyncio]>=2.8.0` — SOCKS5 proxy support
- `ddgs>=9.5.5` — DuckDuckGo search (default search provider)
- `oauth-cli-kit>=0.1.3` — OAuth device-code flow (GitHub Copilot, OpenAI Codex providers)
- `langfuse>=0.1.0` (optional `langfuse` extra) + `langsmith>=0.1.0` (optional `langsmith` extra) — LLM observability tracing
## Configuration
- Pydantic `BaseSettings` with `env_prefix="NANOBOT_"` and `env_nested_delimiter="__"` (`nanobot/config/schema.py` `Config` class)
- Config file loaded from `~/.nanobot/config.yaml` by default
- Key env vars: `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `OPENROUTER_API_KEY`, `GROQ_API_KEY`, `DEEPSEEK_API_KEY`, `GEMINI_API_KEY`, plus per-channel tokens (see INTEGRATIONS.md)
- `pyproject.toml` — project metadata, dependencies, build configuration
- `hatch.build` includes `nanobot/**/*.py`, template `.md` files, skill `.sh` files, and the `bridge/` directory
## Platform Requirements
- Python 3.11 or 3.12
- Node.js 20+ (for WhatsApp bridge only)
- `uv` recommended for dependency management
- Docker via `docker-compose.yml` (three services: `nanobot-gateway` on port 18790, `nanobot-api` on port 8900, `nanobot-cli`)
- Base image: `ghcr.io/astral-sh/uv:python3.12-bookworm-slim` (Debian bookworm)
- Runs as non-root user `nanobot` (UID 1000)
- Requires `SYS_ADMIN` capability for sandbox (bubblewrap)
- Data directory: `~/.nanobot` (volume-mounted in Docker)
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

## Naming Patterns
- Modules use `snake_case`: `openai_compat_provider.py`, `github_copilot_provider.py`
- Test files prefixed with `test_`: `test_provider_retry.py`, `test_filesystem_tools.py`
- Private helpers prefixed with `_`: `_FsTool`, `_gen_tool_id`, `_fake_resolve`
- `PascalCase` throughout: `LLMProvider`, `OpenAICompatProvider`, `AnthropicProvider`
- Abstract bases use descriptive names: `LLMProvider`, `BaseChannel`, `_FsTool`
- Test fakes/stubs named with intent: `ScriptedProvider`, `MockChannel`, `_DummyChannel`
- `snake_case`: `chat_with_retry`, `get_default_model`, `build_image_content_blocks`
- Private methods prefixed `_`: `_sanitize_empty_content`, `_enforce_role_alternation`, `_extract_retry_after`
- Static/classmethod helpers prefixed `_`: `_tool_name`, `_is_transient_error`, `_normalize_error_token`
- `snake_case`: `retry_after`, `error_status_code`, `last_error_key`
- Module-level constants: `UPPER_SNAKE_CASE`: `_UNSAFE_CHARS`, `_TOOL_RESULT_PREVIEW_CHARS`
- Sentinel values: `_SENTINEL = object()` (class-level, single-underscore prefixed)
- Use `is_` / `has_` / `supports_` prefixes: `has_tool_calls`, `is_allowed`, `is_transient_error`, `supports_prompt_caching`
- Type annotations on all signatures using modern Python 3.10+ union syntax: `str | None`, `list[dict[str, Any]] | None`
## Code Style
- Tool: `ruff` (`line-length = 100`)
- Target version: `py311`
- Config in `pyproject.toml` under `[tool.ruff]`
- `ruff` with rule sets: `E` (pycodestyle), `F` (Pyflakes), `I` (isort), `N` (pep8-naming), `W` (warnings)
- `E501` (line too long) is explicitly ignored — ruff formats but won't flag long lines as errors
- All function signatures carry full type annotations
- `Any` from `typing` used for heterogeneous dict values
- `from __future__ import annotations` used in ~40 files to enable forward references
## Import Organization
- None — all imports use absolute `nanobot.*` paths. No `__init__.py` re-exports used for aliasing.
## Error Handling
- Exceptions raised at validation boundaries with `ValueError` (bad config/args) or `RuntimeError` (runtime failures): `raise ValueError("Azure OpenAI api_key is required")`, `raise RuntimeError("GitHub Copilot is not logged in...")`
- Provider errors converted to `LLMResponse(finish_reason="error")` rather than propagating: `_safe_chat` wraps `chat()` and catches all `Exception` (except `asyncio.CancelledError`)
- `asyncio.CancelledError` is always re-raised — never swallowed: `except asyncio.CancelledError: raise`
- `PermissionError` raised for filesystem boundary violations: `_resolve_path` raises if path escapes workspace
- No bare `except:` usage — exceptions are typed or at least `except Exception`
- LLM call errors returned as `LLMResponse(content=f"Error calling LLM: {exc}", finish_reason="error")`
- Structured error metadata fields on `LLMResponse`: `error_status_code`, `error_kind`, `error_type`, `error_code`, `error_retry_after_s`, `error_should_retry`
## Logging
- `logger.warning(...)` for transient/retryable errors and degraded behavior
- `logger.warning("Failed to parse tool call arguments...")` for non-fatal parse failures
- Loguru template-style placeholders: `logger.warning("LLM error (attempt {}{}), retrying in {}s: {}", attempt, ...)`
- No `logger.info` in hot paths — debug-level info not widely used in the provider layer
## Comments
- Module-level docstring on every module: `"""Base LLM provider interface."""`
- Class-level docstring explains purpose and scope: `"""Base class for LLM providers."""`
- Method-level docstrings on public/abstract methods with Args/Returns sections
- Inline comments for non-obvious decisions: `# Unknown 429 defaults to WAIT+retry.`
- Section separators using `# ---` dashes to divide large classes/files
## Function Design
- Short utility functions preferred (< 30 lines)
- Larger orchestration methods exist (`_run_with_retry`, `chat_stream_with_retry`) but are bounded by single responsibility
- `_sanitize_empty_content` (~40 lines) is the typical upper range for non-trivial helpers
- Keyword arguments used for optional parameters: `model: str | None = None`, `tool_choice: str | dict[str, Any] | None = None`
- Sentinel pattern for distinguishing "not passed" from `None`: `max_tokens: object = _SENTINEL`
- `**kwargs: Any` used in retry wrappers to forward argument dicts
- Explicit return type annotations on all methods
- `LLMResponse` returned uniformly from all provider call paths
- Helpers return `None` to signal "no change needed" (e.g., `_strip_image_content` returns `None` if no images found)
- Tuple returns used in security module: `validate_url_target` returns `(bool, str)`
## Module Design
- `__init__.py` files are minimal — they re-export key symbols from submodules
- Example: `nanobot/providers/__init__.py` exports provider classes for external use
- Thin `__init__.py` re-exports used at package boundaries (`nanobot/agent/__init__.py`, `nanobot/providers/__init__.py`)
- Not used for deep intra-package imports — modules import directly from sibling modules
## Data Structures
- Used for DTOs and value objects: `ToolCallRequest`, `LLMResponse`, `GenerationSettings`
- `frozen=True` used for immutable settings: `@dataclass(frozen=True) class GenerationSettings`
- `field(default_factory=list)` for mutable defaults
- `BaseModel` (via `pydantic`) used for all configuration schema: `DreamConfig`, `AgentDefaults`, `ChannelsConfig`
- Base `class Base(BaseModel)` with `alias_generator=to_camel` for camelCase JSON compatibility
- `ConfigDict(populate_by_name=True)` allows both snake_case and camelCase input keys
- `Field(..., exclude=True)` used for legacy compatibility fields hidden from serialization
## Async Patterns
- All LLM calls are `async` throughout: `async def chat(...)`, `async def chat_stream(...)`
- `asyncio.CancelledError` always re-raised, never swallowed
- `asyncio.sleep` used for retry delays — patched via `monkeypatch` in tests for speed
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

## Pattern Overview
- A central `MessageBus` (async queue pair) decouples all chat channels from the agent core
- The `AgentLoop` is the sole consumer of inbound messages and drives the LLM iteration cycle
- LLM providers are abstracted behind a uniform `LLMProvider` ABC; all concrete providers implement `chat()` and `chat_stream()`
- Tool execution, session persistence, memory, and scheduling are independent subsystems wired together inside `AgentLoop.__init__`
- A hook system (`AgentHook` / `CompositeHook`) gives callers lifecycle callbacks at each iteration without coupling to the loop internals
## Layers
- Purpose: User-facing interface; starts the asyncio event loop, initializes all subsystems, prints responses
- Location: `nanobot/cli/commands.py`
- Contains: typer commands (`chat`, `run`, `serve`, `status`, `config`), streaming renderers
- Depends on: config loader, `AgentLoop`, `ChannelManager`, `MessageBus`
- Used by: End users via `nanobot` script entry point; `nanobot/__main__.py`
- Purpose: Adapts chat platform messages (Telegram, Discord, Slack, WhatsApp, etc.) to/from bus events
- Location: `nanobot/channels/`
- Contains: `BaseChannel` ABC + 15 concrete implementations; `ChannelManager`; plugin registry
- Depends on: `MessageBus`, `nanobot/bus/events.py`
- Used by: `AgentLoop.run()` dispatches outbound; channels push inbound
- Purpose: Async decoupling layer — two asyncio queues (inbound / outbound)
- Location: `nanobot/bus/queue.py`, `nanobot/bus/events.py`
- Contains: `MessageBus`, `InboundMessage`, `OutboundMessage` dataclasses
- Depends on: nothing (pure asyncio)
- Used by: `AgentLoop`, `ChannelManager`, `SubagentManager`, `MessageTool`
- Purpose: Drives the LLM tool-use loop; manages sessions; calls providers; executes tools
- Location: `nanobot/agent/`
- Contains: `AgentLoop`, `AgentRunner`, `ContextBuilder`, `SubagentManager`, `AgentHook`, `MemoryStore`, `Consolidator`, `Dream`, `SkillsLoader`
- Depends on: providers, tools, session, config, bus, memory
- Used by: CLI, API server, programmatic `Nanobot` facade
- Purpose: Abstract LLM access; normalize responses; retry transient failures
- Location: `nanobot/providers/`
- Contains: `LLMProvider` ABC (`nanobot/providers/base.py`), concrete providers (anthropic, openai_compat, azure, codex, copilot, openai_responses), `ProviderSpec` registry (`nanobot/providers/registry.py`)
- Depends on: external HTTP libs (anthropic SDK, httpx, openai SDK)
- Used by: `AgentLoop`, `AgentRunner`, `SubagentManager`, `Consolidator`, `Dream`
- Purpose: Executable capabilities the LLM can invoke; all tools conform to `Tool` base class
- Location: `nanobot/agent/tools/`
- Contains: `ToolRegistry`, `ReadFileTool`, `WriteFileTool`, `EditFileTool`, `ListDirTool`, `GlobTool`, `GrepTool`, `ExecTool`, `WebSearchTool`, `WebFetchTool`, `MessageTool`, `SpawnTool`, `CronTool`, MCP connector
- Depends on: security module for SSRF protection, config, bus
- Used by: `AgentRunner` during tool execution phase
- Purpose: Persist per-conversation history across turns; manage session keys
- Location: `nanobot/session/manager.py`
- Contains: `Session` dataclass, `SessionManager` (JSON file persistence under workspace)
- Depends on: filesystem
- Used by: `AgentLoop._process_message()`, `AgentLoop._save_turn()`
- Purpose: Slash-command routing (`/stop`, `/clear`, `/skills`, etc.) short-circuiting normal agent dispatch
- Location: `nanobot/command/`
- Contains: `CommandRouter` (priority / exact / prefix / interceptor tiers), `CommandContext`, `register_builtin_commands()`
- Depends on: session, bus events
- Used by: `AgentLoop.run()` (priority commands before lock) and `_process_message()` (other commands inside lock)
- Purpose: Load and validate `~/.nanobot/config.json`; provide typed access to all settings
- Location: `nanobot/config/`
- Contains: `Config` Pydantic model, `AgentDefaults`, `ProviderConfig`, `ChannelsConfig`, `ToolsConfig`; `load_config()`, `resolve_config_env_vars()`
- Depends on: pydantic, pydantic-settings
- Used by: CLI startup, `Nanobot.from_config()`, all subsystems
- Purpose: Expose an OpenAI-compatible `/v1/chat/completions` HTTP endpoint
- Location: `nanobot/api/server.py`
- Contains: aiohttp routes mapping to `AgentLoop.process_direct()`
- Depends on: `AgentLoop`, aiohttp (optional dep)
- Used by: `nanobot serve` CLI command
- Purpose: WebSocket server that bridges the Python agent to WhatsApp Web via `whatsapp-web.js`
- Location: `bridge/src/`
- Contains: `BridgeServer` (TypeScript), `WhatsAppClient`, `server.ts` entry point
- Depends on: ws, whatsapp-web.js
- Used by: WhatsApp channel implementation (`nanobot/channels/whatsapp.py`)
## Data Flow
- Conversation history is stored as JSON files under `{workspace}/sessions/`
- Long-term memory (`MEMORY.md`, `history.jsonl`) is stored under `{workspace}/memory/`
- `Consolidator` monitors token counts and triggers summarization when `context_window_tokens` is exceeded
- `Dream` runs on a cron schedule to synthesize `history.jsonl` entries into `MEMORY.md`
- Runtime checkpoints (in-flight tool calls) are stored in `session.metadata` and restored on restart
## Key Abstractions
- Purpose: Uniform interface to all LLM backends
- Pattern: Abstract base class; subclasses implement `chat()` and optionally override `chat_stream()`; retry logic (`chat_stream_with_retry`, `chat_with_retry`) lives in the base class
- Purpose: Single executable capability with a JSON schema definition
- Pattern: ABC with `name`, `description`, `parameters`, and `call()` async method; `ToolRegistry` holds instances by name
- Purpose: Lifecycle observer inserted at `before_iteration`, `before_execute_tools`, `after_iteration`, and `finalize_content`
- Pattern: Null-object base class; `CompositeHook` fans out to multiple hooks with per-hook error isolation; `_LoopHook` is the internal implementation for streaming + progress
- Purpose: Adapter for a single chat platform
- Pattern: ABC requiring `start()`, `stop()`, and `send()`; platform-specific subclasses in `nanobot/channels/`; discovered at runtime via `pkgutil` scan + `entry_points` plugins
- Purpose: Metadata record describing one LLM provider (keywords, env key, backend type, API base URL)
- Pattern: Frozen dataclass in a global `PROVIDERS` tuple; `find_by_name()` does lookup; config auto-detects provider from model name keywords
- Purpose: Isolated conversation state keyed by `"{channel}:{chat_id}"`
- Pattern: Dataclass with `messages: list[dict]`; serialized to/from JSON by `SessionManager`; `get_history()` returns a legal tool-call-boundary-aligned slice
## Entry Points
- Location: `nanobot/cli/commands.py` → `@app.command("chat")`
- Triggers: User runs `nanobot chat` in terminal
- Responsibilities: Load config, construct `AgentLoop` + channels, run asyncio event loop, render responses
- Location: `nanobot/__main__.py`
- Triggers: `python -m nanobot`
- Responsibilities: Delegates to `nanobot.cli.commands:app`
- Location: `nanobot/nanobot.py`
- Triggers: `await Nanobot.from_config().run("...")`
- Responsibilities: Creates provider + `AgentLoop` from config; exposes single `run()` coroutine returning `RunResult`
- Location: `nanobot/api/server.py`; started by `nanobot serve` command
- Triggers: POST `/v1/chat/completions`
- Responsibilities: Validate request, call `AgentLoop.process_direct()`, return OpenAI-compatible JSON
## Error Handling
- `AgentRunner` catches tool execution exceptions and returns an error string as the tool result
- `AgentLoop._dispatch()` wraps each message task in a broad `except Exception` that logs and publishes an error outbound message
- `CompositeHook._for_each_hook_safe()` catches per-hook exceptions so a faulty hook cannot crash the loop
- The `_safe_chat` / `_safe_chat_stream` wrappers convert unexpected provider exceptions to `LLMResponse(finish_reason="error")`
- Non-transient provider errors (quota exhausted, 4xx non-429) are NOT retried; structured error metadata (`error_should_retry`, `error_status_code`) takes precedence over text matching
## Cross-Cutting Concerns
<!-- GSD:architecture-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd:quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd:debug` for investigation and bug fixing
- `/gsd:execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->



<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd:profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
