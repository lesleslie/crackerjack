from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from crackerjack.clone.grouper import CloneGroup, CloneGrouper, CloneLocation, CloneType


@pytest.mark.unit
class TestCloneGrouperTypeMapping:
    def test_grouper_clusters_identical_blocks_as_type1(self) -> None:
        """Type 2 clone pairs (renamed vars) → CloneType.RENAMED (pyscn type 2)."""
        raw_pairs = [
            {
                "id": 1,
                "clone1": {
                    "location": {
                        "file_path": "a.py",
                        "start_line": 1,
                        "end_line": 10,
                        "start_col": 0,
                        "end_col": 50,
                    }
                },
                "clone2": {
                    "location": {
                        "file_path": "b.py",
                        "start_line": 5,
                        "end_line": 14,
                        "start_col": 0,
                        "end_col": 50,
                    }
                },
                "similarity": 1.0,
                "type": 1,
                "confidence": 1.0,
            }
        ]
        grouper = CloneGrouper()
        groups = grouper.group_pairs(raw_pairs)
        assert len(groups) == 1
        assert groups[0].clone_type == CloneType.EXACT

    def test_grouper_clusters_renamed_variables_as_type2(self) -> None:
        """pyscn type=2 clone pair → CloneType.RENAMED."""
        raw_pairs = [
            {
                "id": 1,
                "clone1": {
                    "location": {
                        "file_path": "a.py",
                        "start_line": 1,
                        "end_line": 17,
                        "start_col": 0,
                        "end_col": 66,
                    }
                },
                "clone2": {
                    "location": {
                        "file_path": "b.py",
                        "start_line": 1,
                        "end_line": 17,
                        "start_col": 0,
                        "end_col": 66,
                    }
                },
                "similarity": 0.991,
                "type": 2,
                "confidence": 0.95,
            }
        ]
        grouper = CloneGrouper()
        groups = grouper.group_pairs(raw_pairs)
        assert groups[0].clone_type == CloneType.RENAMED

    def test_grouper_assigns_group_ids_unique_per_cluster(self) -> None:
        """Each CloneGroup gets a unique group_id."""
        raw_pairs = [
            {
                "id": 1,
                "clone1": {
                    "location": {
                        "file_path": "a.py",
                        "start_line": 1,
                        "end_line": 10,
                        "start_col": 0,
                        "end_col": 50,
                    }
                },
                "clone2": {
                    "location": {
                        "file_path": "b.py",
                        "start_line": 1,
                        "end_line": 10,
                        "start_col": 0,
                        "end_col": 50,
                    }
                },
                "similarity": 1.0,
                "type": 1,
                "confidence": 1.0,
            },
            {
                "id": 2,
                "clone1": {
                    "location": {
                        "file_path": "c.py",
                        "start_line": 20,
                        "end_line": 35,
                        "start_col": 0,
                        "end_col": 60,
                    }
                },
                "clone2": {
                    "location": {
                        "file_path": "d.py",
                        "start_line": 5,
                        "end_line": 20,
                        "start_col": 0,
                        "end_col": 60,
                    }
                },
                "similarity": 0.85,
                "type": 3,
                "confidence": 0.80,
            },
        ]
        grouper = CloneGrouper()
        groups = grouper.group_pairs(raw_pairs)
        assert len(groups) == 2
        group_ids = {g.group_id for g in groups}
        assert len(group_ids) == 2, "group_ids must be unique"

    async def test_grouper_skips_group_with_handled_dhara_key(self) -> None:
        """Groups already handled (dhara.get_async returns data) must be skipped."""
        raw_pairs = [
            {
                "id": 1,
                "clone1": {
                    "location": {
                        "file_path": "a.py",
                        "start_line": 1,
                        "end_line": 10,
                        "start_col": 0,
                        "end_col": 50,
                    }
                },
                "clone2": {
                    "location": {
                        "file_path": "b.py",
                        "start_line": 1,
                        "end_line": 10,
                        "start_col": 0,
                        "end_col": 50,
                    }
                },
                "similarity": 1.0,
                "type": 1,
                "confidence": 1.0,
            }
        ]
        mock_dhara = AsyncMock()
        mock_dhara.get_async = AsyncMock(
            return_value={"refactored_at": "2026-06-01T00:00:00Z"}
        )

        grouper = CloneGrouper(dhara=mock_dhara)
        groups = await grouper.group_pairs_filtered(raw_pairs)
        assert groups == [], "Groups with Dhara handled key must be skipped"


@pytest.mark.unit
class TestCloneGrouperDataModel:
    def test_clone_location_from_dict(self) -> None:
        loc = CloneLocation(
            file_path=Path("crackerjack/core/app.py"),
            start_line=10,
            end_line=25,
            start_col=0,
            end_col=80,
        )
        assert loc.start_line == 10
        assert loc.file_path == Path("crackerjack/core/app.py")

    def test_clone_group_has_line_count(self) -> None:
        loc1 = CloneLocation(
            file_path=Path("a.py"), start_line=1, end_line=17, start_col=0, end_col=66
        )
        loc2 = CloneLocation(
            file_path=Path("b.py"), start_line=1, end_line=17, start_col=0, end_col=66
        )
        group = CloneGroup(
            group_id="test-id",
            clone_type=CloneType.RENAMED,
            similarity=0.991,
            locations=[loc1, loc2],
            pattern_description="Renamed variable clone",
            line_count=17,
        )
        assert group.line_count == 17
        assert len(group.locations) == 2
