"""Tests for adapter_metadata module."""

from __future__ import annotations

from uuid import UUID

import pytest

from crackerjack.models.adapter_metadata import AdapterMetadata, AdapterStatus


class TestAdapterStatus:
    """Tests for AdapterStatus enum."""

    def test_enum_values(self) -> None:
        """Verify all AdapterStatus values."""
        assert AdapterStatus.STABLE.value == "stable"
        assert AdapterStatus.BETA.value == "beta"
        assert AdapterStatus.ALPHA.value == "alpha"
        assert AdapterStatus.DEPRECATED.value == "deprecated"

    def test_enum_members(self) -> None:
        """Verify all AdapterStatus members exist."""
        members = {member.value for member in AdapterStatus}
        assert members == {"stable", "beta", "alpha", "deprecated"}

    def test_enum_is_str_enum(self) -> None:
        """Verify AdapterStatus is a StrEnum."""
        # StrEnum members are also strings
        assert isinstance(AdapterStatus.STABLE, str)
        assert AdapterStatus.STABLE == "stable"

    def test_enum_iteration(self) -> None:
        """Verify can iterate over all statuses."""
        statuses = list(AdapterStatus)
        assert len(statuses) == 4
        assert AdapterStatus.STABLE in statuses
        assert AdapterStatus.BETA in statuses
        assert AdapterStatus.ALPHA in statuses
        assert AdapterStatus.DEPRECATED in statuses


class TestAdapterMetadata:
    """Tests for AdapterMetadata dataclass."""

    def test_minimal_adapter_metadata(self) -> None:
        """Verify minimal AdapterMetadata creation."""
        module_id = UUID("12345678-1234-5678-1234-567812345678")
        metadata = AdapterMetadata(
            module_id=module_id,
            name="TestAdapter",
            category="lint",
            version="1.0.0",
            status=AdapterStatus.STABLE,
        )
        assert metadata.module_id == module_id
        assert metadata.name == "TestAdapter"
        assert metadata.category == "lint"
        assert metadata.version == "1.0.0"
        assert metadata.status == AdapterStatus.STABLE
        assert metadata.description == ""

    def test_adapter_metadata_full(self) -> None:
        """Verify AdapterMetadata with all fields."""
        module_id = UUID("87654321-4321-8765-4321-876543218765")
        metadata = AdapterMetadata(
            module_id=module_id,
            name="AdvancedAdapter",
            category="refactor",
            version="2.1.0",
            status=AdapterStatus.BETA,
            description="Advanced refactoring adapter",
        )
        assert metadata.module_id == module_id
        assert metadata.name == "AdvancedAdapter"
        assert metadata.category == "refactor"
        assert metadata.version == "2.1.0"
        assert metadata.status == AdapterStatus.BETA
        assert metadata.description == "Advanced refactoring adapter"

    def test_adapter_metadata_all_statuses(self) -> None:
        """Verify AdapterMetadata works with all status values."""
        module_id = UUID("11111111-1111-1111-1111-111111111111")
        for status in AdapterStatus:
            metadata = AdapterMetadata(
                module_id=module_id,
                name="TestAdapter",
                category="test",
                version="1.0",
                status=status,
            )
            assert metadata.status == status

    def test_adapter_metadata_to_dict(self) -> None:
        """Verify to_dict() method."""
        module_id = UUID("99999999-9999-9999-9999-999999999999")
        metadata = AdapterMetadata(
            module_id=module_id,
            name="DictAdapter",
            category="security",
            version="3.0.0",
            status=AdapterStatus.ALPHA,
            description="Security analysis adapter",
        )
        result = metadata.to_dict()

        assert isinstance(result, dict)
        assert result["module_id"] == "99999999-9999-9999-9999-999999999999"
        assert result["name"] == "DictAdapter"
        assert result["category"] == "security"
        assert result["version"] == "3.0.0"
        assert result["status"] == "alpha"
        assert result["description"] == "Security analysis adapter"

    def test_adapter_metadata_dict_method(self) -> None:
        """Verify dict() method delegates to to_dict()."""
        module_id = UUID("22222222-2222-2222-2222-222222222222")
        metadata = AdapterMetadata(
            module_id=module_id,
            name="AliasAdapter",
            category="format",
            version="1.5.0",
            status=AdapterStatus.STABLE,
        )
        dict_result = metadata.dict()
        to_dict_result = metadata.to_dict()

        assert dict_result == to_dict_result
        assert dict_result["name"] == "AliasAdapter"

    def test_adapter_metadata_str_representation(self) -> None:
        """Verify __str__ method."""
        module_id = UUID("33333333-3333-3333-3333-333333333333")
        metadata = AdapterMetadata(
            module_id=module_id,
            name="StrAdapter",
            category="test",
            version="2.0.1",
            status=AdapterStatus.BETA,
        )
        str_result = str(metadata)

        assert str_result == "StrAdapter v2.0.1 (beta)"

    def test_adapter_metadata_str_all_statuses(self) -> None:
        """Verify __str__ format with all statuses."""
        module_id = UUID("44444444-4444-4444-4444-444444444444")

        test_cases = [
            (AdapterStatus.STABLE, "MyAdapter v1.0 (stable)"),
            (AdapterStatus.BETA, "MyAdapter v1.0 (beta)"),
            (AdapterStatus.ALPHA, "MyAdapter v1.0 (alpha)"),
            (AdapterStatus.DEPRECATED, "MyAdapter v1.0 (deprecated)"),
        ]

        for status, expected_str in test_cases:
            metadata = AdapterMetadata(
                module_id=module_id,
                name="MyAdapter",
                category="test",
                version="1.0",
                status=status,
            )
            assert str(metadata) == expected_str

    def test_adapter_metadata_with_empty_description(self) -> None:
        """Verify AdapterMetadata with explicit empty description."""
        module_id = UUID("55555555-5555-5555-5555-555555555555")
        metadata = AdapterMetadata(
            module_id=module_id,
            name="NoDescAdapter",
            category="test",
            version="1.0",
            status=AdapterStatus.STABLE,
            description="",
        )
        assert metadata.description == ""
        assert metadata.to_dict()["description"] == ""

    def test_adapter_metadata_uuid_serialization(self) -> None:
        """Verify UUID is serialized as string in to_dict()."""
        module_id = UUID("66666666-6666-6666-6666-666666666666")
        metadata = AdapterMetadata(
            module_id=module_id,
            name="UUIDAdapter",
            category="test",
            version="1.0",
            status=AdapterStatus.STABLE,
        )
        result = metadata.to_dict()

        assert isinstance(result["module_id"], str)
        assert result["module_id"] == "66666666-6666-6666-6666-666666666666"

    def test_adapter_metadata_category_various(self) -> None:
        """Verify AdapterMetadata works with various categories."""
        module_id = UUID("77777777-7777-7777-7777-777777777777")
        categories = ["lint", "format", "refactor", "test", "security", "custom"]

        for category in categories:
            metadata = AdapterMetadata(
                module_id=module_id,
                name="TestAdapter",
                category=category,
                version="1.0",
                status=AdapterStatus.STABLE,
            )
            assert metadata.category == category
