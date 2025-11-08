import typing as t
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from acb.console import Console

from crackerjack.config.hooks import HookStrategy
from crackerjack.models.protocols import OptionsProtocol


class ExecutionStrategy(str, Enum):
    BATCH = "batch"
    INDIVIDUAL = "individual"
    ADAPTIVE = "adaptive"
    SELECTIVE = "selective"


class ProgressLevel(str, Enum):
    BASIC = "basic"
    DETAILED = "detailed"
    GRANULAR = "granular"
    STREAMING = "streaming"


class StreamingMode(str, Enum):
    WEBSOCKET = "websocket"
    FILE = "file"
    HYBRID = "hybrid"


class AICoordinationMode(str, Enum):
    SINGLE_AGENT = "single-agent"
    MULTI_AGENT = "multi-agent"
    COORDINATOR = "coordinator"


class AIIntelligence(str, Enum):
    BASIC = "basic"
    ADAPTIVE = "adaptive"
    LEARNING = "learning"


@dataclass
class OrchestrationConfig:
    execution_strategy: ExecutionStrategy = ExecutionStrategy.BATCH
    progress_level: ProgressLevel = ProgressLevel.BASIC
    streaming_mode: StreamingMode = StreamingMode.WEBSOCKET
    ai_coordination_mode: AICoordinationMode = AICoordinationMode.SINGLE_AGENT
    ai_intelligence: AIIntelligence = AIIntelligence.BASIC

    correlation_tracking: bool = True
    failure_analysis: bool = True
    intelligent_retry: bool = True

    max_parallel_hooks: int = 3
    max_parallel_tests: int = 4
    timeout_multiplier: float = 1.0

    debug_level: str = "standard"
    log_individual_outputs: bool = False
    preserve_temp_files: bool = False

    def to_dict(self) -> dict[str, t.Any]:
        return {
            "execution_strategy": self.execution_strategy.value,
            "progress_level": self.progress_level.value,
            "streaming_mode": self.streaming_mode.value,
            "ai_coordination_mode": self.ai_coordination_mode.value,
            "ai_intelligence": self.ai_intelligence.value,
            "correlation_tracking": self.correlation_tracking,
            "failure_analysis": self.failure_analysis,
            "intelligent_retry": self.intelligent_retry,
            "max_parallel_hooks": self.max_parallel_hooks,
            "max_parallel_tests": self.max_parallel_tests,
            "timeout_multiplier": self.timeout_multiplier,
            "debug_level": self.debug_level,
            "log_individual_outputs": self.log_individual_outputs,
            "preserve_temp_files": self.preserve_temp_files,
        }


class ExecutionContext:
    def __init__(
        self,
        pkg_path: Path,
        options: OptionsProtocol,
        previous_failures: list[str] | None = None,
        changed_files: list[Path] | None = None,
        iteration_count: int = 1,
    ) -> None:
        self.pkg_path = pkg_path
        self.options = options
        self.previous_failures = previous_failures or []
        self.changed_files = changed_files or []
        self.iteration_count = iteration_count

        self.total_python_files = len(list[t.Any](pkg_path.rglob(" * .py")))
        self.total_test_files = len(list[t.Any](pkg_path.glob("tests / test_ * .py")))
        self.has_complex_setup = self._detect_complex_setup()
        self.estimated_hook_duration = self._estimate_hook_duration()

    def _detect_complex_setup(self) -> bool:
        complex_indicators = [
            (self.pkg_path / "pyproject.toml").exists(),
            (self.pkg_path / "setup.py").exists(),
            (self.pkg_path / "requirements.txt").exists(),
            len(list[t.Any](self.pkg_path.rglob(" * .py"))) > 50,
            len(list[t.Any](self.pkg_path.glob("tests / test_ * .py"))) > 20,
        ]
        return sum(complex_indicators) >= 3

    def _estimate_hook_duration(self) -> float:
        base_time = 30.0
        file_factor = self.total_python_files * 0.5
        test_factor = self.total_test_files * 2.0

        return base_time + file_factor + test_factor

    @property
    def ai_agent_mode(self) -> bool:
        """Check if AI agent mode is enabled."""
        return getattr(self.options, "ai_agent", False)

    @property
    def ai_debug_mode(self) -> bool:
        """Check if AI debug mode is enabled."""
        return getattr(self.options, "ai_debug", False)

    @property
    def interactive(self) -> bool:
        """Check if interactive mode is enabled."""
        return getattr(self.options, "interactive", False)

    @property
    def working_directory(self) -> Path:
        """Get the working directory path."""
        return self.pkg_path


class StrategySelector:
    def __init__(self, console: Console) -> None:
        self.console = console

    def select_strategy(
        self,
        config: OrchestrationConfig,
        context: ExecutionContext,
    ) -> ExecutionStrategy:
        if config.execution_strategy != ExecutionStrategy.ADAPTIVE:
            return config.execution_strategy

        return self._select_adaptive_strategy(context)

    def _select_adaptive_strategy(self, context: ExecutionContext) -> ExecutionStrategy:
        if context.iteration_count == 1:
            return ExecutionStrategy.BATCH

        if len(context.previous_failures) > 5:
            self.console.print(
                "[yellow]🧠 Switching to individual execution due to multiple failures[/ yellow]",
            )
            return ExecutionStrategy.INDIVIDUAL

        if context.changed_files and len(context.changed_files) < 5:
            self.console.print(
                "[cyan]🎯 Using selective execution for targeted file changes[/ cyan]",
            )
            return ExecutionStrategy.SELECTIVE

        if context.has_complex_setup and context.iteration_count > 2:
            return ExecutionStrategy.INDIVIDUAL

        return ExecutionStrategy.BATCH

    def select_hook_subset(
        self,
        strategy: HookStrategy,
        execution_strategy: ExecutionStrategy,
        context: ExecutionContext,
    ) -> HookStrategy:
        if execution_strategy == ExecutionStrategy.SELECTIVE:
            return self._create_selective_strategy(strategy, context)

        return strategy

    def _create_selective_strategy(
        self,
        strategy: HookStrategy,
        context: ExecutionContext,
    ) -> HookStrategy:
        priority_hooks = set[t.Any](context.previous_failures)

        if context.changed_files:
            for file_path in context.changed_files:
                if file_path.suffix == ".py":
                    priority_hooks.update(["pyright", "ruff-check", "ruff-format"])
                if "test" in str(file_path):
                    priority_hooks.update(["pytest", "coverage"])
                if str(file_path).endswith(("setup.py", "pyproject.toml")):
                    priority_hooks.update(["bandit", "creosote", "gitleaks"])

        selected_hooks = [
            hook for hook in strategy.hooks if hook.name in priority_hooks
        ]

        if not selected_hooks:
            selected_hooks = strategy.hooks[:3]

        self.console.print(
            f"[cyan]🎯 Selected {len(selected_hooks)} hooks for targeted execution: "
            f"{', '.join(h.name for h in selected_hooks)}[/ cyan]",
        )

        return HookStrategy(
            name=f"{strategy.name}_selective",
            hooks=selected_hooks,
            timeout=strategy.timeout,
            retry_policy=strategy.retry_policy,
            parallel=strategy.parallel,
            max_workers=min(strategy.max_workers, len(selected_hooks)),
        )


class OrchestrationPlanner:
    def __init__(self, console: Console) -> None:
        self.console = console
        self.strategy_selector = StrategySelector(console)

    def create_execution_plan(
        self,
        config: OrchestrationConfig,
        context: ExecutionContext,
        hook_strategies: list[HookStrategy],
    ) -> "ExecutionPlan":
        execution_strategy = self.strategy_selector.select_strategy(config, context)

        hook_plans = []
        for strategy in hook_strategies:
            selected_strategy = self.strategy_selector.select_hook_subset(
                strategy,
                execution_strategy,
                context,
            )
            hook_plans.append(
                {
                    "strategy": selected_strategy,
                    "execution_mode": execution_strategy,
                    "estimated_duration": self._estimate_strategy_duration(
                        selected_strategy,
                    ),
                },
            )

        test_plan = self._create_test_plan(config, context, execution_strategy)

        ai_plan = self._create_ai_plan(config, context)

        return ExecutionPlan(
            config=config,
            execution_strategy=execution_strategy,
            hook_plans=hook_plans,
            test_plan=test_plan,
            ai_plan=ai_plan,
            estimated_total_duration=float(
                sum(int(float(str(plan["estimated_duration"]))) for plan in hook_plans)
            )
            + float(test_plan["estimated_duration"]),
        )

    def _estimate_strategy_duration(self, strategy: HookStrategy) -> float:
        base_time_per_hook = 10.0
        return len(strategy.hooks) * base_time_per_hook

    def _create_test_plan(
        self,
        config: OrchestrationConfig,
        context: ExecutionContext,
        execution_strategy: ExecutionStrategy,
    ) -> dict[str, t.Any]:
        if execution_strategy == ExecutionStrategy.INDIVIDUAL:
            test_mode = "individual_with_progress"
        elif execution_strategy == ExecutionStrategy.SELECTIVE:
            test_mode = "selective"
        else:
            test_mode = "full_suite"

        return {
            "mode": test_mode,
            "parallel_workers": min(
                config.max_parallel_tests,
                context.total_test_files,
            ),
            "estimated_duration": context.total_test_files * 2.0,
            "progress_tracking": config.progress_level
            in (ProgressLevel.DETAILED, ProgressLevel.GRANULAR),
        }

    def _create_ai_plan(
        self,
        config: OrchestrationConfig,
        context: ExecutionContext,
    ) -> dict[str, t.Any]:
        return {
            "mode": config.ai_coordination_mode,
            "intelligence_level": config.ai_intelligence,
            "batch_processing": True,
            "correlation_tracking": config.correlation_tracking,
            "failure_analysis": config.failure_analysis,
            "adaptive_retry": config.intelligent_retry,
        }


@dataclass
class ExecutionPlan:
    config: OrchestrationConfig
    execution_strategy: ExecutionStrategy
    hook_plans: list[dict[str, t.Any]]
    test_plan: dict[str, t.Any]
    ai_plan: dict[str, t.Any]
    estimated_total_duration: float

    def print_plan_summary(self, console: Console) -> None:
        console.print("\n" + "=" * 80)
        console.print(
            "[bold bright_blue]🎯 ORCHESTRATED EXECUTION PLAN[/ bold bright_blue]",
        )
        console.print("=" * 80)

        console.print(f"[bold]Strategy: [/ bold] {self.execution_strategy.value}")
        console.print(
            f"[bold]AI Mode: [/ bold] {self.config.ai_coordination_mode.value}",
        )
        console.print(
            f"[bold]Progress Level: [/ bold] {self.config.progress_level.value}",
        )
        console.print(
            f"[bold]Estimated Duration: [/ bold] {self.estimated_total_duration: .1f}s",
        )

        console.print("\n[bold cyan]Hook Execution: [/ bold cyan]")
        for i, plan in enumerate(self.hook_plans, 1):
            strategy = plan["strategy"]
            console.print(
                f" {i}. {strategy.name}-{len(strategy.hooks)} hooks "
                f"({plan['estimated_duration']: .1f}s)",
            )

        console.print("\n[bold green]Test Execution: [/ bold green]")
        console.print(f" Mode: {self.test_plan['mode']}")
        console.print(f" Workers: {self.test_plan['parallel_workers']}")
        console.print(f" Duration: {self.test_plan['estimated_duration']: .1f}s")

        console.print("\n[bold magenta]AI Coordination: [/ bold magenta]")
        console.print(f" Mode: {self.ai_plan['mode'].value}")
        console.print(f" Intelligence: {self.ai_plan['intelligence_level'].value}")
        console.print(
            f" Batch Processing: {'✅' if self.ai_plan['batch_processing'] else '❌'}",
        )

        console.print("=" * 80)
