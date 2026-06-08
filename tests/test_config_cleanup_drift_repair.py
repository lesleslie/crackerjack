"""Tests focused on drift detection, repair, backup-before-write, and idempotence.

These tests extend the existing test_config_cleanup.py suite with deeper
coverage of edge cases in ConfigCleanupService, particularly:
- Backup failure and rollback
- Git dirty-tree detection
- Idempotence of cleanup operations
- Drift detection via dry-run repeatability
- Repair: running cleanup twice produces stable result
- Per-file failure paths
- Unsafe path rejection during cleanup
"""

from __future__ import annotations

import json
import shutil
import tarfile
import tempfile
import tomllib
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from rich.console import Console

from crackerjack.config.settings import (
    ConfigCleanupSettings,
    CrackerjackSettings,
)
from crackerjack.models.protocols import GitInterface
from crackerjack.services.backup_service import BackupMetadata
from crackerjack.services.config_cleanup import (
    ConfigCleanupResult,
    ConfigCleanupService,
    MergeStrategy,
)


# Reuse fixtures from main suite (pytest will find them)
# If not, define locally
@pytest.fixture
def temp_pkg_path():
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture
def mock_console():
    return Mock(spec=Console)


@pytest.fixture
def mock_git_service():
    git_service = Mock(spec=GitInterface)
    git_service.get_changed_files = Mock(return_value=[])
    return git_service


@pytest.fixture
def base_settings():
    return ConfigCleanupSettings(
        enabled=True,
        backup_before_cleanup=True,
        dry_run_by_default=False,
        merge_strategies={
            "mypy.ini": "tool.mypy",
            ".ruffignore": "tool.ruff.extend-exclude",
            ".codespell-ignore": "tool.codespell.ignore-words-list",
            "pyrightconfig.json": "tool.pyright",
        },
        config_files_to_remove=[
            ".semgrep.yml",
        ],
        cache_dirs_to_clean=[
            ".pytest_cache",
            "__pycache__",
        ],
        output_files_to_clean=[
            "coverage.json",
        ],
    )


@pytest.fixture
def service(
    temp_pkg_path: Path,
    mock_console: Mock,
    mock_git_service: Mock,
    base_settings: ConfigCleanupSettings,
):
    settings = CrackerjackSettings()
    settings.config_cleanup = base_settings
    return ConfigCleanupService(
        console=mock_console,
        pkg_path=temp_pkg_path,
        git_service=mock_git_service,
        settings=settings,
    )


# ---------------------------------------------------------------------------
# Drift detection
# ---------------------------------------------------------------------------
class TestDriftDetection:
    """Drift = 'config files have diverged from baseline pyproject.toml'."""

    def test_detects_existing_standalone_configs(
        self,
        service: ConfigCleanupService,
        temp_pkg_path: Path,
    ):
        """Detect drift: standalone config files exist on disk."""
        (temp_pkg_path / "pyproject.toml").write_text('[tool]\nname = "x"\n')
        (temp_pkg_path / "mypy.ini").write_text("[mypy]\nwarn_unused = true\n")
        (temp_pkg_path / ".ruffignore").write_text("foo/\n")

        detected = service._detect_config_files()
        names = {p.name for p in detected}
        assert names == {"mypy.ini", ".ruffignore"}

    def test_detects_no_drift_when_clean(
        self,
        service: ConfigCleanupService,
        temp_pkg_path: Path,
    ):
        """No drift: no standalone config files present."""
        (temp_pkg_path / "pyproject.toml").write_text('[tool]\nname = "x"\n')
        assert service._detect_config_files() == []

    def test_detects_cache_drift(
        self,
        service: ConfigCleanupService,
        temp_pkg_path: Path,
    ):
        (temp_pkg_path / "pyproject.toml").write_text('[tool]\nname = "x"\n')
        (temp_pkg_path / ".pytest_cache").mkdir()
        (temp_pkg_path / "__pycache__").mkdir()

        cache_dirs = service._detect_cache_dirs()
        names = {p.name for p in cache_dirs}
        assert names == {".pytest_cache", "__pycache__"}

    def test_detects_output_file_drift(
        self,
        service: ConfigCleanupService,
        temp_pkg_path: Path,
    ):
        (temp_pkg_path / "pyproject.toml").write_text('[tool]\nname = "x"\n')
        (temp_pkg_path / "coverage.json").write_text("{}")

        outputs = service._detect_output_files()
        assert len(outputs) == 1
        assert outputs[0].name == "coverage.json"

    def test_short_circuit_no_drift(
        self,
        service: ConfigCleanupService,
        temp_pkg_path: Path,
    ):
        """No drift -> no backup, no merges, success=True."""
        (temp_pkg_path / "pyproject.toml").write_text('[tool]\nname = "x"\n')

        result = service.cleanup_configs(dry_run=False)
        assert result.success is True
        assert result.configs_merged == 0
        assert result.configs_removed == 0
        assert result.cache_dirs_cleaned == 0
        assert result.output_files_cleaned == 0
        assert result.backup_metadata is None
        assert "No config files" in result.summary


# ---------------------------------------------------------------------------
# Backup before write
# ---------------------------------------------------------------------------
class TestBackupBeforeWrite:
    """Backup is created before any file is mutated."""

    def test_backup_archive_contains_files(
        self,
        service: ConfigCleanupService,
        temp_pkg_path: Path,
    ):
        (temp_pkg_path / "pyproject.toml").write_text('[tool]\nname = "x"\n')
        mypy_ini = temp_pkg_path / "mypy.ini"
        mypy_ini.write_text("[mypy]\nwarn_unused = true\n")

        result = service.cleanup_configs(dry_run=False)
        assert result.backup_metadata is not None

        archive = result.backup_metadata.backup_directory / "backup.tar.gz"
        assert archive.exists()
        assert archive.stat().st_size > 0

        # Verify archive contains the original file
        with tarfile.open(str(archive), "r|gz") as tar:
            members = tar.getnames()
        assert "mypy.ini" in members

    def test_backup_records_checksums(
        self,
        service: ConfigCleanupService,
        temp_pkg_path: Path,
    ):
        (temp_pkg_path / "pyproject.toml").write_text('[tool]\nname = "x"\n')
        (temp_pkg_path / "mypy.ini").write_text("[mypy]\nfoo = bar\n")

        result = service.cleanup_configs(dry_run=False)
        assert result.backup_metadata is not None
        assert "mypy.ini" in result.backup_metadata.file_checksums
        # Checksum is a hex sha256
        assert len(result.backup_metadata.file_checksums["mypy.ini"]) == 64

    def test_dry_run_skips_backup(
        self,
        service: ConfigCleanupService,
        temp_pkg_path: Path,
    ):
        (temp_pkg_path / "pyproject.toml").write_text('[tool]\nname = "x"\n')
        (temp_pkg_path / "mypy.ini").write_text("[mypy]\nfoo = bar\n")

        result = service.cleanup_configs(dry_run=True)
        assert result.success
        # In dry run, no backup should be created
        assert result.backup_metadata is None

    def test_backup_failure_marks_result_failed(
        self,
        service: ConfigCleanupService,
        temp_pkg_path: Path,
    ):
        (temp_pkg_path / "pyproject.toml").write_text('[tool]\nname = "x"\n')
        (temp_pkg_path / "mypy.ini").write_text("[mypy]\nfoo = bar\n")

        with patch.object(
            service,
            "_create_backup",
            return_value=None,
        ):
            result = service.cleanup_configs(dry_run=False)

        assert result.success is False
        assert "Backup creation failed" in (result.error_message or "")

    def test_backup_creation_exception_returns_none(
        self,
        service: ConfigCleanupService,
        temp_pkg_path: Path,
    ):
        """If tarball creation fails, _create_backup returns None."""
        with patch(
            "tarfile.open",
            side_effect=OSError("disk full"),
        ):
            metadata = service._create_backup(
                [temp_pkg_path / "pyproject.toml"]
            )
        assert metadata is None


# ---------------------------------------------------------------------------
# Rollback
# ---------------------------------------------------------------------------
class TestRollback:
    def test_rollback_restores_files(
        self,
        service: ConfigCleanupService,
        temp_pkg_path: Path,
    ):
        """Rollback restores files from a manually-constructed backup."""
        from datetime import datetime, UTC

        (temp_pkg_path / "pyproject.toml").write_text('[tool]\nname = "x"\n')
        mypy_ini = temp_pkg_path / "mypy.ini"
        mypy_ini.write_text("[mypy]\nfoo = bar\n")

        # Build a backup archive manually so the rollback test does not
        # depend on the broken _write_pyproject_config code path.
        backup_root = temp_pkg_path / "docs" / ".backups" / "manual"
        backup_root.mkdir(parents=True)
        archive = backup_root / "backup.tar.gz"
        with tarfile.open(str(archive), "w|gz") as tar:
            tar.add(mypy_ini, arcname="mypy.ini")

        meta = BackupMetadata(
            backup_id="manual",
            timestamp=datetime.now(UTC),
            package_directory=temp_pkg_path,
            backup_directory=backup_root,
            total_files=1,
            total_size=0,
            checksum="",
            file_checksums={},
        )

        # Simulate drift: alter file
        mypy_ini.write_text("[mypy]\nfoo = CHANGED\n")

        ok = service.rollback_cleanup(meta)
        assert ok is True
        assert "[mypy]\nfoo = bar\n" in mypy_ini.read_text()

    def test_rollback_missing_directory(
        self,
        service: ConfigCleanupService,
        temp_pkg_path: Path,
    ):
        from datetime import datetime, UTC

        fake_meta = BackupMetadata(
            backup_id="nonexistent",
            timestamp=datetime.now(UTC),
            package_directory=temp_pkg_path,
            backup_directory=temp_pkg_path / "docs" / ".backups" / "missing",
            total_files=0,
            total_size=0,
            checksum="",
            file_checksums={},
        )
        assert service.rollback_cleanup(fake_meta) is False

    def test_rollback_missing_archive(
        self,
        service: ConfigCleanupService,
        temp_pkg_path: Path,
    ):
        from datetime import datetime, UTC

        backup_dir = temp_pkg_path / "fake_backup"
        backup_dir.mkdir(parents=True)
        # No archive inside
        fake_meta = BackupMetadata(
            backup_id="x",
            timestamp=datetime.now(UTC),
            package_directory=temp_pkg_path,
            backup_directory=backup_dir,
            total_files=0,
            total_size=0,
            checksum="",
            file_checksums={},
        )
        assert service.rollback_cleanup(fake_meta) is False

    def test_rollback_exception_returns_false(
        self,
        service: ConfigCleanupService,
        temp_pkg_path: Path,
    ):
        from datetime import datetime, UTC

        backup_dir = temp_pkg_path / "broken"
        backup_dir.mkdir(parents=True)
        (backup_dir / "backup.tar.gz").write_bytes(b"not a real tarball")

        fake_meta = BackupMetadata(
            backup_id="x",
            timestamp=datetime.now(UTC),
            package_directory=temp_pkg_path,
            backup_directory=backup_dir,
            total_files=0,
            total_size=0,
            checksum="",
            file_checksums={},
        )
        assert service.rollback_cleanup(fake_meta) is False


# ---------------------------------------------------------------------------
# Idempotence / repair
# ---------------------------------------------------------------------------
class TestIdempotence:
    """Running cleanup twice must converge to a stable state.

    NOTE: The pyproject.toml merge write path is currently broken
    (ImportError on _dump_toml in config_service), so the public cleanup
    path is exercised with dry_run=True for merge assertions. The
    remove/cache/output cleanup phases do not depend on the broken write
    path and are exercised end-to-end.
    """

    def test_repair_removes_all_drift_on_first_run(
        self,
        service: ConfigCleanupService,
        temp_pkg_path: Path,
    ):
        (temp_pkg_path / "pyproject.toml").write_text('[tool]\nname = "x"\n')
        (temp_pkg_path / ".pytest_cache").mkdir()
        (temp_pkg_path / "coverage.json").write_text("{}")

        first = service.cleanup_configs(dry_run=False)
        assert first.success

        # Cache and output dirs in cleanup lists are gone
        assert not (temp_pkg_path / ".pytest_cache").exists()
        assert not (temp_pkg_path / "coverage.json").exists()
        # Backup is taken
        assert first.backup_metadata is not None

    def test_idempotent_second_run(
        self,
        service: ConfigCleanupService,
        temp_pkg_path: Path,
    ):
        (temp_pkg_path / "pyproject.toml").write_text('[tool]\nname = "x"\n')
        (temp_pkg_path / ".pytest_cache").mkdir()
        (temp_pkg_path / "coverage.json").write_text("{}")

        first = service.cleanup_configs(dry_run=False)
        second = service.cleanup_configs(dry_run=False)

        # Second run should be a no-op success
        assert first.success
        assert second.success
        assert second.cache_dirs_cleaned == 0
        assert second.output_files_cleaned == 0
        assert second.backup_metadata is None

    def test_repair_after_drift_returns(
        self,
        service: ConfigCleanupService,
        temp_pkg_path: Path,
    ):
        """If drift returns, repair re-cleans it."""
        (temp_pkg_path / "pyproject.toml").write_text('[tool]\nname = "x"\n')
        (temp_pkg_path / "coverage.json").write_text("{}")

        service.cleanup_configs(dry_run=False)
        assert not (temp_pkg_path / "coverage.json").exists()

        # Drift returns
        (temp_pkg_path / "coverage.json").write_text("{}")
        (temp_pkg_path / ".pytest_cache").mkdir()

        result = service.cleanup_configs(dry_run=False)
        assert result.success
        assert result.cache_dirs_cleaned >= 1
        assert result.output_files_cleaned >= 1
        assert not (temp_pkg_path / "coverage.json").exists()
        assert not (temp_pkg_path / ".pytest_cache").exists()

    def test_dry_run_idempotent(
        self,
        service: ConfigCleanupService,
        temp_pkg_path: Path,
    ):
        """Dry-run must not change observable state across multiple calls."""
        (temp_pkg_path / "pyproject.toml").write_text('[tool]\nname = "x"\n')
        (temp_pkg_path / "mypy.ini").write_text("[mypy]\nfoo = bar\n")

        a = service.cleanup_configs(dry_run=True)
        b = service.cleanup_configs(dry_run=True)

        assert a.success and b.success
        assert a.configs_merged == b.configs_merged
        # Files untouched
        assert (temp_pkg_path / "mypy.ini").exists()


# ---------------------------------------------------------------------------
# Precondition validation
# ---------------------------------------------------------------------------
class TestPreconditions:
    def test_missing_pyproject_blocks_cleanup(
        self,
        service: ConfigCleanupService,
        temp_pkg_path: Path,
    ):
        (temp_pkg_path / "mypy.ini").write_text("[mypy]\nfoo = bar\n")
        result = service.cleanup_configs(dry_run=False)
        assert result.success is False
        assert "pyproject.toml not found" in (result.error_message or "")

    def test_dirty_git_tree_blocks_cleanup(
        self,
        temp_pkg_path: Path,
        mock_console: Mock,
        base_settings: ConfigCleanupSettings,
    ):
        git = Mock(spec=GitInterface)
        git.get_changed_files = Mock(
            return_value=["src/unrelated.py", "README.md"]
        )
        settings = CrackerjackSettings()
        settings.config_cleanup = base_settings
        service = ConfigCleanupService(
            console=mock_console,
            pkg_path=temp_pkg_path,
            git_service=git,
            settings=settings,
        )
        (temp_pkg_path / "pyproject.toml").write_text('[tool]\nname = "x"\n')
        (temp_pkg_path / "mypy.ini").write_text("[mypy]\nfoo = bar\n")

        result = service.cleanup_configs(dry_run=False)
        assert result.success is False
        assert "uncommitted" in (result.error_message or "").lower()

    def test_dirty_git_tree_with_only_config_files_passes(
        self,
        service: ConfigCleanupService,
        temp_pkg_path: Path,
    ):
        """Changed files within the allowlist pass validation."""
        (temp_pkg_path / "pyproject.toml").write_text('[tool]\nname = "x"\n')
        (temp_pkg_path / ".pytest_cache").mkdir()
        service.git_service.get_changed_files = Mock(
            return_value=["pyproject.toml", ".gitignore"]
        )

        result = service.cleanup_configs(dry_run=False)
        assert result.success is True

    def test_dirty_git_tree_with_backup_files_ignored(
        self,
        service: ConfigCleanupService,
        temp_pkg_path: Path,
    ):
        """Files in docs/.backups/ don't block cleanup."""
        (temp_pkg_path / "pyproject.toml").write_text('[tool]\nname = "x"\n')
        (temp_pkg_path / ".pytest_cache").mkdir()
        service.git_service.get_changed_files = Mock(
            return_value=["docs/.backups/something/backup.tar.gz", "pyproject.toml"]
        )

        result = service.cleanup_configs(dry_run=False)
        assert result.success is True

    def test_git_service_exception_does_not_block(
        self,
        service: ConfigCleanupService,
        temp_pkg_path: Path,
    ):
        service.git_service.get_changed_files = Mock(
            side_effect=RuntimeError("git error")
        )
        (temp_pkg_path / "pyproject.toml").write_text('[tool]\nname = "x"\n')
        (temp_pkg_path / "mypy.ini").write_text("[mypy]\nfoo = bar\n")

        result = service.cleanup_configs(dry_run=False)
        # Exception is suppressed -> cleanup continues
        assert result.success is True


# ---------------------------------------------------------------------------
# Per-merge-strategy edge cases
# ---------------------------------------------------------------------------
class TestMergeEdgeCases:
    def test_load_pyproject_failure(
        self,
        service: ConfigCleanupService,
        temp_pkg_path: Path,
    ):
        (temp_pkg_path / "pyproject.toml").write_text("invalid { toml")
        result = service.cleanup_configs(dry_run=False)
        # Should not crash, just skip merge step
        assert isinstance(result, ConfigCleanupResult)
        assert result.configs_merged == 0

    def test_merge_single_file_exception_is_swallowed(
        self,
        service: ConfigCleanupService,
        temp_pkg_path: Path,
    ):
        """Exception in _merge_ini_file is caught; result still succeeds."""
        (temp_pkg_path / "pyproject.toml").write_text(
            '[tool.mypy]\npython_version = "3.13"\n'
        )
        mypy_ini = temp_pkg_path / "mypy.ini"
        mypy_ini.write_text("[mypy]\nwarn_unused = true\n")

        with patch.object(
            service,
            "_merge_ini_file",
            side_effect=OSError("boom"),
        ):
            config = service._load_pyproject_config()
            ok = service._merge_single_file(
                mypy_ini,
                service._get_strategy_for_file("mypy.ini"),
                config,
            )

        assert ok is False

    def test_write_pyproject_failure(
        self,
        service: ConfigCleanupService,
        temp_pkg_path: Path,
    ):
        (temp_pkg_path / "pyproject.toml").write_text(
            '[tool.mypy]\npython_version = "3.13"\n'
        )
        # Make the import inside _write_pyproject_config fail to simulate
        # a write failure (the actual _dump_toml symbol is missing today).
        import sys
        original = sys.modules.get("crackerjack.services.config_service")
        try:
            sys.modules["crackerjack.services.config_service"] = type(sys)(
                "crackerjack.services.config_service"
            )
            # Should not raise
            service._write_pyproject_config({"tool": {"mypy": {"x": 1}}})
        finally:
            if original is not None:
                sys.modules["crackerjack.services.config_service"] = original
            else:
                sys.modules.pop(
                    "crackerjack.services.config_service", None
                )

    def test_ini_converts_bool_and_int_values(
        self,
        service: ConfigCleanupService,
    ):
        assert service._convert_ini_value("true") is True
        assert service._convert_ini_value("True") is True
        assert service._convert_ini_value("yes") is True
        assert service._convert_ini_value("on") is True
        assert service._convert_ini_value("false") is False
        assert service._convert_ini_value("no") is False
        assert service._convert_ini_value("off") is False
        assert service._convert_ini_value("42") == 42
        assert service._convert_ini_value("hello") == "hello"

    def test_get_strategy_for_unknown_returns_none(
        self,
        service: ConfigCleanupService,
    ):
        assert service._get_strategy_for_file("nope.ini") is None

    def test_ini_skips_non_mypy_sections(
        self,
        service: ConfigCleanupService,
        temp_pkg_path: Path,
    ):
        """Non-[mypy] sections in INI files are not merged."""
        ini = temp_pkg_path / "mypy.ini"
        ini.write_text(
            "[mypy]\nfoo = 1\n\n[mypy-tests.*]\nbar = 2\n"
        )
        config = {"tool": {"mypy": {}}}
        merged = service._merge_ini_file(ini, config, "tool.mypy")
        # Only mypy section is merged
        assert merged["tool"]["mypy"].get("foo") == 1
        # Per-module section name should not pollute the dict
        assert "mypy-tests.*" not in merged["tool"]["mypy"]

    def test_pattern_file_strips_comments_and_blanks(
        self,
        service: ConfigCleanupService,
        temp_pkg_path: Path,
    ):
        ruff = temp_pkg_path / ".ruffignore"
        ruff.write_text(
            "# this is a comment\n"
            "tests/\n"
            "\n"
            "  \n"
            "build/\n"
        )
        config = {"tool": {"ruff": {}}}
        merged = service._merge_pattern_file(ruff, config, "tool.ruff.extend-exclude")
        patterns = merged["tool"]["ruff"]["extend-exclude"]
        assert "tests/" in patterns
        assert "build/" in patterns
        assert "this is a comment" not in patterns

    def test_pattern_file_normalizes_string_to_list(
        self,
        service: ConfigCleanupService,
        temp_pkg_path: Path,
    ):
        ruff = temp_pkg_path / ".ruffignore"
        ruff.write_text("a/\nb/\n")
        config = {"tool": {"ruff": {"extend-exclude": "existing/"}}}
        merged = service._merge_pattern_file(ruff, config, "tool.ruff.extend-exclude")
        # String should be normalized to list and combined
        result = merged["tool"]["ruff"]["extend-exclude"]
        assert isinstance(result, list)
        assert "existing/" in result
        assert "a/" in result

    def test_json_deep_merge_dicts(
        self,
        service: ConfigCleanupService,
        temp_pkg_path: Path,
    ):
        json_file = temp_pkg_path / "pyrightconfig.json"
        json_file.write_text(json.dumps({"typeCheckingMode": "basic"}))
        config = {
            "tool": {"pyright": {"include": ["src"], "reportErrors": "none"}}
        }
        merged = service._merge_json_file(json_file, config, "tool.pyright")
        pyright = merged["tool"]["pyright"]
        # Existing preserved
        assert pyright["include"] == ["src"]
        # New added
        assert pyright["typeCheckingMode"] == "basic"

    def test_json_lists_deduplicated(
        self,
        service: ConfigCleanupService,
        temp_pkg_path: Path,
    ):
        json_file = temp_pkg_path / "pyrightconfig.json"
        json_file.write_text(json.dumps({"include": ["src", "extra"]}))
        config = {"tool": {"pyright": {"include": ["src"]}}}
        merged = service._merge_json_file(json_file, config, "tool.pyright")
        # 'src' should appear once
        assert merged["tool"]["pyright"]["include"].count("src") == 1

    def test_ignore_file_joins_comma_separated(
        self,
        service: ConfigCleanupService,
        temp_pkg_path: Path,
    ):
        ci = temp_pkg_path / ".codespell-ignore"
        ci.write_text("crate\nuptodate\n")
        config = {"tool": {"codespell": {"ignore-words-list": "nd"}}}
        merged = service._merge_ignore_file(
            ci, config, "tool.codespell.ignore-words-list"
        )
        result = merged["tool"]["codespell"]["ignore-words-list"]
        assert "nd" in result
        assert "crate" in result
        assert "uptodate" in result

    def test_ignore_file_normalizes_string_to_list(
        self,
        service: ConfigCleanupService,
        temp_pkg_path: Path,
    ):
        ci = temp_pkg_path / ".codespell-ignore"
        ci.write_text("crate\n")
        config = {"tool": {"codespell": {"ignore-words-list": "nd"}}}
        merged = service._merge_ignore_file(
            ci, config, "tool.codespell.ignore-words-list"
        )
        words = merged["tool"]["codespell"]["ignore-words-list"]
        # Implementation joins back into a single string
        assert "nd" in words
        assert "crate" in words

    def test_target_section_auto_creates_nested(
        self,
        service: ConfigCleanupService,
    ):
        config: dict = {}
        result = service._get_target_section(config, "tool.ruff.lint")
        assert isinstance(result, dict)
        assert config["tool"]["ruff"]["lint"] is result


# ---------------------------------------------------------------------------
# Remove / cleanup with edge cases
# ---------------------------------------------------------------------------
class TestRemoveStandaloneConfigs:
    def test_unsafe_path_skipped(
        self,
        service: ConfigCleanupService,
        temp_pkg_path: Path,
    ):
        (temp_pkg_path / "pyproject.toml").write_text('[tool]\nname = "x"\n')
        semgrep = temp_pkg_path / ".semgrep.yml"
        semgrep.write_text("rules: []\n")

        with patch.object(
            service.path_validator,
            "validate_safe_path",
            return_value=False,
        ):
            result = service._remove_standalone_configs(
                [semgrep], dry_run=False
            )

        assert result == 0
        assert semgrep.exists()

    def test_remove_failure_swallowed(
        self,
        service: ConfigCleanupService,
        temp_pkg_path: Path,
    ):
        (temp_pkg_path / "pyproject.toml").write_text('[tool]\nname = "x"\n')
        semgrep = temp_pkg_path / ".semgrep.yml"
        semgrep.write_text("rules: []\n")

        # Inject a failing unlink call via the service's remove path.
        # Patch shutil/os.unlink to raise.
        with patch(
            "pathlib.Path.unlink",
            side_effect=OSError("permission denied"),
        ):
            result = service._remove_standalone_configs(
                [semgrep], dry_run=False
            )
        assert result == 0


class TestCleanupCacheDirsEdgeCases:
    def test_unsafe_cache_path(
        self,
        service: ConfigCleanupService,
        temp_pkg_path: Path,
    ):
        cache = temp_pkg_path / ".pytest_cache"
        cache.mkdir()
        (cache / "x").write_text("y")

        with patch.object(
            service.path_validator,
            "validate_safe_path",
            return_value=False,
        ):
            result = service._cleanup_cache_dirs([cache], dry_run=False)

        assert result == 0
        assert cache.exists()

    def test_cache_rmtree_exception(
        self,
        service: ConfigCleanupService,
        temp_pkg_path: Path,
    ):
        cache = temp_pkg_path / ".pytest_cache"
        cache.mkdir()

        with patch(
            "shutil.rmtree", side_effect=OSError("nope")
        ):
            result = service._cleanup_cache_dirs([cache], dry_run=False)
        assert result == 0


class TestCleanupOutputFilesEdgeCases:
    def test_unsafe_output_path(
        self,
        service: ConfigCleanupService,
        temp_pkg_path: Path,
    ):
        out = temp_pkg_path / "coverage.json"
        out.write_text("{}")

        with patch.object(
            service.path_validator,
            "validate_safe_path",
            return_value=False,
        ):
            result = service._cleanup_output_files([out], dry_run=False)

        assert result == 0
        assert out.exists()

    def test_output_unlink_exception(
        self,
        service: ConfigCleanupService,
        temp_pkg_path: Path,
    ):
        out = temp_pkg_path / "coverage.json"
        out.write_text("{}")

        with patch(
            "pathlib.Path.unlink",
            side_effect=OSError("locked"),
        ):
            result = service._cleanup_output_files([out], dry_run=False)
        assert result == 0


# ---------------------------------------------------------------------------
# Settings loader
# ---------------------------------------------------------------------------
class TestSettingsLoader:
    def test_default_settings_loaded_when_none_provided(
        self,
        temp_pkg_path: Path,
        mock_console: Mock,
        mock_git_service: Mock,
    ):
        with patch(
            "crackerjack.config.load_settings",
            return_value=CrackerjackSettings(),
        ):
            service = ConfigCleanupService(
                console=mock_console,
                pkg_path=temp_pkg_path,
                git_service=mock_git_service,
                settings=None,
            )
        assert service.settings is not None
        assert service._merge_strategies  # populated from default settings


# ---------------------------------------------------------------------------
# Smart gitignore edge cases
# ---------------------------------------------------------------------------
class TestSmartGitignoreEdgeCases:
    def test_gitignore_create_failure(
        self,
        service: ConfigCleanupService,
        temp_pkg_path: Path,
    ):
        # Force the write to fail
        with patch.object(
            Path, "write_text", side_effect=OSError("perm denied")
        ):
            result = service._smart_merge_gitignore(dry_run=False)
        assert result is False

    def test_gitignore_merge_exception(
        self,
        service: ConfigCleanupService,
        temp_pkg_path: Path,
    ):
        gi = temp_pkg_path / ".gitignore"
        gi.write_text("foo\n")

        with patch(
            "crackerjack.services.config_merge.ConfigMergeService",
            side_effect=ImportError("nope"),
        ):
            result = service._smart_merge_gitignore(dry_run=False)
        assert result is False


# ---------------------------------------------------------------------------
# Display completion
# ---------------------------------------------------------------------------
class TestDisplayCompletion:
    def test_displays_failure_block(
        self,
        service: ConfigCleanupService,
        mock_console: Mock,
    ):
        result = ConfigCleanupResult(
            success=False,
            error_message="something failed",
        )
        service._display_completion(result)
        # print was called with at least one error-related string
        assert any(
            "Config cleanup failed" in str(c)
            for c in mock_console.print.call_args_list
        )

    def test_displays_success_block_when_merged(
        self,
        service: ConfigCleanupService,
        mock_console: Mock,
    ):
        result = ConfigCleanupResult(
            success=True,
            configs_merged=2,
        )
        service._display_completion(result)
        assert any(
            "Config cleanup completed" in str(c)
            for c in mock_console.print.call_args_list
        )

    def test_displays_no_files_message(
        self,
        service: ConfigCleanupService,
        mock_console: Mock,
    ):
        result = ConfigCleanupResult(
            success=True,
            configs_merged=0,
            configs_removed=0,
            cache_dirs_cleaned=0,
            output_files_cleaned=0,
        )
        service._display_completion(result)
        assert any(
            "No files to clean" in str(c)
            for c in mock_console.print.call_args_list
        )


# ---------------------------------------------------------------------------
# Summary generation
# ---------------------------------------------------------------------------
class TestSummaryGeneration:
    def test_summary_includes_all_sections(
        self,
        service: ConfigCleanupService,
        temp_pkg_path: Path,
    ):
        result = ConfigCleanupResult(
            success=True,
            configs_merged=1,
            configs_removed=2,
            cache_dirs_cleaned=3,
            output_files_cleaned=4,
            merged_files={"mypy.ini": "tool.mypy"},
        )
        summary = service._generate_summary(result)
        assert "Configs merged: 1" in summary
        assert "Configs removed: 2" in summary
        assert "Cache dirs cleaned: 3" in summary
        assert "Output files cleaned: 4" in summary
        assert "mypy.ini" in summary
        assert "tool.mypy" in summary


# ---------------------------------------------------------------------------
# _handle_dry_run_merge
# ---------------------------------------------------------------------------
class TestHandleDryRunMerge:
    def test_prints_target(
        self,
        service: ConfigCleanupService,
        mock_console: Mock,
    ):
        strategy = MergeStrategy(
            filename="mypy.ini",
            target_section="tool.mypy",
            merge_type="ini_flatten",
        )
        service._handle_dry_run_merge("mypy.ini", strategy)
        mock_console.print.assert_called_once()
        msg = str(mock_console.print.call_args)
        assert "mypy.ini" in msg
        assert "tool.mypy" in msg

    def test_dry_run_remove_message(
        self,
        service: ConfigCleanupService,
        mock_console: Mock,
    ):
        """Dry-run path for `_remove_standalone_configs` prints intent."""
        (temp_pkg_path := service.pkg_path / "dummy")  # noqa: F841
        cfg = service.pkg_path / ".semgrep.yml"
        cfg.write_text("rules: []\n")
        result = service._remove_standalone_configs([cfg], dry_run=True)
        assert result == 1
        # File should still exist after dry run
        assert cfg.exists()
        # Print should mention intent
        assert any(
            "Would remove" in str(c) for c in mock_console.print.call_args_list
        )

    def test_dry_run_output_clean_message(
        self,
        service: ConfigCleanupService,
        mock_console: Mock,
    ):
        out = service.pkg_path / "coverage.json"
        out.write_text("{}")
        result = service._cleanup_output_files([out], dry_run=True)
        assert result == 1
        assert out.exists()
        assert any(
            "Would clean" in str(c) for c in mock_console.print.call_args_list
        )

    def test_dry_run_cache_clean_message(
        self,
        service: ConfigCleanupService,
        mock_console: Mock,
    ):
        cache = service.pkg_path / ".pytest_cache"
        cache.mkdir()
        result = service._cleanup_cache_dirs([cache], dry_run=True)
        assert result == 1
        assert cache.exists()


class TestTopLevelException:
    def test_top_level_exception_caught(
        self,
        service: ConfigCleanupService,
        temp_pkg_path: Path,
    ):
        """If an unexpected error occurs mid-cleanup, the result is failure."""
        (temp_pkg_path / "pyproject.toml").write_text('[tool]\nname = "x"\n')
        with patch.object(
            service,
            "_detect_config_files",
            side_effect=RuntimeError("boom"),
        ):
            result = service.cleanup_configs(dry_run=False)
        assert result.success is False
        assert "boom" in (result.error_message or "")


class TestBuildMergeStrategies:
    def test_build_strategies_classifies_filenames(
        self,
        service: ConfigCleanupService,
    ):
        strategies = service._build_merge_strategies()
        # Should have at least one strategy from base settings
        assert len(strategies) >= 1
        # mypy.ini should be ini_flatten
        mypy = next((s for s in strategies if s.filename == "mypy.ini"), None)
        assert mypy is not None
        assert mypy.merge_type == "ini_flatten"


class TestBackupRootNone:
    def test_create_backup_when_root_none(
        self,
        temp_pkg_path: Path,
        mock_console: Mock,
        mock_git_service: Mock,
        base_settings: ConfigCleanupSettings,
    ):
        """When backup_root is None, _create_backup returns None."""
        from crackerjack.services.backup_service import PackageBackupService

        settings = CrackerjackSettings()
        settings.config_cleanup = base_settings
        service = ConfigCleanupService(
            console=mock_console,
            pkg_path=temp_pkg_path,
            git_service=mock_git_service,
            settings=settings,
        )
        service.backup_service = PackageBackupService(backup_root=None)
        result = service._create_backup([temp_pkg_path / "x.txt"])
        assert result is None


class TestRemoveDryRunPath:
    def test_remove_dry_run_no_validation(
        self,
        service: ConfigCleanupService,
        temp_pkg_path: Path,
    ):
        cfg = temp_pkg_path / ".semgrep.yml"
        cfg.write_text("rules: []\n")
        result = service._remove_standalone_configs([cfg], dry_run=True)
        assert result == 1
        assert cfg.exists()


class TestCleanupOutputDryRun:
    def test_output_dry_run_path(
        self,
        service: ConfigCleanupService,
        temp_pkg_path: Path,
    ):
        out = temp_pkg_path / "coverage.json"
        out.write_text("{}")
        result = service._cleanup_output_files([out], dry_run=True)
        assert result == 1
        assert out.exists()


class TestCacheDryRun:
    def test_cache_dry_run_path(
        self,
        service: ConfigCleanupService,
        temp_pkg_path: Path,
    ):
        cache = temp_pkg_path / ".pytest_cache"
        cache.mkdir()
        result = service._cleanup_cache_dirs([cache], dry_run=True)
        assert result == 1
        assert cache.exists()


# ---------------------------------------------------------------------------
# Property: idempotence under repeated cleanup
# ---------------------------------------------------------------------------
class TestPropertyIdempotence:
    @pytest.mark.property
    def test_repeated_cleanup_converges(
        self,
        service: ConfigCleanupService,
        temp_pkg_path: Path,
    ):
        """Property: after N runs, the cache/output cleanup state is stable."""
        (temp_pkg_path / "pyproject.toml").write_text('[tool]\nname = "x"\n')
        (temp_pkg_path / ".pytest_cache").mkdir()
        (temp_pkg_path / "coverage.json").write_text("{}")

        for _ in range(3):
            r = service.cleanup_configs(dry_run=False)
            assert r.success

        # After 3 runs, cache/output state is still clean
        assert not (temp_pkg_path / ".pytest_cache").exists()
        assert not (temp_pkg_path / "coverage.json").exists()


# ---------------------------------------------------------------------------
# _calculate_backup_checksum
# ---------------------------------------------------------------------------
class TestBackupChecksum:
    def test_checksum_deterministic(
        self,
        service: ConfigCleanupService,
    ):
        checksums = {"a.txt": "abc", "b.txt": "def"}
        c1 = service._calculate_backup_checksum(checksums)
        c2 = service._calculate_backup_checksum(checksums)
        assert c1 == c2
        assert len(c1) == 64  # sha256 hex

    def test_checksum_order_independent(
        self,
        service: ConfigCleanupService,
    ):
        # Order shouldn't matter — sorted internally
        c1 = service._calculate_backup_checksum({"a": "1", "b": "2"})
        c2 = service._calculate_backup_checksum({"b": "2", "a": "1"})
        assert c1 == c2

    def test_checksum_changes_with_content(
        self,
        service: ConfigCleanupService,
    ):
        c1 = service._calculate_backup_checksum({"a": "1"})
        c2 = service._calculate_backup_checksum({"a": "2"})
        assert c1 != c2


# ---------------------------------------------------------------------------
# _generate_backup_id
# ---------------------------------------------------------------------------
class TestBackupId:
    def test_backup_id_format(
        self,
        service: ConfigCleanupService,
    ):
        bid = service._generate_backup_id()
        # YYYYMMDD-HHMMSS
        assert len(bid) == 15
        assert bid[8] == "-"
