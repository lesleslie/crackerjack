from __future__ import annotations

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
    auto_run: bool = True
    config_path: Path | None = None
    security_level: SecurityLevel = SecurityLevel.MEDIUM
    accepts_file_paths: bool = False
    disabled: bool = False
    run_schedule: str | None = None
    _direct_cmd_cache: list[str] | None = field(default=None, init=False, repr=False)

    def get_command(self) -> list[str]:
        if self.command:
            return self.command

        if self._direct_cmd_cache is None:
            try:
                self._direct_cmd_cache = get_tool_command(
                    self.name,
                    pkg_path=Path.cwd(),
                )
            except KeyError as exc:
                msg = f"Hook '{self.name}' is not registered for direct execution."
                raise ValueError(msg) from exc

        return self._direct_cmd_cache

    def build_command(self, files: list[Path] | None = None) -> list[str]:

        base_cmd = self.get_command()

        if files and self.accepts_file_paths:
            base_cmd.extend([str(f) for f in files])
        else:
            base_cmd.append("crackerjack/")

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
        is_formatting=True,
        timeout=150,
        retry_on_failure=True,
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
        timeout=180,
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
    HookDefinition(
        name="pip-audit",
        command=[],
        timeout=180,
        retry_on_failure=True,
        security_level=SecurityLevel.CRITICAL,
        accepts_file_paths=False,
        description="Dependency vulnerability scanning with auto-fix",
    ),
]

COMPREHENSIVE_HOOKS = [
    HookDefinition(
        name="ty",
        command=[],
        timeout=120,
        stage=HookStage.COMPREHENSIVE,
        auto_run=True,
        security_level=SecurityLevel.HIGH,
        accepts_file_paths=True,
        description="Default type checker (replaces zuban as primary)",
    ),
    HookDefinition(
        name="zuban",
        command=[],
        timeout=60,
        stage=HookStage.COMPREHENSIVE,
        auto_run=False,
        security_level=SecurityLevel.HIGH,
        accepts_file_paths=True,
        description="Legacy type checker (opt-in via enable_zuban flag)",
    ),
    HookDefinition(
        name="semgrep",
        command=[],
        timeout=480,
        stage=HookStage.COMPREHENSIVE,
        auto_run=True,
        security_level=SecurityLevel.CRITICAL,
        accepts_file_paths=True,
    ),
    HookDefinition(
        name="pyscn",
        command=[],
        timeout=300,
        stage=HookStage.COMPREHENSIVE,
        auto_run=True,
        security_level=SecurityLevel.HIGH,
        accepts_file_paths=True,
    ),
    HookDefinition(
        name="betterleaks",
        command=[],
        timeout=180,
        stage=HookStage.COMPREHENSIVE,
        auto_run=True,
        security_level=SecurityLevel.CRITICAL,
        disabled=False,
        description=(
            "Secrets detection (primary gate — requires the betterleaks Go binary "
            "from https://github.com/betterleaks/betterleaks on PATH)"
        ),
    ),
    HookDefinition(
        name="gitleaks",
        command=[],
        timeout=180,
        stage=HookStage.COMPREHENSIVE,
        auto_run=True,
        security_level=SecurityLevel.CRITICAL,
        disabled=True,
        description=(
            "Secrets detection (FALLBACK: only enable if betterleaks is unavailable; "
            "see betterleaks entry for the install-then-activate flow)"
        ),
    ),
    HookDefinition(
        name="skylos",
        command=[],
        timeout=900,
        stage=HookStage.COMPREHENSIVE,
        auto_run=True,
        security_level=SecurityLevel.MEDIUM,
        accepts_file_paths=True,
        run_schedule="weekly",
        disabled=True,
        description=(
            "Dead code detection (DISABLED 2026-06-29 — replaced by pyscn's "
            "CFG-based dead-code detection. Re-enable if pyscn misses findings "
            "skylos would catch, or if you specifically need Rust-speed.)"
        ),
    ),
    HookDefinition(
        name="refurb",
        command=[],
        timeout=1800,
        stage=HookStage.COMPREHENSIVE,
        auto_run=True,
        security_level=SecurityLevel.MEDIUM,
        accepts_file_paths=True,
    ),
    HookDefinition(
        name="creosote",
        command=[],
        timeout=600,
        stage=HookStage.COMPREHENSIVE,
        auto_run=True,
        security_level=SecurityLevel.HIGH,
    ),
    HookDefinition(
        name="complexipy",
        command=[],
        timeout=900,
        stage=HookStage.COMPREHENSIVE,
        auto_run=True,
        security_level=SecurityLevel.MEDIUM,
        accepts_file_paths=True,
        run_schedule="weekly",
        disabled=True,
        description=(
            "Cognitive complexity analysis (DISABLED 2026-06-29 — too slow at "
            "~10 min vs pyscn's ~60s; pyscn handles cyclomatic complexity in "
            "comp hooks via JSON output. Cognitive signal not load-bearing.)"
        ),
    ),
    HookDefinition(
        name="cohesion",
        command=[],
        timeout=300,
        stage=HookStage.COMPREHENSIVE,
        security_level=SecurityLevel.MEDIUM,
        accepts_file_paths=False,
        description="Class cohesion measurement (GPL-3.0, CLI-only invocation)",
    ),
    HookDefinition(
        name="pymetrica",
        command=[],
        timeout=1200,
        stage=HookStage.COMPREHENSIVE,
        security_level=SecurityLevel.MEDIUM,
        accepts_file_paths=False,
        description="Halstead Volume, Primitive Obsession, Instability, Maintainability Cost",  # noqa: E501
    ),
    HookDefinition(
        name="check-jsonschema",
        command=[],
        timeout=180,
        stage=HookStage.COMPREHENSIVE,
        auto_run=True,
        security_level=SecurityLevel.HIGH,
        accepts_file_paths=True,
    ),
    HookDefinition(
        name="linkcheckmd",
        command=[],
        timeout=300,
        stage=HookStage.COMPREHENSIVE,
        auto_run=True,
        security_level=SecurityLevel.LOW,
        accepts_file_paths=False,
        description="Comprehensive link validation (local + external URLs)",
    ),
    HookDefinition(
        name="lychee",
        command=[],
        timeout=300,
        stage=HookStage.COMPREHENSIVE,
        auto_run=True,
        security_level=SecurityLevel.LOW,
        accepts_file_paths=False,
        description="Comprehensive async link checker (Markdown, HTML, reStructuredText, text files with URLs)",  # noqa: E501
    ),
]


def _build_opt_in_type_hooks() -> list[HookDefinition]:

    optional_hooks: list[HookDefinition] = []

    with suppress(Exception):
        from crackerjack.config import CrackerjackSettings, load_settings

        settings = load_settings(CrackerjackSettings)
        adapter_timeouts = getattr(settings, "adapter_timeouts", None)

        if getattr(settings.hooks, "enable_pyrefly", False):
            optional_hooks.append(
                HookDefinition(
                    name="pyrefly",
                    command=[],
                    timeout=getattr(adapter_timeouts, "pyrefly_timeout", 120),
                    stage=HookStage.COMPREHENSIVE,
                    auto_run=True,
                    security_level=SecurityLevel.HIGH,
                    accepts_file_paths=True,
                    description="Opt-in Pyrefly type checking",
                )
            )

        if getattr(settings.hooks, "enable_zuban", False):
            optional_hooks.append(
                HookDefinition(
                    name="zuban",
                    command=[],
                    timeout=getattr(adapter_timeouts, "zuban_timeout", 60),
                    stage=HookStage.COMPREHENSIVE,
                    auto_run=True,
                    security_level=SecurityLevel.HIGH,
                    accepts_file_paths=True,
                    description="Opt-in Zuban type checking (legacy, alongside ty)",
                )
            )

    return optional_hooks


def _build_comprehensive_hooks() -> list[HookDefinition]:
    hooks = COMPREHENSIVE_HOOKS.copy()
    hooks.extend(_build_opt_in_type_hooks())

    hooks = [h for h in hooks if h.auto_run and not h.disabled]
    return hooks


FAST_STRATEGY = HookStrategy(
    name="fast",
    hooks=FAST_HOOKS,
    timeout=300,
    retry_policy=RetryPolicy.NONE,
    parallel=True,
    max_workers=6,
)


COMPREHENSIVE_STRATEGY = HookStrategy(
    name="comprehensive",
    hooks=[h for h in COMPREHENSIVE_HOOKS if h.auto_run and not h.disabled],
    timeout=1800,
    retry_policy=RetryPolicy.NONE,
    parallel=True,
    max_workers=6,
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
            hooks = _build_comprehensive_hooks()
            _update_hook_timeouts_from_settings(hooks)
            return HookStrategy(
                name="comprehensive",
                hooks=hooks,
                timeout=1800,
                retry_policy=RetryPolicy.NONE,
                parallel=True,
                max_workers=6,
            )
        msg = f"Unknown hook strategy: {name}"
        raise ValueError(msg)
