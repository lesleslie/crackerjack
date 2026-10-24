"""Run ``linkcheckmd`` with a raised HTTP response-header ceiling.

GitHub serves a ``Content-Security-Policy`` response header larger than
aiohttp's default 8190-byte ``max_field_size``. ``linkcheckmd`` builds its
``aiohttp.ClientSession`` without passing that ceiling, so aiohttp raises
``LineTooLong`` and surfaces it as a ``ClientResponseError`` -- an exception
type linkcheckmd's ``except`` clauses do not cover. Because ``asyncio.gather``
propagates the first exception it sees, a single oversized header aborts the
whole scan instead of reporting one bad link.

This module raises the ceiling before handing off to linkcheckmd's own CLI, so
the tool's exit-code and output contract is unchanged.
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from functools import wraps
from typing import Any

import aiohttp

# GitHub's CSP header runs roughly 9 KB; 64 KiB leaves generous headroom
# while still bounding what the response parser will accept.
MAX_FIELD_SIZE = 65536


@contextmanager
def _header_limit(limit: int = MAX_FIELD_SIZE) -> Generator[None]:
    """Default ``aiohttp.ClientSession.max_field_size`` to ``limit``.

    ``setdefault`` keeps an explicit ``max_field_size`` supplied by a caller
    authoritative; only linkcheckmd's own (absent) value is filled in. The
    original constructor is restored on exit.
    """
    original_init = aiohttp.ClientSession.__init__

    @wraps(original_init)
    def patched_init(self: Any, *args: Any, **kwargs: Any) -> None:
        kwargs.setdefault("max_field_size", limit)
        original_init(self, *args, **kwargs)

    # Deliberate runtime interop shim: the replacement constructor accepts a
    # superset of the original's arguments, which a static checker cannot see.
    aiohttp.ClientSession.__init__ = patched_init  # ty: ignore[invalid-assignment]
    try:
        yield
    finally:
        aiohttp.ClientSession.__init__ = original_init  # ty: ignore[invalid-assignment]


def main() -> None:
    """Raise the header ceiling, then delegate to linkcheckmd's CLI."""
    from linkcheckmd.__main__ import main as linkcheckmd_main

    with _header_limit():
        linkcheckmd_main()


if __name__ == "__main__":
    main()
