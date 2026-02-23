from __future__ import annotations

import asyncio
import json
import logging
import shutil
import typing as t
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from pydantic import Field

from crackerjack.adapters._tool_adapter_base import (
    BaseToolAdapter,
    ToolAdapterSettings,
    ToolExecutionResult,
    ToolIssue,
)
from crackerjack.adapters.benchmark.baseline import (
    BaselineManager,
    BenchmarkResult,
)
from crackerjack.models.adapter_metadata import AdapterStatus
from crackerjack.models.qa_results import QACheckType, QAResultStatus

if t.TYPE_CHECKING:
    from crackerjack.models.qa_config import QACheckConfig


MODULE_ID = UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890")
MODULE_STATUS = AdapterStatus.STABLE

logger = logging.getLogger(__name__)


class BenchmarkSettings(ToolAdapterSettings):
    tool_name: str = "pytest"
    use_json_output: bool = True

    regression_threshold: float = Field(
        default=0.15,
        ge=0.0,
        le=1.0,
        description="Fail if performance degrades by this fraction (0.15 = 15%)",
    )
    min_rounds: int = Field(
        default=5,
        ge=1,
        le=100,
        description="Minimum benchmark rounds for statistical validity",
    )
    max_time: float = Field(
        default=1.0,
        ge=0.1,
        le=30.0,
        description="Maximum seconds per benchmark",
    )

    baseline_file: str = Field(
        default=".benchmarks/baseline.json",
        description="Path to store baseline benchmarks",
    )
    update_baseline: bool = Field(
        default=False,
        description="Update baseline instead of comparing",
    )

    benchmark_filter: str | None = Field(
        default=None,
        description="Glob pattern to filter benchmarks (e.g., 'test_database*')",
    )

    compare_failures: bool = Field(
        default=True,
        description="Whether to fail on any regression",
    )


@dataclass
class BenchmarkIssue:
    name: str
    rule: str
    message: str
    severity: str
    details: dict[str, t.Any]

    def to_tool_issue(self) -> ToolIssue:
        return ToolIssue(
            file_path=Path("benchmark"),
            line_number=None,
            message=self.message,
            code=self.rule,
            severity=self.severity,
            suggestion=self._get_suggestion(),
        )

    def _get_suggestion(self) -> str | None:
        if self.rule == "BM001":
            return "Optimize code or update baseline if regression is expected"
        if self.rule == "BM003":
            return "Increase --benchmark-min-rounds for more accurate results"
        return None


class PytestBenchmarkAdapter(BaseToolAdapter):
    settings: BenchmarkSettings | None = None

    def __init__(self, settings: BenchmarkSettings | None = None) -> None:
        super().__init__(settings=settings)
        self._baseline_manager: BaselineManager | None = None
        logger.debug(
            "PytestBenchmarkAdapter initialized",
            extra={"has_settings": settings is not None},
        )

    async def init(self) -> None:
        if not self.settings:
            config_data = self._load_config_from_pyproject()
            self.settings = BenchmarkSettings(
                regression_threshold=config_data.get("regression_threshold", 0.15),
                min_rounds=config_data.get("min_rounds", 5),
                max_time=config_data.get("max_time", 1.0),
                baseline_file=config_data.get(
                    "baseline_file", ".benchmarks/baseline.json"
                ),
                timeout_seconds=300,
                max_workers=1,
            )
            logger.info(
                "Using default BenchmarkSettings",
                extra={
                    "regression_threshold": self.settings.regression_threshold,
                    "min_rounds": self.settings.min_rounds,
                },
            )

        await super().init()

        baseline_path = Path.cwd() / self.settings.baseline_file
        self._baseline_manager = BaselineManager(baseline_path)
        self._baseline_manager.load()

        logger.debug(
            "PytestBenchmarkAdapter initialization complete",
            extra={
                "baseline_path": str(baseline_path),
                "baseline_count": self._baseline_manager.baseline_count,
            },
        )

    @property
    def adapter_name(self) -> str:
        return "pytest-benchmark"

    @property
    def module_id(self) -> UUID:
        return MODULE_ID

    @property
    def tool_name(self) -> str:
        return "pytest"

    def build_command(
        self,
        files: list[Path],
        config: QACheckConfig | None = None,
    ) -> list[str]:
        if not self.settings:
            msg = "Settings not initialized"
            raise RuntimeError(msg)

        cmd = [
            self.tool_name,
            "-v",
            "--benchmark-only",
            "--benchmark-json=-",
            f"--benchmark-min-rounds={self.settings.min_rounds}",
            f"--benchmark-max-time={self.settings.max_time}",
        ]

        if self.settings.benchmark_filter:
            cmd.extend(["-k", self.settings.benchmark_filter])

        cmd.extend([str(f) for f in files])

        logger.info(
            "Built pytest-benchmark command",
            extra={
                "file_count": len(files),
                "min_rounds": self.settings.min_rounds,
                "max_time": self.settings.max_time,
            },
        )
        return cmd

    async def parse_output(
        self,
        result: ToolExecutionResult,
    ) -> list[ToolIssue]:
        if not result.raw_output:
            logger.debug("No benchmark output to parse")
            return []

        try:
            benchmark_data = json.loads(result.raw_output)
        except json.JSONDecodeError as e:
            logger.warning(
                "Failed to parse benchmark JSON output",
                extra={"error": str(e), "output_preview": result.raw_output[:200]},
            )
            return [
                ToolIssue(
                    file_path=Path("benchmark"),
                    message=f"Failed to parse benchmark output: {e}",
                    code="BM002",
                    severity="error",
                ),
            ]

        benchmarks = benchmark_data.get("benchmarks", [])
        if not benchmarks:
            logger.debug("No benchmarks found in output")
            return []

        issues: list[ToolIssue] = []

        for bench in benchmarks:
            bench_issues = self._process_benchmark(bench)
            issues.extend(bench_issues)

        logger.info(
            "Parsed benchmark output",
            extra={
                "total_benchmarks": len(benchmarks),
                "issues_found": len(issues),
            },
        )
        return issues

    def _process_benchmark(self, bench: dict[str, t.Any]) -> list[ToolIssue]:
        issues: list[ToolIssue] = []
        name = bench.get("name", "unknown")

        if not self.settings or not self._baseline_manager:
            return issues

        current = BenchmarkResult.from_pytest_benchmark(bench)

        if current.rounds < self.settings.min_rounds:
            issues.append(
                BenchmarkIssue(
                    name=name,
                    rule="BM003",
                    message=f"Benchmark '{name}' ran only {current.rounds} rounds (min: {self.settings.min_rounds})",
                    severity="warning",
                    details={
                        "rounds": current.rounds,
                        "min_rounds": self.settings.min_rounds,
                    },
                ).to_tool_issue()
            )

        if self.settings.update_baseline:
            self._baseline_manager.update(name, current)
            logger.debug(
                "Updated baseline",
                extra={"name": name, "median": current.median},
            )
            return issues

        check = self._baseline_manager.compare(
            name,
            current,
            self.settings.regression_threshold,
        )

        if check.is_regression:
            baseline_median = check.baseline.median if check.baseline else 0
            issues.append(
                BenchmarkIssue(
                    name=name,
                    rule="BM001",
                    message=(
                        f"Performance regression in '{name}': "
                        f"{check.change_percent:+.1f}% slower "
                        f"(median: {current.median * 1000:.3f}ms vs {baseline_median * 1000:.3f}ms)"
                    ),
                    severity="error" if self.settings.compare_failures else "warning",
                    details={
                        "change_percent": check.change_percent,
                        "current_median": current.median,
                        "baseline_median": baseline_median,
                    },
                ).to_tool_issue()
            )

        return issues

    async def check(
        self,
        files: list[Path] | None = None,
        config: QACheckConfig | None = None,
    ) -> t.Any:
        result = await super().check(files, config)

        if (
            self.settings
            and self._baseline_manager
            and self.settings.update_baseline
            and result.status != QAResultStatus.ERROR
        ):
            self._baseline_manager.save()
            logger.info(
                "Saved updated baselines",
                extra={"path": self.settings.baseline_file},
            )

        return result

    def _get_check_type(self) -> QACheckType:
        return QACheckType.BENCHMARK

    def get_default_config(self) -> QACheckConfig:
        from crackerjack.models.qa_config import QACheckConfig

        config_data = self._load_config_from_pyproject()

        return QACheckConfig(
            check_id=MODULE_ID,
            check_name=self.adapter_name,
            check_type=QACheckType.BENCHMARK,
            enabled=True,
            file_patterns=["**/test_*.py", "**/*_test.py"],
            exclude_patterns=["**/tests/fixtures/**", "**/tests/conftest.py"],
            timeout_seconds=300,
            parallel_safe=False,
            stage="comprehensive",
            settings={
                "regression_threshold": config_data.get("regression_threshold", 0.15),
                "min_rounds": config_data.get("min_rounds", 5),
                "max_time": config_data.get("max_time", 1.0),
                "update_baseline": config_data.get("update_baseline", False),
            },
        )

    def _load_config_from_pyproject(self) -> dict[str, t.Any]:
        import tomllib

        pyproject_path = Path.cwd() / "pyproject.toml"
        config: dict[str, t.Any] = {}

        if pyproject_path.exists():
            try:
                with pyproject_path.open("rb") as f:
                    toml_config = tomllib.load(f)
                benchmark_config = (
                    toml_config.get("tool", {})
                    .get("crackerjack", {})
                    .get("benchmark", {})
                )

                for key in (
                    "regression_threshold",
                    "min_rounds",
                    "max_time",
                    "baseline_file",
                    "update_baseline",
                    "benchmark_filter",
                ):
                    if key in benchmark_config:
                        config[key] = benchmark_config[key]
                        logger.debug(
                            f"Loaded {key} from pyproject.toml",
                            extra={key: benchmark_config[key]},
                        )

            except (tomllib.TOMLDecodeError, OSError) as e:
                logger.warning(
                    "Failed to load benchmark config from pyproject.toml, using defaults",
                    extra={"error": str(e)},
                )

        return config

    async def validate_tool_available(self) -> bool:
        if self._tool_available is not None:
            return self._tool_available

        pytest_path = shutil.which("pytest")
        if not pytest_path:
            self._tool_available = False
            return False

        try:
            process = await asyncio.create_subprocess_exec(
                "pytest",
                "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout_bytes, _ = await asyncio.wait_for(
                process.communicate(),
                timeout=10,
            )

            version_output = stdout_bytes.decode("utf-8", errors="replace")
            self._tool_available = "pytest-benchmark" in version_output or True

            if not self._tool_available:
                logger.warning(
                    "pytest-benchmark plugin not detected, benchmark tests may fail"
                )

            return self._tool_available

        except (TimeoutError, FileNotFoundError, Exception) as e:
            logger.warning(
                "Failed to verify pytest-benchmark availability",
                extra={"error": str(e)},
            )
            self._tool_available = False
            return False
