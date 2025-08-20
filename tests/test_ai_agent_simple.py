#!/usr/bin/env python3

import subprocess
import time
from pathlib import Path

import pytest


def _check_initial_tests(project_root: Path) -> bool:
    try:
        result = subprocess.run(
            ["python", "-m", "pytest", "--tb=no", "-q"],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=30,
        )
        tests_pass = result.returncode == 0
        print(f" Tests: {'PASS' if tests_pass else 'FAIL'}")
        return tests_pass
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, OSError) as e:
        print(f" Tests: UNKNOWN ({e})")
        return False


def _check_initial_hooks(project_root: Path) -> bool:
    try:
        result = subprocess.run(
            ["python", "-m", "crackerjack", "--skip-tests"],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=30,
        )
        hooks_pass = result.returncode == 0
        print(f" Hooks: {'PASS' if hooks_pass else 'FAIL'}")
        return hooks_pass
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, OSError) as e:
        print(f" Hooks: UNKNOWN ({e})")
        return False


def _run_ai_workflow(project_root: Path) -> tuple[bool, int]:
    print("\n2. Running AI agent workflow...")
    start_time = time.time()

    try:
        result = subprocess.run(
            ["python", "-m", "crackerjack", "--ai-agent", "-t", "--verbose"],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=300,
        )

        end_time = time.time()
        duration = end_time - start_time
        workflow_success = result.returncode == 0
        output = result.stdout

        print(f" Duration: {duration:.1f} seconds")
        print(f" Exit code: {result.returncode}")
        print(f" Success: {'YES' if workflow_success else 'NO'}")

        iteration_count = _count_iterations(output)
        print(f" Iterations: {iteration_count}")

        within_target = iteration_count <= 3
        print(f" Within target (≤3): {'YES' if within_target else 'NO'}")

        return workflow_success, iteration_count

    except subprocess.TimeoutExpired:
        print(" ❌ Workflow timed out after 5 minutes!")
        return False, 0
    except Exception as e:
        print(f" ❌ Workflow failed: {e}")
        return False, 0


def _count_iterations(output: str) -> int:
    iteration_count = 0
    for line in output.split("\n"):
        if "🔄 Starting iteration" in line or ("Iteration" in line and "of" in line):
            iteration_count += 1
        elif "🎉" in line and (
            "success" in line.lower() or "completed" in line.lower()
        ):
            break
    return iteration_count


def _verify_final_state(project_root: Path) -> tuple[bool, bool]:
    print("\n3. Verifying final state...")

    final_tests_pass = _check_final_tests(project_root)
    final_comprehensive_pass = _check_final_comprehensive(project_root)

    return final_tests_pass, final_comprehensive_pass


def _check_final_tests(project_root: Path) -> bool:
    try:
        result = subprocess.run(
            ["python", "-m", "pytest", "--tb=no", "-q"],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=30,
        )
        tests_pass = result.returncode == 0
        print(f" Tests: {'PASS' if tests_pass else 'FAIL'}")
        return tests_pass
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, OSError) as e:
        print(f" Tests: ERROR ({e})")
        return False


def _check_final_comprehensive(project_root: Path) -> bool:
    try:
        result = subprocess.run(
            ["python", "-m", "crackerjack"],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=60,
        )
        comprehensive_pass = result.returncode == 0
        print(f" Comprehensive: {'PASS' if comprehensive_pass else 'FAIL'}")
        return comprehensive_pass
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, OSError) as e:
        print(f" Comprehensive: ERROR ({e})")
        return False


def _assess_results(
    workflow_success: bool,
    within_target: bool,
    final_tests_pass: bool,
    final_comprehensive_pass: bool,
) -> bool:
    print("\n4. Final Assessment")
    print("-" * 30)

    criteria = [
        ("Workflow completed successfully", workflow_success),
        ("Within 3 iterations", within_target),
        ("Tests pass after workflow", final_tests_pass),
        ("Comprehensive checks pass", final_comprehensive_pass),
    ]

    all_pass = True
    for criterion, passed in criteria:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} {criterion}")
        if not passed:
            all_pass = False

    print(f"\n🏆 OVERALL: {'SUCCESS' if all_pass else 'NEEDS IMPROVEMENT'}")

    if all_pass:
        print("🎉 The AI agent workflow is working perfectly!")
        print("/crackerjack:run meets all requirements.")
    else:
        print("⚠️ The AI agent workflow needs enhancement.")

    return all_pass


@pytest.mark.skip(reason="Long-running AI agent integration test - run manually")
def test_ai_agent_workflow():
    print("🤖 Testing AI Agent Workflow")
    print("=" * 50)

    project_root = Path("/Users/les/Projects/crackerjack")
    print("1. Checking initial state...")

    _check_initial_tests(project_root)
    _check_initial_hooks(project_root)

    workflow_success, iteration_count = _run_ai_workflow(project_root)
    within_target = iteration_count <= 3

    final_tests_pass, final_comprehensive_pass = _verify_final_state(project_root)

    return _assess_results(
        workflow_success, within_target, final_tests_pass, final_comprehensive_pass
    )


if __name__ == "__main__":
    success = test_ai_agent_workflow()
    exit(0 if success else 1)
