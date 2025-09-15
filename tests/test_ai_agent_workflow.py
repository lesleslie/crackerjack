import asyncio
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

sys.path.append(os.path.expanduser("~ / Projects / claude / toolkits"))

try:
    from verification.verification_toolkit import VerificationToolkit

    VERIFICATION_AVAILABLE = True
except ImportError:
    VERIFICATION_AVAILABLE = False


class AIAgentWorkflowTester:
    def __init__(self) -> None:
        self.project_root = Path("/ Users / les / Projects / crackerjack")
        self.test_results: dict[str, str] = {}
        self.verification_toolkit = None

        if VERIFICATION_AVAILABLE:
            self.verification_toolkit = VerificationToolkit()

    def setup_test_environment(self) -> dict[str, Any]:
        return {
            "timestamp": time.time(),
            "git_status": self._get_git_status(),
            "test_status": self._run_quick_test_check(),
            "hook_status": self._run_quick_hook_check(),
            "python_files": list(self.project_root.glob(" **/ * .py")),
        }

    def _get_git_status(self) -> dict[str, list[str]]:
        try:
            result = subprocess.run(
                ["git", "status", " - - porcelain"],
                check=False,
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=10,
            )

            lines = result.stdout.strip().split("\n") if result.stdout.strip() else []

            status = {"modified": [], "added": [], "deleted": [], "untracked": []}

            for line in lines:
                if line.startswith(" M"):
                    status["modified"].append(line[3:])
                elif line.startswith("A"):
                    status["added"].append(line[3:])
                elif line.startswith(" D"):
                    status["deleted"].append(line[3:])
                elif line.startswith("??"):
                    status["untracked"].append(line[3:])

            return status

        except Exception as e:
            return {
                "error": str(e),
                "modified": [],
                "added": [],
                "deleted": [],
                "untracked": [],
            }

    def _run_quick_test_check(self) -> dict[str, Any]:
        try:
            result = subprocess.run(
                ["python", " - m", "pytest", " - - tb = no", " - q"],
                check=False,
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=60,
            )

            return {
                "return_code": result.returncode,
                "passed": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }

        except subprocess.TimeoutExpired:
            return {"error": "Test check timed out", "passed": False}
        except Exception as e:
            return {"error": str(e), "passed": False}

    def _run_quick_hook_check(self) -> dict[str, Any]:
        try:
            result = subprocess.run(
                [
                    "python",
                    " - m",
                    "crackerjack",
                    " - - skip - comprehensive",
                    " - - skip - tests",
                ],
                check=False,
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=30,
            )

            return {
                "return_code": result.returncode,
                "passed": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }

        except subprocess.TimeoutExpired:
            return {"error": "Hook check timed out", "passed": False}
        except Exception as e:
            return {"error": str(e), "passed": False}

    async def run_ai_agent_workflow(self) -> dict[str, Any]:
        if self.verification_toolkit:
            return await self._run_with_verification()
        return await self._run_basic_workflow()

    async def _run_with_verification(self) -> dict[str, Any]:
        def execute_ai_workflow():
            return subprocess.run(
                [
                    "python",
                    " - m",
                    "crackerjack",
                    " - - ai - agent",
                    " - t",
                    " - - verbose",
                ],
                check=False,
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=600,
            )

        workflow_result = self.verification_toolkit.execute_with_verification(
            "ai_agent_workflow",
            execute_ai_workflow,
        )

        output = workflow_result.get("result", {}).get("stdout", "")
        iterations = self._parse_iterations_from_output(output)

        return {
            "verification_success": workflow_result["success"],
            "process_result": workflow_result.get("result", {}),
            "iterations": iterations,
            "evidence": workflow_result.get("evidence", {}),
            "total_iterations": len(iterations),
        }

    async def _run_basic_workflow(self) -> dict[str, Any]:
        try:
            result = subprocess.run(
                [
                    "python",
                    " - m",
                    "crackerjack",
                    " - - ai - agent",
                    " - t",
                    " - - verbose",
                ],
                check=False,
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=600,
            )

            iterations = self._parse_iterations_from_output(result.stdout)

            return {
                "verification_success": result.returncode == 0,
                "process_result": {
                    "returncode": result.returncode,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                },
                "iterations": iterations,
                "total_iterations": len(iterations),
            }

        except subprocess.TimeoutExpired:
            return {
                "verification_success": False,
                "error": "AI agent workflow timed out after 10 minutes",
                "iterations": [],
                "total_iterations": 0,
            }
        except Exception as e:
            return {
                "verification_success": False,
                "error": str(e),
                "iterations": [],
                "total_iterations": 0,
            }

    def _parse_iterations_from_output(self, output: str) -> list[dict[str, Any]]:
        iterations: list[dict[str, Any]] = []
        lines = output.split("\n")
        current_iteration = None

        for line in lines:
            if self._is_iteration_start(line):
                if current_iteration:
                    iterations.append(current_iteration)
                current_iteration = self._create_new_iteration(len(iterations) + 1)
            elif current_iteration:
                self._process_iteration_line(line, current_iteration)

        if current_iteration:
            iterations.append(current_iteration)

        return iterations

    def _is_iteration_start(self, line: str) -> bool:
        return "🔄 Starting iteration" in line or ("Iteration" in line and "of" in line)

    def _create_new_iteration(self, number: int) -> dict[str, Any]:
        return {
            "iteration_number": number,
            "stages": [],
            "errors_fixed": 0,
            "success": False,
        }

    def _process_iteration_line(
        self,
        line: str,
        current_iteration: dict[str, Any],
    ) -> None:
        stage_mapping = {
            "⚡ Fast Hooks": "fast_hooks",
            "🧪 Full Test Suite": "tests",
            "🔍 Comprehensive Hooks": "comprehensive_hooks",
            "🤖 AI Analysis": "ai_analysis",
        }

        for marker, stage in stage_mapping.items():
            if marker in line:
                current_iteration["stages"].append(stage)
                return

        if "fixes applied" in line.lower():
            self._extract_fixes_count(line, current_iteration)
        elif "🎉" in line and (
            "success" in line.lower() or "completed" in line.lower()
        ):
            current_iteration["success"] = True

    def _extract_fixes_count(
        self,
        line: str,
        current_iteration: dict[str, Any],
    ) -> None:
        try:
            import re

            match = re.search(
                r"(\d +)\s + fixes?\s + applied", line.lower()
            )  # REGEX OK: parsing test output format
            if match:
                current_iteration["errors_fixed"] += int(match.group(1))
        except (ValueError, AttributeError, ImportError):
            pass

    def verify_final_state(self) -> dict[str, Any]:
        final_state = {
            "timestamp": time.time(),
            "git_status": self._get_git_status(),
            "test_status": self._run_quick_test_check(),
            "hook_status": self._run_quick_hook_check(),
        }

        comprehensive_result = self._run_comprehensive_check()
        final_state["comprehensive_check"] = comprehensive_result

        final_state["all_tests_pass"] = final_state["test_status"]["passed"]
        final_state["all_hooks_pass"] = final_state["hook_status"]["passed"]
        final_state["comprehensive_pass"] = comprehensive_result["passed"]

        final_state["workflow_success"] = all(
            [
                final_state["all_tests_pass"],
                final_state["all_hooks_pass"],
                final_state["comprehensive_pass"],
            ],
        )

        return final_state

    def _run_comprehensive_check(self) -> dict[str, Any]:
        try:
            result = subprocess.run(
                ["python", " - m", "crackerjack"],
                check=False,
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=300,  # Fixed: Use 300s to match pytest config
            )

            return {
                "return_code": result.returncode,
                "passed": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }

        except subprocess.TimeoutExpired:
            return {"error": "Comprehensive check timed out", "passed": False}
        except Exception as e:
            return {"error": str(e), "passed": False}

    def generate_test_report(
        self,
        initial_state: dict,
        workflow_result: dict,
        final_state: dict,
    ) -> str:
        report = []
        report.append(" = " * 80)
        report.append("🤖 AI AGENT WORKFLOW TEST REPORT")
        report.append(" = " * 80)
        report.append("")

        report.append("📊 TEST SUMMARY")
        report.append(" - " * 40)

        workflow_success = workflow_result.get("verification_success", False)
        final_success = final_state.get("workflow_success", False)
        total_iterations = workflow_result.get("total_iterations", 0)

        report.append(
            f"✅ Workflow Execution: {'SUCCESS' if workflow_success else 'FAILED'}",
        )
        report.append(f"✅ Final State: {'SUCCESS' if final_success else 'FAILED'}")
        report.append(f"🔄 Total Iterations: {total_iterations}")
        report.append("🎯 Target: ≤ 3 iterations")
        report.append(
            f"📈 Efficiency: {'EXCELLENT' if total_iterations <= 3 else 'NEEDS IMPROVEMENT'}",
        )
        report.append("")

        report.append("📈 BEFORE vs AFTER COMPARISON")
        report.append(" - " * 40)

        initial_tests_pass = initial_state.get("test_status", {}).get("passed", False)
        initial_hooks_pass = initial_state.get("hook_status", {}).get("passed", False)

        final_tests_pass = final_state.get("all_tests_pass", False)
        final_hooks_pass = final_state.get("all_hooks_pass", False)
        final_comprehensive_pass = final_state.get("comprehensive_pass", False)

        report.append(
            f"🧪 Tests: {self._status_change(initial_tests_pass, final_tests_pass)}",
        )
        report.append(
            f"🪝 Hooks: {self._status_change(initial_hooks_pass, final_hooks_pass)}",
        )
        report.append(
            f"🔍 Comprehensive: {'N / A' if initial_state.get('comprehensive_check') is None else 'INITIAL'} → {'PASS' if final_comprehensive_pass else 'FAIL'}",
        )
        report.append("")

        if workflow_result.get("iterations"):
            report.append("🔄 ITERATION BREAKDOWN")
            report.append(" - " * 40)

            for i, iteration in enumerate(workflow_result["iterations"], 1):
                report.append(f"Iteration {i}: ")
                report.append(f" 📋 Stages: {', '.join(iteration.get('stages', []))}")
                report.append(f" 🔧 Fixes Applied: {iteration.get('errors_fixed', 0)}")
                report.append(
                    f" ✅ Success: {'YES' if iteration.get('success', False) else 'NO'}",
                )
                report.append("")

        if workflow_result.get("evidence"):
            report.append("🔍 VERIFICATION EVIDENCE")
            report.append(" - " * 40)
            evidence = workflow_result["evidence"]

            if "pre_state" in evidence:
                report.append("📍 Pre - execution state captured ✓")
            if "post_state" in evidence:
                report.append("📍 Post - execution state captured ✓")

            report.append("")

        report.append("🎯 SUCCESS CRITERIA ASSESSMENT")
        report.append(" - " * 40)

        criteria = [
            ("Fixes ALL current errors", final_success),
            ("Completes within 3 iterations", total_iterations <= 3),
            (
                "Stops with success when all stages pass",
                workflow_success and final_success,
            ),
            ("All tests pass after completion", final_tests_pass),
            ("All hooks pass after completion", final_hooks_pass),
            ("Comprehensive quality check passes", final_comprehensive_pass),
        ]

        all_criteria_met = True
        for criterion, met in criteria:
            status: str = "✅ PASS" if met else "❌ FAIL"
            report.append(f"{status} {criterion}")
            if not met:
                all_criteria_met = False

        report.append("")

        report.append("🏆 FINAL VERDICT")
        report.append(" - " * 40)

        if all_criteria_met:
            report.append("🎉 EXCELLENT: AI agent workflow meets all requirements ! ")
            report.append(" The / crackerjack: run slash command is working perfectly.")
        else:
            report.append("⚠️ IMPROVEMENT NEEDED: Some criteria not met.")
            report.append(" The AI agent workflow needs enhancement.")

        report.append("")
        report.append(" = " * 80)

        return "\n".join(report)

    def _status_change(self, before: bool, after: bool) -> str:
        before_str = "PASS" if before else "FAIL"
        after_str = "PASS" if after else "FAIL"

        if before == after:
            return f"{before_str} → {after_str} (no change)"
        if after:
            return f"{before_str} → {after_str} ✅ IMPROVED"
        return f"{before_str} → {after_str} ❌ REGRESSED"

    async def run_complete_test(self) -> dict[str, Any]:
        initial_state = self.setup_test_environment()

        workflow_result = await self.run_ai_agent_workflow()

        final_state = self.verify_final_state()

        report = self.generate_test_report(initial_state, workflow_result, final_state)

        return {
            "initial_state": initial_state,
            "workflow_result": workflow_result,
            "final_state": final_state,
            "report": report,
            "test_success": (
                workflow_result.get("verification_success", False)
                and final_state.get("workflow_success", False)
                and workflow_result.get("total_iterations", 999) <= 3
            ),
        }


async def main() -> None:
    tester = AIAgentWorkflowTester()

    try:
        result = await tester.run_complete_test()

        results_file = Path(
            " / Users / les / Projects / crackerjack / ai_agent_test_results.json",
        )
        with open(results_file, "w") as f:
            json.dump(
                {
                    "timestamp": time.time(),
                    "test_success": result["test_success"],
                    "workflow_result": result["workflow_result"],
                    "final_state": result["final_state"],
                },
                f,
                indent=2,
                default=str,
            )

        sys.exit(0 if result["test_success"] else 1)

    except KeyboardInterrupt:
        sys.exit(130)
    except Exception:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
