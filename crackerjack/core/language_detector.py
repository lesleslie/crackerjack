from __future__ import annotations

from pathlib import Path

from crackerjack.adapters.base import LanguageAdapter


def detect(
    adapters: list[LanguageAdapter],
    project_root: Path,
) -> list[LanguageAdapter]:
    """Return adapters whose ``detect()`` returns True for the project.

    The order of the input ``adapters`` list is preserved in the output.
    Callers typically pass ``discover_adapters().values()``.
    """
    return [a for a in adapters if a.detect(project_root)]
