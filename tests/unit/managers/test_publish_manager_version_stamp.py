"""Unit tests for the release path's version-claim re-stamping.

A release bumps ``version`` in ``pyproject.toml``; every doc surface that
carries a version claim has to move with it. Before this existed, the bump
wrote pyproject and left the claims behind — the fleet accumulated eleven
releases of drift on one README that way.

``PublishManagerImpl._stamp_version_claims`` closes the loop at the only
point where the drift is created: the bump itself. Repos that keep no
version claims ship no ``scripts/stamp_version.py`` and the step is a
no-op; repos that do ship it cannot publish a version whose docs disagree
with it, because a failing stamp aborts the release.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from crackerjack.managers.publish_manager import PublishManagerImpl

# A stand-in for the fleet's ``scripts/stamp_version.py``. It implements the
# same contract the real stampers do: read the version from pyproject.toml,
# rewrite the claim, exit 0. The real ones additionally support ``--check``
# and ``--stage``; neither matters here, because the release path invokes
# the script without flags and lets the publish flow stage the result.
_FAKE_STAMP_SCRIPT = r'''#!/usr/bin/env python3
"""Stand-in for the fleet's scripts/stamp_version.py (contract only)."""
import re
import sys
import tomllib
from pathlib import Path

root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
with (root / "pyproject.toml").open("rb") as handle:
    version = str(tomllib.load(handle)["project"]["version"])
claim = root / "README.md"
text = claim.read_text()
new_text = re.sub(r"(\*\*Version:\*\* )\d+\.\d+\.\d+", rf"\g<1>{version}", text)
if new_text != text:
    claim.write_text(new_text)
sys.exit(0)
'''

# A stamp script that fails the way a real one fails: the claim it was told
# to rewrite cannot be found. Exit 2 is the real script's "a claim could not
# be found, or a file could not be read" code.
_FAILING_STAMP_SCRIPT = """#!/usr/bin/env python3
import sys

print("ERROR: no version claim matched in README.md", file=sys.stderr)
sys.exit(2)
"""


def _write_repo(root: Path, *, stamp_script: str | None) -> Path:
    """Lay out a minimal repo: pyproject, a README claim, maybe a stamper."""
    (root / "pyproject.toml").write_text(
        '[project]\nname = "sample"\nversion = "0.1.0"\n',
    )
    (root / "README.md").write_text("# Sample\n\n**Version:** 0.1.0\n")
    if stamp_script is not None:
        scripts = root / "scripts"
        scripts.mkdir(exist_ok=True)
        (scripts / "stamp_version.py").write_text(stamp_script)
    return root


def _make_manager(root: Path) -> PublishManagerImpl:
    """Build a PublishManager over *root* with the noisy edges stubbed."""
    changelog_generator = Mock()
    changelog_generator.generate_changelog_from_commits.return_value = False
    return PublishManagerImpl(
        git_service=Mock(),
        version_analyzer=Mock(),
        changelog_generator=changelog_generator,
        console=Mock(),
        pkg_path=root,
    )


@pytest.mark.unit
class TestVersionClaimStamping:
    """The release path re-stamps doc claims alongside the version bump."""

    def test_bump_moves_the_claim_with_the_version(self, tmp_path: Path) -> None:
        """The claim surface ends the bump carrying the new version."""
        root = _write_repo(tmp_path, stamp_script=_FAKE_STAMP_SCRIPT)
        manager = _make_manager(root)

        new_version = manager._perform_bump("0.1.0", "patch")

        assert new_version == "0.1.1"
        assert "**Version:** 0.1.1" in (root / "README.md").read_text()

    def test_bump_invokes_the_stamper_with_the_repo_root(self, tmp_path: Path) -> None:
        """The script is called with the repo root, not the caller's cwd."""
        root = _write_repo(tmp_path, stamp_script=_FAKE_STAMP_SCRIPT)
        manager = _make_manager(root)

        with patch.object(
            manager,
            "_run_command",
            wraps=manager._run_command,
        ) as run_command:
            manager._perform_bump("0.1.0", "patch")

        assert run_command.call_count == 1
        command = run_command.call_args[0][0]
        assert command[0] == sys.executable
        assert command[1] == str(root / "scripts" / "stamp_version.py")
        assert command[2] == str(root)

    def test_bump_without_a_stamper_is_a_no_op(self, tmp_path: Path) -> None:
        """A repo that keeps no version claims publishes without the step."""
        root = _write_repo(tmp_path, stamp_script=None)
        manager = _make_manager(root)

        new_version = manager._perform_bump("0.1.0", "patch")

        assert new_version == "0.1.1"
        assert 'version = "0.1.1"' in (root / "pyproject.toml").read_text()

    def test_failing_stamper_aborts_the_bump(self, tmp_path: Path) -> None:
        """A stamp failure aborts the release rather than shipping drift."""
        root = _write_repo(tmp_path, stamp_script=_FAILING_STAMP_SCRIPT)
        manager = _make_manager(root)

        with pytest.raises(RuntimeError, match="stamp_version.py failed"):
            manager._perform_bump("0.1.0", "patch")

    def test_failing_stamper_rolls_the_version_back(self, tmp_path: Path) -> None:
        """The aborted bump leaves pyproject at the version it started from."""
        root = _write_repo(tmp_path, stamp_script=_FAILING_STAMP_SCRIPT)
        manager = _make_manager(root)

        with pytest.raises(RuntimeError):
            manager._perform_bump("0.1.0", "patch")

        assert 'version = "0.1.0"' in (root / "pyproject.toml").read_text()

    def test_dry_run_does_not_stamp(self, tmp_path: Path) -> None:
        """A dry run changes nothing, so it must not run the stamper."""
        root = _write_repo(tmp_path, stamp_script=_FAKE_STAMP_SCRIPT)
        manager = PublishManagerImpl(
            git_service=Mock(),
            version_analyzer=Mock(),
            changelog_generator=Mock(),
            console=Mock(),
            pkg_path=root,
            dry_run=True,
        )

        new_version = manager._perform_bump("0.1.0", "patch")

        assert new_version == "0.1.1"
        assert "**Version:** 0.1.0" in (root / "README.md").read_text()
        assert 'version = "0.1.0"' in (root / "pyproject.toml").read_text()
