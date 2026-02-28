
from __future__ import annotations

import os
import re
import subprocess
import sys
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any


try:
    import testmon  # type: ignore
    TESTMON_AVAILABLE = True
except ImportError:
    TESTMON_AVAILABLE = False


class TestSelectionStrategy(str, Enum):
    __test__ = False


    ALL = "all"
    CHANGED = "changed"
    RELATED = "related"
    FAST = "fast"


@dataclass
class TestSelectionResult:
    __test__ = False


    strategy: TestSelectionStrategy
    total_tests: int = 0
    selected_tests: int = 0
    skipped_tests: int = 0
    selection_time_seconds: float = 0.0
    estimated_savings_seconds: float = 0.0
    affected_files: list[str] = field(default_factory=list)
    changed_tests: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def reduction_percentage(self) -> float:
        if self.total_tests == 0:
            return 0.0
        return (self.skipped_tests / self.total_tests) * 100

    @property
    def efficiency_ratio(self) -> float:
        if self.total_tests == 0:
            return 0.0
        return (self.skipped_tests / self.total_tests)


@dataclass
class TestMetrics:
    __test__ = False


    total_tests: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    duration_seconds: float = 0.0
    collection_time_seconds: float = 0.0
    selection_time_seconds: float = 0.0

    @property
    def success_rate(self) -> float:
        if self.total_tests == 0:
            return 0.0
        return (self.passed / self.total_tests) * 100


class TestSelector:
    __test__ = False


    def __init__(
        self,
        testmon_data_file: str = ".testmondata",
        project_root: str | None = None,
    ):
        self.testmon_data_file = testmon_data_file
        self.project_root = Path(project_root) if project_root else Path.cwd()

    def detect_changed_files(
        self, since_commit: str | None = None
    ) -> set[str]:
        with suppress((subprocess.SubprocessError, FileNotFoundError)):

            if since_commit:
                result = subprocess.run(
                    ["git", "diff", "--name-only", f"{since_commit}^..HEAD"],
                    capture_output=True,
                    text=True,
                    cwd=self.project_root,
                    check=False,
                )
            else:

                result = subprocess.run(
                    ["git", "diff", "--name-only", "HEAD~1", "HEAD"],
                    capture_output=True,
                    text=True,
                    cwd=self.project_root,
                    check=False,
                )

            if result.returncode == 0:
                changed = result.stdout.strip().split("\n")
                return {f for f in changed if f}


        return set()

    def select_tests_by_changes(
        self,
        test_files: list[Path],
        changed_files: set[str],
        strategy: TestSelectionStrategy = TestSelectionStrategy.CHANGED,
    ) -> TestSelectionResult:
        started = datetime.now(UTC)

        if not TESTMON_AVAILABLE:

            return TestSelectionResult(
                strategy=TestSelectionStrategy.ALL,
                total_tests=len(test_files),
                selected_tests=len(test_files),
                skipped_tests=0,
                selection_time_seconds=(datetime.now(UTC) - started).total_seconds(),
                changed_tests=[str(f) for f in test_files],
            )


        test_mapping = self._parse_testmon_data()


        if strategy == TestSelectionStrategy.ALL:
            selected = test_files.copy()
        elif strategy == TestSelectionStrategy.CHANGED:
            selected = self._select_changed_tests(test_files, changed_files, test_mapping)
        elif strategy == TestSelectionStrategy.RELATED:
            selected = self._select_related_tests(test_files, changed_files, test_mapping)
        elif strategy == TestSelectionStrategy.FAST:
            selected = self._select_fast_tests(test_files, test_mapping)
        else:
            selected = test_files.copy()

        selection_time = (datetime.now(UTC) - started).total_seconds()

        return TestSelectionResult(
            strategy=strategy,
            total_tests=len(test_files),
            selected_tests=len(selected),
            skipped_tests=len(test_files) - len(selected),
            selection_time_seconds=selection_time,
            affected_files=list(changed_files),
            changed_tests=[str(f) for f in selected],
            metadata={
                "testmon_available": True,
                "test_mapping_size": len(test_mapping),
            },
        )

    def _parse_testmon_data(self) -> dict[str, set[str]]:
        testmon_file = self.project_root / self.testmon_data_file

        if not testmon_file.exists():
            return {}


        return {}

    def _select_changed_tests(
        self,
        test_files: list[Path],
        changed_files: set[str],
        test_mapping: dict[str, set[str]],
    ) -> list[Path]:
        selected = []

        for test_file in test_files:
            test_path = str(test_file)


            if test_path in changed_files:
                selected.append(test_file)
                continue


            if test_mapping:
                for source_file in test_mapping.get(test_path, []):
                    if source_file in changed_files:
                        selected.append(test_file)
                        break

        return selected

    def _select_related_tests(
        self,
        test_files: list[Path],
        changed_files: set[str],
        test_mapping: dict[str, set[str]],
    ) -> list[Path]:

        changed_tests = set(self._select_changed_tests(test_files, changed_files, test_mapping))

        related: set[Path] = set()

        for test_file in changed_tests:

            for source_file in test_mapping.get(str(test_file), []):
                source_tests: set[str] | list[str] = test_mapping.get(source_file, [])
                for source_test in source_tests:
                    if isinstance(source_test, Path):
                        related.add(source_test)
                    else:
                        related.add(Path(source_test))

        return list(changed_tests | related)

    def _select_fast_tests(
        self,
        test_files: list[Path],
        test_mapping: dict[str, set[str]],
    ) -> list[Path]:

        fast_tests = []

        for test_file in test_files:
            test_path = str(test_file).lower()
            if "fast" in test_path:
                fast_tests.append(test_file)


        return fast_tests or test_files.copy()

    def run_pytest_with_selection(
        self,
        test_args: list[str],
        strategy: TestSelectionStrategy = TestSelectionStrategy.CHANGED,
        output_file: str | None = None,
    ) -> TestMetrics:
        started = datetime.now(UTC)


        cmd = ["python", "-m", "pytest"]


        if TESTMON_AVAILABLE:
            cmd.extend(["--testmon", "--testmon-datafile", self.testmon_data_file])


        cmd.extend(test_args)


        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=self.project_root,
            )


            metrics = self._parse_pytest_output(result.stdout, result.returncode)

        except subprocess.SubprocessError:
            metrics = TestMetrics(
                total_tests=0,
                passed=0,
                failed=0,
                duration_seconds=0.0,
            )

        selection_time = (datetime.now(UTC) - started).total_seconds()


        metrics.selection_time_seconds = selection_time

        return metrics

    def _parse_pytest_output(self, output: str, returncode: int) -> TestMetrics:
        # Try full pattern with all components first
        full_pattern = r"(\d+) passed, (\d+) failed, (\d+) skipped.*?in ([\d.]+) seconds?"
        match = re.search(full_pattern, output)
        if match:
            return TestMetrics(
                total_tests=int(match.group(1)) + int(match.group(2)) + int(match.group(3)),
                passed=int(match.group(1)),
                failed=int(match.group(2)),
                skipped=int(match.group(3)),
                duration_seconds=float(match.group(4)),
            )

        # Try pattern with passed and failed only
        passed_failed_pattern = r"(\d+) passed, (\d+) failed.*?in ([\d.]+) seconds?"
        match = re.search(passed_failed_pattern, output)
        if match:
            return TestMetrics(
                total_tests=int(match.group(1)) + int(match.group(2)),
                passed=int(match.group(1)),
                failed=int(match.group(2)),
                skipped=0,
                duration_seconds=float(match.group(3)),
            )

        # Try pattern with passed only
        passed_only_pattern = r"(\d+) passed.*?in ([\d.]+) seconds?"
        match = re.search(passed_only_pattern, output)
        if match:
            return TestMetrics(
                total_tests=int(match.group(1)),
                passed=int(match.group(1)),
                failed=0,
                skipped=0,
                duration_seconds=float(match.group(2)),
            )

        # Fallback for unrecognized output
        lines = output.count("\n")
        return TestMetrics(
            total_tests=max(0, lines - 5),
            passed=1 if returncode == 0 else 0,
            failed=1 if returncode != 0 else 0,
            skipped=0,
            duration_seconds=0.0,
        )

    def generate_selection_report(
        self,
        result: TestSelectionResult,
        output_file: str | None = None,
    ) -> str:
        lines = [
            "=" * 70,
            "Crackerjack Test Selection Report",
            "=" * 70,
            f"Strategy: {result.strategy.value}",
            f"Total Tests: {result.total_tests}",
            f"Selected: {result.selected_tests}",
            f"Skipped: {result.skipped_tests}",
            f"Reduction: {result.reduction_percentage:.1f}%",
            f"Selection Time: {result.selection_time_seconds:.2f}s",
            f"Est. Time Saved: {result.estimated_savings_seconds:.1f}s",
            "",
            f"Affected Files: {len(result.affected_files)}",
        ]

        for file in result.affected_files[:10]:
            lines.append(f"  - {file}")

        if len(result.affected_files) > 10:
            lines.append(f"  ... and {len(result.affected_files) - 10} more")

        lines.extend([
            "",
            f"Changed Tests: {len(result.changed_tests)}",
        ])

        for test in result.changed_tests[:10]:
            lines.append(f"  - {test}")

        if len(result.changed_tests) > 10:
            lines.append(f"  ... and {len(result.changed_tests) - 10} more")

        lines.append("=" * 70)

        report = "\n".join(lines)

        if output_file:
            output_path = self.project_root / output_file
            output_path.write_text(report)
            print(f"Report written to {output_path}")

        return report


def get_test_selector(
    testmon_data_file: str = ".testmondata",
    project_root: str | None = None,
) -> TestSelector:
    return TestSelector(
        testmon_data_file=testmon_data_file,
        project_root=project_root,
    )


def get_test_strategy_from_env() -> TestSelectionStrategy:
    strategy_str = os.getenv("CRACKERJACK_TEST_STRATEGY", "changed").lower()

    try:
        return TestSelectionStrategy(strategy_str)
    except ValueError:
        return TestSelectionStrategy.CHANGED


def install_testmon() -> bool:
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "pytest-testmon"],
            check=True,
            capture_output=True,
        )
        return True
    except subprocess.CalledProcessError:
        return False


def run_smart_tests(
    test_args: list[str] | None = None,
    strategy: TestSelectionStrategy | None = None,
) -> TestMetrics:

    if strategy is None:
        strategy = get_test_strategy_from_env()


    selector = get_test_selector()


    test_args = test_args or []
    return selector.run_pytest_with_selection(test_args, strategy)


def select_tests_for_ci(
    strategy: TestSelectionStrategy = TestSelectionStrategy.CHANGED,
    output_file: str = "test_selection_report.txt",
) -> TestSelectionResult:
    selector = get_test_selector()


    changed_files = selector.detect_changed_files()


    test_files = list(Path().rglob("test_*.py"))
    test_files.extend(Path().rglob("tests/test_*.py"))


    result = selector.select_tests_by_changes(test_files, changed_files, strategy)


    selector.generate_selection_report(result, output_file)

    return result
