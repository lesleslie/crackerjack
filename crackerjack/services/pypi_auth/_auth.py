from __future__ import annotations

import logging
import typing as t

logger = logging.getLogger(__name__)


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


class PyPIAuth:
    """Opaque PyPI credential wrapper.

    The constructor is the only place a raw ``str`` becomes a
    :class:`PyPIAuth`. Once constructed, the credential is opaque:
    consumers must call :meth:`as_uv_publish_token` to extract it,
    which is the explicit acknowledgment that the value is about to
    be handled outside the safety boundary.

    Equality and hashing are by identity only. Pickling is rejected
    via :meth:`__reduce__`. ``__repr__`` and ``__str__`` never include
    the token bytes. Subclasses may override :meth:`source` to label
    the provenance for banner output.
    """

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
    """Sentinel returned by TrustedPublishingProvider.

    The value here is NOT a real PyPI token — it is a placeholder that
    passes the constructor's format check so the rest of the publish
    pipeline can treat it uniformly. The publish manager recognizes
    ``is_trusted_publishing() == True`` and switches to
    ``uv publish --trusted-publishing`` instead of injecting an env var.
    """

    def __init__(self) -> None:


        super().__init__("pypi-trusted-publishing-placeholder-do-not-use")

    def as_uv_publish_token(self) -> str:
        # Defense-in-depth: callers must check ``is_trusted_publishing()`` and
        # route to ``uv publish --trusted-publishing always`` instead. If a
        # future caller forgets and pipes this placeholder to PyPI, fail
        # loudly rather than silently producing a meaningless 401.
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
    """Structural protocol for a PyPI credential source.

    A downstream plugin can add a new provider by satisfying this
    protocol — no registration required. The class itself never needs
    to be imported; only the three members matter.
    """

    name: str

    def is_available(self) -> bool: ...

    def resolve(self) -> PyPIAuth | None: ...


def discover_auth(
    providers: t.Sequence[PyPIAuthProvider] | None = None,
) -> tuple[PyPIAuth | None, list[PyPIAuthProvider]]:
    """Run providers in priority order; return first successful auth.

    Returns a tuple ``(auth_or_None, providers_checked)`` where the
    second element is the ordered list of providers that were actually
    queried (``is_available`` was called and either resolved or was
    unavailable). Providers that come AFTER a successful one in the
    input list are NOT included in the checked list — they were never
    queried. This lets callers render a banner like "Checked: TP"
    rather than overstating what happened.

    If ``providers`` is None, the default list is
    ``[TrustedPublishingProvider(), EnvVarAuthProvider(),
    KeyringAuthProvider()]`` — order matters; trusted publishing is
    preferred over ambient credentials.
    """
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
