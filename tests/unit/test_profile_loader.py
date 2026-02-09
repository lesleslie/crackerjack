"""
Unit tests for profile loader module.

Tests verify that profiles can be loaded, validated, and compared.
"""

import pytest
from pathlib import Path

from crackerjack.config.profile_loader import (
    ProfileLoader,
    ProfileConfig,
    ProfileMetadata,
    get_profile_loader,
    load_profile,
    list_profiles,
)


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
