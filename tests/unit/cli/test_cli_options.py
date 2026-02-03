"""Tests for CLI options."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from crackerjack.cli.options import (
    BumpOption,
    Options,
    create_options,
    CLI_OPTIONS,
)


class TestBumpOption:
    """Tests for BumpOption."""

    def test_bump_option_values(self):
        """Test BumpOption enum values."""
        assert BumpOption.PATCH.value == "patch"
        assert BumpOption.MINOR.value == "minor"
        assert BumpOption.MAJOR.value == "major"
        assert BumpOption.AUTO.value == "auto"


class TestOptions:
    """Tests for Options dataclass."""

    def test_create_default_options(self):
        """Test creating options with default values."""
        options = Options()

        # Check some default values
        assert options.commit is False
        assert options.interactive is False
        assert options.verbose is False
        assert options.debug is False
        assert options.dry_run is False

    def test_create_custom_options(self):
        """Test creating options with custom values."""
        options = Options(
            commit=True,
            verbose=True,
            fast=True,
            tool="ruff",
        )

        assert options.commit is True
        assert options.verbose is True
        assert options.fast is True
        assert options.tool == "ruff"

    def test_options_with_bump(self):
        """Test options with bump configuration."""
        options = Options(
            publish=BumpOption.MINOR,
            bump=BumpOption.PATCH,
        )

        assert options.publish == BumpOption.MINOR
        assert options.bump == BumpOption.PATCH

    def test_options_with_test_config(self):
        """Test options with test configuration."""
        options = Options(
            run_tests=True,
            test_workers=4,
            test_timeout=300,
            benchmark=True,
        )

        assert options.run_tests is True
        assert options.test_workers == 4
        assert options.test_timeout == 300
        assert options.benchmark is True

    def test_options_with_ai_config(self):
        """Test options with AI configuration."""
        options = Options(
            ai_fix=True,
            select_provider=True,
            max_iterations=10,
            dev=True,
        )

        assert options.ai_fix is True
        assert options.select_provider is True
        assert options.max_iterations == 10
        assert options.dev is True

    def test_options_with_coverage_config(self):
        """Test options with coverage configuration."""
        options = Options(
            coverage_status=True,
            coverage_goal=90.0,
            boost_coverage=True,
            no_coverage_ratchet=False,
        )

        assert options.coverage_status is True
        assert options.coverage_goal == 90.0
        assert options.boost_coverage is True
        assert options.no_coverage_ratchet is False

    def test_options_with_documentation_config(self):
        """Test options with documentation configuration."""
        options = Options(
            cleanup_docs=True,
            docs_dry_run=False,
            update_docs=True,
            generate_docs=True,
            validate_docs=True,
        )

        assert options.cleanup_docs is True
        assert options.docs_dry_run is False
        assert options.update_docs is True
        assert options.generate_docs is True
        assert options.validate_docs is True

    def test_options_with_cache_config(self):
        """Test options with cache configuration."""
        options = Options(
            clear_cache=True,
            cache_stats=True,
            refresh_cache=True,
        )

        assert options.clear_cache is True
        assert options.cache_stats is True
        assert options.refresh_cache is True

    def test_options_with_semantic_config(self):
        """Test options with semantic configuration."""
        options = Options(
            index="test.py",
            search="function",
            semantic_stats=True,
            remove_from_index="old.py",
        )

        assert options.index == "test.py"
        assert options.search == "function"
        assert options.semantic_stats is True
        assert options.remove_from_index == "old.py"


class TestCreateOptions:
    """Tests for create_options function."""

    def test_create_options_with_defaults(self):
        """Test create_options with all defaults."""
        options = create_options(
            commit=False,
            interactive=False,
            no_config_updates=False,
            verbose=False,
            debug=False,
            publish=None,
            bump=None,
            benchmark=False,
            test_workers=0,
            test_timeout=0,
            skip_hooks=False,
            fast=False,
            comp=False,
            fast_iteration=False,
            tool=None,
            changed_only=False,
            all_files=False,
            create_pr=False,
            experimental_hooks=False,
            enable_pyrefly=False,
            enable_ty=False,
            start_zuban_lsp=False,
            stop_zuban_lsp=False,
            restart_zuban_lsp=False,
            no_zuban_lsp=False,
            zuban_lsp_port=0,
            zuban_lsp_mode="",
            zuban_lsp_timeout=0,
            enable_lsp_hooks=False,
            no_git_tags=False,
            skip_version_check=False,
            dev=False,
            max_iterations=5,
            coverage_status=False,
            coverage_goal=None,
            no_coverage_ratchet=False,
            boost_coverage=False,
            disable_global_locks=False,
            global_lock_timeout=300,
            global_lock_cleanup=False,
            global_lock_dir=None,
            quick=False,
            thorough=False,
            clear_cache=False,
            cleanup_docs=False,
            docs_dry_run=False,
            cleanup_configs=False,
            configs_dry_run=False,
            cleanup_git=False,
            update_docs=False,
            cache_stats=False,
            generate_docs=False,
            docs_format="",
            validate_docs=False,
            generate_changelog=False,
            changelog_version=None,
            changelog_since=None,
            changelog_dry_run=False,
            auto_version=False,
            version_since=None,
            accept_version=False,
            smart_commit=False,
            heatmap=False,
            heatmap_type="",
            heatmap_output=None,
            anomaly_detection=False,
            anomaly_sensitivity=0.5,
            anomaly_report=None,
            predictive_analytics=False,
            prediction_periods=0,
            analytics_dashboard=None,
            advanced_optimizer=False,
            advanced_profile=None,
            advanced_report=None,
            mkdocs_integration=False,
            mkdocs_serve=False,
            mkdocs_theme="",
            mkdocs_output=None,
            contextual_ai=False,
            ai_recommendations=0,
            ai_help_query=None,
            check_config_updates=False,
            apply_config_updates=False,
            diff_config=None,
            config_interactive=False,
            refresh_cache=False,
            strip_code=False,
            run_tests=False,
            xcode_tests=False,
            xcode_project="",
            xcode_scheme="",
            xcode_configuration="",
            xcode_destination="",
            ai_fix=False,
            dry_run=False,
            full_release=None,
            show_progress=None,
            advanced_monitor=None,
            coverage_report=None,
            clean_releases=None,
        )

        assert isinstance(options, Options)

    def test_create_options_with_custom_values(self):
        """Test create_options with custom values."""
        options = create_options(
            commit=True,
            verbose=True,
            fast=True,
            tool="pytest",
            test_workers=4,
            ai_fix=True,
            publish=BumpOption.MINOR,
            bump=BumpOption.PATCH,
        )

        assert options.commit is True
        assert options.verbose is True
        assert options.fast is True
        assert options.tool == "pytest"
        assert options.test_workers == 4
        assert options.ai_fix is True
        assert options.publish == BumpOption.MINOR
        assert options.bump == BumpOption.PATCH


class TestCliOptionsDict:
    """Tests for CLI_OPTIONS dictionary."""

    def test_cli_options_structure(self):
        """Test that CLI_OPTIONS has expected structure."""
        assert isinstance(CLI_OPTIONS, dict)

        # Check for some expected keys
        expected_keys = [
            "commit",
            "interactive",
            "verbose",
            "debug",
            "publish",
            "fast",
            "tool",
            "ai_fix",
            "dry_run",
            "coverage_status",
            "cleanup_docs",
            "semantic_stats",
            "clear_cache",
        ]

        for key in expected_keys:
            assert key in CLI_OPTIONS, f"Missing key: {key}"

    def test_cli_options_values(self):
        """Test that CLI_OPTIONS values are properly configured."""
        # Check that some options have the right types
        assert isinstance(CLI_OPTIONS["commit"], bool)
        assert isinstance(CLI_OPTIONS["verbose"], bool)
        assert isinstance(CLI_OPTIONS["debug"], bool)

        # Check enum options
        assert CLI_OPTIONS["publish"] is None or isinstance(
            CLI_OPTIONS["publish"],
            BumpOption,
        )
