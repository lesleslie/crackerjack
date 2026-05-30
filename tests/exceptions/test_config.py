from __future__ import annotations

from crackerjack.exceptions.config import ConfigIntegrityError


def test_config_integrity_error_is_exception_subclass() -> None:
    assert issubclass(ConfigIntegrityError, Exception)


def test_config_integrity_error_can_be_raised() -> None:
    try:
        raise ConfigIntegrityError("bad config")
    except ConfigIntegrityError as exc:
        assert str(exc) == "bad config"
