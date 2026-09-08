from __future__ import annotations

from pathlib import Path

from crackerjack.adapters.base import Capabilities, LanguageAdapterBase
from crackerjack.adapters.python.hooks import python_hooks
from crackerjack.adapters.python.lifecycle import PythonLifecycle
from crackerjack.adapters.python.version_source import PyprojectVersionSource

__all__ = ["PythonAdapter", "PyprojectVersionSource", "PythonLifecycle", "python_hooks"]


class PythonAdapter(LanguageAdapterBase):
    """The Python language adapter.

    Phase 1: detects pyproject.toml projects, exposes existing
    crackerjack hooks, and delegates lifecycle to the existing
    publish_manager / services/git machinery.
    """

    name = "python"

    def detect(self, project_root: Path) -> bool:
        return (project_root / "pyproject.toml").is_file()

    def capabilities(self, project_root: Path) -> Capabilities:
        version_source = PyprojectVersionSource(project_root)
        return Capabilities(
            version_source=version_source,
            hooks=python_hooks(),
            has_lifecycle=True,
        )
