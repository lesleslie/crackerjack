from __future__ import annotations

import uuid

import pytest


@pytest.mark.unit
class TestUuidUtilsAvailability:
    """uuid-utils must be importable and provide uuid4/uuid7."""

    def test_uuid_utils_uuid4_importable(self) -> None:
        from uuid_utils import uuid4

        result = uuid4()
        assert result is not None

    def test_uuid_utils_uuid7_importable(self) -> None:
        from uuid_utils import uuid7

        result = uuid7()
        assert result is not None

    def test_uuid7_produces_time_ordered_ids(self) -> None:
        """UUID v7 is monotonically increasing — two successive IDs must be ordered."""
        from uuid_utils import uuid7

        id1 = uuid7()
        id2 = uuid7()
        # Time-ordered: string comparison reflects temporal order in UUID v7
        assert str(id1) <= str(id2)

    def test_uuid7_boundary_converts_to_stdlib_uuid(self) -> None:
        """At model boundaries, uuid_utils.UUID must convert to stdlib uuid.UUID."""
        from uuid_utils import uuid7

        uid = uuid7()
        stdlib_uuid = uuid.UUID(str(uid))
        assert isinstance(stdlib_uuid, uuid.UUID)

    def test_uuid7_not_subclass_of_stdlib_uuid(self) -> None:
        """m-new-7: uuid_utils.UUID is NOT a subclass of uuid.UUID — must convert explicitly."""
        from uuid_utils import uuid7

        uid = uuid7()
        assert not isinstance(uid, uuid.UUID), (
            "uuid_utils.UUID is not a stdlib uuid.UUID subclass — "
            "use uuid.UUID(str(uid)) at model boundaries"
        )

    def test_uuid_utils_uuid4_matches_stdlib_format(self) -> None:
        """Generated UUIDs must conform to standard 8-4-4-4-12 hex format."""
        from uuid_utils import uuid4

        uid = uuid4()
        parts = str(uid).split("-")
        assert len(parts) == 5
        assert len(parts[0]) == 8
        assert len(parts[1]) == 4
        assert len(parts[4]) == 12


@pytest.mark.unit
class TestAgentBaseUsesUuidUtils:
    """agents/base.py should use uuid_utils.uuid4 for issue ID generation."""

    def test_issue_id_prefix_format(self) -> None:
        """Issue IDs must start with 'issue_' and contain hex characters."""
        from crackerjack.agents.base import Issue, IssueType, Priority

        issue = Issue(
            type=IssueType.FORMATTING,
            severity=Priority.LOW,
            message="test issue",
        )
        assert issue.id.startswith("issue_")
        hex_part = issue.id[len("issue_"):]
        assert all(c in "0123456789abcdef" for c in hex_part)
