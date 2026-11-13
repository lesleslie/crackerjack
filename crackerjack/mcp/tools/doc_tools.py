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
        validate_links: bool = True,
        store: str | None = None,
    ) -> str:
        """Validate YAML frontmatter across the project's Markdown documents.

        Scans the files discovered by the frontmatter validator and checks
        them against the project's frontmatter schema, optionally
        validating links and tolerating nonstandard keys.

        Parameters
        ----------
        pkg_path
            Root directory to scan. Defaults to the current directory.
        strict
            Treat warnings as failures.
        allow_nonstandard
            Accept nonstandard frontmatter keys instead of flagging them.
        validate_links
            Also validate the links referenced by each document.
        store
            Optional documentation store to scan alongside the package files.

        Returns
        -------
        str
            JSON string with ``success``, ``files_scanned``, ``errors``,
            ``warnings`` and ``duration_ms``. On a validator crash it
            returns ``success`` false with a ``reason`` and the raw errors.
        """
        from crackerjack.services.frontmatter_validator import (
            FrontmatterValidationError,
            FrontmatterValidator,
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
                "errors": [
                    e.__dict__ for e in (exc.result.errors if exc.result else [])
                ],
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
