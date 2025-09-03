#!/usr/bin/env python3
"""Configuration Management for Session Management MCP Server.

Loads configuration from pyproject.toml and environment variables with sensible defaults.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import tomllib  # Python 3.11+
except ImportError:
    try:
        import tomli as tomllib  # fallback for older Python versions
    except ImportError:
        tomllib = None


@dataclass
class DatabaseConfig:
    """Database configuration."""

    path: str = "~/.claude/data/reflection.duckdb"
    connection_timeout: int = 30
    query_timeout: int = 120
    max_connections: int = 10

    # Multi-project settings
    enable_multi_project: bool = True
    auto_detect_projects: bool = True
    project_groups_enabled: bool = True

    # Search settings
    enable_full_text_search: bool = True
    search_index_update_interval: int = 3600  # seconds
    max_search_results: int = 100


@dataclass
class SearchConfig:
    """Search and indexing configuration."""

    enable_semantic_search: bool = True
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_cache_size: int = 1000

    # Advanced search settings
    enable_faceted_search: bool = True
    max_facet_values: int = 50
    enable_search_suggestions: bool = True
    suggestion_limit: int = 10

    # Full-text search
    enable_stemming: bool = True
    enable_fuzzy_matching: bool = True
    fuzzy_threshold: float = 0.8


@dataclass
class TokenOptimizationConfig:
    """Token optimization settings."""

    enable_optimization: bool = True
    default_max_tokens: int = 4000
    default_chunk_size: int = 2000

    # Optimization strategies
    preferred_strategy: str = "auto"  # auto, truncate_old, summarize_content, etc.
    enable_response_chunking: bool = True
    enable_duplicate_filtering: bool = True

    # Usage tracking
    track_usage: bool = True
    usage_retention_days: int = 90


@dataclass
class SessionConfig:
    """Session management configuration."""

    auto_checkpoint_interval: int = 1800  # seconds (30 minutes)
    enable_auto_commit: bool = True
    commit_message_template: str = "checkpoint: Session checkpoint - {timestamp}"

    # Session permissions
    enable_permission_system: bool = True
    default_trusted_operations: list[str] = field(
        default_factory=lambda: ["git_commit", "uv_sync", "file_operations"],
    )

    # Session cleanup
    auto_cleanup_old_sessions: bool = True
    session_retention_days: int = 365


@dataclass
class IntegrationConfig:
    """External integrations configuration."""

    # Crackerjack integration
    enable_crackerjack: bool = True
    crackerjack_command: str = "crackerjack"

    # Git integration
    enable_git_integration: bool = True
    git_auto_stage: bool = False

    # Global workspace
    global_workspace_path: str = "~/Projects/claude"
    enable_global_toolkits: bool = True


@dataclass
class LoggingConfig:
    """Logging configuration."""

    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    # File logging
    enable_file_logging: bool = True
    log_file_path: str = "~/.claude/logs/session-mgmt.log"
    log_file_max_size: int = 10 * 1024 * 1024  # 10MB
    log_file_backup_count: int = 5

    # Performance logging
    enable_performance_logging: bool = False
    log_slow_queries: bool = True
    slow_query_threshold: float = 1.0  # seconds


@dataclass
class SecurityConfig:
    """Security and privacy settings."""

    # Data privacy
    anonymize_paths: bool = False
    exclude_sensitive_patterns: list[str] = field(
        default_factory=lambda: [
            r"password\s*=\s*['\"][^'\"]+['\"]",
            r"api[_-]?key\s*=\s*['\"][^'\"]+['\"]",
            r"secret\s*=\s*['\"][^'\"]+['\"]",
            r"token\s*=\s*['\"][^'\"]+['\"]",
        ],
    )

    # Access control
    enable_rate_limiting: bool = True
    max_requests_per_minute: int = 100

    # Input validation
    max_query_length: int = 10000
    max_content_length: int = 1000000  # 1MB


@dataclass
class SessionMgmtConfig:
    """Main configuration container."""

    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    search: SearchConfig = field(default_factory=SearchConfig)
    token_optimization: TokenOptimizationConfig = field(
        default_factory=TokenOptimizationConfig,
    )
    session: SessionConfig = field(default_factory=SessionConfig)
    integration: IntegrationConfig = field(default_factory=IntegrationConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)

    # MCP Server settings
    server_host: str = "localhost"
    server_port: int = 3000
    enable_websockets: bool = True

    # Development settings
    debug: bool = False
    enable_hot_reload: bool = False


class ConfigLoader:
    """Loads configuration from pyproject.toml and environment variables."""

    def __init__(self, project_root: Path | None = None) -> None:
        self.project_root = project_root or self._find_project_root()
        self._config_cache: SessionMgmtConfig | None = None

    def _find_project_root(self) -> Path:
        """Find the project root by looking for pyproject.toml."""
        current = Path.cwd()

        # Check if we're already in the session-mgmt-mcp directory
        if (current / "pyproject.toml").exists():
            return current

        # Look for pyproject.toml in parent directories
        for parent in current.parents:
            if (parent / "pyproject.toml").exists():
                # Check if this is the session-mgmt-mcp project
                try:
                    with open(parent / "pyproject.toml", "rb") as f:
                        if tomllib:
                            toml_data = tomllib.load(f)
                            if (
                                toml_data.get("project", {}).get("name")
                                == "session-mgmt-mcp"
                            ):
                                return parent
                except Exception:
                    pass

        # Fallback to current directory
        return current

    def load_config(self, reload: bool = False) -> SessionMgmtConfig:
        """Load configuration from pyproject.toml and environment variables."""
        if self._config_cache and not reload:
            return self._config_cache

        config = SessionMgmtConfig()

        # Load from pyproject.toml
        pyproject_path = self.project_root / "pyproject.toml"
        if pyproject_path.exists() and tomllib:
            try:
                with open(pyproject_path, "rb") as f:
                    toml_data = tomllib.load(f)
                    self._apply_toml_config(config, toml_data)
            except Exception as e:
                print(f"Warning: Failed to load pyproject.toml: {e}")

        # Override with environment variables
        self._apply_env_config(config)

        # Expand user paths
        self._expand_paths(config)

        # Validate configuration
        self._validate_config(config)

        self._config_cache = config
        return config

    def _get_tool_config(self, toml_data: dict[str, Any]) -> dict[str, Any]:
        """Extract tool configuration from TOML data."""
        tool_config = toml_data.get("tool", {}).get("session-mgmt-mcp", {})
        if not tool_config:
            # Also check tool.session_mgmt_mcp (underscore variant)
            tool_config = toml_data.get("tool", {}).get("session_mgmt_mcp", {})
        return tool_config

    def _apply_section_config(
        self,
        config: SessionMgmtConfig,
        section_name: str,
        section_config: dict[str, Any],
    ) -> None:
        """Apply configuration for a specific section."""
        if not hasattr(config, section_name):
            return

        section_obj = getattr(config, section_name)
        for key, value in section_config.items():
            if hasattr(section_obj, key):
                setattr(section_obj, key, value)

    def _apply_server_config(
        self,
        config: SessionMgmtConfig,
        tool_config: dict[str, Any],
    ) -> None:
        """Apply server-level configuration."""
        server_keys = [
            "server_host",
            "server_port",
            "enable_websockets",
            "debug",
            "enable_hot_reload",
        ]

        for key in server_keys:
            if key in tool_config and hasattr(config, key):
                setattr(config, key, tool_config[key])

    def _apply_toml_config(
        self, config: SessionMgmtConfig, toml_data: dict[str, Any]
    ) -> None:
        """Apply configuration from pyproject.toml."""
        tool_config = self._get_tool_config(toml_data)
        if not tool_config:
            return

        # Define config sections that map to config object attributes
        config_sections = [
            "database",
            "search",
            "token_optimization",
            "session",
            "integration",
            "logging",
            "security",
        ]

        # Apply section configs
        for section_name in config_sections:
            if section_name in tool_config:
                self._apply_section_config(
                    config,
                    section_name,
                    tool_config[section_name],
                )

        # Apply server-level config
        self._apply_server_config(config, tool_config)

    def _apply_env_config(self, config: SessionMgmtConfig) -> None:
        """Apply configuration from environment variables."""
        env_mappings = {
            # Database
            "SESSION_MGMT_DB_PATH": ("database", "path"),
            "SESSION_MGMT_DB_TIMEOUT": ("database", "connection_timeout", int),
            "SESSION_MGMT_ENABLE_MULTI_PROJECT": (
                "database",
                "enable_multi_project",
                bool,
            ),
            # Search
            "SESSION_MGMT_ENABLE_SEMANTIC_SEARCH": (
                "search",
                "enable_semantic_search",
                bool,
            ),
            "SESSION_MGMT_EMBEDDING_MODEL": ("search", "embedding_model"),
            # Token optimization
            "SESSION_MGMT_ENABLE_OPTIMIZATION": (
                "token_optimization",
                "enable_optimization",
                bool,
            ),
            "SESSION_MGMT_MAX_TOKENS": (
                "token_optimization",
                "default_max_tokens",
                int,
            ),
            # Session
            "SESSION_MGMT_AUTO_CHECKPOINT": (
                "session",
                "auto_checkpoint_interval",
                int,
            ),
            "SESSION_MGMT_ENABLE_AUTO_COMMIT": ("session", "enable_auto_commit", bool),
            # Logging
            "SESSION_MGMT_LOG_LEVEL": ("logging", "level"),
            "SESSION_MGMT_ENABLE_FILE_LOGGING": (
                "logging",
                "enable_file_logging",
                bool,
            ),
            # Server
            "SESSION_MGMT_HOST": ("server_host",),
            "SESSION_MGMT_PORT": ("server_port", int),
            "SESSION_MGMT_DEBUG": ("debug", bool),
        }

        for env_var, mapping in env_mappings.items():
            value = os.getenv(env_var)
            if value is not None:
                try:
                    # Parse value if type converter provided
                    if len(mapping) > 2:
                        converter = mapping[2]
                        if converter is bool:
                            value = value.lower() in ("true", "1", "yes", "on")
                        elif converter is int:
                            value = int(value)
                    elif len(mapping) == 2 and not isinstance(mapping[1], str):
                        # This is a top-level attribute with type (e.g., ("server_port", int))
                        converter = mapping[1]
                        if converter is bool:
                            value = value.lower() in ("true", "1", "yes", "on")
                        elif converter is int:
                            value = int(value)

                    # Set value on config object
                    if len(mapping) == 3 or (
                        len(mapping) == 2 and isinstance(mapping[1], str)
                    ):
                        # Nested attribute (e.g., database.path) with optional type
                        section_name, attr_name = mapping[0], mapping[1]
                        section = getattr(config, section_name)
                        setattr(section, attr_name, value)
                    elif len(mapping) >= 1:
                        # Top-level attribute - mapping[0] should be string
                        attr_name = mapping[0]
                        if isinstance(attr_name, str):
                            setattr(config, attr_name, value)

                except (ValueError, AttributeError) as e:
                    print(
                        f"Warning: Invalid environment variable {env_var}={value}: {e}",
                    )

    def _expand_paths(self, config: SessionMgmtConfig) -> None:
        """Expand user paths in configuration."""
        # Database path
        config.database.path = os.path.expanduser(config.database.path)

        # Log file path
        config.logging.log_file_path = os.path.expanduser(config.logging.log_file_path)

        # Global workspace path
        config.integration.global_workspace_path = os.path.expanduser(
            config.integration.global_workspace_path,
        )

    def _validate_config(self, config: SessionMgmtConfig) -> None:
        """Validate configuration values."""
        # Validate port range
        if not (1024 <= config.server_port <= 65535):
            print(
                f"Warning: Invalid server port {config.server_port}, using default 3000",
            )
            config.server_port = 3000

        # Validate token limits
        if config.token_optimization.default_max_tokens < 100:
            print("Warning: max_tokens too low, setting to 100")
            config.token_optimization.default_max_tokens = 100

        # Validate log level
        valid_log_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if config.logging.level.upper() not in valid_log_levels:
            print(f"Warning: Invalid log level {config.logging.level}, using INFO")
            config.logging.level = "INFO"

        # Create log directory if needed
        if config.logging.enable_file_logging:
            log_path = Path(config.logging.log_file_path)
            log_path.parent.mkdir(parents=True, exist_ok=True)

    def get_example_config(self) -> str:
        """Get example pyproject.toml configuration."""
        return """
# Example session-mgmt-mcp configuration in pyproject.toml

[tool.session-mgmt-mcp]
# Server settings
debug = false
server_host = "localhost"
server_port = 3000
enable_websockets = true

[tool.session-mgmt-mcp.database]
# Database configuration
path = "~/.claude/data/reflection.duckdb"
connection_timeout = 30
query_timeout = 120
enable_multi_project = true
auto_detect_projects = true
enable_full_text_search = true

[tool.session-mgmt-mcp.search]
# Search and embedding settings
enable_semantic_search = true
embedding_model = "all-MiniLM-L6-v2"
enable_faceted_search = true
max_facet_values = 50
enable_search_suggestions = true

[tool.session-mgmt-mcp.token_optimization]
# Token optimization settings
enable_optimization = true
default_max_tokens = 4000
default_chunk_size = 2000
preferred_strategy = "auto"
enable_response_chunking = true
track_usage = true

[tool.session-mgmt-mcp.session]
# Session management
auto_checkpoint_interval = 1800  # 30 minutes
enable_auto_commit = true
enable_permission_system = true
default_trusted_operations = ["git_commit", "uv_sync", "file_operations"]
session_retention_days = 365

[tool.session-mgmt-mcp.integration]
# External integrations
enable_crackerjack = true
enable_git_integration = true
global_workspace_path = "~/Projects/claude"
enable_global_toolkits = true

[tool.session-mgmt-mcp.logging]
# Logging configuration
level = "INFO"
enable_file_logging = true
log_file_path = "~/.claude/logs/session-mgmt.log"
enable_performance_logging = false
log_slow_queries = true

[tool.session-mgmt-mcp.security]
# Security settings
anonymize_paths = false
enable_rate_limiting = true
max_requests_per_minute = 100
max_query_length = 10000
"""


# Global config instance
_config_loader: ConfigLoader | None = None


def get_config(reload: bool = False) -> SessionMgmtConfig:
    """Get the global configuration instance."""
    global _config_loader

    if _config_loader is None:
        _config_loader = ConfigLoader()

    return _config_loader.load_config(reload=reload)


def reload_config() -> SessionMgmtConfig:
    """Force reload configuration from files."""
    return get_config(reload=True)
