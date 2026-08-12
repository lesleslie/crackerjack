"""Tests for syrupy_wrapper tool.

The wrapper auto-discovers snapshot tests by walking ``tests/`` for files with
sibling ``__snapshots__/`` directories containing at least one entry. When no
snapshot tests exist, the hook exits 0 so projects that do not use syrupy are
not flagged as failures.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from crackerjack.tools.syrupy_wrapper import find_snapshot_tests, main


class TestFindSnapshotTests:
    def test_returns_empty_when_tests_dir_missing(self, tmp_path: Path) -> None:
        assert find_snapshot_tests(tmp_path / "missing") == []

    def test_returns_empty_when_no_snapshot_tests(self, tmp_path: Path) -> None:
        (tmp_path / "test_alpha.py").write_text("def test_x() -> None: pass\n")
        assert find_snapshot_tests(tmp_path) == []

    def test_ignores_file_with_snapshot_in_name_only(self, tmp_path: Path) -> None:
        # Filename heuristic would falsely match runtime-snapshot tests that
        # don't use syrupy. Only sibling __snapshots__/ directories qualify.
        (tmp_path / "test_runtime_snapshots.py").write_text("def test_x(): pass\n")
        assert find_snapshot_tests(tmp_path) == []

    def test_finds_file_with_sibling_snapshot_dir(self, tmp_path: Path) -> None:
        test_file = tmp_path / "test_alpha.py"
        test_file.write_text("def test_x() -> None: pass\n")
        snap_dir = tmp_path / "__snapshots__"
        snap_dir.mkdir()
        (snap_dir / "test_alpha.ambr").write_text("'snapshot'\n")

        result = find_snapshot_tests(tmp_path)
        assert result == [str(test_file)]

    def test_ignores_empty_snapshot_dir(self, tmp_path: Path) -> None:
        (tmp_path / "test_alpha.py").write_text("def test_x() -> None: pass\n")
        (tmp_path / "__snapshots__").mkdir()  # empty

        assert find_snapshot_tests(tmp_path) == []

    def test_finds_files_in_nested_dirs(self, tmp_path: Path) -> None:
        nested = tmp_path / "unit" / "channel"
        nested.mkdir(parents=True)
        test_file = nested / "test_state.py"
        test_file.write_text("def test_x() -> None: pass\n")
        (nested / "__snapshots__").mkdir()
        (nested / "__snapshots__" / "test_state.ambr").write_text("'x'\n")

        result = find_snapshot_tests(tmp_path)
        assert result == [str(test_file)]

    def test_results_are_sorted_and_unique(self, tmp_path: Path) -> None:
        a = tmp_path / "test_alpha.py"
        a.write_text("def test_x() -> None: pass\n")
        (tmp_path / "__snapshots__").mkdir()
        (tmp_path / "__snapshots__" / "test_alpha.ambr").write_text("'x'\n")
        nested = tmp_path / "unit"
        nested.mkdir()
        b = nested / "test_beta.py"
        b.write_text("def test_y() -> None: pass\n")
        (nested / "__snapshots__").mkdir()
        (nested / "__snapshots__" / "test_beta.ambr").write_text("'y'\n")

        result = find_snapshot_tests(tmp_path)
        assert result == sorted(set(result))
        assert str(a) in result
        assert str(b) in result


class TestMain:
    @patch("crackerjack.tools.syrupy_wrapper.find_snapshot_tests")
    @patch("crackerjack.tools.syrupy_wrapper.pytest.main")
    def test_exits_zero_when_no_snapshot_tests(
        self, mock_pytest_main, mock_find, capsys: pytest.CaptureFixture[str]
    ) -> None:
        mock_find.return_value = []

        result = main()

        assert result == 0
        mock_pytest_main.assert_not_called()
        captured = capsys.readouterr()
        assert "skipping" in captured.out.lower()

    @patch("crackerjack.tools.syrupy_wrapper.find_snapshot_tests")
    @patch("crackerjack.tools.syrupy_wrapper.pytest.main")
    def test_runs_pytest_on_discovered_tests(
        self, mock_pytest_main, mock_find
    ) -> None:
        mock_find.return_value = ["tests/unit/test_x.py"]
        mock_pytest_main.return_value = 0

        result = main()

        assert result == 0
        mock_pytest_main.assert_called_once()
        args = mock_pytest_main.call_args.args[0]
        assert "tests/unit/test_x.py" in args
        assert "syrupy" in args
        assert "not slow" in args

    @patch("crackerjack.tools.syrupy_wrapper.find_snapshot_tests")
    @patch("crackerjack.tools.syrupy_wrapper.pytest.main")
    def test_propagates_pytest_exit_code(
        self, mock_pytest_main, mock_find
    ) -> None:
        mock_find.return_value = ["tests/unit/test_x.py"]
        mock_pytest_main.return_value = 5  # pytest: no tests collected

        result = main()

        assert result == 5
