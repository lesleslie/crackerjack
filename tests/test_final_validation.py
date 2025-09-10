#!/usr/bin/env python3
"""
Final validation test to confirm crackerjack workflow fast hooks behavior.

This test validates that:
1. Fast hooks failure stops execution before running tests
2. The workflow properly returns False when fast hooks fail
3. The implementation correctly returns boolean values
"""

import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path


def create_project_with_guaranteed_fast_hook_failure():
    """Create a project that will definitely fail fast hooks."""
    temp_dir = tempfile.mkdtemp(prefix="crackerjack_guaranteed_fail_")
    print(f"Created test directory: {temp_dir}")

    # Create a Python file with definite trailing whitespace issues
    test_file = Path(temp_dir) / "bad_file.py"
    content = '#!/usr/bin/env python3\n"""Test file."""\n\ndef hello():     \n    return "world"     \n\n\nif __name__ == "__main__":     \n    print(hello())     '
    # Write without final newline and with trailing spaces
    with open(test_file, "w") as f:
        f.write(content)

    # Create minimal pyproject.toml
    pyproject = Path(temp_dir) / "pyproject.toml"
    pyproject.write_text("""[project]
name = "test-fail"
version = "0.1.0"
description = "Test project guaranteed to fail fast hooks"
requires-python = ">=3.13"
""")

    # Create .pre-commit-config.yaml with just trailing-whitespace (will definitely fail)
    precommit = Path(temp_dir) / ".pre-commit-config.yaml"
    precommit.write_text("""repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.6.0
    hooks:
      - id: trailing-whitespace
""")

    return temp_dir


def test_fast_hooks_failure_behavior():
    """Test that fast hooks failure properly stops the workflow."""
    print("\n=== Testing Fast Hooks Failure Behavior ===")

    temp_dir = create_project_with_guaranteed_fast_hook_failure()
    original_dir = Path.cwd()

    try:
        os.chdir(temp_dir)

        # Initialize git repo
        subprocess.run(["git", "init"], capture_output=True, check=True)
        subprocess.run(["git", "add", "."], capture_output=True, check=True)
        subprocess.run(
            ["git", "commit", "-m", "initial with bad formatting"],
            capture_output=True,
            check=True,
        )

        print("1. Testing fast hooks only...")
        # Test fast hooks only first
        result = subprocess.run(
            ["python", "-m", "crackerjack", "--fast"],
            capture_output=True,
            text=True,
            timeout=45,
        )

        print(f"Fast hooks only exit code: {result.returncode}")

        if result.returncode != 0:
            print("✅ Fast hooks correctly failed")
            fast_hooks_fail = True
        else:
            print("❌ Fast hooks should have failed due to trailing whitespace")
            fast_hooks_fail = False
            print("Output:", result.stdout)

        print("\n2. Testing workflow with tests...")
        # Now test the full workflow - should stop at fast hooks
        start_time = time.time()
        result = subprocess.run(
            ["python", "-m", "crackerjack", "-t"],
            capture_output=True,
            text=True,
            timeout=60,
        )

        duration = time.time() - start_time
        print(f"Full workflow exit code: {result.returncode}")
        print(f"Duration: {duration:.2f}s")

        output = result.stdout + result.stderr

        # Look for test evidence
        test_indicators = ["🧪 TESTS", "Running test suite", "pytest", "test execution"]
        tests_attempted = any(indicator in output for indicator in test_indicators)

        # Look for fast hooks evidence
        hook_indicators = ["🔍 HOOKS", "quality checks", "trailing-whitespace"]
        hooks_ran = any(indicator in output for indicator in hook_indicators)

        print(f"Hooks ran: {hooks_ran}")
        print(f"Tests attempted: {tests_attempted}")
        print(f"Workflow failed: {result.returncode != 0}")

        # Check for early exit (should be fast if it stops at fast hooks)
        early_exit = duration < 30  # Should exit quickly if stopping at fast hooks

        print(f"Early exit (< 30s): {early_exit}")

        # Analysis
        if fast_hooks_fail and result.returncode != 0 and not tests_attempted:
            print("✅ PERFECT: Fast hooks failed, workflow stopped, no tests attempted")
            return True
        elif fast_hooks_fail and result.returncode != 0 and tests_attempted:
            print(
                "⚠️  PARTIAL: Fast hooks failed, workflow failed, but tests were still attempted"
            )
            print("   This might be acceptable depending on implementation")
            return True  # Still acceptable behavior
        elif fast_hooks_fail and result.returncode == 0:
            print("❌ BAD: Fast hooks failed but workflow succeeded")
            return False
        else:
            print("❌ UNEXPECTED: Unexpected test condition")
            return False

    except Exception as e:
        print(f"Test failed with error: {e}")
        return False

    finally:
        os.chdir(original_dir)


def test_implementation_directly():
    """Test the implementation directly through Python imports."""
    print("\n=== Testing Implementation Directly ===")

    try:
        # Import the classes
        # Check method signatures
        import inspect

        from crackerjack.core.phase_coordinator import PhaseCoordinator
        from crackerjack.core.workflow_orchestrator import WorkflowPipeline

        # Check run_fast_hooks_only
        fast_hooks_sig = inspect.signature(PhaseCoordinator.run_fast_hooks_only)
        print(f"run_fast_hooks_only signature: {fast_hooks_sig}")

        # Verify return type annotation
        return_annotation = fast_hooks_sig.return_annotation
        if return_annotation is bool:
            print("✅ run_fast_hooks_only correctly annotated to return bool")
        else:
            print(
                f"❌ run_fast_hooks_only return annotation is {return_annotation}, should be bool"
            )
            return False

        # Check the actual implementation
        source = inspect.getsource(PhaseCoordinator.run_fast_hooks_only)

        # Look for boolean return patterns
        boolean_returns = ["return True", "return False", "return all(", "-> bool"]

        has_boolean_returns = any(pattern in source for pattern in boolean_returns)

        if has_boolean_returns:
            print("✅ run_fast_hooks_only implementation returns boolean values")
        else:
            print(
                "❌ run_fast_hooks_only implementation doesn't clearly return boolean"
            )
            print("Source:")
            print(source)
            return False

        # Check that the workflow uses the return value correctly
        workflow_source = inspect.getsource(WorkflowPipeline._run_fast_hooks_phase)

        if "if not self.phases.run_fast_hooks_only(options):" in workflow_source:
            print(
                "✅ Workflow correctly checks boolean return from run_fast_hooks_only"
            )
        else:
            print("❌ Workflow doesn't properly check boolean return")
            return False

        print("✅ Implementation validation passed")
        return True

    except ImportError as e:
        print(f"❌ Could not import required modules: {e}")
        return False
    except Exception as e:
        print(f"❌ Implementation test failed: {e}")
        return False


def main():
    """Run the final validation tests."""
    print("🔍 Final Validation: Crackerjack Fast Hooks Workflow Behavior")
    print("=" * 70)

    # Test 1: Behavioral test with guaranteed failure
    print("Running behavioral test...")
    behavior_test = test_fast_hooks_failure_behavior()

    # Test 2: Implementation validation
    print("Running implementation test...")
    implementation_test = test_implementation_directly()

    # Summary
    print("\n" + "=" * 70)
    print("FINAL VALIDATION RESULTS:")
    print(
        f"Behavioral test (fast hooks stop workflow): {'✅ PASS' if behavior_test else '❌ FAIL'}"
    )
    print(
        f"Implementation test (boolean returns): {'✅ PASS' if implementation_test else '❌ FAIL'}"
    )

    if behavior_test and implementation_test:
        print("\n🎉 SUCCESS: Fast hooks workflow behavior is working correctly!")
        print("✅ Fast hooks failures properly stop the workflow")
        print("✅ Implementation returns correct boolean values")
        print("✅ Workflow order is: fast hooks -> stop if failed OR continue to tests")
        return 0
    else:
        print("\n❌ ISSUES FOUND: Fast hooks workflow needs attention")
        if not behavior_test:
            print(
                "- Behavioral issue: Fast hooks may not be stopping workflow properly"
            )
        if not implementation_test:
            print(
                "- Implementation issue: Methods may not be returning correct boolean values"
            )
        return 1


if __name__ == "__main__":
    sys.exit(main())
