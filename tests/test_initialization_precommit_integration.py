"""Integration tests for initialization service pre-commit handling."""

import tempfile
from pathlib import Path

import pytest
from rich.console import Console

from crackerjack.services.config_merge import ConfigMergeService
from crackerjack.services.initialization import InitializationService
from crackerjack.services.filesystem import FileSystemService
from crackerjack.services.git import GitService


@pytest.fixture
def console():
    """Create a console fixture."""
    return Console()


@pytest.fixture
def filesystem():
    """Create a filesystem service fixture."""
    return FileSystemService()


@pytest.fixture
def git_service(console):
    """Create a git service fixture."""
    return GitService(console, Path.cwd())


class TestInitializationPrecommitHandling:
    """Integration tests for pre-commit handling in initialization."""

    def _build_config_merge_service(
        self, console, filesystem, git_service
    ) -> ConfigMergeService:
        class DummyLogger:
            def info(self, message: str, **kwargs: object) -> None:
                return None

            def warning(self, message: str, **kwargs: object) -> None:
                return None

            def error(self, message: str, **kwargs: object) -> None:
                return None

            def debug(self, message: str, **kwargs: object) -> None:
                return None

        return ConfigMergeService(
            console=console,
            filesystem=filesystem,
            git_service=git_service,
            logger=DummyLogger(),
        )

    def _build_initialization_service(
        self, console, filesystem, git_service, pkg_path: Path
    ) -> InitializationService:
        config_merge_service = self._build_config_merge_service(
            console, filesystem, git_service
        )
        return InitializationService(
            console=console,
            filesystem=filesystem,
            git_service=git_service,
            pkg_path=pkg_path,
            config_merge_service=config_merge_service,
        )

    def test_precommit_config_not_copied_during_initialization(
        self, console, filesystem, git_service
    ):
        """Test that .pre-commit-config.yaml is not copied during project initialization."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            target_path = Path(tmp_dir)
            pkg_path = Path(tmp_dir)

            # Create initialization service
            init_service = self._build_initialization_service(
                console, filesystem, git_service, pkg_path
            )

            # Run initialization
            result = init_service.initialize_project_full(target_path)

            # Verify initialization was successful
            assert result["success"] is True

            # Check that .pre-commit-config.yaml was not created in the target directory
            precommit_config_path = target_path / ".pre-commit-config.yaml"
            assert not precommit_config_path.exists(), \
                ".pre-commit-config.yaml should not be copied during initialization"

            # Verify that other expected files were created
            expected_files = [
                "pyproject.toml",
                ".gitignore",
                "CLAUDE.md",
                "RULES.md"
            ]

            for filename in expected_files:
                file_path = target_path / filename
                assert file_path.exists(), f"{filename} should be created during initialization"

    def test_config_files_dict_excludes_precommit(
        self, console, filesystem, git_service
    ):
        """Test that the config files dictionary excludes pre-commit configuration."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            pkg_path = Path(tmp_dir)
            init_service = self._build_initialization_service(
                console, filesystem, git_service, pkg_path
            )

            # Get the config files dictionary
            config_files = init_service._get_config_files()

            # Verify that .pre-commit-config.yaml is not in the dictionary
            assert ".pre-commit-config.yaml" not in config_files, \
                "Pre-commit config should not be in the config files dictionary"

            # Verify that expected files are still present
            expected_keys = {
                "pyproject.toml",
                ".gitignore",
                "CLAUDE.md",
                "RULES.md",
                "example.mcp.json"
            }
            assert set(config_files.keys()) == expected_keys, \
                "Config files dictionary should contain expected keys"

    def test_initialization_with_force_flag_still_skips_precommit(
        self, console, filesystem, git_service
    ):
        """Test that even with force flag, pre-commit config is not copied."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            target_path = Path(tmp_dir)
            pkg_path = Path(tmp_dir)

            # Create initialization service
            init_service = self._build_initialization_service(
                console, filesystem, git_service, pkg_path
            )

            # Run initialization with force flag
            result = init_service.initialize_project_full(target_path, force=True)

            # Verify initialization was successful
            assert result["success"] is True

            # Check that .pre-commit-config.yaml was not created
            precommit_config_path = target_path / ".pre-commit-config.yaml"
            assert not precommit_config_path.exists(), \
                ".pre-commit-config.yaml should not be copied even with force flag"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
