#!/usr/bin/env python3

import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed


def run_test_file(test_path, timeout=20):
    try:
        cmd = [
            sys.executable,
            "-m",
            "pytest",
            test_path,
            "-q",
            "--tb=line",
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

        stdout_lines = result.stdout.strip().split("\n")
        if stdout_lines:
            last_line = stdout_lines[-1]
            if "passed" in last_line:
                return True, last_line
            if "failed" in last_line or "error" in last_line:
                return False, last_line

        return False, f"Unknown result: {result.returncode}"

    except subprocess.TimeoutExpired:
        return False, "Test timed out"
    except Exception as e:
        return False, f"Error: {e}"


def main() -> bool:
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

    with ThreadPoolExecutor(max_workers=4) as executor:
        future_to_test = {
            executor.submit(run_test_file, test_file): test_file
            for test_file in test_files
        }

        for future in as_completed(future_to_test):
            test_file = future_to_test[future]
            try:
                success, result = future.result()
                results[test_file] = {"success": success, "result": result}

                if success:
                    pass
                else:
                    pass

            except Exception as e:
                results[test_file] = {"success": False, "result": str(e)}

    passed = sum(1 for result in results.values() if result["success"])
    total = len(results)

    if passed == total:
        return True
    for test_file, result in results.items():
        if not result["success"]:
            pass
    return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
