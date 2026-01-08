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
    if hasattr(options, "effective_max_iterations"):
        return getattr(options, "effective_max_iterations")  # type: ignore[no-any-return]

    if hasattr(options, "max_iterations") and getattr(
        options, "max_iterations", None
    ) not in (0, None):
        return getattr(options, "max_iterations")  # type: ignore[no-any-return]

    return 5


class OptionsAdapter:
    @staticmethod
    def from_options_protocol(options: OptionsProtocol) -> WorkflowOptions:
        return WorkflowOptions(
            cleaning=CleaningConfig(
                clean=getattr(
                    options,
                    "clean",
                    getattr(options, "strip_code", True),
                ),
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
                test=getattr(
                    options,
                    "test",
                    getattr(options, "run_tests", False),
                ),
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
                ai_agent=getattr(
                    options,
                    "ai_agent",
                    getattr(options, "ai_fix", False),
                ),
                autofix=getattr(
                    options,
                    "autofix",
                    getattr(options, "ai_fix", True),
                ),
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
    ) -> WorkflowOptions:
        return workflow_options
