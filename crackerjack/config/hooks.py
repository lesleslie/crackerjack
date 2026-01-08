from contextlib import suppress
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from crackerjack.config.tool_commands import get_tool_command


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
    command: list[str] = field(default_factory=list)
    timeout: int = 60
    stage: HookStage = HookStage.FAST
    description: str | None = None
    retry_on_failure: bool = False
    is_formatting: bool = False
    manual_stage: bool = False
    config_path: Path | None = None
    security_level: SecurityLevel = SecurityLevel.MEDIUM
    accepts_file_paths: bool = False
    _direct_cmd_cache: list[str] | None = field(default=None, init=False, repr=False)

    def get_command(self) -> list[str]:
        if self.command:
            return self.command

        if self._direct_cmd_cache is None:
            try:
                self._direct_cmd_cache = get_tool_command(
                    self.name, pkg_path=Path.cwd()
                )
            except KeyError as exc:
                msg = f"Hook '{self.name}' is not registered for direct execution."
                raise ValueError(msg) from exc

        return self._direct_cmd_cache

    def build_command(self, files: list[Path] | None = None) -> list[str]:
        base_cmd = self.get_command().copy()

        if files and self.accepts_file_paths:
            base_cmd.extend([str(f) for f in files])

        return base_cmd


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
        timeout=120,
        retry_on_failure=True,
        security_level=SecurityLevel.HIGH,
    ),
    HookDefinition(
        name="trailing-whitespace",
        command=[],
        is_formatting=True,
        timeout=120,
        retry_on_failure=True,
        security_level=SecurityLevel.LOW,
        accepts_file_paths=True,
    ),
    HookDefinition(
        name="end-of-file-fixer",
        command=[],
        is_formatting=True,
        timeout=120,
        retry_on_failure=True,
        security_level=SecurityLevel.LOW,
        accepts_file_paths=True,
    ),
    HookDefinition(
        name="check-yaml",
        command=[],
        timeout=60,
        security_level=SecurityLevel.MEDIUM,
        accepts_file_paths=True,
    ),
    HookDefinition(
        name="check-toml",
        command=[],
        timeout=150,
        security_level=SecurityLevel.MEDIUM,
        accepts_file_paths=True,
    ),
    HookDefinition(
        name="check-json",
        command=[],
        timeout=90,
        security_level=SecurityLevel.MEDIUM,
        accepts_file_paths=True,
    ),
    HookDefinition(
        name="check-ast",
        command=[],
        timeout=90,
        security_level=SecurityLevel.HIGH,
        accepts_file_paths=True,
    ),
    HookDefinition(
        name="format-json",
        command=[],
        is_formatting=True,
        timeout=120,
        retry_on_failure=True,
        security_level=SecurityLevel.LOW,
        accepts_file_paths=True,
    ),
    HookDefinition(
        name="check-added-large-files",
        command=[],
        timeout=90,
        security_level=SecurityLevel.HIGH,
    ),
    HookDefinition(
        name="uv-lock",
        command=[],
        timeout=60,
        security_level=SecurityLevel.HIGH,
    ),
    HookDefinition(
        name="codespell",
        command=[],
        timeout=150,
        security_level=SecurityLevel.LOW,
        accepts_file_paths=True,
    ),
    HookDefinition(
        name="ruff-check",
        command=[],
        is_formatting=True,
        timeout=240,
        retry_on_failure=True,
        security_level=SecurityLevel.MEDIUM,
        accepts_file_paths=True,
    ),
    HookDefinition(
        name="ruff-format",
        command=[],
        is_formatting=True,
        timeout=240,
        retry_on_failure=True,
        security_level=SecurityLevel.LOW,
        accepts_file_paths=True,
    ),
    HookDefinition(
        name="mdformat",
        command=[],
        is_formatting=True,
        timeout=600,
        retry_on_failure=True,
        security_level=SecurityLevel.LOW,
        accepts_file_paths=True,
    ),
    HookDefinition(
        name="check-local-links",
        command=[],
        timeout=60,
        security_level=SecurityLevel.LOW,
        accepts_file_paths=True,
        description="Fast local link validation (file references and anchors only)",
    ),
]

COMPREHENSIVE_HOOKS = [
    HookDefinition(
        name="zuban",
        command=[],
        timeout=240,
        stage=HookStage.COMPREHENSIVE,
        manual_stage=True,
        security_level=SecurityLevel.HIGH,
        accepts_file_paths=True,
    ),
    HookDefinition(
        name="semgrep",
        command=[],
        timeout=480,
        stage=HookStage.COMPREHENSIVE,
        manual_stage=True,
        security_level=SecurityLevel.CRITICAL,
        accepts_file_paths=True,
    ),
    HookDefinition(
        name="pyscn",
        command=[],
        timeout=300,
        stage=HookStage.COMPREHENSIVE,
        manual_stage=True,
        security_level=SecurityLevel.HIGH,
        accepts_file_paths=True,
    ),
    HookDefinition(
        name="gitleaks",
        command=[],
        timeout=180,
        stage=HookStage.COMPREHENSIVE,
        manual_stage=True,
        security_level=SecurityLevel.CRITICAL,
    ),
    HookDefinition(
        name="pip-audit",
        command=[],
        timeout=180,
        stage=HookStage.COMPREHENSIVE,
        manual_stage=True,
        security_level=SecurityLevel.CRITICAL,
        accepts_file_paths=False,
    ),
    HookDefinition(
        name="skylos",
        command=[],
        timeout=600,
        stage=HookStage.COMPREHENSIVE,
        manual_stage=True,
        security_level=SecurityLevel.MEDIUM,
        accepts_file_paths=True,
    ),
    HookDefinition(
        name="refurb",
        command=[],
        timeout=480,
        stage=HookStage.COMPREHENSIVE,
        manual_stage=True,
        security_level=SecurityLevel.MEDIUM,
        accepts_file_paths=True,
    ),
    HookDefinition(
        name="creosote",
        command=[],
        timeout=360,
        stage=HookStage.COMPREHENSIVE,
        manual_stage=True,
        security_level=SecurityLevel.HIGH,
    ),
    HookDefinition(
        name="complexipy",
        command=[],
        timeout=300,
        stage=HookStage.COMPREHENSIVE,
        manual_stage=True,
        security_level=SecurityLevel.MEDIUM,
        accepts_file_paths=True,
    ),
    HookDefinition(
        name="check-jsonschema",
        command=[],
        timeout=180,
        stage=HookStage.COMPREHENSIVE,
        manual_stage=True,
        security_level=SecurityLevel.HIGH,
        accepts_file_paths=True,
    ),
    HookDefinition(
        name="linkcheckmd",
        command=[],
        timeout=300,
        stage=HookStage.COMPREHENSIVE,
        manual_stage=True,
        security_level=SecurityLevel.LOW,
        accepts_file_paths=False,
        description="Comprehensive link validation (local + external URLs)",
    ),
]


FAST_STRATEGY = HookStrategy(
    name="fast",
    hooks=FAST_HOOKS,
    timeout=300,
    retry_policy=RetryPolicy.NONE,
    parallel=True,
    max_workers=2,
)

COMPREHENSIVE_STRATEGY = HookStrategy(
    name="comprehensive",
    hooks=COMPREHENSIVE_HOOKS,
    timeout=1800,
    retry_policy=RetryPolicy.NONE,
    parallel=True,
    max_workers=2,
)


def _update_hook_timeouts_from_settings(hooks: list[HookDefinition]) -> None:
    with suppress(Exception):
        from crackerjack.config import CrackerjackSettings, load_settings

        settings = load_settings(CrackerjackSettings)

        for hook in hooks:
            timeout_attr = f"{hook.name}_timeout"
            if hasattr(settings.adapter_timeouts, timeout_attr):
                configured_timeout = getattr(settings.adapter_timeouts, timeout_attr)
                hook.timeout = configured_timeout


class HookConfigLoader:
    @staticmethod
    def load_strategy(name: str, _: Path | None = None) -> HookStrategy:
        if name == "fast":
            _update_hook_timeouts_from_settings(FAST_HOOKS)
            return FAST_STRATEGY
        if name == "comprehensive":
            _update_hook_timeouts_from_settings(COMPREHENSIVE_HOOKS)
            return COMPREHENSIVE_STRATEGY
        msg = f"Unknown hook strategy: {name}"
        raise ValueError(msg)
