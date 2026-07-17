from __future__ import annotations

import json
import logging
import typing as t
from pathlib import Path

logger = logging.getLogger(__name__)


def register_doc_tools(mcp_app: t.Any) -> None:
    _register_frontmatter_validate_tool(mcp_app)


def _register_frontmatter_validate_tool(mcp_app: t.Any) -> None:
    @mcp_app.tool()
    async def crackerjack_doc_frontmatter_validate(
        pkg_path: str = ".",
        strict: bool = False,
        allow_nonstandard: bool = True,
        validate_links: bool = False,
        store: str | None = None,
    ) -> str:
        """Validate YAML frontmatter across the docs/ tree. Returns JSON.

        Args:
            pkg_path: Repo root to validate. Defaults to "." (current working directory).
            strict: Treat warnings as errors.
            allow_nonstandard: Accept legacy non-canonical frontmatter (default True).
            validate_links: Also check cross-references in `superseded_by` / `blocks_on`.
            store: Limit scan to a single store (e.g. "docs/plans/").

        Returns:
            JSON string with keys: success, files_scanned, errors, warnings, duration_ms.
        """
        from crackerjack.services.frontmatter_validator import (
            FrontmatterValidator,
            FrontmatterValidationError,
        )

        validator = FrontmatterValidator(pkg_path=Path(pkg_path))
        try:
            result = validator.validate(
                strict=strict,
                allow_nonstandard=allow_nonstandard,
                validate_links=validate_links,
                store=store,
            )
        except FrontmatterValidationError as exc:
            payload = {
                "success": False,
                "reason": exc.reason,
                "errors": [e.__dict__ for e in (exc.result.errors if exc.result else [])],
            }
            return json.dumps(payload, indent=2)

        return json.dumps(
            {
                "success": result.success,
                "files_scanned": result.files_scanned,
                "errors": [e.__dict__ for e in result.errors],
                "warnings": [w.__dict__ for w in result.warnings],
                "duration_ms": result.duration_ms,
            },
            indent=2,
        )
