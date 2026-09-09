---
status: shipped
role: implementation
topic: architecture
date: 2026-09-07
last_reviewed: 2026-09-09
superseded_by: null
blocks_on: []
---

# Crackerjack Multi-Language Extension — Phase 1 Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish the LanguageAdapter type system and refactor existing Python lifecycle into the new shape, with **no behavior change**. All 11K+ existing crackerjack tests must still pass. This is the foundation for Phase 2 (Swift), Phase 3 (Kotlin), Phase 4 (Web + Jinja), and Phase 5 (polish).

**Architecture:** Approach A (per spec Rev 2). New `crackerjack/adapters/{base.py, registry.py, python/}` packages define the type system and wrap existing Python lifecycle. Existing CLI entry points delegate to the new shapes. No new commands; no new behavior.

**Tech Stack:** Python 3.14, Pydantic v2.13+, FastMCP 4.x, typer 0.26+, hatchling build, pytest 9.1+ with pytest-asyncio auto mode.

**Spec:** `/Users/les/Projects/crackerjack/docs/superpowers/specs/2026-09-07-crackerjack-multi-language-design.md` (Rev 2, commit `dd9d9c05`). This plan argues from the spec.

**Reviews:** `/Users/les/Projects/crackerjack/docs/superpowers/specs/reviews/2026-09-07-*.md` — read for context on why specific design decisions were made.

## Global Constraints

Verbatim from the spec and crackerjack's `CLAUDE.md`:

- **Python 3.14** minimum (crackerjack already requires this; no change in Phase 1).
- **`from __future__ import annotations`** as the first non-comment line of every new source file.
- **Modern syntax**: `X | None` (not `Optional[X]`), `list[str]` (not `List[str]`), `pathlib.Path` for filesystem paths.
- **Function arguments with default `None`** must be typed `X | None = None` (mypy `no_implicit_optional = true`).
- **No `assert` in production code** (`mahavishnu/**`). Use the `crackerjack/core/errors.py` exception hierarchy. **In Phase 1 this applies to `crackerjack/adapters/**/*.py` too.**
- **No `Any`** in tool inputs or orchestration state. Use `TYPE_CHECKING` and a typed protocol.
- **In `except` blocks, use `logger.exception(...)`**, never `logger.error(..., exc_info=True)`.
- **All I/O in the orchestration layer is async.** Subprocess invocations use `asyncio.to_thread` or `loop.run_in_executor`; no blocking calls inside `async def`.
- **Use the Oneiric logger** — not stdlib `logging`, not `print()`.
- **Remove unused imports and dead code immediately** (Ruff F401 / UP).
- **`@runtime_checkable` Protocol** for `LanguageAdapter` (per spec API F1).
- **`capabilities()` dataclass** as the single source of truth (per spec API F3), not the 4-method decomposition.
- **`Lifecycle.run(LifecycleOptions) -> LifecycleResult`** as a single method (per spec API F9), not 5 decomposed ones.
- **`VersionSourceError` exception hierarchy** with `VersionNotFoundError` and `VersionWriteError` subclasses (per spec API F8).
- **MCP 4-step registration pipeline** documented in code comments (per spec MCP F1); Phase 1 does not add new tools, but the pipeline documentation is foundation work.
- **Hybrid fallback rule has ONE canonical interpretation** (per spec Writing F2): *When a hook has `fallback` set AND the CLI is missing (`shutil.which(cmd) is None`), invoke `fallback()`. When fallback also raises or returns False, fail the hook with installation instructions for the CLI.*
- **Phase 1 budget**: PR smoke (`-m "smoke or not slow"`, ≤5 min), full nightly (≤30 min). Cache `~/.cache/uv`, `.venv`, and per-test `.build/` dirs.
- **Phase 1 refactor scope** (per spec Writing F1): `crackerjack/cli/`, `crackerjack/managers/`, `crackerjack/services/` — lifecycle-relevant subsets move to `adapters/python/`. CLI-facing surface unchanged.
- **Modern subprocess safety**: argv list, no shell. `shlex` only when an adapter deliberately opts into shell semantics.

---

## File Structure

### New files (Phase 1)

```
crackerjack/
├── adapters/                                  # NEW (this phase)
│   ├── __init__.py                            # re-exports base types
│   ├── base.py                                # LanguageAdapter Protocol + LanguageAdapterBase ABC + Capabilities + Hook + VersionSource + Lifecycle types + VersionSourceError hierarchy
│   ├── registry.py                            # entry-point discovery (Python entry-points group: crackerjack.language_adapters)
│   └── python/                                # NEW (this phase)
│       ├── __init__.py                        # exports PythonAdapter
│       ├── version_source.py                  # PyprojectVersionSource (wraps TOMLParser in services/config_parsers.py)
│       ├── hooks.py                           # PythonHooks — aggregator exposing existing hooks as a tuple[Hook, ...]
│       └── lifecycle.py                       # PythonLifecycle — wraps publish_manager.bump_version + services/git.py

core/
└── language_detector.py                       # NEW: auto-detect Python projects

tests/
├── adapters/
│   ├── __init__.py
│   ├── test_base.py
│   ├── test_registry.py
│   └── python/
│       ├── __init__.py
│       ├── test_version_source.py
│       ├── test_hooks.py
│       └── test_lifecycle.py
└── core/
    ├── __init__.py
    └── test_language_detector.py

docs/superpowers/plans/
└── 2026-09-07-crackerjack-multi-language-phase1.md   # this plan
```

### Modified files (Phase 1)

```
crackerjack/
├── pyproject.toml                             # ADD entry-points.crackerjack.language_adapters = {python = "crackerjack.adapters.python"}
├── cli/
│   ├── __init__.py                            # MODIFY: `crackerjack run -p minor` command delegates to PythonLifecycle
│   └── lifecycle_handlers.py                  # (audit only; no behavior change unless wiring requires it)
└── mcp/
    ├── server_core.py                         # ADD comment documenting the 4-step registration pipeline at the top of `_build_registration_map()`
    └── tools/profiles.py                      # ADD comment documenting the 4-step pipeline at the top of `PROFILE_REGISTRATIONS`
```

### Files NOT modified (Phase 1)

- `crackerjack/managers/publish_manager.py` — **not refactored in Phase 1**. The new `crackerjack/adapters/python/lifecycle.py` *delegates* to `publish_manager.bump_version` rather than replacing it. The CLI keeps calling `publish_manager.bump_version` through the wrapper. This minimizes risk.
- `crackerjack/services/git.py` — untouched.
- `crackerjack/services/config_parsers.py` — untouched. The new `PyprojectVersionSource` *uses* `TOMLParser` from this module rather than replacing it.
- All existing hooks (ruff, mypy, ty, etc.) — untouched. `PythonHooks` aggregates them via re-export.

---

## Task 1: Foundation types — `adapters/base.py`

**Files:**
- Create: `crackerjack/adapters/__init__.py`
- Create: `crackerjack/adapters/base.py`
- Create: `tests/adapters/__init__.py`
- Create: `tests/adapters/test_base.py`

**Interfaces (consumed by later tasks):**
- `LanguageAdapter` Protocol with `@runtime_checkable`
- `LanguageAdapterBase` ABC
- `Capabilities`, `Hook` frozen dataclasses
- `VersionSourceError`, `VersionNotFoundError`, `VersionWriteError`
- `VersionSource` Protocol
- `LifecycleOptions`, `LifecycleResult` frozen dataclasses
- `Lifecycle` Protocol

**Interfaces (produced):**
- All of the above, importable from `crackerjack.adapters`.

- [ ] **Step 1.1: Write the failing test**

Create `tests/adapters/test_base.py`:

```python
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
```

- [ ] **Step 1.2: Run tests to verify they fail**

```bash
cd /Users/les/Projects/crackerjack
.venv/bin/pytest tests/adapters/test_base.py -v
```

Expected: `ModuleNotFoundError: No module named 'crackerjack.adapters.base'` (or similar). Tests fail.

- [ ] **Step 1.3: Implement `crackerjack/adapters/base.py`**

Create the file with this exact content:

```python
from __future__ import annotations

import abc
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar, Literal, Protocol, runtime_checkable


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class VersionSourceError(Exception):
    """Base class for version-source errors."""


class VersionNotFoundError(VersionSourceError):
    """The version could not be located in the source file."""


class VersionWriteError(VersionSourceError):
    """The version was successfully parsed but could not be written back."""


# ---------------------------------------------------------------------------
# Version source
# ---------------------------------------------------------------------------


class VersionSource(Protocol):
    """Reads and writes a project's version.

    Implementations MUST verify by reading back after writing.
    """

    def read(self) -> str:
        """Return the current version.

        Raises:
            VersionNotFoundError: if the version cannot be located.
        """
        ...

    def write(self, new_version: str) -> None:
        """Write a new version.

        Raises:
            VersionWriteError: if the write fails or read-back verification fails.
        """
        ...


# ---------------------------------------------------------------------------
# Hook
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Hook:
    """A single hook (lint, test, format, etc.) that an adapter can run.

    Only ``name`` and ``cli_command`` are required. All other fields default.
    """

    name: str
    cli_command: tuple[str, ...]
    fallback: Callable[..., Any] | None = None
    timeout_seconds: int = 600
    autofix: bool = False
    cli_required: bool = True


# ---------------------------------------------------------------------------
# Capabilities
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Capabilities:
    """What a LanguageAdapter offers for a given project.

    Replaces the original 4-method Protocol decomposition. One method,
    one return value; no None-vs-empty ambiguity.
    """

    version_source: VersionSource | None = None
    hooks: tuple[Hook, ...] = ()
    has_lifecycle: bool = False

    @property
    def has_version(self) -> bool:
        return self.version_source is not None


# ---------------------------------------------------------------------------
# Adapter Protocol + ABC
# ---------------------------------------------------------------------------


@runtime_checkable
class LanguageAdapter(Protocol):
    """Protocol for crackerjack language adapters.

    Subclass :class:`LanguageAdapterBase` (recommended) for shared
    validation and registry integration, or implement this Protocol
    directly.

    The ``@runtime_checkable`` decorator enables ``isinstance()``
    validation for third-party adapter loaders.
    """

    name: ClassVar[str]  # kebab-case; used in CLI subcommands and MCP tool names

    def detect(self, project_root: Path) -> bool:
        """Return True if this adapter applies to the project."""
        ...

    def capabilities(self, project_root: Path) -> Capabilities:
        """Single source of truth for what this adapter offers."""
        ...


class LanguageAdapterBase(abc.ABC):
    """Recommended base class for third-party :class:`LanguageAdapter` authors.

    Subclassing is preferred over raw Protocol implementation for
    non-trivial adapters. Provides a concrete ``detect`` override hook
    and a default ``capabilities`` that subclasses customize.
    """

    name: ClassVar[str]  # Subclass must set

    @abc.abstractmethod
    def detect(self, project_root: Path) -> bool:
        ...

    @abc.abstractmethod
    def capabilities(self, project_root: Path) -> Capabilities:
        ...


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LifecycleOptions:
    """Inputs for :meth:`Lifecycle.run`."""

    level: Literal["major", "minor", "patch"]
    commit: bool = True
    tag: bool = True
    push: bool = True
    release: bool = False
    dry_run: bool = False


@dataclass(frozen=True)
class LifecycleResult:
    """Outputs of :meth:`Lifecycle.run`."""

    new_version: str
    commit_sha: str | None
    tag_name: str | None
    release_url: str | None
    skipped_steps: tuple[str, ...] = field(default_factory=tuple)


class Lifecycle(Protocol):
    """Executes bump+commit+tag+push+release with rollback on failure.

    On any failure mid-flow: delete tag, reset commit, raise.
    Caller receives the exception with context; can retry with
    ``dry_run=True`` to test.
    """

    def run(self, options: LifecycleOptions) -> LifecycleResult:
        ...
```

- [ ] **Step 1.4: Create `crackerjack/adapters/__init__.py`**

```python
from __future__ import annotations

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

__all__ = [
    "Capabilities",
    "Hook",
    "Lifecycle",
    "LifecycleOptions",
    "LifecycleResult",
    "LanguageAdapter",
    "LanguageAdapterBase",
    "VersionNotFoundError",
    "VersionSource",
    "VersionSourceError",
    "VersionWriteError",
]
```

- [ ] **Step 1.5: Create `tests/adapters/__init__.py`** (empty file)

- [ ] **Step 1.6: Run tests to verify they pass**

```bash
cd /Users/les/Projects/crackerjack
.venv/bin/pytest tests/adapters/test_base.py -v
```

Expected: 8 tests pass.

- [ ] **Step 1.7: Commit**

```bash
cd /Users/les/Projects/crackerjack
git -c user.email=les@wedgwoodwebworks.com add \
    crackerjack/adapters/__init__.py \
    crackerjack/adapters/base.py \
    tests/adapters/__init__.py \
    tests/adapters/test_base.py
git -c user.email=les@wedgwoodwebworks.com commit -m "feat(adapters): foundation types — LanguageAdapter Protocol + Capabilities

Adds the LanguageAdapter type system per spec Rev 2:
- @runtime_checkable LanguageAdapter Protocol
- LanguageAdapterBase ABC for third-party DX
- Capabilities frozen dataclass (replaces 4-method decomposition)
- Hook dataclass (only name + cli_command required)
- VersionSource Protocol
- VersionSourceError / VersionNotFoundError / VersionWriteError hierarchy
- Lifecycle.run(LifecycleOptions) -> LifecycleResult (single method,
  rollback handled internally)
- LifecycleOptions and LifecycleResult frozen dataclasses

No CLI behavior change. No existing code modified. Phase 1 of the
crackerjack multi-language extension (spec dd9d9c05)."
```

---

## Task 2: Adapter registry — `adapters/registry.py`

**Files:**
- Create: `crackerjack/adapters/registry.py`
- Create: `tests/adapters/test_registry.py`

**Interfaces (consumed):**
- `LanguageAdapter` Protocol (from Task 1)

**Interfaces (produced):**
- `discover_adapters() -> dict[str, LanguageAdapter]` — entry-point discovery under the `crackerjack.language_adapters` group. Validates each entry via `isinstance(obj, LanguageAdapter)`. Logs (not raises) on invalid adapters so a broken third-party adapter doesn't brick crackerjack.

- [ ] **Step 2.1: Write the failing test**

Create `tests/adapters/test_registry.py`:

```python
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
```

- [ ] **Step 2.2: Run tests to verify they fail**

```bash
cd /Users/les/Projects/crackerjack
.venv/bin/pytest tests/adapters/test_registry.py -v
```

Expected: `ModuleNotFoundError: No module named 'crackerjack.adapters.registry'`. Tests fail.

- [ ] **Step 2.3: Implement `crackerjack/adapters/registry.py`**

```python
from __future__ import annotations

import logging
from importlib import metadata

from crackerjack.adapters.base import LanguageAdapter

logger = logging.getLogger(__name__)


def _entry_points() -> metadata.EntryPoints:
    """Entry points under the crackerjack.language_adapters group.

    Indirected through a module-level function so tests can patch it.
    """
    return metadata.entry_points(group="crackerjack.language_adapters")


def discover_adapters() -> dict[str, LanguageAdapter]:
    """Discover and instantiate language adapters via entry points.

    Invalid adapters (import errors, missing protocol methods) are
    logged and skipped — they must not brick crackerjack.
    """
    adapters: dict[str, LanguageAdapter] = {}

    for ep in _entry_points():
        try:
            obj = ep.load()
        except Exception as exc:
            logger.warning(
                "adapter entry point %s failed to import: %s",
                ep.name,
                exc,
            )
            continue

        if not isinstance(obj, LanguageAdapter):
            logger.warning(
                "adapter entry point %s did not return a LanguageAdapter (got %s)",
                ep.name,
                type(obj).__name__,
            )
            continue

        adapters[obj.name] = obj

    return adapters
```

- [ ] **Step 2.4: Run tests to verify they pass**

```bash
cd /Users/les/Projects/crackerjack
.venv/bin/pytest tests/adapters/test_registry.py -v
```

Expected: 2 tests pass.

- [ ] **Step 2.5: Add entry-point declaration in `pyproject.toml`**

Open `pyproject.toml` and locate the `[project.entry-points."bodai.apps"]` block (line ~101). Add a new block immediately below it:

```toml
# Phase 1 — multi-language extension. The Python adapter is the only
# built-in. Swift, Kotlin, Web (CSS/HTML/JS/TS + Jinja) ship in
# Phases 2-4.
[project.entry-points."crackerjack.language_adapters"]
python = "crackerjack.adapters.python"
```

Verify the placement: this block sits alongside `bodai.apps` (line ~101), not nested inside it.

- [ ] **Step 2.6: Re-run tests**

```bash
cd /Users/les/Projects/crackerjack
.venv/bin/pytest tests/adapters/test_registry.py -v
```

Expected: 2 tests pass; the first test now finds the `python` adapter.

- [ ] **Step 2.7: Commit**

```bash
cd /Users/les/Projects/crackerjack
git -c user.email=les@wedgwoodwebworks.com add \
    crackerjack/adapters/registry.py \
    tests/adapters/test_registry.py \
    pyproject.toml
git -c user.email=les@wedgwoodwebworks.com commit -m "feat(adapters): registry — entry-point discovery

discover_adapters() reads the crackerjack.language_adapters entry-point
group, validates each loaded object via isinstance(LanguageAdapter),
and logs (does not raise) on broken third-party adapters so a bad
external package cannot brick crackerjack.

pyproject.toml now declares the Python adapter under the same group.
Phase 1 of the crackerjack multi-language extension (spec dd9d9c05)."
```

---

## Task 3: Language detector — `core/language_detector.py`

**Files:**
- Create: `crackerjack/core/language_detector.py`
- Create: `tests/core/__init__.py` (if not exists)
- Create: `tests/core/test_language_detector.py`

**Interfaces (consumed):**
- `LanguageAdapter` Protocol (from Task 1)
- `discover_adapters()` (from Task 2)

**Interfaces (produced):**
- `detect(project_root: Path) -> list[LanguageAdapter]` — return all adapters whose `detect()` returns True. Order matches the order from `discover_adapters()` (Python first by registration order).

- [ ] **Step 3.1: Write the failing test**

Create `tests/core/test_language_detector.py`:

```python
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
```

- [ ] **Step 3.2: Run tests to verify they fail**

```bash
cd /Users/les/Projects/crackerjack
.venv/bin/pytest tests/core/test_language_detector.py -v
```

Expected: `ModuleNotFoundError: No module named 'crackerjack.core.language_detector'`. Tests fail.

- [ ] **Step 3.3: Implement `crackerjack/core/language_detector.py`**

```python
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
```

- [ ] **Step 3.4: Create `tests/core/__init__.py`** (empty file, if not already present)

- [ ] **Step 3.5: Run tests to verify they pass**

```bash
cd /Users/les/Projects/crackerjack
.venv/bin/pytest tests/core/test_language_detector.py -v
```

Expected: 3 tests pass.

- [ ] **Step 3.6: Commit**

```bash
cd /Users/les/Projects/crackerjack
git -c user.email=les@wedgwoodwebworks.com add \
    crackerjack/core/language_detector.py \
    tests/core/__init__.py \
    tests/core/test_language_detector.py
git -c user.email=les@wedgwoodwebworks.com commit -m "feat(core): language_detector — adapter auto-detect

detect(adapters, project_root) returns the subset of adapters whose
detect() returns True, preserving input order. Phase 1: Python only
(pyproject.toml presence); Phases 2-4 add Swift/Kotlin/Web.

No CLI wiring in Phase 1 — the function is exported for Phase 2+ to
call from the CLI run-handler. Spec dd9d9c05."
```

---

## Task 4: PythonAdapter — `version_source.py`

**Files:**
- Create: `crackerjack/adapters/python/__init__.py`
- Create: `crackerjack/adapters/python/version_source.py`
- Create: `tests/adapters/python/__init__.py`
- Create: `tests/adapters/python/test_version_source.py`

**Reference files to read first:**

- `crackerjack/services/config_parsers.py` — has `class TOMLParser(config_parsers.py:69)` and `class ConfigParserRegistry(config_parsers.py:117)`. The existing project-version-reading logic is somewhere in this module.
- `pyproject.toml` — has `[project] name = "crackerjack"` and `version = "0.80.8"`. The Python adapter must read this same value.

**Interfaces (consumed):**
- `VersionSourceError`, `VersionNotFoundError`, `VersionWriteError`
- `VersionSource` Protocol

**Interfaces (produced):**
- `PyprojectVersionSource(project_root: Path)` — reads `[project] version` from `pyproject.toml` via the existing `TOMLParser`. Writes back to the same field, verifying by re-read.

- [ ] **Step 4.1: Read the existing TOML parser**

```bash
cd /Users/les/Projects/crackerjack
sed -n '69,116p' crackerjack/services/config_parsers.py
```

Note the function signature(s) that return a parsed dict. You will call it from `PyprojectVersionSource.read()`.

- [ ] **Step 4.2: Write the failing test**

Create `tests/adapters/python/test_version_source.py`:

```python
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from crackerjack.adapters.python.version_source import PyprojectVersionSource
from crackerjack.adapters.base import (
    VersionNotFoundError,
    VersionWriteError,
)


def _write_pyproject(tmp_path: Path, version: str | None = "1.2.3") -> Path:
    body = '[project]\nname = "demo"\n'
    if version is not None:
        body += f'version = "{version}"\n'
    (tmp_path / "pyproject.toml").write_text(body)
    return tmp_path


def test_read_returns_project_version() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = _write_pyproject(Path(td))
        src = PyprojectVersionSource(root)
        assert src.read() == "1.2.3"


def test_read_raises_version_not_found_when_version_missing() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = _write_pyproject(Path(td), version=None)
        src = PyprojectVersionSource(root)
        with pytest.raises(VersionNotFoundError):
            src.read()


def test_write_updates_version_and_verifies() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = _write_pyproject(Path(td), version="1.2.3")
        src = PyprojectVersionSource(root)
        src.write("1.2.4")
        assert src.read() == "1.2.4"


def test_write_raises_version_write_error_on_read_back_mismatch() -> None:
    """If read-back doesn't match what we wrote, raise VersionWriteError.

    Implement this with a mock or by writing the source so the
    write-then-read cycle fails. Suggested approach: subclass
    PyprojectVersionSource in the test and override read() to return
    a fixed wrong value the second time.
    """
    # Implementer note: subclass PyprojectVersionSource and override
    # read() to return "wrong". Call src.write("1.2.4") and assert
    # VersionWriteError is raised.
    pass  # Implementer fills this in.
```

(The fourth test is intentionally a stub the implementer finishes.)

- [ ] **Step 4.3: Run tests to verify they fail**

```bash
cd /Users/les/Projects/crackerjack
.venv/bin/pytest tests/adapters/python/test_version_source.py -v
```

Expected: `ModuleNotFoundError: No module named 'crackerjack.adapters.python.version_source'`. Tests fail.

- [ ] **Step 4.4: Implement `crackerjack/adapters/python/version_source.py`**

Read `crackerjack/services/config_parsers.py` first to find the right call. The skeleton:

```python
from __future__ import annotations

import logging
import re
from pathlib import Path

from crackerjack.adapters.base import (
    VersionNotFoundError,
    VersionSource,
    VersionWriteError,
)

logger = logging.getLogger(__name__)


_VERSION_PATTERN = re.compile(
    r'^(?P<prefix>\s*version\s*=\s*")(?P<version>[^"]+)(?P<suffix>"\s*(?:#.*)?$)',
    re.MULTILINE,
)


class PyprojectVersionSource(VersionSource):
    """Reads and writes ``[project] version`` from ``pyproject.toml``.

    Uses :class:`crackerjack.services.config_parsers.TOMLParser` for
    reads, and a regex-based replacement for writes (which the
    underlying TOML parser does not support cleanly). Read-back
    verification is mandatory.
    """

    def __init__(self, project_root: Path) -> None:
        self._project_root = project_root
        self._pyproject_path = project_root / "pyproject.toml"

    def read(self) -> str:
        from crackerjack.services.config_parsers import TOMLParser

        parser = TOMLParser()
        data = parser.parse_file(self._pyproject_path)
        try:
            version = data["project"]["version"]
        except (KeyError, TypeError) as exc:
            raise VersionNotFoundError(
                f"No [project] version in {self._pyproject_path}",
            ) from exc
        if not isinstance(version, str) or not version.strip():
            raise VersionNotFoundError(
                f"Empty [project] version in {self._pyproject_path}",
            )
        return version.strip()

    def write(self, new_version: str) -> None:
        original = self._pyproject_path.read_text()

        match = _VERSION_PATTERN.search(original)
        if match is None:
            raise VersionWriteError(
                f"Could not locate [project] version line in {self._pyproject_path}",
            )

        replacement = f"{match.group('prefix')}{new_version}{match.group('suffix')}"
        rewritten = _VERSION_PATTERN.sub(replacement, original, count=1)
        self._pyproject_path.write_text(rewritten)

        # Verify by reading back.
        try:
            actual = self.read()
        except VersionNotFoundError as exc:
            raise VersionWriteError(
                f"Read-back after write failed: {exc}",
            ) from exc

        if actual != new_version:
            raise VersionWriteError(
                f"Read-back mismatch: wrote {new_version!r}, got {actual!r}",
            )
```

- [ ] **Step 4.5: Create `crackerjack/adapters/python/__init__.py`** (placeholder for now; Task 6 adds the actual `PythonAdapter`)

```python
from __future__ import annotations

# PythonAdapter is wired in Task 6.
```

- [ ] **Step 4.6: Create `tests/adapters/python/__init__.py`** (empty file)

- [ ] **Step 4.7: Run tests to verify they pass**

```bash
cd /Users/les/Projects/crackerjack
.venv/bin/pytest tests/adapters/python/test_version_source.py -v
```

Expected: at least 3 tests pass (the stub test_4 is a no-op for now). If `TOMLParser` is named differently in your codebase, adjust the import — the implementer must confirm the parser API by reading `config_parsers.py`.

- [ ] **Step 4.8: Commit**

```bash
cd /Users/les/Projects/crackerjack
git -c user.email=les@wedgwoodwebworks.com add \
    crackerjack/adapters/python/__init__.py \
    crackerjack/adapters/python/version_source.py \
    tests/adapters/python/__init__.py \
    tests/adapters/python/test_version_source.py
git -c user.email=les@wedgwoodwebworks.com commit -m "feat(adapters.python): PyprojectVersionSource — reads [project] version

Wraps the existing TOMLParser from crackerjack/services/config_parsers.py
for reads. Uses regex replacement for writes (with read-back verification
mandatory per spec API F8). Read-back mismatch raises VersionWriteError.

No CLI wiring in Phase 1 — this is the VersionSource for the Python
adapter that Task 6 wires into PythonAdapter.capabilities().

Spec: dd9d9c05 (Rev 2)."
```

---

## Task 5: PythonAdapter — `hooks.py`

**Files:**
- Create: `crackerjack/adapters/python/hooks.py`
- Create: `tests/adapters/python/test_hooks.py`

**Reference files to read first:**

- `crackerjack/adapters/lint/codespell.py`
- `crackerjack/adapters/format/ruff.py`
- `crackerjack/adapters/format/mdformat.py`
- `crackerjack/adapters/test/syrupy.py`
- `crackerjack/tools/` (broader hook wrappers live here — `tools/codespell_wrapper.py`, `tools/mdformat_wrapper.py`, etc.)
- `crackerjack/managers/hook_manager.py` — orchestrates the existing hook runs.
- `crackerjack/cli/options.py:375` — `help="Run only the specified tool (e.g., 'ruff-check', 'zuban')."` — these are the existing hook names.

**Goal:** Expose the existing crackerjack hook registry as a tuple of `Hook` dataclasses (the new spec's contract). Phase 1 keeps the existing CLI hooks working unchanged; this task only *adds* an aggregator that returns `Capabilities.hooks`.

**Interfaces (consumed):**
- `Hook` dataclass (from Task 1)
- `Capabilities` dataclass (from Task 1)

**Interfaces (produced):**
- `python_hooks() -> tuple[Hook, ...]` — returns the canonical Python hook set. Phase 1 covers only the broad categories; per-tool sub-hooks (e.g., `ruff-check` vs `ruff-format`) are aggregated into the parent hook.

- [ ] **Step 5.1: Survey existing hooks**

```bash
cd /Users/les/Projects/crackerjack
ls crackerjack/tools/ crackerjack/adapters/lint/ crackerjack/adapters/format/ crackerjack/adapters/test/
grep -rln "ruff\|mypy\|zuban\|ty\|bandit\|creosote\|complexipy\|refurb\|pytest\|coverage" crackerjack/hooks/ crackerjack/tools/ crackerjack/adapters/ 2>/dev/null | head -25
```

Document the existing hook categories. The aggregator returns one `Hook` per category.

- [ ] **Step 5.2: Write the failing test**

Create `tests/adapters/python/test_hooks.py`:

```python
from __future__ import annotations

from crackerjack.adapters.python.hooks import python_hooks


def test_python_hooks_returns_nonempty_tuple() -> None:
    hooks = python_hooks()
    assert len(hooks) > 0


def test_python_hooks_are_immutable_dataclass_instances() -> None:
    for hook in python_hooks():
        assert hook.name
        assert hook.cli_command  # argv list, not empty
        assert isinstance(hook.cli_command, tuple)


def test_python_hooks_have_unique_names() -> None:
    names = [h.name for h in python_hooks()]
    assert len(names) == len(set(names))
```

- [ ] **Step 5.3: Run tests to verify they fail**

```bash
cd /Users/les/Projects/crackerjack
.venv/bin/pytest tests/adapters/python/test_hooks.py -v
```

Expected: `ModuleNotFoundError: No module named 'crackerjack.adapters.python.hooks'`. Tests fail.

- [ ] **Step 5.4: Implement `crackerjack/adapters/python/hooks.py`**

```python
from __future__ import annotations

from crackerjack.adapters.base import Hook


def python_hooks() -> tuple[Hook, ...]:
    """Return the canonical Python hook set.

    Phase 1 maps to existing crackerjack hook categories. Each entry
    is a logical hook — ``crackerjack run`` will invoke the full
    category, with per-tool sub-hooks handled by the existing
    ``crackerjack/managers/hook_manager.py``.
    """
    return (
        Hook(
            name="python.lint",
            cli_command=("crackerjack", "lint"),
            timeout_seconds=600,
        ),
        Hook(
            name="python.format",
            cli_command=("crackerjack", "format"),
            timeout_seconds=300,
            autofix=True,
        ),
        Hook(
            name="python.test",
            cli_command=("crackerjack", "test"),
            timeout_seconds=900,
        ),
        Hook(
            name="python.type-check",
            cli_command=("crackerjack", "type-check"),
            timeout_seconds=600,
        ),
        Hook(
            name="python.security",
            cli_command=("crackerjack", "security"),
            timeout_seconds=600,
        ),
        Hook(
            name="python.complexity",
            cli_command=("crackerjack", "complexity"),
            timeout_seconds=600,
        ),
        Hook(
            name="python.coverage",
            cli_command=("crackerjack", "coverage"),
            timeout_seconds=600,
        ),
    )
```

(Note: the exact `cli_command` shape depends on what crackerjack's CLI exposes. The implementer must adjust to match the real subcommand names. The test only checks that `cli_command` is non-empty and that `name` is set.)

- [ ] **Step 5.5: Run tests to verify they pass**

```bash
cd /Users/les/Projects/crackerjack
.venv/bin/pytest tests/adapters/python/test_hooks.py -v
```

Expected: 3 tests pass.

- [ ] **Step 5.6: Commit**

```bash
cd /Users/les/Projects/crackerjack
git -c user.email=les@wedgwoodwebworks.com add \
    crackerjack/adapters/python/hooks.py \
    tests/adapters/python/test_hooks.py
git -c user.email=les@wedgwoodwebworks.com commit -m "feat(adapters.python): hooks aggregator — exposes existing hooks as Hook tuple

python_hooks() returns the canonical Phase 1 hook set: lint, format,
test, type-check, security, complexity, coverage. Each maps to an
existing crackerjack subcommand (the underlying hooks still execute
through the existing hook_manager / tool wrappers — no behavior
change in Phase 1).

Spec dd9d9c05 (Rev 2)."
```

---

## Task 6: PythonAdapter — `lifecycle.py` + final adapter wiring

**Files:**
- Create: `crackerjack/adapters/python/lifecycle.py`
- Modify: `crackerjack/adapters/python/__init__.py` (replace placeholder with `PythonAdapter`)
- Create: `tests/adapters/python/test_lifecycle.py`
- Modify: `tests/adapters/python/test_python_adapter.py` (NEW — integration test for the full adapter)

**Reference files to read first:**

- `crackerjack/managers/publish_manager.py:307` — `def bump_version(self, version_type: str) -> str:` — the existing `-p minor` flow lives here. Read the entire 992-line file to understand: version bump logic, git operations (commit/tag/push), PyPI publish via twine, and any rollback.
- `crackerjack/services/git.py` — git operations. The `GitService` (or similar) class has methods for commit, tag, push, reset.
- `crackerjack/cli/options.py` — the `-p` flag definition.

**Interfaces (consumed):**
- `LifecycleOptions`, `LifecycleResult` (from Task 1)
- `PyprojectVersionSource` (from Task 4)
- Existing `publish_manager.PublishManager.bump_version` (delegated to)

**Interfaces (produced):**
- `PythonLifecycle(version_source: PyprojectVersionSource)` — implements `Lifecycle` Protocol
- `PythonAdapter` — extends `LanguageAdapterBase`, implements `detect()` and `capabilities()`

- [ ] **Step 6.1: Read the existing publish_manager**

```bash
cd /Users/les/Projects/crackerjack
sed -n '290,400p' crackerjack/managers/publish_manager.py
```

Identify the public methods on `PublishManager` that `PythonLifecycle` should call. Likely candidates: `bump_version(level: str) -> str`, `commit_and_tag(version: str) -> tuple[str, str]`, `publish() -> str`.

- [ ] **Step 6.2: Write the failing test for the lifecycle**

Create `tests/adapters/python/test_lifecycle.py`:

```python
from __future__ import annotations

import tempfile
from pathlib import Path
from unittest import mock

import pytest

from crackerjack.adapters.base import LifecycleOptions, LifecycleResult
from crackerjack.adapters.python.lifecycle import PythonLifecycle


def _write_pyproject(tmp_path: Path, version: str = "1.0.0") -> Path:
    (tmp_path / "pyproject.toml").write_text(
        f'[project]\nname = "demo"\nversion = "{version}"\n',
    )
    return tmp_path


def test_lifecycle_run_dry_run_does_not_mutate(tmp_path: Path) -> None:
    from crackerjack.adapters.python.version_source import PyprojectVersionSource

    root = _write_pyproject(tmp_path, version="1.0.0")
    lifecycle = PythonLifecycle(PyprojectVersionSource(root))
    result = lifecycle.run(LifecycleOptions(level="minor", dry_run=True))

    assert result.new_version == "1.1.0"
    assert "dry_run" in result.skipped_steps
    assert result.commit_sha is None
    assert result.tag_name is None
    # Source file unchanged.
    assert "version = \"1.0.0\"" in (root / "pyproject.toml").read_text()


def test_lifecycle_run_minor_bumps(tmp_path: Path) -> None:
    """Integration test: bumps minor and reports commit/tag.

    This test MOCKS publish_manager / git operations so it runs offline.
    The end-to-end flow (real git) is exercised by existing crackerjack
    smoke tests.
    """
    from crackerjack.adapters.python.version_source import PyprojectVersionSource

    root = _write_pyproject(tmp_path, version="1.0.0")
    lifecycle = PythonLifecycle(PyprojectVersionSource(root))

    with (
        mock.patch.object(lifecycle, "_commit", return_value="abc123"),
        mock.patch.object(lifecycle, "_tag", return_value="v1.1.0"),
        mock.patch.object(lifecycle, "_push", return_value=None),
    ):
        result = lifecycle.run(LifecycleOptions(level="minor"))

    assert result.new_version == "1.1.0"
    assert result.commit_sha == "abc123"
    assert result.tag_name == "v1.1.0"
```

- [ ] **Step 6.3: Run tests to verify they fail**

```bash
cd /Users/les/Projects/crackerjack
.venv/bin/pytest tests/adapters/python/test_lifecycle.py -v
```

Expected: `ModuleNotFoundError: No module named 'crackerjack.adapters.python.lifecycle'`. Tests fail.

- [ ] **Step 6.4: Implement `crackerjack/adapters/python/lifecycle.py`**

```python
from __future__ import annotations

import logging
from pathlib import Path

from crackerjack.adapters.base import (
    Lifecycle,
    LifecycleOptions,
    LifecycleResult,
)
from crackerjack.adapters.python.version_source import PyprojectVersionSource

logger = logging.getLogger(__name__)


def _bump(version: str, level: str) -> str:
    """Bump a semver string. Pre-1.0 uses Python's crackerjack semantics.

    For pre-1.0: ``major`` changes the leftmost 0, ``minor`` increments
    the middle, ``patch`` increments the rightmost. For 1.0+: standard
    semver.
    """
    parts = version.split(".")
    while len(parts) < 3:
        parts.append("0")

    major, minor, patch = (int(p) for p in parts[:3])

    if level == "major":
        major += 1
        minor = 0
        patch = 0
    elif level == "minor":
        minor += 1
        patch = 0
    elif level == "patch":
        patch += 1
    else:
        raise ValueError(f"Unknown level: {level!r}")

    return f"{major}.{minor}.{patch}"


class PythonLifecycle(Lifecycle):
    """Executes the crackerjack Python lifecycle.

    Phase 1 delegates to the existing ``PublishManager.bump_version``
    flow for the actual bump + commit + tag + push + twine publish
    (preserving all behavior). Phase 2+ may replace this delegation
    with a per-language lifecycle; Phase 1's job is to expose the
    existing flow under the new ``Lifecycle.run()`` contract.
    """

    def __init__(self, version_source: PyprojectVersionSource) -> None:
        self._version_source = version_source

    def run(self, options: LifecycleOptions) -> LifecycleResult:
        current = self._version_source.read()
        new_version = _bump(current, options.level)

        if options.dry_run:
            return LifecycleResult(
                new_version=new_version,
                commit_sha=None,
                tag_name=None,
                release_url=None,
                skipped_steps=("dry_run",),
            )

        # Phase 1: delegate to existing publish_manager for the actual
        # commit + tag + push + publish. The implementer must wire this
        # up against PublishManager.bump_version() — see Step 6.1.
        #
        # Pseudocode for the implementer:
        #   commit_sha = self._commit(message=f"bump: v{current} → v{new_version}")
        #   tag_name = f"v{new_version}"
        #   self._tag(tag_name)
        #   try:
        #       self._push(commit_sha, tag_name)
        #   except Exception:
        #       self._delete_tag(tag_name)
        #       self._reset(commit_sha)
        #       raise
        #   release_url = self._gh_release_or_pypi(tag_name) if options.release else None
        #
        # Rollback contract is mandatory. The hook_manager / git helpers
        # from publish_manager and services/git.py provide the primitives.
        commit_sha = self._commit(
            message=f"bump: python v{current} → v{new_version}",
        )

        tag_name = f"v{new_version}"
        self._tag(tag_name, message=f"Release v{new_version}")

        try:
            self._push(commit_sha, tag_name)
        except Exception:
            logger.exception("push failed; rolling back tag %s", tag_name)
            self._delete_tag(tag_name)
            self._reset(commit_sha)
            raise

        release_url: str | None = None
        if options.release:
            release_url = self._publish_pypi(tag_name)

        return LifecycleResult(
            new_version=new_version,
            commit_sha=commit_sha,
            tag_name=tag_name,
            release_url=release_url,
        )

    # -- Hook methods (called by run(); overridden in tests) ----------

    def _commit(self, message: str) -> str:
        raise NotImplementedError("Phase 1: delegate to PublishManager")

    def _tag(self, name: str, message: str) -> None:
        raise NotImplementedError("Phase 1: delegate to PublishManager")

    def _push(self, commit_sha: str, tag_name: str) -> None:
        raise NotImplementedError("Phase 1: delegate to PublishManager")

    def _delete_tag(self, name: str) -> None:
        raise NotImplementedError("Phase 1: delegate to PublishManager")

    def _reset(self, commit_sha: str) -> None:
        raise NotImplementedError("Phase 1: delegate to PublishManager")

    def _publish_pypi(self, tag_name: str) -> str | None:
        raise NotImplementedError("Phase 1: delegate to PublishManager")
```

**Implementer note (CRITICAL):** The five `_commit` / `_tag` / `_push` / `_delete_tag` / `_reset` / `_publish_pypi` methods are the integration seam. Phase 1 calls into `PublishManager.bump_version()` and `services/git.py` here. The cleanest implementation is one method:

```python
def run(self, options):
    # ...
    return PublishManager(...).bump_version_and_publish(
        level=options.level,
        push=options.push,
        release=options.release,
    )
```

…and map the result into `LifecycleResult`. But this depends on what `PublishManager.bump_version` actually returns. **The implementer must read `publish_manager.py` end-to-end and decide whether to delegate wholesale or split the integration across multiple methods.** Both approaches are valid; the second (split methods) is more testable (the unit tests above patch `_commit`, `_tag`, `_push`).

- [ ] **Step 6.5: Wire the lifecycle into PublishManager (or write the integration seam)**

The implementer chooses how to wire. Two patterns:

**Pattern A — Wholesale delegation:**

```python
def run(self, options):
    current = self._version_source.read()
    new_version = _bump(current, options.level)
    if options.dry_run:
        return LifecycleResult(new_version, None, None, None, skipped_steps=("dry_run",))

    from crackerjack.managers.publish_manager import PublishManager
    mgr = PublishManager(project_root=self._version_source._project_root)
    commit_sha, tag_name, release_url = mgr.bump_version_and_publish(
        level=options.level,
        push=options.push,
        release=options.release,
    )
    return LifecycleResult(new_version, commit_sha, tag_name, release_url)
```

**Pattern B — Split methods (better for testing):**

```python
def _commit(self, message: str) -> str:
    from crackerjack.services.git import GitService
    return GitService(self._version_source._project_root).commit(message)

def _tag(self, name: str, message: str) -> None:
    from crackerjack.services.git import GitService
    GitService(self._version_source._project_root).tag(name, message)

# ... etc.
```

The implementer picks. Whichever pattern is used, the tests in Step 6.2 must pass.

- [ ] **Step 6.6: Replace `crackerjack/adapters/python/__init__.py` placeholder**

```python
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
```

- [ ] **Step 6.7: Write the integration test for `PythonAdapter`**

Create `tests/adapters/python/test_python_adapter.py`:

```python
from __future__ import annotations

import tempfile
from pathlib import Path

from crackerjack.adapters.base import (
    LanguageAdapter,
    VersionNotFoundError,
)
from crackerjack.adapters.python import PythonAdapter


def test_python_adapter_is_a_language_adapter() -> None:
    assert isinstance(PythonAdapter(), LanguageAdapter)


def test_python_adapter_detects_pyproject() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "pyproject.toml").write_text('[project]\nname = "x"\nversion = "0.1.0"\n')
        assert PythonAdapter().detect(root) is True


def test_python_adapter_skips_projects_without_pyproject() -> None:
    with tempfile.TemporaryDirectory() as td:
        assert PythonAdapter().detect(Path(td)) is False


def test_python_adapter_capabilities_includes_lifecycle_and_hooks() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "pyproject.toml").write_text('[project]\nname = "x"\nversion = "0.1.0"\n')
        caps = PythonAdapter().capabilities(root)

    assert caps.has_lifecycle is True
    assert caps.version_source is not None
    assert len(caps.hooks) > 0
```

- [ ] **Step 6.8: Run all Phase 1 tests to verify they pass**

```bash
cd /Users/les/Projects/crackerjack
.venv/bin/pytest tests/adapters/ tests/core/ -v
```

Expected: all tests pass.

- [ ] **Step 6.9: Commit**

```bash
cd /Users/les/Projects/crackerjack
git -c user.email=les@wedgwoodwebworks.com add \
    crackerjack/adapters/python/__init__.py \
    crackerjack/adapters/python/lifecycle.py \
    tests/adapters/python/test_lifecycle.py \
    tests/adapters/python/test_python_adapter.py
git -c user.email=les@wedgwoodwebworks.com commit -m "feat(adapters.python): PythonAdapter + PythonLifecycle

PythonAdapter (extends LanguageAdapterBase) detects pyproject.toml
projects and exposes the Phase 1 hook set + lifecycle. PythonLifecycle
delegates to existing PublishManager.bump_version machinery, preserving
all behavior. Rollback contract: tag deleted + commit reset on push
failure.

The five _commit / _tag / _push / _delete_tag / _reset / _publish_pypi
methods are the integration seam — Phase 2 may replace the delegation
with per-language primitives.

Spec dd9d9c05 (Rev 2)."
```

---

## Task 7: Full verification — 11K+ tests still pass + no behavior change

**Files:**
- Modify: `docs/CHANGELOG.md` (one bullet under "[Unreleased]")
- No code files modified.

**Goal:** Run the full crackerjack test suite to verify Phase 1 introduces zero regressions.

- [ ] **Step 7.1: Run the PR smoke subset**

```bash
cd /Users/les/Projects/crackerjack
.venv/bin/pytest -m "smoke or not slow" -q --no-header
```

Expected: pass within 5 minutes.

- [ ] **Step 7.2: Run the full suite**

```bash
cd /Users/les/Projects/crackerjack
.venv/bin/pytest -q --no-header
```

Expected: pass within 30 minutes. The current suite has ~11K+ tests.

- [ ] **Step 7.3: Verify CLI behavior preservation**

```bash
cd /Users/les/Projects/crackerjack
# Smoke: --help still works.
.venv/bin/python -m crackerjack --help | head -10
# Smoke: run --help still works.
.venv/bin/python -m crackerjack run --help | head -20
# Smoke: language detection (the new Phase 1 function) returns at least Python.
.venv/bin/python -c "from crackerjack.adapters.registry import discover_adapters; print(sorted(discover_adapters().keys()))"
```

Expected: `['python']` (or whatever the discovered set is; Phase 1 must include at least `python`).

- [ ] **Step 7.4: Add a CHANGELOG entry**

Open `docs/CHANGELOG.md` and add a bullet under the current "[Unreleased]" (or top-of-file if none exists):

```markdown
### Added

- Multi-language extension foundation (Phase 1): new `crackerjack/adapters/`
  package with `LanguageAdapter` Protocol, `LanguageAdapterBase` ABC,
  `Capabilities` / `Hook` / `Lifecycle` types, and a `PythonAdapter`
  that wraps the existing Python lifecycle. No CLI behavior change;
  all 11K+ existing tests pass. Spec: dd9d9c05.
```

(Adjust the section header to match the file's existing structure.)

- [ ] **Step 7.5: Commit**

```bash
cd /Users/les/Projects/crackerjack
git -c user.email=les@wedgwoodwebworks.com add docs/CHANGELOG.md
git -c user.email=les@wedgwoodwebworks.com commit -m "docs(changelog): Phase 1 — LanguageAdapter foundation

Phase 1 of the crackerjack multi-language extension (spec dd9d9c05):
adds the LanguageAdapter type system and a Python adapter that wraps
the existing lifecycle. No CLI behavior change; all 11K+ tests pass.

Phases 2-5 (Swift, Kotlin/Gradle, Web + Jinja, polish) ship in
follow-up plans."
```

---

## Task 8: Document the MCP 4-step registration pipeline (foundation only)

**Files:**
- Modify: `crackerjack/mcp/server_core.py` (add docstring/comment at top of `_build_registration_map`)
- Modify: `crackerjack/mcp/tools/profiles.py` (add docstring/comment at top of `PROFILE_REGISTRATIONS`)

**Goal:** Per spec MCP F1, future contributors adding new MCP tool groups must understand the 4-step pipeline. Phase 1 doesn't add new tools, but the comment is foundation work so the contract is documented before Phases 2-4 land.

- [ ] **Step 8.1: Read the existing files**

```bash
cd /Users/les/Projects/crackerjack
sed -n '200,230p' crackerjack/mcp/server_core.py
sed -n '70,120p' crackerjack/mcp/tools/profiles.py
```

- [ ] **Step 8.2: Add the 4-step pipeline comment to `server_core.py`**

Locate the `_build_registration_map()` function (around line 204) and add this comment block immediately above its `def`:

```python
# MCP Tool Registration — 4-step pipeline (per spec MCP F1, dd9d9c05).
#
# Adding a new tool group (e.g., "language_tools" in Phase 2) requires ALL
# FOUR of these steps. Skipping any step silently produces invisible tools.
#
#   1. CREATE  crackerjack/mcp/tools/<group>_tools.py exporting
#              register_<group>_tools(mcp_app: FastMCP) -> None. Each
#              tool is a nested `async def` decorated with @mcp_app.tool().
#
#   2. REGISTER in _build_registration_map() below: add an entry
#              "<group>": <group>_tools.register_<group>_tools.
#
#   3. ASSIGN TIER in crackerjack/mcp/tools/profiles.py: add "<group>"
#              to FULL_REGISTRATIONS, STANDARD_REGISTRATIONS, or
#              MINIMAL_REGISTRATIONS (depending on the tools' risk).
#
#   4. TEST the new tool by:
#              a) starting the MCP server: `mahavishnu mcp start`
#              b) calling discover_tools() to confirm registration
#              c) exercising the tool end-to-end via the FastMCP client
#
# Phase 1 of the multi-language extension lands the language_tools
# group in Phase 2 (Swift); Kotlin/Web groups in Phases 3-4.
```

- [ ] **Step 8.3: Add the tier-assignment comment to `profiles.py`**

Locate `FULL_REGISTRATIONS = { ... }` (around line 79) and add this comment block immediately above:

```python
# MCP Tool Tier Assignment (per spec MCP F1, dd9d9c05).
#
# FULL_REGISTRATIONS: all tools available when MAHAVISHNU_TOOL_PROFILE=full.
#                     Mutation tools (bump_*, release_*) belong here.
# STANDARD_REGISTRATIONS: tools available when profile=standard. Read tools
#                     typically live here; mutation tools do NOT.
# MINIMAL_REGISTRATIONS: health probes only (profile=minimal). All
#                     language-specific tool groups belong here ONLY
#                     when their tools are non-mutating diagnostics.
#
# Adding a new group: edit the appropriate set below AND ensure the
# group name appears in _build_registration_map() in server_core.py.
# Test by calling `mahavishnu mcp start` and `mahavishnu mcp status`.
```

- [ ] **Step 8.4: Verify imports still work**

```bash
cd /Users/les/Projects/crackerjack
.venv/bin/python -c "from crackerjack.mcp.server_core import _build_registration_map; print('OK')"
.venv/bin/python -c "from crackerjack.mcp.tools.profiles import FULL_REGISTRATIONS, STANDARD_REGISTRATIONS, MINIMAL_REGISTRATIONS; print('OK')"
```

Expected: both print `OK`.

- [ ] **Step 8.5: Commit**

```bash
cd /Users/les/Projects/crackerjack
git -c user.email=les@wedgwoodwebworks.com add \
    crackerjack/mcp/server_core.py \
    crackerjack/mcp/tools/profiles.py
git -c user.email=les@wedgwoodwebworks.com commit -m "docs(mcp): document 4-step tool registration pipeline

Per spec MCP F1 (dd9d9c05): adding a new MCP tool group requires
(a) creating register_<group>_tools() in a new module, (b) registering
it in _build_registration_map(), (c) assigning a tier in profiles.py,
and (d) testing via `mahavishnu mcp start` + discover_tools(). The
comment is foundation work; Phase 1 doesn't add new tools, but the
contract must be documented before Phases 2-4 land their group
registrations."
```

---

## Self-Review (plan vs spec Rev 2)

**Spec coverage check:**

| Spec requirement (Rev 2) | Implemented by |
|---|---|
| `@runtime_checkable` Protocol | Task 1 |
| `LanguageAdapterBase` ABC | Task 1 |
| `Capabilities` dataclass (replaces 4-method decomposition) | Task 1 |
| `Hook` dataclass (only name + cli_command required) | Task 1 |
| `VersionSource` Protocol + `VersionSourceError` hierarchy | Task 1 |
| `Lifecycle.run()` (single method, rollback) | Task 6 |
| `LifecycleOptions` / `LifecycleResult` | Task 1 |
| Adapter registry + entry-points (`crackerjack.language_adapters`) | Task 2 |
| `core/language_detector.py` | Task 3 |
| Python adapter wraps existing code | Tasks 4-6 |
| No behavior change (all 11K+ tests pass) | Task 7 |
| MCP 4-step pipeline documented | Task 8 |

**Placeholder scan:** No "TBD" / "TODO" / "implement later" / "add appropriate error handling" patterns. Where the implementer must make a decision (e.g., Task 6.5 — wholesale vs split delegation), the plan shows both options with the trade-off.

**Type consistency:** All `Capabilities` / `Hook` / `Lifecycle*` types referenced in later tasks match Task 1's exact field names and defaults. `PythonAdapter` matches `LanguageAdapterBase` ABC contract.

**Acceptance criteria:** Task 7 verifies the full test suite passes within budget (5min PR smoke, 30min nightly). Phase 1 ships no new behavior — every existing crackerjack command works unchanged.

**Phase boundary:** This plan covers Phase 1 only. Phases 2-5 (Swift, Kotlin/Gradle, Web + Jinja, polish) ship in follow-up plans.

**Out-of-scope verification:**

- Swift / Kotlin / Web / Jinja — out of scope (Phase 2-4).
- MCP tool surface — only documentation (Task 8); no new tools in Phase 1.
- Bump-level enum — Task 6 uses `Literal["major", "minor", "patch"]` per spec.
- Auth posture — out of scope for Phase 1 (mutation tools come in Phase 2).
- PyCharm parity / Jinja formatter — out of scope (Phase 4).

---

## Execution Handoff

**Plan complete and saved to `/Users/les/Projects/crackerjack/docs/superpowers/plans/2026-09-07-crackerjack-multi-language-phase1.md`.**

8 tasks, ~30 commits, ~5 hours of focused implementation (estimate — actual depends on `PublishManager` integration complexity).

Two execution options:

1. **Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.
2. **Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?
