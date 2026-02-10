import ast
import asyncio
import json
import logging
import os
import subprocess
import typing as t
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import TYPE_CHECKING

from rich.console import Console

if TYPE_CHECKING:
    from crackerjack.agents.coordinator import AgentCoordinator
    from crackerjack.models.protocols import (
        AgentCoordinatorProtocol,
        LoggerProtocol,
    )

from crackerjack.adapters.factory import DefaultAdapterFactory
from crackerjack.agents.base import AgentContext, FixResult, Issue, IssueType, Priority
from crackerjack.models.qa_config import QACheckConfig
from crackerjack.models.qa_results import QAResult
from crackerjack.parsers.factory import ParserFactory, ParsingError
from crackerjack.services.ai_fix_progress import AIFixProgressManager
from crackerjack.services.cache import CrackerjackCache

logger = logging.getLogger(__name__)


class AutofixCoordinator:
    def __init__(
        self,
        console: Console | None = None,
        pkg_path: Path | None = None,
        logger: "LoggerProtocol | None" = None,
        max_iterations: int | None = None,
        coordinator_factory: Callable[
            [AgentContext, CrackerjackCache], "AgentCoordinatorProtocol"
        ]
        | None = None,
        enable_fancy_progress: bool = True,
        enable_agent_bars: bool = True,
    ) -> None:
        self.console = console or Console()
        self.pkg_path = pkg_path or Path.cwd()

        self.logger = logger or logging.getLogger("crackerjack.autofix")  # type: ignore[assignment]
        self._max_iterations = max_iterations
        self._coordinator_factory = coordinator_factory
        self._parser_factory = ParserFactory()

        self.progress_manager = AIFixProgressManager(
            console=self.console,
            enabled=enable_fancy_progress,
            enable_agent_bars=enable_agent_bars,
        )

    def apply_autofix_for_hooks(self, mode: str, hook_results: list[object]) -> bool:
        try:
            if self._should_skip_autofix(hook_results):
                return False

            if mode == "fast":
                return self._apply_fast_stage_fixes()
            if mode == "comprehensive":
                return self._apply_comprehensive_stage_fixes(hook_results)
            self.logger.warning(f"Unknown autofix mode: {mode}")
            return False
        except Exception:
            self.logger.exception("Error applying autofix")
            return False

    def apply_fast_stage_fixes(
        self, hook_results: Sequence[object] | None = None
    ) -> bool:
        return self._apply_fast_stage_fixes(hook_results)

    def apply_comprehensive_stage_fixes(self, hook_results: Sequence[object]) -> bool:
        return self._apply_comprehensive_stage_fixes(hook_results)

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

    def _apply_fast_stage_fixes(
        self, hook_results: Sequence[object] | None = None
    ) -> bool:
        ai_agent_enabled = os.environ.get("AI_AGENT") == "1"

        if ai_agent_enabled and hook_results is not None:
            self.logger.info(
                "AI agent mode enabled for fast stage, attempting AI-based fixing"
            )
            return self._apply_ai_agent_fixes(hook_results, stage="fast")

        return self._execute_fast_fixes()

    def _apply_comprehensive_stage_fixes(self, hook_results: Sequence[object]) -> bool:
        ai_agent_enabled = os.environ.get("AI_AGENT") == "1"

        if ai_agent_enabled:
            self.logger.info("AI agent mode enabled, attempting AI-based fixing")
            return self._apply_ai_agent_fixes(hook_results, stage="comprehensive")

        failed_hooks = self._extract_failed_hooks(hook_results)
        if not failed_hooks:
            return True

        hook_specific_fixes = self._get_hook_specific_fixes(failed_hooks)

        if not self._execute_fast_fixes():
            return False

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

        return fixes

    def _execute_fast_fixes(self) -> bool:
        fixes = [
            (["uv", "run", "ruff", "format", "."], "format code"),
            (["uv", "run", "ruff", "check", "--fix", "."], "fix code style"),
        ]

        all_successful = True
        for cmd, description in fixes:
            if not self._run_fix_command(cmd, description):
                all_successful = False

        return all_successful

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
            "ruff",
            "bandit",
            "trailing-whitespace",
        ]

        return bool(len(cmd) > 2 and cmd[2] in allowed_tools)

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
        for result in hook_results:
            raw_output = self._extract_raw_output(result)
            if self._has_import_errors(raw_output):
                self.logger.info("Skipping autofix for import errors")
                return True
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
        coverage_issues = []

        ratchet_path = self.pkg_path / ".coverage-ratchet.json"
        if not ratchet_path.exists():
            self.logger.debug("No coverage ratchet file found, skipping coverage check")
            return coverage_issues

        try:
            with open(ratchet_path) as f:
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
                        file_path=str(ratchet_path),
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
            self.logger.error(f"Failed to check coverage regression: {e}")

        return coverage_issues

    def _should_skip_console_print(self) -> bool:
        return self.progress_manager._live_display is not None

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

        if fixes_applied == 0 and current_count >= previous_count:
            if no_progress_count + 1 >= convergence_threshold:
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

        if fixes_applied > 0:
            self.logger.info(
                f"✓ Progress made: {fixes_applied} fix(es) applied, resetting convergence counter"
            )
            return 0

        if current_count >= previous_count:
            return no_progress_count + 1

        return 0

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

    def _run_ai_fix_iteration(
        self,
        coordinator: "AgentCoordinatorProtocol | AgentCoordinator",
        issues: list[Issue],
    ) -> tuple[bool, int]:
        self.logger.info(
            f"🤖 Starting AI agent fixing iteration with {len(issues)} issues"
        )

        self.logger.info("📋 Sending issues to agents:")
        for i, issue in enumerate(issues[:5]):
            issue_type = issue.type.value
            # Sanitize message for logging (remove spaces/special chars that break format strings)
            safe_msg = issue.message[:60].replace(" ", "_").replace("=", ":")
            self.logger.info(
                f"  [{i}] type={issue_type:15s} | "
                f"file={issue.file_path}:{issue.line_number} | "
                f"msg={safe_msg}"
            )
        if len(issues) > 5:
            self.logger.info(
                f"  ... and {len(issues) - 5} more issues (total: {len(issues)})"
            )

        self.logger.info("🔧 Invoking coordinator.handle_issues()...")
        fix_result = self._execute_ai_fix(coordinator, issues)

        if fix_result is None:
            self.logger.error("❌ AI agent fixing iteration failed - returned None")
            return False, 0

        fixes_applied = len(fix_result.fixes_applied)

        self.logger.info(
            f"✅ AI agent fixing iteration completed:\n"
            f"   - Success: {fix_result.success}\n"
            f"   - Confidence: {fix_result.confidence:.2f}\n"
            f"   - Fixes applied: {fixes_applied}\n"
            f"   - Files modified: {len(fix_result.files_modified)}\n"
            f"   - Remaining issues: {len(fix_result.remaining_issues)}"
        )

        if fix_result.fixes_applied:
            self.logger.info("🔨 Fixes applied:")
            for i, fix in enumerate(fix_result.fixes_applied[:5]):
                self.logger.info(f"  [{i}] {fix[:100]}")
            if len(fix_result.fixes_applied) > 5:
                self.logger.info(
                    f"  ... and {len(fix_result.fixes_applied) - 5} more fixes"
                )

        if fix_result.files_modified:
            self.logger.info(
                f"📝 Files modified: {', '.join(fix_result.files_modified)}"
            )

        if fix_result.files_modified:
            self.logger.info(
                "🔍 Validating modified files for syntax and semantic errors"
            )
            if not self._validate_modified_files(fix_result.files_modified):
                self.logger.error(
                    "❌ AI agents introduced invalid code - rejecting fixes and rolling back"
                )
                self._revert_ai_fix_changes(fix_result.files_modified)
                return False, 0
            self.logger.info("✅ All modified files validated successfully")

        success = self._process_fix_result(fix_result)
        return success, fixes_applied

    def _execute_ai_fix(
        self,
        coordinator: "AgentCoordinatorProtocol | AgentCoordinator",
        issues: list[Issue],
    ) -> FixResult | None:
        try:
            self.logger.info("🚀 Initiating AI agent coordination for issue resolution")

            self._validate_issue_file_paths(issues)

            try:
                asyncio.get_running_loop()
                self.logger.debug("Running AI agent fixing in existing event loop")
                result = self._run_in_threaded_loop(coordinator, issues)
            except RuntimeError:
                self.logger.debug("Creating new event loop for AI agent fixing")
                result = asyncio.run(coordinator.handle_issues(issues))

            self.logger.info("✅ AI agent coordination completed")
            return result
        except Exception:
            self.logger.exception("❌ AI agent handling failed")
            return None

    def _validate_issue_file_paths(self, issues: list[Issue]) -> None:
        self.logger.debug("🔍 Validating file paths for issues...")

        missing_files = []
        for issue in issues:
            if issue.file_path:
                file_path = Path(issue.file_path)
                if not file_path.exists():
                    missing_files.append(str(issue.file_path))
                    self.logger.warning(
                        f"⚠️ File not found: {issue.file_path} (issue: {issue.id})"
                    )

        if missing_files:
            self.logger.error(
                f"❌ {len(missing_files)} issues reference non-existent files: "
                f"{', '.join(missing_files[:3])}"
            )
            if len(missing_files) > 3:
                self.logger.error(f"  ... and {len(missing_files) - 3} more files")

    def _validate_modified_files(self, modified_files: list[str]) -> bool:

        for file_path_str in modified_files:
            if not self._should_validate_file(file_path_str):
                continue

            file_path = Path(file_path_str)
            if not file_path.exists():
                self.logger.warning(f"⚠️ File not found for validation: {file_path}")
                continue

            content = file_path.read_text()
            if not self._validate_file_syntax(file_path, content):
                return False

            if not self._validate_file_duplicates(file_path, content):
                return False

        return True

    def _should_validate_file(self, file_path_str: str) -> bool:
        if not file_path_str.endswith(".py"):
            self.logger.debug(f"⏭️ Skipping non-Python file: {file_path_str}")
            return False
        return True

    def _validate_file_syntax(self, file_path: Path, content: str) -> bool:
        try:
            compile(content, str(file_path), "exec")
            self.logger.debug(f"✅ Syntax validation passed: {file_path}")
            return True
        except SyntaxError as e:
            self.logger.error(f"❌ Syntax error in {file_path}:{e.lineno}: {e.msg}")
            self.logger.error(f"   {e.text}")
            return False

    def _validate_file_duplicates(self, file_path: Path, content: str) -> bool:
        import ast

        try:
            tree = ast.parse(content)
            definitions = self._find_definitions(tree)

            duplicates = self._find_duplicate_definitions(definitions, file_path)
            if duplicates:
                return False

            self.logger.debug(f"✅ No duplicate definitions: {file_path}")
            return True

        except Exception as e:
            self.logger.warning(f"⚠️ Could not check for duplicates in {file_path}: {e}")
            return True

    def _find_definitions(self, tree: ast.AST) -> dict[str, int]:
        import ast

        definitions = {}
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                name = node.name
                if name not in definitions:
                    definitions[name] = node.lineno

        return definitions

    def _find_duplicate_definitions(
        self, definitions: dict[str, int], file_path: Path
    ) -> bool:
        for name, lineno in definitions.items():
            count = sum(
                1 for node_lineno in definitions.values() if node_lineno == lineno
            )
            if count > 1:
                self.logger.error(
                    f"❌ Duplicate definition '{name}' in {file_path} at line {lineno}"
                )
                return True

        return False

    def _revert_ai_fix_changes(self, modified_files: list[str]) -> None:
        import subprocess

        self.logger.warning(f"🔄 Reverting AI changes to {len(modified_files)} files")

        for file_path_str in modified_files:
            try:
                result = subprocess.run(
                    ["git", "checkout", "--", file_path_str],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if result.returncode == 0:
                    self.logger.info(f"✅ Reverted changes: {file_path_str}")
                else:
                    self.logger.warning(
                        f"⚠️ Could not revert {file_path_str}: {result.stderr}"
                    )
            except Exception as e:
                self.logger.error(f"❌ Failed to revert {file_path_str}: {e}")

    def _run_in_threaded_loop(
        self,
        coordinator: "AgentCoordinatorProtocol | AgentCoordinator",
        issues: list[Issue],
    ) -> FixResult | None:
        import threading

        result_container: list[FixResult | None] = [None]
        exception_container: list[Exception | None] = [None]

        def run_in_new_loop() -> None:
            try:
                new_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(new_loop)
                try:
                    self.logger.info(
                        "Starting AI agent coordination in threaded event loop"
                    )
                    result_container[0] = new_loop.run_until_complete(
                        coordinator.handle_issues(issues)
                    )
                    self.logger.info("AI agent coordination in threaded loop completed")
                finally:
                    new_loop.close()
            except Exception as e:
                self.logger.exception("Error in threaded AI agent coordination")
                exception_container[0] = e

        thread = threading.Thread(target=run_in_new_loop)
        thread.start()
        thread.join(timeout=300)

        if exception_container[0] is not None:
            raise exception_container[0]

        if result_container[0] is None:
            raise RuntimeError("AI agent fixing timed out")

        return result_container[0]

    def _process_fix_result(self, fix_result: FixResult) -> bool:
        fixes_count = len(fix_result.fixes_applied)
        remaining_count = len(fix_result.remaining_issues)

        self.logger.info(
            f"Processing fix result: {fixes_count} fixes applied, {remaining_count} issues remaining"
        )

        if fixes_count > 0:
            for i, fix in enumerate(fix_result.fixes_applied[:3]):
                self.logger.info(f"  Applied fix {i + 1}: {fix[:100]}...")
            if len(fix_result.fixes_applied) > 3:
                self.logger.info(
                    f"  ... and {len(fix_result.fixes_applied) - 3} more fixes"
                )

            return self._handle_partial_progress(
                fix_result, fixes_count, remaining_count
            )

        if not fix_result.success and remaining_count > 0:
            if not self._should_skip_console_print():
                self.console.print(
                    "[yellow]⚠ Agents cannot fix remaining issues[/yellow]"
                )
            self.logger.warning("AI agents cannot fix remaining issues")

            for i, issue in enumerate(fix_result.remaining_issues[:3]):
                self.logger.info(f"  Remaining issue {i + 1}: {issue[:100]}...")
            if len(fix_result.remaining_issues) > 3:
                self.logger.info(
                    f"  ... and {len(fix_result.remaining_issues) - 3} more issues"
                )

            return False

        if remaining_count == 0:
            self.logger.info(
                f"All {fixes_count} issues fixed with confidence {fix_result.confidence:.2f}"
            )
            return True

        issue_word = "issue" if remaining_count == 1 else "issues"
        self.logger.warning(
            f"No fixes applied but {remaining_count} {issue_word} remain - agents unable to fix"
        )

        return False

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

        return False

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
        self, hook_name: str, adapter_factory: "DefaultAdapterFactory"
    ) -> QAResult | None:
        try:
            adapter = self._get_qa_adapter(hook_name, adapter_factory)
            if adapter is None:
                return None

            if self._is_in_async_context():
                self.logger.warning(
                    f"QA adapter for '{hook_name}' called from async context, "
                    "this may indicate architectural issue"
                )
                return None

            asyncio.run(adapter.init())
            config = self._create_qa_config(adapter, hook_name)
            qa_result: QAResult = asyncio.run(adapter.check(config=config))

            self._log_qa_adapter_result(hook_name, qa_result)
            return qa_result

        except Exception as e:
            self.logger.warning(
                f"Failed to run QA adapter for '{hook_name}': {e}. "
                f"Will fall back to raw output parsing."
            )
            return None

    def _get_qa_adapter(
        self, hook_name: str, adapter_factory: "DefaultAdapterFactory"
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

    def _create_qa_config(self, adapter: object, hook_name: str) -> "QACheckConfig":
        return QACheckConfig(
            check_id=adapter.module_id,
            check_name=hook_name,
            check_type=adapter._get_check_type(),
            enabled=True,
            file_patterns=["**/*.py"],
            timeout_seconds=60,
        )

    def _log_qa_adapter_result(self, hook_name: str, qa_result: "QAResult") -> None:
        if qa_result.parsed_issues:
            self.logger.info(
                f"✅ QA adapter for '{hook_name}' found "
                f"{len(qa_result.parsed_issues)} issues"
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
                r.name for r in hook_results if getattr(r, "name", "") not in qa_results
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

            if qa_result and qa_result.parsed_issues:
                cached_results[hook_name] = qa_result
                cache_hits += 1
                self.logger.info(
                    f"✅ Cache hit for '{hook_name}': {len(qa_result.parsed_issues)} issues "
                    f"(saved re-running QA adapter)"
                )

        if cache_hits > 0:
            self.logger.info(
                f"🎯 QAResult cache: {cache_hits}/{len(hook_results)} hooks "
                f"({cache_hits / len(hook_results) * 100:.0f}% hit rate)"
            )

        return cached_results

    def _parse_all_hook_results_with_qa(
        self, hook_results: Sequence[object], qa_results: dict[str, QAResult]
    ) -> tuple[list[Issue], dict[str, int]]:
        issues: list[Issue] = []
        parsed_counts_by_hook: dict[str, int] = {}

        for result in hook_results:
            hook_name = getattr(result, "name", "")
            if not hook_name:
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
            hook_name = result.name
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
        if new_count > 0:
            return True

        return hasattr(result, "status") and getattr(result, "status", "") == "failed"

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

    def _collect_current_issues(self, stage: str = "fast") -> list[Issue]:
        pkg_dir = self._detect_package_directory()
        check_commands = self._build_check_commands(pkg_dir, stage=stage)
        self.logger.debug(
            f"Built {len(check_commands)} check commands for stage '{stage}'"
        )
        for cmd, hook_name, timeout in check_commands:
            self.logger.debug(
                f"  Check command: {cmd[:3]}... (hook={hook_name}, timeout={timeout}s)"
            )

        all_issues, successful_checks = self._execute_check_commands(check_commands)

        if successful_checks == 0 and self.pkg_path.exists():
            self.logger.warning(
                "No issues collected from any checks - commands may have failed. "
                "This could indicate a problem with the issue collection process."
            )

        self.logger.debug(
            f"Collected {len(all_issues)} current issues (from {successful_checks} successful checks)"
        )
        return all_issues

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
                "complexity",
                60,
            ),
        ]

        if stage == "fast":
            return [cmd for cmd in all_commands if cmd[1] in ("ruff", "ruff-format")]

        return [
            cmd for cmd in all_commands if cmd[1] in ("zuban", "refurb", "complexity")
        ]

    def _execute_check_commands(
        self, check_commands: list[tuple[list[str], str, int]]
    ) -> tuple[list[Issue], int]:
        all_issues: list[Issue] = []
        successful_checks = 0

        for cmd, hook_name, timeout in check_commands:
            result = self._run_check_command(cmd, timeout, hook_name)
            if result:
                process, stdout, stderr = result
                issues = self._process_check_result(process, stdout, stderr, hook_name)
                all_issues.extend(issues)
                successful_checks += 1

        return all_issues, successful_checks

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
            self.logger.warning(f"Timeout running {hook_name} check")
            return None
        except Exception as e:
            self._kill_process_gracefully(process)
            self.logger.error(f"Error running {hook_name} check: {e}")
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
                self.logger.error(
                    f"Unexpected error converting parsed issue from '{tool_name}': {e}. "
                    f"Issue data: {tool_issue_dict}",
                    exc_info=True,
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
            "refurb": IssueType.COMPLEXITY,
            "skylos": IssueType.DEAD_CODE,
            "creosote": IssueType.DEPENDENCY,
            "pyscn": IssueType.DEPENDENCY,
        }

        if tool_name in tool_type_map:
            return tool_type_map[tool_name]

        message = (
            tool_issue_dict.get("message", "").lower()
            if tool_issue_dict.get("message")
            else ""
        )
        code = (
            tool_issue_dict.get("code", "").lower()
            if tool_issue_dict.get("code")
            else ""
        )

        if any(word in message for word in ["test", "pytest", "unittest"]):
            return IssueType.TEST_FAILURE
        if any(word in message for word in ["complex", "cyclomatic"]):
            return IssueType.COMPLEXITY
        if any(word in message for word in ["dead", "unused", "redundant"]):
            return IssueType.DEAD_CODE
        if any(word in message for word in ["security", "vulnerability"]):
            return IssueType.SECURITY
        if any(word in message for word in ["import", "module"]):
            return IssueType.IMPORT_ERROR
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
            self.logger.error(f"Parsing failed for '{hook_name}': {e}")
            self.logger.warning(
                f"🔧 Continuing workflow despite parsing failure for '{hook_name}' "
                f"(soft fail - stage will still be marked as failed)"
            )
            return []

    def _extract_issue_count(self, output: str, tool_name: str) -> int | None:
        if tool_name in (
            "complexipy",
            "refurb",
            "creosote",
            "pyscn",
            "semgrep",
            "pytest",
            "check-yaml",
            "check-toml",
            "check-json",
            "pip-audit",
            "check-ast",
            "check-local-links",
            "check-added-large-files",
            "format-json",
            "ruff",
            "ruff-check",
            "ruff-format",
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
                f"  [{i}] type={issue.type.value}, "
                f"severity={issue.severity.value}, "
                f"file={issue.file_path}:{issue.line_number}, "
                f"msg={issue.message[:80]!r}"
            )

        if len(issues) > 5:
            self.logger.info(f"  ... and {len(issues) - 5} more issues")

    def _validate_parsed_issues(self, issues: list[Issue]) -> None:
        for i, issue in enumerate(issues):
            if not issue.file_path:
                self.logger.warning(
                    f"Issue {i} ({issue.id}) missing file_path: {issue.message[:50]}"
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

    def _setup_ai_fix_coordinator(self) -> "AgentCoordinatorProtocol":
        context = AgentContext(
            project_path=self.pkg_path,
            subprocess_timeout=300,
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
    ) -> list[Issue]:
        if iteration == 0:
            issues = self._get_iteration_issues(iteration, hook_results, stage)
            self.logger.info(
                f"Iteration {iteration}: Using initial hook results ({len(issues)} issues)"
            )
        else:
            issues = self._collect_current_issues(stage=stage)
            self.logger.info(
                f"Iteration {iteration}: Re-ran hooks, collected {len(issues)} current issues"
            )

        return issues

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

    def _run_ai_fix_iteration_loop(
        self,
        coordinator: "AgentCoordinatorProtocol",
        initial_issues: list[Issue],
        hook_results: Sequence[object],
        stage: str,
    ) -> bool:
        max_iterations = self._get_max_iterations()
        previous_issue_count = float("inf")
        no_progress_count = 0
        iteration = 0

        try:
            while True:
                issues = self._get_iteration_issues_with_log(
                    iteration, hook_results, stage
                )
                current_issue_count = len(issues)

                self.progress_manager.start_iteration(iteration, current_issue_count)

                completion_result = self._check_iteration_completion(
                    iteration,
                    current_issue_count,
                    previous_issue_count,
                    no_progress_count,
                    max_iterations,
                    stage,
                    fixes_applied=0,
                )

                if completion_result is not None:
                    self.progress_manager.end_iteration()
                    self.progress_manager.finish_session(success=completion_result)
                    return completion_result

                success, fixes_applied = self._run_ai_fix_iteration(coordinator, issues)

                no_progress_count = self._update_iteration_progress_with_tracking(
                    iteration,
                    current_issue_count,
                    previous_issue_count,
                    no_progress_count,
                    fixes_applied,
                )

                if not success:
                    self.progress_manager.end_iteration()
                    self.progress_manager.finish_session(success=False)
                    return False

                self.progress_manager.end_iteration()

                previous_issue_count = current_issue_count
                iteration += 1

        except Exception as e:
            self.logger.exception(f"Error during AI fixing at iteration {iteration}")
            self.progress_manager.end_iteration()
            self.progress_manager.finish_session(
                success=False, message=f"Error during AI fixing: {e}"
            )
            raise

    def _validate_final_issues(self, issues: list[Issue]) -> None:
        for i, issue in enumerate(issues):
            errors = self._collect_validation_errors(issue)

            if errors:
                self._log_validation_error(i, issue, errors)
                raise ValueError(f"Invalid issue object: {errors}")

    def _collect_validation_errors(self, issue: Issue) -> list[str]:
        errors = []

        type_errors = self._validate_issue_type(issue)
        errors.extend(type_errors)

        severity_errors = self._validate_issue_severity(issue)
        errors.extend(severity_errors)

        message_errors = self._validate_issue_message(issue)
        errors.extend(message_errors)

        file_path_errors = self._validate_issue_file_path(issue)
        errors.extend(file_path_errors)

        return errors

    def _validate_issue_type(self, issue: Issue) -> list[str]:
        if not hasattr(issue, "type") or issue.type is None:
            return ["missing type"]
        if not isinstance(issue.type, IssueType):
            return [f"invalid type: {type(issue.type)}"]
        return []

    def _validate_issue_severity(self, issue: Issue) -> list[str]:
        if not hasattr(issue, "severity") or issue.severity is None:
            return ["missing severity"]
        if not isinstance(issue.severity, Priority):
            return [f"invalid severity: {type(issue.severity)}"]
        return []

    def _validate_issue_message(self, issue: Issue) -> list[str]:
        if not hasattr(issue, "message") or not issue.message:
            return ["missing or empty message"]
        return []

    def _validate_issue_file_path(self, issue: Issue) -> list[str]:
        if issue.file_path:
            return []

        if self._is_aggregate_issue(issue):
            return []

        return ["missing file_path"]

    def _is_aggregate_issue(self, issue: Issue) -> bool:
        msg_lower = issue.message.lower()
        aggregate_keywords = [
            "files",
            "file(",
            "would be reformatted",
            "require formatting",
            "formatting error",
        ]

        return "file" in msg_lower and any(
            keyword in msg_lower for keyword in aggregate_keywords
        )

    def _log_validation_error(
        self, index: int, issue: Issue, errors: list[str]
    ) -> None:
        self.logger.error(
            f"❌ Issue {index} ({issue.id}) has validation errors: {', '.join(errors)}"
        )
        self.logger.error(
            f"   Issue object: type={getattr(issue, 'type', None)}, "
            f"severity={getattr(issue, 'severity', None)}, "
            f"message={getattr(issue, 'message', None)}, "
            f"file_path={getattr(issue, 'file_path', None)}"
        )

    def _apply_ai_agent_fixes(
        self, hook_results: Sequence[object], stage: str = "fast"
    ) -> bool:

        coordinator = self._setup_ai_fix_coordinator()
        issues = self._collect_fixable_issues(hook_results)

        self.progress_manager.start_fix_session(
            stage=stage,
            initial_issue_count=len(issues),
        )

        result = self._run_ai_fix_iteration_loop(
            coordinator, issues, hook_results, stage
        )

        if result:
            self._validate_final_issues(issues)

        return result


def _extract_issue_count_from_json(output: str, tool_name: str) -> int | None:
    try:
        data = json.loads(output)
        return _count_issues_for_tool(data, tool_name)
    except (json.JSONDecodeError, TypeError):
        return None


def _count_issues_for_tool(data: object, tool_name: str) -> int | None:
    if tool_name in ("ruff", "ruff-check", "mypy", "zuban"):
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


def _count_bandit_results(data: object) -> int | None:
    if isinstance(data, dict) and "results" in data:
        results = data["results"]
        return len(results) if isinstance(results, list) else None
    return None


def _count_semgrep_results(data: object) -> int | None:
    if isinstance(data, dict) and "results" in data:
        results = data["results"]
        return len(results) if isinstance(results, list) else None
    return None


def _count_pytest_results(data: object) -> int | None:
    if isinstance(data, dict) and "tests" in data:
        tests = data["tests"]
        if isinstance(tests, list):
            failed = [
                t for t in tests if isinstance(t, dict) and t.get("outcome") == "failed"
            ]
            return len(failed)
    return None


def _extract_issue_count_from_text_lines(output: str) -> int | None:
    lines = output.split("\n")
    issue_lines = [
        line
        for line in lines
        if line.strip()
        and ":" in line
        and not line.strip().startswith(("#", "─", "Found"))
    ]
    return len(issue_lines) if issue_lines else None
