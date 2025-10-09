"""Tests for smart file filtering service (Phase 10.2.1)."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from crackerjack.services.file_filter import SmartFileFilter


class TestSmartFileFilterInit:
    """Test SmartFileFilter initialization."""

    def test_init_with_explicit_root(self, tmp_path):
        """Test initialization with explicit project root."""
        filter_svc = SmartFileFilter(project_root=tmp_path)

        assert filter_svc.project_root == tmp_path

    def test_init_defaults_to_cwd(self):
        """Test initialization defaults to current directory."""
        filter_svc = SmartFileFilter()

        assert filter_svc.project_root == Path.cwd()

    def test_init_with_git_service(self, tmp_path):
        """Test initialization with optional git service."""
        mock_git = Mock()
        filter_svc = SmartFileFilter(git_service=mock_git, project_root=tmp_path)

        assert filter_svc.git == mock_git
        assert filter_svc.project_root == tmp_path


class TestGetChangedFiles:
    """Test get_changed_files() method."""

    def test_get_changed_files_since_head(self, tmp_path):
        """Test getting files changed since HEAD."""
        filter_svc = SmartFileFilter(project_root=tmp_path)

        # Create test files
        file1 = tmp_path / "test1.py"
        file2 = tmp_path / "test2.py"
        file1.touch()
        file2.touch()

        mock_result = Mock()
        mock_result.stdout = "test1.py\ntest2.py\n"

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            changed = filter_svc.get_changed_files("HEAD")

            assert len(changed) == 2
            assert file1 in changed
            assert file2 in changed
            mock_run.assert_called_once()

    def test_get_changed_files_filters_nonexistent(self, tmp_path):
        """Test that nonexistent files are filtered out."""
        filter_svc = SmartFileFilter(project_root=tmp_path)

        # Only create one file
        file1 = tmp_path / "exists.py"
        file1.touch()

        mock_result = Mock()
        mock_result.stdout = "exists.py\ndeleted.py\n"

        with patch("subprocess.run", return_value=mock_result):
            changed = filter_svc.get_changed_files()

            assert len(changed) == 1
            assert file1 in changed

    def test_get_changed_files_handles_git_error(self, tmp_path):
        """Test graceful handling of git command failure."""
        # mock_git removed
        filter_svc = SmartFileFilter(project_root=tmp_path)

        with patch(
            "subprocess.run", side_effect=subprocess.CalledProcessError(1, "git")
        ):
            changed = filter_svc.get_changed_files()

            assert changed == []

    def test_get_changed_files_handles_timeout(self, tmp_path):
        """Test graceful handling of git command timeout."""
        # mock_git removed
        filter_svc = SmartFileFilter(project_root=tmp_path)

        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("git", 10)):
            changed = filter_svc.get_changed_files()

            assert changed == []


class TestGetStagedFiles:
    """Test get_staged_files() method."""

    def test_get_staged_files(self, tmp_path):
        """Test getting currently staged files."""
        # mock_git removed
        filter_svc = SmartFileFilter(project_root=tmp_path)

        file1 = tmp_path / "staged.py"
        file1.touch()

        mock_result = Mock()
        mock_result.stdout = "staged.py\n"

        with patch("subprocess.run", return_value=mock_result):
            staged = filter_svc.get_staged_files()

            assert len(staged) == 1
            assert file1 in staged

    def test_get_staged_files_empty(self, tmp_path):
        """Test getting staged files when none are staged."""
        # mock_git removed
        filter_svc = SmartFileFilter(project_root=tmp_path)

        mock_result = Mock()
        mock_result.stdout = ""

        with patch("subprocess.run", return_value=mock_result):
            staged = filter_svc.get_staged_files()

            assert staged == []


class TestGetUnstagedFiles:
    """Test get_unstaged_files() method."""

    def test_get_unstaged_files(self, tmp_path):
        """Test getting unstaged modified files."""
        # mock_git removed
        filter_svc = SmartFileFilter(project_root=tmp_path)

        file1 = tmp_path / "modified.py"
        file1.touch()

        mock_result = Mock()
        mock_result.stdout = "modified.py\n"

        with patch("subprocess.run", return_value=mock_result):
            unstaged = filter_svc.get_unstaged_files()

            assert len(unstaged) == 1
            assert file1 in unstaged


class TestFilterByPattern:
    """Test filter_by_pattern() method."""

    def test_filter_by_pattern_simple(self, tmp_path):
        """Test filtering with simple glob pattern."""
        # mock_git removed
        filter_svc = SmartFileFilter(project_root=tmp_path)

        files = [
            tmp_path / "test.py",
            tmp_path / "test.md",
            tmp_path / "test.txt",
        ]

        filtered = filter_svc.filter_by_pattern(files, "*.py")

        assert len(filtered) == 1
        assert files[0] in filtered

    def test_filter_by_pattern_wildcard(self, tmp_path):
        """Test filtering with wildcard pattern."""
        # mock_git removed
        filter_svc = SmartFileFilter(project_root=tmp_path)

        files = [
            tmp_path / "test.py",
            tmp_path / "test.md",
        ]

        filtered = filter_svc.filter_by_pattern(files, "*")

        assert len(filtered) == 2

    def test_filter_by_pattern_complex(self, tmp_path):
        """Test filtering with complex pattern."""
        # mock_git removed
        filter_svc = SmartFileFilter(project_root=tmp_path)

        files = [
            tmp_path / "test_file.py",
            tmp_path / "production.py",
        ]

        filtered = filter_svc.filter_by_pattern(files, "test_*.py")

        assert len(filtered) == 1
        assert files[0] in filtered


class TestFilterByTool:
    """Test filter_by_tool() method."""

    def test_filter_by_tool_python(self, tmp_path):
        """Test filtering for Python tools."""
        # mock_git removed
        filter_svc = SmartFileFilter(project_root=tmp_path)

        files = [
            tmp_path / "test.py",
            tmp_path / "test.md",
            tmp_path / "test.txt",
        ]

        # Test ruff-check (Python tool)
        filtered = filter_svc.filter_by_tool(files, "ruff-check")

        assert len(filtered) == 1
        assert files[0] in filtered

    def test_filter_by_tool_markdown(self, tmp_path):
        """Test filtering for Markdown tools."""
        # mock_git removed
        filter_svc = SmartFileFilter(project_root=tmp_path)

        files = [
            tmp_path / "test.py",
            tmp_path / "README.md",
        ]

        # Test mdformat (Markdown tool)
        filtered = filter_svc.filter_by_tool(files, "mdformat")

        assert len(filtered) == 1
        assert files[1] in filtered

    def test_filter_by_tool_yaml(self, tmp_path):
        """Test filtering for YAML tools."""
        # mock_git removed
        filter_svc = SmartFileFilter(project_root=tmp_path)

        files = [
            tmp_path / "config.yaml",
            tmp_path / "data.yml",
            tmp_path / "test.py",
        ]

        # Test check-yaml (YAML tool)
        filtered = filter_svc.filter_by_tool(files, "check-yaml")

        assert len(filtered) == 2
        assert files[0] in filtered
        assert files[1] in filtered

    def test_filter_by_tool_all_files(self, tmp_path):
        """Test filtering for tools that apply to all files."""
        # mock_git removed
        filter_svc = SmartFileFilter(project_root=tmp_path)

        files = [
            tmp_path / "test.py",
            tmp_path / "test.md",
            tmp_path / "test.txt",
        ]

        # Test trailing-whitespace (applies to all files)
        filtered = filter_svc.filter_by_tool(files, "trailing-whitespace")

        assert len(filtered) == 3

    def test_filter_by_tool_unknown_tool(self, tmp_path):
        """Test filtering with unknown tool falls back to wildcard."""
        # mock_git removed
        filter_svc = SmartFileFilter(project_root=tmp_path)

        files = [
            tmp_path / "test.py",
            tmp_path / "test.md",
        ]

        # Unknown tool should match all files (fallback)
        filtered = filter_svc.filter_by_tool(files, "unknown-tool-xyz")

        assert len(filtered) == 2

    def test_filter_by_tool_removes_duplicates(self, tmp_path):
        """Test that filter_by_tool removes duplicate paths."""
        # mock_git removed
        filter_svc = SmartFileFilter(project_root=tmp_path)

        # Single Python file
        files = [tmp_path / "test.py"]

        # Tool with multiple patterns that could match same file
        with patch.object(
            filter_svc, "filter_by_pattern", return_value=files * 3
        ):  # Simulate duplicates
            filtered = filter_svc.filter_by_tool(files, "ruff-check")

            # Should remove duplicates
            assert len(filtered) == len(set(filtered))


class TestGetAllModifiedFiles:
    """Test get_all_modified_files() method."""

    def test_get_all_modified_combines_staged_and_unstaged(self, tmp_path):
        """Test that method combines staged and unstaged files."""
        # mock_git removed
        filter_svc = SmartFileFilter(project_root=tmp_path)

        file1 = tmp_path / "staged.py"
        file2 = tmp_path / "unstaged.py"
        file1.touch()
        file2.touch()

        with patch.object(
            filter_svc, "get_staged_files", return_value=[file1]
        ), patch.object(filter_svc, "get_unstaged_files", return_value=[file2]):
            all_modified = filter_svc.get_all_modified_files()

            assert len(all_modified) == 2
            assert file1 in all_modified
            assert file2 in all_modified

    def test_get_all_modified_removes_duplicates(self, tmp_path):
        """Test that method removes duplicate files (both staged and unstaged)."""
        # mock_git removed
        filter_svc = SmartFileFilter(project_root=tmp_path)

        file1 = tmp_path / "both.py"
        file1.touch()

        # File appears in both staged and unstaged
        with patch.object(
            filter_svc, "get_staged_files", return_value=[file1]
        ), patch.object(filter_svc, "get_unstaged_files", return_value=[file1]):
            all_modified = filter_svc.get_all_modified_files()

            # Should only appear once
            assert len(all_modified) == 1
            assert file1 in all_modified


class TestFilterByExtensions:
    """Test filter_by_extensions() method."""

    def test_filter_by_extensions_with_dot(self, tmp_path):
        """Test filtering with extensions including leading dot."""
        # mock_git removed
        filter_svc = SmartFileFilter(project_root=tmp_path)

        files = [
            tmp_path / "test.py",
            tmp_path / "test.md",
            tmp_path / "test.txt",
        ]

        filtered = filter_svc.filter_by_extensions(files, [".py", ".md"])

        assert len(filtered) == 2
        assert files[0] in filtered
        assert files[1] in filtered

    def test_filter_by_extensions_without_dot(self, tmp_path):
        """Test filtering with extensions without leading dot."""
        # mock_git removed
        filter_svc = SmartFileFilter(project_root=tmp_path)

        files = [
            tmp_path / "test.py",
            tmp_path / "test.md",
        ]

        # Should normalize extensions to include dot
        filtered = filter_svc.filter_by_extensions(files, ["py"])

        assert len(filtered) == 1
        assert files[0] in filtered


class TestConvenienceMethods:
    """Test convenience methods for common file types."""

    def test_get_python_files(self, tmp_path):
        """Test get_python_files convenience method."""
        # mock_git removed
        filter_svc = SmartFileFilter(project_root=tmp_path)

        files = [
            tmp_path / "test.py",
            tmp_path / "test.md",
            tmp_path / "script.py",
        ]

        python_files = filter_svc.get_python_files(files)

        assert len(python_files) == 2
        assert files[0] in python_files
        assert files[2] in python_files

    def test_get_markdown_files(self, tmp_path):
        """Test get_markdown_files convenience method."""
        # mock_git removed
        filter_svc = SmartFileFilter(project_root=tmp_path)

        files = [
            tmp_path / "README.md",
            tmp_path / "test.py",
            tmp_path / "CHANGELOG.md",
        ]

        markdown_files = filter_svc.get_markdown_files(files)

        assert len(markdown_files) == 2
        assert files[0] in markdown_files
        assert files[2] in markdown_files
