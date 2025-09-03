import os
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest
from rich.console import Console

try:
    from crackerjack.services.tool_version_service import (
        ConfigIntegrityService,
        EnhancedErrorCategorizationService,
        GitHookService,
        ToolVersionService,
        VersionInfo,
    )
except ImportError:
    pytest.skip("tool_version_service not available", allow_module_level=True)


class TestToolVersionServiceStrategic:
    @pytest.fixture
    def console(self) -> Console:
        return Mock(spec=Console)

    @pytest.fixture
    def service(self, console: Console) -> ToolVersionService:
        return ToolVersionService(console)

    @pytest.fixture
    def temp_project_path(self) -> Path:
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_version_info_dataclass_complete(self) -> None:
        basic = VersionInfo("test - tool", "1.0.0")
        assert basic.tool_name == "test - tool"
        assert basic.current_version == "1.0.0"
        assert basic.latest_version is None
        assert basic.update_available is False
        assert basic.error is None

        full = VersionInfo(
            tool_name="ruff",
            current_version="0.1.6",
            latest_version="0.2.0",
            update_available=True,
            error="Network timeout",
        )
        assert full.tool_name == "ruff"
        assert full.current_version == "0.1.6"
        assert full.latest_version == "0.2.0"
        assert full.update_available is True
        assert full.error == "Network timeout"

    def test_service_initialization(
        self, service: ToolVersionService, console: Console
    ) -> None:
        assert service.console == console
        assert hasattr(service, "tools_to_check")
        assert isinstance(service.tools_to_check, dict)

        expected_tools = {"ruff", "pyright", "pre - commit", "uv"}
        assert set(service.tools_to_check.keys()) == expected_tools

        for tool_name, method in service.tools_to_check.items():
            assert callable(method)

    @patch("subprocess.run")
    def test_get_ruff_version(
        self, mock_run: Mock, service: ToolVersionService
    ) -> None:
        mock_run.return_value = Mock(
            stdout="ruff 0.1.6\nCompiled with Rust 1.75.0", returncode=0
        )
        result = service._get_ruff_version()
        assert result == "1.75.0"
        mock_run.assert_called_with(
            ["ruff", "- - version"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )

        mock_run.return_value = Mock(stdout="ruff 0.1.6", returncode=0)
        result = service._get_ruff_version()
        assert result == "0.1.6"

        mock_run.side_effect = FileNotFoundError("Command not found")
        result = service._get_ruff_version()
        assert result is None

        mock_run.side_effect = subprocess.TimeoutExpired(["ruff", "- - version"], 10)
        result = service._get_ruff_version()
        assert result is None

        mock_run.side_effect = None
        mock_run.return_value = Mock(stdout="", returncode=1)
        result = service._get_ruff_version()
        assert result is None

    @patch("subprocess.run")
    def test_get_pyright_version(
        self, mock_run: Mock, service: ToolVersionService
    ) -> None:
        mock_run.return_value = Mock(
            stdout="pyright 1.1.365\nNode.js v18.17.0", returncode=0
        )
        result = service._get_pyright_version()
        assert result == "v18.17.0"

        mock_run.return_value = Mock(stdout="pyright 1.1.365", returncode=0)
        result = service._get_pyright_version()
        assert result == "1.1.365"

    @patch("subprocess.run")
    def test_get_precommit_version(
        self, mock_run: Mock, service: ToolVersionService
    ) -> None:
        mock_run.return_value = Mock(stdout="pre - commit 3.5.0", returncode=0)
        result = service._get_precommit_version()
        assert "3.5.0" in result

    @patch("subprocess.run")
    def test_get_uv_version(self, mock_run: Mock, service: ToolVersionService) -> None:
        mock_run.return_value = Mock(stdout="uv 0.2.18 (Cargo 1.75.0)", returncode=0)
        result = service._get_uv_version()
        assert result == "1.75.0)"

        mock_run.return_value = Mock(stdout="uv 0.2.18", returncode=0)
        result = service._get_uv_version()
        assert result == "0.2.18"

    def test_version_compare_comprehensive(self, service: ToolVersionService) -> None:
        compare = service._version_compare

        assert compare("1.0.0", "1.0.0") == 0
        assert compare("2.1.5", "2.1.5") == 0

        assert compare("1.0.0", "1.0.1") < 0
        assert compare("1.0.0", "1.1.0") < 0
        assert compare("1.0.0", "2.0.0") < 0

        assert compare("1.0.1", "1.0.0") > 0
        assert compare("1.1.0", "1.0.0") > 0
        assert compare("2.0.0", "1.0.0") > 0

        assert compare("1.0", "1.0.0") < 0
        assert compare("1.0.0", "1.0") > 0

    def test_parse_version_parts(self, service: ToolVersionService) -> None:
        parts, length = service._parse_version_parts("1.2.3")
        assert parts == [1, 2, 3]
        assert length == 3

        parts, length = service._parse_version_parts("2.0")
        assert parts == [2, 0]
        assert length == 2

    def test_normalize_version_parts(self, service: ToolVersionService) -> None:
        current = [1, 0]
        latest = [1, 0, 1]

        norm_current, norm_latest = service._normalize_version_parts(current, latest)
        assert norm_current == [1, 0, 0]
        assert norm_latest == [1, 0, 1]

    def test_create_installed_version_info(self, service: ToolVersionService) -> None:
        info = service._create_installed_version_info("ruff", "0.1.6", "0.2.0")
        assert info.tool_name == "ruff"
        assert info.current_version == "0.1.6"
        assert info.latest_version == "0.2.0"
        assert info.update_available is True
        assert info.error is None

        info = service._create_installed_version_info("ruff", "0.2.0", "0.2.0")
        assert info.update_available is False

        info = service._create_installed_version_info("ruff", "0.1.6", None)
        assert info.latest_version is None
        assert info.update_available is False

    def test_create_missing_tool_info(self, service: ToolVersionService) -> None:
        info = service._create_missing_tool_info("missing - tool")
        assert info.tool_name == "missing - tool"
        assert info.current_version == "not installed"
        assert info.latest_version is None
        assert info.update_available is False
        assert "not found or not installed" in info.error

    def test_create_error_version_info(self, service: ToolVersionService) -> None:
        error = Exception("Network timeout")
        info = service._create_error_version_info("test - tool", error)
        assert info.tool_name == "test - tool"
        assert info.current_version == "unknown"
        assert info.latest_version is None
        assert info.update_available is False
        assert "Network timeout" in info.error

    @pytest.mark.asyncio
    async def test_check_single_tool(self, service: ToolVersionService) -> None:
        version_getter = Mock(return_value="1.0.0")

        with patch.object(service, "_fetch_latest_version", return_value="1.1.0"):
            result = await service._check_single_tool("test - tool", version_getter)
            assert result.tool_name == "test - tool"
            assert result.current_version == "1.0.0"
            assert result.latest_version == "1.1.0"
            assert result.update_available is True

        version_getter = Mock(return_value=None)
        result = await service._check_single_tool("missing - tool", version_getter)
        assert result.current_version == "not installed"

        version_getter = Mock(side_effect=Exception("Error"))
        result = await service._check_single_tool("error - tool", version_getter)
        assert result.current_version == "unknown"
        assert "Error" in result.error

    @pytest.mark.asyncio
    async def test_check_tool_updates(self, service: ToolVersionService) -> None:
        with patch.object(service, "_check_single_tool") as mock_check:
            mock_check.return_value = VersionInfo("test - tool", "1.0.0", "1.1.0", True)

            results = await service.check_tool_updates()

            assert len(results) == 4
            assert all(
                tool in results for tool in ["ruff", "pyright", "pre - commit", "uv"]
            )
            assert mock_check.call_count == 4

    @pytest.mark.asyncio
    async def test_fetch_latest_version(self, service: ToolVersionService) -> None:
        mock_response_data = {"info": {"version": "1.2.3"}}

        mock_response = Mock()
        mock_response.json = AsyncMock(return_value=mock_response_data)
        mock_response.raise_for_status = Mock()
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        mock_session = Mock()
        mock_session.get = Mock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            result = await service._fetch_latest_version("ruff")
            assert result == "1.2.3"

        result = await service._fetch_latest_version("unknown - tool")
        assert result is None

        with patch("aiohttp.ClientSession", side_effect=Exception("Network error")):
            result = await service._fetch_latest_version("ruff")
            assert result is None


class TestConfigIntegrityServiceStrategic:
    @pytest.fixture
    def console(self) -> Console:
        return Mock(spec=Console)

    @pytest.fixture
    def temp_project(self) -> Path:
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)

            (project_path / "pyproject.toml").touch()
            (project_path / ".pre - commit - config.yaml").touch()
            yield project_path

    @pytest.fixture
    def service(self, console: Console, temp_project: Path) -> ConfigIntegrityService:
        return ConfigIntegrityService(console, temp_project)

    def test_service_initialization(
        self, service: ConfigIntegrityService, console: Console, temp_project: Path
    ) -> None:
        assert service.console == console
        assert service.project_path == temp_project
        assert service.cache_dir == Path.home() / ".cache" / "crackerjack"
        assert service.cache_dir.exists()

    def test_check_config_integrity(
        self, service: ConfigIntegrityService, temp_project: Path
    ) -> None:
        results = service.categorize_errors(error_text)
        assert len(results) >= 3

        for i in range(len(results) - 1):
            assert results[i]["priority"] <= results[i + 1]["priority"]

    def test_categorize_errors_with_list(
        self, service: EnhancedErrorCategorizationService
    ) -> None:
        error_lines = [
            "ModuleNotFoundError: No module named 'missing_package'",
            "SyntaxError: invalid syntax",
            "unused import 'sys'",
        ]

        results = service.categorize_errors(error_lines)

        assert len(results) == 3

        found_types = {r["type"] for r in results}
        assert len(found_types) >= 1

    def test_get_error_summary_empty(
        self, service: EnhancedErrorCategorizationService
    ) -> None:
        summary = service.get_error_summary([])

        assert summary["total_errors"] == 0
        assert summary["by_category"] == {}
        assert summary["by_severity"] == {}
        assert summary["auto_fixable_count"] == 0
        assert summary["critical_issues"] == []

    def test_get_error_summary_with_errors(
        self, service: EnhancedErrorCategorizationService
    ) -> None:
        errors = [
            {
                "type": "import_error",
                "category": "dependency",
                "severity": "high",
                "auto_fixable": True,
                "raw_line": "ModuleNotFoundError: No module named 'test'",
                "description": "Missing dependency",
            },
            {
                "type": "syntax_error",
                "category": "syntax",
                "severity": "critical",
                "auto_fixable": True,
                "raw_line": "SyntaxError: invalid syntax",
                "description": "Syntax error",
            },
        ]

        summary = service.get_error_summary(errors)

        assert summary["total_errors"] == 2
        assert summary["by_category"]["dependency"] == 1
        assert summary["by_category"]["syntax"] == 1
        assert summary["by_severity"]["high"] == 1
        assert summary["by_severity"]["critical"] == 1
        assert summary["auto_fixable_count"] == 2

    def test_suggest_fix_methods(
        self, service: EnhancedErrorCategorizationService
    ) -> None:
        fix = service._suggest_fix("import_error", ("missing_package",), "line")
        assert "missing_package" in fix
        assert "uv add" in fix

        fix = service._suggest_fix("syntax_error", (), "line")
        assert "syntax" in fix

        fix = service._suggest_fix("type_error", ("type mismatch",), "line")
        assert "type" in fix

        fix = service._suggest_fix("unknown_error", (), "line")
        assert fix is None


class TestGitHookServiceStrategic:
    @pytest.fixture
    def console(self) -> Console:
        return Mock(spec=Console)

    @pytest.fixture
    def temp_project(self) -> Path:
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            git_dir = project_path / ".git"
            git_dir.mkdir()
            hooks_dir = git_dir / "hooks"
            hooks_dir.mkdir()
            yield project_path

    @pytest.fixture
    def service(self, console: Console, temp_project: Path) -> GitHookService:
        return GitHookService(console, temp_project)

    def test_service_initialization(
        self, service: GitHookService, temp_project: Path
    ) -> None:
        assert service.project_path == temp_project
        assert service.hooks_dir == temp_project / ".git" / "hooks"

    def test_install_pre_commit_hook(self, service: GitHookService) -> None:
        result = service.install_pre_commit_hook()
        assert result is True

        hook_path = service.hooks_dir / "pre - commit"
        assert hook_path.exists()
        assert hook_path.is_file()

        import stat

        assert hook_path.stat().st_mode & stat.S_IEXEC

        result = service.install_pre_commit_hook(force=True)
        assert result is True

        result = service.install_pre_commit_hook(force=False)
        assert result is False

    def test_remove_pre_commit_hook(self, service: GitHookService) -> None:
        service.install_pre_commit_hook()
        assert (service.hooks_dir / "pre - commit").exists()

        hook_path = service.hooks_dir / "pre - commit"
        content = hook_path.read_text()

        modified_content = content.replace(
            "#! / bin / bash", "#! / bin / bash\n# Crackerjack pre - commit hook"
        )
        hook_path.write_text(modified_content)

        result = service.remove_pre_commit_hook()
        assert result is True
        assert not (service.hooks_dir / "pre - commit").exists()

        result = service.remove_pre_commit_hook()
        assert result is False

    def test_is_hook_installed(self, service: GitHookService) -> None:
        assert service.is_hook_installed() is False

        service.install_pre_commit_hook()

        hook_path = service.hooks_dir / "pre - commit"
        content = hook_path.read_text()
        modified_content = content.replace(
            "#! / bin / bash", "#! / bin / bash\n# Crackerjack pre - commit hook"
        )
        hook_path.write_text(modified_content)

        assert service.is_hook_installed() is True

        service.remove_pre_commit_hook()
        assert service.is_hook_installed() is False

    def test_check_init_needed_quick(
        self, service: GitHookService, temp_project: Path
    ) -> None:
        result = service.check_init_needed_quick()
        assert result == 1

        (temp_project / "pyproject.toml").touch()
        result = service.check_init_needed_quick()
        assert result == 0

        pre_commit_config = temp_project / ".pre - commit - config.yaml"
        pre_commit_config.touch()

        import time

        old_time = time.time() - (31 * 24 * 60 * 60)
        os.utime(pre_commit_config, (old_time, old_time))

        result = service.check_init_needed_quick()
        assert result == 1

    def test_create_pre_commit_hook_script(self, service: GitHookService) -> None:
        script = service._create_pre_commit_hook_script()

        assert "#! / bin / bash" in script
        assert "crackerjack" in script
        assert "python" in script
        assert "check_init_needed_quick" in script
