"""Stage 0: scaffolded pyproject.toml must default unsafe-fixes to false."""

from __future__ import annotations

from pathlib import Path

from rich.console import Console
from tomli_w import dumps

from crackerjack.services.config_template import ConfigTemplateService


def test_scaffolded_unsafe_fixes_default_is_false() -> None:
    service = ConfigTemplateService(Console(), Path())

    content = dumps(service._build_pyproject_tools())

    # The scaffolded [tool.ruff] block must set unsafe-fixes = false.
    assert "unsafe-fixes = false" in content, (
        f"scaffolded config must disable unsafe-fixes by default; got:\n{content}"
    )
    assert "unsafe-fixes = true" not in content
