"""Integration tests for security-hardened workflow orchestrator."""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from rich.console import Console

from crackerjack.core.workflow_orchestrator import WorkflowPipeline


class MockOptions:
    """Mock options for testing."""

    def __init__(self, **kwargs):
        # Default values
        self.publish = kwargs.get("publish", False)
        self.all = kwargs.get("all", False)
        self.commit = kwargs.get("commit", False)
        self.test = kwargs.get("test", False)
        self.ai_agent = kwargs.get("ai_agent", False)
        self.verbose = kwargs.get("verbose", False)

        # Add any other attributes passed in
        for key, value in kwargs.items():
            setattr(self, key, value)


class MockSessionTracker:
    """Mock session tracker for testing."""

    def __init__(self):
        self.tasks = {}


class MockSession:
    """Mock session coordinator for testing."""

    def __init__(self):
        self.session_tracker = MockSessionTracker()

    def track_task(self, task_id, task_name):
        pass

    def fail_task(self, task_id, error):
        pass

    def complete_task(self, task_id, details=None):
        pass


class MockPhases:
    """Mock phase coordinator for testing."""

    def __init__(self):
        self.hook_manager = Mock()

    def run_testing_phase(self, options):
        return True

    def run_comprehensive_hooks_only(self, options):
        return True


class TestSecurityIntegration:
    """Test security integration in workflow orchestrator."""

    def test_security_critical_failure_blocks_publishing_standard_workflow(self):
        """Test that security-critical failures block publishing in standard workflow."""
        console = Console()
        pkg_path = Path.cwd()
        session = MockSession()
        phases = MockPhases()

        pipeline = WorkflowPipeline(console, pkg_path, session, phases)

        # Mock security check to return critical failures
        with patch.object(
            pipeline, "_check_security_critical_failures", return_value=True
        ):
            options = MockOptions(publish="patch")

            result = pipeline._handle_standard_workflow(
                options, 1, testing_passed=True, comprehensive_passed=True
            )

            # Should fail even though tests and hooks passed due to security gate
            assert not result

    def test_security_passes_allows_publishing_with_partial_success(self):
        """Test that passing security allows publishing with partial success."""
        console = Console()
        pkg_path = Path.cwd()
        session = MockSession()
        phases = MockPhases()

        pipeline = WorkflowPipeline(console, pkg_path, session, phases)

        # Mock security check to return no critical failures
        with patch.object(
            pipeline, "_check_security_critical_failures", return_value=False
        ):
            with patch.object(pipeline, "_show_security_audit_warning"):
                options = MockOptions(publish="patch")

                result = pipeline._handle_standard_workflow(
                    options, 1, testing_passed=True, comprehensive_passed=False
                )

                # Should pass because tests passed and no security issues
                assert result

    def test_non_publishing_workflow_unaffected_by_security_gates(self):
        """Test that non-publishing workflows are not affected by security gates."""
        console = Console()
        pkg_path = Path.cwd()
        session = MockSession()
        phases = MockPhases()

        pipeline = WorkflowPipeline(console, pkg_path, session, phases)

        # Security check should not even be called for non-publishing workflows
        options = MockOptions(publish=False, all=False, commit=False)

        result = pipeline._handle_standard_workflow(
            options, 1, testing_passed=True, comprehensive_passed=False
        )

        # Should fail because comprehensive hooks failed (original behavior)
        assert not result

    @pytest.mark.asyncio
    async def test_ai_agent_security_gates(self):
        """Test that AI agent workflows respect security gates."""
        console = Console()
        pkg_path = Path.cwd()
        session = MockSession()
        phases = MockPhases()

        pipeline = WorkflowPipeline(console, pkg_path, session, phases)

        # Mock security check to return critical failures
        with patch.object(
            pipeline, "_check_security_critical_failures", return_value=True
        ):
            with patch.object(pipeline, "_run_ai_agent_fixing_phase") as mock_ai_fix:
                mock_ai_fix.return_value = False  # AI fixing fails

                options = MockOptions(publish="patch", ai_agent=True)

                result = await pipeline._handle_ai_agent_workflow(
                    options, 1, testing_passed=True, comprehensive_passed=True
                )

                # Should fail because security issues couldn't be fixed
                assert not result
                # AI fixing should have been attempted
                mock_ai_fix.assert_called_once()

    def test_fail_safe_behavior_on_security_check_error(self):
        """Test that security checks fail safely when they encounter errors."""
        console = Console()
        pkg_path = Path.cwd()
        session = MockSession()
        phases = MockPhases()

        pipeline = WorkflowPipeline(console, pkg_path, session, phases)

        # Mock security check to raise an exception
        with patch.object(
            pipeline,
            "_check_security_critical_failures",
            side_effect=Exception("Security check failed"),
        ):
            options = MockOptions(publish="patch")

            result = pipeline._handle_standard_workflow(
                options, 1, testing_passed=True, comprehensive_passed=True
            )

            # Should fail safely when security check fails
            assert not result

    def test_security_audit_report_generation(self):
        """Test that security audit reports are generated correctly."""
        console = Console()
        pkg_path = Path.cwd()
        session = MockSession()
        phases = MockPhases()

        pipeline = WorkflowPipeline(console, pkg_path, session, phases)

        # Mock the security audit report
        from crackerjack.security.audit import SecurityAuditReport

        mock_audit = SecurityAuditReport(
            critical_failures=[],
            high_failures=[],
            medium_failures=[],
            low_failures=[],
            allows_publishing=True,
            security_warnings=["Test warning"],
            recommendations=["Test recommendation"],
        )

        pipeline._last_security_audit = mock_audit

        # Test that the audit warning uses the stored report
        with patch.object(console, "print") as mock_print:
            pipeline._show_security_audit_warning()

            # Should have called print with audit information
            assert mock_print.called
            # Check that recommendations were shown
            calls = [str(call) for call in mock_print.call_args_list]
            assert any("Test recommendation" in call for call in calls)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
