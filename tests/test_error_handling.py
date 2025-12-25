from __future__ import annotations

import subprocess

from crackerjack.decorators.error_handling_decorators import (
    handle_file_errors,
    handle_subprocess_errors,
    handle_validation_errors,
)


def test_handle_subprocess_errors_returns_default():
    @handle_subprocess_errors(default_return="fallback", log_error=False)
    def run():
        raise subprocess.CalledProcessError(1, ["echo", "fail"])

    assert run() == "fallback"


def test_handle_file_errors_reraises_without_default():
    @handle_file_errors(default_return=None, log_error=False)
    def read():
        raise FileNotFoundError("missing")

    try:
        read()
    except FileNotFoundError:
        pass
    else:
        raise AssertionError("Expected FileNotFoundError to be re-raised")


def test_handle_validation_errors_returns_default():
    @handle_validation_errors(default_return=0, log_error=False)
    def parse(value):
        if not isinstance(value, int):
            raise TypeError("invalid")
        return value

    assert parse("bad") == 0
