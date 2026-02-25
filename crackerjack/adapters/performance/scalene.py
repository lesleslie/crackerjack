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
from crackerjack.models.adapter_metadata import AdapterStatus
from crackerjack.models.qa_results import QACheckType

if t.TYPE_CHECKING:
    from crackerjack.models.qa_config import QACheckConfig


MODULE_ID = UUID("b2c3d4e5-f6a7-8901-bcde-f23456789012")
MODULE_STATUS = AdapterStatus.STABLE

logger = logging.getLogger(__name__)


class ScaleneSettings(ToolAdapterSettings):
    tool_name: str = "scalene"
    use_json_output: bool = True

    cpu_percent_threshold: float = Field(
        default=5.0,
        ge=0.0,
        le=100.0,
        description="Report lines using > X% of CPU time",
    )

    memory_threshold_mb: float = Field(
        default=10.0,
        ge=0.0,
        description="Report lines allocating > X MB",
    )

    copy_threshold_mb: float = Field(
        default=50.0,
        ge=0.0,
        description="Report lines with > X MB copy volume",
    )

    profile_cpu: bool = Field(
        default=True,
        description="Enable CPU profiling",
    )

    profile_memory: bool = Field(
        default=True,
        description="Enable memory profiling",
    )

    profile_gpu: bool = Field(
        default=False,
        description="Enable GPU profiling (NVIDIA only)",
    )

    detect_leaks: bool = Field(
        default=True,
        description="Detect potential memory leaks",
    )

    reduced_profile: bool = Field(
        default=True,
        description="Only report lines with activity",
    )

    profile_all: bool = Field(
        default=False,
        description="Profile all imported modules",
    )


@dataclass
class ProfileHotspot:
    file_path: Path
    line_number: int
    rule: str
    message: str
    severity: str
    details: dict[str, t.Any]

    def to_tool_issue(self) -> ToolIssue:
        return ToolIssue(
            file_path=self.file_path,
            line_number=self.line_number,
            message=self.message,
            code=self.rule,
            severity=self.severity,
            suggestion=self._get_suggestion(),
        )

    def _get_suggestion(self) -> str | None:
        suggestions = {
            "SC001": "Consider optimizing this CPU-intensive code or using a more efficient algorithm",
            "SC002": "Review memory allocation patterns; consider object pooling or generators",
            "SC003": "Investigate memory lifecycle; objects may not be properly released",
            "SC004": "Reduce copying by using views, references, or in-place operations",
            "SC005": "Optimize GPU utilization or consider CPU fallback for small batches",
        }
        return suggestions.get(self.rule)


class ScaleneAdapter(BaseToolAdapter):
    settings: ScaleneSettings | None = None

    def __init__(self, settings: ScaleneSettings | None = None) -> None:
        super().__init__(settings=settings)
        logger.debug(
            "ScaleneAdapter initialized",
            extra={"has_settings": settings is not None},
        )

    async def init(self) -> None:
        if not self.settings:
            config_data = self._load_config_from_pyproject()
            self.settings = ScaleneSettings(
                cpu_percent_threshold=config_data.get("cpu_percent_threshold", 5.0),
                memory_threshold_mb=config_data.get("memory_threshold_mb", 10.0),
                copy_threshold_mb=config_data.get("copy_threshold_mb", 50.0),
                profile_cpu=config_data.get("profile_cpu", True),
                profile_memory=config_data.get("profile_memory", True),
                profile_gpu=config_data.get("profile_gpu", False),
                detect_leaks=config_data.get("detect_leaks", True),
                reduced_profile=config_data.get("reduced_profile", True),
                timeout_seconds=300,
                max_workers=1,
            )
            logger.info(
                "Using default ScaleneSettings",
                extra={
                    "cpu_percent_threshold": self.settings.cpu_percent_threshold,
                    "memory_threshold_mb": self.settings.memory_threshold_mb,
                },
            )

        await super().init()
        logger.debug("ScaleneAdapter initialization complete")

    @property
    def adapter_name(self) -> str:
        return "scalene"

    @property
    def module_id(self) -> UUID:
        return MODULE_ID

    @property
    def tool_name(self) -> str:
        return "scalene"

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
            "--cli",
            "--json",
        ]

        if self.settings.profile_cpu:
            cmd.append("--cpu")

        if self.settings.profile_memory:
            cmd.append("--memory")

        if self.settings.profile_gpu:
            cmd.append("--gpu")

        if self.settings.reduced_profile:
            cmd.append("--reduced-profile")

        if self.settings.profile_all:
            cmd.extend(
                (
                    "--profile-all",
                    f"--cpu-percent-threshold={self.settings.cpu_percent_threshold}",
                )
            )

        cmd.extend(("--outfile=-", "---"))

        if self._detect_test_file(files):
            cmd.extend(["python", "-m", "pytest", "-x", *[str(f) for f in files]])
        else:
            cmd.extend(["python", *[str(f) for f in files]])

        logger.info(
            "Built scalene command",
            extra={
                "file_count": len(files),
                "profile_cpu": self.settings.profile_cpu,
                "profile_memory": self.settings.profile_memory,
            },
        )
        return cmd

    def _detect_test_file(self, files: list[Path]) -> bool:
        for f in files:
            name = f.name.lower()
            if name.startswith("test_") or name.endswith("_test.py"):
                return True
        return False

    async def parse_output(
        self,
        result: ToolExecutionResult,
    ) -> list[ToolIssue]:
        if not result.raw_output:
            logger.debug("No scalene output to parse")
            return []

        json_output = self._extract_json(result.raw_output)

        if not json_output:
            logger.warning(
                "No JSON found in scalene output",
                extra={"output_preview": result.raw_output[:500]},
            )
            return []

        try:
            profile_data = json.loads(json_output)
        except json.JSONDecodeError as e:
            logger.warning(
                "Failed to parse scalene JSON output",
                extra={"error": str(e)},
            )
            return [
                ToolIssue(
                    file_path=Path("scalene"),
                    message=f"Failed to parse scalene output: {e}",
                    code="SC000",
                    severity="error",
                ),
            ]

        issues: list[ToolIssue] = []

        for file_profile in profile_data.get("files", []):
            file_issues = self._process_file_profile(file_profile)
            issues.extend(file_issues)

        logger.info(
            "Parsed scalene output",
            extra={
                "total_files": len(profile_data.get("files", [])),
                "issues_found": len(issues),
            },
        )
        return issues

    def _extract_json(self, output: str) -> str | None:

        lines = output.strip().split("\n")

        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("{"):
                return "\n".join(lines[i:])

        return None

    def _process_file_profile(self, file_profile: dict[str, t.Any]) -> list[ToolIssue]:
        issues: list[ToolIssue] = []

        if not self.settings:
            return issues

        filename = file_profile.get("filename", "unknown")
        file_path = Path(filename) if filename != "unknown" else Path("scalene")

        lines_data = file_profile.get("lines", {})

        if isinstance(lines_data, dict):
            for line_num_str, line_data in lines_data.items():
                try:
                    line_num = int(line_num_str)
                except ValueError:
                    continue

                line_issues = self._analyze_line(file_path, line_num, line_data)
                issues.extend(line_issues)

        return issues

    def _analyze_line(
        self,
        file_path: Path,
        line_num: int,
        line_data: dict[str, t.Any],
    ) -> list[ToolIssue]:
        issues: list[ToolIssue] = []

        if not self.settings:
            return issues

        cpu_percent = line_data.get("cpu_percent", 0.0)
        cpu_python = line_data.get("cpu_python", 0.0)
        cpu_c = line_data.get("cpu_c", 0.0)
        mem_mb = line_data.get("mem_mb", 0.0) or line_data.get("memory_mb", 0.0)
        copy_mb = line_data.get("copy_mb", 0.0)
        gpu_percent = line_data.get("gpu_percent", 0.0)
        net_memory = line_data.get("net_memory", 0.0)

        if (
            self.settings.profile_cpu
            and cpu_percent > self.settings.cpu_percent_threshold
        ):
            issues.append(
                ProfileHotspot(
                    file_path=file_path,
                    line_number=line_num,
                    rule="SC001",
                    message=(
                        f"CPU hotspot: line consumes {cpu_percent:.1f}% of CPU time "
                        f"(Python: {cpu_python:.1f}%, Native: {cpu_c:.1f}%)"
                    ),
                    severity="warning",
                    details={
                        "cpu_percent": cpu_percent,
                        "cpu_python": cpu_python,
                        "cpu_c": cpu_c,
                        "threshold": self.settings.cpu_percent_threshold,
                    },
                ).to_tool_issue()
            )

        if self.settings.profile_memory and mem_mb > self.settings.memory_threshold_mb:
            issues.append(
                ProfileHotspot(
                    file_path=file_path,
                    line_number=line_num,
                    rule="SC002",
                    message=f"Memory hotspot: line allocated {mem_mb:.1f} MB",
                    severity="warning",
                    details={
                        "memory_mb": mem_mb,
                        "threshold": self.settings.memory_threshold_mb,
                    },
                ).to_tool_issue()
            )

        if self.settings.detect_leaks and net_memory < -10:
            issues.append(
                ProfileHotspot(
                    file_path=file_path,
                    line_number=line_num,
                    rule="SC003",
                    message=(
                        f"Potential memory leak: net negative allocation of "
                        f"{abs(net_memory):.1f} MB (more freed than allocated)"
                    ),
                    severity="error",
                    details={
                        "net_memory": net_memory,
                    },
                ).to_tool_issue()
            )

        if copy_mb > self.settings.copy_threshold_mb:
            issues.append(
                ProfileHotspot(
                    file_path=file_path,
                    line_number=line_num,
                    rule="SC004",
                    message=f"Excessive copying: {copy_mb:.1f} MB copied on this line",
                    severity="warning",
                    details={
                        "copy_mb": copy_mb,
                        "threshold": self.settings.copy_threshold_mb,
                    },
                ).to_tool_issue()
            )

        if self.settings.profile_gpu and gpu_percent < 10.0 and cpu_percent > 20.0:
            issues.append(
                ProfileHotspot(
                    file_path=file_path,
                    line_number=line_num,
                    rule="SC005",
                    message=(
                        f"GPU underutilization: {gpu_percent:.1f}% GPU vs "
                        f"{cpu_percent:.1f}% CPU (consider GPU acceleration)"
                    ),
                    severity="info",
                    details={
                        "gpu_percent": gpu_percent,
                        "cpu_percent": cpu_percent,
                    },
                ).to_tool_issue()
            )

        return issues

    def _get_check_type(self) -> QACheckType:
        return QACheckType.PROFILE

    def get_default_config(self) -> QACheckConfig:
        from crackerjack.models.qa_config import QACheckConfig

        config_data = self._load_config_from_pyproject()

        return QACheckConfig(
            check_id=MODULE_ID,
            check_name=self.adapter_name,
            check_type=QACheckType.PROFILE,
            enabled=True,
            file_patterns=["**/*.py"],
            exclude_patterns=[
                "**/tests/**",
                "**/test_*.py",
                "**/*_test.py",
                "**/conftest.py",
            ],
            timeout_seconds=300,
            parallel_safe=False,
            stage="comprehensive",
            settings={
                "cpu_percent_threshold": config_data.get("cpu_percent_threshold", 5.0),
                "memory_threshold_mb": config_data.get("memory_threshold_mb", 10.0),
                "copy_threshold_mb": config_data.get("copy_threshold_mb", 50.0),
                "profile_cpu": config_data.get("profile_cpu", True),
                "profile_memory": config_data.get("profile_memory", True),
                "profile_gpu": config_data.get("profile_gpu", False),
                "detect_leaks": config_data.get("detect_leaks", True),
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
                scalene_config = (
                    toml_config.get("tool", {})
                    .get("crackerjack", {})
                    .get("scalene", {})
                )

                for key in (
                    "cpu_percent_threshold",
                    "memory_threshold_mb",
                    "copy_threshold_mb",
                    "profile_cpu",
                    "profile_memory",
                    "profile_gpu",
                    "detect_leaks",
                    "reduced_profile",
                    "profile_all",
                ):
                    if key in scalene_config:
                        config[key] = scalene_config[key]
                        logger.debug(
                            f"Loaded {key} from pyproject.toml",
                            extra={key: scalene_config[key]},
                        )

            except (tomllib.TOMLDecodeError, OSError) as e:
                logger.warning(
                    "Failed to load scalene config from pyproject.toml, using defaults",
                    extra={"error": str(e)},
                )

        return config

    async def validate_tool_available(self) -> bool:
        if self._tool_available is not None:
            return self._tool_available

        scalene_path = shutil.which("scalene")
        if not scalene_path:
            self._tool_available = False
            logger.warning("scalene not found in PATH")
            return False

        try:
            process = await asyncio.create_subprocess_exec(
                "scalene",
                "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout_bytes, _ = await asyncio.wait_for(
                process.communicate(),
                timeout=10,
            )

            version_output = stdout_bytes.decode("utf-8", errors="replace")
            self._tool_available = True
            logger.debug(
                "scalene found",
                extra={"version": version_output.strip()},
            )
            return self._tool_available

        except (TimeoutError, FileNotFoundError, Exception) as e:
            logger.warning(
                "Failed to verify scalene availability",
                extra={"error": str(e)},
            )
            self._tool_available = False
            return False
