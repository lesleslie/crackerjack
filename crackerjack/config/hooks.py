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


class SecurityLevel(Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


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
    security_level: SecurityLevel = SecurityLevel.MEDIUM

    def get_command(self) -> list[str]:
        import shutil
        from pathlib import Path

        pre_commit_path = None
        current_dir = Path.cwd()
        project_pre_commit = current_dir / ".venv" / "bin" / "pre-commit"
        if project_pre_commit.exists():
            pre_commit_path = str(project_pre_commit)
        else:
            pre_commit_path = shutil.which("pre-commit") or "pre-commit"

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
        command=[],
        is_formatting=True,
        timeout=30,
        retry_on_failure=True,
        security_level=SecurityLevel.HIGH,
    ),
    HookDefinition(
        name="trailing-whitespace",
        command=[],
        is_formatting=True,
        retry_on_failure=True,
        security_level=SecurityLevel.LOW,
    ),
    HookDefinition(
        name="end-of-file-fixer",
        command=[],
        is_formatting=True,
        retry_on_failure=True,
        security_level=SecurityLevel.LOW,
    ),
    HookDefinition(
        name="check-yaml",
        command=[],
        security_level=SecurityLevel.MEDIUM,
    ),
    HookDefinition(
        name="check-toml",
        command=[],
        security_level=SecurityLevel.MEDIUM,
    ),
    HookDefinition(
        name="check-added-large-files",
        command=[],
        security_level=SecurityLevel.HIGH,
    ),
    HookDefinition(
        name="uv-lock",
        command=[],
        security_level=SecurityLevel.HIGH,
    ),
    HookDefinition(
        name="gitleaks",
        command=[],
        security_level=SecurityLevel.CRITICAL,
    ),
    HookDefinition(
        name="codespell",
        command=[],
        security_level=SecurityLevel.LOW,
    ),
    HookDefinition(
        name="ruff-check",
        command=[],
        is_formatting=True,
        retry_on_failure=True,
        security_level=SecurityLevel.MEDIUM,
    ),
    HookDefinition(
        name="ruff-format",
        command=[],
        is_formatting=True,
        retry_on_failure=True,
        security_level=SecurityLevel.LOW,
    ),
    HookDefinition(
        name="mdformat",
        command=[],
        is_formatting=True,
        retry_on_failure=True,
        security_level=SecurityLevel.LOW,
    ),
]

COMPREHENSIVE_HOOKS = [
    HookDefinition(
        name="zuban",
        command=[],
        timeout=30,
        stage=HookStage.COMPREHENSIVE,
        manual_stage=True,
        security_level=SecurityLevel.CRITICAL,
    ),
    HookDefinition(
        name="bandit",
        command=[],
        timeout=300,
        stage=HookStage.COMPREHENSIVE,
        manual_stage=True,
        security_level=SecurityLevel.CRITICAL,
    ),
    HookDefinition(
        name="skylos",
        command=[],
        timeout=30,
        stage=HookStage.COMPREHENSIVE,
        manual_stage=True,
        security_level=SecurityLevel.MEDIUM,
    ),
    HookDefinition(
        name="refurb",
        command=[],
        timeout=300,
        stage=HookStage.COMPREHENSIVE,
        manual_stage=True,
        security_level=SecurityLevel.MEDIUM,
    ),
    HookDefinition(
        name="creosote",
        command=[],
        timeout=300,
        stage=HookStage.COMPREHENSIVE,
        manual_stage=True,
        security_level=SecurityLevel.HIGH,
    ),
    HookDefinition(
        name="complexipy",
        command=[],
        timeout=60,
        stage=HookStage.COMPREHENSIVE,
        manual_stage=True,
        security_level=SecurityLevel.MEDIUM,
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
    timeout=300,
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
