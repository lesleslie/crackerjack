import tempfile
from pathlib import Path
from unittest.mock import Mock, patch


class TestSimpleToolVersionService:
    def test_version_info_dataclass(self) -> None:
        from crackerjack.services.tool_version_service import VersionInfo

        version = VersionInfo("ruff", "1.0.0")
        assert version.tool_name == "ruff"
        assert version.current_version == "1.0.0"

        version_full = VersionInfo(
            tool_name="pyright",
            current_version="1.1.0",
            latest_version="1.2.0",
            update_available=True,
            error="test error",
        )
        assert version_full.update_available is True
        assert version_full.error == "test error"

    def test_tool_version_service_init(self) -> None:
        from crackerjack.services.tool_version_service import ToolVersionService

        mock_console = Mock()
        service = ToolVersionService(mock_console)

        assert service.console == mock_console
        assert "ruff" in service.tools_to_check
        assert "pyright" in service.tools_to_check
        assert "pre-commit" in service.tools_to_check
        assert "uv" in service.tools_to_check

    @patch("subprocess.run")
    def test_version_methods_basic(self, mock_run) -> None:
        from crackerjack.services.tool_version_service import ToolVersionService

        mock_console = Mock()
        service = ToolVersionService(mock_console)

        mock_run.return_value = Mock(returncode=0, stdout="ruff 1.0.0")
        version = service._get_ruff_version()
        assert version == "1.0.0"

        mock_run.return_value = Mock(returncode=1, stdout="")
        version = service._get_ruff_version()
        assert version is None

        mock_run.side_effect = FileNotFoundError()
        version = service._get_ruff_version()
        assert version is None

    def test_version_compare_logic(self) -> None:
        from crackerjack.services.tool_version_service import ToolVersionService

        mock_console = Mock()
        service = ToolVersionService(mock_console)

        assert service._version_compare("1.0.0", "1.0.0") == 0
        assert service._version_compare("1.0.0", "1.0.1") == -1
        assert service._version_compare("1.0.1", "1.0.0") == 1

        assert service._version_compare("1.0", "1.0.0") == -1
        assert service._version_compare("1.0.0", "1.0") == 1

        assert service._version_compare("invalid", "1.0.0") == 0

    def test_config_integrity_service_init(self) -> None:
        from crackerjack.services.tool_version_service import ConfigIntegrityService

        with tempfile.TemporaryDirectory() as temp_dir:
            project_path = Path(temp_dir)
            mock_console = Mock()

            service = ConfigIntegrityService(mock_console, project_path)

            assert service.console == mock_console
            assert service.project_path == project_path
            assert service.cache_dir.name == "crackerjack"

    def test_config_integrity_basic_checks(self) -> None:
        from crackerjack.services.tool_version_service import ConfigIntegrityService

        with tempfile.TemporaryDirectory() as temp_dir:
            project_path = Path(temp_dir)
            mock_console = Mock()
            service = ConfigIntegrityService(mock_console, project_path)

            drift = service.check_config_integrity()
            assert drift is True

            pyproject_content = """
[tool.ruff]
line-length = 88

[tool.pyright]
strict = true

[tool.pytest.ini_options]
testpaths = ["tests"]

[tool.ruff]
line-length = 88

[tool.pyright]
strict = true
"""
            (project_path / "pyproject.toml").write_text(pyproject_content.strip())
            service = UnifiedConfigurationService(mock_console, project_path)

            config = service.get_unified_config()
            assert config["project_type"] == "python"
            assert "tools" in config
            assert "testing" in config
            assert "quality" in config

            config2 = service.get_unified_config()
            assert config is config2

    def test_error_categorization_service_init(self) -> None:
        from crackerjack.services.tool_version_service import (
            EnhancedErrorCategorizationService,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            project_path = Path(temp_dir)
            mock_console = Mock()

            service = EnhancedErrorCategorizationService(mock_console, project_path)

            assert service.console == mock_console
            assert service.project_path == project_path
            assert len(service.error_patterns) > 0
            assert "import_error" in service.error_patterns
            assert len(service.error_history) == 0

    def test_error_categorization_basic(self) -> None:
        from crackerjack.services.tool_version_service import (
            EnhancedErrorCategorizationService,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            project_path = Path(temp_dir)
            mock_console = Mock()
            service = EnhancedErrorCategorizationService(mock_console, project_path)

            summary = service.get_error_summary([])
            assert summary["total_errors"] == 0
            assert len(summary["by_category"]) == 0

            assert service._get_severity_score("critical") == 1
            assert service._get_severity_score("high") == 2
            assert service._get_severity_score("medium") == 3
            assert service._get_severity_score("low") == 4

    def test_git_hook_service_init(self) -> None:
        from crackerjack.services.tool_version_service import GitHookService

        with tempfile.TemporaryDirectory() as temp_dir:
            project_path = Path(temp_dir)
            hooks_dir = project_path / ".git" / "hooks"
            hooks_dir.mkdir(parents=True)
            mock_console = Mock()

            service = GitHookService(mock_console, project_path)

            assert service.console == mock_console
            assert service.project_path == project_path
            assert service.hooks_dir == hooks_dir

    def test_git_hook_basic_functionality(self) -> None:
        from crackerjack.services.tool_version_service import GitHookService

        with tempfile.TemporaryDirectory() as temp_dir:
            project_path = Path(temp_dir)
            hooks_dir = project_path / ".git" / "hooks"
            hooks_dir.mkdir(parents=True)
            mock_console = Mock()
            service = GitHookService(mock_console, project_path)

            assert service.is_hook_installed() is False

            assert service.check_init_needed_quick() == 1

            (project_path / "pyproject.toml").write_text("[project]\nname = 'test'")
            assert service.check_init_needed_quick() == 0

            script = service._create_pre_commit_hook_script()
            assert "#! / bin / bash" in script
            assert "python" in script.lower()
