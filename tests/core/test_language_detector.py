from __future__ import annotations

import tempfile
from pathlib import Path

from crackerjack.adapters.base import Capabilities, LanguageAdapter
from crackerjack.core.language_detector import detect


class _AlwaysAdapter:
    name = "always"

    def detect(self, project_root):
        return True

    def capabilities(self, project_root):
        return Capabilities()


class _NeverAdapter:
    name = "never"

    def detect(self, project_root):
        return False

    def capabilities(self, project_root):
        return Capabilities()


def test_detect_returns_only_adapters_whose_detect_is_true(tmp_path: Path) -> None:
    adapters = [_AlwaysAdapter(), _NeverAdapter()]
    result = detect(adapters, tmp_path)
    names = [a.name for a in result]
    assert "always" in names
    assert "never" not in names


def test_detect_returns_empty_for_empty_adapter_list(tmp_path: Path) -> None:
    assert detect([], tmp_path) == []


def test_detect_preserves_order(tmp_path: Path) -> None:
    adapters = [_AlwaysAdapter(), _NeverAdapter(), _AlwaysAdapter()]
    # Two `_AlwaysAdapter` instances — collision. Patch name to differentiate.
    adapters[2].name = "also"  # type: ignore[misc]
    result = detect(adapters, tmp_path)
    names = [a.name for a in result]
    assert names == ["always", "also"]
