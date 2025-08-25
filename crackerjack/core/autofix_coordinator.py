"""Autofix coordination and retry logic for crackerjack workflows."""

import logging
import subprocess
import typing as t
from pathlib import Path

from rich.console import Console


class AutofixCoordinator:
    def __init__(self, console: Console, pkg_path: Path) -> None:
        self.console = console
        self.pkg_path = pkg_path
        self.logger = logging.getLogger("crackerjack.autofix")

    def apply_autofix_for_hooks(self, mode: str, hook_results: list[t.Any]) -> bool:
        self.logger.debug(
            f"Applying autofix for {mode} mode with {len(hook_results)} hook results",
        )
        try:
            if self._should_skip_autofix(hook_results):
                self.logger.info(
                    f"Skipping autofix for {mode} - unfixable error patterns detected",
                )
                return False
            if mode == "fast":
                result = self._apply_fast_stage_fixes()
                self.logger.debug(f"Fast stage fixes result: {result}")
                return result
            if mode == "comprehensive":
                result = self._apply_comprehensive_stage_fixes(hook_results)
                self.logger.debug(f"Comprehensive stage fixes result: {result}")
                return result
            self.logger.warning(f"Unknown autofix mode: {mode}")
            return False
        except Exception as e:
            self.logger.error(f"Auto-fix error in {mode} mode: {e}", exc_info=True)
            self.console.print(f"[dim red]Auto-fix error: {e}[/dim red]")
            return False

    def apply_fast_stage_fixes(self) -> bool:
        """Public interface for applying fast stage fixes."""
        return self._apply_fast_stage_fixes()

    def apply_comprehensive_stage_fixes(self, hook_results: list[t.Any]) -> bool:
        """Public interface for applying comprehensive stage fixes."""
        return self._apply_comprehensive_stage_fixes(hook_results)

    def run_fix_command(self, cmd: list[str], description: str) -> bool:
        """Public interface for running fix commands."""
        return self._run_fix_command(cmd, description)

    def check_tool_success_patterns(self, cmd: list[str], result: t.Any) -> bool:
        """Public interface for checking tool success patterns."""
        return self._check_tool_success_patterns(cmd, result)

    def validate_fix_command(self, cmd: list[str]) -> bool:
        """Public interface for validating fix commands."""
        return self._validate_fix_command(cmd)

    def validate_hook_result(self, result: t.Any) -> bool:
        """Public interface for validating hook results."""
        return self._validate_hook_result(result)

    def should_skip_autofix(self, hook_results: list[t.Any]) -> bool:
        """Public interface for checking if autofix should be skipped."""
        return self._should_skip_autofix(hook_results)

    def _apply_fast_stage_fixes(self) -> bool:
        return self._execute_fast_fixes()

    def _execute_fast_fixes(self) -> bool:
        fixes_applied = False
        fix_commands = [
            (["uv", "run", "ruff", "format", "."], "ruff formatting"),
            (["uv", "run", "ruff", "check", ".", "--fix"], "ruff auto-fixes"),
        ]
        for cmd, description in fix_commands:
            if self._run_fix_command(cmd, description):
                fixes_applied = True

        return fixes_applied

    def _apply_comprehensive_stage_fixes(self, hook_results: list[t.Any]) -> bool:
        fixes_applied = False
        if self._apply_fast_stage_fixes():
            fixes_applied = True
        failed_hooks = self._extract_failed_hooks(hook_results)
        hook_specific_fixes = self._get_hook_specific_fixes(failed_hooks)
        for cmd, description in hook_specific_fixes:
            if self._run_fix_command(cmd, description):
                fixes_applied = True

        return fixes_applied

    def _extract_failed_hooks(self, hook_results: list[t.Any]) -> set[str]:
        failed_hooks: set[str] = set()
        for result in hook_results:
            if self._validate_hook_result(result):
                hook_name: str = getattr(result, "name", "").lower()
                hook_status: str = getattr(result, "status", "")
                if hook_status == "Failed" and hook_name:
                    failed_hooks.add(hook_name)

        return failed_hooks

    def _get_hook_specific_fixes(
        self,
        failed_hooks: set[str],
    ) -> list[tuple[list[str], str]]:
        hook_specific_fixes: list[tuple[list[str], str]] = []
        if "bandit" in failed_hooks:
            hook_specific_fixes.append(
                (["uv", "run", "bandit", "-f", "json", ".", "-ll"], "bandit analysis"),
            )

        return hook_specific_fixes

    def _run_fix_command(self, cmd: list[str], description: str) -> bool:
        if not self._validate_fix_command(cmd):
            return False
        try:
            result = subprocess.run(
                cmd,
                check=False,
                capture_output=True,
                text=True,
                timeout=30,
                cwd=self.pkg_path,
            )
            return self._handle_command_result(result, description)
        except Exception:
            return False

    def _handle_command_result(
        self,
        result: subprocess.CompletedProcess[str],
        description: str,
    ) -> bool:
        return bool(result.returncode == 0 or self._is_successful_fix(result))

    def _is_successful_fix(self, result: subprocess.CompletedProcess[str]) -> bool:
        output = result.stdout.lower()
        return "fixed" in output or "reformatted" in output

    def _check_tool_success_patterns(self, cmd: list[str], result: t.Any) -> bool:
        """Check if a tool command result indicates success."""
        if not cmd or len(cmd) < 3:
            return False

        tool_name = cmd[2] if len(cmd) > 2 else ""

        # Check if result is a subprocess.CompletedProcess
        if hasattr(result, "returncode"):
            return result.returncode == 0

        # Check for specific tool success patterns
        if isinstance(result, str):
            output_lower = result.lower()
            if "ruff" in tool_name:
                return "fixed" in output_lower or "would reformat" in output_lower
            if "trailing-whitespace" in tool_name:
                return "fixing" in output_lower or "fixed" in output_lower

        return False

    def _validate_fix_command(self, cmd: list[str]) -> bool:
        if len(cmd) < 3:
            return False
        if cmd[0] != "uv" or cmd[1] != "run":
            return False
        tool_name = cmd[2]
        return tool_name in ("ruff", "bandit")

    def _validate_hook_result(self, result: t.Any) -> bool:
        if not hasattr(result, "name") or not hasattr(result, "status"):
            self.logger.warning(f"Invalid hook result structure: {type(result)}")
            return False
        name = getattr(result, "name", None)
        status = getattr(result, "status", None)
        if not isinstance(name, str) or not name.strip():
            self.logger.warning(f"Hook result has invalid name: {name}")
            return False
        if status not in ("Passed", "Failed", "Skipped", "Error"):
            self.logger.warning(f"Hook result has invalid status: {status}")
            return False

        return True

    def _should_skip_autofix(self, hook_results: list[t.Any]) -> bool:
        for result in hook_results:
            if hasattr(result, "raw_output"):
                output = getattr(result, "raw_output", "")
                if "ModuleNotFoundError" in output or "ImportError" in output:
                    self.console.print(
                        "[dim yellow]  → Skipping autofix (import errors)[/dim yellow]",
                    )
                    return True
        return False
