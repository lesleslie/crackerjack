"""
Unit tests for profile loader module.

Tests verify that profiles can be loaded, validated, and compared.
"""

import pytest
import yaml
from pathlib import Path
from unittest.mock import patch

from pydantic import ValidationError

from crackerjack.config.profile_loader import (
    OutputConfig,
    PerformanceConfig,
    ProfileConfig,
    ProfileLoader,
    ProfileMetadata,
    QualityGates,
    RuffConfig,
    TestingConfig,
    get_profile_loader,
    load_profile,
    list_profiles,
)

# Imported Pydantic models that start with ``Test`` would be mistakenly collected
# by pytest's class discovery. Disable collection explicitly on each.
for _name in (
    "OutputConfig",
    "PerformanceConfig",
    "ProfileConfig",
    "ProfileLoader",
    "ProfileMetadata",
    "QualityGates",
    "RuffConfig",
    "TestingConfig",
):
    globals()[_name].__test__ = False


class TestProfileLoader:
    """Test ProfileLoader class."""

    def test_init_default_directory(self):
        """Test ProfileLoader initializes with default directory."""
        loader = ProfileLoader()
        assert loader.profile_dir is not None
        assert loader.profile_dir.exists()

    def test_init_custom_directory(self, tmp_path):
        """Test ProfileLoader initializes with custom directory."""
        loader = ProfileLoader(profile_dir=tmp_path)
        assert loader.profile_dir == tmp_path

    def test_list_profiles(self):
        """Test list_profiles returns built-in profiles."""
        loader = ProfileLoader()
        profiles = loader.list_profiles()

        assert isinstance(profiles, list)
        assert "quick" in profiles
        assert "standard" in profiles
        assert "comprehensive" in profiles

    def test_profile_exists_quick(self):
        """Test profile_exists for quick profile."""
        loader = ProfileLoader()
        assert loader.profile_exists("quick")

    def test_profile_exists_standard(self):
        """Test profile_exists for standard profile."""
        loader = ProfileLoader()
        assert loader.profile_exists("standard")

    def test_profile_exists_comprehensive(self):
        """Test profile_exists for comprehensive profile."""
        loader = ProfileLoader()
        assert loader.profile_exists("comprehensive")

    def test_profile_exists_invalid(self):
        """Test profile_exists for invalid profile."""
        loader = ProfileLoader()
        assert not loader.profile_exists("nonexistent")

    def test_load_profile_quick(self):
        """Test loading quick profile."""
        loader = ProfileLoader()
        config = loader.load_profile("quick")

        assert isinstance(config, ProfileConfig)
        assert config.profile.name == "quick"
        assert config.testing.enabled is False

    def test_load_profile_standard(self):
        """Test loading standard profile."""
        loader = ProfileLoader()
        config = loader.load_profile("standard")

        assert isinstance(config, ProfileConfig)
        assert config.profile.name == "standard"
        assert config.testing.enabled is True
        assert config.testing.coverage is True

    def test_load_profile_comprehensive(self):
        """Test loading comprehensive profile."""
        loader = ProfileLoader()
        config = loader.load_profile("comprehensive")

        assert isinstance(config, ProfileConfig)
        assert config.profile.name == "comprehensive"
        assert config.testing.enabled is True
        assert config.testing.incremental is False

    def test_load_profile_invalid(self):
        """Test loading invalid profile raises ValueError."""
        loader = ProfileLoader()
        with pytest.raises(ValueError, match="Unknown profile"):
            loader.load_profile("nonexistent")

    def test_get_profile_metadata(self):
        """Test getting profile metadata."""
        loader = ProfileLoader()
        metadata = loader.get_profile_metadata("quick")

        assert isinstance(metadata, ProfileMetadata)
        assert metadata.name == "quick"
        assert metadata.execution_time == "< 1 minute"

    def test_get_default_profile(self):
        """Test getting default profile name."""
        loader = ProfileLoader()
        default = loader.get_default_profile()
        assert default == "standard"

    def test_compare_profiles(self):
        """Test comparing two profiles."""
        loader = ProfileLoader()
        comparison = loader.compare_profiles("quick", "comprehensive")

        assert "profile1" in comparison
        assert "profile2" in comparison
        assert comparison["profile1"] == "quick"
        assert comparison["profile2"] == "comprehensive"
        assert "testing" in comparison

    def test_cache(self):
        """Test that profiles are cached after loading."""
        loader = ProfileLoader()

        # Load profile twice
        config1 = loader.load_profile("standard")
        config2 = loader.load_profile("standard")

        # Should be the same object (cached)
        assert config1 is config2


class TestProfileConfig:
    """Test ProfileConfig model."""

    def test_quick_profile_config(self):
        """Test quick profile has correct configuration."""
        config = load_profile("quick")

        assert config.testing.enabled is False
        assert config.quality_gates.fail_on_coverage is False
        assert config.performance.timeout == 60

    def test_standard_profile_config(self):
        """Test standard profile has correct configuration."""
        config = load_profile("standard")

        assert config.testing.enabled is True
        assert config.testing.coverage is True
        assert config.testing.incremental is True
        assert config.quality_gates.coverage_threshold == 80
        assert config.performance.timeout == 300

    def test_comprehensive_profile_config(self):
        """Test comprehensive profile has correct configuration."""
        config = load_profile("comprehensive")

        assert config.testing.enabled is True
        assert config.testing.incremental is False
        assert config.quality_gates.fail_on_complexity is True
        assert config.performance.timeout == 600


class TestConvenienceFunctions:
    """Test convenience functions."""

    def test_get_profile_loader_singleton(self):
        """Test get_profile_loader returns singleton."""
        loader1 = get_profile_loader()
        loader2 = get_profile_loader()
        assert loader1 is loader2

    def test_load_profile_function(self):
        """Test load_profile convenience function."""
        config = load_profile("standard")
        assert isinstance(config, ProfileConfig)
        assert config.profile.name == "standard"

    def test_list_profiles_function(self):
        """Test list_profiles convenience function."""
        profiles = list_profiles()
        assert isinstance(profiles, list)
        assert "standard" in profiles


class TestProfileValidation:
    """Test profile validation."""

    def test_quick_profile_minimal_checks(self):
        """Test quick profile has minimal checks enabled."""
        config = load_profile("quick")
        assert "ruff" in config.checks.get("enabled", [])
        assert "pytest" not in config.checks.get("enabled", [])

    def test_standard_profile_balanced_checks(self):
        """Test standard profile has balanced checks."""
        config = load_profile("standard")
        assert "ruff" in config.checks.get("enabled", [])
        assert "pytest" in config.checks.get("enabled", [])

    def test_comprehensive_profile_all_checks(self):
        """Test comprehensive profile has all checks."""
        config = load_profile("comprehensive")
        assert "ruff" in config.checks.get("enabled", [])
        assert "pytest" in config.checks.get("enabled", [])
        assert len(config.checks.get("enabled", [])) >= 5


class TestProfileQualityGates:
    """Test quality gate configuration in profiles."""

    def test_quick_profile_lenient_gates(self):
        """Test quick profile has lenient quality gates."""
        config = load_profile("quick")
        assert config.quality_gates.fail_on_test_errors is False
        assert config.quality_gates.fail_on_coverage is False

    def test_standard_profile_balanced_gates(self):
        """Test standard profile has balanced quality gates."""
        config = load_profile("standard")
        assert config.quality_gates.fail_on_test_errors is True
        assert config.quality_gates.fail_on_coverage is True
        assert config.quality_gates.fail_on_complexity is False

    def test_comprehensive_profile_strict_gates(self):
        """Test comprehensive profile has strict quality gates."""
        config = load_profile("comprehensive")
        assert config.quality_gates.fail_on_test_errors is True
        assert config.quality_gates.fail_on_coverage is True
        assert config.quality_gates.fail_on_complexity is True


class TestPydanticModelsDefaults:
    """Cover direct instantiation of each Pydantic config model."""

    def test_profile_metadata_defaults_via_construction(self):
        """ProfileMetadata requires explicit fields; constructor kwargs satisfy them."""
        meta = ProfileMetadata(
            name="custom",
            description="custom profile",
            execution_time="5m",
        )
        assert meta.name == "custom"
        assert meta.description == "custom profile"
        assert meta.execution_time == "5m"

    def test_quality_gates_defaults(self):
        """QualityGates factory defaults match the dataclass-style defaults."""
        gates = QualityGates()
        assert gates.fail_on_ruff_errors is True
        assert gates.fail_on_test_errors is True
        assert gates.fail_on_coverage is False
        assert gates.coverage_threshold is None
        assert gates.fail_on_complexity is False
        assert gates.max_complexity is None
        assert gates.fail_on_security is False

    def test_quality_gates_overrides(self):
        """QualityGates overrides are applied."""
        gates = QualityGates(
            fail_on_ruff_errors=False,
            fail_on_test_errors=False,
            fail_on_coverage=True,
            coverage_threshold=90,
            fail_on_complexity=True,
            max_complexity=10,
            fail_on_security=True,
        )
        assert gates.fail_on_ruff_errors is False
        assert gates.coverage_threshold == 90
        assert gates.max_complexity == 10
        assert gates.fail_on_security is True

    def test_ruff_config_defaults(self):
        """RuffConfig default select/ignore lists."""
        ruff = RuffConfig()
        assert ruff.select == ["E", "W", "F"]
        assert ruff.ignore == []

    def test_ruff_config_overrides(self):
        """RuffConfig override fields."""
        ruff = RuffConfig(select=["B", "C4"], ignore=["E501"])
        assert ruff.select == ["B", "C4"]
        assert ruff.ignore == ["E501"]

    def test_testing_config_defaults(self):
        """TestingConfig defaults reflect the standard production settings."""
        testing = TestingConfig()
        assert testing.enabled is True
        assert testing.coverage is True
        assert testing.coverage_threshold == 80
        assert testing.parallel is True
        assert testing.auto_detect_workers is True
        assert testing.max_workers == 8
        assert testing.min_workers == 2
        assert testing.timeout == 300
        assert testing.incremental is True
        assert testing.benchmark is False

    def test_testing_config_overrides(self):
        """TestingConfig overrides are applied."""
        testing = TestingConfig(
            enabled=False,
            coverage=False,
            coverage_threshold=95,
            parallel=False,
            auto_detect_workers=False,
            max_workers=2,
            min_workers=1,
            timeout=120,
            incremental=False,
            benchmark=True,
        )
        assert testing.enabled is False
        assert testing.coverage_threshold == 95
        assert testing.max_workers == 2
        assert testing.benchmark is True

    def test_performance_config_defaults(self):
        """PerformanceConfig defaults."""
        perf = PerformanceConfig()
        assert perf.parallel_execution is True
        assert perf.cache_enabled is True
        assert perf.incremental is True
        assert perf.timeout == 300

    def test_performance_config_overrides(self):
        """PerformanceConfig overrides are applied."""
        perf = PerformanceConfig(
            parallel_execution=False,
            cache_enabled=False,
            incremental=False,
            timeout=900,
        )
        assert perf.parallel_execution is False
        assert perf.timeout == 900

    def test_output_config_defaults(self):
        """OutputConfig defaults."""
        output = OutputConfig()
        assert output.verbose is False
        assert output.show_progress is True
        assert output.color is True
        assert output.format == "console"
        assert output.coverage_reports == ["term"]

    def test_output_config_overrides(self):
        """OutputConfig overrides are applied."""
        output = OutputConfig(
            verbose=True,
            show_progress=False,
            color=False,
            format="json",
            coverage_reports=["term", "html"],
        )
        assert output.verbose is True
        assert output.show_progress is False
        assert output.format == "json"
        assert output.coverage_reports == ["term", "html"]


class TestProfileConfigValidator:
    """Cover ProfileConfig.validate_checks validator paths."""

    def test_validate_checks_adds_missing_enabled_key(self):
        """When ``enabled`` is missing, validator inserts an empty list."""
        config = ProfileConfig(
            profile=ProfileMetadata(
                name="x", description="d", execution_time="1m"
            ),
            checks={"disabled": ["pytest"]},
        )
        assert config.checks["enabled"] == []
        assert config.checks["disabled"] == ["pytest"]

    def test_validate_checks_adds_missing_disabled_key(self):
        """When ``disabled`` is missing, validator inserts an empty list."""
        config = ProfileConfig(
            profile=ProfileMetadata(
                name="x", description="d", execution_time="1m"
            ),
            checks={"enabled": ["ruff"]},
        )
        assert config.checks["enabled"] == ["ruff"]
        assert config.checks["disabled"] == []

    def test_validate_checks_adds_both_keys_when_empty(self):
        """When checks dict is empty, both keys default to empty lists."""
        config = ProfileConfig(
            profile=ProfileMetadata(
                name="x", description="d", execution_time="1m"
            ),
            checks={},
        )
        assert config.checks == {"enabled": [], "disabled": []}

    def test_profile_config_defaults_for_sub_models(self):
        """ProfileConfig builds correct sub-model defaults when none are provided."""
        config = ProfileConfig(
            profile=ProfileMetadata(
                name="x", description="d", execution_time="1m"
            ),
        )
        # Sub-model factories should populate defaults.
        assert isinstance(config.quality_gates, QualityGates)
        assert isinstance(config.ruff, RuffConfig)
        assert isinstance(config.testing, TestingConfig)
        assert isinstance(config.performance, PerformanceConfig)
        assert isinstance(config.output, OutputConfig)
        # Dict defaults with lambdas should also populate.
        assert config.complexity == {"enabled": False}
        assert config.security == {"enabled": False}
        assert config.documentation == {"cleanup": False}
        assert config.git == {
            "commit": False,
            "create_pr": False,
            "update_hooks": False,
        }


class TestListProfilesEdgeCases:
    """Cover list_profiles branch edges (missing dir, non-builtin yaml files)."""

    def test_list_profiles_returns_empty_when_dir_missing(self, tmp_path):
        """list_profiles returns [] when profile_dir does not exist."""
        missing = tmp_path / "does_not_exist"
        loader = ProfileLoader(profile_dir=missing)
        assert loader.list_profiles() == []

    def test_list_profiles_skips_non_builtin_yaml_files(self, tmp_path):
        """list_profiles only includes yaml files matching BUILTIN_PROFILES."""
        # Create a builtin name and an unrelated yaml file.
        (tmp_path / "quick.yaml").write_text(
            "profile:\n  name: quick\n  description: d\n  execution_time: 1m\n"
        )
        (tmp_path / "custom_extra.yaml").write_text(
            "profile:\n  name: custom\n  description: d\n  execution_time: 1m\n"
        )
        loader = ProfileLoader(profile_dir=tmp_path)
        profiles = loader.list_profiles()
        assert "quick" in profiles
        assert "custom_extra" not in profiles

    def test_list_profiles_only_yaml_files(self, tmp_path):
        """Non-yaml files in the profile dir are ignored."""
        (tmp_path / "quick.yaml").write_text(
            "profile:\n  name: quick\n  description: d\n  execution_time: 1m\n"
        )
        (tmp_path / "notes.txt").write_text("not a profile")
        (tmp_path / "README.md").write_text("# readme")
        loader = ProfileLoader(profile_dir=tmp_path)
        assert loader.list_profiles() == ["quick"]


class TestLoadProfileFileNotFound:
    """Cover the FileNotFoundError path in load_profile (line 120)."""

    def test_load_profile_raises_when_file_missing(self, tmp_path):
        """When validation passes but file does not exist, FileNotFoundError is raised."""
        # Subclass so we can add a fake builtin profile name whose yaml file is missing.
        class TestLoader(ProfileLoader):
            BUILTIN_PROFILES = ["quick", "ghost"]

        loader = TestLoader(profile_dir=tmp_path)
        # 'ghost' passes _validate_profile_name but has no file on disk.
        with pytest.raises(FileNotFoundError, match="Profile file not found"):
            loader.load_profile("ghost")


class TestLoadAndCacheErrors:
    """Cover yaml.YAMLError and generic Exception paths in _load_and_cache_profile."""

    def test_load_profile_invalid_yaml_raises_value_error(self, tmp_path):
        """Invalid YAML in a builtin profile file raises ValueError with a clear message."""
        (tmp_path / "quick.yaml").write_text(
            "profile:\n  name: quick\n  description: d\n  execution_time: 1m\n"
            "checks:\n  enabled: [unclosed"
        )
        loader = ProfileLoader(profile_dir=tmp_path)
        with pytest.raises(ValueError, match="Invalid YAML in profile file"):
            loader.load_profile("quick")

    def test_load_profile_validation_error_raises_value_error(self, tmp_path):
        """Pydantic validation errors are wrapped in ValueError by the loader."""
        # ProfileConfig requires `profile` to be a ProfileMetadata-shaped dict.
        # Omitting it entirely triggers a ValidationError, which the loader
        # wraps as ValueError("Error loading profile ...").
        (tmp_path / "quick.yaml").write_text("not_a_profile: true\n")
        loader = ProfileLoader(profile_dir=tmp_path)
        with pytest.raises(ValueError, match="Error loading profile quick"):
            loader.load_profile("quick")


class TestProfileExistsEdgeCases:
    """Cover profile_exists for non-builtin profile names."""

    def test_profile_exists_returns_false_for_unknown_builtin_name(self, tmp_path):
        """profile_exists returns False when name is not in BUILTIN_PROFILES."""
        loader = ProfileLoader(profile_dir=tmp_path)
        assert loader.profile_exists("nonexistent") is False

    def test_profile_exists_returns_false_when_file_missing(self, tmp_path):
        """profile_exists returns False for a builtin name whose file is absent."""
        loader = ProfileLoader(profile_dir=tmp_path)
        assert loader.profile_exists("quick") is False


class TestCompareProfilesDeepFields:
    """Deeper assertions on compare_profiles output structure."""

    def test_compare_profiles_includes_all_sections(self):
        """compare_profiles returns testing, quality_gates, and performance sections."""
        loader = ProfileLoader()
        result = loader.compare_profiles("quick", "standard")
        assert set(result.keys()) == {"profile1", "profile2", "testing", "quality_gates", "performance"}
        assert result["profile1"] == "quick"
        assert result["profile2"] == "standard"

    def test_compare_profiles_testing_fields_present(self):
        """Each testing sub-section includes enabled and coverage flags for both profiles."""
        loader = ProfileLoader()
        result = loader.compare_profiles("quick", "comprehensive")
        testing = result["testing"]
        assert set(testing["enabled"].keys()) == {"quick", "comprehensive"}
        assert set(testing["coverage"].keys()) == {"quick", "comprehensive"}
        # quick disables tests, comprehensive enables them.
        assert testing["enabled"]["quick"] is False
        assert testing["enabled"]["comprehensive"] is True

    def test_compare_profiles_quality_gates_field(self):
        """quality_gates comparison contains fail_on_coverage values for both profiles."""
        loader = ProfileLoader()
        result = loader.compare_profiles("quick", "standard")
        qg = result["quality_gates"]["fail_on_coverage"]
        assert qg["quick"] is False
        assert qg["standard"] is True

    def test_compare_profiles_performance_timeout(self):
        """performance.timeout comparison surfaces both profiles' timeout values."""
        loader = ProfileLoader()
        result = loader.compare_profiles("quick", "comprehensive")
        perf = result["performance"]["timeout"]
        assert perf["quick"] == 60
        assert perf["comprehensive"] == 600


class TestConvenienceFunctionsDeep:
    """Additional convenience-function edge cases."""

    def test_load_profile_function_propagates_value_error(self, monkeypatch):
        """load_profile convenience function surfaces ValueError for unknown names."""
        with pytest.raises(ValueError, match="Unknown profile"):
            load_profile("does_not_exist")

    def test_list_profiles_function_matches_loader(self, monkeypatch):
        """list_profiles convenience function returns the same list as loader.list_profiles()."""
        loader = get_profile_loader()
        assert list_profiles() == loader.list_profiles()

    def test_get_profile_loader_returns_profile_loader_instance(self):
        """get_profile_loader returns a ProfileLoader (not None, not a different type)."""
        loader = get_profile_loader()
        assert isinstance(loader, ProfileLoader)
        # Path is normalized to absolute.
        assert isinstance(loader.profile_dir, Path)


class TestCachingBehavior:
    """Cover the cache short-circuit in load_profile (lines 113-114)."""

    def test_cache_returns_same_object_across_calls(self):
        """Multiple load_profile calls return the same cached object."""
        loader = ProfileLoader()
        first = loader.load_profile("quick")
        # Mutate the cache directly to prove the second call returns the cached value.
        loader._cache["quick"] = "sentinel"
        second = loader.load_profile("quick")
        assert second == "sentinel"
        # Restore so subsequent tests using get_profile_loader() are unaffected.
        loader._cache["quick"] = first

    def test_independent_loaders_do_not_share_cache(self):
        """Each ProfileLoader instance owns its own cache."""
        loader_a = ProfileLoader()
        loader_b = ProfileLoader()
        loader_a._cache["quick"] = "sentinel_a"
        assert "quick" not in loader_b._cache
