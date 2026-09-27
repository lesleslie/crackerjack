"""CI guard: keep version stamps in lockstep with pyproject.toml.

Mirrors ``akosha/tests/unit/test_version_sync.py`` (commit 3203ea2) +
mahavishnu/session-buddy counterparts. Crackerjack already implements
the single-source-of-truth contract natively:

- ``crackerjack/__init__.py:97`` uses the bare ``importlib.metadata.version()``
  oneiric form (crackerjack/__init__.py:28 import).
- ``crackerjack/mcp/server_core.py:13-16`` uses the defensive try/except
  form with sentinel ``"0.0.0-unknown"``.

This guard verifies runtime parity and pins the crackerjack-specific
fallback sentinel so future maintainers don't drift crackerjack's
contract to a different sentinel.
"""

from __future__ import annotations

import importlib.util
import re
from importlib import metadata
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[2]

# Crackerjack uses ``0.0.0-unknown`` rather than the PEP 440 ``0+unknown``
# sentinel the other Bodai core components adopted (see
# ``akosha/akosha/__init__.py`` and ``mahavishnu/mahavishnu/__init__.py``).
# This guard pins it so a future cosmetic refactor doesn't accidentally
# align crackerjack with the rest of the ecosystem; the sentinel
# choice is documented in ``crackerjack/mcp/server_core.py``.
_CRACKERJACK_FALLBACK_VERSION = "0.0.0-unknown"


def _read_pyproject_version() -> str:
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    if not match:
        pytest.fail("pyproject.toml does not contain a version field")
    return match.group(1)


def test_pyproject_version_is_canonical() -> None:
    version = _read_pyproject_version()
    assert re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version), (
        f"pyproject version {version!r} is not a valid PEP 440 stamp"
    )


def test_runtime_equals_metadata_version() -> None:
    """``crackerjack.__version__`` must equal ``metadata.version('crackerjack')``.

    Crackerjack uses the bare oneiric form ``version('crackerjack')``
    in ``crackerjack/__init__.py``; no fallback. The MCP server module
    has its own defensive try/except (``mcp/server_core.py:13-16``).
    """
    import crackerjack

    assert crackerjack.__version__ == metadata.version("crackerjack"), (
        f"crackerjack.__version__={crackerjack.__version__!r} "
        f"diverged from installed metadata "
        f"{metadata.version('crackerjack')!r}"
    )


def test_mcp_server_core_falls_back_to_canonical_sentinel() -> None:
    """``crackerjack.mcp.server_core.__version__`` falls back to ``0.0.0-unknown``.

    Sub-package (``mcp/server_core``) uses the defensive try/except
    form — verifying the sentinel string stays stable guards against
    silent breakage of any health probes that key on the version.

    Implementation: uses :func:`runpy.run_module` (not
    ``importlib.util.spec_from_file_location``) so the module loads
    with its real package context (``crackerjack.mcp.server_core``),
    which makes the ``from .context import`` relative import succeed
    and exercises the full module body — including its
    ``importlib.metadata.version`` lookup under a packaged path.

    The side_effect only fires for ``"crackerjack"`` lookups so that
    transitive imports of ``fastmcp`` / ``mcp_common`` / ``rich`` /
    ``crackerjack.api`` (which chain through the same
    ``importlib.metadata.version`` entry point during module import)
    succeed normally.
    """
    import runpy

    def _filter_side_effect(distribution_name: str) -> str:
        if distribution_name == "crackerjack":
            raise metadata.PackageNotFoundError
        # Sentinel return for non-crackerjack lookups (during transitive
        # imports). Value doesn't matter — the real lookup is unaffected
        # outside this patch; the test only inspects ``fresh.__version__``.
        return "999.0.0"

    fresh_globals: dict[str, object] = {}

    with patch("importlib.metadata.version", side_effect=_filter_side_effect):
        exec_globals = runpy.run_module(
            "crackerjack.mcp.server_core",
            run_name="__main__",
            init_globals=None,
        )
        fresh_globals.update(exec_globals or {})

    assert fresh_globals.get("__version__") == _CRACKERJACK_FALLBACK_VERSION, (
        f"MCP server core fallback returned "
        f"{fresh_globals.get('__version__')!r}; expected "
        f"crackerjack-specific sentinel "
        f"{_CRACKERJACK_FALLBACK_VERSION!r} when metadata is unavailable"
    )


def test_no_hardcoded_version_literals() -> None:
    """Regression: no hardcoded ``X.Y.Z`` version stamps in package code.

    Crackerjack's ``mcp/server_core.py:15`` contains a fallback
    ``"0.0.0-unknown"`` literal — that string is intentionally NOT
    matched by ``X.Y.Z`` regex (the format is sentinel-shaped, not a
    PEP 440 release version) and should not trip this guard. The
    patterns/operations/versioning test-fixtures contain
    ``'__version__ = \"1.2.3\"'`` literals as TEST DATA for the
    string-replacement tool — those live under ``crackerjack/services/patterns/``
    and are the tool's source data, NOT real version stamps. Allow
    them by directory exclusion.
    """
    package_root = ROOT / "crackerjack"
    offenders: list[tuple[str, str]] = []
    literal_pattern = re.compile(
        r"""(?:__version__|APP_VERSION|SERVICE_VERSION)\s*[:=]\s*["']"""
        r"""(\d+\.\d+(?:\.\d+)?)["']"""
    )
    skip_dirs = {"patterns", "__pycache__", "services/patterns"}
    for py_file in sorted(package_root.rglob("*.py")):
        if "__pycache__" in py_file.parts:
            continue
        if any(part in skip_dirs for part in py_file.parts):
            continue
        text = py_file.read_text(encoding="utf-8")
        for match in literal_pattern.finditer(text):
            offenders.append((str(py_file.relative_to(ROOT)), match.group(1)))
    assert not offenders, (
        f"Hardcoded version literals re-introduced drift: {offenders}"
    )
