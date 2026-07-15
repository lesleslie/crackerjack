"""Tests for config_adapter module."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from crackerjack.models.config_adapter import OptionsAdapter, _determine_max_iterations
from crackerjack.models.config import WorkflowOptions


class TestDetermineMaxIterations:
    """Tests for _determine_max_iterations function."""

    def test_with_effective_max_iterations(self) -> None:
        """Verify uses effective_max_iterations if available."""
        options = MagicMock()
        options.effective_max_iterations = 10
        result = _determine_max_iterations(options)
        assert result == 10

    def test_with_max_iterations_nonzero(self) -> None:
        """Verify uses max_iterations if non-zero and effective not available."""
        options = MagicMock(spec=[])
        options.max_iterations = 7
        result = _determine_max_iterations(options)
        assert result == 7

    def test_with_max_iterations_zero(self) -> None:
        """Verify ignores max_iterations if zero."""
        options = MagicMock(spec=[])
        options.max_iterations = 0
        result = _determine_max_iterations(options)
        assert result == 5

    def test_with_max_iterations_none(self) -> None:
        """Verify ignores max_iterations if None."""
        options = MagicMock(spec=[])
        options.max_iterations = None
        result = _determine_max_iterations(options)
        assert result == 5

    def test_without_max_iterations(self) -> None:
        """Verify returns default 5 when no max_iterations."""
        options = MagicMock(spec=[])
        result = _determine_max_iterations(options)
        assert result == 5

    def test_effective_takes_precedence(self) -> None:
        """Verify effective_max_iterations takes precedence over max_iterations."""
        options = MagicMock()
        options.effective_max_iterations = 15
        options.max_iterations = 3
        result = _determine_max_iterations(options)
        assert result == 15


class TestOptionsAdapter:
    """Tests for OptionsAdapter class."""

    def create_minimal_options(self) -> Any:
        """Create a minimal options object with no attributes."""
        options = MagicMock(spec=[])
        return options

    def create_full_options(self) -> Any:
        """Create a full options object with all attributes."""
        options = MagicMock()
        # Cleaning options
        options.clean = True
        options.strip_code = True
        options.strip_comments_only = True
        options.strip_docstrings_only = True
        options.update_docs = True
        options.force_update_docs = True
        options.compress_docs = True
        options.auto_compress_docs = True
        # Hook options
        options.skip_hooks = True
        options.experimental_hooks = True
        options.enable_pyrefly = True
        options.enable_ty = True
        options.enable_lsp_hooks = True
        # Test options
        options.test = True
        options.run_tests = True
        options.benchmark = True
        options.benchmark_regression = True
        options.benchmark_regression_threshold = 0.2
        options.test_workers = 4
        options.test_timeout = 600
        options.xcode_tests = True
        options.xcode_project = "custom/project.xcodeproj"
        options.xcode_scheme = "CustomScheme"
        options.xcode_configuration = "Release"
        options.xcode_destination = "platform=iOS"
        # Publishing options
        options.publish = "major"
        options.bump = "minor"
        options.all = True
        options.cleanup_pypi = True
        options.keep_releases = 20
        options.no_git_tags = True
        options.skip_version_check = True
        # Git options
        options.commit = True
        options.create_pr = True
        # AI options
        options.ai_agent = True
        options.ai_fix = True
        options.autofix = True
        options.ai_agent_autofix = True
        options.start_mcp_server = True
        options.max_iterations = 8
        # Execution options
        options.interactive = True
        options.verbose = True
        options.async_mode = True
        options.no_config_updates = True
        # Progress options
        options.track_progress = True
        options.resume_from = "checkpoint_123"
        options.progress_file = "/path/to/progress.json"
        # Cleanup options
        options.auto_cleanup = False
        options.keep_debug_logs = 10
        options.keep_coverage_files = 15
        # Advanced options
        options.advanced_batch = {"some": "value"}
        options.license_key = "key123"
        options.organization = "org123"
        # MCP server options
        options.http_port = 9999
        options.http_host = "0.0.0.0"
        options.websocket_port = 9998
        options.http_enabled = True
        # Zuban LSP options
        options.no_zuban_lsp = False
        options.zuban_lsp_port = 8888
        options.zuban_lsp_mode = "tcp"
        options.zuban_lsp_timeout = 60
        return options

    def test_from_options_protocol_minimal(self) -> None:
        """Verify from_options_protocol with minimal options."""
        options = self.create_minimal_options()
        result = OptionsAdapter.from_options_protocol(options)

        assert isinstance(result, WorkflowOptions)
        # Verify defaults are used (strip_code defaults to True, so clean defaults to True)
        assert result.cleaning.clean is True
        assert result.testing.test is False
        assert result.ai.max_iterations == 5

    def test_from_options_protocol_full(self) -> None:
        """Verify from_options_protocol with all options set."""
        options = self.create_full_options()
        result = OptionsAdapter.from_options_protocol(options)

        # Verify all options are mapped
        assert result.cleaning.clean is True
        assert result.cleaning.strip_comments_only is True
        assert result.testing.test is True
        assert result.testing.benchmark_regression_threshold == 0.2
        assert result.publishing.cleanup_pypi is True
        assert result.git.commit is True
        assert result.ai.ai_agent is True
        assert result.execution.verbose is True
        assert result.progress.track_progress is True
        assert result.cleanup.auto_cleanup is False
        assert result.advanced.license_key == "key123"
        assert result.mcp_server.http_port == 9999
        assert result.zuban_lsp.port == 8888

    def test_cleaning_defaults(self) -> None:
        """Verify cleaning config defaults."""
        options = self.create_minimal_options()
        result = OptionsAdapter.from_options_protocol(options)

        # clean defaults to True (strip_code defaults to True)
        assert result.cleaning.clean is True
        assert result.cleaning.strip_comments_only is False
        assert result.cleaning.strip_docstrings_only is False
        assert result.cleaning.update_docs is False

    def test_cleaning_strip_code_fallback(self) -> None:
        """Verify cleaning uses strip_code as fallback for clean."""
        options = MagicMock(spec=[])
        options.strip_code = True
        result = OptionsAdapter.from_options_protocol(options)

        assert result.cleaning.clean is True

    def test_hooks_defaults(self) -> None:
        """Verify hooks config defaults."""
        options = self.create_minimal_options()
        result = OptionsAdapter.from_options_protocol(options)

        assert result.hooks.skip_hooks is False
        assert result.hooks.experimental_hooks is False
        assert result.hooks.enable_pyrefly is False

    def test_testing_defaults(self) -> None:
        """Verify testing config defaults."""
        options = self.create_minimal_options()
        result = OptionsAdapter.from_options_protocol(options)

        assert result.testing.test is False
        assert result.testing.benchmark is False
        assert result.testing.test_workers == 0
        assert result.testing.xcode_project == "app/MdInjectApp/MdInjectApp.xcodeproj"
        assert result.testing.xcode_scheme == "MdInjectApp"

    def test_publishing_defaults(self) -> None:
        """Verify publishing config defaults."""
        options = self.create_minimal_options()
        result = OptionsAdapter.from_options_protocol(options)

        assert result.publishing.publish is None
        assert result.publishing.bump is None
        assert result.publishing.cleanup_pypi is False
        assert result.publishing.keep_releases == 10

    def test_git_defaults(self) -> None:
        """Verify git config defaults."""
        options = self.create_minimal_options()
        result = OptionsAdapter.from_options_protocol(options)

        assert result.git.commit is False
        assert result.git.create_pr is False

    def test_ai_defaults(self) -> None:
        """Verify AI config defaults."""
        options = self.create_minimal_options()
        result = OptionsAdapter.from_options_protocol(options)

        assert result.ai.ai_agent is False
        assert result.ai.autofix is True  # autofix defaults to True
        assert result.ai.max_iterations == 5

    def test_ai_fix_fallback(self) -> None:
        """Verify AI config uses ai_fix as fallback."""
        options = MagicMock(spec=[])
        options.ai_fix = True
        result = OptionsAdapter.from_options_protocol(options)

        # ai_fix affects both ai_agent and autofix defaults
        assert result.ai.ai_agent is True
        assert result.ai.autofix is True

    def test_execution_defaults(self) -> None:
        """Verify execution config defaults."""
        options = self.create_minimal_options()
        result = OptionsAdapter.from_options_protocol(options)

        assert result.execution.interactive is False
        assert result.execution.verbose is False
        assert result.execution.async_mode is False

    def test_progress_defaults(self) -> None:
        """Verify progress config defaults."""
        options = self.create_minimal_options()
        result = OptionsAdapter.from_options_protocol(options)

        assert result.progress.track_progress is False
        assert result.progress.resume_from is None
        assert result.progress.progress_file is None

    def test_cleanup_defaults(self) -> None:
        """Verify cleanup config defaults."""
        options = self.create_minimal_options()
        result = OptionsAdapter.from_options_protocol(options)

        assert result.cleanup.auto_cleanup is True
        assert result.cleanup.keep_debug_logs == 5
        assert result.cleanup.keep_coverage_files == 10

    def test_advanced_enabled_detection(self) -> None:
        """Verify advanced config detects enabled status from advanced_batch."""
        # With advanced_batch set
        options = MagicMock(spec=[])
        options.advanced_batch = {"key": "value"}
        result = OptionsAdapter.from_options_protocol(options)
        assert result.advanced.enabled is True

        # Without advanced_batch
        options2 = self.create_minimal_options()
        result2 = OptionsAdapter.from_options_protocol(options2)
        assert result2.advanced.enabled is False

    def test_advanced_defaults(self) -> None:
        """Verify advanced config defaults."""
        options = self.create_minimal_options()
        result = OptionsAdapter.from_options_protocol(options)

        assert result.advanced.license_key is None
        assert result.advanced.organization is None

    def test_mcp_server_defaults(self) -> None:
        """Verify MCP server config defaults."""
        options = self.create_minimal_options()
        result = OptionsAdapter.from_options_protocol(options)

        assert result.mcp_server.http_port == 8676
        assert result.mcp_server.http_host == "127.0.0.1"
        assert result.mcp_server.websocket_port == 8696
        assert result.mcp_server.http_enabled is False

    def test_zuban_lsp_defaults(self) -> None:
        """Verify Zuban LSP config defaults."""
        options = self.create_minimal_options()
        result = OptionsAdapter.from_options_protocol(options)

        assert result.zuban_lsp.enabled is True
        assert result.zuban_lsp.auto_start is True
        assert result.zuban_lsp.port == 8685
        assert result.zuban_lsp.mode == "stdio"
        assert result.zuban_lsp.timeout == 30

    def test_zuban_lsp_disabled(self) -> None:
        """Verify Zuban LSP can be disabled via no_zuban_lsp."""
        options = MagicMock(spec=[])
        options.no_zuban_lsp = True
        result = OptionsAdapter.from_options_protocol(options)

        assert result.zuban_lsp.enabled is False

    def test_to_options_protocol_identity(self) -> None:
        """Verify to_options_protocol returns same object."""
        options = self.create_full_options()
        workflow_options = OptionsAdapter.from_options_protocol(options)
        result = OptionsAdapter.to_options_protocol(workflow_options)

        assert result is workflow_options

    def test_mixed_options_with_run_tests_fallback(self) -> None:
        """Verify testing config uses run_tests as fallback for test."""
        options = MagicMock(spec=[])
        options.run_tests = True
        result = OptionsAdapter.from_options_protocol(options)

        assert result.testing.test is True

    def test_max_iterations_priority(self) -> None:
        """Verify max_iterations uses proper priority."""
        # Test with only max_iterations
        options = MagicMock(spec=[])
        options.max_iterations = 12
        result = OptionsAdapter.from_options_protocol(options)
        assert result.ai.max_iterations == 12

        # Test with effective_max_iterations taking precedence
        options2 = MagicMock()
        options2.effective_max_iterations = 20
        options2.max_iterations = 12
        result2 = OptionsAdapter.from_options_protocol(options2)
        assert result2.ai.max_iterations == 20
