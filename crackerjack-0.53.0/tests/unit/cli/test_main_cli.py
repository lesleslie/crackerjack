"""Tests for the main CLI module."""

from __future__ import annotations

import subprocess
import typing as t
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from crackerjack.__main__ import app, main, _detect_package_name_standalone

runner = CliRunner()


class TestDetectPackageNameStandalone:
    """Tests for _detect_package_name_standalone function."""

    def test_detects_from_pyproject_toml(self, tmp_path, monkeypatch):
        """Test package name detection from pyproject.toml."""
        # Create a pyproject.toml file
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            '[project]\nname = "test-package"\nversion = "1.0.0"\n',
        )

        monkeypatch.chdir(tmp_path)

        result = _detect_package_name_standalone()
        assert result == "test_package"

    def test_falls_back_to_directory_scan(self, tmp_path, monkeypatch):
        """Test fallback to directory scanning when no pyproject.toml."""
        # Create a package directory
        pkg_dir = tmp_path / "mypackage"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").touch()

        monkeypatch.chdir(tmp_path)

        result = _detect_package_name_standalone()
        assert result == "mypackage"

    def test_returns_default_when_no_package_found(self, tmp_path, monkeypatch):
        """Test default return when no package structure is found."""
        monkeypatch.chdir(tmp_path)

        result = _detect_package_name_standalone()
        assert result == "crackerjack"


class TestVersionOption:
    """Tests for version option."""

    def test_version_output(self):
        """Test version flag displays version."""
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert "Crackerjack" in result.stdout
        assert "v" in result.stdout  # Version prefix


class TestRunCommand:
    """Tests for the run command."""

    @patch("crackerjack.__main__.setup_ai_agent_env")
    @patch("crackerjack.__main__.handle_standard_mode")
    @patch("crackerjack.__main__.load_settings")
    def test_run_basic_command(
        self,
        mock_load_settings,
        mock_handle_standard,
        mock_setup_ai,
    ):
        """Test basic run command execution."""
        from crackerjack.config.settings import CrackerjackSettings

        mock_settings = MagicMock(spec=CrackerjackSettings)
        mock_settings.execution.verbose = False
        mock_load_settings.return_value = mock_settings

        result = runner.invoke(app, ["run"])

        assert result.exit_code == 0
        mock_setup_ai.assert_called_once()
        mock_handle_standard.assert_called_once()

    @patch("crackerjack.__main__.setup_ai_agent_env")
    @patch("crackerjack.__main__.handle_interactive_mode")
    @patch("crackerjack.__main__.load_settings")
    def test_run_interactive_mode(
        self,
        mock_load_settings,
        mock_handle_interactive,
        mock_setup_ai,
    ):
        """Test run command in interactive mode."""
        from crackerjack.config.settings import CrackerjackSettings

        mock_settings = MagicMock(spec=CrackerjackSettings)
        mock_settings.execution.verbose = False
        mock_load_settings.return_value = mock_settings

        result = runner.invoke(app, ["run", "--interactive"])

        assert result.exit_code == 0
        mock_handle_interactive.assert_called_once()

    @patch("crackerjack.__main__.setup_ai_agent_env")
    @patch("crackerjack.__main__.handle_standard_mode")
    @patch("crackerjack.__main__.load_settings")
    def test_run_with_dry_run(
        self,
        mock_load_settings,
        mock_handle_standard,
        mock_setup_ai,
    ):
        """Test run command with dry run flag."""
        from crackerjack.config.settings import CrackerjackSettings

        mock_settings = MagicMock(spec=CrackerjackSettings)
        mock_settings.execution.verbose = False
        mock_load_settings.return_value = mock_settings

        result = runner.invoke(app, ["run", "--dry-run"])

        assert result.exit_code == 0
        # Verify dry_run is set in options
        mock_handle_standard.assert_called_once()
        call_args = mock_handle_standard.call_args
        assert call_args[0][0].dry_run is True

    @patch("crackerjack.__main__.setup_ai_agent_env")
    @patch("crackerjack.__main__.handle_config_updates")
    @patch("crackerjack.__main__.load_settings")
    def test_run_with_check_config_updates(
        self,
        mock_load_settings,
        mock_handle_config,
        mock_setup_ai,
    ):
        """Test run command with check config updates flag."""
        from crackerjack.config.settings import CrackerjackSettings

        mock_settings = MagicMock(spec=CrackerjackSettings)
        mock_settings.execution.verbose = False
        mock_load_settings.return_value = mock_settings

        result = runner.invoke(app, ["run", "--check-config-updates"])

        assert result.exit_code == 0
        mock_handle_config.assert_called_once()


class TestRunTestsCommand:
    """Tests for the run_tests command."""

    @patch("subprocess.run")
    def test_run_tests_default(self, mock_subprocess_run):
        """Test run_tests with default parameters."""
        mock_result = MagicMock(returncode=0)
        mock_subprocess_run.return_value = mock_result

        with pytest.raises(SystemExit) as exc_info:
            runner.invoke(app, ["run-tests"])

        assert exc_info.value.code == 0
        # Verify subprocess was called
        assert mock_subprocess_run.called

    @patch("subprocess.run")
    def test_run_tests_with_workers(self, mock_subprocess_run):
        """Test run_tests with custom worker count."""
        mock_result = MagicMock(returncode=0)
        mock_subprocess_run.return_value = mock_result

        with pytest.raises(SystemExit):
            runner.invoke(app, ["run-tests", "--workers", "4"])

        call_args = mock_subprocess_run.call_args
        cmd = call_args[0][0]
        assert "-n" in cmd
        assert "4" in cmd

    @patch("subprocess.run")
    def test_run_tests_with_timeout(self, mock_subprocess_run):
        """Test run_tests with custom timeout."""
        mock_result = MagicMock(returncode=0)
        mock_subprocess_run.return_value = mock_result

        with pytest.raises(SystemExit):
            runner.invoke(app, ["run-tests", "--timeout", "600"])

        call_args = mock_subprocess_run.call_args
        cmd = call_args[0][0]
        assert "--timeout=600" in cmd

    @patch("subprocess.run")
    def test_run_tests_no_coverage(self, mock_subprocess_run):
        """Test run_tests without coverage."""
        mock_result = MagicMock(returncode=0)
        mock_subprocess_run.return_value = mock_result

        with pytest.raises(SystemExit):
            runner.invoke(app, ["run-tests", "--no-coverage"])

        call_args = mock_subprocess_run.call_args
        cmd = call_args[0][0]
        assert "--cov" not in " ".join(cmd)

    @patch("subprocess.run")
    def test_run_tests_with_benchmark(self, mock_subprocess_run):
        """Test run_tests with benchmark flag."""
        mock_result = MagicMock(returncode=0)
        mock_subprocess_run.return_value = mock_result

        with pytest.raises(SystemExit):
            runner.invoke(app, ["run-tests", "--benchmark"])

        call_args = mock_subprocess_run.call_args
        cmd = call_args[0][0]
        assert "--benchmark-only" in cmd


class TestQAHealthCommand:
    """Tests for the qa_health command."""

    @patch("crackerjack.__main__.load_settings")
    @patch("crackerjack.server.CrackerjackServer")
    def test_qa_health_all_healthy(self, mock_server_class, mock_load_settings):
        """Test qa_health when all adapters are healthy."""
        from crackerjack.config.settings import CrackerjackSettings

        mock_settings = MagicMock(spec=CrackerjackSettings)
        mock_load_settings.return_value = mock_settings

        mock_server = MagicMock()
        mock_server_class.return_value = mock_server

        # Mock healthy state
        mock_server.get_health_snapshot.return_value = {
            "lifecycle_state": {
                "qa_adapters": {
                    "total": 5,
                    "healthy": 5,
                    "enabled_flags": {
                        "ruff": True,
                        "pytest": True,
                        "bandit": True,
                        "mypy": True,
                        "coverage": True,
                    },
                },
            },
        }

        with pytest.raises(SystemExit) as exc_info:
            runner.invoke(app, ["qa-health"])

        assert exc_info.value.code == 0

    @patch("crackerjack.server.CrackerjackServer")
    @patch("crackerjack.__main__.load_settings")
    def test_qa_health_some_unhealthy(self, mock_load_settings, mock_server_class):
        """Test qa_health when some adapters are unhealthy."""
        from crackerjack.config.settings import CrackerjackSettings

        mock_settings = MagicMock(spec=CrackerjackSettings)
        mock_load_settings.return_value = mock_settings

        mock_server = MagicMock()
        mock_server_class.return_value = mock_server

        # Mock unhealthy state
        mock_server.get_health_snapshot.return_value = {
            "lifecycle_state": {
                "qa_adapters": {
                    "total": 5,
                    "healthy": 3,
                    "enabled_flags": {
                        "ruff": True,
                        "pytest": True,
                        "bandit": False,
                        "mypy": True,
                        "coverage": False,
                    },
                },
            },
        }

        with pytest.raises(SystemExit) as exc_info:
            runner.invoke(app, ["qa-health"])

        assert exc_info.value.code == 1


class TestMainFunction:
    """Tests for main function."""

    @patch("crackerjack.__main__.app")
    def test_main_calls_app(self, mock_app):
        """Test that main function calls the app."""
        main()
        mock_app.assert_called_once_with()
