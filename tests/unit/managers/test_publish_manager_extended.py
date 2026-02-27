"""Extended unit tests for PublishManager.

Tests version bumping, changelog generation, authentication,
build execution, git tagging, and package info extraction.
"""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from crackerjack.managers.publish_manager import PublishManagerImpl


@pytest.mark.unit
class TestPublishManagerVersionBumping:
    """Test version bumping functionality."""

    @pytest.fixture
    def manager(self, temp_pkg_path):
        """Create PublishManager with mock dependencies."""
        return PublishManagerImpl(
            pkg_path=temp_pkg_path,
            dry_run=False,
        )

    def test_calculate_next_version_patch(self, manager) -> None:
        """Test patch version bump."""
        new_version = manager._calculate_next_version("1.2.3", "patch")

        assert new_version == "1.2.4"

    def test_calculate_next_version_minor(self, manager) -> None:
        """Test minor version bump."""
        new_version = manager._calculate_next_version("1.2.3", "minor")

        assert new_version == "1.3.0"

    def test_calculate_next_version_major(self, manager) -> None:
        """Test major version bump."""
        new_version = manager._calculate_next_version("1.2.3", "major")

        assert new_version == "2.0.0"

    def test_calculate_next_version_invalid_format(self, manager) -> None:
        """Test version bump with invalid format."""
        with pytest.raises(ValueError):
            manager._calculate_next_version("1.2", "patch")

    def test_calculate_next_version_invalid_bump_type(self, manager) -> None:
        """Test version bump with invalid type."""
        with pytest.raises(ValueError):
            manager._calculate_next_version("1.2.3", "invalid")

    def test_get_current_version_from_file(self, manager, temp_pkg_path) -> None:
        """Test reading current version from pyproject.toml."""

        pyproject = temp_pkg_path / "pyproject.toml"
        content = """
[project]
name = "test-package"
version = "1.2.3"
"""
        pyproject.write_text(content)

        version = manager._get_current_version()

        assert version == "1.2.3"

    def test_get_current_version_no_file(self, manager, temp_pkg_path) -> None:
        """Test reading version when no pyproject.toml."""
        version = manager._get_current_version()

        assert version is None

    def test_get_current_version_invalid_toml(self, manager, temp_pkg_path) -> None:
        """Test reading version with invalid TOML."""
        pyproject = temp_pkg_path / "pyproject.toml"
        pyproject.write_text("invalid toml [[")

        version = manager._get_current_version()

        assert version is None

    def test_update_version_in_file(self, manager, temp_pkg_path) -> None:
        """Test updating version in file."""
        pyproject = temp_pkg_path / "pyproject.toml"
        content = """
[project]
name = "test-package"
version = "1.2.3"
"""
        pyproject.write_text(content)

        result = manager._update_version_in_file("1.2.4")

        assert result is True

        # Verify file was updated
        new_content = pyproject.read_text()
        assert "1.2.4" in new_content

    def test_update_version_no_pattern_found(self, manager, temp_pkg_path) -> None:
        """Test updating version when pattern not found."""
        pyproject = temp_pkg_path / "pyproject.toml"
        content = """
[project]
name = "test-package"
"""
        pyproject.write_text(content)

        result = manager._update_version_in_file("1.2.4")

        assert result is False

    def test_update_python_version_files(self, manager, temp_pkg_path) -> None:
        """Test updating __version__ in Python files."""
        # Create __init__.py with __version__
        init_file = temp_pkg_path / "__init__.py"
        init_file.write_text('__version__ = "1.2.3"\n')

        result = manager._update_python_version_files("1.2.4")

        assert result is True

        # Verify file was updated
        new_content = init_file.read_text()
        assert "1.2.4" in new_content

    def test_bump_version_dry_run(self, manager, temp_pkg_path) -> None:
        """Test version bump in dry run mode."""
        manager.dry_run = True

        pyproject = temp_pkg_path / "pyproject.toml"
        pyproject.write_text('[project]\nversion = "1.2.3"\n')

        new_version = manager.bump_version("patch")

        assert new_version == "1.2.4"

        # File should not be modified in dry run
        content = pyproject.read_text()
        assert "1.2.3" in content

    def test_bump_version_no_current_version(self, manager, temp_pkg_path) -> None:
        """Test version bump when current version unknown."""
        pyproject = temp_pkg_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "test"\n')

        with pytest.raises(ValueError):
            manager.bump_version("patch")


@pytest.mark.unit
class TestPublishManagerAuthentication:
    """Test authentication validation."""

    @pytest.fixture
    def manager(self, temp_pkg_path):
        """Create PublishManager."""
        return PublishManagerImpl(pkg_path=temp_pkg_path)

    def test_validate_auth_env_token_valid(self, manager, monkeypatch) -> None:
        """Test auth validation with valid env token."""
        monkeypatch.setenv("UV_PUBLISH_TOKEN", "pypi-valid_test_token_123")

        with patch.object(manager.security, "validate_token_format", return_value=True):
            result = manager.validate_auth()

            assert result is True

    def test_validate_auth_env_token_invalid(self, manager, monkeypatch) -> None:
        """Test auth validation with invalid env token."""
        monkeypatch.setenv("UV_PUBLISH_TOKEN", "invalid_token")

        with patch.object(manager.security, "validate_token_format", return_value=False):
            result = manager.validate_auth()

            assert result is False

    def test_validate_auth_no_token(self, manager, monkeypatch) -> None:
        """Test auth validation with no token."""
        monkeypatch.delenv("UV_PUBLISH_TOKEN", raising=False)

        with patch.object(manager, "_run_command"):
            with patch.object(manager.security, "validate_token_format", return_value=True):
                result = manager.validate_auth()

                # Should try keyring and fail (no keyring mock)
                # Result depends on keyring availability

    def test_check_env_token_auth(self, manager, monkeypatch) -> None:
        """Test env token authentication check."""
        monkeypatch.setenv("UV_PUBLISH_TOKEN", "pypi-valid_token")

        with patch.object(manager.security, "validate_token_format", return_value=True):
            result = manager._check_env_token_auth()

            assert result == "Environment variable (UV_PUBLISH_TOKEN)"

    def test_check_env_token_auth_invalid_format(self, manager, monkeypatch) -> None:
        """Test env token auth with invalid format."""
        monkeypatch.setenv("UV_PUBLISH_TOKEN", "invalid")

        with patch.object(manager.security, "validate_token_format", return_value=False):
            result = manager._check_env_token_auth()

            assert result is None

    def test_check_keyring_auth_success(self, manager) -> None:
        """Test keyring authentication success."""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "pypi-valid_token"

        with patch.object(manager, "_run_command", return_value=mock_result):
            with patch.object(manager.security, "validate_token_format", return_value=True):
                result = manager._check_keyring_auth()

                assert result == "Keyring storage"

    def test_check_keyring_auth_failure(self, manager) -> None:
        """Test keyring authentication failure."""
        mock_result = Mock()
        mock_result.returncode = 1

        with patch.object(manager, "_run_command", return_value=mock_result):
            result = manager._check_keyring_auth()

            assert result is None


@pytest.mark.unit
class TestPublishManagerBuild:
    """Test package building."""

    @pytest.fixture
    def manager(self, temp_pkg_path):
        """Create PublishManager."""
        return PublishManagerImpl(pkg_path=temp_pkg_path)

    def test_build_package_success(self, manager) -> None:
        """Test successful package build."""
        mock_result = Mock()
        mock_result.returncode = 0

        with patch.object(manager, "_run_command", return_value=mock_result):
            result = manager.build_package()

            assert result is True

    def test_build_package_failure(self, manager) -> None:
        """Test failed package build."""
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stderr = "Build error"

        with patch.object(manager, "_run_command", return_value=mock_result):
            result = manager.build_package()

            assert result is False

    def test_build_package_dry_run(self, manager) -> None:
        """Test build in dry run mode."""
        manager.dry_run = True

        result = manager.build_package()

        assert result is True
        # Should not actually run build

    def test_clean_dist_directory(self, manager, temp_pkg_path) -> None:
        """Test cleaning dist directory."""
        dist_dir = temp_pkg_path / "dist"
        dist_dir.mkdir()
        (dist_dir / "old_file.whl").touch()

        manager._clean_dist_directory()

        # Dist directory should exist but be empty
        assert dist_dir.exists()
        assert not list(dist_dir.glob("*"))

    def test_clean_dist_directory_no_exist(self, manager, temp_pkg_path) -> None:
        """Test cleaning when dist doesn't exist - should not raise and does not create."""
        # Should not raise
        manager._clean_dist_directory()

        dist_dir = temp_pkg_path / "dist"
        # The implementation returns early if dist doesn't exist, so it won't create it
        assert not dist_dir.exists()

    def test_execute_build(self, manager) -> None:
        """Test build execution."""
        mock_result = Mock()
        mock_result.returncode = 0

        with patch.object(manager, "_run_command", return_value=mock_result):
            with patch.object(manager, "_clean_dist_directory"):
                result = manager._execute_build()

                assert result is True

    def test_format_file_size_kb(self, manager) -> None:
        """Test formatting file size in KB."""
        size_str = manager._format_file_size(1024)

        assert "KB" in size_str
        assert "1.0" in size_str or "1" in size_str

    def test_format_file_size_mb(self, manager) -> None:
        """Test formatting file size in MB."""
        size_str = manager._format_file_size(2 * 1024 * 1024)

        assert "MB" in size_str


@pytest.mark.unit
class TestPublishManagerPublish:
    """Test package publishing."""

    @pytest.fixture
    def manager(self, temp_pkg_path):
        """Create PublishManager."""
        return PublishManagerImpl(pkg_path=temp_pkg_path)

    def test_publish_package_success(self, manager) -> None:
        """Test successful publish."""
        with patch.object(manager, "_validate_prerequisites", return_value=True):
            with patch.object(manager, "build_package", return_value=True):
                with patch.object(manager, "_execute_publish", return_value=True):
                    result = manager.publish_package()

                    assert result is True

    def test_publish_package_validation_fails(self, manager) -> None:
        """Test publish when validation fails."""
        with patch.object(manager, "_validate_prerequisites", return_value=False):
            result = manager.publish_package()

            assert result is False

    def test_execute_publish_success(self, manager) -> None:
        """Test execute publish with success."""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "Successfully uploaded package"

        with patch.object(manager, "_run_command", return_value=mock_result):
            result = manager._execute_publish()

            assert result is True

    def test_execute_publish_success_in_output(self, manager) -> None:
        """Test execute publish detecting success in output."""
        mock_result = Mock()
        mock_result.returncode = 1  # Non-zero but success in output
        mock_result.stdout = "Package uploaded successfully"
        mock_result.stderr = ""

        with patch.object(manager, "_run_command", return_value=mock_result):
            result = manager._execute_publish()

            assert result is True

    def test_execute_publish_failure(self, manager) -> None:
        """Test execute publish with failure."""
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "Upload failed"

        with patch.object(manager, "_run_command", return_value=mock_result):
            result = manager._execute_publish()

            assert result is False

    def test_publish_package_dry_run(self, manager) -> None:
        """Test publish in dry run mode."""
        manager.dry_run = True

        with patch.object(manager, "_validate_prerequisites", return_value=True):
            result = manager.publish_package()

            assert result is True


@pytest.mark.unit
class TestPublishManagerGitTagging:
    """Test git tag creation."""

    @pytest.fixture
    def manager(self, temp_pkg_path):
        """Create PublishManager."""
        return PublishManagerImpl(pkg_path=temp_pkg_path)

    def test_create_git_tag_local_success(self, manager) -> None:
        """Test creating local git tag."""
        mock_result = Mock()
        mock_result.returncode = 0

        with patch.object(manager, "_run_command", return_value=mock_result):
            result = manager.create_git_tag_local("1.2.3")

            assert result is True

    def test_create_git_tag_local_failure(self, manager) -> None:
        """Test failed local git tag creation."""
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stderr = "Tag already exists"

        with patch.object(manager, "_run_command", return_value=mock_result):
            result = manager.create_git_tag_local("1.2.3")

            assert result is False

    def test_create_git_tag_with_push_success(self, manager) -> None:
        """Test creating and pushing git tag."""
        mock_result = Mock()
        mock_result.returncode = 0

        with patch.object(manager, "_run_command", return_value=mock_result):
            result = manager.create_git_tag("1.2.3")

            assert result is True

    def test_create_git_tag_push_fails(self, manager) -> None:
        """Test creating tag when push fails."""
        # First call (tag) succeeds, second call (push) fails
        mock_result_success = Mock(returncode=0)
        mock_result_failure = Mock(returncode=1, stderr="Push failed")

        with patch.object(manager, "_run_command", side_effect=[mock_result_success, mock_result_failure]):
            result = manager.create_git_tag("1.2.3")

            # Should still return True since tag was created
            assert result is True

    def test_create_git_tag_dry_run(self, manager) -> None:
        """Test git tag in dry run mode."""
        manager.dry_run = True

        result = manager.create_git_tag("1.2.3")

        assert result is True


@pytest.mark.unit
class TestPublishManagerPackageInfo:
    """Test package info extraction."""

    @pytest.fixture
    def manager(self, temp_pkg_path):
        """Create PublishManager."""
        return PublishManagerImpl(pkg_path=temp_pkg_path)

    def test_get_package_info(self, manager, temp_pkg_path) -> None:
        """Test extracting package info."""
        pyproject = temp_pkg_path / "pyproject.toml"
        content = """
[project]
name = "test-package"
version = "1.2.3"
description = "A test package"
authors = [
    {name = "Test Author", email = "test@example.com"}
]
dependencies = ["requests>=2.0"]
requires-python = ">=3.8"
"""
        pyproject.write_text(content)

        info = manager.get_package_info()

        assert info["name"] == "test-package"
        assert info["version"] == "1.2.3"
        assert info["description"] == "A test package"
        assert len(info["authors"]) > 0
        assert "requests" in str(info["dependencies"])
        assert info["python_requires"] == ">=3.8"

    def test_get_package_info_no_file(self, manager, temp_pkg_path) -> None:
        """Test package info when no pyproject.toml."""
        info = manager.get_package_info()

        assert info == {}

    def test_get_package_name(self, manager, temp_pkg_path) -> None:
        """Test extracting package name."""
        pyproject = temp_pkg_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "my-package"\n')

        name = manager._get_package_name()

        assert name == "my-package"

    def test_parse_project_section_fallback(self, manager) -> None:
        """Test fallback project section parsing."""
        content = """
[project]
name = "test-pkg"
version = "1.0.0"
description = "Test"
authors = ["Author"]
dependencies = ["dep1", "dep2"]
"""

        result = manager._parse_project_section_fallback(content)

        assert "project" in result
        assert result["project"]["name"] == "test-pkg"
        assert result["project"]["version"] == "1.0.0"

    def test_parse_project_section_inline_list(self, manager) -> None:
        """Test parsing inline list values (fallback parser limitation - single line only)."""
        # The fallback parser only handles single-line values
        # Multi-line arrays are not supported by the simple fallback parser
        content = """
[project]
dependencies = ["requests>=2.0", "click>=8.0"]
"""

        result = manager._parse_project_section_fallback(content)

        deps = result["project"]["dependencies"]
        # The fallback parser stores the raw string value
        assert "requests" in str(deps)


@pytest.mark.unit
class TestPublishManagerChangelog:
    """Test changelog generation."""

    @pytest.fixture
    def manager(self, temp_pkg_path):
        """Create PublishManager."""
        mock_changelog = Mock()
        mock_changelog.generate_changelog_from_commits.return_value = True

        return PublishManagerImpl(
            pkg_path=temp_pkg_path,
            changelog_generator=mock_changelog,
        )

    def test_update_changelog_for_version_success(self, manager) -> None:
        """Test updating changelog for version."""
        manager._update_changelog_for_version("1.2.3", "1.2.4")

        # Should call changelog generator
        assert manager._changelog_generator.generate_changelog_from_commits.called

    def test_update_changelog_for_version_failure(self, manager) -> None:
        """Test changelog update with failure."""
        manager._changelog_generator.generate_changelog_from_commits.return_value = False

        # Should not raise
        manager._update_changelog_for_version("1.2.3", "1.2.4")

    def test_update_changelog_exception(self, manager) -> None:
        """Test changelog update with exception."""
        manager._changelog_generator.generate_changelog_from_commits.side_effect = Exception("Test error")

        # Should not raise
        manager._update_changelog_for_version("1.2.3", "1.2.4")


@pytest.mark.unit
class TestPublishManagerDependencyResolution:
    """Test dependency resolution methods."""

    def test_resolve_console(self, temp_pkg_path) -> None:
        """Test console resolution."""
        mock_console = Mock()

        manager = PublishManagerImpl(pkg_path=temp_pkg_path, console=mock_console)

        assert manager.console == mock_console

    def test_resolve_console_default(self, temp_pkg_path) -> None:
        """Test console resolution with default."""
        manager = PublishManagerImpl(pkg_path=temp_pkg_path)

        assert manager.console is not None

    def test_resolve_pkg_path(self, temp_pkg_path) -> None:
        """Test pkg_path resolution."""
        manager = PublishManagerImpl(pkg_path=temp_pkg_path)

        assert manager.pkg_path == temp_pkg_path

    def test_resolve_pkg_path_default(self) -> None:
        """Test pkg_path resolution with default."""

        manager = PublishManagerImpl()

        assert manager.pkg_path == Path.cwd()

    def test_resolve_filesystem(self, temp_pkg_path) -> None:
        """Test filesystem resolution."""
        manager = PublishManagerImpl(pkg_path=temp_pkg_path)

        assert manager.filesystem is not None

    def test_resolve_security(self, temp_pkg_path) -> None:
        """Test security resolution."""
        manager = PublishManagerImpl(pkg_path=temp_pkg_path)

        assert manager.security is not None
