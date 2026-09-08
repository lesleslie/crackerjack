from __future__ import annotations

from unittest import mock

from crackerjack.adapters.base import Capabilities, LanguageAdapter
from crackerjack.adapters.registry import discover_adapters


class _FakeAdapter:
    name = "fake"

    def detect(self, project_root):
        return True

    def capabilities(self, project_root):
        return Capabilities()


def test_discover_adapters_returns_dict_with_python_key(monkeypatch: object) -> None:
    """The Python adapter must always be discoverable."""
    monkeypatch_ = monkeypatch  # type: ignore[assignment]
    adapters = discover_adapters()
    # Built-in Python adapter is registered via entry-point in pyproject.toml.
    assert "python" in adapters
    assert isinstance(adapters["python"], LanguageAdapter)


def test_discover_adapters_skips_invalid_entry_points(monkeypatch: object) -> None:
    """A broken third-party adapter must not brick crackerjack."""
    fake_entry_points = mock.MagicMock()
    fake_entry_points.select.return_value = [
        mock.MagicMock(load=mock.MagicMock(side_effect=ImportError("nope"))),
        mock.MagicMock(load=mock.MagicMock(return_value=_FakeAdapter())),
    ]
    with mock.patch("crackerjack.adapters.registry._entry_points", return_value=fake_entry_points):
        adapters = discover_adapters()
    assert "fake" in adapters  # The valid one is still picked up.
