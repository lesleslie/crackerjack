import typing as t
from dataclasses import dataclass, field


@dataclass
class CleaningConfig:
    clean: bool = True
    update_docs: bool = False
    force_update_docs: bool = False
    compress_docs: bool = False
    auto_compress_docs: bool = False


@dataclass
class HookConfig:
    skip_hooks: bool = False
    update_precommit: bool = False
    experimental_hooks: bool = False
    enable_pyrefly: bool = False
    enable_ty: bool = False


@dataclass
class TestConfig:
    test: bool = False
    benchmark: bool = False
    test_workers: int = 0
    test_timeout: int = 0


@dataclass
class PublishConfig:
    publish: t.Any | None = None
    bump: t.Any | None = None
    all: t.Any | None = None
    no_git_tags: bool = False
    skip_version_check: bool = False


@dataclass
class GitConfig:
    commit: bool = False
    create_pr: bool = False


@dataclass
class AIConfig:
    ai_agent: bool = False
    start_mcp_server: bool = False
    max_iterations: int = 10
    autofix: bool = True
    ai_agent_autofix: bool = False


@dataclass
class ExecutionConfig:
    interactive: bool = False
    verbose: bool = False
    async_mode: bool = False
    no_config_updates: bool = False


@dataclass
class ProgressConfig:
    enabled: bool = False


@dataclass
class CleanupConfig:
    auto_cleanup: bool = True
    keep_debug_logs: int = 5
    keep_coverage_files: int = 10


@dataclass
class EnterpriseConfig:
    enabled: bool = False
    license_key: str | None = None
    organization: str | None = None


@dataclass
class MCPServerConfig:
    http_port: int = 8676
    http_host: str = "127.0.0.1"
    websocket_port: int = 8675
    http_enabled: bool = False


@dataclass
class WorkflowOptions:
    cleaning: CleaningConfig = field(default_factory=CleaningConfig)
    hooks: HookConfig = field(default_factory=HookConfig)
    testing: TestConfig = field(default_factory=TestConfig)
    publishing: PublishConfig = field(default_factory=PublishConfig)
    git: GitConfig = field(default_factory=GitConfig)
    ai: AIConfig = field(default_factory=AIConfig)
    execution: ExecutionConfig = field(default_factory=ExecutionConfig)
    progress: ProgressConfig = field(default_factory=ProgressConfig)
    cleanup: CleanupConfig = field(default_factory=CleanupConfig)
    enterprise: EnterpriseConfig = field(default_factory=EnterpriseConfig)
    mcp_server: MCPServerConfig = field(default_factory=MCPServerConfig)
