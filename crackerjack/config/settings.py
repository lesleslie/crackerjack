"""Unified ACB Settings for Crackerjack.

Single source of truth consolidating all configuration:
- Workflow settings (cleaning, hooks, testing, publishing, git, AI)
- Orchestration settings (caching, parallelism, execution)
- QA framework settings
- Enterprise and MCP server settings

ACB Settings provides:
- YAML-based configuration from settings directory
- Type validation via Pydantic
- Secrets management (auto-masked in logs)
- Configuration layering and merging
- Sensible defaults for all settings
"""

from __future__ import annotations

from pathlib import Path

from acb.config import Settings
from pydantic import Field


class CrackerjackSettings(Settings):
    """Unified settings for all Crackerjack configuration.

    Configuration Loading:
        Settings are loaded from YAML files in the settings directory:
        - settings/crackerjack.yaml (main config)
        - settings/local.yaml (local overrides, gitignored)
        - settings/production.yaml (production settings)

    Priority Order:
        1. settings/local.yaml (highest - local overrides)
        2. settings/{environment}.yaml (environment-specific)
        3. settings/crackerjack.yaml (base configuration)
        4. Defaults from this class (lowest)

    Settings Directory Structure:
        settings/
        ├── crackerjack.yaml      # Base configuration (committed)
        ├── local.yaml            # Local overrides (gitignored)
        ├── development.yaml      # Dev environment (committed)
        └── production.yaml       # Prod environment (committed)
    """

    # === Workflow Settings ===

    # Cleaning
    clean: bool = True
    update_docs: bool = False
    force_update_docs: bool = False
    compress_docs: bool = False
    auto_compress_docs: bool = False

    # Hooks
    skip_hooks: bool = False
    update_precommit: bool = False
    experimental_hooks: bool = False
    enable_pyrefly: bool = False
    enable_ty: bool = False
    enable_lsp_optimization: bool = False

    # Testing
    run_tests: bool = False
    benchmark: bool = False
    test_workers: int = 0
    test_timeout: int = 0

    # Publishing
    publish_version: str | None = None
    bump_version: str | None = None
    all_workflow: str | None = None
    no_git_tags: bool = False
    skip_version_check: bool = False

    # Git
    commit: bool = False
    create_pr: bool = False

    # AI Agent
    ai_agent: bool = False
    start_mcp_server: bool = False
    max_iterations: int = 5
    autofix: bool = True
    ai_agent_autofix: bool = False

    # Execution
    interactive: bool = False
    verbose: bool = False
    async_mode: bool = False
    no_config_updates: bool = False

    # Progress
    progress_enabled: bool = False

    # Cleanup
    auto_cleanup: bool = True
    keep_debug_logs: int = 5
    keep_coverage_files: int = 10

    # Enterprise
    enterprise_enabled: bool = False
    license_key: str | None = Field(None, description="Enterprise license key (auto-masked in logs)")
    organization: str | None = None

    # MCP Server
    mcp_http_port: int = 8676
    mcp_http_host: str = "127.0.0.1"
    mcp_websocket_port: int = 8675
    mcp_http_enabled: bool = False

    # Zuban LSP
    zuban_enabled: bool = True
    zuban_auto_start: bool = True
    zuban_port: int = 8677
    zuban_mode: str = "stdio"
    zuban_timeout: int = 30

    # === Orchestration Settings ===

    # Core orchestration
    enable_orchestration: bool = False
    orchestration_mode: str = "acb"  # 'legacy' or 'acb'

    # Cache settings
    enable_caching: bool = True
    cache_backend: str = "memory"  # 'memory' or 'tool_proxy'
    cache_ttl: int = 3600  # seconds
    cache_max_entries: int = 100  # memory cache only

    # Execution settings
    max_parallel_hooks: int = 4
    default_timeout: int = 600  # seconds
    stop_on_critical_failure: bool = True

    # Advanced orchestration
    enable_dependency_resolution: bool = True
    log_cache_stats: bool = False
    log_execution_timing: bool = False

    # Triple parallelism (Phase 5-7)
    enable_strategy_parallelism: bool = True  # Run fast + comprehensive concurrently
    enable_adaptive_execution: bool = True  # Use adaptive strategy (dependency-aware)
    max_concurrent_strategies: int = 2  # Usually 2 (fast + comprehensive)

    # Phase 8: Direct tool invocation
    use_precommit_legacy: bool = True  # Use pre-commit wrapper (True) or direct (False)

    # === QA Framework Settings ===

    # Core QA settings
    project_root: Path = Field(default_factory=Path.cwd, description="Project root directory")
    qa_max_parallel_checks: int = 4
    qa_fail_fast: bool = False
    qa_run_formatters_first: bool = True
    qa_enable_incremental: bool = True

    # === Global Settings ===

    # Global locking
    global_lock_timeout: int = 30
    lock_directory: Path = Field(
        default_factory=lambda: Path.home() / ".crackerjack" / "locks",
        description="Directory for global lock files"
    )

    # === Monitoring & Dashboard Settings ===

    # Dashboard
    dashboard_enabled: bool = False
    dashboard_port: int = 8678
    dashboard_host: str = "127.0.0.1"

    # Monitoring
    monitoring_enabled: bool = False
    monitoring_interval: int = 60  # seconds

    # === Advanced Features ===

    # Code stripping
    strip_code: bool = False
    strip_patterns: list[str] = Field(
        default_factory=list,
        description="Patterns for code stripping (e.g., 'TODO', 'DEBUG')"
    )

    # AI debugging
    ai_debug: bool = False
    ai_debug_verbose: bool = False

    # Watchdog
    watchdog_enabled: bool = False
    watchdog_interval: int = 30  # seconds

    # Coverage
    coverage_enabled: bool = False
    coverage_status: bool = False

    # Workflow visualization
    show_workflow: bool = False


# Note: Settings registration happens in __init__.py to avoid circular imports
