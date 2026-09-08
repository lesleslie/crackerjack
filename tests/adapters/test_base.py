from __future__ import annotations

import pytest

from crackerjack.adapters.base import (
    Capabilities,
    Hook,
    Lifecycle,
    LifecycleOptions,
    LifecycleResult,
    LanguageAdapter,
    LanguageAdapterBase,
    VersionNotFoundError,
    VersionSource,
    VersionSourceError,
    VersionWriteError,
)


def test_language_adapter_is_runtime_checkable() -> None:
    class FakeAdapter:
        name = "fake"

        def detect(self, project_root):
            return True

        def capabilities(self, project_root):
            return Capabilities()

    assert isinstance(FakeAdapter(), LanguageAdapter)


def test_capabilities_is_frozen() -> None:
    caps = Capabilities()
    with pytest.raises((AttributeError, Exception)):  # FrozenInstanceError is subclass of AttributeError
        caps.has_lifecycle = True  # type: ignore[misc]


def test_capabilities_defaults() -> None:
    caps = Capabilities()
    assert caps.version_source is None
    assert caps.hooks == ()
    assert caps.has_lifecycle is False
    assert caps.has_version is False


def test_hook_required_fields_only() -> None:
    hook = Hook(name="x.test", cli_command=("x", "test"))
    assert hook.timeout_seconds == 600
    assert hook.autofix is False
    assert hook.cli_required is True
    assert hook.fallback is None


def test_version_source_error_hierarchy() -> None:
    assert issubclass(VersionNotFoundError, VersionSourceError)
    assert issubclass(VersionWriteError, VersionSourceError)
    assert issubclass(VersionSourceError, Exception)


def test_lifecycle_options_accepts_known_levels() -> None:
    for level in ("major", "minor", "patch"):
        opts = LifecycleOptions(level=level)  # type: ignore[arg-type]
        assert opts.level == level


def test_lifecycle_options_rejects_unknown_level() -> None:
    with pytest.raises(ValueError):
        LifecycleOptions(level="epic")  # type: ignore[arg-type]


def test_lifecycle_result_defaults() -> None:
    result = LifecycleResult(
        new_version="1.0.0",
        commit_sha=None,
        tag_name=None,
        release_url=None,
    )
    assert result.skipped_steps == ()


def test_language_adapter_base_requires_name() -> None:
    with pytest.raises(TypeError):
        LanguageAdapterBase()  # abstract, but `name` is also required
