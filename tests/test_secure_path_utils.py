import tempfile
from pathlib import Path
from unittest.mock import Mock

import pytest

import crackerjack.services.secure_path_utils as secure_path_utils
from crackerjack.errors import ExecutionError
from crackerjack.mcp.context import MCPServerConfig
from crackerjack.services.secure_path_utils import (
    AtomicFileOperations,
    SecurePathValidator,
    SubprocessPathValidator,
)


@pytest.fixture
def security_logger(monkeypatch: pytest.MonkeyPatch) -> Mock:
    logger = Mock()
    monkeypatch.setattr(secure_path_utils, "get_security_logger", lambda: logger)
    return logger


class TestSecurePathValidator:
    """Test secure path validation functionality."""

    def test_validate_safe_path_basic(self) -> None:
        """Test basic path validation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            test_file = temp_path / "test.txt"
            test_file.write_text("test content")

            # Valid path should work
            validated = SecurePathValidator.validate_safe_path(test_file)
            assert validated.exists()
            assert validated.is_absolute()

    def test_validate_safe_path_used_by_mcp_context(self) -> None:
        """Regression test for MCP context setup with Path inputs."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            config = MCPServerConfig(project_path=temp_path)

            assert config.project_path == temp_path.resolve()

    def test_validate_safe_path_traversal_attack(self) -> None:
        """Test that path traversal attacks are blocked."""
        with tempfile.TemporaryDirectory() as temp_dir:
            Path(temp_dir)

            # Directory traversal should be blocked
            with pytest.raises(
                ExecutionError, match="Directory traversal pattern detected",
            ):
                SecurePathValidator.validate_safe_path("../../../etc/passwd")

    def test_validate_safe_path_null_byte_attack(self) -> None:
        """Test that null byte attacks are blocked."""
        with pytest.raises(ExecutionError, match="Null byte pattern detected"):
            SecurePathValidator.validate_safe_path("/test/file%00.txt")

    def test_validate_safe_path_rejects_invalid_path_format(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        def raise_value_error(cls, path: Path) -> Path:
            raise ValueError("bad path")

        monkeypatch.setattr(
            SecurePathValidator,
            "normalize_path",
            classmethod(raise_value_error),
        )

        with pytest.raises(ExecutionError, match="Invalid path format"):
            SecurePathValidator.validate_safe_path("/tmp/example")

    def test_validate_safe_path_rejects_long_path(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        def fake_normalize(cls, path: Path) -> Path:
            return Path("/" + "a" * (SecurePathValidator.MAX_PATH_LENGTH + 1))

        monkeypatch.setattr(
            SecurePathValidator,
            "normalize_path",
            classmethod(fake_normalize),
        )

        with pytest.raises(ExecutionError, match="Path too long"):
            SecurePathValidator.validate_safe_path("/tmp/example")

    def test_validate_safe_path_rejects_outside_base_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir, tempfile.TemporaryDirectory() as other_dir:
            base_path = Path(temp_dir)
            outside_path = Path(other_dir) / "file.txt"
            outside_path.write_text("data")

            with pytest.raises(ExecutionError, match="Path outside allowed directory"):
                SecurePathValidator.validate_safe_path(outside_path, base_path)

    def test_validate_safe_path_encoded_traversal(self) -> None:
        """Test that URL encoded traversal attacks are blocked."""
        with pytest.raises(
            ExecutionError, match="Directory traversal pattern detected",
        ):
            SecurePathValidator.validate_safe_path(
                "/test/%2e%2e%2f%2e%2e%2f/etc/passwd",
            )

    def test_is_within_directory(self) -> None:
        """Test directory containment validation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            test_file = temp_path / "subdir" / "test.txt"
            test_file.parent.mkdir()
            test_file.write_text("test")

            # Should be within directory
            assert SecurePathValidator.is_within_directory(test_file, temp_path)

            # Should not be within unrelated directory
            with tempfile.TemporaryDirectory() as other_dir:
                other_path = Path(other_dir)
                assert not SecurePathValidator.is_within_directory(
                    test_file, other_path,
                )

    def test_secure_path_join(self) -> None:
        """Test secure path joining."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Valid join should work
            result = SecurePathValidator.secure_path_join(
                temp_path, "subdir", "file.txt",
            )
            expected = temp_path / "subdir" / "file.txt"

            # Use resolved paths for comparison to handle macOS /private prefix
            assert result.resolve() == expected.resolve()

            # Directory traversal in join should be blocked
            with pytest.raises(
                ExecutionError, match="Directory traversal pattern detected",
            ):
                SecurePathValidator.secure_path_join(
                    temp_path, "../outside", "file.txt",
                )

    def test_secure_path_join_rejects_absolute_and_escaping_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            outside_path = temp_path.parent / "outside-secure-path-utils"
            outside_path.mkdir(exist_ok=True)

            symlink = temp_path / "escape"
            symlink.symlink_to(outside_path, target_is_directory=True)

            with pytest.raises(ExecutionError, match="Absolute path not allowed"):
                SecurePathValidator.secure_path_join(temp_path, "/tmp/absolute")

            with pytest.raises(ExecutionError, match="Joined path escapes base directory"):
                SecurePathValidator.secure_path_join(temp_path, "escape", "file.txt")

    def test_normalize_path_wraps_resolution_errors(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        def raise_os_error(cls, path: Path) -> None:
            raise OSError("boom")

        monkeypatch.setattr(
            SecurePathValidator,
            "_validate_resolved_path",
            classmethod(raise_os_error),
        )

        with pytest.raises(ExecutionError, match="Path normalization failed"):
            SecurePathValidator.normalize_path(Path("/tmp/example"))

    def test_check_malicious_patterns_handles_unicode_decode_error(
        self,
        monkeypatch: pytest.MonkeyPatch,
        security_logger: Mock,
    ) -> None:
        monkeypatch.setattr(
            secure_path_utils,
            "validate_path_security",
            lambda _path: {
                "null_bytes": [],
                "traversal_patterns": [],
                "suspicious_patterns": [],
            },
        )

        SecurePathValidator._check_malicious_patterns("%FF")

        security_logger.log_security_event.assert_not_called()

    def test_validate_resolved_path_rejects_suspicious_patterns(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(
            secure_path_utils,
            "validate_path_security",
            lambda _path: {
                "null_bytes": [],
                "traversal_patterns": [],
                "suspicious_patterns": ["detect_parent_directory_in_path"],
            },
        )

        with pytest.raises(ExecutionError, match="Parent directory reference"):
            SecurePathValidator._validate_resolved_path(Path("/tmp/example"))

    def test_validate_resolved_path_rejects_temp_traversal(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(
            secure_path_utils,
            "validate_path_security",
            lambda _path: {
                "null_bytes": [],
                "traversal_patterns": [],
                "suspicious_patterns": ["detect_suspicious_temp_traversal"],
            },
        )

        with pytest.raises(ExecutionError, match="Suspicious path pattern detected"):
            SecurePathValidator._validate_resolved_path(Path("/tmp/example"))

    def test_validate_within_base_directory_rejects_outside_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir, tempfile.TemporaryDirectory() as other_dir:
            base_path = Path(temp_dir)
            outside_path = Path(other_dir) / "child.txt"
            outside_path.write_text("data")

            with pytest.raises(ExecutionError, match="Path outside allowed directory"):
                SecurePathValidator._validate_within_base_directory(outside_path, base_path)

    def test_validate_within_base_directory_accepts_inside_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base_path = Path(temp_dir)
            inside_path = base_path / "child.txt"
            inside_path.write_text("data")

            SecurePathValidator._validate_within_base_directory(
                inside_path.resolve(),
                base_path,
            )

    def test_safe_resolve_rejects_path_that_escapes_after_resolution(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        base_path = Path("/tmp/base")

        def fake_validate_safe_path(
            cls,
            path: Path,
            base_directory: Path | None = None,
        ) -> Path:
            return base_path / "inner"

        def fake_normalize_path(cls, path: Path) -> Path:
            return Path("/etc/passwd")

        monkeypatch.setattr(
            SecurePathValidator,
            "validate_safe_path",
            classmethod(fake_validate_safe_path),
        )
        monkeypatch.setattr(
            SecurePathValidator,
            "normalize_path",
            classmethod(fake_normalize_path),
        )

        with pytest.raises(ExecutionError, match="Resolved path escapes base directory"):
            SecurePathValidator.safe_resolve(Path("ignored"), base_path)

    def test_safe_resolve_returns_resolved_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            test_file = temp_path / "child.txt"
            test_file.write_text("data")

            assert SecurePathValidator.safe_resolve(test_file) == test_file.resolve()

    def test_validate_file_size_rejects_oversized_file(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        class FakeStat:
            st_size = SecurePathValidator.MAX_FILE_SIZE + 1

        monkeypatch.setattr(Path, "stat", lambda _self: FakeStat())

        with pytest.raises(ExecutionError, match="File too large"):
            SecurePathValidator.validate_file_size(Path("/tmp/example"))

    def test_validate_file_size_wraps_oserror(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        def raise_os_error(_self: Path) -> None:
            raise OSError("stat failed")

        monkeypatch.setattr(Path, "stat", raise_os_error)

        with pytest.raises(ExecutionError, match="Cannot check file size"):
            SecurePathValidator.validate_file_size(Path("/tmp/example"))

    def test_create_secure_temp_file_wraps_oserror(
        self,
        monkeypatch: pytest.MonkeyPatch,
        security_logger: Mock,
    ) -> None:
        def raise_os_error(*_args: object, **_kwargs: object) -> None:
            raise OSError("no temp files")

        monkeypatch.setattr(tempfile, "NamedTemporaryFile", raise_os_error)

        with pytest.raises(ExecutionError, match="Failed to create secure temporary file"):
            SecurePathValidator.create_secure_temp_file(purpose="unit_testing")

        security_logger.log_temp_file_created.assert_not_called()

    def test_dangerous_components_detection(self) -> None:
        """Test detection of dangerous path components."""
        with pytest.raises(ExecutionError, match="Dangerous path component detected"):
            SecurePathValidator.validate_safe_path("/test/CON/file.txt")

        with pytest.raises(ExecutionError, match="Dangerous path component detected"):
            SecurePathValidator.validate_safe_path("/test/NUL/file.txt")

    def test_create_secure_temp_file(self) -> None:
        """Test secure temporary file creation."""
        temp_file = SecurePathValidator.create_secure_temp_file(
            suffix=".test", prefix="secure_test_", purpose="unit_testing",
        )

        try:
            assert temp_file.name.endswith(".test")
            assert "secure_test_" in temp_file.name

            # Verify file permissions (owner read/write only)
            import os
            import stat

            file_mode = os.stat(temp_file.name).st_mode
            assert stat.S_IMODE(file_mode) == 0o600

        finally:
            temp_file.close()
            Path(temp_file.name).unlink(missing_ok=True)


class TestAtomicFileOperations:
    """Test atomic file operations with security."""

    def test_atomic_write(self) -> None:
        """Test atomic file writing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            test_file = temp_path / "atomic_test.txt"
            test_content = "This is a test of atomic writing"

            # Atomic write should succeed
            AtomicFileOperations.atomic_write(test_file, test_content, temp_path)

            # File should exist with correct content
            assert test_file.exists()
            assert test_file.read_text() == test_content

    def test_atomic_backup_and_write(self) -> None:
        """Test atomic backup and write operation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            test_file = temp_path / "backup_test.txt"
            original_content = "Original content"
            new_content = "New content"

            # Create original file
            test_file.write_text(original_content)

            # Backup and write new content
            backup_path = AtomicFileOperations.atomic_backup_and_write(
                test_file, new_content, temp_path,
            )

            # Original file should have new content
            assert test_file.read_text() == new_content

            # Backup should have original content
            assert backup_path.exists()
            assert backup_path.read_text() == original_content

    def test_atomic_operations_path_validation(self) -> None:
        """Test that atomic operations validate paths securely."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Directory traversal should be blocked
            with pytest.raises(ExecutionError):
                AtomicFileOperations.atomic_write(
                    "../../../etc/passwd", "malicious content", temp_path,
                )

    def test_atomic_write_cleans_up_on_replace_error(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            target = temp_path / "atomic_failure.txt"

            temp_file = tempfile.NamedTemporaryFile(
                mode="w+b",
                suffix=".tmp",
                prefix="atomic_write_",
                dir=temp_path,
                delete=False,
            )

            def fake_create_secure_temp_file(**_kwargs: object) -> object:
                return temp_file

            def raise_replace(self: Path, target_path: Path) -> Path:
                raise OSError("replace failed")

            monkeypatch.setattr(
                SecurePathValidator,
                "create_secure_temp_file",
                staticmethod(fake_create_secure_temp_file),
            )
            monkeypatch.setattr(Path, "replace", raise_replace)

            with pytest.raises(ExecutionError, match="Atomic write failed"):
                AtomicFileOperations.atomic_write(target, "content", temp_path)

            assert not Path(temp_file.name).exists()

    def test_atomic_backup_and_write_missing_file_raises(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            with pytest.raises(ExecutionError, match="File does not exist"):
                AtomicFileOperations.atomic_backup_and_write(
                    temp_path / "missing.txt",
                    "content",
                    temp_path,
                )

    def test_atomic_backup_and_write_cleans_up_failed_backup(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            original = temp_path / "document.txt"
            original.write_text("original")
            backup = temp_path / "document.txt.backup"
            backup.write_text("stale backup")

            def fake_atomic_write(*_args: object, **_kwargs: object) -> None:
                if fake_atomic_write.calls == 0:
                    fake_atomic_write.calls += 1
                    return None
                raise RuntimeError("write failed")

            fake_atomic_write.calls = 0  # type: ignore[attr-defined]

            monkeypatch.setattr(
                AtomicFileOperations,
                "atomic_write",
                staticmethod(fake_atomic_write),
            )

            with pytest.raises(ExecutionError, match="Atomic backup and write failed"):
                AtomicFileOperations.atomic_backup_and_write(original, "updated", temp_path)

            assert not backup.exists()

    def test_validate_subprocess_cwd_paths(self, security_logger: Mock) -> None:
        assert SubprocessPathValidator.validate_subprocess_cwd(None) is None

        with pytest.raises(ExecutionError, match="Forbidden subprocess working directory"):
            SubprocessPathValidator.validate_subprocess_cwd("/etc/passwd")

        with pytest.raises(ExecutionError, match="Dangerous subprocess working directory"):
            SubprocessPathValidator.validate_subprocess_cwd("/etc/project")

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            assert SubprocessPathValidator.validate_subprocess_cwd(temp_path) == temp_path.resolve()

        assert security_logger.log_dangerous_path_detected.call_count == 2

    def test_validate_executable_path_variants(self, security_logger: Mock) -> None:
        assert SubprocessPathValidator.validate_executable_path("python") == Path("python")
        assert SubprocessPathValidator.validate_executable_path("./tool") == Path("./tool").resolve()

        with pytest.raises(ExecutionError, match="Dangerous executable blocked"):
            SubprocessPathValidator.validate_executable_path("/bin/rm")

        assert security_logger.log_dangerous_path_detected.call_count == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
