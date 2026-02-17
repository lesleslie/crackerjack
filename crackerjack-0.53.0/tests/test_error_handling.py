from __future__ import annotations

import subprocess
from typing import Never

from crackerjack.decorators.error_handling_decorators import (
    handle_file_errors,
    handle_subprocess_errors,
    handle_validation_errors,
)


def test_handle_subprocess_errors_returns_default() -> None:
    @handle_subprocess_errors(default_return="fallback", log_error=False)
    def run() -> Never:
        raise subprocess.CalledProcessError(1, ["echo", "fail"])

    assert run() == "fallback"


def test_handle_file_errors_reraises_without_default() -> None:
    @handle_file_errors(default_return=None, log_error=False)
    def read() -> Never:
        msg = "missing"
        raise FileNotFoundError(msg)

    try:
        read()
    except FileNotFoundError:
        pass
    else:
        msg = "Expected FileNotFoundError to be re-raised"
        raise AssertionError(msg)


def test_handle_validation_errors_returns_default() -> None:
    @handle_validation_errors(default_return=0, log_error=False)
    def parse(value):
        if not isinstance(value, int):
            msg = "invalid"
            raise TypeError(msg)
        return value

    assert parse("bad") == 0
