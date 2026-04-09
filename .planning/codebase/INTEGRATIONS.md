# External Integrations

**Analysis Date:** 2026-04-09

## LLM Providers

All providers are configured under `providers.*` in config and resolved by `nanobot/providers/registry.py`. The `AnthropicProvider` (`nanobot/providers/anthropic_provider.py`) uses the native Anthropic SDK; all others use the `OpenAICompatProvider` (`nanobot/providers/openai_compat_provider.py`) with provider-specific base URLs.

**Anthropic (Claude):**
- SDK: `anthropic` Python package
- Auth: `ANTHROPIC_API_KEY` env var / `providers.anthropic.api_key` config
- Default model: `anthropic/claude-opus-4-5`
- Features: prompt caching, extended thinking (`reasoning_effort`), streaming, adaptive thinking

**OpenAI:**
- SDK: `openai` Python package
- Auth: `OPENAI_API_KEY` / `providers.openai.api_key`
- Supports `max_completion_tokens` parameter

**OpenAI Codex (OAuth):**
- Backend: `nanobot/providers/openai_codex_provider.py`
- Auth: OAuth device-code flow via `oauth-cli-kit`; tokens stored at `~/.nanobot/oauth/`
- Base URL: `https://chatgpt.com/backend-api`

**GitHub Copilot (OAuth):**
- Backend: `nanobot/providers/github_copilot_provider.py`
- Auth: GitHub device-code OAuth (client ID `Iv1.b507a08c87ecfe98`); tokens in `~/.nanobot/oauth/github-copilot.json`
- Base URL: `https://api.githubcopilot.com`

**OpenRouter (gateway):**
- Auth: `OPENROUTER_API_KEY` / `providers.openrouter.api_key`; detected by `sk-or-` key prefix
- Base URL: `https://openrouter.ai/api/v1`
- Supports prompt caching pass-through

**DeepSeek:**
- Auth: `DEEPSEEK_API_KEY` / `providers.deepseek.api_key`
- Base URL: `https://api.deepseek.com`

**Google Gemini:**
- Auth: `GEMINI_API_KEY` / `providers.gemini.api_key`
- Base URL: `https://generativelanguage.googleapis.com/v1beta/openai/`

**Groq:**
- Auth: `GROQ_API_KEY` / `providers.groq.api_key`
- Base URL: `https://api.groq.com/openai/v1`
- Primary use: voice transcription (Whisper) via `nanobot/providers/transcription.py`

**DashScope / Qwen (Alibaba):**
- Auth: `DASHSCOPE_API_KEY`
- Base URL: `https://dashscope.aliyuncs.com/compatible-mode/v1`

**Zhipu AI:**
- Auth: `ZAI_API_KEY` (also set as `ZHIPUAI_API_KEY`)
- Base URL: `https://open.bigmodel.cn/api/paas/v4`

**Moonshot (Kimi):**
- Auth: `MOONSHOT_API_KEY`
- Base URL: `https://api.moonshot.ai/v1`

**MiniMax:**
- Auth: `MINIMAX_API_KEY`
- Base URL: `https://api.minimax.io/v1`

**Mistral:**
- Auth: `MISTRAL_API_KEY`
- Base URL: `https://api.mistral.ai/v1`

**Step Fun (阶跃星辰):**
- Auth: `STEPFUN_API_KEY`
- Base URL: `https://api.stepfun.com/v1`

**Xiaomi MIMO:**
- Auth: `XIAOMIMIMO_API_KEY`
- Base URL: `https://api.xiaomimimo.com/v1`

**Qianfan / Baidu ERNIE:**
- Auth: `QIANFAN_API_KEY`
- Base URL: `https://qianfan.baidubce.com/v2`

**Azure OpenAI:**
- Backend: `nanobot/providers/azure_openai_provider.py`
- Auth: configured via `providers.azure_openai` config block

**VolcEngine / BytePlus (ByteDance):**
- Auth: `OPENAI_API_KEY` (reused)
- Base URLs: `https://ark.cn-beijing.volces.com/api/v3` (VolcEngine), `https://ark.ap-southeast.bytepluses.com/api/v3` (BytePlus)

**SiliconFlow (硅基流动):**
- Auth: `OPENAI_API_KEY` (reused)
- Base URL: `https://api.siliconflow.cn/v1`

**AiHubMix:**
- Auth: `OPENAI_API_KEY` (reused)
- Base URL: `https://aihubmix.com/v1`

**Local / Self-hosted:**
- Ollama: `OLLAMA_API_KEY`, default `http://localhost:11434/v1`; auto-detected by port `11434` in base URL
- vLLM: `HOSTED_VLLM_API_KEY`; user-supplied `api_base`
- OpenVINO Model Server (OVMS): no API key; default `http://localhost:8000/v3`
- Custom: any OpenAI-compatible endpoint via `providers.custom.api_base`

## Messaging Channel Integrations

All channels are in `nanobot/channels/` and configured under `channels.*` in config.

**Telegram:**
- SDK: `python-telegram-bot[socks]>=22.6`
- Auth: `channels.telegram.token` (bot token from BotFather)
- Inbound: webhook or polling; outbound: Bot API
- File: `nanobot/channels/telegram.py`

**Slack:**
- SDK: `slack-sdk>=3.39.0` (Socket Mode)
- Auth: `channels.slack.bot_token` (Bot token) + `channels.slack.app_token` (Socket Mode token)
- File: `nanobot/channels/slack.py`

**Discord:**
- SDK: `discord.py>=2.5.2` (optional `discord` extra)
- Auth: `channels.discord.token` (bot token)
- File: `nanobot/channels/discord.py`

**WhatsApp:**
- Protocol: Node.js bridge using `@whiskeysockets/baileys` (WhatsApp Web protocol)
- IPC: WebSocket between Python and Node bridge (`ws://localhost:3001` by default)
- Auth: QR code scan on first start; session persisted in `~/.nanobot/runtime/whatsapp-auth/`
- Bridge source: `bridge/src/` (TypeScript)
- Python channel: `nanobot/channels/whatsapp.py`

**Feishu / Lark:**
- SDK: `lark-oapi>=1.5.0`
- Auth: `channels.feishu.app_id` + `channels.feishu.app_secret`
- Transport: WebSocket long connection
- File: `nanobot/channels/feishu.py`

**DingTalk:**
- SDK: `dingtalk-stream>=0.24.0`
- Auth: `channels.dingtalk.client_id` + `channels.dingtalk.client_secret`
- Transport: Stream Mode
- File: `nanobot/channels/dingtalk.py`

**QQ:**
- SDK: `qq-botpy>=1.2.0`
- Auth: `channels.qq.app_id` + `channels.qq.app_secret`
- File: `nanobot/channels/qq.py`

**WeCom (企业微信):**
- SDK: `wecom-aibot-sdk-python>=0.1.5` (optional `wecom` extra)
- File: `nanobot/channels/wecom.py`

**WeChat / Weixin:**
- Deps: `qrcode[pil]>=8.0` + `pycryptodome>=3.20.0` (optional `weixin` extra)
- File: `nanobot/channels/weixin.py`

**Matrix / Element:**
- SDK: `matrix-nio[e2e]>=0.25.2` (optional `matrix` extra); supports E2E encryption
- Auth: `channels.matrix.homeserver_url` + `channels.matrix.username` + `channels.matrix.password`
- File: `nanobot/channels/matrix.py`

**Email:**
- Protocol: Standard library `imaplib` (inbound) + `smtplib` (outbound)
- Auth: `channels.email.imap_username/password` and `channels.email.smtp_username/password`
- File: `nanobot/channels/email.py`

**MoChat / 企微群聊:**
- File: `nanobot/channels/mochat.py`

## Web Search Providers

Configured under `tools.web.search.provider` in config. File: `nanobot/agent/tools/web.py`.

- **DuckDuckGo** (default, no API key) — via `ddgs` library
- **Brave Search** — `BRAVE_API_KEY` / `tools.web.search.api_key`; endpoint `https://api.search.brave.com/res/v1/web/search`
- **Tavily** — `TAVILY_API_KEY`; endpoint `https://api.tavily.com/search`
- **Jina** — `JINA_API_KEY`; endpoint `https://s.jina.ai/`
- **SearXNG** — self-hosted; `SEARXNG_BASE_URL` / `tools.web.search.base_url`

## Data Storage

**Databases:**
- None — no relational or document database
- All state is file-system based under `~/.nanobot/` (configurable via `agents.defaults.workspace`)

**File Storage:**
- Local filesystem only
- Workspace: `~/.nanobot/workspace/` (agent working directory)
- Media/attachments: `~/.nanobot/data/media/`
- Agent memories: `~/.nanobot/data/memory/`
- OAuth tokens: `~/.nanobot/oauth/`
- Runtime state: `~/.nanobot/runtime/`

**Caching:**
- None — no Redis or in-memory cache
- Anthropic prompt caching is used at the API level (controlled by `supports_prompt_caching` flag in provider registry)

## Authentication & Identity

**Auth Provider:**
- Custom per-channel auth (each messaging platform has its own token/credential)
- OAuth device-code flow for GitHub Copilot and OpenAI Codex via `oauth-cli-kit` library

## Monitoring & Observability

**LLM Tracing:**
- Langfuse (optional `langfuse` extra) — activated when `LANGFUSE_SECRET_KEY` env var is set; replaces `AsyncOpenAI` import in `nanobot/providers/openai_compat_provider.py`
- LangSmith (optional `langsmith` extra) — `langsmith>=0.1.0`

**Logs:**
- `loguru` throughout the codebase; no structured log shipping configured
- Docker logs to stdout/stderr

**Error Tracking:**
- None — no Sentry or similar service detected

## CI/CD & Deployment

**Hosting:**
- Docker / Docker Compose (`docker-compose.yml`)
- Three services: `nanobot-gateway` (port 18790), `nanobot-api` (port 127.0.0.1:8900), `nanobot-cli`
- Also installable as a Python package via pip: `pip install nanobot-ai`

**CI Pipeline:**
- Not detected (no `.github/workflows/`, no CI config found in repo root)

## Model Context Protocol (MCP)

- MCP client via `mcp>=1.26.0` library
- Supports stdio, SSE, and StreamableHttp server connections
- Config: `tools.mcp_servers` dict in config schema (`nanobot/config/schema.py`)
- Implementation: `nanobot/agent/tools/mcp.py`
- Per-server tool filtering via `enabled_tools` config field

## Webhooks & Callbacks

**Incoming:**
- Gateway WebSocket endpoint on port 18790 (`nanobot/bus/`)
- OpenAI-compatible HTTP API on port 8900 (`nanobot/api/server.py`): `POST /v1/chat/completions`, `GET /v1/models`
- Slack events webhook path: `/slack/events` (configurable via `channels.slack.webhook_path`)

**Outgoing:**
- All LLM provider APIs (see LLM Providers section)
- All messaging platform APIs (see Messaging Channel Integrations section)
- Web search provider APIs (see Web Search Providers section)
- Voice transcription: OpenAI Whisper (`https://api.openai.com/v1/audio/transcriptions`) or Groq Whisper (`https://api.groq.com/openai/v1/audio/transcriptions`)

## Environment Configuration

**Required env vars (minimum viable setup):**
- At least one LLM provider key, e.g. `ANTHROPIC_API_KEY`
- Per-channel credentials for each enabled messaging platform (e.g. `TELEGRAM_TOKEN`)
- `NANOBOT_` prefix for any config override (e.g. `NANOBOT_AGENTS__DEFAULTS__MODEL`)

**Secrets location:**
- Environment variables (production) or `~/.nanobot/config.yaml` (local dev)
- OAuth tokens stored on disk in `~/.nanobot/oauth/`
- WhatsApp bridge token stored in `~/.nanobot/runtime/whatsapp-auth/bridge-token`

---

*Integration audit: 2026-04-09*
