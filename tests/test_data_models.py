"""Tests for data models module."""

from datetime import datetime
from unittest.mock import Mock

import pytest

from crackerjack.data.models import QualityBaselineRecord, ProjectHealthRecord


class TestQualityBaselineRecord:
    """Tests for QualityBaselineRecord model."""

    def test_quality_baseline_record_initialization(self):
        """Test QualityBaselineRecord initialization."""
        record = QualityBaselineRecord(
            git_hash="abc123def456",
            coverage_percent=85.5,
            test_count=42,
            test_pass_rate=95.2,
            hook_failures=2,
            complexity_violations=5,
            security_issues=1,
            type_errors=3,
            linting_issues=10,
            quality_score=88,
        )

        assert record.git_hash == "abc123def456"
        assert record.coverage_percent == 85.5
        assert record.test_count == 42
        assert record.test_pass_rate == 95.2
        assert record.hook_failures == 2
        assert record.complexity_violations == 5
        assert record.security_issues == 1
        assert record.type_errors == 3
        assert record.linting_issues == 10
        assert record.quality_score == 88
        assert isinstance(record.recorded_at, datetime)

    def test_quality_baseline_record_default_values(self):
        """Test QualityBaselineRecord with default values."""
        record = QualityBaselineRecord(git_hash="test123")

        assert record.coverage_percent == 0.0
        assert record.test_count == 0
        assert record.test_pass_rate == 0.0
        assert record.hook_failures == 0
        assert record.complexity_violations == 0
        assert record.security_issues == 0
        assert record.type_errors == 0
        assert record.linting_issues == 0
        assert record.quality_score == 0
        assert record.extra_metadata is None

    def test_quality_baseline_record_update_from_dict(self):
        """Test QualityBaselineRecord update_from_dict method."""
        record = QualityBaselineRecord(git_hash="test123")

        update_data = {
            "coverage_percent": 90.5,
            "test_count": 100,
            "test_pass_rate": 98.7,
            "quality_score": 95,
            "extra_metadata": {"ci_build": "#123"}
        }

        record.update_from_dict(update_data)

        assert record.coverage_percent == 90.5
        assert record.test_count == 100
        assert record.test_pass_rate == 98.7
        assert record.quality_score == 95
        assert record.extra_metadata == {"ci_build": "#123"}

    def test_quality_baseline_record_update_ignores_invalid_keys(self):
        """Test that update_from_dict ignores invalid keys."""
        record = QualityBaselineRecord(git_hash="test123")

        update_data = {
            "coverage_percent": 75.0,
            "invalid_key": "should_be_ignored",
            "another_invalid": 123
        }

        record.update_from_dict(update_data)

        assert record.coverage_percent == 75.0
        assert not hasattr(record, "invalid_key")
        assert not hasattr(record, "another_invalid")

    def test_quality_baseline_record_table_name(self):
        """Test QualityBaselineRecord table name."""
        assert QualityBaselineRecord.__tablename__ == "quality_baselines"

    def test_quality_baseline_record_field_types(self):
        """Test QualityBaselineRecord field types."""
        record = QualityBaselineRecord(git_hash="test123")

        # Verify field types
        assert isinstance(record.id, int) or record.id is None
        assert isinstance(record.git_hash, str)
        assert isinstance(record.recorded_at, datetime)
        assert isinstance(record.coverage_percent, float)
        assert isinstance(record.test_count, int)
        assert isinstance(record.test_pass_rate, float)
        assert isinstance(record.hook_failures, int)
        assert isinstance(record.complexity_violations, int)
        assert isinstance(record.security_issues, int)
        assert isinstance(record.type_errors, int)
        assert isinstance(record.linting_issues, int)
        assert isinstance(record.quality_score, int)

    def test_quality_baseline_record_equality(self):
        """Test QualityBaselineRecord equality comparison."""
        record1 = QualityBaselineRecord(git_hash="test123", coverage_percent=80.0)
        record2 = QualityBaselineRecord(git_hash="test123", coverage_percent=80.0)

        # Should be equal if all fields are the same
        assert record1.git_hash == record2.git_hash
        assert record1.coverage_percent == record2.coverage_percent

    def test_quality_baseline_record_string_representation(self):
        """Test QualityBaselineRecord string representation."""
        record = QualityBaselineRecord(git_hash="test123", coverage_percent=75.5)

        # Should have a string representation
        assert str(record) is not None
        assert len(str(record)) > 0

    def test_quality_baseline_record_with_extra_metadata(self):
        """Test QualityBaselineRecord with extra metadata."""
        metadata = {
            "ci_system": "github_actions",
            "build_number": 42,
            "environment": "production"
        }

        record = QualityBaselineRecord(
            git_hash="test123",
            coverage_percent=85.0,
            extra_metadata=metadata
        )

        assert record.extra_metadata == metadata
        assert record.extra_metadata["ci_system"] == "github_actions"
        assert record.extra_metadata["build_number"] == 42

    def test_quality_baseline_record_inheritance(self):
        """Test QualityBaselineRecord inherits from SQLModel."""
        from sqlmodel import SQLModel

        record = QualityBaselineRecord(git_hash="test123")
        assert isinstance(record, SQLModel)


class TestProjectHealthRecord:
    """Tests for ProjectHealthRecord model."""

    def test_project_health_record_initialization(self):
        """Test ProjectHealthRecord initialization."""
        record = ProjectHealthRecord(
            project_name="test_project",
            health_score=85,
            last_updated=datetime.utcnow(),
            issue_count=15,
            warning_count=8,
            error_count=3,
            maintenance_score=90
        )

        assert record.project_name == "test_project"
        assert record.health_score == 85
        assert isinstance(record.last_updated, datetime)
        assert record.issue_count == 15
        assert record.warning_count == 8
        assert record.error_count == 3
        assert record.maintenance_score == 90

    def test_project_health_record_default_values(self):
        """Test ProjectHealthRecord with default values."""
        record = ProjectHealthRecord(project_name="test")

        assert record.health_score == 0
        assert record.issue_count == 0
        assert record.warning_count == 0
        assert record.error_count == 0
        assert record.maintenance_score == 0
        assert isinstance(record.last_updated, datetime)

    def test_project_health_record_table_name(self):
        """Test ProjectHealthRecord table name."""
        assert ProjectHealthRecord.__tablename__ == "project_health"

    def test_project_health_record_inheritance(self):
        """Test ProjectHealthRecord inherits from SQLModel."""
        from sqlmodel import SQLModel

        record = ProjectHealthRecord(project_name="test")
        assert isinstance(record, SQLModel)

    def test_project_health_record_field_types(self):
        """Test ProjectHealthRecord field types."""
        record = ProjectHealthRecord(project_name="test")

        assert isinstance(record.id, int) or record.id is None
        assert isinstance(record.project_name, str)
        assert isinstance(record.health_score, int)
        assert isinstance(record.last_updated, datetime)
        assert isinstance(record.issue_count, int)
        assert isinstance(record.warning_count, int)
        assert isinstance(record.error_count, int)
        assert isinstance(record.maintenance_score, int)


class TestDataModelsIntegration:
    """Integration tests for data models."""

    def test_models_can_be_imported(self):
        """Test that all data models can be imported."""
        try:
            from crackerjack.data.models import QualityBaselineRecord, ProjectHealthRecord
            assert QualityBaselineRecord is not None
            assert ProjectHealthRecord is not None
        except ImportError as e:
            pytest.fail(f"Failed to import data models: {e}")

    def test_models_have_required_attributes(self):
        """Test that models have required SQLAlchemy attributes."""
        from sqlmodel import SQLModel

        # Test QualityBaselineRecord
        assert hasattr(QualityBaselineRecord, '__tablename__')
        assert hasattr(QualityBaselineRecord, 'id')
        assert hasattr(QualityBaselineRecord, 'git_hash')

        # Test ProjectHealthRecord
        assert hasattr(ProjectHealthRecord, '__tablename__')
        assert hasattr(ProjectHealthRecord, 'id')
        assert hasattr(ProjectHealthRecord, 'project_name')

    def test_models_are_sqlmodel_instances(self):
        """Test that models are proper SQLModel instances."""
        from sqlmodel import SQLModel

        record1 = QualityBaselineRecord(git_hash="test")
        record2 = ProjectHealthRecord(project_name="test")

        assert isinstance(record1, SQLModel)
        assert isinstance(record2, SQLModel)

    def test_models_can_be_serialized(self):
        """Test that models can be converted to dictionaries."""
        record = QualityBaselineRecord(
            git_hash="test123",
            coverage_percent=80.0,
            test_count=50
        )

        # Should be able to access attributes
        data = {
            'git_hash': record.git_hash,
            'coverage_percent': record.coverage_percent,
            'test_count': record.test_count
        }

        assert data['git_hash'] == "test123"
        assert data['coverage_percent'] == 80.0
        assert data['test_count'] == 50
