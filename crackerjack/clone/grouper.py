from __future__ import annotations

import hashlib
from contextlib import suppress
from dataclasses import dataclass
from enum import IntEnum
from pathlib import Path
from typing import TYPE_CHECKING, Any

from oneiric.core.logging import get_logger

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)


class CloneType(IntEnum):
    EXACT = 1
    RENAMED = 2
    MODIFIED = 3
    SEMANTIC = 4

    @classmethod
    def from_pyscn(cls, type_int: int) -> CloneType:
        mapping = {
            0: cls.EXACT,
            1: cls.EXACT,
            2: cls.RENAMED,
            3: cls.MODIFIED,
            4: cls.SEMANTIC,
        }
        return mapping.get(type_int, cls.SEMANTIC)


@dataclass
class CloneLocation:
    file_path: Path
    start_line: int
    end_line: int
    start_col: int
    end_col: int

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CloneLocation:
        loc = data.get("location", data)
        return cls(
            file_path=Path(loc["file_path"]),
            start_line=loc["start_line"],
            end_line=loc["end_line"],
            start_col=loc.get("start_col", 0),
            end_col=loc.get("end_col", 0),
        )


@dataclass
class CloneGroup:
    group_id: str
    clone_type: CloneType
    similarity: float
    locations: list[CloneLocation]
    pattern_description: str
    line_count: int


class CloneGrouper:
    def __init__(self, dhara: Any | None = None) -> None:
        self._dhara = dhara

    def group_pairs(self, raw_pairs: list[dict[str, Any]]) -> list[CloneGroup]:
        groups: list[CloneGroup] = []
        for pair in raw_pairs:
            clone_type = CloneType.from_pyscn(pair.get("type", 1))
            similarity = float(pair.get("similarity", 0.0))

            loc1 = CloneLocation.from_dict(pair["clone1"])
            loc2 = CloneLocation.from_dict(pair["clone2"])
            line_count = max(
                loc1.end_line - loc1.start_line + 1,
                loc2.end_line - loc2.start_line + 1,
            )

            group_id = self._make_group_id(pair, clone_type, similarity)
            description = (
                f"Type {clone_type.value} clone between "
                f"{loc1.file_path.name} and {loc2.file_path.name}"
            )

            groups.append(
                CloneGroup(
                    group_id=group_id,
                    clone_type=clone_type,
                    similarity=similarity,
                    locations=[loc1, loc2],
                    pattern_description=description,
                    line_count=line_count,
                )
            )

        logger.info(
            "CloneGrouper: grouped %d pairs into %d groups", len(raw_pairs), len(groups)
        )
        return groups

    async def group_pairs_filtered(
        self, raw_pairs: list[dict[str, Any]]
    ) -> list[CloneGroup]:
        groups = self.group_pairs(raw_pairs)
        if self._dhara is None:
            return groups

        filtered: list[CloneGroup] = []
        for group in groups:
            with suppress(Exception):
                existing = await self._dhara.get_async(
                    f"clone-handled/{group.group_id}"
                )
                if existing:
                    logger.info(
                        "CloneGrouper: skipping handled group %s", group.group_id
                    )
                    continue
            filtered.append(group)

        return filtered

    @staticmethod
    def _make_group_id(
        pair: dict[str, Any], clone_type: CloneType, similarity: float
    ) -> str:
        loc1 = pair["clone1"].get("location", pair["clone1"])
        loc2 = pair["clone2"].get("location", pair["clone2"])
        key = (
            f"{loc1.get('file_path', '')}:{loc1.get('start_line', 0)}-{loc1.get('end_line', 0)}|"  # noqa: E501
            f"{loc2.get('file_path', '')}:{loc2.get('start_line', 0)}-{loc2.get('end_line', 0)}|"  # noqa: E501
            f"type{clone_type.value}"
        )
        return hashlib.sha256(key.encode()).hexdigest()[:16]
