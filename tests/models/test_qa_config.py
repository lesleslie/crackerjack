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
