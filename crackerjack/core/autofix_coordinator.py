from __future__ import annotations

import ast
import asyncio
import fnmatch
import hashlib
import json
import logging
import os
import re
import shutil
import subprocess
import time
import typing as t
from collections.abc import Callable, Sequence
from contextlib import suppress
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from rich.console import Console

from crackerjack.agents.parallel_dispatcher import (
    DispatchResult,
    ParallelDispatcher,
)
from crackerjack.ai_fix.issue_lifecycle import is_no_op_failure
from crackerjack.ai_fix.output_validator import OutputValidator
from crackerjack.ai_fix.working_tree_snapshot import WorkingTreeSnapshot
from crackerjack.config import CrackerjackSettings
from crackerjack.config.hooks import COMPREHENSIVE_HOOKS
from crackerjack.config.tool_commands import get_tool_command
from crackerjack.core.ai_fix_event_bus import AIFixEventBus
from crackerjack.core.ai_fix_events import (
    AgentDispatched,
    FixSessionFinished,
    FixSessionStarted,
    IssueResolved,
    IterationFinished,
    IterationStarted,
    RunFinished,
    RunStarted,
)
from crackerjack.core.ai_fix_sinks import build_default_bus
from crackerjack.core.preflight import PreflightConfig, PreflightFixer
from crackerjack.integration.skills_tracking import create_skills_tracker
from crackerjack.services.prompt_evolution import get_prompt_evolution

if TYPE_CHECKING:
    from crackerjack.agents.analysis_coordinator import AnalysisCoordinator
    from crackerjack.agents.fixer_coordinator import FixerCoordinator
    from crackerjack.agents.validation_coordinator import ValidationCoordinator
    from crackerjack.models.protocols import (
        AgentCoordinatorProtocol,
        LoggerProtocol,
    )

from crackerjack.adapters.factory import DefaultAdapterFactory
from crackerjack.agents.base import AgentContext, FixResult, Issue, IssueType, Priority
from crackerjack.models.fix_plan import FixPlan
from crackerjack.models.qa_config import QACheckConfig
from crackerjack.models.qa_results import QAResult
from crackerjack.parsers.factory import (
    ParserFactory,
    ParsingError,
    strip_non_error_output,
)
from crackerjack.services.ai_fix_progress import AIFixProgressManager
from crackerjack.services.cache import CrackerjackCache
from crackerjack.services.import_resolution import get_safe_import_spec
from crackerjack.services.pycharm_mcp_integration import (
    MahavishnuPycharmMCPClient,
    PyCharmMCPAdapter,
)
from crackerjack.services.refurb_fixer import SafeRefurbFixer
from crackerjack.utils.issue_detection import extract_issue_lines

logger = logging.getLogger(__name__)

_HOOK_SCOPES: dict[str, tuple[str, ...]] = {
    "refurb": ("**/*.py", "**/*.pyi"),
    "complexipy": ("**/*.py",),
    "pyscn": ("**/*.py",),
    "zuban": ("**/*.py", "**/*.pyi"),
    "ruff": ("**/*.py", "**/*.pyi"),
    "ruff-format": ("**/*.py", "**/*.pyi"),
    "semgrep": ("**/*.py",),
    "bandit": ("**/*.py",),
    "check-ast": ("**/*.py",),
    "linkcheckmd": ("**/*.md", "**/*.markdown"),
    "lychee": ("**/*.md", "**/*.markdown"),
    "check-local-links": ("**/*.md", "**/*.markdown"),
    "check-jsonschema": ("**/*.json",),
    "check-yaml": ("**/*.yml", "**/*.yaml"),
    "check-toml": ("**/*.toml",),
    "check-json": ("**/*.json",),
    "format-json": ("**/*.json",),
    "creosote": (
        "**/pyproject.toml",
        "**/uv.lock",
        "**/requirements*.txt",
        "**/*.py",
    ),
    "pip-audit": (
        "**/pyproject.toml",
        "**/uv.lock",
        "**/requirements*.txt",
    ),
    "gitleaks": ("**",),
    "check-added-large-files": ("**",),
    "pytest": ("**/*.py", "**/tests/**"),
}


class AutofixCoordinator:
    def __init__(
        self,
        console: Console | None = None,
        pkg_path: Path | None = None,
        logger: LoggerProtocol | None = None,
        max_iterations: int | None = None,
        coordinator_factory: Callable[
            [AgentContext, CrackerjackCache], AgentCoordinatorProtocol
        ]
        | None = None,
        enable_fancy_progress: bool = True,
        enable_agent_bars: bool = True,
        adapter_learner_integration: t.Any | None = None,
        pycharm_adapter: PyCharmMCPAdapter | None = None,
        event_bus: AIFixEventBus | None = None,
        preflight_config: PreflightConfig | None = None,
    ) -> None:
        self.console = console or Console()
        self.pkg_path = pkg_path or Path.cwd()
        self._event_bus: AIFixEventBus = event_bus or t.cast(
            AIFixEventBus, build_default_bus(self.pkg_path)
        )
        self._run_id: str = ""
        self._preflight_config = preflight_config or PreflightConfig()
        self._adapter_learner_integration = adapter_learner_integration

        self.logger = logger or logging.getLogger("crackerjack.autofix") # type: ignore[assignment]
        self._max_iterations = max_iterations
        self._coordinator_factory = coordinator_factory
        self._global_attempt_count = 0
        self._output_validator: OutputValidator = OutputValidator()
        self._working_tree_snapshot: WorkingTreeSnapshot | None = None
        self._parser_factory = ParserFactory()

        self.progress_manager = AIFixProgressManager(
            console=self.console,
            enabled=enable_fancy_progress,
            enable_agent_bars=enable_agent_bars,
        )

        self._collected_errors: list[dict[str, str]] = []
        self._success_count = 0
        self._total_count = 0
        self._prompt_evolution = get_prompt_evolution()
        self._failed_issue_keys: set[str] = set()
        self._active_ai_fix_scope_files: set[str] = set()
        self._stdout_hash_cache: dict[str, str] = {}
        self._pycharm_adapter = pycharm_adapter or self._create_pycharm_adapter()

    def _create_pycharm_adapter(self) -> PyCharmMCPAdapter | None:
        if os.environ.get("CRACKERJACK_ENABLE_PYCHARM_MCP", "0") != "1":
            return None

        try:
            client = MahavishnuPycharmMCPClient()
            return PyCharmMCPAdapter(
                mcp_client=client,
                allowed_roots=(self.pkg_path, Path("/tmp")),
            )
        except Exception as e:
            logger.debug("PyCharm MCP adapter unavailable: %s", e)
            return None

    def _collect_error(
        self, error_type: str, message: str, file_path: str = ""
    ) -> None:
        self._collected_errors.append(
            {
                "type": error_type,
                "message": message,
                "file": file_path,
            }
        )

    def record_fix_attempt(
        self,
        issue: Issue,
        attempted_fix: str,
        success: bool,
        context: dict[str, str] | None = None,
    ) -> None:
        if success:
            pass
        else:
            self._prompt_evolution.record_failed_fix(
                issue=issue,
                attempted_fix=attempted_fix,
                failure_reason="Fix validation failed",
                context=context,
            )

    def get_evolved_prompt(self, issue: Issue, base_prompt: str) -> str:
        return self._prompt_evolution.get_evolved_prompt(issue, base_prompt)

    def _display_error_summary(self) -> None:
        if not self._collected_errors:
            return

        import rich.box
        from rich.panel import Panel
        from rich.table import Table

        error_groups: dict[str, list[dict[str, str]]] = {}
        for error in self._collected_errors:
            error_type = error["type"]
            if error_type not in error_groups:
                error_groups[error_type] = []
            error_groups[error_type].append(error)

        table = Table(
            show_header=True,
            header_style="bold red",
            box=rich.box.SIMPLE,
            width=66,
        )
        table.add_column("Error Type", style="red")
        table.add_column("Count", justify="right")
        table.add_column("Files Affected", style="dim")

        for error_type, errors in error_groups.items():
            files = {e["file"] for e in errors if e["file"]}
            files_str = ", ".join(sorted(str(f) for f in files)[:3]) # noqa: FURB123 (Path objects must be coerced)
            if len(files) > 3:
                files_str += f" (+{len(files) - 3} more)"
            table.add_row(error_type, str(len(errors)), files_str or "N/A")

        self.console.print("\n")
        self.console.print(
            Panel(
                table,
                title=f"[bold red]AI Fix Errors Summary[/bold red] ({len(self._collected_errors)} total)",
                border_style="red",
                width=70,
            )
        )

        if self._total_count > 0:
            rate = (self._success_count / self._total_count) * 100
            self.console.print(
                f"[dim]Success rate: {self._success_count}/{self._total_count} ({rate:.1f}%)[/dim]"
            )

        self._display_detailed_errors(error_groups)

        self._log_errors_to_file(error_groups)

    def _display_detailed_errors(
        self, error_groups: dict[str, list[dict[str, str]]]
    ) -> None:
        from rich.panel import Panel
        from rich.text import Text

        for error_type, errors in error_groups.items():
            if not errors:
                continue

            detailed_text = Text()
            for i, error in enumerate(errors[:3]):
                file_info = f"[{error['file']}] " if error.get("file") else ""
                message = error.get("message", "No details")

                if len(message) > 200:
                    message = message[:197] + "..."
                detailed_text.append(f"\n{i + 1}. {file_info}{message}\n", style="dim")

            if errors:
                remaining = len(errors) - 3
                if remaining > 0:
                    detailed_text.append(
                        f"\n ... and {remaining} more {error_type.lower()}s\n",
                        style="dim italic",
                    )

                self.console.print(
                    Panel(
                        detailed_text,
                        title=f"[bold yellow]{error_type} Details[/bold yellow] (showing {min(3, len(errors))} of {len(errors)})",
                        border_style="yellow",
                        width=70,
                    )
                )

    def _log_errors_to_file(
        self, error_groups: dict[str, list[dict[str, str]]]
    ) -> None:
        import json
        import tempfile
        from datetime import datetime

        log_dirs = [
            self.pkg_path / ".crackerjack" / "logs",
            Path(tempfile.gettempdir()) / "crackerjack" / "logs",
        ]
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        log_data = {
            "timestamp": timestamp,
            "total_errors": len(self._collected_errors),
            "success_count": self._success_count,
            "total_count": self._total_count,
            "success_rate": (
                round((self._success_count / self._total_count) * 100, 1)
                if self._total_count > 0
                else 0
            ),
            "error_groups": error_groups,
        }

        for log_dir in log_dirs:
            try:
                log_dir.mkdir(parents=True, exist_ok=True)
                log_file = log_dir / f"ai-fix-errors-{timestamp}.json"

                with log_file.open("w", encoding="utf-8") as f:
                    json.dump(log_data, f, indent=2, default=str)

                display_path = (
                    log_file.relative_to(self.pkg_path)
                    if log_file.is_relative_to(self.pkg_path)
                    else log_file
                )
                self.console.print(f"[dim]📝 Detailed error log: {display_path}[/dim]")
                return
            except Exception as e:
                self.logger.warning(f"Failed to write error log at {log_dir}: {e}")

    async def apply_autofix_for_hooks(
        self, mode: str, hook_results: list[object]
    ) -> bool:

        self._collected_errors = []
        self._success_count = 0
        self._total_count = 0
        self._run_id = AIFixEventBus.new_run_id()


        try:
            self._working_tree_snapshot = WorkingTreeSnapshot(self.pkg_path).take()
        except Exception as snapshot_err:
            self.logger.warning(
                f"Could not take working-tree snapshot: {snapshot_err}; "
                f"continuing without run-level checkpoint"
            )
            self._working_tree_snapshot = None

        initial_issue_count = self.progress_manager.compute_hook_total(hook_results)
        await self._event_bus.emit(
            RunStarted(
                run_id=self._run_id,
                iteration=0,
                stage=mode,
                initial_issue_count=initial_issue_count,
            )
        )

        try:
            if self._should_skip_autofix(hook_results):
                return False

            if mode == "comprehensive":
                failed_count = sum(
                    1
                    for r in hook_results
                    if self._validate_hook_result(r)
                    and getattr(r, "status", "").lower()
                    in {"failed", "timeout", "error"}
                )
                await self._event_bus.emit(
                    RunStarted(
                        run_id=self._run_id,
                        iteration=0,
                        stage=mode,
                        initial_issue_count=failed_count,
                    )
                )

            if mode == "fast":
                result = await self._apply_fast_stage_fixes(hook_results)
            elif mode == "comprehensive":
                result = await self._apply_comprehensive_stage_fixes(hook_results)
            else:
                self.logger.warning(f"Unknown autofix mode: {mode}")
                result = False
        except Exception:
            self.logger.exception("Error applying autofix")
            result = False
        finally:
            self._display_error_summary()

        return result

    async def apply_fast_stage_fixes(
        self, hook_results: Sequence[object] | None = None
    ) -> bool:
        return await self._apply_fast_stage_fixes(hook_results)

    async def apply_comprehensive_stage_fixes(
        self, hook_results: Sequence[object]
    ) -> bool:
        return await self._apply_comprehensive_stage_fixes(hook_results)

    def run_fix_command(self, cmd: list[str], description: str) -> bool:
        return self._run_fix_command(cmd, description)

    def check_tool_success_patterns(self, cmd: list[str], result: object) -> bool:
        return self._check_tool_success_patterns(cmd, result)

    def validate_fix_command(self, cmd: list[str]) -> bool:
        return self._validate_fix_command(cmd)

    def validate_hook_result(self, result: object) -> bool:
        return self._validate_hook_result(result)

    def should_skip_autofix(self, hook_results: Sequence[object]) -> bool:
        return self._should_skip_autofix(hook_results)

    async def _apply_fast_stage_fixes(
        self, hook_results: Sequence[object] | None = None
    ) -> bool:
        ai_agent_enabled = os.environ.get("AI_AGENT") == "1"

        if ai_agent_enabled and hook_results:
            self.logger.info(
                "AI agent mode enabled for fast stage, attempting AI-based fixing"
            )
            return await self._apply_ai_agent_fixes(hook_results, stage="fast")

        return await self._execute_fast_fixes()

    async def _apply_comprehensive_stage_fixes(
        self, hook_results: Sequence[object]
    ) -> bool:
        self._failed_issue_keys = set()
        if not await self._execute_fast_fixes():
            return False

        ai_agent_enabled = os.environ.get("AI_AGENT") == "1"

        if ai_agent_enabled:
            self.logger.info("AI agent mode enabled, attempting AI-based fixing")
            return await self._apply_ai_agent_fixes(hook_results, stage="comprehensive")

        failed_hooks = self._extract_failed_hooks(hook_results)
        if not failed_hooks:
            return True

        hook_specific_fixes = self._get_hook_specific_fixes(failed_hooks)

        all_successful = True
        for cmd, description in hook_specific_fixes:
            if not self._run_fix_command(cmd, description):
                all_successful = False

        return all_successful

    def _extract_failed_hooks(self, hook_results: Sequence[object]) -> set[str]:
        failed_hooks: set[str] = set()
        for result in hook_results:
            if (
                self._validate_hook_result(result)
                and getattr(result, "status", "").lower() == "failed"
            ):
                name = getattr(result, "name", "")
                if isinstance(name, str):
                    failed_hooks.add(name)
        return failed_hooks

    def _get_hook_specific_fixes(
        self,
        failed_hooks: set[str],
    ) -> list[tuple[list[str], str]]:
        fixes: list[tuple[list[str], str]] = []

        if "bandit" in failed_hooks:
            fixes.append((["uv", "run", "bandit", "-r", "."], "bandit analysis"))

        if "zuban" in failed_hooks:
            self._fix_zuban_missing_imports_in_mypy_ini()

        if "ty" in failed_hooks:
            fixes.append(
                (
                    ["uv", "run", "python", "-m", "crackerjack.tools.ty_cleanup"],
                    "remove unused type ignores and redundant casts",
                )
            )

        if "cohesion" in failed_hooks:
            fixes.append(
                (
                    [
                        "echo",
                        "cohesion issues require AI_AGENT=1 (refactor classes with low cohesion)",
                    ],
                    "cohesion: requires AI agent",
                )
            )

        if "pymetrica" in failed_hooks:
            fixes.append(
                (
                    [
                        "echo",
                        "pymetrica issues require AI_AGENT=1 (interpret maintainability metrics)",
                    ],
                    "pymetrica: requires AI agent",
                )
            )

        return fixes

    async def _execute_fast_fixes(self) -> bool:

        fixes = [
            (["uv", "run", "ruff", "check", "--fix", "."], "fix code style"),
            (["uv", "run", "ruff", "format", "."], "format code"),
        ]

        all_successful = True
        for cmd, description in fixes:
            if not await asyncio.to_thread(self._run_fix_command, cmd, description):
                all_successful = False

        return all_successful

    def _strip_jsonc_comments_from_failed_json_files(self) -> bool:
        from crackerjack.tools._git_utils import get_files_by_extension

        jsonc_files: list[Path] = []
        try:
            jsonc_files = get_files_by_extension(
                [".json"], use_git=True, root=self.pkg_path
            )
        except Exception:
            self.logger.exception("Failed to find JSON files for JSONC stripping")
            return False

        if not jsonc_files:
            self.logger.info("No JSON files found to check for JSONC comments")
            return True

        self.logger.info(f"Checking {len(jsonc_files)} JSON files for JSONC comments")

        all_successful = True
        for json_file in jsonc_files:
            stripped, had_comments = self._strip_jsonc_comments(json_file)
            self.logger.debug(f"{json_file}: had_comments={had_comments}")
            if had_comments:
                try:
                    json.loads(stripped)
                    json_file.write_text(stripped, encoding="utf-8")
                    self.logger.info(f"Stripped JSONC comments from {json_file}")
                except json.JSONDecodeError as e:
                    self.logger.warning(
                        f"Stripped content from {json_file} is not valid JSON: {e}"
                    )
                    all_successful = False

        return all_successful

    def _strip_jsonc_comments(self, file_path: Path) -> tuple[str, bool]:
        try:
            content = file_path.read_text(encoding="utf-8")
        except Exception:
            return "", False

        lines = content.split("\n")
        new_lines = []
        had_comments = False
        for line in lines:
            comment_start = -1
            in_string = False
            i = 0
            while i < len(line):
                c = line[i]
                if c == '"' and (i == 0 or line[i - 1] != "\\"):
                    in_string = not in_string
                elif not in_string and c == "#":
                    comment_start = i
                    break
                i += 1

            if comment_start >= 0:
                had_comments = True
                new_lines.append(line[:comment_start].rstrip())
            else:
                new_lines.append(line)

        return "\n".join(new_lines), had_comments

    def _run_fix_command(self, cmd: list[str], description: str) -> bool:
        if not self._validate_fix_command(cmd):
            self.logger.warning(f"Invalid fix command: {cmd}")
            return False

        try:
            self.logger.info(f"Running fix command: {description}")
            result = subprocess.run(
                cmd,
                check=False,
                cwd=self.pkg_path,
                env=self._get_fix_environment(),
                capture_output=True,
                text=True,
                timeout=300,
            )
            return self._handle_command_result(result, description)
        except Exception:
            self.logger.exception("Error running fix command: %s", description)
            return False

    def _handle_command_result(
        self,
        result: subprocess.CompletedProcess[str],
        description: str,
    ) -> bool:
        if result.returncode == 0:
            self.logger.info(f"Fix command succeeded: {description}")
            return True

        if description == "fix code style" and result.returncode == 1:
            self.logger.info(
                "Fix command applied partial changes: %s (ruff returned 1 with remaining diagnostics)",
                description,
            )
            return True

        if self._is_successful_fix(result):
            self.logger.info(f"Fix command applied changes: {description}")
            return True

        stderr_excerpt = result.stderr[:200] if result.stderr else "No stderr"
        self.logger.warning(
            "Fix command failed: %s (returncode=%s, stderr=%s)",
            description,
            result.returncode,
            stderr_excerpt,
        )
        return False

    def _get_fix_environment(self) -> dict[str, str]:
        env = os.environ.copy()
        env.update(self._get_uv_environment_paths())
        return env

    def _get_uv_environment_paths(self) -> dict[str, str]:
        import tempfile

        root_dir = self.pkg_path / ".crackerjack" / "uv"
        try:
            if root_dir.exists():
                shutil.rmtree(root_dir)
            cache_dir = root_dir / "cache"
            data_dir = root_dir / "data"
            tool_dir = root_dir / "tools"
            cache_dir.mkdir(parents=True, exist_ok=True)
            data_dir.mkdir(parents=True, exist_ok=True)
            tool_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            root_dir = Path(tempfile.gettempdir()) / "crackerjack" / "uv"
            cache_dir = root_dir / "cache"
            data_dir = root_dir / "data"
            tool_dir = root_dir / "tools"
            cache_dir.mkdir(parents=True, exist_ok=True)
            data_dir.mkdir(parents=True, exist_ok=True)
            tool_dir.mkdir(parents=True, exist_ok=True)

        ruff_cache_dir = cache_dir / "ruff"
        pip_cache_dir = cache_dir / "pip"
        ruff_cache_dir.mkdir(parents=True, exist_ok=True)
        pip_cache_dir.mkdir(parents=True, exist_ok=True)

        return {
            "UV_CACHE_DIR": str(cache_dir),
            "UV_TOOL_DIR": str(tool_dir),
            "XDG_CACHE_HOME": str(cache_dir),
            "XDG_DATA_HOME": str(data_dir),
            "RUFF_CACHE_DIR": str(ruff_cache_dir),
            "PIP_CACHE_DIR": str(pip_cache_dir),
        }

    def _is_successful_fix(self, result: subprocess.CompletedProcess[str]) -> bool:
        success_indicators = [
            "fixed",
            "formatted",
            "reformatted",
            "updated",
            "changed",
            "removed",
        ]

        if hasattr(result, "stdout") and hasattr(result, "stderr"):
            stdout = getattr(result, "stdout", "") or ""
            stderr = getattr(result, "stderr", "") or ""

            if not isinstance(stdout, str):
                stdout = str(stdout)
            if not isinstance(stderr, str):
                stderr = str(stderr)
            output = stdout + stderr
        else:
            output = str(result)

        output_lower = output.lower()

        return any(indicator in output_lower for indicator in success_indicators)

    def _check_tool_success_patterns(self, cmd: list[str], result: object) -> bool:
        if not cmd:
            return False

        if hasattr(result, "returncode"):
            return self._check_process_result_success(result)

        if isinstance(result, str):
            return self._check_string_result_success(result)

        return False

    def _check_process_result_success(self, result: object) -> bool:
        if getattr(result, "returncode", 1) == 0:
            return True

        output = self._extract_process_output(result)
        return self._has_success_patterns(output)

    def _extract_process_output(self, result: object) -> str:
        stdout = getattr(result, "stdout", "") or ""
        stderr = getattr(result, "stderr", "") or ""

        if not isinstance(stdout, str):
            stdout = str(stdout)
        if not isinstance(stderr, str):
            stderr = str(stderr)

        return stdout + stderr

    def _check_string_result_success(self, result: str) -> bool:
        return self._has_success_patterns(result)

    def _has_success_patterns(self, output: str) -> bool:
        if not output:
            return False

        success_patterns = [
            "fixed",
            "formatted",
            "reformatted",
            "would reformat",
            "fixing",
        ]

        output_lower = output.lower()
        return any(pattern in output_lower for pattern in success_patterns)

    def _validate_fix_command(self, cmd: list[str]) -> bool:
        if not cmd or len(cmd) < 2:
            return False

        if cmd[0] != "uv":
            return False

        if cmd[1] != "run":
            return False

        allowed_tools = [
            "bandit",
            "trailing-whitespace",
            "ruff",
            "ruff-format",
            "ty",
            "pyrefly",
        ]

        return bool(len(cmd) > 2 and cmd[2] in allowed_tools)

    def _should_retry_quality_validation(self, file_path: str, feedback: str) -> bool:
        if not file_path.endswith((".py", ".pyi")):
            return False

        feedback_lower = feedback.lower()
        fixable_markers = (
            "ruff",
            "refurb",
            "f401",
            "f821",
            "e501",
            "line too long",
            "unused import",
            "undefined name",
        )
        return any(marker in feedback_lower for marker in fixable_markers)

    def _run_targeted_python_fixes(self, file_path: str) -> bool:
        commands = [
            (["uv", "run", "ruff", "check", "--fix", file_path], "ruff check --fix"),
            (["uv", "run", "ruff", "format", file_path], "ruff format"),
        ]

        all_successful = True
        for cmd, description in commands:
            if not self._run_fix_command(cmd, description):
                all_successful = False
        return all_successful

    def _should_retry_missing_imports(self, feedback: str) -> bool:
        feedback_lower = feedback.lower()
        return "f821" in feedback_lower and "undefined name" in feedback_lower

    def _should_retry_refurb_validation(self, feedback: str) -> bool:
        feedback_lower = feedback.lower()
        refurb_markers = ("refurb", "furb113", "furb126")
        return any(marker in feedback_lower for marker in refurb_markers)

    def _extract_undefined_names(self, feedback: str) -> list[str]:
        names: list[str] = []
        for match in re.finditer(
            r"Undefined name [`'\"]([^`'\"]+)[`'\"]",
            feedback,
            re.IGNORECASE,
        ):
            name = match.group(1).strip()
            if name and name not in names:
                names.append(name)
        return names

    def _missing_import_spec(
        self, undefined_name: str
    ) -> tuple[str, str | None, str] | None:
        spec = get_safe_import_spec(undefined_name)
        if spec is None:
            return None
        return spec.module_name, spec.symbol_name, spec.import_line

    def _has_import(self, content: str, module: str, symbol: str | None = None) -> bool:
        if symbol is None:
            pattern = rf"^\s*import\s+{re.escape(module)}(?:\s+as\s+\w+)?(?:\s*, |\s*$)"
            return bool(re.search(pattern, content, re.MULTILINE))

        pattern = (
            rf"^\s*from\s+{re.escape(module)}\s+import\s+.*\b{re.escape(symbol)}\b"
        )
        return bool(re.search(pattern, content, re.MULTILINE))

    def _find_import_insertion_index(self, lines: list[str]) -> int:
        start_index = 0
        try:
            tree = ast.parse("\n".join(lines))
        except SyntaxError:
            tree = None

        if tree and tree.body:
            first_node = tree.body[0]
            docstring = ast.get_docstring(tree, clean=False)
            if docstring and isinstance(first_node, ast.Expr):
                end_lineno = getattr(first_node, "end_lineno", first_node.lineno)
                start_index = end_lineno

        insert_index = start_index
        saw_import = False
        for i in range(start_index, len(lines)):
            stripped = lines[i].strip()
            if stripped.startswith(("import ", "from ")):
                saw_import = True
                insert_index = i + 1
                continue
            if not stripped or stripped.startswith("#"):
                continue
            if saw_import:
                return insert_index
            return i

        return insert_index

    def _insert_import_into_content(self, content: str, import_line: str) -> str:
        if import_line in content:
            return content

        lines = content.split("\n")
        insert_index = self._find_import_insertion_index(lines)
        if insert_index < 0:
            insert_index = 0
        if insert_index > len(lines):
            insert_index = len(lines)

        lines.insert(insert_index, import_line)
        return "\n".join(lines)

    def _normalize_future_import_position(self, content: str) -> str:
        had_trailing_newline = content.endswith("\n")
        lines = content.split("\n")
        future_lines = [
            line for line in lines if line.strip().startswith("from __future__ import ")
        ]
        if not future_lines:
            return content

        non_future_lines = [
            line
            for line in lines
            if not line.strip().startswith("from __future__ import ")
        ]
        insert_at = 0
        if non_future_lines and non_future_lines[0].strip().startswith(('"""', "'''")):
            insert_at = 1
            while (
                insert_at < len(non_future_lines)
                and non_future_lines[insert_at].strip()
            ):
                insert_at += 1
            if (
                insert_at < len(non_future_lines)
                and not non_future_lines[insert_at].strip()
            ):
                insert_at += 1

        rebuilt = (
            non_future_lines[:insert_at] + future_lines + non_future_lines[insert_at:]
        )
        content = "\n".join(rebuilt)
        if had_trailing_newline and not content.endswith("\n"):
            content += "\n"
        return content

    def _apply_missing_import_repair(self, file_path: str, feedback: str) -> bool:
        if not file_path.endswith((".py", ".pyi")):
            return False

        names = self._extract_undefined_names(feedback)
        if not names:
            return False

        path = Path(file_path)
        try:
            content = path.read_text(encoding="utf-8")
        except OSError:
            return False

        import_lines: list[str] = []
        for name in names:
            spec = self._missing_import_spec(name)
            if spec is None:
                continue
            module_name, symbol_name, import_line = spec
            if self._has_import(content, module_name, symbol_name):
                continue
            if import_line not in import_lines:
                import_lines.append(import_line)

        if not import_lines:
            return False

        new_content = content
        for import_line in import_lines:
            new_content = self._insert_import_into_content(new_content, import_line)
        new_content = self._normalize_future_import_position(new_content)
        if new_content == content:
            return False

        path.write_text(new_content, encoding="utf-8")
        self.logger.info(
            "Applied deterministic import repair to %s for: %s",
            file_path,
            ", ".join(names),
        )
        return True

    def _run_targeted_refurb_fixes(self, file_path: str) -> bool:
        if not file_path.endswith(".py"):
            return False

        path = Path(file_path)
        if not path.exists():
            return False

        fixer = SafeRefurbFixer()
        fixes = fixer.fix_file(path)
        if fixes <= 0:
            return False

        self.logger.info(
            "Applied deterministic refurb repair to %s for %s fix(es)",
            file_path,
            fixes,
        )
        return True

    def _validate_hook_result(self, result: object) -> bool:
        name = getattr(result, "name", None)
        status = getattr(result, "status", None)

        if not name or not isinstance(name, str):
            return False

        if not status or not isinstance(status, str):
            return False

        valid_statuses = {"passed", "failed", "skipped", "error", "timeout"}
        return status.lower() in valid_statuses

    def _should_skip_autofix(self, hook_results: Sequence[object]) -> bool:
        failed_results = [
            result
            for result in hook_results
            if self._validate_hook_result(result)
            and getattr(result, "status", "").lower() in {"failed", "timeout", "error"}
        ]
        candidate_results = failed_results or hook_results.copy()
        if not candidate_results: # type: ignore
            return False

        import_error_results = [
            result
            for result in candidate_results
            if self._has_import_errors(self._extract_raw_output(result))
        ]
        if not import_error_results:
            return False

        if len(import_error_results) == len(candidate_results):
            self.logger.info(
                "Skipping autofix because all failed hooks are import errors"
            )
            return True

        self.logger.info(
            "Continuing autofix despite import errors because other hooks failed too"
        )
        return False

    def _extract_raw_output(self, result: object) -> str:
        output = getattr(result, "output", None)
        error = getattr(result, "error", None)
        error_message = getattr(result, "error_message", None)

        output = str(output) if output else ""
        error = str(error) if error else ""
        error_message = str(error_message) if error_message else ""

        return output + error + error_message

    def _has_import_errors(self, raw_output: str) -> bool:
        if not raw_output:
            return False
        output_lower = raw_output.lower()
        return "importerror" in output_lower or "modulenotfounderror" in output_lower

    def _handle_zero_issues_case(
        self, iteration: int, stage: str = "fast"
    ) -> bool | None:
        if iteration > 0:
            self.logger.debug("Verifying issue resolution...")
            verification_issues = self._collect_current_issues(stage=stage)
            if verification_issues:
                count = len(verification_issues)
                issue_word = "issue" if count == 1 else "issues"
                self.logger.warning(
                    f"False positive detected: {count} {issue_word} remain"
                )

                return None
            else:
                self._report_iteration_success(iteration)
                return True
        else:
            self.logger.debug("Iteration 0: No issues detected from hook results")
            return None

    def _get_iteration_issues(
        self,
        iteration: int,
        hook_results: Sequence[object],
        stage: str = "fast",
    ) -> list[Issue]:
        self.logger.debug(
            f"Iteration {iteration}: Parsing {len(hook_results)} hook results"
        )
        issues = self._parse_hook_results_to_issues(hook_results)
        self.logger.info(
            f"Iteration {iteration}: Extracted {len(issues)} issues from hook results"
        )
        return issues

    def _check_coverage_regression(self, hook_results: Sequence[object]) -> list[Issue]:
        coverage_issues: list[Issue] = []

        ratchet_path = self.pkg_path / ".coverage-ratchet.json"
        if not ratchet_path.exists():
            self.logger.debug("No coverage ratchet file found, skipping coverage check")
            return coverage_issues

        try:
            with ratchet_path.open() as f:
                ratchet_data = json.load(f)

            current_coverage = ratchet_data.get("current_coverage", 0)
            baseline = ratchet_data.get("baseline_coverage", 0)
            tolerance = ratchet_data.get("tolerance_margin", 2.0)

            if current_coverage < (baseline - tolerance):
                gap = baseline - current_coverage
                self.logger.warning(
                    f"📉 Coverage regression detected: {current_coverage:.1f}% "
                    f"(baseline: {baseline:.1f}%, gap: {gap:.1f}%)"
                )

                coverage_issues.append(
                    Issue(
                        type=IssueType.COVERAGE_IMPROVEMENT,
                        severity=Priority.HIGH,
                        message=f"Coverage regression: {current_coverage:.1f}% (baseline: {baseline:.1f}%, gap: {gap:.1f}%)",
                        file_path=ratchet_path, # type: ignore
                        line_number=None,
                        stage="coverage-ratchet",
                        details=[
                            f"baseline_coverage: {baseline:.1f}%",
                            f"current_coverage: {current_coverage:.1f}%",
                            f"regression_amount: {gap:.1f}%",
                            f"tolerance_margin: {tolerance:.1f}%",
                            f"action: Add tests to increase coverage by {gap:.1f}%",
                        ],
                    )
                )
        except Exception as e:
            self._collect_error("Coverage Error", str(e))

        return coverage_issues

    def _should_skip_console_print(self) -> bool:
        return self.progress_manager.is_in_progress()

    def _report_iteration_success(self, iteration: int) -> None:

        if not self._should_skip_console_print():
            self.console.print(
                f"[green]✓ All issues resolved in {iteration} iteration(s)![/green]"
            )
            self.console.print()
        self.logger.info(f"All issues resolved in {iteration} iteration(s)")

    def _should_stop_on_convergence(
        self,
        current_count: int,
        previous_count: float,
        no_progress_count: int,
        fixes_applied: int = 0,
    ) -> bool:
        convergence_threshold = self._get_convergence_threshold()

        del fixes_applied

        if no_progress_count >= convergence_threshold:
            issue_word = "issue" if current_count == 1 else "issues"

            if not self._should_skip_console_print():
                self.console.print(
                    f"[yellow]⚠ No progress for {convergence_threshold} iterations "
                    f"({current_count} {issue_word} remain)[/yellow]"
                )
            self.logger.warning(
                f"No progress for {convergence_threshold} iterations, "
                f"{current_count} {issue_word} remain"
            )
            return True
        return False

    def _update_progress_count(
        self,
        current_count: int,
        previous_count: float,
        no_progress_count: int,
        fixes_applied: int = 0,
    ) -> int:

        del fixes_applied

        if current_count < previous_count:
            resolved = previous_count - current_count
            self.logger.info(
                f"✓ Progress made: {resolved} issue(s) resolved, "
                f"resetting convergence counter"
            )
            return 0

        return no_progress_count + 1

    def _report_iteration_progress(
        self,
        iteration: int,
        issue_count: int,
    ) -> None:
        issue_word = "issue" if issue_count == 1 else "issues"

        if not self._should_skip_console_print():
            self.console.print(
                f"[cyan]→ Iteration {iteration + 1}: "
                f"{issue_count} {issue_word} to fix[/cyan]"
            )
            self.console.print()
        self.logger.info(
            f"Iteration {iteration + 1}: {issue_count} {issue_word} to fix"
        )

    def _handle_partial_progress(
        self, fix_result: FixResult, fixes_count: int, remaining_count: int
    ) -> bool:
        self.logger.info(
            f"Fixed {fixes_count} issues with confidence {fix_result.confidence:.2f}"
        )

        if remaining_count == 0:
            self.logger.info("All issues fixed")
            return True

        issue_word = "issue" if remaining_count == 1 else "issues"

        if not self._should_skip_console_print():
            self.console.print(
                f"[yellow]⚠ Partial progress: {fixes_count} fixes applied, "
                f"{remaining_count} {issue_word} remain[/yellow]"
            )
        self.logger.info(
            f"Partial progress: {fixes_count} fixes applied, "
            f"{remaining_count} {issue_word} remain"
        )

        return True

    def _report_max_iterations_reached(
        self, max_iterations: int, stage: str = "fast"
    ) -> bool:
        final_issue_count = len(self._collect_current_issues(stage=stage))
        issue_word = "issue" if final_issue_count == 1 else "issues"

        if not self._should_skip_console_print():
            self.console.print(
                f"[yellow]⚠ Reached {max_iterations} iterations with "
                f"{final_issue_count} {issue_word} remaining[/yellow]"
            )
            self.console.print()
        self.logger.warning(
            f"Reached {max_iterations} iterations with {final_issue_count} {issue_word} remaining"
        )
        return False

    def _parse_hook_results_to_issues(
        self, hook_results: Sequence[object]
    ) -> list[Issue]:
        self.logger.debug(f"Parsing {len(hook_results)} hook results for issues")

        issues, parsed_counts_by_hook = self._parse_all_hook_results(hook_results)
        self._update_hook_issue_counts(hook_results, parsed_counts_by_hook)
        unique_issues = self._deduplicate_issues(issues)

        self._log_parsing_summary(len(issues), len(unique_issues))
        return unique_issues

    def _parse_all_hook_results(
        self, hook_results: Sequence[object]
    ) -> tuple[list[Issue], dict[str, int]]:
        issues: list[Issue] = []
        parsed_counts_by_hook: dict[str, int] = {}

        for result in hook_results:
            hook_issues = self._parse_single_hook_result(result)
            self._track_hook_issue_count(result, hook_issues, parsed_counts_by_hook)
            issues.extend(hook_issues)

        return issues, parsed_counts_by_hook

    def _run_qa_adapters_for_hooks(
        self, hook_results: Sequence[object]
    ) -> dict[str, QAResult]:
        qa_results: dict[str, QAResult] = {}
        adapter_factory = DefaultAdapterFactory()

        for result in hook_results:
            if not self._should_run_qa_adapter(result):
                continue

            hook_name = getattr(result, "name", "")
            if not hook_name:
                continue

            qa_result = self._run_single_qa_adapter(hook_name, adapter_factory)
            if qa_result is not None:
                qa_results[hook_name] = qa_result

        return qa_results

    def _should_run_qa_adapter(self, result: object) -> bool:
        if not self._validate_hook_result(result):
            return False

        status = getattr(result, "status", "")

        return status.lower() in ("failed", "timeout")

    def _run_single_qa_adapter(
        self, hook_name: str, adapter_factory: DefaultAdapterFactory
    ) -> QAResult | None:
        try:
            adapter = self._get_qa_adapter(hook_name, adapter_factory)
            if adapter is None:
                return None

            if self._is_in_async_context():
                self.logger.debug(
                    f"QA adapter for '{hook_name}' called from async context, "
                    "falling back to raw output parsing"
                )
                return None

            asyncio.run(adapter.init()) # type: ignore
            config = self._create_qa_config(adapter, hook_name)
            check_start = time.monotonic()
            qa_result: QAResult = asyncio.run(adapter.check(config=config)) # type: ignore
            execution_time_ms = int((time.monotonic() - check_start) * 1000)

            if self._adapter_learner_integration is not None:
                with suppress(Exception):
                    self._adapter_learner_integration.track_adapter_execution(
                        adapter_name=hook_name,
                        file_path=str(self.pkg_path),
                        file_size=0,
                        project_context={},
                        success=qa_result.is_success if qa_result else True,
                        execution_time_ms=execution_time_ms,
                        error_type=qa_result.details
                        if qa_result and not qa_result.is_success
                        else None,
                    )

            self._log_qa_adapter_result(hook_name, qa_result)
            return qa_result

        except Exception as e:
            self.logger.warning(
                f"Failed to run QA adapter for '{hook_name}': {e}. "
                f"Will fall back to raw output parsing."
            )
            return None

    def _get_qa_adapter(
        self, hook_name: str, adapter_factory: DefaultAdapterFactory
    ) -> object | None:
        adapter_name = adapter_factory.get_adapter_name(hook_name)
        if not adapter_name:
            self.logger.debug(f"No adapter name mapping for '{hook_name}'")
            return None

        adapter = adapter_factory.create_adapter(adapter_name)
        if adapter is None:
            self.logger.debug(f"No QA adapter available for '{hook_name}'")
            return None

        return adapter

    def _is_in_async_context(self) -> bool:
        try:
            asyncio.get_running_loop()
            return True
        except RuntimeError:
            return False

    def _create_qa_config(self, adapter: object, hook_name: str) -> QACheckConfig:
        return QACheckConfig(
            check_id=adapter.module_id, # type: ignore
            check_name=hook_name,
            check_type=adapter._get_check_type(), # type: ignore
            enabled=True,
            file_patterns=["**/*.py"],
            timeout_seconds=60,
        )

    def _log_qa_adapter_result(self, hook_name: str, qa_result: QAResult) -> None:
        parsed_issues = getattr(qa_result, "parsed_issues", None)
        issue_count = self._safe_issue_count(parsed_issues)
        if issue_count > 0:
            self.logger.info(
                f"✅ QA adapter for '{hook_name}' found {issue_count} issues"
            )
        else:
            self.logger.debug(f"QA adapter for '{hook_name}' found no issues")

    def _parse_hook_results_to_issues_with_qa(
        self, hook_results: Sequence[object]
    ) -> list[Issue]:
        self.logger.info(f"🔄 Processing {len(hook_results)} hook results...")

        qa_results = self._extract_cached_qa_results(hook_results)

        if len(qa_results) < len(hook_results):
            missing_hooks = [
                r.name # type: ignore
                for r in hook_results
                if getattr(r, "name", "") not in qa_results # type: ignore[untyped]
            ]
            if missing_hooks:
                self.logger.debug(
                    f"Running QA adapters for {len(missing_hooks)} hooks without cache: {missing_hooks}"
                )
                additional_results = self._run_qa_adapters_for_hooks(hook_results)
                qa_results.update(additional_results)

        self.logger.info(
            f"📦 Got QAResult for {len(qa_results)} hooks: {list(qa_results.keys())}"
        )

        issues, parsed_counts_by_hook = self._parse_all_hook_results_with_qa(
            hook_results, qa_results
        )

        self._update_hook_issue_counts(hook_results, parsed_counts_by_hook)
        unique_issues = self._deduplicate_issues(issues)

        self._log_parsing_summary(len(issues), len(unique_issues))
        return unique_issues

    def _extract_cached_qa_results(
        self, hook_results: Sequence[object]
    ) -> dict[str, t.Any]:
        cached_results: dict[str, t.Any] = {}
        cache_hits = 0

        for result in hook_results:
            hook_name = getattr(result, "name", "")
            if not hook_name:
                continue

            qa_result = getattr(result, "qa_result", None)

            parsed_issues = getattr(qa_result, "parsed_issues", None)
            issue_count = self._safe_issue_count(parsed_issues)
            if qa_result and issue_count > 0:
                cached_results[hook_name] = qa_result
                cache_hits += 1
                self.logger.info(
                    f"✅ Cache hit for '{hook_name}': {issue_count} issues "
                    f"(saved re-running QA adapter)"
                )

        if cache_hits > 0:
            self.logger.info(
                f"🎯 QAResult cache: {cache_hits}/{len(hook_results)} hooks "
                f"({cache_hits / len(hook_results) * 100:.0f}% hit rate)"
            )

        return cached_results

    def _safe_issue_count(self, parsed_issues: t.Any) -> int:
        if parsed_issues is None:
            return 0
        try:
            return len(parsed_issues)
        except TypeError:
            return 0

    def _parse_all_hook_results_with_qa(
        self, hook_results: Sequence[object], qa_results: dict[str, QAResult]
    ) -> tuple[list[Issue], dict[str, int]]:
        issues: list[Issue] = []
        parsed_counts_by_hook: dict[str, int] = {}

        for result in hook_results:
            hook_name = getattr(result, "name", "")
            if not hook_name:
                continue

            status = getattr(result, "status", "")
            if (
                isinstance(status, str)
                and status
                and status.lower() not in ("failed", "timeout")
            ):
                self.logger.debug(
                    f"Skipping hook '{hook_name}' with status '{status}' (not failed/timeout)"
                )
                continue

            qa_result = qa_results.get(hook_name)
            raw_output = self._extract_raw_output(result)

            if qa_result and qa_result.parsed_issues:
                hook_issues = self._convert_parsed_issues_to_issues(
                    hook_name, qa_result.parsed_issues
                )
                self.logger.info(
                    f"✅ Used QAResult for '{hook_name}': {len(hook_issues)} issues"
                )
            else:
                hook_issues = self._parse_hook_to_issues(
                    hook_name, raw_output, qa_result
                )
                self.logger.info(
                    f"🔄 Fallback to raw output parsing for '{hook_name}': "
                    f"{len(hook_issues)} issues"
                )

            self._track_hook_issue_count(result, hook_issues, parsed_counts_by_hook)
            issues.extend(hook_issues)

        return issues, parsed_counts_by_hook

    def _track_hook_issue_count(
        self,
        result: object,
        hook_issues: list[Issue],
        parsed_counts_by_hook: dict[str, int],
    ) -> None:
        if hasattr(result, "name"):
            hook_name = str(result.name)
            if hook_name not in parsed_counts_by_hook:
                parsed_counts_by_hook[hook_name] = 0
            parsed_counts_by_hook[hook_name] += len(hook_issues)

    def _update_hook_issue_counts(
        self, hook_results: Sequence[object], parsed_counts_by_hook: dict[str, int]
    ) -> None:
        for result in hook_results:
            if not (hasattr(result, "name") and hasattr(result, "issues_count")):
                continue

            hook_name = getattr(result, "name")
            if hook_name not in parsed_counts_by_hook:
                continue

            old_count = getattr(result, "issues_count", 0)
            new_count = parsed_counts_by_hook[hook_name]

            if self._should_update_issue_count(result, new_count):
                self._update_single_hook_count(result, hook_name, old_count, new_count)

    def _should_update_issue_count(self, result: object, new_count: int) -> bool:

        return new_count > 0

    def _update_single_hook_count(
        self, result: object, hook_name: str, old_count: int, new_count: int
    ) -> None:
        if old_count == new_count:
            return

        self.logger.debug(
            f"Updated issues_count for '{hook_name}': "
            f"{old_count} → {new_count} (matched to parsed issues)"
        )
        setattr(result, "issues_count", new_count)

    def _deduplicate_issues(self, issues: list[Issue]) -> list[Issue]:
        seen: set[tuple[str | None, int | None, str, str]] = set()
        unique_issues: list[Issue] = []

        for issue in issues:
            key = (
                issue.file_path,
                issue.line_number,
                issue.stage,
                issue.message,
            )
            if key not in seen:
                seen.add(key)
                unique_issues.append(issue)

        return unique_issues

    def _log_parsing_summary(self, raw_count: int, unique_count: int) -> None:
        if raw_count != unique_count:
            self.logger.info(
                f"Deduplicated issues: {raw_count} raw -> {unique_count} unique"
            )
        else:
            self.logger.info(f"Total issues extracted from all hooks: {unique_count}")

    def _parse_single_hook_result(self, result: object) -> list[Issue]:
        if not self._validate_hook_result(result):
            return []

        status = getattr(result, "status", "")

        if status.lower() not in ("failed", "timeout"):
            self.logger.debug(
                f"Skipping hook with status '{status}' (not failed/timeout)"
            )
            return []

        hook_name = getattr(result, "name", "")
        if not hook_name:
            self.logger.warning("Hook result has no name attribute")
            return []

        self.logger.debug(f"Parsing hook result: name='{hook_name}', status='{status}'")

        raw_output = self._extract_raw_output(result)
        self._log_hook_parsing_start(hook_name, result, raw_output)

        hook_issues = self._parse_hook_to_issues(hook_name, raw_output)
        self._log_hook_parsing_result(hook_name, hook_issues, raw_output)

        return hook_issues

    def _log_hook_parsing_start(
        self, hook_name: str, result: object, raw_output: str
    ) -> None:
        output = getattr(result, "output", None) or ""
        error = getattr(result, "error", None) or ""
        error_message = getattr(result, "error_message", None) or ""
        self.logger.debug(
            f"Parsing hook '{hook_name}': "
            f"output_len={len(str(output))}, error_len={len(str(error))}, "
            f"error_msg_len={len(str(error_message))}, total_raw_len={len(raw_output)}"
        )

    def _log_hook_parsing_result(
        self, hook_name: str, hook_issues: list[Issue], raw_output: str
    ) -> None:
        self.logger.debug(
            f"Hook '{hook_name}' produced {len(hook_issues)} issues. "
            f"Sample (first 200 chars of raw_output): {raw_output[:200]!r}"
        )

    def _get_max_iterations(self) -> int:
        if self._max_iterations is not None:
            return self._max_iterations

        return int(os.environ.get("CRACKERJACK_AI_FIX_MAX_ITERATIONS", "5"))

    def _get_convergence_threshold(self) -> int:
        return int(os.environ.get("CRACKERJACK_AI_FIX_CONVERGENCE_THRESHOLD", "5"))

    @staticmethod
    def _get_per_issue_timeout() -> int:
        raw = os.environ.get("CRACKERJACK_AI_FIX_PER_ISSUE_TIMEOUT")
        if raw is None:
            return 300
        try:
            return int(raw)
        except ValueError:
            return 300

    @staticmethod
    def _get_global_retry_budget() -> int:
        raw = os.environ.get("CRACKERJACK_AI_FIX_GLOBAL_RETRY_BUDGET")
        if raw is None:
            return 200
        try:
            return int(raw)
        except ValueError:
            return 200

    def _is_global_budget_exhausted(self) -> bool:
        return self._global_attempt_count >= self._get_global_retry_budget()

    def _collect_current_issues(self, stage: str = "fast") -> list[Issue]:
        pkg_dir = self._detect_package_directory()
        check_commands = self._build_check_commands(pkg_dir, stage=stage)
        self.logger.debug(
            f"Built {len(check_commands)} check commands for stage '{stage}'"
        )
        for cmd, hook_name, timeout in check_commands:
            self.logger.debug(
                f" Check command: {cmd[:3]}... (hook={hook_name}, timeout={timeout}s)"
            )

        all_issues, successful_checks = self._execute_check_commands(check_commands)
        scoped_issues = self._filter_issues_to_active_scope(all_issues)

        if successful_checks == 0 and self.pkg_path.exists():
            self.logger.warning(
                "No issues collected from any checks - commands may have failed. "
                "This could indicate a problem with the issue collection process."
            )

        self.logger.debug(
            f"Collected {len(scoped_issues)} current issues "
            f"(from {successful_checks} successful checks)"
        )
        return scoped_issues

    def _matches_hook_scope(self, hook_name: str, file_path: Path) -> bool:
        patterns = _HOOK_SCOPES.get(hook_name, ("**",))
        path_str = str(file_path)
        basename = file_path.name
        for pattern in patterns:
            if fnmatch.fnmatch(path_str, pattern):
                return True
            if not basename:
                continue
            if fnmatch.fnmatch(basename, pattern):
                return True
            if pattern.startswith("**/"):
                bare = pattern[3:]
                if bare and fnmatch.fnmatch(basename, bare):
                    return True
        return False

    def _collect_targeted_issues(
        self,
        stage: str,
        files_modified: Sequence[Path | str] = (),
        previous_hook_results: Sequence[object] = (),
        pre_fix_issue_keys: set[str] | None = None,
    ) -> list[Issue]:
        pkg_dir = self._detect_package_directory()
        all_check_commands = self._build_check_commands(pkg_dir, stage=stage)

        previous_status_by_hook: dict[str, str] = {}
        previous_issues_by_hook: dict[str, int] = {}
        for result in previous_hook_results:
            name = getattr(result, "name", "")
            if name:
                previous_status_by_hook[name] = getattr(result, "status", "").lower()
                previous_issues_by_hook[name] = len(
                    getattr(result, "issues_found", []) or []
                )

        normalized_modified = [
            p if isinstance(p, Path) else Path(p) for p in files_modified
        ]

        targeted: list[tuple[list[str], str, int]] = []
        skipped_for_log: list[str] = []
        for cmd, hook_name, timeout in all_check_commands:
            previous_status = previous_status_by_hook.get(hook_name, "")
            if previous_status in {"failed", "error", "timeout"}:
                targeted.append((cmd, hook_name, timeout))
                continue
            if not previous_status:
                targeted.append((cmd, hook_name, timeout))
                continue

            if any(self._matches_hook_scope(hook_name, p) for p in normalized_modified):
                targeted.append((cmd, hook_name, timeout))
            else:
                skipped_for_log.append(hook_name)

        if skipped_for_log:
            self.logger.info(
                f"Scope-aware re-run: skipping {len(skipped_for_log)} "
                f"passed hook(s) with no in-scope modifications: "
                f"{', '.join(sorted(skipped_for_log))}"
            )

        if not targeted:
            self.logger.warning(
                "Scope-aware re-run: no hooks targeted; returning empty issue list"
            )
            return []

        self.logger.debug(
            f"Scope-aware re-run: targeting {len(targeted)} hook(s) "
            f"(out of {len(all_check_commands)} total)"
        )
        all_issues, _ = self._execute_check_commands(targeted)
        return self._filter_issues_to_active_scope(
            all_issues, pre_fix_issue_keys=pre_fix_issue_keys
        )

    def _collect_final_verification(self, stage: str = "comprehensive") -> list[Issue]:
        self.logger.info(
            "Final verification: re-running ALL hooks to confirm "
            "the post-fix state is clean across every checker"
        )
        return self._collect_current_issues(stage=stage)

    def _filter_issues_to_active_scope(
        self,
        issues: list[Issue],
        pre_fix_issue_keys: set[str] | None = None,
    ) -> list[Issue]:
        if not self._active_ai_fix_scope_files:
            return issues

        pre_fix_keys = pre_fix_issue_keys or set()
        scoped_issues: list[Issue] = []
        for issue in issues:
            normalized = self._normalize_issue_file_path(issue.file_path)
            if normalized in self._active_ai_fix_scope_files:
                scoped_issues.append(issue)
                continue

            if pre_fix_keys and self._issue_signature(issue) not in pre_fix_keys:
                scoped_issues.append(issue)
        if len(scoped_issues) != len(issues):
            kept_new = sum(
                1
                for issue in scoped_issues
                if self._normalize_issue_file_path(issue.file_path)
                not in self._active_ai_fix_scope_files
            )
            self.logger.info(
                "Scoped AI-fix verification to %s target file(s): %s -> %s issues "
                "(%s newly-introduced out-of-scope kept)",
                len(self._active_ai_fix_scope_files),
                len(issues),
                len(scoped_issues),
                kept_new,
            )
        return scoped_issues

    @staticmethod
    def _issue_signature(issue: Issue) -> str:
        file_path = issue.file_path or ""
        line_number = issue.line_number if issue.line_number is not None else -1
        message = issue.message
        return f"{file_path}:{line_number}:{message}"

    def _normalize_issue_file_path(self, file_path: str | Path | None) -> str | None:
        if not file_path:
            return None

        path = Path(file_path)
        if not path.is_absolute():
            path = self.pkg_path / path
        return str(path.resolve(strict=False))

    def _build_ai_fix_scope_files(self, issues: list[Issue]) -> set[str]:
        scope_files: set[str] = set()
        for issue in issues:
            normalized = self._normalize_issue_file_path(issue.file_path)
            if normalized:
                scope_files.add(normalized)
        return scope_files

    def _detect_package_directory(self) -> Path:
        pkg_name = self.pkg_path.name

        pkg_dirs = [
            self.pkg_path / pkg_name,
            self.pkg_path / "src" / pkg_name,
            self.pkg_path / "src",
            self.pkg_path,
        ]

        for d in pkg_dirs:
            if d.exists() and d.is_dir():
                return d

        self.logger.warning(f"Cannot find package directory, using {self.pkg_path}")
        return self.pkg_path

    def _build_check_commands(
        self, pkg_dir: Path, stage: str = "fast"
    ) -> list[tuple[list[str], str, int]]:
        pkg_name = self.pkg_path.name
        settings = CrackerjackSettings()
        adapter_timeouts = getattr(settings, "adapter_timeouts", None)

        optional_type_commands: list[tuple[list[str], str, int]] = []
        if getattr(settings.hooks, "enable_ty", False):
            optional_type_commands.append(
                (
                    [
                        "uv",
                        "run",
                        "ty",
                        "check",
                        "--output-format",
                        "concise",
                        "--no-progress",
                        str(pkg_dir),
                    ],
                    "ty",
                    int(getattr(adapter_timeouts, "ty_timeout", 120)),
                )
            )

        if getattr(settings.hooks, "enable_pyrefly", False):
            optional_type_commands.append(
                (
                    [
                        "uv",
                        "run",
                        "pyrefly",
                        "check",
                        "--output-format",
                        "json",
                        "--summary",
                        "none",
                        "--no-progress-bar",
                        str(pkg_dir),
                    ],
                    "pyrefly",
                    int(getattr(adapter_timeouts, "pyrefly_timeout", 120)),
                )
            )

        all_commands = [
            (["uv", "run", "ruff", "check", "."], "ruff", 60),
            (["uv", "run", "ruff", "format", "--check", "."], "ruff-format", 60),
            (
                [
                    "uv",
                    "run",
                    "zuban",
                    "mypy",
                    "--config-file",
                    "mypy.ini",
                    "--no-error-summary",
                    str(pkg_dir),
                ],
                "zuban",
                120,
            ),
            (
                [
                    "uv",
                    "run",
                    "refurb",
                    str(pkg_dir),
                ],
                "refurb",
                120,
            ),
            (
                [
                    "uv",
                    "run",
                    "complexipy",
                    "--max-complexity-allowed",
                    "15",
                    pkg_name,
                ],
                "complexipy",
                60,
            ),
        ]
        all_commands.extend(optional_type_commands)
        all_commands.extend(self._build_comprehensive_check_commands())

        if stage == "fast":
            return [cmd for cmd in all_commands if cmd[1] in ("ruff", "ruff-format")]

        allowed = {h.name for h in COMPREHENSIVE_HOOKS if not h.disabled}
        allowed.add("pyrefly")
        return [cmd for cmd in all_commands if cmd[1] in allowed]

    def _build_comprehensive_check_commands(self) -> list[tuple[list[str], str, int]]:

        settings = CrackerjackSettings()
        adapter_timeouts = getattr(settings, "adapter_timeouts", None)
        hook_timeouts: dict[str, int] = {}
        for h in COMPREHENSIVE_HOOKS:
            if h.disabled:
                continue
            override = getattr(adapter_timeouts, f"{h.name}_timeout", None)
            hook_timeouts[h.name] = int(override) if override is not None else h.timeout

        commands: list[tuple[list[str], str, int]] = []
        for hook_name, timeout in hook_timeouts.items():
            try:
                commands.append(
                    (get_tool_command(hook_name, self.pkg_path), hook_name, timeout)
                )
            except (KeyError, FileNotFoundError):
                self.logger.debug(
                    "No configured command for comprehensive hook %s", hook_name
                )

        return commands

    def _execute_check_commands(
        self, check_commands: list[tuple[list[str], str, int]]
    ) -> tuple[list[Issue], int]:
        all_issues: list[Issue] = []
        successful_checks = 0
        scope_paths = self._scope_signature_paths()

        for cmd, hook_name, timeout in check_commands:
            if hook_name == "gitleaks":
                (self.pkg_path / ".cache").mkdir(exist_ok=True)
            signature = self._check_command_output_signature(hook_name, scope_paths)
            if self._stdout_hash_cache.get(hook_name) == signature:
                self.logger.debug(
                    "Skip %s: no file changes since last run (stdout-hash match)",
                    hook_name,
                )
                continue
            result = self._run_check_command(cmd, timeout, hook_name)
            if result:
                process, stdout, stderr = result
                issues = self._process_check_result(process, stdout, stderr, hook_name)
                all_issues.extend(issues)
                successful_checks += 1
                self._stdout_hash_cache[hook_name] = signature

        return all_issues, successful_checks

    def _scope_signature_paths(self) -> list[Path]:
        paths: list[Path] = [
            Path(entry) for entry in sorted(self._active_ai_fix_scope_files)
        ]
        return paths

    def _check_command_output_signature(
        self, tool: str, files_modified: list[Path]
    ) -> str:
        payload = b""
        for path in files_modified:
            try:
                stat = path.stat()
            except OSError:
                continue
            payload += f"{path}:{stat.st_mtime}:{stat.st_size}".encode()
        digest = hashlib.sha256(payload).hexdigest()
        return f"{tool}:{digest}"

    def _run_check_command(
        self, cmd: list[str], timeout: int, hook_name: str
    ) -> tuple[subprocess.Popen[str], str, str] | None:
        process: subprocess.Popen[str] | None = None
        try:
            process = subprocess.Popen(
                cmd,
                cwd=self.pkg_path,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            stdout, stderr = process.communicate(timeout=timeout)
            return (process, stdout, stderr)
        except subprocess.TimeoutExpired:
            self._kill_process_gracefully(process)
            self.progress_manager.log_warning(f"Timeout running {hook_name} check")
            return None
        except Exception as e:
            self._kill_process_gracefully(process)
            self._collect_error("Hook Error", f"{hook_name}: {e}")
            return None

    def _kill_process_gracefully(self, process: subprocess.Popen[str] | None) -> None:
        if process:
            process.kill()
            try:
                process.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()

    def _process_check_result(
        self, process: subprocess.Popen[str], stdout: str, stderr: str, hook_name: str
    ) -> list[Issue]:
        combined_output = stdout + stderr

        self.logger.debug(
            f"{hook_name}: returncode={process.returncode}, "
            f"stdout_len={len(stdout)}, stderr_len={len(stderr)}, "
            f"combined_len={len(combined_output)}"
        )

        if process.returncode != 0 or combined_output:
            hook_issues = self._parse_hook_to_issues(hook_name, combined_output)
            if hook_issues:
                self.logger.debug(
                    f"{hook_name}: Parsed {len(hook_issues)} issues from output"
                )
            else:
                self.logger.debug(
                    f"{hook_name}: Output present but no issues parsed (filtered out?)"
                )
            return hook_issues

        return []

    def _convert_parsed_issues_to_issues(
        self, tool_name: str, parsed_issues: list[dict[str, t.Any]]
    ) -> list[Issue]:
        issues = []

        for tool_issue_dict in parsed_issues:
            try:
                file_path = tool_issue_dict.get("file_path")
                if not file_path:
                    self.logger.debug(
                        f"Skipping issue from '{tool_name}': missing file_path. "
                        f"Issue data: {tool_issue_dict}"
                    )
                    continue

                severity_raw = tool_issue_dict.get("severity", "error")
                severity_str = severity_raw.lower() if severity_raw else "error"
                severity = self._map_severity_to_priority(severity_str)

                issue_type = self._determine_issue_type(tool_name, tool_issue_dict)

                details = self._build_issue_details(tool_issue_dict)

                issue = Issue(
                    type=issue_type,
                    severity=severity,
                    message=tool_issue_dict.get("message", ""),
                    file_path=file_path,
                    line_number=tool_issue_dict.get("line_number"),
                    details=details,
                    stage=tool_name,
                )

                issues.append(issue)

            except (KeyError, TypeError, ValueError) as e:
                self.logger.warning(
                    f"Failed to convert parsed issue from '{tool_name}': {e}. "
                    f"Issue data: {tool_issue_dict}",
                    exc_info=True,
                )
                continue
            except Exception as e:
                self._collect_error(
                    "Parse Error",
                    f"{tool_name}: {e}",
                )
                continue

        self.logger.info(
            f"✅ Converted {len(issues)} issues from '{tool_name}' "
            f"(from QAResult.parsed_issues)"
        )

        return issues

    def _map_severity_to_priority(self, severity_str: str) -> Priority:
        severity_map = {
            "error": Priority.HIGH,
            "warning": Priority.MEDIUM,
            "info": Priority.LOW,
            "note": Priority.LOW,
        }

        return severity_map.get(severity_str, Priority.MEDIUM)

    def _determine_issue_type(
        self, tool_name: str, tool_issue_dict: dict[str, t.Any]
    ) -> IssueType:
        code = (
            tool_issue_dict.get("code", "").upper()
            if tool_issue_dict.get("code")
            else ""
        )
        message = (
            tool_issue_dict.get("message", "").lower()
            if tool_issue_dict.get("message")
            else ""
        )

        issue_type = self._determine_issue_type_from_tool_and_code(tool_name, code)
        if issue_type is not None:
            return issue_type

        return self._determine_issue_type_from_message(message, code)

    def _determine_issue_type_from_tool_and_code(
        self, tool_name: str, code: str
    ) -> IssueType | None:
        if tool_name == "ruff":
            if code.startswith("C90") or code == "C901":
                return IssueType.COMPLEXITY
            if code in {"F403", "F405", "F822", "F404", "F821", "I001"}:
                return IssueType.IMPORT_ERROR

        if tool_name in (
            "check-local-links",
            "check-links",
            "lychee",
            "linkcheckmd",
            "markdown-link-check",
        ):
            return IssueType.DOCUMENTATION

        tool_type_map = {
            "ruff": IssueType.FORMATTING,
            "ruff-format": IssueType.FORMATTING,
            "mdformat": IssueType.FORMATTING,
            "codespell": IssueType.FORMATTING,
            "mypy": IssueType.TYPE_ERROR,
            "zuban": IssueType.TYPE_ERROR,
            "pyright": IssueType.TYPE_ERROR,
            "pylint": IssueType.TYPE_ERROR,
            "bandit": IssueType.SECURITY,
            "gitleaks": IssueType.SECURITY,
            "semgrep": IssueType.SECURITY,
            "safety": IssueType.SECURITY,
            "pytest": IssueType.TEST_FAILURE,
            "complexipy": IssueType.COMPLEXITY,
            "refurb": IssueType.REFURB,
            "skylos": IssueType.DEAD_CODE,
            "creosote": IssueType.DEPENDENCY,
            "pyscn": IssueType.DEPENDENCY,
            "cohesion": IssueType.COMPLEXITY,
            "pymetrica": IssueType.COMPLEXITY,
        }
        return tool_type_map.get(tool_name)

    def _determine_issue_type_from_message(self, message: str, code: str) -> IssueType:
        message_keywords: dict[str, IssueType] = {
            "broken link": IssueType.DOCUMENTATION,
            "file not found": IssueType.DOCUMENTATION,
            "local link": IssueType.DOCUMENTATION,
            "documentation": IssueType.DOCUMENTATION,
            "markdown link": IssueType.DOCUMENTATION,
            "test": IssueType.TEST_FAILURE,
            "pytest": IssueType.TEST_FAILURE,
            "unittest": IssueType.TEST_FAILURE,
            "complex": IssueType.COMPLEXITY,
            "cyclomatic": IssueType.COMPLEXITY,
            "dead": IssueType.DEAD_CODE,
            "unused": IssueType.DEAD_CODE,
            "redundant": IssueType.DEAD_CODE,
            "security": IssueType.SECURITY,
            "vulnerability": IssueType.SECURITY,
            "import": IssueType.IMPORT_ERROR,
            "module": IssueType.IMPORT_ERROR,
        }
        for keyword, issue_type in message_keywords.items():
            if keyword in message:
                return issue_type
        if "type" in message or "type:" in code:
            return IssueType.TYPE_ERROR
        return IssueType.FORMATTING

    def _build_issue_details(self, tool_issue_dict: dict[str, t.Any]) -> list[str]:
        details = []

        if code := tool_issue_dict.get("code"):
            details.append(f"code: {code}")

        if suggestion := tool_issue_dict.get("suggestion"):
            details.append(f"suggestion: {suggestion}")

        if column := tool_issue_dict.get("column_number"):
            details.append(f"column: {column}")

        details.append(f"severity: {tool_issue_dict.get('severity', 'unknown')}")

        return details

    def _parse_hook_to_issues(
        self,
        hook_name: str,
        raw_output: str,
        qa_result: QAResult | None = None,
    ) -> list[Issue]:
        self.logger.debug(
            f"Parsing hook '{hook_name}': "
            f"raw_output_lines={len(raw_output.split(chr(10)))}"
        )

        output_preview = raw_output[:500] if raw_output else "(empty)"
        self.logger.debug(f"Raw output preview from '{hook_name}':\n{output_preview!r}")

        if qa_result and qa_result.parsed_issues:
            self.logger.info(
                f"📦 Using QAResult.parsed_issues for '{hook_name}' "
                f"({len(qa_result.parsed_issues)} issues)"
            )
            return self._convert_parsed_issues_to_issues(
                hook_name, qa_result.parsed_issues
            )

        self.logger.info(
            f"🔄 QAResult not available for '{hook_name}', parsing raw output"
        )
        expected_count = self._extract_issue_count(raw_output, hook_name)
        if (
            self._active_ai_fix_scope_files
            and hook_name in {"ruff", "ruff-format"}
            and expected_count is not None
        ):
            self.logger.info(
                "Skipping issue-count validation for scoped %s verification "
                "(expected %s issues before filtering)",
                hook_name,
                expected_count,
            )
            expected_count = None
        self.logger.info(f"Parsing '{hook_name}': expected_count={expected_count}")

        try:
            issues = self._parser_factory.parse_with_validation(
                tool_name=hook_name,
                output=raw_output,
                expected_count=expected_count,
            )

            self.logger.info(
                f"Successfully parsed {len(issues)} issues from '{hook_name}'"
            )

            if issues:
                self._log_parsed_issues(hook_name, issues)
                self._validate_parsed_issues(issues)
            else:
                self.logger.info(f"✅ No issues found from '{hook_name}' (clean run)")

            return issues

        except (ParsingError, ValueError) as e:
            self._collect_error("Parsing Error", f"{hook_name}: {e}")

            try:
                filtered_output = strip_non_error_output(raw_output)
                if filtered_output != raw_output:
                    self.logger.info(
                        f"Filtered panic noise from '{hook_name}' output "
                        f"({len(raw_output)} → {len(filtered_output)} bytes)"
                    )
                    issues = self._parser_factory.parse_with_validation(
                        tool_name=hook_name,
                        output=filtered_output,
                        expected_count=None,
                    )
                    if issues:
                        self.logger.info(
                            f"Recovered {len(issues)} issues from '{hook_name}' "
                            "after panic-noise filtering"
                        )
                        return issues
            except Exception as filter_error:
                self.logger.debug(
                    f"Panic-noise filtering failed for '{hook_name}': {filter_error}"
                )

            try:
                issues = self._parser_factory.parse_with_validation(
                    tool_name=hook_name,
                    output=raw_output,
                    expected_count=None,
                )
                if issues:
                    self.logger.info(
                        f"Recovered {len(issues)} issues from '{hook_name}' "
                        "after validation failure"
                    )
                    return issues
            except Exception as recovery_error:
                self.logger.debug(
                    f"Best-effort parsing failed for '{hook_name}': {recovery_error}"
                )
            return []

    def _extract_issue_count(self, output: str, tool_name: str) -> int | None:

        if tool_name in (
            "complexipy",
            "complexity",
            "refurb",
            "creosote",
            "pyscn",
            "semgrep",
            "pytest",
            "check-yaml",
            "check-toml",
            "check-json",
            "check-jsonschema",
            "pip-audit",
            "check-ast",
            "check-local-links",
            "check-added-large-files",
            "format-json",
            "gitleaks",
            "betterleaks",
            "lychee",
            "ty",
            "cohesion",
            "pymetrica",
        ):
            return None

        json_count = _extract_issue_count_from_json(output, tool_name)
        if json_count is not None:
            return json_count

        return _extract_issue_count_from_text_lines(output)

    def _log_parsed_issues(self, hook_name: str, issues: list[Issue]) -> None:
        self.logger.info(f"📋 Issue structure from '{hook_name}':")
        for i, issue in enumerate(issues[:5]):
            self.logger.info(
                f" [{i}] type={issue.type.value}, "
                f"severity={issue.severity.value}, "
                f"file={issue.file_path}:{issue.line_number}, "
                f"msg={issue.message!r}"
            )

        if len(issues) > 5:
            self.logger.info(f" ... and {len(issues) - 5} more issues")

    def _validate_parsed_issues(self, issues: list[Issue]) -> None:
        for i, issue in enumerate(issues):
            if not issue.file_path:
                self.logger.warning(
                    f"Issue {i} ({issue.id}) missing file_path: {issue.message}"
                )

            if not issue.message:
                self.logger.warning(
                    f"Issue {i} ({issue.id}) missing message, file={issue.file_path}"
                )

            if issue.severity not in Priority:
                self.logger.warning(
                    f"Issue {i} has invalid severity: {issue.severity.value}"
                )

            if issue.type not in IssueType:
                self.logger.warning(f"Issue {i} has invalid type: {issue.type.value}")

    def _setup_ai_fix_coordinator(self) -> AgentCoordinatorProtocol:

        settings = CrackerjackSettings()

        skills_tracker = None
        if settings.skills.enabled:
            try:
                skills_tracker = create_skills_tracker(
                    session_id=f"autofix-{os.getpid()}",
                    enabled=settings.skills.enabled,
                    backend=settings.skills.backend,
                    db_path=Path(settings.skills.db_path)
                    if settings.skills.db_path
                    else None,
                    mcp_server_url=settings.skills.mcp_server_url,
                )
                self.logger.debug(
                    f"Skills tracking enabled: backend={skills_tracker.get_backend()}, "
                    f"enabled={skills_tracker.is_enabled()}"
                )
            except Exception as e:
                self.logger.warning(f"Failed to initialize skills tracking: {e}")

        fix_strategy_memory = None
        if settings.fix_strategy_memory.enabled:
            try:
                from crackerjack.memory.fix_strategy_storage import FixStrategyStorage

                fix_strategy_memory = FixStrategyStorage(
                    db_path=Path(settings.fix_strategy_memory.db_path)
                )
                self.logger.info(
                    f"✅ Fix strategy memory enabled: {settings.fix_strategy_memory.db_path}"
                )
            except Exception as e:
                self.logger.warning(f"Failed to initialize fix strategy memory: {e}")

        context = AgentContext(
            project_path=self.pkg_path,
            subprocess_timeout=300,
            skills_tracker=skills_tracker,
            fix_strategy_memory=fix_strategy_memory,
        )
        cache = CrackerjackCache()

        if self._coordinator_factory is not None:
            coordinator = self._coordinator_factory(context, cache)
        else:
            from crackerjack.agents.coordinator import AgentCoordinator
            from crackerjack.agents.tracker import get_agent_tracker
            from crackerjack.services.debug import get_ai_agent_debugger

            coordinator = AgentCoordinator(
                context=context,
                tracker=get_agent_tracker(),
                debugger=get_ai_agent_debugger(),
                cache=cache,
            )

        return coordinator

    def _collect_fixable_issues(self, hook_results: Sequence[object]) -> list[Issue]:
        initial_issues = self._parse_hook_results_to_issues_with_qa(hook_results)

        coverage_issues = self._check_coverage_regression(hook_results)
        if coverage_issues:
            self.logger.info(
                f"🧪 Test AI Stage: Detected {len(coverage_issues)} coverage failures, "
                f"adding to AI-fix queue for test creation"
            )
            initial_issues.extend(coverage_issues)

        return initial_issues

    def _get_iteration_issues_with_log(
        self,
        iteration: int,
        hook_results: Sequence[object],
        stage: str,
        initial_issues: list[Issue],
        previous_issues: list[Issue] | None = None,
        previous_fixes_applied: int = 0,
        previous_files_modified: Sequence[Path | str] = (),
        previous_hook_statuses: dict[str, str] | None = None,
    ) -> tuple[list[Issue], dict[str, str]]:
        if iteration == 0:
            return initial_issues.copy(), {}

        if previous_fixes_applied == 0 and previous_issues is not None:
            self.logger.info(
                f"Iteration {iteration}: Skipped hook re-run "
                f"(previous iteration made 0 fixes); reusing "
                f"{len(previous_issues)} cached issues"
            )
            return previous_issues.copy(), previous_hook_statuses or {}

        previous_results = self._build_previous_results_from_statuses(
            previous_hook_statuses or {}
        )

        pre_fix_keys = (
            {self._issue_signature(i) for i in (previous_issues or [])}
            if previous_issues is not None
            else None
        )
        return self._collect_targeted_issues_with_log(
            stage=stage,
            files_modified=previous_files_modified,
            previous_hook_results=previous_results,
            pre_fix_issue_keys=pre_fix_keys,
        )

    def _build_previous_results_from_statuses(
        self, hook_statuses: dict[str, str]
    ) -> list[object]:
        from types import SimpleNamespace

        return [
            SimpleNamespace(name=name, status=status, issues_found=[], issues_count=0)
            for name, status in hook_statuses.items()
        ]

    def _collect_targeted_issues_with_log(
        self,
        stage: str,
        files_modified: Sequence[Path | str] = (),
        previous_hook_results: Sequence[object] = (),
        pre_fix_issue_keys: set[str] | None = None,
    ) -> tuple[list[Issue], dict[str, str]]:
        targeted_issues = self._collect_targeted_issues(
            stage=stage,
            files_modified=files_modified,
            previous_hook_results=previous_hook_results,
            pre_fix_issue_keys=pre_fix_issue_keys,
        )
        statuses: dict[str, str] = {}
        for result in previous_hook_results:
            name = getattr(result, "name", "")
            if name:
                statuses[name] = getattr(result, "status", "").lower()
        return targeted_issues, statuses

    def _check_iteration_completion(
        self,
        iteration: int,
        current_issue_count: int,
        previous_issue_count: float,
        no_progress_count: int,
        max_iterations: int,
        stage: str,
        fixes_applied: int = 0,
    ) -> bool | None:
        if current_issue_count == 0:
            return self._handle_zero_issues_case(iteration, stage)

        if iteration >= max_iterations:
            self.logger.warning(
                f"Reached max iterations ({max_iterations}) with {current_issue_count} issues remaining"
            )
            return False

        if self._should_stop_on_convergence(
            current_issue_count,
            previous_issue_count,
            no_progress_count,
            fixes_applied,
        ):
            return False

        return None

    def _update_iteration_progress_with_tracking(
        self,
        iteration: int,
        current_issue_count: int,
        previous_issue_count: float,
        no_progress_count: int,
        fixes_applied: int = 0,
    ) -> int:
        no_progress_count = self._update_progress_count(
            current_issue_count,
            previous_issue_count,
            no_progress_count,
            fixes_applied,
        )

        self.progress_manager.update_iteration_progress(
            iteration,
            current_issue_count,
            no_progress_count,
        )

        return no_progress_count

    async def _run_iteration_loop_dispatch(
        self,
        ctx: AutoFixContext,
        step_fn: IterationStepFn,
    ) -> bool:
        try:
            while True:
                ctx.current_issues, ctx.previous_hook_statuses = (
                    self._get_iteration_issues_with_log(
                        ctx.iteration,
                        ctx.hook_results,
                        ctx.stage,
                        ctx.initial_issues,
                        previous_issues=ctx.previous_issues,
                        previous_fixes_applied=ctx.previous_fixes_applied,
                        previous_files_modified=ctx.previous_files_modified,
                        previous_hook_statuses=ctx.previous_hook_statuses,
                    )
                )
                current_issue_count = len(ctx.current_issues)

                self.progress_manager.start_iteration(
                    ctx.iteration, current_issue_count
                )
                await self._event_bus.emit(
                    IterationStarted(
                        run_id=self._run_id,
                        iteration=ctx.iteration,
                        issue_count=current_issue_count,
                    )
                )

                completion_result = self._check_iteration_completion(
                    ctx.iteration,
                    current_issue_count,
                    ctx.previous_issue_count,
                    ctx.no_progress_count,
                    ctx.max_iterations,
                    ctx.stage,
                    fixes_applied=ctx.previous_fixes_applied,
                )
                if completion_result is not None:
                    await self._finalize_v2_iteration_loop(
                        ctx.iteration, completion_result
                    )
                    return completion_result

                step_result = await step_fn(ctx)

                ctx.no_progress_count = self._update_iteration_progress_with_tracking(
                    ctx.iteration,
                    current_issue_count,
                    ctx.previous_issue_count,
                    ctx.no_progress_count,
                    step_result.fixes_applied,
                )

                if not step_result.success:
                    if step_result.fixes_applied == 0:
                        await self._finalize_v2_iteration_loop(ctx.iteration, False)
                        return False
                    self.logger.info(
                        "Partial AI-fix progress detected; "
                        "continuing with remaining issues"
                    )

                await self._event_bus.emit(
                    IterationFinished(
                        run_id=self._run_id,
                        iteration=ctx.iteration,
                        resolved=step_result.fixes_applied,
                        success=step_result.success,
                    )
                )
                self.progress_manager.end_iteration()

                ctx.previous_issue_count = current_issue_count
                ctx.previous_fixes_applied = step_result.fixes_applied
                ctx.previous_issues = ctx.current_issues.copy()
                ctx.previous_files_modified = []
                ctx.iteration += 1

        except Exception as e:
            self.logger.exception(
                f"Error during AI fixing at iteration {ctx.iteration}"
            )
            self.progress_manager.end_iteration()
            self.progress_manager.finish_session(
                success=False,
                message=f"Error during AI fixing: {e}",
                iteration_count=ctx.iteration,
            )
            await self._event_bus.emit(
                RunFinished(
                    run_id=self._run_id,
                    iteration=ctx.iteration,
                    success=False,
                    total_iterations=ctx.iteration,
                )
            )
            raise

    async def _v2_iteration_step(
        self,
        ctx: AutoFixContext,
        analysis_coordinator: AnalysisCoordinator,
        fixer_coordinator: FixerCoordinator,
        validation_coordinator: ValidationCoordinator,
    ) -> StepResult:

        router_outcome = await self._dispatch_through_router(
            fixer_coordinator, ctx.current_issues
        )
        if router_outcome.fully_resolved:
            return StepResult(
                success=True,
                fixes_applied=router_outcome.fixes_applied,
            )

        ctx.current_issues = router_outcome.remaining_issues

        plans = await self._create_fix_plans(analysis_coordinator, ctx.current_issues)
        if not plans:
            return StepResult(
                success=False,
                fixes_applied=0,
                failure_reason="No fix plans produced",
            )

        results = await self._execute_plans_with_validation(
            plans,
            fixer_coordinator,
            validation_coordinator,
            analysis_coordinator,
            ctx.current_issues,
        )

        fixes_applied = sum(len(result.fixes_applied) for result in results)
        success = self._check_execution_results(results)
        failure_reason = (
            ""
            if success or fixes_applied > 0
            else ("Execution results reported failure and no fixes were applied")
        )

        if not success and fixes_applied == 0:
            return StepResult(
                success=False,
                fixes_applied=0,
                failure_reason=failure_reason,
            )

        if not success:
            self.logger.info(
                "Partial AI-fix progress detected; continuing with remaining issues"
            )

        return StepResult(
            success=True,
            fixes_applied=fixes_applied,
        )

    async def _dispatch_through_router(
        self,
        fixer_coordinator: FixerCoordinator,
        issues: list[Issue],
    ) -> RouterOutcome:
        router = getattr(self, "_fix_router", None)
        if router is None:
            return RouterOutcome(
                remaining_issues=issues.copy(),
                fixes_applied=0,
                fully_resolved=False,
            )

        remaining: list[Issue] = []
        fixes_applied = 0
        for issue in issues:
            try:
                result = await router.fix(issue)
            except Exception as exc: # noqa: BLE001 — defensive
                self.logger.debug("FixRouter raised for %s: %s", issue.file_path, exc)

                remaining.append(issue)
                continue

            if result.success:
                fixes_applied += len(result.fixes_applied) or 1
                self.logger.debug(
                    "FixRouter resolved %s via %s",
                    issue.file_path,
                    result.fixes_applied,
                )
                continue

            if any("non-fixable" in msg.lower() for msg in result.remaining_issues):
                self.logger.debug(
                    "FixRouter filtered non-fixable %s: %s",
                    issue.file_path,
                    result.remaining_issues,
                )
                continue

            remaining.append(issue)

        return RouterOutcome(
            remaining_issues=remaining,
            fixes_applied=fixes_applied,
            fully_resolved=not remaining,
        )

    async def _apply_ai_agent_fixes(
        self, hook_results: Sequence[object], stage: str = "fast"
    ) -> bool:
        self.logger.info("🚀 Using V2 Two-Stage Pipeline with validation")
        return await self._apply_ai_agent_fixes_v2(hook_results, stage)

    async def _execute_plan_with_validation(
        self,
        plan: FixPlan,
        fixer_coordinator: FixerCoordinator,
        validation_coordinator: ValidationCoordinator,
        bar: Any, # type: ignore
    ) -> tuple[bool, list[FixResult], str]:

        if bar:
            self.progress_manager.update_bar_text(plan.file_path)

        self.logger.info(
            f"Plan {plan.file_path}: {len(plan.changes)} changes, risk={plan.risk_level}"
        )

        primary_key = fixer_coordinator._candidate_fixer_keys(plan.issue_type)[0]
        primary_agent = fixer_coordinator.fixers.get(primary_key)
        agent_name = (
            getattr(primary_agent, "name", primary_key)
            if primary_agent
            else "FixerCoordinator"
        )

        self.progress_manager.log_event(
            agent=agent_name,
            action="Executing plan",
            file=plan.file_path,
            severity="info",
            issue_type=plan.issue_type,
        )
        self._event_bus.emit_nowait(
            AgentDispatched(
                run_id=self._run_id,
                iteration=0,
                agent=agent_name,
                action="Executing plan",
                file=plan.file_path,
                issue_type=plan.issue_type,
            )
        )

        if "backup" in Path(plan.file_path).name.split("."):
            self.logger.debug(f"Skipping plan: {plan.file_path} is a backup file")
            return False, [], "plan target is a backup file"

        backup_path = self._create_backup(plan.file_path)
        original_content = Path(plan.file_path).read_text()
        quality_checks = self._validation_quality_checks_for_plan(plan)

        try:
            plan_results = await fixer_coordinator.execute_plans([plan])
            if not plan_results:
                return False, [], "No fixer available for this issue type"
            if not plan_results[0].success:
                failure_reasons = plan_results[0].remaining_issues or [
                    "Unknown failure"
                ]
                return False, [], f"Fix failed: {'; '.join(failure_reasons)}"

            modified_content = Path(plan.file_path).read_text()

            if modified_content == original_content:
                self.logger.warning(
                    f"⚠️ No-op fix for {plan.file_path}: "
                    "fixer reported success but file content is unchanged"
                )
                try:
                    self._restore_backup(backup_path)
                except OSError as restore_err:
                    msg = (
                        "no-op fix: file content unchanged; "
                        f"rollback failed: {restore_err}"
                    )
                    self.logger.error(f"⚠️ {msg}")
                    return False, [], msg
                return False, [], "no-op fix: file content unchanged"

            if plan.file_path.endswith(".py"):
                validation_result = self._output_validator.validate(
                    Path(plan.file_path)
                )
                if not validation_result.passed:
                    self.logger.warning(
                        f"⚠️ Output validation failed for {plan.file_path}: "
                        f"{validation_result.reason} — rolling back"
                    )
                    try:
                        self._restore_backup(backup_path)
                    except OSError as restore_err:
                        msg = (
                            f"output validation failed for {plan.file_path}: "
                            f"{validation_result.reason}; "
                            f"rollback failed: {restore_err}"
                        )
                        self.logger.error(f"⚠️ {msg}")
                        return False, [], msg
                    return (
                        False,
                        [],
                        (
                            f"output validation failed for {plan.file_path}: "
                            f"{validation_result.reason}"
                        ),
                    )

            is_valid, feedback = await validation_coordinator.validate_fix(
                code=modified_content,
                file_path=plan.file_path,
                original_code=original_content,
                quality_checks=quality_checks,
                compare_to_original=self._should_compare_validation_to_original(plan),
            )

            if is_valid:
                self._record_validation_success(
                    plan.file_path,
                    "Validated successfully",
                    bar,
                    issue_type=plan.issue_type,
                )
                return True, plan_results, ""

            feedback = await self._retry_validation_after_targeted_python_fix(
                plan=plan,
                validation_coordinator=validation_coordinator,
                original_content=original_content,
                feedback=feedback,
                bar=bar,
            )
            if feedback is None:
                return True, plan_results, ""

            feedback = await self._retry_validation_after_targeted_refurb_fix(
                plan=plan,
                validation_coordinator=validation_coordinator,
                original_content=original_content,
                feedback=feedback,
                bar=bar,
            )
            if feedback is None:
                return True, plan_results, ""

            feedback = await self._retry_validation_after_missing_import_fix(
                plan=plan,
                validation_coordinator=validation_coordinator,
                original_content=original_content,
                feedback=feedback,
                bar=bar,
            )
            if feedback is None:
                return True, plan_results, ""

            self.logger.warning(f"⚠️ Validation failed, rolling back {plan.file_path}")
            self._restore_backup(backup_path)
            return False, [], feedback

        except Exception as e:
            self._restore_backup(backup_path)
            return False, [], str(e)

    def _validation_quality_checks_for_plan(
        self, plan: FixPlan
    ) -> tuple[str, ...] | None:
        issue_type = plan.issue_type.upper()
        issue_stage = plan.issue_stage.lower()

        if issue_type == "COMPLEXITY" or issue_stage in {"ruff-check", "ruff"}:
            return ("ruff",)

        return None

    def _should_compare_validation_to_original(self, plan: FixPlan) -> bool:

        return plan.risk_level == "high" or plan.issue_type == "COMPLEXITY"

    def _record_validation_success(
        self,
        file_path: str,
        action: str,
        bar: Any, # type: ignore
        issue_type: str = "",
    ) -> None:
        self.logger.info(f"✅ Plan validated: {file_path}")
        self.progress_manager.log_event(
            agent="ValidationCoordinator",
            action=action,
            file=file_path,
            severity="success",
            issue_type=issue_type,
        )
        self._event_bus.emit_nowait(
            IssueResolved(
                run_id=self._run_id,
                iteration=0,
                agent="ValidationCoordinator",
                file=file_path,
                issue_type=issue_type,
            )
        )
        if bar:
            bar()

    async def _retry_validation_after_targeted_python_fix(
        self,
        *,
        plan: FixPlan,
        validation_coordinator: ValidationCoordinator,
        original_content: str,
        feedback: str,
        bar: Any, # type: ignore
    ) -> str | None:
        if not self._should_retry_quality_validation(plan.file_path, feedback):
            return feedback

        self.logger.info(
            f"🧹 Applying targeted Ruff repair before rollback: {plan.file_path}"
        )
        if not self._run_targeted_python_fixes(plan.file_path):
            return feedback

        return await self._retry_validation_after_repair(
            plan=plan,
            validation_coordinator=validation_coordinator,
            original_content=original_content,
            feedback=feedback,
            repair_action="Validated successfully after Ruff repair",
            repair_success_message="✅ Targeted Ruff repair validated",
            bar=bar,
        )

    async def _retry_validation_after_targeted_refurb_fix(
        self,
        *,
        plan: FixPlan,
        validation_coordinator: ValidationCoordinator,
        original_content: str,
        feedback: str,
        bar: Any, # type: ignore
    ) -> str | None:
        if not self._should_retry_refurb_validation(feedback):
            return feedback

        self.logger.info(
            f"🧩 Applying deterministic refurb repair before rollback: {plan.file_path}"
        )
        if not self._run_targeted_refurb_fixes(plan.file_path):
            return feedback

        return await self._retry_validation_after_repair(
            plan=plan,
            validation_coordinator=validation_coordinator,
            original_content=original_content,
            feedback=feedback,
            repair_action="Validated successfully after refurb repair",
            repair_success_message="✅ Deterministic refurb repair validated",
            bar=bar,
        )

    async def _retry_validation_after_missing_import_fix(
        self,
        *,
        plan: FixPlan,
        validation_coordinator: ValidationCoordinator,
        original_content: str,
        feedback: str,
        bar: Any, # type: ignore
    ) -> str | None:
        if not self._should_retry_missing_imports(feedback):
            return feedback

        self.logger.info(
            f"🧩 Applying deterministic import repair before rollback: {plan.file_path}"
        )
        if not self._apply_missing_import_repair(plan.file_path, feedback):
            return feedback

        return await self._retry_validation_after_repair(
            plan=plan,
            validation_coordinator=validation_coordinator,
            original_content=original_content,
            feedback=feedback,
            repair_action="Validated successfully after import repair",
            repair_success_message="✅ Deterministic import repair validated",
            bar=bar,
        )

    async def _retry_validation_after_repair(
        self,
        *,
        plan: FixPlan,
        validation_coordinator: ValidationCoordinator,
        original_content: str,
        feedback: str,
        repair_action: str,
        repair_success_message: str,
        bar: Any, # type: ignore
    ) -> str | None:
        quality_checks = self._validation_quality_checks_for_plan(plan)
        modified_content = Path(plan.file_path).read_text()
        is_valid, retry_feedback = await validation_coordinator.validate_fix(
            code=modified_content,
            file_path=plan.file_path,
            original_code=original_content,
            quality_checks=quality_checks,
            compare_to_original=self._should_compare_validation_to_original(plan),
        )
        if is_valid:
            self.logger.info(f"{repair_success_message}: {plan.file_path}")
            self.progress_manager.log_event(
                agent="ValidationCoordinator",
                action=repair_action,
                file=plan.file_path,
                severity="success",
                issue_type=plan.issue_type,
            )
            if bar:
                bar()
            return None
        return retry_feedback

    async def _apply_ai_agent_fixes_v2(
        self, hook_results: Sequence[object], stage: str = "fast"
    ) -> bool:
        from pathlib import Path

        from ..agents.analysis_coordinator import AnalysisCoordinator
        from ..agents.fixer_coordinator import FixerCoordinator
        from ..agents.validation_coordinator import ValidationCoordinator
        from ..services.debug import get_ai_agent_debugger

        self.logger.info("🎯 Initializing V2 Two-Stage Pipeline")

        initial_hook_total = self.progress_manager.compute_hook_total(hook_results)

        issues = self._collect_fixable_issues(hook_results)
        if not issues:
            self.logger.info("✅ No issues to fix")
            return True

        active_scope_files = self._build_ai_fix_scope_files(issues)
        previous_scope_files = self._active_ai_fix_scope_files
        self._active_ai_fix_scope_files = active_scope_files

        issues = self._filter_fixable_issues(issues)
        if not issues:
            self._active_ai_fix_scope_files = previous_scope_files
            return True

        try:
            tracker = _FileChangeTracker(self.pkg_path)
            tracker.capture()
            preflight = PreflightFixer(
                config=self._preflight_config,
                bus=self._event_bus,
                pkg_path=self.pkg_path,
            )
            await preflight.run(run_id=self._run_id, iteration=0)
            tracker.capture()

            refreshed_type_issues = await self._apply_type_tool_fix_prepasses(
                hook_results
            )
            if refreshed_type_issues:
                issues = self._replace_refreshed_type_issues(
                    issues,
                    refreshed_type_issues,
                )

            await self._apply_zuban_fix_prepass(hook_results)

            issues = await self._apply_pycharm_hook_diagnostics_context(issues, stage)

            pycharm_reformat_success = await self._apply_pycharm_reformat_prepass(
                issues
            )
            if pycharm_reformat_success:
                self.logger.info("✅ Applied PyCharm reformat prepass where available")

            force_prepass = self._preflight_config.force_prepass
            if tracker.delta() == 0 and not force_prepass:
                self.logger.debug(
                    "Skip refurb prepass: no file changes since last ruff/refurb run"
                )
                refreshed_refurb_issues: dict[str, list[Issue]] = {"refurb": []}
            else:
                refreshed_refurb_issues = await self._apply_refurb_fix_prepasses(
                    hook_results
                )
            tracker.capture()
            if refreshed_refurb_issues:
                issues = self._replace_refreshed_type_issues(
                    issues,
                    refreshed_refurb_issues,
                )
                self.logger.info("✅ Applied Refurb fix prepass where available")

            if not issues:
                self.logger.info(
                    "✅ Deterministic prepasses resolved all fast-stage issues"
                )
                return True

            self.logger.info(
                "🧹 Running deterministic fast-fix pass before AI analysis"
            )
            if tracker.delta() == 0 and not force_prepass:
                self.logger.debug(
                    "Skip fast fixes: no file changes since last ruff/refurb run"
                )
                deterministic_fix_success = True
            else:
                deterministic_fix_success = await self._execute_fast_fixes()
            if deterministic_fix_success:
                self.logger.info(
                    "✅ Deterministic fast fixes completed before AI analysis"
                )
            else:
                self.logger.warning(
                    "⚠️ Deterministic fast fixes did not complete cleanly; continuing with AI analysis"
                )

            project_path = str(self.pkg_path)
            analysis_coordinator = AnalysisCoordinator(
                project_path=project_path,
                debugger=get_ai_agent_debugger(),
            )
            fixer_coordinator = FixerCoordinator(project_path=project_path)

            self._attach_tier3_agent(fixer_coordinator, project_path)

            self._attach_fix_router(fixer_coordinator, project_path)
            validation_coordinator = ValidationCoordinator(
                project_path=Path(project_path)
            )

            result = await self._run_v2_ai_fix_iteration_loop(
                analysis_coordinator=analysis_coordinator,
                fixer_coordinator=fixer_coordinator,
                validation_coordinator=validation_coordinator,
                initial_issues=issues,
                hook_results=hook_results,
                stage=stage,
                initial_hook_total=initial_hook_total,
            )
            return result
        finally:
            self._active_ai_fix_scope_files = previous_scope_files

    def _attach_tier3_agent(
        self,
        fixer_coordinator: FixerCoordinator,
        project_path: str,
    ) -> None:
        from crackerjack.core.tier3_factory import build_iterative_agent

        try:
            agent = build_iterative_agent(
                project_root=Path(project_path),
            )
        except Exception as exc:
            logger.debug("Tier-3 attach raised (treating as no agent): %s", exc)
            agent = None
        if agent is None:
            logger.debug("Tier-3 disabled for this run (no agent available)")
            return
        fixer_coordinator.attach_iterative_agent(agent)
        logger.info("Tier-3 enabled for this run")

    def _attach_fix_router(
        self,
        fixer_coordinator: FixerCoordinator,
        project_path: str,
    ) -> None:
        from crackerjack.ai_fix.fix_router import build_fix_router

        self._fix_router = build_fix_router(fixer_coordinator)
        logger.debug(
            "FixRouter attached (registry=%d built-ins, classifier=classify)",
            len(fixer_coordinator.fixers),
        )

    async def _finalize_v2_iteration_loop(
        self,
        iteration: int,
        success: bool,
        fixer_coordinator: FixerCoordinator | None = None,
    ) -> None:
        self.progress_manager.end_iteration()
        self.progress_manager.finish_session(success=success, iteration_count=iteration)
        await self._event_bus.emit(
            RunFinished(
                run_id=self._run_id,
                iteration=iteration,
                success=success,
                total_iterations=iteration,
            )
        )

        if fixer_coordinator is not None:
            await self._finalize_promotions(fixer_coordinator)

    def _finalize_promotions_sync(self, fixer_coordinator: FixerCoordinator) -> None:
        try:
            from crackerjack.ai_fix.promotion_pipeline import (
                PromotionPipeline,
                PromotionSettings,
            )
        except ImportError as exc:
            self.logger.debug("PromotionPipeline unavailable: %s", exc)
            return

        skill_store = (
            fixer_coordinator.iterative_agent.skill_store
            if fixer_coordinator.iterative_agent is not None
            else None
        )
        if skill_store is None:
            return

        settings = PromotionSettings()
        pipeline = PromotionPipeline(
            settings=settings,
            skill_store=skill_store,
        )
        try:
            for signature in _list_signatures(skill_store):
                try:
                    result = pipeline.maybe_promote(signature)
                    if result.promoted: # type: ignore[attr-defined]
                        self.logger.info(
                            "Auto-promoted fixer for %s: %s",
                            signature,
                            result.pr_url,
                        ) # type: ignore[attr-defined]
                except Exception as exc: # noqa: BLE001 — defensive
                    self.logger.debug("Promotion for %s failed: %s", signature, exc)
        except Exception as exc: # noqa: BLE001 — defensive
            self.logger.debug("Promotion finalization raised: %s", exc)

    async def _finalize_promotions(self, fixer_coordinator: FixerCoordinator) -> None:
        self._finalize_promotions_sync(fixer_coordinator)
        return None

    async def _run_v2_ai_fix_iteration_loop(
        self,
        analysis_coordinator: AnalysisCoordinator,
        fixer_coordinator: FixerCoordinator,
        validation_coordinator: ValidationCoordinator,
        initial_issues: list[Issue],
        hook_results: Sequence[object],
        stage: str,
        initial_hook_total: int | None = None,
    ) -> bool:

        if initial_hook_total is None:
            initial_hook_total = self.progress_manager.compute_hook_total(hook_results)

        self.progress_manager.start_fix_session(
            stage=stage,
            initial_issue_count=initial_hook_total,
        )

        ctx = AutoFixContext(
            iteration=0,
            initial_issue_count=initial_hook_total,
            current_issues=initial_issues.copy(),
            previous_issues=initial_issues.copy(),
            previous_files_modified=[],
            previous_hook_statuses={},
            previous_fixes_applied=0,
            stage=stage,
            max_iterations=self._get_max_iterations(),
            hook_results=hook_results,
            initial_issues=initial_issues.copy(),
            no_progress_count=0,
            previous_issue_count=float("inf"),
            coordinator_set={},
        )

        async def _step(local_ctx: AutoFixContext) -> StepResult:
            return await self._v2_iteration_step(
                local_ctx,
                analysis_coordinator,
                fixer_coordinator,
                validation_coordinator,
            )

        return await self._run_iteration_loop_dispatch(ctx=ctx, step_fn=_step)

    async def _apply_type_tool_fix_prepasses(
        self, hook_results: Sequence[object]
    ) -> dict[str, list[Issue]]:
        refreshed_issues: dict[str, list[Issue]] = {}
        type_tool_files = self._collect_type_tool_files(hook_results)

        for tool_name, file_paths in type_tool_files.items():
            if tool_name == "zuban":
                continue

            adapter = self._create_type_tool_adapter(tool_name)
            if adapter is None:
                continue

            supports_fix = getattr(adapter, "supports_fix", None)
            if callable(supports_fix):
                try:
                    if not supports_fix():
                        continue
                except Exception:
                    continue

            if not self._run_native_tool_fix(adapter, tool_name, file_paths):
                continue

            refreshed_issues[tool_name] = await self._rerun_type_tool_check(
                adapter,
                tool_name,
                file_paths,
            )

        return refreshed_issues

    async def _apply_ruff_fix_prepasses(
        self, hook_results: Sequence[object]
    ) -> dict[str, list[Issue]]:
        refreshed_issues: dict[str, list[Issue]] = {}
        ruff_files = self._collect_ruff_files(hook_results)

        if not ruff_files:
            return refreshed_issues

        if not self._run_ruff_safe_fixes(ruff_files):
            return refreshed_issues

        adapter = self._create_type_tool_adapter("ruff")
        if adapter is None:
            return refreshed_issues

        rerun_issues = await self._rerun_type_tool_check(adapter, "ruff", ruff_files)
        for issue in rerun_issues:
            issue.stage = "ruff-check"

        refreshed_issues["ruff-check"] = rerun_issues
        return refreshed_issues

    async def _apply_refurb_fix_prepasses(
        self, hook_results: Sequence[object]
    ) -> dict[str, list[Issue]]:
        refreshed_issues: dict[str, list[Issue]] = {}
        refurb_files = self._collect_refurb_files(hook_results)

        if not refurb_files:
            return refreshed_issues

        if not self._run_refurb_safe_fixes(refurb_files):
            return refreshed_issues

        adapter = self._create_type_tool_adapter("refurb")
        if adapter is None:
            return refreshed_issues

        refreshed_issues["refurb"] = await self._rerun_type_tool_check(
            adapter,
            "refurb",
            refurb_files,
        )

        return refreshed_issues

    def _collect_zuban_files(self, hook_results: Sequence[object]) -> list[Path]:
        files: list[Path] = []
        for result in hook_results:
            if not self._validate_hook_result(result):
                continue
            status = getattr(result, "status", "")
            if not isinstance(status, str) or status.lower() not in (
                "failed",
                "timeout",
            ):
                continue
            hook_name = getattr(result, "name", "").lower()
            if hook_name != "zuban":
                continue
            for file_path in self._extract_hook_result_files(result):
                if file_path not in files:
                    files.append(file_path)
        return files

    def _fix_zuban_missing_imports_in_mypy_ini(self) -> int:
        import re

        mypy_ini_path = self.pkg_path / "mypy.ini"
        if not mypy_ini_path.exists():
            return 0
        content = mypy_ini_path.read_text()
        if "ignore_missing_imports" in content.lower():
            return 0
        new_content = re.sub(
            r"(\[mypy\][^\[]*)",
            lambda m: m.group(0).rstrip() + "\nignore_missing_imports = True\n",
            content,
            count=1,
        )
        if new_content == content:
            return 0
        mypy_ini_path.write_text(new_content)
        return 1

    async def _apply_zuban_fix_prepass(
        self, hook_results: Sequence[object]
    ) -> dict[str, list[Issue]]:
        refreshed: dict[str, list[Issue]] = {}
        zuban_files = self._collect_zuban_files(hook_results)
        if not zuban_files:
            return refreshed

        all_issues = self._collect_fixable_issues(hook_results)
        import_errors = [
            i
            for i in all_issues
            if getattr(i, "stage", "") == "zuban"
            and "import-not-found" in (getattr(i, "code", "") or "")
        ]

        if import_errors:
            fixed = self._fix_zuban_missing_imports_in_mypy_ini()
            if fixed:
                self.logger.info(
                    "✅ Added ignore_missing_imports to mypy.ini "
                    f"({len(import_errors)} import-not-found errors suppressed)"
                )

        adapter = self._create_type_tool_adapter("zuban")
        if adapter is None:
            return refreshed

        refreshed["zuban"] = await self._rerun_type_tool_check(
            adapter, "zuban", zuban_files
        )
        return refreshed

    async def _apply_pycharm_diagnostics_context(
        self,
        issues: list[Issue],
    ) -> list[Issue]:
        adapter = self._pycharm_adapter
        if adapter is None:
            return issues

        relevant_issues = [
            issue
            for issue in issues
            if issue.file_path
            and issue.type in {IssueType.TYPE_ERROR, IssueType.IMPORT_ERROR}
        ]
        if not relevant_issues:
            return issues

        for issue in relevant_issues:
            file_path = issue.file_path
            if not file_path:
                continue

            try:
                problems = await adapter.get_file_problems(file_path, errors_only=True)
            except Exception as e:
                self.logger.debug("PyCharm diagnostics failed for %s: %s", file_path, e)
                continue

            if not problems:
                continue

            detail_lines = [
                f"PyCharm diagnostics found {len(problems)} problem(s) in {file_path}"
            ]
            for problem in problems[:3]:
                message = problem.get("message", "")
                severity = problem.get("severity", "warning")
                line = problem.get("line")
                location = f"line {line}" if line else "file-level"
                detail_lines.append(f"{severity}: {location}: {message}")

            existing_details = issue.details.copy()
            existing_details.extend(
                line for line in detail_lines if line not in existing_details
            )
            issue.details = existing_details

        return issues

    async def _apply_pycharm_hook_diagnostics_context(
        self,
        issues: list[Issue],
        stage: str,
    ) -> list[Issue]:
        if stage != "comprehensive":
            return issues
        return await self._apply_pycharm_diagnostics_context(issues)

    async def _apply_pycharm_reformat_prepass(self, issues: list[Issue]) -> bool:
        adapter = self._pycharm_adapter
        if adapter is None:
            return False

        file_paths: list[Path] = []
        for issue in issues:
            if not issue.file_path:
                continue
            path = Path(issue.file_path)
            if path.suffix not in {".py", ".pyi"}:
                continue
            if path in file_paths:
                continue
            file_paths.append(path)

        if not file_paths:
            return False

        any_reformatted = False
        for file_path in file_paths:
            try:
                reformatted = await adapter.reformat_file(file_path) # type: ignore noqa: FURB123 (Path objects must be coerced for adapter API)
            except Exception as e:
                self.logger.debug(
                    "PyCharm reformat failed for %s: %s",
                    file_path,
                    e,
                )
                continue

            if reformatted:
                any_reformatted = True

        return any_reformatted

    def _collect_type_tool_files(
        self, hook_results: Sequence[object]
    ) -> dict[str, list[Path]]:
        files_by_tool: dict[str, list[Path]] = {}

        for result in hook_results:
            if not self._validate_hook_result(result):
                continue

            status = getattr(result, "status", "")
            if not isinstance(status, str) or status.lower() not in (
                "failed",
                "timeout",
            ):
                continue

            hook_name = getattr(result, "name", "").lower()
            if hook_name not in {"ty", "pyrefly"}:
                continue

            file_paths = self._extract_hook_result_files(result)
            if not file_paths:
                continue

            bucket = files_by_tool.setdefault(hook_name, [])
            for file_path in file_paths:
                if file_path not in bucket:
                    bucket.append(file_path)

        return files_by_tool

    def _collect_refurb_files(self, hook_results: Sequence[object]) -> list[Path]:
        files: list[Path] = []

        for result in hook_results:
            if not self._validate_hook_result(result):
                continue

            status = getattr(result, "status", "")
            if not isinstance(status, str) or status.lower() not in (
                "failed",
                "timeout",
            ):
                continue

            hook_name = getattr(result, "name", "").lower()
            if hook_name != "refurb":
                continue

            for file_path in self._extract_hook_result_files(result):
                if file_path not in files:
                    files.append(file_path)

        return files

    def _run_refurb_safe_fixes(self, file_paths: list[Path]) -> bool:
        if not file_paths:
            return False

        fixer = SafeRefurbFixer()
        total_fixes = 0
        for file_path in file_paths:
            total_fixes += fixer.fix_file(file_path)

        if total_fixes <= 0:
            return False

        self.logger.info(
            "Applied deterministic refurb prepass to %s file(s) for %s fix(es)",
            len(file_paths),
            total_fixes,
        )
        return True

    def _collect_ruff_files(self, hook_results: Sequence[object]) -> list[Path]:
        files: list[Path] = []

        for result in hook_results:
            if not self._validate_hook_result(result):
                continue

            status = getattr(result, "status", "")
            if not isinstance(status, str) or status.lower() not in (
                "failed",
                "timeout",
            ):
                continue

            hook_name = getattr(result, "name", "").lower()
            if hook_name not in {"ruff", "ruff-check"}:
                continue

            for file_path in self._extract_hook_result_files(result):
                if file_path not in files:
                    files.append(file_path)

        return files

    def _run_ruff_safe_fixes(self, file_paths: list[Path]) -> bool:
        if not file_paths:
            return False

        any_fixed = False
        for file_path in file_paths:
            if self._run_targeted_python_fixes(file_path): # type: ignore
                any_fixed = True

        if any_fixed:
            self.logger.info(
                "Applied deterministic ruff prepass to %s file(s)",
                len(file_paths),
            )

        return any_fixed

    def _extract_hook_result_files(self, result: object) -> list[Path]:
        file_values: list[t.Any] = []

        files_checked = getattr(result, "files_checked", None)
        if isinstance(files_checked, list):
            file_values.extend(files_checked)

        qa_result = getattr(result, "qa_result", None)
        qa_files = getattr(qa_result, "files_checked", None)
        if isinstance(qa_files, list):
            file_values.extend(qa_files)

        hook_output = self._extract_raw_output(result)
        if hook_output:
            file_values.extend(
                self._extract_issue_file_paths_from_lines(
                    extract_issue_lines(
                        hook_output,
                        tool_name=str(getattr(result, "name", "")),
                    )
                )
            )
            issues_found = getattr(result, "issues_found", None)
            if isinstance(issues_found, list):
                file_values.extend(
                    self._extract_issue_file_paths_from_lines(
                        extract_issue_lines(
                            "\n".join(str(issue) for issue in issues_found),
                            tool_name=str(getattr(result, "name", "")),
                        )
                    )
                )

        paths: list[Path] = []
        for value in file_values:
            try:
                path = Path(value)
            except TypeError:
                continue

            if path not in paths:
                paths.append(path)

        return paths

    def _extract_issue_file_paths_from_lines(self, lines: list[str]) -> list[str]:
        if not lines:
            return []

        paths: list[str] = []
        issue_pattern = re.compile(
            r"^(.+?):\s*\d+(?::\s*\d+)?\s*:",
        )

        for line in lines:
            match = issue_pattern.match(line.strip())
            if not match:
                continue

            file_path = match.group(1).strip()
            if file_path and file_path not in paths:
                paths.append(file_path)

        return paths

    def _create_type_tool_adapter(self, tool_name: str) -> object | None:
        adapter_name = DefaultAdapterFactory().get_adapter_name(tool_name)
        if not adapter_name:
            return None

        try:
            return DefaultAdapterFactory().create_adapter(adapter_name)
        except Exception as e:
            self.logger.debug("Could not create adapter for %s: %s", tool_name, e)
            return None

    def _run_native_tool_fix(
        self,
        adapter: object,
        tool_name: str,
        file_paths: list[Path],
    ) -> bool:
        if not file_paths:
            return False

        settings = self._get_adapter_settings(adapter)
        self._configure_settings_for_fix(settings, adapter)

        command = self._build_fix_command(adapter, tool_name, file_paths)
        if not command:
            return False

        if command[0] == tool_name:
            command = ["uv", "run", *command]

        return self._run_fix_command(command, f"{tool_name} native fix")

    def _get_adapter_settings(self, adapter: object) -> object | None:
        settings = getattr(adapter, "settings", None)
        if settings is not None:
            return settings
        try:
            return getattr(adapter, "get_default_config", lambda: None)()
        except Exception:
            return None

    def _configure_settings_for_fix(
        self, settings: object | None, adapter: object
    ) -> None:
        if settings is None:
            return

        cfg = t.cast("_MutableSettings", settings)

        try:
            cfg.fix_enabled = True
        except (AttributeError, TypeError):
            return
        if hasattr(settings, "add_ignore_enabled"):
            cfg.add_ignore_enabled = False
        if hasattr(settings, "suppress_errors"):
            cfg.suppress_errors = False
        if hasattr(settings, "baseline_file"):
            cfg.baseline_file = None

        setattr(adapter, "settings", settings)

    def _build_fix_command(
        self, adapter: object, tool_name: str, file_paths: list[Path]
    ) -> list[str] | None:
        build_command = getattr(adapter, "build_command", None)
        if not callable(build_command):
            return None
        try:
            return build_command(file_paths)
        except Exception as e:
            self.logger.debug("Could not build fix command for %s: %s", tool_name, e)
            return None

    async def _rerun_type_tool_check(
        self,
        adapter: object,
        tool_name: str,
        file_paths: list[Path],
    ) -> list[Issue]:
        check = getattr(adapter, "check", None)
        if not callable(check):
            return []

        try:
            qa_result = await check(files=file_paths)
        except Exception as e:
            self.logger.debug("Could not rerun %s after fix: %s", tool_name, e)
            return []

        parsed_issues = getattr(qa_result, "parsed_issues", None)
        if not isinstance(parsed_issues, list):
            return []

        return self._convert_parsed_issues_to_issues(tool_name, parsed_issues)

    def _replace_refreshed_type_issues(
        self,
        issues: list[Issue],
        refreshed_type_issues: dict[str, list[Issue]],
    ) -> list[Issue]:
        refreshed_tools = set(refreshed_type_issues)
        if not refreshed_tools:
            return issues

        updated_issues = [
            issue for issue in issues if issue.stage not in refreshed_tools
        ]
        for tool_name in sorted(refreshed_tools):
            updated_issues.extend(refreshed_type_issues[tool_name])
        return updated_issues

    def _filter_fixable_issues(self, issues: list[Issue]) -> list[Issue]:
        fixable_issues = [i for i in issues if i.file_path]
        skipped_issues = [i for i in issues if not i.file_path]

        _infra_files = {"autofix_coordinator.py"}
        infra_issues = [
            i
            for i in fixable_issues
            if i.file_path and any(f in i.file_path for f in _infra_files)
        ]
        if infra_issues:
            fixable_issues = [i for i in fixable_issues if i not in infra_issues]
            self.logger.info(
                f"🛡️ Excluding {len(infra_issues)} infrastructure issues from AI-fix "
                f"(pipeline files must not be self-modified)"
            )

        if skipped_issues:
            self.logger.warning(
                f"⚠️ Skipping {len(skipped_issues)} issues without file_path: "
                f"{', '.join(i.message[:50] + '...' for i in skipped_issues[:3])}"
            )

        if not fixable_issues:
            self.logger.info("✅ No fixable issues (all require manual intervention)")

        return fixable_issues

    async def _create_fix_plans(
        self, analysis_coordinator: AnalysisCoordinator, issues: list[Issue]
    ) -> list[FixPlan] | None:
        import asyncio

        self.logger.info("🔍 Stage 2: Analysis Phase - creating FixPlans")
        try:
            try:
                asyncio.get_running_loop()
                self.logger.debug("Running in existing event loop")
                plans = await analysis_coordinator.analyze_issues(issues)
            except RuntimeError:
                self.logger.debug("Creating new event loop for analysis")
                plans = asyncio.run(analysis_coordinator.analyze_issues(issues))

            self.logger.info(f"✅ Created {len(plans)} FixPlans")
            return plans.copy()
        except Exception as e:
            self._collect_error("Analysis Error", str(e))
            return None

    @staticmethod
    def _issue_key(file_path: str, line_number: int | None, issue_type: str) -> str:
        return f"{file_path}:{line_number or ''}:{issue_type}"

    async def _execute_plans_with_validation(
        self,
        plans: list[FixPlan],
        fixer_coordinator: FixerCoordinator,
        validation_coordinator: ValidationCoordinator,
        analysis_coordinator: AnalysisCoordinator,
        issues: list[Issue],
    ) -> list[FixResult]:
        results: list[FixResult] = []
        plan_to_issue = {
            self._issue_key(i.file_path, i.line_number, i.type.value): i
            for i in issues
            if i.file_path
        }

        viable_plans, skipped_plans = self._filter_viable_plans(plans, results)
        if skipped_plans:
            self.logger.info(
                f"⏭️ Skipping {len(skipped_plans)} plans with no viable changes (would fail all 3 retries)"
            )

        viable_plans = self._deduplicate_plans(viable_plans)

        viable_plans, previously_failed = self._filter_previously_failed_plans(
            viable_plans, results
        )

        viable_plans, phantom_count = self._filter_phantom_line_plans(
            viable_plans, issues, results
        )
        if phantom_count:
            self.logger.info(
                f"\033[2m⏭️ Skipped {phantom_count} phantom-line plan(s) "
                f"(targeted lines with no real reported issue)\033[0m"
            )

        run_plan = self._make_plan_runner(
            fixer_coordinator,
            validation_coordinator,
            analysis_coordinator,
            plan_to_issue,
        )
        dispatcher = ParallelDispatcher(
            execute_plan=run_plan,
            bus=self._event_bus,
            run_id=self._run_id,
            iteration=0,
        )
        dispatch_result: DispatchResult = await dispatcher.dispatch(viable_plans)
        results.extend(dispatch_result.results)

        if dispatch_result.deferred:
            self.logger.info(
                f"⏭️ Early exit: {len(dispatch_result.deferred)} plans deferred to next iteration"
            )

        return results

    def _filter_viable_plans(
        self, plans: list[FixPlan], results: list[FixResult]
    ) -> tuple[list[FixPlan], list[FixPlan]]:
        viable = [p for p in plans if p.changes]
        skipped = [p for p in plans if not p.changes]
        for p in skipped:
            results.append(
                FixResult(
                    success=False,
                    confidence=0.0,
                    remaining_issues=[
                        f"No viable changes for {p.issue_type} at {p.file_path}"
                    ],
                )
            )
        return viable, skipped

    def _deduplicate_plans(self, plans: list[FixPlan]) -> list[FixPlan]:
        seen: set[tuple[str, str, int | None]] = set()
        deduped: list[FixPlan] = []
        for p in plans:
            line_number = p.changes[0].line_range[0] if p.changes else None
            key = (p.file_path, p.issue_type, line_number)
            if key not in seen:
                seen.add(key)
                deduped.append(p)
        if len(deduped) < len(plans):
            self.logger.info(f"🔀 Deduplicated {len(plans)} → {len(deduped)} plans")
        return deduped

    def _filter_previously_failed_plans(
        self, plans: list[FixPlan], results: list[FixResult]
    ) -> tuple[list[FixPlan], int]:
        retry_plans: list[FixPlan] = []
        failed_count = 0
        for p in plans:
            pk = self._issue_key(
                p.file_path,
                p.changes[0].line_range[0] if p.changes else None,
                p.issue_type,
            )
            if pk in self._failed_issue_keys:
                self.logger.info(
                    f"\033[2m⏭️ Skipping previously failed: {p.file_path} ({p.issue_type})\033[0m"
                )
                results.append(
                    FixResult(
                        success=False,
                        confidence=0.0,
                        remaining_issues=[
                            f"Previously failed: {p.issue_type} at {p.file_path}"
                        ],
                    )
                )
                failed_count += 1
            else:
                retry_plans.append(p)
        return retry_plans, failed_count

    def _filter_phantom_line_plans(
        self,
        plans: list[FixPlan],
        issues: list[Issue],
        results: list[FixResult],
    ) -> tuple[list[FixPlan], int]:
        real_lines_by_file: dict[str, set[int]] = {}
        for issue in issues:
            if issue.file_path and issue.line_number is not None:
                real_lines_by_file.setdefault(issue.file_path, set()).add(
                    issue.line_number
                )

        viable: list[FixPlan] = []
        phantom_count = 0
        for plan in plans:
            if not plan.changes:
                viable.append(plan)
                continue
            real_in_file = real_lines_by_file.get(plan.file_path, set())
            overlaps = any(
                start <= real_line <= end
                for change in plan.changes
                for start, end in (change.line_range,)
                for real_line in real_in_file
            )
            if overlaps:
                viable.append(plan)
            else:
                phantom_count += 1
                self.logger.warning(
                    f"\033[2m👻 Phantom line plan: {plan.file_path} "
                    f"({plan.issue_type}) targets {plan.changes[0].line_range} "
                    f"but no real issue at those lines — skipping\033[0m"
                )
                results.append(
                    FixResult(
                        success=False,
                        confidence=0.0,
                        remaining_issues=[
                            f"Phantom line: {plan.issue_type} at {plan.file_path} "
                            f"({plan.changes[0].line_range}) does not match any "
                            f"reported issue"
                        ],
                    )
                )
        return viable, phantom_count

    def _make_plan_runner(
        self,
        fixer_coordinator: FixerCoordinator,
        validation_coordinator: ValidationCoordinator,
        analysis_coordinator: AnalysisCoordinator,
        plan_to_issue: dict[str, Issue],
    ):

        async def _run_plan(plan: FixPlan) -> FixResult:
            plan_key = self._issue_key(
                plan.file_path,
                plan.changes[0].line_range[0] if plan.changes else None,
                plan.issue_type,
            )

            started_at = time.monotonic()
            await self._event_bus.emit(
                FixSessionStarted(
                    run_id=self._run_id,
                    iteration=0,
                    issue_signature=plan_key,
                    file=plan.file_path,
                    issue_type=plan.issue_type,
                )
            )
            no_op_count = 0
            try:
                result = await self._execute_single_plan_with_retry(
                    plan,
                    fixer_coordinator,
                    validation_coordinator,
                    analysis_coordinator,
                    plan_to_issue,
                    plan_key,
                    None,
                )
            except Exception as exc:
                result = FixResult(
                    success=False,
                    confidence=0.0,
                    remaining_issues=[f"Exception: {exc}"],
                )
                no_op_count = 1
            no_op_count += self._count_no_op_messages(result)
            if not result.success:
                self._failed_issue_keys.add(plan_key)
            await self._event_bus.emit(
                FixSessionFinished(
                    run_id=self._run_id,
                    iteration=0,
                    issue_signature=plan_key,
                    file=plan.file_path,
                    success=result.success,
                    final_tier=1 if result.success else 0,
                    total_duration_s=time.monotonic() - started_at,
                    no_op_count=no_op_count,
                )
            )
            return result

        return _run_plan

    @staticmethod
    def _count_no_op_messages(result: FixResult) -> int:
        for issue in result.remaining_issues:
            if "no-op fix" in issue:
                return 1
        return 0

    async def _execute_single_plan_with_retry(
        self,
        plan: FixPlan,
        fixer_coordinator: FixerCoordinator,
        validation_coordinator: ValidationCoordinator,
        analysis_coordinator: AnalysisCoordinator,
        plan_to_issue: dict[str, Issue],
        plan_key: str,
        bar: Any, # type: ignore
    ) -> FixResult:
        accumulated_feedback: list[str] = []
        per_issue_timeout = self._get_per_issue_timeout()
        plan_loc = (
            f"{plan.file_path}:{plan.changes[0].line_range[0]}"
            if plan.changes
            else plan.file_path
        )

        if not self._is_writable_target(plan.file_path):
            feedback = f"Workspace is not writable: {plan.file_path}"
            self.logger.warning(
                f"\033[91m✗ [FixerCoordinator] Non-retryable workspace write failure ({plan_loc})\033[0m"
            )
            self._collect_error("Workspace Write Error", feedback, plan.file_path)
            if bar:
                bar()
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=[feedback],
            )

        if "backup" in Path(plan.file_path).name.split("."):
            self.logger.debug(f"Skipping plan: {plan.file_path} is a backup file")
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=["plan target is a backup file"],
            )

        for attempt in range(3):


            if self._is_global_budget_exhausted():
                budget = self._get_global_retry_budget()
                feedback = (
                    f"Global retry budget exhausted "
                    f"({self._global_attempt_count}/{budget} attempts)"
                )
                self.logger.error(
                    f"\033[91m⛔ [FixerCoordinator] {feedback}; bailing run\033[0m"
                )
                return self._fail_plan(
                    "Budget Exhausted",
                    feedback,
                    feedback,
                    plan.file_path,
                    accumulated_feedback,
                    bar,
                )
            self._global_attempt_count += 1

            try:
                success, plan_results, feedback = await asyncio.wait_for(
                    self._execute_plan_with_validation(
                        plan, fixer_coordinator, validation_coordinator, bar
                    ),
                    timeout=per_issue_timeout,
                )
            except TimeoutError:
                feedback = f"Timed out after {per_issue_timeout}s"
                self.logger.warning(
                    f"\033[91m⏱️ [FixerCoordinator] Plan timed out "
                    f"({plan_loc}), "
                    f"attempt {attempt + 1}/3\033[0m"
                )
                accumulated_feedback.append(feedback)
                if attempt < 2:
                    plan = await self._regenerate_plan_with_feedback(
                        plan,
                        plan_key,
                        analysis_coordinator,
                        plan_to_issue,
                        accumulated_feedback,
                    )
                continue

            if success and plan_results:
                return plan_results[0]

            accumulated_feedback.append(f"Attempt {attempt + 1}: {feedback}")

            terminal = self._classify_terminal_failure(feedback, plan_results, plan_loc)
            if terminal is not None:
                error_type, log_message = terminal
                return self._fail_plan(
                    error_type,
                    log_message,
                    feedback,
                    plan.file_path,
                    accumulated_feedback,
                    bar,
                )

            if attempt < 2:
                previous_plan = plan
                plan = await self._regenerate_plan_with_feedback(
                    plan,
                    plan_key,
                    analysis_coordinator,
                    plan_to_issue,
                    accumulated_feedback,
                )
                if self._plans_equivalent(previous_plan, plan):
                    return self._fail_plan(
                        "No-Progress Error",
                        f"\033[91m✗ [FixerCoordinator] No progress — regenerated "
                        f"plan is identical to the failed one ({plan_loc})\033[0m",
                        f"Regenerated plan identical after: {feedback}",
                        plan.file_path,
                        accumulated_feedback,
                        bar,
                    )

        return self._fail_plan(
            "Max Retries Error",
            f"\033[91m✗ [FixerCoordinator] Max retries exceeded ({plan_loc})\033[0m",
            f"Failed after 3 attempts: {'; '.join(accumulated_feedback)}",
            plan.file_path,
            accumulated_feedback,
            bar,
        )

    def _fail_plan(
        self,
        error_type: str,
        log_message: str,
        feedback: str,
        file_path: str,
        accumulated_feedback: list[str],
        bar: Any, # type: ignore
    ) -> FixResult:
        self.logger.warning(log_message)
        self._collect_error(error_type, feedback, file_path)
        if bar:
            bar()
        return FixResult(
            success=False,
            confidence=0.0,
            remaining_issues=accumulated_feedback,
        )

    def _classify_terminal_failure(
        self,
        feedback: str,
        plan_results: list[FixResult] | None,
        plan_loc: str,
    ) -> tuple[str, str] | None:
        if self._is_non_retryable_write_failure(feedback, plan_results):
            return (
                "Workspace Write Error",
                f"\033[91m✗ [FixerCoordinator] Non-retryable write failure "
                f"({plan_loc})\033[0m",
            )
        if self._is_no_op_failure(feedback, plan_results):
            return (
                "No-Op Fix",
                f"\033[91m✗ [FixerCoordinator] No-op fix — not retryable "
                f"({plan_loc})\033[0m",
            )
        return None

    async def _regenerate_plan_with_feedback(
        self,
        plan: FixPlan,
        plan_key: str,
        analysis_coordinator: AnalysisCoordinator,
        plan_to_issue: dict[str, Issue],
        feedback: list[str],
    ) -> FixPlan:
        plan_loc = (
            f"{plan.file_path}:{plan.changes[0].line_range[0]}"
            if plan.changes
            else plan.file_path
        )
        self.logger.info(
            f"\033[93m🔄 [AnalysisCoordinator] Regenerating plan with feedback "
            f"({plan_loc})\033[0m"
        )

        source_issue = plan_to_issue.get(plan_key)
        if not source_issue:
            source_issue = plan_to_issue.get(plan.file_path)
        if not source_issue:
            return plan

        enhanced_issue = self._enhance_issue_with_feedback(source_issue, feedback)
        try:
            new_plans = await asyncio.wait_for(
                analysis_coordinator.analyze_issues([enhanced_issue]),
                timeout=30,
            )
            if new_plans:
                self.logger.info(
                    f"📋 Re-generated plan with {len(new_plans[0].changes)} changes"
                )
                return new_plans[0]
        except TimeoutError:
            self.logger.warning(
                f"\033[91m⏱️ [AnalysisCoordinator] Plan regeneration timed out "
                f"({plan_loc})\033[0m"
            )
        except Exception as e:
            self.logger.warning(f"Could not regenerate plan: {e}")

        return plan

    def _check_execution_results(self, results: list[FixResult]) -> bool:
        success_count = sum(1 for r in results if r.success)
        total_count = len(results)
        self._success_count = success_count
        self._total_count = total_count

        self._display_error_summary()

        if total_count > 0:
            self.logger.info(
                f"📊 V2 Pipeline Results: {success_count}/{total_count} plans succeeded"
            )

        return total_count > 0 and success_count == total_count

    def _create_backup(self, file_path: str) -> str:
        import shutil
        import tempfile

        source_path = Path(file_path)
        backup_dirs = [
            source_path.parent,
            self.pkg_path / ".crackerjack" / "backups",
            Path(tempfile.gettempdir()) / "crackerjack" / "backups",
        ]

        for backup_dir in backup_dirs:
            try:
                backup_dir.mkdir(parents=True, exist_ok=True)
                backup_path = backup_dir / f"{source_path.name}.backup"
                shutil.copy2(source_path, backup_path)
                metadata_path = backup_path.with_suffix(backup_path.suffix + ".json")
                metadata_path.write_text(
                    json.dumps({"original_path": source_path}, default=str), # noqa: FURB123 (Path objects must be coerced for JSON)
                    encoding="utf-8",
                )
                self.logger.debug(f"Created backup: {backup_path}")
                return backup_path # type: ignore
            except OSError as exc:
                self.logger.debug(
                    "Backup path unavailable, trying next candidate: %s",
                    exc,
                )
                continue

        raise OSError(f"Unable to create backup for {file_path}")

    def _restore_backup(self, backup_path: str) -> None:
        import shutil

        backup_file = Path(backup_path)
        metadata_path = backup_file.with_suffix(backup_file.suffix + ".json")
        if metadata_path.exists():
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            file_path = Path(metadata["original_path"])
        else:
            file_path = Path(backup_path.replace(".backup", ""))

        shutil.move(str(backup_file), file_path)
        if metadata_path.exists():
            metadata_path.unlink(missing_ok=True)
        self.logger.debug(f"Restored backup: {file_path}")

    def _is_non_retryable_write_failure(
        self,
        feedback: str,
        plan_results: list[FixResult] | None = None,
    ) -> bool:
        text_parts = [feedback.lower()]
        if plan_results:
            for result in plan_results:
                text_parts.extend(issue.lower() for issue in result.remaining_issues)

        text = " ".join(text_parts)
        failure_markers = (
            "operation not permitted",
            "permission denied",
            "read-only database",
            "read only",
            "failed to write",
            "failed to create backup",
            "failed to open",
        )
        return any(marker in text for marker in failure_markers)

    def _is_no_op_failure(
        self,
        feedback: str,
        plan_results: list[FixResult] | None = None,
    ) -> bool:
        return is_no_op_failure(feedback, plan_results)

    def _plans_equivalent(self, first: FixPlan, second: FixPlan) -> bool:
        return first.file_path == second.file_path and first.changes == second.changes

    def _is_writable_target(self, file_path: str) -> bool:
        path = Path(file_path)
        if path.exists():
            return os.access(path, os.W_OK)
        return os.access(path.parent, os.W_OK)

    def _enhance_issue_with_feedback(
        self, issue: Issue, feedback_history: list[str]
    ) -> Issue:

        enhanced_details = issue.details.copy() if issue.details else []
        enhanced_details.append("--- Previous Attempt Feedback ---")
        for i, feedback in enumerate(feedback_history[-3:], 1):
            truncated = feedback[:200] + "..." if len(feedback) > 200 else feedback
            enhanced_details.append(f"[{i}] {truncated}")

        return Issue(
            type=issue.type,
            severity=issue.severity,
            message=f"{issue.message} (retry with feedback)",
            file_path=issue.file_path,
            line_number=issue.line_number,
            details=enhanced_details,
            stage=issue.stage,
        )

    _swarm_manager: t.Any = None # type: ignore[misc]

    @property
    def swarm_enabled(self) -> bool:
        return os.environ.get("CRACKERJACK_SWARM", "1") == "1"

    async def _get_swarm_manager(self) -> t.Any:
        if self._swarm_manager is None:
            from crackerjack.services.swarm_client import SwarmManager

            worker_count = int(os.environ.get("CRACKERJACK_SWARM_WORKERS", "4"))
            mcp_port = int(os.environ.get("CRACKERJACK_SWARM_MCP_PORT", "8680"))

            self._swarm_manager = SwarmManager(
                project_path=self.pkg_path,
                prefer_parallel=True,
                worker_count=worker_count,
                mcp_port=mcp_port,
                agent_executor=self._create_swarm_agent_executor(),
            )

            await self._swarm_manager.initialize()

            if self._swarm_manager.is_parallel:
                self.logger.info(
                    f"🐝 Swarm mode active: {worker_count} parallel workers"
                )
            else:
                self.logger.info("🔄 Swarm mode: sequential fallback")

        return self._swarm_manager

    def _create_swarm_agent_executor(
        self,
    ) -> t.Callable[[t.Any], t.Awaitable[t.Any]]:

        async def executor(task: t.Any) -> t.Any:
            from crackerjack.services.swarm_client import SwarmResult

            try:
                result = await self._execute_single_agent_fix(
                    issue_type=task.issue_type,
                    file_paths=task.file_paths,
                    prompt=task.prompt,
                    context=task.context,
                )

                return SwarmResult(
                    task_id=task.task_id,
                    worker_id="",
                    success=result.get("success", False),
                    files_modified=result.get("files_modified", []),
                    fixes_applied=result.get("fixes_applied", 0),
                    errors=result.get("errors", []),
                )
            except Exception as e:
                from crackerjack.services.swarm_client import SwarmResult

                return SwarmResult(
                    task_id=task.task_id,
                    worker_id="",
                    success=False,
                    errors=[str(e)],
                )

        return executor

    async def _execute_single_agent_fix(
        self,
        issue_type: str,
        file_paths: list[str],
        prompt: str,
        context: dict[str, t.Any],
    ) -> dict[str, t.Any]:
        from pathlib import Path

        from crackerjack.agents.base import AgentContext, Issue, IssueType, Priority

        issue_type_map = {
            "typing": IssueType.TYPE_ERROR,
            "refurb": IssueType.REFURB,
            "complexity": IssueType.COMPLEXITY,
            "security": IssueType.SECURITY,
            "formatting": IssueType.FORMATTING,
            "import": IssueType.IMPORT_ERROR,
            "test": IssueType.TEST_FAILURE,
            "documentation": IssueType.DOCUMENTATION,
        }

        mapped_type = issue_type_map.get(issue_type.lower(), IssueType.TYPE_ERROR)

        issues = []
        for file_path in file_paths:
            issue = Issue(
                type=mapped_type,
                severity=Priority.MEDIUM,
                message=prompt,
                file_path=str(Path(file_path)),
                line_number=context.get("line"),
                details=[context.get("original_message", "")],
            )
            issues.append(issue)

        if not issues:
            return {"success": False, "errors": ["No issues to fix"]}

        try:
            coordinator = self._setup_ai_fix_coordinator()
            context_obj = AgentContext(project_path=self.pkg_path)

            results = []
            for _issue in issues:
                result = coordinator.analyze_and_fix(context_obj) # type: ignore
                results.append(result)

            success = any(r.success for r in results if hasattr(r, "success"))
            files_modified = list(
                set(
                    str(r.file_path)
                    for r in results
                    if hasattr(r, "file_path") and r.file_path
                )
            )
            fixes_applied = sum(
                r.fixes_applied for r in results if hasattr(r, "fixes_applied")
            )
            errors = [
                e
                for r in results
                if hasattr(r, "errors") and r.errors
                for e in r.errors
            ]

            return {
                "success": success,
                "files_modified": files_modified,
                "fixes_applied": fixes_applied,
                "errors": errors,
            }

        except Exception as e:
            self.logger.error(f"Swarm agent execution failed: {e}")
            return {"success": False, "errors": [str(e)]}

    async def _apply_swarm_fixes(
        self,
        issues: list[Issue],
        stage: str = "comprehensive",
    ) -> bool:
        if not issues:
            return True

        if not self.swarm_enabled:
            self.logger.debug("Swarm mode disabled, using standard pipeline")
            return False

        try:
            manager = await self._get_swarm_manager()

            issue_dicts = [
                {
                    "type": i.type.value if hasattr(i.type, "value") else str(i.type),
                    "file": str(i.file_path) if i.file_path else "",
                    "message": i.message,
                    "priority": i.severity.value if hasattr(i.severity, "value") else 0,
                    "line": i.line_number,
                    "context": {
                        "details": i.details.copy() if i.details else [],
                    },
                }
                for i in issues
            ]

            results = await manager.execute_fixes(issue_dicts)

            success_count = sum(1 for r in results if r.success)
            total_count = len(results)

            self._success_count = success_count
            self._total_count = total_count

            for result in results:
                if result.success:
                    self.logger.info(
                        f"✅ Swarm fix: {result.task_id} - "
                        f"{result.fixes_applied} fixes in {len(result.files_modified)} files"
                    )
                else:
                    self.logger.warning(
                        f"❌ Swarm fix failed: {result.task_id} - "
                        f"{', '.join(result.errors[:2])}"
                    )
                    self._collect_error(
                        "Swarm Fix Error",
                        "; ".join(result.errors[:2]),
                        result.files_modified[0] if result.files_modified else "",
                    )

            await manager.shutdown()

            self.logger.info(
                f"🐝 Swarm results: {success_count}/{total_count} tasks succeeded "
                f"(mode: {manager.mode.value})"
            )

            return success_count > 0

        except Exception as e:
            self.logger.error(f"Swarm fixing failed: {e}")
            self._collect_error("Swarm Error", str(e))
            return False


def _extract_issue_count_from_json(output: str, tool_name: str) -> int | None:
    try:
        data = json.loads(output)
        return _count_issues_for_tool(data, tool_name)
    except (json.JSONDecodeError, TypeError):
        return None


def _count_issues_for_tool(data: object, tool_name: str) -> int | None:
    if tool_name in ("ruff", "ruff-check", "mypy", "zuban", "pyrefly", "ty", "pyright"):
        return _count_list_data(data)
    if tool_name == "bandit":
        return _count_bandit_results(data)
    if tool_name == "semgrep":
        return _count_semgrep_results(data)
    if tool_name == "pytest":
        return _count_pytest_results(data)
    return None


def _count_list_data(data: object) -> int | None:
    return len(data) if isinstance(data, list) else None


@dataclass
class StepResult:
    success: bool
    fixes_applied: int = 0
    files_modified: list[Path] = field(default_factory=list)
    failure_reason: str = ""


@dataclass
class RouterOutcome:
    remaining_issues: list[Issue] = field(default_factory=list)
    fixes_applied: int = 0
    fully_resolved: bool = False


@dataclass
class AutoFixContext:
    iteration: int = 0
    initial_issue_count: int = 0
    current_issues: list[Issue] = field(default_factory=list)
    previous_issues: list[Issue] = field(default_factory=list)
    previous_files_modified: list[Path] = field(default_factory=list)
    previous_hook_statuses: dict[str, str] = field(default_factory=dict)
    previous_fixes_applied: int = 0
    stage: str = "fast"
    max_iterations: int = 5
    hook_results: Sequence[object] = field(default_factory=tuple)
    initial_issues: list[Issue] = field(default_factory=list)
    no_progress_count: int = 0
    previous_issue_count: float = float("inf")
    coordinator_set: dict[str, object] = field(default_factory=dict)


IterationStepFn = Callable[[AutoFixContext], t.Awaitable[StepResult]]


class _FileChangeTracker:
    def __init__(self, pkg_path: Path) -> None:
        self._pkg_path = pkg_path
        self._baseline: dict[Path, float] | None = None

    def capture(self) -> None:
        mtimes: dict[Path, float] = {}
        for path in self._pkg_path.rglob("*.py"):
            with suppress(OSError):
                mtimes[path] = path.stat().st_mtime
        self._baseline = mtimes

    def delta(self) -> int:
        if self._baseline is None:
            return 0
        changed = 0
        for path, mtime_before in self._baseline.items():
            with suppress(OSError):
                if path.stat().st_mtime != mtime_before:
                    changed += 1
        return changed


class _MutableSettings(t.Protocol):
    fix_enabled: bool
    add_ignore_enabled: bool
    suppress_errors: bool
    baseline_file: t.Any


def _count_bandit_results(data: object) -> int | None:
    if isinstance(data, dict):
        results = data.get("results")
        return len(results) if isinstance(results, list) else None
    return None


def _count_semgrep_results(data: object) -> int | None:
    if isinstance(data, dict):
        results = data.get("results")
        return len(results) if isinstance(results, list) else None
    return None


def _count_pytest_results(data: object) -> int | None:
    if isinstance(data, dict):
        tests = data.get("tests")
        if isinstance(tests, list):
            failed = [
                t for t in tests if isinstance(t, dict) and t.get("outcome") == "failed"
            ]
            return len(failed)
    return None


def _extract_issue_count_from_text_lines(output: str) -> int | None:
    noise_prefixes = (
        "#",
        "─",
        "Found",
        "warning:",
        "note:",
        "panicked at",
        "thread 'main'",
        'thread "main"',
        "stack backtrace",
        "<sys>:",
        "ResourceWarning:",
        "DeprecationWarning:",
        "FutureWarning:",
        "SyntaxWarning:",
        "ImportWarning:",
        "UserWarning:",
        "PendingDeprecationWarning:",
        "RuntimeWarning:",
        "BytesWarning:",
    )
    lines = output.split("\n")
    issue_lines: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped or ":" not in stripped:
            continue
        if stripped.startswith(noise_prefixes):
            continue

        if "crates/" in stripped and not stripped.endswith((".py", ".pyi")):
            continue

        if stripped.startswith("#") and " 0x" in stripped:
            continue

        if stripped.startswith("RUST_BACKTRACE"):
            continue

        if stripped.lower().startswith("panic"):
            continue

        if stripped.startswith(">") and "panic" in output.lower():
            continue

        if "ResourceWarning" in stripped or "DeprecationWarning" in stripped:
            continue
        issue_lines.append(line)
    return len(issue_lines) if issue_lines else None


def _list_signatures(skill_store: object) -> list[str]:
    internal = getattr(skill_store, "_skills", None)
    if isinstance(internal, dict):
        return list(internal.keys())
    return []
