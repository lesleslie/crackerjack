"""The test suite must not write to the user's real runtime data.

Crackerjack's runtime data resolves under the XDG base directories, and
``TestManager`` falls back to ``RunStateSettings().storage_path`` when no
store path is injected. That default is the *user's* real data directory,
so a test that runs the test phase would otherwise write a run-state row
into the user's database - noise that grows on every suite run and is
never cleaned up.

``crackerjack.utils.xdg_paths`` resolves on every call, so redirecting the
``XDG_*`` environment variables for the test session contains it — but only
for callers that resolve on every call too. A path captured in a
module-level constant is frozen at import time, before the session fixture
can redirect anything, and the suite writes into the user's real directory
regardless.

**Scope: the XDG-resolved paths.** One path still escapes the sandbox,
because it never used XDG at all: ``AsyncTaskSettings.storage_path``
resolves to ``~/.crackerjack/state/async_tasks.db``, and a suite run
writes to it. Moving it is a separate change — it alters where the MCP
server's task state lives, and the old file needs a migration — so it is
recorded as not-yet-implemented in the XDG decision record rather than
fixed here. The sandbox does not pretend to contain it.
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

    def test_health_snapshot_db_is_inside_the_test_sandbox(
        self, xdg_sandbox_root: Path
    ) -> None:
        """The health snapshot database must resolve into the sandbox.

        This one was captured at import time, so the session-scoped
        redirect could not reach it: the suite wrote health snapshots into
        the user's real ``~/.local/share/crackerjack/`` on every run.
        """
        from crackerjack.cli.handlers.health import resolve_integration_db_path

        db_path = resolve_integration_db_path()

        assert db_path.is_relative_to(xdg_sandbox_root), (
            f"the health snapshot database resolved to {db_path}, outside the "
            f"test sandbox {xdg_sandbox_root}; the test suite would be writing "
            f"to the user's real XDG data directory"
        )
