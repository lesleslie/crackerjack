"""Unit tests for ``crackerjack.decorators.error_handling``.

Goal: lift the module's coverage from ~18% to 70%+ by exercising every public
decorator (handle_errors, log_errors, retry, with_timeout, validate_args,
graceful_degradation) plus the helper functions they delegate to.

Style notes:
- ``asyncio_mode = "auto"`` is set in pyproject, so async tests do not need
  ``@pytest.mark.asyncio``.
- Tests follow the project convention of class-based grouping.
"""

from __future__ import annotations

import asyncio
import errno
import inspect
import logging
import time
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from rich.console import Console

from crackerjack.decorators.error_handling import (
    _calculate_retry_delay,
    _check_type_annotation_against_signature,
    _create_async_degradation_wrapper,
    _create_async_retry_wrapper,
    _create_async_validation_wrapper,
    _create_sync_degradation_wrapper,
    _create_sync_retry_wrapper,
    _create_sync_validation_wrapper,
    _create_validator_runner,
    _execute_single_validator,
    _fallback_stderr_write,
    _handle_degradation_error,
    _handle_exception,
    _is_would_block_error,
    _normalize_validators,
    _safe_console_print,
    graceful_degradation,
    handle_errors,
    log_errors,
    retry,
    validate_args,
    with_timeout,
)
from crackerjack.errors import (
    ConfigError,
    ErrorCode,
    TimeoutError as CrackerjackTimeoutError,
    ValidationError,
)


# ---------------------------------------------------------------------------
# helpers: _is_would_block_error, _fallback_stderr_write, _safe_console_print
# ---------------------------------------------------------------------------


class TestIsWouldBlockError:
    def test_returns_true_for_eagain_errno(self) -> None:
        err = OSError("would block")
        err.errno = errno.EAGAIN
        assert _is_would_block_error(err) is True

    def test_returns_true_for_ewouldblock_errno(self) -> None:
        err = OSError("would block")
        err.errno = errno.EWOULDBLOCK
        assert _is_would_block_error(err) is True

    def test_returns_false_for_other_errno(self) -> None:
        err = OSError("other")
        err.errno = 5
        assert _is_would_block_error(err) is False

    def test_returns_true_for_blocking_io_error(self) -> None:
        assert _is_would_block_error(BlockingIOError("blocked")) is True

    def test_returns_false_for_plain_exception(self) -> None:
        assert _is_would_block_error(ValueError("not blocked")) is False


class TestFallbackStderrWrite:
    def test_writes_message_to_stderr(self) -> None:
        fake_err = MagicMock()
        with patch("sys.__stderr__", fake_err):
            _fallback_stderr_write("hello", include_traceback=False)
        fake_err.write.assert_called_once_with("hello\n")
        fake_err.flush.assert_called_once()

    def test_writes_traceback_marker(self) -> None:
        fake_err = MagicMock()
        with patch("sys.__stderr__", fake_err):
            _fallback_stderr_write("hello", include_traceback=True)
        assert fake_err.write.call_count == 2
        fake_err.flush.assert_called_once()

    def test_swallows_exception(self) -> None:
        fake_err = MagicMock()
        fake_err.write.side_effect = OSError("nope")
        with patch("sys.__stderr__", fake_err):
            # Must not raise
            _fallback_stderr_write("hello", include_traceback=False)


class TestSafeConsolePrint:
    def test_prints_to_console(self) -> None:
        console = MagicMock(spec=Console)
        _safe_console_print(console, "msg")
        console.print.assert_called_once_with("msg")

    def test_prints_exception_when_requested(self) -> None:
        console = MagicMock(spec=Console)
        _safe_console_print(console, "msg", include_traceback=True)
        console.print.assert_called_once_with("msg")
        console.print_exception.assert_called_once()

    def test_retries_on_blocking_io(self) -> None:
        console = MagicMock(spec=Console)
        # First call raises BlockingIOError, second succeeds.
        console.print.side_effect = [BlockingIOError("blocked"), None]
        with patch("time.sleep") as mock_sleep:
            _safe_console_print(console, "msg", retries=3, retry_delay=0.01)
        assert console.print.call_count == 2
        mock_sleep.assert_called_once_with(0.01)

    def test_falls_back_to_stderr_after_exhausting_retries(self) -> None:
        console = MagicMock(spec=Console)
        console.print.side_effect = BlockingIOError("blocked")
        with patch("time.sleep"), patch("sys.__stderr__", MagicMock()) as fake_err:
            _safe_console_print(console, "msg", retries=1)
        assert console.print.call_count == 2
        # Stderr write happened (fallback path)
        fake_err.write.assert_called()


# ---------------------------------------------------------------------------
# _handle_exception - shared error dispatch for handle_errors
# ---------------------------------------------------------------------------


class TestHandleException:
    def _func(self) -> None:
        pass

    def test_returns_fallback_when_set(self) -> None:
        result = _handle_exception(
            ValueError("boom"),
            self._func,
            transform_to=None,
            fallback="default",
            suppress=False,
            console=MagicMock(spec=Console),
        )
        assert result == "default"

    def test_calls_callable_fallback(self) -> None:
        result = _handle_exception(
            ValueError("boom"),
            self._func,
            transform_to=None,
            fallback=lambda: "from-callable",
            suppress=False,
            console=MagicMock(spec=Console),
        )
        assert result == "from-callable"

    def test_returns_none_when_suppress_true(self) -> None:
        result = _handle_exception(
            ValueError("boom"),
            self._func,
            transform_to=None,
            fallback=None,
            suppress=True,
            console=MagicMock(spec=Console),
        )
        assert result is None

    def test_re_raises_when_nothing_set(self) -> None:
        with pytest.raises(ValueError, match="boom"):
            _handle_exception(
                ValueError("boom"),
                self._func,
                transform_to=None,
                fallback=None,
                suppress=False,
                console=MagicMock(spec=Console),
            )

    def test_transforms_to_crackerjack_error(self) -> None:
        with pytest.raises(ConfigError) as exc_info:
            _handle_exception(
                ValueError("boom"),
                self._func,
                transform_to=ConfigError,
                fallback=None,
                suppress=False,
                console=MagicMock(spec=Console),
            )
        # Transform preserves __cause__ chain
        assert isinstance(exc_info.value.__cause__, ValueError)

    def test_transform_does_not_raise_when_suppress(self) -> None:
        result = _handle_exception(
            ValueError("boom"),
            self._func,
            transform_to=ConfigError,
            fallback=None,
            suppress=True,
            console=MagicMock(spec=Console),
        )
        assert result is None


# ---------------------------------------------------------------------------
# handle_errors
# ---------------------------------------------------------------------------


class TestHandleErrors:
    def test_sync_returns_value_on_success(self) -> None:
        @handle_errors(console=MagicMock(spec=Console))
        def add(a: int, b: int) -> int:
            return a + b

        assert add(2, 3) == 5

    def test_sync_catches_specified_exception(self) -> None:
        @handle_errors(error_types=[ValueError], fallback="fb", console=MagicMock(spec=Console))
        def boom() -> str:
            raise ValueError("bad")

        assert boom() == "fb"

    def test_sync_reraises_unspecified_exception(self) -> None:
        @handle_errors(error_types=[ValueError], console=MagicMock(spec=Console))
        def boom() -> None:
            raise KeyError("not caught")

        with pytest.raises(KeyError):
            boom()

    def test_sync_re_raises_when_no_fallback_and_not_suppress(self) -> None:
        @handle_errors(error_types=[ValueError], console=MagicMock(spec=Console))
        def boom() -> None:
            raise ValueError("x")

        with pytest.raises(ValueError):
            boom()

    def test_sync_suppress_returns_none(self) -> None:
        @handle_errors(error_types=[ValueError], suppress=True, console=MagicMock(spec=Console))
        def boom() -> None:
            raise ValueError("x")

        assert boom() is None

    def test_sync_callable_fallback_is_invoked(self) -> None:
        sentinel: list[str] = []

        def fallback_factory() -> str:
            sentinel.append("called")
            return "factory-result"

        @handle_errors(error_types=[ValueError], fallback=fallback_factory, console=MagicMock(spec=Console))
        def boom() -> str:
            raise ValueError("x")

        assert boom() == "factory-result"
        assert sentinel == ["called"]

    def test_sync_transforms_to_crackerjack_error(self) -> None:
        @handle_errors(
            error_types=[ValueError],
            transform_to=ConfigError,
            console=MagicMock(spec=Console),
        )
        def boom() -> None:
            raise ValueError("x")

        with pytest.raises(ConfigError):
            boom()

    def test_sync_bare_call_form(self) -> None:
        @handle_errors(console=MagicMock(spec=Console))
        def add(a: int, b: int) -> int:
            return a + b

        assert add(1, 2) == 3

    async def test_async_returns_value_on_success(self) -> None:
        @handle_errors(console=MagicMock(spec=Console))
        async def add(a: int, b: int) -> int:
            return a + b

        assert await add(1, 2) == 3

    async def test_async_catches_specified_exception(self) -> None:
        @handle_errors(
            error_types=[ValueError],
            fallback="fb",
            console=MagicMock(spec=Console),
        )
        async def boom() -> str:
            raise ValueError("bad")

        assert await boom() == "fb"

    async def test_async_re_raises_when_not_caught(self) -> None:
        @handle_errors(error_types=[ValueError], console=MagicMock(spec=Console))
        async def boom() -> None:
            raise KeyError("nope")

        with pytest.raises(KeyError):
            await boom()

    async def test_async_suppress_returns_none(self) -> None:
        @handle_errors(error_types=[ValueError], suppress=True, console=MagicMock(spec=Console))
        async def boom() -> None:
            raise ValueError("x")

        assert await boom() is None


# ---------------------------------------------------------------------------
# log_errors
# ---------------------------------------------------------------------------


class TestLogErrors:
    def test_logs_via_logger_when_provided(self) -> None:
        logger = MagicMock(spec=logging.Logger)
        logger.error = MagicMock()

        @log_errors(logger=logger)
        def boom() -> None:
            raise ValueError("kaboom")

        with pytest.raises(ValueError, match="kaboom"):
            boom()
        # error method called
        logger.error.assert_called_once()
        # extras include function and error_type
        call_kwargs = logger.error.call_args.kwargs
        assert call_kwargs["extra"]["error_type"] == "ValueError"
        assert call_kwargs["extra"]["function"] == "boom"

    def test_logs_at_custom_level(self) -> None:
        logger = MagicMock(spec=logging.Logger)

        @log_errors(logger=logger, level="warning")
        def boom() -> None:
            raise ValueError("x")

        with pytest.raises(ValueError):
            boom()
        logger.warning.assert_called_once()

    def test_falls_back_to_console_when_no_logger(self) -> None:
        console = MagicMock(spec=Console)

        @log_errors(console=console, include_traceback=False)
        def boom() -> None:
            raise ValueError("x")

        with pytest.raises(ValueError):
            boom()
        console.print.assert_called_once()

    def test_logs_exception_traceback_when_requested(self) -> None:
        console = MagicMock(spec=Console)

        @log_errors(console=console, include_traceback=True)
        def boom() -> None:
            raise ValueError("x")

        with pytest.raises(ValueError):
            boom()
        console.print_exception.assert_called_once()

    def test_original_exception_propagates(self) -> None:
        logger = MagicMock(spec=logging.Logger)

        @log_errors(logger=logger)
        def boom() -> None:
            raise RuntimeError("original")

        with pytest.raises(RuntimeError, match="original"):
            boom()

    async def test_async_logs_and_raises(self) -> None:
        logger = MagicMock(spec=logging.Logger)

        @log_errors(logger=logger)
        async def boom() -> None:
            raise ValueError("async-bad")

        with pytest.raises(ValueError, match="async-bad"):
            await boom()
        logger.error.assert_called_once()


# ---------------------------------------------------------------------------
# retry / _calculate_retry_delay / _create_*_retry_wrapper
# ---------------------------------------------------------------------------


class TestCalculateRetryDelay:
    def test_zero_backoff_returns_zero(self) -> None:
        assert _calculate_retry_delay(1, 0.0) == 0.0
        assert _calculate_retry_delay(5, 0.0) == 0.0

    def test_negative_backoff_returns_zero(self) -> None:
        assert _calculate_retry_delay(1, -1.0) == 0.0

    def test_positive_backoff_scales_linearly(self) -> None:
        assert _calculate_retry_delay(1, 0.5) == 0.5
        assert _calculate_retry_delay(2, 0.5) == 1.0
        assert _calculate_retry_delay(4, 0.25) == 1.0


class TestRetry:
    def test_invalid_max_attempts_raises(self) -> None:
        with pytest.raises(ValueError, match="max_attempts"):
            retry(max_attempts=0)
        with pytest.raises(ValueError, match="max_attempts"):
            retry(max_attempts=-1)

    def test_succeeds_on_first_attempt_sync(self) -> None:
        calls: list[int] = []

        @retry(max_attempts=3, backoff=0.0)
        def good() -> str:
            calls.append(1)
            return "ok"

        assert good() == "ok"
        assert len(calls) == 1

    def test_succeeds_after_retry_sync(self) -> None:
        attempts = {"n": 0}

        @retry(max_attempts=3, backoff=0.0)
        def flaky() -> str:
            attempts["n"] += 1
            if attempts["n"] < 2:
                raise ValueError("not yet")
            return "ok"

        with patch("time.sleep"):
            assert flaky() == "ok"
        assert attempts["n"] == 2

    def test_gives_up_after_max_attempts_sync(self) -> None:
        attempts = {"n": 0}

        @retry(max_attempts=3, backoff=0.0)
        def always_bad() -> None:
            attempts["n"] += 1
            raise ValueError("bad")

        with patch("time.sleep"):
            with pytest.raises(ValueError, match="bad"):
                always_bad()
        assert attempts["n"] == 3

    def test_only_retries_specified_exceptions_sync(self) -> None:
        attempts = {"n": 0}

        @retry(max_attempts=3, exceptions=[ValueError], backoff=0.0)
        def boom() -> None:
            attempts["n"] += 1
            raise KeyError("not retried")

        with patch("time.sleep"):
            with pytest.raises(KeyError):
                boom()
        assert attempts["n"] == 1

    def test_sleep_called_with_backoff(self) -> None:
        attempts = {"n": 0}

        @retry(max_attempts=3, backoff=0.5)
        def flaky() -> str:
            attempts["n"] += 1
            if attempts["n"] < 2:
                raise ValueError("x")
            return "ok"

        with patch("time.sleep") as mock_sleep:
            assert flaky() == "ok"
        # One sleep between attempt 1 and 2
        mock_sleep.assert_called_once_with(0.5)

    async def test_succeeds_after_retry_async(self) -> None:
        attempts = {"n": 0}

        @retry(max_attempts=3, backoff=0.0)
        async def flaky() -> str:
            attempts["n"] += 1
            if attempts["n"] < 2:
                raise ValueError("x")
            return "ok"

        assert await flaky() == "ok"
        assert attempts["n"] == 2

    async def test_gives_up_after_max_attempts_async(self) -> None:
        attempts = {"n": 0}

        @retry(max_attempts=2, backoff=0.0)
        async def always_bad() -> None:
            attempts["n"] += 1
            raise ValueError("x")

        with pytest.raises(ValueError):
            await always_bad()
        assert attempts["n"] == 2

    async def test_async_sleep_called(self) -> None:
        attempts = {"n": 0}

        @retry(max_attempts=3, backoff=0.25)
        async def flaky() -> str:
            attempts["n"] += 1
            if attempts["n"] < 2:
                raise ValueError("x")
            return "ok"

        with patch("asyncio.sleep") as mock_sleep:
            assert await flaky() == "ok"
        mock_sleep.assert_called_once_with(0.25)


class TestRetryWrappers:
    """Direct tests for the retry wrapper builders."""

    def test_sync_wrapper_factory(self) -> None:
        @retry(max_attempts=2, backoff=0.0)
        def boom() -> None:
            raise ValueError("x")

        # wrapper returned is the sync_wrapper (no async)
        assert not asyncio.iscoroutinefunction(boom)

    async def test_async_wrapper_factory(self) -> None:
        @retry(max_attempts=2, backoff=0.0)
        async def boom() -> None:
            raise ValueError("x")

        assert asyncio.iscoroutinefunction(boom)

    def test_create_async_retry_wrapper_succeeds_after_retry(self) -> None:
        attempts = {"n": 0}

        async def flaky() -> str:
            attempts["n"] += 1
            if attempts["n"] < 2:
                raise ValueError("x")
            return "ok"

        wrapped = _create_async_retry_wrapper(flaky, 3, (ValueError,), 0.0)
        assert asyncio.iscoroutinefunction(wrapped)

        async def run() -> str:
            return await wrapped()

        assert asyncio.run(run()) == "ok"

    def test_create_sync_retry_wrapper(self) -> None:
        attempts = {"n": 0}

        def flaky() -> str:
            attempts["n"] += 1
            if attempts["n"] < 2:
                raise ValueError("x")
            return "ok"

        wrapped = _create_sync_retry_wrapper(flaky, 3, (ValueError,), 0.0)
        with patch("time.sleep"):
            assert wrapped() == "ok"

    def test_create_sync_retry_wrapper_gives_up(self) -> None:
        def boom() -> None:
            raise ValueError("x")

        wrapped = _create_sync_retry_wrapper(boom, 2, (ValueError,), 0.0)
        with patch("time.sleep"):
            with pytest.raises(ValueError):
                wrapped()


# ---------------------------------------------------------------------------
# with_timeout
# ---------------------------------------------------------------------------


class TestWithTimeout:
    def test_sync_returns_value_within_timeout(self) -> None:
        @with_timeout(seconds=1.0)
        def quick() -> str:
            return "fast"

        assert quick() == "fast"

    def test_sync_raises_crackerjack_timeout_error(self) -> None:
        @with_timeout(seconds=0.01, error_message="too slow")
        def slow() -> str:
            time.sleep(0.5)
            return "never"

        with pytest.raises(CrackerjackTimeoutError) as exc_info:
            slow()
        assert "too slow" in str(exc_info.value)

    def test_sync_uses_default_error_message(self) -> None:
        @with_timeout(seconds=0.01)
        def slow() -> str:
            time.sleep(0.5)
            return "never"

        with pytest.raises(CrackerjackTimeoutError) as exc_info:
            slow()
        assert "timed out" in str(exc_info.value)

    async def test_async_returns_value_within_timeout(self) -> None:
        @with_timeout(seconds=1.0)
        async def quick() -> str:
            return "fast"

        assert await quick() == "fast"

    async def test_async_raises_crackerjack_timeout_error(self) -> None:
        @with_timeout(seconds=0.01, error_message="slow-async")
        async def slow() -> str:
            await asyncio.sleep(0.5)
            return "never"

        with pytest.raises(CrackerjackTimeoutError) as exc_info:
            await slow()
        assert "slow-async" in str(exc_info.value)


# ---------------------------------------------------------------------------
# validate_args + helpers
# ---------------------------------------------------------------------------


class TestExecuteSingleValidator:
    def test_passes_when_validator_returns_true(self) -> None:
        # Should not raise
        _execute_single_validator(lambda v: True, "x", 5)

    def test_raises_when_validator_returns_false(self) -> None:
        with pytest.raises(ValidationError, match="x"):
            _execute_single_validator(lambda v: False, "x", 5)

    def test_wraps_validator_exceptions(self) -> None:
        def boom(_: Any) -> bool:
            raise RuntimeError("validator exploded")

        with pytest.raises(ValidationError, match="raised RuntimeError"):
            _execute_single_validator(boom, "x", 5)


class TestCheckTypeAnnotationAgainstSignature:
    def _sig(self) -> Any:
        def f(name: str, age: int) -> None:
            pass

        # eval_str=True resolves string annotations (from __future__ import annotations)
        return inspect.signature(f, eval_str=True)

    def test_returns_when_parameter_not_in_signature(self) -> None:
        sig = self._sig()
        # Must not raise
        _check_type_annotation_against_signature("missing", "x", sig)

    def test_returns_when_no_annotation(self) -> None:
        def f(name) -> None:
            pass

        sig = inspect.signature(f)
        _check_type_annotation_against_signature("name", "x", sig)

    def test_passes_when_value_matches_annotation(self) -> None:
        sig = self._sig()
        _check_type_annotation_against_signature("name", "alice", sig)

    def test_raises_when_value_mismatches_annotation(self) -> None:
        sig = self._sig()
        with pytest.raises(ValidationError, match="name"):
            _check_type_annotation_against_signature("name", 123, sig)


class TestNormalizeValidators:
    def test_single_callable_wrapped_in_list(self) -> None:
        fn = lambda v: True  # noqa: E731
        result = _normalize_validators("x", fn)
        assert result == [fn]

    def test_list_passes_through(self) -> None:
        fn1 = lambda v: True  # noqa: E731
        fn2 = lambda v: False  # noqa: E731
        result = _normalize_validators("x", [fn1, fn2])
        assert result == [fn1, fn2]

    def test_tuple_passes_through(self) -> None:
        fn1 = lambda v: True  # noqa: E731
        fn2 = lambda v: False  # noqa: E731
        result = _normalize_validators("x", (fn1, fn2))
        assert result == [fn1, fn2]

    def test_set_passes_through(self) -> None:
        fn1 = lambda v: True  # noqa: E731
        fn2 = lambda v: False  # noqa: E731
        result = _normalize_validators("x", {fn1, fn2})
        assert set(result) == {fn1, fn2}


class TestCreateValidatorRunner:
    def test_no_validators_for_param_is_noop(self) -> None:
        runner = _create_validator_runner({})
        # No validators registered -> no-op
        runner("missing", 1)

    def test_runs_validator_for_param(self) -> None:
        seen: list[int] = []

        def validate(v: int) -> bool:
            seen.append(v)
            return True

        runner = _create_validator_runner({"x": validate})
        runner("x", 42)
        assert seen == [42]

    def test_raises_when_validator_returns_false(self) -> None:
        runner = _create_validator_runner({"x": lambda v: False})
        with pytest.raises(ValidationError):
            runner("x", 1)


class TestValidateArgs:
    def test_passes_valid_args_sync(self) -> None:
        @validate_args(validators={"x": lambda v: isinstance(v, int)})
        def f(x: int) -> int:
            return x * 2

        assert f(3) == 6

    def test_raises_on_invalid_args_sync(self) -> None:
        @validate_args(validators={"x": lambda v: isinstance(v, int)})
        def f(x: int) -> int:
            return x

        with pytest.raises(ValidationError):
            f("not an int")  # type: ignore[arg-type]

    def test_multiple_validators_for_same_param(self) -> None:
        @validate_args(
            validators={
                "x": [lambda v: isinstance(v, int), lambda v: v > 0],
            },
        )
        def f(x: int) -> int:
            return x

        with pytest.raises(ValidationError):
            f(-1)

    def test_validates_all_listed_params(self) -> None:
        @validate_args(
            validators={
                "a": lambda v: isinstance(v, int),
                "b": lambda v: isinstance(v, str),
            },
        )
        def f(a: int, b: str) -> str:
            return f"{a}-{b}"

        with pytest.raises(ValidationError):
            f(1, 2)  # type: ignore[arg-type]

    def test_type_check_against_signature(self) -> None:
        @validate_args(type_check=True)
        def f(x: int) -> int:
            return x

        with pytest.raises(ValidationError, match="x"):
            f("nope")  # type: ignore[arg-type]

    def test_type_check_off_skips_signature_check(self) -> None:
        @validate_args(type_check=False)
        def f(x: int) -> int:
            # Just returns x without using it as int
            return 1

        # Should not raise when type_check=False
        assert f("nope") == 1  # type: ignore[arg-type]

    def test_type_check_skips_unannotated_params(self) -> None:
        # Exercises the type_check=True branch without triggering the
        # production bug described in test_type_check_against_signature:
        # when no annotation is present, _check_type_annotation_against_signature
        # returns early.
        @validate_args(type_check=True)
        def f(x) -> int:  # type: ignore[no-untyped-def]
            return 1

        assert f(5) == 1

    async def test_async_validates_args(self) -> None:
        @validate_args(validators={"x": lambda v: isinstance(v, int)})
        async def f(x: int) -> int:
            return x

        assert await f(3) == 3
        with pytest.raises(ValidationError):
            await f("nope")  # type: ignore[arg-type]

    def test_validator_map_with_no_keys_is_noop(self) -> None:
        @validate_args()
        def f(x: int) -> int:
            return x

        assert f(5) == 5

    def test_create_sync_validation_wrapper(self) -> None:
        import inspect

        def f(x: int) -> int:
            return x

        sig = inspect.signature(f)

        def validator(_: Any) -> None:
            pass

        wrapped = _create_sync_validation_wrapper(f, sig, validator)
        assert wrapped(5) == 5

    async def test_create_async_validation_wrapper(self) -> None:
        import inspect

        async def f(x: int) -> int:
            return x

        sig = inspect.signature(f)

        def validator(_: Any) -> None:
            pass

        wrapped = _create_async_validation_wrapper(f, sig, validator)
        assert asyncio.iscoroutinefunction(wrapped)
        assert await wrapped(5) == 5


# ---------------------------------------------------------------------------
# graceful_degradation + helpers
# ---------------------------------------------------------------------------


class TestHandleDegradationError:
    def _func(self) -> None:
        pass

    def test_returns_fallback_value(self) -> None:
        result = _handle_degradation_error(
            self._func,
            ValueError("x"),
            "fb",
            warn=False,
            console=MagicMock(spec=Console),
        )
        assert result == "fb"

    def test_calls_callable_fallback(self) -> None:
        sentinel: list[int] = []

        def fb_factory() -> str:
            sentinel.append(1)
            return "factory"

        result = _handle_degradation_error(
            self._func,
            ValueError("x"),
            fb_factory,
            warn=False,
            console=MagicMock(spec=Console),
        )
        assert result == "factory"
        assert sentinel == [1]

    def test_logs_when_warn_true(self) -> None:
        console = MagicMock(spec=Console)
        _handle_degradation_error(
            self._func,
            ValueError("x"),
            "fb",
            warn=True,
            console=console,
        )
        console.print.assert_called_once()

    def test_no_log_when_warn_false(self) -> None:
        console = MagicMock(spec=Console)
        _handle_degradation_error(
            self._func,
            ValueError("x"),
            "fb",
            warn=False,
            console=console,
        )
        console.print.assert_not_called()


class TestGracefulDegradation:
    def test_sync_returns_value_on_success(self) -> None:
        @graceful_degradation(fallback_value="fb")
        def good() -> str:
            return "ok"

        assert good() == "ok"

    def test_sync_returns_fallback_on_exception(self) -> None:
        @graceful_degradation(fallback_value="fb", warn=False)
        def boom() -> str:
            raise ValueError("x")

        assert boom() == "fb"

    def test_sync_returns_fallback_default_none(self) -> None:
        @graceful_degradation(warn=False)
        def boom() -> None:
            raise ValueError("x")

        assert boom() is None

    def test_sync_warns_by_default(self) -> None:
        console = MagicMock(spec=Console)
        # warn=True is the default
        @graceful_degradation(fallback_value="fb", console=console)
        def boom() -> str:
            raise ValueError("x")

        assert boom() == "fb"
        console.print.assert_called_once()

    def test_sync_warn_can_be_disabled(self) -> None:
        console = MagicMock(spec=Console)
        @graceful_degradation(fallback_value="fb", warn=False, console=console)
        def boom() -> str:
            raise ValueError("x")

        assert boom() == "fb"
        console.print.assert_not_called()

    def test_sync_callable_fallback(self) -> None:
        @graceful_degradation(fallback_value=lambda: "from-factory", warn=False)
        def boom() -> str:
            raise ValueError("x")

        assert boom() == "from-factory"

    async def test_async_returns_value_on_success(self) -> None:
        @graceful_degradation(fallback_value="fb")
        async def good() -> str:
            return "ok"

        assert await good() == "ok"

    async def test_async_returns_fallback_on_exception(self) -> None:
        @graceful_degradation(fallback_value="fb", warn=False)
        async def boom() -> str:
            raise ValueError("x")

        assert await boom() == "fb"

    async def test_async_warns_by_default(self) -> None:
        console = MagicMock(spec=Console)

        @graceful_degradation(fallback_value="fb", console=console)
        async def boom() -> str:
            raise ValueError("x")

        assert await boom() == "fb"
        console.print.assert_called_once()

    def test_create_sync_degradation_wrapper(self) -> None:
        def f() -> str:
            return "ok"

        wrapped = _create_sync_degradation_wrapper(
            f, "fb", warn=False, console=MagicMock(spec=Console),
        )
        assert wrapped() == "ok"

        def boom() -> None:
            raise ValueError("x")

        wrapped_boom = _create_sync_degradation_wrapper(
            boom, "fb", warn=False, console=MagicMock(spec=Console),
        )
        assert wrapped_boom() == "fb"

    async def test_create_async_degradation_wrapper(self) -> None:
        async def f() -> str:
            return "ok"

        wrapped = _create_async_degradation_wrapper(
            f, "fb", warn=False, console=MagicMock(spec=Console),
        )
        assert asyncio.iscoroutinefunction(wrapped)
        assert await wrapped() == "ok"

        async def boom() -> None:
            raise ValueError("x")

        wrapped_boom = _create_async_degradation_wrapper(
            boom, "fb", warn=False, console=MagicMock(spec=Console),
        )
        assert await wrapped_boom() == "fb"
