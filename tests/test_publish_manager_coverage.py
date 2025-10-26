import os
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from typing import Any

import pytest

from crackerjack.managers.publish_manager import PublishManagerImpl
from acb.depends import depends
from acb.console import Console


# Module-level fixtures available to all test classes
@pytest.fixture
def mock_console() -> MagicMock:
    """Mock Console for all tests."""
    return MagicMock(spec=Console)


@pytest.fixture
def mock_git_service() -> MagicMock:
    """Mock GitServiceProtocol for all tests."""
    return MagicMock()


@pytest.fixture
def mock_version_analyzer() -> MagicMock:
    """Mock VersionAnalyzerProtocol for all tests."""
    return MagicMock()


@pytest.fixture
def mock_changelog_generator() -> MagicMock:
    """Mock ChangelogGeneratorProtocol for all tests."""
    return MagicMock()


@pytest.fixture
def mock_filesystem() -> MagicMock:
    """Mock FileSystemInterface for all tests."""
    return MagicMock()


@pytest.fixture
def mock_security_service() -> MagicMock:
    """Mock SecurityServiceProtocol for all tests."""
    return MagicMock()


@pytest.fixture
def mock_regex_patterns() -> MagicMock:
    """Mock RegexPatternsProtocol for all tests."""
    return MagicMock()


@pytest.fixture
def temp_pkg_path() -> Path:
    """Temporary package path for all tests."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture
def publish_manager_di_context(
    mock_console: MagicMock,
    mock_git_service: MagicMock,
    mock_version_analyzer: MagicMock,
    mock_changelog_generator: MagicMock,
    mock_filesystem: MagicMock,
    mock_security_service: MagicMock,
    mock_regex_patterns: MagicMock,
    temp_pkg_path: Path,
):
    """Set up DI context for PublishManagerImpl testing."""
    from crackerjack.models.protocols import (
        ChangelogGeneratorProtocol,
        FileSystemInterface,
        GitServiceProtocol,
        RegexPatternsProtocol,
        SecurityServiceProtocol,
        VersionAnalyzerProtocol,
    )
    from acb.logger import Logger

    injection_map = {
        Console: mock_console,
        Logger: MagicMock(spec=Logger),
        GitServiceProtocol: mock_git_service,
        VersionAnalyzerProtocol: mock_version_analyzer,
        ChangelogGeneratorProtocol: mock_changelog_generator,
        FileSystemInterface: mock_filesystem,
        SecurityServiceProtocol: mock_security_service,
        RegexPatternsProtocol: mock_regex_patterns,
        Path: temp_pkg_path,
    }

    # Save original values
    original_values = {}
    try:
        # Register all dependencies
        for dep_type, dep_value in injection_map.items():
            try:
                original_values[dep_type] = depends.get_sync(dep_type)
            except Exception:
                original_values[dep_type] = None
            depends.set(dep_type, dep_value)

        yield injection_map, temp_pkg_path
    finally:
        # Restore original values after test completes
        for dep_type, original_value in original_values.items():
            if original_value is not None:
                depends.set(dep_type, original_value)


def create_publish_manager(
    mock_console: MagicMock,
    mock_git_service: MagicMock,
    mock_version_analyzer: MagicMock,
    mock_changelog_generator: MagicMock,
    mock_filesystem: MagicMock,
    mock_security_service: MagicMock,
    mock_regex_patterns: MagicMock,
    temp_pkg_path: Path,
    dry_run: bool = False,
) -> PublishManagerImpl:
    """Helper function to create PublishManagerImpl with mocked dependencies."""
    return PublishManagerImpl(
        git_service=mock_git_service,
        version_analyzer=mock_version_analyzer,
        changelog_generator=mock_changelog_generator,
        filesystem=mock_filesystem,
        security=mock_security_service,
        regex_patterns=mock_regex_patterns,
        console=mock_console,
        pkg_path=temp_pkg_path,
        dry_run=dry_run,
    )


class TestPublishManagerCore:
    @pytest.fixture
    def publish_manager(
        self,
        publish_manager_di_context,
        mock_console,
        mock_git_service,
        mock_version_analyzer,
        mock_changelog_generator,
        mock_filesystem,
        mock_security_service,
        mock_regex_patterns,
        temp_pkg_path,
    ):
        """Create PublishManagerImpl with mocked dependencies."""
        injection_map, pkg_path = publish_manager_di_context
        return create_publish_manager(
            mock_console=mock_console,
            mock_git_service=mock_git_service,
            mock_version_analyzer=mock_version_analyzer,
            mock_changelog_generator=mock_changelog_generator,
            mock_filesystem=mock_filesystem,
            mock_security_service=mock_security_service,
            mock_regex_patterns=mock_regex_patterns,
            temp_pkg_path=temp_pkg_path,
            dry_run=False,
        )

    @pytest.fixture
    def dry_run_manager(
        self,
        publish_manager_di_context,
        mock_console,
        mock_git_service,
        mock_version_analyzer,
        mock_changelog_generator,
        mock_filesystem,
        mock_security_service,
        mock_regex_patterns,
        temp_pkg_path,
    ):
        """Create PublishManagerImpl in dry-run mode with mocked dependencies."""
        injection_map, pkg_path = publish_manager_di_context
        return create_publish_manager(
            mock_console=mock_console,
            mock_git_service=mock_git_service,
            mock_version_analyzer=mock_version_analyzer,
            mock_changelog_generator=mock_changelog_generator,
            mock_filesystem=mock_filesystem,
            mock_security_service=mock_security_service,
            mock_regex_patterns=mock_regex_patterns,
            temp_pkg_path=temp_pkg_path,
            dry_run=True,
        )

    def test_initialization(self, publish_manager, mock_console, temp_pkg_path) -> None:
        assert publish_manager.console == mock_console
        assert publish_manager.pkg_path == temp_pkg_path
        assert publish_manager.dry_run is False
        assert publish_manager.filesystem is not None
        assert publish_manager.security is not None

    def test_initialization_dry_run(
        self,
        dry_run_manager,
        mock_console,
        temp_pkg_path,
    ) -> None:
        assert dry_run_manager.console == mock_console
        assert dry_run_manager.pkg_path == temp_pkg_path
        assert dry_run_manager.dry_run is True

    @patch("subprocess.run")
    def test_run_command_success(self, mock_run, publish_manager) -> None:
        mock_result = Mock()
        mock_result.stdout = "success output"
        mock_result.stderr = ""
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        result = publish_manager._run_command(["echo", "test"])

        assert result == mock_result
        mock_run.assert_called_once()

    @patch("subprocess.run")
    def test_run_command_with_token_masking(self, mock_run, publish_manager) -> None:
        mock_result = Mock()
        mock_result.stdout = "pypi - abcd1234efgh5678"
        mock_result.stderr = "Error with token pypi - abcd1234efgh5678"
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        with patch.object(publish_manager.security, "mask_tokens") as mock_mask:
            mock_mask.side_effect = lambda x: x.replace(
                "pypi - abcd1234efgh5678",
                "pypi - **** ",
            )

            publish_manager._run_command(["test"])

            mock_mask.assert_called()

    def test_get_current_version_success(self, publish_manager) -> None:
        pyproject_content = """
[project]
name = "test - package"
version = "1.2.3"
description = "Test package"
"""
        with patch.object(
            publish_manager.filesystem,
            "read_file",
            return_value=pyproject_content,
        ):
            version = publish_manager._get_current_version()
            assert version == "1.2.3"

    def test_get_current_version_missing_file(self, publish_manager) -> None:
        version = publish_manager._get_current_version()
        assert version is None

    def test_get_current_version_invalid_content(self, publish_manager) -> None:
        with patch.object(
            publish_manager.filesystem,
            "read_file",
            return_value="invalid toml [[[",
        ):
            version = publish_manager._get_current_version()
            assert version is None

    def test_calculate_next_version_patch(self, publish_manager) -> None:
        result = publish_manager._calculate_next_version("1.2.3", "patch")
        assert result == "1.2.4"

    def test_calculate_next_version_minor(self, publish_manager) -> None:
        result = publish_manager._calculate_next_version("1.2.3", "minor")
        assert result == "1.3.0"

    def test_calculate_next_version_major(self, publish_manager) -> None:
        result = publish_manager._calculate_next_version("1.2.3", "major")
        assert result == "2.0.0"

    def test_calculate_next_version_invalid_type(self, publish_manager) -> None:
        with pytest.raises(ValueError, match="Invalid bump type"):
            publish_manager._calculate_next_version("1.2.3", "invalid")

    def test_calculate_next_version_invalid_format(self, publish_manager) -> None:
        with pytest.raises(ValueError, match="Invalid version format"):
            publish_manager._calculate_next_version("1.2", "patch")

    def test_update_version_in_file_success(self, publish_manager) -> None:
        original_content = 'version = "1.2.3"'
        expected_content = 'version = "1.2.4"'

        with (
            patch.object(
                publish_manager.filesystem,
                "read_file",
                return_value=original_content,
            ),
            patch.object(publish_manager.filesystem, "write_file") as mock_write,
        ):
            result = publish_manager._update_version_in_file("1.2.4")

            assert result is True
            mock_write.assert_called_once_with(
                publish_manager.pkg_path / "pyproject.toml",
                expected_content,
            )

    def test_update_version_in_file_dry_run(self, dry_run_manager) -> None:
        original_content = 'version = "1.2.3"'

        with (
            patch.object(
                dry_run_manager.filesystem,
                "read_file",
                return_value=original_content,
            ),
            patch.object(dry_run_manager.filesystem, "write_file") as mock_write,
        ):
            result = dry_run_manager._update_version_in_file("1.2.4")

            assert result is True
            mock_write.assert_not_called()

    def test_update_version_in_file_pattern_not_found(self, publish_manager) -> None:
        original_content = 'name = "test - package"'

        with patch.object(
            publish_manager.filesystem,
            "read_file",
            return_value=original_content,
        ):
            result = publish_manager._update_version_in_file("1.2.4")
            assert result is False

    def test_update_version_in_file_error(self, publish_manager) -> None:
        with patch.object(
            publish_manager.filesystem,
            "read_file",
            side_effect=Exception("File error"),
        ):
            result = publish_manager._update_version_in_file("1.2.4")
            assert result is False


class TestPublishManagerVersionBumping:
    @pytest.fixture
    def publish_manager(
        self,
        publish_manager_di_context,
        mock_console,
        mock_git_service,
        mock_version_analyzer,
        mock_changelog_generator,
        mock_filesystem,
        mock_security_service,
        mock_regex_patterns,
        temp_pkg_path,
    ):
        """Create PublishManagerImpl with mocked dependencies."""
        injection_map, pkg_path = publish_manager_di_context
        return create_publish_manager(
            mock_console=mock_console,
            mock_git_service=mock_git_service,
            mock_version_analyzer=mock_version_analyzer,
            mock_changelog_generator=mock_changelog_generator,
            mock_filesystem=mock_filesystem,
            mock_security_service=mock_security_service,
            mock_regex_patterns=mock_regex_patterns,
            temp_pkg_path=temp_pkg_path,
            dry_run=False,
        )

    def test_bump_version_success(self, publish_manager) -> None:
        with (
            patch.object(
                publish_manager,
                "_get_current_version",
                return_value="1.2.3",
            ),
            patch.object(
                publish_manager,
                "_update_version_in_file",
                return_value=True,
            ),
        ):
            result = publish_manager.bump_version("patch")
            assert result == "1.2.4"

    def test_bump_version_no_current_version(self, publish_manager) -> None:
        with patch.object(publish_manager, "_get_current_version", return_value=None):
            with pytest.raises(ValueError, match="Cannot determine current version"):
                publish_manager.bump_version("patch")

    def test_bump_version_update_failure(self, publish_manager) -> None:
        with (
            patch.object(
                publish_manager,
                "_get_current_version",
                return_value="1.2.3",
            ),
            patch.object(
                publish_manager,
                "_update_version_in_file",
                return_value=False,
            ),
            pytest.raises(
                ValueError,
                match="Failed to update version in file",
            ),
        ):
            publish_manager.bump_version("patch")

    def test_bump_version_dry_run(self, publish_manager) -> None:
        publish_manager.dry_run = True

        with patch.object(
            publish_manager,
            "_get_current_version",
            return_value="1.2.3",
        ):
            result = publish_manager.bump_version("minor")
            assert result == "1.3.0"


class TestPublishManagerAuthentication:
    @pytest.fixture
    def publish_manager(
        self,
        publish_manager_di_context,
        mock_console,
        mock_git_service,
        mock_version_analyzer,
        mock_changelog_generator,
        mock_filesystem,
        mock_security_service,
        mock_regex_patterns,
        temp_pkg_path,
    ):
        """Create PublishManagerImpl with mocked dependencies."""
        injection_map, pkg_path = publish_manager_di_context
        return create_publish_manager(
            mock_console=mock_console,
            mock_git_service=mock_git_service,
            mock_version_analyzer=mock_version_analyzer,
            mock_changelog_generator=mock_changelog_generator,
            mock_filesystem=mock_filesystem,
            mock_security_service=mock_security_service,
            mock_regex_patterns=mock_regex_patterns,
            temp_pkg_path=temp_pkg_path,
            dry_run=False,
        )

    @patch.dict(os.environ, {"UV_PUBLISH_TOKEN": "pypi - valid - token"})
    def test_check_env_token_auth_valid(self, publish_manager) -> None:
        with patch.object(
            publish_manager.security,
            "validate_token_format",
            return_value=True,
        ):
            result = publish_manager._check_env_token_auth()
            assert result == "Environment variable (UV_PUBLISH_TOKEN)"

    @patch.dict(os.environ, {"UV_PUBLISH_TOKEN": "invalid - token"})
    def test_check_env_token_auth_invalid(self, publish_manager) -> None:
        with patch.object(
            publish_manager.security,
            "validate_token_format",
            return_value=False,
        ):
            result = publish_manager._check_env_token_auth()
            assert result is None

    @patch.dict(os.environ, {}, clear=True)
    def test_check_env_token_auth_missing(self, publish_manager) -> None:
        result = publish_manager._check_env_token_auth()
        assert result is None

    def test_check_keyring_auth_success(self, publish_manager) -> None:
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "pypi - keyring - token"

        with patch.object(publish_manager, "_run_command", return_value=mock_result):
            with patch.object(
                publish_manager.security,
                "validate_token_format",
                return_value=True,
            ):
                result = publish_manager._check_keyring_auth()
                assert result == "Keyring storage"

    def test_check_keyring_auth_failure(self, publish_manager) -> None:
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stdout = ""

        with patch.object(publish_manager, "_run_command", return_value=mock_result):
            result = publish_manager._check_keyring_auth()
            assert result is None

    def test_check_keyring_auth_exception(self, publish_manager) -> None:
        with patch.object(
            publish_manager,
            "_run_command",
            side_effect=subprocess.SubprocessError,
        ):
            result = publish_manager._check_keyring_auth()
            assert result is None

    def test_validate_auth_success(self, publish_manager) -> None:
        with patch.object(
            publish_manager,
            "_collect_auth_methods",
            return_value=["Environment variable"],
        ):
            result = publish_manager.validate_auth()
            assert result is True

    def test_validate_auth_failure(self, publish_manager) -> None:
        with patch.object(publish_manager, "_collect_auth_methods", return_value=[]):
            result = publish_manager.validate_auth()
            assert result is False

    def test_report_auth_status_with_methods(self, publish_manager) -> None:
        auth_methods = ["Environment variable", "Keyring storage"]
        result = publish_manager._report_auth_status(auth_methods)
        assert result is True

    def test_report_auth_status_no_methods(self, publish_manager) -> None:
        auth_methods = []
        result = publish_manager._report_auth_status(auth_methods)
        assert result is False

    def test_display_auth_setup_instructions(self, publish_manager) -> None:
        publish_manager._display_auth_setup_instructions()

        assert publish_manager.console.print.called


class TestPublishManagerBuildPackage:
    @pytest.fixture
    def publish_manager(
        self,
        publish_manager_di_context,
        mock_console,
        mock_git_service,
        mock_version_analyzer,
        mock_changelog_generator,
        mock_filesystem,
        mock_security_service,
        mock_regex_patterns,
        temp_pkg_path,
    ):
        """Create PublishManagerImpl with mocked dependencies."""
        injection_map, pkg_path = publish_manager_di_context
        return create_publish_manager(
            mock_console=mock_console,
            mock_git_service=mock_git_service,
            mock_version_analyzer=mock_version_analyzer,
            mock_changelog_generator=mock_changelog_generator,
            mock_filesystem=mock_filesystem,
            mock_security_service=mock_security_service,
            mock_regex_patterns=mock_regex_patterns,
            temp_pkg_path=temp_pkg_path,
            dry_run=False,
        )

    def test_build_package_success(self, publish_manager) -> None:
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stderr = ""

        with patch.object(publish_manager, "_run_command", return_value=mock_result):
            with patch.object(publish_manager, "_display_build_artifacts"):
                result = publish_manager.build_package()
                assert result is True

    def test_build_package_failure(self, publish_manager) -> None:
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stderr = "Build failed"

        with patch.object(publish_manager, "_run_command", return_value=mock_result):
            result = publish_manager.build_package()
            assert result is False

    def test_build_package_dry_run(self, publish_manager) -> None:
        publish_manager.dry_run = True
        result = publish_manager.build_package()
        assert result is True

    def test_build_package_exception(self, publish_manager) -> None:
        with patch.object(
            publish_manager,
            "_run_command",
            side_effect=Exception("Build error"),
        ):
            result = publish_manager.build_package()
            assert result is False

    def test_display_build_artifacts(self, publish_manager, temp_pkg_path) -> None:
        publish_manager.pkg_path = temp_pkg_path
        dist_dir = temp_pkg_path / "dist"
        dist_dir.mkdir()

        (dist_dir / "package - 1.0.0.tar.gz").write_text("test")
        (dist_dir / "package - 1.0.0 - py3 - none - any.whl").write_text("test")

        publish_manager._display_build_artifacts()

    def test_display_build_artifacts_no_dist(self, publish_manager) -> None:
        publish_manager._display_build_artifacts()

    def test_format_file_size_kb(self, publish_manager) -> None:
        result = publish_manager._format_file_size(1024)
        assert result == "1.0KB"

    def test_format_file_size_mb(self, publish_manager) -> None:
        result = publish_manager._format_file_size(1024 * 1024)
        assert result == "1.0MB"

    def test_format_file_size_large_mb(self, publish_manager) -> None:
        result = publish_manager._format_file_size(5 * 1024 * 1024)
        assert result == "5.0MB"


class TestPublishManagerPublishPackage:
    @pytest.fixture
    def publish_manager(
        self,
        publish_manager_di_context,
        mock_console,
        mock_git_service,
        mock_version_analyzer,
        mock_changelog_generator,
        mock_filesystem,
        mock_security_service,
        mock_regex_patterns,
        temp_pkg_path,
    ):
        """Create PublishManagerImpl with mocked dependencies."""
        injection_map, pkg_path = publish_manager_di_context
        return create_publish_manager(
            mock_console=mock_console,
            mock_git_service=mock_git_service,
            mock_version_analyzer=mock_version_analyzer,
            mock_changelog_generator=mock_changelog_generator,
            mock_filesystem=mock_filesystem,
            mock_security_service=mock_security_service,
            mock_regex_patterns=mock_regex_patterns,
            temp_pkg_path=temp_pkg_path,
            dry_run=False,
        )

    def test_publish_package_success(self, publish_manager) -> None:
        with (
            patch.object(
                publish_manager,
                "_validate_prerequisites",
                return_value=True,
            ),
            patch.object(
                publish_manager,
                "_perform_publish_workflow",
                return_value=True,
            ),
        ):
            result = publish_manager.publish_package()
            assert result is True

    def test_publish_package_auth_failure(self, publish_manager) -> None:
        with patch.object(
            publish_manager,
            "_validate_prerequisites",
            return_value=False,
        ):
            result = publish_manager.publish_package()
            assert result is False

    def test_publish_package_exception(self, publish_manager) -> None:
        with patch.object(
            publish_manager,
            "_validate_prerequisites",
            side_effect=Exception("Auth error"),
        ):
            result = publish_manager.publish_package()
            assert result is False

    def test_perform_publish_workflow_dry_run(self, publish_manager) -> None:
        publish_manager.dry_run = True
        result = publish_manager._perform_publish_workflow()
        assert result is True

    def test_perform_publish_workflow_build_failure(self, publish_manager) -> None:
        with patch.object(publish_manager, "build_package", return_value=False):
            result = publish_manager._perform_publish_workflow()
            assert result is False

    def test_perform_publish_workflow_success(self, publish_manager) -> None:
        with patch.object(publish_manager, "build_package", return_value=True):
            with patch.object(publish_manager, "_execute_publish", return_value=True):
                result = publish_manager._perform_publish_workflow()
                assert result is True

    def test_execute_publish_success(self, publish_manager) -> None:
        mock_result = Mock()
        mock_result.returncode = 0

        with patch.object(publish_manager, "_run_command", return_value=mock_result):
            with patch.object(publish_manager, "_handle_publish_success"):
                result = publish_manager._execute_publish()
                assert result is True

    def test_execute_publish_failure(self, publish_manager) -> None:
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stderr = "Publish failed"

        with patch.object(publish_manager, "_run_command", return_value=mock_result):
            with patch.object(publish_manager, "_handle_publish_failure"):
                result = publish_manager._execute_publish()
                assert result is False

    def test_handle_publish_success(self, publish_manager) -> None:
        with patch.object(publish_manager, "_display_package_url"):
            publish_manager._handle_publish_success()

    def test_handle_publish_failure(self, publish_manager) -> None:
        publish_manager._handle_publish_failure("Error message")

    def test_display_package_url(self, publish_manager) -> None:
        with (
            patch.object(
                publish_manager,
                "_get_current_version",
                return_value="1.0.0",
            ),
            patch.object(
                publish_manager,
                "_get_package_name",
                return_value="test - package",
            ),
        ):
            publish_manager._display_package_url()


class TestPublishManagerUtilities:
    @pytest.fixture
    def publish_manager(
        self,
        publish_manager_di_context,
        mock_console,
        mock_git_service,
        mock_version_analyzer,
        mock_changelog_generator,
        mock_filesystem,
        mock_security_service,
        mock_regex_patterns,
        temp_pkg_path,
    ):
        """Create PublishManagerImpl with mocked dependencies."""
        injection_map, pkg_path = publish_manager_di_context
        return create_publish_manager(
            mock_console=mock_console,
            mock_git_service=mock_git_service,
            mock_version_analyzer=mock_version_analyzer,
            mock_changelog_generator=mock_changelog_generator,
            mock_filesystem=mock_filesystem,
            mock_security_service=mock_security_service,
            mock_regex_patterns=mock_regex_patterns,
            temp_pkg_path=temp_pkg_path,
            dry_run=False,
        )

    def test_get_package_name_success(self, publish_manager) -> None:
        pyproject_content = """
[project]
name = "test - package"
version = "1.0.0"
"""
        with patch.object(
            publish_manager.filesystem,
            "read_file",
            return_value=pyproject_content,
        ):
            name = publish_manager._get_package_name()
            assert name == "test - package"

    def test_get_package_name_missing(self, publish_manager) -> None:
        pyproject_content = """
[project]
version = "1.0.0"
"""
        with patch.object(
            publish_manager.filesystem,
            "read_file",
            return_value=pyproject_content,
        ):
            name = publish_manager._get_package_name()
            assert name == ""

    def test_get_package_name_error(self, publish_manager) -> None:
        with patch.object(
            publish_manager.filesystem,
            "read_file",
            side_effect=Exception("File error"),
        ):
            name = publish_manager._get_package_name()
            assert name is None

    def test_get_package_info_success(self, publish_manager) -> None:
        pyproject_content = """
[project]
name = "test - package"
version = "1.0.0"
description = "A test package"
authors = [{"name": "Test Author", "email": "test@example.com"}]
dependencies = ["requests >=    2.0.0"]
requires - python = " >=    3.8"
"""
        with patch.object(
            publish_manager.filesystem,
            "read_file",
            return_value=pyproject_content,
        ):
            info = publish_manager.get_package_info()

            assert info["name"] == "test - package"
            assert info["version"] == "1.0.0"
            assert info["description"] == "A test package"
            assert len(info["authors"]) == 1
            assert len(info["dependencies"]) == 1
            assert info["python_requires"] == " >=    3.8"

    def test_get_package_info_missing_file(self, publish_manager) -> None:
        info = publish_manager.get_package_info()
        assert info == {}

    def test_get_package_info_error(self, publish_manager) -> None:
        with patch.object(
            publish_manager.filesystem,
            "read_file",
            side_effect=Exception("File error"),
        ):
            info = publish_manager.get_package_info()
            assert info == {}

    def test_create_git_tag_success(self, publish_manager) -> None:
        mock_tag_result = Mock()
        mock_tag_result.returncode = 0
        mock_push_result = Mock()
        mock_push_result.returncode = 0

        with patch.object(
            publish_manager,
            "_run_command",
            side_effect=[mock_tag_result, mock_push_result],
        ):
            result = publish_manager.create_git_tag("1.0.0")
            assert result is True

    def test_create_git_tag_failure(self, publish_manager) -> None:
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stderr = "Tag creation failed"

        with patch.object(publish_manager, "_run_command", return_value=mock_result):
            result = publish_manager.create_git_tag("1.0.0")
            assert result is False

    def test_create_git_tag_push_failure(self, publish_manager) -> None:
        mock_tag_result = Mock()
        mock_tag_result.returncode = 0
        mock_push_result = Mock()
        mock_push_result.returncode = 1
        mock_push_result.stderr = "Push failed"

        with patch.object(
            publish_manager,
            "_run_command",
            side_effect=[mock_tag_result, mock_push_result],
        ):
            result = publish_manager.create_git_tag("1.0.0")
            assert result is True

    def test_create_git_tag_dry_run(self, publish_manager) -> None:
        publish_manager.dry_run = True
        result = publish_manager.create_git_tag("1.0.0")
        assert result is True

    def test_create_git_tag_exception(self, publish_manager) -> None:
        with patch.object(
            publish_manager,
            "_run_command",
            side_effect=Exception("Git error"),
        ):
            result = publish_manager.create_git_tag("1.0.0")
            assert result is False

    def test_cleanup_old_releases_success(self, publish_manager) -> None:
        pyproject_content = """
[project]
name = "test - package"
version = "1.0.0"
"""
        with patch.object(
            publish_manager.filesystem,
            "read_file",
            return_value=pyproject_content,
        ):
            result = publish_manager.cleanup_old_releases(5)
            assert result is True

    def test_cleanup_old_releases_dry_run(self, publish_manager) -> None:
        publish_manager.dry_run = True
        result = publish_manager.cleanup_old_releases()
        assert result is True

    def test_cleanup_old_releases_no_package_name(self, publish_manager) -> None:
        pyproject_content = """
[project]
version = "1.0.0"
"""
        with patch.object(
            publish_manager.filesystem,
            "read_file",
            return_value=pyproject_content,
        ):
            result = publish_manager.cleanup_old_releases()
            assert result is False

    def test_cleanup_old_releases_error(self, publish_manager) -> None:
        with patch.object(
            publish_manager.filesystem,
            "read_file",
            side_effect=Exception("File error"),
        ):
            result = publish_manager.cleanup_old_releases()
            assert result is False
