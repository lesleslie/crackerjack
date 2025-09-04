"""Test runner utilities with coverage reporting and quality metrics.

Provides utilities for:
- Running test suites with coverage
- Generating quality reports
- Performance profiling
- Test result analysis
"""

import json
import statistics
import subprocess
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import Any


class TestRunner:
    """Enhanced test runner with coverage and quality metrics."""

    def __init__(self, project_root: Path) -> None:
        self.project_root = Path(project_root)
        self.test_dir = self.project_root / "tests"
        self.coverage_dir = self.project_root / "htmlcov"
        self.reports_dir = self.project_root / "test_reports"
        self.reports_dir.mkdir(exist_ok=True)

    def run_all_tests(
        self,
        coverage: bool = True,
        parallel: bool = True,
        verbose: bool = True,
    ) -> dict[str, Any]:
        """Run all test suites with comprehensive reporting."""
        start_time = time.time()

        results = {
            "timestamp": datetime.now().isoformat(),
            "test_results": {},
            "coverage": {},
            "quality_metrics": {},
            "execution_time": 0,
            "summary": {},
        }

        try:
            # Run unit tests
            results["test_results"]["unit"] = self.run_test_suite(
                "unit",
                coverage=coverage,
                parallel=parallel,
                verbose=verbose,
            )

            # Run integration tests
            results["test_results"]["integration"] = self.run_test_suite(
                "integration",
                coverage=coverage,
                parallel=parallel,
                verbose=verbose,
            )

            # Run performance tests
            results["test_results"]["performance"] = self.run_test_suite(
                "performance",
                coverage=coverage,
                parallel=False,
                verbose=verbose,
            )

            # Run security tests
            results["test_results"]["security"] = self.run_test_suite(
                "security",
                coverage=coverage,
                parallel=parallel,
                verbose=verbose,
            )

            # Generate coverage report if enabled
            if coverage:
                results["coverage"] = self.generate_coverage_report()

            # Calculate quality metrics
            results["quality_metrics"] = self.calculate_quality_metrics(results)

            # Generate summary
            results["summary"] = self.generate_test_summary(results)

        except Exception as e:
            results["error"] = str(e)

        results["execution_time"] = time.time() - start_time

        # Save results to file
        self.save_test_results(results)

        return results

    def run_test_suite(
        self,
        suite_name: str,
        coverage: bool = True,
        parallel: bool = True,
        verbose: bool = True,
    ) -> dict[str, Any]:
        """Run a specific test suite."""
        suite_path = self.test_dir / suite_name

        if not suite_path.exists():
            return {"error": f"Test suite not found: {suite_name}"}

        # Build pytest command
        cmd = ["pytest", str(suite_path)]

        if coverage:
            cmd.extend(["--cov=session_mgmt_mcp", "--cov-append"])

        if parallel:
            cmd.extend(["-n", "auto"])

        if verbose:
            cmd.extend(["-v"])

        # Add markers for specific suite
        cmd.extend(["-m", suite_name])

        # Add JUnit XML output
        junit_file = self.reports_dir / f"junit_{suite_name}.xml"
        cmd.extend(["--junitxml", str(junit_file)])

        # Add timeout
        cmd.extend(["--timeout=300"])

        try:
            start_time = time.time()
            result = subprocess.run(
                cmd,
                check=False,
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=600,  # 10 minute timeout
            )
            execution_time = time.time() - start_time

            # Parse JUnit XML for detailed results
            test_details = (
                self.parse_junit_xml(junit_file) if junit_file.exists() else {}
            )

            return {
                "suite": suite_name,
                "exit_code": result.returncode,
                "execution_time": execution_time,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "success": result.returncode == 0,
                "test_details": test_details,
            }

        except subprocess.TimeoutExpired:
            return {
                "suite": suite_name,
                "error": "Test suite timed out",
                "success": False,
                "execution_time": 600,
            }
        except Exception as e:
            return {
                "suite": suite_name,
                "error": str(e),
                "success": False,
                "execution_time": 0,
            }

    def parse_junit_xml(self, junit_file: Path) -> dict[str, Any]:
        """Parse JUnit XML file for test details."""
        try:
            tree = ET.parse(junit_file)
            root = tree.getroot()

            details = {
                "total_tests": int(root.get("tests", 0)),
                "failures": int(root.get("failures", 0)),
                "errors": int(root.get("errors", 0)),
                "skipped": int(root.get("skipped", 0)),
                "time": float(root.get("time", 0)),
                "test_cases": [],
            }

            # Parse individual test cases
            for testcase in root.findall(".//testcase"):
                test_info = {
                    "name": testcase.get("name"),
                    "classname": testcase.get("classname"),
                    "time": float(testcase.get("time", 0)),
                    "status": "passed",
                }

                # Check for failures or errors
                if testcase.find("failure") is not None:
                    test_info["status"] = "failed"
                    test_info["failure_message"] = testcase.find("failure").get(
                        "message",
                    )
                elif testcase.find("error") is not None:
                    test_info["status"] = "error"
                    test_info["error_message"] = testcase.find("error").get("message")
                elif testcase.find("skipped") is not None:
                    test_info["status"] = "skipped"
                    test_info["skip_reason"] = testcase.find("skipped").get("message")

                details["test_cases"].append(test_info)

            return details

        except Exception as e:
            return {"error": f"Failed to parse JUnit XML: {e}"}

    def generate_coverage_report(self) -> dict[str, Any]:
        """Generate comprehensive coverage report."""
        coverage_data = {}

        try:
            # Generate HTML coverage report
            subprocess.run(
                ["coverage", "html", "--directory", str(self.coverage_dir)],
                cwd=self.project_root,
                check=True,
            )

            # Generate XML coverage report
            coverage_xml = self.project_root / "coverage.xml"
            subprocess.run(
                ["coverage", "xml", "--output", str(coverage_xml)],
                cwd=self.project_root,
                check=True,
            )

            # Generate JSON coverage report
            coverage_json = self.project_root / "coverage.json"
            subprocess.run(
                ["coverage", "json", "--output", str(coverage_json)],
                cwd=self.project_root,
                check=True,
            )

            # Parse coverage data
            if coverage_json.exists():
                with open(coverage_json) as f:
                    coverage_data = json.load(f)

                # Extract summary metrics
                summary = coverage_data.get("totals", {})
                coverage_data["summary"] = {
                    "lines_covered": summary.get("covered_lines", 0),
                    "lines_total": summary.get("num_statements", 0),
                    "coverage_percent": summary.get("percent_covered", 0),
                    "branches_covered": summary.get("covered_branches", 0),
                    "branches_total": summary.get("num_branches", 0),
                    "branch_coverage_percent": summary.get(
                        "percent_covered_branches",
                        0,
                    ),
                }

                # File-level coverage details
                coverage_data["files"] = {}
                for filename, file_data in coverage_data.get("files", {}).items():
                    file_summary = file_data.get("summary", {})
                    coverage_data["files"][filename] = {
                        "coverage_percent": file_summary.get("percent_covered", 0),
                        "lines_covered": file_summary.get("covered_lines", 0),
                        "lines_total": file_summary.get("num_statements", 0),
                        "missing_lines": file_data.get("missing_lines", []),
                    }

        except Exception as e:
            coverage_data["error"] = f"Failed to generate coverage report: {e}"

        return coverage_data

    def calculate_quality_metrics(self, test_results: dict[str, Any]) -> dict[str, Any]:
        """Calculate comprehensive quality metrics."""
        metrics = {
            "test_quality": {},
            "code_quality": {},
            "performance_metrics": {},
            "overall_score": 0,
        }

        try:
            # Test quality metrics
            total_tests = 0
            passed_tests = 0
            failed_tests = 0
            execution_times = []

            for suite_results in test_results.get(
                "test_results",
                {},
            ).values():
                if "test_details" in suite_results:
                    details = suite_results["test_details"]
                    total_tests += details.get("total_tests", 0)
                    failed_tests += details.get("failures", 0) + details.get(
                        "errors",
                        0,
                    )
                    passed_tests += (
                        details.get("total_tests", 0)
                        - details.get("failures", 0)
                        - details.get("errors", 0)
                        - details.get("skipped", 0)
                    )

                    if "execution_time" in suite_results:
                        execution_times.append(suite_results["execution_time"])

            metrics["test_quality"] = {
                "total_tests": total_tests,
                "passed_tests": passed_tests,
                "failed_tests": failed_tests,
                "success_rate": (passed_tests / total_tests * 100)
                if total_tests > 0
                else 0,
                "average_execution_time": statistics.mean(execution_times)
                if execution_times
                else 0,
            }

            # Code coverage metrics
            coverage = test_results.get("coverage", {}).get("summary", {})
            metrics["code_quality"] = {
                "line_coverage": coverage.get("coverage_percent", 0),
                "branch_coverage": coverage.get("branch_coverage_percent", 0),
                "lines_covered": coverage.get("lines_covered", 0),
                "lines_total": coverage.get("lines_total", 0),
            }

            # Performance metrics
            performance_results = test_results.get("test_results", {}).get(
                "performance",
                {},
            )
            metrics["performance_metrics"] = {
                "performance_tests_passed": performance_results.get("success", False),
                "performance_execution_time": performance_results.get(
                    "execution_time",
                    0,
                ),
                "performance_issues": [],
            }

            # Calculate overall quality score
            score_components = {
                "test_success_rate": metrics["test_quality"]["success_rate"] * 0.3,
                "line_coverage": metrics["code_quality"]["line_coverage"] * 0.25,
                "branch_coverage": metrics["code_quality"]["branch_coverage"] * 0.15,
                "performance_score": (
                    100
                    if metrics["performance_metrics"]["performance_tests_passed"]
                    else 0
                )
                * 0.2,
                "security_score": (
                    100
                    if test_results.get("test_results", {})
                    .get("security", {})
                    .get("success", False)
                    else 0
                )
                * 0.1,
            }

            metrics["overall_score"] = sum(score_components.values())
            metrics["score_breakdown"] = score_components

        except Exception as e:
            metrics["error"] = f"Failed to calculate quality metrics: {e}"

        return metrics

    def generate_test_summary(self, results: dict[str, Any]) -> dict[str, Any]:
        """Generate comprehensive test summary."""
        summary = {
            "timestamp": results["timestamp"],
            "execution_time": results["execution_time"],
            "overall_status": "UNKNOWN",
            "test_suites": {},
            "coverage_summary": {},
            "quality_score": 0,
            "recommendations": [],
        }

        try:
            # Analyze test suite results
            all_suites_passed = True
            for suite_name, suite_results in results.get("test_results", {}).items():
                suite_summary = {
                    "status": "PASSED"
                    if suite_results.get("success", False)
                    else "FAILED",
                    "execution_time": suite_results.get("execution_time", 0),
                    "test_count": suite_results.get("test_details", {}).get(
                        "total_tests",
                        0,
                    ),
                    "failure_count": suite_results.get("test_details", {}).get(
                        "failures",
                        0,
                    )
                    + suite_results.get("test_details", {}).get("errors", 0),
                }

                summary["test_suites"][suite_name] = suite_summary

                if not suite_results.get("success", False):
                    all_suites_passed = False

            # Overall status
            summary["overall_status"] = "PASSED" if all_suites_passed else "FAILED"

            # Coverage summary
            coverage = results.get("coverage", {}).get("summary", {})
            summary["coverage_summary"] = {
                "line_coverage": coverage.get("coverage_percent", 0),
                "branch_coverage": coverage.get("branch_coverage_percent", 0),
                "coverage_target": 85.0,  # From pytest.ini
                "meets_target": coverage.get("coverage_percent", 0) >= 85.0,
            }

            # Quality score
            summary["quality_score"] = results.get("quality_metrics", {}).get(
                "overall_score",
                0,
            )

            # Generate recommendations
            summary["recommendations"] = self.generate_recommendations(results)

        except Exception as e:
            summary["error"] = f"Failed to generate summary: {e}"

        return summary

    def generate_recommendations(self, results: dict[str, Any]) -> list[str]:
        """Generate actionable recommendations based on test results."""
        recommendations = []

        try:
            # Coverage recommendations
            coverage = results.get("coverage", {}).get("summary", {})
            line_coverage = coverage.get("coverage_percent", 0)

            if line_coverage < 85:
                recommendations.append(
                    f"Increase line coverage from {line_coverage:.1f}% to at least 85%",
                )

            if coverage.get("branch_coverage_percent", 0) < 80:
                recommendations.append("Improve branch coverage to at least 80%")

            # Test failure recommendations
            for suite_name, suite_results in results.get("test_results", {}).items():
                if not suite_results.get("success", False):
                    failure_count = suite_results.get("test_details", {}).get(
                        "failures",
                        0,
                    )
                    error_count = suite_results.get("test_details", {}).get("errors", 0)

                    if failure_count > 0:
                        recommendations.append(
                            f"Fix {failure_count} failing tests in {suite_name} suite",
                        )

                    if error_count > 0:
                        recommendations.append(
                            f"Resolve {error_count} test errors in {suite_name} suite",
                        )

            # Performance recommendations
            performance_results = results.get("test_results", {}).get("performance", {})
            if not performance_results.get("success", False):
                recommendations.append("Review and fix performance test failures")

            # Security recommendations
            security_results = results.get("test_results", {}).get("security", {})
            if not security_results.get("success", False):
                recommendations.append("Address security test failures immediately")

            # Quality score recommendations
            quality_score = results.get("quality_metrics", {}).get("overall_score", 0)
            if quality_score < 80:
                recommendations.append(
                    f"Improve overall quality score from {quality_score:.1f} to at least 80",
                )

            # Execution time recommendations
            total_time = results.get("execution_time", 0)
            if total_time > 300:  # 5 minutes
                recommendations.append("Consider optimizing test execution time")

        except Exception as e:
            recommendations.append(f"Error generating recommendations: {e}")

        return recommendations

    def save_test_results(self, results: dict[str, Any]):
        """Save test results to file."""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            results_file = self.reports_dir / f"test_results_{timestamp}.json"

            with open(results_file, "w") as f:
                json.dump(results, f, indent=2, default=str)

            # Also save latest results
            latest_file = self.reports_dir / "latest_test_results.json"
            with open(latest_file, "w") as f:
                json.dump(results, f, indent=2, default=str)

        except Exception as e:
            print(f"Failed to save test results: {e}")

    def run_quick_tests(self) -> dict[str, Any]:
        """Run quick smoke tests for fast feedback."""
        return self.run_test_suite(
            "smoke",
            coverage=False,
            parallel=True,
            verbose=False,
        )

    def run_regression_tests(self) -> dict[str, Any]:
        """Run regression tests."""
        return self.run_test_suite(
            "regression",
            coverage=True,
            parallel=True,
            verbose=True,
        )


def run_test_harness():
    """Main entry point for test harness."""
    project_root = Path(__file__).parent.parent.parent
    runner = TestRunner(project_root)

    print("🚀 Starting comprehensive test harness...")
    print(f"Project root: {project_root}")
    print(f"Test directory: {runner.test_dir}")

    # Run all tests
    results = runner.run_all_tests()

    # Print summary
    summary = results.get("summary", {})
    print("\n📊 Test Results Summary")
    print("=" * 50)
    print(f"Overall Status: {summary.get('overall_status', 'UNKNOWN')}")
    print(f"Execution Time: {results.get('execution_time', 0):.2f}s")
    print(f"Quality Score: {summary.get('quality_score', 0):.1f}/100")

    # Coverage summary
    coverage = summary.get("coverage_summary", {})
    print("\n📈 Coverage Summary")
    print(f"Line Coverage: {coverage.get('line_coverage', 0):.1f}%")
    print(f"Branch Coverage: {coverage.get('branch_coverage', 0):.1f}%")
    print(f"Meets Target: {'✅' if coverage.get('meets_target', False) else '❌'}")

    # Test suites
    print("\n🧪 Test Suites")
    for suite_name, suite_summary in summary.get("test_suites", {}).items():
        status_emoji = "✅" if suite_summary["status"] == "PASSED" else "❌"
        print(
            f"{status_emoji} {suite_name}: {suite_summary['test_count']} tests, {suite_summary['execution_time']:.2f}s",
        )

    # Recommendations
    recommendations = summary.get("recommendations", [])
    if recommendations:
        print("\n💡 Recommendations")
        for i, rec in enumerate(recommendations, 1):
            print(f"{i}. {rec}")

    print(f"\n📋 Detailed results saved to: {runner.reports_dir}")

    return results


if __name__ == "__main__":
    run_test_harness()
