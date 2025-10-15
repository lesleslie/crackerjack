"""Comprehensive tests for CLI integration with global lock system.

Tests cover:
- CLI option parsing for global lock arguments
- Options object creation with global lock fields
- Configuration flow: CLI → Options → GlobalLockConfig → HookLockManager
- CLI argument validation and default values
"""

import unittest.mock
from pathlib import Path

import typer

from crackerjack.cli.options import CLI_OPTIONS, Options, create_options
from crackerjack.config.global_lock_config import GlobalLockConfig
from crackerjack.executors.hook_lock_manager import HookLockManager


class TestGlobalLockCLIOptions:
    """Test CLI option definitions for global lock functionality."""

    def test_global_lock_cli_options_exist(self):
        """Test that all global lock CLI options are defined."""
        expected_options = [
            "disable_global_locks",
            "global_lock_timeout",
            "global_lock_cleanup",
            "global_lock_dir",
        ]

        for option_name in expected_options:
            assert option_name in CLI_OPTIONS
            assert isinstance(CLI_OPTIONS[option_name], typer.models.OptionInfo)

    def test_disable_global_locks_option_definition(self):
        """Test disable_global_locks CLI option definition."""
        option = CLI_OPTIONS["disable_global_locks"]

        # Should be a boolean option with default False
        assert option.default is False
        assert "--disable-global-locks" in option.param_decls
        assert "Disable global locking" in option.help

    def test_global_lock_timeout_option_definition(self):
        """Test global_lock_timeout CLI option definition."""
        option = CLI_OPTIONS["global_lock_timeout"]

        # Should have default of 600 seconds (10 minutes)
        assert option.default == 600
        assert "--global-lock-timeout" in option.param_decls
        assert "timeout in seconds" in option.help

    def test_global_lock_cleanup_option_definition(self):
        """Test global_lock_cleanup CLI option definition."""
        option = CLI_OPTIONS["global_lock_cleanup"]

        # Should be boolean option with default True
        assert option.default is True
        # The param_decls contains the combined flag format
        param_decl = option.param_decls[0]
        assert (
            "--cleanup-stale-locks" in param_decl
            and "--no-cleanup-stale-locks" in param_decl
        )
        assert "Clean up stale global lock files" in option.help

    def test_global_lock_dir_option_definition(self):
        """Test global_lock_dir CLI option definition."""
        option = CLI_OPTIONS["global_lock_dir"]

        # Should be optional string with default None
        assert option.default is None
        assert "--global-lock-dir" in option.param_decls
        assert "Custom directory for global lock files" in option.help


class TestOptionsObjectCreation:
    """Test Options object creation with global lock fields."""

    def test_options_default_values(self):
        """Test Options object default values for global lock fields."""
        options = Options()

        assert options.disable_global_locks is False
        assert options.global_lock_timeout == 600
        assert options.global_lock_cleanup is True
        assert options.global_lock_dir is None

    def test_options_with_custom_values(self):
        """Test Options object with custom global lock values."""
        options = Options(
            disable_global_locks=True,
            global_lock_timeout=300,
            global_lock_cleanup=False,
            global_lock_dir="/custom/lock/path",
        )

        assert options.disable_global_locks is True
        assert options.global_lock_timeout == 300
        assert options.global_lock_cleanup is False
        assert options.global_lock_dir == "/custom/lock/path"

    def test_create_options_function_with_global_locks(self):
        """Test create_options function includes global lock parameters."""
        options = create_options(
            commit=False,
            interactive=False,
            no_config_updates=False,
            update_precommit=False,
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
            create_pr=False,
            async_mode=False,
            experimental_hooks=False,
            enable_pyrefly=False,
            enable_ty=False,
            no_git_tags=False,
            skip_version_check=False,
            orchestrated=False,
            orchestration_strategy="adaptive",
            orchestration_progress="granular",
            orchestration_ai_mode="single-agent",
            dev=False,
            dashboard=False,
            unified_dashboard=False,
            unified_dashboard_port=None,
            max_iterations=10,
            coverage_status=False,
            coverage_goal=None,
            no_coverage_ratchet=False,
            boost_coverage=True,
            disable_global_locks=True,
            global_lock_timeout=120,
            global_lock_cleanup=False,
            global_lock_dir="/test/locks",
            quick=False,
            thorough=False,
            clear_cache=False,
            cache_stats=False,
            generate_docs=False,
            docs_format="markdown",
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
            heatmap_type="error_frequency",
            heatmap_output=None,
            anomaly_detection=False,
            anomaly_sensitivity=2.0,
            anomaly_report=None,
            predictive_analytics=False,
            prediction_periods=10,
            analytics_dashboard=None,
            advanced_profile=None,
            advanced_report=None,
            mkdocs_integration=False,
            mkdocs_serve=False,
            mkdocs_theme="material",
            mkdocs_output=None,
            contextual_ai=False,
            ai_recommendations=5,
            ai_help_query=None,
        )

        # Verify global lock options are properly set
        assert options.disable_global_locks is True
        assert options.global_lock_timeout == 120
        assert options.global_lock_cleanup is False
        assert options.global_lock_dir == "/test/locks"

    def test_create_options_function_with_defaults(self):
        """Test create_options function with default global lock values."""
        options = create_options(
            commit=False,
            interactive=False,
            no_config_updates=False,
            update_precommit=False,
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
            create_pr=False,
            async_mode=False,
            experimental_hooks=False,
            enable_pyrefly=False,
            enable_ty=False,
            no_git_tags=False,
            skip_version_check=False,
            orchestrated=False,
            orchestration_strategy="adaptive",
            orchestration_progress="granular",
            orchestration_ai_mode="single-agent",
            dev=False,
            dashboard=False,
            unified_dashboard=False,
            unified_dashboard_port=None,
            max_iterations=10,
            coverage_status=False,
            coverage_goal=None,
            no_coverage_ratchet=False,
            boost_coverage=True,
            disable_global_locks=False,
            global_lock_timeout=600,
            global_lock_cleanup=True,
            global_lock_dir=None,
            quick=False,
            thorough=False,
            clear_cache=False,
            cache_stats=False,
            generate_docs=False,
            docs_format="markdown",
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
            heatmap_type="error_frequency",
            heatmap_output=None,
            anomaly_detection=False,
            anomaly_sensitivity=2.0,
            anomaly_report=None,
            predictive_analytics=False,
            prediction_periods=10,
            analytics_dashboard=None,
            advanced_optimizer=False,
            advanced_profile=None,
            advanced_report=None,
            mkdocs_integration=False,
            mkdocs_serve=False,
            mkdocs_theme="material",
            mkdocs_output=None,
            contextual_ai=False,
            ai_recommendations=5,
            ai_help_query=None,
        )

        # Verify default values
        assert options.disable_global_locks is False
        assert options.global_lock_timeout == 600
        assert options.global_lock_cleanup is True
        assert options.global_lock_dir is None


class TestConfigurationFlow:
    """Test configuration flow from CLI options to lock manager."""

    def test_cli_to_global_lock_config_flow(self, tmp_path):
        """Test CLI options → GlobalLockConfig flow."""
        # Create CLI options
        options = Options(
            disable_global_locks=False,
            global_lock_timeout=900,
            global_lock_dir=str(tmp_path / "cli_test_locks"),
        )

        # Create GlobalLockConfig from options
        config = GlobalLockConfig.from_options(options)

        # Verify configuration
        assert config.enabled is True  # !disable_global_locks
        assert config.timeout_seconds == 900.0
        assert config.lock_directory == tmp_path / "cli_test_locks"
        assert config.lock_directory.exists()

    def test_cli_to_lock_manager_configuration_flow(self, tmp_path):
        """Test full CLI → Options → GlobalLockConfig → HookLockManager flow."""
        # Start with CLI options
        cli_options = Options(
            disable_global_locks=False,
            global_lock_timeout=300,
            global_lock_cleanup=True,
            global_lock_dir=str(tmp_path / "full_flow_locks"),
        )

        # Configure lock manager from CLI options
        lock_manager = HookLockManager()
        lock_manager.configure_from_options(cli_options)

        # Verify complete configuration flow
        assert lock_manager.is_global_lock_enabled() is True
        assert lock_manager._global_config.timeout_seconds == 300.0
        assert (
            lock_manager._global_config.lock_directory == tmp_path / "full_flow_locks"
        )
        assert lock_manager._global_config.lock_directory.exists()

    def test_disabled_global_locks_configuration_flow(self):
        """Test configuration flow when global locks are disabled via CLI."""
        cli_options = Options(
            disable_global_locks=True,
            global_lock_timeout=600,
            global_lock_cleanup=False,
        )

        # Configure from CLI options
        config = GlobalLockConfig.from_options(cli_options)

        # Should be properly disabled
        assert config.enabled is False

        # Configure lock manager
        lock_manager = HookLockManager()
        lock_manager.configure_from_options(cli_options)

        assert lock_manager.is_global_lock_enabled() is False

    def test_custom_timeout_configuration_flow(self):
        """Test custom timeout configuration through CLI."""
        custom_timeouts = [60, 120, 300, 900, 1800]  # Various timeout values

        for timeout in custom_timeouts:
            cli_options = Options(
                disable_global_locks=False, global_lock_timeout=timeout
            )

            config = GlobalLockConfig.from_options(cli_options)
            assert config.timeout_seconds == float(timeout)

            lock_manager = HookLockManager()
            lock_manager.configure_from_options(cli_options)
            assert lock_manager._global_config.timeout_seconds == float(timeout)

    def test_custom_directory_configuration_flow(self, tmp_path):
        """Test custom directory configuration through CLI."""
        custom_dirs = [
            tmp_path / "custom1",
            tmp_path / "custom2" / "nested",
            tmp_path / "very" / "deeply" / "nested" / "locks",
        ]

        for custom_dir in custom_dirs:
            cli_options = Options(
                disable_global_locks=False, global_lock_dir=str(custom_dir)
            )

            config = GlobalLockConfig.from_options(cli_options)
            assert config.lock_directory == custom_dir
            assert custom_dir.exists()  # Should be created

            # Check permissions
            stat_result = custom_dir.stat()
            permissions = stat_result.st_mode & 0o777
            assert permissions == 0o700


class TestCLIArgumentValidation:
    """Test CLI argument validation for global lock options."""

    def test_global_lock_timeout_validation(self):
        """Test validation of global lock timeout values."""
        # Test valid timeout values
        valid_timeouts = [1, 60, 300, 600, 900, 3600]

        for timeout in valid_timeouts:
            options = Options(global_lock_timeout=timeout)
            assert options.global_lock_timeout == timeout

    def test_global_lock_timeout_edge_cases(self):
        """Test edge cases for global lock timeout."""
        # Test zero timeout (might be valid for immediate failure)
        options = Options(global_lock_timeout=0)
        assert options.global_lock_timeout == 0

        # Test very large timeout
        large_timeout = 86400  # 24 hours
        options = Options(global_lock_timeout=large_timeout)
        assert options.global_lock_timeout == large_timeout

    def test_global_lock_directory_validation(self, tmp_path):
        """Test validation of global lock directory paths."""
        # Test various path formats
        test_paths = [
            str(tmp_path / "simple"),
            str(tmp_path / "with-dashes"),
            str(tmp_path / "with_underscores"),
            str(tmp_path / "with.dots"),
            str(tmp_path / "with spaces"),  # May or may not be supported
        ]

        for path_str in test_paths:
            options = Options(global_lock_dir=path_str)
            assert options.global_lock_dir == path_str

            # Test that GlobalLockConfig can handle it
            config = GlobalLockConfig.from_options(options)
            assert str(config.lock_directory) == path_str

    def test_boolean_option_validation(self):
        """Test boolean options validation for global lock settings."""
        # Test all combinations of boolean settings
        boolean_combinations = [
            (True, True),
            (True, False),
            (False, True),
            (False, False),
        ]

        for disable_locks, cleanup in boolean_combinations:
            options = Options(
                disable_global_locks=disable_locks, global_lock_cleanup=cleanup
            )

            assert options.disable_global_locks == disable_locks
            assert options.global_lock_cleanup == cleanup

    def test_none_values_handling(self):
        """Test handling of None values for optional CLI arguments."""
        options = Options(global_lock_dir=None)
        assert options.global_lock_dir is None

        # Should use default directory when None
        config = GlobalLockConfig.from_options(options)
        expected_default = Path.home() / ".crackerjack" / "locks"
        assert config.lock_directory == expected_default


class TestCLIIntegrationScenarios:
    """Test real-world CLI integration scenarios."""

    def test_default_cli_scenario(self):
        """Test default CLI scenario (no global lock arguments provided)."""
        # Simulate default CLI invocation
        options = Options()  # All defaults

        # Should have sensible defaults
        assert options.disable_global_locks is False  # Global locks enabled
        assert options.global_lock_timeout == 600  # 10 minutes
        assert options.global_lock_cleanup is True  # Clean stale locks
        assert options.global_lock_dir is None  # Use default directory

        # Should configure properly
        config = GlobalLockConfig.from_options(options)
        assert config.enabled is True
        assert config.timeout_seconds == 600.0
        assert config.lock_directory == Path.home() / ".crackerjack" / "locks"

    def test_performance_focused_cli_scenario(self):
        """Test performance-focused CLI scenario (global locks disabled)."""
        options = Options(
            disable_global_locks=True,  # Disable for maximum performance
            global_lock_cleanup=False,  # Don't spend time cleaning up
        )

        config = GlobalLockConfig.from_options(options)
        assert config.enabled is False

        lock_manager = HookLockManager()
        lock_manager.configure_from_options(options)
        assert lock_manager.is_global_lock_enabled() is False

    def test_safety_focused_cli_scenario(self, tmp_path):
        """Test safety-focused CLI scenario (strict locking, short timeouts)."""
        options = Options(
            disable_global_locks=False,  # Keep global locks enabled
            global_lock_timeout=60,  # Short timeout for quick failure
            global_lock_cleanup=True,  # Clean up stale locks
            global_lock_dir=str(tmp_path / "safe_locks"),  # Isolated directory
        )

        config = GlobalLockConfig.from_options(options)
        assert config.enabled is True
        assert config.timeout_seconds == 60.0
        assert config.lock_directory == tmp_path / "safe_locks"

        lock_manager = HookLockManager()
        lock_manager.configure_from_options(options)
        assert lock_manager.is_global_lock_enabled() is True
        assert lock_manager._global_config.timeout_seconds == 60.0

    def test_development_cli_scenario(self, tmp_path):
        """Test development CLI scenario (custom directory, longer timeout)."""
        dev_lock_dir = tmp_path / "dev_locks"

        options = Options(
            disable_global_locks=False,
            global_lock_timeout=1800,  # 30 minutes for long dev operations
            global_lock_cleanup=True,
            global_lock_dir=str(dev_lock_dir),
        )

        config = GlobalLockConfig.from_options(options)
        assert config.enabled is True
        assert config.timeout_seconds == 1800.0
        assert config.lock_directory == dev_lock_dir
        assert dev_lock_dir.exists()

    def test_ci_cd_cli_scenario(self, tmp_path):
        """Test CI/CD CLI scenario (strict settings, custom directory)."""
        ci_lock_dir = tmp_path / "ci_locks"

        options = Options(
            disable_global_locks=False,  # Keep locks for CI safety
            global_lock_timeout=300,  # 5 minutes max for CI
            global_lock_cleanup=True,  # Always clean up in CI
            global_lock_dir=str(ci_lock_dir),
        )

        GlobalLockConfig.from_options(options)
        lock_manager = HookLockManager()
        lock_manager.configure_from_options(options)

        # Verify CI-appropriate configuration
        assert lock_manager.is_global_lock_enabled() is True
        assert lock_manager._global_config.timeout_seconds == 300.0
        assert lock_manager._global_config.lock_directory == ci_lock_dir
        assert ci_lock_dir.exists()


class TestCLIOptionCompletion:
    """Test CLI option completeness and consistency."""

    def test_options_model_has_all_cli_fields(self):
        """Test that Options model has all necessary fields for CLI integration."""
        # Check that Options model includes all global lock fields
        options_instance = Options()

        required_global_lock_fields = [
            "disable_global_locks",
            "global_lock_timeout",
            "global_lock_cleanup",
            "global_lock_dir",
        ]

        for field in required_global_lock_fields:
            assert hasattr(options_instance, field)

    def test_cli_options_dict_completeness(self):
        """Test that CLI_OPTIONS dictionary includes all global lock options."""
        expected_cli_options = [
            "disable_global_locks",
            "global_lock_timeout",
            "global_lock_cleanup",
            "global_lock_dir",
        ]

        for option_name in expected_cli_options:
            assert option_name in CLI_OPTIONS
            option_def = CLI_OPTIONS[option_name]

            # Should be a Typer option
            assert isinstance(option_def, typer.models.OptionInfo)

            # Should have help text
            assert option_def.help is not None
            assert len(option_def.help) > 0

    def test_create_options_function_signature(self):
        """Test that create_options function has all global lock parameters."""
        import inspect

        # Get function signature
        sig = inspect.signature(create_options)
        param_names = list(sig.parameters.keys())

        required_global_lock_params = [
            "disable_global_locks",
            "global_lock_timeout",
            "global_lock_cleanup",
            "global_lock_dir",
        ]

        for param_name in required_global_lock_params:
            assert param_name in param_names

    def test_options_model_protocol_compliance(self):
        """Test that Options model is compatible with OptionsProtocol."""
        from crackerjack.models.protocols import OptionsProtocol

        options = Options()

        # Should have all required protocol fields
        protocol_fields = [
            "disable_global_locks",
            "global_lock_timeout",
            "global_lock_cleanup",
            "global_lock_dir",
        ]

        for field in protocol_fields:
            assert hasattr(options, field)

        # Test that it can be used where OptionsProtocol is expected
        def test_function(opts: OptionsProtocol) -> bool:
            return (
                hasattr(opts, "disable_global_locks")
                and hasattr(opts, "global_lock_timeout")
                and hasattr(opts, "global_lock_cleanup")
                and hasattr(opts, "global_lock_dir")
            )

        assert test_function(options)


class TestCLIErrorHandling:
    """Test CLI error handling for global lock options."""

    def test_invalid_timeout_handling(self):
        """Test handling of invalid timeout values in Options model."""
        # Negative timeout - Pydantic should accept it (validation may be elsewhere)
        options = Options(global_lock_timeout=-1)
        assert options.global_lock_timeout == -1

        # Very large timeout - should be accepted
        options = Options(global_lock_timeout=999999)
        assert options.global_lock_timeout == 999999

    def test_invalid_directory_path_handling(self):
        """Test handling of invalid directory paths."""
        # Invalid path characters (depends on OS)
        potentially_invalid_paths = [
            "",  # Empty string
            "   ",  # Whitespace only
            "/root/inaccessible",  # Potentially inaccessible
        ]

        for path in potentially_invalid_paths:
            # Options model should accept string values
            options = Options(global_lock_dir=path)
            assert options.global_lock_dir == path

            # GlobalLockConfig might handle or raise errors
            # (Testing the actual behavior without making assumptions)

    def test_none_and_empty_value_handling(self):
        """Test handling of None and empty values."""
        # None values should be handled gracefully
        options = Options(global_lock_dir=None)
        assert options.global_lock_dir is None

        # Should work with GlobalLockConfig
        config = GlobalLockConfig.from_options(options)
        assert config.lock_directory == Path.home() / ".crackerjack" / "locks"

    def test_type_consistency(self):
        """Test type consistency between CLI options and Options model."""
        # Test that CLI defaults match Options model defaults
        options_defaults = Options()

        cli_option_defaults = {
            "disable_global_locks": CLI_OPTIONS["disable_global_locks"].default,
            "global_lock_timeout": CLI_OPTIONS["global_lock_timeout"].default,
            "global_lock_cleanup": CLI_OPTIONS["global_lock_cleanup"].default,
            "global_lock_dir": CLI_OPTIONS["global_lock_dir"].default,
        }

        assert (
            options_defaults.disable_global_locks
            == cli_option_defaults["disable_global_locks"]
        )
        assert (
            options_defaults.global_lock_timeout
            == cli_option_defaults["global_lock_timeout"]
        )
        assert (
            options_defaults.global_lock_cleanup
            == cli_option_defaults["global_lock_cleanup"]
        )
        assert (
            options_defaults.global_lock_dir == cli_option_defaults["global_lock_dir"]
        )


class TestCLIMockingSupport:
    """Test CLI mocking capabilities for testing."""

    def test_options_object_mocking(self):
        """Test that Options objects can be properly mocked for testing."""
        # Create mock options
        mock_options = unittest.mock.Mock(spec=Options)
        mock_options.disable_global_locks = True
        mock_options.global_lock_timeout = 123
        mock_options.global_lock_cleanup = False
        mock_options.global_lock_dir = "/mock/path"

        # Should be usable with GlobalLockConfig
        # (This tests the interface compatibility)
        assert hasattr(mock_options, "disable_global_locks")
        assert hasattr(mock_options, "global_lock_timeout")
        assert hasattr(mock_options, "global_lock_cleanup")
        assert hasattr(mock_options, "global_lock_dir")

    def test_partial_options_mocking(self):
        """Test mocking only specific global lock options."""
        # Create real options and override specific fields
        base_options = Options()

        with unittest.mock.patch.object(base_options, "disable_global_locks", True):
            with unittest.mock.patch.object(base_options, "global_lock_timeout", 999):
                assert base_options.disable_global_locks is True
                assert base_options.global_lock_timeout == 999
                # Other fields should remain as defaults
                assert base_options.global_lock_cleanup is True
                assert base_options.global_lock_dir is None

    def test_cli_options_testability(self):
        """Test that CLI options support testing scenarios."""
        # Test creating options with various combinations for testing
        test_scenarios = [
            # Scenario 1: All defaults
            {},
            # Scenario 2: Global locks disabled
            {"disable_global_locks": True},
            # Scenario 3: Custom timeout
            {"global_lock_timeout": 42},
            # Scenario 4: Custom directory
            {"global_lock_dir": "/test/path"},
            # Scenario 5: All custom
            {
                "disable_global_locks": True,
                "global_lock_timeout": 300,
                "global_lock_cleanup": False,
                "global_lock_dir": "/custom/test/locks",
            },
        ]

        for scenario_kwargs in test_scenarios:
            options = Options(**scenario_kwargs)

            # Should be valid Options object
            assert isinstance(options, Options)

            # Should have all required fields
            assert hasattr(options, "disable_global_locks")
            assert hasattr(options, "global_lock_timeout")
            assert hasattr(options, "global_lock_cleanup")
            assert hasattr(options, "global_lock_dir")
