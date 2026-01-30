import asyncio
import logging
import os
import subprocess
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

from crackerjack.agents.base import AgentContext, FixResult, Issue, IssueType, Priority
from crackerjack.services.cache import CrackerjackCache
from crackerjack.utils.issue_detection import should_count_as_issue

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
    ) -> None:
        self.console = console or Console()
        self.pkg_path = pkg_path or Path.cwd()

        self.logger = logger or logging.getLogger("crackerjack.autofix")  # type: ignore[assignment]
        self._max_iterations = max_iterations
        self._coordinator_factory = coordinator_factory

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

    def _apply_ai_agent_fixes(
        self, hook_results: Sequence[object], stage: str = "fast"
    ) -> bool:
        max_iterations = self._get_max_iterations()

        context = AgentContext(
            project_path=self.pkg_path,
            subprocess_timeout=300,
        )
        cache = CrackerjackCache()

        if self._coordinator_factory is not None:
            coordinator = self._coordinator_factory(context, cache)
        else:
            from crackerjack.agents.coordinator import AgentCoordinator

            coordinator = AgentCoordinator(context=context, cache=cache)

        previous_issue_count = float("inf")
        no_progress_count = 0

        for iteration in range(max_iterations):
            issues = self._get_iteration_issues(iteration, hook_results, stage)
            current_issue_count = len(issues)

            if current_issue_count == 0:
                result = self._handle_zero_issues_case(iteration, stage)
                if result is not None:
                    return result

            if self._should_stop_on_convergence(
                current_issue_count,
                previous_issue_count,
                no_progress_count,
            ):
                return False

            no_progress_count = self._update_progress_count(
                current_issue_count,
                previous_issue_count,
                no_progress_count,
            )

            self._report_iteration_progress(
                iteration, max_iterations, current_issue_count
            )

            if not self._run_ai_fix_iteration(coordinator, issues):
                return False

            previous_issue_count = current_issue_count

        return self._report_max_iterations_reached(max_iterations, stage)

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

    def _report_iteration_success(self, iteration: int) -> None:
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
    ) -> bool:
        convergence_threshold = self._get_convergence_threshold()

        if current_count >= previous_count:
            if no_progress_count + 1 >= convergence_threshold:
                issue_word = "issue" if current_count == 1 else "issues"
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
    ) -> int:
        if current_count >= previous_count:
            return no_progress_count + 1
        return 0

    def _report_iteration_progress(
        self,
        iteration: int,
        max_iterations: int,
        issue_count: int,
    ) -> None:
        issue_word = "issue" if issue_count == 1 else "issues"
        self.console.print(
            f"[cyan]→ Iteration {iteration + 1}/{max_iterations}: "
            f"{issue_count} {issue_word} to fix[/cyan]"
        )
        self.console.print()
        self.logger.info(
            f"Iteration {iteration + 1}/{max_iterations}: {issue_count} {issue_word} to fix"
        )

    def _run_ai_fix_iteration(
        self,
        coordinator: "AgentCoordinatorProtocol | AgentCoordinator",
        issues: list[Issue],
    ) -> bool:
        self.logger.info(
            f"Starting AI agent fixing iteration with {len(issues)} issues"
        )

        for i, issue in enumerate(issues[:3]):
            self.logger.info(
                f"  Issue {i + 1}: {issue.type.value} in {issue.file_path}:{issue.line_number} - {issue.message[:100]}..."
            )
        if len(issues) > 3:
            self.logger.info(f"  ... and {len(issues) - 3} more issues")

        fix_result = self._execute_ai_fix(coordinator, issues)
        if fix_result is None:
            self.logger.warning("AI agent fixing iteration failed")
            return False

        self.logger.info(
            f"AI agent fixing iteration completed with {len(fix_result.remaining_issues)} remaining issues"
        )
        return self._process_fix_result(fix_result)

    def _execute_ai_fix(
        self,
        coordinator: "AgentCoordinatorProtocol | AgentCoordinator",
        issues: list[Issue],
    ) -> FixResult | None:
        try:
            self.logger.info("Initiating AI agent coordination for issue resolution")

            try:
                asyncio.get_running_loop()
                self.logger.debug("Running AI agent fixing in existing event loop")
                result = self._run_in_threaded_loop(coordinator, issues)
            except RuntimeError:
                self.logger.debug("Creating new event loop for AI agent fixing")
                result = asyncio.run(coordinator.handle_issues(issues))

            self.logger.info("AI agent coordination completed")
            return result
        except Exception:
            self.logger.exception("AI agent handling failed")
            return None

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
            self.console.print("[yellow]⚠ Agents cannot fix remaining issues[/yellow]")
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
        issues: list[Issue] = []
        self.logger.debug(f"Parsing {len(hook_results)} hook results for issues")

        for result in hook_results:
            hook_issues = self._parse_single_hook_result(result)
            issues.extend(hook_issues)

        seen: set[tuple[str | None, int | None, str]] = set()
        unique_issues: list[Issue] = []
        for issue in issues:
            key = (
                issue.file_path,
                issue.line_number,
                issue.message[:100],
            )
            if key not in seen:
                seen.add(key)
                unique_issues.append(issue)

        if len(issues) != len(unique_issues):
            self.logger.info(
                f"Deduplicated issues: {len(issues)} raw -> {len(unique_issues)} unique"
            )
        else:
            self.logger.info(
                f"Total issues extracted from all hooks: {len(unique_issues)}"
            )

        return unique_issues

    def _parse_single_hook_result(self, result: object) -> list[Issue]:
        if not self._validate_hook_result(result):
            return []

        status = getattr(result, "status", "")
        if status.lower() != "failed":
            self.logger.debug(f"Skipping hook with status '{status}' (not failed)")
            return []

        hook_name = getattr(result, "name", "")
        if not hook_name:
            self.logger.warning("Hook result has no name attribute")
            return []

        self.logger.debug(
            f"Parsing failed hook result: name='{hook_name}', status='{status}'"
        )

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
        return int(os.environ.get("CRACKERJACK_AI_FIX_CONVERGENCE_THRESHOLD", "3"))

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

    def _parse_hook_to_issues(self, hook_name: str, raw_output: str) -> list[Issue]:
        issues: list[Issue] = []

        self.logger.debug(
            f"Parsing hook '{hook_name}': raw_output_lines={len(raw_output.split(chr(10)))}"
        )

        hook_type_map: dict[str, IssueType] = {
            "zuban": IssueType.TYPE_ERROR,
            "refurb": IssueType.COMPLEXITY,
            "complexipy": IssueType.COMPLEXITY,
            "pyright": IssueType.TYPE_ERROR,
            "mypy": IssueType.TYPE_ERROR,
            "ruff": IssueType.FORMATTING,
            "ruff-check": IssueType.FORMATTING,
            "ruff-format": IssueType.FORMATTING,
            "codespell": IssueType.FORMATTING,
            "bandit": IssueType.SECURITY,
            "vulture": IssueType.DEAD_CODE,
            "skylos": IssueType.DEAD_CODE,
            "creosote": IssueType.DEPENDENCY,
            "check-local-links": IssueType.DOCUMENTATION,
            "check-yaml": IssueType.FORMATTING,
            "check-toml": IssueType.FORMATTING,
            "check-json": IssueType.FORMATTING,
        }

        issue_type = hook_type_map.get(hook_name)
        if not issue_type:
            self.logger.debug(f"Unknown hook type: {hook_name}")
            return issues

        if hook_name in ("zuban", "pyright", "mypy"):
            self.logger.debug(f"Using type checker parser for '{hook_name}'")
            issues.extend(
                self._parse_type_checker_output(hook_name, raw_output, issue_type)
            )
        elif hook_name in ("ruff", "ruff-check"):
            self.logger.debug(f"Using ruff parser for '{hook_name}'")
            issues.extend(self._parse_ruff_output(raw_output))
        elif hook_name == "ruff-format":
            self.logger.debug(f"Using ruff-format parser for '{hook_name}'")
            issues.extend(self._parse_ruff_format_output(raw_output, issue_type))
        elif hook_name == "codespell":
            self.logger.debug(f"Using codespell parser for '{hook_name}'")
            issues.extend(self._parse_codespell_output(raw_output, issue_type))
        elif hook_name == "refurb":
            self.logger.debug(f"Using refurb parser for '{hook_name}'")
            issues.extend(self._parse_refurb_output(raw_output, issue_type))
        elif hook_name == "complexipy":
            self.logger.debug(f"Using complexipy parser for '{hook_name}'")
            issues.extend(self._parse_complexity_output(raw_output, issue_type))
        elif hook_name == "bandit":
            self.logger.debug(f"Using bandit parser for '{hook_name}'")
            issues.extend(self._parse_security_output(raw_output, issue_type))
        elif hook_name in ("vulture", "skylos"):
            self.logger.debug(f"Using dead code parser for '{hook_name}'")
            issues.extend(self._parse_dead_code_output(raw_output, issue_type))
        elif hook_name == "check-local-links":
            self.logger.debug(f"Using local links parser for '{hook_name}'")
            issues.extend(self._parse_check_local_links_output(raw_output, issue_type))
        elif hook_name in ("check-yaml", "check-toml", "check-json"):
            self.logger.debug(f"Using structured data parser for '{hook_name}'")
            issues.extend(self._parse_structured_data_output(raw_output, issue_type))
        else:
            self.logger.debug(f"Using generic parser for '{hook_name}'")
            issues.extend(self._parse_generic_output(hook_name, raw_output, issue_type))

        self.logger.debug(f"Hook '{hook_name}' produced {len(issues)} issues total")
        return issues

    def _parse_type_checker_output(
        self,
        tool_name: str,
        raw_output: str,
        issue_type: IssueType,
    ) -> list[Issue]:
        issues: list[Issue] = []

        lines = raw_output.split("\n")
        self.logger.debug(f"{tool_name}: Processing {len(lines)} output lines")

        lines_filtered = 0
        lines_parsed = 0
        lines_failed = 0

        for line in lines:
            line = line.strip()
            if not self._should_parse_line(line):
                lines_filtered += 1
                continue

            issue = self._parse_type_checker_line(line, tool_name, issue_type)
            if issue:
                issues.append(issue)
                lines_parsed += 1
            else:
                lines_failed += 1

        self.logger.debug(
            f"{tool_name}: Parsed {lines_parsed} issues, "
            f"filtered {lines_filtered} lines, "
            f"failed to parse {lines_failed} lines"
        )

        return issues

    def _should_parse_line(self, line: str) -> bool:
        return should_count_as_issue(line)

    def _parse_type_checker_line(
        self,
        line: str,
        tool_name: str,
        issue_type: IssueType,
    ) -> Issue | None:
        if ":" not in line:
            return None

        parts = line.split(":", 3)
        if len(parts) < 3:
            return None

        file_path = parts[0].strip()
        line_number = self._parse_line_number(parts[1])
        message = self._extract_message(parts, line)

        return Issue(
            type=issue_type,
            severity=Priority.HIGH,
            message=message,
            file_path=file_path,
            line_number=line_number,
            stage=tool_name,
        )

    def _parse_line_number(self, part: str) -> int | None:
        try:
            return int(part.strip())
        except (ValueError, IndexError):
            return None

    def _extract_message(self, parts: list[str], fallback: str) -> str:
        if len(parts) == 4:
            return parts[3].strip()
        if len(parts) > 2:
            return parts[2].strip()
        return fallback

    def _parse_refurb_output(
        self, raw_output: str, issue_type: IssueType
    ) -> list[Issue]:
        issues: list[Issue] = []

        for line in raw_output.split("\n"):
            line = line.strip()
            if not line or line.startswith(("Found", "Checked")):
                continue

            if "FURB" in line and ":" in line:
                parts = line.split(":", 2)
                if len(parts) >= 2:
                    file_path = parts[0].strip()
                    try:
                        line_number = int(parts[1].strip())
                    except (ValueError, IndexError):
                        line_number = None

                    message = parts[2].strip() if len(parts) > 2 else line

                    issues.append(
                        Issue(
                            type=issue_type,
                            severity=Priority.MEDIUM,
                            message=message,
                            file_path=file_path,
                            line_number=line_number,
                            stage="refurb",
                        )
                    )

        return issues

    def _parse_ruff_output(self, raw_output: str) -> list[Issue]:
        import re

        issues: list[Issue] = []

        pattern = re.compile(r"^(.+?):(\d+):(\d+):?\s*([A-Z]\d+)\s+(.+)$")

        for line in raw_output.split("\n"):
            line = line.strip()
            if not line or line.startswith(("Found", "Checked", "-")):
                continue

            match = pattern.match(line)
            if not match:
                continue

            file_path, line_num, col_num, code, message = match.groups()

            issue_type = self._get_ruff_issue_type(code)
            severity = self._get_ruff_severity(code)

            issues.append(
                Issue(
                    type=issue_type,
                    severity=severity,
                    message=f"{code} {message}",
                    file_path=file_path,
                    line_number=int(line_num),
                    stage="ruff-check",
                    details=[f"column: {col_num}", f"code: {code}"],
                )
            )

        return issues

    def _get_ruff_issue_type(self, code: str) -> IssueType:
        if code.startswith("C9"):
            return IssueType.COMPLEXITY

        if code.startswith("S"):
            return IssueType.SECURITY

        if code.startswith("F4"):
            return IssueType.IMPORT_ERROR

        if code.startswith("F"):
            return IssueType.FORMATTING

        return IssueType.FORMATTING

    def _get_ruff_severity(self, code: str) -> Priority:
        if code.startswith(("C9", "S")):
            return Priority.HIGH

        if code.startswith("F4"):
            return Priority.MEDIUM

        return Priority.LOW

    def _parse_complexity_output(
        self, raw_output: str, issue_type: IssueType
    ) -> list[Issue]:
        """Parse complexipy output to extract complexity issues."""
        issues: list[Issue] = []
        lines = raw_output.split("\n")

        in_failed_section = False
        current_file = ""

        for line in lines:
            line_stripped = line.strip()

            if self._is_failed_section_start(line_stripped):
                in_failed_section = True
                continue

            if self._is_failed_section_end(line_stripped, in_failed_section):
                break

            if self._is_file_marker(line_stripped, in_failed_section):
                current_file = self._extract_file_from_marker(line_stripped)
                continue

            if self._is_function_line(
                line_stripped, in_failed_section, bool(current_file)
            ):
                issue = self._create_complexity_issue(
                    line_stripped, current_file, issue_type
                )
                issues.append(issue)

        return issues

    def _is_failed_section_start(self, line: str) -> bool:
        """Check if line marks the start of the failed functions section."""
        return line.startswith("Failed functions:")

    def _is_failed_section_end(self, line: str, in_section: bool) -> bool:
        """Check if line marks the end of the failed functions section."""
        return in_section and (not line or line.startswith("─"))

    def _is_file_marker(self, line: str, in_section: bool) -> bool:
        """Check if line is a file path marker."""
        return in_section and line.startswith("- ") and line.endswith(":")

    def _extract_file_from_marker(self, line: str) -> str:
        """Extract file path from a file marker line."""
        remaining = line[2:].strip()  # Remove "- " prefix
        return remaining[:-1].strip()  # Remove trailing ":"

    def _is_function_line(self, line: str, in_section: bool, has_file: bool) -> bool:
        """Check if line is a function with complexity issue."""
        return in_section and has_file and not line.startswith("- ") and "::" in line

    def _create_complexity_issue(
        self, line: str, file_path: str, issue_type: IssueType
    ) -> Issue:
        """Create an Issue object for a complexity violation."""
        message = f"Complexity exceeded for {line}"
        return Issue(
            type=issue_type,
            severity=Priority.MEDIUM,
            message=message,
            file_path=file_path,
            line_number=None,
            stage="complexity",
        )

    def _parse_security_output(
        self, raw_output: str, issue_type: IssueType
    ) -> list[Issue]:
        issues: list[Issue] = []

        for line in raw_output.split("\n"):
            line = line.strip()
            if not line or line.startswith((">>", "Run")):
                continue

            if "Issue:" in line:
                parts = line.split("Issue:", 1)
                if len(parts) == 2:
                    message = parts[1].strip()

                    issues.append(
                        Issue(
                            type=issue_type,
                            severity=Priority.CRITICAL,
                            message=message,
                            file_path=None,
                            line_number=None,
                            stage="security",
                        )
                    )

        return issues

    def _parse_dead_code_output(
        self, raw_output: str, issue_type: IssueType
    ) -> list[Issue]:
        issues: list[Issue] = []

        for line in raw_output.split("\n"):
            line = line.strip()
            if not line:
                continue

            if ":" in line:
                parts = line.split(":", 1)
                file_path = parts[0].strip()
                message = parts[1].strip() if len(parts) > 1 else "Dead code detected"

                issues.append(
                    Issue(
                        type=issue_type,
                        severity=Priority.LOW,
                        message=message,
                        file_path=file_path,
                        line_number=None,
                        stage="dead_code",
                    )
                )

        return issues

    def _parse_check_local_links_output(
        self, raw_output: str, issue_type: IssueType
    ) -> list[Issue]:
        issues: list[Issue] = []

        for line in raw_output.split("\n"):
            line = line.strip()
            if not self._should_parse_local_link_line(line):
                continue

            issue = self._parse_single_local_link_line(line, issue_type)
            if issue:
                issues.append(issue)

        return issues

    def _should_parse_local_link_line(self, line: str) -> bool:
        return bool(line and "File not found:" in line)

    def _parse_single_local_link_line(
        self, line: str, issue_type: IssueType
    ) -> Issue | None:
        try:
            file_path, line_number, target_file = self._extract_local_link_parts(line)
            if not file_path:
                return None

            message = self._create_link_error_message(target_file)
            details = self._create_link_error_details(target_file)

            return Issue(
                type=issue_type,
                severity=Priority.MEDIUM,
                message=message,
                file_path=file_path,
                line_number=line_number,
                stage="documentation",
                details=details,
            )
        except Exception as e:
            self.logger.debug(f"Failed to parse check-local-links line: {line} ({e})")
            return None

    def _extract_local_link_parts(
        self, line: str
    ) -> tuple[str, int | None, str | None]:
        if ":" not in line:
            return "", None, None

        file_path, rest = line.split(":", 1)

        if ":" not in rest:
            return file_path.strip(), None, None

        line_number_str, message_part = rest.split(":", 1)
        line_number = self._parse_line_number(line_number_str)

        target_file = self._extract_target_file_from_message(message_part)

        return file_path.strip(), line_number, target_file

    def _extract_target_file_from_message(self, message_part: str) -> str | None:
        if " - " in message_part:
            return message_part.split(" - ")[0].strip()
        return None

    def _create_link_error_message(self, target_file: str | None) -> str:
        if target_file:
            return f"Broken documentation link: '{target_file}' (file not found)"
        return "Broken documentation link (target file not found)"

    def _create_link_error_details(self, target_file: str | None) -> list[str]:
        return [f"Target file: {target_file}"] if target_file else []

    def _parse_structured_data_output(
        self, raw_output: str, issue_type: IssueType
    ) -> list[Issue]:
        issues: list[Issue] = []

        for line in raw_output.split("\n"):
            line = line.strip()
            if not self._should_parse_structured_data_line(line):
                continue

            issue = self._parse_single_structured_data_line(line, issue_type)
            if issue:
                issues.append(issue)

        return issues

    def _should_parse_structured_data_line(self, line: str) -> bool:
        return bool(line and line.startswith("✗"))

    def _parse_single_structured_data_line(
        self, line: str, issue_type: IssueType
    ) -> Issue | None:
        try:
            file_path, error_message = self._extract_structured_data_parts(line)
            if not file_path:
                return None

            return Issue(
                type=issue_type,
                severity=Priority.MEDIUM,
                message=error_message,
                file_path=file_path,
                line_number=None,
                stage="structured-data",
            )
        except Exception as e:
            self.logger.debug(f"Failed to parse structured data line: {line} ({e})")
            return None

    def _extract_structured_data_parts(self, line: str) -> tuple[str, str]:
        if line.startswith("✗"):
            line = line[1:].strip()

        if ":" not in line:
            return "", line

        file_path, error_message = line.split(":", 1)
        return file_path.strip(), error_message.strip()

    def _parse_codespell_output(
        self, raw_output: str, issue_type: IssueType
    ) -> list[Issue]:
        issues: list[Issue] = []

        for line in raw_output.split("\n"):
            line = line.strip()
            if not self._should_parse_codespell_line(line):
                continue

            issue = self._parse_single_codespell_line(line, issue_type)
            if issue:
                issues.append(issue)

        return issues

    def _should_parse_codespell_line(self, line: str) -> bool:
        return bool(line and "==>" in line)

    def _parse_single_codespell_line(
        self, line: str, issue_type: IssueType
    ) -> Issue | None:
        try:
            file_path, line_number, message = self._extract_codespell_parts(line)
            if not file_path:
                return None

            return Issue(
                type=issue_type,
                severity=Priority.LOW,
                message=message,
                file_path=file_path,
                line_number=line_number,
                stage="spelling",
            )
        except Exception as e:
            self.logger.debug(f"Failed to parse codespell line: {line} ({e})")
            return None

    def _extract_codespell_parts(self, line: str) -> tuple[str, int | None, str]:
        if ":" not in line:
            return "", None, ""

        file_path, rest = line.split(":", 1)

        if ":" not in rest:
            return file_path.strip(), None, rest.strip()

        line_number_str, message_part = rest.split(":", 1)
        line_number = self._parse_line_number(line_number_str)

        message = self._format_codespell_message(message_part)

        return file_path.strip(), line_number, message

    def _format_codespell_message(self, message_part: str) -> str:
        if "==>" in message_part:
            wrong_word, suggestions = message_part.split("==>", 1)
            return f"Spelling: '{wrong_word.strip()}' should be '{suggestions.strip()}'"
        return message_part.strip()

    def _parse_ruff_format_output(
        self, raw_output: str, issue_type: IssueType
    ) -> list[Issue]:
        issues: list[Issue] = []

        if "would be reformatted" in raw_output or "Failed to format" in raw_output:
            file_count = 1
            if "file" in raw_output:
                import re

                match = re.search(r"(\d+) files?", raw_output)
                if match:
                    file_count = int(match.group(1))

            message = f"{file_count} file(s) require formatting"

            if "error:" in raw_output:
                error_lines = [line for line in raw_output.split("\n") if line.strip()]
                if error_lines:
                    message = f"Formatting error: {error_lines[0]}"

            issues.append(
                Issue(
                    type=issue_type,
                    severity=Priority.MEDIUM,
                    message=message,
                    file_path=None,
                    line_number=None,
                    stage="formatting",
                    details=["Run 'uv run ruff format .' to fix"],
                )
            )

        return issues

    def _parse_generic_output(
        self,
        hook_name: str,
        raw_output: str,
        issue_type: IssueType,
    ) -> list[Issue]:
        issues: list[Issue] = []

        if not raw_output or not raw_output.strip():
            return issues

        issues.append(
            Issue(
                type=issue_type,
                severity=Priority.MEDIUM,
                message=f"{hook_name} check failed",
                file_path=None,
                line_number=None,
                stage=hook_name,
                details=[raw_output[:500]],
            )
        )

        return issues
