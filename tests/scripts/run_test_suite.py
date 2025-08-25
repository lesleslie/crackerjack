#!/usr/bin/env python3
"""Comprehensive test runner for the crackerjack test harness.

This script provides multiple test execution modes optimized for different
scenarios: development, CI/CD, coverage analysis, and performance benchmarking.
"""

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path


class TestRunner:
    """Comprehensive test runner with multiple execution modes."""

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root
        self.tests_dir = project_root / "tests"

    def run_fast_tests(self, verbose: bool = False) -> int:
        """Run fast unit tests only."""
        cmd = [
            "python",
            "-m",
            "pytest",
            "tests/unit/",
            "-m",
            "not slow and not benchmark",
            "--tb=short",
            "-q" if not verbose else "-v",
        ]

        return self._execute_pytest(cmd, "Fast Unit Tests")

    def run_comprehensive_tests(self, verbose: bool = False) -> int:
        """Run all tests including integration and slow tests."""
        cmd = [
            "python",
            "-m",
            "pytest",
            "tests/",
            "-m",
            "not benchmark",
            "--tb=short",
            "-v" if verbose else "-q",
            "--cov=crackerjack",
            "--cov-report=term-missing:skip-covered",
            "--cov-report=html:htmlcov",
            "--cov-fail-under=42",
        ]

        return self._execute_pytest(cmd, "Comprehensive Test Suite")

    def run_coverage_focused(self, target_coverage: int = 42) -> int:
        """Run tests with focus on achieving target coverage."""
        cmd = [
            "python",
            "-m",
            "pytest",
            "tests/unit/",
            "tests/integration/",
            "--cov=crackerjack",
            "--cov-report=term-missing",
            "--cov-report=html:htmlcov",
            "--cov-report=json",
            f"--cov-fail-under={target_coverage}",
            "-v",
        ]

        return self._execute_pytest(
            cmd,
            f"Coverage-Focused Tests (Target: {target_coverage}%)",
        )

    def run_performance_tests(self) -> int:
        """Run performance benchmark tests."""
        cmd = [
            "python",
            "-m",
            "pytest",
            "tests/performance/",
            "--benchmark-only",
            "--benchmark-sort=mean",
            "-v",
        ]

        return self._execute_pytest(cmd, "Performance Benchmark Tests")

    def run_security_tests(self) -> int:
        """Run security validation tests."""
        cmd = ["python", "-m", "pytest", "tests/security/", "-m", "security", "-v"]

        return self._execute_pytest(cmd, "Security Validation Tests")

    def run_ci_tests(self, parallel: bool = True) -> int:
        """Run tests optimized for CI environment."""
        cmd = [
            "python",
            "-m",
            "pytest",
            "tests/",
            "-m",
            "not benchmark",
            "--tb=short",
            "-v",
            "--cov=crackerjack",
            "--cov-report=xml",  # For CI reporting
            "--cov-report=term",
            "--cov-fail-under=42",
            "--timeout=300",  # 5 minute timeout per test
        ]

        if parallel and self._detect_ci_environment():
            cmd.extend(["-n", "auto"])  # Parallel execution

        return self._execute_pytest(cmd, "CI Test Suite")

    def run_specific_tests(self, test_paths: list[str], verbose: bool = False) -> int:
        """Run specific test files or directories."""
        cmd = ["python", "-m", "pytest", *test_paths, "-v" if verbose else "-q"]

        return self._execute_pytest(cmd, f"Specific Tests: {', '.join(test_paths)}")

    def run_failed_tests(self) -> int:
        """Re-run only the tests that failed in the last run."""
        cmd = [
            "python",
            "-m",
            "pytest",
            "--lf",  # Last failed
            "-v",
        ]

        return self._execute_pytest(cmd, "Re-running Failed Tests")

    def run_test_discovery(self) -> int:
        """Run test discovery to validate test structure."""
        cmd = ["python", "-m", "pytest", "--collect-only", "-q"]

        return self._execute_pytest(cmd, "Test Discovery")

    def generate_coverage_report(self) -> int:
        """Generate detailed coverage report."""
        # First run tests with coverage
        cmd = [
            "python",
            "-m",
            "pytest",
            "tests/",
            "-m",
            "not benchmark",
            "--cov=crackerjack",
            "--cov-report=html:htmlcov",
            "--cov-report=json",
            "--cov-report=xml",
            "-q",
        ]

        result = self._execute_pytest(cmd, "Coverage Analysis")

        if result == 0:
            pass

        return result

    def _execute_pytest(self, cmd: list[str], description: str) -> int:
        """Execute pytest command with timing and error handling."""
        start_time = time.time()

        try:
            result = subprocess.run(
                cmd,
                check=False,
                cwd=self.project_root,
                timeout=600,  # 10 minute timeout
            )

            time.time() - start_time

            if result.returncode == 0:
                pass
            else:
                pass

            return result.returncode

        except subprocess.TimeoutExpired:
            return 1

        except KeyboardInterrupt:
            return 130

        except Exception:
            return 1

    def _detect_ci_environment(self) -> bool:
        """Detect if running in CI environment."""
        ci_indicators = [
            "CI",
            "CONTINUOUS_INTEGRATION",
            "GITHUB_ACTIONS",
            "GITLAB_CI",
            "JENKINS_URL",
            "TRAVIS",
            "CIRCLECI",
            "BUILDKITE",
        ]
        return any(os.getenv(indicator) for indicator in ci_indicators)

    def print_test_summary(self) -> None:
        """Print summary of available test suites."""


def main():
    """Main entry point for test runner."""
    parser = argparse.ArgumentParser(
        description="Comprehensive test runner for crackerjack",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Test suite options
    parser.add_argument("--fast", action="store_true", help="Run fast unit tests only")
    parser.add_argument(
        "--comprehensive",
        action="store_true",
        help="Run full test suite",
    )
    parser.add_argument(
        "--coverage",
        action="store_true",
        help="Run coverage-focused tests",
    )
    parser.add_argument(
        "--coverage-report",
        action="store_true",
        help="Generate coverage reports",
    )
    parser.add_argument(
        "--performance",
        action="store_true",
        help="Run performance tests",
    )
    parser.add_argument("--security", action="store_true", help="Run security tests")
    parser.add_argument("--ci", action="store_true", help="Run CI-optimized tests")
    parser.add_argument("--failed", action="store_true", help="Re-run failed tests")
    parser.add_argument("--discover", action="store_true", help="Run test discovery")

    # Specific test options
    parser.add_argument("--tests", nargs="+", help="Run specific test paths")

    # Configuration options
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument(
        "--target",
        type=int,
        default=42,
        help="Coverage target percentage",
    )
    parser.add_argument(
        "--no-parallel",
        action="store_true",
        help="Disable parallel execution",
    )

    args = parser.parse_args()

    # Find project root (now located in tests/scripts/)
    current_dir = Path(__file__).parent.parent.parent
    if not (current_dir / "pyproject.toml").exists():
        return 1

    runner = TestRunner(current_dir)

    # If no specific test suite requested, show help
    test_modes = [
        args.fast,
        args.comprehensive,
        args.coverage,
        args.coverage_report,
        args.performance,
        args.security,
        args.ci,
        args.failed,
        args.discover,
        bool(args.tests),
    ]

    if not any(test_modes):
        runner.print_test_summary()
        return 0

    # Execute requested test suites
    exit_code = 0

    if args.fast:
        exit_code |= runner.run_fast_tests(args.verbose)

    if args.comprehensive:
        exit_code |= runner.run_comprehensive_tests(args.verbose)

    if args.coverage:
        exit_code |= runner.run_coverage_focused(args.target)

    if args.coverage_report:
        exit_code |= runner.generate_coverage_report()

    if args.performance:
        exit_code |= runner.run_performance_tests()

    if args.security:
        exit_code |= runner.run_security_tests()

    if args.ci:
        exit_code |= runner.run_ci_tests(not args.no_parallel)

    if args.failed:
        exit_code |= runner.run_failed_tests()

    if args.discover:
        exit_code |= runner.run_test_discovery()

    if args.tests:
        exit_code |= runner.run_specific_tests(args.tests, args.verbose)

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
