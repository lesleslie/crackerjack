"""Tests for codespell wrapper tool."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from crackerjack.tools.codespell_wrapper import _is_ignored_file, main


class TestMain:
    """Tests for main function."""

    @patch("crackerjack.tools.codespell_wrapper.get_git_tracked_files")
    def test_no_files(self, mock_get) -> None:
        """Test with no git-tracked files."""
        mock_get.return_value = []
        result = main()
        assert result == 1

    @patch("crackerjack.tools.codespell_wrapper.get_git_tracked_files")
    @patch("subprocess.run")
    def test_success_with_files(self, mock_run, mock_get) -> None:
        """Test successful codespell run."""
        mock_file = Path("/tmp/test.py")
        mock_get.return_value = [mock_file]
        mock_result = MagicMock(returncode=0)
        mock_run.return_value = mock_result

        result = main()
        assert result == 0
        mock_run.assert_called_once()

    @patch("crackerjack.tools.codespell_wrapper.get_git_tracked_files")
    @patch("subprocess.run")
    def test_error_return_code(self, mock_run, mock_get) -> None:
        """Test codespell returns error code."""
        mock_file = Path("/tmp/test.py")
        mock_get.return_value = [mock_file]
        mock_result = MagicMock(returncode=1)
        mock_run.return_value = mock_result

        result = main()
        assert result == 1

    @patch("crackerjack.tools.codespell_wrapper.get_git_tracked_files")
    @patch("subprocess.run")
    def test_file_not_found_exception(self, mock_run, mock_get) -> None:
        """Test FileNotFoundError returns 127."""
        mock_file = Path("/tmp/test.py")
        mock_get.return_value = [mock_file]
        mock_run.side_effect = FileNotFoundError()

        result = main()
        assert result == 127

    @patch("crackerjack.tools.codespell_wrapper.get_git_tracked_files")
    @patch("subprocess.run")
    def test_general_exception(self, mock_run, mock_get) -> None:
        """Test general exception returns 1."""
        mock_file = Path("/tmp/test.py")
        mock_get.return_value = [mock_file]
        mock_run.side_effect = Exception("Test error")

        result = main()
        assert result == 1

    @patch("crackerjack.tools.codespell_wrapper.get_git_tracked_files")
    @patch("crackerjack.tools.codespell_wrapper.Path.cwd")
    @patch("subprocess.run")
    def test_uses_venv_binary_when_exists(self, mock_run, mock_cwd, mock_get, tmp_path: Path) -> None:
        """Test uses .venv/bin/codespell when it exists."""
        mock_file = Path("/tmp/test.py")
        mock_get.return_value = [mock_file]
        mock_cwd.return_value = tmp_path

        # Create venv binary
        venv_bin = tmp_path / ".venv" / "bin" / "codespell"
        venv_bin.parent.mkdir(parents=True, exist_ok=True)
        venv_bin.write_text("")
        venv_bin.chmod(0o755)

        mock_result = MagicMock(returncode=0)
        mock_run.return_value = mock_result

        result = main()

        assert result == 0
        call_args = mock_run.call_args[0][0]
        assert str(venv_bin) in call_args[0]

    @patch("crackerjack.tools.codespell_wrapper.get_git_tracked_files")
    @patch("crackerjack.tools.codespell_wrapper.Path.cwd")
    @patch("crackerjack.tools.codespell_wrapper.shutil.which")
    @patch("subprocess.run")
    def test_uses_global_binary_when_venv_missing(self, mock_run, mock_which, mock_cwd, mock_get, tmp_path: Path) -> None:
        """Test uses global codespell when venv not found."""
        mock_file = Path("/tmp/test.py")
        mock_get.return_value = [mock_file]
        mock_cwd.return_value = tmp_path
        mock_which.return_value = "/usr/bin/codespell"

        mock_result = MagicMock(returncode=0)
        mock_run.return_value = mock_result

        result = main()

        assert result == 0
        call_args = mock_run.call_args[0][0]
        assert "/usr/bin/codespell" in call_args

    @patch("crackerjack.tools.codespell_wrapper.get_git_tracked_files")
    @patch("crackerjack.tools.codespell_wrapper.Path.cwd")
    @patch("crackerjack.tools.codespell_wrapper.shutil.which")
    @patch("subprocess.run")
    def test_uses_fallback_when_no_binary_found(self, mock_run, mock_which, mock_cwd, mock_get, tmp_path: Path) -> None:
        """Test uses fallback 'codespell' when binary not found."""
        mock_file = Path("/tmp/test.py")
        mock_get.return_value = [mock_file]
        mock_cwd.return_value = tmp_path
        mock_which.return_value = None

        mock_result = MagicMock(returncode=0)
        mock_run.return_value = mock_result

        result = main()

        call_args = mock_run.call_args[0][0]
        assert call_args[0] == "codespell"

    @patch("crackerjack.tools.codespell_wrapper.get_git_tracked_files")
    @patch("subprocess.run")
    def test_includes_write_changes_flag(self, mock_run, mock_get) -> None:
        """Test --write-changes flag is always included."""
        mock_file = Path("/tmp/test.py")
        mock_get.return_value = [mock_file]
        mock_result = MagicMock(returncode=0)
        mock_run.return_value = mock_result

        result = main()

        call_args = mock_run.call_args[0][0]
        assert "--write-changes" in call_args

    @patch("crackerjack.tools.codespell_wrapper.get_git_tracked_files")
    @patch("subprocess.run")
    def test_passes_custom_arguments(self, mock_run, mock_get) -> None:
        """Test custom arguments are passed to codespell."""
        mock_file = Path("/tmp/test.py")
        mock_get.return_value = [mock_file]
        mock_result = MagicMock(returncode=0)
        mock_run.return_value = mock_result

        result = main(["--ignore-words-list", "foo,bar"])

        call_args = mock_run.call_args[0][0]
        assert "--ignore-words-list" in call_args
        assert "foo,bar" in call_args

    @patch("crackerjack.tools.codespell_wrapper.get_git_tracked_files")
    @patch("subprocess.run")
    def test_passes_file_paths_to_codespell(self, mock_run, mock_get) -> None:
        """Test file paths are passed to codespell."""
        file1 = Path("/tmp/test1.py")
        file2 = Path("/tmp/test2.py")
        mock_get.return_value = [file1, file2]
        mock_result = MagicMock(returncode=0)
        mock_run.return_value = mock_result

        result = main()

        call_args = mock_run.call_args[0][0]
        assert str(file1) in call_args
        assert str(file2) in call_args

    @patch("crackerjack.tools.codespell_wrapper.get_git_tracked_files")
    @patch("subprocess.run")
    def test_uses_current_working_directory(self, mock_run, mock_get) -> None:
        """Test subprocess runs in current working directory."""
        mock_file = Path("/tmp/test.py")
        mock_get.return_value = [mock_file]
        mock_result = MagicMock(returncode=0)
        mock_run.return_value = mock_result

        from pathlib import Path as PathCls
        with patch("crackerjack.tools.codespell_wrapper.Path.cwd") as mock_cwd:
            mock_cwd.return_value = PathCls("/some/path")
            result = main()

        call_kwargs = mock_run.call_args[1]
        assert call_kwargs.get("cwd") == PathCls("/some/path")

    @patch("crackerjack.tools.codespell_wrapper.get_git_tracked_files")
    @patch("subprocess.run")
    def test_check_false_parameter(self, mock_run, mock_get) -> None:
        """Test subprocess called with check=False."""
        mock_file = Path("/tmp/test.py")
        mock_get.return_value = [mock_file]
        mock_result = MagicMock(returncode=0)
        mock_run.return_value = mock_result

        result = main()

        call_kwargs = mock_run.call_args[1]
        assert call_kwargs.get("check") is False


class TestIsIgnoredFile:
    """Tests for the _is_ignored_file lockfile filter.

    Lockfiles contain legitimate non-English package names
    (``asteroid``, ``tldextract``, ``passlib``, ...) that codespell
    mis-flags as misspellings. The wrapper's filter must skip them
    so we don't have to maintain a per-package ignore list.
    """

    @pytest.mark.parametrize(
        "filename",
        [
            "uv.lock",
            "poetry.lock",
            "Cargo.lock",
            "package-lock.json",
            "yarn.lock",
            "pnpm-lock.yaml",
        ],
    )
    def test_skips_lockfiles(self, filename: str) -> None:
        """All common lockfile names/extensions are filtered out."""
        assert _is_ignored_file(Path(filename)) is True
        # ...and the same is true when nested in a subdirectory.
        assert _is_ignored_file(Path("subdir/nested") / filename) is True

    @pytest.mark.parametrize(
        "filename",
        [
            "README.md",
            "src/module.py",
            "docs/guide.rst",
            "data/note.txt",
        ],
    )
    def test_keeps_normal_source_files(self, filename: str) -> None:
        """Regular source/doc files are NOT filtered out."""
        assert _is_ignored_file(Path(filename)) is False

    def test_skips_backup_files(self) -> None:
        """Existing backup-suffix behaviour still works."""
        assert _is_ignored_file(Path("module.py.bak")) is True
        assert _is_ignored_file(Path("notes.txt.backup")) is True

    def test_skips_skip_dirs(self) -> None:
        """Existing _SKIP_DIRS behaviour still works."""
        assert _is_ignored_file(Path(".venv/lib/foo.py")) is True
        assert _is_ignored_file(Path("node_modules/x.js")) is True

    @patch("crackerjack.tools.codespell_wrapper.get_git_tracked_files")
    @patch("subprocess.run")
    def test_lockfiles_excluded_from_codespell_invocation(
        self, mock_run, mock_get
    ) -> None:
        """When tracked files include uv.lock, codespell must not see it."""
        mock_get.return_value = [
            Path("README.md"),
            Path("uv.lock"),
            Path("src/module.py"),
        ]
        mock_result = MagicMock(returncode=0)
        mock_run.return_value = mock_result

        result = main()
        assert result == 0

        call_args = mock_run.call_args[0][0]
        assert "README.md" in call_args
        assert "src/module.py" in call_args
        assert "uv.lock" not in call_args
