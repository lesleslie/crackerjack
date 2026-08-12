from __future__ import annotations

import ast
import asyncio
import json
import logging
import os
import re
import shutil
import subprocess
import typing as t
from collections.abc import Callable, Sequence
from contextlib import suppress
from dataclasses import dataclass, field
from pathlib import Path

from rich.console import Console

# NOTE: Many imports below were deleted by Tasks 25-27 (crackerjack.agents,
# crackerjack.ai_fix, crackerjack.memory, crackerjack.skills, etc.). The
# dead-code cleanup that will remove the methods using them is pending
# Task 24b Step 1. Until then this file will fail to import.
from crackerjack.core.ai_fix_event_bus import AIFixEventBus
from crackerjack.core.ai_fix_events import (
    RunStarted,
)
from crackerjack.core.ai_fix_sinks import build_default_bus
from crackerjack.core.preflight import PreflightConfig, PreflightFixer
from crackerjack.models.fix_plan import FixPlan
from crackerjack.models.issues import Issue, IssueType
from crackerjack.parsers.factory import (
    ParserFactory,
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

_VALIDATION_DETAIL_LINES: int = 30

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

        self.logger = logger or logging.getLogger("crackerjack.autofix")  # type: ignore[assignment]
        self._max_iterations = max_iterations
        self._coordinator_factory = coordinator_factory
        self._global_attempt_count = 0
        self._parser_factory = ParserFactory()

        self.progress_manager = AIFixProgressManager(
            console=self.console,
            enabled=enable_fancy_progress,
        )

        self._collected_errors: list[dict[str, str]] = []
        self._success_count = 0
        self._total_count = 0
        self._failed_issue_keys: set[str] = set()
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
            files_str = ", ".join(sorted(str(f) for f in files)[:3])  # noqa: FURB123 (Path objects must be coerced)
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
        from datetime import UTC, datetime

        log_dirs = [
            self.pkg_path / ".crackerjack" / "logs",
            Path(tempfile.gettempdir()) / "crackerjack" / "logs",
        ]
        timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
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
        return await self._execute_fast_fixes()

    async def _apply_comprehensive_stage_fixes(
        self, hook_results: Sequence[object]
    ) -> bool:
        self._failed_issue_keys = set()
        if not await self._execute_fast_fixes():
            return False

        # Deterministic prepass block (Task 24a Step 4 finding): the prepasses
        # inside the now-removed AI dispatch were non-AI tool orchestration and
        # must run unconditionally. Promoted from the AI path.
        issues = self._collect_fixable_issues(hook_results)
        issues = self._filter_fixable_issues(issues)

        if issues:
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

            issues = await self._apply_pycharm_hook_diagnostics_context(
                issues, "comprehensive"
            )

            pycharm_reformat_success = await self._apply_pycharm_reformat_prepass(
                issues
            )
            if pycharm_reformat_success:
                self.logger.info("✅ Applied PyCharm reformat prepass where available")

            force_prepass = self._preflight_config.force_prepass
            if tracker.delta() == 0 and not force_prepass:
                self.logger.debug("Skip refurb prepass: no file changes since last run")
            else:
                refreshed_refurb_issues = await self._apply_refurb_fix_prepasses(
                    hook_results
                )
                if refreshed_refurb_issues:
                    issues = self._replace_refreshed_type_issues(
                        issues,
                        refreshed_refurb_issues,
                    )
                    self.logger.info("✅ Applied Refurb fix prepass where available")

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
        insert_index = max(insert_index, 0)
        insert_index = min(insert_index, len(lines))

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
        candidate_results = failed_results or list(hook_results)
        if not candidate_results:
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
                reformatted = await adapter.reformat_file(file_path)  # type: ignore  # noqa: FURB123 (Path objects must be coerced for adapter API)
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
            if self._run_targeted_python_fixes(file_path):  # type: ignore
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

        adapter.settings = settings

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

        _infra_files: frozenset[str] = frozenset(
            {
                "autofix_coordinator.py",
                "fixer_coordinator.py",
                "ty_narrow.py",
                "ty_imports.py",
            }
        )
        infra_issues = [
            i
            for i in fixable_issues
            if i.file_path and any(f in i.file_path for f in _infra_files)
        ]
        if infra_issues:
            fixable_issues = [i for i in fixable_issues if i not in infra_issues]
            self.logger.info(
                f"🛡️ Excluding {len(infra_issues)} infrastructure issues from AI-fix "
                f"(pipeline files must not be self-modified): "
                f"{', '.join(sorted(p.file_path for i in infra_issues if (p := i.file_path) is not None))}"
            )

        if skipped_issues:
            self.logger.warning(
                f"⚠️ Skipping {len(skipped_issues)} issues without file_path: "
                f"{', '.join(i.message[:50] + '...' for i in skipped_issues[:3])}"
            )

        if not fixable_issues:
            self.logger.info("✅ No fixable issues (all require manual intervention)")

        return fixable_issues

    _swarm_manager: t.Any = None  # type: ignore[misc]


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
        return list(internal.keys())  # type: ignore
    return []


class _UnavailableLLMCodegen:
    async def generate_fixer(
        self,
        *,
        signature: str,
        original_error: str,
        skill_diff: str,
    ) -> str:
        raise RuntimeError("LLM codegen not wired for promotion")


class _UnavailableSandboxRunner:
    def run_tests(
        self,
        *,
        fixer_source: str,
        signature: str,
        project_root: Path,
    ) -> SandboxResult:
        raise RuntimeError("Sandbox runner not wired for promotion")


class _UnavailablePRCreator:
    def create_pr(
        self,
        *,
        fixer_source: str,
        signature: str,
        skill_diff: str,
    ) -> str:
        raise RuntimeError("PR creator not wired for promotion")


def _format_plan_loc(plan: FixPlan) -> str:
    return (
        f"{plan.file_path}:{plan.changes[0].line_range[0]}"
        if plan.changes
        else plan.file_path
    )


@dataclass
class _RetryContext:
    plan: FixPlan
    accumulated_feedback: list[str]
    previous_plan_signature: str | None = None
