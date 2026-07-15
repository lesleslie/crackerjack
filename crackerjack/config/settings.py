import typing as t
from pathlib import Path

from oneiric.core.config import OneiricMCPConfig


class CleaningSettings(OneiricMCPConfig):
    clean: bool = True
    strip_comments_only: bool = False
    strip_docstrings_only: bool = False
    update_docs: bool = False
    force_update_docs: bool = False
    compress_docs: bool = False
    auto_compress_docs: bool = False


class HookSettings(OneiricMCPConfig):
    skip_hooks: bool = False
    experimental_hooks: bool = False
    enable_pyrefly: bool = False
    enable_ty: bool = False
    enable_zuban: bool = False
    enable_lsp_optimization: bool = False
    skip_offline_pip_audit: bool = True


class TestSettings(OneiricMCPConfig):
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


class PublishSettings(OneiricMCPConfig):
    publish: str | None = None
    bump: str | None = None
    all: str | None = None
    no_git_tags: bool = False
    skip_version_check: bool = False


class GitSettings(OneiricMCPConfig):
    commit: bool = False
    create_pr: bool = False
    auth_fallback: bool = True
    persist_fallback: bool = False


class FixStrategyMemorySettings(OneiricMCPConfig):
    enabled: bool = True
    db_path: str = ".crackerjack/fix_strategy_memory.db"
    embedding_model: str = "all-MiniLM-L6-v2"
    min_similarity: float = 0.3
    k_neighbors: int = 10
    auto_update_effectiveness: bool = True


class AISettings(OneiricMCPConfig):
    ai_agent: bool = False
    start_mcp_server: bool = False
    max_iterations: int = 20
    autofix: bool = True
    ai_agent_autofix: bool = False
    ai_fix_use_sandbox: bool = False
    ai_fix_sandbox_timeout_s: int = 300

    ai_providers: list[
        t.Literal["claude", "minimax", "llama_server", "qwen", "ollama"]
    ] = [
        "minimax",
        "llama_server",
        "ollama",
    ]

    ai_provider: t.Literal["claude", "minimax", "llama_server", "qwen", "ollama"] = (
        "minimax"
    )

    ollama_base_url: str = "http://localhost: 11434"
    ollama_model: str = "qwen2.5-coder: 7b"
    ollama_timeout: int = 300

    llama_server_url: str = "http://localhost: 8081"
    llama_server_model: str = "qwen3.5"


class SwarmSettings(OneiricMCPConfig):
    swarm: bool = True

    swarm_workers: int = 4

    swarm_mcp_port: int = 8680

    swarm_timeout: int = 300

    swarm_verbose: bool = False


class ExecutionSettings(OneiricMCPConfig):
    interactive: bool = False
    verbose: bool = False
    async_mode: bool = False
    no_config_updates: bool = False


class ProgressSettings(OneiricMCPConfig):
    enabled: bool = False
    track_progress: bool = True


class CleanupSettings(OneiricMCPConfig):
    auto_cleanup: bool = True
    keep_debug_logs: int = 5
    keep_coverage_files: int = 10


class DocumentationSettings(OneiricMCPConfig):
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


class AdvancedSettings(OneiricMCPConfig):
    enabled: bool = False
    license_key: str | None = None
    organization: str | None = None


class ConsoleSettings(OneiricMCPConfig):
    width: int = 70
    verbose: bool = False


class MCPServerSettings(OneiricMCPConfig):
    http_port: int = 8676
    http_host: str = "127.0.0.1"
    http_enabled: bool = False
    websocket_port: int = 8696


class ZubanLSPSettings(OneiricMCPConfig):
    enabled: bool = False
    auto_start: bool = False
    port: int = 8685
    mode: str = "stdio"
    timeout: int = 120


class GlobalLockSettings(OneiricMCPConfig):
    enabled: bool = True
    timeout_seconds: float = 1800.0
    stale_lock_hours: float = 2.0
    lock_directory: Path = Path.home() / ".crackerjack" / "locks"
    session_heartbeat_interval: float = 30.0
    max_retry_attempts: int = 3
    retry_delay_seconds: float = 5.0
    enable_lock_monitoring: bool = True


class EventBridgeSettings(OneiricMCPConfig):
    """Operator toggle for the Oneiric EventBridge publisher.

    The publisher module (``crackerjack.core.eventbridge_publisher``)
    accepts an injected publisher. This settings class controls whether
    a publisher is constructed at app startup and wired into
    ``PhaseCoordinator``. It mirrors ``akosha.config.EventBridgeConfig``
    for cross-repo operator consistency.

    Defaults are conservative (enabled=False, dry_run=True) so existing
    installs see no behavior change until operators opt in.

    Production wiring is opt-in: the publisher is constructed only when
    ``enabled=True``. With ``dry_run=True``, the envelope is logged but
    not transmitted; set ``dry_run=False`` to actually emit events.
    """

    enabled: bool = False
    endpoint: str = ""
    dry_run: bool = True


class AdapterTimeouts(OneiricMCPConfig):
    zuban_lsp_timeout: float = 120.0
    skylos_timeout: int = 900

    refurb_timeout: int = 1800
    zuban_timeout: int = 60
    ty_timeout: int = 120
    pyrefly_timeout: int = 120
    bandit_timeout: int = 300
    semgrep_timeout: int = 300
    pip_audit_timeout: int = 120
    creosote_timeout: int = 300
    complexipy_timeout: int = 900
    pyscn_timeout: int = 60
    gitleaks_timeout: int = 60
    lychee_timeout: int = 300
    pymetrica_timeout: int = 1200
    betterleaks_timeout: int = 180
    check_jsonschema_timeout: int = 180
    linkcheckmd_timeout: int = 300
    cohesion_timeout: int = 300


class ConfigCleanupSettings(OneiricMCPConfig):
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


class GitCleanupSettings(OneiricMCPConfig):
    enabled: bool = True
    smart_approach: bool = True
    filter_branch_threshold: int = 100
    require_clean_working_tree: bool = True


class DocUpdateSettings(OneiricMCPConfig):
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


class IncrementalQASettings(OneiricMCPConfig):
    enabled: bool = True
    full_scan_threshold: int = 50
    base_branch: str = "main"
    force_incremental: bool = False
    force_full: bool = False


class FileChunkingSettings(OneiricMCPConfig):
    enabled: bool = False
    chunk_size: int = 50
    overlap_percentage: int = 10


class FastHooksSettings(OneiricMCPConfig):
    incremental: bool = True
    full_scan_threshold: int = 50
    base_branch: str = "main"
    force_incremental: bool = False
    force_full: bool = False


class SkillsSettings(OneiricMCPConfig):
    enabled: bool = True

    backend: str = "auto"

    db_path: str | None = None

    mcp_server_url: str = "http://localhost: 8678"

    mcp_timeout: int = 5

    min_similarity: float = 0.3

    max_recommendations: int = 5

    enable_phase_aware: bool = True

    phase_weight: float = 0.3


class LearningSettings(OneiricMCPConfig):
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
    adapter_learning_enabled: bool = True
    adapter_learning_backend: str = "auto"

    workflow_learning_db: str = ".crackerjack/workflow_learning.db"
    workflow_min_executions: int = 5


class DharaMCPSettings(OneiricMCPConfig):
    url: str = "http://localhost: 8683"
    timeout_seconds: int = 5
    enabled: bool = True
    token: str | None = None


class MahavishnuSettings(OneiricMCPConfig):
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


class PoolConfiguration(OneiricMCPConfig):
    name: str = "crackerjack-quality-scanners"
    pool_type: str = "mahavishnu"
    min_workers: int = 2
    max_workers: int = 8
    worker_type: str = "terminal-qwen"


class AutoScalingConfiguration(OneiricMCPConfig):
    enabled: bool = True
    scale_up_threshold: int = 10
    scale_down_threshold: int = 300
    max_workers: int = 16


class MemoryConfiguration(OneiricMCPConfig):
    enabled: bool = True
    cache_duration: int = 86400


class PoolRouterConfiguration(OneiricMCPConfig):
    enabled: bool = True
    tool_worker_map: dict[str, str] = {
        "refurb": "heavy-cpu-worker",
        "complexipy": "heavy-cpu-worker",
        "pylint": "heavy-cpu-worker",
        "mypy": "heavy-cpu-worker",
        "bandit": "heavy-cpu-worker",
        "skylos": "fast-worker",
        "ruff": "fast-worker",
        "vulture": "fast-worker",
        "codespell": "fast-worker",
        "check-jsonschema": "fast-worker",
        "semgrep": "security-worker",
        "gitleaks": "security-worker",
    }


class PoolScanningSettings(OneiricMCPConfig):
    enabled: bool = False
    mcp_server_url: str = "http://localhost: 8680"

    pool: PoolConfiguration = PoolConfiguration()

    pooled_tools: list[str] = [
        "refurb",
        "complexipy",
        "skylos",
        "semgrep",
        "gitleaks",
    ]

    local_tools: list[str] = [
        "ruff",
        "vulture",
        "codespell",
        "check-jsonschema",
    ]

    autoscaling: AutoScalingConfiguration = AutoScalingConfiguration()

    memory: MemoryConfiguration = MemoryConfiguration()

    pool_router: PoolRouterConfiguration = PoolRouterConfiguration()


class CrackerjackSettings(OneiricMCPConfig):
    pkg_path: Path | None = None

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
    eventbridge: EventBridgeSettings = EventBridgeSettings()
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
