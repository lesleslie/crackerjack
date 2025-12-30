"""Pydantic models to replace dataclasses in the Crackerjack codebase."""

from typing import Any

from pydantic import BaseModel, Field


class CleaningConfig(BaseModel):
    clean: bool = True
    update_docs: bool = False
    force_update_docs: bool = False
    compress_docs: bool = False
    auto_compress_docs: bool = False
    targets: list[str] = Field(
        default_factory=list
    )  # Changed Path to str for validation

    @classmethod
    def from_settings(cls, settings: Any) -> "CleaningConfig":
        return cls(
            clean=getattr(settings, "clean", True),
            update_docs=getattr(settings, "update_docs", False),
            force_update_docs=getattr(settings, "force_update_docs", False),
            compress_docs=getattr(settings, "compress_docs", False),
            auto_compress_docs=getattr(settings, "auto_compress_docs", False),
            targets=[str(p) for p in getattr(settings, "targets", [])],
        )


class HookConfig(BaseModel):
    skip_hooks: bool = False
    experimental_hooks: bool = False
    enable_pyrefly: bool = False
    enable_ty: bool = False
    enable_lsp_optimization: bool = False

    @classmethod
    def from_settings(cls, settings: Any) -> "HookConfig":
        return cls(
            skip_hooks=getattr(settings, "skip_hooks", False),
            experimental_hooks=getattr(settings, "experimental_hooks", False),
            enable_pyrefly=getattr(settings, "enable_pyrefly", False),
            enable_ty=getattr(settings, "enable_ty", False),
            enable_lsp_optimization=getattr(settings, "enable_lsp_optimization", False),
        )


class TestConfig(BaseModel):
    test: bool = False
    benchmark: bool = False
    benchmark_regression: bool = False
    benchmark_regression_threshold: float = 0.1
    test_workers: int = 0
    test_timeout: int = 0

    @classmethod
    def from_settings(cls, settings: Any) -> "TestConfig":
        return cls(
            test=getattr(settings, "test", False),
            benchmark=getattr(settings, "benchmark", False),
            benchmark_regression=getattr(settings, "benchmark_regression", False),
            benchmark_regression_threshold=getattr(
                settings,
                "benchmark_regression_threshold",
                0.1,
            ),
            test_workers=getattr(settings, "test_workers", 0),
            test_timeout=getattr(settings, "test_timeout", 0),
        )


class PublishConfig(BaseModel):
    publish: str | None = None
    bump: str | None = None
    all: str | None = None
    cleanup_pypi: bool = False
    keep_releases: int = 10
    no_git_tags: bool = False
    skip_version_check: bool = False

    @classmethod
    def from_settings(cls, settings: Any) -> "PublishConfig":
        return cls(
            publish=getattr(settings, "publish", None),
            bump=getattr(settings, "bump", None),
            all=getattr(settings, "all", None),
            cleanup_pypi=getattr(settings, "cleanup_pypi", False),
            keep_releases=getattr(settings, "keep_releases", 10),
            no_git_tags=getattr(settings, "no_git_tags", False),
            skip_version_check=getattr(settings, "skip_version_check", False),
        )


class GitConfig(BaseModel):
    commit: bool = False
    create_pr: bool = False

    @classmethod
    def from_settings(cls, settings: Any) -> "GitConfig":
        return cls(
            commit=getattr(settings, "commit", False),
            create_pr=getattr(settings, "create_pr", False),
        )


class AIConfig(BaseModel):
    ai_agent: bool = False
    autofix: bool = True
    ai_agent_autofix: bool = False
    start_mcp_server: bool = False
    max_iterations: int = 5

    @classmethod
    def from_settings(cls, settings: Any) -> "AIConfig":
        return cls(
            ai_agent=getattr(settings, "ai_agent", False),
            autofix=getattr(settings, "autofix", True),
            ai_agent_autofix=getattr(settings, "ai_agent_autofix", False),
            start_mcp_server=getattr(settings, "start_mcp_server", False),
            max_iterations=getattr(settings, "max_iterations", 5),
        )


class ExecutionConfig(BaseModel):
    interactive: bool = True
    verbose: bool = False
    async_mode: bool = False
    no_config_updates: bool = False
    dry_run: bool = False

    @classmethod
    def from_settings(cls, settings: Any) -> "ExecutionConfig":
        return cls(
            interactive=getattr(settings, "interactive", True),
            verbose=getattr(settings, "verbose", False),
            async_mode=getattr(settings, "async_mode", False),
            no_config_updates=getattr(settings, "no_config_updates", False),
            dry_run=getattr(settings, "dry_run", False),
        )


class ProgressConfig(BaseModel):
    track_progress: bool = False
    resume_from: str | None = None
    progress_file: str | None = None

    @classmethod
    def from_settings(cls, settings: Any) -> "ProgressConfig":
        return cls(
            track_progress=getattr(settings, "enabled", False),
            resume_from=getattr(settings, "resume_from", None),
            progress_file=getattr(settings, "progress_file", None),
        )


class CleanupConfig(BaseModel):
    auto_cleanup: bool = True
    keep_debug_logs: int = 5
    keep_coverage_files: int = 10

    @classmethod
    def from_settings(cls, settings: Any) -> "CleanupConfig":
        return cls(
            auto_cleanup=getattr(settings, "auto_cleanup", True),
            keep_debug_logs=getattr(settings, "keep_debug_logs", 5),
            keep_coverage_files=getattr(settings, "keep_coverage_files", 10),
        )


class AdvancedConfig(BaseModel):
    enabled: bool = False
    license_key: str | None = None
    organization: str | None = None

    @classmethod
    def from_settings(cls, settings: Any) -> "AdvancedConfig":
        return cls(
            enabled=getattr(settings, "enabled", False),
            license_key=getattr(settings, "license_key", None),
            organization=getattr(settings, "organization", None),
        )


class MCPServerConfig(BaseModel):
    http_port: int = 8676
    http_host: str = "127.0.0.1"
    websocket_port: int = 8675
    http_enabled: bool = False

    @classmethod
    def from_settings(cls, settings: Any) -> "MCPServerConfig":
        return cls(
            http_port=getattr(settings, "http_port", 8676),
            http_host=getattr(settings, "http_host", "127.0.0.1"),
            websocket_port=getattr(settings, "websocket_port", 8675),
            http_enabled=getattr(settings, "http_enabled", False),
        )


class ZubanLSPConfig(BaseModel):
    enabled: bool = True
    auto_start: bool = True
    port: int = 8677
    mode: str = "stdio"
    timeout: int = 30

    @classmethod
    def from_settings(cls, settings: Any) -> "ZubanLSPConfig":
        return cls(
            enabled=getattr(settings, "enabled", True),
            auto_start=getattr(settings, "auto_start", True),
            port=getattr(settings, "port", 8677),
            mode=getattr(settings, "mode", "stdio"),
            timeout=getattr(settings, "timeout", 30),
        )


class WorkflowOptions(BaseModel):
    cleaning: CleaningConfig = Field(default_factory=CleaningConfig)
    hooks: HookConfig = Field(default_factory=HookConfig)
    testing: TestConfig = Field(default_factory=TestConfig)
    publishing: PublishConfig = Field(default_factory=PublishConfig)
    git: GitConfig = Field(default_factory=GitConfig)
    ai: AIConfig = Field(default_factory=AIConfig)
    execution: ExecutionConfig = Field(default_factory=ExecutionConfig)
    progress: ProgressConfig = Field(default_factory=ProgressConfig)
    cleanup: CleanupConfig = Field(default_factory=CleanupConfig)
    advanced: AdvancedConfig = Field(default_factory=AdvancedConfig)
    mcp_server: MCPServerConfig = Field(default_factory=MCPServerConfig)
    zuban_lsp: ZubanLSPConfig = Field(default_factory=ZubanLSPConfig)

    # Simple properties that map to nested config values
    @property
    def clean(self) -> bool:
        return self.cleaning.clean

    @clean.setter
    def clean(self, value: bool) -> None:
        self.cleaning.clean = value

    @property
    def test(self) -> bool:
        return self.testing.test

    @test.setter
    def test(self, value: bool) -> None:
        self.testing.test = value

    @property
    def publish(self) -> str | None:
        return self.publishing.publish

    @publish.setter
    def publish(self, value: str | None) -> None:
        self.publishing.publish = value

    @property
    def commit(self) -> bool:
        return self.git.commit

    @commit.setter
    def commit(self, value: bool) -> None:
        self.git.commit = value

    @classmethod
    def from_settings(cls, settings: Any) -> "WorkflowOptions":
        # Simplified implementation for demonstration
        return cls(
            cleaning=CleaningConfig.from_settings(getattr(settings, "cleaning", {})),
            hooks=HookConfig.from_settings(getattr(settings, "hooks", {})),
            testing=TestConfig.from_settings(getattr(settings, "testing", {})),
            publishing=PublishConfig.from_settings(getattr(settings, "publishing", {})),
            git=GitConfig.from_settings(getattr(settings, "git", {})),
            ai=AIConfig.from_settings(getattr(settings, "ai", {})),
            execution=ExecutionConfig.from_settings(getattr(settings, "execution", {})),
            progress=ProgressConfig.from_settings(getattr(settings, "progress", {})),
            cleanup=CleanupConfig.from_settings(getattr(settings, "cleanup", {})),
            advanced=AdvancedConfig.from_settings(getattr(settings, "advanced", {})),
            mcp_server=MCPServerConfig.from_settings(
                getattr(settings, "mcp_server", {})
            ),
            zuban_lsp=ZubanLSPConfig.from_settings(getattr(settings, "zuban_lsp", {})),
        )

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump()


# Results models
class ExecutionResult(BaseModel):
    operation_id: str
    success: bool
    duration_seconds: float
    output: str = ""
    error: str = ""
    exit_code: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)


class ParallelExecutionResult(BaseModel):
    group_name: str
    total_operations: int
    successful_operations: int
    failed_operations: int
    total_duration_seconds: float
    results: list[ExecutionResult]

    @property
    def success_rate(self) -> float:
        return (
            self.successful_operations / self.total_operations
            if self.total_operations > 0
            else 0.0
        )

    @property
    def overall_success(self) -> bool:
        return self.failed_operations == 0
