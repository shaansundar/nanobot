"""Tests for ClaudeCodeProvider -- Claude Code CLI bypass provider."""

from __future__ import annotations

import asyncio
import json

import pytest

from nanobot.providers.base import LLMResponse

# ---------------------------------------------------------------------------
# Fixtures -- JSON payloads matching verified CLI output schema
# ---------------------------------------------------------------------------

SUCCESS_JSON: dict = {
    "type": "result",
    "subtype": "success",
    "is_error": False,
    "result": "hello world",
    "session_id": "test-id",
    "total_cost_usd": 0.035,
    "usage": {"input_tokens": 10, "output_tokens": 20},
}

AUTH_ERROR_JSON: dict = {
    "type": "result",
    "subtype": "success",
    "is_error": True,
    "result": "Not logged in - Please run /login",
    "session_id": "test-id",
    "total_cost_usd": 0,
    "usage": {"input_tokens": 0, "output_tokens": 0},
}

RATE_LIMIT_JSON: dict = {
    "type": "result",
    "subtype": "success",
    "is_error": True,
    "result": "rate limit exceeded, try again in 30s",
    "session_id": "test-id",
    "total_cost_usd": 0,
    "usage": {"input_tokens": 0, "output_tokens": 0},
}


# ---------------------------------------------------------------------------
# FakeProcess -- lightweight asyncio subprocess stand-in
# ---------------------------------------------------------------------------


class FakeProcess:
    """Mimics an asyncio.subprocess.Process for testing."""

    def __init__(
        self,
        stdout: bytes,
        stderr: bytes = b"",
        returncode: int = 0,
    ) -> None:
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode

    async def communicate(self) -> tuple[bytes, bytes]:
        return self.stdout, self.stderr

    async def wait(self) -> int:
        return self.returncode


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_provider(monkeypatch, cli_path: str = "/usr/local/bin/claude"):
    """Create a ClaudeCodeProvider with shutil.which mocked."""
    monkeypatch.setattr("shutil.which", lambda _name: cli_path)
    from nanobot.providers.claude_code_provider import ClaudeCodeProvider

    return ClaudeCodeProvider()


def _patch_subprocess(monkeypatch, fake: FakeProcess):
    """Monkeypatch asyncio.create_subprocess_exec to return *fake*."""

    async def _mock_exec(*_args, **_kwargs):
        return fake

    monkeypatch.setattr("asyncio.create_subprocess_exec", _mock_exec)


# ---------------------------------------------------------------------------
# Tests -- Happy path (CORE-01: chat round-trip)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_chat_returns_response(monkeypatch) -> None:
    provider = _make_provider(monkeypatch)
    _patch_subprocess(
        monkeypatch,
        FakeProcess(stdout=json.dumps(SUCCESS_JSON).encode()),
    )

    result = await provider.chat(
        messages=[{"role": "user", "content": "say hello"}],
    )

    assert isinstance(result, LLMResponse)
    assert result.content == "hello world"
    assert result.finish_reason == "stop"
    assert result.tool_calls == []


@pytest.mark.asyncio
async def test_chat_usage_mapping(monkeypatch) -> None:
    provider = _make_provider(monkeypatch)
    _patch_subprocess(
        monkeypatch,
        FakeProcess(stdout=json.dumps(SUCCESS_JSON).encode()),
    )

    result = await provider.chat(
        messages=[{"role": "user", "content": "hello"}],
    )

    assert result.usage == {"prompt_tokens": 10, "completion_tokens": 20}


@pytest.mark.asyncio
async def test_tool_calls_always_empty(monkeypatch) -> None:
    provider = _make_provider(monkeypatch)
    _patch_subprocess(
        monkeypatch,
        FakeProcess(stdout=json.dumps(SUCCESS_JSON).encode()),
    )

    result = await provider.chat(
        messages=[{"role": "user", "content": "hello"}],
    )

    assert result.tool_calls == []


# ---------------------------------------------------------------------------
# Tests -- CLI not found (CORE-04)
# ---------------------------------------------------------------------------


def test_cli_not_found_raises(monkeypatch) -> None:
    monkeypatch.setattr("shutil.which", lambda _name: None)
    from nanobot.providers.claude_code_provider import ClaudeCodeProvider

    with pytest.raises(RuntimeError, match="Claude Code CLI not found"):
        ClaudeCodeProvider()


def test_cli_not_found_message_contains_install_instructions(monkeypatch) -> None:
    monkeypatch.setattr("shutil.which", lambda _name: None)
    from nanobot.providers.claude_code_provider import ClaudeCodeProvider

    with pytest.raises(RuntimeError, match="npm install -g @anthropic-ai/claude-code"):
        ClaudeCodeProvider()


# ---------------------------------------------------------------------------
# Tests -- Error propagation (CORE-05)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_auth_error_propagated(monkeypatch) -> None:
    provider = _make_provider(monkeypatch)
    _patch_subprocess(
        monkeypatch,
        FakeProcess(stdout=json.dumps(AUTH_ERROR_JSON).encode()),
    )

    result = await provider.chat(
        messages=[{"role": "user", "content": "hello"}],
    )

    assert result.finish_reason == "error"
    assert "Not logged in" in (result.content or "")


@pytest.mark.asyncio
async def test_auth_error_not_retryable(monkeypatch) -> None:
    provider = _make_provider(monkeypatch)
    _patch_subprocess(
        monkeypatch,
        FakeProcess(stdout=json.dumps(AUTH_ERROR_JSON).encode()),
    )

    result = await provider.chat(
        messages=[{"role": "user", "content": "hello"}],
    )

    assert result.error_should_retry is False


@pytest.mark.asyncio
async def test_rate_limit_retryable(monkeypatch) -> None:
    provider = _make_provider(monkeypatch)
    _patch_subprocess(
        monkeypatch,
        FakeProcess(stdout=json.dumps(RATE_LIMIT_JSON).encode()),
    )

    result = await provider.chat(
        messages=[{"role": "user", "content": "hello"}],
    )

    assert result.finish_reason == "error"
    assert result.error_should_retry is True


@pytest.mark.asyncio
async def test_empty_stdout_returns_error(monkeypatch) -> None:
    provider = _make_provider(monkeypatch)
    _patch_subprocess(
        monkeypatch,
        FakeProcess(stdout=b"", returncode=1),
    )

    result = await provider.chat(
        messages=[{"role": "user", "content": "hello"}],
    )

    assert result.finish_reason == "error"


@pytest.mark.asyncio
async def test_invalid_json_returns_error(monkeypatch) -> None:
    provider = _make_provider(monkeypatch)
    _patch_subprocess(
        monkeypatch,
        FakeProcess(stdout=b"this is not json"),
    )

    result = await provider.chat(
        messages=[{"role": "user", "content": "hello"}],
    )

    assert result.finish_reason == "error"
    assert "Failed to parse" in (result.content or "")


# ---------------------------------------------------------------------------
# Tests -- CLI flags (CORE-06: --setting-sources, not --bare)
# ---------------------------------------------------------------------------


def test_command_includes_setting_sources(monkeypatch) -> None:
    provider = _make_provider(monkeypatch)
    cmd = provider._build_command("test prompt")

    # "--setting-sources" must appear, followed by "" (empty string)
    idx = cmd.index("--setting-sources")
    assert cmd[idx + 1] == ""


def test_command_does_not_include_bare(monkeypatch) -> None:
    provider = _make_provider(monkeypatch)
    cmd = provider._build_command("test prompt")

    assert "--bare" not in cmd


def test_command_includes_p_flag(monkeypatch) -> None:
    provider = _make_provider(monkeypatch)
    cmd = provider._build_command("test prompt")

    assert "-p" in cmd


def test_command_includes_output_format_json(monkeypatch) -> None:
    provider = _make_provider(monkeypatch)
    cmd = provider._build_command("test prompt")

    idx = cmd.index("--output-format")
    assert cmd[idx + 1] == "json"


# ---------------------------------------------------------------------------
# Tests -- Message extraction
# ---------------------------------------------------------------------------


def test_extract_latest_user_content_simple(monkeypatch) -> None:
    provider = _make_provider(monkeypatch)
    messages = [{"role": "user", "content": "hello"}]

    result = provider._extract_latest_user_content(messages)

    assert result == "hello"


def test_extract_latest_user_content_multipart(monkeypatch) -> None:
    provider = _make_provider(monkeypatch)
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "part one"},
                {"type": "text", "text": "part two"},
            ],
        },
    ]

    result = provider._extract_latest_user_content(messages)

    assert "part one" in result
    assert "part two" in result


# ---------------------------------------------------------------------------
# Tests -- Subprocess stdin (D-03: prevent TTY hang)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stdin_is_devnull(monkeypatch) -> None:
    provider = _make_provider(monkeypatch)
    captured_kwargs: dict = {}

    async def _capturing_exec(*_args, **kwargs):
        captured_kwargs.update(kwargs)
        return FakeProcess(stdout=json.dumps(SUCCESS_JSON).encode())

    monkeypatch.setattr("asyncio.create_subprocess_exec", _capturing_exec)

    await provider.chat(messages=[{"role": "user", "content": "hello"}])

    assert captured_kwargs.get("stdin") == asyncio.subprocess.DEVNULL


# ---------------------------------------------------------------------------
# Tests -- Default model
# ---------------------------------------------------------------------------


def test_get_default_model(monkeypatch) -> None:
    monkeypatch.setattr("shutil.which", lambda _name: "/usr/local/bin/claude")
    from nanobot.providers.claude_code_provider import ClaudeCodeProvider

    model = "claude_code/claude-sonnet-4-20250514"
    provider = ClaudeCodeProvider(default_model=model)

    assert provider.get_default_model() == model
