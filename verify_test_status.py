#!/usr/bin/env python3

import subprocess
import sys


def run_pytest_test(test_path, timeout=30):
    try:
        cmd = [
            sys.executable,
            "-m",
            "pytest",
            test_path,
            "-v",
            "--tb=short",
            "--timeout=10",
        ]
        result = subprocess.run(
            cmd,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd="/Users/les/Projects/crackerjack",
        )
        return result.returncode == 0, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return False, "", "Test timed out"
    except Exception as e:
        return False, "", f"Error running test: {e}"


def check_test_files():
    test_files = [
        "tests/test_qa_tool_adapters.py",
        "tests/unit/managers/test_hook_manager.py",
        "tests/test_error_handling_decorators.py",
        "tests/test_config_service.py",
        "tests/test_global_lock_config.py",
        "tests/test_performance_monitor.py",
        "tests/unit/agents/test_formatting_agent.py",
        "tests/unit/core/test_session_coordinator.py",
    ]

    results = {}
    for test_file in test_files:
        success, stdout, stderr = run_pytest_test(test_file)
        results[test_file] = {"success": success, "stdout": stdout, "stderr": stderr}

        if success or stderr:
            pass

    return results


def main() -> bool:
    results = check_test_files()

    passed = sum(1 for result in results.values() if result["success"])
    total = len(results)

    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
