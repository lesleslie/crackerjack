import time
from pathlib import Path
from unittest.mock import Mock

import pytest
from rich.console import Console

from crackerjack.orchestration.test_progress_streamer import (
    PytestOutputParser,
    TestProgress,
    TestProgressStreamer,
    TestSuiteProgress,
)


class TestTestProgress:
    def test_test_progress_creation(self):
        progress = TestProgress(
            test_id="tests / test_file.py:: TestClass:: test_method",
            test_file="test_file.py",
            test_class="TestClass",
            test_method="test_method",
            status="pending",
            start_time=time.time(),
        )

        assert progress.test_id == "tests / test_file.py:: TestClass:: test_method"
        assert progress.test_file == "test_file.py"
        assert progress.test_class == "TestClass"
        assert progress.test_method == "test_method"
        assert progress.status == "pending"
        assert progress.output_lines == []
        assert progress.error_details == []

    def test_test_progress_to_dict(self):
        progress = TestProgress(
            test_id="tests / test_file.py:: test_method",
            test_file="test_file.py",
            test_method="test_method",
            status="passed",
            start_time=time.time(),
            end_time=time.time() + 1.5,
            errors_found=0,
            warnings_found=1,
        )

        data = progress.to_dict()

        assert data["test_id"] == "tests / test_file.py:: test_method"
        assert data["status"] == "passed"
        assert data["duration"] == pytest.approx(1.5, abs=0.1)
        assert data["errors_found"] == 0
        assert data["warnings_found"] == 1


class TestTestSuiteProgress:
    def test_suite_progress_metrics(self):
        suite = TestSuiteProgress(
            total_tests=10,
            completed_tests=6,
            passed_tests=4,
            failed_tests=2,
            skipped_tests=0,
        )

        assert suite.progress_percentage == 60.0
        assert suite.success_rate == pytest.approx(66.67, abs=0.1)

    def test_suite_progress_empty(self):
        suite = TestSuiteProgress()

        assert suite.progress_percentage == 0.0
        assert suite.success_rate == 0.0


class TestPytestOutputParser:
    def test_parse_test_collection(self):
        parser = PytestOutputParser()
        output_lines = ["test session starts", "collected 42 items"]

        result = parser.parse_pytest_output(output_lines)

        assert result["suite_progress"].total_tests == 42

    def test_parse_test_results(self):
        parser = PytestOutputParser()
        output_lines = [
            "tests / test_file.py:: test_method PASSED",
            "tests / test_other.py:: TestClass:: test_failing FAILED",
            "tests / test_skip.py:: test_skipped SKIPPED",
        ]

        result = parser.parse_pytest_output(output_lines)

        assert result["test_count"] == 3
        assert result["suite_progress"].passed_tests == 1
        assert result["suite_progress"].failed_tests == 1
        assert result["suite_progress"].skipped_tests == 1

    def test_parse_coverage_info(self):
        parser = PytestOutputParser()
        output_lines = [
            "TOTAL 245 56 77 % ",
        ]

        result = parser.parse_pytest_output(output_lines)

        assert result["suite_progress"].coverage_percentage == 77.0


class TestTestProgressStreamer:
    def test_streamer_initialization(self):
        console = Console()
        pkg_path = Path("/test / path")

        streamer = TestProgressStreamer(console, pkg_path)

        assert streamer.console == console
        assert streamer.pkg_path == pkg_path
        assert isinstance(streamer.parser, PytestOutputParser)

    def test_progress_callback_setup(self):
        console = Console()
        pkg_path = Path("/test / path")
        streamer = TestProgressStreamer(console, pkg_path)

        progress_callback = Mock()
        test_callback = Mock()

        streamer.set_progress_callback(progress_callback)
        streamer.set_test_callback(test_callback)

        assert streamer.progress_callback == progress_callback
        assert streamer.test_callback == test_callback

    def test_build_pytest_command_basic(self):
        console = Console()
        pkg_path = Path("/test / path")
        streamer = TestProgressStreamer(console, pkg_path)

        options = Mock()
        options.coverage = False

        options.test_timeout = 300
        options.test_workers = 1

        cmd = streamer.build_pytest_command(options, "full_suite")

        assert cmd[0:3] == ["uv", "run", "pytest"]
        assert " - v" in cmd
        assert " -- tb = short" in cmd
        assert " - q" in cmd

    def test_build_pytest_command_with_coverage(self):
        console = Console()
        pkg_path = Path("/test / path")
        streamer = TestProgressStreamer(console, pkg_path)

        options = Mock()
        options.coverage = True

        options.test_timeout = 300
        options.test_workers = 1

        cmd = streamer.build_pytest_command(options, "full_suite")

        assert " -- cov = crackerjack" in cmd
        assert " -- cov - report = term - missing" in cmd

    def test_build_pytest_command_individual(self):
        console = Console()
        pkg_path = Path("/test / path")
        streamer = TestProgressStreamer(console, pkg_path)

        options = Mock()
        options.coverage = False

        options.test_timeout = 300
        options.test_workers = 1

        cmd = streamer.build_pytest_command(options, "individual_with_progress")

        assert " - x" in cmd
        assert " -- no - header" in cmd
