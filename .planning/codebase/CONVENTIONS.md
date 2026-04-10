# Coding Conventions

**Analysis Date:** 2026-04-09

## Naming Patterns

**Files:**
- Modules use `snake_case`: `openai_compat_provider.py`, `github_copilot_provider.py`
- Test files prefixed with `test_`: `test_provider_retry.py`, `test_filesystem_tools.py`
- Private helpers prefixed with `_`: `_FsTool`, `_gen_tool_id`, `_fake_resolve`

**Classes:**
- `PascalCase` throughout: `LLMProvider`, `OpenAICompatProvider`, `AnthropicProvider`
- Abstract bases use descriptive names: `LLMProvider`, `BaseChannel`, `_FsTool`
- Test fakes/stubs named with intent: `ScriptedProvider`, `MockChannel`, `_DummyChannel`

**Functions and Methods:**
- `snake_case`: `chat_with_retry`, `get_default_model`, `build_image_content_blocks`
- Private methods prefixed `_`: `_sanitize_empty_content`, `_enforce_role_alternation`, `_extract_retry_after`
- Static/classmethod helpers prefixed `_`: `_tool_name`, `_is_transient_error`, `_normalize_error_token`

**Variables:**
- `snake_case`: `retry_after`, `error_status_code`, `last_error_key`
- Module-level constants: `UPPER_SNAKE_CASE`: `_UNSAFE_CHARS`, `_TOOL_RESULT_PREVIEW_CHARS`
- Sentinel values: `_SENTINEL = object()` (class-level, single-underscore prefixed)

**Booleans:**
- Use `is_` / `has_` / `supports_` prefixes: `has_tool_calls`, `is_allowed`, `is_transient_error`, `supports_prompt_caching`

**Type Aliases and Dataclass Fields:**
- Type annotations on all signatures using modern Python 3.10+ union syntax: `str | None`, `list[dict[str, Any]] | None`

## Code Style

**Formatting:**
- Tool: `ruff` (`line-length = 100`)
- Target version: `py311`
- Config in `pyproject.toml` under `[tool.ruff]`

**Linting:**
- `ruff` with rule sets: `E` (pycodestyle), `F` (Pyflakes), `I` (isort), `N` (pep8-naming), `W` (warnings)
- `E501` (line too long) is explicitly ignored — ruff formats but won't flag long lines as errors

**Type Annotations:**
- All function signatures carry full type annotations
- `Any` from `typing` used for heterogeneous dict values
- `from __future__ import annotations` used in ~40 files to enable forward references

## Import Organization

**Standard approach (enforced by ruff `I` rules):**
1. Standard library imports
2. Third-party imports
3. First-party `nanobot.*` imports

**Pattern:**
```python
from __future__ import annotations  # only in files that need it

import asyncio
import json
import re
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from typing import Any

from loguru import logger

from nanobot.providers.base import LLMProvider, LLMResponse
```

**Path Aliases:**
- None — all imports use absolute `nanobot.*` paths. No `__init__.py` re-exports used for aliasing.

## Error Handling

**Patterns:**
- Exceptions raised at validation boundaries with `ValueError` (bad config/args) or `RuntimeError` (runtime failures): `raise ValueError("Azure OpenAI api_key is required")`, `raise RuntimeError("GitHub Copilot is not logged in...")`
- Provider errors converted to `LLMResponse(finish_reason="error")` rather than propagating: `_safe_chat` wraps `chat()` and catches all `Exception` (except `asyncio.CancelledError`)
- `asyncio.CancelledError` is always re-raised — never swallowed: `except asyncio.CancelledError: raise`
- `PermissionError` raised for filesystem boundary violations: `_resolve_path` raises if path escapes workspace
- No bare `except:` usage — exceptions are typed or at least `except Exception`

**Error in responses:**
- LLM call errors returned as `LLMResponse(content=f"Error calling LLM: {exc}", finish_reason="error")`
- Structured error metadata fields on `LLMResponse`: `error_status_code`, `error_kind`, `error_type`, `error_code`, `error_retry_after_s`, `error_should_retry`

## Logging

**Framework:** `loguru` — imported as `from loguru import logger`

**Patterns:**
- `logger.warning(...)` for transient/retryable errors and degraded behavior
- `logger.warning("Failed to parse tool call arguments...")` for non-fatal parse failures
- Loguru template-style placeholders: `logger.warning("LLM error (attempt {}{}), retrying in {}s: {}", attempt, ...)`
- No `logger.info` in hot paths — debug-level info not widely used in the provider layer

## Comments

**When to Comment:**
- Module-level docstring on every module: `"""Base LLM provider interface."""`
- Class-level docstring explains purpose and scope: `"""Base class for LLM providers."""`
- Method-level docstrings on public/abstract methods with Args/Returns sections
- Inline comments for non-obvious decisions: `# Unknown 429 defaults to WAIT+retry.`
- Section separators using `# ---` dashes to divide large classes/files

**Inline Comment Style:**
```python
# ── _parse: non-streaming ─────────────────────────────────────────────────
```
Section banners used in test files to group related tests.

## Function Design

**Size:**
- Short utility functions preferred (< 30 lines)
- Larger orchestration methods exist (`_run_with_retry`, `chat_stream_with_retry`) but are bounded by single responsibility
- `_sanitize_empty_content` (~40 lines) is the typical upper range for non-trivial helpers

**Parameters:**
- Keyword arguments used for optional parameters: `model: str | None = None`, `tool_choice: str | dict[str, Any] | None = None`
- Sentinel pattern for distinguishing "not passed" from `None`: `max_tokens: object = _SENTINEL`
- `**kwargs: Any` used in retry wrappers to forward argument dicts

**Return Values:**
- Explicit return type annotations on all methods
- `LLMResponse` returned uniformly from all provider call paths
- Helpers return `None` to signal "no change needed" (e.g., `_strip_image_content` returns `None` if no images found)
- Tuple returns used in security module: `validate_url_target` returns `(bool, str)`

## Module Design

**Exports:**
- `__init__.py` files are minimal — they re-export key symbols from submodules
- Example: `nanobot/providers/__init__.py` exports provider classes for external use

**Barrel Files:**
- Thin `__init__.py` re-exports used at package boundaries (`nanobot/agent/__init__.py`, `nanobot/providers/__init__.py`)
- Not used for deep intra-package imports — modules import directly from sibling modules

## Data Structures

**Dataclasses:**
- Used for DTOs and value objects: `ToolCallRequest`, `LLMResponse`, `GenerationSettings`
- `frozen=True` used for immutable settings: `@dataclass(frozen=True) class GenerationSettings`
- `field(default_factory=list)` for mutable defaults

**Pydantic:**
- `BaseModel` (via `pydantic`) used for all configuration schema: `DreamConfig`, `AgentDefaults`, `ChannelsConfig`
- Base `class Base(BaseModel)` with `alias_generator=to_camel` for camelCase JSON compatibility
- `ConfigDict(populate_by_name=True)` allows both snake_case and camelCase input keys
- `Field(..., exclude=True)` used for legacy compatibility fields hidden from serialization

## Async Patterns

- All LLM calls are `async` throughout: `async def chat(...)`, `async def chat_stream(...)`
- `asyncio.CancelledError` always re-raised, never swallowed
- `asyncio.sleep` used for retry delays — patched via `monkeypatch` in tests for speed

---

*Convention analysis: 2026-04-09*
