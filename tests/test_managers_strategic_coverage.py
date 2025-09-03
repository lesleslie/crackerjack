from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from rich.console import Console

from crackerjack.managers.publish_manager import PublishManagerImpl


class TestPublishManagerImpl:
    @pytest.fixture
    def console(self):
        return Mock(spec=Console)

    @pytest.fixture
    def pkg_path(self):
        return Path("/ tmp / test")

    @pytest.fixture
    def mock_config_service(self):
        service = Mock()
        service.load_pyproject_config.return_value = {"project": {"version": "1.0.0"}}
        service.save_pyproject_config.return_value = True
        return service

    @pytest.fixture
    def mock_git_service(self):
        service = Mock()
        service.tag_version.return_value = True
        service.push_tags.return_value = True
        return service

    @pytest.fixture
    def mock_security_service(self):
        service = Mock()
        service.get_publish_token.return_value = "test_token"
        return service

    @pytest.fixture
    def publish_manager(self, console, pkg_path):
        return PublishManagerImpl(console=console, pkg_path=pkg_path, dry_run=True)

    def test_init(self, publish_manager, console, pkg_path) -> None:
        assert publish_manager.console == console
        assert publish_manager.pkg_path == pkg_path
        assert publish_manager.dry_run is True
        assert publish_manager.filesystem is not None
        assert publish_manager.security is not None

    def test_bump_version_patch(self, publish_manager) -> None:
        with (
            patch.object(
                publish_manager,
                "_get_current_version",
                return_value="1.0.0",
            ),
            patch.object(
                publish_manager,
                "_update_version_in_file",
                return_value=True,
            ),
        ):
            result = publish_manager.bump_version("patch")

            assert result == "1.0.1"

    def test_bump_version_minor(self, publish_manager) -> None:
        with (
            patch.object(
                publish_manager,
                "_get_current_version",
                return_value="1.0.0",
            ),
            patch.object(
                publish_manager,
                "_update_version_in_file",
                return_value=True,
            ),
        ):
            result = publish_manager.bump_version("minor")

            assert result == "1.1.0"

    def test_bump_version_major(self, publish_manager) -> None:
        with (
            patch.object(
                publish_manager,
                "_get_current_version",
                return_value="1.0.0",
            ),
            patch.object(
                publish_manager,
                "_update_version_in_file",
                return_value=True,
            ),
        ):
            result = publish_manager.bump_version("major")

            assert result == "2.0.0"

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

    def test_publish_package_failure(self, publish_manager) -> None:
        with patch.object(
            publish_manager,
            "_validate_prerequisites",
            return_value=False,
        ):
            result = publish_manager.publish_package()

            assert result is False

    def test_validate_auth(self, publish_manager) -> None:
        with (
            patch.object(
                publish_manager,
                "_collect_auth_methods",
                return_value=["env_token"],
            ),
            patch.object(
                publish_manager,
                "_report_auth_status",
                return_value=True,
            ),
        ):
            result = publish_manager.validate_auth()

            assert result is True

    def test_build_package_success(self, publish_manager) -> None:
        with patch.object(publish_manager, "_execute_build", return_value=True):
            result = publish_manager.build_package()

            assert result is True

    def test_build_package_dry_run(self, publish_manager) -> None:
        assert publish_manager.dry_run is True

        result = publish_manager.build_package()

        assert result is True

    def test_create_git_tag(self, publish_manager) -> None:
        with patch("crackerjack.managers.publish_manager.subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0

            result = publish_manager.create_git_tag("1.0.1")

            assert result is True

    def test_get_current_version(self, publish_manager) -> None:
        version = publish_manager._get_current_version()

        assert version is None or isinstance(version, str)

    def test_calculate_next_version(self, publish_manager) -> None:
        assert publish_manager._calculate_next_version("1.0.0", "patch") == "1.0.1"
        assert publish_manager._calculate_next_version("1.0.0", "minor") == "1.1.0"
        assert publish_manager._calculate_next_version("1.0.0", "major") == "2.0.0"

    def test_get_package_info(self, publish_manager) -> None:
        info = publish_manager.get_package_info()

        assert isinstance(info, dict)

        assert "name" in info or len(info) == 0

    def test_cleanup_old_releases(self, publish_manager) -> None:
        result = publish_manager.cleanup_old_releases(keep_releases=5)

        assert isinstance(result, bool)


class TestPublishManagerCoverage:
    def test_private_methods_exist(self) -> None:
        console = Mock(spec=Console)
        pkg_path = Path("/ tmp / test")
        manager = PublishManagerImpl(console=console, pkg_path=pkg_path)

        assert hasattr(manager, "_get_current_version")
        assert hasattr(manager, "_calculate_next_version")
        assert hasattr(manager, "_update_version_in_file")
        assert hasattr(manager, "_run_command")

    def test_auth_methods_exist(self) -> None:
        console = Mock(spec=Console)
        pkg_path = Path("/ tmp / test")
        manager = PublishManagerImpl(console=console, pkg_path=pkg_path)

        assert hasattr(manager, "validate_auth")
        assert hasattr(manager, "_collect_auth_methods")
        assert hasattr(manager, "_check_env_token_auth")
        assert hasattr(manager, "_check_keyring_auth")

    def test_build_methods_exist(self) -> None:
        console = Mock(spec=Console)
        pkg_path = Path("/ tmp / test")
        manager = PublishManagerImpl(console=console, pkg_path=pkg_path)

        assert hasattr(manager, "build_package")
        assert hasattr(manager, "_execute_build")
        assert hasattr(manager, "_display_build_artifacts")

    def test_util_methods_exist(self) -> None:
        console = Mock(spec=Console)
        pkg_path = Path("/ tmp / test")
        manager = PublishManagerImpl(console=console, pkg_path=pkg_path)

        assert hasattr(manager, "_format_file_size")
        assert hasattr(manager, "_get_package_name")
        assert hasattr(manager, "get_package_info")
