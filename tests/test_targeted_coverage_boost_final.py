"""Targeted Coverage Boost - Final Push to 42%.
==========================================

Current Status: 21.44% coverage
Target: 42% coverage (20.56 percentage points needed)

This test file targets the single highest-impact module: tool_version_service.py
- 595 lines at only 13% coverage = 518 uncovered lines
- Contains 6 major classes with functional methods
- Uses proven patterns: dataclass instantiation + service mocking

Focus: Maximum coverage from tool_version_service.py alone could add ~8-10%
to overall coverage, getting us to 29-31% coverage.

Strategy: Comprehensive testing of all classes and methods with proper mocking.
"""

import stat
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest


class TestVersionInfoDataclass:
    """Test VersionInfo dataclass - guaranteed coverage from instantiation."""

    def test_version_info_basic_instantiation(self) -> None:
        """Test VersionInfo with basic fields."""
        from crackerjack.services.tool_version_service import VersionInfo

        version = VersionInfo(tool_name="ruff", current_version="0.1.0")
        assert version.tool_name == "ruff"
        assert version.current_version == "0.1.0"
        assert version.latest_version is None
        assert version.update_available is False
        assert version.error is None

    def test_version_info_full_instantiation(self) -> None:
        """Test VersionInfo with all fields."""
        from crackerjack.services.tool_version_service import VersionInfo

        version = VersionInfo(
            tool_name="pyright",
            current_version="1.1.0",
            latest_version="1.2.0",
            update_available=True,
            error="test error",
        )
        assert version.tool_name == "pyright"
        assert version.current_version == "1.1.0"
        assert version.latest_version == "1.2.0"
        assert version.update_available is True
        assert version.error == "test error"


class TestToolVersionService:
    """Test ToolVersionService - high coverage potential with proper mocking."""

    @pytest.fixture
    def mock_console(self):
        """Mock Rich Console."""
        mock = Mock()
        mock.print = Mock()
        return mock

    @pytest.fixture
    def tool_version_service(self, mock_console):
        """Create ToolVersionService instance."""
        from crackerjack.services.tool_version_service import ToolVersionService

        return ToolVersionService(mock_console)

    def test_init_configuration(self, tool_version_service) -> None:
        """Test service initialization."""
        assert tool_version_service.console is not None
        assert "ruff" in tool_version_service.tools_to_check
        assert "pyright" in tool_version_service.tools_to_check
        assert "pre-commit" in tool_version_service.tools_to_check
        assert "uv" in tool_version_service.tools_to_check

    @patch("subprocess.run")
    def test_get_ruff_version_success(self, mock_run, tool_version_service) -> None:
        """Test successful ruff version detection."""
        mock_run.return_value = Mock(returncode=0, stdout="ruff 0.1.0")

        version = tool_version_service._get_ruff_version()
        assert version == "0.1.0"
        mock_run.assert_called_once_with(
            ["ruff", "--version"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )

    @patch("subprocess.run")
    def test_get_ruff_version_failure(self, mock_run, tool_version_service) -> None:
        """Test ruff version detection failure."""
        mock_run.return_value = Mock(returncode=1)

        version = tool_version_service._get_ruff_version()
        assert version is None

    @patch("subprocess.run")
    def test_get_ruff_version_not_found(self, mock_run, tool_version_service) -> None:
        """Test ruff not found."""
        mock_run.side_effect = FileNotFoundError()

        version = tool_version_service._get_ruff_version()
        assert version is None

    @patch("subprocess.run")
    def test_get_pyright_version_success(self, mock_run, tool_version_service) -> None:
        """Test successful pyright version detection."""
        mock_run.return_value = Mock(returncode=0, stdout="pyright 1.1.0")

        version = tool_version_service._get_pyright_version()
        assert version == "1.1.0"

    @patch("subprocess.run")
    def test_get_precommit_version_success(self, mock_run, tool_version_service) -> None:
        """Test successful pre-commit version detection."""
        mock_run.return_value = Mock(returncode=0, stdout="pre-commit 2.20.0")

        version = tool_version_service._get_precommit_version()
        assert version == "2.20.0"

    @patch("subprocess.run")
    def test_get_uv_version_success(self, mock_run, tool_version_service) -> None:
        """Test successful uv version detection."""
        mock_run.return_value = Mock(returncode=0, stdout="uv 0.1.0")

        version = tool_version_service._get_uv_version()
        assert version == "0.1.0"

    def test_version_compare_basic(self, tool_version_service) -> None:
        """Test version comparison."""
        # Same versions
        assert tool_version_service._version_compare("1.0.0", "1.0.0") == 0

        # Current older
        assert tool_version_service._version_compare("1.0.0", "1.0.1") == -1

        # Current newer
        assert tool_version_service._version_compare("1.0.1", "1.0.0") == 1

    def test_version_compare_different_lengths(self, tool_version_service) -> None:
        """Test version comparison with different lengths."""
        assert tool_version_service._version_compare("1.0", "1.0.0") == -1
        assert tool_version_service._version_compare("1.0.0", "1.0") == 1
        assert tool_version_service._version_compare("1", "1.0") == 0

    def test_version_compare_invalid(self, tool_version_service) -> None:
        """Test version comparison with invalid versions."""
        assert tool_version_service._version_compare("invalid", "1.0.0") == 0
        assert tool_version_service._version_compare("1.0.0", "invalid") == 0

    @pytest.mark.asyncio
    async def test_fetch_latest_version_success(self, tool_version_service) -> None:
        """Test successful latest version fetch."""
        mock_response = AsyncMock()
        mock_response.json.return_value = {"info": {"version": "1.2.0"}}
        mock_response.raise_for_status.return_value = None

        with patch("aiohttp.ClientSession") as mock_session:
            mock_session_instance = AsyncMock()
            mock_session.return_value.__aenter__.return_value = mock_session_instance
            mock_session_instance.get.return_value.__aenter__.return_value = (
                mock_response
            )

            version = await tool_version_service._fetch_latest_version("ruff")
            assert version == "1.2.0"

    @pytest.mark.asyncio
    async def test_fetch_latest_version_failure(self, tool_version_service) -> None:
        """Test latest version fetch failure."""
        with patch("aiohttp.ClientSession") as mock_session:
            mock_session.return_value.__aenter__.return_value.get.side_effect = (
                Exception("Network error")
            )

            version = await tool_version_service._fetch_latest_version("ruff")
            assert version is None

    @pytest.mark.asyncio
    async def test_fetch_latest_version_unknown_tool(self, tool_version_service) -> None:
        """Test latest version fetch for unknown tool."""
        version = await tool_version_service._fetch_latest_version("unknown-tool")
        assert version is None

    @pytest.mark.asyncio
    @patch("subprocess.run")
    async def test_check_tool_updates_with_update(self, mock_run, tool_version_service) -> None:
        """Test check_tool_updates with update available."""
        mock_run.return_value = Mock(returncode=0, stdout="ruff 0.1.0")

        mock_response = AsyncMock()
        mock_response.json.return_value = {"info": {"version": "0.2.0"}}
        mock_response.raise_for_status.return_value = None

        with patch("aiohttp.ClientSession") as mock_session:
            mock_session_instance = AsyncMock()
            mock_session.return_value.__aenter__.return_value = mock_session_instance
            mock_session_instance.get.return_value.__aenter__.return_value = (
                mock_response
            )

            results = await tool_version_service.check_tool_updates()

            assert "ruff" in results
            assert results["ruff"].current_version == "0.1.0"
            assert results["ruff"].latest_version == "0.2.0"
            assert results["ruff"].update_available is True

    @pytest.mark.asyncio
    @patch("subprocess.run")
    async def test_check_tool_updates_no_update(self, mock_run, tool_version_service) -> None:
        """Test check_tool_updates with no update available."""
        mock_run.return_value = Mock(returncode=0, stdout="ruff 1.0.0")

        mock_response = AsyncMock()
        mock_response.json.return_value = {"info": {"version": "1.0.0"}}
        mock_response.raise_for_status.return_value = None

        with patch("aiohttp.ClientSession") as mock_session:
            mock_session_instance = AsyncMock()
            mock_session.return_value.__aenter__.return_value = mock_session_instance
            mock_session_instance.get.return_value.__aenter__.return_value = (
                mock_response
            )

            results = await tool_version_service.check_tool_updates()

            assert "ruff" in results
            assert results["ruff"].update_available is False


class TestConfigIntegrityService:
    """Test ConfigIntegrityService - significant coverage potential."""

    @pytest.fixture
    def mock_console(self):
        """Mock Rich Console."""
        mock = Mock()
        mock.print = Mock()
        return mock

    @pytest.fixture
    def temp_project_path(self):
        """Create temporary project directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    @pytest.fixture
    def config_integrity_service(self, mock_console, temp_project_path):
        """Create ConfigIntegrityService instance."""
        from crackerjack.services.tool_version_service import ConfigIntegrityService

        return ConfigIntegrityService(mock_console, temp_project_path)

    def test_init_configuration(self, config_integrity_service, temp_project_path) -> None:
        """Test service initialization."""
        assert config_integrity_service.console is not None
        assert config_integrity_service.project_path == temp_project_path
        assert config_integrity_service.cache_dir.name == "crackerjack"

    def test_check_config_integrity_no_files(self, config_integrity_service) -> None:
        """Test config integrity check with no config files."""
        drift = config_integrity_service.check_config_integrity()
        assert drift is True  # No required sections

    def test_check_config_integrity_with_files(
        self, config_integrity_service, temp_project_path,
    ) -> None:
        """Test config integrity check with config files."""
        # Create pyproject.toml
        pyproject_content = """
[tool.ruff]
line-length = 88

[tool.pyright]
strict = true

[tool.pytest.ini_options]
testpaths = ["tests"]
"""
        (temp_project_path / "pyproject.toml").write_text(pyproject_content)

        # Create pre-commit config
        (temp_project_path / ".pre-commit-config.yaml").write_text("repos: []")

        drift = config_integrity_service.check_config_integrity()
        assert drift is False  # All required sections present

    def test_has_required_config_sections_missing_file(self, config_integrity_service) -> None:
        """Test required config sections check with missing pyproject.toml."""
        has_sections = config_integrity_service._has_required_config_sections()
        assert has_sections is False

    def test_has_required_config_sections_missing_sections(
        self, config_integrity_service, temp_project_path,
    ) -> None:
        """Test required config sections check with missing sections."""
        # Create incomplete pyproject.toml
        (temp_project_path / "pyproject.toml").write_text("[tool.other] = {}")

        has_sections = config_integrity_service._has_required_config_sections()
        assert has_sections is False


class TestSmartSchedulingService:
    """Test SmartSchedulingService - complex scheduling logic."""

    @pytest.fixture
    def mock_console(self):
        """Mock Rich Console."""
        mock = Mock()
        mock.print = Mock()
        return mock

    @pytest.fixture
    def temp_project_path(self):
        """Create temporary project directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    @pytest.fixture
    def scheduling_service(self, mock_console, temp_project_path):
        """Create SmartSchedulingService instance."""
        from crackerjack.services.tool_version_service import SmartSchedulingService

        return SmartSchedulingService(mock_console, temp_project_path)

    def test_init_configuration(self, scheduling_service, temp_project_path) -> None:
        """Test service initialization."""
        assert scheduling_service.console is not None
        assert scheduling_service.project_path == temp_project_path
        assert scheduling_service.cache_dir.name == "crackerjack"

    @patch.dict("os.environ", {"CRACKERJACK_INIT_SCHEDULE": "disabled"})
    def test_should_scheduled_init_disabled(self, scheduling_service) -> None:
        """Test scheduled init when disabled."""
        should_init = scheduling_service.should_scheduled_init()
        assert should_init is False

    @patch.dict("os.environ", {"CRACKERJACK_INIT_SCHEDULE": "weekly"})
    def test_should_scheduled_init_weekly(self, scheduling_service) -> None:
        """Test weekly scheduling check."""
        with patch.object(
            scheduling_service, "_check_weekly_schedule", return_value=True,
        ):
            should_init = scheduling_service.should_scheduled_init()
            assert should_init is True

    @patch.dict("os.environ", {"CRACKERJACK_INIT_SCHEDULE": "commit-based"})
    def test_should_scheduled_init_commit_based(self, scheduling_service) -> None:
        """Test commit-based scheduling."""
        with patch.object(
            scheduling_service, "_check_commit_based_schedule", return_value=True,
        ):
            should_init = scheduling_service.should_scheduled_init()
            assert should_init is True

    @patch.dict("os.environ", {"CRACKERJACK_INIT_SCHEDULE": "activity-based"})
    def test_should_scheduled_init_activity_based(self, scheduling_service) -> None:
        """Test activity-based scheduling."""
        with patch.object(
            scheduling_service, "_check_activity_based_schedule", return_value=True,
        ):
            should_init = scheduling_service.should_scheduled_init()
            assert should_init is True

    def test_get_last_init_timestamp_no_file(self, scheduling_service) -> None:
        """Test getting last init timestamp when no file exists."""
        timestamp = scheduling_service._get_last_init_timestamp()
        # Should return 30 days ago
        assert timestamp < datetime.now()
        assert (datetime.now() - timestamp).days >= 29

    def test_record_init_timestamp(self, scheduling_service) -> None:
        """Test recording init timestamp."""
        scheduling_service.record_init_timestamp()

        # Check that timestamp file was created and is recent
        timestamp = scheduling_service._get_last_init_timestamp()
        assert (datetime.now() - timestamp).seconds < 10

    @patch("subprocess.run")
    def test_count_commits_since_init_success(self, mock_run, scheduling_service) -> None:
        """Test counting commits since init."""
        mock_run.return_value = Mock(returncode=0, stdout="commit1\ncommit2\ncommit3\n")

        count = scheduling_service._count_commits_since_init()
        assert count == 3

    @patch("subprocess.run")
    def test_count_commits_since_init_failure(self, mock_run, scheduling_service) -> None:
        """Test counting commits when git fails."""
        mock_run.return_value = Mock(returncode=1)

        count = scheduling_service._count_commits_since_init()
        assert count == 0

    @patch("subprocess.run")
    def test_has_recent_activity_true(self, mock_run, scheduling_service) -> None:
        """Test recent activity detection - true."""
        mock_run.return_value = Mock(returncode=0, stdout="recent commit\n")

        has_activity = scheduling_service._has_recent_activity()
        assert has_activity is True

    @patch("subprocess.run")
    def test_has_recent_activity_false(self, mock_run, scheduling_service) -> None:
        """Test recent activity detection - false."""
        mock_run.return_value = Mock(returncode=0, stdout="")

        has_activity = scheduling_service._has_recent_activity()
        assert has_activity is False


class TestUnifiedConfigurationService:
    """Test UnifiedConfigurationService - largest class with complex config logic."""

    @pytest.fixture
    def mock_console(self):
        """Mock Rich Console."""
        mock = Mock()
        mock.print = Mock()
        return mock

    @pytest.fixture
    def temp_project_path(self):
        """Create temporary project directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    @pytest.fixture
    def python_unified_config_service(self, mock_console, temp_project_path):
        """Create UnifiedConfigurationService for Python project."""
        from crackerjack.services.tool_version_service import (
            UnifiedConfigurationService,
        )

        # Create pyproject.toml to make it a Python project
        (temp_project_path / "pyproject.toml").write_text("[project]\nname = 'test'")
        return UnifiedConfigurationService(mock_console, temp_project_path)

    @pytest.fixture
    def node_unified_config_service(self, mock_console, temp_project_path):
        """Create UnifiedConfigurationService for Node project."""
        from crackerjack.services.tool_version_service import (
            UnifiedConfigurationService,
        )

        # Create package.json to make it a Node project
        (temp_project_path / "package.json").write_text('{"name": "test"}')
        return UnifiedConfigurationService(mock_console, temp_project_path)

    def test_detect_project_type_python(self, python_unified_config_service) -> None:
        """Test Python project type detection."""
        assert python_unified_config_service.project_type == "python"

    def test_detect_project_type_node(self, node_unified_config_service) -> None:
        """Test Node project type detection."""
        assert node_unified_config_service.project_type == "node"

    def test_detect_project_type_generic(self, mock_console, temp_project_path) -> None:
        """Test generic project type detection."""
        from crackerjack.services.tool_version_service import (
            UnifiedConfigurationService,
        )

        service = UnifiedConfigurationService(mock_console, temp_project_path)
        assert service.project_type == "generic"

    def test_get_unified_config_python(self, python_unified_config_service) -> None:
        """Test getting unified config for Python project."""
        config = python_unified_config_service.get_unified_config()

        assert config["project_type"] == "python"
        assert "tools" in config
        assert "hooks" in config
        assert "testing" in config
        assert "quality" in config

    def test_get_unified_config_caching(self, python_unified_config_service) -> None:
        """Test config caching."""
        config1 = python_unified_config_service.get_unified_config()
        config2 = python_unified_config_service.get_unified_config()

        # Should be the same object (cached)
        assert config1 is config2

    def test_get_tool_config_exists(
        self, python_unified_config_service, temp_project_path,
    ) -> None:
        """Test getting tool config that exists."""
        # Create pyproject.toml with ruff config
        pyproject_content = """
[tool.ruff]
line-length = 88
"""
        (temp_project_path / "pyproject.toml").write_text(pyproject_content)

        # Clear cache to reload config
        python_unified_config_service.config_cache.clear()

        tool_config = python_unified_config_service.get_tool_config("ruff")
        assert tool_config is not None
        assert tool_config["enabled"] is True

    def test_get_tool_config_not_exists(self, python_unified_config_service) -> None:
        """Test getting tool config that doesn't exist."""
        tool_config = python_unified_config_service.get_tool_config("nonexistent-tool")
        assert tool_config is None

    def test_validate_configuration_success(
        self, python_unified_config_service, temp_project_path,
    ) -> None:
        """Test configuration validation - success."""
        # Create complete pyproject.toml
        pyproject_content = """
[tool.ruff]
line-length = 88

[tool.pyright]
strict = true

[tool.pytest.ini_options]
testpaths = ["tests"]
"""
        (temp_project_path / "pyproject.toml").write_text(pyproject_content)

        # Clear cache to reload config
        python_unified_config_service.config_cache.clear()

        validation = python_unified_config_service.validate_configuration()
        assert validation["valid"] is True
        assert len(validation["errors"]) == 0

    def test_validate_configuration_missing_tools(self, python_unified_config_service) -> None:
        """Test configuration validation - missing required tools."""
        validation = python_unified_config_service.validate_configuration()
        assert validation["valid"] is False
        assert len(validation["errors"]) > 0


class TestEnhancedErrorCategorizationService:
    """Test EnhancedErrorCategorizationService - complex error analysis logic."""

    @pytest.fixture
    def mock_console(self):
        """Mock Rich Console."""
        mock = Mock()
        mock.print = Mock()
        return mock

    @pytest.fixture
    def temp_project_path(self):
        """Create temporary project directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    @pytest.fixture
    def error_categorization_service(self, mock_console, temp_project_path):
        """Create EnhancedErrorCategorizationService instance."""
        from crackerjack.services.tool_version_service import (
            EnhancedErrorCategorizationService,
        )

        return EnhancedErrorCategorizationService(mock_console, temp_project_path)

    def test_init_configuration(self, error_categorization_service) -> None:
        """Test service initialization."""
        assert error_categorization_service.console is not None
        assert "import_error" in error_categorization_service.error_patterns
        assert "syntax_error" in error_categorization_service.error_patterns
        assert "type_error" in error_categorization_service.error_patterns
        assert len(error_categorization_service.error_history) == 0

    def test_categorize_errors_import_error(self, error_categorization_service) -> None:
        """Test categorizing import errors."""
        error_text = "ModuleNotFoundError: No module named 'missing_module'"

        errors = error_categorization_service.categorize_errors(error_text)

        assert len(errors) == 1
        assert errors[0]["type"] == "import_error"
        assert errors[0]["category"] == "dependency"
        assert errors[0]["severity"] == "high"
        assert errors[0]["auto_fixable"] is True

    def test_categorize_errors_syntax_error(self, error_categorization_service) -> None:
        """Test categorizing syntax errors."""
        error_text = "SyntaxError: invalid syntax"

        errors = error_categorization_service.categorize_errors(error_text)

        assert len(errors) == 1
        assert errors[0]["type"] == "syntax_error"
        assert errors[0]["category"] == "syntax"
        assert errors[0]["severity"] == "critical"

    def test_categorize_errors_multiple(self, error_categorization_service) -> None:
        """Test categorizing multiple errors."""
        error_lines = [
            "ModuleNotFoundError: No module named 'test'",
            "SyntaxError: invalid syntax",
            "TypeError: unsupported operand type",
        ]

        errors = error_categorization_service.categorize_errors(error_lines)

        assert len(errors) == 3
        assert errors[0]["type"] in ["import_error", "syntax_error", "type_error"]

    def test_categorize_errors_unknown(self, error_categorization_service) -> None:
        """Test categorizing unknown errors."""
        error_text = "This is an unknown error that doesn't match patterns"

        errors = error_categorization_service.categorize_errors(error_text)

        assert len(errors) == 1
        assert errors[0]["type"] == "unknown"
        assert errors[0]["category"] == "unknown"
        assert errors[0]["auto_fixable"] is False

    def test_get_error_summary_empty(self, error_categorization_service) -> None:
        """Test error summary with no errors."""
        summary = error_categorization_service.get_error_summary([])

        assert summary["total_errors"] == 0
        assert len(summary["by_category"]) == 0
        assert len(summary["critical_issues"]) == 0

    def test_get_error_summary_with_errors(self, error_categorization_service) -> None:
        """Test error summary with errors."""
        error_text = "ModuleNotFoundError: No module named 'test'"
        errors = error_categorization_service.categorize_errors(error_text)

        summary = error_categorization_service.get_error_summary(errors)

        assert summary["total_errors"] == 1
        assert summary["by_category"]["dependency"] == 1
        assert summary["by_severity"]["high"] == 1
        assert summary["auto_fixable_count"] == 1
        assert summary["auto_fixable_percentage"] == 100.0

    def test_print_error_report_no_errors(self, error_categorization_service) -> None:
        """Test printing error report with no errors."""
        error_categorization_service.print_error_report([])

        error_categorization_service.console.print.assert_called_with(
            "[green]✅ No errors found ! [/green]",
        )

    def test_print_error_report_with_errors(self, error_categorization_service) -> None:
        """Test printing error report with errors."""
        error_text = "ModuleNotFoundError: No module named 'test'"
        errors = error_categorization_service.categorize_errors(error_text)

        error_categorization_service.print_error_report(errors)

        # Should have printed multiple lines of the report
        assert error_categorization_service.console.print.call_count > 1


class TestGitHookService:
    """Test GitHookService - git hook management functionality."""

    @pytest.fixture
    def mock_console(self):
        """Mock Rich Console."""
        mock = Mock()
        mock.print = Mock()
        return mock

    @pytest.fixture
    def temp_project_path(self):
        """Create temporary project directory with git hooks."""
        with tempfile.TemporaryDirectory() as temp_dir:
            project_path = Path(temp_dir)
            hooks_dir = project_path / ".git" / "hooks"
            hooks_dir.mkdir(parents=True, exist_ok=True)
            yield project_path

    @pytest.fixture
    def git_hook_service(self, mock_console, temp_project_path):
        """Create GitHookService instance."""
        from crackerjack.services.tool_version_service import GitHookService

        return GitHookService(mock_console, temp_project_path)

    def test_init_configuration(self, git_hook_service, temp_project_path) -> None:
        """Test service initialization."""
        assert git_hook_service.console is not None
        assert git_hook_service.project_path == temp_project_path
        assert git_hook_service.hooks_dir == temp_project_path / ".git" / "hooks"

    def test_install_pre_commit_hook_success(self, git_hook_service) -> None:
        """Test successful pre-commit hook installation."""
        result = git_hook_service.install_pre_commit_hook()

        assert result is True
        hook_path = git_hook_service.hooks_dir / "pre-commit"
        assert hook_path.exists()
        assert hook_path.stat().st_mode & stat.S_IEXEC  # Executable bit

    def test_install_pre_commit_hook_exists_no_force(self, git_hook_service) -> None:
        """Test installing pre-commit hook when it already exists."""
        # Create existing hook
        hook_path = git_hook_service.hooks_dir / "pre-commit"
        hook_path.write_text("#!/bin/bash\necho 'existing hook'")

        result = git_hook_service.install_pre_commit_hook(force=False)
        assert result is False

    def test_install_pre_commit_hook_exists_with_force(self, git_hook_service) -> None:
        """Test installing pre-commit hook with force overwrite."""
        # Create existing hook
        hook_path = git_hook_service.hooks_dir / "pre-commit"
        hook_path.write_text("#!/bin/bash\necho 'existing hook'")

        result = git_hook_service.install_pre_commit_hook(force=True)
        assert result is True

        # Should contain Crackerjack hook content
        content = hook_path.read_text()
        assert "crackerjack" in content.lower()

    def test_install_pre_commit_hook_no_git(self, mock_console, temp_project_path) -> None:
        """Test installing pre-commit hook when no .git directory exists."""
        from crackerjack.services.tool_version_service import GitHookService

        # Create service with directory without .git
        no_git_path = temp_project_path / "no_git"
        no_git_path.mkdir()
        service = GitHookService(mock_console, no_git_path)

        result = service.install_pre_commit_hook()
        assert result is False

    def test_check_init_needed_quick_no_pyproject(self, git_hook_service) -> None:
        """Test quick init check when no pyproject.toml."""
        result = git_hook_service.check_init_needed_quick()
        assert result == 1

    def test_check_init_needed_quick_old_precommit(
        self, git_hook_service, temp_project_path,
    ) -> None:
        """Test quick init check with old pre-commit config."""
        # Create pyproject.toml
        (temp_project_path / "pyproject.toml").write_text("[project]\nname = 'test'")

        # Create old pre-commit config (simulate 35 days old)
        pre_commit_path = temp_project_path / ".pre-commit-config.yaml"
        pre_commit_path.write_text("repos: []")

        # Mock file to be 35 days old
        old_time = datetime.now().timestamp() - (35 * 86400)
        with patch.object(pre_commit_path, "stat") as mock_stat:
            mock_stat.return_value.st_mtime = old_time
            result = git_hook_service.check_init_needed_quick()
            assert result == 1

    def test_check_init_needed_quick_recent(self, git_hook_service, temp_project_path) -> None:
        """Test quick init check with recent pre-commit config."""
        # Create pyproject.toml
        (temp_project_path / "pyproject.toml").write_text("[project]\nname = 'test'")

        # Create recent pre-commit config
        pre_commit_path = temp_project_path / ".pre-commit-config.yaml"
        pre_commit_path.write_text("repos: []")

        result = git_hook_service.check_init_needed_quick()
        assert result == 0

    def test_is_hook_installed_false(self, git_hook_service) -> None:
        """Test checking if hook is installed - false."""
        is_installed = git_hook_service.is_hook_installed()
        assert is_installed is False

    def test_is_hook_installed_true(self, git_hook_service) -> None:
        """Test checking if hook is installed - true."""
        # Install hook first
        git_hook_service.install_pre_commit_hook()

        is_installed = git_hook_service.is_hook_installed()
        assert is_installed is True

    def test_remove_pre_commit_hook_not_exists(self, git_hook_service) -> None:
        """Test removing pre-commit hook that doesn't exist."""
        result = git_hook_service.remove_pre_commit_hook()
        assert result is False

    def test_remove_pre_commit_hook_success(self, git_hook_service) -> None:
        """Test successful pre-commit hook removal."""
        # Install hook first
        git_hook_service.install_pre_commit_hook()

        # Mock the hook content check since we know our hook contains identifiable content
        hook_path = git_hook_service.hooks_dir / "pre-commit"
        content = hook_path.read_text()
        # Add the identifier to the existing content
        hook_path.write_text("Crackerjack pre-commit hook\n" + content)

        result = git_hook_service.remove_pre_commit_hook()
        assert result is True
        assert not hook_path.exists()
