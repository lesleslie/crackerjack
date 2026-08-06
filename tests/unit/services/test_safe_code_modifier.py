"""Stage 3 bak-sibling rollback tests for SafeCodeModifier.

The existing ``SafeCodeModifier`` machinery backs files up with a timestamped
``.bak.<ts>.<seq>.<suffix>`` naming scheme and prunes older backups (see
``_backup_file`` / ``_cleanup_old_backups``). That is fine for the high-level
``apply_changes_with_validation`` flow, which can roll back from the in-memory
``BackupMetadata``.

Stage 3 adds a thinner synchronous helper, ``apply_with_backup``, that
performs the minimal safe-rewrite dance:
  - if ``allow_unsafe=True``, write a sibling ``<path>.bak`` *before* writing
    new content;
  - otherwise skip the backup and just rewrite.

The contract is intentionally narrower than the existing async flow so callers
that already validated upstream (e.g. preflight after the working-tree guard
passes) can opt into a fast path without paying for syntax/ruff validation.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock


def test_unsafe_creates_bak_sibling(tmp_path) -> None:
    from crackerjack.services.safe_code_modifier import SafeCodeModifier

    target = tmp_path / "module.py"
    target.write_text("original = 1\n")
    modifier = SafeCodeModifier(console=MagicMock(), project_path=tmp_path)

    modifier.apply_with_backup(
        "modified = 2\n",
        path=target,
        allow_unsafe=True,
    )

    bak = target.with_suffix(target.suffix + ".bak")
    assert bak.exists(), f"expected .bak sibling at {bak}"
    assert bak.read_text() == "original = 1\n"
    assert target.read_text() == "modified = 2\n"
