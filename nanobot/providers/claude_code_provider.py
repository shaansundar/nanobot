"""Claude Code CLI bypass provider."""

from __future__ import annotations

import asyncio
import json
import os
import signal
import shutil
from typing import Any

from loguru import logger

from nanobot.providers.base import LLMProvider, LLMResponse

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DEFAULT_MODEL = "claude_code/claude-sonnet-4-20250514"

_CLI_NOT_FOUND_MESSAGE = """\
Claude Code CLI not found. Install it with:
  npm install -g @anthropic-ai/claude-code

Then authenticate:
  claude
  # Follow the login prompts"""


# ---------------------------------------------------------------------------
# Provider
# ---------------------------------------------------------------------------


class ClaudeCodeProvider(LLMProvider):
    """Route prompts through the official Claude Code CLI subprocess.

    This provider implements the Agent Proxy architecture: prompts are sent
    to the ``claude`` CLI binary with ``-p --output-format json``, and the
    resulting JSON envelope is parsed into an ``LLMResponse``.

    The ``--setting-sources ""`` flag is used instead of ``--bare`` to reduce
    per-turn overhead while preserving subscription OAuth keychain auth
    (``--bare`` was proven to break Max/Pro subscription logins).
    """

    def __init__(
        self,
        cli_path: str | None = None,
        default_model: str = _DEFAULT_MODEL,
        max_concurrent: int = 5,
        env_isolation: bool = False,
        timeout: int = 300,
    ) -> None:
        super().__init__(api_key=None, api_base=None)

        self._cli_path: str = cli_path or shutil.which("claude") or ""
        if not self._cli_path:
            raise RuntimeError(_CLI_NOT_FOUND_MESSAGE)

        self._default_model: str = default_model

        # Robustness: concurrency limiting (ROBU-02)
        self._subprocess_semaphore: asyncio.Semaphore = asyncio.Semaphore(max_concurrent)

        # Robustness: environment isolation (ROBU-03)
        self._env_isolation: bool = env_isolation

        # Robustness: subprocess timeout (ROBU-01)
        self._timeout: int = timeout

        # Session management state (per D-04)
        self._session_map: dict[str, str] = {}  # nanobot session key -> claude session UUID
        self._current_session_key: str | None = None
        self._current_session_mode: str = "session"

    # -- Session context ----------------------------------------------------

    def set_session_context(self, session_key: str, session_mode: str = "session") -> None:
        """Set session context before a chat() call.

        Called by AgentLoop to thread the nanobot session key and mode
        into the provider before each chat() invocation.
        """
        self._current_session_key = session_key
        self._current_session_mode = session_mode

    def clear_session(self, session_key: str) -> None:
        """Remove session mapping for a conversation (per D-12: /clear support)."""
        self._session_map.pop(session_key, None)

    # -- Command building ---------------------------------------------------

    def _build_command(
        self,
        prompt: str,
        session_id: str | None = None,
        no_session_persistence: bool = False,
    ) -> list[str]:
        """Build the CLI argument list for a prompt invocation.

        Flags:
        * ``-p``                         -- print-mode (non-interactive)
        * ``--output-format json``       -- structured JSON envelope
        * ``--setting-sources ""``       -- skip user/project settings to reduce
          overhead (~50K -> ~5K tokens) while preserving keychain OAuth
        * ``--resume <id>``              -- resume an existing session (D-01)
        * ``--no-session-persistence``   -- disable session persistence (D-03)
        """
        cmd = [
            self._cli_path,
            "-p",
            "--output-format",
            "json",
            "--setting-sources",
            "",
        ]
        if session_id:
            cmd.extend(["--resume", session_id])
        if no_session_persistence:
            cmd.append("--no-session-persistence")
        cmd.append(prompt)
        return cmd

    # -- Environment isolation (ROBU-03) ------------------------------------

    @staticmethod
    def _build_isolated_env() -> dict[str, str]:
        """Build a minimal environment for subprocess execution.

        Only essential variables are forwarded.  API keys, tokens, and other
        secrets are excluded to prevent leakage in gateway mode.
        """
        return {
            "HOME": os.environ.get("HOME", "/tmp"),
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "LANG": os.environ.get("LANG", "C.UTF-8"),
            "TERM": os.environ.get("TERM", "dumb"),
            "USER": os.environ.get("USER", ""),
            "SHELL": os.environ.get("SHELL", "/bin/sh"),
        }

    # -- Process group management (ROBU-01) --------------------------------

    @staticmethod
    async def _kill_process_group(proc: asyncio.subprocess.Process) -> None:
        """Send SIGTERM to the process group, then SIGKILL after a grace period.

        Catches ``ProcessLookupError`` and ``PermissionError`` for cases where
        the process has already exited or the user lacks permissions.
        """
        try:
            pgid = os.getpgid(proc.pid)
            os.killpg(pgid, signal.SIGTERM)
            logger.debug("Sent SIGTERM to process group pgid={}", pgid)
        except (ProcessLookupError, PermissionError):
            return

        try:
            await asyncio.wait_for(proc.wait(), timeout=5.0)
            return  # Process exited after SIGTERM
        except asyncio.TimeoutError:
            pass  # Escalate to SIGKILL

        try:
            pgid = os.getpgid(proc.pid)
            os.killpg(pgid, signal.SIGKILL)
            logger.debug("Sent SIGKILL to process group pgid={}", pgid)
        except (ProcessLookupError, PermissionError):
            return

        try:
            await asyncio.wait_for(proc.wait(), timeout=2.0)
        except asyncio.TimeoutError:
            logger.warning("Could not reap process pid={} after SIGKILL", proc.pid)

    # -- Chat ---------------------------------------------------------------

    async def _run_cli(self, cmd: list[str]) -> LLMResponse:
        """Execute a CLI command and parse the result.

        Hardened with:
        * ``start_new_session=True`` -- all children in a process group (ROBU-01)
        * Timeout via ``asyncio.wait_for`` (ROBU-01)
        * SIGTERM/SIGKILL escalation on timeout (ROBU-01)
        * Zombie prevention via ``proc.wait()`` in finally (ROBU-01)
        * Semaphore-based concurrency limiting (ROBU-02)
        * Conditional environment isolation (ROBU-03)
        """
        async with self._subprocess_semaphore:  # ROBU-02
            env = self._build_isolated_env() if self._env_isolation else None  # ROBU-03
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                start_new_session=True,  # ROBU-01
                env=env,
            )
            logger.debug("Claude Code subprocess started, pid={}", proc.pid)
            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    proc.communicate(), timeout=self._timeout,  # ROBU-01
                )
            except asyncio.TimeoutError:
                await self._kill_process_group(proc)  # ROBU-01
                return LLMResponse(
                    content=f"Claude Code CLI timed out after {self._timeout}s",
                    tool_calls=[],
                    finish_reason="error",
                )
            except asyncio.CancelledError:
                await self._kill_process_group(proc)  # ROBU-01
                raise
            finally:
                if proc.returncode is None:  # ROBU-01: reap zombie
                    try:
                        await asyncio.wait_for(proc.wait(), timeout=2.0)
                    except asyncio.TimeoutError:
                        logger.warning("Could not reap subprocess pid={}", proc.pid)
            return self._parse_result(stdout_bytes, stderr_bytes, proc.returncode)

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        reasoning_effort: str | None = None,
        tool_choice: str | dict[str, Any] | None = None,
    ) -> LLMResponse:
        """Send the latest user message to the Claude Code CLI.

        Only the most recent user message is forwarded (per the Agent Proxy
        design -- full conversation context is not passed to the CLI).

        Session behaviour (D-01, D-02, D-03, D-06):
        * **session mode** -- passes ``--resume <id>`` on subsequent calls to
          maintain conversation context across turns.
        * **oneshot mode** -- passes ``--no-session-persistence`` so each prompt
          is independent with no stored session state.
        * If a ``--resume`` call fails, the provider falls back to a fresh
          session and logs a warning.
        """
        prompt = self._extract_latest_user_content(messages)

        # Capture session context into locals for concurrent safety
        session_key = self._current_session_key
        session_mode = self._current_session_mode

        # Determine CLI flags based on session mode
        session_id: str | None = None
        no_persist = False
        if session_mode == "session" and session_key:
            session_id = self._session_map.get(session_key)
        elif session_mode == "oneshot":
            no_persist = True

        cmd = self._build_command(
            prompt, session_id=session_id, no_session_persistence=no_persist
        )
        result = await self._run_cli(cmd)

        # D-06: If resume failed, retry without --resume (start fresh session)
        if (
            result.finish_reason == "error"
            and session_id is not None
            and session_mode == "session"
        ):
            logger.warning(
                "Claude Code --resume failed for session {}, starting fresh session",
                session_key,
            )
            result = await self._run_cli(self._build_command(prompt))

        return result

    # -- Message extraction -------------------------------------------------

    def _extract_latest_user_content(
        self,
        messages: list[dict[str, Any]],
    ) -> str:
        """Pull the text content from the last user message.

        Handles both plain-string content and multipart content lists
        (joining text blocks).
        """
        for msg in reversed(messages):
            if msg.get("role") != "user":
                continue

            content = msg.get("content")

            if isinstance(content, str):
                return content

            if isinstance(content, list):
                parts = [
                    block["text"]
                    for block in content
                    if isinstance(block, dict) and block.get("type") == "text"
                ]
                return "\n".join(parts)

        return ""

    # -- Result parsing -----------------------------------------------------

    def _parse_result(
        self,
        stdout_bytes: bytes,
        stderr_bytes: bytes,
        returncode: int | None,
    ) -> LLMResponse:
        """Parse raw subprocess output into an ``LLMResponse``."""
        stderr_text = stderr_bytes.decode("utf-8", errors="replace")
        if stderr_text.strip():
            logger.debug("Claude Code stderr: {}", stderr_text[:500])

        stdout_text = stdout_bytes.decode("utf-8", errors="replace").strip()

        if not stdout_text:
            return LLMResponse(
                content=(
                    f"Claude Code CLI returned no output. "
                    f"Exit code: {returncode}. "
                    f"stderr: {stderr_text[:200]}"
                ),
                tool_calls=[],
                finish_reason="error",
            )

        try:
            data: dict[str, Any] = json.loads(stdout_text)
        except json.JSONDecodeError as exc:
            return LLMResponse(
                content=(
                    f"Failed to parse Claude Code JSON output: {exc}. "
                    f"Raw: {stdout_text[:200]}"
                ),
                tool_calls=[],
                finish_reason="error",
            )

        # D-02: Extract session_id from JSON output and store in session map
        new_session_id = data.get("session_id", "")
        if (
            new_session_id
            and self._current_session_mode == "session"
            and self._current_session_key
        ):
            self._session_map[self._current_session_key] = new_session_id

        result_text: str = data.get("result", "") or ""
        usage_raw: dict[str, int] = data.get("usage") or {}
        is_error: bool = data.get("is_error", False)

        if is_error:
            return self._build_error_response(result_text, stderr_text, usage_raw)

        return LLMResponse(
            content=result_text or None,
            tool_calls=[],
            finish_reason="stop",
            usage={
                "prompt_tokens": usage_raw.get("input_tokens", 0),
                "completion_tokens": usage_raw.get("output_tokens", 0),
            },
        )

    # -- Error classification -----------------------------------------------

    def _build_error_response(
        self,
        result_text: str,
        stderr_text: str,
        usage: dict[str, int],
    ) -> LLMResponse:
        """Classify a CLI error and return a structured error ``LLMResponse``."""
        lower = result_text.lower()

        if "not logged in" in lower:
            error_kind = "auth"
            error_should_retry = False
        elif "rate limit" in lower or "too many requests" in lower:
            error_kind = "rate_limit"
            error_should_retry = True
        elif "overloaded" in lower:
            error_kind = "overloaded"
            error_should_retry = True
        else:
            error_kind = "cli_error"
            error_should_retry = False

        return LLMResponse(
            content=result_text,
            tool_calls=[],
            finish_reason="error",
            usage={
                "prompt_tokens": usage.get("input_tokens", 0),
                "completion_tokens": usage.get("output_tokens", 0),
            },
            error_kind=error_kind,
            error_should_retry=error_should_retry,
        )

    # -- Default model ------------------------------------------------------

    def get_default_model(self) -> str:
        """Return the default model identifier."""
        return self._default_model
