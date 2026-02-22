import typing as t
from pathlib import Path

from pydantic_settings import BaseSettings as Settings


class CleaningSettings(Settings):
    clean: bool = True
    strip_comments_only: bool = False
    strip_docstrings_only: bool = False
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
    __test__ = False

    test: bool = False
    benchmark: bool = False
    test_workers: int = 0
    test_timeout: int = 0
    incremental_tests: bool = True
    auto_detect_workers: bool = True
    max_workers: int = 8
    min_workers: int = 2
    memory_per_worker_gb: float = 2.0
    coverage: bool = False
    xcode_tests: bool = False
    xcode_project: str = "app/MdInjectApp/MdInjectApp.xcodeproj"
    xcode_scheme: str = "MdInjectApp"
    xcode_configuration: str = "Debug"
    xcode_destination: str = "platform=macOS"
    xdist_dist_mode: t.Literal["loadfile", "each", "loadscope", "no"] = "loadfile"
    xdist_timeout_seconds: int = 60
    xdist_fallback_to_sequential: bool = True


class PublishSettings(Settings):
    publish: str | None = None
    bump: str | None = None
    all: str | None = None
    no_git_tags: bool = False
    skip_version_check: bool = False


class GitSettings(Settings):
    commit: bool = False
    create_pr: bool = False


class FixStrategyMemorySettings(Settings):
    enabled: bool = True
    db_path: str = ".crackerjack/fix_strategy_memory.db"
    embedding_model: str = "all-MiniLM-L6-v2"
    min_similarity: float = 0.3
    k_neighbors: int = 10
    auto_update_effectiveness: bool = True


class AISettings(Settings):
    ai_agent: bool = False
    start_mcp_server: bool = False
    max_iterations: int = 20
    autofix: bool = True
    ai_agent_autofix: bool = False

    ai_providers: list[t.Literal["claude", "qwen", "ollama"]] = [
        "claude",
        "qwen",
        "ollama",
    ]

    ai_provider: t.Literal["claude", "qwen", "ollama"] = "claude"

    ollama_base_url: str = "http://localhost: 11434"
    ollama_model: str = "qwen2.5-coder: 7b"
    ollama_timeout: int = 300


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


class DocumentationSettings(Settings):
    enabled: bool = True
    auto_cleanup_on_publish: bool = True
    dry_run_by_default: bool = False
    backup_before_cleanup: bool = True
    essential_files: list[str] = [
        "AGENTS.md",
        "CHANGELOG.md",
        "CLAUDE.md",
        "NOTES.md",
        "QWEN.md",
        "README.md",
        "RULES.md",
        "SECURITY.md",
        "LICENSE",
        "pyproject.toml",
        "example.mcp.json",
    ]
    archive_patterns: list[str] = [
        "*PLAN*.md",
        "*SUMMARY*.md",
        "*ANALYSIS*.md",
        "*MIGRATION*.md",
        "*PROGRESS*.md",
        "SPRINT*.md",
        "PHASE*.md",
    ]
    archive_subdirectories: dict[str, str] = {
        "*PLAN*.md": "implementation-plans",
        "*SUMMARY*.md": "summaries",
        "SPRINT*.md": "sprints",
        "PHASE*.md": "phase-completions",
        "*CLEANUP*.md": "cleanup",
        "*CONFIG*.md": "config-automation",
        "*PERFORMANCE*.md": "performance",
    }


class AdvancedSettings(Settings):
    enabled: bool = False
    license_key: str | None = None
    organization: str | None = None


class ConsoleSettings(Settings):
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
    zuban_lsp_timeout: float = 120.0
    skylos_timeout: int = 600
    refurb_timeout: int = 600
    zuban_timeout: int = 60
    bandit_timeout: int = 300
    semgrep_timeout: int = 300
    pip_audit_timeout: int = 120
    creosote_timeout: int = 300
    complexipy_timeout: int = 600
    pyscn_timeout: int = 60
    gitleaks_timeout: int = 60
    lychee_timeout: int = 300


class ConfigCleanupSettings(Settings):
    enabled: bool = True
    backup_before_cleanup: bool = True
    dry_run_by_default: bool = False

    merge_strategies: dict[str, str] = {
        "mypy.ini": "tool.mypy",
        ".ruffignore": "tool.ruff.extend-exclude",
        ".mdformatignore": "tool.mdformat.exclude",
        "pyrightconfig.json": "tool.pyright",
        ".codespell-ignore": "tool.codespell.ignore-words-list",
        ".codespellrc": "tool.codespell",
    }

    config_files_to_remove: list[str] = [
        ".semgrep.yml",
        ".semgrepignore",
        ".gitleaksignore",
        ".gitleaks.toml",
    ]

    cache_dirs_to_clean: list[str] = [
        ".complexipy_cache",
        ".pyscn",
        "__pycache__",
        ".pytest_cache",
        ".ruff_cache",
        ".mypy_cache",
        ".coverage",
        "htmlcov/",
    ]

    output_files_to_clean: list[str] = [
        "complexipy.json",
        "coverage.xml",
        "coverage.json",
    ]


class GitCleanupSettings(Settings):
    enabled: bool = True
    smart_approach: bool = True
    filter_branch_threshold: int = 100
    require_clean_working_tree: bool = True


class DocUpdateSettings(Settings):
    enabled: bool = True
    ai_powered: bool = True
    doc_patterns: list[str] = [
        "*.md",
        "docs/**/*.md",
        "docs/reference/**/*.md",
        "docs/guides/**/*.md",
    ]
    api_key: str | None = None
    model: str = "claude-sonnet-4-20250514"
    max_tokens: int = 4096


class IncrementalQASettings(Settings):
    enabled: bool = True
    full_scan_threshold: int = 50
    base_branch: str = "main"
    force_incremental: bool = False
    force_full: bool = False


class FileChunkingSettings(Settings):
    enabled: bool = False
    chunk_size: int = 50
    overlap_percentage: int = 10


class FastHooksSettings(Settings):
    incremental: bool = True
    full_scan_threshold: int = 50
    base_branch: str = "main"
    force_incremental: bool = False
    force_full: bool = False


class SkillsSettings(Settings):
    enabled: bool = True

    backend: str = "auto"

    db_path: str | None = None

    mcp_server_url: str = "http://localhost: 8678"

    mcp_timeout: int = 5

    min_similarity: float = 0.3

    max_recommendations: int = 5

    enable_phase_aware: bool = True

    phase_weight: float = 0.3


class LearningSettings(Settings):
    enabled: bool = True
    effectiveness_tracking_enabled: bool = True
    min_sample_size: int = 10
    adaptation_rate: float = 0.1

    skills_effectiveness_db: str = ".crackerjack/skills_effectiveness.db"

    query_learning_db: str = ".crackerjack/query_learning.db"
    query_min_interactions: int = 5

    dag_learning_db: str = ".crackerjack/dag_learning.db"
    dag_min_executions: int = 5

    adapter_learning_db: str = ".crackerjack/adapter_learning.db"
    adapter_min_attempts: int = 5

    workflow_learning_db: str = ".crackerjack/workflow_learning.db"
    workflow_min_executions: int = 5


class MahavishnuSettings(Settings):
    enabled: bool = False
    git_metrics_enabled: bool = True
    git_metrics_db_path: str = ".crackerjack/git_metrics.db"
    portfolio_repos: list[str] = []
    websocket_enabled: bool = False
    websocket_host: str = "127.0.0.1"
    websocket_port: int = 8686
    dashboard_refresh_interval: int = 300
    db_path: str = ".crackerjack/mahavishnu.db"
    cache_ttl_seconds: int = 300


class PoolConfiguration(Settings):
    """Pool configuration settings."""

    name: str = "crackerjack-quality-scanners"
    pool_type: str = "mahavishnu"  # or "session-buddy", "kubernetes"
    min_workers: int = 2
    max_workers: int = 8
    worker_type: str = "terminal-qwen"  # or "terminal-claude", "container"


class AutoScalingConfiguration(Settings):
    """Auto-scaling configuration for pool management."""

    enabled: bool = True
    scale_up_threshold: int = 10  # Pending tasks
    scale_down_threshold: int = 300  # Idle seconds
    max_workers: int = 16


class MemoryConfiguration(Settings):
    """Memory integration settings for smart caching."""

    enabled: bool = True
    cache_duration: int = 86400  # 24 hours in seconds


class PoolRouterConfiguration(Settings):
    """Pool router configuration for intelligent tool-to-worker routing."""

    enabled: bool = True
    tool_worker_map: dict[str, str] = {
        # Heavy CPU tools → dedicated workers
        "refurb": "heavy-cpu-worker",
        "complexipy": "heavy-cpu-worker",
        "pylint": "heavy-cpu-worker",
        "mypy": "heavy-cpu-worker",
        "bandit": "heavy-cpu-worker",
        # Fast tools (Rust-based, already optimized) → shared workers
        "skylos": "fast-worker",
        "ruff": "fast-worker",
        "vulture": "fast-worker",
        "codespell": "fast-worker",
        "check-jsonschema": "fast-worker",
        # Security tools → dedicated workers (isolation)
        "semgrep": "security-worker",
        "gitleaks": "security-worker",
        # Note: bandit and pylint defined above as heavy-cpu-worker
    }


class PoolScanningSettings(Settings):
    """Settings for Mahavishnu pool-based scanning acceleration."""

    enabled: bool = False
    mcp_server_url: str = "http://localhost:8680"

    pool: PoolConfiguration = PoolConfiguration()

    # Tools to run in pools (slow tools that benefit from parallelization)
    pooled_tools: list[str] = [
        "refurb",
        "complexipy",
        "skylos",
        "semgrep",
        "gitleaks",
    ]

    # Tools to run locally (fast tools that don't benefit significantly from pools)
    local_tools: list[str] = [
        "ruff",
        "vulture",
        "codespell",
        "check-jsonschema",
    ]

    # Auto-scaling configuration
    autoscaling: AutoScalingConfiguration = AutoScalingConfiguration()

    # Memory integration
    memory: MemoryConfiguration = MemoryConfiguration()

    # Pool router configuration (Phase 3)
    pool_router: PoolRouterConfiguration = PoolRouterConfiguration()


class PoolConfiguration(Settings):
    """Pool configuration settings."""

    name: str = "crackerjack-quality-scanners"
    pool_type: str = "mahavishnu"  # or "session-buddy", "kubernetes"
    min_workers: int = 2
    max_workers: int = 8
    worker_type: str = "terminal-qwen"  # or "terminal-claude", "container"


class AutoScalingConfiguration(Settings):
    """Auto-scaling configuration for pool management."""

    enabled: bool = True
    scale_up_threshold: int = 10  # Pending tasks
    scale_down_threshold: int = 300  # Idle seconds
    max_workers: int = 16


class MemoryConfiguration(Settings):
    """Memory integration settings for smart caching."""

    enabled: bool = True
    cache_duration: int = 86400  # 24 hours in seconds


class CrackerjackSettings(Settings):
    console: ConsoleSettings = ConsoleSettings()
    cleaning: CleaningSettings = CleaningSettings()
    hooks: HookSettings = HookSettings()
    testing: TestSettings = TestSettings()
    publishing: PublishSettings = PublishSettings()
    git: GitSettings = GitSettings()
    ai: AISettings = AISettings()
    fix_strategy_memory: FixStrategyMemorySettings = FixStrategyMemorySettings()
    execution: ExecutionSettings = ExecutionSettings()
    progress: ProgressSettings = ProgressSettings()
    cleanup: CleanupSettings = CleanupSettings()
    documentation: DocumentationSettings = DocumentationSettings()
    advanced: AdvancedSettings = AdvancedSettings()
    mcp_server: MCPServerSettings = MCPServerSettings()
    zuban_lsp: ZubanLSPSettings = ZubanLSPSettings()
    global_lock: GlobalLockSettings = GlobalLockSettings()
    adapter_timeouts: AdapterTimeouts = AdapterTimeouts()
    config_cleanup: ConfigCleanupSettings = ConfigCleanupSettings()
    git_cleanup: GitCleanupSettings = GitCleanupSettings()
    doc_updates: DocUpdateSettings = DocUpdateSettings()
    incremental_qa: IncrementalQASettings = IncrementalQASettings()
    file_chunking: FileChunkingSettings = FileChunkingSettings()
    fast_hooks: FastHooksSettings = FastHooksSettings()
    skills: SkillsSettings = SkillsSettings()
    learning: LearningSettings = LearningSettings()
    mahavishnu: MahavishnuSettings = MahavishnuSettings()
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
