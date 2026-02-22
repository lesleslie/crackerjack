"""Redbaron-based surgeon for AST transformations.

Uses redbaron (FST - Full Syntax Tree) for exact formatting preservation.
This is the fallback surgeon when libcst produces valid but poorly formatted code.

NOTE: This surgeon has limitations with complex transformations due to how
redbaron handles indentation in replace operations. It works best for simple
early_return patterns. For complex cases, libcst is preferred.

Known Limitations:
- Mixed indentation in replacement strings can cause content loss
- Complex nested structures may not transform correctly
- Best used as fallback when libcst fails validation due to formatting

For most cases, the LibcstSurgeon should be preferred.
"""

from pathlib import Path

from crackerjack.agents.helpers.ast_transform.surgeons.base import (
    BaseSurgeon,
    TransformResult,
)


class RedbaronSurgeon(BaseSurgeon):
    """Fallback surgeon using redbaron for exact formatting preservation.

    This surgeon is used as a fallback when libcst produces valid code but
    with formatting issues. It attempts to preserve comments and exact formatting.

    When to use:
    - Libcst produces valid code but loses comments
    - Simple early_return patterns where comment preservation is critical

    Limitations:
    - Complex transformations may not work correctly
    - Some indentation patterns may be lost
    - Less actively maintained (last release 2022)
    """

    @property
    def name(self) -> str:
        return "redbaron"

    def apply(
        self,
        code: str,
        match_info: dict,
        file_path: Path | None = None,
    ) -> TransformResult:
        """Apply transformation using redbaron.

        Args:
            code: Original source code
            match_info: Pattern match information
            file_path: Optional file path for error reporting

        Returns:
            TransformResult with transformed code or error
        """
        _ = match_info.get("type", "")  # Pattern type (not used in stub)

        # Note: Due to redbaron's limitations with indentation handling,
        # we delegate to libcst for actual transformation and only use
        # redbaron for extracting comment information to preserve.
        # This is a simplified implementation that can be enhanced later.

        # For now, indicate that this surgeon cannot handle the transformation
        # and let the engine fall back to manual review or libcst result
        return TransformResult(
            success=False,
            error_message=(
                "RedbaronSurgeon has limitations with complex transformations. "
                "Consider using LibcstSurgeon output or manual review."
            ),
        )

    def can_handle(self, match_info: dict) -> bool:
        """Check if this surgeon can handle the given match."""
        # Currently disabled due to indentation handling limitations
        return False

    def extract_comments(self, code: str) -> list[tuple[int, str]]:
        """Extract all comments from code with their line numbers.

        This is a utility method that can be used to preserve comments
        when applying transformations with other surgeons.

        Args:
            code: Source code

        Returns:
            List of (line_number, comment_text) tuples
        """
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
