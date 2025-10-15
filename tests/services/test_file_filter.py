import subprocess
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from crackerjack.models.protocols import GitServiceProtocol
from crackerjack.services.file_filter import SmartFileFilter


@pytest.fixture
def mock_git_service() -> MagicMock:
    return MagicMock(spec=GitServiceProtocol)


class TestSmartFileFilterInit:
    """Test SmartFileFilter initialization."""

    def test_init_with_explicit_root(self, tmp_path, mock_git_service: MagicMock):
        """Test initialization with explicit project root."""
        filter_svc = SmartFileFilter(git_service=mock_git_service, project_root=tmp_path)

        assert filter_svc.project_root == tmp_path
        assert filter_svc._git_service == mock_git_service

    def test_init_defaults_to_cwd(self, mock_git_service: MagicMock):
        """Test initialization defaults to current directory."""
        filter_svc = SmartFileFilter(git_service=mock_git_service)

        assert filter_svc.project_root == Path.cwd()
        assert filter_svc._git_service == mock_git_service


class TestGetChangedFiles:
    """Test get_changed_files() method."""

    def test_get_changed_files_since_head(self, tmp_path, mock_git_service: MagicMock):
        """Test getting files changed since HEAD."""
        filter_svc = SmartFileFilter(git_service=mock_git_service, project_root=tmp_path)

        expected_files = [tmp_path / "test1.py", tmp_path / "test2.py"]
        mock_git_service.get_changed_files_since.return_value = expected_files

        changed = filter_svc.get_changed_files("HEAD")

        assert changed == expected_files
        mock_git_service.get_changed_files_since.assert_called_once_with("HEAD", tmp_path)

    def test_get_changed_files_handles_git_error(self, tmp_path, mock_git_service: MagicMock):
        """Test graceful handling of git command failure."""
        filter_svc = SmartFileFilter(git_service=mock_git_service, project_root=tmp_path)

        mock_git_service.get_changed_files_since.side_effect = Exception("Git error")

        with pytest.raises(Exception, match="Git error"):
            filter_svc.get_changed_files()

        mock_git_service.get_changed_files_since.assert_called_once_with("HEAD", tmp_path)


class TestGetStagedFiles:
    """Test get_staged_files() method."""

    def test_get_staged_files(self, tmp_path, mock_git_service: MagicMock):
        """Test getting currently staged files."""
        filter_svc = SmartFileFilter(git_service=mock_git_service, project_root=tmp_path)

        expected_files = [tmp_path / "staged.py"]
        mock_git_service.get_staged_files.return_value = expected_files

        staged = filter_svc.get_staged_files()

        assert staged == expected_files
        mock_git_service.get_staged_files.assert_called_once_with(tmp_path)


class TestGetUnstagedFiles:
    """Test get_unstaged_files() method."""

    def test_get_unstaged_files(self, tmp_path, mock_git_service: MagicMock):
        """Test getting unstaged modified files."""
        filter_svc = SmartFileFilter(git_service=mock_git_service, project_root=tmp_path)

        expected_files = [tmp_path / "modified.py"]
        mock_git_service.get_unstaged_files.return_value = expected_files

        unstaged = filter_svc.get_unstaged_files()

        assert unstaged == expected_files
        mock_git_service.get_unstaged_files.assert_called_once_with(tmp_path)


class TestFilterByPattern:
    """Test filter_by_pattern() method."""

    def test_filter_by_pattern_simple(self, tmp_path, mock_git_service: MagicMock):
        """Test filtering with simple glob pattern."""
        filter_svc = SmartFileFilter(git_service=mock_git_service, project_root=tmp_path)

        files = [
            tmp_path / "test.py",
            tmp_path / "test.md",
            tmp_path / "test.txt",
        ]

        filtered = filter_svc.filter_by_pattern(files, "*.py")

        assert len(filtered) == 1
        assert files[0] in filtered

    def test_filter_by_pattern_wildcard(self, tmp_path, mock_git_service: MagicMock):
        """Test filtering with wildcard pattern."""
        filter_svc = SmartFileFilter(git_service=mock_git_service, project_root=tmp_path)

        files = [
            tmp_path / "test.py",
            tmp_path / "test.md",
        ]

        filtered = filter_svc.filter_by_pattern(files, "*")

        assert len(filtered) == 2

    def test_filter_by_pattern_complex(self, tmp_path, mock_git_service: MagicMock):
        """Test filtering with complex pattern."""
        filter_svc = SmartFileFilter(git_service=mock_git_service, project_root=tmp_path)

        files = [
            tmp_path / "test_file.py",
            tmp_path / "production.py",
        ]

        filtered = filter_svc.filter_by_pattern(files, "test_*.py")

        assert len(filtered) == 1
        assert files[0] in filtered


class TestFilterByTool:
    """Test filter_by_tool() method."""

    def test_filter_by_tool_python(self, tmp_path, mock_git_service: MagicMock):
        """Test filtering for Python tools."""
        filter_svc = SmartFileFilter(git_service=mock_git_service, project_root=tmp_path)

        files = [
            tmp_path / "test.py",
            tmp_path / "test.md",
            tmp_path / "test.txt",
        ]

        # Test ruff-check (Python tool)
        filtered = filter_svc.filter_by_tool(files, "ruff-check")

        assert len(filtered) == 1
        assert files[0] in filtered

    def test_filter_by_tool_markdown(self, tmp_path, mock_git_service: MagicMock):
        """Test filtering for Markdown tools."""
        filter_svc = SmartFileFilter(git_service=mock_git_service, project_root=tmp_path)

        files = [
            tmp_path / "test.py",
            tmp_path / "README.md",
        ]

        # Test mdformat (Markdown tool)
        filtered = filter_svc.filter_by_tool(files, "mdformat")

        assert len(filtered) == 1
        assert files[1] in filtered

    def test_filter_by_tool_yaml(self, tmp_path, mock_git_service: MagicMock):
        """Test filtering for YAML tools."""
        filter_svc = SmartFileFilter(git_service=mock_git_service, project_root=tmp_path)

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

    def test_filter_by_tool_all_files(self, tmp_path, mock_git_service: MagicMock):
        """Test filtering for tools that apply to all files."""
        filter_svc = SmartFileFilter(git_service=mock_git_service, project_root=tmp_path)

        files = [
            tmp_path / "test.py",
            tmp_path / "test.md",
            tmp_path / "test.txt",
        ]

        # Test trailing-whitespace (applies to all files)
        filtered = filter_svc.filter_by_tool(files, "trailing-whitespace")

        assert len(filtered) == 3

    def test_filter_by_tool_unknown_tool(self, tmp_path, mock_git_service: MagicMock):
        """Test filtering with unknown tool falls back to wildcard."""
        filter_svc = SmartFileFilter(git_service=mock_git_service, project_root=tmp_path)

        files = [
            tmp_path / "test.py",
            tmp_path / "test.md",
        ]

        # Unknown tool should match all files (fallback)
        filtered = filter_svc.filter_by_tool(files, "unknown-tool-xyz")

        assert len(filtered) == 2

    def test_filter_by_tool_removes_duplicates(self, tmp_path, mock_git_service: MagicMock):
        """Test that filter_by_tool removes duplicate paths."""
        filter_svc = SmartFileFilter(git_service=mock_git_service, project_root=tmp_path)

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

    def test_get_all_modified_combines_staged_and_unstaged(self, tmp_path, mock_git_service: MagicMock):
        """Test that method combines staged and unstaged files."""
        filter_svc = SmartFileFilter(git_service=mock_git_service, project_root=tmp_path)

        file1 = tmp_path / "staged.py"
        file2 = tmp_path / "unstaged.py"

        mock_git_service.get_staged_files.return_value = [file1]
        mock_git_service.get_unstaged_files.return_value = [file2]

        all_modified = filter_svc.get_all_modified_files()

        assert len(all_modified) == 2
        assert file1 in all_modified
        assert file2 in all_modified
        mock_git_service.get_staged_files.assert_called_once_with(tmp_path)
        mock_git_service.get_unstaged_files.assert_called_once_with(tmp_path)

    def test_get_all_modified_removes_duplicates(self, tmp_path, mock_git_service: MagicMock):
        """Test that method removes duplicate files (both staged and unstaged)."""
        filter_svc = SmartFileFilter(git_service=mock_git_service, project_root=tmp_path)

        file1 = tmp_path / "both.py"

        mock_git_service.get_staged_files.return_value = [file1]
        mock_git_service.get_unstaged_files.return_value = [file1]

        all_modified = filter_svc.get_all_modified_files()

        assert len(all_modified) == 1
        assert file1 in all_modified
        mock_git_service.get_staged_files.assert_called_once_with(tmp_path)
        mock_git_service.get_unstaged_files.assert_called_once_with(tmp_path)


class TestFilterByExtensions:
    """Test filter_by_extensions() method."""

    def test_filter_by_extensions_with_dot(self, tmp_path, mock_git_service: MagicMock):
        """Test filtering with extensions including leading dot."""
        filter_svc = SmartFileFilter(git_service=mock_git_service, project_root=tmp_path)

        files = [
            tmp_path / "test.py",
            tmp_path / "test.md",
            tmp_path / "test.txt",
        ]

        filtered = filter_svc.filter_by_extensions(files, [".py", ".md"])

        assert len(filtered) == 2
        assert files[0] in filtered
        assert files[1] in filtered

    def test_filter_by_extensions_without_dot(self, tmp_path, mock_git_service: MagicMock):
        """Test filtering with extensions without leading dot."""
        filter_svc = SmartFileFilter(git_service=mock_git_service, project_root=tmp_path)

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

    def test_get_python_files(self, tmp_path, mock_git_service: MagicMock):
        """Test get_python_files convenience method."""
        filter_svc = SmartFileFilter(git_service=mock_git_service, project_root=tmp_path)

        files = [
            tmp_path / "test.py",
            tmp_path / "test.md",
            tmp_path / "script.py",
        ]

        python_files = filter_svc.get_python_files(files)

        assert len(python_files) == 2
        assert files[0] in python_files
        assert files[2] in python_files

    def test_get_markdown_files(self, tmp_path, mock_git_service: MagicMock):
        """Test get_markdown_files convenience method."""
        filter_svc = SmartFileFilter(git_service=mock_git_service, project_root=tmp_path)

        files = [
            tmp_path / "README.md",
            tmp_path / "test.py",
            tmp_path / "CHANGELOG.md",
        ]

        markdown_files = filter_svc.get_markdown_files(files)

        assert len(markdown_files) == 2
        assert files[0] in markdown_files
        assert files[2] in markdown_files
