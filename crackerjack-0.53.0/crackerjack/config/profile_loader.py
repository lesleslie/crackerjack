import logging
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)


class ProfileMetadata(BaseModel):
    name: str = Field(description="Profile name")
    description: str = Field(description="Profile description")
    execution_time: str = Field(description="Expected execution time")


class QualityGates(BaseModel):
    fail_on_ruff_errors: bool = True
    fail_on_test_errors: bool = True
    fail_on_coverage: bool = False
    coverage_threshold: int | None = None
    fail_on_complexity: bool = False
    max_complexity: int | None = None
    fail_on_security: bool = False


class RuffConfig(BaseModel):
    select: list[str] = ["E", "W", "F"]
    ignore: list[str] = []


class TestingConfig(BaseModel):
    enabled: bool = True
    coverage: bool = True
    coverage_threshold: int = 80
    parallel: bool = True
    auto_detect_workers: bool = True
    max_workers: int = 8
    min_workers: int = 2
    timeout: int = 300
    incremental: bool = True
    benchmark: bool = False


class PerformanceConfig(BaseModel):
    parallel_execution: bool = True
    cache_enabled: bool = True
    incremental: bool = True
    timeout: int = 300


class OutputConfig(BaseModel):
    verbose: bool = False
    show_progress: bool = True
    color: bool = True
    format: str = "console"
    coverage_reports: list[str] = ["term"]


class ProfileConfig(BaseModel):
    profile: ProfileMetadata
    checks: dict[str, Any] = Field(default_factory=dict)
    quality_gates: QualityGates = Field(default_factory=QualityGates)
    ruff: RuffConfig = Field(default_factory=RuffConfig)
    testing: TestingConfig = Field(default_factory=TestingConfig)
    complexity: dict[str, Any] = Field(default_factory=lambda: {"enabled": False})
    security: dict[str, Any] = Field(default_factory=lambda: {"enabled": False})
    performance: PerformanceConfig = Field(default_factory=PerformanceConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)
    documentation: dict[str, Any] = Field(default_factory=lambda: {"cleanup": False})
    git: dict[str, Any] = Field(
        default_factory=lambda: {
            "commit": False,
            "create_pr": False,
            "update_hooks": False,
        }
    )

    @field_validator("checks")
    def validate_checks(cls, v):
        if "enabled" not in v:
            v["enabled"] = []
        if "disabled" not in v:
            v["disabled"] = []
        return v


class ProfileLoader:
    BUILTIN_PROFILES = ["quick", "standard", "comprehensive"]

    def __init__(self, profile_dir: Path | None = None):
        if profile_dir is None:
            package_root = Path(__file__).parent.parent.parent
            profile_dir = package_root / "settings" / "profiles"

        self.profile_dir = Path(profile_dir)
        self._cache: dict[str, ProfileConfig] = {}

    def list_profiles(self) -> list[str]:
        profiles = []

        if self.profile_dir.exists():
            for profile_file in self.profile_dir.glob("*.yaml"):
                profile_name = profile_file.stem
                if profile_name in self.BUILTIN_PROFILES:
                    profiles.append(profile_name)

        return sorted(profiles)

    def load_profile(self, profile_name: str) -> ProfileConfig:

        if profile_name in self._cache:
            return self._cache[profile_name]

        if profile_name not in self.BUILTIN_PROFILES:
            raise ValueError(
                f"Unknown profile: {profile_name}. "
                f"Available profiles: {', '.join(self.BUILTIN_PROFILES)}"
            )

        profile_file = self.profile_dir / f"{profile_name}.yaml"

        if not profile_file.exists():
            raise FileNotFoundError(
                f"Profile file not found: {profile_file}. "
                f"Available profiles: {', '.join(self.list_profiles())}"
            )

        try:
            with profile_file.open("r") as f:
                profile_data = yaml.safe_load(f)

            config = ProfileConfig(**profile_data)

            self._cache[profile_name] = config

            return config

        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML in profile file {profile_file}: {e}")
        except Exception as e:
            raise ValueError(f"Error loading profile {profile_name}: {e}")

    def get_profile_metadata(self, profile_name: str) -> ProfileMetadata:
        config = self.load_profile(profile_name)
        return config.profile

    def profile_exists(self, profile_name: str) -> bool:
        return (
            profile_name in self.BUILTIN_PROFILES
            and (self.profile_dir / f"{profile_name}.yaml").exists()
        )

    def compare_profiles(self, profile1: str, profile2: str) -> dict[str, Any]:
        config1 = self.load_profile(profile1)
        config2 = self.load_profile(profile2)

        comparison = {
            "profile1": profile1,
            "profile2": profile2,
            "testing": {
                "enabled": {
                    profile1: config1.testing.enabled,
                    profile2: config2.testing.enabled,
                },
                "coverage": {
                    profile1: config1.testing.coverage,
                    profile2: config2.testing.coverage,
                },
            },
            "quality_gates": {
                "fail_on_coverage": {
                    profile1: config1.quality_gates.fail_on_coverage,
                    profile2: config2.quality_gates.fail_on_coverage,
                },
            },
            "performance": {
                "timeout": {
                    profile1: config1.performance.timeout,
                    profile2: config2.performance.timeout,
                },
            },
        }

        return comparison

    def get_default_profile(self) -> str:
        return "standard"


_default_loader: ProfileLoader | None = None


def get_profile_loader() -> ProfileLoader:
    global _default_loader
    if _default_loader is None:
        _default_loader = ProfileLoader()
    return _default_loader


def load_profile(profile_name: str) -> ProfileConfig:
    return get_profile_loader().load_profile(profile_name)


def list_profiles() -> list[str]:
    return get_profile_loader().list_profiles()


__all__ = [
    "ProfileConfig",
    "ProfileLoader",
    "get_profile_loader",
    "load_profile",
    "list_profiles",
]
