"""Tests for CLI handlers module."""

import os
import logging
from unittest.mock import Mock, patch

import pytest

from crackerjack.cli.handlers import setup_ai_agent_env


class TestCLIHandlers:
    """Tests for CLI handlers functions."""

    def test_setup_ai_agent_env_with_ai_and_debug(self):
        """Test setup_ai_agent_env with AI agent and debug mode enabled."""
        # Clear any existing environment variables
        for var in ['CRACKERJACK_DEBUG', 'AI_AGENT', 'AI_AGENT_DEBUG', 'AI_AGENT_VERBOSE']:
            if var in os.environ:
                del os.environ[var]

        # Call the function
        setup_ai_agent_env(ai_agent=True, debug_mode=True)

        # Verify environment variables are set
        assert os.environ.get('CRACKERJACK_DEBUG') == '1'
        assert os.environ.get('AI_AGENT') == '1'
        assert os.environ.get('AI_AGENT_DEBUG') == '1'
        assert os.environ.get('AI_AGENT_VERBOSE') == '1'

    def test_setup_ai_agent_env_with_ai_no_debug(self):
        """Test setup_ai_agent_env with AI agent but no debug mode."""
        # Clear any existing environment variables
        for var in ['CRACKERJACK_DEBUG', 'AI_AGENT', 'AI_AGENT_DEBUG', 'AI_AGENT_VERBOSE']:
            if var in os.environ:
                del os.environ[var]

        # Call the function
        setup_ai_agent_env(ai_agent=True, debug_mode=False)

        # Verify environment variables are set
        assert os.environ.get('AI_AGENT') == '1'
        assert os.environ.get('CRACKERJACK_DEBUG') is None
        assert os.environ.get('AI_AGENT_DEBUG') is None
        assert os.environ.get('AI_AGENT_VERBOSE') is None

    def test_setup_ai_agent_env_no_ai_with_debug(self):
        """Test setup_ai_agent_env with debug mode but no AI agent."""
        # Clear any existing environment variables
        for var in ['CRACKERJACK_DEBUG', 'AI_AGENT', 'AI_AGENT_DEBUG', 'AI_AGENT_VERBOSE']:
            if var in os.environ:
                del os.environ[var]

        # Call the function
        setup_ai_agent_env(ai_agent=False, debug_mode=True)

        # Verify environment variables are set
        assert os.environ.get('CRACKERJACK_DEBUG') == '1'
        assert os.environ.get('AI_AGENT_DEBUG') == '1'
        assert os.environ.get('AI_AGENT_VERBOSE') == '1'
        assert os.environ.get('AI_AGENT') is None

    def test_setup_ai_agent_env_no_ai_no_debug(self):
        """Test setup_ai_agent_env with neither AI agent nor debug mode."""
        # Clear any existing environment variables
        for var in ['CRACKERJACK_DEBUG', 'AI_AGENT', 'AI_AGENT_DEBUG', 'AI_AGENT_VERBOSE']:
            if var in os.environ:
                del os.environ[var]

        # Call the function
        setup_ai_agent_env(ai_agent=False, debug_mode=False)

        # Verify no environment variables are set
        assert os.environ.get('CRACKERJACK_DEBUG') is None
        assert os.environ.get('AI_AGENT') is None
        assert os.environ.get('AI_AGENT_DEBUG') is None
        assert os.environ.get('AI_AGENT_VERBOSE') is None

    @patch('crackerjack.cli.handlers.console.print')
    def test_setup_ai_agent_env_console_output_ai_debug(self, mock_print):
        """Test console output when AI agent and debug mode are enabled."""
        # Clear any existing environment variables
        for var in ['CRACKERJACK_DEBUG', 'AI_AGENT', 'AI_AGENT_DEBUG', 'AI_AGENT_VERBOSE']:
            if var in os.environ:
                del os.environ[var]

        # Call the function
        setup_ai_agent_env(ai_agent=True, debug_mode=True)

        # Verify console output was called
        assert mock_print.call_count >= 4

        # Check that the expected messages were printed
        calls = [str(call) for call in mock_print.call_args_list]
        assert any('AI Agent Debug Mode Configuration' in str(call) for call in calls)
        assert any('AI Agent: ✅ Enabled' in str(call) for call in calls)
        assert any('Debug Mode: ✅ Enabled' in str(call) for call in calls)

    @patch('crackerjack.cli.handlers.console.print')
    def test_setup_ai_agent_env_console_output_debug_only(self, mock_print):
        """Test console output when only debug mode is enabled."""
        # Clear any existing environment variables
        for var in ['CRACKERJACK_DEBUG', 'AI_AGENT', 'AI_AGENT_DEBUG', 'AI_AGENT_VERBOSE']:
            if var in os.environ:
                del os.environ[var]

        # Call the function
        setup_ai_agent_env(ai_agent=False, debug_mode=True)

        # Verify console output was called
        assert mock_print.call_count >= 2

        # Check that the expected messages were printed
        calls = [str(call) for call in mock_print.call_args_list]
        assert any('AI Debug Mode Configuration' in str(call) for call in calls)
        assert any('Debug Mode: ✅ Enabled' in str(call) for call in calls)

    def test_setup_ai_agent_env_environment_variable_persistence(self):
        """Test that environment variables persist after function call."""
        # Clear any existing environment variables
        for var in ['CRACKERJACK_DEBUG', 'AI_AGENT', 'AI_AGENT_DEBUG', 'AI_AGENT_VERBOSE']:
            if var in os.environ:
                del os.environ[var]

        # Call the function
        setup_ai_agent_env(ai_agent=True, debug_mode=True)

        # Verify environment variables persist
        assert os.environ.get('AI_AGENT') == '1'

        # Call again with different parameters
        setup_ai_agent_env(ai_agent=False, debug_mode=False)

        # Verify environment variables can be changed
        # Note: This test shows that the function can be called multiple times
        # The actual values depend on the last call

    def test_setup_ai_agent_env_default_parameters(self):
        """Test setup_ai_agent_env with default parameters."""
        # Clear any existing environment variables
        for var in ['CRACKERJACK_DEBUG', 'AI_AGENT', 'AI_AGENT_DEBUG', 'AI_AGENT_VERBOSE']:
            if var in os.environ:
                del os.environ[var]

        # Call the function with default debug_mode (False)
        setup_ai_agent_env(ai_agent=True)

        # Verify environment variables are set correctly
        assert os.environ.get('AI_AGENT') == '1'
        assert os.environ.get('CRACKERJACK_DEBUG') is None

    def test_setup_ai_agent_env_overwrites_existing(self):
        """Test that setup_ai_agent_env overwrites existing environment variables."""
        # Set some initial environment variables
        os.environ['AI_AGENT'] = '0'
        os.environ['AI_AGENT_DEBUG'] = '0'

        # Call the function
        setup_ai_agent_env(ai_agent=True, debug_mode=True)

        # Verify environment variables are overwritten
        assert os.environ.get('AI_AGENT') == '1'
        assert os.environ.get('AI_AGENT_DEBUG') == '1'

    def test_setup_ai_agent_env_function_signature(self):
        """Test the function signature and parameter types."""
        # Test that the function accepts the correct parameters
        try:
            setup_ai_agent_env(ai_agent=True, debug_mode=True)
            setup_ai_agent_env(ai_agent=False, debug_mode=False)
            setup_ai_agent_env(ai_agent=True, debug_mode=False)
            setup_ai_agent_env(ai_agent=False, debug_mode=True)
        except Exception as e:
            pytest.fail(f"Function signature test failed: {e}")

    def test_setup_ai_agent_env_no_side_effects(self):
        """Test that the function doesn't have unexpected side effects."""
        # Clear environment
        for var in ['CRACKERJACK_DEBUG', 'AI_AGENT', 'AI_AGENT_DEBUG', 'AI_AGENT_VERBOSE']:
            if var in os.environ:
                del os.environ[var]

        # Call function
        setup_ai_agent_env(ai_agent=True, debug_mode=True)

        # Verify only expected environment variables are set
        env_vars = list(os.environ.keys())
        unexpected_vars = [var for var in env_vars if var.startswith(('CRACKERJACK', 'AI_AGENT')) and var not in ['CRACKERJACK_DEBUG', 'AI_AGENT', 'AI_AGENT_DEBUG', 'AI_AGENT_VERBOSE']]

        assert len(unexpected_vars) == 0, f"Unexpected environment variables set: {unexpected_vars}"


def test_cli_handlers_module_import():
    """Test that the CLI handlers module can be imported successfully."""
    try:
        from crackerjack.cli import handlers
        assert hasattr(handlers, 'setup_ai_agent_env')
        assert hasattr(handlers, 'console')
        assert hasattr(handlers, 'logger')
    except ImportError as e:
        pytest.fail(f"Failed to import CLI handlers module: {e}")


def test_cli_handlers_console_instance():
    """Test that the console instance is properly configured."""
    from crackerjack.cli.handlers import console

    # Verify console is a Rich Console instance
    from rich.console import Console
    assert isinstance(console, Console)


def test_cli_handlers_logger_instance():
    """Test that the logger instance is properly configured."""
    from crackerjack.cli.handlers import logger

    # Verify logger is a logging.Logger instance
    assert isinstance(logger, logging.Logger)
    assert logger.name == 'crackerjack.cli.handlers'
