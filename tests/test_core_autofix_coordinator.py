import subprocess
from pathlib import Path
from shutil import copy2 as real_copy2
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
from rich.console import Console

from crackerjack.agents.base import FixResult, Issue, IssueType, Priority
from crackerjack.agents.fixer_coordinator import FixerCoordinator
from crackerjack.core.autofix_coordinator import AutofixCoordinator
from crackerjack.models.fix_plan import ChangeSpec, FixPlan


class TestAutofixCoordinator:
    @pytest.fixture
    def mock_console(self):
        return Mock(spec=Console)

    @pytest.fixture
    def coordinator(self, mock_console):
        pkg_path = Path("/ test / path")
        return AutofixCoordinator(console=mock_console, pkg_path=pkg_path)

    def test_coordinator_initialization(self, mock_console) -> None:
        pkg_path = Path("/ test / path")
        coordinator = AutofixCoordinator(console=mock_console, pkg_path=pkg_path)

        assert coordinator.console is mock_console
        assert coordinator.pkg_path == pkg_path
        assert coordinator.logger.name == "crackerjack.autofix"

    @pytest.mark.asyncio
    async def test_apply_autofix_for_hooks_fast_mode(self, coordinator) -> None:
        hook_results = [Mock(name="test_hook", status="failed")]

        with (
            patch.object(coordinator, "_should_skip_autofix", return_value=False),
            patch.object(
                coordinator, "_apply_fast_stage_fixes", return_value=True
            ) as mock_fast,
        ):
            result = await coordinator.apply_autofix_for_hooks("fast", hook_results)

            assert result is True
            mock_fast.assert_called_once()

    @pytest.mark.asyncio
    async def test_apply_autofix_for_hooks_comprehensive_mode(
        self, coordinator
    ) -> None:
        hook_results = [Mock(name="test_hook", status="failed")]

        with (
            patch.object(coordinator, "_should_skip_autofix", return_value=False),
            patch.object(
                coordinator,
                "_apply_comprehensive_stage_fixes",
                return_value=True,
            ) as mock_comp,
        ):
            result = await coordinator.apply_autofix_for_hooks(
                "comprehensive", hook_results
            )

            assert result is True
            mock_comp.assert_called_once_with(hook_results)

    @pytest.mark.asyncio
    async def test_apply_autofix_for_hooks_skip_when_should_skip(
        self, coordinator
    ) -> None:
        hook_results = [Mock()]

        with patch.object(coordinator, "_should_skip_autofix", return_value=True):
            result = await coordinator.apply_autofix_for_hooks("fast", hook_results)

            assert result is False

    @pytest.mark.asyncio
    async def test_apply_autofix_for_hooks_unknown_mode(self, coordinator) -> None:
        hook_results = []

        with patch.object(coordinator, "_should_skip_autofix", return_value=False):
            result = await coordinator.apply_autofix_for_hooks("unknown", hook_results)

            assert result is False

    @pytest.mark.asyncio
    async def test_apply_autofix_for_hooks_exception_handling(
        self, coordinator
    ) -> None:
        hook_results = []

        with patch.object(
            coordinator,
            "_should_skip_autofix",
            side_effect=Exception("Test error"),
        ):
            result = await coordinator.apply_autofix_for_hooks("fast", hook_results)

            assert result is False

    @pytest.mark.asyncio
    async def test_public_interface_methods(self, coordinator) -> None:
        hook_results = [Mock()]
        cmd = ["uv", "run", "ruff", "format", "."]
        result_mock = Mock()

        with (
            patch.object(
                coordinator,
                "_apply_fast_stage_fixes",
                return_value=True,
            ) as mock_fast,
            patch.object(
                coordinator,
                "_apply_comprehensive_stage_fixes",
                return_value=True,
            ) as mock_comp,
            patch.object(
                coordinator,
                "_run_fix_command",
                return_value=True,
            ) as mock_run,
            patch.object(
                coordinator,
                "_check_tool_success_patterns",
                return_value=True,
            ) as mock_check,
            patch.object(
                coordinator,
                "_validate_fix_command",
                return_value=True,
            ) as mock_validate_cmd,
            patch.object(
                coordinator,
                "_validate_hook_result",
                return_value=True,
            ) as mock_validate_hook,
            patch.object(
                coordinator,
                "_should_skip_autofix",
                return_value=False,
            ) as mock_skip,
        ):
            assert await coordinator.apply_fast_stage_fixes() is True
            mock_fast.assert_called_once()

            assert (
                await coordinator.apply_comprehensive_stage_fixes(hook_results) is True
            )
            mock_comp.assert_called_once_with(hook_results)

            assert coordinator.run_fix_command(cmd, "test") is True
            mock_run.assert_called_once_with(cmd, "test")

            assert coordinator.check_tool_success_patterns(cmd, result_mock) is True
            mock_check.assert_called_once_with(cmd, result_mock)

            assert coordinator.validate_fix_command(cmd) is True
            mock_validate_cmd.assert_called_once_with(cmd)

            assert coordinator.validate_hook_result(result_mock) is True
            mock_validate_hook.assert_called_once_with(result_mock)

            assert coordinator.should_skip_autofix(hook_results) is False
            mock_skip.assert_called_once_with(hook_results)

    @pytest.mark.asyncio
    async def test_execute_fast_fixes(self, coordinator) -> None:
        with patch.object(
            coordinator,
            "_run_fix_command",
            return_value=True,
        ) as mock_run:
            result = await coordinator._execute_fast_fixes()

            assert result is True
            assert mock_run.call_count == 2

    @pytest.mark.asyncio
    async def test_execute_fast_fixes_no_fixes_applied(self, coordinator) -> None:
        with patch.object(coordinator, "_run_fix_command", return_value=False):
            result = await coordinator._execute_fast_fixes()

            assert result is False

    @pytest.mark.asyncio
    async def test_apply_comprehensive_stage_fixes(self, coordinator) -> None:
        hook_results = [Mock(name="bandit", status="failed")]

        with (
            patch.object(
                coordinator,
                "_execute_fast_fixes",
                new_callable=AsyncMock,
                return_value=True,
            ) as mock_fast,
            patch.object(coordinator, "_extract_failed_hooks", return_value={"bandit"}),
            patch.object(coordinator, "_get_hook_specific_fixes", return_value=[]),
            patch.object(coordinator, "_run_fix_command", return_value=True),
        ):
            result = await coordinator._apply_comprehensive_stage_fixes(hook_results)

            assert result is True
            mock_fast.assert_called_once()

    def test_extract_failed_hooks(self, coordinator) -> None:
        ruff_result = Mock()
        ruff_result.name = "ruff"
        ruff_result.status = "failed"

        bandit_result = Mock()
        bandit_result.name = "bandit"
        bandit_result.status = "passed"

        pyright_result = Mock()
        pyright_result.name = "pyright"
        pyright_result.status = "failed"

        hook_results = [ruff_result, bandit_result, pyright_result]

        failed_hooks = coordinator._extract_failed_hooks(hook_results)

        assert failed_hooks == {"ruff", "pyright"}

    def test_extract_failed_hooks_invalid_results(self, coordinator) -> None:
        hook_results = [Mock(), Mock()]

        with patch.object(coordinator, "_validate_hook_result", return_value=False):
            failed_hooks = coordinator._extract_failed_hooks(hook_results)

            assert failed_hooks == set()

    def test_get_hook_specific_fixes(self, coordinator) -> None:
        failed_hooks = {"bandit", "ruff"}

        fixes = coordinator._get_hook_specific_fixes(failed_hooks)

        assert len(fixes) == 1
        assert fixes[0][1] == "bandit analysis"

    def test_get_hook_specific_fixes_no_matches(self, coordinator) -> None:
        failed_hooks = {"ruff", "pyright"}

        fixes = coordinator._get_hook_specific_fixes(failed_hooks)

        assert fixes == []

    def test_build_check_commands_includes_opt_in_type_tools_when_enabled(
        self, coordinator
    ) -> None:
        settings = SimpleNamespace(
            hooks=SimpleNamespace(enable_ty=True, enable_pyrefly=True),
            adapter_timeouts=SimpleNamespace(ty_timeout=91, pyrefly_timeout=92),
        )

        with patch(
            "crackerjack.core.autofix_coordinator.CrackerjackSettings",
            return_value=settings,
        ):
            commands = coordinator._build_check_commands(
                Path("/tmp/example"), stage="comprehensive"
            )

        command_names = [hook_name for _, hook_name, _ in commands]
        assert "zuban" in command_names
        assert "refurb" in command_names
        assert "complexity" in command_names
        assert "ty" in command_names
        assert "pyrefly" in command_names

        ty_cmd, _, ty_timeout = next(cmd for cmd in commands if cmd[1] == "ty")
        pyrefly_cmd, _, pyrefly_timeout = next(
            cmd for cmd in commands if cmd[1] == "pyrefly"
        )

        assert ty_cmd[:5] == ["uv", "run", "ty", "check", "--output-format"]
        assert pyrefly_cmd[:5] == ["uv", "run", "pyrefly", "check", "--output-format"]
        assert ty_timeout == 91
        assert pyrefly_timeout == 92

    def test_validate_fix_command_allows_type_tools(self, coordinator) -> None:
        assert coordinator._validate_fix_command(["uv", "run", "ty", "check"])
        assert coordinator._validate_fix_command(["uv", "run", "pyrefly", "check"])

    @pytest.mark.asyncio
    async def test_apply_type_tool_fix_prepasses_runs_ty_fix(self, coordinator) -> None:
        hook_results = [
            SimpleNamespace(
                name="ty",
                status="failed",
                files_checked=[Path("src/example.py")],
            ),
        ]

        mock_adapter = Mock()
        mock_adapter.supports_fix = Mock(return_value=True)
        mock_adapter.settings = Mock(
            fix_enabled=False,
            add_ignore_enabled=False,
            suppress_errors=False,
            baseline_file=Path(".cache/ty-baseline.json"),
        )
        mock_adapter.build_command = Mock(
            return_value=[
                "ty",
                "check",
                "--output-format",
                "concise",
                "--no-progress",
                "--fix",
                "src/example.py",
            ]
        )
        mock_adapter.check = AsyncMock(
            return_value=Mock(parsed_issues=[{"file_path": "src/example.py"}])
        )

        with (
            patch.object(coordinator, "_validate_hook_result", return_value=True),
            patch.object(
                coordinator,
                "_create_type_tool_adapter",
                return_value=mock_adapter,
            ),
            patch.object(
                coordinator, "_run_fix_command", return_value=True
            ) as mock_run,
        ):
            refreshed = await coordinator._apply_type_tool_fix_prepasses(hook_results)

        assert "ty" in refreshed
        assert len(refreshed["ty"]) == 1
        assert refreshed["ty"][0].stage == "ty"
        mock_run.assert_called_once()
        mock_adapter.check.assert_awaited_once()

    @patch("subprocess.run")
    def test_run_fix_command_success(self, mock_subprocess, coordinator) -> None:
        cmd = ["uv", "run", "ruff", "format", "."]
        mock_result = Mock(returncode=0, stdout="", stderr="")
        mock_subprocess.return_value = mock_result

        with patch.object(coordinator, "_validate_fix_command", return_value=True):
            result = coordinator._run_fix_command(cmd, "test")

            assert result is True
            mock_subprocess.assert_called_once()

    @patch("subprocess.run")
    def test_run_fix_command_uses_repo_uv_cache(
        self, mock_subprocess, tmp_path
    ) -> None:
        coordinator = AutofixCoordinator(pkg_path=tmp_path)
        cmd = ["uv", "run", "bandit", "-r", "."]
        mock_subprocess.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="",
            stderr="",
        )

        with patch.object(coordinator, "_validate_fix_command", return_value=True):
            result = coordinator._run_fix_command(cmd, "test")

        assert result is True
        env = mock_subprocess.call_args.kwargs["env"]
        assert env["UV_CACHE_DIR"] == str(tmp_path / ".crackerjack" / "uv" / "cache")
        assert env["RUFF_CACHE_DIR"] == str(
            tmp_path / ".crackerjack" / "uv" / "cache" / "ruff",
        )
        assert env["PIP_CACHE_DIR"] == str(
            tmp_path / ".crackerjack" / "uv" / "cache" / "pip",
        )
        assert Path(env["UV_CACHE_DIR"]).exists()

    def test_create_backup_falls_back_to_writable_backup_dir(
        self, tmp_path: Path
    ) -> None:
        coordinator = AutofixCoordinator(pkg_path=tmp_path)
        source_file = tmp_path / "example.py"
        source_file.write_text("print('hello')\n", encoding="utf-8")

        def fake_copy2(src: Path, dst: Path) -> None:
            if dst.parent == source_file.parent:
                raise OSError("Operation not permitted")
            real_copy2(src, dst)

        with patch(
            "crackerjack.core.autofix_coordinator.shutil.copy2", side_effect=fake_copy2
        ):
            backup_path = coordinator._create_backup(str(source_file))

        backup_file = Path(backup_path)
        assert backup_file.exists()
        assert backup_file.parent != source_file.parent
        assert backup_file.with_suffix(backup_file.suffix + ".json").exists()

        source_file.write_text("print('changed')\n", encoding="utf-8")
        coordinator._restore_backup(backup_path)

        assert source_file.read_text(encoding="utf-8") == "print('hello')\n"
        assert not backup_file.exists()

    @pytest.mark.asyncio
    async def test_execute_single_plan_stops_on_non_retryable_write_failure(
        self, tmp_path: Path
    ) -> None:
        coordinator = AutofixCoordinator(pkg_path=tmp_path)
        plan = Mock()
        plan.file_path = str(tmp_path / "example.py")
        plan.changes = [Mock(line_range=(1, 1))]

        plan_results = [
            Mock(
                success=False,
                remaining_issues=["Failed to write refactored file: example.py"],
            )
        ]

        with (
            patch.object(
                coordinator,
                "_execute_plan_with_validation",
                return_value=(False, plan_results, "Fix failed: failed to write"),
            ),
            patch.object(
                coordinator,
                "_regenerate_plan_with_feedback",
                side_effect=AssertionError("should not retry"),
            ) as mock_regenerate,
        ):
            result = await coordinator._execute_single_plan_with_retry(
                plan=plan,
                fixer_coordinator=Mock(),
                validation_coordinator=Mock(),
                analysis_coordinator=Mock(),
                plan_to_issue={},
                plan_key="example",
                bar=None,
            )

        assert result.success is False
        assert "Fix failed: failed to write" in result.remaining_issues[0]
        mock_regenerate.assert_not_called()

    def test_should_retry_quality_validation(self, coordinator) -> None:
        assert (
            coordinator._should_retry_quality_validation(
                "example.py",
                "Quality validation failed (ruff/refurb):\n  - ruff F401 (line 1): unused import",
            )
            is True
        )
        assert (
            coordinator._should_retry_quality_validation(
                "example.py",
                "Quality validation failed (ruff/refurb):\n  - ruff E501 (line 1): line too long",
            )
            is True
        )
        assert (
            coordinator._should_retry_quality_validation(
                "example.txt",
                "Quality validation failed (ruff/refurb):\n  - ruff F401 (line 1): unused import",
            )
            is False
        )
        assert (
            coordinator._should_retry_quality_validation(
                "example.py",
                "Logic validation failed",
            )
            is False
        )

    def test_should_retry_missing_imports(self, coordinator) -> None:
        assert (
            coordinator._should_retry_missing_imports(
                "Quality validation failed (ruff/refurb):\n  - ruff F821 (line 4): Undefined name `suppress`",
            )
            is True
        )
        assert (
            coordinator._should_retry_missing_imports(
                "Quality validation failed (ruff/refurb):\n  - ruff F401 (line 4): unused import",
            )
            is False
        )

    def test_apply_missing_import_repair_adds_suppress_import(
        self, tmp_path: Path
    ) -> None:
        coordinator = AutofixCoordinator(pkg_path=tmp_path)
        source_file = tmp_path / "example.py"
        source_file.write_text(
            "def f():\n    with suppress(Exception):\n        pass\n",
            encoding="utf-8",
        )

        feedback = (
            "Quality validation failed (ruff/refurb):\n"
            "  - ruff F821 (line 2): Undefined name `suppress`\n"
        )

        assert (
            coordinator._apply_missing_import_repair(str(source_file), feedback) is True
        )
        assert source_file.read_text(encoding="utf-8").startswith(
            "from contextlib import suppress\n"
        )

    @pytest.mark.asyncio
    async def test_execute_plan_with_validation_retries_ruff_feedback(
        self, tmp_path: Path
    ) -> None:
        coordinator = AutofixCoordinator(pkg_path=tmp_path)
        source_file = tmp_path / "example.py"
        source_file.write_text(
            "from contextlib import suppress\n\nvalue = 1\n", encoding="utf-8"
        )

        plan = Mock()
        plan.file_path = str(source_file)
        plan.changes = [Mock(line_range=(1, 1))]
        plan.risk_level = "low"

        fixer_coordinator = Mock()
        fixer_coordinator._candidate_fixer_keys = Mock(return_value=["ruff"])
        fixer_coordinator.execute_plans = AsyncMock(
            return_value=[Mock(success=True, remaining_issues=[])]
        )

        validation_coordinator = Mock()
        validation_coordinator.validate_fix = AsyncMock(
            side_effect=[
                (
                    False,
                    "Quality validation failed (ruff/refurb):\n  - ruff F401 (line 1): unused import",
                ),
                (True, "Fix validated"),
            ]
        )

        with (
            patch.object(coordinator, "_create_backup", return_value="backup-path"),
            patch.object(
                coordinator,
                "_run_targeted_python_fixes",
                return_value=True,
            ) as mock_targeted,
            patch.object(coordinator.progress_manager, "log_event"),
        ):
            (
                result,
                plan_results,
                feedback,
            ) = await coordinator._execute_plan_with_validation(
                plan=plan,
                fixer_coordinator=fixer_coordinator,
                validation_coordinator=validation_coordinator,
                bar=None,
            )

        assert result is True
        assert feedback == ""
        assert plan_results[0].success is True
        mock_targeted.assert_called_once_with(str(source_file))
        assert validation_coordinator.validate_fix.await_count == 2

    @pytest.mark.asyncio
    async def test_execute_plan_with_validation_retries_missing_imports(
        self, tmp_path: Path
    ) -> None:
        coordinator = AutofixCoordinator(pkg_path=tmp_path)
        source_file = tmp_path / "example.py"
        source_file.write_text(
            "def f():\n    with suppress(Exception):\n        pass\n",
            encoding="utf-8",
        )

        plan = Mock()
        plan.file_path = str(source_file)
        plan.changes = [Mock(line_range=(1, 1))]
        plan.risk_level = "low"

        fixer_coordinator = Mock()
        fixer_coordinator._candidate_fixer_keys = Mock(return_value=["ruff"])
        fixer_coordinator.execute_plans = AsyncMock(
            return_value=[Mock(success=True, remaining_issues=[])]
        )

        validation_coordinator = Mock()
        validation_coordinator.validate_fix = AsyncMock(
            side_effect=[
                (
                    False,
                    "Quality validation failed (ruff/refurb):\n"
                    "  - ruff F821 (line 2): Undefined name `suppress`",
                ),
                (True, "Fix validated"),
            ]
        )

        with (
            patch.object(coordinator, "_create_backup", return_value="backup-path"),
            patch.object(
                coordinator,
                "_run_targeted_python_fixes",
                return_value=False,
            ),
            patch.object(coordinator.progress_manager, "log_event"),
        ):
            (
                result,
                plan_results,
                feedback,
            ) = await coordinator._execute_plan_with_validation(
                plan=plan,
                fixer_coordinator=fixer_coordinator,
                validation_coordinator=validation_coordinator,
                bar=None,
            )

        assert result is True
        assert feedback == ""
        assert plan_results[0].success is True
        assert source_file.read_text(encoding="utf-8").startswith(
            "from contextlib import suppress\n"
        )
        assert validation_coordinator.validate_fix.await_count == 2

    @pytest.mark.asyncio
    async def test_execute_plan_with_validation_keeps_written_fix_on_disk(
        self, tmp_path: Path
    ) -> None:
        coordinator = AutofixCoordinator(pkg_path=tmp_path)
        source_file = tmp_path / "example.py"
        source_file.write_text("value = 1\n", encoding="utf-8")

        plan = FixPlan(
            file_path=str(source_file),
            issue_type="FORMATTING",
            changes=[
                ChangeSpec(
                    line_range=(1, 1),
                    old_code="value = 1",
                    new_code="value = 2",
                    reason="Apply targeted fix",
                )
            ],
            rationale="Update literal value",
            risk_level="low",
            validated_by="PlanningAgent",
            issue_message="Update literal value",
            issue_stage="ruff-check",
        )

        real_fixer = FixerCoordinator(project_path=str(tmp_path))

        validation_coordinator = Mock()
        validation_coordinator.validate_fix = AsyncMock(
            return_value=(True, "Fix validated")
        )

        with patch.object(coordinator.progress_manager, "log_event"):
            result, plan_results, feedback = await coordinator._execute_plan_with_validation(
                plan=plan,
                fixer_coordinator=real_fixer,
                validation_coordinator=validation_coordinator,
                bar=None,
            )

        assert result is True
        assert feedback == ""
        assert plan_results[0].success is True
        assert source_file.read_text(encoding="utf-8") == "value = 2\n"

    @pytest.mark.asyncio
    async def test_execute_plans_with_validation_keeps_same_file_different_lines(
        self, tmp_path: Path
    ) -> None:
        coordinator = AutofixCoordinator(pkg_path=tmp_path)
        source_file = tmp_path / "example.py"
        source_file.write_text("first = 1\nsecond = 2\n", encoding="utf-8")

        plans = [
            FixPlan(
                file_path=str(source_file),
                issue_type="FORMATTING",
                changes=[
                    ChangeSpec(
                        line_range=(1, 1),
                        old_code="first = 1",
                        new_code="first = 2",
                        reason="update first line",
                    )
                ],
                rationale="first",
                risk_level="low",
                validated_by="test",
                issue_message="first",
                issue_stage="ruff-check",
            ),
            FixPlan(
                file_path=str(source_file),
                issue_type="FORMATTING",
                changes=[
                    ChangeSpec(
                        line_range=(2, 2),
                        old_code="second = 2",
                        new_code="second = 3",
                        reason="update second line",
                    )
                ],
                rationale="second",
                risk_level="low",
                validated_by="test",
                issue_message="second",
                issue_stage="ruff-check",
            ),
        ]
        issues = [
            Issue(
                type=IssueType.FORMATTING,
                severity=Priority.LOW,
                message="first",
                file_path=str(source_file),
                line_number=1,
            ),
            Issue(
                type=IssueType.FORMATTING,
                severity=Priority.LOW,
                message="second",
                file_path=str(source_file),
                line_number=2,
            ),
        ]

        async def fake_execute_single_plan_with_retry(*args, **kwargs) -> FixResult:
            return FixResult(
                success=True,
                confidence=1.0,
                fixes_applied=["ok"],
                files_modified=[str(source_file)],
            )

        with patch.object(
            coordinator,
            "_execute_single_plan_with_retry",
            side_effect=fake_execute_single_plan_with_retry,
        ) as mock_execute:
            results = await coordinator._execute_plans_with_validation(
                plans=plans,
                fixer_coordinator=Mock(),
                validation_coordinator=Mock(),
                analysis_coordinator=Mock(),
                issues=issues,
            )

        assert mock_execute.await_count == 2
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_apply_ai_agent_fixes_v2_runs_multiple_iterations(
        self, tmp_path: Path
    ) -> None:
        coordinator = AutofixCoordinator(pkg_path=tmp_path)
        source_file = tmp_path / "example.py"
        source_file.write_text("value = 1\n", encoding="utf-8")

        initial_issue = Issue(
            type=IssueType.FORMATTING,
            severity=Priority.LOW,
            message="first pass",
            file_path=str(source_file),
            line_number=1,
        )
        next_issue = Issue(
            type=IssueType.FORMATTING,
            severity=Priority.LOW,
            message="second pass",
            file_path=str(source_file),
            line_number=1,
        )

        first_plan = FixPlan(
            file_path=str(source_file),
            issue_type="FORMATTING",
            changes=[
                ChangeSpec(
                    line_range=(1, 1),
                    old_code="value = 1",
                    new_code="value = 2",
                    reason="first iteration",
                )
            ],
            rationale="first",
            risk_level="low",
            validated_by="test",
            issue_message="first pass",
            issue_stage="ruff-check",
        )
        second_plan = FixPlan(
            file_path=str(source_file),
            issue_type="FORMATTING",
            changes=[
                ChangeSpec(
                    line_range=(1, 1),
                    old_code="value = 2",
                    new_code="value = 3",
                    reason="second iteration",
                )
            ],
            rationale="second",
            risk_level="low",
            validated_by="test",
            issue_message="second pass",
            issue_stage="ruff-check",
        )

        plan_result = FixResult(
            success=True,
            confidence=1.0,
            fixes_applied=["applied"],
            files_modified=[str(source_file)],
        )

        with (
            patch.object(
                coordinator,
                "_collect_fixable_issues",
                return_value=[initial_issue],
            ),
            patch.object(coordinator, "_filter_fixable_issues", side_effect=lambda x: x),
            patch.object(
                coordinator,
                "_apply_type_tool_fix_prepasses",
                new_callable=AsyncMock,
                return_value={},
            ),
            patch.object(
                coordinator,
                "_apply_ruff_fix_prepasses",
                new_callable=AsyncMock,
                return_value={},
            ),
            patch.object(
                coordinator,
                "_apply_refurb_fix_prepasses",
                new_callable=AsyncMock,
                return_value={},
            ),
            patch.object(
                coordinator,
                "_apply_pycharm_hook_diagnostics_context",
                new_callable=AsyncMock,
                return_value=[initial_issue],
            ),
            patch.object(
                coordinator,
                "_apply_pycharm_reformat_prepass",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch.object(
                coordinator,
                "_execute_fast_fixes",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch.object(
                coordinator,
                "_collect_current_issues",
                side_effect=[[next_issue], [], []],
            ),
            patch.object(
                coordinator,
                "_create_fix_plans",
                new_callable=AsyncMock,
                side_effect=[[first_plan], [second_plan]],
            ) as mock_create_plans,
            patch.object(
                coordinator,
                "_execute_plans_with_validation",
                new_callable=AsyncMock,
                return_value=[plan_result],
            ) as mock_execute_plans,
            patch.object(
                coordinator,
                "_check_execution_results",
                return_value=True,
            ),
        ):
            result = await coordinator._apply_ai_agent_fixes_v2(
                [SimpleNamespace(name="ruff-check", status="failed")],
                stage="fast",
            )

        assert result is True
        assert mock_create_plans.await_count == 2
        assert mock_execute_plans.await_count == 2

    @pytest.mark.asyncio
    async def test_execute_single_plan_stops_when_target_is_not_writable(
        self, tmp_path: Path
    ) -> None:
        coordinator = AutofixCoordinator(pkg_path=tmp_path)
        plan = Mock()
        plan.file_path = str(tmp_path / "example.py")
        plan.changes = [Mock(line_range=(1, 1))]

        with (
            patch.object(coordinator, "_is_writable_target", return_value=False),
            patch.object(
                coordinator,
                "_execute_plan_with_validation",
                side_effect=AssertionError("should not run"),
            ),
            patch.object(
                coordinator,
                "_regenerate_plan_with_feedback",
                side_effect=AssertionError("should not retry"),
            ),
        ):
            result = await coordinator._execute_single_plan_with_retry(
                plan=plan,
                fixer_coordinator=Mock(),
                validation_coordinator=Mock(),
                analysis_coordinator=Mock(),
                plan_to_issue={},
                plan_key="example",
                bar=None,
            )

        assert result.success is False
        assert result.remaining_issues == [
            f"Workspace is not writable: {plan.file_path}"
        ]

    @patch("subprocess.run")
    def test_run_fix_command_invalid(self, mock_subprocess, coordinator) -> None:
        cmd = ["invalid", "command"]

        with patch.object(coordinator, "_validate_fix_command", return_value=False):
            result = coordinator._run_fix_command(cmd, "test")

            assert result is False
            mock_subprocess.assert_not_called()

    @patch("subprocess.run")
    def test_run_fix_command_exception(self, mock_subprocess, coordinator) -> None:
        cmd = ["uv", "run", "ruff", "format", "."]
        mock_subprocess.side_effect = Exception("Test error")

        with patch.object(coordinator, "_validate_fix_command", return_value=True):
            result = coordinator._run_fix_command(cmd, "test")

            assert result is False

    def test_handle_command_result_success(self, coordinator) -> None:
        result = Mock(returncode=0, stdout="", stderr="")

        handled = coordinator._handle_command_result(result, "test")

        assert handled is True

    def test_handle_command_result_successful_fix(self, coordinator) -> None:
        result = Mock(returncode=1, stdout="Fixed 5 files", stderr="")

        with patch.object(coordinator, "_is_successful_fix", return_value=True):
            handled = coordinator._handle_command_result(result, "test")

            assert handled is True

    def test_handle_command_result_failure(self, coordinator) -> None:
        result = Mock(returncode=1, stdout="", stderr="")

        with patch.object(coordinator, "_is_successful_fix", return_value=False):
            handled = coordinator._handle_command_result(result, "test")

            assert handled is False

    def test_handle_command_result_allows_partial_ruff_fix_pass(
        self, coordinator
    ) -> None:
        result = Mock(returncode=1, stdout="", stderr="")

        with patch.object(coordinator, "_is_successful_fix", return_value=False):
            handled = coordinator._handle_command_result(result, "fix code style")

            assert handled is True

    def test_is_successful_fix(self, coordinator) -> None:
        result = Mock(stdout="Fixed 3 files")
        assert coordinator._is_successful_fix(result) is True

        result = Mock(stdout="Reformatted code")
        assert coordinator._is_successful_fix(result) is True

        result = Mock(stdout="No changes made")
        assert coordinator._is_successful_fix(result) is False

    def test_check_tool_success_patterns(self, coordinator) -> None:
        assert coordinator._check_tool_success_patterns([], None) is False
        assert coordinator._check_tool_success_patterns(["uv"], None) is False

        cmd = ["uv", "run", "ruff"]
        result = Mock(returncode=0)
        assert coordinator._check_tool_success_patterns(cmd, result) is True

        cmd = ["uv", "run", "ruff"]
        assert coordinator._check_tool_success_patterns(cmd, "Fixed 5 files") is True
        assert (
            coordinator._check_tool_success_patterns(cmd, "would reformat 3 files")
            is True
        )

        cmd = ["uv", "run", "trailing-whitespace"]
        assert (
            coordinator._check_tool_success_patterns(cmd, "Fixing whitespace") is True
        )

    def test_validate_fix_command(self, coordinator) -> None:
        # Valid commands with allowed tools
        assert (
            coordinator._validate_fix_command(["uv", "run", "bandit", "-r", "."])
            is True
        )

        # Invalid commands
        assert coordinator._validate_fix_command([]) is False
        assert coordinator._validate_fix_command(["uv"]) is False
        assert coordinator._validate_fix_command(["python", "run", "ruff"]) is False
        assert coordinator._validate_fix_command(["uv", "run", "invalid_tool"]) is False
        # Ruff commands should now be allowed for deterministic autofix support
        assert (
            coordinator._validate_fix_command(["uv", "run", "ruff", "format"]) is True
        )

    def test_validate_hook_result(self, coordinator) -> None:
        valid_result = Mock()
        valid_result.name = "test_hook"
        valid_result.status = "failed"
        assert coordinator._validate_hook_result(valid_result) is True

        invalid_result1 = object()
        assert coordinator._validate_hook_result(invalid_result1) is False

        invalid_result2 = Mock()
        invalid_result2.name = ""
        invalid_result2.status = "failed"
        assert coordinator._validate_hook_result(invalid_result2) is False

        invalid_result3 = Mock()
        invalid_result3.name = "test"
        invalid_result3.status = "Invalid"
        assert coordinator._validate_hook_result(invalid_result3) is False

    def test_should_skip_autofix(self, coordinator) -> None:
        normal_result = Mock()
        normal_result.output = "Some normal output"
        normal_result.error = ""
        normal_result.error_message = ""
        assert coordinator._should_skip_autofix([normal_result]) is False

        import_error_result = Mock()
        import_error_result.output = "ModuleNotFoundError: No module named 'test'"
        import_error_result.error = ""
        import_error_result.error_message = ""
        assert coordinator._should_skip_autofix([import_error_result]) is True

        import_error_result2 = Mock()
        import_error_result2.output = "ImportError: cannot import name 'test'"
        import_error_result2.error = ""
        import_error_result2.error_message = ""
        assert coordinator._should_skip_autofix([import_error_result2]) is True

        no_output_result = Mock()
        no_output_result.output = None
        no_output_result.error = None
        no_output_result.error_message = None
        assert coordinator._should_skip_autofix([no_output_result]) is False


class TestAutofixCoordinatorIntegration:
    @pytest.fixture
    def coordinator(self):
        console = Mock(spec=Console)
        pkg_path = Path("/ test")
        return AutofixCoordinator(console=console, pkg_path=pkg_path)

    @pytest.mark.asyncio
    async def test_full_fast_workflow(self, coordinator) -> None:
        hook_results = []

        with (
            patch.object(
                coordinator,
                "_run_fix_command",
                return_value=True,
            ) as mock_run,
            patch.object(coordinator, "_should_skip_autofix", return_value=False),
        ):
            result = await coordinator.apply_autofix_for_hooks("fast", hook_results)

            assert result is True

            assert mock_run.call_count == 2

    @pytest.mark.asyncio
    async def test_full_comprehensive_workflow(self, coordinator) -> None:
        ruff_result = Mock()
        ruff_result.name = "ruff"
        ruff_result.status = "failed"
        ruff_result.output = "Some ruff error output"
        ruff_result.error = ""
        ruff_result.error_message = ""

        bandit_result = Mock()
        bandit_result.name = "bandit"
        bandit_result.status = "failed"
        bandit_result.output = "Some bandit error output"
        bandit_result.error = ""
        bandit_result.error_message = ""

        hook_results = [ruff_result, bandit_result]

        with (
            patch.object(
                coordinator,
                "_run_fix_command",
                return_value=True,
            ) as mock_run,
            patch.object(coordinator, "_should_skip_autofix", return_value=False),
        ):
            result = await coordinator.apply_autofix_for_hooks(
                "comprehensive", hook_results
            )

            assert result is True

            assert mock_run.call_count >= 2

    @pytest.mark.asyncio
    async def test_error_recovery(self, coordinator) -> None:
        hook_results = []

        with (
            patch.object(
                coordinator,
                "_run_fix_command",
                side_effect=Exception("Test error"),
            ),
            patch.object(coordinator, "_should_skip_autofix", return_value=False),
        ):
            result = await coordinator.apply_autofix_for_hooks("fast", hook_results)

            assert result is False

    @pytest.mark.asyncio
    async def test_v2_comprehensive_stage_runs_fast_fixes(self) -> None:
        """Bug 2: comprehensive stage must dispatch deterministic fast-fix.

        The test must NOT mock `_collect_fixable_issues` to return [] — the
        function has an early `if not issues: return True` at
        `autofix_coordinator.py:3269` that returns BEFORE the fast-fix branch
        is reached. Provide a real issue so the test drives the path under
        repair.
        """
        pkg_path = Path("/test/path")
        coordinator = AutofixCoordinator(console=Mock(spec=Console), pkg_path=pkg_path)
        real_issue = SimpleNamespace(
            file_path="x.py", line=1, message="m", issue_type="t"
        )

        with (
            patch.object(
                coordinator, "_collect_fixable_issues", return_value=[real_issue]
            ),
            patch.object(
                coordinator,
                "_apply_refurb_fix_prepasses",
                AsyncMock(return_value=False),
            ),
            patch.object(
                coordinator,
                "_execute_fast_fixes",
                new_callable=AsyncMock,
                return_value=True,
            ) as fast_fix,
            patch.object(
                coordinator,
                "_run_v2_ai_fix_iteration_loop",
                AsyncMock(return_value=True),
            ) as run_loop,
        ):
            result = await coordinator._apply_ai_agent_fixes_v2(
                hook_results=[
                    SimpleNamespace(name="refurb", status="failed", issues_count=20)
                ],
                stage="comprehensive",
            )

        assert result is True
        fast_fix.assert_called_once()
        run_loop.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_v2_comprehensive_stage_does_not_skip_fast_fix_log(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Bug 2 regression: the "Skipping" warning must not appear for comprehensive.

        The test must provide a non-empty `_collect_fixable_issues` return so it
        reaches the fast-fix branch — otherwise the bug is hidden by the
        `if not issues: return True` early-return at `autofix_coordinator.py:3269`.
        """
        pkg_path = Path("/test/path")
        coordinator = AutofixCoordinator(console=Mock(spec=Console), pkg_path=pkg_path)
        real_issue = SimpleNamespace(
            file_path="x.py", line=1, message="m", issue_type="t"
        )

        with caplog.at_level(20, logger="crackerjack.autofix"):
            with (
                patch.object(
                    coordinator, "_collect_fixable_issues", return_value=[real_issue]
                ),
                patch.object(
                    coordinator,
                    "_apply_refurb_fix_prepasses",
                    AsyncMock(return_value=False),
                ),
                patch.object(
                    coordinator,
                    "_execute_fast_fixes",
                    new_callable=AsyncMock,
                    return_value=True,
                ),
                patch.object(
                    coordinator,
                    "_run_v2_ai_fix_iteration_loop",
                    AsyncMock(return_value=True),
                ),
            ):
                await coordinator._apply_ai_agent_fixes_v2(
                    hook_results=[
                        SimpleNamespace(name="refurb", status="failed", issues_count=20)
                    ],
                    stage="comprehensive",
                )

        skip_message = "Skipping deterministic fast-fix pass for comprehensive AI analysis"
        assert skip_message not in caplog.text
        run_message = "Running deterministic fast-fix pass before"
        assert run_message in caplog.text

    @pytest.mark.asyncio
    async def test_v2_loop_passes_previous_fixes_to_completion_check(self) -> None:
        """Bug 4: _check_iteration_completion must receive the previous
        iteration's `fixes_applied`, not 0.

        The buggy code at `autofix_coordinator.py:3356` always passes
        `fixes_applied=0`, so the convergence check sees "no fixes ever
        applied" on every iteration, even after a successful first iteration.
        This test spies on `_check_iteration_completion` and asserts that
        BOTH the 2nd and 3rd calls receive the *previous* iteration's
        `fixes_applied` value — a regression that only affected iteration 2+
        would slip past a single-iteration assertion.

        The test must NOT mock `_create_fix_plans` to return `[]` — the loop
        has an early `if not plans: return False` at line 3372 that bypasses
        the convergence check entirely. Provide a non-empty plan and mock
        validation to return increasing fix counts per iteration so each
        completion-check call sees a different `fixes_applied` value.
        """
        pkg_path = Path("/test/path")
        coordinator = AutofixCoordinator(console=Mock(spec=Console), pkg_path=pkg_path)
        coordinator._max_iterations = 100  # never hit max
        coordinator._get_convergence_threshold = lambda: 100  # type: ignore[method-assign]  # never converge early
        plan = SimpleNamespace(plan_id="p", issues=[])

        # Each iteration produces a different fix count, so consecutive
        # completion-check calls see different previous_fixes_applied values.
        # iter 0 → 1 fix, iter 1 → 3 fixes, iter 2 → 5 fixes.
        fix_counts_per_iter = [
            [SimpleNamespace(fixes_applied=["f1"])],  # iter 0: sum = 1
            [SimpleNamespace(fixes_applied=["f1", "f2", "f3"])],  # iter 1: sum = 3
            [SimpleNamespace(fixes_applied=["f1", "f2", "f3", "f4", "f5"])],  # iter 2: sum = 5
        ]

        with (
            patch.object(
                coordinator,
                "_get_iteration_issues_with_log",
                return_value=[SimpleNamespace()] * 20,
            ),
            patch.object(
                coordinator, "_create_fix_plans", AsyncMock(return_value=[plan])
            ),
            patch.object(
                coordinator,
                "_execute_plans_with_validation",
                AsyncMock(side_effect=fix_counts_per_iter),
            ),
            patch.object(coordinator, "_check_execution_results", return_value=True),
            # 3 None → loop runs 3 iterations; 4th value False exits via
            # `_check_iteration_completion` returning a truthy result.
            patch.object(
                coordinator,
                "_check_iteration_completion",
                side_effect=[None, None, None, False],
            ) as check,
        ):
            await coordinator._run_v2_ai_fix_iteration_loop(
                analysis_coordinator=Mock(),
                fixer_coordinator=Mock(),
                validation_coordinator=Mock(),
                initial_issues=[SimpleNamespace()] * 20,
                hook_results=[],
                stage="comprehensive",
            )

        # Verify all 3 completion-check calls received the expected
        # previous-iteration fix count. Bug: literal 0 instead of the
        # threading value.
        assert len(check.call_args_list) == 4, (
            f"Expected 4 _check_iteration_completion calls (3 iters + 1 "
            f"exit), got {len(check.call_args_list)}"
        )
        expected_fixes = [0, 1, 3, 5]  # initial, iter 0, iter 1, iter 2
        for i, expected in enumerate(expected_fixes):
            actual = check.call_args_list[i].kwargs.get("fixes_applied")
            assert actual == expected, (
                f"call {i + 1}: expected fixes_applied={expected} (from "
                f"previous iteration), got {actual}. The buggy code passes "
                f"a literal 0 to _check_iteration_completion on every call."
            )

    @pytest.mark.asyncio
    async def test_v2_loop_passes_iteration_count_to_finish_session(self) -> None:
        """Bugs 3+4: every finish_session call must include iteration_count."""
        pkg_path = Path("/test/path")
        coordinator = AutofixCoordinator(console=Mock(spec=Console), pkg_path=pkg_path)
        coordinator._max_iterations = 100
        coordinator._get_convergence_threshold = lambda: 100  # type: ignore[method-assign]
        plan = SimpleNamespace(plan_id="p", issues=[])

        with (
            patch.object(
                coordinator,
                "_get_iteration_issues_with_log",
                return_value=[SimpleNamespace()] * 20,
            ),
            patch.object(
                coordinator, "_create_fix_plans", AsyncMock(return_value=[plan])
            ),
            patch.object(
                coordinator,
                "_execute_plans_with_validation",
                AsyncMock(return_value=[SimpleNamespace(fixes_applied=[])]),
            ),
            patch.object(coordinator, "_check_execution_results", return_value=True),
            patch.object(coordinator, "progress_manager") as pm,
            # Stop the loop after 2 iterations via a 2-call side-effect
            patch.object(
                coordinator,
                "_check_iteration_completion",
                side_effect=[None, False],
            ),
        ):
            await coordinator._run_v2_ai_fix_iteration_loop(
                analysis_coordinator=Mock(),
                fixer_coordinator=Mock(),
                validation_coordinator=Mock(),
                initial_issues=[SimpleNamespace()] * 20,
                hook_results=[],
                stage="comprehensive",
            )

        # Every finish_session call must include iteration_count
        finish_calls = pm.finish_session.call_args_list
        assert finish_calls, "finish_session was never called"
        for call in finish_calls:
            assert "iteration_count" in call.kwargs, (
                f"finish_session called without iteration_count: {call}"
            )
            assert call.kwargs["iteration_count"] is not None

    @pytest.mark.asyncio
    async def test_v2_loop_finish_session_on_no_plans_path(self) -> None:
        """Bug 3 coverage for the `if not plans: return False` path at
        `autofix_coordinator.py:3392`. This path's `finish_session` call could
        silently lose `iteration_count` without a test that exercises it.
        """
        pkg_path = Path("/test/path")
        coordinator = AutofixCoordinator(console=Mock(spec=Console), pkg_path=pkg_path)
        coordinator._max_iterations = 100
        coordinator._get_convergence_threshold = lambda: 100  # type: ignore[method-assign]

        with (
            patch.object(
                coordinator,
                "_get_iteration_issues_with_log",
                return_value=[SimpleNamespace()] * 5,
            ),
            # Empty plans list → triggers the `if not plans` early return.
            patch.object(
                coordinator, "_create_fix_plans", AsyncMock(return_value=[])
            ),
            patch.object(coordinator, "progress_manager") as pm,
        ):
            result = await coordinator._run_v2_ai_fix_iteration_loop(
                analysis_coordinator=Mock(),
                fixer_coordinator=Mock(),
                validation_coordinator=Mock(),
                initial_issues=[SimpleNamespace()] * 5,
                hook_results=[],
                stage="comprehensive",
            )

        assert result is False
        finish_calls = pm.finish_session.call_args_list
        assert len(finish_calls) == 1
        call = finish_calls[0]
        assert call.kwargs.get("success") is False
        assert call.kwargs.get("iteration_count") == 0, (
            f"`if not plans` path must pass iteration_count; got {call.kwargs}"
        )

    @pytest.mark.asyncio
    async def test_v2_loop_finish_session_on_no_fixes_applied_path(self) -> None:
        """Bug 3 coverage for the `if fixes_applied == 0: return False` path
        at `autofix_coordinator.py:3425`. This path's `finish_session` call
        could silently lose `iteration_count` without a test that exercises it.
        """
        pkg_path = Path("/test/path")
        coordinator = AutofixCoordinator(console=Mock(spec=Console), pkg_path=pkg_path)
        coordinator._max_iterations = 100
        coordinator._get_convergence_threshold = lambda: 100  # type: ignore[method-assign]
        plan = SimpleNamespace(plan_id="p", issues=[])

        with (
            patch.object(
                coordinator,
                "_get_iteration_issues_with_log",
                return_value=[SimpleNamespace()] * 5,
            ),
            patch.object(
                coordinator, "_create_fix_plans", AsyncMock(return_value=[plan])
            ),
            # Empty fixes_applied list → sum is 0 → triggers the
            # `if fixes_applied == 0` early return.
            patch.object(
                coordinator,
                "_execute_plans_with_validation",
                AsyncMock(return_value=[SimpleNamespace(fixes_applied=[])]),
            ),
            # _check_execution_results returns False so the
            # `if not self._check_execution_results(results):` block is entered.
            patch.object(coordinator, "_check_execution_results", return_value=False),
            patch.object(coordinator, "progress_manager") as pm,
        ):
            result = await coordinator._run_v2_ai_fix_iteration_loop(
                analysis_coordinator=Mock(),
                fixer_coordinator=Mock(),
                validation_coordinator=Mock(),
                initial_issues=[SimpleNamespace()] * 5,
                hook_results=[],
                stage="comprehensive",
            )

        assert result is False
        finish_calls = pm.finish_session.call_args_list
        assert len(finish_calls) == 1
        call = finish_calls[0]
        assert call.kwargs.get("success") is False
        assert call.kwargs.get("iteration_count") == 0, (
            f"`if fixes_applied == 0` path must pass iteration_count; got {call.kwargs}"
        )

    @pytest.mark.asyncio
    async def test_v2_loop_bug2_branches_have_equivalent_observable_behavior(
        self,
    ) -> None:
        """Bug 2 (M3 refactor) — the v2 dispatcher's two near-identical
        early-exit branches (`if not plans: return False` at line 3392 and
        `if fixes_applied == 0: return False` at line 3425) duplicate the
        same dispatch pattern: `end_iteration`, `finish_session(success=False,
        iteration_count=iteration)`, `emit RunFinished(success=False, ...)`,
        `return False`. The only difference is that the second branch runs
        after the bookkeeping (fixes_applied / no_progress_count) and the
        first runs immediately. This test exercises BOTH branches and
        asserts they produce equivalent observable behavior — proving the
        duplicated dispatch is safe to collapse into a single helper.
        """
        pkg_path = Path("/test/path")

        # --- Branch A: `if not plans: return False` path (immediate exit) ---
        coordinator_a = AutofixCoordinator(console=Mock(spec=Console), pkg_path=pkg_path)
        coordinator_a._max_iterations = 100
        coordinator_a._get_convergence_threshold = lambda: 100  # type: ignore[method-assign]

        with (
            patch.object(
                coordinator_a,
                "_get_iteration_issues_with_log",
                return_value=[SimpleNamespace()] * 5,
            ),
            # Empty plans list triggers the `if not plans` early return.
            patch.object(
                coordinator_a, "_create_fix_plans", AsyncMock(return_value=[])
            ),
            patch.object(coordinator_a, "progress_manager") as pm_a,
        ):
            result_a = await coordinator_a._run_v2_ai_fix_iteration_loop(
                analysis_coordinator=Mock(),
                fixer_coordinator=Mock(),
                validation_coordinator=Mock(),
                initial_issues=[SimpleNamespace()] * 5,
                hook_results=[],
                stage="comprehensive",
            )

        # --- Branch B: `if fixes_applied == 0: return False` path (post-bookkeeping) ---
        coordinator_b = AutofixCoordinator(console=Mock(spec=Console), pkg_path=pkg_path)
        coordinator_b._max_iterations = 100
        coordinator_b._get_convergence_threshold = lambda: 100  # type: ignore[method-assign]
        plan_b = SimpleNamespace(plan_id="p", issues=[])

        with (
            patch.object(
                coordinator_b,
                "_get_iteration_issues_with_log",
                return_value=[SimpleNamespace()] * 5,
            ),
            patch.object(
                coordinator_b, "_create_fix_plans", AsyncMock(return_value=[plan_b])
            ),
            # Empty fixes_applied list → sum is 0 → triggers
            # `if fixes_applied == 0` early return.
            patch.object(
                coordinator_b,
                "_execute_plans_with_validation",
                AsyncMock(return_value=[SimpleNamespace(fixes_applied=[])]),
            ),
            # _check_execution_results returns False so the
            # `if not self._check_execution_results(results):` block is entered.
            patch.object(coordinator_b, "_check_execution_results", return_value=False),
            patch.object(coordinator_b, "progress_manager") as pm_b,
        ):
            result_b = await coordinator_b._run_v2_ai_fix_iteration_loop(
                analysis_coordinator=Mock(),
                fixer_coordinator=Mock(),
                validation_coordinator=Mock(),
                initial_issues=[SimpleNamespace()] * 5,
                hook_results=[],
                stage="comprehensive",
            )

        # --- Equivalence assertions ---
        # 1. Both branches must return False (identical return value).
        assert result_a is False
        assert result_b is False
        assert result_a == result_b, (
            f"return values differ between branches: A={result_a!r} B={result_b!r}"
        )

        # 2. Both branches must call finish_session exactly once.
        finish_a = pm_a.finish_session.call_args_list
        finish_b = pm_b.finish_session.call_args_list
        assert len(finish_a) == 1, (
            f"`if not plans` branch must call finish_session once, got {len(finish_a)}"
        )
        assert len(finish_b) == 1, (
            f"`if fixes_applied == 0` branch must call finish_session once, "
            f"got {len(finish_b)}"
        )

        # 3. Both branches must call finish_session with the SAME kwargs
        #    (this is the equivalence claim that justifies the refactor).
        assert finish_a[0].kwargs == finish_b[0].kwargs, (
            f"finish_session kwargs differ between branches — branches are NOT "
            f"equivalent and the refactor is unsafe:\n"
            f"  no_plans:       {finish_a[0].kwargs}\n"
            f"  no_fixes:       {finish_b[0].kwargs}"
        )

        # 4. The shared kwargs must be the documented exit contract:
        #    success=False, iteration_count=0 (we run 0 iterations in both
        #    scenarios because the early-exit fires on iteration 0).
        assert finish_a[0].kwargs.get("success") is False
        assert finish_a[0].kwargs.get("iteration_count") == 0

    def test_v1_loop_does_not_crash_with_unbound_previous_fixes_applied(
        self,
    ) -> None:
        """Regression: commit f3fc38a6 added `fixes_applied=previous_fixes_applied`
        to the v1 loop's _check_iteration_completion call but never initialized
        the variable, so any v1 invocation would raise UnboundLocalError on
        iteration 0. The fix is `previous_fixes_applied = 0` in the locals
        block.

        This test calls the v1 loop with `_check_iteration_completion` set to
        return `True` on the first call so the loop exits immediately after
        the convergence check. If the variable is uninitialized, the call to
        `_check_iteration_completion` raises before returning.
        """
        pkg_path = Path("/test/path")
        coordinator = AutofixCoordinator(console=Mock(spec=Console), pkg_path=pkg_path)
        coordinator._max_iterations = 100  # never hit max
        coordinator._get_convergence_threshold = lambda: 100  # type: ignore[method-assign]  # never converge early

        with (
            patch.object(coordinator, "_event_bus"),
            patch.object(
                coordinator,
                "_get_iteration_issues_with_log",
                return_value=[SimpleNamespace()] * 20,
            ),
            patch.object(
                coordinator,
                "_check_iteration_completion",
                return_value=True,
            ) as check,
        ):
            result = coordinator._run_ai_fix_iteration_loop(
                coordinator=Mock(),
                initial_issues=[SimpleNamespace()] * 20,
                hook_results=[],
                stage="comprehensive",
            )

        assert result is True
        check.assert_called_once()
        # fixes_applied must be present and equal to the initial value (0).
        assert check.call_args.kwargs.get("fixes_applied") == 0, (
            "v1 loop must initialize previous_fixes_applied=0 and pass it to "
            "_check_iteration_completion; missing init raises UnboundLocalError."
        )

    def test_v1_loop_passes_previous_fixes_to_completion_check(self) -> None:
        """Bug 4 (v1 parity): second iteration's _check_iteration_completion
        call must receive the first iteration's fixes_applied, not 0.

        Mirrors `test_v2_loop_passes_previous_fixes_to_completion_check` for
        the v1 pipeline so future refactors that touch one loop and not the
        other are caught.
        """
        pkg_path = Path("/test/path")
        coordinator = AutofixCoordinator(console=Mock(spec=Console), pkg_path=pkg_path)
        coordinator._max_iterations = 100
        coordinator._get_convergence_threshold = lambda: 100  # type: ignore[method-assign]

        with (
            patch.object(coordinator, "_event_bus"),
            patch.object(
                coordinator,
                "_get_iteration_issues_with_log",
                return_value=[SimpleNamespace()] * 20,
            ),
            patch.object(
                coordinator, "_run_ai_fix_iteration", return_value=(True, 3)
            ),
            patch.object(
                coordinator,
                "_update_iteration_progress_with_tracking",
                return_value=0,
            ),
            patch.object(
                coordinator,
                "_check_iteration_completion",
                side_effect=[None, True],
            ) as check,
        ):
            result = coordinator._run_ai_fix_iteration_loop(
                coordinator=Mock(),
                initial_issues=[SimpleNamespace()] * 20,
                hook_results=[],
                stage="comprehensive",
            )

        assert result is True
        assert len(check.call_args_list) >= 2
        # First call receives the initial 0; second call must receive the
        # first iteration's fixes_applied (3), proving the v1 loop threads
        # previous_fixes_applied through.
        assert check.call_args_list[0].kwargs.get("fixes_applied") == 0
        assert check.call_args_list[1].kwargs.get("fixes_applied") == 3, (
            "v1 loop must update previous_fixes_applied=fixes_applied after "
            "each iteration; second call to _check_iteration_completion "
            "should see fixes_applied=3, not 0."
        )

    def test_v1_loop_passes_iteration_count_to_finish_session(self) -> None:
        """Bug 3 (v1 parity): every finish_session call in the v1 loop must
        include iteration_count. Without it, the footer reports
        len(issue_history) instead of the actual iteration count.
        """
        pkg_path = Path("/test/path")
        coordinator = AutofixCoordinator(console=Mock(spec=Console), pkg_path=pkg_path)
        coordinator._max_iterations = 100
        coordinator._get_convergence_threshold = lambda: 100  # type: ignore[method-assign]

        with (
            patch.object(coordinator, "_event_bus"),
            patch.object(
                coordinator,
                "_get_iteration_issues_with_log",
                return_value=[SimpleNamespace()] * 20,
            ),
            patch.object(
                coordinator, "_run_ai_fix_iteration", return_value=(True, 3)
            ),
            patch.object(
                coordinator,
                "_update_iteration_progress_with_tracking",
                return_value=0,
            ),
            patch.object(
                coordinator,
                "_check_iteration_completion",
                side_effect=[None, True],
            ),
            patch.object(coordinator, "progress_manager") as pm,
        ):
            result = coordinator._run_ai_fix_iteration_loop(
                coordinator=Mock(),
                initial_issues=[SimpleNamespace()] * 20,
                hook_results=[],
                stage="comprehensive",
            )

        assert result is True
        finish_calls = pm.finish_session.call_args_list
        assert finish_calls, "finish_session was never called"
        for call in finish_calls:
            assert "iteration_count" in call.kwargs, (
                f"v1 finish_session called without iteration_count: {call}"
            )
            assert call.kwargs["iteration_count"] is not None

    def test_v1_loop_finish_session_on_not_success_path(self) -> None:
        """Bug 3 (v1 parity) coverage for the v1 not-success early-return at
        `autofix_coordinator.py:2736-2740`. Mirrors
        test_v2_loop_finish_session_on_no_fixes_applied_path for the v1
        loop. When `_run_ai_fix_iteration` returns `(False, ...)`, the v1
        loop calls `finish_session(success=False, iteration_count=iteration)`
        — this test guards that the `iteration_count` kwarg is present.
        """
        pkg_path = Path("/test/path")
        coordinator = AutofixCoordinator(console=Mock(spec=Console), pkg_path=pkg_path)
        coordinator._max_iterations = 100
        coordinator._get_convergence_threshold = lambda: 100  # type: ignore[method-assign]

        with (
            patch.object(coordinator, "_event_bus"),
            patch.object(
                coordinator,
                "_get_iteration_issues_with_log",
                return_value=[SimpleNamespace()] * 5,
            ),
            # None on first call → loop body runs; True would have exited
            # via the completion-check path (covered by other tests).
            patch.object(
                coordinator,
                "_check_iteration_completion",
                return_value=None,
            ),
            # (False, 0) → success=False → v1 not-success early-return fires.
            patch.object(
                coordinator, "_run_ai_fix_iteration", return_value=(False, 0)
            ),
            patch.object(
                coordinator,
                "_update_iteration_progress_with_tracking",
                return_value=0,
            ),
            patch.object(coordinator, "progress_manager") as pm,
        ):
            result = coordinator._run_ai_fix_iteration_loop(
                coordinator=Mock(),
                initial_issues=[SimpleNamespace()] * 5,
                hook_results=[],
                stage="comprehensive",
            )

        assert result is False
        finish_calls = pm.finish_session.call_args_list
        assert len(finish_calls) == 1
        call = finish_calls[0]
        assert call.kwargs.get("success") is False
        assert call.kwargs.get("iteration_count") == 0, (
            f"v1 not-success path must pass iteration_count; got {call.kwargs}"
        )

    def test_v1_loop_finish_session_on_exception_path(self) -> None:
        """Bug 3 (v1 parity) coverage for the v1 except block at
        `autofix_coordinator.py:2765-2773`. When an exception is raised
        inside the v1 loop body, the except handler calls
        `finish_session(success=False, message=..., iteration_count=iteration)`
        and re-raises. This test guards that the `iteration_count` kwarg is
        present AND the exception propagates.
        """
        pkg_path = Path("/test/path")
        coordinator = AutofixCoordinator(console=Mock(spec=Console), pkg_path=pkg_path)
        coordinator._max_iterations = 100
        coordinator._get_convergence_threshold = lambda: 100  # type: ignore[method-assign]

        boom = RuntimeError("simulated v1 loop failure")

        with (
            patch.object(coordinator, "_event_bus"),
            patch.object(
                coordinator,
                "_get_iteration_issues_with_log",
                return_value=[SimpleNamespace()] * 5,
            ),
            # _check_iteration_completion raises → except block runs.
            patch.object(
                coordinator,
                "_check_iteration_completion",
                side_effect=boom,
            ),
            patch.object(coordinator, "progress_manager") as pm,
        ):
            with pytest.raises(RuntimeError, match="simulated v1 loop failure"):
                coordinator._run_ai_fix_iteration_loop(
                    coordinator=Mock(),
                    initial_issues=[SimpleNamespace()] * 5,
                    hook_results=[],
                    stage="comprehensive",
                )

        # Except block must have called finish_session with iteration_count
        # BEFORE re-raising.
        finish_calls = pm.finish_session.call_args_list
        assert len(finish_calls) == 1
        call = finish_calls[0]
        assert call.kwargs.get("success") is False
        assert call.kwargs.get("iteration_count") == 0, (
            f"v1 except path must pass iteration_count; got {call.kwargs}"
        )
        assert "simulated v1 loop failure" in call.kwargs.get("message", "")
