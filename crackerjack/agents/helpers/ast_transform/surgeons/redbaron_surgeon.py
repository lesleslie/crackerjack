from pathlib import Path

from crackerjack.agents.helpers.ast_transform.surgeons.base import (
    BaseSurgeon,
    TransformResult,
)


class RedbaronSurgeon(BaseSurgeon):
    @property
    def name(self) -> str:
        return "redbaron"

    def apply(
        self,
        code: str,
        match_info: dict,
        file_path: Path | None = None,
    ) -> TransformResult:
        _ = match_info.get("type", "")

        return TransformResult(
            success=False,
            error_message=(
                "RedbaronSurgeon has limitations with complex transformations. "
                "Consider using LibcstSurgeon output or manual review."
            ),
        )

    def can_handle(self, match_info: dict) -> bool:

        return False

    def extract_comments(self, code: str) -> list[tuple[int, str]]:
        try:
            from redbaron import RedBaron

            fst = RedBaron(code)
            comments = []

            for comment in fst.find_all("CommentNode"):
                line = comment.absolute_bounding_box.top_left.line
                comments.append((line, comment.dumps()))

            return comments
        except Exception:
            return []
