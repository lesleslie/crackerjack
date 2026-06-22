from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.unit
class TestSelfPatcherDenyPaths:
    def test_deny_paths_includes_hooks_config(self) -> None:
        from crackerjack.services.self_patcher import SELFPATCHER_DENY_PATHS

        assert "crackerjack/config/hooks.py" in SELFPATCHER_DENY_PATHS

    def test_deny_paths_includes_self_patcher(self) -> None:
        from crackerjack.services.self_patcher import SELFPATCHER_DENY_PATHS

        assert "crackerjack/services/self_patcher.py" in SELFPATCHER_DENY_PATHS

    def test_deny_paths_includes_improvement_generator(self) -> None:
        from crackerjack.services.self_patcher import SELFPATCHER_DENY_PATHS

        assert "crackerjack/services/improvement_generator.py" in SELFPATCHER_DENY_PATHS

    def test_deny_paths_includes_settings_yaml(self) -> None:
        from crackerjack.services.self_patcher import SELFPATCHER_DENY_PATHS

        assert "settings/crackerjack.yaml" in SELFPATCHER_DENY_PATHS

    def test_deny_paths_includes_pyproject(self) -> None:
        from crackerjack.services.self_patcher import SELFPATCHER_DENY_PATHS

        assert "pyproject.toml" in SELFPATCHER_DENY_PATHS

    def test_deny_paths_includes_failure_recorder(self) -> None:
        from crackerjack.services.self_patcher import SELFPATCHER_DENY_PATHS

        assert "crackerjack/services/failure_recorder.py" in SELFPATCHER_DENY_PATHS


@pytest.mark.unit
class TestSelfPatcherDiffValidation:
    def test_patcher_rejects_diff_touching_deny_path(self, tmp_path: Path) -> None:
        from crackerjack.services.improvement_generator import ImprovementProposal
        from crackerjack.services.self_patcher import SelfPatcher

        patcher = SelfPatcher(repo_root=tmp_path)
        proposal = ImprovementProposal(
            improvement_id="imp-001",
            improvement_type="prompt",
            diff=(
                "--- a/crackerjack/config/hooks.py\n"
                "+++ b/crackerjack/config/hooks.py\n"
                "@@ -1 +1 @@\n-old\n+new\n"
            ),
            rationale="tweak hooks",
            confidence=0.9,
            expected_improvement="better",
        )

        is_safe, reason = patcher.validate_diff(proposal)
        assert not is_safe
        assert "deny" in reason.lower()

    def test_patcher_accepts_safe_diff(self, tmp_path: Path) -> None:
        from crackerjack.services.improvement_generator import ImprovementProposal
        from crackerjack.services.self_patcher import SelfPatcher

        patcher = SelfPatcher(repo_root=tmp_path)
        proposal = ImprovementProposal(
            improvement_id="imp-002",
            improvement_type="prompt",
            diff=(
                "--- a/crackerjack/agents/ruff_agent.py\n"
                "+++ b/crackerjack/agents/ruff_agent.py\n"
                "@@ -10 +10 @@\n-old_prompt\n+new_prompt\n"
            ),
            rationale="improve ruff prompt",
            confidence=0.9,
            expected_improvement="better",
        )

        is_safe, _ = patcher.validate_diff(proposal)
        assert is_safe

    def test_patcher_rejects_symlink_mode_in_diff(self, tmp_path: Path) -> None:
        from crackerjack.services.improvement_generator import ImprovementProposal
        from crackerjack.services.self_patcher import SelfPatcher

        patcher = SelfPatcher(repo_root=tmp_path)
        proposal = ImprovementProposal(
            improvement_id="imp-003",
            improvement_type="prompt",
            diff=(
                "--- a/crackerjack/agents/safe_agent.py\n"
                "+++ b/crackerjack/agents/safe_agent.py\n"
                "new mode 120000\n"
                "@@ -1 +1 @@\n-x\n+y\n"
            ),
            rationale="add symlink",
            confidence=0.9,
            expected_improvement="whatever",
        )

        is_safe, reason = patcher.validate_diff(proposal)
        assert not is_safe
        assert "symlink" in reason.lower()

    def test_patcher_rejects_git_binary_patch(self, tmp_path: Path) -> None:
        from crackerjack.services.improvement_generator import ImprovementProposal
        from crackerjack.services.self_patcher import SelfPatcher

        patcher = SelfPatcher(repo_root=tmp_path)
        proposal = ImprovementProposal(
            improvement_id="imp-004",
            improvement_type="prompt",
            diff="GIT binary patch\nliteral 10\ndata",
            rationale="binary",
            confidence=0.9,
            expected_improvement="whatever",
        )

        is_safe, reason = patcher.validate_diff(proposal)
        assert not is_safe
        assert "binary" in reason.lower()


@pytest.mark.unit
class TestSelfPatcherSentinel:
    def test_sentinel_path_is_under_crackerjack_dir(self, tmp_path: Path) -> None:
        from crackerjack.services.self_patcher import SelfPatcher

        patcher = SelfPatcher(repo_root=tmp_path)
        sentinel = patcher.sentinel_path
        assert sentinel.parent.name == ".crackerjack"
        assert sentinel.name == "self_patch.lock"

    async def test_startup_check_reverts_when_sentinel_exists(
        self, tmp_path: Path
    ) -> None:
        from crackerjack.services.self_patcher import SelfPatcher

        # Create sentinel
        lock_dir = tmp_path / ".crackerjack"
        lock_dir.mkdir()
        (lock_dir / "self_patch.lock").write_text("patch-in-progress")

        # Initialize a git repo so git revert has something to do
        subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=tmp_path, check=True, capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=tmp_path, check=True, capture_output=True,
        )
        subprocess.run(
            ["git", "commit", "--allow-empty", "-m", "init"],
            cwd=tmp_path, check=True, capture_output=True,
        )

        patcher = SelfPatcher(repo_root=tmp_path)

        with patch.object(patcher, "_git_revert_working_tree") as mock_revert:
            mock_revert.return_value = None
            await patcher.startup_check()
            mock_revert.assert_called_once()

        # Sentinel must be cleaned up after startup_check
        assert not (lock_dir / "self_patch.lock").exists()

    async def test_startup_check_noop_when_no_sentinel(self, tmp_path: Path) -> None:
        from crackerjack.services.self_patcher import SelfPatcher

        patcher = SelfPatcher(repo_root=tmp_path)

        with patch.object(patcher, "_git_revert_working_tree") as mock_revert:
            await patcher.startup_check()
            mock_revert.assert_not_called()


@pytest.mark.unit
class TestSelfPatcherShadowMode:
    async def test_shadow_mode_never_commits(self, tmp_path: Path) -> None:
        from crackerjack.services.improvement_generator import ImprovementProposal
        from crackerjack.services.self_patcher import SelfPatcher

        patcher = SelfPatcher(repo_root=tmp_path, shadow_mode=True)
        proposal = ImprovementProposal(
            improvement_id="imp-shadow",
            improvement_type="prompt",
            diff=(
                "--- a/crackerjack/agents/ruff_agent.py\n"
                "+++ b/crackerjack/agents/ruff_agent.py\n"
                "@@ -1 +1 @@\n-old\n+new\n"
            ),
            rationale="shadow test",
            confidence=0.9,
            expected_improvement="better",
        )

        with patch.object(patcher, "_git_commit") as mock_commit:
            with patch.object(patcher, "_run_validation", new_callable=AsyncMock) as mock_val:
                mock_val.return_value = (True, "passed")
                with patch.object(patcher, "_apply_diff_to_working_tree") as mock_apply:
                    mock_apply.return_value = None
                    result = await patcher.apply(proposal)

        mock_commit.assert_not_called()
        assert result["shadow_mode"] is True

    async def test_non_shadow_mode_commits_on_pass(self, tmp_path: Path) -> None:
        from crackerjack.services.improvement_generator import ImprovementProposal
        from crackerjack.services.self_patcher import SelfPatcher

        patcher = SelfPatcher(repo_root=tmp_path, shadow_mode=False)
        proposal = ImprovementProposal(
            improvement_id="imp-live",
            improvement_type="prompt",
            diff=(
                "--- a/crackerjack/agents/ruff_agent.py\n"
                "+++ b/crackerjack/agents/ruff_agent.py\n"
                "@@ -1 +1 @@\n-old\n+new\n"
            ),
            rationale="live test",
            confidence=0.9,
            expected_improvement="better",
        )

        with patch.object(patcher, "_git_commit") as mock_commit:
            with patch.object(patcher, "_run_validation", new_callable=AsyncMock) as mock_val:
                mock_val.return_value = (True, "passed")
                with patch.object(patcher, "_apply_diff_to_working_tree") as mock_apply:
                    mock_apply.return_value = None
                    with patch.object(patcher, "_write_sentinel") as _:
                        with patch.object(patcher, "_delete_sentinel") as _:
                            result = await patcher.apply(proposal)

        mock_commit.assert_called_once()
        assert result["committed"] is True


@pytest.mark.unit
class TestSelfPatcherValidationTimeout:
    async def test_validation_timeout_triggers_revert(self, tmp_path: Path) -> None:
        import asyncio

        from crackerjack.services.improvement_generator import ImprovementProposal
        from crackerjack.services.self_patcher import SelfPatcher

        patcher = SelfPatcher(
            repo_root=tmp_path,
            shadow_mode=False,
            validation_timeout_seconds=1,
        )
        proposal = ImprovementProposal(
            improvement_id="imp-timeout",
            improvement_type="prompt",
            diff=(
                "--- a/crackerjack/agents/ruff_agent.py\n"
                "+++ b/crackerjack/agents/ruff_agent.py\n"
                "@@ -1 +1 @@\n-old\n+new\n"
            ),
            rationale="timeout test",
            confidence=0.9,
            expected_improvement="better",
        )

        async def slow_validation() -> tuple[bool, str]:
            await asyncio.sleep(10)  # will be cancelled by timeout
            return True, "passed"

        with patch.object(patcher, "_run_validation", side_effect=slow_validation):
            with patch.object(patcher, "_apply_diff_to_working_tree") as mock_apply:
                mock_apply.return_value = None
                with patch.object(patcher, "_git_revert_working_tree") as mock_revert:
                    mock_revert.return_value = None
                    with patch.object(patcher, "_write_sentinel") as _:
                        with patch.object(patcher, "_delete_sentinel") as _:
                            result = await patcher.apply(proposal)

        assert result["reverted"] is True
        mock_revert.assert_called_once()
