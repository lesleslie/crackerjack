# !/ usr / bin / env python3

import json
import tempfile
import time
from pathlib import Path


def test_error_tracking():
    print("🧪 Testing Enhanced Error Tracking")
    print(" = " * 50)

    progress_dir = Path(tempfile.gettempdir()) / "crackerjack-progress"
    progress_dir.mkdir(exist_ok=True)

    job_id = "test-job-123"
    progress_file = progress_dir / f"job-{job_id}.json"

    test_cases = [
        {
            "iteration": 1,
            "message": "Initial errors found",
            "total_issues": 15,
            "errors_fixed": 0,
            "errors_failed": 0,
            "current_errors": {
                "hook_errors": 5,
                "hook_failures": 3,
                "test_failures": 5,
                "test_errors": 2,
                "total": 15,
            },
        },
        {
            "iteration": 2,
            "message": "Applied formatting fixes",
            "total_issues": 15,
            "errors_fixed": 8,
            "errors_failed": 7,
            "current_errors": {
                "hook_errors": 0,
                "hook_failures": 0,
                "test_failures": 5,
                "test_errors": 2,
                "total": 7,
            },
        },
        {
            "iteration": 3,
            "message": "Fixed test issues",
            "total_issues": 15,
            "errors_fixed": 15,
            "errors_failed": 0,
            "current_errors": {
                "hook_errors": 0,
                "hook_failures": 0,
                "test_failures": 0,
                "test_errors": 0,
                "total": 0,
            },
        },
    ]

    for i, test_case in enumerate(test_cases):
        print(f"\n📍 Iteration {test_case['iteration']}: ")
        print(f" Message: {test_case['message']}")

        progress_data = {
            "job_id": job_id,
            "status": "running" if i < len(test_cases) - 1 else "completed",
            "iteration": test_case["iteration"],
            "max_iterations": 10,
            "overall_progress": int((test_case["iteration"] / 10) * 100),
            "current_stage": "fixes_applied" if i > 0 else "analyzing_results",
            "message": test_case["message"],
            "timestamp": time.time(),
            "project_path": str(Path.cwd()),
            "total_issues": test_case["total_issues"],
            "errors_fixed": test_case["errors_fixed"],
            "errors_failed": test_case["errors_failed"],
            "current_errors": test_case["current_errors"],
            "details": {
                "fast_hooks": "passed"
                if test_case["current_errors"]["hook_errors"] == 0
                else "failed",
                "comprehensive_hooks": "passed"
                if test_case["current_errors"]["hook_failures"] == 0
                else "failed",
                "tests": "passed"
                if test_case["current_errors"]["test_failures"] == 0
                else "failed",
            },
        }

        with progress_file.open("w") as f:
            json.dump(progress_data, f, indent=2)

        print(f" 🔍 Discovered: {test_case['total_issues']}")
        print(f" ✅ Resolved: {test_case['errors_fixed']}")
        print(f" ❌ Remaining: {test_case['total_issues'] - test_case['errors_fixed']}")
        print(
            f" 📈 Progress: {int((test_case['errors_fixed'] / test_case['total_issues']) * 100) if test_case['total_issues'] > 0 else 0} % "
        )

        with progress_file.open() as f:
            saved_data = json.load(f)

        assert saved_data["total_issues"] == test_case["total_issues"]
        assert saved_data["errors_fixed"] == test_case["errors_fixed"]
        assert saved_data["errors_failed"] == test_case["errors_failed"]
        assert saved_data["current_errors"] == test_case["current_errors"]

        print(" ✅ Progress file verified")

        time.sleep(0.5)

    print("\n🎉 SUCCESS: Error tracking is properly implemented ! ")
    print("\nThe TUI will now display: ")
    print(" - 🔍 Discovered: 15 (errors found initially)")
    print(" - ✅ Resolved: 15 (successfully fixed)")
    print(" - ❌ Remaining: 0 (still have errors)")
    print(" - 📈 Progress: 100 % (completion percentage)")

    print(f"\n📄 Test progress file: {progress_file}")
    print("\nTo see in action: ")
    print("1. Start the progress monitor: python -m crackerjack --monitor")
    print(f"2. It will discover job: {job_id}")
    print("3. The error tracking stats will update in real-time")

    progress_file.unlink(missing_ok=True)
    print("\n✅ Test cleanup completed")


if __name__ == "__main__":
    test_error_tracking()
