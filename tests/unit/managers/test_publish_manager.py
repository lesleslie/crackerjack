"""Unit tests for PublishManager.

Tests version management, authentication validation, package building,
publishing workflow, and git tagging functionality.
"""

import subprocess
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from crackerjack.managers.publish_manager import PublishManagerImpl


@pytest.mark.unit
class TestPublishManagerInitialization:
    """Test PublishManager initialization."""

    @pytest.fixture
    def mock_dependencies(self, tmp_path):
        """Create mock dependencies for PublishManager."""
        return {
            "git_service": Mock(),
            "version_analyzer": Mock(),
            "changelog_generator": Mock(),
            "filesystem": Mock(),
            "security": Mock(),
            "regex_patterns": Mock(),
            "console": Mock(),
            "pkg_path": tmp_path,
        }

    def test_initialization_with_dependencies(self, mock_dependencies):
        """Test PublishManager initializes with injected dependencies."""
        manager = PublishManagerImpl(**mock_dependencies)

        assert manager.console == mock_dependencies["console"]
        assert manager.pkg_path == mock_dependencies["pkg_path"]
        assert manager.filesystem == mock_dependencies["filesystem"]
        assert manager.security == mock_dependencies["security"]
        assert manager.dry_run is False

    def test_initialization_with_dry_run(self, mock_dependencies):
        """Test PublishManager initializes with dry run mode."""
        manager = PublishManagerImpl(**mock_dependencies, dry_run=True)

        assert manager.dry_run is True


@pytest.mark.unit
class TestPublishManagerVersionManagement:
    """Test version management methods."""

    @pytest.fixture
    def manager(self, tmp_path):
        """Create PublishManager instance for testing."""
        mock_fs = Mock()
        return PublishManagerImpl(
            git_service=Mock(),
            version_analyzer=Mock(),
            changelog_generator=Mock(),
            filesystem=mock_fs,
            security=Mock(),
            regex_patterns=Mock(),
            console=Mock(),
            pkg_path=tmp_path,
        )

    def test_get_current_version_success(self, manager, tmp_path):
        """Test reading current version from pyproject.toml."""
        pyproject_content = '[project]\nversion = "1.2.3"\nname = "test-package"\n'
        manager.filesystem.read_file.return_value = pyproject_content

        # Create the file so it exists
        pyproject_path = tmp_path / "pyproject.toml"
        pyproject_path.write_text(pyproject_content)

        version = manager._get_current_version()

        assert version == "1.2.3"

    def test_get_current_version_file_not_exists(self, manager):
        """Test get_current_version when pyproject.toml doesn't exist."""
        version = manager._get_current_version()

        assert version is None

    def test_get_current_version_invalid_format(self, manager, tmp_path):
        """Test get_current_version with invalid TOML format."""
        pyproject_path = tmp_path / "pyproject.toml"
        pyproject_path.write_text("invalid toml [")

        manager.filesystem.read_file.return_value = "invalid toml ["

        version = manager._get_current_version()

        assert version is None

    def test_calculate_next_version_patch(self, manager):
        """Test calculating next patch version."""
        next_version = manager._calculate_next_version("1.2.3", "patch")

        assert next_version == "1.2.4"

    def test_calculate_next_version_minor(self, manager):
        """Test calculating next minor version."""
        next_version = manager._calculate_next_version("1.2.3", "minor")

        assert next_version == "1.3.0"

    def test_calculate_next_version_major(self, manager):
        """Test calculating next major version."""
        next_version = manager._calculate_next_version("1.2.3", "major")

        assert next_version == "2.0.0"

    def test_calculate_next_version_invalid_format(self, manager):
        """Test calculate_next_version with invalid version format."""
        with pytest.raises(ValueError, match="Invalid version format"):
            manager._calculate_next_version("1.2", "patch")

    def test_calculate_next_version_invalid_bump_type(self, manager):
        """Test calculate_next_version with invalid bump type."""
        with pytest.raises(ValueError, match="Invalid bump type"):
            manager._calculate_next_version("1.2.3", "invalid")

    def test_update_version_in_file_success(self, manager, tmp_path):
        """Test updating version in pyproject.toml."""
        pyproject_path = tmp_path / "pyproject.toml"
        original_content = '[project]\nversion = "1.2.3"\n'
        updated_content = '[project]\nversion = "1.2.4"\n'

        pyproject_path.write_text(original_content)
        manager.filesystem.read_file.return_value = original_content
        manager._regex_patterns.update_pyproject_version.return_value = updated_content

        result = manager._update_version_in_file("1.2.4")

        assert result is True
        manager.filesystem.write_file.assert_called_once()

    def test_update_version_in_file_no_change(self, manager, tmp_path):
        """Test update_version_in_file when pattern doesn't match."""
        pyproject_path = tmp_path / "pyproject.toml"
        content = '[project]\nname = "test"\n'

        pyproject_path.write_text(content)
        manager.filesystem.read_file.return_value = content
        manager._regex_patterns.update_pyproject_version.return_value = content

        result = manager._update_version_in_file("1.2.4")

        assert result is False

    def test_update_version_in_file_dry_run(self, manager, tmp_path):
        """Test update_version_in_file in dry run mode."""
        manager.dry_run = True
        pyproject_path = tmp_path / "pyproject.toml"
        original_content = '[project]\nversion = "1.2.3"\n'
        updated_content = '[project]\nversion = "1.2.4"\n'

        pyproject_path.write_text(original_content)
        manager.filesystem.read_file.return_value = original_content
        manager._regex_patterns.update_pyproject_version.return_value = updated_content

        result = manager._update_version_in_file("1.2.4")

        assert result is True
        # Should not write file in dry run mode
        manager.filesystem.write_file.assert_not_called()

    def test_bump_version_patch(self, manager, tmp_path):
        """Test bumping patch version."""
        pyproject_path = tmp_path / "pyproject.toml"
        pyproject_content = '[project]\nversion = "1.2.3"\n'
        pyproject_path.write_text(pyproject_content)

        manager.filesystem.read_file.return_value = pyproject_content
        manager._regex_patterns.update_pyproject_version.return_value = (
            '[project]\nversion = "1.2.4"\n'
        )

        with patch.object(manager, "_get_version_recommendation", return_value=None):
            with patch.object(manager, "_update_changelog_for_version"):
                new_version = manager.bump_version("patch")

                assert new_version == "1.2.4"

    def test_bump_version_no_current_version(self, manager):
        """Test bump_version when current version cannot be determined."""
        with pytest.raises(ValueError, match="Cannot determine current version"):
            manager.bump_version("patch")

    def test_bump_version_auto_with_recommendation(self, manager, tmp_path):
        """Test bump_version in auto mode with AI recommendation."""
        pyproject_path = tmp_path / "pyproject.toml"
        pyproject_content = '[project]\nversion = "1.2.3"\n'
        pyproject_path.write_text(pyproject_content)

        manager.filesystem.read_file.return_value = pyproject_content
        manager._regex_patterns.update_pyproject_version.return_value = (
            '[project]\nversion = "1.3.0"\n'
        )

        # Mock AI recommendation
        mock_recommendation = Mock()
        mock_recommendation.bump_type.value = "minor"

        with patch.object(manager, "_get_version_recommendation", return_value=mock_recommendation):
            with patch.object(manager, "_display_version_analysis"):
                with patch.object(manager, "_update_changelog_for_version"):
                    new_version = manager.bump_version("auto")

                    assert new_version == "1.3.0"


@pytest.mark.unit
class TestPublishManagerAuthentication:
    """Test authentication validation methods."""

    @pytest.fixture
    def manager(self, tmp_path):
        """Create PublishManager instance."""
        mock_security = Mock()
        return PublishManagerImpl(
            git_service=Mock(),
            version_analyzer=Mock(),
            changelog_generator=Mock(),
            filesystem=Mock(),
            security=mock_security,
            regex_patterns=Mock(),
            console=Mock(),
            pkg_path=tmp_path,
        )

    def test_validate_auth_success_env_token(self, manager):
        """Test successful authentication validation with environment token."""
        with patch.object(manager, "_check_env_token_auth", return_value="Environment variable"):
            result = manager.validate_auth()

            assert result is True

    def test_validate_auth_success_keyring(self, manager):
        """Test successful authentication validation with keyring."""
        with patch.object(manager, "_check_env_token_auth", return_value=None):
            with patch.object(manager, "_check_keyring_auth", return_value="Keyring storage"):
                result = manager.validate_auth()

                assert result is True

    def test_validate_auth_failure(self, manager):
        """Test authentication validation failure."""
        with patch.object(manager, "_check_env_token_auth", return_value=None):
            with patch.object(manager, "_check_keyring_auth", return_value=None):
                result = manager.validate_auth()

                assert result is False

    def test_check_env_token_auth_valid(self, manager):
        """Test checking environment token with valid token."""
        with patch("os.getenv", return_value="pypi-test-token-1234567890"):
            manager.security.validate_token_format.return_value = True
            manager.security.mask_tokens.return_value = "pypi-****"

            result = manager._check_env_token_auth()

            assert result == "Environment variable (UV_PUBLISH_TOKEN)"

    def test_check_env_token_auth_invalid_format(self, manager):
        """Test checking environment token with invalid format."""
        with patch("os.getenv", return_value="invalid-token"):
            manager.security.validate_token_format.return_value = False

            result = manager._check_env_token_auth()

            assert result is None

    def test_check_env_token_auth_not_set(self, manager):
        """Test checking environment token when not set."""
        with patch("os.getenv", return_value=None):
            result = manager._check_env_token_auth()

            assert result is None

    def test_check_keyring_auth_success(self, manager):
        """Test checking keyring authentication successfully."""
        mock_result = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="pypi-keyring-token-1234567890\n",
            stderr="",
        )

        with patch.object(manager, "_run_command", return_value=mock_result):
            manager.security.validate_token_format.return_value = True

            result = manager._check_keyring_auth()

            assert result == "Keyring storage"

    def test_check_keyring_auth_invalid_token(self, manager):
        """Test checking keyring with invalid token format."""
        mock_result = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="invalid-token\n",
            stderr="",
        )

        with patch.object(manager, "_run_command", return_value=mock_result):
            manager.security.validate_token_format.return_value = False

            result = manager._check_keyring_auth()

            assert result is None

    def test_check_keyring_auth_command_failure(self, manager):
        """Test checking keyring when command fails."""
        mock_result = subprocess.CompletedProcess(
            args=[],
            returncode=1,
            stdout="",
            stderr="keyring not available",
        )

        with patch.object(manager, "_run_command", return_value=mock_result):
            result = manager._check_keyring_auth()

            assert result is None


@pytest.mark.unit
class TestPublishManagerBuildPackage:
    """Test package building methods."""

    @pytest.fixture
    def manager(self, tmp_path):
        """Create PublishManager instance."""
        return PublishManagerImpl(
            git_service=Mock(),
            version_analyzer=Mock(),
            changelog_generator=Mock(),
            filesystem=Mock(),
            security=Mock(),
            regex_patterns=Mock(),
            console=Mock(),
            pkg_path=tmp_path,
        )

    def test_build_package_success(self, manager, tmp_path):
        """Test successful package build."""
        mock_result = subprocess.CompletedProcess(
            args=["uv", "build"],
            returncode=0,
            stdout="Building package...\nPackage built successfully",
            stderr="",
        )

        # Create dist directory with artifacts
        dist_dir = tmp_path / "dist"
        dist_dir.mkdir()
        (dist_dir / "package-1.0.0.tar.gz").write_text("content")

        with patch.object(manager, "_run_command", return_value=mock_result):
            result = manager.build_package()

            assert result is True

    def test_build_package_failure(self, manager):
        """Test package build failure."""
        mock_result = subprocess.CompletedProcess(
            args=["uv", "build"],
            returncode=1,
            stdout="",
            stderr="Build failed: invalid configuration",
        )

        with patch.object(manager, "_run_command", return_value=mock_result):
            result = manager.build_package()

            assert result is False

    def test_build_package_dry_run(self, manager):
        """Test package build in dry run mode."""
        manager.dry_run = True

        result = manager.build_package()

        assert result is True

    def test_clean_dist_directory(self, manager, tmp_path):
        """Test cleaning dist directory before build."""
        dist_dir = tmp_path / "dist"
        dist_dir.mkdir()
        (dist_dir / "old_artifact.whl").write_text("old content")

        manager._clean_dist_directory()

        # Directory should exist but be empty
        assert dist_dir.exists()
        assert list(dist_dir.iterdir()) == []

    def test_clean_dist_directory_not_exists(self, manager):
        """Test clean_dist_directory when directory doesn't exist."""
        # Should not raise an error
        manager._clean_dist_directory()

    def test_format_file_size_kilobytes(self, manager):
        """Test formatting file size in kilobytes."""
        size_str = manager._format_file_size(1024 * 50)  # 50KB

        assert "KB" in size_str

    def test_format_file_size_megabytes(self, manager):
        """Test formatting file size in megabytes."""
        size_str = manager._format_file_size(1024 * 1024 * 5)  # 5MB

        assert "MB" in size_str


@pytest.mark.unit
class TestPublishManagerPublishing:
    """Test package publishing methods."""

    @pytest.fixture
    def manager(self, tmp_path):
        """Create PublishManager instance."""
        return PublishManagerImpl(
            git_service=Mock(),
            version_analyzer=Mock(),
            changelog_generator=Mock(),
            filesystem=Mock(),
            security=Mock(),
            regex_patterns=Mock(),
            console=Mock(),
            pkg_path=tmp_path,
        )

    def test_publish_package_success(self, manager):
        """Test successful package publishing."""
        mock_build_result = subprocess.CompletedProcess(
            args=["uv", "build"], returncode=0, stdout="Built", stderr=""
        )
        mock_publish_result = subprocess.CompletedProcess(
            args=["uv", "publish"],
            returncode=0,
            stdout="Successfully uploaded package",
            stderr="",
        )

        with patch.object(manager, "validate_auth", return_value=True):
            with patch.object(manager, "_run_command") as mock_run:
                mock_run.side_effect = [mock_build_result, mock_publish_result]

                result = manager.publish_package()

                assert result is True

    def test_publish_package_auth_failure(self, manager):
        """Test publish_package when authentication fails."""
        with patch.object(manager, "validate_auth", return_value=False):
            result = manager.publish_package()

            assert result is False

    def test_publish_package_build_failure(self, manager):
        """Test publish_package when build fails."""
        mock_build_result = subprocess.CompletedProcess(
            args=["uv", "build"], returncode=1, stdout="", stderr="Build failed"
        )

        with patch.object(manager, "validate_auth", return_value=True):
            with patch.object(manager, "_run_command", return_value=mock_build_result):
                result = manager.publish_package()

                assert result is False

    def test_publish_package_publish_failure(self, manager):
        """Test publish_package when publish command fails."""
        mock_build_result = subprocess.CompletedProcess(
            args=["uv", "build"], returncode=0, stdout="Built", stderr=""
        )
        mock_publish_result = subprocess.CompletedProcess(
            args=["uv", "publish"],
            returncode=1,
            stdout="",
            stderr="Upload failed: network error",
        )

        with patch.object(manager, "validate_auth", return_value=True):
            with patch.object(manager, "_run_command") as mock_run:
                mock_run.side_effect = [mock_build_result, mock_publish_result]

                result = manager.publish_package()

                assert result is False

    def test_publish_package_dry_run(self, manager):
        """Test publish_package in dry run mode."""
        manager.dry_run = True

        with patch.object(manager, "validate_auth", return_value=True):
            result = manager.publish_package()

            assert result is True

    def test_execute_publish_success_indicator(self, manager):
        """Test publish succeeds based on success indicator in output."""
        # Non-zero return code but has success indicator
        mock_result = subprocess.CompletedProcess(
            args=["uv", "publish"],
            returncode=2,  # Non-zero but not failure
            stdout="Warning: xyz\nSuccessfully uploaded package to PyPI",
            stderr="",
        )

        with patch.object(manager, "_run_command", return_value=mock_result):
            result = manager._execute_publish()

            assert result is True


@pytest.mark.unit
class TestPublishManagerGitTagging:
    """Test git tagging methods."""

    @pytest.fixture
    def manager(self, tmp_path):
        """Create PublishManager instance."""
        return PublishManagerImpl(
            git_service=Mock(),
            version_analyzer=Mock(),
            changelog_generator=Mock(),
            filesystem=Mock(),
            security=Mock(),
            regex_patterns=Mock(),
            console=Mock(),
            pkg_path=tmp_path,
        )

    def test_create_git_tag_local_success(self, manager):
        """Test creating local git tag successfully."""
        mock_result = subprocess.CompletedProcess(
            args=["git", "tag", "v1.2.3"], returncode=0, stdout="", stderr=""
        )

        with patch.object(manager, "_run_command", return_value=mock_result):
            result = manager.create_git_tag_local("1.2.3")

            assert result is True

    def test_create_git_tag_local_failure(self, manager):
        """Test creating local git tag failure."""
        mock_result = subprocess.CompletedProcess(
            args=["git", "tag", "v1.2.3"],
            returncode=1,
            stdout="",
            stderr="tag already exists",
        )

        with patch.object(manager, "_run_command", return_value=mock_result):
            result = manager.create_git_tag_local("1.2.3")

            assert result is False

    def test_create_git_tag_local_dry_run(self, manager):
        """Test creating local git tag in dry run mode."""
        manager.dry_run = True

        result = manager.create_git_tag_local("1.2.3")

        assert result is True

    def test_create_git_tag_with_push_success(self, manager):
        """Test creating and pushing git tag successfully."""
        mock_tag_result = subprocess.CompletedProcess(
            args=["git", "tag", "v1.2.3"], returncode=0, stdout="", stderr=""
        )
        mock_push_result = subprocess.CompletedProcess(
            args=["git", "push", "origin", "v1.2.3"],
            returncode=0,
            stdout="",
            stderr="",
        )

        with patch.object(manager, "_run_command") as mock_run:
            mock_run.side_effect = [mock_tag_result, mock_push_result]

            result = manager.create_git_tag("1.2.3")

            assert result is True
            assert mock_run.call_count == 2

    def test_create_git_tag_push_failure(self, manager):
        """Test creating git tag when push fails."""
        mock_tag_result = subprocess.CompletedProcess(
            args=["git", "tag", "v1.2.3"], returncode=0, stdout="", stderr=""
        )
        mock_push_result = subprocess.CompletedProcess(
            args=["git", "push", "origin", "v1.2.3"],
            returncode=1,
            stdout="",
            stderr="network error",
        )

        with patch.object(manager, "_run_command") as mock_run:
            mock_run.side_effect = [mock_tag_result, mock_push_result]

            result = manager.create_git_tag("1.2.3")

            # Tag created successfully even if push fails
            assert result is True


@pytest.mark.unit
class TestPublishManagerPackageInfo:
    """Test package information methods."""

    @pytest.fixture
    def manager(self, tmp_path):
        """Create PublishManager instance."""
        mock_fs = Mock()
        return PublishManagerImpl(
            git_service=Mock(),
            version_analyzer=Mock(),
            changelog_generator=Mock(),
            filesystem=mock_fs,
            security=Mock(),
            regex_patterns=Mock(),
            console=Mock(),
            pkg_path=tmp_path,
        )

    def test_get_package_info_success(self, manager, tmp_path):
        """Test getting package information successfully."""
        pyproject_content = """
[project]
name = "test-package"
version = "1.2.3"
description = "A test package"
requires-python = ">=3.8"
authors = [{name = "Test Author", email = "test@example.com"}]
dependencies = ["requests>=2.28.0"]
"""
        pyproject_path = tmp_path / "pyproject.toml"
        pyproject_path.write_text(pyproject_content)
        manager.filesystem.read_file.return_value = pyproject_content

        info = manager.get_package_info()

        assert info["name"] == "test-package"
        assert info["version"] == "1.2.3"
        assert info["description"] == "A test package"
        assert info["python_requires"] == ">=3.8"
        assert len(info["authors"]) > 0
        assert len(info["dependencies"]) > 0

    def test_get_package_info_file_not_exists(self, manager):
        """Test get_package_info when pyproject.toml doesn't exist."""
        info = manager.get_package_info()

        assert info == {}

    def test_get_package_name_success(self, manager, tmp_path):
        """Test getting package name successfully."""
        pyproject_content = '[project]\nname = "test-package"\n'
        pyproject_path = tmp_path / "pyproject.toml"
        pyproject_path.write_text(pyproject_content)
        manager.filesystem.read_file.return_value = pyproject_content

        name = manager._get_package_name()

        assert name == "test-package"

    def test_get_package_name_error(self, manager, tmp_path):
        """Test get_package_name when reading fails."""
        manager.filesystem.read_file.side_effect = Exception("Read error")

        name = manager._get_package_name()

        assert name is None


@pytest.mark.unit
class TestPublishManagerUtilities:
    """Test utility methods."""

    @pytest.fixture
    def manager(self, tmp_path):
        """Create PublishManager instance."""
        mock_security = Mock()
        mock_security.create_secure_command_env.return_value = {"PATH": "/usr/bin"}
        mock_security.mask_tokens.side_effect = lambda x: x
        return PublishManagerImpl(
            git_service=Mock(),
            version_analyzer=Mock(),
            changelog_generator=Mock(),
            filesystem=Mock(),
            security=mock_security,
            regex_patterns=Mock(),
            console=Mock(),
            pkg_path=tmp_path,
        )

    def test_run_command_success(self, manager, tmp_path):
        """Test running command successfully."""
        with patch("subprocess.run") as mock_run:
            mock_result = subprocess.CompletedProcess(
                args=["echo", "test"], returncode=0, stdout="test", stderr=""
            )
            mock_run.return_value = mock_result

            result = manager._run_command(["echo", "test"])

            assert result.returncode == 0
            assert result.stdout == "test"

    def test_run_command_masks_tokens(self, manager):
        """Test run_command masks tokens in output."""
        manager.security.mask_tokens.side_effect = lambda x: x.replace(
            "secret123", "***"
        )

        with patch("subprocess.run") as mock_run:
            mock_result = subprocess.CompletedProcess(
                args=["echo", "test"],
                returncode=0,
                stdout="Token: secret123",
                stderr="Error: secret123",
            )
            mock_run.return_value = mock_result

            result = manager._run_command(["echo", "test"])

            assert "secret123" not in result.stdout
            assert "secret123" not in result.stderr
            assert "***" in result.stdout
            assert "***" in result.stderr

    def test_cleanup_old_releases_dry_run(self, manager):
        """Test cleanup_old_releases in dry run mode."""
        manager.dry_run = True

        result = manager.cleanup_old_releases(keep_releases=10)

        assert result is True

    def test_cleanup_old_releases_no_package_name(self, manager, tmp_path):
        """Test cleanup_old_releases when package name cannot be determined."""
        pyproject_content = "[project]\n"  # No name field
        pyproject_path = tmp_path / "pyproject.toml"
        pyproject_path.write_text(pyproject_content)
        manager.filesystem.read_file.return_value = pyproject_content

        result = manager.cleanup_old_releases()

        assert result is False

    def test_update_changelog_for_version(self, manager):
        """Test updating changelog for new version."""
        mock_changelog_gen = Mock()
        mock_changelog_gen.generate_changelog_from_commits.return_value = True
        manager._changelog_generator = mock_changelog_gen

        manager._update_changelog_for_version("1.2.3", "1.2.4")

        mock_changelog_gen.generate_changelog_from_commits.assert_called_once()

    def test_update_changelog_for_version_failure(self, manager):
        """Test updating changelog when generation fails."""
        mock_changelog_gen = Mock()
        mock_changelog_gen.generate_changelog_from_commits.side_effect = Exception(
            "Generation failed"
        )
        manager._changelog_generator = mock_changelog_gen

        # Should not raise exception
        manager._update_changelog_for_version("1.2.3", "1.2.4")
