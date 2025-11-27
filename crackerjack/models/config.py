from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from acb.depends import depends

from crackerjack.config.settings import (
    AdvancedSettings,
    AISettings,
    CleaningSettings,
    CrackerjackSettings,
    ExecutionSettings,
    GitSettings,
    HookSettings,
    MCPServerSettings,
    ProgressSettings,
    PublishSettings,
    TestSettings,
    ZubanLSPSettings,
)
from crackerjack.config.settings import (
    CleanupSettings as CleanupSettingsModel,
)


@dataclass
class CleaningConfig:
    clean: bool = True
    update_docs: bool = False
    force_update_docs: bool = False
    compress_docs: bool = False
    auto_compress_docs: bool = False
    targets: list[Path] = field(default_factory=list)

    @classmethod
    def from_settings(cls, settings: CleaningSettings) -> CleaningConfig:
        return cls(
            clean=settings.clean,
            update_docs=settings.update_docs,
            force_update_docs=settings.force_update_docs,
            compress_docs=settings.compress_docs,
            auto_compress_docs=settings.auto_compress_docs,
            targets=settings.targets if hasattr(settings, "targets") else [],
        )


@dataclass
class HookConfig:
    skip_hooks: bool = False
    update_precommit: bool = False
    experimental_hooks: bool = False
    enable_pyrefly: bool = False
    enable_ty: bool = False
    enable_lsp_optimization: bool = False

    @classmethod
    def from_settings(cls, settings: HookSettings) -> HookConfig:
        return cls(
            skip_hooks=settings.skip_hooks,
            update_precommit=settings.update_precommit,
            experimental_hooks=settings.experimental_hooks,
            enable_pyrefly=settings.enable_pyrefly,
            enable_ty=settings.enable_ty,
            enable_lsp_optimization=settings.enable_lsp_optimization,
        )


@dataclass
class TestConfig:
    test: bool = False
    benchmark: bool = False
    benchmark_regression: bool = False
    benchmark_regression_threshold: float = 0.1
    test_workers: int = 0
    test_timeout: int = 0

    @property
    def workers(self) -> int:
        return self.test_workers

    @workers.setter
    def workers(self, value: int) -> None:
        self.test_workers = value

    @property
    def timeout(self) -> int:
        return self.test_timeout

    @timeout.setter
    def timeout(self, value: int) -> None:
        self.test_timeout = value

    @classmethod
    def from_settings(cls, settings: TestSettings) -> TestConfig:
        return cls(
            test=settings.test,
            benchmark=settings.benchmark,
            benchmark_regression=getattr(settings, "benchmark_regression", False),
            benchmark_regression_threshold=getattr(
                settings,
                "benchmark_regression_threshold",
                0.1,
            ),
            test_workers=settings.test_workers,
            test_timeout=settings.test_timeout,
        )


@dataclass
class PublishConfig:
    publish: str | None = None
    bump: str | None = None
    all: str | None = None
    cleanup_pypi: bool = False
    keep_releases: int = 10
    no_git_tags: bool = False
    skip_version_check: bool = False

    @classmethod
    def from_settings(cls, settings: PublishSettings) -> PublishConfig:
        return cls(
            publish=settings.publish,
            bump=settings.bump,
            all=settings.all,
            cleanup_pypi=getattr(settings, "cleanup_pypi", False),
            keep_releases=getattr(settings, "keep_releases", 10),
            no_git_tags=settings.no_git_tags,
            skip_version_check=settings.skip_version_check,
        )


@dataclass
class GitConfig:
    commit: bool = False
    create_pr: bool = False

    @classmethod
    def from_settings(cls, settings: GitSettings) -> GitConfig:
        return cls(commit=settings.commit, create_pr=settings.create_pr)


@dataclass
class AIConfig:
    ai_agent: bool = False
    autofix: bool = True
    ai_agent_autofix: bool = False
    start_mcp_server: bool = False
    max_iterations: int = 5

    @classmethod
    def from_settings(cls, settings: AISettings) -> AIConfig:
        return cls(
            ai_agent=settings.ai_agent,
            autofix=settings.autofix,
            ai_agent_autofix=settings.ai_agent_autofix,
            start_mcp_server=settings.start_mcp_server,
            max_iterations=settings.max_iterations,
        )


@dataclass
class ExecutionConfig:
    interactive: bool = True
    verbose: bool = False
    async_mode: bool = False
    no_config_updates: bool = False
    dry_run: bool = False

    @classmethod
    def from_settings(cls, settings: ExecutionSettings) -> ExecutionConfig:
        return cls(
            interactive=settings.interactive,
            verbose=settings.verbose,
            async_mode=settings.async_mode,
            no_config_updates=settings.no_config_updates,
            dry_run=getattr(settings, "dry_run", False),
        )


@dataclass
class ProgressConfig:
    track_progress: bool = False
    resume_from: str | None = None
    progress_file: str | None = None

    @classmethod
    def from_settings(cls, settings: ProgressSettings) -> ProgressConfig:
        return cls(
            track_progress=settings.enabled,
            resume_from=getattr(settings, "resume_from", None),
            progress_file=getattr(settings, "progress_file", None),
        )


@dataclass
class CleanupConfig:
    auto_cleanup: bool = True
    keep_debug_logs: int = 5
    keep_coverage_files: int = 10

    @classmethod
    def from_settings(
        cls,
        settings: CleanupSettingsModel,
    ) -> CleanupConfig:
        return cls(
            auto_cleanup=settings.auto_cleanup,
            keep_debug_logs=settings.keep_debug_logs,
            keep_coverage_files=settings.keep_coverage_files,
        )


@dataclass
class AdvancedConfig:
    enabled: bool = False
    license_key: str | None = None
    organization: str | None = None

    @classmethod
    def from_settings(cls, settings: AdvancedSettings) -> AdvancedConfig:
        return cls(
            enabled=settings.enabled,
            license_key=settings.license_key,
            organization=settings.organization,
        )


@dataclass
class MCPServerConfig:
    http_port: int = 8676
    http_host: str = "127.0.0.1"
    websocket_port: int = 8675
    http_enabled: bool = False

    @classmethod
    def from_settings(cls, settings: MCPServerSettings) -> MCPServerConfig:
        return cls(
            http_port=settings.http_port,
            http_host=settings.http_host,
            websocket_port=settings.websocket_port,
            http_enabled=settings.http_enabled,
        )


@dataclass
class ZubanLSPConfig:
    enabled: bool = True
    auto_start: bool = True
    port: int = 8677
    mode: str = "stdio"
    timeout: int = 30

    @classmethod
    def from_settings(cls, settings: ZubanLSPSettings) -> ZubanLSPConfig:
        return cls(
            enabled=settings.enabled,
            auto_start=settings.auto_start,
            port=settings.port,
            mode=settings.mode,
            timeout=settings.timeout,
        )


@dataclass(init=False)
class WorkflowOptions:
    cleaning: CleaningConfig
    hooks: HookConfig
    testing: TestConfig
    publishing: PublishConfig
    git: GitConfig
    ai: AIConfig
    execution: ExecutionConfig
    progress: ProgressConfig
    cleanup: CleanupConfig
    advanced: AdvancedConfig
    mcp_server: MCPServerConfig
    zuban_lsp: ZubanLSPConfig

    _DEFAULT_OVERRIDES: dict[str, Any] = field(
        default_factory=lambda: {
            "clean": False,
            "test": False,
            "publish": None,
            "bump": None,
            "commit": False,
            "create_pr": False,
            "interactive": True,
            "dry_run": False,
        },
        init=False,
    )

    def _initialize_config_attributes(
        self,
        cleaning: CleaningConfig | None,
        hooks: HookConfig | None,
        testing: TestConfig | None,
        publishing: PublishConfig | None,
        git: GitConfig | None,
        ai: AIConfig | None,
        execution: ExecutionConfig | None,
        progress: ProgressConfig | None,
        cleanup: CleanupConfig | None,
        advanced: AdvancedConfig | None,
        mcp_server: MCPServerConfig | None,
        zuban_lsp: ZubanLSPConfig | None,
    ) -> None:
        """Initialize all configuration attributes."""
        self.cleaning = cleaning or CleaningConfig()
        self.hooks = hooks or HookConfig()
        self.testing = testing or TestConfig()
        self.publishing = publishing or PublishConfig()
        self.git = git or GitConfig()
        self.ai = ai or AIConfig()
        self.execution = execution or ExecutionConfig()
        self.progress = progress or ProgressConfig()
        self.cleanup = cleanup or CleanupConfig()
        self.advanced = advanced or AdvancedConfig()
        self.mcp_server = mcp_server or MCPServerConfig()
        self.zuban_lsp = zuban_lsp or ZubanLSPConfig()

    def _set_default_overrides(self, kwargs: dict[str, Any]) -> None:
        """Set default overrides for specific attributes."""
        self._DEFAULT_OVERRIDES = {
            "clean": False,
            "test": False,
            "publish": None,
            "bump": None,
            "commit": False,
            "create_pr": False,
            "interactive": True,
            "dry_run": False,
        }

        for attr, value in self._DEFAULT_OVERRIDES.items():
            if attr not in kwargs:
                setattr(self, attr, value)

    def _set_kwargs_attributes(self, kwargs: dict[str, Any]) -> None:
        """Set attributes based on provided kwargs."""
        for attr, value in kwargs.items():
            if hasattr(self.__class__, attr):
                setattr(self, attr, value)
            elif hasattr(self, attr):
                setattr(self, attr, value)

    def __init__(
        self,
        *,
        cleaning: CleaningConfig | None = None,
        hooks: HookConfig | None = None,
        testing: TestConfig | None = None,
        publishing: PublishConfig | None = None,
        git: GitConfig | None = None,
        ai: AIConfig | None = None,
        execution: ExecutionConfig | None = None,
        progress: ProgressConfig | None = None,
        cleanup: CleanupConfig | None = None,
        advanced: AdvancedConfig | None = None,
        mcp_server: MCPServerConfig | None = None,
        zuban_lsp: ZubanLSPConfig | None = None,
        **kwargs: Any,
    ) -> None:
        self._initialize_config_attributes(
            cleaning,
            hooks,
            testing,
            publishing,
            git,
            ai,
            execution,
            progress,
            cleanup,
            advanced,
            mcp_server,
            zuban_lsp,
        )
        self._set_default_overrides(kwargs)
        self._set_kwargs_attributes(kwargs)

    # Convenience property mappings
    @property
    def clean(self) -> bool:
        return self.cleaning.clean

    @clean.setter
    def clean(self, value: bool) -> None:
        self.cleaning.clean = value

    @property
    def update_docs(self) -> bool:
        return self.cleaning.update_docs

    @update_docs.setter
    def update_docs(self, value: bool) -> None:
        self.cleaning.update_docs = value

    @property
    def test(self) -> bool:
        return self.testing.test

    @test.setter
    def test(self, value: bool) -> None:
        self.testing.test = value

    @property
    def benchmark(self) -> bool:
        return self.testing.benchmark

    @benchmark.setter
    def benchmark(self, value: bool) -> None:
        self.testing.benchmark = value

    @property
    def benchmark_regression(self) -> bool:
        return self.testing.benchmark_regression

    @benchmark_regression.setter
    def benchmark_regression(self, value: bool) -> None:
        self.testing.benchmark_regression = value

    @property
    def benchmark_regression_threshold(self) -> float:
        return self.testing.benchmark_regression_threshold

    @benchmark_regression_threshold.setter
    def benchmark_regression_threshold(self, value: float) -> None:
        self.testing.benchmark_regression_threshold = value

    @property
    def test_workers(self) -> int:
        return self.testing.test_workers

    @test_workers.setter
    def test_workers(self, value: int) -> None:
        self.testing.test_workers = value

    @property
    def test_timeout(self) -> int:
        return self.testing.test_timeout

    @test_timeout.setter
    def test_timeout(self, value: int) -> None:
        self.testing.test_timeout = value

    @property
    def publish(self) -> str | None:
        return self.publishing.publish

    @publish.setter
    def publish(self, value: str | None) -> None:
        self.publishing.publish = value

    @property
    def bump(self) -> str | None:
        return self.publishing.bump

    @bump.setter
    def bump(self, value: str | None) -> None:
        self.publishing.bump = value

    @property
    def all(self) -> str | None:
        return self.publishing.all

    @all.setter
    def all(self, value: str | None) -> None:
        self.publishing.all = value

    @property
    def commit(self) -> bool:
        return self.git.commit

    @commit.setter
    def commit(self, value: bool) -> None:
        self.git.commit = value

    @property
    def create_pr(self) -> bool:
        return self.git.create_pr

    @create_pr.setter
    def create_pr(self, value: bool) -> None:
        self.git.create_pr = value

    @property
    def ai_agent(self) -> bool:
        return self.ai.ai_agent

    @ai_agent.setter
    def ai_agent(self, value: bool) -> None:
        self.ai.ai_agent = value

    @property
    def autofix(self) -> bool:
        return self.ai.autofix

    @autofix.setter
    def autofix(self, value: bool) -> None:
        self.ai.autofix = value

    @property
    def ai_agent_autofix(self) -> bool:
        return self.ai.ai_agent_autofix

    @ai_agent_autofix.setter
    def ai_agent_autofix(self, value: bool) -> None:
        self.ai.ai_agent_autofix = value

    @property
    def start_mcp_server(self) -> bool:
        return self.ai.start_mcp_server

    @start_mcp_server.setter
    def start_mcp_server(self, value: bool) -> None:
        self.ai.start_mcp_server = value

    @property
    def max_iterations(self) -> int:
        return self.ai.max_iterations

    @max_iterations.setter
    def max_iterations(self, value: int) -> None:
        self.ai.max_iterations = value

    @property
    def interactive(self) -> bool:
        return self.execution.interactive

    @interactive.setter
    def interactive(self, value: bool) -> None:
        self.execution.interactive = value

    @property
    def verbose(self) -> bool:
        return self.execution.verbose

    @verbose.setter
    def verbose(self, value: bool) -> None:
        self.execution.verbose = value

    @property
    def async_mode(self) -> bool:
        return self.execution.async_mode

    @async_mode.setter
    def async_mode(self, value: bool) -> None:
        self.execution.async_mode = value

    @property
    def no_config_updates(self) -> bool:
        return self.execution.no_config_updates

    @no_config_updates.setter
    def no_config_updates(self, value: bool) -> None:
        self.execution.no_config_updates = value

    @property
    def dry_run(self) -> bool:
        return self.execution.dry_run

    @dry_run.setter
    def dry_run(self, value: bool) -> None:
        self.execution.dry_run = value

    @property
    def skip_hooks(self) -> bool:
        return self.hooks.skip_hooks

    @skip_hooks.setter
    def skip_hooks(self, value: bool) -> None:
        self.hooks.skip_hooks = value

    @property
    def update_precommit(self) -> bool:
        return self.hooks.update_precommit

    @update_precommit.setter
    def update_precommit(self, value: bool) -> None:
        self.hooks.update_precommit = value

    @property
    def experimental_hooks(self) -> bool:
        return self.hooks.experimental_hooks

    @experimental_hooks.setter
    def experimental_hooks(self, value: bool) -> None:
        self.hooks.experimental_hooks = value

    @property
    def enable_pyrefly(self) -> bool:
        return self.hooks.enable_pyrefly

    @enable_pyrefly.setter
    def enable_pyrefly(self, value: bool) -> None:
        self.hooks.enable_pyrefly = value

    @property
    def enable_ty(self) -> bool:
        return self.hooks.enable_ty

    @enable_ty.setter
    def enable_ty(self, value: bool) -> None:
        self.hooks.enable_ty = value

    @property
    def enable_lsp_optimization(self) -> bool:
        return self.hooks.enable_lsp_optimization

    @enable_lsp_optimization.setter
    def enable_lsp_optimization(self, value: bool) -> None:
        self.hooks.enable_lsp_optimization = value

    @property
    def track_progress(self) -> bool:
        return self.progress.track_progress

    @track_progress.setter
    def track_progress(self, value: bool) -> None:
        self.progress.track_progress = value

    @property
    def resume_from(self) -> str | None:
        return self.progress.resume_from

    @resume_from.setter
    def resume_from(self, value: str | None) -> None:
        self.progress.resume_from = value

    @property
    def progress_file(self) -> str | None:
        return self.progress.progress_file

    @progress_file.setter
    def progress_file(self, value: str | None) -> None:
        self.progress.progress_file = value

    @classmethod
    def from_settings(cls, settings: CrackerjackSettings) -> WorkflowOptions:
        return cls(
            cleaning=CleaningConfig.from_settings(settings.cleaning),
            hooks=HookConfig.from_settings(settings.hooks),
            testing=TestConfig.from_settings(settings.testing),
            publishing=PublishConfig.from_settings(settings.publishing),
            git=GitConfig.from_settings(settings.git),
            ai=AIConfig.from_settings(settings.ai),
            execution=ExecutionConfig.from_settings(settings.execution),
            progress=ProgressConfig.from_settings(settings.progress),
            cleanup=CleanupConfig.from_settings(settings.cleanup),
            advanced=AdvancedConfig.from_settings(settings.advanced),
            mcp_server=MCPServerConfig.from_settings(settings.mcp_server),
            zuban_lsp=ZubanLSPConfig.from_settings(settings.zuban_lsp),
        )

    def to_settings(self) -> CrackerjackSettings:
        return CrackerjackSettings(
            cleaning=self.cleaning.__dict__,
            hooks=self.hooks.__dict__,
            testing=self.testing.__dict__,
            publishing=self.publishing.__dict__,
            git=self.git.__dict__,
            ai=self.ai.__dict__,
            execution=self.execution.__dict__,
            progress={"enabled": self.progress.track_progress},
            cleanup=self.cleanup.__dict__,
            advanced=self.advanced.__dict__,
            mcp_server=self.mcp_server.__dict__,
            zuban_lsp=self.zuban_lsp.__dict__,
        )

    @classmethod
    def from_args(cls, args: Any) -> WorkflowOptions:
        simple_fields = [
            "clean",
            "test",
            "publish",
            "bump",
            "commit",
            "create_pr",
            "dry_run",
        ]
        kwargs = {
            field: getattr(args, field)
            for field in simple_fields
            if hasattr(args, field)
        }
        return cls(**kwargs)

    def to_dict(self) -> dict[str, Any]:
        return {
            "cleaning": self.cleaning.__dict__,
            "hooks": self.hooks.__dict__,
            "testing": self.testing.__dict__,
            "publishing": self.publishing.__dict__,
            "git": self.git.__dict__,
            "ai": self.ai.__dict__,
            "execution": self.execution.__dict__,
            "progress": self.progress.__dict__,
            "cleanup": self.cleanup.__dict__,
            "advanced": self.advanced.__dict__,
            "mcp_server": self.mcp_server.__dict__,
            "zuban_lsp": self.zuban_lsp.__dict__,
        }


from typing import cast


def get_workflow_options() -> CrackerjackSettings:
    return cast(CrackerjackSettings, depends.get_sync(CrackerjackSettings))


__all__ = [
    "AIConfig",
    "CleaningConfig",
    "CleanupConfig",
    "AdvancedConfig",
    "ExecutionConfig",
    "GitConfig",
    "HookConfig",
    "MCPServerConfig",
    "PublishConfig",
    "ProgressConfig",
    "TestConfig",
    "WorkflowOptions",
    "ZubanLSPConfig",
    "get_workflow_options",
]
