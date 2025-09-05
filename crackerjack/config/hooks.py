from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class HookStage(Enum):
    FAST = "fast"
    COMPREHENSIVE = "comprehensive"


class RetryPolicy(Enum):
    NONE = "none"
    FORMATTING_ONLY = "formatting_only"
    ALL_HOOKS = "all_hooks"


@dataclass
class HookDefinition:
    name: str
    command: list[str]
    timeout: int = 60
    stage: HookStage = HookStage.FAST
    retry_on_failure: bool = False
    is_formatting: bool = False
    manual_stage: bool = False
    config_path: Path | None = None

    def get_command(self) -> list[str]:
        # Use direct pre-commit execution (pre-commit manages its own environments)
        import shutil
        from pathlib import Path

        # Find pre-commit executable - prefer project venv, fallback to system
        pre_commit_path = None
        current_dir = Path.cwd()
        project_pre_commit = current_dir / ".venv" / "bin" / "pre-commit"
        if project_pre_commit.exists():
            pre_commit_path = str(project_pre_commit)
        else:
            pre_commit_path = shutil.which("pre-commit") or "pre-commit"

        # Build command for direct pre-commit execution
        cmd = [pre_commit_path, "run"]
        if self.config_path:
            cmd.extend(["-c", str(self.config_path)])
        if self.manual_stage:
            cmd.extend(["--hook-stage", "manual"])
        cmd.extend([self.name, "--all-files"])
        return cmd


@dataclass
class HookStrategy:
    name: str
    hooks: list[HookDefinition]
    timeout: int = 300
    retry_policy: RetryPolicy = RetryPolicy.NONE
    parallel: bool = False
    max_workers: int = 3


FAST_HOOKS = [
    HookDefinition(
        name="validate-regex-patterns",
        command=[],  # Dynamically built by get_command()
        timeout=30,
        retry_on_failure=False,  # Regex validation should be strict, no retries
    ),
    HookDefinition(
        name="trailing-whitespace",
        command=[],  # Dynamically built by get_command()
        is_formatting=True,
        retry_on_failure=True,
    ),
    HookDefinition(
        name="end-of-file-fixer",
        command=[],  # Dynamically built by get_command()
        is_formatting=True,
        retry_on_failure=True,
    ),
    HookDefinition(
        name="check-yaml",
        command=[],  # Dynamically built by get_command()
    ),
    HookDefinition(
        name="check-toml",
        command=[],  # Dynamically built by get_command()
    ),
    HookDefinition(
        name="check-added-large-files",
        command=[],  # Dynamically built by get_command()
    ),
    HookDefinition(
        name="uv-lock",
        command=[],  # Dynamically built by get_command()
    ),
    HookDefinition(
        name="gitleaks",
        command=[],  # Dynamically built by get_command()
    ),
    HookDefinition(
        name="codespell",
        command=[],  # Dynamically built by get_command()
    ),
    HookDefinition(
        name="ruff-check",
        command=[],  # Dynamically built by get_command()
    ),
    HookDefinition(
        name="ruff-format",
        command=[],  # Dynamically built by get_command()
        is_formatting=True,
        retry_on_failure=True,
    ),
    HookDefinition(
        name="mdformat",
        command=[],  # Dynamically built by get_command()
        is_formatting=True,
        retry_on_failure=True,
    ),
]

COMPREHENSIVE_HOOKS = [
    HookDefinition(
        name="pyright",
        command=[],  # Dynamically built by get_command()
        timeout=120,
        stage=HookStage.COMPREHENSIVE,
        manual_stage=True,
    ),
    HookDefinition(
        name="bandit",
        command=[],  # Dynamically built by get_command()
        timeout=120,
        stage=HookStage.COMPREHENSIVE,
        manual_stage=True,
    ),
    HookDefinition(
        name="vulture",
        command=[],  # Dynamically built by get_command()
        timeout=120,
        stage=HookStage.COMPREHENSIVE,
        manual_stage=True,
    ),
    HookDefinition(
        name="refurb",
        command=[],  # Dynamically built by get_command()
        timeout=120,
        stage=HookStage.COMPREHENSIVE,
        manual_stage=True,
    ),
    HookDefinition(
        name="creosote",
        command=[],  # Dynamically built by get_command()
        timeout=120,
        stage=HookStage.COMPREHENSIVE,
        manual_stage=True,
    ),
    HookDefinition(
        name="complexipy",
        command=[],  # Dynamically built by get_command()
        timeout=60,
        stage=HookStage.COMPREHENSIVE,
        manual_stage=True,
    ),
]


FAST_STRATEGY = HookStrategy(
    name="fast",
    hooks=FAST_HOOKS,
    timeout=60,
    retry_policy=RetryPolicy.FORMATTING_ONLY,
)

COMPREHENSIVE_STRATEGY = HookStrategy(
    name="comprehensive",
    hooks=COMPREHENSIVE_HOOKS,
    timeout=120,
    retry_policy=RetryPolicy.NONE,
)


class HookConfigLoader:
    @staticmethod
    def load_strategy(name: str, _: Path | None = None) -> HookStrategy:
        if name == "fast":
            return FAST_STRATEGY
        if name == "comprehensive":
            return COMPREHENSIVE_STRATEGY
        msg = f"Unknown hook strategy: {name}"
        raise ValueError(msg)

    # Removed unused method: get_all_strategies
