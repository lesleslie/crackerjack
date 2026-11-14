from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

from crackerjack.config import CrackerjackSettings
from crackerjack.core.session_coordinator import (
    PROTECTED_COVERAGE_ARTIFACTS,
    SessionCoordinator,
)
from crackerjack.core.workflow_orchestrator import WorkflowPipeline
from crackerjack.models.config import CleanupConfig


def _touch(path: Path, mtime: float) -> Path:
    """Create a file with a specific mtime so keep-N ordering is testable."""
    path.write_text("x")
    import os

    os.utime(path, (mtime, mtime))
    return path


class TestCleanupCoverageFiles:
    """``_cleanup_coverage_files`` prunes coverage.py shards and nothing else."""

    def test_ratchet_survives_cleanup(self, tmp_path: Path) -> None:
        """The enforced coverage floor must survive a session cleanup.

        Deleting it makes the release audit treat the repo as having no
        ratchet at all, which silently skips the coverage claim.
        """
        session = SessionCoordinator(pkg_path=tmp_path)
        ratchet = _touch(tmp_path / ".coverage-ratchet.json", 1000.0)

        session.cleanup_resources()

        assert ratchet.exists(), "the coverage ratchet was deleted by cleanup"

    def test_coverage_json_survives_cleanup(self, tmp_path: Path) -> None:
        """pytest-cov's JSON report must survive.

        The ratchet records its mtime and the release audit reads it for
        the measured-coverage tolerance check.
        """
        session = SessionCoordinator(pkg_path=tmp_path)
        report = _touch(tmp_path / "coverage.json", 1000.0)

        session.cleanup_resources()

        assert report.exists(), "coverage.json was deleted by cleanup"

    def test_coverage_shards_are_removed(self, tmp_path: Path) -> None:
        """coverage.py's per-process shards are the cleanup's actual target."""
        session = SessionCoordinator(pkg_path=tmp_path)
        shard = _touch(tmp_path / ".coverage.host.1234.5678", 1000.0)

        session.cleanup_resources()

        assert not shard.exists()

    def test_keep_recent_keeps_the_newest_shards(self, tmp_path: Path) -> None:
        """``keep_recent`` keeps the newest shards and removes the rest."""
        session = SessionCoordinator(pkg_path=tmp_path)
        old = _touch(tmp_path / ".coverage.host.1.old", 1000.0)
        new = _touch(tmp_path / ".coverage.host.1.new", 2000.0)

        session._cleanup_coverage_files(keep_recent=1)

        assert new.exists()
        assert not old.exists()

    def test_protected_artifacts_are_declared(self) -> None:
        """The protection is explicit, not a side effect of the glob."""
        assert ".coverage-ratchet.json" in PROTECTED_COVERAGE_ARTIFACTS
        assert "coverage.json" in PROTECTED_COVERAGE_ARTIFACTS


class TestPipelineSessionCleanup:
    """The pipeline prunes session artifacts on every exit path."""

    @patch("crackerjack.core.workflow_orchestrator.load_settings")
    @patch("crackerjack.core.workflow_orchestrator.SessionCoordinator")
    @patch("crackerjack.core.workflow_orchestrator.PhaseCoordinator")
    @patch("crackerjack.core.workflow_orchestrator.build_oneiric_runtime")
    @patch("crackerjack.core.workflow_orchestrator.register_crackerjack_workflow")
    async def test_cleanup_runs_after_a_successful_workflow(
        self,
        mock_register_wf: Mock,
        mock_build_runtime: Mock,
        mock_phase_coord: Mock,
        mock_session_coord: Mock,
        mock_load_settings: Mock,
    ) -> None:
        mock_settings = CrackerjackSettings()
        mock_load_settings.return_value = mock_settings

        mock_runtime = Mock()
        mock_runtime.workflow_bridge.execute_dag = AsyncMock(
            return_value={"results": {"hook1": True}}
        )
        mock_build_runtime.return_value = mock_runtime

        pipeline = WorkflowPipeline(settings=mock_settings, pkg_path=Path("/tmp"))
        pipeline.session.initialize_session_tracking = Mock()
        pipeline.session.finalize_session = Mock()

        result = await pipeline.run_complete_workflow({"test": "options"})

        assert result is True
        pipeline.session.cleanup_resources.assert_called_once()

    @patch("crackerjack.core.workflow_orchestrator.load_settings")
    @patch("crackerjack.core.workflow_orchestrator.SessionCoordinator")
    @patch("crackerjack.core.workflow_orchestrator.PhaseCoordinator")
    @patch("crackerjack.core.workflow_orchestrator.build_oneiric_runtime")
    @patch("crackerjack.core.workflow_orchestrator.register_crackerjack_workflow")
    async def test_cleanup_runs_after_a_failed_workflow(
        self,
        mock_register_wf: Mock,
        mock_build_runtime: Mock,
        mock_phase_coord: Mock,
        mock_session_coord: Mock,
        mock_load_settings: Mock,
    ) -> None:
        """A crashed run must not leave the next one to clean up after it."""
        mock_settings = CrackerjackSettings()
        mock_load_settings.return_value = mock_settings

        mock_runtime = Mock()
        mock_runtime.workflow_bridge.execute_dag = AsyncMock(
            side_effect=RuntimeError("boom")
        )
        mock_build_runtime.return_value = mock_runtime

        pipeline = WorkflowPipeline(settings=mock_settings, pkg_path=Path("/tmp"))
        pipeline.session.initialize_session_tracking = Mock()
        pipeline.session.finalize_session = Mock()

        result = await pipeline.run_complete_workflow({"test": "options"})

        assert result is False
        pipeline.session.cleanup_resources.assert_called_once()

    def test_cleanup_policy_is_configured_from_settings(self) -> None:
        """The session gets the configured keep-N policy, not its defaults."""
        settings = CrackerjackSettings()
        session = Mock()
        pipeline = WorkflowPipeline(
            settings=settings, session=session, pkg_path=Path("/tmp")
        )

        pipeline._configure_session_cleanup({})

        session.set_cleanup_config.assert_called_once()
        applied = session.set_cleanup_config.call_args[0][0]
        assert isinstance(applied, CleanupConfig)
        assert applied.keep_coverage_files == settings.cleanup.keep_coverage_files
        assert applied.keep_debug_logs == settings.cleanup.keep_debug_logs

    def test_cleanup_failure_does_not_change_the_verdict(self) -> None:
        """A cleanup error is swallowed; the workflow's result stands."""
        settings = CrackerjackSettings()
        session = Mock()
        session.cleanup_resources.side_effect = OSError("disk gone")
        pipeline = WorkflowPipeline(
            settings=settings, session=session, pkg_path=Path("/tmp")
        )

        pipeline._cleanup_session_artifacts()  # must not raise
