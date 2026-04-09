# Codebase Concerns

**Analysis Date:** 2026-04-09

## Known Bugs

**`truncate_text` name collision causes `TypeError` at runtime:**
- Symptoms: When `_sanitize_persisted_blocks` is called with `truncate_text=True` and a text block exceeds `max_tool_result_chars`, Python raises `TypeError: 'bool' object is not callable` because the parameter name `truncate_text: bool` shadows the module-level imported function `truncate_text` from `nanobot.utils.helpers`.
- Files: `nanobot/agent/loop.py` lines 592 and 621
- Trigger: Any persisted multimodal tool result (list-based content) that contains a text block exceeding the configured `max_tool_result_chars` limit. This path is hit in `_save_turn` via `self._sanitize_persisted_blocks(content, truncate_text=True)`.
- Workaround: None; the bug is latent and only fires in the specific code path, so it may be triggered rarely in practice. Fix by renaming the parameter to `do_truncate` or by aliasing the import.

**Dirty read in task cleanup done-callback:**
- Symptoms: The lambda passed to `task.add_done_callback` reads `_active_tasks[k]` twice without a lock — once in the guard condition and once in the `.remove()` call — creating a potential `ValueError` if another callback or coroutine modifies the list between checks.
- Files: `nanobot/agent/loop.py` line 396
- Trigger: High-concurrency scenarios where multiple tasks for the same session complete near-simultaneously.
- Workaround: Currently a theoretical race; the GIL reduces (but does not eliminate) the window. Fix with `try: self._active_tasks[k].remove(t) except ValueError: pass`.

## Tech Debt

**Oversized files exceeding the 800-line guideline:**
- Files: `nanobot/channels/feishu.py` (1680 lines), `nanobot/channels/weixin.py` (1380 lines), `nanobot/cli/commands.py` (1405 lines), `nanobot/channels/telegram.py` (1075 lines), `nanobot/channels/mochat.py` (947 lines), `nanobot/agent/tools/search.py` (555 lines)
- Impact: Hard to navigate and test; `commands.py` in particular mixes CLI wiring, provider construction, session management, and workspace migration logic in a single file.
- Fix approach: Extract `_make_provider`, `_migrate_cron_store`, and `_onboard_plugins` from `commands.py` into dedicated modules. Split each channel file into message-handling, formatting, and API-client layers.

**`logging.basicConfig` in production code path:**
- Files: `nanobot/cli/commands.py` line 647
- Impact: Calling `logging.basicConfig` in the `--verbose` flag handler reconfigures the stdlib `logging` root logger at runtime. The project uses `loguru` throughout, so this call is inconsistent, may produce duplicate log lines if any library initializes stdlib logging, and has no effect on loguru sinks.
- Fix approach: Replace with `logger.enable("")` or configure a `loguru` sink at DEBUG level via `logger.add(sys.stderr, level="DEBUG")`.

**`except Exception: pass` used to silence errors in critical paths:**
- Files: `nanobot/cli/commands.py` lines 20–21, 91–92, 113–114, 126–127; `nanobot/channels/mochat.py` lines 335–336, 465
- Impact: Errors in TTY setup, terminal restore, and MCP cleanup are silently discarded with no log entry. Makes debugging startup and shutdown failures impossible without a debugger.
- Fix approach: Replace bare `except Exception: pass` with at minimum `logger.debug(...)` to record what was suppressed. For TTY restore, use a dedicated guard with `logger.warning` so users can diagnose terminal corruption.

**Reverse-engineered third-party protocol (WeChat/WeXin channel):**
- Files: `nanobot/channels/weixin.py`
- Impact: The WeChat channel is built on a protocol described as "reverse-engineered from `@tencent-weixin/openclaw-weixin` v1.0.3" with no official API backing. Protocol changes upstream will silently break this channel with no clear migration path.
- Fix approach: Document the dependency on the specific version; add a version check or changelog monitor. Consider flagging the channel as "experimental" in user-facing docs.

**Feishu channel uses a `threading.Thread` to drive an async SDK:**
- Files: `nanobot/channels/feishu.py` lines 380–390
- Impact: The lark-oapi WebSocket client runs in a daemon thread with its own event loop, while the rest of nanobot is async. This creates a bridged concurrency model where the thread's loop and the main asyncio loop interact only via `asyncio.get_running_loop().run_in_executor`. Exceptions in the thread are caught and logged but do not propagate to the main loop's supervision.
- Fix approach: Replace with `asyncio.to_thread` wrapping or an asyncio-native lark client when one becomes available. Add structured error escalation so persistent WebSocket failures notify the main process.

**Session files lack write locking:**
- Files: `nanobot/session/manager.py` lines 186–203
- Impact: `SessionManager.save` writes session files with a plain `open(path, "w")` and no file lock. If the gateway receives concurrent messages for the same session key from different OS processes (e.g., running two gateway instances against the same workspace), writes will corrupt. Within a single process, per-session asyncio locks in `AgentLoop._session_locks` prevent this, but the file layer itself is not protected.
- Fix approach: Use `filelock.FileLock` (already a project dependency, used in `nanobot/cron/service.py`) around `SessionManager.save` and `_load`.

**Unbounded `_session_locks` dict grows forever:**
- Files: `nanobot/agent/loop.py` line 204; `nanobot/api/server.py` line 190
- Impact: The dicts `self._session_locks` and `app["session_locks"]` are never pruned. Long-running gateway processes accumulate one `asyncio.Lock` per unique `(channel, chat_id)` pair seen. At scale with many unique users this is a minor memory leak.
- Fix approach: Use a `weakref.WeakValueDictionary` or an LRU-bounded dict with a cleanup sweep on session deletion.

**`_active_tasks` list per session not cleaned up on session clear:**
- Files: `nanobot/agent/loop.py` lines 202, 394–396
- Impact: The done-callback removes tasks from the list, but the key itself stays in `_active_tasks` forever with an empty list. Minor memory leak with many unique sessions.
- Fix approach: In the done-callback, remove the key when the list becomes empty.

## Security Considerations

**SSRF protection missing from SearXNG base URL:**
- Risk: `_search_searxng` validates the final endpoint URL for scheme/domain via `_validate_url` (which does NOT check resolved IPs), while `_validate_url_safe` (which does the full SSRF check) is used only by `WebFetchTool`. An attacker who controls the SearXNG base URL in config could point it at an internal address.
- Files: `nanobot/agent/tools/web.py` lines 166–168
- Current mitigation: None specifically for the SearXNG URL.
- Recommendations: Replace the `_validate_url` call with `_validate_url_safe` for `endpoint`, or at minimum resolve the hostname before construction.

**DNS rebinding window in `validate_url_target`:**
- Risk: `validate_url_target` in `nanobot/security/network.py` resolves the hostname at validation time, but HTTP clients re-resolve on connection. Between validation and the actual request, a DNS rebinding attack can swap the IP to a private address. Both `WebFetchTool` and the shell guard call this function.
- Files: `nanobot/security/network.py` lines 46–78; `nanobot/agent/tools/web.py` lines 56–59; `nanobot/agent/tools/shell.py` lines 248–250
- Current mitigation: `validate_resolved_url` is called post-redirect in `WebFetchTool`, which catches the common redirect case. The shell URL scanner only runs pre-execution.
- Recommendations: For `WebFetchTool`, pass a resolved IP directly to the HTTP client instead of a hostname, or use a custom transport that re-validates each connection.

**Shell command deny-list is regex-based and incomplete:**
- Risk: The `deny_patterns` list in `ExecTool` uses case-lowered regex matching. It can be bypassed via shell escaping, environment variable expansion, command substitution (`$(rm -rf .)`) or aliases. The `allow_patterns` list is empty by default, so `restrict_to_workspace=False` relies entirely on the deny list.
- Files: `nanobot/agent/tools/shell.py` lines 53–63
- Current mitigation: Optional sandbox via `bwrap` (`nanobot/agent/tools/sandbox.py`), workspace path restriction when `restrict_to_workspace=True`.
- Recommendations: Enforce `bwrap` sandbox by default in server/gateway mode; document clearly that the deny-list is best-effort, not a security boundary.

**Subprocess env isolation only applies to Unix:**
- Risk: On Windows, `_build_env` passes the full `PATH` to subprocesses. On Unix it passes only `HOME`, `LANG`, and `TERM`, relying on `bash -l` to source a login profile. The login profile may set sensitive env vars (e.g., `OPENAI_API_KEY` exported in `.bashrc`).
- Files: `nanobot/agent/tools/shell.py` lines 199–233
- Current mitigation: On Unix, only three variables are passed; API keys must be in the profile to leak.
- Recommendations: Document the risk of exporting API keys in shell profiles when using `exec` tool. Consider stripping known secret env-var prefixes (`*_API_KEY`, `*_SECRET`, `*_TOKEN`) from the login-profile-inherited environment.

## Performance Bottlenecks

**Synchronous `socket.getaddrinfo` call in SSRF guard:**
- Problem: `validate_url_target` calls the blocking `socket.getaddrinfo` synchronously from within the async event loop (`nanobot/security/network.py` line 66). Every web fetch and every shell command containing a URL blocks the loop during DNS resolution.
- Files: `nanobot/security/network.py` line 66; called from `nanobot/agent/tools/web.py` and `nanobot/agent/tools/shell.py`
- Cause: `socket.getaddrinfo` is a stdlib blocking call with no async variant.
- Improvement path: Wrap in `asyncio.get_event_loop().run_in_executor(None, socket.getaddrinfo, ...)`, or use `aiodns` for non-blocking resolution.

**Token estimation uses `tiktoken` on every turn:**
- Problem: `estimate_prompt_tokens` is called in `_snip_history` (on every agent iteration) and in `Consolidator.maybe_consolidate_by_tokens`. Both create a new `tiktoken` encoding object per invocation via `tiktoken.get_encoding("cl100k_base")`, which is not free despite internal caching.
- Files: `nanobot/utils/helpers.py` lines 295, 330; `nanobot/agent/runner.py` via `estimate_prompt_tokens_chain`
- Cause: The encoding object is instantiated inline rather than cached at module level.
- Improvement path: Cache the encoding as a module-level singleton: `_enc = tiktoken.get_encoding("cl100k_base")`.

**`maybe_persist_tool_result` runs `_cleanup_tool_result_buckets` on every oversized result:**
- Problem: Each call to `maybe_persist_tool_result` that exceeds `max_chars` triggers a directory scan of all sibling buckets under `.nanobot/tool-results/`. For long-running sessions with many tool calls this is repeated I/O.
- Files: `nanobot/utils/helpers.py` lines 214–217
- Cause: Cleanup is done eagerly instead of periodically.
- Improvement path: Rate-limit cleanup to at most once per minute per session, or run it in a background task.

## Fragile Areas

**`_snip_history` discards history without warning:**
- Files: `nanobot/agent/runner.py` lines 640–697
- Why fragile: When the context window is exceeded, `_snip_history` silently drops old messages from the front. If the resulting sliced history starts mid-turn (orphan tool results), `find_legal_message_start` advances the start pointer further, potentially discarding more than intended. The caller receives no indication of how much was dropped.
- Safe modification: When changing context window handling, always run through the full suite in `tests/agent/test_consolidate_offset.py`. Add a log statement that reports the number of messages dropped.
- Test coverage: `tests/agent/test_consolidate_offset.py` (619 lines) covers the consolidation path but not the snip-history fast path.

**`_restore_runtime_checkpoint` overlap detection uses key comparison:**
- Files: `nanobot/agent/loop.py` lines 683–732
- Why fragile: The overlap detection algorithm compares messages by a tuple of 7 fields. Any message that legitimately contains `None` in fields like `tool_call_id` or `reasoning_content` will compare correctly, but mutations to message dicts after checkpointing (e.g., adding a `timestamp`) can cause the comparison to miss the overlap, resulting in duplicate messages in session history.
- Safe modification: Do not mutate checkpoint messages before comparison. Use a stable hash or unique tool-call IDs for overlap detection.
- Test coverage: No dedicated tests for `_restore_runtime_checkpoint` found.

**Feishu channel WebSocket runs in a daemon thread with no health monitoring:**
- Files: `nanobot/channels/feishu.py` lines 380–390
- Why fragile: If the daemon thread crashes, `self._running` remains `True`, the main async loop spins on `asyncio.sleep(1)`, and no error is propagated. There is no watchdog or restart mechanism.
- Safe modification: Set a thread-local exception flag and check it in the main `while self._running` loop. Raise or log a fatal error if the WebSocket thread is no longer alive.

## Test Coverage Gaps

**`_restore_runtime_checkpoint` logic is untested:**
- What's not tested: The full flow of saving a checkpoint mid-turn, crashing, and restoring the correct partial conversation state on next startup.
- Files: `nanobot/agent/loop.py` lines 683–732
- Risk: Silent session corruption after an interrupted request (e.g., SIGKILL during tool execution). The bug would only appear in production with poor repro conditions.
- Priority: High

**Shell command `_guard_command` deny-list bypass paths are untested:**
- What's not tested: Command substitution patterns (`$(...)`, backticks), multi-step pipelines that embed a blocked pattern after a semicolon in a way the lowercase check misses, env-var indirection.
- Files: `nanobot/agent/tools/shell.py` lines 235–274
- Risk: A model-generated command could evade the safety guard.
- Priority: High

**Session file write-corruption under concurrent access:**
- What's not tested: Two concurrent writes to the same session file from different coroutines or processes. The in-process asyncio lock prevents in-process races, but cross-process or lock-bypass cases are not tested.
- Files: `nanobot/session/manager.py` lines 186–203
- Risk: Silent session file truncation/corruption in multi-process deployments.
- Priority: Medium

**`WebFetchTool` post-redirect SSRF validation:**
- What's not tested: A redirect chain that terminates at a private IP. `validate_resolved_url` is called after the redirect but before body consumption; test coverage for this path is minimal.
- Files: `nanobot/agent/tools/web.py` lines 270–274
- Risk: SSRF via 301/302 redirect to internal service.
- Priority: High

---

*Concerns audit: 2026-04-09*
