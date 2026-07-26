from __future__ import annotations

import logging
import re
import typing as t

logger = logging.getLogger(__name__)


_PYPI_TOKEN_RE = re.compile(r"^pypi-[A-Za-z0-9_-]+$")


def _validate_pypi_token(value: str) -> None:
    if not value:
        msg = "PyPI token must be a non-empty string"
        raise ValueError(msg)
    if not value.startswith("pypi-"):
        msg = "PyPI token must start with 'pypi-'"
        raise ValueError(msg)
    if len(value) < 16:
        msg = "PyPI token must be at least 16 characters"
        raise ValueError(msg)
    if not _PYPI_TOKEN_RE.match(value):
        msg = (
            "PyPI token must contain only ASCII letters, digits, '-',"
            " or '_' after the 'pypi-' prefix"
        )
        raise ValueError(msg)


class PyPIAuth:
    __slots__ = ("_value",)

    def __init__(self, value: str) -> None:
        _validate_pypi_token(value)
        self._value = value

    def as_uv_publish_token(self) -> str:
        return self._value

    def is_trusted_publishing(self) -> bool:
        return False

    def source(self) -> str:
        return "unknown"

    def __repr__(self) -> str:
        return f"<PyPIAuth source={self.source()}>"

    def __str__(self) -> str:
        return self.__repr__()

    def __eq__(self, other: object) -> bool:
        return self is other

    def __hash__(self) -> int:
        return id(self)

    def __reduce__(self) -> t.NoReturn:
        raise TypeError("PyPIAuth instances cannot be pickled")


class _TrustedPublishingSentinel(PyPIAuth):
    def __init__(self) -> None:

        super().__init__("pypi-trusted-publishing-placeholder-do-not-use")

    def as_uv_publish_token(self) -> str:

        msg = (
            "TrustedPublishingSentinel has no token; use is_trusted_publishing()"
            " to branch into the OIDC publish path instead"
        )
        raise RuntimeError(msg)

    def is_trusted_publishing(self) -> bool:
        return True

    def source(self) -> str:
        return "trusted-publishing"


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

    checked: list[PyPIAuthProvider] = []
    for provider in providers:
        checked.append(provider)
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
            return auth, checked

    return None, checked
