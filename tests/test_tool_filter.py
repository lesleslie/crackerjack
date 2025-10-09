"""Tests for Phase 10.3.3: Tool Filtering Logic."""

from pathlib import Path

import pytest

from crackerjack.services.incremental_executor import IncrementalExecutor
from crackerjack.services.tool_filter import (
    FilterConfig,
    FilterResult,
    ToolFilter,
    create_changed_files_filter,
    create_combined_filter,
    create_tool_only_filter,
)


class TestFilterConfig:
    """Test FilterConfig dataclass."""

    def test_filter_config_defaults(self):
        """Test FilterConfig initializes with defaults."""
        config = FilterConfig()

        assert config.tool_name is None
        assert config.changed_only is False
        assert config.file_patterns == []
        assert config.exclude_patterns == []

    def test_filter_config_tool_name(self):
        """Test FilterConfig with tool_name."""
        config = FilterConfig(tool_name="ruff-check")

        assert config.tool_name == "ruff-check"

    def test_filter_config_changed_only(self):
        """Test FilterConfig with changed_only."""
        config = FilterConfig(changed_only=True)

        assert config.changed_only is True

    def test_filter_config_patterns(self):
        """Test FilterConfig with file patterns."""
        config = FilterConfig(
            file_patterns=["*.py", "*.pyi"],
            exclude_patterns=["test_*.py"],
        )

        assert config.file_patterns == ["*.py", "*.pyi"]
        assert config.exclude_patterns == ["test_*.py"]


class TestFilterResult:
    """Test FilterResult dataclass and properties."""

    def test_filter_result_initialization(self):
        """Test FilterResult can be initialized."""
        result = FilterResult(
            total_tools=5,
            filtered_tools=["tool1", "tool2"],
            skipped_tools=["tool3", "tool4", "tool5"],
            total_files=100,
            filtered_files=[Path("file1.py")],
            skipped_files=[Path(f"file{i}.py") for i in range(2, 101)],
            filter_effectiveness=98.0,
        )

        assert result.total_tools == 5
        assert len(result.filtered_tools) == 2
        assert len(result.skipped_tools) == 3
        assert result.total_files == 100
        assert result.filter_effectiveness == 98.0

    def test_tools_filtered_out_property(self):
        """Test tools_filtered_out property."""
        result = FilterResult(
            total_tools=5,
            filtered_tools=["tool1"],
            skipped_tools=["tool2", "tool3", "tool4", "tool5"],
            total_files=0,
            filtered_files=[],
            skipped_files=[],
            filter_effectiveness=80.0,
        )

        assert result.tools_filtered_out == 4

    def test_files_filtered_out_property(self):
        """Test files_filtered_out property."""
        result = FilterResult(
            total_tools=1,
            filtered_tools=["tool1"],
            skipped_tools=[],
            total_files=100,
            filtered_files=[Path("file1.py")],
            skipped_files=[Path(f"file{i}.py") for i in range(2, 101)],
            filter_effectiveness=99.0,
        )

        assert result.files_filtered_out == 99


class TestToolFilter:
    """Test ToolFilter class."""

    def test_filter_tools_no_filter(self):
        """Test filter_tools with no filtering."""
        config = FilterConfig()
        filter_obj = ToolFilter(config=config)

        available_tools = ["ruff-check", "bandit", "zuban"]
        result = filter_obj.filter_tools(available_tools)

        assert result.total_tools == 3
        assert result.filtered_tools == ["ruff-check", "bandit", "zuban"]
        assert result.skipped_tools == []
        assert result.filter_effectiveness == 0.0

    def test_filter_tools_specific_tool(self):
        """Test filter_tools with specific tool."""
        config = FilterConfig(tool_name="bandit")
        filter_obj = ToolFilter(config=config)

        available_tools = ["ruff-check", "bandit", "zuban"]
        result = filter_obj.filter_tools(available_tools)

        assert result.filtered_tools == ["bandit"]
        assert result.skipped_tools == ["ruff-check", "zuban"]
        assert result.filter_effectiveness == pytest.approx(66.67, abs=0.01)

    def test_filter_tools_nonexistent_tool(self):
        """Test filter_tools with nonexistent tool."""
        config = FilterConfig(tool_name="nonexistent")
        filter_obj = ToolFilter(config=config)

        available_tools = ["ruff-check", "bandit", "zuban"]
        result = filter_obj.filter_tools(available_tools)

        assert result.filtered_tools == []
        assert result.skipped_tools == available_tools
        assert result.filter_effectiveness == 100.0

    def test_filter_files_no_filter(self, tmp_path: Path):
        """Test filter_files with no filtering."""
        config = FilterConfig()
        filter_obj = ToolFilter(config=config)

        files = [tmp_path / f"file{i}.py" for i in range(5)]
        result = filter_obj.filter_files("test-tool", files)

        assert len(result.filtered_files) == 5
        assert result.skipped_files == []
        assert result.filter_effectiveness == 0.0

    def test_filter_files_changed_only(self, tmp_path: Path):
        """Test filter_files with changed_only flag."""
        # Create test files
        file1 = tmp_path / "file1.py"
        file2 = tmp_path / "file2.py"
        file3 = tmp_path / "file3.py"
        file1.write_text("content1")
        file2.write_text("content2")
        file3.write_text("content3")

        # Setup executor with cache for file1 and file2
        executor = IncrementalExecutor(cache_dir=tmp_path / "cache")

        def dummy_func(file: Path) -> str:
            return "ok"

        executor.execute_incremental("test-tool", [file1, file2], dummy_func)

        # Now filter with changed_only (file3 is new/changed)
        config = FilterConfig(changed_only=True)
        filter_obj = ToolFilter(config=config, executor=executor)

        result = filter_obj.filter_files("test-tool", [file1, file2, file3])

        assert file3 in result.filtered_files
        assert file1 not in result.filtered_files
        assert file2 not in result.filtered_files
        assert result.filter_effectiveness == pytest.approx(66.67, abs=0.01)

    def test_filter_files_include_patterns(self, tmp_path: Path):
        """Test filter_files with include patterns."""
        files = [
            tmp_path / "file1.py",
            tmp_path / "file2.txt",
            tmp_path / "file3.py",
        ]

        config = FilterConfig(file_patterns=["*.py"])
        filter_obj = ToolFilter(config=config)

        result = filter_obj.filter_files("test-tool", files)

        assert len(result.filtered_files) == 2
        assert tmp_path / "file1.py" in result.filtered_files
        assert tmp_path / "file3.py" in result.filtered_files
        assert tmp_path / "file2.txt" not in result.filtered_files

    def test_filter_files_exclude_patterns(self, tmp_path: Path):
        """Test filter_files with exclude patterns."""
        files = [
            tmp_path / "file1.py",
            tmp_path / "test_file2.py",
            tmp_path / "file3.py",
        ]

        config = FilterConfig(exclude_patterns=["test_*.py"])
        filter_obj = ToolFilter(config=config)

        result = filter_obj.filter_files("test-tool", files)

        assert len(result.filtered_files) == 2
        assert tmp_path / "file1.py" in result.filtered_files
        assert tmp_path / "file3.py" in result.filtered_files
        assert tmp_path / "test_file2.py" not in result.filtered_files

    def test_should_run_tool_no_filter(self):
        """Test should_run_tool with no filter."""
        config = FilterConfig()
        filter_obj = ToolFilter(config=config)

        assert filter_obj.should_run_tool("any-tool") is True

    def test_should_run_tool_with_filter_match(self):
        """Test should_run_tool with matching tool."""
        config = FilterConfig(tool_name="ruff-check")
        filter_obj = ToolFilter(config=config)

        assert filter_obj.should_run_tool("ruff-check") is True

    def test_should_run_tool_with_filter_no_match(self):
        """Test should_run_tool with non-matching tool."""
        config = FilterConfig(tool_name="ruff-check")
        filter_obj = ToolFilter(config=config)

        assert filter_obj.should_run_tool("bandit") is False

    def test_get_filtered_files(self, tmp_path: Path):
        """Test get_filtered_files returns filtered list."""
        files = [
            tmp_path / "file1.py",
            tmp_path / "file2.txt",
            tmp_path / "file3.py",
        ]

        config = FilterConfig(file_patterns=["*.py"])
        filter_obj = ToolFilter(config=config)

        filtered = filter_obj.get_filtered_files("test-tool", files)

        assert len(filtered) == 2
        assert all(f.suffix == ".py" for f in filtered)

    def test_estimate_time_savings_no_filter(self):
        """Test estimate_time_savings with no filtering."""
        config = FilterConfig()
        filter_obj = ToolFilter(config=config)

        tool_times = {
            "ruff-check": 2.0,
            "bandit": 3.0,
            "zuban": 5.0,
        }

        savings = filter_obj.estimate_time_savings(tool_times)

        assert savings["total_time_baseline"] == 10.0
        assert savings["total_time_filtered"] == 10.0
        assert savings["time_saved"] == 0.0
        assert savings["percent_saved"] == 0.0

    def test_estimate_time_savings_with_tool_filter(self):
        """Test estimate_time_savings with tool filter."""
        config = FilterConfig(tool_name="ruff-check")
        filter_obj = ToolFilter(config=config)

        tool_times = {
            "ruff-check": 2.0,
            "bandit": 3.0,
            "zuban": 5.0,
        }

        savings = filter_obj.estimate_time_savings(tool_times)

        assert savings["total_time_baseline"] == 10.0
        assert savings["total_time_filtered"] == 2.0
        assert savings["time_saved"] == 8.0
        assert savings["percent_saved"] == 80.0

    def test_generate_filter_summary_tools_only(self):
        """Test generate_filter_summary with tool filtering."""
        config = FilterConfig(tool_name="ruff-check")
        filter_obj = ToolFilter(config=config)

        tool_result = FilterResult(
            total_tools=3,
            filtered_tools=["ruff-check"],
            skipped_tools=["bandit", "zuban"],
            total_files=0,
            filtered_files=[],
            skipped_files=[],
            filter_effectiveness=66.67,
        )

        summary = filter_obj.generate_filter_summary(tool_result=tool_result)

        assert "# Filter Summary" in summary
        assert "## Tool Filtering" in summary
        assert "Total Tools: 3" in summary
        assert "Tools to Run: 1" in summary
        assert "ruff-check" in summary

    def test_generate_filter_summary_files_only(self, tmp_path: Path):
        """Test generate_filter_summary with file filtering."""
        config = FilterConfig()
        filter_obj = ToolFilter(config=config)

        file_result = FilterResult(
            total_tools=1,
            filtered_tools=["test-tool"],
            skipped_tools=[],
            total_files=10,
            filtered_files=[tmp_path / "file1.py"],
            skipped_files=[tmp_path / f"file{i}.py" for i in range(2, 11)],
            filter_effectiveness=90.0,
        )

        summary = filter_obj.generate_filter_summary(file_result=file_result)

        assert "# Filter Summary" in summary
        assert "## File Filtering" in summary
        assert "Total Files: 10" in summary
        assert "Files to Process: 1" in summary


class TestConvenienceFunctions:
    """Test convenience factory functions."""

    def test_create_tool_only_filter(self):
        """Test create_tool_only_filter creates correct filter."""
        filter_obj = create_tool_only_filter("ruff-check")

        assert filter_obj.config.tool_name == "ruff-check"
        assert filter_obj.config.changed_only is False
        assert filter_obj.should_run_tool("ruff-check") is True
        assert filter_obj.should_run_tool("bandit") is False

    def test_create_changed_files_filter(self, tmp_path: Path):
        """Test create_changed_files_filter creates correct filter."""
        executor = IncrementalExecutor(cache_dir=tmp_path / "cache")
        filter_obj = create_changed_files_filter(executor)

        assert filter_obj.config.tool_name is None
        assert filter_obj.config.changed_only is True
        assert filter_obj.executor is executor

    def test_create_combined_filter(self, tmp_path: Path):
        """Test create_combined_filter creates correct filter."""
        executor = IncrementalExecutor(cache_dir=tmp_path / "cache")
        filter_obj = create_combined_filter("ruff-check", executor)

        assert filter_obj.config.tool_name == "ruff-check"
        assert filter_obj.config.changed_only is True
        assert filter_obj.executor is executor


class TestFilterIntegration:
    """Integration tests for realistic filtering scenarios."""

    def test_full_workflow_tool_and_files(self, tmp_path: Path):
        """Test complete workflow: filter tools and files."""
        # Create test files with unique content
        py_files = [tmp_path / f"file{i}.py" for i in range(5)]
        txt_files = [tmp_path / f"file{i}.txt" for i in range(5)]
        for i, f in enumerate(py_files):
            f.write_text(f"py_content_{i}")
        for i, f in enumerate(txt_files):
            f.write_text(f"txt_content_{i}")

        # Setup executor and cache first 3 py files
        executor = IncrementalExecutor(cache_dir=tmp_path / "cache")

        def dummy_func(file: Path) -> str:
            return "ok"

        executor.execute_incremental("ruff-check", py_files[:3], dummy_func)

        # Create combined filter
        filter_obj = create_combined_filter("ruff-check", executor)

        # Filter tools
        available_tools = ["ruff-check", "bandit", "zuban"]
        tool_result = filter_obj.filter_tools(available_tools)

        assert tool_result.filtered_tools == ["ruff-check"]
        assert len(tool_result.skipped_tools) == 2

        # Filter files (only uncached py files)
        # Test with only py files to check changed-only filtering
        file_result = filter_obj.filter_files("ruff-check", py_files)

        # Should only include py_files[3:] (the 2 uncached py files)
        assert len(file_result.filtered_files) == 2
        assert py_files[3] in file_result.filtered_files
        assert py_files[4] in file_result.filtered_files

    def test_time_savings_calculation(self):
        """Test realistic time savings calculation."""
        config = FilterConfig(tool_name="ruff-check")
        filter_obj = ToolFilter(config=config)

        # Realistic tool execution times
        tool_times = {
            "ruff-format": 0.5,
            "ruff-isort": 0.3,
            "ruff-check": 1.2,
            "zuban": 8.5,
            "bandit": 3.2,
            "complexipy": 2.1,
        }

        savings = filter_obj.estimate_time_savings(tool_times)

        # Should save everything except ruff-check (1.2s)
        assert savings["total_time_baseline"] == 15.8
        assert savings["total_time_filtered"] == 1.2
        assert savings["time_saved"] == pytest.approx(14.6, abs=0.01)
        assert savings["percent_saved"] == pytest.approx(92.41, abs=0.01)
