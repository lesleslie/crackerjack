"""Guard test: no first-party import path may shadow an excluded dependency.

Creosote decides whether a declared dependency is used by looking for its
name as an element of the dotted path of every import in the package:

    for imp in imports:
        if not imp.module and import_name in imp.name:      # import a.b.c
            ...
        elif imp.name and import_name in imp.module:        # from a.b import c
            ...

An excluded dependency is one that is *never* imported by name -- a
Rust binary invoked as an external CLI, a test-only plugin, a stub
distribution. The exclusion is what stops creosote reporting it as an
unused dependency.

The two facts interact. If the package itself contains a module whose
dotted path ends in a path element equal to an excluded dependency's
name, creosote concludes that the distribution *is* imported, and then
reports the exclusion itself as redundant:

    Redundant exclusion 'ty': import detected in source code

That happened here. ``crackerjack/adapters/type/ty.py`` -- the adapter
for the ``ty`` type checker -- put ``ty`` in the import path of every
``from crackerjack.adapters.type.ty import ...`` statement, which
satisfied the third-party ``ty`` distribution. The exclusion for ``ty``
became unreachable, the comprehensive stage failed, and the autofixer
was one keystroke away from deleting a legitimate exclusion.

The fix was to rename the module to ``ty_adapter.py``. This test pins
the invariant so the next module that shadows a distribution name is
caught here rather than by a failing quality gate.
"""

from __future__ import annotations

import ast
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PACKAGE_DIR = ROOT / "crackerjack"


def _excluded_dependencies() -> set[str]:
    """Return the canonicalized names in ``[tool.creosote].exclude-deps``.

    Canonicalization mirrors creosote's own ``canonicalize_module_name``:
    hyphens and dots become underscores, and the comparison is
    case-insensitive.
    """
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    excluded = pyproject["tool"]["creosote"]["exclude-deps"]
    return {name.replace("-", "_").replace(".", "_").lower() for name in excluded}


def _matchable_path_elements(python_file: Path) -> set[str]:
    """Return the path elements creosote could match a dependency against.

    Mirrors creosote's import model exactly:

    - ``import a.b.c`` contributes ``a``, ``b``, ``c``
    - ``from a.b import c`` contributes ``a``, ``b`` (its module path)
    - ``from . import c`` contributes ``c`` (no module path to match on)
    - ``from .ty import c`` contributes ``ty`` (a relative module path
      still produces a path element)
    """
    tree = ast.parse(
        python_file.read_text(encoding="utf-8"),
        filename=str(python_file),
    )

    elements: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                elements.update(alias.name.split("."))
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                elements.update(node.module.split("."))
            else:
                for alias in node.names:
                    elements.update(alias.name.split("."))
    return elements


def test_no_excluded_dependency_is_shadowed_by_an_import_path() -> None:
    excluded = _excluded_dependencies()

    violations: list[str] = []
    for python_file in sorted(PACKAGE_DIR.rglob("*.py")):
        shadowed = sorted(_matchable_path_elements(python_file) & excluded)
        if shadowed:
            relative = python_file.relative_to(ROOT)
            violations.append(f"{relative}: {', '.join(shadowed)}")

    assert not violations, (
        "First-party import paths shadow excluded dependency names. Creosote "
        "would resolve these distributions as 'imported', report their "
        "exclude-deps entries as redundant, and fail the comprehensive "
        "stage. Rename the shadowing module so its dotted path contains no "
        "path element equal to an excluded dependency name.\n\n"
        + "\n".join(violations)
    )
