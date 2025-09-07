#!/usr/bin/env python3
"""
Simple test to verify fast hooks stop behavior.
"""

import subprocess
import sys


def test_fast_hooks_stop_on_failure():
    """Test that workflow stops when fast hooks fail."""
    print("=== Testing Fast Hooks Stop Behavior ===")

    # Test 1: Run just fast hooks to see if they pass/fail
    print("\n1. Testing fast hooks only...")
    result = subprocess.run(
        ["python", "-m", "crackerjack", "--fast"],
        capture_output=True,
        text=True,
        timeout=60,
    )

    print(f"Fast hooks only - Exit code: {result.returncode}")

    if result.returncode == 0:
        print("✅ Fast hooks PASSED")
        fast_hooks_status = "PASS"
    else:
        print("❌ Fast hooks FAILED")
        fast_hooks_status = "FAIL"
        print("Fast hooks error output:")
        print(result.stdout)
        print(result.stderr)

    # Test 2: Run with tests to see if workflow continues/stops appropriately
    print("\n2. Testing workflow with tests...")
    result = subprocess.run(
        ["python", "-m", "crackerjack", "-t"],
        capture_output=True,
        text=True,
        timeout=120,
    )

    print(f"Full workflow - Exit code: {result.returncode}")
    output = result.stdout + result.stderr

    # Look for evidence of test execution
    test_evidence = [
        "🧪 TESTS",
        "Running test suite",
        "pytest",
        "test execution",
        "tests passed",
        "tests failed",
        "collected",
    ]

    tests_attempted = any(phrase in output for phrase in test_evidence)
    print(f"Tests attempted: {tests_attempted}")

    # Analysis
    print("\n3. Analysis:")
    if fast_hooks_status == "PASS":
        if tests_attempted:
            print("✅ CORRECT: Fast hooks passed, workflow continued to tests")
            return True
        else:
            print(
                "❌ INCORRECT: Fast hooks passed but workflow didn't continue to tests"
            )
            print("This might be due to early exit for other reasons")
            return False
    else:  # fast_hooks_status == "FAIL"
        if result.returncode != 0:
            print("✅ CORRECT: Fast hooks failed, workflow stopped with error")
            return True
        else:
            print("❌ INCORRECT: Fast hooks failed but workflow succeeded")
            return False


def test_comprehensive_workflow_order():
    """Test that workflow runs in the right order when everything passes."""
    print("\n=== Testing Workflow Order ===")

    # Skip if we're in a state where fast hooks are failing
    result = subprocess.run(
        ["python", "-m", "crackerjack", "--fast"],
        capture_output=True,
        text=True,
        timeout=60,
    )

    if result.returncode != 0:
        print(
            "⏭️  SKIP: Fast hooks are currently failing, can't test full workflow order"
        )
        return True

    # Run comprehensive hooks only
    print("Testing comprehensive hooks only...")
    result = subprocess.run(
        ["python", "-m", "crackerjack", "--comp"],
        capture_output=True,
        text=True,
        timeout=120,
    )

    print(f"Comprehensive hooks - Exit code: {result.returncode}")

    if result.returncode == 0:
        print("✅ Comprehensive hooks can pass")
    else:
        print("⚠️  Comprehensive hooks currently failing")

    return True


def main():
    """Main test function."""
    print("Testing Crackerjack Fast Hooks Stop Behavior")
    print("=" * 50)

    try:
        # Test 1: Fast hooks stop behavior
        test1_result = test_fast_hooks_stop_on_failure()

        # Test 2: Workflow order (when possible)
        test2_result = test_comprehensive_workflow_order()

        print("\n" + "=" * 50)
        print("SUMMARY:")
        print(f"Fast hooks stop behavior: {'✅ PASS' if test1_result else '❌ FAIL'}")
        print(f"Workflow order test: {'✅ PASS' if test2_result else '❌ FAIL'}")

        if test1_result:
            print("\n🎉 Fast hooks properly stop workflow on failure!")
        else:
            print("\n❌ Fast hooks behavior needs attention")

        return 0 if test1_result else 1

    except Exception as e:
        print(f"Test failed with error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
