import logging
import os
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

from rich.console import Console

if TYPE_CHECKING:
    from crackerjack.models.protocols import LoggerProtocol

from crackerjack.agents.base import AgentContext, Issue, IssueType, Priority
from crackerjack.agents.coordinator import AgentCoordinator
from crackerjack.services.cache import CrackerjackCache

logger = logging.getLogger(__name__)


class AutofixCoordinator:
    def __init__(
        self,
        console: Console | None = None,
        pkg_path: Path | None = None,
        logger: "LoggerProtocol | None" = None,
        max_iterations: int | None = None,
    ) -> None:
        self.console = console or Console()
        self.pkg_path = pkg_path or Path.cwd()

        self.logger = logger or logging.getLogger("crackerjack.autofix")  # type: ignore[assignment]
        self._max_iterations = max_iterations

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

    def apply_fast_stage_fixes(self) -> bool:
        return self._apply_fast_stage_fixes()

    def apply_comprehensive_stage_fixes(self, hook_results: list[object]) -> bool:
        return self._apply_comprehensive_stage_fixes(hook_results)

    def run_fix_command(self, cmd: list[str], description: str) -> bool:
        return self._run_fix_command(cmd, description)

    def check_tool_success_patterns(self, cmd: list[str], result: object) -> bool:
        return self._check_tool_success_patterns(cmd, result)

    def validate_fix_command(self, cmd: list[str]) -> bool:
        return self._validate_fix_command(cmd)

    def validate_hook_result(self, result: object) -> bool:
        return self._validate_hook_result(result)

    def should_skip_autofix(self, hook_results: list[object]) -> bool:
        return self._should_skip_autofix(hook_results)

    def _apply_fast_stage_fixes(self) -> bool:
        return self._execute_fast_fixes()

    def _apply_comprehensive_stage_fixes(self, hook_results: list[object]) -> bool:
        ai_agent_enabled = os.environ.get("AI_AGENT") == "1"

        if ai_agent_enabled:
            self.logger.info("AI agent mode enabled, attempting AI-based fixing")
            return self._apply_ai_agent_fixes(hook_results)

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

    def _extract_failed_hooks(self, hook_results: list[object]) -> set[str]:
        failed_hooks = set()
        for result in hook_results:
            if (
                self._validate_hook_result(result)
                and getattr(result, "status", "") == "Failed"
            ):
                failed_hooks.add(getattr(result, "name", ""))
        return failed_hooks

    def _get_hook_specific_fixes(
        self,
        failed_hooks: set[str],
    ) -> list[tuple[list[str], str]]:
        fixes = []

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

        valid_statuses = ["Passed", "Failed", "Skipped", "Error"]
        return status in valid_statuses

    def _should_skip_autofix(self, hook_results: list[object]) -> bool:
        for result in hook_results:
            raw_output = getattr(result, "raw_output", None)
            if raw_output:
                output_lower = raw_output.lower()

                if (
                    "importerror" in output_lower
                    or "modulenotfounderror" in output_lower
                ):
                    self.logger.info("Skipping autofix for import errors")
                    return True
        return False

    def _apply_ai_agent_fixes(self, hook_results: list[object]) -> bool:
        """
        Apply AI agent fixes with Ralph-style retry loop.

        Iterates until all issues are fixed or max_iterations is reached.
        Re-runs quality checks on each iteration to detect new/remaining issues.

        Args:
            hook_results: Initial hook execution results

        Returns:
            bool: True if all issues resolved, False otherwise
        """
        import asyncio

        max_iterations = self._get_max_iterations()

        context = AgentContext(
            project_path=self.pkg_path,
            subprocess_timeout=300,
        )

        cache = CrackerjackCache()
        coordinator = AgentCoordinator(context=context, cache=cache)

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        previous_issue_count = float("inf")
        no_progress_count = 0

        for iteration in range(max_iterations):
            # Collect and check issues
            issues = self._get_iteration_issues(iteration, hook_results)
            current_issue_count = len(issues)

            # Check for success
            if current_issue_count == 0:
                self._report_iteration_success(iteration)
                return True

            # Check convergence
            if self._should_stop_on_convergence(
                current_issue_count,
                previous_issue_count,
                no_progress_count,
            ):
                return False

            # Update progress tracking
            no_progress_count = self._update_progress_count(
                current_issue_count,
                previous_issue_count,
                no_progress_count,
            )

            # Report progress
            self._report_iteration_progress(iteration, max_iterations, current_issue_count)

            # Apply fixes
            if not self._run_ai_fix_iteration(coordinator, loop, issues):
                return False

            previous_issue_count = current_issue_count

        # Max iterations reached
        return self._report_max_iterations_reached(max_iterations)

    def _get_iteration_issues(
        self,
        iteration: int,
        hook_results: list[object],
    ) -> list[Issue]:
        """Get issues for current iteration."""
        if iteration == 0:
            return self._parse_hook_results_to_issues(hook_results)
        return self._collect_current_issues()

    def _report_iteration_success(self, iteration: int) -> None:
        """Report successful resolution of all issues."""
        self.console.print(
            f"[green]✓ All issues resolved in {iteration} iteration(s)![/green]"
        )
        self.logger.info(f"All issues resolved in {iteration} iteration(s)")

    def _should_stop_on_convergence(
        self,
        current_count: int,
        previous_count: float,
        no_progress_count: int,
    ) -> bool:
        """Check if we should stop due to lack of progress."""
        convergence_threshold = self._get_convergence_threshold()

        if current_count >= previous_count:
            if no_progress_count + 1 >= convergence_threshold:
                self.console.print(
                    f"[yellow]⚠ No progress for {convergence_threshold} iterations "
                    f"({current_count} issues remain)[/yellow]"
                )
                self.logger.warning(
                    f"No progress for {convergence_threshold} iterations, "
                    f"{current_count} issues remain"
                )
                return True
        return False

    def _update_progress_count(
        self,
        current_count: int,
        previous_count: float,
        no_progress_count: int,
    ) -> int:
        """Update progress tracking count."""
        if current_count >= previous_count:
            return no_progress_count + 1
        return 0  # Reset if making progress

    def _report_iteration_progress(
        self,
        iteration: int,
        max_iterations: int,
        issue_count: int,
    ) -> None:
        """Report progress for current iteration."""
        self.console.print(
            f"[cyan]→ Iteration {iteration + 1}/{max_iterations}: "
            f"{issue_count} issues to fix[/cyan]"
        )
        self.logger.info(
            f"Iteration {iteration + 1}/{max_iterations}: "
            f"{issue_count} issues to fix"
        )

    def _run_ai_fix_iteration(
        self,
        coordinator: "AgentCoordinator",
        loop: "asyncio.AbstractEventLoop",
        issues: list[Issue],
    ) -> bool:
        """
        Run a single AI fix iteration.

        Returns:
            bool: True if iteration succeeded, False otherwise
        """
        try:
            fix_result = loop.run_until_complete(coordinator.handle_issues(issues))
        except Exception:
            self.logger.exception("AI agent handling failed")
            return False

        if not fix_result.success:
            self.console.print(
                "[yellow]⚠ Agents cannot fix remaining issues[/yellow]"
            )
            self.logger.warning("AI agents cannot fix remaining issues")
            return False

        self.logger.info(
            f"Fixed {len(fix_result.fixes_applied)} issues "
            f"with confidence {fix_result.confidence:.2f}"
        )
        return True

    def _report_max_iterations_reached(self, max_iterations: int) -> bool:
        """Report that max iterations were reached."""
        final_issue_count = len(self._collect_current_issues())
        self.console.print(
            f"[yellow]⚠ Reached {max_iterations} iterations with "
            f"{final_issue_count} issues remaining[/yellow]"
        )
        self.logger.warning(
            f"Reached {max_iterations} iterations with {final_issue_count} issues remaining"
        )
        return False

    def _parse_hook_results_to_issues(self, hook_results: list[object]) -> list[Issue]:
        issues: list[Issue] = []

        for result in hook_results:
            if not self._validate_hook_result(result):
                continue

            if getattr(result, "status", "") != "Failed":
                continue

            hook_name = getattr(result, "name", "")
            raw_output = getattr(result, "raw_output", "")

            if not hook_name:
                continue

            hook_issues = self._parse_hook_to_issues(hook_name, raw_output)
            issues.extend(hook_issues)

        return issues

    def _get_max_iterations(self) -> int:
        """Get maximum AI fix iterations from parameter, environment, or default."""
        import os

        if self._max_iterations is not None:
            return self._max_iterations

        return int(os.environ.get("CRACKERJACK_AI_FIX_MAX_ITERATIONS", "5"))

    def _get_convergence_threshold(self) -> int:
        """Get convergence threshold from environment or default."""
        import os

        return int(os.environ.get("CRACKERJACK_AI_FIX_CONVERGENCE_THRESHOLD", "3"))

    def _collect_current_issues(self) -> list[Issue]:
        """
        Re-run quality checks to collect current issues.

        This method is called on each retry loop iteration to detect:
        - New issues introduced by AI fixes
        - Remaining issues that weren't fixed
        - Issues that changed after fixes

        Returns:
            list[Issue]: Current issues from quality checks
        """
        import subprocess

        self.logger.debug("Collecting current issues by re-running quality checks")

        # Run a subset of fast hooks to detect current issues
        # We focus on hooks that are most likely to catch issues introduced by AI fixes
        check_commands = [
            (["uv", "run", "ruff", "check", "."], "ruff"),
            (["uv", "run", "ruff", "format", "--check", "."], "ruff-format"),
        ]

        all_issues: list[Issue] = []

        for cmd, hook_name in check_commands:
            try:
                result = subprocess.run(
                    cmd,
                    check=False,
                    cwd=self.pkg_path,
                    capture_output=True,
                    text=True,
                    timeout=60,
                )

                if result.returncode != 0 or result.stdout:
                    hook_issues = self._parse_hook_to_issues(
                        hook_name,
                        result.stdout + result.stderr,
                    )
                    all_issues.extend(hook_issues)

            except subprocess.TimeoutExpired:
                self.logger.warning(f"Timeout running {hook_name} check")
            except Exception as e:
                self.logger.warning(f"Error running {hook_name} check: {e}")

        self.logger.debug(f"Collected {len(all_issues)} current issues")
        return all_issues

    def _parse_hook_to_issues(self, hook_name: str, raw_output: str) -> list[Issue]:
        issues: list[Issue] = []

        hook_type_map: dict[str, IssueType] = {
            "zuban": IssueType.TYPE_ERROR,
            "refurb": IssueType.COMPLEXITY,
            "complexipy": IssueType.COMPLEXITY,
            "pyright": IssueType.TYPE_ERROR,
            "mypy": IssueType.TYPE_ERROR,
            "ruff": IssueType.FORMATTING,
            "bandit": IssueType.SECURITY,
            "vulture": IssueType.DEAD_CODE,
            "skylos": IssueType.DEAD_CODE,
            "creosote": IssueType.DEPENDENCY,
        }

        issue_type = hook_type_map.get(hook_name)
        if not issue_type:
            self.logger.debug(f"Unknown hook type: {hook_name}")
            return issues

        if hook_name in ("zuban", "pyright", "mypy"):
            issues.extend(
                self._parse_type_checker_output(hook_name, raw_output, issue_type)
            )
        elif hook_name == "refurb":
            issues.extend(self._parse_refurb_output(raw_output, issue_type))
        elif hook_name == "complexipy":
            issues.extend(self._parse_complexity_output(raw_output, issue_type))
        elif hook_name == "bandit":
            issues.extend(self._parse_security_output(raw_output, issue_type))
        elif hook_name in ("vulture", "skylos"):
            issues.extend(self._parse_dead_code_output(raw_output, issue_type))
        else:
            issues.extend(self._parse_generic_output(hook_name, raw_output, issue_type))

        return issues

    def _parse_type_checker_output(
        self,
        tool_name: str,
        raw_output: str,
        issue_type: IssueType,
    ) -> list[Issue]:
        """Parse type checker output (zuban, pyright, mypy) into Issue objects."""
        issues: list[Issue] = []

        for line in raw_output.split("\n"):
            line = line.strip()
            if not self._should_parse_line(line):
                continue

            issue = self._parse_type_checker_line(line, tool_name, issue_type)
            if issue:
                issues.append(issue)

        return issues

    def _should_parse_line(self, line: str) -> bool:
        """Check if a line should be parsed for type checker issues."""
        if not line:
            return False
        return not line.startswith(("Found", "Checked"))

    def _parse_type_checker_line(
        self,
        line: str,
        tool_name: str,
        issue_type: IssueType,
    ) -> Issue | None:
        """Parse a single type checker line into an Issue object."""
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
        """Parse line number from type checker output."""
        try:
            return int(part.strip())
        except (ValueError, IndexError):
            return None

    def _extract_message(self, parts: list[str], fallback: str) -> str:
        """Extract error message from type checker output parts."""
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

    def _parse_complexity_output(
        self, raw_output: str, issue_type: IssueType
    ) -> list[Issue]:
        issues: list[Issue] = []

        for line in raw_output.split("\n"):
            line = line.strip()
            if not line or "complexity" not in line.lower():
                continue

            if "-" in line and ":" in line:
                parts = line.split("-", 1)
                if len(parts) == 2:
                    location = parts[0].strip()
                    message = parts[1].strip()

                    file_path = (
                        location.split(":")[0].strip() if ":" in location else location
                    )

                    issues.append(
                        Issue(
                            type=issue_type,
                            severity=Priority.MEDIUM,
                            message=message,
                            file_path=file_path,
                            line_number=None,
                            stage="complexity",
                        )
                    )

        return issues

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
