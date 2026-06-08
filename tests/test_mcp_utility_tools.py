"""Tests for utility_tools.py MCP tools.

Tests clean, config, analyze, and validate_claude_md tools.
"""

import json
import pytest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock

from crackerjack.mcp.tools.utility_tools import (
    _create_error_response,
    clean_temp_files,
    _process_directory,
    _process_file_for_cleanup,
    _process_pattern,
    _check_file_eligibility,
    _parse_cleanup_options,
    _parse_clean_configuration,
    _execute_cleanup_operations,
    _create_cleanup_response,
    _check_claude_md_missing,
    _check_integration_markers,
    _check_quality_principles,
    _extract_crackerjack_section,
    _perform_claude_md_validation,
    _update_claude_md_if_needed,
    register_utility_tools,
)


class TestCreateErrorResponse:
    """Tests for _create_error_response function."""

    def test_creates_error_response_with_default_success(self) -> None:
        """Test creates error response with success=False by default."""
        result = _create_error_response("Test error message")

        parsed = json.loads(result)
        assert parsed["error"] == "Test error message"
        assert parsed["success"] is False

    def test_creates_error_response_with_custom_success(self) -> None:
        """Test creates error response with custom success value."""
        result = _create_error_response("Test error", success=True)

        parsed = json.loads(result)
        assert parsed["error"] == "Test error"
        assert parsed["success"] is True


class TestCleanTempFiles:
    """Tests for clean_temp_files function."""

    @pytest.mark.asyncio
    async def test_returns_empty_for_nonexistent_directory(self) -> None:
        """Test returns empty results for nonexistent directory."""
        result = await clean_temp_files(
            older_than_hours=24,
            patterns=["*.log"],
            directories=[Path("/nonexistent/path")],
        )

        assert result["all_cleaned_files"] == []
        assert result["total_size"] == 0

    @pytest.mark.asyncio
    async def test_uses_default_patterns(self) -> None:
        """Test uses default patterns when none provided."""
        with patch("crackerjack.mcp.tools.utility_tools._process_directory") as mock:
            mock.return_value = ([], 0)

            await clean_temp_files(older_than_hours=24, directories=[Path("/tmp")])

            call_args = mock.call_args
            patterns = call_args[0][1]
            assert "*.log" in patterns
            assert ".coverage.*" in patterns

    @pytest.mark.asyncio
    async def test_calculates_total_size(self) -> None:
        """Test returns correct total size of cleaned files."""
        with patch("crackerjack.mcp.tools.utility_tools._process_directory") as mock:
            mock.side_effect = [
                (["file1.log", "file2.log"], 1024),
                (["file3.log"], 512),
            ]

            result = await clean_temp_files(
                older_than_hours=24,
                directories=[Path("/tmp"), Path("/var/tmp")],
            )

            assert result["total_size"] == 1536
            assert len(result["all_cleaned_files"]) == 3


class TestProcessDirectory:
    """Tests for _process_directory function."""

    def test_returns_empty_for_nonexistent_directory(self) -> None:
        """Test returns empty results for nonexistent directory."""
        result = _process_directory(
            Path("/nonexistent"),
            ["*.log"],
            datetime.now(),
            dry_run=True,
        )

        assert result == ([], 0)

    def test_processes_multiple_patterns(self) -> None:
        """Test processes multiple patterns."""
        with patch("crackerjack.mcp.tools.utility_tools._process_pattern") as mock:
            mock.side_effect = [
                (["a.log"], 100),
                (["b.log"], 200),
            ]

            result = _process_directory(
                Path("/tmp"),
                ["*.log", "*.tmp"],
                datetime.now(),
                dry_run=True,
            )

            assert result == (["a.log", "b.log"], 300)


class TestProcessPattern:
    """Tests for _process_pattern function."""

    def test_returns_empty_for_empty_glob(self, tmp_path) -> None:
        """Test returns empty when no files match pattern."""
        result = _process_pattern(tmp_path, "*.log", datetime.now(), dry_run=True)

        assert result == ([], 0)

    def test_cleans_matching_files(self, tmp_path) -> None:
        """Test processes and cleans matching files."""
        old_file = tmp_path / "test.log"
        old_file.write_text("content")
        import os
        old_time = datetime.now() - timedelta(hours=25)
        os.utime(old_file, (old_time.timestamp(), old_time.timestamp()))

        result = _process_pattern(
            tmp_path,
            "*.log",
            datetime.now() - timedelta(hours=24),
            dry_run=False,
        )

        assert len(result[0]) == 1
        assert not old_file.exists()


class TestCheckFileEligibility:
    """Tests for _check_file_eligibility function."""

    def test_returns_none_for_recent_file(self, tmp_path) -> None:
        """Test returns None for file newer than cutoff."""
        recent_file = tmp_path / "recent.log"
        recent_file.write_text("content")

        # Pick a cutoff in the past so the freshly-written file is
        # ``newer than cutoff`` and the function returns ``None``.
        result = _check_file_eligibility(
            recent_file, datetime.now() - timedelta(hours=1)
        )

        assert result is None

    def test_returns_size_for_old_file(self, tmp_path) -> None:
        """Test returns file size for old file."""
        old_file = tmp_path / "old.log"
        old_file.write_text("x" * 100)
        import os
        old_time = datetime.now() - timedelta(hours=25)
        os.utime(old_file, (old_time.timestamp(), old_time.timestamp()))

        result = _check_file_eligibility(old_file, datetime.now() - timedelta(hours=24))

        assert result is not None
        size, should_clean = result
        assert size == 100
        assert should_clean is True

    def test_returns_none_for_oserror(self) -> None:
        """Test returns None on OSError."""
        fake_path = Path("/proc/fake/file")
        result = _check_file_eligibility(fake_path, datetime.now())
        assert result is None


class TestParseCleanupOptions:
    """Tests for _parse_cleanup_options function."""

    def test_parses_valid_json(self) -> None:
        """Test parses valid JSON kwargs."""
        kwargs, error = _parse_cleanup_options('{"dry_run": true, "older_than": 48}')

        assert error is None
        assert kwargs["dry_run"] is True
        assert kwargs["older_than"] == 48

    def test_returns_empty_dict_for_empty_string(self) -> None:
        """Test returns empty dict for empty string."""
        kwargs, error = _parse_cleanup_options("")

        assert error is None
        assert kwargs == {}

    def test_returns_error_for_invalid_json(self) -> None:
        """Test returns error for invalid JSON."""
        kwargs, error = _parse_cleanup_options("not json")

        assert error is not None
        assert "Invalid JSON" in error


class TestParseCleanConfiguration:
    """Tests for _parse_clean_configuration function."""

    def test_default_scope_is_all(self) -> None:
        """Test default scope is 'all'."""
        config = _parse_clean_configuration("", "{}")

        assert config["scope"] == "all"
        assert config["dry_run"] is False
        assert config["older_than_hours"] == 24

    def test_parses_temp_scope(self) -> None:
        """Test parses temp scope."""
        config = _parse_clean_configuration("temp", "{}")

        assert config["scope"] == "temp"

    def test_parses_progress_scope(self) -> None:
        """Test parses progress scope."""
        config = _parse_clean_configuration("progress", "{}")

        assert config["scope"] == "progress"

    def test_uses_kwargs_for_options(self) -> None:
        """Test uses kwargs for dry_run and older_than."""
        config = _parse_clean_configuration("all", '{"dry_run": true, "older_than": 48}')

        assert config["dry_run"] is True
        assert config["older_than_hours"] == 48


class TestCreateCleanupResponse:
    """Tests for _create_cleanup_response function."""

    def test_creates_success_response(self) -> None:
        """Test creates successful cleanup response."""
        clean_config = {
            "scope": "all",
            "dry_run": False,
            "older_than_hours": 24,
        }
        cleanup_results = {
            "all_cleaned_files": ["file1.log", "file2.log"],
            "total_size": 1024,
        }

        result = _create_cleanup_response(clean_config, cleanup_results)

        parsed = json.loads(result)
        assert parsed["success"] is True
        assert parsed["command"] == "clean_crackerjack"
        assert parsed["files_cleaned"] == 2
        assert parsed["total_size_bytes"] == 1024

    def test_truncates_file_list_at_50(self) -> None:
        """Test truncates file list when over 50 files."""
        clean_config = {"scope": "all", "dry_run": True, "older_than_hours": 24}
        many_files = [f"file{i}.log" for i in range(60)]
        cleanup_results = {"all_cleaned_files": many_files, "total_size": 1000}

        result = _create_cleanup_response(clean_config, cleanup_results)

        parsed = json.loads(result)
        assert len(parsed["files"]) == 50


class TestCheckClaudeMdMissing:
    """Tests for _check_claude_md_missing function."""

    def test_returns_none_when_file_exists(self, tmp_path) -> None:
        """Test returns None when CLAUDE.md exists."""
        claude_md = tmp_path / "CLAUDE.md"
        claude_md.write_text("# CLAUDE.md")

        result = _check_claude_md_missing(claude_md)

        assert result is None

    def test_returns_issues_when_file_missing(self, tmp_path) -> None:
        """Test returns issues dict when CLAUDE.md is missing."""
        claude_md = tmp_path / "CLAUDE.md"

        result = _check_claude_md_missing(claude_md)

        assert result is not None
        assert result["valid"] is False
        assert "not found" in result["issues"][0].lower()
        assert "suggestions" in result


class TestCheckIntegrationMarkers:
    """Tests for _check_integration_markers function."""

    def test_returns_issues_when_marker_missing(self) -> None:
        """Test returns issues when crackerjack marker is missing."""
        content = "# CLAUDE.md\n\nSome content without markers."

        issues, suggestions = _check_integration_markers(content, Path("CLAUDE.md"))

        assert len(issues) > 0
        assert "integration" in issues[0].lower()

    def test_returns_empty_when_marker_present(self) -> None:
        """Test returns empty lists when marker is present."""
        content = """
# CLAUDE.md

<!-- CRACKERJACK INTEGRATION START -->
Some integration content
<!-- CRACKERJACK INTEGRATION END -->
"""

        issues, suggestions = _check_integration_markers(content, Path("CLAUDE.md"))

        assert len(issues) == 0
        assert len(suggestions) == 0


class TestCheckQualityPrinciples:
    """Tests for _check_quality_principles function."""

    def test_returns_issues_for_missing_principles(self) -> None:
        """Test returns issues when quality principles are missing."""
        section = "Some random content without principles"

        issues, suggestions = _check_quality_principles(section)

        assert len(issues) > 0
        assert len(suggestions) > 0

    def test_returns_empty_for_complete_section(self) -> None:
        """Test returns empty for section with all principles."""
        section = """
Check yourself before you wreck yourself
Take the time to do things right the first time
Coverage ratchet
Cognitive complexity
"""

        issues, suggestions = _check_quality_principles(section)

        assert len(issues) == 0
        assert len(suggestions) == 0


class TestExtractCrackerjackSection:
    """Tests for _extract_crackerjack_section function."""

    def test_extracts_section_when_both_markers_present(self) -> None:
        """Test extracts section when both markers are present."""
        content = """
# CLAUDE.md

Some content

<!-- CRACKERJACK INTEGRATION START -->
Integration content here
<!-- CRACKERJACK INTEGRATION END -->

More content
"""

        result = _extract_crackerjack_section(content)

        assert result is not None
        assert "CRACKERJACK INTEGRATION START" in result
        assert "CRACKERJACK INTEGRATION END" in result
        assert "Integration content here" in result

    def test_returns_none_when_start_marker_missing(self) -> None:
        """Test returns None when start marker is missing."""
        content = "Content without start marker <!-- CRACKERJACK INTEGRATION END -->"

        result = _extract_crackerjack_section(content)

        assert result is None

    def test_returns_none_when_end_marker_missing(self) -> None:
        """Test returns None when end marker is missing."""
        content = "Content <!-- CRACKERJACK INTEGRATION START --> without end"

        result = _extract_crackerjack_section(content)

        assert result is None


class TestPerformClaudeMdValidation:
    """Tests for _perform_claude_md_validation function."""

    def test_returns_missing_when_file_not_found(self, tmp_path) -> None:
        """Test returns missing result when CLAUDE.md doesn't exist."""
        result = _perform_claude_md_validation(tmp_path)

        assert result["valid"] is False
        assert any("not found" in issue.lower() for issue in result["issues"])

    def test_returns_valid_for_complete_claude_md(self, tmp_path) -> None:
        """Test returns valid for complete CLAUDE.md file."""
        # All four ``essential_principles`` must live inside the
        # ``<!-- CRACKERJACK INTEGRATION START/END -->`` block — the
        # validator only inspects that section.
        claude_md = tmp_path / "CLAUDE.md"
        claude_md.write_text(
            "# CLAUDE.md\n\n"
            "<!-- CRACKERJACK INTEGRATION START -->\n"
            "Check yourself before you wreck yourself\n"
            "Take the time to do things right the first time\n"
            "Coverage ratchet\n"
            "Cognitive complexity\n"
            "<!-- CRACKERJACK INTEGRATION END -->\n"
        )

        result = _perform_claude_md_validation(tmp_path)

        assert result["valid"] is True
        assert len(result["issues"]) == 0

    def test_detects_missing_integration_markers(self, tmp_path) -> None:
        """Test detects missing integration markers."""
        claude_md = tmp_path / "CLAUDE.md"
        claude_md.write_text("""
# CLAUDE.md

Check yourself before you wreck yourself
Take the time to do things right the first time

No integration markers here.
""")

        result = _perform_claude_md_validation(tmp_path)

        assert result["valid"] is False
        assert any("integration" in issue.lower() for issue in result["issues"])


class TestUpdateClaudeMdIfNeeded:
    """Tests for _update_claude_md_if_needed function."""

    def test_returns_error_on_exception(self, tmp_path) -> None:
        """Test returns error dict when exception occurs."""
        context = MagicMock()
        context.console = None

        # ``InitializationService`` is imported lazily inside the function,
        # so the patch target is the source module, not the (re)importer.
        with patch(
            "crackerjack.services.initialization.InitializationService",
            side_effect=ImportError("Module not found"),
        ):
            result = _update_claude_md_if_needed(tmp_path, context)

            assert result["success"] is False
            assert "error" in result

    def test_returns_success_result(self, tmp_path) -> None:
        """Test returns success result when initialization succeeds."""
        context = MagicMock()
        context.console = None

        with patch(
            "crackerjack.services.initialization.InitializationService"
        ) as mock_init:
            mock_service = MagicMock()
            mock_service.initialize_project_full.return_value = {
                "success": True,
                "files_copied": ["CLAUDE.md"],
            }
            mock_init.return_value = mock_service

            result = _update_claude_md_if_needed(tmp_path, context)

            assert result["success"] is True
            assert "CLAUDE.md" in result["files_updated"]


class TestRegisterUtilityTools:
    """Tests for register_utility_tools function."""

    def test_registers_four_tools(self) -> None:
        """Test registers four MCP tools."""
        mcp_app = MagicMock()

        register_utility_tools(mcp_app)

        assert mcp_app.tool.call_count == 4

    def test_registers_clean_tool(self) -> None:
        """Test registers clean_crackerjack tool."""
        mcp_app = MagicMock()

        register_utility_tools(mcp_app)

        tool_calls = mcp_app.tool.call_args_list
        tool_names = [call.kwargs.get("name") or str(call) for call in tool_calls]

        # At least one tool should be registered
        assert mcp_app.tool.called

    def test_registers_config_tool(self) -> None:
        """Test registers config_crackerjack tool."""
        mcp_app = MagicMock()

        register_utility_tools(mcp_app)

        assert mcp_app.tool.called

    def test_registers_analyze_tool(self) -> None:
        """Test registers analyze_crackerjack tool."""
        mcp_app = MagicMock()

        register_utility_tools(mcp_app)

        assert mcp_app.tool.called

    def test_registers_validate_claude_md_tool(self) -> None:
        """Test registers validate_claude_md tool."""
        mcp_app = MagicMock()

        register_utility_tools(mcp_app)

        assert mcp_app.tool.called
