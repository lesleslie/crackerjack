import typing as t

from .config import (
    AdvancedConfig,
    AIConfig,
    CleaningConfig,
    CleanupConfig,
    ExecutionConfig,
    GitConfig,
    HookConfig,
    MCPServerConfig,
    ProgressConfig,
    PublishConfig,
    TestConfig,
    WorkflowOptions,
    ZubanLSPConfig,
)
from .protocols import OptionsProtocol


def _determine_max_iterations(options: OptionsProtocol) -> int:
    """Determine max_iterations using effective_max_iterations if available, otherwise fallback logic.

    Priority:
    1. Use effective_max_iterations property if available (handles quick/thorough flags)
    2. Explicit max_iterations value
    3. Default: 5 iterations
    """
    # Use effective_max_iterations property if available (Options class has this)
    if hasattr(options, "effective_max_iterations"):
        return getattr(options, "effective_max_iterations")  # type: ignore[no-any-return]

    # Fallback for other OptionsProtocol implementations
    if hasattr(options, "max_iterations") and getattr(
        options, "max_iterations", None
    ) not in (0, None):
        return getattr(options, "max_iterations")  # type: ignore[no-any-return]

    # Default to 5 iterations
    return 5


class OptionsAdapter:
    @staticmethod
    def from_options_protocol(options: OptionsProtocol) -> WorkflowOptions:
        return WorkflowOptions(
            cleaning=CleaningConfig(
                clean=getattr(options, "clean", True),
                update_docs=getattr(options, "update_docs", False),
                force_update_docs=getattr(options, "force_update_docs", False),
                compress_docs=getattr(options, "compress_docs", False),
                auto_compress_docs=getattr(options, "auto_compress_docs", False),
            ),
            hooks=HookConfig(
                skip_hooks=getattr(options, "skip_hooks", False),
                experimental_hooks=getattr(options, "experimental_hooks", False),
                enable_pyrefly=getattr(options, "enable_pyrefly", False),
                enable_ty=getattr(options, "enable_ty", False),
                enable_lsp_optimization=getattr(options, "enable_lsp_hooks", False),
            ),
            testing=TestConfig(
                test=getattr(options, "test", False),
                benchmark=getattr(options, "benchmark", False),
                benchmark_regression=getattr(options, "benchmark_regression", False),
                benchmark_regression_threshold=getattr(
                    options,
                    "benchmark_regression_threshold",
                    0.1,
                ),
                test_workers=getattr(options, "test_workers", 0),
                test_timeout=getattr(options, "test_timeout", 0),
            ),
            publishing=PublishConfig(
                publish=getattr(options, "publish", None),
                bump=getattr(options, "bump", None),
                all=getattr(options, "all", None),
                cleanup_pypi=getattr(options, "cleanup_pypi", False),
                keep_releases=getattr(options, "keep_releases", 10),
                no_git_tags=getattr(options, "no_git_tags", False),
                skip_version_check=getattr(options, "skip_version_check", False),
            ),
            git=GitConfig(
                commit=getattr(options, "commit", False),
                create_pr=getattr(options, "create_pr", False),
            ),
            ai=AIConfig(
                ai_agent=getattr(options, "ai_agent", False),
                autofix=getattr(options, "autofix", True),
                ai_agent_autofix=getattr(options, "ai_agent_autofix", False),
                start_mcp_server=getattr(options, "start_mcp_server", False),
                max_iterations=_determine_max_iterations(options),
            ),
            execution=ExecutionConfig(
                interactive=getattr(options, "interactive", False),
                verbose=getattr(options, "verbose", False),
                async_mode=getattr(options, "async_mode", False),
                no_config_updates=getattr(options, "no_config_updates", False),
            ),
            progress=ProgressConfig(
                track_progress=getattr(options, "track_progress", False),
                resume_from=getattr(options, "resume_from", None),
                progress_file=getattr(options, "progress_file", None),
            ),
            cleanup=CleanupConfig(
                auto_cleanup=getattr(options, "auto_cleanup", True),
                keep_debug_logs=getattr(options, "keep_debug_logs", 5),
                keep_coverage_files=getattr(options, "keep_coverage_files", 10),
            ),
            advanced=AdvancedConfig(
                enabled=getattr(options, "advanced_batch", None) is not None,
                license_key=getattr(options, "license_key", None),
                organization=getattr(options, "organization", None),
            ),
            mcp_server=MCPServerConfig(
                http_port=getattr(options, "http_port", 8676),
                http_host=getattr(options, "http_host", "127.0.0.1"),
                websocket_port=getattr(options, "websocket_port", 8675),
                http_enabled=getattr(options, "http_enabled", False),
            ),
            zuban_lsp=ZubanLSPConfig(
                enabled=not getattr(options, "no_zuban_lsp", False),
                auto_start=True,
                port=getattr(options, "zuban_lsp_port", 8677),
                mode=getattr(options, "zuban_lsp_mode", "stdio"),
                timeout=getattr(options, "zuban_lsp_timeout", 30),
            ),
        )

    @staticmethod
    def to_options_protocol(
        workflow_options: WorkflowOptions,
    ) -> "LegacyOptionsWrapper":
        return LegacyOptionsWrapper(workflow_options)


class LegacyOptionsWrapper:
    def __init__(self, workflow_options: WorkflowOptions) -> None:
        self._options = workflow_options

    @property
    def commit(self) -> bool:
        return self._options.git.commit

    @property
    def interactive(self) -> bool:
        return self._options.execution.interactive

    @property
    def no_config_updates(self) -> bool:
        return self._options.execution.no_config_updates

    @property
    def verbose(self) -> bool:
        return self._options.execution.verbose

    @property
    def update_docs(self) -> bool:
        return self._options.cleaning.update_docs

    @property
    def force_update_docs(self) -> bool:
        return self._options.cleaning.force_update_docs

    @property
    def compress_docs(self) -> bool:
        return self._options.cleaning.compress_docs

    @property
    def auto_compress_docs(self) -> bool:
        return self._options.cleaning.auto_compress_docs

    @property
    def clean(self) -> bool:
        return self._options.cleaning.clean

    @property
    def test(self) -> bool:
        return self._options.testing.test

    @property
    def benchmark(self) -> bool:
        return self._options.testing.benchmark

    @property
    def test_workers(self) -> int:
        return self._options.testing.test_workers

    @property
    def test_timeout(self) -> int:
        return self._options.testing.test_timeout

    @property
    def benchmark_regression(self) -> bool:
        return self._options.testing.benchmark_regression

    @property
    def benchmark_regression_threshold(self) -> float:
        return self._options.testing.benchmark_regression_threshold

    @property
    def publish(self) -> t.Any | None:
        return self._options.publishing.publish

    @property
    def bump(self) -> t.Any | None:
        return self._options.publishing.bump

    @property
    def all(self) -> t.Any | None:
        return self._options.publishing.all

    @property
    def ai_agent(self) -> bool:
        return self._options.ai.ai_agent

    @property
    def autofix(self) -> bool:
        return self._options.ai.autofix

    @property
    def ai_agent_autofix(self) -> bool:
        return self._options.ai.ai_agent_autofix

    @property
    def start_mcp_server(self) -> bool:
        return self._options.ai.start_mcp_server

    @property
    def max_iterations(self) -> int:
        return self._options.ai.max_iterations

    @property
    def create_pr(self) -> bool:
        return self._options.git.create_pr

    @property
    def skip_hooks(self) -> bool:
        return self._options.hooks.skip_hooks

    @property
    def async_mode(self) -> bool:
        return self._options.execution.async_mode

    @property
    def track_progress(self) -> bool:
        return self._options.progress.track_progress

    @property
    def resume_from(self) -> str | None:
        return self._options.progress.resume_from

    @property
    def progress_file(self) -> str | None:
        return self._options.progress.progress_file

    @property
    def experimental_hooks(self) -> bool:
        return self._options.hooks.experimental_hooks

    @property
    def enable_pyrefly(self) -> bool:
        return self._options.hooks.enable_pyrefly

    @property
    def enable_ty(self) -> bool:
        return self._options.hooks.enable_ty

    @property
    def enable_lsp_hooks(self) -> bool:
        return self._options.hooks.enable_lsp_optimization

    @property
    def no_git_tags(self) -> bool:
        return self._options.publishing.no_git_tags

    @property
    def skip_version_check(self) -> bool:
        return self._options.publishing.skip_version_check

    @property
    def cleanup_pypi(self) -> bool:
        return self._options.publishing.cleanup_pypi

    @property
    def keep_releases(self) -> int:
        return self._options.publishing.keep_releases

    @property
    def advanced_batch(self) -> str | None:
        return None

    @property
    def monitor_dashboard(self) -> str | None:
        return None
