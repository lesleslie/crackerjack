"""Web language adapter (CSS / HTML / JS / TS).

The Web adapter activates only on projects with `package.json` at root or an
explicit `[tool.crackerjack.web] enabled = true` opt-in. This prevents
false-positive activation on Django / Sphinx / MkDocs Python projects.

Phase 4 ships CLI-only hooks (no Python fallbacks) — Swift/Kotlin precedent.
"""
from __future__ import annotations

import tomllib
from pathlib import Path

from crackerjack.adapters.base import Capabilities, LanguageAdapterBase
from crackerjack.adapters.web.hooks import web_hooks


def package_json_present(project_root: Path) -> bool:
    """Return True if `package.json` exists at the project root."""
    return (project_root / "package.json").is_file()


def _opt_in_enabled(project_root: Path) -> bool:
    """Return True if `[tool.crackerjack.web] enabled = true` in pyproject.toml."""
    pyproject = project_root / "pyproject.toml"
    if not pyproject.is_file():
        return False
    try:
        with pyproject.open("rb") as f:
            data = tomllib.load(f)
    except (OSError, tomllib.TOMLDecodeError):
        return False
    tool = data.get("tool", {})
    crackerjack = tool.get("crackerjack", {})
    web = crackerjack.get("web", {})
    return bool(web.get("enabled", False))


def web_enabled(project_root: Path) -> bool:
    """Return True if the Web adapter should activate for this project.

    Per spec Writing F3: `package.json` at root OR `[tool.crackerjack.web] enabled = true`.
    """
    return package_json_present(project_root) or _opt_in_enabled(project_root)


class WebAdapter(LanguageAdapterBase):
    """Web (CSS/HTML/JS/TS) language adapter.

    Phase 4 ships CLI-only hooks with no lifecycle (per spec line 65).
    """

    name = "web"

    def detect(self, project_root: Path) -> bool:
        """Return True iff the Web adapter should activate for `project_root`."""
        return web_enabled(project_root)

    def capabilities(self, project_root: Path) -> Capabilities:
        """Return the Web adapter's capabilities for `project_root`."""
        return Capabilities(
            version_source=None,  # No version management for Web
            hooks=web_hooks(project_root),
            has_lifecycle=False,
        )


__all__ = ["WebAdapter", "package_json_present", "web_enabled", "web_hooks"]
