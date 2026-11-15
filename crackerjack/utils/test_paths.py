"""Recognise paths that live in a test suite rather than in shipped code.

The convention is not crackerjack's invention -- it is already the one the
rest of the toolchain uses:

* ``TestManager.has_tests`` looks for ``tests``/``test`` directories.
* The ``cohesion``, ``bandit`` and ``pyright`` sections of a repository's
  ``pyproject.toml`` exclude ``tests/``.
* Ruff's own ``exclude`` lists ``tests/`` alongside the test-file name
  patterns.

Only the *directory* rule is applied here. The file-name patterns
(``test_*.py``, ``*_test.py``) are deliberately not: several packages
carry production modules under those names -- crackerjack's own
``managers/test_progress.py``, ``managers/test_executor.py`` and
``managers/test_command_builder.py`` are shipped code, not tests. A test
suite lives in a directory; a file name is not a reliable signal.
"""

from __future__ import annotations

TEST_DIR_NAMES: frozenset[str] = frozenset({"tests", "test"})


def is_test_path(path: str) -> bool:
    """True when ``path`` lives under a test directory.

    A path counts as a test path when any of its directory components is
    named ``tests`` or ``test``. The file name itself is not part of the
    rule: ``managers/test_progress.py`` is production code.
    """
    normalized = path.replace("\\", "/")
    parts = [part for part in normalized.split("/") if part not in ("", ".")]
    if not parts:
        return False

    return any(part in TEST_DIR_NAMES for part in parts[:-1])
