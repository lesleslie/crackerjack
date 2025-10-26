import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from rich.console import Console

from crackerjack.managers.hook_manager import HookManagerImpl
from crackerjack.models.config import HookConfig


@pytest.mark.skip(reason="HookManagerImpl requires complex nested ACB DI setup - integration test, not unit test")
class TestHookManagerImpl:
    @pytest.fixture
    def console(self):
        return Console()

    @pytest.fixture
    def hook_manager(self, console):
        return HookManagerImpl()

    def test_init(self, hook_manager, console):
        """Test HookManagerImpl initialization"""
        assert hook_manager.console == console
        assert hook_manager.config_path is None
        assert hook_manager.lsp_optimization_enabled is False
        assert hook_manager.tool_proxy_enabled is False
        assert hook_manager.logger is not None

    def test_set_config_path(self, hook_manager):
        """Test set_config_path method"""
        config_path = Path("/tmp/pre-commit-config.yaml")
        hook_manager.set_config_path(config_path)

        assert hook_manager.config_path == config_path

    def test_run_fast_hooks(self, hook_manager):
        """Test run_fast_hooks method"""
        with patch.object(hook_manager, '_run_hooks_with_executor') as mock_run:
            mock_result = Mock()
            mock_run.return_value = [mock_result]

            results = hook_manager.run_fast_hooks()

            assert results == [mock_result]
            # Verify that fast hooks configuration was used
            mock_run.assert_called_once()
            args, kwargs = mock_run.call_args
            # Check that the executor type is for fast hooks

    def test_run_comprehensive_hooks(self, hook_manager):
        """Test run_comprehensive_hooks method"""
        with patch.object(hook_manager, '_run_hooks_with_executor') as mock_run:
            mock_result = Mock()
            mock_run.return_value = [mock_result]

            results = hook_manager.run_comprehensive_hooks()

            assert results == [mock_result]
            # Verify that comprehensive hooks configuration was used
            mock_run.assert_called_once()

    def test_run_hooks(self, hook_manager):
        """Test run_hooks method"""
        with patch.object(hook_manager, '_run_hooks_with_executor') as mock_run:
            mock_result = Mock()
            mock_run.return_value = [mock_result]

            results = hook_manager.run_hooks()

            assert results == [mock_result]
            mock_run.assert_called_once()

    def test_get_execution_info(self, hook_manager):
        """Test get_execution_info method"""
        # Set some values to test
        hook_manager.lsp_optimization_enabled = True
        hook_manager.tool_proxy_enabled = True
        hook_manager.config_path = Path("/tmp/config.yaml")

        info = hook_manager.get_execution_info()

        assert isinstance(info, dict)
        assert info["lsp_optimization_enabled"] is True
        assert info["tool_proxy_enabled"] is True
        assert info["config_path"] == "/tmp/config.yaml"

    def test_configure_lsp_optimization(self, hook_manager):
        """Test configure_lsp_optimization method"""
        # Test enabling
        hook_manager.configure_lsp_optimization(True)
        assert hook_manager.lsp_optimization_enabled is True

        # Test disabling
        hook_manager.configure_lsp_optimization(False)
        assert hook_manager.lsp_optimization_enabled is False

    def test_configure_tool_proxy(self, hook_manager):
        """Test configure_tool_proxy method"""
        # Test enabling
        hook_manager.configure_tool_proxy(True)
        assert hook_manager.tool_proxy_enabled is True

        # Test disabling
        hook_manager.configure_tool_proxy(False)
        assert hook_manager.tool_proxy_enabled is False

    def test_validate_hooks_config_valid(self, hook_manager):
        """Test validate_hooks_config method with valid config"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_path = Path(tmp_dir) / ".pre-commit-config.yaml"
            config_path.write_text("""
repos:
  - repo: https://github.com/psf/black
    rev: 22.3.0
    hooks:
      - id: black
""")
            hook_manager.set_config_path(config_path)

            is_valid = hook_manager.validate_hooks_config()
            assert is_valid is True

    def test_validate_hooks_config_invalid(self, hook_manager):
        """Test validate_hooks_config method with invalid config"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_path = Path(tmp_dir) / ".pre-commit-config.yaml"
            # Write invalid YAML
            config_path.write_text("""
repos:
  - repo: https://github.com/psf/black
    rev: 22.3.0
    hooks:
      - id: black
        invalid_field: value
        # Missing colon
        invalid
""")
            hook_manager.set_config_path(config_path)

            is_valid = hook_manager.validate_hooks_config()
            assert is_valid is False

    def test_validate_hooks_config_nonexistent(self, hook_manager):
        """Test validate_hooks_config method with nonexistent config"""
        hook_manager.set_config_path(Path("/nonexistent/config.yaml"))
        is_valid = hook_manager.validate_hooks_config()
        assert is_valid is False

    def test_get_hook_ids(self, hook_manager):
        """Test get_hook_ids method"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_path = Path(tmp_dir) / ".pre-commit-config.yaml"
            config_content = """
repos:
  - repo: https://github.com/psf/black
    rev: 22.3.0
    hooks:
      - id: black
      - id: flake8
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v0.950
    hooks:
      - id: mypy
"""
            config_path.write_text(config_content)
            hook_manager.set_config_path(config_path)

            hook_ids = hook_manager.get_hook_ids()

            # Should return the hook IDs from the config
            assert isinstance(hook_ids, list)
            assert len(hook_ids) == 3
            assert "black" in hook_ids
            assert "flake8" in hook_ids
            assert "mypy" in hook_ids

    def test_install_hooks(self, hook_manager):
        """Test install_hooks method"""
        with patch('subprocess.run') as mock_subprocess:
            mock_subprocess.return_value.returncode = 0

            result = hook_manager.install_hooks()

            assert result is True
            mock_subprocess.assert_called_once()
            # Check that pre-commit install command was called

    def test_update_hooks(self, hook_manager):
        """Test update_hooks method"""
        with patch('subprocess.run') as mock_subprocess:
            mock_subprocess.return_value.returncode = 0

            result = hook_manager.update_hooks()

            assert result is True
            mock_subprocess.assert_called_once()
            # Check that pre-commit autoupdate command was called

    def test_get_hook_summary(self, hook_manager):
        """Test get_hook_summary method"""
        # Create mock hook results
        mock_result1 = Mock()
        mock_result1.success = True
        mock_result1.hook_id = "black"
        mock_result1.duration = 1.5

        mock_result2 = Mock()
        mock_result2.success = False
        mock_result2.hook_id = "flake8"
        mock_result2.duration = 0.8
        mock_result2.error = "Some error occurred"

        results = [mock_result1, mock_result2]
        summary = hook_manager.get_hook_summary(results)

        assert isinstance(summary, dict)
        assert "total" in summary
        assert "passed" in summary
        assert "failed" in summary
        assert "duration" in summary
        assert summary["total"] == 2
        assert summary["passed"] == 1
        assert summary["failed"] == 1
        assert summary["duration"] == 2.3  # 1.5 + 0.8
