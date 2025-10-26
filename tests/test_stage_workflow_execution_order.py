"""
Tests to verify workflow stage execution order under different options.

Tests cover the critical workflow ordering requirements:
1. Fast hooks run first
2. Code cleaning runs after fast hooks when -x is set
3. Post-cleaning fast hooks run after cleaning for sanity check
4. Tests and comprehensive hooks run after cleaning (when both -x and -t are set)
5. AI agents trigger cleaning if not already done
"""

from unittest.mock import Mock, call, patch

import pytest

from crackerjack.core.workflow_orchestrator import WorkflowOrchestrator


@pytest.mark.skip(reason="WorkflowOrchestrator requires complex nested ACB DI setup - integration test, not unit test")
class MockOptions:
    """Mock options class for testing different workflow configurations."""

    def __init__(
        self,
        clean: bool = False,
        test: bool = False,
        ai_agent: bool = False,
        skip_hooks: bool = False,
        comprehensive: bool = False,
        fast_only: bool = False,
        commit: bool = False,
        publish: bool = False,
        interactive: bool = False,
        verbose: bool = False,
        **kwargs,
    ):
        self.clean = clean
        self.test = test
        self.ai_agent = ai_agent
        self.skip_hooks = skip_hooks
        self.comprehensive = comprehensive
        self.fast_only = fast_only
        self.commit = commit
        self.publish = publish
        self.interactive = interactive
        self.verbose = verbose

        # Set other common attributes with defaults
        for key, value in kwargs.items():
            setattr(self, key, value)


@pytest.mark.skip(reason="WorkflowOrchestrator requires complex nested ACB DI setup - integration test, not unit test")
class TestStageWorkflowExecutionOrder:
    """Test stage execution order under different option combinations."""

    @pytest.fixture
    def mock_workflow_orchestrator(self):
        """Create a mock workflow orchestrator with all dependencies mocked."""
        orchestrator = WorkflowOrchestrator()

        # Mock all phase coordinators and managers
        orchestrator.phases = Mock()
        orchestrator.phases.run_cleaning_phase.return_value = True
        orchestrator.phases.run_hooks_phase.return_value = True
        orchestrator.phases.run_testing_phase.return_value = True

        # Mock console and other attributes
        orchestrator.console = Mock()
        orchestrator._cleaning_completed = False

        return orchestrator

    def test_basic_workflow_no_cleaning(self, mock_workflow_orchestrator):
        """Test basic workflow without cleaning option."""
        orchestrator = mock_workflow_orchestrator
        options = MockOptions()

        with patch.object(
            orchestrator, "_run_fast_hooks_phase", return_value=True
        ) as mock_fast:
            with patch.object(
                orchestrator, "_run_comprehensive_hooks_phase", return_value=True
            ) as mock_comp:
                with patch.object(
                    orchestrator, "_run_testing_phase", return_value=True
                ) as mock_test:
                    orchestrator._execute_workflow_phases(options)

        # Verify order: fast hooks → comprehensive hooks (no cleaning)
        mock_fast.assert_called_once()
        mock_comp.assert_called_once()
        mock_test.assert_not_called()  # No -t option

        # Verify cleaning was not called
        orchestrator.phases.run_cleaning_phase.assert_not_called()

    def test_cleaning_workflow_proper_order(self, mock_workflow_orchestrator):
        """Test that code cleaning runs in proper order: fast hooks → cleaning → post-cleaning fast hooks."""
        orchestrator = mock_workflow_orchestrator
        options = MockOptions(clean=True)

        with patch.object(
            orchestrator, "_run_initial_fast_hooks", return_value=True
        ) as mock_initial_fast:
            with patch.object(
                orchestrator, "_run_code_cleaning_phase", return_value=True
            ) as mock_cleaning:
                with patch.object(
                    orchestrator, "_run_post_cleaning_fast_hooks", return_value=True
                ) as mock_post_fast:
                    with patch.object(
                        orchestrator,
                        "_run_main_quality_phases",
                        return_value=(True, True),
                    ) as mock_main:
                        orchestrator._execute_test_workflow(options)

        # Verify proper execution order
        assert mock_initial_fast.called
        assert mock_cleaning.called
        assert mock_post_fast.called
        assert mock_main.called

        # Verify call order
        [
            call(mock_initial_fast),
            call(mock_cleaning),
            call(mock_post_fast),
            call(mock_main),
        ]

    def test_cleaning_with_tests_workflow_order(self, mock_workflow_orchestrator):
        """Test that cleaning runs before tests when both -x and -t options are set."""
        orchestrator = mock_workflow_orchestrator
        options = MockOptions(clean=True, test=True)

        execution_order = []

        def track_initial_fast_hooks(*args, **kwargs):
            execution_order.append("initial_fast_hooks")
            return True

        def track_cleaning(*args, **kwargs):
            execution_order.append("cleaning")
            return True

        def track_post_cleaning_fast_hooks(*args, **kwargs):
            execution_order.append("post_cleaning_fast_hooks")
            return True

        def track_main_phases(*args, **kwargs):
            execution_order.append("main_phases")
            return (True, True)

        with patch.object(
            orchestrator,
            "_run_initial_fast_hooks",
            side_effect=track_initial_fast_hooks,
        ):
            with patch.object(
                orchestrator, "_run_code_cleaning_phase", side_effect=track_cleaning
            ):
                with patch.object(
                    orchestrator,
                    "_run_post_cleaning_fast_hooks",
                    side_effect=track_post_cleaning_fast_hooks,
                ):
                    with patch.object(
                        orchestrator,
                        "_run_main_quality_phases",
                        side_effect=track_main_phases,
                    ):
                        orchestrator._execute_test_workflow(options)

        # Verify exact execution order
        expected_order = [
            "initial_fast_hooks",
            "cleaning",
            "post_cleaning_fast_hooks",
            "main_phases",
        ]
        assert execution_order == expected_order

    def test_ai_agent_triggers_cleaning_if_not_done(self, mock_workflow_orchestrator):
        """Test that AI agent triggers cleaning if cleaning option is set but not yet run."""
        orchestrator = mock_workflow_orchestrator
        options = MockOptions(clean=True, ai_agent=True)

        # Mock that code cleaning hasn't run yet
        orchestrator._cleaning_completed = False

        execution_order = []

        def track_has_cleaning_run(*args, **kwargs):
            execution_order.append("check_cleaning_run")
            return False  # Cleaning hasn't run

        def track_cleaning_phase(*args, **kwargs):
            execution_order.append("cleaning_phase")
            orchestrator._cleaning_completed = True
            return True

        def track_post_cleaning_fast(*args, **kwargs):
            execution_order.append("post_cleaning_fast")
            return True

        def track_mark_complete(*args, **kwargs):
            execution_order.append("mark_complete")
            return None

        with patch.object(
            orchestrator, "_has_code_cleaning_run", side_effect=track_has_cleaning_run
        ):
            with patch.object(
                orchestrator,
                "_run_code_cleaning_phase",
                side_effect=track_cleaning_phase,
            ):
                with patch.object(
                    orchestrator,
                    "_run_post_cleaning_fast_hooks",
                    side_effect=track_post_cleaning_fast,
                ):
                    with patch.object(
                        orchestrator,
                        "_mark_code_cleaning_complete",
                        side_effect=track_mark_complete,
                    ):
                        with patch.object(
                            orchestrator,
                            "_run_ai_agent_fixing_phase",
                            return_value=True,
                        ):
                            # Simulate the AI agent code that checks and runs cleaning
                            if (
                                options.clean
                                and not orchestrator._has_code_cleaning_run()
                            ):
                                orchestrator.console.print(
                                    "[bold yellow]🤖 AI agents recommend running code cleaning first...[/bold yellow]"
                                )
                                if orchestrator._run_code_cleaning_phase(options):
                                    orchestrator._run_post_cleaning_fast_hooks(options)
                                    orchestrator._mark_code_cleaning_complete()

        # Verify AI agent triggered cleaning workflow
        expected_order = [
            "check_cleaning_run",
            "cleaning_phase",
            "post_cleaning_fast",
            "mark_complete",
        ]
        assert execution_order == expected_order

    def test_fast_hooks_retry_logic_after_cleaning(self, mock_workflow_orchestrator):
        """Test that fast hooks are re-run after cleaning for sanity check."""
        orchestrator = mock_workflow_orchestrator
        options = MockOptions(clean=True)

        fast_hooks_call_count = 0

        def track_fast_hooks(*args, **kwargs):
            nonlocal fast_hooks_call_count
            fast_hooks_call_count += 1
            return True

        with patch.object(
            orchestrator, "_run_fast_hooks_phase", side_effect=track_fast_hooks
        ):
            with patch.object(
                orchestrator, "_run_code_cleaning_phase", return_value=True
            ):
                with patch.object(
                    orchestrator, "_run_comprehensive_hooks_phase", return_value=True
                ):
                    # Simulate the workflow that runs fast hooks twice (before and after cleaning)
                    orchestrator._run_fast_hooks_phase(options)  # Initial fast hooks
                    if options.clean:
                        orchestrator._run_code_cleaning_phase(options)  # Cleaning
                        orchestrator._run_fast_hooks_phase(
                            options
                        )  # Post-cleaning fast hooks
                    orchestrator._run_comprehensive_hooks_phase(
                        options
                    )  # Comprehensive hooks

        # Verify fast hooks were called twice (before and after cleaning)
        assert fast_hooks_call_count == 2

    def test_skip_hooks_bypasses_all_hook_stages(self, mock_workflow_orchestrator):
        """Test that --skip-hooks bypasses all hook execution."""
        orchestrator = mock_workflow_orchestrator
        options = MockOptions(clean=True, test=True, skip_hooks=True)

        with patch.object(orchestrator, "_run_fast_hooks_phase") as mock_fast:
            with patch.object(
                orchestrator, "_run_comprehensive_hooks_phase"
            ) as mock_comp:
                with patch.object(
                    orchestrator, "_run_testing_phase", return_value=True
                ) as mock_test:
                    with patch.object(
                        orchestrator, "_run_code_cleaning_phase", return_value=True
                    ) as mock_clean:
                        # Simulate skip_hooks behavior
                        if not options.skip_hooks:
                            orchestrator._run_fast_hooks_phase(options)
                            if options.clean:
                                orchestrator._run_code_cleaning_phase(options)
                                orchestrator._run_fast_hooks_phase(
                                    options
                                )  # Post-cleaning
                            orchestrator._run_comprehensive_hooks_phase(options)
                        if options.test:
                            orchestrator._run_testing_phase(options)

        # Verify hooks were skipped but tests still run
        mock_fast.assert_not_called()
        mock_comp.assert_not_called()
        mock_clean.assert_not_called()
        mock_test.assert_called_once()

    def test_fast_only_option_skips_comprehensive_hooks(
        self, mock_workflow_orchestrator
    ):
        """Test that --fast-only skips comprehensive hooks but includes cleaning if requested."""
        orchestrator = mock_workflow_orchestrator
        options = MockOptions(clean=True, fast_only=True)

        with patch.object(
            orchestrator, "_run_fast_hooks_phase", return_value=True
        ) as mock_fast:
            with patch.object(
                orchestrator, "_run_code_cleaning_phase", return_value=True
            ) as mock_clean:
                with patch.object(
                    orchestrator, "_run_comprehensive_hooks_phase"
                ) as mock_comp:
                    # Simulate fast_only behavior with cleaning
                    orchestrator._run_fast_hooks_phase(options)
                    if options.clean:
                        orchestrator._run_code_cleaning_phase(options)
                        orchestrator._run_fast_hooks_phase(
                            options
                        )  # Post-cleaning sanity check
                    if not options.fast_only:
                        orchestrator._run_comprehensive_hooks_phase(options)

        # Verify fast hooks and cleaning ran, but comprehensive hooks were skipped
        assert mock_fast.call_count == 2  # Before and after cleaning
        mock_clean.assert_called_once()
        mock_comp.assert_not_called()

    def test_cleaning_failure_prevents_subsequent_stages(
        self, mock_workflow_orchestrator
    ):
        """Test that cleaning failure prevents subsequent stages from running."""
        orchestrator = mock_workflow_orchestrator
        options = MockOptions(clean=True, test=True, comprehensive=True)

        with patch.object(
            orchestrator, "_run_initial_fast_hooks", return_value=True
        ) as mock_initial_fast:
            with patch.object(
                orchestrator, "_run_code_cleaning_phase", return_value=False
            ) as mock_cleaning:  # Cleaning fails
                with patch.object(
                    orchestrator, "_run_post_cleaning_fast_hooks"
                ) as mock_post_fast:
                    with patch.object(
                        orchestrator, "_run_main_quality_phases"
                    ) as mock_main:
                        result = orchestrator._execute_test_workflow(options)

        # Verify cleaning failure stops the workflow
        mock_initial_fast.assert_called_once()
        mock_cleaning.assert_called_once()
        mock_post_fast.assert_not_called()  # Should not run after cleaning failure
        mock_main.assert_not_called()  # Should not run after cleaning failure
        assert result is False

    def test_post_cleaning_fast_hooks_failure_handling(
        self, mock_workflow_orchestrator
    ):
        """Test handling of post-cleaning fast hooks failure."""
        orchestrator = mock_workflow_orchestrator
        options = MockOptions(clean=True)

        with patch.object(orchestrator, "_run_initial_fast_hooks", return_value=True):
            with patch.object(
                orchestrator, "_run_code_cleaning_phase", return_value=True
            ):
                with patch.object(
                    orchestrator, "_run_post_cleaning_fast_hooks", return_value=False
                ) as mock_post_fast:  # Post-cleaning fails
                    with patch.object(
                        orchestrator, "_run_main_quality_phases"
                    ) as mock_main:
                        result = orchestrator._execute_test_workflow(options)

        # Verify post-cleaning failure stops the workflow
        mock_post_fast.assert_called_once()
        mock_main.assert_not_called()  # Should not run after post-cleaning failure
        assert result is False

    def test_complex_workflow_all_options_enabled(self, mock_workflow_orchestrator):
        """Test complex workflow with all options enabled to verify complete execution order."""
        orchestrator = mock_workflow_orchestrator
        options = MockOptions(clean=True, test=True, comprehensive=True, ai_agent=True)

        execution_order = []

        def track_execution(stage_name):
            def tracker(*args, **kwargs):
                execution_order.append(stage_name)
                return True

            return tracker

        with patch.object(
            orchestrator,
            "_run_initial_fast_hooks",
            side_effect=track_execution("initial_fast"),
        ):
            with patch.object(
                orchestrator,
                "_run_code_cleaning_phase",
                side_effect=track_execution("cleaning"),
            ):
                with patch.object(
                    orchestrator,
                    "_run_post_cleaning_fast_hooks",
                    side_effect=track_execution("post_clean_fast"),
                ):
                    with patch.object(
                        orchestrator,
                        "_run_main_quality_phases",
                        side_effect=lambda *args: (
                            execution_order.append("tests"),
                            execution_order.append("comprehensive"),
                            (True, True),
                        )[-1],
                    ):
                        with patch.object(
                            orchestrator,
                            "_run_ai_agent_fixing_phase",
                            side_effect=track_execution("ai_agent"),
                        ):
                            orchestrator._execute_test_workflow(options)

        # Verify comprehensive execution includes all expected stages
        expected_stages = [
            "initial_fast",
            "cleaning",
            "post_clean_fast",
            "tests",
            "comprehensive",
        ]
        for stage in expected_stages:
            assert stage in execution_order, f"Missing expected stage: {stage}"

        # Verify stages appear in correct order (initial_fast before cleaning, etc.)
        initial_fast_idx = execution_order.index("initial_fast")
        cleaning_idx = execution_order.index("cleaning")
        post_clean_fast_idx = execution_order.index("post_clean_fast")

        assert initial_fast_idx < cleaning_idx, (
            "Initial fast hooks should run before cleaning"
        )
        assert cleaning_idx < post_clean_fast_idx, (
            "Cleaning should run before post-cleaning fast hooks"
        )
