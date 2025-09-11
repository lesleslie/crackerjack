#!/usr/bin/env python3
"""Configuration Management for Session Management MCP Server.

Loads configuration from pyproject.toml and environment variables with sensible defaults.
"""

import os
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

try:
    import tomllib  # Python 3.11+
except ImportError:
    try:
        import tomli as tomllib  # fallback for older Python versions
    except ImportError:
        tomllib = None


class DatabaseConfig(BaseModel):
    """Database configuration."""

    path: str = Field(
        default="~/.claude/data/reflection.duckdb",
        description="Path to the DuckDB database file",
    )
    connection_timeout: int = Field(
        default=30,
        ge=1,
        le=300,
        description="Database connection timeout in seconds",
    )
    query_timeout: int = Field(
        default=120,
        ge=1,
        le=3600,
        description="Database query timeout in seconds",
    )
    max_connections: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Maximum number of database connections",
    )

    # Multi-project settings
    enable_multi_project: bool = Field(
        default=True,
        description="Enable multi-project coordination features",
    )
    auto_detect_projects: bool = Field(
        default=True,
        description="Auto-detect project relationships",
    )
    project_groups_enabled: bool = Field(
        default=True,
        description="Enable project grouping functionality",
    )

    # Search settings
    enable_full_text_search: bool = Field(
        default=True,
        description="Enable full-text search capabilities",
    )
    search_index_update_interval: int = Field(
        default=3600,
        ge=60,
        le=86400,
        description="Search index update interval in seconds",
    )
    max_search_results: int = Field(
        default=100,
        ge=1,
        le=10000,
        description="Maximum number of search results to return",
    )

    @field_validator("path")
    @classmethod
    def expand_path(cls, v: str) -> str:
        """Expand user paths in database path."""
        return os.path.expanduser(v)


class SearchConfig(BaseModel):
    """Search and indexing configuration."""

    enable_semantic_search: bool = Field(
        default=True,
        description="Enable semantic search using embeddings",
    )
    embedding_model: str = Field(
        default="all-MiniLM-L6-v2",
        description="Embedding model for semantic search",
    )
    embedding_cache_size: int = Field(
        default=1000,
        ge=10,
        le=100000,
        description="Number of embeddings to cache in memory",
    )

    # Advanced search settings
    enable_faceted_search: bool = Field(
        default=True,
        description="Enable faceted search capabilities",
    )
    max_facet_values: int = Field(
        default=50,
        ge=1,
        le=1000,
        description="Maximum number of facet values to return",
    )
    enable_search_suggestions: bool = Field(
        default=True,
        description="Enable search suggestions and autocomplete",
    )
    suggestion_limit: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Maximum number of search suggestions",
    )

    # Full-text search
    enable_stemming: bool = Field(
        default=True,
        description="Enable word stemming in search",
    )
    enable_fuzzy_matching: bool = Field(
        default=True,
        description="Enable fuzzy matching for typos",
    )
    fuzzy_threshold: float = Field(
        default=0.8,
        ge=0.1,
        le=1.0,
        description="Fuzzy matching similarity threshold",
    )


class TokenOptimizationConfig(BaseModel):
    """Token optimization settings."""

    enable_optimization: bool = Field(
        default=True,
        description="Enable token optimization features",
    )
    default_max_tokens: int = Field(
        default=4000,
        ge=100,
        le=200000,
        description="Default maximum tokens for responses",
    )
    default_chunk_size: int = Field(
        default=2000,
        ge=50,
        le=100000,
        description="Default chunk size for response splitting",
    )

    # Optimization strategies
    preferred_strategy: Literal[
        "auto", "truncate_old", "summarize_content", "compress"
    ] = Field(
        default="auto",
        description="Preferred optimization strategy",
    )
    enable_response_chunking: bool = Field(
        default=True,
        description="Enable automatic response chunking for large outputs",
    )
    enable_duplicate_filtering: bool = Field(
        default=True,
        description="Filter out duplicate content in responses",
    )

    # Usage tracking
    track_usage: bool = Field(
        default=True,
        description="Track token usage statistics",
    )
    usage_retention_days: int = Field(
        default=90,
        ge=1,
        le=3650,
        description="Number of days to retain usage statistics",
    )

    @model_validator(mode="after")
    def validate_chunk_size(self) -> "TokenOptimizationConfig":
        """Ensure chunk size is not larger than max tokens."""
        if self.default_chunk_size >= self.default_max_tokens:
            self.default_chunk_size = max(50, self.default_max_tokens // 2)
        return self


class SessionConfig(BaseModel):
    """Session management configuration."""

    auto_checkpoint_interval: int = Field(
        default=1800,
        ge=60,
        le=86400,
        description="Auto-checkpoint interval in seconds (default: 30 minutes)",
    )
    enable_auto_commit: bool = Field(
        default=True,
        description="Enable automatic git commits during checkpoints",
    )
    commit_message_template: str = Field(
        default="checkpoint: Session checkpoint - {timestamp}",
        min_length=10,
        description="Template for automatic commit messages",
    )

    # Session permissions
    enable_permission_system: bool = Field(
        default=True,
        description="Enable the permission system for trusted operations",
    )
    default_trusted_operations: list[str] = Field(
        default=["git_commit", "uv_sync", "file_operations"],
        description="List of operations that are trusted by default",
    )

    # Session cleanup
    auto_cleanup_old_sessions: bool = Field(
        default=True,
        description="Automatically clean up old session data",
    )
    session_retention_days: int = Field(
        default=365,
        ge=1,
        le=3650,
        description="Number of days to retain session data",
    )

    @field_validator("commit_message_template")
    @classmethod
    def validate_commit_template(cls, v: str) -> str:
        """Ensure commit message template contains timestamp placeholder."""
        if "{timestamp}" not in v:
            msg = "Commit message template must contain {timestamp} placeholder"
            raise ValueError(msg)
        return v


class IntegrationConfig(BaseModel):
    """External integrations configuration."""

    # Crackerjack integration
    enable_crackerjack: bool = Field(
        default=True,
        description="Enable Crackerjack code quality integration",
    )
    crackerjack_command: str = Field(
        default="crackerjack",
        min_length=1,
        description="Command to run Crackerjack",
    )

    # Git integration
    enable_git_integration: bool = Field(
        default=True,
        description="Enable Git integration features",
    )
    git_auto_stage: bool = Field(
        default=False,
        description="Automatically stage changes before commits",
    )

    # Global workspace
    global_workspace_path: str = Field(
        default="~/Projects/claude",
        description="Path to global workspace directory",
    )
    enable_global_toolkits: bool = Field(
        default=True,
        description="Enable global toolkit discovery and usage",
    )

    @field_validator("global_workspace_path")
    @classmethod
    def expand_workspace_path(cls, v: str) -> str:
        """Expand user paths in global workspace path."""
        return os.path.expanduser(v)


class LoggingConfig(BaseModel):
    """Logging configuration."""

    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO",
        description="Logging level",
    )
    format: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        min_length=10,
        description="Log message format string",
    )

    # File logging
    enable_file_logging: bool = Field(
        default=True,
        description="Enable logging to file",
    )
    log_file_path: str = Field(
        default="~/.claude/logs/session-mgmt.log",
        description="Path to log file",
    )
    log_file_max_size: int = Field(
        default=10 * 1024 * 1024,
        ge=1024,
        le=1024 * 1024 * 1024,
        description="Maximum log file size in bytes (default: 10MB)",
    )
    log_file_backup_count: int = Field(
        default=5,
        ge=0,
        le=100,
        description="Number of backup log files to keep",
    )

    # Performance logging
    enable_performance_logging: bool = Field(
        default=False,
        description="Enable detailed performance logging",
    )
    log_slow_queries: bool = Field(
        default=True,
        description="Log slow database queries",
    )
    slow_query_threshold: float = Field(
        default=1.0,
        ge=0.1,
        le=60.0,
        description="Threshold for slow query logging in seconds",
    )

    @field_validator("log_file_path")
    @classmethod
    def expand_log_path(cls, v: str) -> str:
        """Expand user paths and create parent directories."""
        expanded = os.path.expanduser(v)
        Path(expanded).parent.mkdir(parents=True, exist_ok=True)
        return expanded


class SecurityConfig(BaseModel):
    """Security and privacy settings."""

    # Data privacy
    anonymize_paths: bool = Field(
        default=False,
        description="Anonymize file paths in logs and data",
    )
    exclude_sensitive_patterns: list[str] = Field(
        default=[
            r"password\s*=\s*['\"][^'\"]+['\"]",
            r"api[_-]?key\s*=\s*['\"][^'\"]+['\"]",
            r"secret\s*=\s*['\"][^'\"]+['\"]",
            r"token\s*=\s*['\"][^'\"]+['\"]",
        ],
        description="Regex patterns for sensitive data to exclude from storage",
    )

    # Access control
    enable_rate_limiting: bool = Field(
        default=True,
        description="Enable rate limiting for API requests",
    )
    max_requests_per_minute: int = Field(
        default=100,
        ge=1,
        le=10000,
        description="Maximum requests per minute per client",
    )

    # Input validation
    max_query_length: int = Field(
        default=10000,
        ge=100,
        le=1000000,
        description="Maximum length for search queries",
    )
    max_content_length: int = Field(
        default=1000000,
        ge=1000,
        le=100000000,
        description="Maximum content length in bytes (default: 1MB)",
    )

    @field_validator("exclude_sensitive_patterns")
    @classmethod
    def validate_patterns(cls, v: list[str]) -> list[str]:
        """Validate regex patterns."""
        import re

        for pattern in v:
            try:
                re.compile(
                    pattern
                )  # REGEX OK: Pattern validation for configuration system - legitimate use for validation
            except re.error as e:
                msg = f"Invalid regex pattern '{pattern}': {e}"
                raise ValueError(msg) from e
        return v


class SessionMgmtConfig(BaseSettings):
    """Main configuration container with environment variable support."""

    model_config = SettingsConfigDict(
        env_prefix="SESSION_MGMT_",
        env_nested_delimiter="__",
        case_sensitive=False,
        extra="ignore",
    )

    database: DatabaseConfig = Field(
        default_factory=DatabaseConfig,
        description="Database configuration settings",
    )
    search: SearchConfig = Field(
        default_factory=SearchConfig,
        description="Search and indexing configuration",
    )
    token_optimization: TokenOptimizationConfig = Field(
        default_factory=TokenOptimizationConfig,
        description="Token optimization settings",
    )
    session: SessionConfig = Field(
        default_factory=SessionConfig,
        description="Session management configuration",
    )
    integration: IntegrationConfig = Field(
        default_factory=IntegrationConfig,
        description="External integrations configuration",
    )
    logging: LoggingConfig = Field(
        default_factory=LoggingConfig,
        description="Logging configuration",
    )
    security: SecurityConfig = Field(
        default_factory=SecurityConfig,
        description="Security and privacy settings",
    )

    # MCP Server settings
    server_host: str = Field(
        default="localhost",
        description="MCP server host address",
    )
    server_port: int = Field(
        default=3000,
        ge=1024,
        le=65535,
        description="MCP server port number",
    )
    enable_websockets: bool = Field(
        default=True,
        description="Enable WebSocket support for MCP server",
    )

    # Development settings
    debug: bool = Field(
        default=False,
        description="Enable debug mode",
    )
    enable_hot_reload: bool = Field(
        default=False,
        description="Enable hot reloading during development",
    )


class ConfigLoader:
    """Simplified configuration loader for Pydantic models."""

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
                    with (parent / "pyproject.toml").open("rb") as f:
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
        """Load configuration using Pydantic's built-in settings management."""
        if self._config_cache and not reload:
            return self._config_cache

        # Load TOML config first if available
        toml_config = {}
        pyproject_path = self.project_root / "pyproject.toml"
        if pyproject_path.exists() and tomllib:
            try:
                with pyproject_path.open("rb") as f:
                    toml_data = tomllib.load(f)
                    toml_config = self._extract_tool_config(toml_data)
            except Exception as e:
                print(f"Warning: Failed to load pyproject.toml: {e}")

        # Create config with Pydantic's settings management
        # This automatically handles environment variables with SESSION_MGMT_ prefix
        config = SessionMgmtConfig(**toml_config)

        self._config_cache = config
        return config

    def _extract_tool_config(self, toml_data: dict[str, Any]) -> dict[str, Any]:
        """Extract tool configuration from TOML data."""
        tool_config = toml_data.get("tool", {}).get("session-mgmt-mcp", {})
        if not tool_config:
            # Also check tool.session_mgmt_mcp (underscore variant)
            tool_config = toml_data.get("tool", {}).get("session_mgmt_mcp", {})
        return tool_config

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
