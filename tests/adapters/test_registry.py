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


def test_discover_adapters_returns_instances_not_classes(monkeypatch: object) -> None:
    """Bug 3 regression: entry points that point at a CLASS must be instantiated.

    The pre-fix code only checked ``isinstance(obj, LanguageAdapter)``. Because
    ``LanguageAdapter`` is ``@runtime_checkable``, ``isinstance(SomeClass,
    LanguageAdapter)`` returns True for any class that happens to have the
    required attributes — so classes were stored as classes and downstream
    code that called ``adapter.detect(...)`` failed with
    ``TypeError: detect() missing self argument``.

    The fix instantiates any class returned from an entry point before
    indexing it under ``obj.name``.
    """
    adapters = discover_adapters()
    python_adapter = adapters["python"]

    # The Phase 1 test above passes for both classes and instances; this is
    # the more specific check the fix requires.
    assert not isinstance(python_adapter, type), (
        "discover_adapters() must return INSTANCES, not classes. "
        "Got the PythonAdapter class object instead of an instance."
    )
    # Sanity: it still satisfies the LanguageAdapter protocol as an instance.
    assert isinstance(python_adapter, LanguageAdapter)


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


def test_discover_adapters_instantiates_class_entry_points() -> None:
    """Bug 3 regression: a CLASS returned from an entry point must be instantiated.

    Mirrors the ``module:ClassName`` form used by pyproject.toml entry points.
    The fixed code detects ``isinstance(obj, type)`` first and calls ``obj()``;
    the returned instance is what ends up in the registry under ``obj.name``.
    """
    ep_class = mock.MagicMock(name="ep_class")
    ep_class.load.return_value = _FakeAdapter  # the class itself, not an instance

    with mock.patch(
        "crackerjack.adapters.registry._entry_points",
        return_value=[ep_class],
    ):
        adapters = discover_adapters()

    assert "fake" in adapters
    # The registry must hold an INSTANCE, not the class.
    assert not isinstance(adapters["fake"], type), (
        "Entry point returned a class; discover_adapters() should have "
        "instantiated it before indexing."
    )
    assert isinstance(adapters["fake"], _FakeAdapter)


def test_discover_adapters_skips_classes_that_fail_to_instantiate() -> None:
    """Bug 3 regression: a class whose constructor raises must be skipped, not crashed."""
    class _BrokenAdapter:
        name = "broken"

        def __init__(self) -> None:
            raise RuntimeError("constructor blew up")

    ep_broken = mock.MagicMock(name="ep_broken")
    ep_broken.load.return_value = _BrokenAdapter

    with mock.patch(
        "crackerjack.adapters.registry._entry_points",
        return_value=[ep_broken],
    ):
        # Must not raise; the broken adapter is logged and skipped.
        adapters = discover_adapters()

    assert "broken" not in adapters
