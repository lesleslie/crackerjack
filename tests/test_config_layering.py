"""The config package must not reach into the services layer.

A configuration that imports a service is a layering edge that runs
the wrong way: the services layer reads the configuration, so the edge
closes a loop. The frontmatter vocabulary used to sit in
``crackerjack.services.frontmatter`` and the settings imported it from
there, which was the only such edge the config package had. The
vocabulary now lives in the neutral ``crackerjack.core`` package, and
this test keeps it there.
"""

from __future__ import annotations

from pathlib import Path

import crackerjack


def test_no_config_module_imports_from_the_services_layer() -> None:
    """The edge stays closed.

    A new import of ``crackerjack.services`` in the config package
    would close the loop again: the services layer reads the
    configuration, so the configuration cannot read the services layer
    back.
    """
    config_dir = Path(crackerjack.__file__).parent / "config"

    offenders = [
        f"{path.relative_to(config_dir.parent)}:{lineno}"
        for path in sorted(config_dir.rglob("*.py"))
        for lineno, line in enumerate(path.read_text().splitlines(), 1)
        if "crackerjack.services" in line
    ]

    assert offenders == [], (
        "the config package must not import from the services layer: "
        + ", ".join(offenders)
    )


def test_the_vocabulary_lives_in_the_neutral_package() -> None:
    """The vocabulary is importable without the services layer.

    Importing it must not pull the settings in behind it, or the
    layering is only a rename: the neutral package's ``__init__`` is
    empty for exactly this reason.
    """
    import subprocess
    import sys

    probe = (
        "from crackerjack.core.lifecycle import ARCHIVABLE_STATUSES; "
        "assert ARCHIVABLE_STATUSES"
    )
    result = subprocess.run(
        [sys.executable, "-c", probe],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
