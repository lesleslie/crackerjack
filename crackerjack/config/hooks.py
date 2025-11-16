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
    command: list[str]
    timeout: int = 60
    stage: HookStage = HookStage.FAST
    description: str | None = None
    retry_on_failure: bool = False
    is_formatting: bool = False
    manual_stage: bool = False
    config_path: Path | None = None
    security_level: SecurityLevel = SecurityLevel.MEDIUM
    use_precommit_legacy: bool = True  # Phase 8.2: Backward compatibility flag
    accepts_file_paths: bool = False  # Phase 10.4.4: Can tool process individual files?
    _direct_cmd_cache: list[str] | None = field(default=None, init=False, repr=False)

    def get_command(self) -> list[str]:
        """Get the command to execute this hook.

        Returns the appropriate command based on use_precommit_legacy flag:
        - If use_precommit_legacy=True: Returns pre-commit wrapper command (legacy mode)
        - If use_precommit_legacy=False: Returns direct tool command (Phase 8+ mode)

        Returns:
            List of command arguments for subprocess execution
        """
        # Phase 8.2: Direct invocation mode (new behavior)
        if not self.use_precommit_legacy:
            if self._direct_cmd_cache is None:
                try:
                    self._direct_cmd_cache = get_tool_command(
                        self.name, pkg_path=Path.cwd()
                    )
                except KeyError:
                    # Fallback to pre-commit if tool not in registry
                    # This ensures graceful degradation during migration
                    self._direct_cmd_cache = None
            if self._direct_cmd_cache is not None:
                return self._direct_cmd_cache

        # Legacy mode: Use pre-commit wrapper (Phase 1-7 behavior)
        import shutil

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

    def build_command(self, files: list[Path] | None = None) -> list[str]:
        """Build command with optional file paths for targeted execution.

        Phase 10.4.4: Enables incremental execution on specific files when supported.

        Args:
            files: Optional list of file paths to process. If None, processes all files.

        Returns:
            Command list with file paths appended if tool accepts them.

        Example:
            >>> hook = HookDefinition(
            ...     name="ruff-check",
            ...     command=["ruff", "check"],
            ...     accepts_file_paths=True,
            ... )
            >>> hook.build_command([Path("foo.py"), Path("bar.py")])
            ["ruff", "check", "foo.py", "bar.py"]
        """
        base_cmd = self.get_command().copy()

        # Append file paths if tool accepts them and files are provided
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
        timeout=60,  # Increased from 20 to handle larger codebases (was potentially causing issues at 20s)
        retry_on_failure=True,
        security_level=SecurityLevel.HIGH,
        use_precommit_legacy=False,  # Phase 8.4: Direct invocation
    ),
    HookDefinition(
        name="trailing-whitespace",
        command=[],
        is_formatting=True,
        timeout=60,  # Increased from 20 to handle larger codebases (was potentially causing issues at 20s)
        retry_on_failure=True,
        security_level=SecurityLevel.LOW,
        use_precommit_legacy=False,  # Phase 8.4: Direct invocation
        accepts_file_paths=True,  # Phase 10.4.4: File-level fixer
    ),
    HookDefinition(
        name="end-of-file-fixer",
        command=[],
        is_formatting=True,
        timeout=60,  # Increased from 20 to handle larger codebases (was potentially causing issues at 20s)
        retry_on_failure=True,
        security_level=SecurityLevel.LOW,
        use_precommit_legacy=False,  # Phase 8.4: Direct invocation
        accepts_file_paths=True,  # Phase 10.4.4: File-level fixer
    ),
    HookDefinition(
        name="check-yaml",
        command=[],
        timeout=20,  # UV init (~10s) + tool execution (P95=0.53s) + safety margin
        security_level=SecurityLevel.MEDIUM,
        use_precommit_legacy=False,  # Phase 8.4: Direct invocation
        accepts_file_paths=True,  # Phase 10.4.4: File-level validator
    ),
    HookDefinition(
        name="check-toml",
        command=[],
        timeout=79,  # Phase 10.4.1: Profiled P95=26.58s, safety=3x
        security_level=SecurityLevel.MEDIUM,
        use_precommit_legacy=False,  # Phase 8.4: Direct invocation
        accepts_file_paths=True,  # Phase 10.4.4: File-level validator
    ),
    HookDefinition(
        name="check-json",
        command=[],
        timeout=30,  # UV init (~10s) + tool execution (P95=~0.5s) + safety margin
        security_level=SecurityLevel.MEDIUM,
        use_precommit_legacy=False,  # Phase 8.4: Direct invocation
        accepts_file_paths=True,  # Phase 10.4.4: File-level validator
    ),
    HookDefinition(
        name="check-ast",
        command=[],
        timeout=30,  # UV init (~10s) + tool execution (P95=~0.2s) + safety margin
        security_level=SecurityLevel.HIGH,
        use_precommit_legacy=False,  # Phase 8.4: Direct invocation
        accepts_file_paths=True,  # Phase 10.4.4: File-level validator
    ),
    HookDefinition(
        name="format-json",
        command=[],
        is_formatting=True,
        timeout=45,  # UV init (~10s) + tool execution + formatting overhead
        retry_on_failure=True,
        security_level=SecurityLevel.LOW,
        use_precommit_legacy=False,  # Phase 8.4: Direct invocation
        accepts_file_paths=True,  # Phase 10.4.4: File-level formatter
    ),
    HookDefinition(
        name="check-added-large-files",
        command=[],
        timeout=30,  # UV init (~10s) + tool execution (P95=0.27s) + increased safety margin
        security_level=SecurityLevel.HIGH,
        use_precommit_legacy=False,  # Phase 8.4: Direct invocation
    ),
    HookDefinition(
        name="uv-lock",
        command=[],
        timeout=20,  # UV init (~10s) + tool execution (P95=1.99s) + safety margin
        security_level=SecurityLevel.HIGH,
        use_precommit_legacy=False,  # Phase 8.4: Direct invocation
    ),
    HookDefinition(
        name="codespell",
        command=[],
        timeout=45,  # UV init (~10s) + tool execution + large repo scanning overhead
        security_level=SecurityLevel.LOW,
        use_precommit_legacy=False,  # Phase 8.4: Direct invocation
        accepts_file_paths=True,  # Phase 10.4.4: File-level spell checker
    ),
    HookDefinition(
        name="ruff-check",
        command=[],
        is_formatting=True,
        timeout=120,  # Increased from 20 to handle larger codebases (was causing timeouts at 20s)
        retry_on_failure=True,
        security_level=SecurityLevel.MEDIUM,
        use_precommit_legacy=False,  # Phase 8.4: Direct invocation
        accepts_file_paths=True,  # Phase 10.4.4: File-level Python linter
    ),
    HookDefinition(
        name="ruff-format",
        command=[],
        is_formatting=True,
        timeout=120,  # Increased from 20 to handle larger codebases (was causing timeouts at 20s)
        retry_on_failure=True,
        security_level=SecurityLevel.LOW,
        use_precommit_legacy=False,  # Phase 8.4: Direct invocation
        accepts_file_paths=True,  # Phase 10.4.4: File-level Python formatter
    ),
    HookDefinition(
        name="mdformat",
        command=[],
        is_formatting=True,
        timeout=120,  # 266 markdown files + mdformat-ruff plugin overhead (~0.45s per file average)
        retry_on_failure=True,
        security_level=SecurityLevel.LOW,
        use_precommit_legacy=False,  # Phase 8.4: Direct invocation
        accepts_file_paths=True,  # Phase 10.4.4: File-level markdown formatter
    ),
]

COMPREHENSIVE_HOOKS = [
    HookDefinition(
        name="zuban",
        command=[],
        timeout=80,  # UV init (~10s) + tool execution (P95=10.97s) + increased safety margin
        stage=HookStage.COMPREHENSIVE,
        manual_stage=True,
        security_level=SecurityLevel.HIGH,  # Changed from CRITICAL to HIGH to allow other hooks to run
        use_precommit_legacy=False,  # Phase 8.4: Direct invocation
    ),
    HookDefinition(
        name="semgrep",
        command=[],
        timeout=240,  # 4 minutes - most scans complete in <1 min (observed: 9-10s)
        stage=HookStage.COMPREHENSIVE,
        manual_stage=True,
        security_level=SecurityLevel.CRITICAL,
        use_precommit_legacy=False,  # Phase 8.4: Direct invocation
        accepts_file_paths=True,  # Phase 10.4.4: File-level SAST scanner
    ),
    # NOTE: Bandit replaced with Semgrep (using uvx for Python 3.13 isolation)
    # HookDefinition(
    #     name="bandit",
    #     command=[],
    #     timeout=180,  # 3 minutes for SAST scanning
    #     stage=HookStage.COMPREHENSIVE,
    #     manual_stage=True,
    #     security_level=SecurityLevel.CRITICAL,
    #     use_precommit_legacy=False,  # Phase 8.4: Direct invocation
    #     accepts_file_paths=True,  # Phase 10.4.4: File-level SAST scanner
    # ),
    HookDefinition(
        name="gitleaks",
        command=[],
        timeout=45,  # Reduce to avoid long stalls in restricted environments
        stage=HookStage.COMPREHENSIVE,
        manual_stage=True,
        security_level=SecurityLevel.CRITICAL,
        use_precommit_legacy=False,  # Phase 8.4: Direct invocation
    ),
    HookDefinition(
        name="skylos",
        command=[],
        timeout=60,  # Allow more time for scanning
        stage=HookStage.COMPREHENSIVE,
        manual_stage=True,
        security_level=SecurityLevel.MEDIUM,
        use_precommit_legacy=False,  # Phase 8.4: Direct invocation
        accepts_file_paths=True,  # Phase 10.5: Incremental execution on changed files
    ),
    HookDefinition(
        name="refurb",
        command=[],
        timeout=240,  # 4 minutes - matches adapter default
        stage=HookStage.COMPREHENSIVE,
        manual_stage=True,
        security_level=SecurityLevel.MEDIUM,
        use_precommit_legacy=False,  # Phase 8.4: Direct invocation
        accepts_file_paths=True,  # Phase 10.5: Incremental execution on changed files (240s -> ~10s)
    ),
    HookDefinition(
        name="creosote",
        command=[],
        timeout=180,  # Increase to accommodate slower dependency scans
        stage=HookStage.COMPREHENSIVE,
        manual_stage=True,
        security_level=SecurityLevel.HIGH,
        use_precommit_legacy=False,  # Phase 8.4: Direct invocation
    ),
    HookDefinition(
        name="complexipy",
        command=[],
        timeout=120,  # Allow more time for full-tree complexity analysis
        stage=HookStage.COMPREHENSIVE,
        manual_stage=True,
        security_level=SecurityLevel.MEDIUM,
        use_precommit_legacy=False,  # Phase 8.4: Direct invocation
        accepts_file_paths=True,  # Phase 10.5: Incremental execution on changed files
    ),
    HookDefinition(
        name="check-jsonschema",
        command=[],
        timeout=60,  # UV init (~10s) + schema validation overhead
        stage=HookStage.COMPREHENSIVE,
        manual_stage=True,
        security_level=SecurityLevel.HIGH,
        use_precommit_legacy=False,  # Phase 8.4: Direct invocation
        accepts_file_paths=True,  # Phase 10.4.4: File-level schema validator
    ),
]


FAST_STRATEGY = HookStrategy(
    name="fast",
    hooks=FAST_HOOKS,
    timeout=60,
    retry_policy=RetryPolicy.FORMATTING_ONLY,
    parallel=True,  # Phase 6: Enable parallel execution for 2-3x speedup
    max_workers=4,  # Optimal concurrency for fast hooks
)

COMPREHENSIVE_STRATEGY = HookStrategy(
    name="comprehensive",
    hooks=COMPREHENSIVE_HOOKS,
    timeout=300,
    retry_policy=RetryPolicy.NONE,
    parallel=True,  # Phase 6: Enable parallel execution for 2x speedup
    max_workers=4,  # Optimal concurrency for comprehensive hooks
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
