# Codebase Structure

**Analysis Date:** 2026-04-09

## Directory Layout

```
nanobot-harness-bypass/
├── nanobot/                # Main Python package (installed as nanobot-ai)
│   ├── __init__.py         # Package version + logo
│   ├── __main__.py         # python -m nanobot entry point
│   ├── nanobot.py          # Programmatic SDK facade (Nanobot class)
│   ├── agent/              # Core agent engine
│   │   ├── loop.py         # AgentLoop — main message dispatch + orchestration
│   │   ├── runner.py       # AgentRunner — pure LLM iteration loop
│   │   ├── hook.py         # AgentHook ABC + CompositeHook
│   │   ├── context.py      # ContextBuilder — assembles system prompt + messages
│   │   ├── memory.py       # MemoryStore, Consolidator, Dream
│   │   ├── skills.py       # SkillsLoader — markdown skill files
│   │   ├── subagent.py     # SubagentManager — background task agents
│   │   └── tools/          # Built-in tool implementations
│   │       ├── base.py     # Tool ABC + Schema validation
│   │       ├── registry.py # ToolRegistry
│   │       ├── filesystem.py   # read_file, write_file, edit_file, list_dir
│   │       ├── search.py   # glob, grep
│   │       ├── shell.py    # exec
│   │       ├── web.py      # web_search, web_fetch
│   │       ├── message.py  # message (send to channel)
│   │       ├── spawn.py    # spawn (launch subagent)
│   │       ├── cron.py     # cron tool
│   │       ├── mcp.py      # MCP server connector
│   │       ├── sandbox.py  # Sandbox exec wrapper
│   │       └── schema.py   # JSON schema fragments
│   ├── api/                # Optional OpenAI-compatible HTTP server
│   │   └── server.py       # aiohttp routes for /v1/chat/completions
│   ├── bus/                # Async message bus
│   │   ├── events.py       # InboundMessage, OutboundMessage dataclasses
│   │   └── queue.py        # MessageBus (two asyncio.Queue wrappers)
│   ├── channels/           # Chat platform adapters
│   │   ├── base.py         # BaseChannel ABC
│   │   ├── manager.py      # ChannelManager — init + routing
│   │   ├── registry.py     # Auto-discovery via pkgutil + entry_points
│   │   ├── telegram.py
│   │   ├── discord.py
│   │   ├── slack.py
│   │   ├── whatsapp.py
│   │   ├── weixin.py
│   │   ├── wecom.py
│   │   ├── feishu.py
│   │   ├── dingtalk.py
│   │   ├── matrix.py
│   │   ├── qq.py
│   │   ├── email.py
│   │   └── mochat.py
│   ├── cli/                # typer CLI application
│   │   ├── commands.py     # All CLI commands (chat, run, serve, status, config)
│   │   └── stream.py       # StreamRenderer, ThinkingSpinner
│   ├── command/            # Slash command routing (/stop, /clear, /skills, etc.)
│   │   ├── builtin.py      # Built-in command handlers
│   │   └── router.py       # CommandRouter + CommandContext
│   ├── config/             # Configuration loading + schema
│   │   ├── loader.py       # load_config(), resolve_config_env_vars()
│   │   ├── paths.py        # Canonical filesystem paths (~/.nanobot/…)
│   │   └── schema.py       # Pydantic models (Config, AgentDefaults, etc.)
│   ├── cron/               # Scheduled task service
│   │   ├── service.py      # CronService — file-persisted job queue
│   │   └── types.py        # CronJob, CronSchedule, CronStore dataclasses
│   ├── heartbeat/          # Periodic background agent wake-up
│   │   └── service.py      # HeartbeatService (two-phase: decide then execute)
│   ├── providers/          # LLM backend implementations
│   │   ├── base.py         # LLMProvider ABC, LLMResponse, GenerationSettings
│   │   ├── registry.py     # ProviderSpec + PROVIDERS tuple (single source of truth)
│   │   ├── anthropic_provider.py
│   │   ├── openai_compat_provider.py
│   │   ├── azure_openai_provider.py
│   │   ├── openai_codex_provider.py
│   │   ├── github_copilot_provider.py
│   │   ├── transcription.py    # Whisper (OpenAI + Groq) transcription
│   │   └── openai_responses/  # Subpackage for OpenAI Responses API
│   ├── security/           # Network security utilities
│   │   └── network.py      # SSRF protection, private IP blocking
│   ├── session/            # Conversation history persistence
│   │   └── manager.py      # Session dataclass + SessionManager (JSON files)
│   ├── skills/             # Built-in skill markdown files
│   │   ├── clawhub/
│   │   ├── cron/
│   │   ├── github/
│   │   ├── memory/
│   │   ├── skill-creator/
│   │   ├── summarize/
│   │   ├── tmux/
│   │   └── weather/
│   ├── templates/          # Jinja2 prompt templates
│   │   ├── agent/          # identity.md, platform_policy.md, skills_section.md, etc.
│   │   └── memory/         # Memory consolidation prompts
│   └── utils/              # Shared utilities
│       ├── helpers.py      # Token estimation, text truncation, misc helpers
│       ├── prompt_templates.py  # render_template() Jinja2 loader
│       ├── runtime.py      # Agent runtime helpers and constants
│       ├── gitstore.py     # GitStore — git-backed memory persistence
│       ├── tool_hints.py   # Format tool call summaries for progress display
│       ├── restart.py      # Restart-detection helpers
│       ├── evaluator.py    # LLM-as-evaluator utilities
│       ├── searchusage.py  # Search quota tracking
│       └── path.py         # Path normalization utilities
├── bridge/                 # Node.js WhatsApp bridge (TypeScript)
│   └── src/
│       ├── server.ts       # BridgeServer (WebSocket auth + routing)
│       ├── whatsapp.ts     # WhatsAppClient wrapper
│       ├── types.d.ts      # Type declarations
│       └── index.ts        # Entry point
├── tests/                  # pytest test suite (mirrors nanobot/ layout)
│   ├── agent/
│   ├── channels/
│   ├── cli/
│   ├── command/
│   ├── config/
│   ├── cron/
│   ├── providers/
│   ├── security/
│   ├── tools/
│   └── utils/
├── case/                   # Example GIFs / demo assets
├── docs/                   # Additional documentation
├── .github/workflows/      # CI/CD workflow files
├── pyproject.toml          # Project metadata, deps, hatch build config
├── Dockerfile              # Container build definition
├── docker-compose.yml      # Docker Compose for containerized deployment
├── entrypoint.sh           # Docker container entrypoint
└── .planning/              # GSD planning documents
    └── codebase/           # This directory
```

## Directory Purposes

**`nanobot/agent/`:**
- Purpose: The intelligence layer — agent loop, context assembly, memory, skills, subagents
- Contains: Loop orchestration, LLM runner, hook lifecycle, tool registry, memory consolidation
- Key files: `nanobot/agent/loop.py` (central orchestrator), `nanobot/agent/runner.py` (iteration engine), `nanobot/agent/context.py` (prompt assembly)

**`nanobot/channels/`:**
- Purpose: Platform adapters translating between platform-native events and the bus event types
- Contains: One file per platform, plus manager and auto-discovery registry
- Key files: `nanobot/channels/base.py` (ABC), `nanobot/channels/manager.py` (ChannelManager)

**`nanobot/providers/`:**
- Purpose: All LLM backend communication; retry logic; response normalization
- Contains: One file per backend type; shared retry logic in base; metadata-only registry
- Key files: `nanobot/providers/base.py` (LLMProvider ABC), `nanobot/providers/registry.py` (ProviderSpec + PROVIDERS)

**`nanobot/skills/`:**
- Purpose: Markdown files bundled with the package that teach the agent domain-specific behaviors; each skill is a directory containing `SKILL.md`
- Contains: Built-in skills (clawhub, cron, github, memory, summarize, tmux, weather, skill-creator)
- Key files: Individual `SKILL.md` inside each skill directory

**`nanobot/templates/`:**
- Purpose: Jinja2 templates for system prompt sections; never contain Python logic
- Contains: `agent/*.md` (identity, platform policy, skills section, subagent prompts), `memory/*.md` (consolidation prompts)
- Key files: `nanobot/templates/agent/identity.md` (core system prompt identity block)

**`tests/`:**
- Purpose: pytest test suite; directory structure mirrors `nanobot/` for one-to-one mapping
- Contains: Unit and integration tests per subsystem
- Key files: Top-level `tests/test_nanobot_facade.py` (Nanobot SDK facade tests), `tests/test_openai_api.py` (API server integration)

**`bridge/`:**
- Purpose: Standalone Node.js process providing WhatsApp connectivity via `whatsapp-web.js`; communicates with Python via local WebSocket
- Contains: TypeScript source compiled to JavaScript; separate `package.json`
- Key files: `bridge/src/server.ts` (authentication + command routing), `bridge/src/whatsapp.ts` (WhatsApp client)

## Key File Locations

**Entry Points:**
- `nanobot/__main__.py`: `python -m nanobot` entry
- `nanobot/cli/commands.py`: `nanobot` CLI script entry (defined in `pyproject.toml [project.scripts]`)
- `nanobot/nanobot.py`: Programmatic `Nanobot` facade

**Configuration:**
- `nanobot/config/schema.py`: All Pydantic config models; start here when adding new config fields
- `nanobot/config/loader.py`: `load_config()` and env var interpolation
- `nanobot/config/paths.py`: Canonical filesystem paths (`~/.nanobot/config.json`, workspace, etc.)

**Core Logic:**
- `nanobot/agent/loop.py`: `AgentLoop` — wire-up of all subsystems; message dispatch; session management
- `nanobot/agent/runner.py`: `AgentRunner` — pure iteration loop; context truncation; tool concurrency
- `nanobot/providers/base.py`: `LLMProvider` ABC + retry machinery
- `nanobot/providers/registry.py`: `PROVIDERS` tuple — add new provider specs here

**Testing:**
- `tests/`: All tests; run with `pytest` from repo root
- `tests/providers/`: Provider-specific tests including role alternation, retry logic
- `tests/agent/`: Agent loop and runner tests

## Naming Conventions

**Files:**
- Module files: `snake_case.py` (e.g., `openai_compat_provider.py`, `session_manager.py`)
- Skill directories: `kebab-case` or `snake_case` directory with `SKILL.md` inside (e.g., `skill-creator/SKILL.md`)
- Template files: `snake_case.md` under `nanobot/templates/`

**Directories:**
- Python packages: `snake_case` (e.g., `nanobot/channels/`, `nanobot/providers/`)
- Skill directories: mixed convention (e.g., `clawhub`, `skill-creator`, `tmux`)

**Classes:**
- PascalCase throughout (e.g., `AgentLoop`, `MessageBus`, `BaseChannel`, `ProviderSpec`)
- Abstract bases end in their role name: `LLMProvider`, `BaseChannel`, `AgentHook`, `Tool`

**Dataclasses / models:**
- Config Pydantic models: `*Config` suffix (e.g., `ChannelsConfig`, `ProviderConfig`, `WebToolsConfig`)
- Event dataclasses: descriptive nouns (e.g., `InboundMessage`, `OutboundMessage`, `LLMResponse`)

## Where to Add New Code

**New LLM provider:**
1. Add a `ProviderSpec` entry to `PROVIDERS` in `nanobot/providers/registry.py`
2. Add a `ProviderConfig` field to `ProvidersConfig` in `nanobot/config/schema.py`
3. If a new backend type is needed, create `nanobot/providers/{name}_provider.py` implementing `LLMProvider`
4. Wire instantiation in `nanobot/nanobot.py:_make_provider()` and `nanobot/cli/commands.py`

**New chat channel:**
1. Create `nanobot/channels/{name}.py` with a class inheriting `BaseChannel`
2. Implement `start()`, `stop()`, `send(msg: OutboundMessage)` methods
3. Add channel config fields to `ChannelsConfig` in `nanobot/config/schema.py` if needed
4. Auto-discovered via `pkgutil` scan — no registry change required

**New built-in tool:**
1. Create or add to a file in `nanobot/agent/tools/`; subclass `Tool` from `nanobot/agent/tools/base.py`
2. Register in `AgentLoop._register_default_tools()` in `nanobot/agent/loop.py`
3. Add tests under `tests/tools/`

**New slash command:**
1. Add handler function in `nanobot/command/builtin.py`
2. Register via `commands.exact(...)`, `commands.prefix(...)`, or `commands.priority(...)` in `register_builtin_commands()`

**New built-in skill:**
1. Create `nanobot/skills/{skill-name}/SKILL.md`
2. Optionally add a `skill.json` frontmatter for requirements/always-load flags
3. Auto-discovered by `SkillsLoader` at runtime

**New Jinja2 prompt template:**
- Add `.md` file under `nanobot/templates/agent/` or `nanobot/templates/memory/`
- Reference via `render_template("agent/filename.md", **kwargs)` from `nanobot/utils/prompt_templates.py`

**New config fields:**
- Add to the appropriate Pydantic model in `nanobot/config/schema.py`; camelCase / snake_case are both accepted (via `alias_generator=to_camel`)

**Tests:**
- Mirror the source path: code in `nanobot/providers/foo.py` → test in `tests/providers/test_foo.py`
- Use `pytest-asyncio` for async tests

## Special Directories

**`nanobot/skills/`:**
- Purpose: Bundled skill markdown files shipped with the package
- Generated: No
- Committed: Yes (included in hatch build via `nanobot/skills/**/*.md`)

**`nanobot/templates/`:**
- Purpose: Jinja2 prompt templates; treated as data files
- Generated: No
- Committed: Yes (included in hatch build via `nanobot/templates/**/*.md`)

**`bridge/`:**
- Purpose: Separate Node.js process for WhatsApp; has its own `package.json` and build
- Generated: No (source is committed; `node_modules/` and compiled output are not)
- Committed: Yes (TypeScript source; forced into wheel via `[tool.hatch.build.targets.wheel.force-include]`)

**`.planning/codebase/`:**
- Purpose: GSD architecture and analysis documents for AI-assisted development
- Generated: Yes (by GSD mapping agents)
- Committed: Configurable; `.planning/` is not in `.gitignore` by default

---

*Structure analysis: 2026-04-09*
