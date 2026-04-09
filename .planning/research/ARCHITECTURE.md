# Architecture Patterns

**Domain:** CLI-based LLM provider integration (Claude Code CLI proxy for async Python agent framework)
**Researched:** 2026-04-09

## The Central Architecture Decision

There are two fundamentally different ways to integrate Claude Code CLI as a nanobot provider. The choice determines the entire system's data flow, component boundaries, and feature surface.

### Option A: Completion Proxy (nanobot controls tools)

Claude Code CLI runs with `--tools ""` -- all its built-in tools disabled. It acts as a pure LLM completion backend. Nanobot's `AgentRunner` drives the tool-use loop: it sends messages, receives text+tool_call responses, executes tools via `ToolRegistry`, and iterates.

**Pros:**
- Nanobot's full feature set works: custom tools (MCP, MessageTool, SpawnTool), AgentHook callbacks, checkpoint system, progress tracking, subagent spawning
- Consistent behavior with all other providers -- the provider is a drop-in replacement
- Tool execution permissions, security, and SSRF protection controlled by nanobot
- Session management stays in nanobot's SessionManager

**Cons:**
- Must solve message serialization: nanobot's OpenAI-format message list must be converted into a CLI-compatible prompt string each turn
- Each AgentRunner iteration spawns a new CLI subprocess (1-3s overhead per turn with `--bare`)
- Claude Code's own tools (which are well-integrated with its context window) are unused
- Tool call format may not survive the round-trip (nanobot's tools use different schemas than Claude Code's)

**Feasibility risk: MEDIUM** -- The `--tools ""` flag is documented. However, disabling tools may cause the model to respond differently (no tool definitions in context means no tool calls in response). The model must still produce tool_call responses for nanobot's tools even though Claude Code's tools are disabled. This requires passing nanobot's tool definitions via the prompt or system prompt, which is non-standard.

**CRITICAL CONCERN:** When Claude Code runs with `--tools ""`, the model has no tool definitions in its context. It will produce plain text responses, NOT tool_call structured objects. Nanobot's `AgentRunner` expects `LLMResponse.tool_calls` to contain `ToolCallRequest` objects. Without tool definitions, the model cannot produce these. This means Option A requires injecting nanobot's tool definitions into the system prompt and then parsing natural-language "tool calls" from the response text -- which is fragile and defeats the purpose of structured tool use.

### Option B: Agent Proxy (Claude Code controls tools)

Claude Code CLI runs with tools enabled (its default). It acts as a complete agent: the CLI's internal agent loop reads files, writes files, runs bash commands, etc. Nanobot sends a prompt and receives a final result. `LLMResponse.tool_calls` is always empty.

**Pros:**
- Simplest integration: prompt in, final result out
- Claude Code's tools are purpose-built for its context and model
- Session continuity via `--resume` preserves full agent context across turns
- The `claude_agent_sdk` Python package handles all subprocess management, streaming, and session tracking
- No message serialization problem -- the SDK accepts prompts and returns structured messages

**Cons:**
- Nanobot's `ToolRegistry` is bypassed entirely -- no custom tools (MCP, MessageTool, SpawnTool)
- Nanobot's `AgentHook` system does not fire for tool execution (no before_execute_tools, no progress callbacks)
- Two session stores: nanobot's SessionManager for channel routing + Claude Code's JSONL for agent context
- Tool execution happens inside the CLI subprocess -- nanobot cannot intercept, modify, or cancel individual tool calls
- Nanobot's security controls (SSRF protection, tool permission checks) do not apply to Claude Code's tool execution
- `AgentRunner.run()` loop executes only one iteration (since `LLMResponse.tool_calls` is always empty)

### Recommendation: Option B for MVP, Option A as future investigation

**Option B is the correct starting point** because:

1. It actually works. Option A's critical concern (no tool definitions = no tool calls) makes it non-viable without significant prompt engineering that undermines reliability.
2. The project's stated goal is "subscription users can keep using nanobot's full feature set by transparently proxying through Claude Code CLI." The key value is multi-channel delivery and session management, not nanobot-specific tool execution.
3. The `claude_agent_sdk` Python package provides production-quality subprocess management. Building this from scratch adds risk for no benefit.
4. Claude Code's built-in tools (Read, Edit, Bash, Glob, Grep) cover the same capabilities as nanobot's tools, executed within Claude Code's optimized context.

**Option A may become viable if:** Anthropic adds a mode where Claude Code passes tool schemas through to the model without executing them locally. This would allow nanobot to inject its own tool definitions and receive structured tool_call responses. As of April 2026, this mode does not exist.

## Recommended Architecture (Option B: Agent Proxy)

### Component Diagram

```
User Message
    |
    v
[Channel Layer] (Telegram/Discord/Slack/CLI/etc.)
    |
    v
[MessageBus] (inbound queue)
    |
    v
[AgentLoop._process_message()]
    |
    v
[ContextBuilder.build_messages()] --> system prompt + history + user message
    |
    v
[AgentRunner.run()]
    |
    +-- calls provider.chat_stream_with_retry()
    |       |
    |       v
    |   [ClaudeCodeProvider]  <-- NEW COMPONENT
    |       |
    |       +-- Extracts latest user message + system prompt from messages list
    |       +-- Calls claude_agent_sdk.query() or ClaudeSDKClient.query()
    |       +-- SDK spawns CLI subprocess internally
    |       +-- CLI runs full agent loop (reads files, executes bash, edits code)
    |       +-- SDK streams AssistantMessage, StreamEvent, ResultMessage back
    |       +-- Provider maps to LLMResponse(content=final_result, tool_calls=[])
    |       |
    |       v
    |   [LLMResponse] (content only, no tool_calls)
    |
    +-- tool_calls is empty -> AgentRunner loop exits after 1 iteration
            |
            v
        [OutboundMessage] --> MessageBus --> Channel
```

### Component Boundaries

| Component | Responsibility | Communicates With |
|-----------|---------------|-------------------|
| `ClaudeCodeProvider` | `LLMProvider` subclass. Translates nanobot messages into SDK `query()` calls. Collects streaming text and maps `ResultMessage` to `LLMResponse`. | `AgentRunner` (called by), `claude_agent_sdk` (calls query/ClaudeSDKClient) |
| `claude_agent_sdk` | Official Anthropic Python package. Manages CLI subprocess lifecycle, stdin/stdout JSON-lines transport, message parsing. | `ClaudeCodeProvider` (called by), `claude` CLI binary (spawns as subprocess) |
| `claude` CLI subprocess | Node.js process running Claude Code. Handles API calls, tool execution, session persistence. | `claude_agent_sdk` (managed by), Anthropic API (calls) |
| `ProviderSpec` entry | Registry metadata: `name="claude_code"`, `backend="claude_code"`, `is_direct=True` | `Config._match_provider()` (matched by), CLI commands (selects provider) |
| `ProviderConfig` field | Config schema for provider settings: `cli_path`, `session_mode`, `persona_passthrough`, `output_verbosity` | `Config.get_provider()` (provides), `ClaudeCodeProvider.__init__()` (consumes) |

### Data Flow: Detailed

**Turn lifecycle (channel message to response):**

```
1. Channel receives user message -> bus.publish_inbound(InboundMessage)
2. AgentLoop.run() dequeues from bus.inbound
3. _process_message() resolves Session, calls ContextBuilder.build_messages()
   -> Produces: [system_msg, ...history..., user_msg]
4. AgentRunner.run() calls provider.chat_stream_with_retry()
5. ClaudeCodeProvider.chat_stream() executes:
   a. Extracts system_prompt from messages[0] if role=="system"
   b. Extracts latest user content from messages[-1]
   c. Looks up session_id from self._session_map[session_key]
   d. Builds ClaudeAgentOptions:
      - system_prompt or append_system_prompt (for persona)
      - allowed_tools=["Read", "Edit", "Bash", "Glob", "Grep"]
      - permission_mode="acceptEdits" or "bypassPermissions"
      - resume=session_id (if continuing)
      - include_partial_messages=True (for streaming)
      - model=self._resolve_model(model)
      - setting_sources=[] (bare mode equivalent)
   e. Calls: async for msg in query(prompt=user_content, options=options)
   f. For each StreamEvent with text_delta: calls on_content_delta(text)
   g. For each AssistantMessage: accumulates text blocks
   h. For ResultMessage: captures session_id, usage, cost
6. Returns LLMResponse(
       content=accumulated_text,
       tool_calls=[],  # Always empty in agent proxy mode
       finish_reason="stop" or "error",
       usage={prompt_tokens: ..., completion_tokens: ...},
   )
7. AgentRunner sees no tool_calls -> loop exits
8. AgentLoop._save_turn() persists to nanobot session
9. _process_message() returns OutboundMessage -> bus -> channel
```

**Session continuity flow:**

```
First turn for a nanobot session:
  1. query(prompt=..., options=ClaudeAgentOptions(resume=None))
  2. SDK creates new Claude Code session
  3. ResultMessage.session_id = "abc-123-..."
  4. Provider stores: self._session_map["telegram:12345"] = "abc-123-..."

Subsequent turns for same nanobot session:
  1. query(prompt=..., options=ClaudeAgentOptions(resume="abc-123-..."))
  2. SDK resumes existing Claude Code session (full prior context available)
  3. ResultMessage.session_id = "abc-123-..." (same ID)
  4. Agent has full context from prior turns without re-sending history
```

**Error flow:**

```
CLI not installed:
  -> ClaudeCodeProvider.__init__() checks shutil.which("claude")
  -> Raises descriptive error with install instructions

CLI not authenticated:
  -> ResultMessage with is_error=True, subtype containing auth error
  -> LLMResponse(finish_reason="error", content="Please run 'claude auth login'")

Rate limit:
  -> RateLimitEvent from SDK with status="rejected", resets_at=timestamp
  -> LLMResponse(finish_reason="error", error_should_retry=True, error_retry_after_s=...)
  -> Base class _run_with_retry handles backoff

SDK import failure (not installed):
  -> ImportError caught at provider instantiation
  -> Clear message: "Install bypass support: pip install nanobot[bypass]"

Process crash:
  -> SDK raises exception (transport error)
  -> Caught in _safe_chat_stream -> LLMResponse(finish_reason="error")
```

## Patterns to Follow

### Pattern 1: Agent Proxy Provider
**What:** The provider sends prompts to Claude Code and receives final results. Tool execution happens inside the CLI, not in nanobot.
**When:** For the bypass/proxy mode.
**Why:** Claude Code with tools enabled is a complete agent. Trying to disable its tools and re-implement them in nanobot is more complex and less reliable than letting Claude Code do what it does well.
**Example:**
```python
class ClaudeCodeProvider(LLMProvider):
    async def chat_stream(self, messages, tools, model, on_content_delta, **kw):
        from claude_agent_sdk import query, ClaudeAgentOptions, AssistantMessage, ResultMessage, TextBlock
        from claude_agent_sdk.types import StreamEvent

        prompt = self._extract_latest_user_content(messages)
        system = self._extract_system_prompt(messages)

        options = ClaudeAgentOptions(
            allowed_tools=["Read", "Edit", "Bash", "Glob", "Grep"],
            permission_mode="bypassPermissions",
            resume=self._get_session_id(session_key),
            include_partial_messages=True,
            model=self._resolve_model(model),
        )
        if system and self._persona_passthrough:
            options.system_prompt = system

        content_parts = []
        session_id = None
        usage = {}

        async for msg in query(prompt=prompt, options=options):
            if isinstance(msg, StreamEvent):
                event = msg.event
                if event.get("type") == "content_block_delta":
                    delta = event.get("delta", {})
                    if delta.get("type") == "text_delta" and on_content_delta:
                        await on_content_delta(delta["text"])
            elif isinstance(msg, AssistantMessage):
                for block in msg.content:
                    if isinstance(block, TextBlock):
                        content_parts.append(block.text)
            elif isinstance(msg, ResultMessage):
                session_id = msg.session_id
                usage = msg.usage or {}

        if session_id:
            self._store_session_id(session_key, session_id)

        return LLMResponse(
            content="".join(content_parts) or None,
            tool_calls=[],
            finish_reason="stop",
            usage=usage,
        )
```

### Pattern 2: Optional Dependency with Fallback
**What:** Import `claude_agent_sdk` lazily. If not installed, fall back to raw `asyncio.create_subprocess_exec`.
**When:** At provider instantiation and each `chat()` call.
**Why:** The SDK is an optional dependency (`nanobot[bypass]`). Users who haven't installed it should get a clear error. The raw subprocess fallback ensures the feature works even if the SDK has compatibility issues.
**Example:**
```python
class ClaudeCodeProvider(LLMProvider):
    def __init__(self, cli_path=None, **kw):
        super().__init__(**kw)
        self._cli_path = cli_path or shutil.which("claude")
        if not self._cli_path:
            raise RuntimeError(
                "Claude Code CLI not found. Install: npm install -g @anthropic-ai/claude-code"
            )
        try:
            from claude_agent_sdk import query
            self._use_sdk = True
        except ImportError:
            logger.warning("claude-agent-sdk not installed; using raw subprocess fallback")
            self._use_sdk = False

    async def chat_stream(self, messages, **kw):
        if self._use_sdk:
            return await self._chat_via_sdk(messages, **kw)
        return await self._chat_via_subprocess(messages, **kw)
```

### Pattern 3: Backend Registration
**What:** Register as a new `ProviderSpec` with `backend="claude_code"` and add the instantiation branch.
**When:** Adding the provider to nanobot's system.
**Why:** The registry pattern means adding a provider requires exactly 3 touchpoints: (1) `ProviderSpec` entry, (2) config schema field, (3) backend switch. Everything else (status display, auto-detection, config validation) derives automatically.
**Example:**
```python
# registry.py
ProviderSpec(
    name="claude_code",
    keywords=("claude-code", "bypass"),
    env_key="",
    display_name="Claude Code CLI",
    backend="claude_code",
    is_direct=True,
)

# commands.py
elif backend == "claude_code":
    from nanobot.providers.claude_code_provider import ClaudeCodeProvider
    provider = ClaudeCodeProvider(
        cli_path=getattr(config.providers, "claude_code", None) and config.providers.claude_code.cli_path,
        default_model=model,
    )
```

### Pattern 4: Session ID Mapping
**What:** Maintain a dictionary mapping nanobot session keys to Claude Code session UUIDs.
**When:** When session continuity is enabled.
**Why:** Nanobot keys sessions by `"{channel}:{chat_id}"`. Claude Code uses UUIDs. The provider bridges these two namespaces.
**Note:** The current `LLMProvider.chat_stream()` signature does not include a `session_key` parameter. This will need to be threaded through from `AgentRunner` or stored as provider instance state set by `AgentLoop` before each call.

## Anti-Patterns to Avoid

### Anti-Pattern 1: Completion Proxy with Empty Tool List
**What:** Running `claude -p --tools ""` and expecting the model to produce structured tool_call responses for nanobot's tools.
**Why bad:** With no tool definitions in context, the model produces plain text, not structured tool calls. Nanobot's `AgentRunner` receives `LLMResponse(tool_calls=[])` every time and never enters its tool loop.
**Instead:** Accept that Claude Code handles tools internally. The provider returns final results, not intermediate tool calls.

### Anti-Pattern 2: Synchronous Subprocess Calls
**What:** Using `subprocess.run()` or blocking `Popen.communicate()`.
**Why bad:** Blocks the entire asyncio event loop. All other sessions freeze.
**Instead:** Use `claude_agent_sdk` (which uses anyio internally) or `asyncio.create_subprocess_exec` for the fallback path.

### Anti-Pattern 3: Dual Session Stores as Source of Truth
**What:** Treating both nanobot's SessionManager AND Claude Code's JSONL sessions as the conversation history.
**Why bad:** They will diverge. Nanobot's session stores the messages as it sees them (prompt + final result). Claude Code's session stores the full agent trace (prompt + tool calls + tool results + intermediate responses + final result). Syncing them is a maintenance nightmare.
**Instead:** Nanobot's SessionManager is the source of truth for channel routing and history display. Claude Code's session is an internal detail used only via `--resume` for context continuity. They serve different purposes and should not be reconciled.

### Anti-Pattern 4: Passing Full Message History as Prompt
**What:** Serializing all nanobot messages into the `-p` prompt string.
**Why bad:** Prompt length limits, startup delay, redundancy with `--resume` context.
**Instead:** Pass only the latest user message. Use `--resume` for history. For first turns, include minimal recent context if needed.

## Scalability Considerations

| Concern | Single User | 10 Concurrent Sessions | 100+ Sessions |
|---------|------------|----------------------|--------------|
| Process overhead | One CLI subprocess per turn (managed by SDK) | 10 concurrent subprocesses; SDK handles lifecycle | Bound via asyncio.Semaphore (reuse nanobot's existing pattern; max 3-5) |
| Session storage | Claude Code JSONL files auto-managed | Accumulates; use --no-session-persistence for stateless if needed | Consider periodic cleanup; session files grow with tool traces |
| Startup latency | 1-3s per turn with bare mode | Parallel starts fine; no shared state between processes | ClaudeSDKClient (persistent subprocess) reduces per-turn overhead |
| Memory | SDK subprocess: ~50-100MB while running | Bounded by semaphore | Queue excess requests; don't spawn unbounded |
| Auth/Rate limits | User's subscription caps | Same caps shared across all sessions | Surface RateLimitEvent from SDK; respect resets_at |

## Build Order

Based on dependencies between components:

### Phase 1: Core Provider (MVP)
1. **ProviderSpec + Config** -- Add `claude_code` to registry and config schema. This is pure metadata; no behavior yet.
2. **ClaudeCodeProvider class** -- `LLMProvider` subclass implementing `chat()`, `chat_stream()`, `get_default_model()`. Uses `claude_agent_sdk.query()` for the happy path. Includes raw subprocess fallback.
3. **Backend switch** -- Add `elif backend == "claude_code":` to `commands.py` provider instantiation.
4. **CLI availability check** -- Validate `claude` binary exists and is authenticated at provider init.

*After Phase 1:* One-shot mode works end-to-end. User selects the provider, sends a message, Claude Code agent runs, final result flows back through all channels.

### Phase 2: Streaming and Session Continuity
5. **Content streaming** -- Enable `include_partial_messages=True`. Wire `StreamEvent` text_delta to `on_content_delta` callback.
6. **Session ID mapping** -- Store `ResultMessage.session_id` per nanobot session key. Pass `resume` on subsequent calls.
7. **Session mode config** -- Config field: `session_mode: "oneshot" | "persistent"`. Oneshot uses `--no-session-persistence`.

*After Phase 2:* Text streams in real-time. Multi-turn conversations maintain context. Full UX parity.

### Phase 3: Robustness and Error Handling
8. **Error mapping** -- Parse `ResultMessage.is_error`, `RateLimitEvent`, auth failures. Map to `LLMResponse` error fields for base class retry.
9. **Process lifecycle** -- Handle cancellation (kill subprocess), timeouts, stderr capture.
10. **Usage/cost tracking** -- Extract `ResultMessage.total_cost_usd` and token counts into `LLMResponse.usage`.

*After Phase 3:* Production-ready error handling. Retry on transient failures. Cost visibility.

### Phase 4: UX and Polish
11. **Persona passthrough** -- Config toggle: pass nanobot's system prompt to Claude Code via `--append-system-prompt` or run raw.
12. **Output verbosity** -- Config enum controlling what gets surfaced: all tool traces, final only, or abbreviated.
13. **--bypass CLI flag** -- Typer option as shortcut for provider selection.
14. **Menu integration** -- Add to provider picker in `nanobot config` onboarding.

### Phase 5: Advanced (Optional)
15. **ClaudeSDKClient mode** -- Persistent subprocess via `ClaudeSDKClient` for interactive sessions. Reduces per-turn latency.
16. **Bash wrapper script** -- Optional intermediary for users who want to customize CLI invocation.
17. **Interrupt support** -- Map nanobot's `/stop` to `ClaudeSDKClient.interrupt()`.

## Sources

- [Claude Code CLI Reference](https://code.claude.com/docs/en/cli-reference) -- All CLI flags and options including --tools, --bare, --output-format (HIGH confidence)
- [Run Claude Code Programmatically](https://code.claude.com/docs/en/headless) -- Headless mode, --bare flag, output formats (HIGH confidence)
- [Agent SDK Sessions](https://code.claude.com/docs/en/agent-sdk/sessions) -- Session IDs, resume, fork, continue, persistence (HIGH confidence)
- [Stream Responses in Real-time](https://code.claude.com/docs/en/agent-sdk/streaming-output) -- StreamEvent types, text_delta, tool streaming (HIGH confidence)
- [Python Agent SDK Reference](https://code.claude.com/docs/en/agent-sdk/python) -- query(), ClaudeSDKClient, ClaudeAgentOptions, message types (HIGH confidence)
- Nanobot codebase: `nanobot/providers/base.py` -- LLMProvider ABC with chat(), chat_stream(), retry logic (HIGH confidence)
- Nanobot codebase: `nanobot/providers/registry.py` -- ProviderSpec pattern, PROVIDERS tuple, find_by_name() (HIGH confidence)
- Nanobot codebase: `nanobot/agent/runner.py` -- AgentRunner.run() loop, tool execution, LLMResponse handling (HIGH confidence)
- Nanobot codebase: `nanobot/cli/commands.py` -- Provider instantiation switch, backend selection (HIGH confidence)
- Nanobot codebase: `nanobot/providers/anthropic_provider.py` -- Reference implementation of a concrete LLMProvider (HIGH confidence)

---

*Architecture analysis: 2026-04-09*
