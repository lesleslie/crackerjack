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
        cmd = ["pre-commit", "run"]
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
        name="trailing-whitespace",
        command=["pre-commit", "run", "trailing-whitespace", "--all-files"],
        is_formatting=True,
        retry_on_failure=True,
    ),
    HookDefinition(
        name="end-of-file-fixer",
        command=["pre-commit", "run", "end-of-file-fixer", "--all-files"],
        is_formatting=True,
        retry_on_failure=True,
    ),
    HookDefinition(
        name="check-yaml",
        command=["pre-commit", "run", "check-yaml", "--all-files"],
    ),
    HookDefinition(
        name="check-toml",
        command=["pre-commit", "run", "check-toml", "--all-files"],
    ),
    HookDefinition(
        name="check-added-large-files",
        command=["pre-commit", "run", "check-added-large-files", "--all-files"],
    ),
    HookDefinition(
        name="uv-lock",
        command=["pre-commit", "run", "uv-lock", "--all-files"],
    ),
    HookDefinition(
        name="gitleaks",
        command=["pre-commit", "run", "gitleaks", "--all-files"],
    ),
    HookDefinition(
        name="codespell",
        command=["pre-commit", "run", "codespell", "--all-files"],
    ),
    HookDefinition(
        name="ruff-check",
        command=["pre-commit", "run", "ruff-check", "--all-files"],
    ),
    HookDefinition(
        name="ruff-format",
        command=["pre-commit", "run", "ruff-format", "--all-files"],
        is_formatting=True,
        retry_on_failure=True,
    ),
    HookDefinition(
        name="mdformat",
        command=["pre-commit", "run", "mdformat", "--all-files"],
        is_formatting=True,
        retry_on_failure=True,
    ),
]

COMPREHENSIVE_HOOKS = [
    HookDefinition(
        name="pyright",
        command=[
            "pre-commit",
            "run",
            "--hook-stage",
            "manual",
            "pyright",
            "--all-files",
        ],
        timeout=120,
        stage=HookStage.COMPREHENSIVE,
        manual_stage=True,
    ),
    HookDefinition(
        name="bandit",
        command=[
            "pre-commit",
            "run",
            "--hook-stage",
            "manual",
            "bandit",
            "--all-files",
        ],
        timeout=120,
        stage=HookStage.COMPREHENSIVE,
        manual_stage=True,
    ),
    HookDefinition(
        name="vulture",
        command=[
            "pre-commit",
            "run",
            "--hook-stage",
            "manual",
            "vulture",
            "--all-files",
        ],
        timeout=120,
        stage=HookStage.COMPREHENSIVE,
        manual_stage=True,
    ),
    HookDefinition(
        name="refurb",
        command=[
            "pre-commit",
            "run",
            "--hook-stage",
            "manual",
            "refurb",
            "--all-files",
        ],
        timeout=120,
        stage=HookStage.COMPREHENSIVE,
        manual_stage=True,
    ),
    HookDefinition(
        name="creosote",
        command=[
            "pre-commit",
            "run",
            "--hook-stage",
            "manual",
            "creosote",
            "--all-files",
        ],
        timeout=120,
        stage=HookStage.COMPREHENSIVE,
        manual_stage=True,
    ),
    HookDefinition(
        name="complexipy",
        command=[
            "pre-commit",
            "run",
            "--hook-stage",
            "manual",
            "complexipy",
            "--all-files",
        ],
        timeout=120,
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

    @staticmethod
    def get_all_strategies() -> dict[str, HookStrategy]:
        return {"fast": FAST_STRATEGY, "comprehensive": COMPREHENSIVE_STRATEGY}
