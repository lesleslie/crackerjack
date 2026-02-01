import asyncio
import json
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

from crackerjack.agents.base import AgentContext, FixResult, Issue
from crackerjack.parsers.factory import ParserFactory, ParsingError
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
    ) -> None:
        self.console = console or Console()
        self.pkg_path = pkg_path or Path.cwd()

        self.logger = logger or logging.getLogger("crackerjack.autofix")  # type: ignore[assignment]
        self._max_iterations = max_iterations
        self._coordinator_factory = coordinator_factory
        self._parser_factory = ParserFactory()  # Create parser factory instance

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

        # Track parsed counts per hook to update HookResult.issues_count
        # This fixes the mismatch where hook executors count raw output lines
        # but parsers return filtered actionable issues
        parsed_counts_by_hook: dict[str, int] = {}

        for result in hook_results:
            hook_issues = self._parse_single_hook_result(result)

            # Track how many issues we actually parsed for this hook
            if hasattr(result, "name"):
                hook_name = result.name
                if hook_name not in parsed_counts_by_hook:
                    parsed_counts_by_hook[hook_name] = 0
                parsed_counts_by_hook[hook_name] += len(hook_issues)

            issues.extend(hook_issues)

        # Update HookResult.issues_count to match parsed counts
        # This ensures AI-fix reports accurate issue counts
        # Only update if we actually parsed issues for this hook (count > 0 or hook failed)
        for result in hook_results:
            if hasattr(result, "name") and hasattr(result, "issues_count"):
                hook_name = getattr(result, "name")
                if hook_name in parsed_counts_by_hook:
                    old_count = getattr(result, "issues_count", 0)
                    new_count = parsed_counts_by_hook[hook_name]
                    # Only update if we actually parsed something or hook failed
                    # Don't update passed hooks with no issues
                    if new_count > 0 or (
                        hasattr(result, "status") and getattr(result, "status", "") == "failed"
                    ):
                        if old_count != new_count:
                            self.logger.debug(
                                f"Updated issues_count for '{hook_name}': "
                                f"{old_count} → {new_count} (matched to parsed issues)"
                            )
                            # Use setattr to avoid type checker errors on object type
                            setattr(result, "issues_count", new_count)

        seen: set[tuple[str | None, int | None, str, str]] = set()
        unique_issues: list[Issue] = []
        for issue in issues:
            # More specific deduplication key to avoid false positives
            # Include: file_path, line_number, stage (tool name), and full message
            # This prevents legitimate issues from being incorrectly deduplicated
            key = (
                issue.file_path,
                issue.line_number,
                issue.stage,  # Tool name (e.g., "mypy", "ruff-check")
                issue.message,  # Full message, not truncated
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
        """Parse hook output using JSON parser with validation.

        This method now uses the ParserFactory which automatically selects
        the appropriate parser (JSON or regex) based on tool capabilities.

        Args:
            hook_name: Name of the hook
            raw_output: Raw tool output (JSON or text)

        Returns:
            List of parsed Issue objects

        Raises:
            ParsingError: If parsing fails or validation fails
        """
        self.logger.debug(
            f"Parsing hook '{hook_name}': "
            f"raw_output_lines={len(raw_output.split(chr(10)))}"
        )

        # Extract expected issue count from output for validation
        expected_count = self._extract_issue_count(raw_output, hook_name)

        # Parse with validation using the factory
        try:
            issues = self._parser_factory.parse_with_validation(
                tool_name=hook_name,
                output=raw_output,
                expected_count=expected_count,
            )

            self.logger.info(
                f"Successfully parsed {len(issues)} issues from '{hook_name}'"
            )
            return issues

        except ParsingError as e:
            self.logger.error(f"Parsing failed for '{hook_name}': {e}")
            # Re-raise to fail fast - don't silently continue with wrong data
            raise

    def _extract_issue_count(self, output: str, tool_name: str) -> int | None:
        """Extract expected issue count from tool output.

        This attempts to parse the tool's output to determine how many issues
        it reported, for validation purposes.

        Args:
            output: Raw tool output
            tool_name: Name of the tool

        Returns:
            Expected issue count, or None if unable to determine

        Note:
            Returns None for tools that do filtering in the adapter (like complexipy)
            where the raw output can't be used to predict the final filtered count.
        """
        # Tools that do filtering in the adapter - skip validation
        # The adapter applies business logic (thresholds, filters) that can't be
        # determined from the raw output alone.
        if tool_name in ("complexipy", "refurb", "creosote"):
            # These tools output more data than the adapter ultimately returns:
            # - complexipy: outputs all functions (6076), adapter filters by threshold (~9)
            # - refurb: outputs all lines, adapter filters for "[FURB" prefix
            # - creosote: outputs multiple sections, adapter filters for "unused" deps
            # We can't predict the filtered count from raw output
            return None

        # Try parsing JSON to get count
        try:
            data = json.loads(output)
            if tool_name in ("ruff", "ruff-check"):
                return len(data) if isinstance(data, list) else None
            elif tool_name == "bandit":
                if isinstance(data, dict) and "results" in data:
                    results = data["results"]
                    return len(results) if isinstance(results, list) else None
            elif tool_name in ("mypy", "zuban"):
                return len(data) if isinstance(data, list) else None
        except (json.JSONDecodeError, TypeError):
            pass

        # Fallback: count lines that look like issues
        lines = output.split("\n")
        issue_lines = [
            line
            for line in lines
            if line.strip()
            and ":" in line
            and not line.strip().startswith(("#", "─", "Found"))
        ]
        return len(issue_lines) if issue_lines else None
