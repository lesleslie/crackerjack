"""Tests for crackerjack.fixers.import_optimization.

Ported from tests/test_agents/test_import_optimization_agent.py and
tests/unit/agents/test_import_optimization_agent.py, keeping only the cases
that exercise real ast-based import analysis, real ``vulture`` subprocess
output parsing, and real file-content transforms. Cases exercising
SubAgent/coordinator dispatch (``can_handle``, ``get_supported_types``,
``ImportOptimizationAgent.__init__``, ``analyze_and_fix`` as a bare wrapper)
were dropped, since that machinery no longer exists -- see the module
docstring of ``crackerjack/fixers/import_optimization.py`` for the full
kept/dropped rationale, including the one pre-existing behavioral quirk
preserved verbatim (not fixed) per CLAUDE.md Rule 7.

Where the originals mocked ``self.context`` (an ``AgentContext``), tests
below use ``tmp_path`` as the real ``project_root: Path`` parameter instead
-- no ``AgentContext`` exists anymore, and the real filesystem is a more
faithful substitute than a mock for functions that ``rglob``/read/write
real files.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import Mock

import pytest

from crackerjack.fixers import import_optimization as io
from crackerjack.models.issues import Issue, IssueType, Priority


def _issue(**kwargs: object) -> Issue:
    defaults: dict[str, object] = {
        "id": "import-test",
        "type": IssueType.IMPORT_ERROR,
        "severity": Priority.MEDIUM,
        "message": "Import error",
    }
    defaults.update(kwargs)
    return Issue(**defaults)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# analyze_file / basic file validation
# ---------------------------------------------------------------------------


class TestAnalyzeFile:
    async def test_analyze_file_valid_python(self, tmp_path: Path) -> None:
        test_file = tmp_path / "module.py"
        test_file.write_text(
            "import os\nimport sys\nfrom pathlib import Path\nfrom typing import Any\n"
        )

        analysis = await io.analyze_file(test_file, tmp_path)

        assert isinstance(analysis, io.ImportAnalysis)
        assert analysis.file_path == test_file

    async def test_analyze_file_with_mixed_imports(self, tmp_path: Path) -> None:
        test_file = tmp_path / "module.py"
        test_file.write_text("import os\nfrom os import path\n")

        analysis = await io.analyze_file(test_file, tmp_path)

        assert len(analysis.mixed_imports) > 0
        assert "os" in analysis.mixed_imports

    async def test_analyze_file_invalid(self, tmp_path: Path) -> None:
        test_file = tmp_path / "nonexistent.py"

        analysis = await io.analyze_file(test_file, tmp_path)

        assert analysis.file_path == test_file
        assert analysis.mixed_imports == []

    async def test_analyze_file_syntax_error(self, tmp_path: Path) -> None:
        test_file = tmp_path / "broken.py"
        test_file.write_text("import os\nif True")

        analysis = await io.analyze_file(test_file, tmp_path)

        assert isinstance(analysis, io.ImportAnalysis)
        assert analysis.mixed_imports == []

    def test_is_valid_python_file(self, tmp_path: Path) -> None:
        valid_file = tmp_path / "module.py"
        valid_file.write_text("import os")

        invalid_file = tmp_path / "data.txt"
        invalid_file.write_text("text")

        assert io._is_valid_python_file(valid_file) is True
        assert io._is_valid_python_file(invalid_file) is False
        assert io._is_valid_python_file(tmp_path / "missing.py") is False

    def test_create_empty_import_analysis(self) -> None:
        result = io._create_empty_import_analysis(Path("/test/file.py"))
        assert result.file_path == Path("/test/file.py")
        assert result.mixed_imports == []
        assert result.redundant_imports == []


# ---------------------------------------------------------------------------
# vulture-based unused-import detection
# ---------------------------------------------------------------------------


class TestUnusedImportDetection:
    async def test_detect_unused_imports_success(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        test_file = tmp_path / "module.py"
        mock_result = Mock(returncode=0, stdout="unused import 'os'\n")
        monkeypatch.setattr(
            io, "_run_vulture_analysis", lambda fp, pr: mock_result
        )

        unused = await io._detect_unused_imports(test_file, tmp_path)

        assert unused == ["os"]

    async def test_detect_unused_imports_timeout(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        test_file = tmp_path / "module.py"

        def _raise(fp: Path, pr: Path) -> None:
            raise subprocess.TimeoutExpired("vulture", 30)

        monkeypatch.setattr(io, "_run_vulture_analysis", _raise)

        unused = await io._detect_unused_imports(test_file, tmp_path)

        assert unused == []

    def test_run_vulture_analysis_real_subprocess(self, tmp_path: Path) -> None:
        """Real, unmocked subprocess.run invocation of vulture."""
        test_file = tmp_path / "module.py"
        test_file.write_text("import os\n\n\ndef foo() -> int:\n    return 1\n")

        result = io._run_vulture_analysis(test_file, tmp_path)

        assert isinstance(result, subprocess.CompletedProcess)
        assert "unused import" in result.stdout.lower()
        assert "os" in result.stdout

    def test_run_vulture_analysis_pins_cwd_to_project_root(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        # Task 22a regression: exercise the real subprocess.run call and
        # capture the `cwd` kwarg to prove it is pinned to `project_root`,
        # matching the original `SubAgent.run_command`'s
        # `cwd=self.context.project_path` behavior.
        test_file = tmp_path / "module.py"
        test_file.write_text("import os\n")

        captured: dict[str, object] = {}
        real_run = subprocess.run

        def spying_run(*args: object, **kwargs: object):
            captured["cwd"] = kwargs.get("cwd")
            return real_run(*args, **kwargs)  # type: ignore[arg-type]

        monkeypatch.setattr(subprocess, "run", spying_run)

        io._run_vulture_analysis(test_file, tmp_path)

        assert captured["cwd"] == tmp_path

    def test_extract_unused_imports_from_result(self) -> None:
        """Pre-existing quirk preserved verbatim per CLAUDE.md Rule 7 (see
        the ``crackerjack/fixers/import_optimization.py`` module docstring,
        quirk 2): ``.apply()`` substitutes the matched ``unused import
        'name'`` substring *within* the full vulture line rather than
        returning the bare captured name, so real (multi-part) vulture
        lines come out as mangled full lines, not clean import names."""
        mock_result = Mock(
            returncode=0,
            stdout="module.py:1: unused import 'os' (confidence 80%)\n"
            "module.py:2: unused import 'sys' (confidence 90%)\n",
        )

        unused = io._extract_unused_imports_from_result(mock_result)

        assert unused == [
            "module.py:1: os (confidence 80%)",
            "module.py:2: sys (confidence 90%)",
        ]

    def test_extract_import_name_from_line_bare_substring_extracts_cleanly(
        self,
    ) -> None:
        """When the *entire* input is exactly the matched substring (as in
        ``extract_unused_import_name``'s own ``ValidatedPattern.test_cases``),
        ``.apply()`` does reduce to the bare name -- it's only real,
        multi-part vulture output lines (see the test above) where the
        surrounding prefix/suffix text survives the substitution."""
        assert io._extract_import_name_from_line("unused import 'os'") == "os"

    def test_is_valid_vulture_result(self) -> None:
        valid_result = Mock(returncode=0, stdout="output")
        invalid_result = Mock(returncode=1, stdout="")
        empty_result = Mock(returncode=0, stdout="")

        assert io._is_valid_vulture_result(valid_result) is True
        assert io._is_valid_vulture_result(invalid_result) is False
        assert io._is_valid_vulture_result(empty_result) is False


# ---------------------------------------------------------------------------
# import extraction / analysis
# ---------------------------------------------------------------------------


class TestImportAnalysis:
    def test_extract_import_information(self) -> None:
        import ast

        code = (
            "import os\nimport sys\nfrom pathlib import Path\n"
            "from typing import Any, Dict\n"
        )
        tree = ast.parse(code)

        module_imports, all_imports = io._extract_import_information(tree)

        assert "os" in module_imports
        assert "sys" in module_imports
        assert "pathlib" in module_imports
        # 4 import statements, but `from typing import Any, Dict` contributes
        # 2 entries (one per alias), for 5 total.
        assert len(all_imports) == 5

    def test_find_mixed_imports(self) -> None:
        module_imports = {
            "os": [
                {"type": "standard", "module": "os", "name": "os", "line": 1},
                {"type": "from", "module": "os", "name": "path", "line": 2},
            ],
            "sys": [
                {"type": "standard", "module": "sys", "name": "sys", "line": 3},
            ],
        }
        mixed = io._find_mixed_imports(module_imports)
        assert "os" in mixed
        assert "sys" not in mixed

    def test_find_redundant_imports(self) -> None:
        all_imports = [
            {"module": "os", "name": "path", "line": 1},
            {"module": "os", "name": "path", "line": 2},
            {"module": "sys", "name": "argv", "line": 3},
        ]
        redundant = io._find_redundant_imports(all_imports)
        assert len(redundant) == 1
        assert "Line 2" in redundant[0]

    def test_find_optimization_opportunities(self) -> None:
        module_imports = {
            "pathlib": [
                {"type": "standard", "module": "pathlib"},
                {"type": "standard", "module": "pathlib"},
            ],
        }
        opportunities = io._find_optimization_opportunities(module_imports)
        assert len(opportunities) > 0
        assert "Consolidate" in opportunities[0]

    def test_check_star_imports(self) -> None:
        content = "from os import *\nfrom pathlib import Path\n"
        violations = io._check_star_imports(content)
        assert len(violations) > 0
        assert "star import" in violations[0].lower()

    def test_should_skip_symbol_scan_path(self, tmp_path: Path) -> None:
        hidden_path = tmp_path / ".venv" / "lib" / "site.py"
        normal_path = tmp_path / "pkg" / "core" / "module.py"

        assert io._should_skip_symbol_scan_path(hidden_path) is True
        assert io._should_skip_symbol_scan_path(normal_path) is False

    def test_process_standard_import(self) -> None:
        import ast

        code = "import os, sys"
        tree = ast.parse(code)
        all_imports: list[dict[str, object]] = []
        module_imports: dict[str, list[dict[str, object]]] = {}

        node = tree.body[0]
        io._process_standard_import(node, all_imports, module_imports)  # type: ignore[arg-type]

        assert len(all_imports) == 2
        assert "os" in module_imports
        assert "sys" in module_imports

    def test_process_from_import(self) -> None:
        import ast

        code = "from pathlib import Path, PurePath"
        tree = ast.parse(code)
        all_imports: list[dict[str, object]] = []
        module_imports: dict[str, list[dict[str, object]]] = {}

        node = tree.body[0]
        io._process_from_import(node, all_imports, module_imports)  # type: ignore[arg-type]

        assert len(all_imports) == 2
        assert "pathlib" in module_imports


# ---------------------------------------------------------------------------
# import ordering / PEP 8 categorization
# ---------------------------------------------------------------------------


class TestImportOrdering:
    def test_get_import_category_stdlib(self) -> None:
        assert io._get_import_category("os") == 1

    def test_get_import_category_third_party(self) -> None:
        assert io._get_import_category("requests") == 2

    def test_get_import_category_local(self) -> None:
        assert io._get_import_category("crackerjack.services") == 3

    def test_get_import_category_future(self) -> None:
        assert io._get_import_category("__future__") == 0

    def test_get_import_category_empty(self) -> None:
        assert io._get_import_category("") == 3

    def test_is_stdlib_module(self) -> None:
        assert io._is_stdlib_module("os") is True
        assert io._is_stdlib_module("sys") is True
        assert io._is_stdlib_module("pathlib") is True
        assert io._is_stdlib_module("requests") is False

    def test_is_local_import(self) -> None:
        assert io._is_local_import("crackerjack.agents", "crackerjack") is True
        assert io._is_local_import(".services", "services") is True
        assert io._is_local_import("os.path", "os") is False


# ---------------------------------------------------------------------------
# rule-code / predicate helpers
# ---------------------------------------------------------------------------


class TestRuleCodeHelpers:
    def test_extract_ruff_rule_code(self) -> None:
        assert io._extract_ruff_rule_code("F401 imported but unused") == "F401"
        assert io._extract_ruff_rule_code("E501 line too long") == "E501"
        assert io._extract_ruff_rule_code("no code found") is None

    def test_extract_issue_rule_code_from_message(self) -> None:
        issue = _issue(message="F401 imported but unused")
        assert io._extract_issue_rule_code(issue) == "F401"

    def test_extract_issue_rule_code_from_details(self) -> None:
        issue = _issue(message="Some error", details=["Additional info", "code: F401"])
        assert io._extract_issue_rule_code(issue) == "F401"

    def test_is_unused_import_issue(self) -> None:
        assert io._is_unused_import_issue(_issue(message="imported but unused 'os'"))
        assert io._is_unused_import_issue(_issue(message="unused import 'sys'"))
        assert not io._is_unused_import_issue(_issue(message="different error"))

    def test_is_import_lint_suppressible(self) -> None:
        assert io._is_import_lint_suppressible(_issue(message="F401 imported but unused"))
        assert io._is_import_lint_suppressible(_issue(message="F403 star import"))
        assert not io._is_import_lint_suppressible(_issue(message="E501 line too long"))

    def test_is_import_order_issue(self) -> None:
        assert io._is_import_order_issue(_issue(message="I001 import order"))
        assert not io._is_import_order_issue(_issue(message="F401 imported but unused"))

    def test_is_star_import_line(self) -> None:
        assert io._is_star_import_line("from os import *") is True
        assert io._is_star_import_line("from os import path") is False
        assert io._is_star_import_line("import os") is False

    def test_is_star_import_expansion_candidate(self) -> None:
        content = "from os import *"
        assert (
            io._is_star_import_expansion_candidate(
                _issue(message="F403 star import"), content
            )
            is True
        )
        assert (
            io._is_star_import_expansion_candidate(
                _issue(message="F401 imported but unused"), content
            )
            is False
        )

    def test_extract_undefined_name(self) -> None:
        issue1 = _issue(message='Name "foo" is not defined')
        issue2 = _issue(message="Some other error", details=['Undefined name "bar"'])

        assert io._extract_undefined_name(issue1) == "foo"
        assert io._extract_undefined_name(issue2) == "bar"

    def test_line_already_has_noqa(self) -> None:
        assert io._line_already_has_noqa("import os  # noqa: F401", "F401") is True
        assert io._line_already_has_noqa("import os", "F401") is False
        assert io._line_already_has_noqa("import os  # noqa: F402", "F401") is False

    def test_append_noqa_code(self) -> None:
        result = io._append_noqa_code("import os", "F401")
        assert result == "import os # noqa: F401"

        result = io._append_noqa_code("import os  # noqa: F402", "F401")
        assert result == "import os  # noqa: F402, F401"

    def test_needs_future_import_reorder(self) -> None:
        content = "import os\nfrom __future__ import annotations\n"
        issue1 = _issue(message="F404 some error")
        issue2 = _issue(message="some unrelated error")

        assert io._needs_future_import_reorder(issue1, content) is True
        assert io._needs_future_import_reorder(issue2, content) is False

        content_no_future = "import os\nimport sys\n"
        assert io._needs_future_import_reorder(issue1, content_no_future) is False

    def test_is_multi_import_line(self) -> None:
        assert io._is_multi_import_line("from os import path, sep") is True
        assert io._is_multi_import_line("import os") is False

    def test_is_import_line(self) -> None:
        assert io._is_import_line("import os") is True
        assert io._is_import_line("from os import path") is True
        assert io._is_import_line("# import os") is False
        assert io._is_import_line("def foo(): pass") is False

    def test_extract_module_name(self) -> None:
        assert io._extract_module_name("import os.path") == "os"
        assert io._extract_module_name("from pathlib import Path") == "pathlib"

    def test_categorize_imports(self) -> None:
        all_imports = [
            {"module": "os", "name": "path"},
            {"module": "requests", "name": "get"},
            {"module": "crackerjack.services", "name": "config"},
        ]

        categories = io._categorize_imports(all_imports)

        assert 1 in categories
        assert 2 in categories
        assert 3 in categories

    def test_parse_import_lines(self) -> None:
        lines = ["import os", "from pathlib import Path", "", "def main(): pass"]

        import_lines, other_lines, bounds = io._parse_import_lines(lines)

        assert len(import_lines) == 2
        assert len(other_lines) > 0
        assert bounds == (0, 1)


class TestEnclosingImportStatement:
    def test_find_enclosing_import_statement(self) -> None:
        lines = ["", "import os", "", "import sys"]
        assert io._find_enclosing_import_statement(lines, 2) == 1
        assert io._find_enclosing_import_statement(lines, 3) == 3
        assert io._find_enclosing_import_statement(lines, 0) is None

    def test_find_enclosing_import_statement_no_import(self) -> None:
        lines = ["def foo():", "    pass"]
        assert io._find_enclosing_import_statement(lines, 1) is None


class TestSortSingleFromImportLine:
    def test_sorts_names(self) -> None:
        result = io._sort_single_from_import_line("from os import path, sep")
        assert result is not None
        assert "path" in result
        assert "sep" in result

    def test_unchanged_for_single_import(self) -> None:
        result = io._sort_single_from_import_line("from os import path")
        assert result is None


class TestExtractAllExportNames:
    def test_extracts_names(self) -> None:
        content = '__all__ = ["foo", "bar", "baz"]'
        names = io._extract_all_export_names(content)
        assert names == ["foo", "bar", "baz"]

    def test_no_all_returns_empty(self) -> None:
        content = "import os\ndef foo():\n    pass\n"
        assert io._extract_all_export_names(content) == []


class TestCollectUndefinedAllExports:
    def test_finds_undefined_exports(self) -> None:
        content = '\n__all__ = ["foo", "bar"]\n\ndef foo():\n    pass\n'
        undefined = io._collect_undefined_all_exports(content)
        assert "bar" in undefined
        assert "foo" not in undefined


class TestCommonImportsAndTyping:
    def test_common_imports_mapping(self) -> None:
        assert "Any" in io._COMMON_IMPORTS
        assert "Callable" in io._COMMON_IMPORTS
        assert "Dict" in io._COMMON_IMPORTS
        assert io._COMMON_IMPORTS["Any"] == "from typing import Any"

    def test_infer_typing_import(self) -> None:
        assert io._infer_typing_import("Any") == "from typing import Any"
        assert io._infer_typing_import("Optional") == "from typing import Optional"
        assert io._infer_typing_import("List") == "from typing import List"
        assert io._infer_typing_import("UnknownType") is None


# ---------------------------------------------------------------------------
# project-wide symbol search (project_root threading)
# ---------------------------------------------------------------------------


class TestProjectSymbolSearch:
    def test_path_to_module_name(self, tmp_path: Path) -> None:
        path = tmp_path / "pkg" / "module.py"
        result = io._path_to_module_name(path, tmp_path)
        assert result == "pkg.module"

        init_path = tmp_path / "pkg" / "__init__.py"
        result = io._path_to_module_name(init_path, tmp_path)
        assert result == "pkg"

    def test_path_to_module_name_outside_project(self, tmp_path: Path) -> None:
        outside = tmp_path.parent / "other_project_dir_xyz" / "file.py"
        result = io._path_to_module_name(outside, tmp_path)
        assert result is None

    def test_find_project_symbol_import_finds_class(self, tmp_path: Path) -> None:
        (tmp_path / "widgets.py").write_text("class Widget:\n    pass\n")

        result = io._find_project_symbol_import("Widget", tmp_path)

        assert result == "from widgets import Widget"

    def test_find_project_symbol_import_stdlib_fallback(self, tmp_path: Path) -> None:
        result = io._find_project_symbol_import("dataclasses", tmp_path)
        assert result == "import dataclasses"

    def test_find_project_symbol_import_no_match(self, tmp_path: Path) -> None:
        result = io._find_project_symbol_import("TotallyUnknownSymbolXyz", tmp_path)
        assert result is None

    def test_find_project_symbol_imports_multiple(self, tmp_path: Path) -> None:
        (tmp_path / "helpers.py").write_text(
            "def alpha():\n    pass\n\ndef beta():\n    pass\n"
        )

        result = io._find_project_symbol_imports(["alpha", "beta"], tmp_path)

        assert result["alpha"] == "from helpers import alpha"
        assert result["beta"] == "from helpers import beta"

    def test_find_project_symbol_imports_skips_non_utf8(self, tmp_path: Path) -> None:
        (tmp_path / "bad.py").write_bytes(b"\xff\xfe\xa4not-utf8")
        (tmp_path / "good.py").write_text("def target():\n    pass\n")

        result = io._find_project_symbol_imports(["target"], tmp_path)

        assert result["target"] == "from good import target"


# ---------------------------------------------------------------------------
# import insertion / __future__ positioning
# ---------------------------------------------------------------------------


class TestImportInsertion:
    def test_find_import_insertion_index(self) -> None:
        lines = ["", "import os", "", "def foo():", "    pass"]
        assert io._find_import_insertion_index(lines) == 2

    def test_find_import_insertion_index_with_docstring(self) -> None:
        lines = [
            '"""Module docstring."""',
            "",
            "import os",
            "",
            "def foo():",
            "    pass",
        ]
        assert io._find_import_insertion_index(lines) == 3

    def test_find_future_import_insertion_index(self) -> None:
        lines = ['"""Docstring."""', "", "import os", "", "def foo():"]
        assert io._find_future_import_insertion_index(lines) >= 0


# ---------------------------------------------------------------------------
# fix_import_issue -- validation / no-op paths
# ---------------------------------------------------------------------------


class TestValidateAndNoOptimizationPaths:
    def test_validate_issue_without_file_path(self) -> None:
        result = io._validate_issue(_issue(file_path=None))
        assert result is not None
        assert result.success is False

    def test_validate_issue_with_file_path(self) -> None:
        result = io._validate_issue(_issue(file_path="/test/file.py"))
        assert result is None

    async def test_process_import_optimization_issue_no_file_path(
        self, tmp_path: Path
    ) -> None:
        result = await io._process_import_optimization_issue(
            _issue(file_path=None), tmp_path
        )
        assert result.success is False
        assert "No file path" in result.remaining_issues[0]

    def test_are_optimizations_needed(self) -> None:
        empty_analysis = io.ImportAnalysis(Path("/test.py"), [], [], [], [], [])
        assert io._are_optimizations_needed(empty_analysis) is False

        needs_analysis = io.ImportAnalysis(Path("/test.py"), ["os"], [], [], [], [])
        assert io._are_optimizations_needed(needs_analysis) is True

    def test_create_no_optimization_needed_result(self) -> None:
        result = io._create_no_optimization_needed_result()
        assert result.success is True
        assert result.confidence == 1.0
        assert "No import optimizations needed" in result.fixes_applied


class TestFixIssueNoOptimizationsNeeded:
    async def test_no_optimizations_needed_end_to_end(self, tmp_path: Path) -> None:
        test_file = tmp_path / "module.py"
        test_file.write_text("import os\n")

        issue = _issue(message="Check imports", file_path=str(test_file))

        result = await io.fix_import_issue(issue, tmp_path)

        assert result.success is True
        assert result.confidence == 1.0
        assert "No import optimizations needed" in result.fixes_applied[0]

    async def test_no_file_path(self, tmp_path: Path) -> None:
        result = await io.fix_import_issue(_issue(file_path=None), tmp_path)
        assert result.success is False
        assert "No file path" in result.remaining_issues[0]


# ---------------------------------------------------------------------------
# fix_import_issue -- real end-to-end transforms
# ---------------------------------------------------------------------------


class TestFixIssueEndToEnd:
    async def test_adds_missing_typing_alias_import(self, tmp_path: Path) -> None:
        test_file = tmp_path / "module.py"
        test_file.write_text("def build(values):\n    return t.Any\n")

        issue = _issue(
            message='Name "t" is not defined  [name-defined]',
            file_path=str(test_file),
        )

        result = await io.fix_import_issue(issue, tmp_path)

        assert result.success is True
        assert "Added typing alias import" in result.fixes_applied
        assert "import typing as t" in test_file.read_text()

    async def test_moves_future_import_to_top(self, tmp_path: Path) -> None:
        test_file = tmp_path / "module.py"
        test_file.write_text(
            "import os\nfrom __future__ import annotations\n\nVALUE = os.name\n"
        )

        issue = _issue(
            message="`from __future__` imports must occur at the beginning of the file",
            file_path=str(test_file),
        )

        result = await io.fix_import_issue(issue, tmp_path)

        assert result.success is True
        written = test_file.read_text()
        assert written.startswith("from __future__ import annotations\n")
        assert "Moved __future__ import to the top of the file" in result.fixes_applied

    async def test_adds_project_import_for_export_name(self, tmp_path: Path) -> None:
        helper_file = tmp_path / "ulid_resolution.py"
        helper_file.write_text("def generate_with_retry():\n    return 1\n")

        package_dir = tmp_path / "core"
        package_dir.mkdir()
        test_file = package_dir / "ulid.py"
        test_file.write_text('__all__ = ["generate_with_retry"]\n\nVALUE = 1\n')

        issue = _issue(
            message='Undefined name "generate_with_retry" in __all__',
            file_path=str(test_file),
        )

        result = await io.fix_import_issue(issue, tmp_path)

        assert result.success is True
        written = test_file.read_text()
        assert "from ulid_resolution import generate_with_retry" in written

    async def test_expands_star_import_using_all(self, tmp_path: Path) -> None:
        source_file = tmp_path / "collections" / "btree.py"
        source_file.parent.mkdir(parents=True)
        source_file.write_text(
            "class BTree:\n    pass\n\nclass BNode:\n    pass\n", encoding="utf-8"
        )

        shim_file = tmp_path / "btree.py"
        shim_file.write_text(
            'from collections.btree import *  # noqa: F403, F405\n\n'
            '__all__ = ["BTree", "BNode"]\n',
            encoding="utf-8",
        )

        issue = _issue(
            message="`BTree` may be undefined, or defined from star imports",
            file_path=str(shim_file),
            line_number=1,
        )

        result = await io.fix_import_issue(issue, tmp_path)

        assert result.success is True
        written = shim_file.read_text()
        assert "from collections.btree import BTree, BNode" in written
        assert "*  # noqa" not in written

    async def test_expands_star_import_when_f405_points_to_use_site(
        self, tmp_path: Path
    ) -> None:
        source_file = tmp_path / "collections" / "btree.py"
        source_file.parent.mkdir(parents=True)
        source_file.write_text(
            "class BTree:\n    pass\n\nclass BNode:\n    pass\n", encoding="utf-8"
        )

        shim_file = tmp_path / "btree.py"
        shim_file.write_text(
            'from collections.btree import *  # noqa: F403, F405\n\n'
            '__all__ = ["BTree", "BNode"]\n\n'
            "tree = BTree()\n",
            encoding="utf-8",
        )

        issue = _issue(
            message="F405 `BTree` may be undefined, or defined from star imports",
            file_path=str(shim_file),
            line_number=4,
        )

        result = await io.fix_import_issue(issue, tmp_path)

        assert result.success is True
        assert "from collections.btree import BTree, BNode" in shim_file.read_text()

    async def test_sorts_from_import_names_for_i001(self, tmp_path: Path) -> None:
        test_file = tmp_path / "connection.py"
        test_file.write_text(
            "from __future__ import annotations\n\n"
            "import warnings\n\n"
            "from dhara.core.connection import Connection, ROOT_OID\n",
            encoding="utf-8",
        )

        issue = _issue(
            message="I001 Import block is un-sorted or un-formatted",
            file_path=str(test_file),
            line_number=5,
        )

        result = await io.fix_import_issue(issue, tmp_path)

        assert result.success is True
        written = test_file.read_text()
        assert "from dhara.core.connection import ROOT_OID, Connection" in written
        assert any("Sorted imported names" in fix for fix in result.fixes_applied)

    async def test_adds_project_imports_for_all_undefined_exports(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / "ulid_collision.py").write_text(
            "class CollisionError(Exception):\n    pass\n\n"
            "def generate_with_retry() -> str:\n    return 'ok'\n"
        )
        (tmp_path / "ulid_resolution.py").write_text(
            "def export_registry() -> dict[str, dict]:\n    return {}\n\n"
            "def register_reference() -> None:\n    return None\n"
        )

        test_file = tmp_path / "ulid.py"
        test_file.write_text(
            '__all__ = [\n'
            '    "generate_with_retry",\n'
            '    "CollisionError",\n'
            '    "export_registry",\n'
            '    "register_reference",\n'
            "]\n"
        )

        issue = _issue(
            message='Undefined name "generate_with_retry" in __all__',
            file_path=str(test_file),
        )

        result = await io.fix_import_issue(issue, tmp_path)

        assert result.success is True
        written = test_file.read_text()
        assert "from ulid_collision import generate_with_retry" in written
        assert "from ulid_collision import CollisionError" in written
        assert "from ulid_resolution import export_registry" in written
        assert "from ulid_resolution import register_reference" in written

    async def test_preserves_future_import_position_with_multiline_docstring(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / "ulid_resolution.py").write_text(
            "def generate_with_retry() -> int:\n    return 1\n"
        )

        test_file = tmp_path / "ulid.py"
        test_file.write_text(
            '"""ULID integration for configuration management.\n\n'
            "This module provides traceability.\n"
            '"""\n\n'
            "from __future__ import annotations\n\n"
            '__all__ = ["generate_with_retry"]\n'
        )

        issue = _issue(
            message='Undefined name "generate_with_retry" in __all__',
            file_path=str(test_file),
        )

        result = await io.fix_import_issue(issue, tmp_path)

        assert result.success is True
        written = test_file.read_text()
        lines = written.splitlines()
        future_index = lines.index("from __future__ import annotations")
        import_index = lines.index("from ulid_resolution import generate_with_retry")
        assert future_index < import_index

    async def test_skips_non_utf8_python_files_during_symbol_scan(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / "bad.py").write_bytes(b"\xff\xfe\xa4not-utf8")
        (tmp_path / "ulid_resolution.py").write_text(
            "def generate_with_retry() -> int:\n    return 1\n"
        )

        test_file = tmp_path / "ulid.py"
        test_file.write_text('__all__ = ["generate_with_retry"]\n')

        issue = _issue(
            message='Undefined name "generate_with_retry" in __all__',
            file_path=str(test_file),
        )

        result = await io.fix_import_issue(issue, tmp_path)

        assert result.success is True
        assert "from ulid_resolution import generate_with_retry" in test_file.read_text()

    async def test_marks_unused_import_with_noqa(self, tmp_path: Path) -> None:
        test_file = tmp_path / "client.py"
        test_file.write_text(
            "from IPython.terminal.ipapp import load_default_config\n\n"
            "def run() -> None:\n    return None\n",
        )

        issue = _issue(
            message=(
                "F401 `IPython.terminal.ipapp.load_default_config` imported but unused"
            ),
            file_path=str(test_file),
            line_number=1,
        )

        result = await io.fix_import_issue(issue, tmp_path)

        assert result.success is True
        assert "# noqa: F401" in test_file.read_text()

    async def test_marks_multiline_unused_import_block_with_noqa(
        self, tmp_path: Path
    ) -> None:
        test_file = tmp_path / "__init__.py"
        test_file.write_text(
            "from .tools import (\n    health_check,\n    run_status,\n)\n",
            encoding="utf-8",
        )

        issue = _issue(
            message="F401 `run_status` imported but unused",
            file_path=str(test_file),
            line_number=3,
        )

        result = await io.fix_import_issue(issue, tmp_path)

        assert result.success is True
        updated = test_file.read_text(encoding="utf-8")
        assert "from .tools import ( # noqa: F401" in updated

    async def test_suppresses_star_import_lint_without_rewrite(
        self, tmp_path: Path
    ) -> None:
        test_file = tmp_path / "__init__.py"
        test_file.write_text("from .registry import *\n", encoding="utf-8")

        issue = _issue(
            message="F403 `from .registry import *` used; unable to detect undefined names",
            file_path=str(test_file),
            line_number=1,
        )

        result = await io.fix_import_issue(issue, tmp_path)

        assert result.success is True
        assert "# noqa: F403" in test_file.read_text(encoding="utf-8")

    async def test_safe_init_fallback_applies_noqa_to_top_level_imports(
        self, tmp_path: Path
    ) -> None:
        test_file = tmp_path / "__init__.py"
        test_file.write_text(
            "import asyncio\nimport json\nfrom enum import Enum\n",
            encoding="utf-8",
        )

        issue = _issue(
            message="F401 `json` imported but unused",
            file_path=str(test_file),
            line_number=999,
        )

        result = await io.fix_import_issue(issue, tmp_path)

        assert result.success is True
        updated = test_file.read_text(encoding="utf-8")
        assert "import asyncio # noqa: F401" in updated
        assert "import json # noqa: F401" in updated
        assert "from enum import Enum # noqa: F401" in updated

    async def test_safe_init_fallback_reads_code_from_issue_details(
        self, tmp_path: Path
    ) -> None:
        test_file = tmp_path / "__init__.py"
        test_file.write_text("from .registry import *\n", encoding="utf-8")

        issue = _issue(
            message="Star import used; unable to detect undefined names",
            file_path=str(test_file),
            line_number=None,
            details=["code: F403"],
        )

        result = await io.fix_import_issue(issue, tmp_path)

        assert result.success is True
        assert "# noqa: F403" in test_file.read_text(encoding="utf-8")

    async def test_safe_init_fallback_handles_f822_all_line(
        self, tmp_path: Path
    ) -> None:
        test_file = tmp_path / "__init__.py"
        test_file.write_text(
            'from .registry import foo\n__all__ = [\n    "foo",\n    "bar",\n]\n',
            encoding="utf-8",
        )

        issue = _issue(
            message="Undefined name in __all__",
            file_path=str(test_file),
            line_number=2,
            details=["code: F822"],
        )

        result = await io.fix_import_issue(issue, tmp_path)

        assert result.success is True
        assert "# noqa: F822" in test_file.read_text(encoding="utf-8")

    async def test_init_does_not_call_risky_optimizer_path(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        test_file = tmp_path / "__init__.py"
        test_file.write_text("value = 1\n", encoding="utf-8")

        issue = _issue(
            message="import error without direct/safe fallback",
            file_path=str(test_file),
            line_number=1,
        )

        def _boom(issue: Issue) -> None:
            raise AssertionError("should not be called for __init__.py")

        monkeypatch.setattr(io, "_process_import_optimization_issue", _boom)

        result = await io.fix_import_issue(issue, tmp_path)

        assert result.success is False
        assert (
            "Skipped risky import-block optimization for __init__.py"
            in result.remaining_issues[0]
        )

    async def test_rejects_invalid_optimized_python(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        test_file = tmp_path / "client.py"
        test_file.write_text(
            "import os\n\nclass Example:\n    def run(self):\n        return True\n",
        )

        issue = _issue(
            message="Import optimization failed",
            file_path=str(test_file),
        )

        analysis = io.ImportAnalysis(
            test_file,
            [],
            [],
            [],
            [],
            ["Import 'os' should come before previous imports"],
        )

        async def _fake_analyze(fp: Path, pr: Path) -> io.ImportAnalysis:
            return analysis

        async def _fake_optimize(content: str, a: io.ImportAnalysis) -> str:
            return "def broken(:\n    pass\n"

        write_called = False

        async def _fake_write(fp: Path, content: str) -> None:
            nonlocal write_called
            write_called = True

        monkeypatch.setattr(io, "analyze_file", _fake_analyze)
        monkeypatch.setattr(io, "_optimize_imports", _fake_optimize)
        monkeypatch.setattr(io, "_write_optimized_content", _fake_write)

        result = await io.fix_import_issue(issue, tmp_path)

        assert write_called is False
        assert result.success is False
        assert "invalid Python" in result.remaining_issues[0]


# ---------------------------------------------------------------------------
# _optimize_imports pipeline (real transforms + syntax validation)
# ---------------------------------------------------------------------------


class TestOptimizeImports:
    async def test_optimize_imports_returns_string(self) -> None:
        content = "import os\nfrom os import path\n"
        analysis = io.ImportAnalysis(Path("test.py"), ["os"], [], [], [], [])

        optimized = await io._optimize_imports(content, analysis)

        assert isinstance(optimized, str)

    async def test_optimize_imports_preserves_import_lines_and_syntax(self) -> None:
        import ast

        content = (
            "from __future__ import annotations\n\n"
            "import os\nfrom pathlib import Path\n\n\n"
            "class Example:\n"
            "    async def is_secure(self) -> bool:\n"
            '        """Check if connection is using WSS (secure)."""\n'
            "        return True\n"
        )
        analysis = io.ImportAnalysis(Path("client.py"), [], [], [], [], [])

        optimized = await io._optimize_imports(content, analysis)

        assert "import os" in optimized
        assert "from pathlib import Path" in optimized
        ast.parse(optimized)

    async def test_optimize_imports_keeps_future_import_first(self) -> None:
        import ast

        content = (
            '"""Module docstring."""\n\n'
            "import os\n"
            "from __future__ import annotations\n"
            "from oneiric.core.ulid_resolution import resolve_ulid\n"
        )
        analysis = io.ImportAnalysis(Path("ulid.py"), [], [], [], [], [])

        optimized = await io._optimize_imports(content, analysis)
        lines = optimized.splitlines()
        future_index = lines.index("from __future__ import annotations")
        stdlib_index = lines.index("import os")
        local_index = lines.index(
            "from oneiric.core.ulid_resolution import resolve_ulid"
        )

        assert future_index < stdlib_index
        assert future_index < local_index
        ast.parse(optimized)

    async def test_optimize_imports_preserves_nested_try_imports(self) -> None:
        import ast

        content = (
            "from __future__ import annotations\n\n"
            "import os\n\n"
            "try:\n"
            "    import websockets\n"
            "    from websockets.client import WebSocketClientProtocol\n\n"
            "    WEBSOCKETS_AVAILABLE = True\n"
            "except ImportError:\n"
            "    WEBSOCKETS_AVAILABLE = False\n\n"
            "def load():\n"
            "    return os.name\n"
        )
        analysis = io.ImportAnalysis(Path("client.py"), [], ["os"], [], [], [])

        optimized = await io._optimize_imports(content, analysis)

        assert "import websockets" in optimized
        assert "from websockets.client import WebSocketClientProtocol" in optimized
        ast.parse(optimized)

    def test_remove_unused_imports(self) -> None:
        lines = ["import os", "import sys", "def main(): pass"]

        filtered = io._remove_unused_imports(lines, ["sys"])

        assert "import sys" not in filtered
        assert "import os" in filtered

    def test_consolidate_mixed_imports(self) -> None:
        lines = ["import os", "from os import path", "def main(): pass"]

        consolidated = io._consolidate_mixed_imports(lines, ["os"])

        assert isinstance(consolidated, list)
        joined = "\n".join(consolidated)
        assert "from os import" in joined
        assert "path" in joined
        assert "os" in joined

    def test_remove_redundant_imports(self) -> None:
        lines = ["import os", "import os", "def main(): pass"]

        filtered = io._remove_redundant_imports(lines, ["Line 2: os"])

        assert filtered.count("import os") == 1

    def test_organize_imports_pep8(self) -> None:
        lines = [
            "from crackerjack.services import config",
            "import os",
            "import requests",
            "def main(): pass",
        ]

        organized = io._organize_imports_pep8(lines)

        os_index = organized.index("import os")
        requests_index = organized.index("import requests")
        local_index = organized.index("from crackerjack.services import config")
        assert os_index < requests_index < local_index


# ---------------------------------------------------------------------------
# _apply_optimizations_and_prepare_results -- including the preserved
# files_modified Path-not-str quirk (CLAUDE.md Rule 7)
# ---------------------------------------------------------------------------


class TestApplyOptimizationsAndPrepareResults:
    async def test_success_end_to_end(self, tmp_path: Path) -> None:
        test_file = tmp_path / "module.py"
        test_file.write_text("import os\nfrom os import path\n")

        analysis = await io.analyze_file(test_file, tmp_path)
        assert io._are_optimizations_needed(analysis)

        result = await io._apply_optimizations_and_prepare_results(
            test_file, analysis
        )

        assert result.success is True
        assert result.confidence == 0.85

    async def test_files_modified_contains_path_not_str_pre_existing_quirk(
        self, tmp_path: Path
    ) -> None:
        """Pre-existing quirk preserved verbatim per CLAUDE.md Rule 7:
        ``files_modified`` is typed ``list[str]`` but this code path stores
        the raw ``Path`` object (marked ``# type: ignore`` in the source),
        unlike ``_apply_direct_import_fix``/``_apply_safe_init_import_fallback``
        which correctly stringify it."""
        test_file = tmp_path / "module.py"
        test_file.write_text("import os\nfrom os import path\n")

        analysis = await io.analyze_file(test_file, tmp_path)

        result = await io._apply_optimizations_and_prepare_results(
            test_file, analysis
        )

        assert result.files_modified == [test_file]
        assert isinstance(result.files_modified[0], Path)
        assert not isinstance(result.files_modified[0], str)

    async def test_handles_optimization_error(self, tmp_path: Path) -> None:
        missing_file = tmp_path / "does_not_exist.py"
        analysis = io.ImportAnalysis(missing_file, ["os"], [], [], [], [])

        result = await io._apply_optimizations_and_prepare_results(
            missing_file, analysis
        )

        assert result.success is False
        assert result.confidence == 0.0
        assert "Failed to optimize imports" in result.remaining_issues[0]


# ---------------------------------------------------------------------------
# diagnostics
# ---------------------------------------------------------------------------


class TestDiagnostics:
    async def test_get_diagnostics_success(self, tmp_path: Path) -> None:
        (tmp_path / "module1.py").write_text("import os\n")
        (tmp_path / "module2.py").write_text("import sys\nfrom sys import argv\n")

        diagnostics = await io.get_diagnostics(tmp_path)

        assert diagnostics["agent"] == "ImportOptimizationAgent"
        assert diagnostics["files_analyzed"] == 2
        assert "capabilities" in diagnostics

    async def test_get_diagnostics_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def _boom(project_root: Path) -> None:
            raise RuntimeError("Error")

        monkeypatch.setattr(io, "_get_python_files", _boom)

        diagnostics = await io.get_diagnostics(tmp_path)

        assert diagnostics["files_analyzed"] == 0
        assert "error" in diagnostics

    def test_get_python_files(self, tmp_path: Path) -> None:
        (tmp_path / "a.py").write_text("")
        (tmp_path / "b.py").write_text("")
        (tmp_path / "c.txt").write_text("")

        files = io._get_python_files(tmp_path)

        assert len(files) == 2
        assert all(f.suffix == ".py" for f in files)


# ---------------------------------------------------------------------------
# integration
# ---------------------------------------------------------------------------


class TestIntegration:
    async def test_full_optimization_workflow(self, tmp_path: Path) -> None:
        test_file = tmp_path / "module.py"
        test_file.write_text(
            "from crackerjack.services import config\n"
            "import os\nimport requests\nfrom os import path\n"
        )

        issue = _issue(
            message="Mixed imports and ordering issues", file_path=str(test_file)
        )

        result = await io.fix_import_issue(issue, tmp_path)

        assert isinstance(result, io.FixResult)

    async def test_analyze_then_optimize(self, tmp_path: Path) -> None:
        test_file = tmp_path / "module.py"
        test_file.write_text("import os\nfrom os import path\n")

        analysis = await io.analyze_file(test_file, tmp_path)
        assert isinstance(analysis, io.ImportAnalysis)

        if any(
            [
                analysis.mixed_imports,
                analysis.redundant_imports,
                analysis.unused_imports,
            ]
        ):
            content = test_file.read_text()
            optimized = await io._optimize_imports(content, analysis)
            assert isinstance(optimized, str)

    def test_import_analysis_namedtuple(self) -> None:
        analysis = io.ImportAnalysis(
            file_path=Path("test.py"),
            mixed_imports=["os"],
            redundant_imports=["sys"],
            unused_imports=["json"],
            optimization_opportunities=["Consolidate imports"],
            import_violations=["PEP 8 violation"],
        )

        assert analysis.file_path == Path("test.py")
        assert "os" in analysis.mixed_imports
        assert "sys" in analysis.redundant_imports
        assert "json" in analysis.unused_imports
        assert len(analysis.optimization_opportunities) == 1
        assert len(analysis.import_violations) == 1
