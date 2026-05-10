"""Tests for autofix_coordinator bug fixes - simplified version.

This module tests the critical fixes made to the autofix_coordinator:
1. Issue count extraction fix - complexipy/refurb/creosote skip validation (adapter does filtering)
2. Iteration discrepancy fix - ensures consistent use of hook_results across iterations
"""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from rich.console import Console

from crackerjack.agents.base import Issue, IssueType, Priority
from crackerjack.core.autofix_coordinator import AutofixCoordinator
from crackerjack.models.task import HookResult
from crackerjack.services.ai_fix_progress import AIFixProgressManager
from crackerjack.services.refurb_fixer import SafeRefurbFixer


class TestIterationDiscrepancyFix:
    """Test the iteration discrepancy bug fix."""

    @pytest.fixture
    def coordinator(self):
        """Create an AutofixCoordinator instance for testing."""
        pkg_path = Path("/tmp/test")
        return AutofixCoordinator(console=None, pkg_path=pkg_path)

    def test_iteration_0_processes_hook_results(self, coordinator):
        """Iteration 0 should process hook_results parameter."""
        # Create mock hook results
        mock_hook = Mock()
        hook_results = [mock_hook]

        # Should not crash and should return a list
        issues = coordinator._get_iteration_issues(0, hook_results, "fast")
        assert isinstance(issues, list)

    def test_iteration_1_also_uses_hook_results(self, coordinator):
        """Iteration 1 should also use hook_results (this was the bug)."""
        # Create mock hook results
        mock_hook = Mock()
        hook_results = [mock_hook]

        # This used to rerun tools - now it should use hook_results
        issues = coordinator._get_iteration_issues(1, hook_results, "comprehensive")
        assert isinstance(issues, list)

    def test_iteration_2_maintains_consistency(self, coordinator):
        """Iteration 2+ should maintain consistency with earlier iterations."""
        mock_hook = Mock()
        hook_results = [mock_hook]

        issues = coordinator._get_iteration_issues(2, hook_results, "comprehensive")
        assert isinstance(issues, list)

    def test_iteration_with_empty_results(self, coordinator):
        """Should handle empty hook_results gracefully."""
        issues = coordinator._get_iteration_issues(0, [], "fast")
        assert issues == []

    def test_iteration_parses_multiple_hook_results(self, coordinator):
        """Should parse multiple hook results."""
        # Create multiple mock hooks
        hook_results = [Mock(), Mock(), Mock()]

        issues = coordinator._get_iteration_issues(0, hook_results, "comprehensive")
        assert isinstance(issues, list)


class TestIssueCountExtractionFix:
    """Test the issue count extraction bug fix for filtered tools.

    Background: Some tools output more data than the adapter ultimately returns
    because the adapter applies filtering logic (thresholds, patterns, etc.).
    The _extract_issue_count method should return None for these tools to skip
    validation, since the raw output can't predict the filtered result.

    Tools with filtering:
    - complexipy: outputs ALL functions (6076), adapter filters by threshold (~9)
    - refurb: outputs all lines, adapter filters for "[FURB" prefix
    - creosote: outputs multiple sections, adapter filters for "unused" deps
    """

    @pytest.fixture
    def coordinator(self):
        """Create an AutofixCoordinator instance."""
        pkg_path = Path("/tmp/test")
        return AutofixCoordinator(console=None, pkg_path=pkg_path)

    def test_complexipy_returns_none_to_skip_validation(self, coordinator):
        """complexipy should return None because adapter does filtering."""
        complexipy_output = '{"complexity": 20, "file_name": "test.py", "function_name": "test", "path": "test.py"}'

        result = coordinator._extract_issue_count(complexipy_output, "complexipy")

        assert result is None, (
            "complexipy should return None because the adapter filters "
            "by threshold, making raw output count unpredictable"
        )

    def test_refurb_returns_none_to_skip_validation(self, coordinator):
        """refurb should return None because adapter does filtering."""
        refurb_output = """file1.py:10: Some output
file2.py:20: [FURB] This is a refurb issue
file3.py:30: More output"""

        result = coordinator._extract_issue_count(refurb_output, "refurb")

        assert result is None, (
            "refurb should return None because the adapter filters "
            "for '[FURB' prefix, making raw output count unpredictable"
        )

    def test_creosote_returns_none_to_skip_validation(self, coordinator):
        """creosote should return None because adapter does filtering."""
        creosote_output = """Found dependencies: 10
Unused dependencies: 3
pkg1
pkg2
pkg3"""

        result = coordinator._extract_issue_count(creosote_output, "creosote")

        assert result is None, (
            "creosote should return None because the adapter filters "
            "for 'unused' section, making raw output count unpredictable"
        )

    def test_ruff_still_returns_count(self, coordinator):
        """Tools without filtering should still return counts."""
        ruff_output = '[{"message": "error1"}, {"message": "error2"}]'

        result = coordinator._extract_issue_count(ruff_output, "ruff")

        assert result == 2, "ruff should return the JSON array length"

    def test_fallback_line_counting_still_works(self, coordinator):
        """Fallback line counting should still work for unknown tools."""
        # Text output with colons (looks like issues)
        text_output = """file1.py:10: error message
file2.py:20: another error
file3.py:30: third error"""

        result = coordinator._extract_issue_count(text_output, "unknown-tool")

        assert result == 3, "Should count lines with colons"


class TestBugFixIntegration:
    """Integration tests showing both fixes working together."""

    @pytest.fixture
    def coordinator(self):
        """Create an AutofixCoordinator instance."""
        pkg_path = Path("/tmp/test")
        return AutofixCoordinator(console=None, pkg_path=pkg_path)

    def test_issue_count_stability(self, coordinator):
        """Issue counts should remain stable across iterations."""
        # Create stable mock results
        mock_hook = Mock(to_issues=lambda: [])
        hook_results = [mock_hook]

        # Multiple iterations should return consistent types
        for i in range(5):
            issues = coordinator._get_iteration_issues(i, hook_results, "fast")
            assert isinstance(issues, list), f"Iteration {i} should return list"

    def test_collect_current_issues_filters_to_active_scope(self, coordinator):
        """Scoped verification should ignore issues outside the active file set."""
        keep_path = coordinator.pkg_path / "keep.py"
        drop_path = coordinator.pkg_path / "drop.py"
        keep_issue = Issue(
            type=IssueType.FORMATTING,
            severity=Priority.LOW,
            message="keep",
            file_path=str(keep_path),
            line_number=1,
        )
        drop_issue = Issue(
            type=IssueType.FORMATTING,
            severity=Priority.LOW,
            message="drop",
            file_path=str(drop_path),
            line_number=1,
        )

        coordinator._active_ai_fix_scope_files = {
            str(keep_path.resolve(strict=False)),
        }
        coordinator._build_check_commands = Mock(return_value=[])  # type: ignore[method-assign]
        coordinator._execute_check_commands = Mock(  # type: ignore[method-assign]
            return_value=([keep_issue, drop_issue], 1)
        )

        issues = coordinator._collect_current_issues(stage="fast")

        assert issues == [keep_issue]

    def test_parse_hook_to_issues_skips_count_validation_for_scoped_ruff(
        self, coordinator
    ):
        """Scoped Ruff verification should not use the original issue count."""
        coordinator._active_ai_fix_scope_files = {
            str((coordinator.pkg_path / "keep.py").resolve(strict=False)),
        }
        coordinator._extract_issue_count = Mock(return_value=58)  # type: ignore[method-assign]
        coordinator._parser_factory = Mock()
        coordinator._parser_factory.parse_with_validation = Mock(  # type: ignore[attr-defined]
            return_value=[]
        )

        coordinator._parse_hook_to_issues("ruff", "C901 demo is too complex")

        coordinator._parser_factory.parse_with_validation.assert_called_once_with(
            tool_name="ruff",
            output="C901 demo is too complex",
            expected_count=None,
        )
    def test_update_bar_text_accepts_path_objects(self):
        """The progress manager should accept Path objects without crashing."""
        from crackerjack.services.ai_fix_progress import AIFixProgressManager

        class FakeBar:
            def __init__(self) -> None:
                self.text_value = None

            def text(self, value: str) -> None:
                self.text_value = value

        manager = AIFixProgressManager(enabled=True)
        fake_bar = FakeBar()
        manager._bar = fake_bar

        manager.update_bar_text(Path("nested/example.py"))

        assert fake_bar.text_value == "📄 nested/example.py"

    def test_log_event_accepts_path_objects(self, capsys):
        """The progress manager should stringify Path objects in log output."""
        from crackerjack.services.ai_fix_progress import AIFixProgressManager

        manager = AIFixProgressManager(enabled=True)
        manager.log_event("FixerCoordinator", "Testing", Path("nested/example.py"))

        captured = capsys.readouterr()
        assert "example.py" in captured.out

    def test_error_summary_accepts_mixed_path_types(self, coordinator):
        """Error summaries should normalize mixed Path and string file entries."""
        coordinator._collected_errors = [
            {"type": "Workspace Write Error", "file": Path("nested/example.py")},
            {"type": "Workspace Write Error", "file": "nested/other.py"},
        ]
        coordinator.console = Mock()

        coordinator._display_error_summary()

    @pytest.mark.asyncio
    async def test_execute_single_agent_fix_normalizes_issue_file_paths(
        self, coordinator
    ):
        """Swarm executor should store file paths as strings on Issue objects."""

        class DummyCoordinator:
            def __init__(self) -> None:
                self.seen_issue_paths: list[type] = []

            def analyze_and_fix(self, context: object) -> SimpleNamespace:
                self.seen_issue_paths.append(type(context.issue.file_path))  # type: ignore[attr-defined]
                return SimpleNamespace(
                    success=True,
                    file_path=context.issue.file_path,  # type: ignore[attr-defined]
                    fixes_applied=1,
                    errors=[],
                )

        dummy_coordinator = DummyCoordinator()
        coordinator._setup_ai_fix_coordinator = Mock(  # type: ignore[method-assign]
            return_value=dummy_coordinator
        )

        result = await coordinator._execute_single_agent_fix(
            issue_type="formatting",
            file_paths=["nested/example.py"],
            prompt="fix it",
            context={"line": 3, "original_message": "test"},
        )

        assert result["success"] is True
        assert dummy_coordinator.seen_issue_paths == [str]


class TestAIFixProgressFooter:
    """Test session completion footer formatting and counts."""

    def test_successful_session_reports_zero_remaining_issues(self):
        """Successful sessions should report the final issue count as zero."""
        console = Console(record=True, force_terminal=True, width=80)
        manager = AIFixProgressManager(console=console, enabled=True)
        manager.issue_history = [4, 2]

        manager.finish_session(success=True)

        output = console.export_text()
        assert "Session Completed" in output
        assert "Issues: 4 → 0" in output
        assert "Reduction: 100%" in output
        assert "History:" not in output
        assert output.startswith("\n")

    def test_failed_session_still_uses_last_remaining_issue_count(self):
        """Failed sessions should continue to show the last remaining count."""
        console = Console(record=True, force_terminal=True, width=80)
        manager = AIFixProgressManager(console=console, enabled=True)
        manager.issue_history = [4, 2]

        manager.finish_session(success=False)

        output = console.export_text()
        assert "Convergence Limit" in output
        assert "Issues: 4 → 2" in output
        assert "Reduction: 50%" in output
        assert "History:" not in output


class TestRefurbAutomation:
    @pytest.fixture
    def coordinator(self):
        return AutofixCoordinator(console=None, pkg_path=Path("/tmp/test"))

    def test_safe_refurb_fixer_handles_append_extend_and_else_return(self) -> None:
        fixer = SafeRefurbFixer()
        content = (
            "def demo():\n"
            "    output = []\n"
            "    output.append(first)\n"
            "    output.append(second)\n"
            "\n"
            "    if value:\n"
            "        return value\n"
            "    else:\n"
            "        return fallback\n"
        )

        new_content, fixes = fixer._apply_fixes(content)

        assert fixes >= 2
        assert "output.extend((first, second))" in new_content
        assert "else:" not in new_content
        assert "return fallback" in new_content

    def test_targeted_refurb_repair_applies_safe_fixer(self, coordinator, tmp_path):
        file_path = tmp_path / "demo.py"
        file_path.write_text(
            "def demo():\n"
            "    output = []\n"
            "    output.append(first)\n"
            "    output.append(second)\n"
            "\n"
            "    if value:\n"
            "        return value\n"
            "    else:\n"
            "        return fallback\n",
            encoding="utf-8",
        )

        assert coordinator._run_targeted_refurb_fixes(str(file_path)) is True

        rewritten = file_path.read_text(encoding="utf-8")
        assert "output.extend((first, second))" in rewritten
        assert "else:" not in rewritten

    @pytest.mark.asyncio
    async def test_refurb_prepass_refreshes_issues_before_planning(
        self, coordinator, tmp_path
    ):
        file_path = tmp_path / "demo.py"
        file_path.write_text(
            "def demo():\n"
            "    output = []\n"
            "    output.append(first)\n"
            "    output.append(second)\n",
            encoding="utf-8",
        )

        hook_results = [
            HookResult(
                name="refurb",
                status="failed",
                files_checked=[file_path],
                output="demo.py:3: [FURB113] Replace append with extend",
            )
        ]

        refreshed_issue = Issue(
            type=IssueType.REFURB,
            severity=Priority.LOW,
            message="FURB113: Replace append with extend",
            file_path=str(file_path),
            line_number=3,
            stage="refurb",
        )

        coordinator._create_type_tool_adapter = Mock(return_value=Mock())  # type: ignore[method-assign]
        coordinator._run_refurb_safe_fixes = Mock(return_value=True)  # type: ignore[method-assign]
        coordinator._rerun_type_tool_check = AsyncMock(  # type: ignore[method-assign]
            return_value=[refreshed_issue]
        )

        refreshed = await coordinator._apply_refurb_fix_prepasses(hook_results)

        assert "refurb" in refreshed
        assert refreshed["refurb"] == [refreshed_issue]
        coordinator._run_refurb_safe_fixes.assert_called_once()  # type: ignore[attr-defined]
        coordinator._rerun_type_tool_check.assert_called_once()  # type: ignore[attr-defined]

    @pytest.mark.asyncio
    async def test_ruff_prepass_refreshes_issues_before_planning(
        self, coordinator, tmp_path
    ):
        file_path = tmp_path / "demo.py"
        file_path.write_text(
            "import os\n\n"
            "def demo():\n"
            "    return os.path.join('a', 'b')\n",
            encoding="utf-8",
        )

        hook_results = [
            HookResult(
                name="ruff-check",
                status="failed",
                files_checked=[file_path],
                output="demo.py:1:1: F401 unused import `os`",
            )
        ]

        refreshed_issue = Issue(
            type=IssueType.IMPORT_ERROR,
            severity=Priority.MEDIUM,
            message="F401 unused import `os`",
            file_path=str(file_path),
            line_number=1,
            stage="ruff-check",
        )

        coordinator._create_type_tool_adapter = Mock(return_value=Mock())  # type: ignore[method-assign]
        coordinator._run_ruff_safe_fixes = Mock(return_value=True)  # type: ignore[method-assign]
        coordinator._rerun_type_tool_check = AsyncMock(  # type: ignore[method-assign]
            return_value=[refreshed_issue]
        )

        refreshed = await coordinator._apply_ruff_fix_prepasses(hook_results)

        assert "ruff-check" in refreshed
        assert refreshed["ruff-check"] == [refreshed_issue]
        coordinator._run_ruff_safe_fixes.assert_called_once()  # type: ignore[attr-defined]
        coordinator._rerun_type_tool_check.assert_called_once()  # type: ignore[attr-defined]

    def test_collect_ruff_files_parses_output_when_files_checked_missing(
        self, coordinator, tmp_path
    ):
        file_path = tmp_path / "server.py"
        hook_result = HookResult(
            name="ruff-check",
            status="failed",
            output=(
                f"{file_path}:63:1: F401 unused import `os`\n"
                f"{file_path}:313:5: E501 line too long"
            ),
        )

        files = coordinator._collect_ruff_files([hook_result])

        assert files == [file_path]

    def test_extract_hook_result_files_parses_output_for_other_hooks(
        self, coordinator, tmp_path
    ):
        file_path = tmp_path / "subscriber.py"
        hook_result = HookResult(
            name="ty",
            status="failed",
            output=f"{file_path}:12:1: error: undefined name `value`",
        )

        files = coordinator._extract_hook_result_files(hook_result)

        assert files == [file_path]
