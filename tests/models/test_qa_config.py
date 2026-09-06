"""Tests for qa_config module."""

from __future__ import annotations

from uuid import UUID

import pytest
from pydantic import ValidationError

from crackerjack.models.qa_config import QACheckConfig
from crackerjack.models.qa_results import QACheckType


class TestQACheckConfig:
    """Tests for QACheckConfig Pydantic model."""

    def test_minimal_qa_check_config(self) -> None:
        """Verify minimal QACheckConfig creation."""
        check_id = UUID("12345678-1234-5678-1234-567812345678")
        config = QACheckConfig(
            check_id=check_id,
            check_name="ruff-lint",
            check_type=QACheckType.LINT,
        )
        assert config.check_id == check_id
        assert config.check_name == "ruff-lint"
        assert config.check_type == QACheckType.LINT
        assert config.enabled is True
        assert config.file_patterns == []
        assert config.exclude_patterns == []
        assert config.timeout_seconds == 300
        assert config.retry_on_failure is False
        assert config.is_formatter is False
        assert config.parallel_safe is True
        assert config.stage == "fast"
        assert config.settings == {}

    def test_qa_check_config_full(self) -> None:
        """Verify QACheckConfig with all fields."""
        check_id = UUID("87654321-4321-8765-4321-876543218765")
        config = QACheckConfig(
            check_id=check_id,
            check_name="ruff-format",
            check_type=QACheckType.FORMAT,
            enabled=False,
            file_patterns=["src/**/*.py", "tests/**/*.py"],
            exclude_patterns=["**/migrations/**"],
            timeout_seconds=60,
            retry_on_failure=True,
            is_formatter=True,
            parallel_safe=False,
            stage="comprehensive",
            settings={"line-length": 100, "target-version": "py313"},
        )
        assert config.check_id == check_id
        assert config.check_name == "ruff-format"
        assert config.check_type == QACheckType.FORMAT
        assert config.enabled is False
        assert config.file_patterns == ["src/**/*.py", "tests/**/*.py"]
        assert config.exclude_patterns == ["**/migrations/**"]
        assert config.timeout_seconds == 60
        assert config.retry_on_failure is True
        assert config.is_formatter is True
        assert config.parallel_safe is False
        assert config.stage == "comprehensive"
        assert config.settings == {"line-length": 100, "target-version": "py313"}

    def test_qa_check_config_all_check_types(self) -> None:
        """Verify QACheckConfig works with all QACheckType values."""
        check_id = UUID("11111111-1111-1111-1111-111111111111")
        for check_type in QACheckType:
            config = QACheckConfig(
                check_id=check_id,
                check_name=f"check-{check_type.value}",
                check_type=check_type,
            )
            assert config.check_type == check_type

    def test_qa_check_config_timeout_validation(self) -> None:
        """Verify timeout_seconds must be greater than 0."""
        check_id = UUID("22222222-2222-2222-2222-222222222222")

        # Valid timeout values
        QACheckConfig(
            check_id=check_id,
            check_name="test",
            check_type=QACheckType.LINT,
            timeout_seconds=1,
        )
        QACheckConfig(
            check_id=check_id,
            check_name="test",
            check_type=QACheckType.LINT,
            timeout_seconds=600,
        )

        # Invalid timeout (0 or negative)
        with pytest.raises(ValidationError):
            QACheckConfig(
                check_id=check_id,
                check_name="test",
                check_type=QACheckType.LINT,
                timeout_seconds=0,
            )

    def test_qa_check_config_is_fast_stage_property(self) -> None:
        """Verify is_fast_stage property."""
        check_id = UUID("33333333-3333-3333-3333-333333333333")

        config = QACheckConfig(
            check_id=check_id,
            check_name="test",
            check_type=QACheckType.LINT,
            stage="fast",
        )
        assert config.is_fast_stage is True
        assert config.is_comprehensive_stage is False

    def test_qa_check_config_is_comprehensive_stage_property(self) -> None:
        """Verify is_comprehensive_stage property."""
        check_id = UUID("44444444-4444-4444-4444-444444444444")

        config = QACheckConfig(
            check_id=check_id,
            check_name="test",
            check_type=QACheckType.LINT,
            stage="comprehensive",
        )
        assert config.is_comprehensive_stage is True
        assert config.is_fast_stage is False

    def test_qa_check_config_stage_property_both_false(self) -> None:
        """Verify both stage properties false with different stage."""
        check_id = UUID("55555555-5555-5555-5555-555555555555")

        config = QACheckConfig(
            check_id=check_id,
            check_name="test",
            check_type=QACheckType.LINT,
            stage="other",
        )
        assert config.is_fast_stage is False
        assert config.is_comprehensive_stage is False

    def test_qa_check_config_name_property(self) -> None:
        """Verify name property returns check_name."""
        check_id = UUID("66666666-6666-6666-6666-666666666666")

        config = QACheckConfig(
            check_id=check_id,
            check_name="mypy-check",
            check_type=QACheckType.TYPE,
        )
        assert config.name == "mypy-check"
        assert config.name == config.check_name

    def test_qa_check_config_formatter_flag(self) -> None:
        """Verify is_formatter flag."""
        check_id = UUID("77777777-7777-7777-7777-777777777777")

        # Formatter
        formatter_config = QACheckConfig(
            check_id=check_id,
            check_name="black",
            check_type=QACheckType.FORMAT,
            is_formatter=True,
        )
        assert formatter_config.is_formatter is True

        # Non-formatter
        linter_config = QACheckConfig(
            check_id=check_id,
            check_name="flake8",
            check_type=QACheckType.LINT,
            is_formatter=False,
        )
        assert linter_config.is_formatter is False

    def test_qa_check_config_parallel_safe_flag(self) -> None:
        """Verify parallel_safe flag."""
        check_id = UUID("88888888-8888-8888-8888-888888888888")

        # Parallel safe
        parallel_config = QACheckConfig(
            check_id=check_id,
            check_name="ruff",
            check_type=QACheckType.LINT,
            parallel_safe=True,
        )
        assert parallel_config.parallel_safe is True

        # Not parallel safe
        serial_config = QACheckConfig(
            check_id=check_id,
            check_name="pylint",
            check_type=QACheckType.LINT,
            parallel_safe=False,
        )
        assert serial_config.parallel_safe is False

    def test_qa_check_config_file_patterns(self) -> None:
        """Verify file_patterns list."""
        check_id = UUID("99999999-9999-9999-9999-999999999999")

        patterns = [
            "src/**/*.py",
            "tests/**/*.py",
            "docs/**/*.py",
        ]
        config = QACheckConfig(
            check_id=check_id,
            check_name="test",
            check_type=QACheckType.LINT,
            file_patterns=patterns,
        )
        assert config.file_patterns == patterns
        assert len(config.file_patterns) == 3

    def test_qa_check_config_exclude_patterns(self) -> None:
        """Verify exclude_patterns list."""
        check_id = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")

        exclude = [
            "**/migrations/**",
            "**/venv/**",
            "**/__pycache__/**",
        ]
        config = QACheckConfig(
            check_id=check_id,
            check_name="test",
            check_type=QACheckType.LINT,
            exclude_patterns=exclude,
        )
        assert config.exclude_patterns == exclude

    def test_qa_check_config_settings_dict(self) -> None:
        """Verify settings dictionary."""
        check_id = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")

        settings = {
            "line-length": 100,
            "target-version": "py313",
            "extend-ignore": "E203,W503",
            "max-complexity": 10,
        }
        config = QACheckConfig(
            check_id=check_id,
            check_name="test",
            check_type=QACheckType.LINT,
            settings=settings,
        )
        assert config.settings == settings
        assert config.settings["line-length"] == 100
        assert config.settings["max-complexity"] == 10

    def test_qa_check_config_enabled_flag(self) -> None:
        """Verify enabled flag."""
        check_id = UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")

        enabled = QACheckConfig(
            check_id=check_id,
            check_name="enabled-check",
            check_type=QACheckType.LINT,
            enabled=True,
        )
        assert enabled.enabled is True

        disabled = QACheckConfig(
            check_id=check_id,
            check_name="disabled-check",
            check_type=QACheckType.LINT,
            enabled=False,
        )
        assert disabled.enabled is False

    def test_qa_check_config_retry_on_failure_flag(self) -> None:
        """Verify retry_on_failure flag."""
        check_id = UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")

        # With retry
        with_retry = QACheckConfig(
            check_id=check_id,
            check_name="test",
            check_type=QACheckType.LINT,
            retry_on_failure=True,
        )
        assert with_retry.retry_on_failure is True

        # Without retry
        without_retry = QACheckConfig(
            check_id=check_id,
            check_name="test",
            check_type=QACheckType.LINT,
            retry_on_failure=False,
        )
        assert without_retry.retry_on_failure is False

    def test_qa_check_config_model_dump(self) -> None:
        """Verify model_dump() serialization."""
        check_id = UUID("eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee")
        config = QACheckConfig(
            check_id=check_id,
            check_name="test-check",
            check_type=QACheckType.LINT,
            timeout_seconds=120,
            settings={"key": "value"},
        )
        data = config.model_dump()

        assert isinstance(data, dict)
        assert data["check_id"] == check_id
        assert data["check_name"] == "test-check"
        assert data["check_type"] == QACheckType.LINT
        assert data["timeout_seconds"] == 120
        assert data["settings"] == {"key": "value"}

    def test_qa_check_config_serialization(self) -> None:
        """Verify JSON serialization."""
        check_id = UUID("ffffffff-ffff-ffff-ffff-ffffffffffff")
        config = QACheckConfig(
            check_id=check_id,
            check_name="json-check",
            check_type=QACheckType.FORMAT,
            stage="comprehensive",
        )
        data = config.model_dump(mode="json")

        assert isinstance(data["check_id"], str)
        assert data["check_name"] == "json-check"
        assert isinstance(data["check_type"], str)
        assert data["stage"] == "comprehensive"

    def test_qa_check_config_various_stages(self) -> None:
        """Verify QACheckConfig with various stage values."""
        check_id = UUID("12121212-1212-1212-1212-121212121212")

        stages = ["fast", "comprehensive", "custom"]
        for stage in stages:
            config = QACheckConfig(
                check_id=check_id,
                check_name="test",
                check_type=QACheckType.LINT,
                stage=stage,
            )
            assert config.stage == stage

    def test_qa_check_config_empty_patterns_and_settings(self) -> None:
        """Verify empty lists and dicts are properly initialized."""
        check_id = UUID("13131313-1313-1313-1313-131313131313")
        config = QACheckConfig(
            check_id=check_id,
            check_name="test",
            check_type=QACheckType.LINT,
        )

        assert config.file_patterns == []
        assert config.exclude_patterns == []
        assert config.settings == {}
        assert isinstance(config.file_patterns, list)
        assert isinstance(config.exclude_patterns, list)
        assert isinstance(config.settings, dict)

    def test_qa_check_config_property_return_lines_all_three_branches(
        self,
    ) -> None:
        """Exercise every property return line under both True and False cases.

        Pins coverage on lines 64, 68, 72 of qa_config.py. Each property must
        return both True and False to ensure full branch coverage of the
        equality comparisons and the direct attribute return.
        """
        check_id = UUID("14141414-1414-1414-1414-141414141414")

        # is_fast_stage == True
        fast = QACheckConfig(
            check_id=check_id,
            check_name="fast-check",
            check_type=QACheckType.LINT,
            stage="fast",
        )
        assert fast.is_fast_stage is True
        assert fast.is_comprehensive_stage is False  # exercises line 68 False

        # is_comprehensive_stage == True
        comprehensive = QACheckConfig(
            check_id=check_id,
            check_name="comprehensive-check",
            check_type=QACheckType.LINT,
            stage="comprehensive",
        )
        assert comprehensive.is_comprehensive_stage is True
        assert comprehensive.is_fast_stage is False  # exercises line 64 False

        # Custom stage: both properties False (default comparisons)
        custom = QACheckConfig(
            check_id=check_id,
            check_name="custom-check",
            check_type=QACheckType.LINT,
            stage="custom",
        )
        assert custom.is_fast_stage is False  # line 64 False branch
        assert custom.is_comprehensive_stage is False  # line 68 False branch

        # name property must always mirror check_name (line 72)
        assert fast.name == "fast-check"
        assert comprehensive.name == "comprehensive-check"
        assert custom.name == "custom-check"
        assert fast.name == fast.check_name
        assert comprehensive.name == comprehensive.check_name
        assert custom.name == custom.check_name

    def test_qa_check_config_default_stage_is_fast(self) -> None:
        """Verify default stage produces True for is_fast_stage property."""
        check_id = UUID("15151515-1515-1515-1515-151515151515")
        config = QACheckConfig(
            check_id=check_id,
            check_name="default-stage-check",
            check_type=QACheckType.LINT,
        )
        # Default stage is "fast" per the Field default
        assert config.stage == "fast"
        assert config.is_fast_stage is True
        assert config.is_comprehensive_stage is False

    def test_qa_check_config_round_trip_serialization(self) -> None:
        """Verify model_dump then model_validate reproduces an equal instance."""
        check_id = UUID("16161616-1616-1616-1616-161616161616")
        original = QACheckConfig(
            check_id=check_id,
            check_name="round-trip",
            check_type=QACheckType.LINT,
            enabled=False,
            file_patterns=["src/**/*.py"],
            exclude_patterns=["**/migrations/**"],
            timeout_seconds=120,
            retry_on_failure=True,
            is_formatter=True,
            parallel_safe=False,
            stage="comprehensive",
            settings={"line-length": 100},
        )

        # Dump and re-validate
        data = original.model_dump()
        restored = QACheckConfig.model_validate(data)

        # Field-by-field equality
        assert restored.check_id == original.check_id
        assert restored.check_name == original.check_name
        assert restored.check_type == original.check_type
        assert restored.enabled == original.enabled
        assert restored.file_patterns == original.file_patterns
        assert restored.exclude_patterns == original.exclude_patterns
        assert restored.timeout_seconds == original.timeout_seconds
        assert restored.retry_on_failure == original.retry_on_failure
        assert restored.is_formatter == original.is_formatter
        assert restored.parallel_safe == original.parallel_safe
        assert restored.stage == original.stage
        assert restored.settings == original.settings

    def test_qa_check_config_json_round_trip(self) -> None:
        """Verify JSON serialization round trip preserves all data."""
        check_id = UUID("17171717-1717-1717-1717-171717171717")
        original = QACheckConfig(
            check_id=check_id,
            check_name="json-round-trip",
            check_type=QACheckType.FORMAT,
            timeout_seconds=60,
            settings={"mode": "check"},
        )

        json_str = original.model_dump_json()
        restored = QACheckConfig.model_validate_json(json_str)

        assert restored.check_id == original.check_id
        assert restored.check_name == original.check_name
        assert restored.check_type == original.check_type
        assert restored.timeout_seconds == original.timeout_seconds
        assert restored.settings == original.settings

    def test_qa_check_config_equality(self) -> None:
        """Verify Pydantic-generated __eq__ compares all fields."""
        check_id = UUID("18181818-1818-1818-1818-181818181818")

        config_a = QACheckConfig(
            check_id=check_id,
            check_name="same",
            check_type=QACheckType.LINT,
            timeout_seconds=42,
        )
        config_b = QACheckConfig(
            check_id=check_id,
            check_name="same",
            check_type=QACheckType.LINT,
            timeout_seconds=42,
        )
        config_c = QACheckConfig(
            check_id=check_id,
            check_name="different",
            check_type=QACheckType.LINT,
            timeout_seconds=42,
        )

        # Equal instances are equal
        assert config_a == config_b
        # Different fields produce inequality
        assert config_a != config_c
        # Pydantic BaseModel is unhashable by default — verify that explicitly
        with pytest.raises(TypeError):
            hash(config_a)

    def test_qa_check_config_default_lists_are_independent(self) -> None:
        """Verify default_factory creates separate lists per instance.

        Ensures that mutating one instance's file_patterns/exclude_patterns
        does not affect another instance — a common default_factory pitfall.
        """
        check_id = UUID("19191919-1919-1919-1919-191919191919")

        first = QACheckConfig(
            check_id=check_id,
            check_name="first",
            check_type=QACheckType.LINT,
        )
        second = QACheckConfig(
            check_id=check_id,
            check_name="second",
            check_type=QACheckType.LINT,
        )

        first.file_patterns.append("**/*.py")
        first.exclude_patterns.append("**/.venv/**")
        first.settings["new_key"] = "new_value"

        assert second.file_patterns == []
        assert second.exclude_patterns == []
        assert second.settings == {}

    def test_qa_check_config_repr_contains_check_name(self) -> None:
        """Verify __repr__ exposes identifying fields for debugging."""
        check_id = UUID("20202020-2020-2020-2020-202020202020")
        config = QACheckConfig(
            check_id=check_id,
            check_name="repr-check",
            check_type=QACheckType.LINT,
        )
        text = repr(config)
        assert "repr-check" in text
        assert str(check_id) in text
