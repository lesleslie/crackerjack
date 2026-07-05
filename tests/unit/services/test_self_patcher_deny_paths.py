from __future__ import annotations

from pathlib import Path

import pytest


@pytest.mark.unit
class TestSelfPatcherDenyPathsAuditH11:
    """Audit H11: verify the deny list covers the 10 critical files referenced
    in the 2026-06-26 audit (see HANDOFF.md lines 116-148).

    The list must be enforced via pattern/suffix matching so it works across
    repos — exact paths are insufficient.
    """

    def test_deny_paths_includes_failure_metrics_repository(self) -> None:
        from crackerjack.services.self_patcher import SELFPATCHER_DENY_PATHS

        assert "failure_metrics_repository.py" in SELFPATCHER_DENY_PATHS

    def test_deny_paths_includes_constitution(self) -> None:
        from crackerjack.services.self_patcher import SELFPATCHER_DENY_PATHS

        assert "constitution.py" in SELFPATCHER_DENY_PATHS

    def test_deny_paths_includes_overseer(self) -> None:
        from crackerjack.services.self_patcher import SELFPATCHER_DENY_PATHS

        assert "overseer.py" in SELFPATCHER_DENY_PATHS

    def test_deny_paths_includes_hooks(self) -> None:
        from crackerjack.services.self_patcher import SELFPATCHER_DENY_PATHS

        assert "hooks.py" in SELFPATCHER_DENY_PATHS

    def test_deny_paths_includes_config_directory(self) -> None:
        from crackerjack.services.self_patcher import SELFPATCHER_DENY_PATHS

        assert "config/" in SELFPATCHER_DENY_PATHS

    def test_deny_paths_includes_security_directory(self) -> None:
        from crackerjack.services.self_patcher import SELFPATCHER_DENY_PATHS

        assert "security/" in SELFPATCHER_DENY_PATHS

    def test_deny_paths_includes_settings_directory(self) -> None:
        from crackerjack.services.self_patcher import SELFPATCHER_DENY_PATHS

        assert "settings/" in SELFPATCHER_DENY_PATHS

    def test_deny_paths_includes_mcp_server_config(self) -> None:
        from crackerjack.services.self_patcher import SELFPATCHER_DENY_PATHS

        assert "mcp_server" in SELFPATCHER_DENY_PATHS

    def test_deny_paths_includes_dotenv(self) -> None:
        from crackerjack.services.self_patcher import SELFPATCHER_DENY_PATHS

        assert ".env" in SELFPATCHER_DENY_PATHS

    def test_deny_paths_includes_pyproject_toml(self) -> None:
        from crackerjack.services.self_patcher import SELFPATCHER_DENY_PATHS

        assert "pyproject.toml" in SELFPATCHER_DENY_PATHS


@pytest.mark.unit
class TestSelfPatcherDenyPathMatching:
    """Verify the matcher denies by pattern (basename / path suffix) so the
    list works across repos — not only for files at the canonical
    crackerjack/services/ or crackerjack/config/ locations."""

    def _make_patcher(self, tmp_path: Path):
        from crackerjack.services.self_patcher import SelfPatcher

        return SelfPatcher(repo_root=tmp_path)

    @staticmethod
    def _proposal(diff: str):
        from crackerjack.services.improvement_generator import ImprovementProposal

        return ImprovementProposal(
            improvement_id="imp-h11",
            improvement_type="prompt",
            diff=diff,
            rationale="h11 audit",
            confidence=0.9,
            expected_improvement="audit fix",
        )

    def test_denies_failure_metrics_repository_by_basename(
        self, tmp_path: Path
    ) -> None:
        patcher = self._make_patcher(tmp_path)
        diff = (
            "--- a/some_repo/services/failure_metrics_repository.py\n"
            "+++ b/some_repo/services/failure_metrics_repository.py\n"
            "@@ -1 +1 @@\n-x\n+y\n"
        )
        is_safe, reason = patcher.validate_diff(self._proposal(diff))
        assert not is_safe
        assert "deny" in reason.lower()

    def test_denies_constitution_by_basename(self, tmp_path: Path) -> None:
        patcher = self._make_patcher(tmp_path)
        diff = (
            "--- a/repo/services/constitution.py\n"
            "+++ b/repo/services/constitution.py\n"
            "@@ -1 +1 @@\n-x\n+y\n"
        )
        is_safe, reason = patcher.validate_diff(self._proposal(diff))
        assert not is_safe
        assert "deny" in reason.lower()

    def test_denies_overseer_by_basename(self, tmp_path: Path) -> None:
        patcher = self._make_patcher(tmp_path)
        diff = (
            "--- a/repo/services/improvement_overseer.py\n"
            "+++ b/repo/services/improvement_overseer.py\n"
            "@@ -1 +1 @@\n-x\n+y\n"
        )
        is_safe, reason = patcher.validate_diff(self._proposal(diff))
        assert not is_safe
        assert "deny" in reason.lower()

    def test_denies_hooks_by_basename(self, tmp_path: Path) -> None:
        patcher = self._make_patcher(tmp_path)
        diff = (
            "--- a/repo/config/hooks.py\n"
            "+++ b/repo/config/hooks.py\n"
            "@@ -1 +1 @@\n-x\n+y\n"
        )
        is_safe, reason = patcher.validate_diff(self._proposal(diff))
        assert not is_safe
        assert "deny" in reason.lower()

    def test_denies_any_path_under_config_directory(self, tmp_path: Path) -> None:
        patcher = self._make_patcher(tmp_path)
        diff = (
            "--- a/some_repo/config/something_new.py\n"
            "+++ b/some_repo/config/something_new.py\n"
            "@@ -1 +1 @@\n-x\n+y\n"
        )
        is_safe, reason = patcher.validate_diff(self._proposal(diff))
        assert not is_safe
        assert "deny" in reason.lower()

    def test_denies_any_path_under_security_directory(self, tmp_path: Path) -> None:
        patcher = self._make_patcher(tmp_path)
        diff = (
            "--- a/some_repo/security/auditor.py\n"
            "+++ b/some_repo/security/auditor.py\n"
            "@@ -1 +1 @@\n-x\n+y\n"
        )
        is_safe, reason = patcher.validate_diff(self._proposal(diff))
        assert not is_safe
        assert "deny" in reason.lower()

    def test_denies_any_path_under_settings_directory(self, tmp_path: Path) -> None:
        patcher = self._make_patcher(tmp_path)
        diff = (
            "--- a/some_repo/settings/custom.yaml\n"
            "+++ b/some_repo/settings/custom.yaml\n"
            "@@ -1 +1 @@\n-x\n+y\n"
        )
        is_safe, reason = patcher.validate_diff(self._proposal(diff))
        assert not is_safe
        assert "deny" in reason.lower()

    def test_denies_mcp_server_config_anywhere(self, tmp_path: Path) -> None:
        patcher = self._make_patcher(tmp_path)
        diff = (
            "--- a/some_repo/mcp_server_config.json\n"
            "+++ b/some_repo/mcp_server_config.json\n"
            "@@ -1 +1 @@\n-x\n+y\n"
        )
        is_safe, reason = patcher.validate_diff(self._proposal(diff))
        assert not is_safe
        assert "deny" in reason.lower()

    def test_denies_dotenv_anywhere(self, tmp_path: Path) -> None:
        patcher = self._make_patcher(tmp_path)
        diff = (
            "--- a/.env\n"
            "+++ b/.env\n"
            "@@ -1 +1 @@\n-x\n+y\n"
        )
        is_safe, reason = patcher.validate_diff(self._proposal(diff))
        assert not is_safe
        assert "deny" in reason.lower()

    def test_denies_pyproject_toml_anywhere(self, tmp_path: Path) -> None:
        patcher = self._make_patcher(tmp_path)
        diff = (
            "--- a/some_repo/pyproject.toml\n"
            "+++ b/some_repo/pyproject.toml\n"
            "@@ -1 +1 @@\n-x\n+y\n"
        )
        is_safe, reason = patcher.validate_diff(self._proposal(diff))
        assert not is_safe
        assert "deny" in reason.lower()

    def test_allows_non_denied_path(self, tmp_path: Path) -> None:
        """Sanity: a normal agent or service file is still allowed."""
        patcher = self._make_patcher(tmp_path)
        diff = (
            "--- a/some_repo/agents/ruff_agent.py\n"
            "+++ b/some_repo/agents/ruff_agent.py\n"
            "@@ -1 +1 @@\n-old_prompt\n+new_prompt\n"
        )
        is_safe, _ = patcher.validate_diff(self._proposal(diff))
        assert is_safe
