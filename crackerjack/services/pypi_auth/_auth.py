from __future__ import annotations

import logging
import typing as t

logger = logging.getLogger(__name__)


def _validate_pypi_token(value: str) -> None:
    if not value:
        msg = "PyPI token must be a non-empty string"
        raise ValueError(msg)
    if not value.startswith("pypi-"):
        msg = f"PyPI token must start with 'pypi-' (got {value[:8]!r})"
        raise ValueError(msg)
    if len(value) < 16:
        msg = f"PyPI token must be at least 16 characters (got {len(value)})"
        raise ValueError(msg)


class PyPIAuth:

    __slots__ = ("_value", "_source")

    def __init__(self, value: str, source: str = "unknown") -> None:
        _validate_pypi_token(value)
        self._value = value
        self._source = source

    def as_uv_publish_token(self) -> str:
        return self._value

    def is_trusted_publishing(self) -> bool:
        return False

    def source(self) -> str:
        return self._source

    def __repr__(self) -> str:
        return f"<PyPIAuth source={self._source}>"

    def __str__(self) -> str:
        return self.__repr__()

    def __eq__(self, other: object) -> bool:
        return self is other

    def __hash__(self) -> int:
        return id(self)

    def __reduce__(self) -> t.NoReturn:
        raise TypeError("PyPIAuth instances cannot be pickled")


class PyPIAuthProvider(t.Protocol):

    name: str

    def is_available(self) -> bool: ...

    def resolve(self) -> PyPIAuth | None: ...


def discover_auth(
    providers: t.Sequence[PyPIAuthProvider] | None = None,
) -> tuple[PyPIAuth | None, list[PyPIAuthProvider]]:
    if providers is None:
        from crackerjack.services.pypi_auth._providers import (
            EnvVarAuthProvider,
            KeyringAuthProvider,
        )
        from crackerjack.services.pypi_auth._trusted_publishing import (
            TrustedPublishingProvider,
        )

        providers = [
            TrustedPublishingProvider(),
            EnvVarAuthProvider(),
            KeyringAuthProvider(),
        ]

    for provider in providers:
        try:
            if not provider.is_available():
                logger.debug(
                    "PyPI auth provider %r unavailable, skipping",
                    provider.name,
                )
                continue
            auth = provider.resolve()
        except Exception:
            logger.exception(
                "PyPI auth provider %r raised during resolve()",
                provider.name,
            )
            continue
        if auth is not None:
            logger.debug("PyPI auth resolved via %r", provider.name)
            return auth, list(providers)

    return None, list(providers)
