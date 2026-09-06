"""Unit tests for ``crackerjack.decorators.error_handling_decorators``.

These tests target the seven file-error handling decorators exported by
``crackerjack.decorators.error_handling_decorators``:

* :func:`handle_file_errors`
* :func:`handle_json_errors`
* :func:`handle_subprocess_errors`
* :func:`handle_validation_errors`
* :func:`handle_network_errors`
* :func:`handle_all_errors`
* :func:`retry_on_error`

Behavior verified per decorator:

* Successful execution returns the wrapped function's value untouched.
* The configured exception types are caught (and either re-raised or
  swallowed into ``default_return`` depending on the parameters).
* Unrelated exceptions pass straight through unmodified.
* The log call format (and suppression) matches the implementation.

The decorators all import ``from loguru import logger`` at module scope, so
the tests patch ``crackerjack.decorators.error_handling_decorators.logger``
rather than the global ``loguru.logger`` symbol — that's the symbol the
wrappers actually resolve at call time.
"""

from __future__ import annotations

import json
import subprocess
import time as time_module
from collections.abc import Iterator
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from crackerjack.decorators import error_handling_decorators as ehd


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def patched_logger(monkeypatch: pytest.MonkeyPatch) -> Iterator[MagicMock]:
    """Replace the module-level ``logger`` with a ``MagicMock`` for the test.

    Yields the mock so tests can assert on ``logger.error.call_args`` etc.
    """
    mock = MagicMock(name="logger")
    monkeypatch.setattr(ehd, "logger", mock)
    yield mock


def _make(value: Any = "ok", exc: Exception | None = None) -> Any:
    """Build a function that returns ``value`` or raises ``exc``."""

    def _inner() -> Any:
        if exc is not None:
            raise exc
        return value

    return _inner


# ---------------------------------------------------------------------------
# handle_file_errors
# ---------------------------------------------------------------------------


class TestHandleFileErrors:
    """Behavior of :func:`handle_file_errors`."""

    def test_returns_value_when_no_error(self, patched_logger: MagicMock) -> None:
        func = ehd.handle_file_errors()(_make(value="payload"))

        assert func() == "payload"
        patched_logger.error.assert_not_called()

    @pytest.mark.parametrize(
        "exc",
        [
            FileNotFoundError("missing.txt"),
            PermissionError("denied"),
            OSError(5, "io"),
            IsADirectoryError("/tmp/dir"),
            BlockingIOError(11, "blocked"),
        ],
    )
    def test_catches_configured_exceptions(self, exc: Exception) -> None:
        decorator = ehd.handle_file_errors()

        with pytest.raises(type(exc)) as excinfo:
            decorator(_make(exc=exc))()

        # The decorator should pass through the original exception unchanged.
        assert excinfo.value is exc

    def test_does_not_catch_unrelated_exception(self, patched_logger: MagicMock) -> None:
        decorator = ehd.handle_file_errors()

        # ValueError is not part of the configured tuple → propagate raw.
        with pytest.raises(ValueError, match="not for me"):
            decorator(_make(exc=ValueError("not for me")))()

        patched_logger.error.assert_not_called()

    def test_returns_default_when_provided(
        self,
        patched_logger: MagicMock,
    ) -> None:
        decorator = ehd.handle_file_errors(default_return="fallback")

        result = decorator(_make(exc=FileNotFoundError("missing")))()

        assert result == "fallback"
        patched_logger.error.assert_called_once()

    def test_logs_message_when_no_default_return(
        self,
        patched_logger: MagicMock,
    ) -> None:
        decorator = ehd.handle_file_errors()

        with pytest.raises(FileNotFoundError):
            decorator(_make(exc=FileNotFoundError("nope")))()

        patched_logger.error.assert_called_once()
        msg = patched_logger.error.call_args.args[0]
        assert "File operation failed" in msg
        assert "nope" in msg

    def test_log_error_false_suppresses_log(self, patched_logger: MagicMock) -> None:
        decorator = ehd.handle_file_errors(log_error=False)

        with pytest.raises(FileNotFoundError):
            decorator(_make(exc=FileNotFoundError("nope")))()

        patched_logger.error.assert_not_called()

    def test_reraise_false_with_default_return(self, patched_logger: MagicMock) -> None:
        # ``reraise=False`` should swallow even though the default is None.
        decorator = ehd.handle_file_errors(default_return=None, reraise=False)

        result = decorator(_make(exc=FileNotFoundError("nope")))()

        assert result is None
        patched_logger.error.assert_called_once()

    def test_wraps_preserves_function_metadata(self) -> None:
        @ehd.handle_file_errors()
        def my_func() -> str:
            """My docstring."""

            return "x"

        assert my_func.__name__ == "my_func"
        assert my_func.__doc__ == "My docstring."

    def test_custom_exception_tuple(self, patched_logger: MagicMock) -> None:
        # Caller can supply a different exception tuple; FileNotFoundError
        # is no longer in the catch set, so it must propagate raw.
        decorator = ehd.handle_file_errors(exceptions=(ValueError,))

        with pytest.raises(FileNotFoundError):
            decorator(_make(exc=FileNotFoundError("missing")))()

        patched_logger.error.assert_not_called()

    def test_passes_args_and_kwargs(self) -> None:
        @ehd.handle_file_errors()
        def add(a: int, b: int = 0) -> int:
            return a + b

        assert add(1, 2) == 3
        assert add(a=5) == 5


# ---------------------------------------------------------------------------
# handle_json_errors
# ---------------------------------------------------------------------------


class TestHandleJsonErrors:
    """Behavior of :func:`handle_json_errors`."""

    def test_returns_value_when_no_error(self, patched_logger: MagicMock) -> None:
        func = ehd.handle_json_errors()(_make(value={"ok": 1}))

        assert func() == {"ok": 1}
        patched_logger.error.assert_not_called()

    @pytest.mark.parametrize(
        "exc",
        [
            json.JSONDecodeError("msg", "doc", 0),
            ValueError("invalid literal"),
            TypeError("not iterable"),
        ],
    )
    def test_catches_configured_exceptions(self, exc: Exception) -> None:
        decorator = ehd.handle_json_errors()

        with pytest.raises(type(exc)):
            decorator(_make(exc=exc))()

    def test_does_not_catch_oserror(self, patched_logger: MagicMock) -> None:
        decorator = ehd.handle_json_errors()

        with pytest.raises(OSError):
            decorator(_make(exc=OSError(2, "no such file")))()

        patched_logger.error.assert_not_called()

    def test_returns_default_when_provided(self, patched_logger: MagicMock) -> None:
        decorator = ehd.handle_json_errors(default_return={})

        result = decorator(_make(exc=json.JSONDecodeError("bad", "x", 0)))()

        assert result == {}
        patched_logger.error.assert_called_once()

    def test_logs_message(self, patched_logger: MagicMock) -> None:
        decorator = ehd.handle_json_errors()

        with pytest.raises(ValueError):
            decorator(_make(exc=ValueError("oops")))()

        patched_logger.error.assert_called_once()
        msg = patched_logger.error.call_args.args[0]
        assert "JSON operation failed" in msg
        assert "oops" in msg

    def test_log_error_false(self, patched_logger: MagicMock) -> None:
        decorator = ehd.handle_json_errors(log_error=False)

        with pytest.raises(ValueError):
            decorator(_make(exc=ValueError("silent")))()

        patched_logger.error.assert_not_called()


# ---------------------------------------------------------------------------
# handle_subprocess_errors
# ---------------------------------------------------------------------------


class TestHandleSubprocessErrors:
    """Behavior of :func:`handle_subprocess_errors`."""

    def test_returns_value_when_no_error(self, patched_logger: MagicMock) -> None:
        func = ehd.handle_subprocess_errors()(_make(value="rc=0"))

        assert func() == "rc=0"
        patched_logger.error.assert_not_called()

    def test_catches_called_process_error(self, patched_logger: MagicMock) -> None:
        decorator = ehd.handle_subprocess_errors()
        cpe = subprocess.CalledProcessError(returncode=1, cmd=["ls"])

        with pytest.raises(subprocess.CalledProcessError):
            decorator(_make(exc=cpe))()

        patched_logger.error.assert_called_once()

    def test_catches_timeout_expired(self, patched_logger: MagicMock) -> None:
        decorator = ehd.handle_subprocess_errors()
        timeout_err = subprocess.TimeoutExpired(cmd=["ls"], timeout=5.0)

        with pytest.raises(subprocess.TimeoutExpired):
            decorator(_make(exc=timeout_err))()

        patched_logger.error.assert_called_once()

    def test_does_not_catch_value_error(self, patched_logger: MagicMock) -> None:
        decorator = ehd.handle_subprocess_errors()

        with pytest.raises(ValueError):
            decorator(_make(exc=ValueError("not for me")))()

        patched_logger.error.assert_not_called()

    def test_returns_default_when_provided(self, patched_logger: MagicMock) -> None:
        decorator = ehd.handle_subprocess_errors(default_return="failed")

        result = decorator(_make(exc=subprocess.TimeoutExpired(cmd=["ls"], timeout=1)))()

        assert result == "failed"
        patched_logger.error.assert_called_once()

    def test_logs_message(self, patched_logger: MagicMock) -> None:
        decorator = ehd.handle_subprocess_errors()

        with pytest.raises(subprocess.CalledProcessError):
            decorator(_make(exc=subprocess.CalledProcessError(0, [])))()

        msg = patched_logger.error.call_args.args[0]
        assert "Subprocess operation failed" in msg


# ---------------------------------------------------------------------------
# handle_validation_errors
# ---------------------------------------------------------------------------


class TestHandleValidationErrors:
    """Behavior of :func:`handle_validation_errors`."""

    def test_returns_value_when_no_error(self, patched_logger: MagicMock) -> None:
        func = ehd.handle_validation_errors()(_make(value=42))

        assert func() == 42
        patched_logger.error.assert_not_called()

    @pytest.mark.parametrize(
        "exc",
        [
            ValueError("bad value"),
            TypeError("bad type"),
            AttributeError("no attr"),
        ],
    )
    def test_catches_configured_exceptions(self, exc: Exception) -> None:
        decorator = ehd.handle_validation_errors()

        with pytest.raises(type(exc)):
            decorator(_make(exc=exc))()

    def test_does_not_catch_oserror(self, patched_logger: MagicMock) -> None:
        decorator = ehd.handle_validation_errors()

        with pytest.raises(OSError):
            decorator(_make(exc=OSError(2, "no")))()

        patched_logger.error.assert_not_called()

    def test_logs_message(self, patched_logger: MagicMock) -> None:
        decorator = ehd.handle_validation_errors()

        with pytest.raises(ValueError):
            decorator(_make(exc=ValueError("nope")))()

        msg = patched_logger.error.call_args.args[0]
        assert "Validation failed" in msg
        assert "nope" in msg

    def test_returns_default_when_provided(self, patched_logger: MagicMock) -> None:
        decorator = ehd.handle_validation_errors(default_return=False)

        result = decorator(_make(exc=TypeError("oops")))()

        assert result is False
        patched_logger.error.assert_called_once()


# ---------------------------------------------------------------------------
# handle_network_errors
# ---------------------------------------------------------------------------


class TestHandleNetworkErrors:
    """Behavior of :func:`handle_network_errors`.

    The implementation catches ``ConnectionError``, ``ConnectionRefusedError``,
    and ``TimeoutError``. Note that ``ConnectionRefusedError`` is a subclass of
    ``OSError`` but not ``ConnectionError`` in stdlib — both are caught here.
    """

    def test_returns_value_when_no_error(self, patched_logger: MagicMock) -> None:
        func = ehd.handle_network_errors()(_make(value="ok"))

        assert func() == "ok"
        patched_logger.error.assert_not_called()

    @pytest.mark.parametrize(
        "exc",
        [
            ConnectionError("refused"),
            ConnectionRefusedError("refused"),
            TimeoutError("slow"),
        ],
    )
    def test_catches_configured_exceptions(self, exc: Exception) -> None:
        decorator = ehd.handle_network_errors()

        with pytest.raises(type(exc)):
            decorator(_make(exc=exc))()

    def test_does_not_catch_value_error(self, patched_logger: MagicMock) -> None:
        decorator = ehd.handle_network_errors()

        with pytest.raises(ValueError):
            decorator(_make(exc=ValueError("nope")))()

        patched_logger.error.assert_not_called()

    def test_returns_default_when_provided(self, patched_logger: MagicMock) -> None:
        decorator = ehd.handle_network_errors(default_return={"status": "down"})

        result = decorator(_make(exc=ConnectionError("down")))()

        assert result == {"status": "down"}
        patched_logger.error.assert_called_once()

    def test_logs_message(self, patched_logger: MagicMock) -> None:
        decorator = ehd.handle_network_errors()

        with pytest.raises(TimeoutError):
            decorator(_make(exc=TimeoutError("slow")))()

        msg = patched_logger.error.call_args.args[0]
        assert "Network operation failed" in msg


# ---------------------------------------------------------------------------
# handle_all_errors
# ---------------------------------------------------------------------------


class TestHandleAllErrors:
    """Behavior of :func:`handle_all_errors`."""

    def test_returns_value_when_no_error(self, patched_logger: MagicMock) -> None:
        func = ehd.handle_all_errors()(_make(value="ok"))

        assert func() == "ok"
        patched_logger.error.assert_not_called()

    def test_catches_generic_exception_and_reraises(
        self,
        patched_logger: MagicMock,
    ) -> None:
        decorator = ehd.handle_all_errors()

        with pytest.raises(RuntimeError):
            decorator(_make(exc=RuntimeError("boom")))()

        patched_logger.error.assert_called_once()

    def test_reraises_keyboard_interrupt(self, patched_logger: MagicMock) -> None:
        decorator = ehd.handle_all_errors()

        with pytest.raises(KeyboardInterrupt):
            decorator(_make(exc=KeyboardInterrupt()))()

        # KeyboardInterrupt must NOT be swallowed and NOT be logged.
        patched_logger.error.assert_not_called()

    def test_reraises_system_exit(self, patched_logger: MagicMock) -> None:
        decorator = ehd.handle_all_errors()

        with pytest.raises(SystemExit):
            decorator(_make(exc=SystemExit(1)))()

        patched_logger.error.assert_not_called()

    def test_returns_default_when_provided(self, patched_logger: MagicMock) -> None:
        decorator = ehd.handle_all_errors(default_return="graceful")

        result = decorator(_make(exc=RuntimeError("boom")))()

        assert result == "graceful"
        patched_logger.error.assert_called_once()

    def test_reraise_false_with_default(self, patched_logger: MagicMock) -> None:
        decorator = ehd.handle_all_errors(reraise=False, default_return=None)

        result = decorator(_make(exc=RuntimeError("boom")))()

        assert result is None
        patched_logger.error.assert_called_once()

    def test_logs_unexpected_error_message(self, patched_logger: MagicMock) -> None:
        decorator = ehd.handle_all_errors()

        with pytest.raises(RuntimeError):
            decorator(_make(exc=RuntimeError("something broke")))()

        msg = patched_logger.error.call_args.args[0]
        assert "Unexpected error" in msg
        assert "something broke" in msg

    def test_log_error_false_suppresses_log(self, patched_logger: MagicMock) -> None:
        decorator = ehd.handle_all_errors(log_error=False)

        with pytest.raises(RuntimeError):
            decorator(_make(exc=RuntimeError("silent")))()

        patched_logger.error.assert_not_called()

    def test_custom_exclude(self, patched_logger: MagicMock) -> None:
        # Custom exclude tuple takes precedence over the default behavior.
        decorator = ehd.handle_all_errors(exclude=(ValueError,))

        with pytest.raises(ValueError):
            decorator(_make(exc=ValueError("excluded")))()

        patched_logger.error.assert_not_called()


# ---------------------------------------------------------------------------
# retry_on_error
# ---------------------------------------------------------------------------


class TestRetryOnError:
    """Behavior of :func:`retry_on_error`.

    The implementation sleeps between attempts via ``time.sleep``. To keep the
    test suite fast, ``time.sleep`` is patched globally on the module under
    test using :func:`unittest.mock.patch`.
    """

    def test_succeeds_first_attempt(self, patched_logger: MagicMock) -> None:
        with patch.object(time_module, "sleep") as mock_sleep:
            decorator = ehd.retry_on_error()
            func = decorator(_make(value="ok"))

            assert func() == "ok"

            # No sleep should be issued on the first successful attempt.
            mock_sleep.assert_not_called()

        patched_logger.warning.assert_not_called()
        patched_logger.error.assert_not_called()

    def test_succeeds_after_retry(self, patched_logger: MagicMock) -> None:
        calls: list[int] = []

        def flaky() -> str:
            calls.append(len(calls))
            if len(calls) < 3:
                raise ValueError("not yet")
            return "ok"

        with patch.object(time_module, "sleep") as mock_sleep:
            decorator = ehd.retry_on_error(max_attempts=3, delay=0.01)
            result = decorator(flaky)()

            assert result == "ok"
            # Sleep should fire once between attempts 1 and 2, and once
            # between attempts 2 and 3.
            assert mock_sleep.call_count == 2

        assert patched_logger.warning.call_count == 2
        # No "all attempts failed" error since the function eventually succeeded.
        patched_logger.error.assert_not_called()

    def test_gives_up_after_max_attempts(self, patched_logger: MagicMock) -> None:
        attempts: list[int] = []

        def always_fail() -> None:
            attempts.append(1)
            raise ValueError("always")

        with patch.object(time_module, "sleep") as mock_sleep:
            decorator = ehd.retry_on_error(max_attempts=3, delay=0.01)
            with pytest.raises(ValueError, match="always"):
                decorator(always_fail)()

            # Sleeps should fire between retries, not after the final attempt.
            assert mock_sleep.call_count == 2

        assert len(attempts) == 3
        # Warnings fire only for attempts that will be retried (2), then
        # a single terminal "All 3 attempts failed" error. This avoids
        # duplicate noise — the final attempt is silenced because the
        # loop-exit error already reports the failure.
        assert patched_logger.warning.call_count == 2
        final_msg = patched_logger.error.call_args.args[0]
        assert "All 3 attempts failed" in final_msg

    def test_does_not_retry_on_unrelated_exception(
        self,
        patched_logger: MagicMock,
    ) -> None:
        attempts: list[int] = []

        def odd_error() -> None:
            attempts.append(1)
            raise KeyError("not configured")  # type: ignore[misc]

        decorator = ehd.retry_on_error(
            max_attempts=3,
            exceptions=(ValueError,),
        )

        with patch.object(time_module, "sleep") as mock_sleep:
            with pytest.raises(KeyError):
                decorator(odd_error)()

            mock_sleep.assert_not_called()

        assert len(attempts) == 1
        patched_logger.warning.assert_not_called()
        patched_logger.error.assert_not_called()

    def test_backoff_increases_delay(self, patched_logger: MagicMock) -> None:
        with patch.object(time_module, "sleep") as mock_sleep:
            decorator = ehd.retry_on_error(
                max_attempts=3,
                delay=1.0,
                backoff=2.0,
            )
            with pytest.raises(ValueError):
                decorator(_make(exc=ValueError("boom")))()

            # First sleep = 1.0, second sleep = 1.0 * 2.0 = 2.0.
            sleep_values = [c.args[0] for c in mock_sleep.call_args_list]
            assert sleep_values == [1.0, 2.0]

    def test_log_retry_false_suppresses_warnings(
        self,
        patched_logger: MagicMock,
    ) -> None:
        with patch.object(time_module, "sleep"):
            decorator = ehd.retry_on_error(
                max_attempts=2,
                delay=0.0,
                log_retry=False,
            )
            with pytest.raises(ValueError):
                decorator(_make(exc=ValueError("nope")))()

        # Per-attempt warnings are suppressed.
        patched_logger.warning.assert_not_called()
        # The terminal "all attempts failed" error is always logged when the
        # loop exhausts (independent of log_retry).
        patched_logger.error.assert_called_once()

    def test_warning_includes_attempt_numbers(self, patched_logger: MagicMock) -> None:
        with patch.object(time_module, "sleep"):
            decorator = ehd.retry_on_error(max_attempts=3, delay=0.0)
            with pytest.raises(ValueError):
                decorator(_make(exc=ValueError("boom")))()

        # Warnings fire only for attempts that will be retried — the final
        # attempt is silenced because the loop exit already logs a
        # terminal "All N attempts failed..." error.
        warning_messages = [c.args[0] for c in patched_logger.warning.call_args_list]
        assert len(warning_messages) == 2
        assert any("Attempt 1/3" in msg for msg in warning_messages)
        assert any("Attempt 2/3" in msg for msg in warning_messages)
        # Final attempt (3/3) intentionally NOT warned — avoids duplicate noise.
        assert not any("Attempt 3/3" in msg for msg in warning_messages)

    def test_passes_args_and_kwargs(self) -> None:
        attempts: list[tuple[int, int]] = []

        @ehd.retry_on_error(max_attempts=2, delay=0.0)
        def add(a: int, b: int = 1) -> int:
            attempts.append((a, b))
            if len(attempts) < 2:
                raise ValueError("retry")
            return a + b

        with patch.object(time_module, "sleep"):
            assert add(2, 3) == 5

        assert attempts == [(2, 3), (2, 3)]

    def test_single_attempt_still_fails(self, patched_logger: MagicMock) -> None:
        with patch.object(time_module, "sleep") as mock_sleep:
            decorator = ehd.retry_on_error(max_attempts=1)
            with pytest.raises(ValueError):
                decorator(_make(exc=ValueError("once")))()

            # No sleeps when max_attempts is 1.
            mock_sleep.assert_not_called()

        # Single attempt never gets a "Retrying..." warning because
        # there's no retry to schedule — only the terminal error.
        assert patched_logger.warning.call_count == 0
        patched_logger.error.assert_called_once()

    def test_default_exception_is_exception(self, patched_logger: MagicMock) -> None:
        # The default `exceptions` tuple is `(Exception,)` which catches
        # almost everything but excludes ``BaseException`` subclasses such as
        # ``KeyboardInterrupt`` and ``SystemExit`` (they derive from
        # ``BaseException`` directly).
        attempts: list[int] = []

        def ctrl_c() -> None:
            attempts.append(1)
            raise KeyboardInterrupt()

        decorator = ehd.retry_on_error(max_attempts=3, delay=0.0)

        with patch.object(time_module, "sleep") as mock_sleep:
            with pytest.raises(KeyboardInterrupt):
                decorator(ctrl_c)()

            mock_sleep.assert_not_called()

        assert len(attempts) == 1


# ---------------------------------------------------------------------------
# __all__ export surface
# ---------------------------------------------------------------------------


class TestModuleExports:
    """Static assertions about the public surface of the module."""

    def test_all_exports(self) -> None:
        expected = {
            "handle_all_errors",
            "handle_file_errors",
            "handle_json_errors",
            "handle_network_errors",
            "handle_subprocess_errors",
            "handle_validation_errors",
            "retry_on_error",
            "FunctionType",
        }
        assert set(ehd.__all__) == expected
