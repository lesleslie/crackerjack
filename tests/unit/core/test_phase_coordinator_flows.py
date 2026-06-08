"""Edge case tests for PhaseCoordinator - targeting uncovered hook execution,
AI-fix flows, JSON parsing, rendering, publishing, and version bump paths."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from crackerjack.core.phase_coordinator import PhaseCoordinator
from crackerjack.models.task import HookResult


@pytest.fixture
def coordinator() -> PhaseCoordinator:
    """Create a PhaseCoordinator instance for testing."""
    return PhaseCoordinator()


@pytest.fixture
def mock_options() -> MagicMock:
    """Create mock options for testing."""
    options = MagicMock()
    options.clean = False
    options.skip_hooks = False
    options.test = False
    options.run_tests = False
    options.no_config_updates = True
    options.configs_dry_run = False
    options.cleanup_docs = False
    options.docs_dry_run = False
    options.ai_fix = False
    options.verbose = False
    options.interactive = False
    options.commit = False
    options.no_git_tags = False
    options.publish = None
    options.all = None
    options.bump = None
    return options


# ---------------------------------------------------------------------------
# Hook execution paths
# ---------------------------------------------------------------------------


class TestExecuteHooksOnce:
    """Test the full hook execution flow with progress + result processing."""

    def test_execute_hooks_once_success(self, coordinator: PhaseCoordinator) -> None:
        """All hooks pass -> result is True and summary stored."""
        hook_results = [
            HookResult(
                id="h1",
                name="format",
                status="passed",
                duration=0.1,
                files_checked=[],
                issues_found=None,
                issues_count=0,
            ),
            HookResult(
                id="h2",
                name="imports",
                status="passed",
                duration=0.05,
                files_checked=[],
                issues_found=None,
                issues_count=0,
            ),
        ]
        summary = {"total": 2, "passed": 2, "failed": 0, "errors": 0, "total_duration": 0.15}

        coordinator.hook_manager.get_hook_count = MagicMock(return_value=2)
        coordinator.hook_manager.get_hook_summary = MagicMock(return_value=summary)
        coordinator.hook_manager._progress_callback = None
        coordinator.hook_manager._progress_start_callback = None
        progress_mock = MagicMock()
        progress_mock.__enter__ = MagicMock(return_value=progress_mock)
        progress_mock.__exit__ = MagicMock(return_value=False)
        progress_mock.add_task = MagicMock(return_value="task-1")

        with patch.object(
            coordinator, "_create_progress_bar", return_value=progress_mock
        ):
            result = coordinator._execute_hooks_once(
                "fast",
                MagicMock(return_value=hook_results),
                MagicMock(),
                attempt=1,
            )

        assert result is True
        assert coordinator._last_hook_summary == summary
        assert coordinator._last_hook_results == hook_results

    def test_execute_hooks_once_failure(self, coordinator: PhaseCoordinator) -> None:
        """Hook failure path -> returns False and stores summary."""
        hook_results = [
            HookResult(
                id="h1",
                name="ruff",
                status="failed",
                duration=0.2,
                issues_count=3,
                issues_found=["unused import"],
            ),
        ]
        summary = {"total": 1, "passed": 0, "failed": 1, "errors": 0, "total_duration": 0.2}

        coordinator.hook_manager.get_hook_count = MagicMock(return_value=1)
        coordinator.hook_manager.get_hook_summary = MagicMock(return_value=summary)
        progress_mock = MagicMock()
        progress_mock.__enter__ = MagicMock(return_value=progress_mock)
        progress_mock.__exit__ = MagicMock(return_value=False)
        progress_mock.add_task = MagicMock(return_value="task-1")

        with patch.object(
            coordinator, "_create_progress_bar", return_value=progress_mock
        ):
            result = coordinator._execute_hooks_once(
                "fast",
                MagicMock(return_value=hook_results),
                MagicMock(),
                attempt=2,
            )

        assert result is False
        assert coordinator._last_hook_results == hook_results


class TestRunHooksWithProgress:
    """Test progress callback wiring + exception handling."""

    def test_run_hooks_with_progress_success(
        self, coordinator: PhaseCoordinator
    ) -> None:
        """Returns elapsed time and stores results."""
        from rich.progress import Progress

        hook_results = [
            HookResult(id="h1", name="format", status="passed", duration=0.1),
        ]
        progress = MagicMock(spec=Progress)
        progress.__enter__ = MagicMock(return_value=progress)
        progress.__exit__ = MagicMock(return_value=False)
        progress.add_task = MagicMock(return_value="task-1")
        callbacks = {
            "task_id_holder": {"task_id": None},
            "original": None,
            "original_started": None,
        }

        elapsed = coordinator._run_hooks_with_progress(
            suite_name="fast",
            hook_runner=MagicMock(return_value=hook_results),
            progress=progress,
            hook_count=1,
            attempt=1,
            callbacks=callbacks,
        )

        assert isinstance(elapsed, float)
        assert elapsed >= 0
        assert coordinator._last_hook_results == hook_results

    def test_run_hooks_with_progress_exception(
        self, coordinator: PhaseCoordinator
    ) -> None:
        """Hook runner raises -> returns None and logs."""
        progress = MagicMock()
        progress.__enter__ = MagicMock(return_value=progress)
        progress.__exit__ = MagicMock(return_value=False)
        progress.add_task = MagicMock(return_value="task-1")
        callbacks = {
            "task_id_holder": {"task_id": None},
            "original": None,
            "original_started": None,
        }

        with patch.object(
            coordinator,
            "_handle_hook_execution_error",
        ) as mock_handle:
            elapsed = coordinator._run_hooks_with_progress(
                suite_name="fast",
                hook_runner=MagicMock(side_effect=RuntimeError("boom")),
                progress=progress,
                hook_count=1,
                attempt=1,
                callbacks=callbacks,
            )

        assert elapsed is None
        mock_handle.assert_called_once()
        # Confirm error log message was prepared
        args, _ = mock_handle.call_args
        assert args[0] == "fast"
        assert isinstance(args[1], RuntimeError)
        assert args[2] == 1

    def test_handle_hook_execution_error(
        self, coordinator: PhaseCoordinator
    ) -> None:
        """Should print formatted error message."""
        coordinator.console.print = MagicMock()
        coordinator.logger = MagicMock()

        coordinator._handle_hook_execution_error(
            "fast",
            RuntimeError("kaboom"),
            attempt=2,
        )

        coordinator.console.print.assert_called_once()
        coordinator.logger.error.assert_called_once()
        # Verify logger receives structured extra
        call = coordinator.logger.error.call_args
        assert call.kwargs.get("extra", {}).get("suite") == "fast"
        assert call.kwargs.get("extra", {}).get("attempt") == 2

    def test_restore_progress_callbacks(self, coordinator: PhaseCoordinator) -> None:
        """Original callbacks are restored after run."""
        original_cb = MagicMock(name="original_progress")
        original_start = MagicMock(name="original_progress_start")
        coordinator.hook_manager._progress_callback = MagicMock()
        coordinator.hook_manager._progress_start_callback = MagicMock()

        coordinator._restore_progress_callbacks(
            {
                "original": original_cb,
                "original_started": original_start,
            }
        )

        assert coordinator.hook_manager._progress_callback is original_cb
        assert coordinator.hook_manager._progress_start_callback is original_start


class TestProcessHookResults:
    """Test the hook result processing pipeline."""

    def test_process_hook_results_all_pass(
        self, coordinator: PhaseCoordinator
    ) -> None:
        """All hooks passed -> True."""
        results = [
            HookResult(id="h1", name="format", status="passed", duration=0.1),
        ]
        coordinator._last_hook_results = results
        summary = {
            "total": 1,
            "passed": 1,
            "failed": 0,
            "errors": 0,
            "total_duration": 0.1,
        }
        coordinator.hook_manager.get_hook_summary = MagicMock(return_value=summary)

        with patch.object(coordinator, "_report_hook_results"):
            ok = coordinator._process_hook_results("fast", 0.1, 1)

        assert ok is True
        assert coordinator._last_hook_summary == summary

    def test_process_hook_results_with_failures(
        self, coordinator: PhaseCoordinator
    ) -> None:
        """Failures present -> False."""
        results = [
            HookResult(
                id="h1",
                name="ruff",
                status="failed",
                duration=0.2,
                issues_count=2,
            ),
        ]
        coordinator._last_hook_results = results
        summary = {
            "total": 1,
            "passed": 0,
            "failed": 1,
            "errors": 0,
            "total_duration": 0.2,
        }
        coordinator.hook_manager.get_hook_summary = MagicMock(return_value=summary)

        with patch.object(coordinator, "_report_hook_results"):
            ok = coordinator._process_hook_results("fast", 0.2, 1)

        assert ok is False


class TestReportHookResults:
    """Test the result reporting branches."""

    def test_report_no_hooks_configured(self, coordinator: PhaseCoordinator) -> None:
        """Empty total -> warning printed, no table."""
        coordinator.console.print = MagicMock()
        coordinator._report_hook_results(
            "fast",
            [],
            {"total": 0, "passed": 0, "failed": 0, "errors": 0, "total_duration": 0.0},
            attempt=1,
        )
        # Should print the warning, not the table
        printed = " | ".join(
            str(call.args[0]) for call in coordinator.console.print.call_args_list
        )
        assert "No fast hooks are configured" in printed

    def test_report_pass_only(self, coordinator: PhaseCoordinator) -> None:
        """All passed -> green message printed."""
        results = [
            HookResult(id="h1", name="format", status="passed", duration=0.1),
        ]
        coordinator.console.print = MagicMock()
        with patch.object(coordinator, "_render_hook_results_table"):
            coordinator._report_hook_results(
                "fast",
                results,
                {
                    "total": 1,
                    "passed": 1,
                    "failed": 0,
                    "errors": 0,
                    "total_duration": 0.1,
                },
                attempt=1,
            )
        printed = " | ".join(
            str(call.args[0]) for call in coordinator.console.print.call_args_list
        )
        assert "passed" in printed
        assert "1/1 passed" in printed

    def test_report_with_failures(self, coordinator: PhaseCoordinator) -> None:
        """Failures -> red message printed."""
        results = [
            HookResult(
                id="h1",
                name="ruff",
                status="failed",
                duration=0.2,
                issues_count=2,
            ),
        ]
        coordinator.console.print = MagicMock()
        with patch.object(coordinator, "_render_hook_results_table"):
            coordinator._report_hook_results(
                "fast",
                results,
                {
                    "total": 1,
                    "passed": 0,
                    "failed": 1,
                    "errors": 0,
                    "total_duration": 0.2,
                },
                attempt=2,
            )
        printed = " | ".join(
            str(call.args[0]) for call in coordinator.console.print.call_args_list
        )
        assert "0/1 passed" in printed
        assert "attempt 2" in printed
        # Should print the red error message
        assert "[red]" in printed


# ---------------------------------------------------------------------------
# Hook result rendering
# ---------------------------------------------------------------------------


class TestRenderHookResults:
    """Test plain vs rich rendering branch selection."""

    def test_render_empty_results(self, coordinator: PhaseCoordinator) -> None:
        """No results -> no rendering."""
        with patch.object(
            coordinator, "_render_plain_hook_results"
        ) as mock_plain, patch.object(
            coordinator, "_render_rich_hook_results"
        ) as mock_rich:
            coordinator._render_hook_results_table("fast", [])
        mock_plain.assert_not_called()
        mock_rich.assert_not_called()

    def test_render_plain_mode(self, coordinator: PhaseCoordinator) -> None:
        """Plain mode -> calls _render_plain_hook_results."""
        result = HookResult(id="h1", name="ruff", status="failed", duration=0.1)
        with patch.object(
            coordinator, "_is_plain_output", return_value=True
        ), patch.object(
            coordinator, "_render_plain_hook_results"
        ) as mock_plain, patch.object(
            coordinator, "_render_rich_hook_results"
        ) as mock_rich:
            coordinator._render_hook_results_table("fast", [result])
        mock_plain.assert_called_once_with("fast", [result])
        mock_rich.assert_not_called()

    def test_render_rich_mode(self, coordinator: PhaseCoordinator) -> None:
        """Non-plain mode -> calls _render_rich_hook_results."""
        result = HookResult(id="h1", name="ruff", status="failed", duration=0.1)
        with patch.object(
            coordinator, "_is_plain_output", return_value=False
        ), patch.object(
            coordinator, "_render_plain_hook_results"
        ) as mock_plain, patch.object(
            coordinator, "_render_rich_hook_results"
        ) as mock_rich:
            coordinator._render_hook_results_table("fast", [result])
        mock_rich.assert_called_once_with("fast", [result])
        mock_plain.assert_not_called()


class TestCalculateHookStatistics:
    """Test the statistics calculator."""

    def test_calculate_mixed_status(self, coordinator: PhaseCoordinator) -> None:
        """Mixed passed/failed/other/cfg-error produces correct buckets."""
        results = [
            HookResult(
                id="h1",
                name="format",
                status="passed",
                duration=0.1,
                issues_count=0,
            ),
            HookResult(
                id="h2",
                name="ruff",
                status="failed",
                duration=0.2,
                issues_count=3,
                issues_found=["a", "b", "c"],
            ),
            HookResult(
                id="h3",
                name="security",
                status="timeout",
                duration=5.0,
                issues_count=0,
            ),
            HookResult(
                id="h4",
                name="mypy",
                status="config_error",
                duration=0.0,
                issues_count=0,
                is_config_error=True,
            ),
            HookResult(
                id="h5",
                name="skipped",
                status="skipped",
                duration=0.0,
                issues_count=0,
            ),
        ]
        stats = coordinator._calculate_hook_statistics(results)
        assert stats["total_hooks"] == 5
        assert stats["total_passed"] == 1
        assert len(stats["failed_hooks"]) == 2  # failed + timeout
        assert len(stats["other_hooks"]) == 1
        assert stats["total_issues_found"] == 3
        assert stats["config_errors"] == 1


class TestRenderPlainHookResults:
    """Plain-output rendering paths."""

    def test_plain_with_no_failures(self, coordinator: PhaseCoordinator) -> None:
        """No failures -> print summary at the end."""
        results = [
            HookResult(
                id="h1",
                name="format",
                status="passed",
                duration=0.1,
                issues_count=0,
            ),
        ]
        coordinator.console.print = MagicMock()
        coordinator._render_plain_hook_results("fast", results)
        printed = " | ".join(
            str(call.args[0]) for call in coordinator.console.print.call_args_list
        )
        assert "Summary" in printed
        assert "1/1" in printed

    def test_plain_with_failures(self, coordinator: PhaseCoordinator) -> None:
        """Failures present -> no summary line."""
        results = [
            HookResult(
                id="h1",
                name="ruff",
                status="failed",
                duration=0.2,
                issues_count=2,
                issues_found=["a", "b"],
            ),
        ]
        coordinator.console.print = MagicMock()
        coordinator._render_plain_hook_results("fast", results)
        printed = " | ".join(
            str(call.args[0]) for call in coordinator.console.print.call_args_list
        )
        assert "RUFF" in printed
        # Failed hook branch: not the "Summary" path
        assert "Summary" not in printed

    def test_print_plain_hook_result_passed(
        self, coordinator: PhaseCoordinator
    ) -> None:
        """Passed hook shows 0 issues."""
        result = HookResult(
            id="h1",
            name="format",
            status="passed",
            duration=0.1,
        )
        coordinator.console.print = MagicMock()
        coordinator._print_plain_hook_result(result)
        printed = str(coordinator.console.print.call_args.args[0])
        assert "issues=0" in printed
        assert "PASSED" in printed

    def test_print_plain_hook_result_config_error(
        self, coordinator: PhaseCoordinator
    ) -> None:
        """Config error renders the ! marker."""
        result = HookResult(
            id="h1",
            name="mypy",
            status="failed",
            duration=0.0,
            is_config_error=True,
            issues_count=0,
        )
        coordinator.console.print = MagicMock()
        coordinator._print_plain_hook_result(result)
        printed = str(coordinator.console.print.call_args.args[0])
        assert "[yellow]![/yellow]" in printed

    def test_print_plain_summary_with_config_errors(
        self, coordinator: PhaseCoordinator
    ) -> None:
        """Summary includes the (N config) annotation when present."""
        coordinator.console.print = MagicMock()
        coordinator._print_plain_summary(
            {
                "total_issues_found": 5,
                "config_errors": 2,
                "total_passed": 3,
                "total_hooks": 4,
            }
        )
        printed = str(coordinator.console.print.call_args.args[0])
        assert "5 issues" in printed
        assert "2 config" in printed


class TestRenderRichHookResults:
    """Rich rendering paths."""

    def test_render_rich_with_config_errors(
        self, coordinator: PhaseCoordinator
    ) -> None:
        """When any result is a config error, the ! legend line is printed."""
        results = [
            HookResult(
                id="h1",
                name="mypy",
                status="failed",
                duration=0.1,
                is_config_error=True,
                issues_count=0,
            ),
        ]
        coordinator.console.print = MagicMock()
        with patch.object(coordinator, "_build_results_panel"):
            coordinator._render_rich_hook_results("fast", results)
        printed = " | ".join(
            str(call.args[0]) for call in coordinator.console.print.call_args_list
        )
        assert "Configuration or tool error" in printed

    def test_build_results_table_with_issues(
        self, coordinator: PhaseCoordinator
    ) -> None:
        """Build table with both passed + failed rows."""
        results = [
            HookResult(
                id="h1",
                name="format",
                status="passed",
                duration=0.1,
            ),
            HookResult(
                id="h2",
                name="ruff",
                status="failed",
                duration=0.2,
                issues_count=4,
            ),
            HookResult(
                id="h3",
                name="mypy",
                status="failed",
                duration=0.0,
                is_config_error=True,
                issues_count=0,
            ),
        ]
        table = coordinator._build_results_table(results)
        # Table should have one row per result
        assert table.row_count == 3

    def test_build_summary_text_with_other_and_config(
        self, coordinator: PhaseCoordinator
    ) -> None:
        """Summary text includes Other and config annotation when present."""
        text = PhaseCoordinator._build_summary_text(
            {
                "total_hooks": 5,
                "total_passed": 3,
                "total_failed": 1,
                "total_other": 1,
                "total_issues_found": 4,
                "config_errors": 1,
            }
        )
        assert "Total: 5" in text
        assert "Passed: 3" in text
        assert "Other: 1" in text
        assert "4" in text
        assert "1 config" in text


# ---------------------------------------------------------------------------
# JSON issue-count update logic
# ---------------------------------------------------------------------------


class TestUpdateJsonHookIssueCounts:
    """Test JSON-based issue count extraction."""

    def test_no_results_noop(self, coordinator: PhaseCoordinator) -> None:
        """Empty results list is a no-op."""
        coordinator._last_hook_results = []
        coordinator._update_json_hook_issue_counts()  # must not raise

    def test_skips_non_failed(self, coordinator: PhaseCoordinator) -> None:
        """Passed hooks are skipped (issues_count != 0 filter)."""
        result = HookResult(
            id="h1",
            name="json-check",
            status="passed",
            duration=0.1,
            issues_count=0,
            output='{"errors": 5}',
        )
        coordinator._last_hook_results = [result]
        coordinator._update_json_hook_issue_counts()
        # Count must remain 0 (status check fails)
        assert result.issues_count == 0

    def test_skips_non_json_output(self, coordinator: PhaseCoordinator) -> None:
        """Output that doesn't start with { or [ is skipped."""
        result = HookResult(
            id="h1",
            name="json-check",
            status="failed",
            duration=0.1,
            issues_count=0,
            output="Some plain error text",
        )
        coordinator._last_hook_results = [result]
        coordinator._update_json_hook_issue_counts()
        assert result.issues_count == 0

    def test_updates_count_from_dict_errors(
        self, coordinator: PhaseCoordinator
    ) -> None:
        """JSON object with 'errors' key updates the count."""
        result = HookResult(
            id="h1",
            name="json-check",
            status="failed",
            duration=0.1,
            issues_count=0,
            output=json.dumps({"errors": 7}),
        )
        coordinator._last_hook_results = [result]
        coordinator._update_json_hook_issue_counts()
        assert result.issues_count == 7

    def test_updates_count_from_list(self, coordinator: PhaseCoordinator) -> None:
        """JSON array of items: count == len(items)."""
        result = HookResult(
            id="h1",
            name="json-check",
            status="failed",
            duration=0.1,
            issues_count=0,
            output=json.dumps([{"a": 1}, {"b": 2}, {"c": 3}]),
        )
        coordinator._last_hook_results = [result]
        coordinator._update_json_hook_issue_counts()
        assert result.issues_count == 3

    def test_updates_count_from_dict_results(self, coordinator: PhaseCoordinator) -> None:
        """JSON object with 'results' (list) updates the count."""
        result = HookResult(
            id="h1",
            name="json-check",
            status="failed",
            duration=0.1,
            issues_count=0,
            output=json.dumps({"results": [{"x": 1}, {"y": 2}]}),
        )
        coordinator._last_hook_results = [result]
        coordinator._update_json_hook_issue_counts()
        assert result.issues_count == 2

    def test_updates_count_from_dict_issues(self, coordinator: PhaseCoordinator) -> None:
        """JSON object with 'issues' (list) updates the count."""
        result = HookResult(
            id="h1",
            name="json-check",
            status="failed",
            duration=0.1,
            issues_count=0,
            output=json.dumps({"issues": ["a", "b", "c", "d"]}),
        )
        coordinator._last_hook_results = [result]
        coordinator._update_json_hook_issue_counts()
        assert result.issues_count == 4

    def test_no_relevant_keys_noop(self, coordinator: PhaseCoordinator) -> None:
        """JSON object without 'errors'/'results'/'issues' keys is a no-op."""
        result = HookResult(
            id="h1",
            name="json-check",
            status="failed",
            duration=0.1,
            issues_count=0,
            output=json.dumps({"something": "else"}),
        )
        coordinator._last_hook_results = [result]
        coordinator._update_json_hook_issue_counts()
        assert result.issues_count == 0

    def test_invalid_json_ignored(self, coordinator: PhaseCoordinator) -> None:
        """Invalid JSON output does not raise and leaves count unchanged."""
        result = HookResult(
            id="h1",
            name="json-check",
            status="failed",
            duration=0.1,
            issues_count=0,
            output='{"unclosed": ',
        )
        coordinator._last_hook_results = [result]
        coordinator._update_json_hook_issue_counts()
        assert result.issues_count == 0


# ---------------------------------------------------------------------------
# Ruff diagnostic extraction
# ---------------------------------------------------------------------------


class TestTryParseJsonPayload:
    """Test the JSON payload extractor that scans for arrays/objects."""

    def test_empty_text_returns_none(self, coordinator: PhaseCoordinator) -> None:
        assert coordinator._try_parse_json_payload("") is None

    def test_whitespace_only_returns_none(
        self, coordinator: PhaseCoordinator
    ) -> None:
        assert coordinator._try_parse_json_payload("   \n\t  ") is None

    def test_pure_json_array(self, coordinator: PhaseCoordinator) -> None:
        data = coordinator._try_parse_json_payload('[{"a": 1}, {"b": 2}]')
        assert isinstance(data, list)
        assert len(data) == 2

    def test_pure_json_object(self, coordinator: PhaseCoordinator) -> None:
        data = coordinator._try_parse_json_payload('{"errors": 4}')
        assert isinstance(data, dict)
        assert data["errors"] == 4

    def test_embedded_json_array(self, coordinator: PhaseCoordinator) -> None:
        """Array buried in noise is extracted."""
        payload = 'noise before [{"x": 1}, {"y": 2}] noise after'
        data = coordinator._try_parse_json_payload(payload)
        assert isinstance(data, list)
        assert len(data) == 2

    def test_embedded_json_object(self, coordinator: PhaseCoordinator) -> None:
        """Object buried in noise is extracted."""
        payload = 'noise before {"x": 1} noise after'
        data = coordinator._try_parse_json_payload(payload)
        assert isinstance(data, dict)
        assert data["x"] == 1

    def test_invalid_json_returns_none(self, coordinator: PhaseCoordinator) -> None:
        assert coordinator._try_parse_json_payload("not json at all") is None


class TestExtractRuffDiagnostics:
    """Test ruff diagnostic extraction from output."""

    def test_no_output_returns_empty(self, coordinator: PhaseCoordinator) -> None:
        result = HookResult(id="h1", name="ruff", status="failed")
        assert coordinator._extract_ruff_diagnostics_from_output(result) == []

    def test_pure_json_array(self, coordinator: PhaseCoordinator) -> None:
        result = HookResult(
            id="h1",
            name="ruff",
            status="failed",
            output=json.dumps(
                [
                    {
                        "filename": "a.py",
                        "location": {"row": 1},
                        "code": "F401",
                        "message": "unused",
                    }
                ]
            ),
        )
        diagnostics = coordinator._extract_ruff_diagnostics_from_output(result)
        assert len(diagnostics) == 1
        assert diagnostics[0]["code"] == "F401"

    def test_embedded_json_object(self, coordinator: PhaseCoordinator) -> None:
        """Object with 'diagnostics' key works."""
        output = "noise\n" + json.dumps(
            {"diagnostics": [{"code": "B904", "message": "raise from err"}]}
        )
        result = HookResult(
            id="h1",
            name="ruff",
            status="failed",
            output=output,
        )
        diagnostics = coordinator._extract_ruff_diagnostics_from_output(result)
        assert len(diagnostics) == 1
        assert diagnostics[0]["code"] == "B904"

    def test_embedded_json_results_key(self, coordinator: PhaseCoordinator) -> None:
        """Object with 'results' key works."""
        output = json.dumps({"results": [{"code": "E501"}]})
        result = HookResult(
            id="h1", name="ruff", status="failed", output=output
        )
        diagnostics = coordinator._extract_ruff_diagnostics_from_output(result)
        assert len(diagnostics) == 1
        assert diagnostics[0]["code"] == "E501"

    def test_embedded_json_issues_key(self, coordinator: PhaseCoordinator) -> None:
        """Object with 'issues' key works."""
        output = json.dumps({"issues": [{"code": "W291"}]})
        result = HookResult(
            id="h1", name="ruff", status="failed", output=output
        )
        diagnostics = coordinator._extract_ruff_diagnostics_from_output(result)
        assert len(diagnostics) == 1
        assert diagnostics[0]["code"] == "W291"

    def test_object_without_relevant_keys(self, coordinator: PhaseCoordinator) -> None:
        """Object with unrelated keys returns empty list."""
        result = HookResult(
            id="h1",
            name="ruff",
            status="failed",
            output=json.dumps({"summary": "ok"}),
        )
        assert coordinator._extract_ruff_diagnostics_from_output(result) == []

    def test_uses_error_when_output_empty(
        self, coordinator: PhaseCoordinator
    ) -> None:
        """Falls back to error field when output is empty."""
        result = HookResult(
            id="h1",
            name="ruff",
            status="failed",
            output=None,
            error=json.dumps([{"code": "F401"}]),
        )
        diagnostics = coordinator._extract_ruff_diagnostics_from_output(result)
        assert len(diagnostics) == 1

    def test_uses_error_message_fallback(
        self, coordinator: PhaseCoordinator
    ) -> None:
        """Falls back to error_message when output and error are both empty."""
        result = HookResult(
            id="h1",
            name="ruff",
            status="failed",
            output=None,
            error=None,
            error_message=json.dumps([{"code": "F401"}]),
        )
        diagnostics = coordinator._extract_ruff_diagnostics_from_output(result)
        assert len(diagnostics) == 1


class TestDisplayRuffFailureDetails:
    """Test the ruff output summarizer."""

    def test_non_ruff_hook_skipped(self, coordinator: PhaseCoordinator) -> None:
        """Non-ruff hook names short-circuit."""
        result = HookResult(
            id="h1",
            name="black",
            status="failed",
            duration=0.1,
            output=json.dumps([{"code": "F401"}]),
        )
        coordinator.console.print = MagicMock()
        coordinator._display_ruff_failure_details(result)
        coordinator.console.print.assert_not_called()

    def test_ruff_no_diagnostics(self, coordinator: PhaseCoordinator) -> None:
        """Ruff hook with no diagnostics prints nothing."""
        result = HookResult(
            id="h1", name="ruff-check", status="failed", duration=0.1, output="plain"
        )
        coordinator.console.print = MagicMock()
        coordinator._display_ruff_failure_details(result)
        coordinator.console.print.assert_not_called()

    def test_ruff_summarizes_codes(self, coordinator: PhaseCoordinator) -> None:
        """Top 8 codes are printed sorted by frequency."""
        items = [
            {"filename": "a.py", "location": {"row": 1}, "code": "F401", "message": "x"},
            {"filename": "b.py", "location": {"row": 2}, "code": "F401", "message": "y"},
            {"filename": "c.py", "location": {"row": 3}, "code": "B904", "message": "z"},
        ]
        result = HookResult(
            id="h1",
            name="ruff",
            status="failed",
            duration=0.1,
            output=json.dumps(items),
        )
        coordinator.console.print = MagicMock()
        coordinator._display_ruff_failure_details(result)
        printed = " | ".join(
            str(call.args[0]) for call in coordinator.console.print.call_args_list
        )
        assert "Ruff issues parsed: 3" in printed
        assert "F401 x2" in printed
        assert "B904 x1" in printed
        assert "a.py:1 F401 x" in printed

    def test_ruff_handles_missing_location_row(
        self, coordinator: PhaseCoordinator
    ) -> None:
        """location without a numeric 'row' key is treated as no line number."""
        items = [
            {
                "filename": "a.py",
                "location": {},
                "code": "F401",
                "message": "unused",
            }
        ]
        result = HookResult(
            id="h1",
            name="ruff",
            status="failed",
            duration=0.1,
            output=json.dumps(items),
        )
        coordinator.console.print = MagicMock()
        coordinator._display_ruff_failure_details(result)
        printed = " | ".join(
            str(call.args[0]) for call in coordinator.console.print.call_args_list
        )
        assert "a.py F401" in printed


# ---------------------------------------------------------------------------
# AI fix flows (fast + comprehensive)
# ---------------------------------------------------------------------------


class TestApplyAiFixForFastHooks:
    """The _apply_ai_fix_for_fast_hooks method has multiple branches."""

    async def test_ai_fix_first_iteration_succeeds(
        self, coordinator: PhaseCoordinator, mock_options: MagicMock
    ) -> None:
        """First iteration: AI fix succeeds and re-run passes."""
        mock_options.ai_fix = True
        mock_options.verbose = True
        mock_options.ai_debug = False
        mock_options.ai_fix_max_iterations = 3

        coordinator._last_hook_results = [
            HookResult(
                id="h1",
                name="ruff",
                status="failed",
                duration=0.1,
                issues_count=2,
            ),
        ]

        fake_coordinator = MagicMock()
        fake_coordinator._event_bus = MagicMock()
        fake_coordinator.apply_fast_stage_fixes = AsyncMock(return_value=True)
        fake_coordinator.progress_manager = MagicMock(enabled=False)

        with patch(
            "crackerjack.core.autofix_coordinator.AutofixCoordinator",
            return_value=fake_coordinator,
        ), patch(
            "crackerjack.ui.ai_fix_dashboard.attach_dashboard",
            return_value=MagicMock(stop=MagicMock()),
        ), patch.object(
            coordinator, "_execute_hooks_once", return_value=True
        ):
            result = await coordinator._apply_ai_fix_for_fast_hooks(
                mock_options, current_success=False
            )

        assert result is True

    async def test_ai_fix_failure_returns_current_success(
        self, coordinator: PhaseCoordinator, mock_options: MagicMock
    ) -> None:
        """When AI fix fails on first iteration, return current_success."""
        mock_options.ai_fix = True
        mock_options.verbose = True
        mock_options.ai_fix_max_iterations = 3

        fake_coordinator = MagicMock()
        fake_coordinator._event_bus = MagicMock()
        fake_coordinator.apply_fast_stage_fixes = AsyncMock(return_value=False)
        fake_coordinator.progress_manager = MagicMock(enabled=False)

        with patch(
            "crackerjack.core.autofix_coordinator.AutofixCoordinator",
            return_value=fake_coordinator,
        ), patch(
            "crackerjack.ui.ai_fix_dashboard.attach_dashboard",
            return_value=MagicMock(stop=MagicMock()),
        ):
            result = await coordinator._apply_ai_fix_for_fast_hooks(
                mock_options, current_success=False
            )

        assert result is False

    async def test_ai_fix_exhausts_iterations(
        self, coordinator: PhaseCoordinator, mock_options: MagicMock
    ) -> None:
        """All iterations fail -> returns False."""
        mock_options.ai_fix = True
        mock_options.verbose = False
        mock_options.ai_debug = False
        mock_options.ai_fix_max_iterations = 2

        fake_coordinator = MagicMock()
        fake_coordinator._event_bus = MagicMock()
        fake_coordinator.apply_fast_stage_fixes = AsyncMock(return_value=True)
        fake_coordinator.progress_manager = MagicMock(enabled=False)

        with patch(
            "crackerjack.core.autofix_coordinator.AutofixCoordinator",
            return_value=fake_coordinator,
        ), patch(
            "crackerjack.ui.ai_fix_dashboard.attach_dashboard",
            return_value=MagicMock(stop=MagicMock()),
        ), patch.object(
            coordinator, "_execute_hooks_once", return_value=False
        ):
            result = await coordinator._apply_ai_fix_for_fast_hooks(
                mock_options, current_success=False
            )

        assert result is False


class TestApplyAiFixForComprehensiveHooks:
    """_apply_ai_fix_for_comprehensive_hooks coverage."""

    async def test_first_iteration_passes(
        self, coordinator: PhaseCoordinator, mock_options: MagicMock
    ) -> None:
        """First AI fix iteration succeeds -> returns True."""
        mock_options.ai_fix = True
        mock_options.verbose = False
        mock_options.ai_debug = False
        mock_options.ai_fix_max_iterations = 3

        fake_coordinator = MagicMock()
        fake_coordinator.apply_comprehensive_stage_fixes = AsyncMock(
            return_value=True
        )

        with patch(
            "crackerjack.core.autofix_coordinator.AutofixCoordinator",
            return_value=fake_coordinator,
        ), patch.object(
            coordinator, "_execute_hooks_once", return_value=True
        ):
            result = await coordinator._apply_ai_fix_for_comprehensive_hooks(
                mock_options, current_success=False
            )

        assert result is True

    async def test_first_iteration_fails(
        self, coordinator: PhaseCoordinator, mock_options: MagicMock
    ) -> None:
        """First AI fix iteration fails -> return current_success."""
        mock_options.ai_fix = True
        mock_options.ai_fix_max_iterations = 3

        fake_coordinator = MagicMock()
        fake_coordinator.apply_comprehensive_stage_fixes = AsyncMock(
            return_value=False
        )

        with patch(
            "crackerjack.core.autofix_coordinator.AutofixCoordinator",
            return_value=fake_coordinator,
        ):
            result = await coordinator._apply_ai_fix_for_comprehensive_hooks(
                mock_options, current_success=False
            )

        assert result is False

    async def test_exhausts_iterations(
        self, coordinator: PhaseCoordinator, mock_options: MagicMock
    ) -> None:
        """All iterations pass fix but hooks still fail -> returns False."""
        mock_options.ai_fix = True
        mock_options.ai_fix_max_iterations = 2

        fake_coordinator = MagicMock()
        fake_coordinator.apply_comprehensive_stage_fixes = AsyncMock(
            return_value=True
        )

        with patch(
            "crackerjack.core.autofix_coordinator.AutofixCoordinator",
            return_value=fake_coordinator,
        ), patch.object(
            coordinator, "_execute_hooks_once", return_value=False
        ):
            result = await coordinator._apply_ai_fix_for_comprehensive_hooks(
                mock_options, current_success=False
            )

        assert result is False


class TestShouldShowAiFixBanner:
    """_should_show_ai_fix_banner is True iff verbose or ai_debug."""

    def test_verbose_only(self, coordinator: PhaseCoordinator) -> None:
        opts = MagicMock(verbose=True, ai_debug=False)
        assert coordinator._should_show_ai_fix_banner(opts) is True

    def test_ai_debug_only(self, coordinator: PhaseCoordinator) -> None:
        opts = MagicMock(verbose=False, ai_debug=True)
        assert coordinator._should_show_ai_fix_banner(opts) is True

    def test_neither(self, coordinator: PhaseCoordinator) -> None:
        opts = MagicMock(verbose=False, ai_debug=False)
        assert coordinator._should_show_ai_fix_banner(opts) is False


# ---------------------------------------------------------------------------
# JSONC pre-retry stripping
# ---------------------------------------------------------------------------


class TestPrepareJsoncFilesBeforeRetry:
    """Cover the JSONC retry-stripping branches."""

    def test_no_last_results_noop(self, coordinator: PhaseCoordinator) -> None:
        coordinator._last_hook_results = []
        # Must not raise; should not call AutofixCoordinator
        with patch(
            "crackerjack.core.autofix_coordinator.AutofixCoordinator"
        ) as mock_cls:
            coordinator._prepare_jsonc_files_before_retry()
        mock_cls.assert_not_called()

    def test_no_json_failures_noop(self, coordinator: PhaseCoordinator) -> None:
        coordinator._last_hook_results = [
            HookResult(
                id="h1",
                name="ruff",
                status="failed",
                duration=0.1,
                issues_count=2,
            ),
        ]
        with patch(
            "crackerjack.core.autofix_coordinator.AutofixCoordinator"
        ) as mock_cls:
            coordinator._prepare_jsonc_files_before_retry()
        mock_cls.assert_not_called()

    def test_json_failures_triggers_strip(
        self, coordinator: PhaseCoordinator
    ) -> None:
        coordinator._last_hook_results = [
            HookResult(
                id="h1",
                name="format-json",
                status="failed",
                duration=0.1,
                issues_count=1,
            ),
            HookResult(
                id="h2",
                name="check-json",
                status="failed",
                duration=0.1,
                issues_count=1,
            ),
        ]
        mock_coordinator = MagicMock()
        mock_coordinator._strip_jsonc_comments_from_failed_json_files.return_value = "ok"
        with patch(
            "crackerjack.core.autofix_coordinator.AutofixCoordinator",
            return_value=mock_coordinator,
        ):
            coordinator._prepare_jsonc_files_before_retry()
        mock_coordinator._strip_jsonc_comments_from_failed_json_files.assert_called_once()

    def test_json_failure_with_exception_logs(
        self, coordinator: PhaseCoordinator
    ) -> None:
        """Exception in JSONC strip is caught and logged."""
        coordinator._last_hook_results = [
            HookResult(
                id="h1",
                name="format-json",
                status="failed",
                duration=0.1,
                issues_count=1,
            ),
        ]
        with patch(
            "crackerjack.core.autofix_coordinator.AutofixCoordinator",
            side_effect=RuntimeError("boom"),
        ):
            # Should not raise
            coordinator._prepare_jsonc_files_before_retry()


# ---------------------------------------------------------------------------
# Publishing workflow
# ---------------------------------------------------------------------------


class TestRunPublishingPhase:
    """_run_publishing_phase with and without a version type."""

    def test_runs_publishing_workflow_when_version_present(
        self, coordinator: PhaseCoordinator, mock_options: MagicMock
    ) -> None:
        mock_options.publish = "patch"
        with patch.object(
            coordinator, "_execute_publishing_workflow", return_value=True
        ) as mock_exec:
            result = coordinator.run_publishing_phase(mock_options)
        assert result is True
        mock_exec.assert_called_once_with(mock_options, "patch")

    def test_publishing_failure_marks_session_failed(
        self, coordinator: PhaseCoordinator, mock_options: MagicMock
    ) -> None:
        mock_options.publish = "minor"
        with patch.object(
            coordinator, "_execute_publishing_workflow", return_value=False
        ):
            result = coordinator.run_publishing_phase(mock_options)
        assert result is False


class TestExecutePublishingWorkflow:
    """Cover the version-bump, commit, push, rollback paths."""

    def test_full_publish_success(
        self, coordinator: PhaseCoordinator, mock_options: MagicMock
    ) -> None:
        mock_options.commit = False
        mock_options.no_git_tags = False
        coordinator.git_service.get_current_commit_hash = MagicMock(
            side_effect=["orig123", "new456"]
        )
        coordinator.git_service.push_with_tags = MagicMock(return_value=True)
        coordinator.publish_manager.bump_version = MagicMock(return_value="1.2.4")
        coordinator.publish_manager.publish_package = MagicMock(return_value=True)
        coordinator.publish_manager.create_git_tag_local = MagicMock(
            return_value=True
        )

        with patch.object(
            coordinator, "_handle_pre_publish_commit", return_value=True
        ):
            result = coordinator._execute_publishing_workflow(
                mock_options, "patch"
            )

        assert result is True
        coordinator.publish_manager.bump_version.assert_called_once_with("patch")
        coordinator.publish_manager.publish_package.assert_called_once()

    def test_pre_publish_commit_fails(
        self, coordinator: PhaseCoordinator, mock_options: MagicMock
    ) -> None:
        mock_options.commit = True
        with patch.object(
            coordinator, "_handle_pre_publish_commit", return_value=False
        ):
            result = coordinator._execute_publishing_workflow(
                mock_options, "patch"
            )
        assert result is False

    def test_version_bump_fails(
        self, coordinator: PhaseCoordinator, mock_options: MagicMock
    ) -> None:
        mock_options.commit = False
        coordinator.publish_manager.bump_version = MagicMock(return_value=None)
        with patch.object(
            coordinator, "_handle_pre_publish_commit", return_value=True
        ):
            result = coordinator._execute_publishing_workflow(
                mock_options, "patch"
            )
        assert result is False

    def test_commit_version_changes_no_files(
        self, coordinator: PhaseCoordinator, mock_options: MagicMock
    ) -> None:
        mock_options.commit = False
        coordinator.publish_manager.bump_version = MagicMock(return_value="1.2.4")
        coordinator.git_service.get_changed_files = MagicMock(return_value=[])

        with patch.object(
            coordinator, "_handle_pre_publish_commit", return_value=True
        ), patch.object(
            coordinator, "_commit_version_changes", return_value=None
        ):
            result = coordinator._execute_publishing_workflow(
                mock_options, "patch"
            )
        assert result is False

    def test_publish_to_pypi_failure_triggers_rollback(
        self, coordinator: PhaseCoordinator, mock_options: MagicMock
    ) -> None:
        mock_options.commit = False
        mock_options.no_git_tags = False
        coordinator.publish_manager.bump_version = MagicMock(return_value="1.2.4")
        coordinator.publish_manager.publish_package = MagicMock(return_value=False)
        coordinator.git_service.get_current_commit_hash = MagicMock(
            side_effect=["orig", "new"]
        )
        coordinator.git_service.push_with_tags = MagicMock(return_value=True)

        with patch.object(
            coordinator, "_handle_pre_publish_commit", return_value=True
        ), patch.object(
            coordinator, "_attempt_rollback_version_bump", return_value=True
        ) as mock_rollback, patch.object(
            coordinator, "_commit_version_changes", return_value="newcommit"
        ):
            result = coordinator._execute_publishing_workflow(
                mock_options, "patch"
            )
        assert result is False
        mock_rollback.assert_called_once_with("orig", "new")


class TestCommitVersionChanges:
    """_commit_version_changes paths."""

    def test_no_changed_files(self, coordinator: PhaseCoordinator) -> None:
        coordinator.git_service.get_changed_files = MagicMock(return_value=[])
        coordinator.console.print = MagicMock()

        with patch.object(coordinator, "_display_commit_push_header"):
            result = coordinator._commit_version_changes("1.2.4")

        assert result is None

    def test_add_files_fails(self, coordinator: PhaseCoordinator) -> None:
        coordinator.git_service.get_changed_files = MagicMock(
            return_value=["a.py", "b.py"]
        )
        coordinator.git_service.add_files = MagicMock(return_value=False)
        coordinator.console.print = MagicMock()

        with patch.object(coordinator, "_display_commit_push_header"):
            result = coordinator._commit_version_changes("1.2.4")

        assert result is None

    def test_commit_fails(self, coordinator: PhaseCoordinator) -> None:
        coordinator.git_service.get_changed_files = MagicMock(return_value=["a.py"])
        coordinator.git_service.add_files = MagicMock(return_value=True)
        coordinator.git_service.commit = MagicMock(return_value=False)
        coordinator.console.print = MagicMock()

        with patch.object(coordinator, "_display_commit_push_header"):
            result = coordinator._commit_version_changes("1.2.4")

        assert result is None

    def test_commit_success_no_head_hash(
        self, coordinator: PhaseCoordinator
    ) -> None:
        coordinator.git_service.get_changed_files = MagicMock(return_value=["a.py"])
        coordinator.git_service.add_files = MagicMock(return_value=True)
        coordinator.git_service.commit = MagicMock(return_value=True)
        coordinator.git_service.get_current_commit_hash = MagicMock(
            side_effect=AttributeError("nope")
        )
        coordinator.console.print = MagicMock()

        with patch.object(coordinator, "_display_commit_push_header"):
            result = coordinator._commit_version_changes("1.2.4")

        assert result is None  # hasattr check fails -> None


class TestFinalizePublishing:
    """_finalize_publishing covers both tag and push paths."""

    def test_tag_creation_fails_continues(
        self, coordinator: PhaseCoordinator, mock_options: MagicMock
    ) -> None:
        mock_options.no_git_tags = False
        coordinator.publish_manager.create_git_tag_local = MagicMock(
            return_value=False
        )
        coordinator.git_service.push_with_tags = MagicMock(return_value=True)
        coordinator.console.print = MagicMock()
        coordinator._finalize_publishing(mock_options, "1.2.4")

    def test_push_fails_continues(
        self, coordinator: PhaseCoordinator, mock_options: MagicMock
    ) -> None:
        mock_options.no_git_tags = False
        coordinator.publish_manager.create_git_tag_local = MagicMock(
            return_value=True
        )
        coordinator.git_service.push_with_tags = MagicMock(return_value=False)
        coordinator.console.print = MagicMock()
        coordinator._finalize_publishing(mock_options, "1.2.4")
        coordinator.git_service.push_with_tags.assert_called_once()

    def test_no_git_tags_skips_tag(
        self, coordinator: PhaseCoordinator, mock_options: MagicMock
    ) -> None:
        mock_options.no_git_tags = True
        coordinator.publish_manager.create_git_tag_local = MagicMock()
        coordinator.git_service.push_with_tags = MagicMock(return_value=True)
        coordinator.console.print = MagicMock()
        coordinator._finalize_publishing(mock_options, "1.2.4")
        coordinator.publish_manager.create_git_tag_local.assert_not_called()


class TestAttemptRollbackVersionBump:
    """_attempt_rollback_version_bump happy and error paths."""

    def test_rollback_success(self, coordinator: PhaseCoordinator) -> None:
        coordinator.git_service.reset_hard = MagicMock(return_value=True)
        coordinator.console.print = MagicMock()
        result = coordinator._attempt_rollback_version_bump("orig123", "newcommit456")
        assert result is True

    def test_rollback_returns_false(self, coordinator: PhaseCoordinator) -> None:
        coordinator.git_service.reset_hard = MagicMock(return_value=False)
        coordinator.console.print = MagicMock()
        result = coordinator._attempt_rollback_version_bump("orig123", "newcommit456")
        assert result is False

    def test_rollback_exception(self, coordinator: PhaseCoordinator) -> None:
        coordinator.git_service.reset_hard = MagicMock(
            side_effect=RuntimeError("git error")
        )
        coordinator.console.print = MagicMock()
        result = coordinator._attempt_rollback_version_bump("orig123", "newcommit456")
        assert result is False


# ---------------------------------------------------------------------------
# Commit / push workflow
# ---------------------------------------------------------------------------


class TestRunCommitPhase:
    """_run_commit_phase main branches."""

    def test_no_changes_calls_no_changes(
        self, coordinator: PhaseCoordinator, mock_options: MagicMock
    ) -> None:
        mock_options.commit = True
        coordinator.git_service.get_changed_files = MagicMock(return_value=[])
        with patch.object(
            coordinator, "_handle_no_changes_to_commit", return_value=True
        ) as mock_handler:
            result = coordinator.run_commit_phase(mock_options)
        assert result is True
        mock_handler.assert_called_once()

    def test_changes_runs_commit_and_push(
        self, coordinator: PhaseCoordinator, mock_options: MagicMock
    ) -> None:
        mock_options.commit = True
        mock_options.interactive = False
        coordinator.git_service.get_changed_files = MagicMock(
            return_value=["a.py", "b.py"]
        )
        coordinator.git_service.get_commit_message_suggestions = MagicMock(
            return_value=["feat: new thing"]
        )
        with patch.object(
            coordinator, "_execute_commit_and_push", return_value=True
        ) as mock_exec, patch.object(
            coordinator, "_display_commit_push_header"
        ):
            result = coordinator.run_commit_phase(mock_options)
        assert result is True
        mock_exec.assert_called_once()


class TestGetCommitMessage:
    """_get_commit_message fallback paths."""

    def test_no_suggestions_returns_default(
        self, coordinator: PhaseCoordinator
    ) -> None:
        coordinator.git_service.get_commit_message_suggestions = MagicMock(
            return_value=[]
        )
        result = coordinator._get_commit_message(["a.py"], MagicMock(interactive=False))
        assert result == "Update project files"

    def test_first_suggestion_chosen(
        self, coordinator: PhaseCoordinator
    ) -> None:
        coordinator.git_service.get_commit_message_suggestions = MagicMock(
            return_value=["first message", "second"]
        )
        opts = MagicMock(interactive=False)
        assert (
            coordinator._get_commit_message(["a.py"], opts) == "first message"
        )

    def test_interactive_choice(
        self, coordinator: PhaseCoordinator
    ) -> None:
        coordinator.git_service.get_commit_message_suggestions = MagicMock(
            return_value=["first", "second"]
        )
        opts = MagicMock(interactive=True)
        with patch.object(
            coordinator,
            "_interactive_commit_message_selection",
            return_value="second",
        ):
            result = coordinator._get_commit_message(["a.py"], opts)
        assert result == "second"


class TestInteractiveCommitMessageSelection:
    """_interactive_commit_message_selection with custom input."""

    def test_custom_message_passthrough(
        self, coordinator: PhaseCoordinator
    ) -> None:
        coordinator.console.input = MagicMock(return_value="my custom message")
        coordinator._display_commit_suggestions = MagicMock()
        result = coordinator._interactive_commit_message_selection(
            ["first", "second"]
        )
        assert result == "my custom message"

    def test_numeric_choice_uses_index(
        self, coordinator: PhaseCoordinator
    ) -> None:
        coordinator.console.input = MagicMock(return_value="2")
        coordinator._display_commit_suggestions = MagicMock()
        result = coordinator._interactive_commit_message_selection(
            ["first", "second"]
        )
        assert result == "second"

    def test_empty_choice_uses_default(
        self, coordinator: PhaseCoordinator
    ) -> None:
        coordinator.console.input = MagicMock(return_value="")
        coordinator._display_commit_suggestions = MagicMock()
        result = coordinator._interactive_commit_message_selection(
            ["first", "second"]
        )
        assert result == "first"


class TestDisplayCommitSuggestions:
    """_display_commit_suggestions prints numbered list."""

    def test_prints_numbered_suggestions(
        self, coordinator: PhaseCoordinator
    ) -> None:
        coordinator.console.print = MagicMock()
        coordinator._display_commit_suggestions(["alpha", "beta"])
        printed = " | ".join(
            str(call.args[0]) for call in coordinator.console.print.call_args_list
        )
        assert "Commit message suggestions" in printed
        assert "alpha" in printed
        assert "beta" in printed


class TestExecuteCommitAndPush:
    """_execute_commit_and_push success and failure paths."""

    def test_all_steps_succeed(self, coordinator: PhaseCoordinator) -> None:
        coordinator.git_service.add_files = MagicMock(return_value=True)
        coordinator.git_service.commit = MagicMock(return_value=True)
        coordinator.git_service.push = MagicMock(return_value=True)
        result = coordinator._execute_commit_and_push(["a.py"], "msg")
        assert result is True

    def test_add_files_fails(self, coordinator: PhaseCoordinator) -> None:
        coordinator.git_service.add_files = MagicMock(return_value=False)
        coordinator.git_service.commit = MagicMock()
        coordinator.git_service.push = MagicMock()
        assert coordinator._execute_commit_and_push(["a.py"], "msg") is False
        coordinator.git_service.commit.assert_not_called()

    def test_commit_fails(self, coordinator: PhaseCoordinator) -> None:
        coordinator.git_service.add_files = MagicMock(return_value=True)
        coordinator.git_service.commit = MagicMock(return_value=False)
        coordinator.git_service.push = MagicMock()
        assert coordinator._execute_commit_and_push(["a.py"], "msg") is False
        coordinator.git_service.push.assert_not_called()

    def test_push_fails_still_returns_true(
        self, coordinator: PhaseCoordinator
    ) -> None:
        """Push failure is non-fatal (warning printed)."""
        coordinator.git_service.add_files = MagicMock(return_value=True)
        coordinator.git_service.commit = MagicMock(return_value=True)
        coordinator.git_service.push = MagicMock(return_value=False)
        assert coordinator._execute_commit_and_push(["a.py"], "msg") is True


# ---------------------------------------------------------------------------
# to_json serialization
# ---------------------------------------------------------------------------


class TestToJson:
    """to_json produces the expected dict shape."""

    def test_to_json_empty(self, coordinator: PhaseCoordinator) -> None:
        out = coordinator.to_json([], suite_name="fast")
        assert out["suite"] == "fast"
        assert out["hooks"] == []
        assert "summary" in out

    def test_to_json_with_results(self, coordinator: PhaseCoordinator) -> None:
        results = [
            HookResult(
                id="h1",
                name="ruff",
                status="failed",
                duration=0.2,
                issues_count=2,
                issues_found=["a", "b"],
            ),
        ]
        out = coordinator.to_json(results, suite_name="fast")
        assert out["suite"] == "fast"
        assert len(out["hooks"]) == 1
        assert out["hooks"][0]["name"] == "ruff"
        assert out["hooks"][0]["duration"] == 0.2
        assert out["hooks"][0]["issues_count"] == 2
        assert len(out["hooks"][0]["issues"]) == 2


# ---------------------------------------------------------------------------
# Display hook failures
# ---------------------------------------------------------------------------


class TestDisplayHookFailures:
    """Cover the early-return and printing branches."""

    def test_non_verbose_skips(self, coordinator: PhaseCoordinator) -> None:
        opts = MagicMock(verbose=False, ai_debug=False)
        with patch.object(
            coordinator, "_format_failing_hooks"
        ) as mock_format, patch.object(
            coordinator, "_print_single_hook_failure"
        ) as mock_print:
            coordinator._display_hook_failures("fast", [], opts)
        mock_format.assert_not_called()
        mock_print.assert_not_called()

    def test_verbose_with_no_failures(
        self, coordinator: PhaseCoordinator
    ) -> None:
        opts = MagicMock(verbose=True, ai_debug=False)
        with patch.object(
            coordinator, "_format_failing_hooks", return_value=[]
        ) as mock_format, patch.object(
            coordinator, "_print_single_hook_failure"
        ) as mock_print:
            coordinator._display_hook_failures("fast", [], opts)
        mock_format.assert_called_once()
        mock_print.assert_not_called()

    def test_verbose_with_failures(self, coordinator: PhaseCoordinator) -> None:
        opts = MagicMock(verbose=True, ai_debug=False)
        result = HookResult(
            id="h1", name="ruff", status="failed", duration=0.1
        )
        with patch.object(
            coordinator, "_format_failing_hooks", return_value=[result]
        ), patch.object(
            coordinator, "_print_single_hook_failure"
        ) as mock_print:
            coordinator._display_hook_failures("fast", [result], opts)
        mock_print.assert_called_once_with(result)


class TestFormatFailingHooks:
    """_format_failing_hooks returns only failed/error/timeout."""

    def test_filters_statuses(self, coordinator: PhaseCoordinator) -> None:
        results = [
            HookResult(id="h1", name="a", status="passed", duration=0.1),
            HookResult(id="h2", name="b", status="failed", duration=0.1),
            HookResult(id="h3", name="c", status="error", duration=0.1),
            HookResult(id="h4", name="d", status="timeout", duration=0.1),
            HookResult(id="h5", name="e", status="running", duration=0.1),
        ]
        coordinator.console.print = MagicMock()
        failing = coordinator._format_failing_hooks("fast", results)
        assert len(failing) == 3
        assert {r.name for r in failing} == {"b", "c", "d"}


class TestPrintSingleHookFailure:
    """_print_single_hook_failure branches."""

    def test_with_issues(self, coordinator: PhaseCoordinator) -> None:
        result = HookResult(
            id="h1",
            name="ruff",
            status="failed",
            duration=0.1,
            issues_found=["issue1", "issue2"],
        )
        coordinator.console.print = MagicMock()
        coordinator._print_single_hook_failure(result)
        with patch.object(coordinator, "_display_failure_reasons") as mock_dr:
            pass
        # At least one print call should contain "ruff"
        printed = " | ".join(
            str(call.args[0]) for call in coordinator.console.print.call_args_list
        )
        assert "ruff" in printed

    def test_without_issues_shows_reasons(
        self, coordinator: PhaseCoordinator
    ) -> None:
        result = HookResult(
            id="h1",
            name="ruff",
            status="failed",
            duration=0.1,
            issues_found=None,
            exit_code=137,
        )
        coordinator.console.print = MagicMock()
        with patch.object(coordinator, "_display_failure_reasons") as mock_dr:
            coordinator._print_single_hook_failure(result)
        mock_dr.assert_called_once_with(result)


class TestDisplayIssueDetails:
    """_display_issue_details prints each issue on its own line."""

    def test_no_issues_noop(self, coordinator: PhaseCoordinator) -> None:
        result = HookResult(
            id="h1", name="ruff", status="failed", issues_found=None
        )
        coordinator.console.print = MagicMock()
        coordinator._display_issue_details(result)
        coordinator.console.print.assert_not_called()

    def test_with_issues(self, coordinator: PhaseCoordinator) -> None:
        result = HookResult(
            id="h1",
            name="ruff",
            status="failed",
            issues_found=["a", "b"],
        )
        coordinator.console.print = MagicMock()
        coordinator._display_issue_details(result)
        assert coordinator.console.print.call_count == 2


class TestDisplayTimeoutInfo:
    """_display_timeout_info only fires when is_timeout is set."""

    def test_timeout_set(self, coordinator: PhaseCoordinator) -> None:
        result = HookResult(
            id="h1", name="ruff", status="timeout", is_timeout=True
        )
        coordinator.console.print = MagicMock()
        coordinator._display_timeout_info(result)
        coordinator.console.print.assert_called_once()

    def test_timeout_not_set(self, coordinator: PhaseCoordinator) -> None:
        result = HookResult(id="h1", name="ruff", status="failed", is_timeout=False)
        coordinator.console.print = MagicMock()
        coordinator._display_timeout_info(result)
        coordinator.console.print.assert_not_called()


class TestDisplayExitCodeInfo:
    """_display_exit_code_info covers the well-known exit code branches."""

    def test_no_exit_code(self, coordinator: PhaseCoordinator) -> None:
        result = HookResult(id="h1", name="ruff", status="failed", exit_code=None)
        coordinator.console.print = MagicMock()
        coordinator._display_exit_code_info(result)
        coordinator.console.print.assert_not_called()

    def test_zero_exit_code(self, coordinator: PhaseCoordinator) -> None:
        result = HookResult(id="h1", name="ruff", status="passed", exit_code=0)
        coordinator.console.print = MagicMock()
        coordinator._display_exit_code_info(result)
        coordinator.console.print.assert_not_called()

    def test_oom_137(self, coordinator: PhaseCoordinator) -> None:
        result = HookResult(id="h1", name="ruff", status="failed", exit_code=137)
        coordinator.console.print = MagicMock()
        coordinator._display_exit_code_info(result)
        printed = str(coordinator.console.print.call_args.args[0])
        assert "killed" in printed

    def test_segfault_139(self, coordinator: PhaseCoordinator) -> None:
        result = HookResult(id="h1", name="ruff", status="failed", exit_code=139)
        coordinator.console.print = MagicMock()
        coordinator._display_exit_code_info(result)
        printed = str(coordinator.console.print.call_args.args[0])
        assert "segmentation fault" in printed

    def test_command_not_found(self, coordinator: PhaseCoordinator) -> None:
        result = HookResult(id="h1", name="ruff", status="failed", exit_code=126)
        coordinator.console.print = MagicMock()
        coordinator._display_exit_code_info(result)
        printed = str(coordinator.console.print.call_args.args[0])
        assert "command not found" in printed

    def test_generic_failure_code(self, coordinator: PhaseCoordinator) -> None:
        result = HookResult(id="h1", name="ruff", status="failed", exit_code=1)
        coordinator.console.print = MagicMock()
        coordinator._display_exit_code_info(result)
        printed = str(coordinator.console.print.call_args.args[0])
        assert "Exit code: 1" in printed


class TestDisplayErrorMessage:
    """_display_error_message only fires when error_message is set."""

    def test_no_error_message(self, coordinator: PhaseCoordinator) -> None:
        result = HookResult(
            id="h1", name="ruff", status="failed", error_message=None
        )
        coordinator.console.print = MagicMock()
        coordinator._display_error_message(result)
        coordinator.console.print.assert_not_called()

    def test_with_error_message(self, coordinator: PhaseCoordinator) -> None:
        result = HookResult(
            id="h1",
            name="ruff",
            status="failed",
            error_message="line 1\nline 2",
        )
        coordinator.console.print = MagicMock()
        coordinator._display_error_message(result)
        printed = str(coordinator.console.print.call_args.args[0])
        assert "line 1" in printed
        # The second line is truncated
        assert "line 2" not in printed

    def test_long_error_message_truncated(
        self, coordinator: PhaseCoordinator
    ) -> None:
        long_message = "x" * 500
        result = HookResult(
            id="h1",
            name="ruff",
            status="failed",
            error_message=long_message,
        )
        coordinator.console.print = MagicMock()
        coordinator._display_error_message(result)
        printed = str(coordinator.console.print.call_args.args[0])
        # Preview is at most 200 chars
        assert printed.endswith("x" * 200)


class TestDisplayGenericFailure:
    """_display_generic_failure fires only when no other diagnostic was set."""

    def test_no_reasons_no_print(self, coordinator: PhaseCoordinator) -> None:
        result = HookResult(
            id="h1", name="ruff", status="failed", is_timeout=False, exit_code=0
        )
        coordinator.console.print = MagicMock()
        coordinator._display_generic_failure(result)
        # When exit_code is 0 (not None), the function does NOT print
        coordinator.console.print.assert_not_called()

    def test_all_none_prints(self, coordinator: PhaseCoordinator) -> None:
        result = HookResult(
            id="h1",
            name="ruff",
            status="failed",
            is_timeout=False,
            exit_code=None,
            error_message=None,
        )
        coordinator.console.print = MagicMock()
        coordinator._display_generic_failure(result)
        coordinator.console.print.assert_called_once()


# ---------------------------------------------------------------------------
# JSONC retry + AI fix integration with run_fast_hooks_only
# ---------------------------------------------------------------------------


class TestRunFastHooksWithRetry:
    """_run_fast_hooks_with_retry path: success on first try."""

    def test_first_attempt_succeeds(
        self, coordinator: PhaseCoordinator, mock_options: MagicMock
    ) -> None:
        mock_options.fast_iteration = False
        with patch.object(
            coordinator, "_execute_hooks_once", return_value=True
        ) as mock_exec, patch.object(
            coordinator, "_display_hook_phase_header"
        ):
            result = coordinator._run_fast_hooks_with_retry(mock_options)
        assert result is True
        assert mock_exec.call_count == 1

    def test_two_attempts_then_success(
        self, coordinator: PhaseCoordinator, mock_options: MagicMock
    ) -> None:
        mock_options.fast_iteration = False
        with patch.object(
            coordinator, "_execute_hooks_once", side_effect=[False, True]
        ) as mock_exec, patch.object(
            coordinator, "_display_hook_phase_header"
        ), patch.object(
            coordinator, "_display_hook_failures"
        ), patch.object(
            coordinator, "_prepare_jsonc_files_before_retry"
        ) as mock_prep:
            result = coordinator._run_fast_hooks_with_retry(mock_options)
        assert result is True
        assert mock_exec.call_count == 2
        # JSONC pre-retry should have been called on second attempt
        mock_prep.assert_called_once()

    def test_fast_iteration_breaks_after_first_failure(
        self, coordinator: PhaseCoordinator, mock_options: MagicMock
    ) -> None:
        mock_options.fast_iteration = True
        with patch.object(
            coordinator, "_execute_hooks_once", return_value=False
        ) as mock_exec, patch.object(
            coordinator, "_display_hook_phase_header"
        ), patch.object(
            coordinator, "_prepare_jsonc_files_before_retry"
        ) as mock_prep:
            result = coordinator._run_fast_hooks_with_retry(mock_options)
        assert result is False
        assert mock_exec.call_count == 1
        # Should NOT call JSONC prep on fast_iteration
        mock_prep.assert_not_called()

    def test_both_attempts_fail(
        self, coordinator: PhaseCoordinator, mock_options: MagicMock
    ) -> None:
        mock_options.fast_iteration = False
        with patch.object(
            coordinator, "_execute_hooks_once", return_value=False
        ) as mock_exec, patch.object(
            coordinator, "_display_hook_phase_header"
        ), patch.object(
            coordinator, "_display_hook_failures"
        ), patch.object(
            coordinator, "_prepare_jsonc_files_before_retry"
        ):
            result = coordinator._run_fast_hooks_with_retry(mock_options)
        assert result is False
        assert mock_exec.call_count == 2


class TestCompleteFastHooksTask:
    """_complete_fast_hooks_task sets session state correctly."""

    def test_success_path(self, coordinator: PhaseCoordinator) -> None:
        coordinator._last_hook_summary = {
            "total": 2,
            "passed": 2,
            "failed": 0,
            "errors": 0,
            "total_duration": 0.1,
        }
        coordinator.console.print = MagicMock()
        coordinator._complete_fast_hooks_task(success=True)

    def test_failure_path(self, coordinator: PhaseCoordinator) -> None:
        coordinator._last_hook_summary = {
            "total": 2,
            "passed": 1,
            "failed": 1,
            "errors": 0,
            "total_duration": 0.1,
        }
        coordinator.console.print = MagicMock()
        coordinator._complete_fast_hooks_task(success=False)

    def test_no_summary(self, coordinator: PhaseCoordinator) -> None:
        coordinator._last_hook_summary = None
        coordinator.console.print = MagicMock()
        coordinator._complete_fast_hooks_task(success=True)


# ---------------------------------------------------------------------------
# to_json with issues formatting
# ---------------------------------------------------------------------------


class TestFormatIssues:
    """_format_issues returns the right shape for object and string issues."""

    def test_format_object_issue(self, coordinator: PhaseCoordinator) -> None:
        # Dataclass-like issue
        class _Issue:
            file_path = "x.py"
            line_number = 10
            message = "msg"
            code = "E501"
            severity = "warning"
            suggestion = "fix it"

        out = coordinator._format_issues([_Issue()])
        assert len(out) == 1
        assert out[0]["file"] == "x.py"
        assert out[0]["line"] == 10
        assert out[0]["message"] == "msg"
        assert out[0]["code"] == "E501"

    def test_format_string_issue(self, coordinator: PhaseCoordinator) -> None:
        out = coordinator._format_issues(["just a string"])
        assert len(out) == 1
        assert out[0]["file"] == "unknown"
        assert out[0]["message"] == "just a string"


# ---------------------------------------------------------------------------
# _clean_python_files with files
# ---------------------------------------------------------------------------


class TestCleanPythonFiles:
    """_clean_python_files collects paths of files actually cleaned."""

    def test_returns_only_cleaned_files(
        self, coordinator: PhaseCoordinator, tmp_path: Path
    ) -> None:
        py_file = tmp_path / "a.py"
        py_file.write_text("print('hi')")
        # Stub code_cleaner to clean the first file but not the second
        results = iter([True, False])
        coordinator.code_cleaner.should_process_file = MagicMock(return_value=True)
        coordinator.code_cleaner.clean_file = MagicMock(
            side_effect=lambda f: MagicMock(success=next(results))
        )
        cleaned = coordinator._clean_python_files([py_file, tmp_path / "b.py"])
        assert cleaned == [str(py_file)]


class TestReportCleaningResults:
    """_report_cleaning_results selects the right session message."""

    def test_with_files(self, coordinator: PhaseCoordinator) -> None:
        coordinator.console.print = MagicMock()
        coordinator._report_cleaning_results(["a.py", "b.py"])
        coordinator.session.complete_task.assert_called_once()

    def test_no_files(self, coordinator: PhaseCoordinator) -> None:
        coordinator.console.print = MagicMock()
        coordinator._report_cleaning_results([])
        coordinator.session.complete_task.assert_called_once_with(
            "cleaning", "No cleaning needed"
        )
