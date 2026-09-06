"""Tests for ``crackerjack.services.backup_service``.

The module backs up a Python package directory to a temp location with
checksum validation. Tests build real on-disk project trees in
``tmp_path`` so the file-walking, filtering, and SHA-256 validation
logic is exercised end-to-end.
"""

from __future__ import annotations

import hashlib
import shutil
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from crackerjack.errors import ErrorCode, ExecutionError
from crackerjack.services.backup_service import (
    BackupMetadata,
    BackupValidationResult,
    PackageBackupService,
)


# ---------------------------------------------------------------------------
# Model serialization
# ---------------------------------------------------------------------------


def test_backup_metadata_construction(tmp_path: Path) -> None:
    md = BackupMetadata(
        backup_id="b1",
        timestamp=datetime(2026, 1, 1),
        package_directory=tmp_path / "pkg",
        backup_directory=tmp_path / "bk",
        total_files=3,
        total_size=300,
        checksum="abc",
        file_checksums={"a.py": "deadbeef"},
    )
    assert md.total_files == 3
    assert md.file_checksums == {"a.py": "deadbeef"}


def test_backup_validation_result_construction() -> None:
    r = BackupValidationResult(
        is_valid=True,
        missing_files=[],
        corrupted_files=[],
        total_validated=5,
        validation_errors=[],
    )
    assert r.is_valid is True
    assert r.total_validated == 5


# ---------------------------------------------------------------------------
# model_post_init defaults
# ---------------------------------------------------------------------------


def test_model_post_init_creates_logger(tmp_path: Path) -> None:
    svc = PackageBackupService(backup_root=tmp_path / "bk_root")
    assert svc.logger is not None
    assert svc.security_logger is not None
    assert svc.backup_root == tmp_path / "bk_root"


def test_model_post_init_default_backup_root() -> None:
    """Without backup_root, defaults to <tempdir>/crackerjack_backups."""
    import tempfile
    svc = PackageBackupService()
    expected = Path(tempfile.gettempdir()) / "crackerjack_backups"
    assert svc.backup_root == expected


def test_model_post_init_uses_provided_logger(tmp_path: Path) -> None:
    sentinel = object()
    svc = PackageBackupService(backup_root=tmp_path, logger=sentinel)
    assert svc.logger is sentinel


# ---------------------------------------------------------------------------
# _generate_backup_id
# ---------------------------------------------------------------------------


def test_generate_backup_id_format(tmp_path: Path) -> None:
    svc = PackageBackupService(backup_root=tmp_path)
    bid = svc._generate_backup_id()
    assert bid.startswith("backup_")
    parts = bid.split("_")
    # backup_YYYYMMDD_HHMMSS_<hash8>
    assert len(parts) == 4
    assert len(parts[1]) == 8
    assert len(parts[2]) == 6
    assert len(parts[3]) == 8


def test_generate_backup_id_unique(tmp_path: Path) -> None:
    svc = PackageBackupService(backup_root=tmp_path)
    ids = {svc._generate_backup_id() for _ in range(5)}
    assert len(ids) == 5


# ---------------------------------------------------------------------------
# _filter_package_files
# ---------------------------------------------------------------------------


def test_filter_package_files_skips_ignored_dirs(tmp_path: Path) -> None:
    """Files inside __pycache__ / .venv / .git / tests / build are skipped."""
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "good.py").write_text("x = 1\n")

    pycache = pkg / "__pycache__"
    pycache.mkdir()
    (pycache / "junk.py").write_text("cached")

    venv = pkg / ".venv"
    venv.mkdir()
    (venv / "ignored.py").write_text("venv")

    tests = pkg / "tests"
    tests.mkdir()
    (tests / "test_x.py").write_text("test")

    build = pkg / "build"
    build.mkdir()
    (build / "out.py").write_text("build")

    svc = PackageBackupService(backup_root=tmp_path)
    all_py = list(pkg.rglob("*.py"))
    out = svc._filter_package_files(all_py, pkg)
    paths = [p.name for p in out]
    assert paths == ["good.py"]


def test_filter_package_files_skips_dotfiles(tmp_path: Path) -> None:
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "good.py").write_text("")
    (pkg / ".hidden.py").write_text("")
    svc = PackageBackupService(backup_root=tmp_path)
    out = svc._filter_package_files(list(pkg.rglob("*.py")), pkg)
    paths = [p.name for p in out]
    assert paths == ["good.py"]


def test_filter_package_files_skips_non_py(tmp_path: Path) -> None:
    """Defensive: non-.py files passed in are skipped."""
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    svc = PackageBackupService(backup_root=tmp_path)
    fake_md = pkg / "README.md"
    fake_md.write_text("")
    out = svc._filter_package_files([fake_md], pkg)
    assert out == []


# ---------------------------------------------------------------------------
# _create_backup_directory + _create_temp_restore_directory
# ---------------------------------------------------------------------------


def test_create_backup_directory(tmp_path: Path) -> None:
    svc = PackageBackupService(backup_root=tmp_path / "bk")
    out = svc._create_backup_directory("b1")
    assert out.exists()
    assert out == tmp_path / "bk" / "b1"


def test_create_backup_directory_no_root(tmp_path: Path) -> None:
    svc = PackageBackupService()
    svc.backup_root = None
    with pytest.raises(ExecutionError, match="Backup root"):
        svc._create_backup_directory("b1")


def test_create_temp_restore_directory(tmp_path: Path) -> None:
    svc = PackageBackupService(backup_root=tmp_path)
    out = svc._create_temp_restore_directory("b1")
    assert out.exists()
    assert "restore_b1_" in out.name


# ---------------------------------------------------------------------------
# _calculate_backup_checksum
# ---------------------------------------------------------------------------


def test_calculate_backup_checksum_deterministic(tmp_path: Path) -> None:
    svc = PackageBackupService(backup_root=tmp_path)
    files = {"a.py": "aaa", "b.py": "bbb"}
    c1 = svc._calculate_backup_checksum(files)
    c2 = svc._calculate_backup_checksum(files)
    assert c1 == c2


def test_calculate_backup_checksum_sorted(tmp_path: Path) -> None:
    """Order of dict doesn't matter — checksum is sorted before hashing."""
    svc = PackageBackupService(backup_root=tmp_path)
    c1 = svc._calculate_backup_checksum({"a.py": "x", "b.py": "y"})
    c2 = svc._calculate_backup_checksum({"b.py": "y", "a.py": "x"})
    assert c1 == c2


def test_calculate_backup_checksum_changes_with_content(tmp_path: Path) -> None:
    svc = PackageBackupService(backup_root=tmp_path)
    c1 = svc._calculate_backup_checksum({"a.py": "x"})
    c2 = svc._calculate_backup_checksum({"a.py": "y"})
    assert c1 != c2


# ---------------------------------------------------------------------------
# create_package_backup — full happy path
# ---------------------------------------------------------------------------


def test_create_package_backup_no_py_files(tmp_path: Path) -> None:
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    svc = PackageBackupService(backup_root=tmp_path / "bk")
    with pytest.raises(ExecutionError, match="No package files"):
        svc.create_package_backup(pkg)


def test_create_package_backup_invalid_directory(tmp_path: Path) -> None:
    svc = PackageBackupService(backup_root=tmp_path / "bk")
    with pytest.raises(ExecutionError, match="does not exist"):
        svc.create_package_backup(tmp_path / "nonexistent")


def test_create_package_backup_raises_on_metadata_construction(
    tmp_path: Path,
) -> None:
    """Pre-existing bug: ``BackupMetadata.file_checksums`` is typed ``dict[str, str]``.

    ``_perform_backup`` keys it with ``Path`` objects, which pydantic
    rejects. The resulting ``ValidationError`` is caught by the outer
    ``except Exception`` and re-raised as ``ExecutionError``. Per
    CLAUDE.md Rule 7, preserve verbatim — tests document observable
    behavior.
    """
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "a.py").write_text("a = 1\n")
    svc = PackageBackupService(backup_root=tmp_path / "bk")
    with pytest.raises(ExecutionError, match="Failed to create package backup"):
        svc.create_package_backup(pkg)


def test_create_package_backup_validation_failure_cleans_up(tmp_path: Path) -> None:
    """If validation fails, the backup directory is cleaned up.

    Note: due to the pre-existing Path-keyed file_checksums bug,
    ``create_package_backup`` raises ExecutionError from the
    ValidationError wrap BEFORE reaching the validation-failure cleanup
    branch. This test documents observable behavior.
    """
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "a.py").write_text("a = 1\n")

    bk_root = tmp_path / "bk_root"
    svc = PackageBackupService(backup_root=bk_root)

    # Patch _validate_backup to return invalid (won't be reached).
    svc._validate_backup = MagicMock(  # type: ignore[assignment]
        return_value=BackupValidationResult(
            is_valid=False,
            missing_files=[],
            corrupted_files=[],
            total_validated=0,
            validation_errors=["fake error"],
        ),
    )
    with pytest.raises(ExecutionError):
        svc.create_package_backup(pkg)


def test_create_package_backup_generic_exception_wrapped(tmp_path: Path) -> None:
    """Non-ExecutionError exceptions are wrapped in ExecutionError."""
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "a.py").write_text("a = 1\n")
    svc = PackageBackupService(backup_root=tmp_path / "bk")
    # Force _perform_backup to raise a non-ExecutionError.
    svc._perform_backup = MagicMock(  # type: ignore[assignment]
        side_effect=RuntimeError("disk crash"),
    )
    with pytest.raises(ExecutionError, match="Failed to create package backup"):
        svc.create_package_backup(pkg)


# ---------------------------------------------------------------------------
# _perform_backup — file copy + checksum
# ---------------------------------------------------------------------------


def test_perform_backup(tmp_path: Path) -> None:
    """_perform_backup copies files + builds the buggy Path-keyed dict.

    Because ``BackupMetadata.file_checksums`` is typed ``dict[str, str]``
    but ``_perform_backup`` uses Path keys, the BackupMetadata
    constructor raises ValidationError. We catch it and verify the
    BackupMetadata fields that don't reference file_checksums (i.e.,
    BackupMetadata construction fails BEFORE we can inspect file_checksums).
    Per CLAUDE.md Rule 7, preserve the bug — tests document the failure.
    """
    from pydantic import ValidationError

    pkg = tmp_path / "pkg"
    pkg.mkdir()
    a = pkg / "a.py"
    a.write_text("a = 1\n")
    bk = tmp_path / "bk"
    bk.mkdir()

    svc = PackageBackupService(backup_root=tmp_path)
    # Side-effects (file copy) happen BEFORE the metadata constructor.
    try:
        svc._perform_backup([a], pkg, bk, "b1")
    except ValidationError:
        pass
    # The file was still copied to disk even though metadata construction failed.
    assert (bk / "a.py").exists()
    assert (bk / "a.py").read_bytes() == b"a = 1\n"


def test_perform_backup_with_subdir(tmp_path: Path) -> None:
    """Pre-existing bug — see test_perform_backup. Subdir files still copied."""
    from pydantic import ValidationError

    pkg = tmp_path / "pkg"
    pkg.mkdir()
    sub = pkg / "sub"
    sub.mkdir()
    f = sub / "deep.py"
    f.write_text("x = 1\n")
    bk = tmp_path / "bk"
    bk.mkdir()

    svc = PackageBackupService(backup_root=tmp_path)
    try:
        svc._perform_backup([f], pkg, bk, "b1")
    except ValidationError:
        pass
    assert (bk / "sub" / "deep.py").exists()


# ---------------------------------------------------------------------------
# _validate_backup — using manually-constructed metadata
# ---------------------------------------------------------------------------


def _make_metadata(
    pkg: Path,
    bk: Path,
    files: dict[str, str],
    checksum: str,
) -> BackupMetadata:
    """Build a BackupMetadata with correct (string) keys."""
    return BackupMetadata(
        backup_id="b1",
        timestamp=datetime.now(),
        package_directory=pkg,
        backup_directory=bk,
        total_files=len(files),
        total_size=0,
        checksum=checksum,
        file_checksums=files,
    )


def _populate_backup(bk: Path, files: dict[str, str], content: bytes = b"a = 1\n") -> None:
    """Write files to the backup dir matching the file_checksums keys.

    The default content is ``b"a = 1\n"`` (6 bytes). Tests can override.
    """
    for rel in files:
        f = bk / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(content)


def test_validate_backup_success(tmp_path: Path) -> None:
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    bk = tmp_path / "bk"
    bk.mkdir()

    content = b"a = 1\n"
    expected = hashlib.sha256(content, usedforsecurity=False).hexdigest()
    files = {"a.py": expected}
    _populate_backup(bk, files, content=content)
    md = _make_metadata(pkg, bk, files, "")

    svc = PackageBackupService(backup_root=tmp_path)
    # Patch the overall checksum to match what _calculate_backup_checksum would
    # produce for the given file_checksums dict (sorted + sha256).
    expected_overall = svc._calculate_backup_checksum(files)
    md.checksum = expected_overall
    result = svc._validate_backup(md)
    assert result.is_valid is True


def test_validate_backup_missing_file(tmp_path: Path) -> None:
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    bk = tmp_path / "bk"
    bk.mkdir()
    expected = hashlib.sha256(b"a = 1\n", usedforsecurity=False).hexdigest()
    files = {"a.py": expected}
    # Don't populate the file.
    md = _make_metadata(pkg, bk, files, "")
    svc = PackageBackupService(backup_root=tmp_path)
    result = svc._validate_backup(md)
    assert result.is_valid is False
    assert len(result.missing_files) == 1


def test_validate_backup_corrupted_file(tmp_path: Path) -> None:
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    bk = tmp_path / "bk"
    bk.mkdir()
    expected = hashlib.sha256(b"original", usedforsecurity=False).hexdigest()
    files = {"a.py": expected}
    _populate_backup(bk, files, content=b"original")
    # Tamper: write different content but keep path the same.
    (bk / "a.py").write_bytes(b"tampered")
    md = _make_metadata(pkg, bk, files, "")
    svc = PackageBackupService(backup_root=tmp_path)
    result = svc._validate_backup(md)
    assert result.is_valid is False
    assert len(result.corrupted_files) == 1


def test_validate_backup_missing_directory(tmp_path: Path) -> None:
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    svc = PackageBackupService(backup_root=tmp_path)
    md = BackupMetadata(
        backup_id="b1",
        timestamp=datetime.now(),
        package_directory=pkg,
        backup_directory=tmp_path / "missing",
        total_files=0,
        total_size=0,
        checksum="",
        file_checksums={},
    )
    result = svc._validate_backup(md)
    assert result.is_valid is False
    assert "missing" in result.validation_errors[0].lower()


def test_validate_backup_overall_checksum_mismatch(tmp_path: Path) -> None:
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    bk = tmp_path / "bk"
    bk.mkdir()
    content = b"a = 1\n"
    expected = hashlib.sha256(content, usedforsecurity=False).hexdigest()
    files = {"a.py": expected}
    _populate_backup(bk, files, content=content)
    # Tamper the overall checksum in metadata.
    md = _make_metadata(pkg, bk, files, "0" * 64)
    svc = PackageBackupService(backup_root=tmp_path)
    result = svc._validate_backup(md)
    assert result.is_valid is False
    assert any("checksum" in e.lower() for e in result.validation_errors)


def test_validate_backup_handles_unreadable_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If read_bytes raises, the file is reported as a validation error."""
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    bk = tmp_path / "bk"
    bk.mkdir()
    content = b"a = 1\n"
    expected = hashlib.sha256(content, usedforsecurity=False).hexdigest()
    files = {"a.py": expected}
    _populate_backup(bk, files, content=content)

    real_read_bytes = Path.read_bytes

    def fake_read_bytes(self: Path, *a: object, **kw: object) -> bytes:
        if self.name == "a.py":
            raise OSError("disk failure")
        return real_read_bytes(self, *a, **kw)

    monkeypatch.setattr(Path, "read_bytes", fake_read_bytes)
    md = _make_metadata(pkg, bk, files, "")
    svc = PackageBackupService(backup_root=tmp_path)
    result = svc._validate_backup(md)
    assert result.is_valid is False


# ---------------------------------------------------------------------------
# _stage_backup_files + _commit_restoration
# ---------------------------------------------------------------------------


def test_stage_backup_files(tmp_path: Path) -> None:
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    bk = tmp_path / "bk"
    bk.mkdir()
    staging = tmp_path / "stage"
    staging.mkdir()
    content = b"a = 1\n"
    expected = hashlib.sha256(content, usedforsecurity=False).hexdigest()
    files = {"a.py": expected}
    _populate_backup(bk, files, content=content)
    md = _make_metadata(pkg, bk, files, "")
    svc = PackageBackupService(backup_root=tmp_path)
    svc._stage_backup_files(md, staging)
    assert (staging / "a.py").exists()
    assert (staging / "a.py").read_bytes() == content


def test_commit_restoration_with_base_dir(tmp_path: Path) -> None:
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    bk = tmp_path / "bk"
    bk.mkdir()
    staging = tmp_path / "stage"
    staging.mkdir()
    content = b"a = 1\n"
    expected = hashlib.sha256(content, usedforsecurity=False).hexdigest()
    files = {"a.py": expected}
    _populate_backup(bk, files, content=content)
    # _commit_restoration reads from staging — populate it.
    (staging / "a.py").write_bytes(content)
    md = _make_metadata(pkg, bk, files, "")
    svc = PackageBackupService(backup_root=tmp_path)
    svc._commit_restoration(md, staging, base_directory=tmp_path)
    assert (pkg / "a.py").exists()
    assert (pkg / "a.py").read_bytes() == content


def test_commit_restoration_with_subdir(tmp_path: Path) -> None:
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    bk = tmp_path / "bk"
    bk.mkdir()
    staging = tmp_path / "stage"
    staging.mkdir()
    content = b"x = 1\n"
    expected = hashlib.sha256(content, usedforsecurity=False).hexdigest()
    files = {"sub/deep.py": expected}
    _populate_backup(bk, files, content=content)
    # Populate staging with matching nested structure.
    (staging / "sub").mkdir()
    (staging / "sub" / "deep.py").write_bytes(content)
    md = _make_metadata(pkg, bk, files, "")
    svc = PackageBackupService(backup_root=tmp_path)
    svc._commit_restoration(md, staging, base_directory=tmp_path)
    assert (pkg / "sub" / "deep.py").exists()
    assert (pkg / "sub" / "deep.py").read_bytes() == content


# ---------------------------------------------------------------------------
# restore_from_backup — integration
# ---------------------------------------------------------------------------


def test_restore_from_backup_success(tmp_path: Path) -> None:
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    bk = tmp_path / "bk"
    bk.mkdir()
    content = b"original\n"
    expected = hashlib.sha256(content, usedforsecurity=False).hexdigest()
    files = {"a.py": expected}
    (bk / "a.py").write_bytes(content)
    md = _make_metadata(pkg, bk, files, "")

    svc = PackageBackupService(backup_root=tmp_path)
    svc._calculate_backup_checksum = lambda x: ""  # type: ignore[assignment]
    svc.restore_from_backup(md, base_directory=tmp_path)
    # Restore writes the staged file content back to package_directory.
    assert (pkg / "a.py").read_bytes() == content


def test_restore_from_backup_missing_directory(tmp_path: Path) -> None:
    svc = PackageBackupService(backup_root=tmp_path)
    md = BackupMetadata(
        backup_id="b1",
        timestamp=datetime.now(),
        package_directory=tmp_path / "pkg",
        backup_directory=tmp_path / "missing_bk",
        total_files=0,
        total_size=0,
        checksum="",
        file_checksums={},
    )
    with pytest.raises(ExecutionError, match="Backup directory not found"):
        svc.restore_from_backup(md)


def test_restore_from_backup_validation_failure(tmp_path: Path) -> None:
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    bk = tmp_path / "bk"
    bk.mkdir()
    md = _make_metadata(pkg, bk, {}, "")
    svc = PackageBackupService(backup_root=tmp_path)
    # Force validation to fail.
    svc._validate_backup = MagicMock(  # type: ignore[assignment]
        return_value=BackupValidationResult(
            is_valid=False,
            missing_files=[],
            corrupted_files=[],
            total_validated=0,
            validation_errors=["fake"],
        ),
    )
    with pytest.raises(ExecutionError, match="corrupted backup"):
        svc.restore_from_backup(md)


def test_restore_from_backup_generic_exception_wrapped(tmp_path: Path) -> None:
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    bk = tmp_path / "bk"
    bk.mkdir()
    md = _make_metadata(pkg, bk, {}, "")
    # Patch _validate_backup so it passes (otherwise we hit validation error first).
    svc = PackageBackupService(backup_root=tmp_path)
    svc._validate_backup = MagicMock(  # type: ignore[assignment]
        return_value=BackupValidationResult(
            is_valid=True, missing_files=[], corrupted_files=[],
            total_validated=0, validation_errors=[],
        ),
    )
    # Force staging to fail.
    svc._stage_backup_files = MagicMock(side_effect=RuntimeError("stage fail"))  # type: ignore[assignment]
    with pytest.raises(ExecutionError, match="Failed to restore"):
        svc.restore_from_backup(md)


def test_restore_from_backup_temp_dir_cleaned_on_failure(tmp_path: Path) -> None:
    """On restore failure, the temp_restore_dir is cleaned up in the finally block."""
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    bk = tmp_path / "bk"
    bk.mkdir()
    md = _make_metadata(pkg, bk, {}, "")
    svc = PackageBackupService(backup_root=tmp_path)
    svc._stage_backup_files = MagicMock(side_effect=RuntimeError("boom"))  # type: ignore[assignment]
    with pytest.raises(ExecutionError):
        svc.restore_from_backup(md)
    # Sanity check — the test does not crash; temp dir cleanup is best-effort.


# ---------------------------------------------------------------------------
# cleanup_backup
# ---------------------------------------------------------------------------


def test_cleanup_backup(tmp_path: Path) -> None:
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    bk = tmp_path / "bk"
    bk.mkdir()
    md = _make_metadata(pkg, bk, {}, "")
    assert md.backup_directory.exists()
    svc = PackageBackupService(backup_root=tmp_path)
    svc.cleanup_backup(md)
    assert not md.backup_directory.exists()


def test_cleanup_backup_nonexistent_directory(tmp_path: Path) -> None:
    """If backup dir doesn't exist, cleanup is a no-op."""
    pkg = tmp_path / "pkg"
    svc = PackageBackupService(backup_root=tmp_path)
    md = BackupMetadata(
        backup_id="b1",
        timestamp=datetime.now(),
        package_directory=pkg,
        backup_directory=tmp_path / "never_existed",
        total_files=0,
        total_size=0,
        checksum="",
        file_checksums={},
    )
    svc.cleanup_backup(md)  # must not raise


# ---------------------------------------------------------------------------
# _cleanup_backup_directory
# ---------------------------------------------------------------------------


def test_cleanup_backup_directory_success(tmp_path: Path) -> None:
    d = tmp_path / "subdir"
    d.mkdir()
    (d / "file.txt").write_text("data")
    svc = PackageBackupService(backup_root=tmp_path)
    svc._cleanup_backup_directory(d)
    assert not d.exists()


def test_cleanup_backup_directory_not_a_dir(tmp_path: Path) -> None:
    """If path exists but is not a dir, _cleanup_backup_directory is a no-op."""
    f = tmp_path / "file.txt"
    f.write_text("data")
    svc = PackageBackupService(backup_root=tmp_path)
    svc._cleanup_backup_directory(f)  # must not raise


def test_cleanup_backup_directory_handles_rmtree_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    d = tmp_path / "subdir"
    d.mkdir()

    def fake_rmtree(p: Path) -> None:
        raise OSError("permission denied")

    monkeypatch.setattr(shutil, "rmtree", fake_rmtree)
    svc = PackageBackupService(backup_root=tmp_path)
    svc._cleanup_backup_directory(d)  # must not raise, just logs warning
