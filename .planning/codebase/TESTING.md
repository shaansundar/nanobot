# Testing Patterns

**Analysis Date:** 2026-04-09

## Test Framework

**Runner:**
- `pytest` >= 9.0.0
- Config: `pyproject.toml` under `[tool.pytest.ini_options]`
- `asyncio_mode = "auto"` — all async tests run automatically without explicit event loop setup

**Assertion Library:**
- pytest built-in `assert` (no separate assertion library)

**Coverage:**
- `pytest-cov` >= 6.0.0
- Source: `nanobot/`
- Excludes: `pragma: no cover`, `def __repr__`, `raise NotImplementedError`, `if __name__ == "__main__":`, `if TYPE_CHECKING:`

**Run Commands:**
```bash
pytest                                  # Run all tests (from repo root)
pytest tests/providers/                 # Run a subdirectory
pytest tests/providers/test_provider_retry.py  # Run a single file
pytest --cov=nanobot --cov-report=term-missing  # With coverage
```

## Test File Organization

**Location:**
- All tests live under `tests/` — separate from source, not co-located
- Mirror of source structure: `tests/providers/`, `tests/channels/`, `tests/agent/`, `tests/config/`, etc.

**Naming:**
- Files: `test_<module_or_feature>.py` — e.g., `test_enforce_role_alternation.py`, `test_filesystem_tools.py`
- Classes: `Test<Subject>` — e.g., `TestEnforceRoleAlternation`, `TestReadFileTool`, `TestConvertMessages`
- Functions: `test_<behavior_description>` — e.g., `test_trailing_assistant_removed`, `test_allows_public_ip`

**Structure:**
```
tests/
├── providers/          # Provider layer tests
├── channels/           # Channel adapter tests
├── agent/              # Agent loop, memory, tooling tests
├── config/             # Config schema and loader tests
├── tools/              # Tool implementation tests
├── security/           # SSRF / network security tests
├── utils/              # Utility function tests
├── cli/                # CLI command tests
├── command/            # Command routing tests
├── cron/               # Cron scheduler tests
├── test_openai_api.py  # Top-level API surface tests
└── test_package_version.py
```

## Test Structure

**Suite Organization:**

Class-based grouping is used for related tests on the same subject:
```python
class TestEnforceRoleAlternation:
    """Verify trailing-assistant removal and consecutive same-role merging."""

    def test_empty_messages(self):
        assert LLMProvider._enforce_role_alternation([]) == []

    def test_trailing_assistant_removed(self):
        msgs = [
            {"role": "user", "content": "Hi"},
            {"role": "assistant", "content": "Hello!"},
        ]
        result = LLMProvider._enforce_role_alternation(msgs)
        assert len(result) == 1
        assert result[0]["role"] == "user"
```

Free function tests also appear for single focused behaviors:
```python
def test_rejects_non_http_scheme():
    ok, err = validate_url_target("ftp://example.com/file")
    assert not ok
    assert "http" in err.lower()
```

**Patterns:**
- Arrange inline (no separate setup method unless shared via fixture)
- Act: call the function or method under test
- Assert: multiple `assert` statements in one test when they describe a single behavior
- Docstrings on test functions used to explain non-obvious intent: `"""Malformed JSON arguments should log a warning and fallback."""`

## Mocking

**Frameworks Used:**
- `unittest.mock`: `MagicMock`, `AsyncMock`, `patch`, `patch.dict`
- `monkeypatch` (pytest fixture) for patching module-level attributes like `asyncio.sleep`
- `types.SimpleNamespace` for lightweight fake objects without full mock overhead

**Patterns — patching asyncio.sleep:**
```python
@pytest.mark.asyncio
async def test_chat_with_retry_retries_transient_error_then_succeeds(monkeypatch) -> None:
    delays: list[float] = []

    async def _fake_sleep(delay: float) -> None:
        delays.append(delay)

    monkeypatch.setattr("nanobot.providers.base.asyncio.sleep", _fake_sleep)
    ...
    assert delays == [1]
```

**Patterns — patching network calls:**
```python
def test_blocks_private_ipv4(ip: str, label: str):
    with patch("nanobot.security.network.socket.getaddrinfo", _fake_resolve("evil.com", [ip])):
        ok, err = validate_url_target(f"http://evil.com/path")
        assert not ok
```

**Patterns — patching logger to assert warnings:**
```python
with patch("nanobot.providers.openai_responses.parsing.logger") as mock_logger:
    result = parse_response_output(resp)
mock_logger.warning.assert_called_once()
assert "Failed to parse tool call arguments" in str(mock_logger.warning.call_args)
```

**Patterns — SimpleNamespace fakes:**
```python
def _fake_response(*, status_code: int, headers=None, text="") -> SimpleNamespace:
    return SimpleNamespace(status_code=status_code, headers=headers or {}, text=text)

err.response = _fake_response(status_code=409, headers={"retry-after-ms": "250"})
```

**Scripted provider for retry testing:**
```python
class ScriptedProvider(LLMProvider):
    def __init__(self, responses):
        super().__init__()
        self._responses = list(responses)
        self.calls = 0
        self.last_kwargs: dict = {}

    async def chat(self, *args, **kwargs) -> LLMResponse:
        self.calls += 1
        self.last_kwargs = kwargs
        response = self._responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        return response
```

**What to Mock:**
- `asyncio.sleep` in retry tests to avoid real delays
- `socket.getaddrinfo` in network/SSRF tests
- `loguru.logger` when asserting warning/error was emitted
- External SDK clients (e.g., `AsyncOpenAI`, `AsyncAnthropic`) via `patch` or `MagicMock`
- File system writes avoided by using `tmp_path` pytest fixture instead

**What NOT to Mock:**
- The class under test itself
- Pure Python data transformations — test them directly
- Pydantic model validation — use real `model_validate()` calls

## Fixtures and Factories

**Test Data:**
```python
# Module-level constants for shared test payloads
_IMAGE_MSG = [
    {"role": "user", "content": [
        {"type": "text", "text": "describe this"},
        {"type": "image_url", "image_url": {"url": "data:image/png;base64,abc"}, "_meta": {"path": "/media/test.png"}},
    ]},
]
```

**pytest fixtures:**
```python
@pytest.fixture
def config():
    """Create a minimal config for testing."""
    return Config()

@pytest.fixture
def bus():
    return MessageBus()

@pytest.fixture
def manager(config, bus):
    manager = ChannelManager(config, bus)
    manager.channels["mock"] = MockChannel({}, bus)
    return manager
```

**tmp_path fixture:**
Used extensively for filesystem tool tests — avoids touching real disk:
```python
@pytest.fixture()
def tool(self, tmp_path):
    return ReadFileTool(workspace=tmp_path)

@pytest.fixture()
def sample_file(self, tmp_path):
    f = tmp_path / "sample.txt"
    f.write_text("\n".join(f"line {i}" for i in range(1, 21)), encoding="utf-8")
    return f
```

**Location:**
- No shared `conftest.py` detected — fixtures are defined inline within each test file or test class

## Coverage

**Requirements:**
- No enforced minimum in CI configuration (`pyproject.toml` does not set `fail_under`)
- Coverage config present: `[tool.coverage.run]` sources `nanobot/`, omits `tests/`

**View Coverage:**
```bash
pytest --cov=nanobot --cov-report=term-missing
pytest --cov=nanobot --cov-report=html
```

## Test Types

**Unit Tests:**
- Dominant pattern — the majority of tests isolate a single class, method, or function
- Examples: `test_enforce_role_alternation.py`, `test_dream_config.py`, `test_split_tool_call_id` in `test_openai_responses.py`
- Pure functions tested without any mocking: config schema validation, message conversion, retry logic

**Integration Tests:**
- Tests that wire together multiple real components without external I/O
- Examples: `test_filesystem_tools.py` (uses `tmp_path`), `test_channel_manager_delta_coalescing.py` (uses real `ChannelManager` + `MockChannel`)
- Pattern: replace only the I/O boundary (file system via `tmp_path`, network via mocks)

**E2E Tests:**
- Not used — no Playwright, no HTTP server in test suite
- `tests/test_docker.sh` is a shell script for Docker-level smoke tests (not pytest)

## Common Patterns

**Async Testing:**
```python
@pytest.mark.asyncio
async def test_chat_with_retry_returns_final_error_after_retries(monkeypatch) -> None:
    provider = ScriptedProvider([
        LLMResponse(content="429 rate limit a", finish_reason="error"),
        LLMResponse(content="ok"),
    ])
    response = await provider.chat_with_retry(messages=[{"role": "user", "content": "hello"}])
    assert response.content == "ok"
```

**Error/Exception Testing:**
```python
with pytest.raises(asyncio.CancelledError):
    await provider.chat_with_retry(messages=[{"role": "user", "content": "hello"}])

with pytest.raises(RuntimeError, match="Response failed.*rate_limit_exceeded"):
    await consume_sdk_stream(stream())
```

**Parametrize — used for grouped security tests:**
```python
@pytest.mark.parametrize("ip,label", [
    ("127.0.0.1", "loopback"),
    ("10.0.0.1", "rfc1918_10"),
    ("169.254.169.254", "metadata"),
])
def test_blocks_private_ipv4(ip: str, label: str):
    with patch("nanobot.security.network.socket.getaddrinfo", _fake_resolve("evil.com", [ip])):
        ok, err = validate_url_target(f"http://evil.com/path")
        assert not ok
```

**Immutability assertion:**
```python
def test_original_messages_not_mutated(self):
    msgs = [{"role": "user", "content": "Hello"}, {"role": "user", "content": "World"}]
    original_first = dict(msgs[0])
    LLMProvider._enforce_role_alternation(msgs)
    assert msgs[0] == original_first
    assert len(msgs) == 2
```

**Async generator stream testing:**
```python
async def stream():
    for e in [ev1, ev2, ev3]:
        yield e

content, tool_calls, finish_reason, usage, reasoning = await consume_sdk_stream(stream())
assert content == "Hello world"
```

## Section Separator Style

Tests in larger files use banner comments to group suites:
```python
# ======================================================================
# converters - split_tool_call_id
# ======================================================================

# ---------------------------------------------------------------------------
# ReadFileTool
# ---------------------------------------------------------------------------

# ── _parse: non-streaming ─────────────────────────────────────────────────
```

---

*Testing analysis: 2026-04-09*
