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
    # discover_adapters() iterates _entry_points() directly (not via .select()),
    # so patch it to return a plain list of mock EntryPoints. Each mock needs
    # a `.load()` (one raises ImportError, one returns a valid adapter) and the
    # valid one needs `.name` so adapters[obj.name] indexes correctly.
    ep_invalid = mock.MagicMock(name="ep_invalid")
    ep_invalid.load.side_effect = ImportError("nope")
    ep_valid = mock.MagicMock(name="ep_valid")
    ep_valid.load.return_value = _FakeAdapter()
    # ep_valid.name isn't actually used (we index on obj.name = "fake"), but
    # setting it keeps the mock's repr readable in test failure output.

    with mock.patch(
        "crackerjack.adapters.registry._entry_points",
        return_value=[ep_invalid, ep_valid],
    ):
        adapters = discover_adapters()

    assert "fake" in adapters  # The valid one is still picked up.
    # The invalid entry point (ImportError on load) is logged and skipped,
    # so no adapter named "nope" leaks into the registry.
    assert all(name != "nope" for name in adapters)
