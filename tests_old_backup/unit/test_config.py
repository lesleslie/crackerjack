#!/usr/bin/env python3
"""Unit tests for Configuration Management."""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from session_mgmt_mcp.config import (
    ConfigLoader,
    DatabaseConfig,
    IntegrationConfig,
    LoggingConfig,
    SearchConfig,
    SecurityConfig,
    SessionConfig,
    SessionMgmtConfig,
    TokenOptimizationConfig,
    get_config,
    reload_config,
)


@pytest.fixture
def temp_project_dir():
    """Create a temporary project directory."""
    with tempfile.TemporaryDirectory() as temp_dir:
        project_dir = Path(temp_dir)
        yield project_dir


@pytest.fixture
def sample_pyproject_toml():
    """Sample pyproject.toml content for testing."""
    return """
[project]
name = "session-mgmt-mcp"
version = "0.1.0"

[tool.session-mgmt-mcp]
debug = true
server_host = "0.0.0.0"
server_port = 3001

[tool.session-mgmt-mcp.database]
path = "~/.claude/test/reflection.duckdb"
connection_timeout = 45
enable_multi_project = true
enable_full_text_search = true

[tool.session-mgmt-mcp.search]
enable_semantic_search = false
embedding_model = "all-MiniLM-L12-v2"
enable_faceted_search = true
max_facet_values = 100

[tool.session-mgmt-mcp.token_optimization]
enable_optimization = false
default_max_tokens = 8000
preferred_strategy = "summarize_content"
track_usage = false

[tool.session-mgmt-mcp.session]
auto_checkpoint_interval = 3600
enable_auto_commit = false
session_retention_days = 180

[tool.session-mgmt-mcp.logging]
level = "DEBUG"
enable_file_logging = false
enable_performance_logging = true

[tool.session-mgmt-mcp.security]
anonymize_paths = true
enable_rate_limiting = false
max_requests_per_minute = 50
"""


class TestConfigDataClasses:
    """Test configuration data classes."""

    def test_database_config_defaults(self):
        """Test DatabaseConfig default values."""
        config = DatabaseConfig()

        assert config.path == "~/.claude/data/reflection.duckdb"
        assert config.connection_timeout == 30
        assert config.enable_multi_project is True
        assert config.enable_full_text_search is True

    def test_search_config_defaults(self):
        """Test SearchConfig default values."""
        config = SearchConfig()

        assert config.enable_semantic_search is True
        assert config.embedding_model == "all-MiniLM-L6-v2"
        assert config.enable_faceted_search is True
        assert config.max_facet_values == 50

    def test_token_optimization_config_defaults(self):
        """Test TokenOptimizationConfig default values."""
        config = TokenOptimizationConfig()

        assert config.enable_optimization is True
        assert config.default_max_tokens == 4000
        assert config.preferred_strategy == "auto"
        assert config.track_usage is True

    def test_session_config_defaults(self):
        """Test SessionConfig default values."""
        config = SessionConfig()

        assert config.auto_checkpoint_interval == 1800  # 30 minutes
        assert config.enable_auto_commit is True
        assert config.enable_permission_system is True
        assert "git_commit" in config.default_trusted_operations

    def test_integration_config_defaults(self):
        """Test IntegrationConfig default values."""
        config = IntegrationConfig()

        assert config.enable_crackerjack is True
        assert config.enable_git_integration is True
        assert config.global_workspace_path == "~/Projects/claude"

    def test_logging_config_defaults(self):
        """Test LoggingConfig default values."""
        config = LoggingConfig()

        assert config.level == "INFO"
        assert config.enable_file_logging is True
        assert config.log_file_path == "~/.claude/logs/session-mgmt.log"

    def test_security_config_defaults(self):
        """Test SecurityConfig default values."""
        config = SecurityConfig()

        assert config.anonymize_paths is False
        assert config.enable_rate_limiting is True
        assert config.max_requests_per_minute == 100
        assert len(config.exclude_sensitive_patterns) > 0


class TestConfigLoader:
    """Test ConfigLoader functionality."""

    def test_find_project_root(self, temp_project_dir):
        """Test project root detection."""
        # Create pyproject.toml in temp directory
        pyproject_path = temp_project_dir / "pyproject.toml"
        pyproject_path.write_text("""
[project]
name = "session-mgmt-mcp"
version = "0.1.0"
""")

        # Create subdirectory
        sub_dir = temp_project_dir / "subdir"
        sub_dir.mkdir()

        # ConfigLoader from subdirectory should find project root
        with patch("pathlib.Path.cwd", return_value=sub_dir):
            loader = ConfigLoader()
            assert loader.project_root == temp_project_dir

    def test_load_default_config(self, temp_project_dir):
        """Test loading default configuration when no pyproject.toml exists."""
        loader = ConfigLoader(temp_project_dir)
        config = loader.load_config()

        assert isinstance(config, SessionMgmtConfig)
        assert config.server_host == "localhost"
        assert config.server_port == 3000
        assert config.database.enable_multi_project is True

    def test_load_config_from_toml(self, temp_project_dir, sample_pyproject_toml):
        """Test loading configuration from pyproject.toml."""
        # Write sample pyproject.toml
        pyproject_path = temp_project_dir / "pyproject.toml"
        pyproject_path.write_text(sample_pyproject_toml)

        loader = ConfigLoader(temp_project_dir)
        config = loader.load_config()

        # Test that TOML values override defaults
        assert config.debug is True
        assert config.server_host == "0.0.0.0"
        assert config.server_port == 3001

        # Test nested configuration
        assert config.database.connection_timeout == 45
        assert config.database.enable_multi_project is True

        assert config.search.enable_semantic_search is False
        assert config.search.embedding_model == "all-MiniLM-L12-v2"
        assert config.search.max_facet_values == 100

        assert config.token_optimization.enable_optimization is False
        assert config.token_optimization.default_max_tokens == 8000
        assert config.token_optimization.preferred_strategy == "summarize_content"

        assert config.session.auto_checkpoint_interval == 3600
        assert config.session.enable_auto_commit is False

        assert config.logging.level == "DEBUG"
        assert config.logging.enable_file_logging is False

        assert config.security.anonymize_paths is True
        assert config.security.enable_rate_limiting is False

    def test_underscore_variant_support(self, temp_project_dir):
        """Test support for underscore variant of tool section."""
        toml_content = """
[tool.session_mgmt_mcp]
debug = true
server_port = 4000

[tool.session_mgmt_mcp.database]
connection_timeout = 60
"""

        pyproject_path = temp_project_dir / "pyproject.toml"
        pyproject_path.write_text(toml_content)

        loader = ConfigLoader(temp_project_dir)
        config = loader.load_config()

        assert config.debug is True
        assert config.server_port == 4000
        assert config.database.connection_timeout == 60

    def test_path_expansion(self, temp_project_dir, sample_pyproject_toml):
        """Test user path expansion."""
        pyproject_path = temp_project_dir / "pyproject.toml"
        pyproject_path.write_text(sample_pyproject_toml)

        loader = ConfigLoader(temp_project_dir)
        config = loader.load_config()

        # Paths should be expanded
        assert config.database.path.startswith("/")  # Should be absolute
        assert "~" not in config.database.path  # Should be expanded

    def test_config_validation(self, temp_project_dir):
        """Test configuration validation."""
        toml_content = """
[tool.session-mgmt-mcp]
server_port = 99999  # Invalid port
debug = true

[tool.session-mgmt-mcp.token_optimization]
default_max_tokens = 50  # Too low

[tool.session-mgmt-mcp.logging]
level = "INVALID_LEVEL"  # Invalid log level
"""

        pyproject_path = temp_project_dir / "pyproject.toml"
        pyproject_path.write_text(toml_content)

        loader = ConfigLoader(temp_project_dir)
        config = loader.load_config()

        # Should be corrected by validation
        assert config.server_port == 3000  # Default fallback
        assert config.token_optimization.default_max_tokens == 100  # Minimum enforced
        assert config.logging.level == "INFO"  # Default fallback


class TestEnvironmentVariables:
    """Test environment variable configuration."""

    def test_env_var_overrides(self, temp_project_dir):
        """Test environment variable overrides."""
        env_vars = {
            "SESSION_MGMT_HOST": "192.168.1.100",
            "SESSION_MGMT_PORT": "5000",
            "SESSION_MGMT_DEBUG": "true",
            "SESSION_MGMT_DB_PATH": "/custom/path/db.duckdb",
            "SESSION_MGMT_DB_TIMEOUT": "120",
            "SESSION_MGMT_ENABLE_SEMANTIC_SEARCH": "false",
            "SESSION_MGMT_MAX_TOKENS": "2000",
            "SESSION_MGMT_LOG_LEVEL": "WARNING",
        }

        with patch.dict(os.environ, env_vars):
            loader = ConfigLoader(temp_project_dir)
            config = loader.load_config()

        # Test that environment variables override defaults
        assert config.server_host == "192.168.1.100"
        assert config.server_port == 5000
        assert config.debug is True
        assert config.database.path == "/custom/path/db.duckdb"
        assert config.database.connection_timeout == 120
        assert config.search.enable_semantic_search is False
        assert config.token_optimization.default_max_tokens == 2000
        assert config.logging.level == "WARNING"

    def test_env_var_type_conversion(self, temp_project_dir):
        """Test environment variable type conversion."""
        env_vars = {
            "SESSION_MGMT_PORT": "not_a_number",
            "SESSION_MGMT_DEBUG": "invalid_boolean",
            "SESSION_MGMT_DB_TIMEOUT": "also_not_a_number",
        }

        with patch.dict(os.environ, env_vars):
            loader = ConfigLoader(temp_project_dir)
            config = loader.load_config()

        # Should fall back to defaults for invalid values
        assert config.server_port == 3000  # Default
        assert config.debug is False  # Default
        assert config.database.connection_timeout == 30  # Default

    def test_boolean_env_var_parsing(self, temp_project_dir):
        """Test boolean environment variable parsing."""
        # Test various boolean representations
        boolean_tests = [
            ("true", True),
            ("True", True),
            ("TRUE", True),
            ("1", True),
            ("yes", True),
            ("on", True),
            ("false", False),
            ("False", False),
            ("FALSE", False),
            ("0", False),
            ("no", False),
            ("off", False),
            ("invalid", False),  # Default to False for invalid values
        ]

        for env_value, expected in boolean_tests:
            with patch.dict(os.environ, {"SESSION_MGMT_DEBUG": env_value}):
                loader = ConfigLoader(temp_project_dir)
                config = loader.load_config()
                assert config.debug == expected, f"Failed for value: {env_value}"


class TestConfigCaching:
    """Test configuration caching."""

    def test_config_caching(self, temp_project_dir):
        """Test that configuration is cached."""
        loader = ConfigLoader(temp_project_dir)

        # First load
        config1 = loader.load_config()

        # Second load (should use cache)
        config2 = loader.load_config()

        # Should be the same object (cached)
        assert config1 is config2

    def test_config_reload(self, temp_project_dir, sample_pyproject_toml):
        """Test configuration reloading."""
        # Create initial pyproject.toml
        pyproject_path = temp_project_dir / "pyproject.toml"
        pyproject_path.write_text(sample_pyproject_toml)

        loader = ConfigLoader(temp_project_dir)

        # First load
        config1 = loader.load_config()
        assert config1.server_port == 3001

        # Update pyproject.toml
        updated_toml = sample_pyproject_toml.replace(
            "server_port = 3001",
            "server_port = 4001",
        )
        pyproject_path.write_text(updated_toml)

        # Reload configuration
        config2 = loader.load_config(reload=True)
        assert config2.server_port == 4001

        # Should be different objects
        assert config1 is not config2


class TestGlobalConfigFunctions:
    """Test global configuration functions."""

    def test_get_config_function(self, temp_project_dir):
        """Test get_config() global function."""
        with patch("session_mgmt_mcp.config.ConfigLoader") as mock_loader_class:
            mock_loader = mock_loader_class.return_value
            mock_config = SessionMgmtConfig()
            mock_loader.load_config.return_value = mock_config

            # First call should create loader
            config1 = get_config()
            assert mock_loader_class.called
            assert mock_loader.load_config.called

            # Second call should reuse loader
            mock_loader.load_config.reset_mock()
            config2 = get_config()
            assert mock_loader.load_config.called

            assert config1 is mock_config
            assert config2 is mock_config

    def test_reload_config_function(self, temp_project_dir):
        """Test reload_config() global function."""
        config = reload_config()
        assert isinstance(config, SessionMgmtConfig)


class TestConfigExampleGeneration:
    """Test configuration example generation."""

    def test_get_example_config(self, temp_project_dir):
        """Test example configuration generation."""
        loader = ConfigLoader(temp_project_dir)
        example = loader.get_example_config()

        assert isinstance(example, str)
        assert "[tool.session-mgmt-mcp]" in example
        assert "server_host" in example
        assert "database" in example
        assert "search" in example
        assert "token_optimization" in example
        assert "session" in example
        assert "logging" in example
        assert "security" in example


class TestErrorHandling:
    """Test error handling in configuration."""

    def test_missing_tomllib(self, temp_project_dir, sample_pyproject_toml):
        """Test handling when tomllib is not available."""
        pyproject_path = temp_project_dir / "pyproject.toml"
        pyproject_path.write_text(sample_pyproject_toml)

        with patch("session_mgmt_mcp.config.tomllib", None):
            loader = ConfigLoader(temp_project_dir)
            config = loader.load_config()

            # Should use defaults when tomllib not available
            assert config.server_port == 3000  # Default, not the 3001 from TOML

    def test_corrupted_toml_file(self, temp_project_dir):
        """Test handling of corrupted TOML file."""
        # Create invalid TOML
        pyproject_path = temp_project_dir / "pyproject.toml"
        pyproject_path.write_text("""
[project
name = "invalid-toml"
[tool.session-mgmt-mcp
debug = true
""")

        loader = ConfigLoader(temp_project_dir)
        config = loader.load_config()

        # Should fall back to defaults
        assert config.server_port == 3000
        assert config.debug is False

    def test_io_error_handling(self, temp_project_dir):
        """Test handling of I/O errors."""
        # Create a file that can't be read
        pyproject_path = temp_project_dir / "pyproject.toml"
        pyproject_path.write_text("[project]\nname = 'test'")

        # Mock file read failure
        with patch("builtins.open", side_effect=OSError("Permission denied")):
            loader = ConfigLoader(temp_project_dir)
            config = loader.load_config()

            # Should use defaults when file can't be read
            assert isinstance(config, SessionMgmtConfig)
            assert config.server_port == 3000


class TestConfigIntegration:
    """Test configuration integration scenarios."""

    def test_mixed_config_sources(self, temp_project_dir):
        """Test mixing TOML and environment variable configuration."""
        # Create TOML with some settings
        toml_content = """
[tool.session-mgmt-mcp]
debug = false
server_port = 3001

[tool.session-mgmt-mcp.database]
connection_timeout = 45
"""

        pyproject_path = temp_project_dir / "pyproject.toml"
        pyproject_path.write_text(toml_content)

        # Set environment variables that override some TOML settings
        env_vars = {
            "SESSION_MGMT_DEBUG": "true",  # Override TOML
            "SESSION_MGMT_HOST": "0.0.0.0",  # Not in TOML
            # PORT not set, should use TOML value
        }

        with patch.dict(os.environ, env_vars):
            loader = ConfigLoader(temp_project_dir)
            config = loader.load_config()

        # Environment should override TOML
        assert config.debug is True  # ENV override
        assert config.server_host == "0.0.0.0"  # ENV only
        assert config.server_port == 3001  # TOML only
        assert config.database.connection_timeout == 45  # TOML only

    def test_config_with_all_sections(self, temp_project_dir):
        """Test configuration with all possible sections."""
        complete_toml = """
[project]
name = "session-mgmt-mcp"

[tool.session-mgmt-mcp]
debug = true
server_host = "127.0.0.1"
server_port = 3002
enable_websockets = true
enable_hot_reload = true

[tool.session-mgmt-mcp.database]
path = "~/.claude/custom/db.duckdb"
connection_timeout = 60
query_timeout = 180
enable_multi_project = true
auto_detect_projects = true
enable_full_text_search = true

[tool.session-mgmt-mcp.search]
enable_semantic_search = true
embedding_model = "custom-model"
enable_faceted_search = true
max_facet_values = 75
enable_search_suggestions = true

[tool.session-mgmt-mcp.token_optimization]
enable_optimization = true
default_max_tokens = 6000
default_chunk_size = 3000
preferred_strategy = "prioritize_recent"
enable_response_chunking = true
track_usage = true

[tool.session-mgmt-mcp.session]
auto_checkpoint_interval = 2400
enable_auto_commit = true
enable_permission_system = true
default_trusted_operations = ["custom_op1", "custom_op2"]
session_retention_days = 500

[tool.session-mgmt-mcp.integration]
enable_crackerjack = false
enable_git_integration = true
global_workspace_path = "~/custom/workspace"

[tool.session-mgmt-mcp.logging]
level = "DEBUG"
enable_file_logging = true
log_file_path = "~/custom/logs/session.log"
enable_performance_logging = true

[tool.session-mgmt-mcp.security]
anonymize_paths = true
enable_rate_limiting = true
max_requests_per_minute = 200
max_query_length = 50000
"""

        pyproject_path = temp_project_dir / "pyproject.toml"
        pyproject_path.write_text(complete_toml)

        loader = ConfigLoader(temp_project_dir)
        config = loader.load_config()

        # Verify all sections are loaded correctly
        assert config.debug is True
        assert config.server_host == "127.0.0.1"
        assert config.server_port == 3002
        assert config.enable_websockets is True
        assert config.enable_hot_reload is True

        assert config.database.connection_timeout == 60
        assert config.database.query_timeout == 180

        assert config.search.embedding_model == "custom-model"
        assert config.search.max_facet_values == 75

        assert config.token_optimization.default_max_tokens == 6000
        assert config.token_optimization.preferred_strategy == "prioritize_recent"

        assert config.session.auto_checkpoint_interval == 2400
        assert config.session.default_trusted_operations == ["custom_op1", "custom_op2"]

        assert config.integration.enable_crackerjack is False
        assert "custom/workspace" in config.integration.global_workspace_path

        assert config.logging.level == "DEBUG"
        assert config.logging.enable_performance_logging is True

        assert config.security.anonymize_paths is True
        assert config.security.max_requests_per_minute == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
