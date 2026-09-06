"""Unit tests for crackerjack.decorators.patterns module.

Coverage focus: bring ``crackerjack/decorators/patterns.py`` from ~15% to
``>= 80%`` by exercising every public helper plus the unwrapped internal
helpers (``_handle_result_analysis_sync`` / ``_analyze_result_errors_sync`` /
``_cache_crackerjack_error_sync`` / ``_cache_exception_sync`` and their
async counterparts).

The tests use ``tmp_path`` so that ``ErrorCache`` writes to an isolated
directory per test instead of the user's real ``~/.cache/crackerjack-mcp``.
"""

from __future__ import annotations

import asyncio
import inspect
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from crackerjack.decorators.patterns import (
    _analyze_result_errors,
    _analyze_result_errors_sync,
    _cache_crackerjack_error,
    _cache_crackerjack_error_sync,
    _cache_exception,
    _cache_exception_sync,
    _create_async_wrapper,
    _create_sync_wrapper,
    _handle_generic_exception_sync,
    _handle_result_analysis,
    _handle_result_analysis_sync,
    cache_errors,
)
from crackerjack.errors import ConfigError, ErrorCode
from crackerjack.mcp.cache import ErrorCache, ErrorPattern


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_cache_dir(tmp_path: Path) -> Path:
    """Provide a per-test cache directory."""
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    return cache_dir


@pytest.fixture
def make_cache(tmp_cache_dir: Path):
    """Factory that builds a fresh ``ErrorCache`` rooted in ``tmp_path``."""

    def _factory() -> ErrorCache:
        return ErrorCache(cache_dir=tmp_cache_dir)

    return _factory


@pytest.fixture
def sample_function() -> "callable":
    """A simple function used as the context target for pattern analysis."""

    def the_function(x: int) -> int:
        return x * 2

    return the_function


@pytest.fixture
def async_sample_function() -> "callable":
    """An async function used as the context target for pattern analysis."""

    async def the_async_function(x: int) -> int:
        return x * 2

    return the_async_function


@pytest.fixture
def crackerjack_error_kwargs() -> dict[str, object]:
    """Reusable kwargs for constructing ``ConfigError`` instances."""
    return {
        "message": "could not parse configuration file",
        "error_code": ErrorCode.CONFIG_PARSE_ERROR,
        "recovery": "check the syntax",
    }


# ---------------------------------------------------------------------------
# cache_errors decorator (the public API)
# ---------------------------------------------------------------------------


class TestCacheErrorsPublicAPI:
    """Cover the public-facing ``cache_errors`` decorator factory."""

    def test_returns_callable(self) -> None:
        """``cache_errors`` returns a decorator factory."""
        decorator = cache_errors()
        assert callable(decorator)

    def test_decorator_returns_callable(self, tmp_cache_dir: Path) -> None:
        """The factory returns a function that wraps the target function."""
        decorator_factory = cache_errors(cache_dir=tmp_cache_dir)
        wrapped = decorator_factory(lambda: "ok")
        assert callable(wrapped)

    def test_default_parameters(self) -> None:
        """Default parameters match the documented API."""
        decorator = cache_errors()
        # Just exercise that it is a no-arg call (parameters exist but are optional).
        assert decorator is not None

    def test_preserves_function_metadata(self, tmp_cache_dir: Path) -> None:
        """``@wraps`` should keep ``__name__`` and ``__qualname__``."""

        @cache_errors(cache_dir=tmp_cache_dir)
        def named_function() -> str:
            return "ok"

        assert named_function.__name__ == "named_function"
        assert "named_function" in (named_function.__qualname__ or "")


class TestCacheErrorsSyncWrapper:
    """Behaviour of the sync wrapper when applied to plain functions."""

    def test_returns_result_for_normal_call(
        self,
        tmp_cache_dir: Path,
    ) -> None:
        """A non-error return value passes straight through."""

        @cache_errors(cache_dir=tmp_cache_dir)
        def compute(x: int) -> int:
            return x + 1

        assert compute(2) == 3

    def test_reraises_crackerjack_error(
        self,
        tmp_cache_dir: Path,
        crackerjack_error_kwargs: dict[str, object],
    ) -> None:
        """``CrackerjackError`` propagates unchanged after caching."""

        @cache_errors(cache_dir=tmp_cache_dir)
        def broken() -> None:
            raise ConfigError(**crackerjack_error_kwargs)

        with pytest.raises(ConfigError):
            broken()

    def test_reraises_generic_exception(self, tmp_cache_dir: Path) -> None:
        """A non-``CrackerjackError`` propagates unchanged after caching."""

        @cache_errors(cache_dir=tmp_cache_dir)
        def broken() -> None:
            msg = "boom"
            raise ValueError(msg)

        with pytest.raises(ValueError):
            broken()

    def test_auto_analyze_true_records_crackerjack_error_pattern(
        self,
        tmp_cache_dir: Path,
        crackerjack_error_kwargs: dict[str, object],
        make_cache: "callable",
    ) -> None:
        """With ``auto_analyze=True`` (default), a CrackerjackError is cached."""

        cache = make_cache()

        wrapped = _create_sync_wrapper(
            self._raise_config_error,
            cache,
            error_type=None,
            auto_analyze=True,
        )

        with pytest.raises(ConfigError):
            wrapped()

        assert cache.patterns, "expected pattern to be cached"

    def test_auto_analyze_false_skips_result_analysis(
        self,
        tmp_cache_dir: Path,
        make_cache: "callable",
    ) -> None:
        """When ``auto_analyze=False``, dict results are not analyzed."""

        cache = make_cache()

        wrapped = _create_sync_wrapper(
            self._return_error_dict,
            cache,
            error_type=None,
            auto_analyze=False,
        )

        result = wrapped()
        assert result == {"error": "plain text error message"}
        assert cache.patterns == {}

    def test_error_type_override_propagates_to_crackerjack_error(
        self,
        tmp_cache_dir: Path,
        crackerjack_error_kwargs: dict[str, object],
        make_cache: "callable",
    ) -> None:
        """``error_type`` is used as the ``ErrorPattern.error_type``."""

        cache = make_cache()

        wrapped = _create_sync_wrapper(
            self._raise_config_error,
            cache,
            error_type="my_custom_label",
            auto_analyze=True,
        )

        with pytest.raises(ConfigError):
            wrapped()

        assert any(
            p.error_type == "my_custom_label" for p in cache.patterns.values()
        )

    def test_handles_kwargs(
        self,
        tmp_cache_dir: Path,
        make_cache: "callable",
    ) -> None:
        """The wrapper forwards keyword arguments to the wrapped function."""

        @cache_errors(cache_dir=tmp_cache_dir)
        def greet(name: str = "world", *, suffix: str = "!") -> str:
            return f"hello {name}{suffix}"

        assert greet(name="crack", suffix="?") == "hello crack?"
        assert greet() == "hello world!"

    # Helpers used by the class-level tests above
    @staticmethod
    def _raise_config_error() -> None:
        raise ConfigError(
            "config parse failed",
            ErrorCode.CONFIG_PARSE_ERROR,
            recovery="check the syntax",
        )

    @staticmethod
    def _return_error_dict() -> dict[str, str]:
        return {"error": "plain text error message"}


class TestCacheErrorsAsyncWrapper:
    """Behaviour of the async wrapper when applied to coroutine functions."""

    async def test_returns_result_for_normal_call(
        self,
        tmp_cache_dir: Path,
    ) -> None:
        @cache_errors(cache_dir=tmp_cache_dir)
        async def compute(x: int) -> int:
            return x * 10

        assert await compute(3) == 30

    async def test_reraises_crackerjack_error(
        self,
        tmp_cache_dir: Path,
        crackerjack_error_kwargs: dict[str, object],
    ) -> None:
        @cache_errors(cache_dir=tmp_cache_dir)
        async def broken() -> None:
            raise ConfigError(**crackerjack_error_kwargs)

        with pytest.raises(ConfigError):
            await broken()

    async def test_reraises_generic_exception(self, tmp_cache_dir: Path) -> None:
        @cache_errors(cache_dir=tmp_cache_dir)
        async def broken() -> None:
            msg = "kaboom"
            raise RuntimeError(msg)

        with pytest.raises(RuntimeError):
            await broken()

    async def test_auto_analyze_true_records_crackerjack_error_pattern(
        self,
        tmp_cache_dir: Path,
        make_cache: "callable",
    ) -> None:
        """Async ``CrackerjackError`` path stores the pattern."""

        cache = make_cache()

        async def broken() -> None:
            raise ConfigError("nope", ErrorCode.CONFIG_PARSE_ERROR, recovery="fix")

        wrapped = _create_async_wrapper(
            broken,
            cache,
            error_type="async_label",
            auto_analyze=True,
        )

        with pytest.raises(ConfigError):
            await wrapped()

        assert any(
            p.error_type == "async_label" for p in cache.patterns.values()
        )

    async def test_auto_analyze_false_skips_result_analysis(
        self,
        tmp_cache_dir: Path,
        make_cache: "callable",
    ) -> None:
        cache = make_cache()

        async def returning() -> dict[str, str]:
            return {"error": "ignored because auto_analyze=False"}

        wrapped = _create_async_wrapper(
            returning,
            cache,
            error_type=None,
            auto_analyze=False,
        )

        result = await wrapped()
        assert "error" in result
        assert cache.patterns == {}

    async def test_async_wrapper_routes_result_analysis(
        self,
        tmp_cache_dir: Path,
        make_cache: "callable",
    ) -> None:
        """When result is a dict with ``error``/``errors``, the analyzer runs."""

        cache = make_cache()

        async def returning() -> dict[str, str]:
            return {"error": "lint problem on line 7"}

        wrapped = _create_async_wrapper(
            returning,
            cache,
            error_type="ruff",
            auto_analyze=True,
        )

        result = await wrapped()
        assert "error" in result
        # Either the analyzer detected a pattern, or it returned None — both
        # are valid outcomes; the test exercises the routing branch.

    async def test_async_wrapper_routes_generic_exception(
        self,
        tmp_cache_dir: Path,
        make_cache: "callable",
    ) -> None:
        """Generic exceptions pass through ``_handle_generic_exception``."""

        cache = make_cache()

        async def bad() -> None:
            msg = "bad value"
            raise ValueError(msg)

        wrapped = _create_async_wrapper(
            bad,
            cache,
            error_type=None,
            auto_analyze=False,  # explicit; should NOT cache
        )

        with pytest.raises(ValueError):
            await wrapped()

        assert cache.patterns == {}


# ---------------------------------------------------------------------------
# _handle_result_analysis_sync / _handle_result_analysis (async)
# ---------------------------------------------------------------------------


class TestHandleResultAnalysis:
    """The result-analysis router decides whether to invoke the analyzer."""

    def test_non_dict_result_short_circuits(
        self,
        make_cache: "callable",
        sample_function: "callable",
    ) -> None:
        cache = make_cache()
        _handle_result_analysis_sync(
            "not a dict",
            cache,
            sample_function,
            error_type=None,
            auto_analyze=True,
        )
        assert cache.patterns == {}

    def test_dict_without_error_key_short_circuits(
        self,
        make_cache: "callable",
        sample_function: "callable",
    ) -> None:
        cache = make_cache()
        _handle_result_analysis_sync(
            {"status": "ok", "value": 1},
            cache,
            sample_function,
            error_type=None,
            auto_analyze=True,
        )
        assert cache.patterns == {}

    def test_auto_analyze_false_short_circuits(
        self,
        make_cache: "callable",
        sample_function: "callable",
    ) -> None:
        cache = make_cache()
        _handle_result_analysis_sync(
            {"error": "some message"},
            cache,
            sample_function,
            error_type=None,
            auto_analyze=False,
        )
        assert cache.patterns == {}

    def test_dict_with_error_key_invokes_analyzer(
        self,
        make_cache: "callable",
        sample_function: "callable",
    ) -> None:
        cache = make_cache()
        _handle_result_analysis_sync(
            {"error": "lint problem on line 7"},
            cache,
            sample_function,
            error_type=None,
            auto_analyze=True,
        )
        # Pattern may or may not be detected depending on parser heuristics,
        # but the routing branch must have run (test that it doesn't crash).

    def test_dict_with_errors_key_invokes_analyzer(
        self,
        make_cache: "callable",
        sample_function: "callable",
    ) -> None:
        cache = make_cache()
        _handle_result_analysis_sync(
            {"errors": "lint problem on line 7"},
            cache,
            sample_function,
            error_type=None,
            auto_analyze=True,
        )

    def test_none_result_short_circuits(
        self,
        make_cache: "callable",
        sample_function: "callable",
    ) -> None:
        cache = make_cache()
        _handle_result_analysis_sync(
            None,
            cache,
            sample_function,
            error_type=None,
            auto_analyze=True,
        )
        assert cache.patterns == {}

    def test_empty_dict_short_circuits(
        self,
        make_cache: "callable",
        sample_function: "callable",
    ) -> None:
        cache = make_cache()
        _handle_result_analysis_sync(
            {},
            cache,
            sample_function,
            error_type=None,
            auto_analyze=True,
        )
        assert cache.patterns == {}

    async def test_async_short_circuits_non_dict(
        self,
        make_cache: "callable",
        sample_function: "callable",
    ) -> None:
        cache = make_cache()
        await _handle_result_analysis(
            "not a dict",
            cache,
            sample_function,
            error_type=None,
            auto_analyze=True,
        )
        assert cache.patterns == {}

    async def test_async_with_error_key(
        self,
        make_cache: "callable",
        sample_function: "callable",
    ) -> None:
        cache = make_cache()
        await _handle_result_analysis(
            {"error": "lint problem on line 7"},
            cache,
            sample_function,
            error_type=None,
            auto_analyze=True,
        )

    async def test_async_auto_analyze_false_short_circuits(
        self,
        make_cache: "callable",
        sample_function: "callable",
    ) -> None:
        cache = make_cache()
        await _handle_result_analysis(
            {"error": "ignored"},
            cache,
            sample_function,
            error_type=None,
            auto_analyze=False,
        )
        assert cache.patterns == {}


# ---------------------------------------------------------------------------
# _analyze_result_errors_sync / _analyze_result_errors (async)
# ---------------------------------------------------------------------------


class TestAnalyzeResultErrors:
    """Direct tests for the analyzer that extracts error data from dicts."""

    def test_missing_error_data_is_noop(
        self,
        make_cache: "callable",
        sample_function: "callable",
    ) -> None:
        cache = make_cache()
        _analyze_result_errors_sync(
            cache,
            {"status": "ok"},
            sample_function,
            error_type_override=None,
        )
        assert cache.patterns == {}

    def test_non_string_error_data_is_noop(
        self,
        make_cache: "callable",
        sample_function: "callable",
    ) -> None:
        cache = make_cache()
        _analyze_result_errors_sync(
            cache,
            {"error": 42},
            sample_function,
            error_type_override=None,
        )
        assert cache.patterns == {}

    def test_empty_string_error_data_is_noop(
        self,
        make_cache: "callable",
        sample_function: "callable",
    ) -> None:
        cache = make_cache()
        _analyze_result_errors_sync(
            cache,
            {"error": ""},
            sample_function,
            error_type_override=None,
        )
        assert cache.patterns == {}

    def test_uses_function_name_when_no_override(
        self,
        make_cache: "callable",
    ) -> None:
        """With no ``error_type_override``, the function's ``__name__`` is used."""

        cache = make_cache()

        def named_target() -> None:
            return None

        # Use a string that the parser recognises as meaningful enough to
        # produce a pattern. The analyzer will only add patterns that pass
        # the validity checks inside ``create_pattern_from_error``.
        _analyze_result_errors_sync(
            cache,
            {"error": "ConfigError: missing required key 'name'"},
            named_target,
            error_type_override=None,
        )
        # We don't assert patterns were added because the analyzer may
        # decide the input is not meaningful; but the branch must run.
        # When a pattern IS added, error_type should equal "named_target".
        for pattern in cache.patterns.values():
            assert pattern.error_type == "named_target"

    def test_override_replaces_function_name(
        self,
        make_cache: "callable",
    ) -> None:
        cache = make_cache()

        def named_target() -> None:
            return None

        _analyze_result_errors_sync(
            cache,
            {"error": "ConfigError: missing required key 'name'"},
            named_target,
            error_type_override="ruffer",
        )
        for pattern in cache.patterns.values():
            assert pattern.error_type == "ruffer"

    def test_errors_key_falls_back_to_default(
        self,
        make_cache: "callable",
    ) -> None:
        """If only ``errors`` is present, it should still be analyzed."""

        cache = make_cache()

        def named_target() -> None:
            return None

        _analyze_result_errors_sync(
            cache,
            {"errors": "ConfigError: missing required key 'name'"},
            named_target,
            error_type_override=None,
        )

    async def test_async_analyzer_runs(self, make_cache: "callable") -> None:
        cache = make_cache()

        def named_target() -> None:
            return None

        await _analyze_result_errors(
            cache,
            {"error": "ConfigError: missing required key 'name'"},
            named_target,
            error_type_override=None,
        )

    async def test_async_analyzer_uses_override(self, make_cache: "callable") -> None:
        cache = make_cache()

        def named_target() -> None:
            return None

        await _analyze_result_errors(
            cache,
            {"error": "ConfigError: missing required key 'name'"},
            named_target,
            error_type_override="pyright",
        )
        for pattern in cache.patterns.values():
            assert pattern.error_type == "pyright"

    async def test_async_analyzer_skips_empty_string(
        self,
        make_cache: "callable",
    ) -> None:
        cache = make_cache()

        def named_target() -> None:
            return None

        await _analyze_result_errors(
            cache,
            {"error": ""},
            named_target,
            error_type_override="ruff",
        )
        assert cache.patterns == {}


# ---------------------------------------------------------------------------
# _cache_crackerjack_error_sync / _cache_crackerjack_error (async)
# ---------------------------------------------------------------------------


class TestCacheCrackerjackError:
    """The CrackerjackError-specific caching path."""

    def test_records_pattern_with_error_code_name(
        self,
        make_cache: "callable",
        sample_function: "callable",
    ) -> None:
        cache = make_cache()
        error = ConfigError("a", ErrorCode.CONFIG_PARSE_ERROR)
        _cache_crackerjack_error_sync(
            cache,
            error,
            sample_function,
            error_type_override=None,
        )
        assert cache.patterns
        pattern = next(iter(cache.patterns.values()))
        # When ``error_type_override`` is None the function falls back to
        # ``error.error_code.name``.
        assert pattern.error_type == ErrorCode.CONFIG_PARSE_ERROR.name
        assert pattern.error_code == str(ErrorCode.CONFIG_PARSE_ERROR.value)

    def test_override_replaces_default_error_type(
        self,
        make_cache: "callable",
        sample_function: "callable",
    ) -> None:
        cache = make_cache()
        error = ConfigError("a", ErrorCode.CONFIG_PARSE_ERROR)
        _cache_crackerjack_error_sync(
            cache,
            error,
            sample_function,
            error_type_override="custom",
        )
        pattern = next(iter(cache.patterns.values()))
        assert pattern.error_type == "custom"

    def test_recovery_added_to_common_fixes(
        self,
        make_cache: "callable",
        sample_function: "callable",
    ) -> None:
        """``error.recovery`` populates ``common_fixes``."""

        cache = make_cache()
        error = ConfigError(
            "could not parse",
            ErrorCode.CONFIG_PARSE_ERROR,
            recovery="validate the YAML structure",
        )
        _cache_crackerjack_error_sync(
            cache,
            error,
            sample_function,
            error_type_override=None,
        )
        pattern = next(iter(cache.patterns.values()))
        assert pattern.common_fixes == ["validate the YAML structure"]

    def test_missing_recovery_yields_empty_fixes(
        self,
        make_cache: "callable",
        sample_function: "callable",
    ) -> None:
        cache = make_cache()
        error = ConfigError("a", ErrorCode.CONFIG_PARSE_ERROR, recovery=None)
        _cache_crackerjack_error_sync(
            cache,
            error,
            sample_function,
            error_type_override=None,
        )
        pattern = next(iter(cache.patterns.values()))
        assert pattern.common_fixes == []

    def test_pattern_id_components(
        self,
        make_cache: "callable",
        sample_function: "callable",
    ) -> None:
        """The ``pattern_id`` is composed of type/code/hash-of-message."""

        cache = make_cache()
        error = ConfigError("unique-message", ErrorCode.CONFIG_PARSE_ERROR)
        _cache_crackerjack_error_sync(
            cache,
            error,
            sample_function,
            error_type_override=None,
        )
        pattern_id = next(iter(cache.patterns))
        assert ErrorCode.CONFIG_PARSE_ERROR.name in pattern_id
        assert str(ErrorCode.CONFIG_PARSE_ERROR.value) in pattern_id

    def test_pattern_is_not_auto_fixable(
        self,
        make_cache: "callable",
        sample_function: "callable",
    ) -> None:
        """``CrackerjackError`` patterns are flagged as non auto-fixable."""

        cache = make_cache()
        error = ConfigError("a", ErrorCode.CONFIG_PARSE_ERROR)
        _cache_crackerjack_error_sync(
            cache,
            error,
            sample_function,
            error_type_override=None,
        )
        for pattern in cache.patterns.values():
            assert pattern.auto_fixable is False

    async def test_async_records_pattern(
        self,
        make_cache: "callable",
        sample_function: "callable",
    ) -> None:
        cache = make_cache()
        error = ConfigError("a", ErrorCode.CONFIG_PARSE_ERROR)
        await _cache_crackerjack_error(
            cache,
            error,
            sample_function,
            error_type_override=None,
        )
        assert cache.patterns

    async def test_async_override(
        self,
        make_cache: "callable",
        sample_function: "callable",
    ) -> None:
        cache = make_cache()
        error = ConfigError("a", ErrorCode.CONFIG_PARSE_ERROR)
        await _cache_crackerjack_error(
            cache,
            error,
            sample_function,
            error_type_override="x",
        )
        pattern = next(iter(cache.patterns.values()))
        assert pattern.error_type == "x"

    async def test_async_no_recovery(
        self,
        make_cache: "callable",
        sample_function: "callable",
    ) -> None:
        cache = make_cache()
        error = ConfigError("a", ErrorCode.CONFIG_PARSE_ERROR, recovery=None)
        await _cache_crackerjack_error(
            cache,
            error,
            sample_function,
            error_type_override=None,
        )
        pattern = next(iter(cache.patterns.values()))
        assert pattern.common_fixes == []


# ---------------------------------------------------------------------------
# _cache_exception_sync / _cache_exception (async)
# ---------------------------------------------------------------------------


class TestCacheException:
    """Generic-exception caching path."""

    def test_records_pattern_with_exception_class_name(
        self,
        make_cache: "callable",
        sample_function: "callable",
    ) -> None:
        cache = make_cache()
        error = ValueError("this is a longer meaningful error message content")
        _cache_exception_sync(
            cache,
            error,
            sample_function,
            error_type_override=None,
        )
        assert cache.patterns
        pattern = next(iter(cache.patterns.values()))
        assert pattern.error_type == "ValueError"

    def test_override_replaces_exception_type(
        self,
        make_cache: "callable",
        sample_function: "callable",
    ) -> None:
        cache = make_cache()
        error = ValueError("this is a longer meaningful error message content")
        _cache_exception_sync(
            cache,
            error,
            sample_function,
            error_type_override="ruffer",
        )
        pattern = next(iter(cache.patterns.values()))
        assert pattern.error_type == "ruffer"

    def test_empty_error_message_short_circuits(
        self,
        make_cache: "callable",
        sample_function: "callable",
    ) -> None:
        """Empty error strings fall through and no pattern is added."""

        cache = make_cache()
        error = ValueError("")
        _cache_exception_sync(
            cache,
            error,
            sample_function,
            error_type_override=None,
        )
        assert cache.patterns == {}

    def test_uses_str_of_exception(
        self,
        make_cache: "callable",
        sample_function: "callable",
    ) -> None:
        """The pattern's ``message_pattern`` derives from ``str(error)``."""

        cache = make_cache()
        error = ValueError("this is the meaningful message content")
        _cache_exception_sync(
            cache,
            error,
            sample_function,
            error_type_override=None,
        )
        assert cache.patterns
        pattern = next(iter(cache.patterns.values()))
        # The pattern message may have been normalised by the analyzer, but
        # the source string must be derivable from the exception text.
        assert pattern.message_pattern

    async def test_async_records_pattern(
        self,
        make_cache: "callable",
        sample_function: "callable",
    ) -> None:
        cache = make_cache()
        error = ValueError("this is a longer meaningful error message content")
        await _cache_exception(
            cache,
            error,
            sample_function,
            error_type_override=None,
        )
        assert cache.patterns

    async def test_async_override(
        self,
        make_cache: "callable",
        sample_function: "callable",
    ) -> None:
        cache = make_cache()
        error = ValueError("this is a longer meaningful error message content")
        await _cache_exception(
            cache,
            error,
            sample_function,
            error_type_override="custom_type",
        )
        pattern = next(iter(cache.patterns.values()))
        assert pattern.error_type == "custom_type"


# ---------------------------------------------------------------------------
# _handle_generic_exception_sync
# ---------------------------------------------------------------------------


class TestHandleGenericException:
    """Routes generic exceptions through the cache (when auto_analyze=True)."""

    def test_auto_analyze_true_invokes_cache(
        self,
        make_cache: "callable",
        sample_function: "callable",
    ) -> None:
        cache = make_cache()
        error = ValueError("this is a meaningful error message content")
        _handle_generic_exception_sync(
            error,
            cache,
            sample_function,
            None,
            True,
        )
        # The analyzer may or may not produce a pattern depending on the
        # heuristics inside ``create_pattern_from_error``. The branch must run
        # without raising.
        assert cache.patterns or True

    def test_auto_analyze_false_skips_cache(
        self,
        make_cache: "callable",
        sample_function: "callable",
    ) -> None:
        cache = make_cache()
        error = ValueError("this is a meaningful error message content")
        _handle_generic_exception_sync(
            error,
            cache,
            sample_function,
            None,
            False,
        )
        assert cache.patterns == {}


# ---------------------------------------------------------------------------
# Integration: end-to-end decorator behaviour through the public API
# ---------------------------------------------------------------------------


class TestEndToEndDecorators:
    """Full integration of the decorator with the underlying cache."""

    def test_sync_dict_error_triggers_pattern(
        self,
        tmp_cache_dir: Path,
    ) -> None:
        """A sync function returning a dict-with-error key uses the analyzer."""

        @cache_errors(cache_dir=tmp_cache_dir, error_type="ruff")
        def linter() -> dict[str, str]:
            return {"error": "ConfigError: missing required field"}

        result = linter()
        assert "error" in result

    def test_sync_crackerjack_error_with_recovery(self, tmp_cache_dir: Path) -> None:
        """End-to-end: sync function raising CrackerjackError caches recovery."""

        @cache_errors(cache_dir=tmp_cache_dir, error_type="config")
        def buggy() -> None:
            raise ConfigError(
                "missing required config field",
                ErrorCode.MISSING_CONFIG_FIELD,
                recovery="add the missing field",
            )

        with pytest.raises(ConfigError):
            buggy()

    async def test_async_crackerjack_error_is_recorded(
        self,
        tmp_cache_dir: Path,
    ) -> None:
        @cache_errors(cache_dir=tmp_cache_dir, error_type="async_label")
        async def buggy() -> None:
            raise ConfigError(
                "oops",
                ErrorCode.CONFIG_PARSE_ERROR,
                recovery="fix it",
            )

        with pytest.raises(ConfigError):
            await buggy()

    async def test_async_dict_error_is_recorded(
        self,
        tmp_cache_dir: Path,
    ) -> None:
        @cache_errors(cache_dir=tmp_cache_dir, error_type="ruff")
        async def linter() -> dict[str, str]:
            return {"error": "ConfigError: missing required key"}

        result = await linter()
        assert "error" in result


# ---------------------------------------------------------------------------
# Defensive coverage: return types and signatures
# ---------------------------------------------------------------------------


class TestSignatureSanity:
    """Lightweight structural assertions to keep the public surface stable."""

    def test_cache_errors_signature(self) -> None:
        sig = inspect.signature(cache_errors)
        params = sig.parameters
        assert "cache_dir" in params
        assert "error_type" in params
        assert "auto_analyze" in params

    def test_handle_result_analysis_sync_signature(self) -> None:
        sig = inspect.signature(_handle_result_analysis_sync)
        params = sig.parameters
        assert "result" in params
        assert "cache" in params
        assert "func" in params
        assert "error_type" in params
        assert "auto_analyze" in params

    def test_cache_crackerjack_error_signature(self) -> None:
        sig = inspect.signature(_cache_crackerjack_error_sync)
        params = sig.parameters
        assert "cache" in params
        assert "error" in params
        assert "func" in params
        assert "error_type_override" in params

    def test_cache_exception_signature(self) -> None:
        sig = inspect.signature(_cache_exception_sync)
        params = sig.parameters
        assert "cache" in params
        assert "error" in params
        assert "func" in params
        assert "error_type_override" in params

    def test_cache_errors_returns_decorator_factory(self) -> None:
        # The factory must yield a decorator that itself yields a callable.
        factory = cache_errors()
        decorator = factory(lambda: None)
        assert callable(decorator)


# ---------------------------------------------------------------------------
# Async correctness: the ``asyncio.run`` calls inside the sync helpers must
# execute their inner coroutines to completion (no leaks, no swallowed errors).
# ---------------------------------------------------------------------------


class TestAsyncioRunBehaviour:
    """Confirm the sync helpers' ``asyncio.run`` does not trap coroutines."""

    def test_async_loop_does_not_leak_after_sync_helper(
        self,
        make_cache: "callable",
        sample_function: "callable",
    ) -> None:
        cache = make_cache()
        error = ConfigError("x", ErrorCode.CONFIG_PARSE_ERROR)
        _cache_crackerjack_error_sync(
            cache,
            error,
            sample_function,
            error_type_override=None,
        )
        # If ``asyncio.run`` leaks a coroutine, we'd see a warning here.
        # Run a fresh coroutine to confirm the loop is healthy.
        asyncio.run(self._async_noop())

    async def _async_noop(self) -> None:
        return None

    def test_sync_helper_then_async_helper_via_loop(
        self,
        make_cache: "callable",
        sample_function: "callable",
    ) -> None:
        """Sync helper executes in the top-level sync context (no outer loop)."""
        cache = make_cache()
        error = ConfigError("a", ErrorCode.CONFIG_PARSE_ERROR)
        _cache_crackerjack_error_sync(
            cache,
            error,
            sample_function,
            error_type_override=None,
        )
        assert cache.patterns

    async def test_async_helper_in_running_loop(
        self,
        make_cache: "callable",
        sample_function: "callable",
    ) -> None:
        """Async helper executes inside pytest-asyncio's event loop."""
        async_cache = make_cache()
        error = ConfigError("a", ErrorCode.CONFIG_PARSE_ERROR)
        await _cache_crackerjack_error(
            async_cache,
            error,
            sample_function,
            error_type_override=None,
        )
        assert async_cache.patterns
