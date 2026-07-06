"""Tests for ``crackerjack.tools.ty_imports``.

Mechanical auto-fix for ty ``unresolved-reference`` errors that mean
"missing import". The resolver only handles the unambiguous case where
the missing symbol IS a module name (e.g. ``time``, ``pathlib``) or a
top-level public symbol of an installed stdlib/third-party module
(e.g. ``Path`` → ``pathlib``).

Out of scope:
- Symbols that would need to be re-exported from a private name
- Symbols from optional-dep packages that aren't installed
- Stub generation for missing modules

The design mirrors ``ty_cleanup``:
1. Parse ty output (concise) into ``FixSite`` records
2. Resolve each symbol to a candidate import line
3. Apply by inserting into the file's import block (idempotent)
"""

from __future__ import annotations

from pathlib import Path

from crackerjack.tools.ty_imports import (
    AUTO_FIX_CODES,
    ImportFix,
    apply_import_fix,
    parse_ty_unresolved_reference,
    resolve_symbol,
)

# ---------------------------------------------------------------------------
# parse_ty_unresolved_reference
# ---------------------------------------------------------------------------


class TestParseTyUnresolvedReference:
    """ty concise output looks like:
    ``path/to/file.py:LINE:COL: error[unresolved-reference] Name `X` used when not defined``
    """

    def test_parses_simple_stdlib_name(self) -> None:
        line = (
            "tests/conftest_extensions.py:344:90: "
            "error[unresolved-reference] Name `time` used when not defined"
        )
        site = parse_ty_unresolved_reference(line)
        assert site is not None
        assert site.symbol == "time"
        assert site.line == 344
        assert site.col == 90

    def test_parses_underscore_symbol(self) -> None:
        line = (
            "tests/test_foo.py:10:5: "
            "error[unresolved-reference] Name `get_git_tracked_files` "
            "used when not defined"
        )
        site = parse_ty_unresolved_reference(line)
        assert site is not None
        assert site.symbol == "get_git_tracked_files"
        assert site.line == 10

    def test_returns_none_for_other_codes(self) -> None:
        # unresolved-attribute is NOT an import problem (it's a union access issue)
        line = (
            "tests/adapters/test_foo.py:289:39: "
            "error[unresolved-attribute] Attribute `lower` is not defined "
            "on `None` in union `str | None`"
        )
        assert parse_ty_unresolved_reference(line) is None

    def test_returns_none_for_warnings(self) -> None:
        # We only fix errors, not warnings (lower bar for false positives)
        line = (
            "tests/test_foo.py:10:5: "
            "warning[unresolved-reference] Name `time` used when not defined"
        )
        assert parse_ty_unresolved_reference(line) is None

    def test_returns_none_for_garbage(self) -> None:
        assert parse_ty_unresolved_reference("not a ty line") is None
        assert parse_ty_unresolved_reference("") is None


# ---------------------------------------------------------------------------
# resolve_symbol
# ---------------------------------------------------------------------------


class TestResolveSymbolStdlib:
    """When the symbol IS a stdlib module name itself."""

    def test_time(self) -> None:
        fix = resolve_symbol("time")
        assert fix is not None
        assert fix.import_line == "import time"

    def test_os(self) -> None:
        fix = resolve_symbol("os")
        assert fix is not None
        assert fix.import_line == "import os"

    def test_sys(self) -> None:
        fix = resolve_symbol("sys")
        assert fix is not None
        assert fix.import_line == "import sys"


class TestResolveSymbolStdlibSubname:
    """When the symbol is a public attribute of a stdlib module."""

    def test_path(self) -> None:
        # `Path` lives in `pathlib`. Standard stdlib re-export.
        fix = resolve_symbol("Path")
        assert fix is not None
        assert fix.module == "pathlib"
        assert fix.import_line == "from pathlib import Path"

    def test_counter(self) -> None:
        # `Counter` lives in `collections`.
        fix = resolve_symbol("Counter")
        assert fix is not None
        assert fix.module == "collections"
        assert fix.import_line == "from collections import Counter"


class TestResolveSymbolUnresolvable:
    """Symbols we cannot or should not auto-resolve."""

    def test_builtin_returns_none(self) -> None:
        # `len` is a builtin; no import needed (ty shouldn't flag it,
        # but be defensive).
        assert resolve_symbol("len") is None

    def test_unknown_returns_none(self) -> None:
        assert resolve_symbol("ThisSymbolDoesNotExistAnywhere123") is None

    def test_private_module_attribute_returns_none(self) -> None:
        # We won't reach into private modules to grab names. If ty flagged
        # it, the LLM tier should handle it.
        assert resolve_symbol("_abc_init_unlikely_to_exist") is None


# ---------------------------------------------------------------------------
# apply_import_fix
# ---------------------------------------------------------------------------


class TestApplyImportFix:
    def _write(self, tmp_path: Path, content: str) -> Path:
        p = tmp_path / "module.py"
        p.write_text(content)
        return p

    def test_inserts_into_empty_file(self, tmp_path: Path) -> None:
        p = self._write(tmp_path, "x = 1\n")
        fix = ImportFix(module="time", import_line="import time", symbol="time")
        changed = apply_import_fix(p, fix)
        assert changed is True
        assert p.read_text() == "import time\n\nx = 1\n"

    def test_inserts_after_existing_imports(self, tmp_path: Path) -> None:
        p = self._write(tmp_path, "import os\n\nx = 1\n")
        fix = ImportFix(module="sys", import_line="import sys", symbol="sys")
        changed = apply_import_fix(p, fix)
        assert changed is True
        result = p.read_text()
        # `import sys` should come right after `import os`, not below the blank line
        assert "import os\nimport sys\n\nx = 1\n" == result

    def test_groups_with_same_kind_of_import(self, tmp_path: Path) -> None:
        p = self._write(tmp_path, "from pathlib import Path\n\nx = 1\n")
        fix = ImportFix(
            module="collections",
            import_line="from collections import Counter",
            symbol="Counter",
        )
        changed = apply_import_fix(p, fix)
        assert changed is True
        result = p.read_text()
        assert (
            result
            == "from pathlib import Path\nfrom collections import Counter\n\nx = 1\n"
        )

    def test_idempotent_for_duplicate_import(self, tmp_path: Path) -> None:
        p = self._write(tmp_path, "import time\n\nx = 1\n")
        fix = ImportFix(module="time", import_line="import time", symbol="time")
        changed = apply_import_fix(p, fix)
        assert changed is False
        assert p.read_text() == "import time\n\nx = 1\n"

    def test_idempotent_for_from_import(self, tmp_path: Path) -> None:
        p = self._write(tmp_path, "from pathlib import Path\n\nx = 1\n")
        fix = ImportFix(
            module="pathlib", import_line="from pathlib import Path", symbol="Path"
        )
        changed = apply_import_fix(p, fix)
        assert changed is False

    def test_inserts_before_module_level_code(self, tmp_path: Path) -> None:
        # Module-level __future__ directive + import — new import goes
        # right after the last import line in the contiguous block.
        p = self._write(
            tmp_path,
            "from __future__ import annotations\nimport os\n\nx = 1\n",
        )
        fix = ImportFix(module="sys", import_line="import sys", symbol="sys")
        changed = apply_import_fix(p, fix)
        assert changed is True
        result = p.read_text()
        assert (
            result
            == "from __future__ import annotations\nimport os\nimport sys\n\nx = 1\n"
        )


# ---------------------------------------------------------------------------
# AUTO_FIX_CODES constant
# ---------------------------------------------------------------------------


class TestAutoFixCodes:
    def test_only_unresolved_reference_is_listed(self) -> None:
        # unresolved-attribute is a UNION issue, not an import issue;
        # don't pretend we can fix it by adding an import.
        assert AUTO_FIX_CODES == frozenset({"unresolved-reference"})
