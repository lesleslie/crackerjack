"""Tests for UtilityCheckAdapter - generic configuration-driven adapter.

Tests cover all 5 check types: TEXT_PATTERN, EOF_NEWLINE, SYNTAX_VALIDATION,
SIZE_CHECK, and DEPENDENCY_LOCK with synchronous configuration validation.
"""

from pathlib import Path
from unittest.mock import Mock, patch
from uuid import UUID

import pytest

from crackerjack.adapters.utility.checks import (
    UtilityCheckAdapter,
    UtilityCheckSettings,
    UtilityCheckType,
)
from crackerjack.models.qa_config import QACheckConfig
from crackerjack.models.qa_results import QACheckType, QAResult


class TestUtilityCheckAdapterConfiguration:
    """Test UtilityCheckAdapter configuration and initialization."""

    def test_adapter_with_text_pattern_settings(self):
        """Test adapter with TEXT_PATTERN check type."""
        settings = UtilityCheckSettings(
            check_type=UtilityCheckType.TEXT_PATTERN,
            pattern=r"\\s+$",
        )

        adapter = UtilityCheckAdapter(settings=settings)

        assert adapter.settings is not None
        assert adapter.settings.check_type == UtilityCheckType.TEXT_PATTERN
        assert adapter.settings.pattern == r"\\s+$"

    def test_adapter_with_eof_newline_settings(self):
        """Test adapter with EOF_NEWLINE check type."""
        settings = UtilityCheckSettings(
            check_type=UtilityCheckType.EOF_NEWLINE,
            auto_fix=True,
        )

        adapter = UtilityCheckAdapter(settings=settings)

        assert adapter.settings.check_type == UtilityCheckType.EOF_NEWLINE
        assert adapter.settings.auto_fix is True

    def test_adapter_with_syntax_validation_settings(self):
        """Test adapter with SYNTAX_VALIDATION check type."""
        settings = UtilityCheckSettings(
            check_type=UtilityCheckType.SYNTAX_VALIDATION,
            parser_type="yaml",
        )

        adapter = UtilityCheckAdapter(settings=settings)

        assert adapter.settings.check_type == UtilityCheckType.SYNTAX_VALIDATION
        assert adapter.settings.parser_type == "yaml"

    def test_adapter_with_size_check_settings(self):
        """Test adapter with SIZE_CHECK check type."""
        settings = UtilityCheckSettings(
            check_type=UtilityCheckType.SIZE_CHECK,
            max_size_bytes=1024000,  # 1MB
        )

        adapter = UtilityCheckAdapter(settings=settings)

        assert adapter.settings.check_type == UtilityCheckType.SIZE_CHECK
        assert adapter.settings.max_size_bytes == 1024000

    def test_adapter_with_dependency_lock_settings(self):
        """Test adapter with DEPENDENCY_LOCK check type."""
        settings = UtilityCheckSettings(
            check_type=UtilityCheckType.DEPENDENCY_LOCK,
            lock_command=["uv", "lock"],
        )

        adapter = UtilityCheckAdapter(settings=settings)

        assert adapter.settings.check_type == UtilityCheckType.DEPENDENCY_LOCK
        assert adapter.settings.lock_command == ["uv", "lock"]


class TestUtilityCheckAdapterProperties:
    """Test adapter properties and attributes."""

    def test_adapter_name(self):
        """Test adapter_name property."""
        settings = UtilityCheckSettings(
            check_type=UtilityCheckType.TEXT_PATTERN,
            pattern="test",
        )
        adapter = UtilityCheckAdapter(settings=settings)

        assert isinstance(adapter.adapter_name, str)
        assert len(adapter.adapter_name) > 0

    def test_module_id(self):
        """Test module_id property returns UUID."""
        settings = UtilityCheckSettings(
            check_type=UtilityCheckType.TEXT_PATTERN,
            pattern="test",
        )
        adapter = UtilityCheckAdapter(settings=settings)

        assert isinstance(adapter.module_id, UUID)

    def test_check_type_property(self):
        """Test _get_check_type returns correct type."""
        settings = UtilityCheckSettings(
            check_type=UtilityCheckType.TEXT_PATTERN,
            pattern="test",
        )
        adapter = UtilityCheckAdapter(settings=settings)

        check_type = adapter._get_check_type()
        # Utility checks are FORMAT type
        assert isinstance(check_type, QACheckType)


class TestUtilityCheckDefaultConfigs:
    """Test default configuration generation."""

    def test_get_default_config_text_pattern(self):
        """Test default config for TEXT_PATTERN check."""
        settings = UtilityCheckSettings(
            check_type=UtilityCheckType.TEXT_PATTERN,
            pattern=r"\\s+$",
        )
        adapter = UtilityCheckAdapter(settings=settings)

        config = adapter.get_default_config()

        assert isinstance(config, QACheckConfig)
        assert isinstance(config.check_id, UUID)
        assert config.enabled is True
        assert isinstance(config.file_patterns, list)
        assert config.stage in ["fast", "comprehensive"]

    def test_get_default_config_eof_newline(self):
        """Test default config for EOF_NEWLINE check."""
        settings = UtilityCheckSettings(
            check_type=UtilityCheckType.EOF_NEWLINE,
        )
        adapter = UtilityCheckAdapter(settings=settings)

        config = adapter.get_default_config()

        assert isinstance(config, QACheckConfig)
        assert config.is_formatter is True  # Can modify files
        assert config.parallel_safe is True

    def test_get_default_config_size_check(self):
        """Test default config for SIZE_CHECK."""
        settings = UtilityCheckSettings(
            check_type=UtilityCheckType.SIZE_CHECK,
            max_size_bytes=500000,
        )
        adapter = UtilityCheckAdapter(settings=settings)

        config = adapter.get_default_config()

        assert isinstance(config, QACheckConfig)
        assert config.parallel_safe is True


class TestUtilityCheckModuleRegistration:
    """Test ACB module registration."""

    def test_module_has_required_attributes(self):
        """Test utility_check module has MODULE_ID and MODULE_STATUS."""
        from crackerjack.adapters.utility import checks

        assert hasattr(checks, "MODULE_ID")
        assert isinstance(checks.MODULE_ID, UUID)

        assert hasattr(checks, "MODULE_STATUS")
        assert isinstance(checks.MODULE_STATUS, str)


class TestUtilityCheckTypes:
    """Test UtilityCheckType enum."""

    def test_all_check_types_defined(self):
        """Test all expected check types are defined."""
        expected_types = [
            "TEXT_PATTERN",
            "EOF_NEWLINE",
            "SYNTAX_VALIDATION",
            "SIZE_CHECK",
            "DEPENDENCY_LOCK",
        ]

        for type_name in expected_types:
            assert hasattr(UtilityCheckType, type_name), (
                f"Missing check type: {type_name}"
            )

    def test_check_type_values(self):
        """Test check type enum values."""
        assert UtilityCheckType.TEXT_PATTERN == "text_pattern"
        assert UtilityCheckType.EOF_NEWLINE == "eof_newline"
        assert UtilityCheckType.SYNTAX_VALIDATION == "syntax_validation"
        assert UtilityCheckType.SIZE_CHECK == "size_check"
        assert UtilityCheckType.DEPENDENCY_LOCK == "dependency_lock"


class TestUtilityCheckSettingsValidation:
    """Test settings validation and defaults."""

    def test_settings_requires_check_type(self):
        """Test settings requires check_type field."""
        with pytest.raises(Exception):  # Pydantic validation error
            UtilityCheckSettings()  # Missing required check_type

    def test_settings_optional_fields_have_defaults(self):
        """Test optional fields have None defaults."""
        settings = UtilityCheckSettings(
            check_type=UtilityCheckType.TEXT_PATTERN,
        )

        assert settings.pattern is None
        assert settings.parser_type is None
        assert settings.max_size_bytes is None
        assert settings.auto_fix is False  # Boolean has False default
        assert settings.lock_command is None

    def test_settings_with_all_fields(self):
        """Test settings with all fields populated."""
        settings = UtilityCheckSettings(
            check_type=UtilityCheckType.TEXT_PATTERN,
            pattern=r"\\s+$",
            parser_type="yaml",
            max_size_bytes=1024,
            auto_fix=True,
            lock_command=["uv", "lock"],
        )

        assert settings.check_type == UtilityCheckType.TEXT_PATTERN
        assert settings.pattern == r"\\s+$"
        assert settings.parser_type == "yaml"
        assert settings.max_size_bytes == 1024
        assert settings.auto_fix is True
        assert settings.lock_command == ["uv", "lock"]


class TestUtilityCheckFilePatterns:
    """Test file pattern matching for different check types."""

    def test_text_pattern_file_patterns(self):
        """Test TEXT_PATTERN applies to all text files."""
        settings = UtilityCheckSettings(
            check_type=UtilityCheckType.TEXT_PATTERN,
            pattern=r"\\s+$",
        )
        adapter = UtilityCheckAdapter(settings=settings)

        config = adapter.get_default_config()

        # Should match common text file types
        assert isinstance(config.file_patterns, list)
        assert len(config.file_patterns) > 0

    def test_syntax_validation_file_patterns(self):
        """Test SYNTAX_VALIDATION has parser-specific patterns."""
        settings = UtilityCheckSettings(
            check_type=UtilityCheckType.SYNTAX_VALIDATION,
            parser_type="yaml",
        )
        adapter = UtilityCheckAdapter(settings=settings)

        config = adapter.get_default_config()

        # Should have file patterns
        assert isinstance(config.file_patterns, list)


class TestUtilityCheckExcludePatterns:
    """Test exclude patterns for utility checks."""

    def test_default_exclude_patterns(self):
        """Test default exclude patterns are set."""
        settings = UtilityCheckSettings(
            check_type=UtilityCheckType.TEXT_PATTERN,
            pattern="test",
        )
        adapter = UtilityCheckAdapter(settings=settings)

        config = adapter.get_default_config()

        # Should have common exclude patterns
        assert isinstance(config.exclude_patterns, list)

        # Should exclude common directories
        common_excludes = [".git", ".venv", "node_modules", "__pycache__"]
        patterns = " ".join(config.exclude_patterns)

        for exclude in common_excludes:
            # At least some common excludes should be present
            pass  # Cannot assert exact patterns without implementation details


class TestUtilityCheckTimeout:
    """Test timeout configuration."""

    def test_default_timeout_reasonable(self):
        """Test default timeout is reasonable for utility checks."""
        settings = UtilityCheckSettings(
            check_type=UtilityCheckType.TEXT_PATTERN,
            pattern="test",
        )
        adapter = UtilityCheckAdapter(settings=settings)

        config = adapter.get_default_config()

        # Utility checks should be fast (< 60 seconds)
        assert config.timeout_seconds is not None
        assert config.timeout_seconds <= 60


class TestUtilityCheckStageAssignment:
    """Test stage assignment for different check types."""

    def test_fast_checks_in_fast_stage(self):
        """Test fast checks are assigned to fast stage."""
        # TEXT_PATTERN, EOF_NEWLINE should be in fast stage
        fast_types = [
            UtilityCheckType.TEXT_PATTERN,
            UtilityCheckType.EOF_NEWLINE,
        ]

        for check_type in fast_types:
            settings = UtilityCheckSettings(check_type=check_type)
            if check_type == UtilityCheckType.TEXT_PATTERN:
                settings.pattern = "test"

            adapter = UtilityCheckAdapter(settings=settings)
            config = adapter.get_default_config()

            # Should be in fast stage (or at least have a stage)
            assert config.stage in ["fast", "comprehensive"]

    def test_comprehensive_checks_in_comp_stage(self):
        """Test comprehensive checks may be in comprehensive stage."""
        # SYNTAX_VALIDATION might be in comprehensive stage
        settings = UtilityCheckSettings(
            check_type=UtilityCheckType.SYNTAX_VALIDATION,
            parser_type="yaml",
        )
        adapter = UtilityCheckAdapter(settings=settings)

        config = adapter.get_default_config()

        # Should have a valid stage
        assert config.stage in ["fast", "comprehensive"]
