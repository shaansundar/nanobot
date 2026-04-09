"""Claude Code CLI bypass provider."""

from __future__ import annotations

import asyncio
import json
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
    ) -> None:
        super().__init__(api_key=None, api_base=None)

        self._cli_path: str = cli_path or shutil.which("claude") or ""
        if not self._cli_path:
            raise RuntimeError(_CLI_NOT_FOUND_MESSAGE)

        self._default_model: str = default_model

    # -- Command building ---------------------------------------------------

    def _build_command(self, prompt: str) -> list[str]:
        """Build the CLI argument list for a one-shot prompt invocation.

        Flags:
        * ``-p``                   -- print-mode (one-shot, non-interactive)
        * ``--output-format json`` -- structured JSON envelope
        * ``--setting-sources ""`` -- skip user/project settings to reduce
          overhead (~50K -> ~5K tokens) while preserving keychain OAuth
        """
        return [
            self._cli_path,
            "-p",
            "--output-format",
            "json",
            "--setting-sources",
            "",
            prompt,
        ]

    # -- Chat ---------------------------------------------------------------

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
        """
        prompt = self._extract_latest_user_content(messages)
        cmd = self._build_command(prompt)

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout_bytes, stderr_bytes = await proc.communicate()
        await proc.wait()

        return self._parse_result(stdout_bytes, stderr_bytes, proc.returncode)

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
