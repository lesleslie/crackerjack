import typing as t

from .config import (
    AIConfig,
    CleaningConfig,
    EnterpriseConfig,
    ExecutionConfig,
    GitConfig,
    HookConfig,
    ProgressConfig,
    PublishConfig,
    TestConfig,
    WorkflowOptions,
)
from .protocols import OptionsProtocol


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
                update_precommit=getattr(options, "update_precommit", False),
                experimental_hooks=getattr(options, "experimental_hooks", False),
                enable_pyrefly=getattr(options, "enable_pyrefly", False),
                enable_ty=getattr(options, "enable_ty", False),
            ),
            testing=TestConfig(
                test=getattr(options, "test", False),
                benchmark=getattr(options, "benchmark", False),
                test_workers=getattr(options, "test_workers", 0),
                test_timeout=getattr(options, "test_timeout", 0),
            ),
            publishing=PublishConfig(
                publish=getattr(options, "publish", None),
                bump=getattr(options, "bump", None),
                all=getattr(options, "all", None),
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
                max_iterations=getattr(options, "max_iterations", 10),
            ),
            execution=ExecutionConfig(
                interactive=getattr(options, "interactive", False),
                verbose=getattr(options, "verbose", False),
                async_mode=getattr(options, "async_mode", False),
                no_config_updates=getattr(options, "no_config_updates", False),
            ),
            progress=ProgressConfig(
                enabled=getattr(options, "track_progress", False),
            ),
            enterprise=EnterpriseConfig(
                enabled=getattr(options, "enterprise_batch", None) is not None,
                license_key=getattr(options, "license_key", None),
                organization=getattr(options, "organization", None),
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
    def update_precommit(self) -> bool:
        return self._options.hooks.update_precommit

    @property
    def async_mode(self) -> bool:
        return self._options.execution.async_mode

    @property
    def track_progress(self) -> bool:
        return self._options.progress.enabled

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
    def no_git_tags(self) -> bool:
        return self._options.publishing.no_git_tags

    @property
    def skip_version_check(self) -> bool:
        return self._options.publishing.skip_version_check

    @property
    def enterprise_batch(self) -> str | None:
        return None

    @property
    def monitor_dashboard(self) -> str | None:
        return None
