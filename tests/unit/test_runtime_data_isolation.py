"""The test suite must not write to the user's real runtime data.

Crackerjack's runtime data resolves under the XDG base directories, and
``TestManager`` falls back to ``RunStateSettings().storage_path`` when no
store path is injected. That default is the *user's* real data directory,
so a test that runs the test phase would otherwise write a run-state row
into the user's database - noise that grows on every suite run and is
never cleaned up.

``crackerjack.utils.xdg_paths`` resolves on every call, so redirecting the
``XDG_*`` environment variables for the test session contains it.
"""

from __future__ import annotations

from pathlib import Path

from crackerjack.config.settings import RunStateSettings


class TestRuntimeDataIsolation:
    def test_run_state_store_resolves_inside_the_test_sandbox(
        self, xdg_sandbox_root: Path
    ) -> None:
        storage_path = RunStateSettings().storage_path

        assert storage_path.is_relative_to(xdg_sandbox_root), (
            f"the run-state store resolved to {storage_path}, outside the test "
            f"sandbox {xdg_sandbox_root}; the test suite would be writing to "
            f"the user's real XDG data directory"
        )

    def test_test_manager_default_store_path_is_inside_the_sandbox(
        self, tmp_path: Path, xdg_sandbox_root: Path
    ) -> None:
        """A ``TestManager`` built without an injected path must not fall
        through to the user's database."""
        from crackerjack.managers.test_manager import TestManager

        manager = TestManager(pkg_path=tmp_path)

        assert manager.run_state_db_path.is_relative_to(xdg_sandbox_root), (
            f"TestManager defaulted its run-state store to "
            f"{manager.run_state_db_path}, outside the test sandbox "
            f"{xdg_sandbox_root}"
        )
