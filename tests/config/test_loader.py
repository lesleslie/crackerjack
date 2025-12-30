from pathlib import Path

import pytest


def _make_settings_class():
    # Create a fake Settings-like class with required surface
    class FakeSettings:  # not subclassing to avoid dependency
        model_fields = {"debug": None, "max_workers": None}

        def __init__(self, debug: bool = False, max_workers: int = 4):
            self.debug = debug
            self.max_workers = max_workers

        @classmethod
        async def create_async(cls, **kwargs):
            return cls(**kwargs)

    return FakeSettings


def _write_yaml(base: Path, name: str, content: str) -> Path:
    base.mkdir(parents=True, exist_ok=True)
    path = base / name
    path.write_text(content, encoding="utf-8")
    return path


def test_load_settings_merges_and_filters(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from importlib import import_module, reload

    try:
        loader = import_module("crackerjack.config.loader")
        reload(loader)
    except ImportError as e:  # e.g., missing PyYAML in environment
        pytest.skip(f"loader import prerequisites missing: {e}")

    FakeSettings = _make_settings_class()

    settings_dir = tmp_path / "settings"
    _write_yaml(settings_dir, "crackerjack.yaml", "debug: false\nmax_workers: 2\nunknown: 1\n")
    _write_yaml(settings_dir, "local.yaml", "debug: true\n")

    result = loader.load_settings(FakeSettings, settings_dir=settings_dir)

    # local.yaml should override crackerjack.yaml
    assert result.debug is True
    assert result.max_workers == 2
    # Unknown fields are ignored and not passed to constructor
    assert not hasattr(result, "unknown")


@pytest.mark.asyncio
async def test_load_settings_async_handles_invalid_yaml_and_continues(tmp_path: Path) -> None:
    from importlib import import_module, reload

    try:
        loader = import_module("crackerjack.config.loader")
        reload(loader)
    except ImportError as e:
        pytest.skip(f"loader import prerequisites missing: {e}")

    FakeSettings = _make_settings_class()

    settings_dir = tmp_path / "settings"
    # Invalid YAML in local.yaml should be logged and ignored
    _write_yaml(settings_dir, "local.yaml", ":::: not yaml ::::\n")
    _write_yaml(settings_dir, "crackerjack.yaml", "debug: true\nmax_workers: 8\n")

    result = await loader.load_settings_async(FakeSettings, settings_dir=settings_dir)
    assert result.debug is True
    assert result.max_workers == 8


def test_load_settings_ignores_non_mapping_yaml(tmp_path: Path) -> None:
    from importlib import import_module, reload

    try:
        loader = import_module("crackerjack.config.loader")
        reload(loader)
    except ImportError as e:
        pytest.skip(f"loader import prerequisites missing: {e}")

    FakeSettings = _make_settings_class()

    settings_dir = tmp_path / "settings"
    # Non-dict YAML should be ignored with a warning; only valid mapping should apply
    _write_yaml(settings_dir, "crackerjack.yaml", "- a\n- b\n- c\n")
    _write_yaml(settings_dir, "local.yaml", "max_workers: 6\n")

    result = loader.load_settings(FakeSettings, settings_dir=settings_dir)
    assert result.max_workers == 6
    assert result.debug is False  # default
