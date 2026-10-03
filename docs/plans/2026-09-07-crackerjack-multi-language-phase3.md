---
status: shipped
role: implementation
topic: architecture
date: 2026-09-09
last_reviewed: 2026-09-09
superseded_by: null
blocks_on: []
---

# Crackerjack Multi-Language Extension — Phase 3 (Kotlin/Gradle) Plan

> **For agentic workers:** REQUIRED SUB-KILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Rev 2** — post-multi-agent review. **See end-of-doc "Spec Revision Notes"** for the 8 spec amendments this plan argues for (CRITICAL naming drift + Phase 2 carry-over bugs).
>
> **Status:** Ready for execution.

**Goal:** Add a Kotlin/Gradle language adapter to crackerjack that activates only when `build.gradle.kts` (or `build.gradle`) is present. Provides Kotlin lifecycle (gradle.properties bump + git tag/push) + three Kotlin hooks (ktlint, detekt, test) with Gradle task probing + MCP tools for both lifecycle and hooks.

**Architecture:** Approach A (per spec Rev 2) extended with Kotlin. New `crackerjack/adapters/kotlin/{version_source,hooks,lifecycle,git_backend}.py` packages + `KotlinAdapter` extending `LanguageAdapterBase`. Phase 1 types (`LanguageAdapter` Protocol, `LanguageAdapterBase` ABC, `Capabilities`, `Hook`, `Lifecycle`, `VersionSource`) are reused unchanged. Phase 2's `LanguageAdapter`-derived types (`SwiftLifecycle`, `SwiftAdapter`, etc.) coexist — Phase 3 does NOT modify Swift. New MCP tools (`kotlin_bump_version`, `kotlin_list_hooks`) are added to the existing `language_tools` group registered in Phase 2 (no profile.py changes needed since the group is already in `FULL_REGISTRATIONS`).

**Tech Stack:** Python 3.14, FastMCP 4.x, typer 0.26+, hatchling, Git CLI (via subprocess), Gradle CLI (`./gradlew`, subprocess invocation, no shell), gh CLI for GitHub release creation.

**Spec:** `/Users/les/Projects/crackerjack/docs/superpowers/specs/2026-09-07-crackerjack-multi-language-design.md` (Rev 2, on `main` as of commit `b00b36f0`).

**Reviews:** None yet. Phase 3 plan should be reviewed via 9-lens multi-agent review before execution (mirror Phase 2's review process).

---

## Global Constraints

Verbatim from the spec and project (Phase 2's constraints carry forward unchanged unless noted):

- **Python 3.14** with `from __future__ import annotations` as the first non-comment line of every source file.
- **Modern syntax**: `X | None`, `list[str]`, `pathlib.Path`.
- **Default-`None` args typed `X | None = None`** (mypy `no_implicit_optional = true`).
- **No `assert` in production code** (`crackerjack/adapters/kotlin/**/*.py` is production).
- **No `Any`** in production code. Tests may use `Any` for mocks.
- **`logger.exception(...)`** in `except` blocks.
- **All I/O async.** Subprocess via `asyncio.to_thread` or `loop.run_in_executor`. Sync only at CLI entry points.
- **argv list, no shell** for all subprocess invocations. `--` separator before user-influenced positionals.
- **Imports sorted within each section** (stdlib → third-party → first-party). NO late imports except for circular-import deferral.
- **Remove unused imports and dead code immediately** (Ruff F401 / UP).
- **`@runtime_checkable` Protocol** for `LanguageAdapter` (per spec API F1).
- **`Capabilities` is a frozen dataclass**.
- **`Hook` only requires `name` and `cli_command`**; all other fields default.
- **`Lifecycle.run(LifecycleOptions) -> LifecycleResult`** with rollback contract.
- **MCP tools added to existing `language_tools` group** (Phase 2 already registered this group in `_build_registration_map()` in `crackerjack/mcp/tools/profiles.py` — NOT `server_core.py`. **No `profiles.py` changes needed** for Phase 3 since we're adding tools to an already-registered group).
- **Auth posture for mutation tools** (per spec MCP F5): `MAHAVISHNU_AUTH_ENABLED=true` + `MAHAVISHNU_JWT_SECRET` required. Mutation tools refuse to operate if absent. **Per-invocation check** (not startup-only — Phase 2 ruling 7 carries forward).
- **`KotlinAdapter` lifecycle bumps `gradle.properties`** (NOT `build.gradle.kts`). Typical Kotlin convention keeps version metadata in properties file, not the build script.
- **All Gradle invocations MUST pass `--no-daemon --no-configuration-cache`** (per spec Kotlin F1). Daemon modes are CI-unreliable.
- **Gradle task probing**: probe with `./gradlew tasks --all -q --no-daemon --no-configuration-cache` BEFORE invoking any Gradle task (per spec Kotlin F2). Skip-with-warning if task absent.
- **Hybrid fallback** (per spec Writing F2): one canonical interpretation only — when CLI is missing AND fallback is set, invoke Python fallback; when fallback also raises, fail with installation instructions.
- **Tests**: use `tempfile.TemporaryDirectory()`, `monkeypatch.setattr(shutil, "which", ...)`, `pytest.raises`, and shared test helpers (no duplication).
- **Constructor injection over monkey-patching** (per F4 of security lens and F1 of simplification lens, Phase 2 ruling): `KotlinLifecycle.__init__` accepts the 6 git/gh methods as `Callable` parameters; tests pass mocks directly. NO `lifecycle._commit = mock_fn` assignments.
- **`asyncio.to_thread` for sync subprocess** inside async MCP handlers (per MCP F7).
- **`project_root` validated** via `Path(project_root).resolve(strict=True)` + `MAHAVISHNU_PROJECT_ROOTS` allowlist (per Security F2, Phase 2).
- **Tag name format validated** against semver regex (per Security F7, Phase 2).
- **Pre-flight `git status --porcelain`** before `git reset --hard` (per Security F6, Phase 2).
- **`gh release create` raises on non-zero exit** (no fabricated fallback URLs per Security F3, Phase 2).
- **`_bump` divergence policy (per Phase 2 final review CF-3)**: each adapter defines its own `_bump` with an explicit docstring documenting its semantics. **Phase 3 Kotlin semantics: real semver** — `"major"` bumps `major` (matches Python). Phase 2 Swift uses pre-1.0 semantics (major bumps minor). Document the divergence in `KotlinLifecycle._bump`'s docstring AND in `SwiftLifecycle._bump`'s docstring (the Phase 2 docstring already states pre-1.0; Phase 3 just adds a cross-reference comment).
- **`MAHAVISHNU_GIT_REMOTE` env var** configures push remote, defaulting to `origin` (per Phase 2 fix in commit `b2199190`).
- **`git tag -a -m M -- N`** ordering (per Phase 2 fix in commit `b2199190`): `-a` flag, then `-m message`, then `--`, then positional tag name.
- **Author email `les <les@wedgwoodwebworks.com>`** for every commit (per memory `git-author-email-correct-domain.md`).
- **Module docstring required** for every new Python file (per Writing HIGH-3 from Phase 3 review). Docstrings explain purpose and any non-obvious contract; not just a 1-line summary.
- **`monkeypatch.setattr(shutil, "which", ...)`** is the mandated pattern (per spec Testing F3). `mock.patch.object(shutil, "which", ...)` violates the spec; use `mock.patch.object` only for project-local objects (e.g., `mock.patch.object(GradleTaskProbe, "has_task", ...)`).

---

## File Structure

### New files (Phase 3)

```
crackerjack/
├── adapters/kotlin/                                 # NEW
│   ├── __init__.py                                 # exports KotlinAdapter
│   ├── version_source.py                           # GradlePropertiesVersionSource
│   │                                               # (gradle.properties → build.gradle.kts → ./gradlew properties)
│   ├── hooks.py                                    # ktlint, detekt, test hooks + GradleTaskProbe
│   ├── lifecycle.py                                # KotlinLifecycle — bumps gradle.properties + 6 git/gh methods
│   │                                               # via constructor injection
│   └── git_backend.py                              # Default subprocess git/gh backend (real implementations;
│                                                   # mirror Swift's, identical 6 functions)

mcp/
└── tools/
    └── language_tools.py                           # MODIFIED (Phase 3): adds kotlin_bump_version (mutation)
                                                    # + kotlin_list_hooks. swift_* tools preserved unchanged.

tests/
├── adapters/kotlin/
│   ├── __init__.py
│   ├── _gradle_helpers.py                          # shared test helpers (no duplication)
│   ├── test_version_source.py
│   ├── test_hooks.py
│   ├── test_lifecycle.py                           # uses constructor-injected fakes
│   └── test_kotlin_adapter.py
└── fixtures/
    └── gradle-vanilla/                             # Real Gradle fixture (vanilla Kotlin lib)
        ├── settings.gradle.kts                     # minimal settings
        ├── build.gradle.kts                        # kotlin("jvm") plugin only
        └── src/main/kotlin/Hello.kt                # trivial implementation
```

### Modified files (Phase 3)

```
crackerjack/
├── adapters/registry.py                            # no changes — Phase 2 fix in commit b2199190 already
│                                                   # handles class entry points generically
├── mcp/tools/
│   ├── language_tools.py                           # MODIFIED: add kotlin_bump_version + kotlin_list_hooks
│   └── profiles.py                                 # no changes — language_tools group already registered
pyproject.toml                                      # MODIFIED: add kotlin entry-point
                                                   # (`kotlin = "crackerjack.adapters.kotlin:KotlinAdapter"`)
```

### Files NOT modified

- `crackerjack/adapters/swift/**` — Swift stays untouched. Phase 3 does not refactor Swift.
- `crackerjack/adapters/python/**` — Python stays untouched.
- `crackerjack/mcp/server_core.py` — NOT modified. Per Phase 2 BLOCKER B2, registration lives in `profiles.py`.

---

## Task 1: Foundation — register Kotlin entry-point

**Files:**
- Modify: `pyproject.toml` (one-line addition)
- Test: `python -c "import importlib.metadata; [print(e.name) for e in importlib.metadata.entry_points(group='crackerjack.language_adapters')]"` (manual smoke)

**Interfaces:**
- Consumes: Phase 1 `LanguageAdapterBase` ABC, Phase 1 `discover_adapters()` registry.
- Produces: `kotlin` entry-point name registered. Class is unresolvable until Task 6 lands the `KotlinAdapter` class.

- [ ] **Step 1: Verify current entry-point table**

Run: `grep -A 5 "crackerjack.language_adapters" pyproject.toml`
Expected: 2 entries (python, swift).

- [ ] **Step 2: Add Kotlin entry-point**

In `pyproject.toml`, under `[project.entry-points."crackerjack.language_adapters"]`, add:
```toml
kotlin = "crackerjack.adapters.kotlin:KotlinAdapter"
```

Keep entries alphabetical (python, swift, kotlin).

- [ ] **Step 3: Verify the table**

Run: `grep -A 5 "crackerjack.language_adapters" pyproject.toml`
Expected: 3 entries (python, swift, kotlin). Kotlin entry is declared but unresolvable until Task 6 (expected; matches Phase 2 Task 1's behavior).

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml
git commit -m "feat(adapters): register Kotlin entry-point under crackerjack.language_adapters"
```

---

## Task 2: `version_source.py` — GradlePropertiesVersionSource

**Files:**
- Create: `crackerjack/adapters/kotlin/__init__.py` (empty marker — full `__init__.py` lands in Task 6)
- Create: `crackerjack/adapters/kotlin/version_source.py`
- Test: `tests/adapters/kotlin/__init__.py` (empty marker), `tests/adapters/kotlin/test_version_source.py`

**Interfaces:**
- Consumes: Phase 1 `VersionSource` Protocol, `VersionNotFoundError`, `VersionWriteError` from `crackerjack/adapters/base.py`.
- Produces: `GradlePropertiesVersionSource` class implementing `VersionSource` (read + write methods). Pure file I/O for the gradle.properties probe + build.gradle.kts fallback; subprocess only for the `./gradlew properties` fallback path.

**Sub-task 2.1: gradle.properties probe + build.gradle.kts scan (no subprocess)**

Implement the first two tiers of `read()`:
- Tier 1: parse `gradle.properties` for keys `pluginVersion`, `projectVersion`, `version` (in that order). Anchored with `\b`. Skip comments (`#`) and whitespace-only lines.
- Tier 2: parse `build.gradle.kts` then `build.gradle` for `version = "X.Y.Z"` (regex `^\s*version\s*=\s*"([^"]+)"`).
- Tier 3 (Task 2.2): fallback to `./gradlew properties`.

**Sub-task 2.2: ./gradlew properties fallback**

Implement `_read_via_gradle()` using subprocess:
```python
result = subprocess.run(
    ["./gradlew", "properties", "-q", "--no-daemon", "--no-configuration-cache"],
    cwd=self._project_root, capture_output=True, text=True,
)
if result.returncode != 0:
    raise VersionNotFoundError(f"`gradlew properties` failed: {result.stderr}")
m = re.search(r"^version:\s*(\S+)", result.stdout, re.MULTILINE)
if not m:
    raise VersionNotFoundError("`gradlew properties` did not emit a `version:` line")
return m.group(1)
```

- [ ] **Step 1: Write the failing tests**

```python
# tests/adapters/kotlin/test_version_source.py
from __future__ import annotations

from pathlib import Path
import pytest

from crackerjack.adapters.base import VersionNotFoundError
from crackerjack.adapters.kotlin.version_source import GradlePropertiesVersionSource


def test_read_from_gradle_properties_plugin_version(tmp_path: Path) -> None:
    (tmp_path / "gradle.properties").write_text("pluginVersion=1.2.3\n")
    src = GradlePropertiesVersionSource(tmp_path)
    assert src.read() == "1.2.3"


def test_read_from_gradle_properties_project_version(tmp_path: Path) -> None:
    (tmp_path / "gradle.properties").write_text("projectVersion=2.0.0\n")
    src = GradlePropertiesVersionSource(tmp_path)
    assert src.read() == "2.0.0"


def test_read_from_gradle_properties_version(tmp_path: Path) -> None:
    (tmp_path / "gradle.properties").write_text("version=0.1.0\n")
    src = GradlePropertiesVersionSource(tmp_path)
    assert src.read() == "0.1.0"


def test_read_falls_back_to_build_gradle_kts(tmp_path: Path) -> None:
    (tmp_path / "build.gradle.kts").write_text('version = "1.5.0"\n')
    src = GradlePropertiesVersionSource(tmp_path)
    assert src.read() == "1.5.0"


def test_read_raises_version_not_found_when_nothing_matches(tmp_path: Path) -> None:
    src = GradlePropertiesVersionSource(tmp_path)
    with pytest.raises(VersionNotFoundError):
        src.read()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/adapters/kotlin/test_version_source.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'crackerjack.adapters.kotlin'`.

- [ ] **Step 3: Implement GradlePropertiesVersionSource (file-probe tiers)**

Create `crackerjack/adapters/kotlin/__init__.py` (empty) and `crackerjack/adapters/kotlin/version_source.py`:

```python
from __future__ import annotations

import logging
import re
import subprocess
from pathlib import Path

from crackerjack.adapters.base import VersionNotFoundError, VersionSource

logger = logging.getLogger(__name__)


class GradlePropertiesVersionSource:
    """Probe gradle.properties for version, with multiple key conventions.

    Order (anchored with \\b): pluginVersion, projectVersion, version.
    Falls back to build.gradle.kts scan. Always verifies via Gradle
    (Gradle is source of truth) when neither file-probe tier matches.
    """

    _PROBE_KEYS = ("pluginVersion", "projectVersion", "version")

    def __init__(self, project_root: Path) -> None:
        self._project_root = project_root

    def read(self) -> str:
        properties_path = self._project_root / "gradle.properties"
        if properties_path.exists():
            content = properties_path.read_text()
            for key in self._PROBE_KEYS:
                m = re.search(rf"\b{re.escape(key)}\s*=\s*(\S+?)[,\s]*$", content, re.MULTILINE)
                if m:
                    return m.group(1)
        for gradle_file in ("build.gradle.kts", "build.gradle"):
            path = self._project_root / gradle_file
            if path.exists():
                content = path.read_text()
                m = re.search(r'^\s*version\s*=\s*"([^"]+)"', content, re.MULTILINE)
                if m:
                    return m.group(1)
        return self._read_via_gradle()

    def _read_via_gradle(self) -> str:
        result = subprocess.run(
            ["./gradlew", "properties", "-q", "--no-daemon", "--no-configuration-cache"],
            cwd=self._project_root, capture_output=True, text=True,
        )
        if result.returncode != 0:
            raise VersionNotFoundError(f"`gradlew properties` failed: {result.stderr}")
        m = re.search(r"^version:\s*(\S+)", result.stdout, re.MULTILINE)
        if not m:
            raise VersionNotFoundError("`gradlew properties` did not emit a `version:` line")
        return m.group(1)

    def write(self, new_version: str) -> None:
        properties_path = self._project_root / "gradle.properties"
        if not properties_path.exists():
            raise FileNotFoundError(
                f"gradle.properties not found at {properties_path}; cannot write version"
            )
        content = properties_path.read_text()
        written = False
        for key in self._PROBE_KEYS:
            pattern = rf"^(\s*)({re.escape(key)}\s*=\s*)(\S+?)([,\s]*)$"
            new_content, count = re.subn(pattern, rf"\1\2{new_version}\4", content, flags=re.MULTILINE)
            if count:
                content = new_content
                written = True
                break
        if not written:
            # No existing key — append at end of file
            content = content.rstrip("\n") + f"\nversion={new_version}\n"
        properties_path.write_text(content)
        verified = self.read()
        if verified != new_version:
            from crackerjack.adapters.base import VersionWriteError
            raise VersionWriteError(
                f"Write verification failed: wrote {new_version!r}, read back {verified!r}"
            )


def gradle_properties_version_source(project_root: Path) -> VersionSource:
    """Factory matching the Phase 1 VersionSource Protocol shape.

    Returns the underlying object typed as VersionSource; concrete class is
    `GradlePropertiesVersionSource`. Use this factory for parity with
    `git_tag_version_source()` (Phase 2).
    """
    return GradlePropertiesVersionSource(project_root)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/adapters/kotlin/test_version_source.py -v`
Expected: 5 passed (the 5 file-probe tests above; the gradlew fallback is exercised in Task 8 verification).

- [ ] **Step 5: Commit**

```bash
git add crackerjack/adapters/kotlin/__init__.py \
        crackerjack/adapters/kotlin/version_source.py \
        tests/adapters/kotlin/__init__.py \
        tests/adapters/kotlin/test_version_source.py
git commit -m "feat(adapters.kotlin): GradlePropertiesVersionSource reads from gradle.properties"
```

---

## Task 3: `hooks.py` — Kotlin hooks with GradleTaskProbe

**Files:**
- Create: `crackerjack/adapters/kotlin/hooks.py`
- Test: `tests/adapters/kotlin/test_hooks.py`

**Interfaces:**
- Consumes: Phase 1 `Hook` dataclass from `crackerjack/adapters/base.py`.
- Produces: `GradleTaskProbe` class with `has_task(task_name) -> bool` method, and `kotlin_hooks(project_root: Path) -> tuple[Hook, ...]` factory returning the 3 hooks.

- [ ] **Step 1: Write the failing tests**

```python
# tests/adapters/kotlin/test_hooks.py
from __future__ import annotations

import shutil
from pathlib import Path
from unittest import mock

import pytest

from crackerjack.adapters.kotlin.hooks import GradleTaskProbe, kotlin_hooks


def test_kotlin_hooks_returns_three_hooks_when_all_tasks_present(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "build.gradle.kts").write_text("")
    monkeypatch.setattr(shutil, "which", lambda cmd: "/usr/bin/gradlew" if cmd == "shutil.which" else None)
    with mock.patch.object(GradleTaskProbe, "has_task", return_value=True):
        hooks = kotlin_hooks(tmp_path)
    names = {h.name for h in hooks}
    assert names == {"kotlin.ktlint", "kotlin.detekt", "kotlin.test"}


def test_kotlin_hooks_filters_absent_tasks_with_warning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Per spec Kotlin F2: skip-with-warning if task is absent."""
    (tmp_path / "build.gradle.kts").write_text("")
    monkeypatch.setattr(shutil, "which", lambda cmd: "/usr/bin/gradlew" if cmd == "shutil.which" else None)

    # Probe returns False for ktlintCheck (simulating absent plugin)
    def fake_has_task(self, task_name: str) -> bool:
        return task_name == "detekt"  # ktlintCheck absent, detekt present

    with mock.patch.object(GradleTaskProbe, "has_task", fake_has_task):
        with caplog.at_level("WARNING"):
            hooks = kotlin_hooks(tmp_path)
    names = {h.name for h in hooks}
    assert "kotlin.detekt" in names
    assert "kotlin.ktlint" not in names  # filtered out
    assert "kotlin.test" in names  # always present
    assert any("Skipping kotlin.ktlint" in r.message for r in caplog.records)


def test_kotlin_hooks_uses_gradlew_subprocess(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "build.gradle.kts").write_text("")
    monkeypatch.setattr(shutil, "which", lambda cmd: "/usr/bin/gradlew" if cmd == "shutil.which" else None)
    with mock.patch.object(GradleTaskProbe, "has_task", return_value=True):
        hooks = kotlin_hooks(tmp_path)
    ktlint = next(h for h in hooks if h.name == "kotlin.ktlint")
    assert ktlint.cli_command[:2] == ("./gradlew", "ktlintCheck")


def test_kotlin_detekt_uses_gradlew_detekt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "build.gradle.kts").write_text("")
    monkeypatch.setattr(shutil, "which", lambda cmd: "/usr/bin/gradlew" if cmd == "shutil.which" else None)
    with mock.patch.object(GradleTaskProbe, "has_task", return_value=True):
        hooks = kotlin_hooks(tmp_path)
    detekt = next(h for h in hooks if h.name == "kotlin.detekt")
    assert detekt.cli_command[:2] == ("./gradlew", "detekt")


def test_kotlin_test_uses_gradlew_test(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "build.gradle.kts").write_text("")
    monkeypatch.setattr(shutil, "which", lambda cmd: "/usr/bin/gradlew" if cmd == "shutil.which" else None)
    with mock.patch.object(GradleTaskProbe, "has_task", return_value=True):
        hooks = kotlin_hooks(tmp_path)
    test = next(h for h in hooks if h.name == "kotlin.test")
    assert test.cli_command[:2] == ("./gradlew", "test")


def test_gradle_task_probe_returns_true_when_task_present(tmp_path: Path) -> None:
    probe = GradleTaskProbe(tmp_path)
    with mock.patch("subprocess.run") as mock_run:
        mock_run.return_value.stdout = "ktlintCheck - Run ktlint\ndetekt - Run detekt\n"
        mock_run.return_value.returncode = 0
        assert probe.has_task("ktlintCheck") is True


def test_gradle_task_probe_returns_false_when_task_absent(tmp_path: Path) -> None:
    probe = GradleTaskProbe(tmp_path)
    with mock.patch("subprocess.run") as mock_run:
        mock_run.return_value.stdout = "test - Run tests\n"
        mock_run.return_value.returncode = 0
        assert probe.has_task("ktlintCheck") is False


def test_gradle_task_probe_returns_false_when_gradlew_fails(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Per Kotlin HIGH #5: probe must distinguish gradlew failure from absent task."""
    probe = GradleTaskProbe(tmp_path)
    with mock.patch("subprocess.run") as mock_run:
        mock_run.return_value.stdout = ""
        mock_run.return_value.returncode = 1
        mock_run.return_value.stderr = "gradlew not found"
        with caplog.at_level("WARNING"):
            result = probe.has_task("ktlintCheck")
    assert result is False
    assert any("gradlew tasks --all failed" in r.message for r in caplog.records)


def test_gradle_task_probe_passes_no_daemon_no_configuration_cache(tmp_path: Path) -> None:
    probe = GradleTaskProbe(tmp_path)
    with mock.patch("subprocess.run") as mock_run:
        mock_run.return_value.stdout = ""
        mock_run.return_value.returncode = 0
        probe.has_task("ktlintCheck")
    args = mock_run.call_args[0][0]
    assert "--no-daemon" in args
    assert "--no-configuration-cache" in args
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/adapters/kotlin/test_hooks.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'crackerjack.adapters.kotlin.hooks'`.

- [ ] **Step 3: Implement GradleTaskProbe + kotlin_hooks**

Create `crackerjack/adapters/kotlin/hooks.py`:

```python
"""Kotlin/Gradle hooks and task probing for crackerjack.

Per spec Kotlin F2: probes with `./gradlew tasks --all` before emitting a
hook. Tasks that are absent in the project's plugin set are filtered
out with a `logger.warning()` so the user knows the hook is skipped.
"""

from __future__ import annotations

import logging
import re
import subprocess
from pathlib import Path

from crackerjack.adapters.base import Hook

logger = logging.getLogger(__name__)


class GradleTaskProbe:
    """Detect whether a Gradle task exists before invoking it.

    Per spec Kotlin F2: probe with `./gradlew tasks --all -q --no-daemon
    --no-configuration-cache` before invoking any Gradle task.
    """

    def __init__(self, project_root: Path) -> None:
        self._project_root = project_root

    def has_task(self, task_name: str) -> bool:
        result = subprocess.run(
            ["./gradlew", "tasks", "--all", "-q", "--no-daemon", "--no-configuration-cache"],
            cwd=self._project_root, capture_output=True, text=True,
        )
        if result.returncode != 0:
            logger.warning(
                "`gradlew tasks --all` failed (exit %d); treating %r as absent. "
                "stderr: %s",
                result.returncode,
                task_name,
                result.stderr.strip(),
            )
            return False
        return bool(re.search(rf"^{re.escape(task_name)}\s+", result.stdout, re.MULTILINE))


_HOOK_TASK_MAP: dict[str, str] = {
    "kotlin.ktlint": "ktlintCheck",
    "kotlin.detekt": "detekt",
}


def _build_hooks(project_root: Path) -> tuple[Hook, ...]:
    """Build the three Kotlin hooks, filtering out absent tasks with a warning.

    Per spec Kotlin F2: skip-with-warning if the task is absent.
    `kotlin.test` is always emitted (every Kotlin project has the `test` task
    if the kotlin/jvm plugin is applied; absence here is a plugin error, not
    a hook concern).
    """
    probe = GradleTaskProbe(project_root)
    gradlew = ("./gradlew",)
    hooks: list[Hook] = []
    for hook_name, task_name in _HOOK_TASK_MAP.items():
        if probe.has_task(task_name):
            hooks.append(Hook(name=hook_name, cli_command=(*gradlew, task_name)))
        else:
            logger.warning(
                "Skipping %s hook: `%s` task absent (add the plugin that provides it).",
                hook_name,
                task_name,
            )
    hooks.append(Hook(name="kotlin.test", cli_command=(*gradlew, "test")))
    return tuple(hooks)


def kotlin_hooks(project_root: Path) -> tuple[Hook, ...]:
    """Return the three Kotlin hooks for a Gradle project root.

    Tasks that are absent in the project's plugin set are filtered out
    with a `logger.warning()`. `kotlin.test` is always emitted.
    """
    return _build_hooks(project_root)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/adapters/kotlin/test_hooks.py -v`
Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add crackerjack/adapters/kotlin/hooks.py tests/adapters/kotlin/test_hooks.py
git commit -m "feat(adapters.kotlin): KotlinHooks with GradleTaskProbe"
```

---

## Task 4: `git_backend.py` — default subprocess git/gh backend

**Files:**
- Create: `crackerjack/adapters/kotlin/git_backend.py`
- Test: `tests/adapters/kotlin/_gradle_helpers.py` (shared helpers, mirror Phase 2's `_git_helpers.py`), `tests/adapters/kotlin/test_git_backend.py`

**Interfaces:**
- Consumes: `pathlib.Path`, subprocess.
- Produces: 6 callable functions (`commit`, `tag`, `push`, `delete_tag`, `reset`, `gh_release`) and `make_git_backend(project_root) -> tuple[Callable, ...]` factory.

**Sub-task 4.1: 6 default subprocess methods + factory**

Implement identical to Phase 2's `crackerjack/adapters/swift/git_backend.py`. The implementations are project-agnostic. Refactor to share later if duplication proves costly.

**Sub-task 4.2: shared test helper**

Implement `tests/adapters/kotlin/_gradle_helpers.py` mirroring Phase 2's `tests/adapters/swift/_git_helpers.py::init_git_repo`.

**Phase 2 BLOCKER B1-equivalent pre-flight check**: verify `git tag -a` accepts the message flag before `-m message` and the tag name after `--` (per Phase 2 fix in commit `b2199190`). This is a re-verification; the Swift fix already confirmed this. The Kotlin backend MUST use the same ordering.

- [ ] **Step 1: Write the failing tests (mirror Phase 2's test_git_backend.py)**

```python
# tests/adapters/kotlin/test_git_backend.py
from __future__ import annotations

import subprocess
from pathlib import Path
from unittest import mock

import pytest

from crackerjack.adapters.kotlin.git_backend import (
    commit, delete_tag, gh_release, make_git_backend, push, reset, tag,
)
from tests.adapters.kotlin._gradle_helpers import init_git_repo


def test_commit_runs_git_commit_with_message(tmp_path: Path) -> None:
    init_git_repo(tmp_path)
    sha = commit("initial commit")
    assert len(sha) == 40


def test_commit_refuses_uncommitted_changes(tmp_path: Path) -> None:
    init_git_repo(tmp_path)
    (tmp_path / "untracked.txt").write_text("hi")
    with pytest.raises(RuntimeError, match="uncommitted"):
        commit("nope")


def test_tag_passes_message_flag_before_separator(tmp_path: Path) -> None:
    init_git_repo(tmp_path)
    sha = commit("c1")
    tag("v1.0.0", "release notes")
    result = subprocess.run(
        ["git", "tag", "-l", "--format=%(contents:subject)"],
        cwd=tmp_path, capture_output=True, text=True,
    )
    assert "release notes" in result.stdout


def test_push_uses_configured_remote(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    init_git_repo(tmp_path)
    commit("c1")
    tag("v1.0.0", "msg")
    monkeypatch.setenv("MAHAVISHNU_GIT_REMOTE", "myremote")
    with mock.patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        mock_run.return_value.stderr = ""
        push(sha="dummy", tag_name="v1.0.0")
    args = mock_run.call_args[0][0]
    assert "myremote" in args


def test_push_defaults_to_origin_remote(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MAHAVISHNU_GIT_REMOTE", raising=False)
    init_git_repo(tmp_path)
    commit("c1")
    tag("v1.0.0", "msg")
    with mock.patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        mock_run.return_value.stderr = ""
        push(sha="dummy", tag_name="v1.0.0")
    args = mock_run.call_args[0][0]
    assert "origin" in args


def test_make_git_backend_returns_six_callables(tmp_path: Path) -> None:
    backend = make_git_backend(tmp_path)
    assert len(backend) == 6
    for fn in backend:
        assert callable(fn)


def test_reset_preserves_target_commit(tmp_path: Path) -> None:
    init_git_repo(tmp_path)
    sha = commit("c1")
    tag("v1.0.0", "msg")
    reset(sha)
    # The target commit's tree should still be present
    assert (tmp_path / "README.md").exists()


def test_gh_release_raises_on_nonzero_exit(tmp_path: Path) -> None:
    init_git_repo(tmp_path)
    commit("c1")
    tag("v1.0.0", "msg")
    with mock.patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 1
        mock_run.return_value.stderr = "auth required"
        with pytest.raises(RuntimeError, match="gh release create failed"):
            gh_release("v1.0.0")


def test_gh_release_uses_notes_file_not_generate_notes(tmp_path: Path) -> None:
    init_git_repo(tmp_path)
    commit("c1")
    tag("v1.0.0", "msg")
    with mock.patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "https://example.com/releases/v1.0.0"
        mock_run.return_value.stderr = ""
        gh_release("v1.0.0")
    args = mock_run.call_args[0][0]
    assert "--notes-file" in args
    assert "--generate-notes" not in args
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/adapters/kotlin/test_git_backend.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'crackerjack.adapters.kotlin.git_backend'`.

- [ ] **Step 3: Implement git_backend.py**

Create `crackerjack/adapters/kotlin/git_backend.py`. The implementations are IDENTICAL to Phase 2's `crackerjack/adapters/swift/git_backend.py` (verified at `crackerjack/adapters/swift/git_backend.py` lines 27-158). Copy verbatim, with two header changes:
- Module docstring: replace "Swift" with "Kotlin".
- Logger name: replace `crackerjack.adapters.swift.git_backend` with `crackerjack.adapters.kotlin.git_backend`.

All 6 functions + `make_git_backend(project_root)` factory are reproduced here. The Phase 2 commit `b2199190` already fixed the git tag ordering and hardcoded remote; Phase 3 inherits those fixes.

(For brevity, the full source is reproduced in the plan's appendix; the implementer should diff-verify against the Phase 2 file before copying. The functions: `commit(message) -> str`, `tag(name, message)`, `push(commit_sha, tag_name)`, `delete_tag(name)`, `reset(commit_sha)`, `gh_release(tag_name) -> str`, and `make_git_backend(project_root) -> tuple[Callable, ...]`.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/adapters/kotlin/test_git_backend.py -v`
Expected: 9 passed.

- [ ] **Step 5: Commit**

```bash
git add crackerjack/adapters/kotlin/git_backend.py \
        tests/adapters/kotlin/_gradle_helpers.py \
        tests/adapters/kotlin/test_git_backend.py
git commit -m "feat(adapters.kotlin): default git/gh subprocess backend (mirror Swift)"
```

---

## Task 5: `lifecycle.py` — KotlinLifecycle with constructor-injected methods

**Files:**
- Create: `crackerjack/adapters/kotlin/lifecycle.py`
- Test: `tests/adapters/kotlin/test_lifecycle.py`

**Interfaces:**
- Consumes: Phase 1 `Lifecycle` Protocol, `LifecycleOptions`, `LifecycleResult`, `Lifecycle` types from `crackerjack/adapters/base.py`. Phase 1's `LifecycleOptions.__post_init__` validates `level` against `Literal["major", "minor", "patch"]` (Phase 2 final-review fix; do not re-validate in `KotlinLifecycle.run`).
- Produces: `KotlinLifecycle` class with 6 keyword-only `Callable` constructor parameters (commit/tag/push/delete_tag/reset/gh_release) — matches `SwiftLifecycle`'s constructor shape. **Bumps gradle.properties via `GradlePropertiesVersionSource.write()`** + runs the 6 git/gh methods. Real-semver `_bump()` semantics: `"major"` bumps `major`, `"minor"` bumps `minor`, `"patch"` bumps `patch` (matches Python).

**Sub-task 5.1: `_bump` with real-semver semantics + pre-release qualifier preservation**

```python
import re

_SEMVER_RE = re.compile(
    r"^(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)(?:-(?P<prerelease>[0-9A-Za-z.-]+))?(?:\+[0-9A-Za-z.-]+)?$"
)


def _bump(version: str, level: str) -> str:
    """Real-semver bump: major/minor/patch each bump the named component.

    Preserves pre-release qualifier (e.g. `-SNAPSHOT`, `-RC1`, `-M1`) and
    build metadata (e.g. `+build.123`) unchanged. Real Kotlin/JVM projects
    use these between releases (Kotlin BLOCKER #1 from Phase 3 Kotlin review).

    Cross-adapter divergence: SwiftLifecycle._bump uses pre-1.0 semantics
    (major bumps minor) per its docstring. Kotlin uses real semver, matching
    PythonLifecycle._bump. See Spec Revision Notes §3 (cross-adapter `_bump`).
    """
    m = _SEMVER_RE.match(version)
    if not m:
        raise ValueError(f"version is not valid semver: {version!r}")
    major, minor, patch = int(m["major"]), int(m["minor"]), int(m["patch"])
    prerelease = m["prerelease"]  # may be None
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
        raise ValueError(f"level must be one of ('major', 'minor', 'patch'); got {level!r}")
    bumped = f"{major}.{minor}.{patch}"
    if prerelease is not None:
        bumped += f"-{prerelease}"
    return bumped
```

Add `_SEMVER_RE` to a module-level constant. Tests must cover:
- `1.2.3 + minor → 1.3.0` (regression — pre-Phase-3 semantics)
- `1.2.3-SNAPSHOT + minor → 1.3.0-SNAPSHOT` (Kotlin BLOCKER #1 fix)
- `1.2.3-RC1 + major → 2.0.0-RC1` (Kotlin BLOCKER #1 fix)
- `1.2.3+build.5 + patch → 1.2.4+build.5` (build metadata preserved)
- `0.1.0 + major → 1.0.0` (regression)
- `level="epic"` raises ValueError (covered by `LifecycleOptions.__post_init__`; this defensive check is unreachable but kept for safety)

- [ ] **Step 1: Write the failing tests**

```python
# tests/adapters/kotlin/test_lifecycle.py
from __future__ import annotations

from pathlib import Path
from unittest import mock

import pytest

from crackerjack.adapters.base import LifecycleOptions
from crackerjack.adapters.kotlin.lifecycle import KotlinLifecycle, _bump
from crackerjack.adapters.kotlin.version_source import GradlePropertiesVersionSource


def test_bump_major_real_semver() -> None:
    assert _bump("1.2.3", "major") == "2.0.0"


def test_bump_minor_real_semver() -> None:
    assert _bump("1.2.3", "minor") == "1.3.0"


def test_bump_patch() -> None:
    assert _bump("1.2.3", "patch") == "1.2.4"


def test_bump_major_from_zero() -> None:
    assert _bump("0.1.0", "major") == "1.0.0"


def test_bump_rejects_invalid_level() -> None:
    with pytest.raises(ValueError, match="level must be"):
        _bump("1.2.3", "epic")


def _make_lifecycle(tmp_path: Path) -> tuple[GradlePropertiesVersionSource, KotlinLifecycle]:
    (tmp_path / "gradle.properties").write_text("version=1.2.3\n")
    src = GradlePropertiesVersionSource(tmp_path)
    commit = mock.Mock(return_value="abc123def456" + "0" * 32)
    tag = mock.Mock()
    push = mock.Mock()
    delete_tag = mock.Mock()
    reset = mock.Mock()
    gh_release = mock.Mock(return_value="https://example.com/v1.3.0")
    lifecycle = KotlinLifecycle(
        version_source=src,
        project_root=tmp_path,
        commit=commit,
        tag=tag,
        push=push,
        delete_tag=delete_tag,
        reset=reset,
        gh_release=gh_release,
    )
    return src, lifecycle


def test_kotlin_lifecycle_run_dry_run_does_not_mutate(tmp_path: Path) -> None:
    """Per spec Error Handling: dry_run=True skips ALL mutations.

    Per CRITICAL-1 (Security F-3 + API CRITICAL #1): the gradle.properties
    file MUST NOT be rewritten when dry_run=True. This test asserts both
    the LifecycleResult shape AND the file's unchanged content.
    """
    src, lifecycle = _make_lifecycle(tmp_path)
    original = (tmp_path / "gradle.properties").read_text()
    result = lifecycle.run(LifecycleOptions(level="minor", dry_run=True))
    assert result.new_version == "1.3.0"
    assert result.commit_sha is None
    assert result.tag_name is None
    assert "dry_run" in result.skipped_steps
    # gradle.properties untouched (API CRITICAL #1)
    assert (tmp_path / "gradle.properties").read_text() == original
    lifecycle._commit.assert_not_called()
    lifecycle._tag.assert_not_called()
    lifecycle._push.assert_not_called()


def test_kotlin_lifecycle_run_minor_bumps_gradle_properties_tags_pushes(tmp_path: Path) -> None:
    src, lifecycle = _make_lifecycle(tmp_path)
    result = lifecycle.run(LifecycleOptions(level="minor"))
    assert result.new_version == "1.3.0"
    # gradle.properties was rewritten
    assert src.read() == "1.3.0"
    lifecycle._tag.assert_called_once_with("v1.3.0", mock.ANY)


def test_kotlin_lifecycle_rollback_on_push_failure(tmp_path: Path) -> None:
    """Per API CRITICAL #2: rollback must restore both git state AND gradle.properties."""
    src, lifecycle = _make_lifecycle(tmp_path)
    lifecycle._push.side_effect = RuntimeError("network down")
    with pytest.raises(RuntimeError, match="network down"):
        lifecycle.run(LifecycleOptions(level="minor"))
    # gradle.properties rolled back to original
    assert src.read() == "1.2.3"
    lifecycle._delete_tag.assert_called_once_with("v1.3.0")
    lifecycle._reset.assert_called_once()


def test_kotlin_lifecycle_rollback_on_commit_failure_restores_gradle_properties(tmp_path: Path) -> None:
    """Per API CRITICAL #2: if _commit fails AFTER write succeeded,
    rollback must restore gradle.properties (the uncommitted file change
    that _reset cannot undo, since _reset targets a prior commit)."""
    src, lifecycle = _make_lifecycle(tmp_path)
    lifecycle._commit.side_effect = RuntimeError("commit failed")
    with pytest.raises(RuntimeError, match="commit failed"):
        lifecycle.run(LifecycleOptions(level="minor"))
    # gradle.properties rolled back
    assert src.read() == "1.2.3"
    # No tag was created (commit failed before tag step)
    lifecycle._tag.assert_not_called()
    lifecycle._push.assert_not_called()


def test_bump_preserves_snapshot_qualifier() -> None:
    """Kotlin BLOCKER #1: real Kotlin projects use -SNAPSHOT, -RC1, etc."""
    assert _bump("1.2.3-SNAPSHOT", "minor") == "1.3.0-SNAPSHOT"


def test_bump_preserves_rc_qualifier() -> None:
    assert _bump("2.0.0-RC1", "major") == "3.0.0-RC1"


def test_bump_preserves_build_metadata() -> None:
    assert _bump("1.2.3+build.5", "patch") == "1.2.4+build.5"


def test_bump_rejects_invalid_semver() -> None:
    """Kotlin BLOCKER #1 follow-up: must raise on malformed input."""
    with pytest.raises(ValueError, match="not valid semver"):
        _bump("not-a-version", "minor")


def test_lifecycle_options_rejects_invalid_level() -> None:
    """Per Phase 2 final-review M-3 fix: LifecycleOptions.__post_init__ raises
    during construction. KotlinLifecycle.run does NOT re-validate (Phase 2
    ruling carried forward). This test asserts the construction-time validation.
    """
    with pytest.raises(ValueError, match="level must be"):
        LifecycleOptions(level="epic")


def test_kotlin_lifecycle_writes_gradle_properties_only_not_build_script(tmp_path: Path) -> None:
    (tmp_path / "build.gradle.kts").write_text('version = "1.2.3"\n')
    (tmp_path / "gradle.properties").write_text("version=1.2.3\n")
    src = GradlePropertiesVersionSource(tmp_path)
    lifecycle = KotlinLifecycle(
        version_source=src,
        project_root=tmp_path,
        commit=mock.Mock(return_value="a" * 40),
        tag=mock.Mock(),
        push=mock.Mock(),
        delete_tag=mock.Mock(),
        reset=mock.Mock(),
        gh_release=mock.Mock(return_value=""),
    )
    lifecycle.run(LifecycleOptions(level="minor"))
    # build.gradle.kts untouched
    assert (tmp_path / "build.gradle.kts").read_text() == 'version = "1.2.3"\n'
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/adapters/kotlin/test_lifecycle.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'crackerjack.adapters.kotlin.lifecycle'`.

- [ ] **Step 3: Implement KotlinLifecycle**

Create `crackerjack/adapters/kotlin/lifecycle.py`. Mirror Phase 2's `crackerjack/adapters/swift/lifecycle.py` with these changes:

1. Class name: `SwiftLifecycle` → `KotlinLifecycle`.
2. Module docstring at top.
3. `_bump` body: real-semver with pre-release qualifier preservation (per sub-task 5.1).
4. **CRITICAL — dry_run ordering fix (Security F-3, API CRITICAL #1)**: `dry_run=True` MUST skip ALL mutations per spec Error Handling table. Order the lifecycle flow as:
   - Compute `new_version` via `_bump(current, level)`.
   - If `options.dry_run`: return `LifecycleResult(new_version=new_version, commit_sha=None, tag_name=None, release_url=None, skipped_steps=("dry_run",))` immediately. **DO NOT call `self._version_source.write(new_version)` in the dry_run branch.**
   - Otherwise: `write(new_version)` → `_commit(...)` → `_tag(...)` → `_push(...)` → optional `_gh_release(...)`.
5. **CRITICAL — rollback contract for gradle.properties (API CRITICAL #2)**: Swift's lifecycle has no in-file write step, so its rollback contract is symmetric. Kotlin's `write()` happens BEFORE `_commit()` so the working tree has an uncommitted gradle.properties change after `write()` succeeds but before `_commit()` runs. If `_commit()` then fails, `_reset(commit_sha)` (which targets a prior commit) cannot undo the uncommitted file change. Fix: extend the rollback contract to also restore the original gradle.properties content:
   - Snapshot `original_content = self._version_source._project_root / "gradle.properties".read_text()` BEFORE calling `write()`.
   - In any rollback branch (`except` block), also restore `original_content` to the file.
   - Use the same `_gradle_helpers` module pattern as Swift's `_git_helpers` for the snapshot/restore logic.
6. **Tag/gh_release signature corrections (API HIGH #3, Phase 2 review CRITICAL #2 carry-over)**: The Phase 2 review flagged that `tag: Callable[[str, str], None]` should be `Callable[[str, str], str]` (returns the tag name; needed for gh_release to operate on it) and `gh_release: Callable[[str], str]` should accept an optional `release_name` parameter. Use the corrected signatures from the Phase 2 fix in commit `b2199190` (verify against `crackerjack/adapters/swift/lifecycle.py:60-65` post-`b2199190`).
7. Constructor signature:
```python
def __init__(
    self,
    version_source: GradlePropertiesVersionSource,
    project_root: Path,
    *,
    commit: Callable[[str], str],
    tag: Callable[[str, str], str],
    push: Callable[[str, str], None],
    delete_tag: Callable[[str], None],
    reset: Callable[[str], None],
    gh_release: Callable[[str, str | None], str | None],
) -> None:
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/adapters/kotlin/test_lifecycle.py -v`
Expected: 10 passed.

- [ ] **Step 5: Commit**

```bash
git add crackerjack/adapters/kotlin/lifecycle.py tests/adapters/kotlin/test_lifecycle.py
git commit -m "feat(adapters.kotlin): KotlinLifecycle with real-semver bump and gradle.properties write"
```

---

## Task 6: `__init__.py` — KotlinAdapter wires it all together

**Files:**
- Modify: `crackerjack/adapters/kotlin/__init__.py` (replaces the empty Task 2 marker)
- Create: `tests/adapters/kotlin/test_kotlin_adapter.py`

**Interfaces:**
- Consumes: Phase 1 `LanguageAdapterBase` ABC, `Capabilities` frozen dataclass. Tasks 2-5 outputs.
- Produces: `KotlinAdapter` class with `name = "kotlin"` ClassVar, `detect()`, `capabilities()` methods.

- [ ] **Step 1: Write the failing tests**

```python
# tests/adapters/kotlin/test_kotlin_adapter.py
from __future__ import annotations

from pathlib import Path

from crackerjack.adapters.base import LanguageAdapterBase
from crackerjack.adapters.kotlin import KotlinAdapter


def test_kotlin_adapter_extends_language_adapter_base() -> None:
    assert issubclass(KotlinAdapter, LanguageAdapterBase)


def test_kotlin_adapter_name_is_kotlin() -> None:
    assert KotlinAdapter.name == "kotlin"


def test_detect_returns_true_for_build_gradle_kts(tmp_path: Path) -> None:
    (tmp_path / "build.gradle.kts").write_text("")
    assert KotlinAdapter().detect(tmp_path) is True


def test_detect_returns_true_for_build_gradle(tmp_path: Path) -> None:
    (tmp_path / "build.gradle").write_text("")
    assert KotlinAdapter().detect(tmp_path) is True


def test_detect_returns_false_when_neither_present(tmp_path: Path) -> None:
    assert KotlinAdapter().detect(tmp_path) is False


def test_capabilities_returns_three_hooks_and_has_lifecycle(tmp_path: Path) -> None:
    (tmp_path / "build.gradle.kts").write_text("")
    caps = KotlinAdapter().capabilities(tmp_path)
    assert caps.has_lifecycle is True
    assert caps.has_version is True
    names = {h.name for h in caps.hooks}
    assert names == {"kotlin.ktlint", "kotlin.detekt", "kotlin.test"}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/adapters/kotlin/test_kotlin_adapter.py -v`
Expected: FAIL with `ImportError: cannot import name 'KotlinAdapter'`.

- [ ] **Step 3: Implement KotlinAdapter**

Replace `crackerjack/adapters/kotlin/__init__.py`:

```python
"""Kotlin/Gradle language adapter for crackerjack.

Activates only when `build.gradle.kts` or `build.gradle` is present at
the project root. Provides Kotlin lifecycle (gradle.properties bump + git
tag/push), three Kotlin hooks with Gradle task probing (ktlint, detekt,
test), and version management via GradlePropertiesVersionSource.
"""

from __future__ import annotations

from pathlib import Path

from crackerjack.adapters.base import Capabilities, LanguageAdapterBase
from crackerjack.adapters.kotlin.hooks import kotlin_hooks
from crackerjack.adapters.kotlin.version_source import GradlePropertiesVersionSource

__all__ = ["KotlinAdapter"]


class KotlinAdapter(LanguageAdapterBase):
    """Kotlin/Gradle language adapter — activates on build.gradle(.kts) presence."""

    name: str = "kotlin"

    def detect(self, project_root: Path) -> bool:
        return (project_root / "build.gradle.kts").is_file() or (project_root / "build.gradle").is_file()

    def capabilities(self, project_root: Path) -> Capabilities:
        # Per Phase 2 final-review CF-2 fix: do not construct KotlinLifecycle here.
        # The lifecycle is rebuilt inside the MCP handler (Task 7).
        return Capabilities(
            version_source=GradlePropertiesVersionSource(project_root),
            hooks=kotlin_hooks(project_root),
            has_lifecycle=True,
        )
```

Note: dropped the dead `gradle_properties_version_source` factory and the dead `make_git_backend` import (per Simplification F2/F3).

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/adapters/kotlin/test_kotlin_adapter.py -v`
Expected: 6 passed.

- [ ] **Step 5: Verify `discover_adapters()` returns all three**

Run: `uv run python -c "from crackerjack.adapters.registry import discover_adapters; print(sorted(discover_adapters().keys()))"`
Expected: `['kotlin', 'python', 'swift']`.

- [ ] **Step 6: Commit**

```bash
git add crackerjack/adapters/kotlin/__init__.py tests/adapters/kotlin/test_kotlin_adapter.py
git commit -m "feat(adapters.kotlin): KotlinAdapter wires VersionSource + hooks"
```

---

## Task 7: MCP tools — add kotlin_bump_version + kotlin_list_hooks

**Files:**
- Modify: `crackerjack/mcp/tools/language_tools.py` (add 2 tools; preserve existing swift_* tools)
- Test: `tests/mcp/tools/test_language_tools.py` (add 2 new tests; preserve existing tests)

**Interfaces:**
- Consumes: Existing `language_tools.py` module structure (auth helper, project_root validator, `_run_swift_lifecycle_sync` factory). Phase 2's `_validate_project_root`, `_require_auth_config`, and registry adapter detection patterns.
- Produces: Two new `@mcp_app.tool()` async functions:
  - `kotlin_bump_version(level: Literal["major", "minor", "patch"], project_root: str, dry_run: bool = False, release: bool = False) -> dict` (mutation; auth required per spec MCP F5)
  - `kotlin_list_hooks(project_root: str) -> dict` (read-only; returns 3 hook names + gradle task probe results)

**No `profiles.py` changes** — the `language_tools` group is already registered in `FULL_REGISTRATIONS` (Phase 2 commit `fb6274e7`). Phase 3 just adds tools to the existing group.

- [ ] **Step 1: Write the failing tests**

Append to `tests/mcp/tools/test_language_tools.py`:

```python
async def test_kotlin_list_hooks_returns_three_hook_names(tmp_path: Path) -> None:
    """Happy path: kotlin_list_hooks returns metadata for a valid Gradle project."""
    from crackerjack.adapters.kotlin import KotlinAdapter
    (tmp_path / "build.gradle.kts").write_text("")
    monkeypatch = pytest.MonkeyPatch()
    try:
        monkeypatch.setenv("MAHAVISHNU_PROJECT_ROOTS", str(tmp_path))
        _, tools = asyncio.run(_register())
        tool = tools["kotlin_list_hooks"]
        # Stub the probe so we don't require gradlew on PATH
        with mock.patch.object(GradleTaskProbe, "has_task", return_value=True):
            result = asyncio.run(tool.fn(project_root=str(tmp_path)))
    finally:
        monkeypatch.undo()
    assert isinstance(result, dict)
    names = set(result.keys())
    assert "kotlin.ktlint" in names
    assert "kotlin.detekt" in names
    assert "kotlin.test" in names
    assert result["kotlin.test"]["cli_command"][:2] == ["./gradlew", "test"]


async def test_kotlin_list_hooks_rejects_non_kotlin_directory(tmp_path: Path) -> None:
    """Per Security F-5: must raise if adapter.detect() is False (Phase 2 CF-4 analog)."""
    monkeypatch = pytest.MonkeyPatch()
    try:
        monkeypatch.setenv("MAHAVISHNU_PROJECT_ROOTS", str(tmp_path))
        _, tools = asyncio.run(_register())
        tool = tools["kotlin_list_hooks"]
        with pytest.raises(ValueError, match="No build.gradle"):
            asyncio.run(tool.fn(project_root=str(tmp_path)))
    finally:
        monkeypatch.undo()


async def test_kotlin_bump_version_requires_auth(tmp_path: Path) -> None:
    """Mutation tools require MAHAVISHNU_AUTH_ENABLED + MAHAVISHNU_JWT_SECRET."""
    monkeypatch = pytest.MonkeyPatch()
    try:
        monkeypatch.delenv("MAHAVISHNU_AUTH_ENABLED", raising=False)
        monkeypatch.delenv("MAHAVISHNU_JWT_SECRET", raising=False)
        _, tools = asyncio.run(_register())
        tool = tools["kotlin_bump_version"]
        with pytest.raises(PermissionError):
            asyncio.run(tool.fn(level="minor", project_root=str(tmp_path)))
    finally:
        monkeypatch.undo()


async def test_kotlin_bump_version_runs_with_auth(tmp_path: Path) -> None:
    """Per MCP HIGH-3 / Testing HIGH-1 (Phase 2 CRITICAL-1 analog): happy-path
    test that exercises the real KotlinLifecycle + make_git_backend path.

    Without this test, future regressions (e.g. dry_run mutating gradle.properties,
    rollback contract breakage) would ship silently — exactly the Phase 2
    fake-green pattern that was caught at Task 7 review.
    """
    (tmp_path / "build.gradle.kts").write_text("")
    (tmp_path / "gradle.properties").write_text("version=1.2.3\n")
    # Init a real git repo so commits work (we mock _commit but the
    # pre-flight git status check still runs)
    import subprocess as sp
    sp.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    sp.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, check=True)
    sp.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True)
    (tmp_path / "README.md").write_text("# test")
    sp.run(["git", "add", "README.md"], cwd=tmp_path, check=True)
    sp.run(["git", "commit", "-q", "-m", "init"], cwd=tmp_path, check=True)

    monkeypatch = pytest.MonkeyPatch()
    try:
        monkeypatch.setenv("MAHAVISHNU_AUTH_ENABLED", "true")
        monkeypatch.setenv("MAHAVISHNU_JWT_SECRET", "test-secret")
        monkeypatch.setenv("MAHAVISHNU_PROJECT_ROOTS", str(tmp_path))
        _, tools = asyncio.run(_register())
        tool = tools["kotlin_bump_version"]
        result = asyncio.run(tool.fn(level="minor", project_root=str(tmp_path)))
    finally:
        monkeypatch.undo()
    assert result["new_version"] == "1.3.0"
    # gradle.properties was rewritten
    assert (tmp_path / "gradle.properties").read_text() == "version=1.3.0\n"


async def test_kotlin_bump_version_rejects_non_kotlin_directory(tmp_path: Path) -> None:
    """Per Security F-5: must raise if adapter.detect() is False."""
    monkeypatch = pytest.MonkeyPatch()
    try:
        monkeypatch.setenv("MAHAVISHNU_AUTH_ENABLED", "true")
        monkeypatch.setenv("MAHAVISHNU_JWT_SECRET", "test-secret")
        monkeypatch.setenv("MAHAVISHNU_PROJECT_ROOTS", str(tmp_path))
        _, tools = asyncio.run(_register())
        tool = tools["kotlin_bump_version"]
        with pytest.raises(ValueError, match="No build.gradle"):
            asyncio.run(tool.fn(level="minor", project_root=str(tmp_path)))
    finally:
        monkeypatch.undo()


async def test_kotlin_bump_version_rejects_invalid_level(tmp_path: Path) -> None:
    """Per MCP HIGH-2: level must be one of major/minor/patch (Literal type)."""
    (tmp_path / "build.gradle.kts").write_text("")
    monkeypatch = pytest.MonkeyPatch()
    try:
        monkeypatch.setenv("MAHAVISHNU_AUTH_ENABLED", "true")
        monkeypatch.setenv("MAHAVISHNU_JWT_SECRET", "test-secret")
        monkeypatch.setenv("MAHAVISHNU_PROJECT_ROOTS", str(tmp_path))
        _, tools = asyncio.run(_register())
        tool = tools["kotlin_bump_version"]
        with pytest.raises(ValueError, match="level must be"):
            asyncio.run(tool.fn(level="epic", project_root=str(tmp_path)))
    finally:
        monkeypatch.undo()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/mcp/tools/test_language_tools.py -v`
Expected: FAIL with `KeyError: 'kotlin_list_hooks'` (tool not registered yet) and `KeyError: 'kotlin_bump_version'`.

- [ ] **Step 3: Fix `_validate_project_root` and `_require_auth_config` (Phase 2 carry-over)**

**HIGH**: These are Phase 2 final-review IMPORTANT-1 + A11y F3 carry-overs. Apply the fixes in `language_tools.py` BEFORE adding the new tools (so the new tools inherit the fixed helpers):

1. **`_validate_project_root` fail-closed fix**: Change the env-unset branch from silent return to `raise PermissionError("MAHAVISHNU_PROJECT_ROOTS unset. Configure with colon-separated absolute paths to allow.")`. Update the existing Phase 2 read-only tests (`test_swift_list_hooks_does_not_require_auth` and `test_detect_languages_returns_adapter_names`) to set the env var.
2. **`_require_auth_config` error message improvement**: Replace the tautological "MAHAVISHNU_AUTH_ENABLED=true required" with: `f"Mutation tools require MAHAVISHNU_AUTH_ENABLED=true; current value: {current!r}"` and `f"Mutation tools require MAHAVISHNU_JWT_SECRET; current length: {len(secret)} chars"`. Helps users diagnose configuration issues.

- [ ] **Step 4: Add a `_run_kotlin_lifecycle_sync` helper (MCP MEDIUM 2)**

Per the Phase 2 pattern (`_run_swift_lifecycle_sync` at `language_tools.py:101-128`), factor the lifecycle construction into a helper. Keeps the tool function readable and matches the Phase 2 precedent:

```python
def _run_kotlin_lifecycle_sync(
    root: Path,
    level: Literal["major", "minor", "patch"],
    dry_run: bool,
    release: bool,
) -> LifecycleResult:
    from crackerjack.adapters.base import LifecycleOptions
    from crackerjack.adapters.kotlin.git_backend import make_git_backend
    from crackerjack.adapters.kotlin.lifecycle import KotlinLifecycle
    from crackerjack.adapters.kotlin.version_source import GradlePropertiesVersionSource

    version_source = GradlePropertiesVersionSource(root)
    commit, tag, push, delete_tag, reset, gh_release = make_git_backend(root)
    lifecycle = KotlinLifecycle(
        version_source=version_source,
        project_root=root,
        commit=commit, tag=tag, push=push,
        delete_tag=delete_tag, reset=reset, gh_release=gh_release,
    )
    return lifecycle.run(LifecycleOptions(level=level, dry_run=dry_run, release=release))
```

- [ ] **Step 5: Add the 2 tools to language_tools.py**

Append two new tool definitions to `crackerjack/mcp/tools/language_tools.py`. **Detailed docstrings per A11y F1.**

```python
@mcp_app.tool()
async def kotlin_bump_version(
    level: Literal["major", "minor", "patch"],
    project_root: str,
    dry_run: bool = False,
    release: bool = False,
) -> dict:
    """Bump a Kotlin/Gradle project's version. Writes the new version to
    `gradle.properties` (NOT `build.gradle.kts`), then commits, tags,
    pushes, and optionally creates a GitHub release. Rolls back all
    mutations on failure.

    Args:
        level: Semver component to bump — `major`, `minor`, or `patch`.
            Pre-release qualifiers (e.g. `-SNAPSHOT`, `-RC1`) and build
            metadata (e.g. `+build.5`) are preserved unchanged.
        project_root: Absolute path to the project root. Must contain
            `build.gradle.kts` (or `build.gradle`) and `gradle.properties`.
            Must be in `MAHAVISHNU_PROJECT_ROOTS` allowlist.
        dry_run: If True, compute the new version but make NO mutations
            (no gradle.properties write, no commit, no tag, no push).
        release: If True, create a GitHub release via `gh release create`
            after pushing the tag.

    Returns:
        dict with keys `new_version`, `commit_sha`, `tag_name`,
        `release_url`, `skipped_steps` (tuple of steps that were skipped,
            e.g. `("dry_run",)` when `dry_run=True`).

    Raises:
        PermissionError: if `MAHAVISHNU_AUTH_ENABLED` is not `true`,
            `MAHAVISHNU_JWT_SECRET` is unset, or `project_root` is not
            in `MAHAVISHNU_PROJECT_ROOTS` allowlist.
        ValueError: if `build.gradle.kts` is missing or `level` is not
            one of the literal values.
        FileNotFoundError: if `gradle.properties` is missing.
        RuntimeError: on git/gh subprocess failure (after rollback).
    """
    _require_auth_config()
    root = _validate_project_root(project_root)
    from crackerjack.adapters.kotlin import KotlinAdapter

    adapter = KotlinAdapter()
    if not adapter.detect(root):
        raise ValueError(f"No build.gradle(.kts) at {root}. Run `gradle init --type kotlin-library` to scaffold.")
    result = await asyncio.to_thread(
        _run_kotlin_lifecycle_sync, root, level, dry_run, release,
    )
    return {
        "new_version": result.new_version,
        "commit_sha": result.commit_sha,
        "tag_name": result.tag_name,
        "release_url": result.release_url,
        "skipped_steps": list(result.skipped_steps),
    }


@mcp_app.tool()
async def kotlin_list_hooks(project_root: str) -> dict:
    """Return Kotlin/Gradle hook metadata for the given project.

    Probes `./gradlew tasks --all` to detect which plugins are available.
    Hooks whose tasks are absent (e.g. `ktlintCheck` if no ktlint plugin)
    are filtered out with a logged warning. `kotlin.test` is always
    emitted (every Kotlin project has the `test` task).

    Args:
        project_root: Absolute path to the project root. Must contain
            `build.gradle.kts` (or `build.gradle`). Must be in
            `MAHAVISHNU_PROJECT_ROOTS` allowlist (read-only access).

    Returns:
        dict mapping hook name to metadata: `cli_command` (argv list,
            e.g. `["./gradlew", "ktlintCheck"]`), `autofix`, and
        `timeout_seconds`.

    Raises:
        PermissionError: if `project_root` is not in
            `MAHAVISHNU_PROJECT_ROOTS` allowlist.
        ValueError: if `build.gradle.kts` is missing.
    """
    root = _validate_project_root(project_root)
    from crackerjack.adapters.kotlin import KotlinAdapter

    adapter = KotlinAdapter()
    if not adapter.detect(root):
        raise ValueError(f"No build.gradle(.kts) at {root}. Run `gradle init --type kotlin-library` to scaffold.")
    caps = adapter.capabilities(root)
    return {
        h.name: {
            "cli_command": list(h.cli_command),
            "autofix": h.autofix,
            "timeout_seconds": h.timeout_seconds,
        }
        for h in caps.hooks
    }
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/mcp/tools/test_language_tools.py -v`
Expected: All tests pass (existing 7 swift + 6 new kotlin = 13 minimum).

- [ ] **Step 7: Verify discoverability via MCP server smoke**

Run: Start the MCP server briefly (per Phase 2 Task 8 step 8.7 pattern) and confirm `kotlin_bump_version` and `kotlin_list_hooks` appear in the tool list alongside `swift_bump_version`, `swift_list_hooks`, `detect_languages`.

- [ ] **Step 8: Commit**

```bash
git add crackerjack/mcp/tools/language_tools.py tests/mcp/tools/test_language_tools.py
git commit -m "feat(mcp): kotlin_bump_version + kotlin_list_hooks + Phase 2 carry-over auth fixes"
```

---

## Task 8: Verification — full test suite + CHANGELOG + smoke + Gradle fixture

**Files:**
- Create: `tests/fixtures/gradle-vanilla/settings.gradle.kts`
- Create: `tests/fixtures/gradle-vanilla/build.gradle.kts`
- Create: `tests/fixtures/gradle-vanilla/src/main/kotlin/Hello.kt`
- Modify: `CHANGELOG.md` (add Phase 3 entry under `[Unreleased]`)

**Sub-task 8.1: Real Gradle fixture**

Create a vanilla Kotlin lib fixture at `tests/fixtures/gradle-vanilla/`. **Must include `gradle.properties`** so `GradlePropertiesVersionSource.read()` works end-to-end (per Kotlin HIGH #4). **Must include the ktlint plugin declaration** so real-CLI smoke tests can exercise task probing (per Testing HIGH-4).

`settings.gradle.kts`:
```kotlin
rootProject.name = "gradle-vanilla"
```

`gradle.properties`:
```properties
version=0.1.0
```

`build.gradle.kts`:
```kotlin
plugins {
    kotlin("jvm") version "1.9.0"
    id("org.jlleitschuh.gradle.ktlint") version "11.6.0"
}

repositories {
    mavenCentral()
}

dependencies {
    implementation(kotlin("stdlib"))
}

version = "0.1.0"
```

`src/main/kotlin/Hello.kt`:
```kotlin
package gradle.vanilla

class Hello {
    fun greet(): String = "hello"
}
```

**Sub-task 8.2: CHANGELOG entry**

Add to `CHANGELOG.md` under `[Unreleased]`:
```markdown
- Kotlin/Gradle language adapter (Phase 3): GradlePropertiesVersionSource reads version from
  gradle.properties (keys: pluginVersion, projectVersion, version) with fallback to
  build.gradle.kts scan and `./gradlew properties` as source of truth. Lifecycle bumps via
  gradle.properties write (NOT build.gradle.kts); real-semver `_bump` semantics preserving
  pre-release qualifiers (`-SNAPSHOT`, `-RC1`) and build metadata. Three hooks with
  Gradle task probing: kotlin.ktlint (`./gradlew ktlintCheck`), kotlin.detekt
  (`./gradlew detekt`), kotlin.test (`./gradlew test`); absent tasks filtered with
  logged warning. All Gradle invocations pass `--no-daemon --no-configuration-cache` for
  CI reliability. Two new MCP tools: kotlin_bump_version (mutation; requires auth per
  spec MCP F5 + path validation; per-invocation check), kotlin_list_hooks (read-only;
  returns hook metadata after task probing). `crackerjack.language_adapters` entry-point
  group now registers Python, Swift, and Kotlin adapters. New fixture at
  `tests/fixtures/gradle-vanilla/` exercises the full lifecycle end-to-end.
```

- [ ] **Step 1: Create the Gradle fixture**

Create the three files above at `tests/fixtures/gradle-vanilla/`.

- [ ] **Step 2: Update CHANGELOG.md**

Add the entry above to `CHANGELOG.md`.

- [ ] **Step 3: Run Phase 3 tests**

Run: `uv run pytest tests/adapters/kotlin/ tests/mcp/tools/test_language_tools.py tests/adapters/test_registry.py -v`
Expected: All pass.

- [ ] **Step 4: Smoke test against real Gradle CLI (gated on `gradlew` availability)**

Run: `uv run python -c "from crackerjack.adapters.kotlin import KotlinAdapter; a = KotlinAdapter(); from pathlib import Path; print(a.detect(Path('tests/fixtures/gradle-vanilla'))); print(a.capabilities(Path('tests/fixtures/gradle-vanilla')))"`
Expected: `True` and 3 hooks listed.

- [ ] **Step 5: Verify `discover_adapters()` returns all three**

Run: `uv run python -c "from crackerjack.adapters.registry import discover_adapters; print(sorted(discover_adapters().keys()))"`
Expected: `['kotlin', 'python', 'swift']`.

- [ ] **Step 6: MCP server smoke (verify tools discoverable)**

Run: Start the MCP server (Phase 2 Task 8.7 pattern), confirm `kotlin_bump_version` and `kotlin_list_hooks` appear in the tool list alongside `swift_bump_version`, `swift_list_hooks`, `detect_languages`.

- [ ] **Step 7: Commit**

```bash
git add tests/fixtures/gradle-vanilla/ CHANGELOG.md
git commit -m "docs(changelog): Phase 3 — Kotlin/Gradle adapter + real Gradle fixture"
```

---

## Spec Revision Notes

The 8-lens multi-agent review surfaced the following spec amendments the
spec team should make in the next revision pass:

### §1. MCP tool naming — `kotlin_run_hooks` → `kotlin_list_hooks`

The spec text at lines 44 and 531 says `kotlin_run_hooks`. Phase 2's
Swift lens review HIGH H11 renamed the Swift tool to `swift_list_hooks`
because the tool returns metadata, doesn't execute. Phase 3 mirrors that
rename for Kotlin. The spec should be amended to match: `kotlin_list_hooks`.

### §2. `_validate_project_root` fail-closed default

Per Phase 2 final-review IMPORTANT-1 (carried into Phase 3 as Security F-2
and MCP HIGH-1), the `MAHAVISHNU_PROJECT_ROOTS` env var unset behavior
should `raise PermissionError`, not silently bypass the allowlist. The
spec text should be amended to reflect fail-closed default.

### §3. Cross-adapter `_bump` divergence

Three adapters now have their own `_bump` with divergent semantics
(Python real semver, Swift pre-1.0, Kotlin real semver). Per Phase 2
final-review CF-3, the spec should either (a) extract `_bump` to
`crackerjack/adapters/_semver.py` with explicit per-language dispatch
and docstrings, or (b) narrow `LifecycleOptions.level` to a strict
semver bump and let each adapter interpret `"major"` correctly for its
ecosystem. Phase 3 picks (b) implicitly.

### §4. Pre-release qualifier handling in VersionSource

Per Phase 3 Kotlin BLOCKER #1, real Kotlin/JVM projects use pre-release
qualifiers (`-SNAPSHOT`, `-RC1`, `-M1`) and build metadata
(`+build.5`). The spec should mandate that bump operations preserve these
qualifiers unchanged.

### §5. `_require_auth_config` upgrade path

The current spec mandates env-var-only checks. The spec should be amended
to clarify that this is the Phase 2/3 placeholder pending the Bodai-wide
JWT auth standardization (per memory `project_bodai_auth_standardization.md`).

### §6. Tier 2 build.gradle.kts regex limitations

The spec's Tier 2 regex (`^\s*version\s*=\s*"([^"]+)"`) only matches
literal strings, not `libs.versions.X.get()` (modern Kotlin projects
default to version catalogs). Phase 3 documents this as a Tier 2
limitation; spec should be amended to either (a) explicitly call out
libs.versions.toml support as a Phase 4+ item, or (b) mandate version
catalog parsing.

### §7. Gradle task probing is mandatory, not advisory

The spec Kotlin F2 says "skip-with-warning if absent". Phase 3's plan
implements this as a hard filter (absent tasks are filtered from the
emitted hook list). Spec should be amended to clarify the wire-level
contract.

### §8. KMP / multi-module Gradle projects

Phase 3 only handles single-module Gradle projects. Spec should be
amended to call out KMP/multi-module as Phase 4+ scope.

---

## Cross-adapter `_bump` divergence (Phase 2.5 follow-up, deferred)

Per Phase 2 final review CF-3, the `_bump` function exists in three places with divergent semantics:
- `PythonLifecycle._bump` — real semver (`major` bumps `major`).
- `SwiftLifecycle._bump` — pre-1.0 semantics (`major` bumps `minor`).
- `KotlinLifecycle._bump` (Phase 3) — real semver (matches Python), preserves pre-release qualifiers.

Phase 3 documents the divergence in `KotlinLifecycle._bump`'s docstring AND adds a cross-reference comment to `SwiftLifecycle._bump` (already documented as pre-1.0). The Phase 2.5 follow-up ticket should consider:
- (a) Extract `_bump` to `crackerjack/adapters/_semver.py` with explicit per-language dispatch and docstrings.
- (b) Narrow `LifecycleOptions.level` to be a strict semver bump and let each adapter interpret `"major"` correctly for its ecosystem.

Phase 3 picks (b) implicitly (Kotlin uses real semver, Swift stays pre-1.0). ADR recommended before Phase 4 (JS/TS adapter) lands.

## Self-Review

Per writing-plans skill: 1-question scan to confirm plan completeness.

**1. Spec coverage** — Skim each section/requirement in the spec:

| Spec requirement | Task | Status |
|---|---|---|
| Detect `build.gradle.kts` or `build.gradle` | Task 6 `KotlinAdapter.detect()` | ✓ |
| VersionSource: gradle.properties probe keys (pluginVersion, projectVersion, version) | Task 2 `GradlePropertiesVersionSource._PROBE_KEYS` | ✓ |
| VersionSource: build.gradle.kts fallback scan | Task 2 Tier 2 regex | ✓ |
| VersionSource: `./gradlew properties` source-of-truth fallback | Task 2 `_read_via_gradle()` | ✓ |
| VersionSource.write() with read-back verification | Task 2 `GradlePropertiesVersionSource.write()` | ✓ |
| Hook: kotlin.ktlint → ktlintCheck | Task 3 `_HOOK_TASK_MAP` | ✓ |
| Hook: kotlin.detekt → detekt | Task 3 `_HOOK_TASK_MAP` | ✓ |
| Hook: kotlin.test | Task 3 | ✓ |
| Gradle task probing | Task 3 `GradleTaskProbe.has_task` | ✓ (now wired) |
| Skip-with-warning if task absent | Task 3 `_build_hooks` filter | ✓ |
| All Gradle invocations pass `--no-daemon --no-configuration-cache` | Task 3 `GradleTaskProbe.has_task` argv | ✓ |
| Lifecycle bumps gradle.properties (not build.gradle.kts) | Task 5 `KotlinLifecycle.run` | ✓ |
| Lifecycle rollback on failure | Task 5 try/except | ✓ (extended for gradle.properties) |
| dry_run=True skips ALL mutations | Task 5 ordering | ✓ (Rev 2 fix) |
| 4-step MCP registration pipeline | Task 7 (no profiles.py change needed; group already registered) | ✓ |
| Per-invocation auth check for mutation tools | Task 7 `_require_auth_config` | ✓ (Rev 2: improved messages) |
| project_root allowlist validation | Task 7 `_validate_project_root` | ✓ (Rev 2: fail-closed) |
| Real Gradle fixture | Task 8 `tests/fixtures/gradle-vanilla/` | ✓ (Rev 2: includes gradle.properties + ktlint) |
| Pre-release qualifier preservation | Task 5 `_SEMVER_RE` | ✓ (Rev 2: new) |
| Module docstring on every new file | Global Constraints | ✓ (Rev 2: new rule) |

**Gaps**: None remaining for Phase 3 scope. Items deferred to Phase 3.5+ are tracked in the F-1..F14 finding list and the Spec Revision Notes §3, §6, §7, §8.

**2. Placeholder scan** — Searched for `TBD`, `TODO`, `implement later`, `fill in details`, `Add appropriate error handling`, `Similar to Task N`: none found. All steps contain actual code blocks or concrete instructions.

**3. Type consistency** — Cross-task type names verified:
- `GradlePropertiesVersionSource` consistent across Tasks 2, 5, 6, 7.
- `KotlinLifecycle` consistent across Tasks 5, 6, 7.
- `KotlinAdapter` consistent across Tasks 6, 7.
- `make_git_backend` factory consistent across Tasks 4, 7.
- `_run_kotlin_lifecycle_sync` helper consistent with Phase 2's `_run_swift_lifecycle_sync`.
- `_validate_project_root` and `_require_auth_config` reused from Phase 2 (no re-implementation).

**Why 8 tasks mirroring Phase 2?** Phase 1's foundation + Phase 2's Swift adapter established the 8-task structure: entry-point → version source → hooks → git backend → lifecycle → adapter → MCP tools → verification. Phase 3 mirrors this to keep per-task review gates consistent and to surface any cross-adapter drift early. Refactoring to fewer tasks would force a single reviewer to context-switch across many concerns.

**Why bump gradle.properties instead of build.gradle.kts?** Kotlin convention keeps version metadata in a properties file (separable from build logic, consumable by plugins without parsing Groovy/Kotlin DSL). The lifecycle tests assert that build.gradle.kts is NOT mutated.

**Plan is ready for execution.**
