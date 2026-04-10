# Technology Stack

**Analysis Date:** 2026-04-09

## Languages

**Primary:**
- Python 3.11+ - Core framework (`nanobot/` package, all agent/channel/provider logic)
- TypeScript 5.4 - WhatsApp bridge (`bridge/src/`)

**Secondary:**
- Shell (sh/bash) - Docker entrypoint and skills scripts (`entrypoint.sh`, `nanobot/skills/**/*.sh`)

## Runtime

**Environment:**
- CPython 3.11+ (requires `>=3.11`, tested against 3.11 and 3.12)
- Node.js 20+ (required for WhatsApp bridge; installed in Docker image from NodeSource)

**Package Manager:**
- Python: `uv` (Astral) — base Docker image is `ghcr.io/astral-sh/uv:python3.12-bookworm-slim`
- Node: npm (for `bridge/` only)
- Lockfile: `pyproject.toml` (no separate lockfile committed; uv resolves at build time)

## Frameworks

**Core:**
- `typer>=0.20.0` — CLI entrypoint (`nanobot/cli/commands.py`)
- `pydantic>=2.12.0` + `pydantic-settings>=2.12.0` — config schema and validation (`nanobot/config/schema.py`)
- `aiohttp>=3.9.0` (optional `api` extra) — OpenAI-compatible HTTP API server (`nanobot/api/server.py`)
- `websockets>=16.0` + `websocket-client>=1.9.0` — gateway WebSocket transport (`nanobot/bus/`)
- `python-socketio>=5.16.0` — Socket.IO transport layer

**Testing:**
- `pytest>=9.0.0` with `pytest-asyncio>=1.3.0` — all tests async-native
- `pytest-cov>=6.0.0` — coverage reporting
- Config: `[tool.pytest.ini_options]` in `pyproject.toml`, `asyncio_mode = "auto"`

**Build:**
- `hatchling` — Python package build backend
- `ruff>=0.1.0` — linting and import sorting; line length 100, targets py311

**WhatsApp Bridge (Node):**
- `typescript^5.4` — compiled with `tsc`
- `@whiskeysockets/baileys 7.0.0-rc.9` — WhatsApp Web API client
- `ws^8.17.1` — WebSocket server for bridge ↔ Python IPC
- `pino^9.0.0` — structured logging

## Key Dependencies

**Critical:**
- `anthropic>=0.45.0` — native Anthropic SDK used by `AnthropicProvider` (`nanobot/providers/anthropic_provider.py`); handles prompt caching, streaming, extended thinking
- `openai>=2.8.0` — OpenAI SDK used by `OpenAICompatProvider` (`nanobot/providers/openai_compat_provider.py`); covers all non-Anthropic providers
- `mcp>=1.26.0` — Model Context Protocol client for external tool servers (`nanobot/agent/tools/mcp.py`)
- `jinja2>=3.1.0` — agent system prompt and template rendering (`nanobot/templates/`)

**Messaging Channels:**
- `python-telegram-bot[socks]>=22.6` — Telegram channel (`nanobot/channels/telegram.py`)
- `slack-sdk>=3.39.0` + `slackify-markdown>=0.2.0` — Slack Socket Mode (`nanobot/channels/slack.py`)
- `dingtalk-stream>=0.24.0` — DingTalk channel (`nanobot/channels/dingtalk.py`)
- `lark-oapi>=1.5.0` — Feishu/Lark channel (`nanobot/channels/feishu.py`)
- `qq-botpy>=1.2.0` — QQ channel (`nanobot/channels/qq.py`)
- `matrix-nio[e2e]>=0.25.2` (optional `matrix` extra) — Matrix/Element channel (`nanobot/channels/matrix.py`)
- `discord.py>=2.5.2` (optional `discord` extra) — Discord channel (`nanobot/channels/discord.py`)
- `wecom-aibot-sdk-python>=0.1.5` (optional `wecom` extra) — WeCom channel (`nanobot/channels/wecom.py`)
- `qrcode[pil]>=8.0` + `pycryptodome>=3.20.0` (optional `weixin` extra) — WeChat/Weixin channel (`nanobot/channels/weixin.py`)

**Infrastructure:**
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

**Environment:**
- Pydantic `BaseSettings` with `env_prefix="NANOBOT_"` and `env_nested_delimiter="__"` (`nanobot/config/schema.py` `Config` class)
- Config file loaded from `~/.nanobot/config.yaml` by default
- Key env vars: `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `OPENROUTER_API_KEY`, `GROQ_API_KEY`, `DEEPSEEK_API_KEY`, `GEMINI_API_KEY`, plus per-channel tokens (see INTEGRATIONS.md)

**Build:**
- `pyproject.toml` — project metadata, dependencies, build configuration
- `hatch.build` includes `nanobot/**/*.py`, template `.md` files, skill `.sh` files, and the `bridge/` directory

## Platform Requirements

**Development:**
- Python 3.11 or 3.12
- Node.js 20+ (for WhatsApp bridge only)
- `uv` recommended for dependency management

**Production:**
- Docker via `docker-compose.yml` (three services: `nanobot-gateway` on port 18790, `nanobot-api` on port 8900, `nanobot-cli`)
- Base image: `ghcr.io/astral-sh/uv:python3.12-bookworm-slim` (Debian bookworm)
- Runs as non-root user `nanobot` (UID 1000)
- Requires `SYS_ADMIN` capability for sandbox (bubblewrap)
- Data directory: `~/.nanobot` (volume-mounted in Docker)

---

*Stack analysis: 2026-04-09*
