from pathlib import Path

from pydantic_settings import BaseSettings as Settings


class CleaningSettings(Settings):
    clean: bool = True
    update_docs: bool = False
    force_update_docs: bool = False
    compress_docs: bool = False
    auto_compress_docs: bool = False


class HookSettings(Settings):
    skip_hooks: bool = False
    experimental_hooks: bool = False
    enable_pyrefly: bool = False
    enable_ty: bool = False
    enable_lsp_optimization: bool = False


class TestSettings(Settings):
    test: bool = False
    benchmark: bool = False
    test_workers: int = 0
    test_timeout: int = 0
    auto_detect_workers: bool = True
    max_workers: int = 8
    min_workers: int = 2
    memory_per_worker_gb: float = 2.0
    coverage: bool = False


class PublishSettings(Settings):
    publish: str | None = None
    bump: str | None = None
    all: str | None = None
    no_git_tags: bool = False
    skip_version_check: bool = False


class GitSettings(Settings):
    commit: bool = False
    create_pr: bool = False


class AISettings(Settings):
    ai_agent: bool = False
    start_mcp_server: bool = False
    max_iterations: int = 5
    autofix: bool = True
    ai_agent_autofix: bool = False


class ExecutionSettings(Settings):
    interactive: bool = False
    verbose: bool = False
    async_mode: bool = False
    no_config_updates: bool = False


class ProgressSettings(Settings):
    enabled: bool = False
    track_progress: bool = True


class CleanupSettings(Settings):
    auto_cleanup: bool = True
    keep_debug_logs: int = 5
    keep_coverage_files: int = 10


class AdvancedSettings(Settings):
    enabled: bool = False
    license_key: str | None = None
    organization: str | None = None


class ConsoleSettings(Settings):
    """Console/UI related settings."""

    width: int = 70
    verbose: bool = False


class MCPServerSettings(Settings):
    http_port: int = 8676
    http_host: str = "127.0.0.1"
    http_enabled: bool = False
    websocket_port: int = 8675


class ZubanLSPSettings(Settings):
    enabled: bool = True
    auto_start: bool = True
    port: int = 8677
    mode: str = "stdio"
    timeout: int = 120


class GlobalLockSettings(Settings):
    enabled: bool = True
    timeout_seconds: float = 1800.0
    stale_lock_hours: float = 2.0
    lock_directory: Path = Path.home() / ".crackerjack" / "locks"
    session_heartbeat_interval: float = 30.0
    max_retry_attempts: int = 3
    retry_delay_seconds: float = 5.0
    enable_lock_monitoring: bool = True


class AdapterTimeouts(Settings):
    """Timeout settings for QA adapters (in seconds)."""

    zuban_lsp_timeout: float = 120.0  # Zuban LSP server
    skylos_timeout: int = 600  # Dead code detection (default: 10 minutes)
    refurb_timeout: int = 120  # Modern Python suggestions
    zuban_timeout: int = 120  # Type checking
    bandit_timeout: int = 300  # Security linting
    semgrep_timeout: int = 300  # Security pattern matching
    pip_audit_timeout: int = 120  # Dependency security
    creosote_timeout: int = 120  # Unused imports
    complexipy_timeout: int = 60  # Complexity analysis
    pyscn_timeout: int = 60  # Code quality
    gitleaks_timeout: int = 60  # Secret detection


class CrackerjackSettings(Settings):
    console: ConsoleSettings = ConsoleSettings()
    cleaning: CleaningSettings = CleaningSettings()
    hooks: HookSettings = HookSettings()
    testing: TestSettings = TestSettings()
    publishing: PublishSettings = PublishSettings()
    git: GitSettings = GitSettings()
    ai: AISettings = AISettings()
    execution: ExecutionSettings = ExecutionSettings()
    progress: ProgressSettings = ProgressSettings()
    cleanup: CleanupSettings = CleanupSettings()
    advanced: AdvancedSettings = AdvancedSettings()
    mcp_server: MCPServerSettings = MCPServerSettings()
    zuban_lsp: ZubanLSPSettings = ZubanLSPSettings()
    global_lock: GlobalLockSettings = GlobalLockSettings()
    adapter_timeouts: AdapterTimeouts = AdapterTimeouts()
    enable_orchestration: bool = True
    orchestration_mode: str = "oneiric"
    enable_caching: bool = True
    cache_backend: str = "memory"
    cache_ttl: int = 3600
    cache_max_entries: int = 100
    max_parallel_hooks: int = 4
    default_timeout: int = 1800
    stop_on_critical_failure: bool = True
    enable_dependency_resolution: bool = True
    log_cache_stats: bool = False
    log_execution_timing: bool = False
    enable_strategy_parallelism: bool = True
    enable_adaptive_execution: bool = True
    max_concurrent_strategies: int = 2
    enable_tool_proxy: bool = True
