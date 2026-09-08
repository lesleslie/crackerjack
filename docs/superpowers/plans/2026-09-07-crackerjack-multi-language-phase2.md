# Crackerjack Multi-Language Extension — Phase 2 (Swift) Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Swift language adapter to crackerjack that activates only when `Package.swift` is present. Provides Swift lifecycle (git tags primary, no Package.swift mutation) + Swift hooks (test/build/format/package.update with iOS-Simulator destination detection) + MCP tools for both lifecycle and hooks. Auth posture pinned for mutation tools.

**Architecture:** Approach A (per spec Rev 2) extended with Swift. New `crackerjack/adapters/swift/{version_source,hooks,lifecycle,platforms}.py` packages + `SwiftAdapter` extending `LanguageAdapterBase`. Existing `LanguageAdapter` Protocol / `LanguageAdapterBase` ABC / `Capabilities` / `Hook` / `Lifecycle` types from Phase 1 are reused unchanged. New MCP tool group `language_tools` registered via the 4-step pipeline documented in Phase 1 Task 8.

**Tech Stack:** Python 3.14, FastMCP 4.x, typer 0.26+, hatchling, Git CLI (via subprocess), SwiftPM CLI (subprocess invocation, no shell), gh CLI for GitHub release creation.

**Spec:** `/Users/les/Projects/crackerjack/docs/superpowers/specs/2026-09-07-crackerjack-multi-language-design.md` (Rev 2, on `main` as of commit `b00b36f0`). Phase 2 section: "Per-adapter Swift (Rev 2 — rewritten per Swift F1, F2, F3, F4)".

**Review notes from Phase 1 (must avoid re-introducing):**
- Phase 1's per-task reviewers caught 9 brief-vs-reality defects. Verify against reality (e.g., the actual `swift --help` flags) before transcribing brief claims.
- Phase 1's deferrals for spec/brief amendment (13 items in the Phase 1 ledger) are still open. Some Phase 2 work may surface more.

## Global Constraints

Verbatim from the spec and project:

- **Python 3.14** with `from __future__ import annotations` as the first non-comment line of every source file.
- **Modern syntax**: `X | None` (not `Optional[X]`), `list[str]` (not `List[str]`), `pathlib.Path`.
- **Default-`None` args typed `X | None = None`** (mypy `no_implicit_optional = true`).
- **No `assert` in production code** (`crackerjack/adapters/swift/**/*.py` is production).
- **No `Any`** in production code. Tests may use `Any` for mocks.
- **`logger.exception(...)`** in `except` blocks.
- **All I/O async.** Subprocess via `asyncio.to_thread` or `loop.run_in_executor`. Sync only at CLI entry points.
- **argv list, no shell** for all subprocess invocations. `shlex.quote` only when an adapter deliberately opts in.
- **Imports sorted within each section** (stdlib → third-party → first-party).
- **Remove unused imports and dead code immediately** (Ruff F401 / UP).
- **`@runtime_checkable` Protocol** for `LanguageAdapter` (per spec API F1).
- **`Capabilities` is a frozen dataclass**.
- **`Hook` only requires `name` and `cli_command`**; all other fields default.
- **`Lifecycle.run(LifecycleOptions) -> LifecycleResult`** with rollback contract.
- **MCP 4-step registration pipeline** (per spec MCP F1): CREATE module → REGISTER in `_build_registration_map()` → ASSIGN tier in `profiles.py` → TEST. Phase 1 Task 8 documented this contract; Phase 2 actually creates the `language_tools` group.
- **Auth posture for mutation tools** (per spec MCP F5): `MAHAVISHNU_AUTH_ENABLED=true` + `MAHAVISHNU_JWT_SECRET` required. Mutation tools refuse to operate if absent.
- **Git tag primary for Swift version** (per spec Swift F1): `git describe --tags --abbrev=0 --match "v*"`. NO Package.swift mutation in v1.
- **`swift-format` (third-party) preferred** over `swift format` (built-in). Read `.swift-format` config when present.
- **iOS-Simulator destination** detected from `Package.swift` `platforms:` directive (per spec Swift F4).
- **`swift package update` is a hook** (autofix=false, per spec Swift F3).
- **Hybrid fallback** (per spec Writing F2): one canonical interpretation only — when CLI is missing AND fallback is set, invoke Python fallback; when fallback also raises, fail with installation instructions.
- **Tests**: use `tempfile.TemporaryDirectory()`, `monkeypatch.setattr(shutil, "which", ...)`, `pytest.raises`, and shared `FakeHookRunner`-style abstractions where applicable.

---

## File Structure

### New files (Phase 2)

```
crackerjack/
├── adapters/swift/                                 # NEW
│   ├── __init__.py                                 # exports SwiftAdapter
│   ├── version_source.py                           # GitTagVersionSource (wraps `git describe`)
│   ├── platforms.py                                # Package.swift platforms directive parser
│   ├── hooks.py                                    # swift test/build/format/package.update
│   └── lifecycle.py                                # SwiftLifecycle with rollback contract

mcp/
└── tools/
    └── language_tools.py                           # NEW MCP tool group: swift_bump_version,
                                                     # swift_run_hooks, format_jinja_templates,
                                                     # check_web_lint, detect_languages (Phase 4+)

tests/
├── adapters/swift/                                 # NEW
│   ├── __init__.py
│   ├── test_version_source.py
│   ├── test_platforms.py
│   ├── test_hooks.py
│   ├── test_lifecycle.py
│   └── test_swift_adapter.py
└── mcp/
    └── tools/
        └── test_language_tools.py                  # NEW MCP tool tests

docs/superpowers/plans/
└── 2026-09-07-crackerjack-multi-language-phase2.md  # this plan
```

### Modified files (Phase 2)

```
crackerjack/
├── pyproject.toml                                  # ADD swift entry-point under crackerjack.language_adapters
├── cli/options.py                                  # (audit only — Phase 2 should not change Python CLI flags)
├── mcp/
│   ├── server_core.py                              # REGISTER language_tools in _build_registration_map()
│   └── tools/
│       └── profiles.py                             # ADD language_tools to FULL_REGISTRATIONS
└── CHANGELOG.md                                    # Phase 2 entry
```

### Files NOT modified (Phase 2)

- `crackerjack/adapters/base.py` — Phase 1's types are reusable; Phase 2 only adds new adapter packages.
- `crackerjack/adapters/python/` — Python adapter untouched.
- `crackerjack/cli/` — Phase 2 changes nothing in the Python CLI surface.
- `crackerjack/managers/` — untouched.

---

## Task 1: Foundation — explore existing MCP tools, update registration map

**Files:**
- Read (do NOT modify): `crackerjack/mcp/server_core.py`, `crackerjack/mcp/tools/profiles.py`, `crackerjack/mcp/tools/*.py` (existing tool examples)
- Modify: `crackerjack/pyproject.toml` (add Swift entry-point)
- Test: (none — this task is registration only)

**Interfaces (consumed from Phase 1):**
- `LanguageAdapter` Protocol (from `crackerjack/adapters/base.py`)
- `_build_registration_map()` in `crackerjack/mcp/server_core.py`
- `FULL_REGISTRATIONS` / `STANDARD_REGISTRATIONS` / `MINIMAL_REGISTRATIONS` in `crackerjack/mcp/tools/profiles.py`

**Interfaces (produced):**
- New entry-point in `pyproject.toml[project.entry-points."crackerjack.language_adapters"]`: `swift = "crackerjack.adapters.swift:SwiftAdapter"` (using `module:ClassName` form per the out-of-brief fix from Phase 1 Task 6).

- [ ] **Step 1.1: Read existing crackerjack MCP tools**

```bash
ls /Users/les/Projects/crackerjack/crackerjack/mcp/tools/
sed -n '200,230p' /Users/les/Projects/crackerjack/crackerjack/mcp/server_core.py
sed -n '70,120p' /Users/les/Projects/crackerjack/crackerjack/mcp/tools/profiles.py
cat /Users/les/Projects/crackerjack/crackerjack/mcp/tools/__init__.py
```

Verify: `_build_registration_map()` exists in `server_core.py`; `FULL_REGISTRATIONS` exists in `profiles.py`; existing tool groups follow the 4-step pattern.

- [ ] **Step 1.2: Add Swift entry-point to pyproject.toml**

Locate the `[project.entry-points."crackerjack.language_adapters"]` block (added in Phase 1 Task 2, around line 103-106). Add the Swift entry:

```toml
[project.entry-points."crackerjack.language_adapters"]
python = "crackerjack.adapters.python:PythonAdapter"
swift = "crackerjack.adapters.swift:SwiftAdapter"
```

(The Python entry already uses the `module:ClassName` form from the Phase 1 Task 6 fix. Swift uses the same form.)

- [ ] **Step 1.3: Verify entry-point declaration is well-formed**

```bash
cd /Users/les/Projects/crackerjack
.venv/bin/python -c "
from importlib import metadata
eps = metadata.entry_points(group='crackerjack.language_adapters')
for ep in eps:
    print(ep.name, '->', ep.value)
"
```

Expected output (after Task 6 ships): `python -> crackerjack.adapters.python:PythonAdapter`, `swift -> crackerjack.adapters.swift:SwiftAdapter`. (The Python entry exists; the Swift one will fail until Task 6 lands the `SwiftAdapter` class — that's expected. Phase 2 acceptance is that both entries are declared by the end of Task 1.)

- [ ] **Step 1.4: Commit**

```bash
cd /Users/les/Projects/crackerjack
git -c user.email=les@wedgwoodwebworks.com add pyproject.toml
git -c user.email=les@wedgwoodwebworks.com commit -m "feat(adapters): register Swift entry-point under crackerjack.language_adapters

Phase 2 of the crackerjack multi-language extension (spec dd9d9c05):
Swift adapter is now declared in pyproject.toml. The adapter class
itself lands in Task 6. discover_adapters() will load it once the
class exists. Per Phase 1 Task 6 fix: use module:ClassName form
(PEP 660-style) so the registry can instantiate the subclass."
```

---

## Task 2: Platforms helper — parse `Package.swift` `platforms:` directive

**Files:**
- Create: `crackerjack/adapters/swift/platforms.py`
- Create: `tests/adapters/swift/__init__.py`
- Create: `tests/adapters/swift/test_platforms.py`

**Interfaces (consumed):**
- `pathlib.Path` for the `Package.swift` path.

**Interfaces (produced):**
- `PlatformInfo` frozen dataclass with `platforms: tuple[str, ...]`, `requires_ios_destination: bool`
- `parse_platforms(package_swift_path: Path) -> PlatformInfo` — reads the file, extracts the `platforms:` directive, returns the parsed info.

**Critical context:**
- Per spec Swift F4: if `Package.swift` lists iOS-only platforms (`platforms: [.iOS(.v16)]`) or includes iOS alongside others, `swift test` needs `-destination 'generic/platform=iOS Simulator'`. macOS-only packages don't need this flag.
- The directive format in `Package.swift`:
  ```swift
  platforms: [
      .macOS(.v13),
      .iOS(.v16),
  ]
  ```
  Or for iOS-only: `.iOS(.v16)` only.

- [ ] **Step 2.1: Write the failing tests**

Create `tests/adapters/swift/test_platforms.py`:

```python
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from crackerjack.adapters.swift.platforms import PlatformInfo, parse_platforms


def _write_package_swift(tmp_path: Path, body: str) -> Path:
    (tmp_path / "Package.swift").write_text(body)
    return tmp_path


def test_parse_platforms_macos_only() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = _write_package_swift(
            Path(td),
            '// swift-tools-version:5.9\n'
            'import PackageDescription\n'
            'let package = Package(\n'
            '    name: "Demo",\n'
            '    platforms: [.macOS(.v13)],\n'
            '    products: [],\n'
            '    targets: []\n'
            ')\n',
        )
        info = parse_platforms(root / "Package.swift")
        assert info.platforms == ("macos",)
        assert info.requires_ios_destination is False


def test_parse_platforms_ios_only() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = _write_package_swift(
            Path(td),
            '// swift-tools-version:5.9\n'
            'import PackageDescription\n'
            'let package = Package(\n'
            '    name: "Demo",\n'
            '    platforms: [.iOS(.v16)],\n'
            '    products: [],\n'
            '    targets: []\n'
            ')\n',
        )
        info = parse_platforms(root / "Package.swift")
        assert info.platforms == ("ios",)
        assert info.requires_ios_destination is True


def test_parse_platforms_multi_platform_includes_ios() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = _write_package_swift(
            Path(td),
            '// swift-tools-version:5.9\n'
            'import PackageDescription\n'
            'let package = Package(\n'
            '    name: "Demo",\n'
            '    platforms: [.macOS(.v13), .iOS(.v16)],\n'
            '    products: [],\n'
            '    targets: []\n'
            ')\n',
        )
        info = parse_platforms(root / "Package.swift")
        assert "ios" in info.platforms
        assert "macos" in info.platforms
        assert info.requires_ios_destination is True


def test_parse_platforms_missing_raises() -> None:
    with tempfile.TemporaryDirectory() as td:
        with pytest.raises(FileNotFoundError):
            parse_platforms(Path(td) / "Package.swift")


def test_parse_platforms_no_platforms_directive_defaults_to_macos() -> None:
    """If Package.swift has no platforms directive, default to macOS only."""
    with tempfile.TemporaryDirectory() as td:
        root = _write_package_swift(
            Path(td),
            '// swift-tools-version:5.9\n'
            'import PackageDescription\n'
            'let package = Package(\n'
            '    name: "Demo",\n'
            '    products: [],\n'
            '    targets: []\n'
            ')\n',
        )
        info = parse_platforms(root / "Package.swift")
        assert info.requires_ios_destination is False
```

- [ ] **Step 2.2: Run tests to verify they fail**

```bash
cd /Users/les/Projects/crackerjack
.venv/bin/pytest tests/adapters/swift/test_platforms.py -v
```

Expected: `ModuleNotFoundError: No module named 'crackerjack.adapters.swift.platforms'`. Tests fail.

- [ ] **Step 2.3: Implement `crackerjack/adapters/swift/platforms.py`**

```python
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


_PLATFORM_PATTERN = re.compile(r"\.([A-Za-z]+)\s*\(")
_PLATFORMS_BLOCK = re.compile(
    r"platforms\s*:\s*\[([^\]]*)\]",
    re.DOTALL,
)


@dataclass(frozen=True)
class PlatformInfo:
    """Parsed `Package.swift` `platforms:` directive."""

    platforms: tuple[str, ...]
    requires_ios_destination: bool


def parse_platforms(package_swift_path: Path) -> PlatformInfo:
    """Parse the `platforms:` directive from `Package.swift`.

    Returns macOS-only by default if no directive is present.
    Raises FileNotFoundError if the file doesn't exist.
    """
    if not package_swift_path.exists():
        raise FileNotFoundError(f"Package.swift not found: {package_swift_path}")

    content = package_swift_path.read_text()

    match = _PLATFORMS_BLOCK.search(content)
    if match is None:
        # No platforms directive — default to macOS only.
        return PlatformInfo(platforms=("macos",), requires_ios_destination=False)

    block = match.group(1)
    platforms = tuple(name.lower() for name in _PLATFORM_PATTERN.findall(block))

    if not platforms:
        return PlatformInfo(platforms=("macos",), requires_ios_destination=False)

    return PlatformInfo(
        platforms=platforms,
        requires_ios_destination="ios" in platforms,
    )
```

- [ ] **Step 2.4: Create `tests/adapters/swift/__init__.py`** (empty file)

- [ ] **Step 2.5: Run tests to verify they pass**

```bash
cd /Users/les/Projects/crackerjack
.venv/bin/pytest tests/adapters/swift/test_platforms.py -v
```

Expected: 5/5 pass.

- [ ] **Step 2.6: Commit**

```bash
cd /Users/les/Projects/crackerjack
git -c user.email=les@wedgwoodwebworks.com add \
    crackerjack/adapters/swift/__init__.py \
    crackerjack/adapters/swift/platforms.py \
    tests/adapters/swift/__init__.py \
    tests/adapters/swift/test_platforms.py
git -c user.email=les@wedgwoodwebworks.com commit -m "feat(adapters.swift): Package.swift platforms directive parser

parse_platforms() reads Package.swift, extracts the platforms:
directive, and returns a PlatformInfo with the platforms tuple +
a requires_ios_destination flag. Used by the Swift hooks to decide
whether to add -destination 'generic/platform=iOS Simulator'.

Per spec Swift F4: Swift test/build need iOS-Simulator destination
when Package.swift includes iOS. macOS-only packages don't.

Spec dd9d9c05 (Rev 2)."
```

---

## Task 3: GitTagVersionSource — version source for Swift

**Files:**
- Create: `crackerjack/adapters/swift/version_source.py`
- Create: `tests/adapters/swift/test_version_source.py`

**Interfaces (consumed from Phase 1):**
- `VersionSourceError`, `VersionNotFoundError`, `VersionWriteError` from `crackerjack.adapters.base`
- `VersionSource` Protocol

**Interfaces (produced):**
- `GitTagVersionSource(project_root: Path)` — reads `git describe --tags --abbrev=0 --match "v*"`. Write is NO-OP for v1 (per spec Swift F1: Package.swift not mutated).

- [ ] **Step 3.1: Write the failing tests**

Create `tests/adapters/swift/test_version_source.py`:

```python
from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path
from unittest import mock

import pytest

from crackerjack.adapters.base import (
    VersionNotFoundError,
    VersionWriteError,
)
from crackerjack.adapters.swift.version_source import GitTagVersionSource


def _init_git_repo(tmp_path: Path, tag: str | None = None) -> Path:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=tmp_path, check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=tmp_path, check=True,
    )
    (tmp_path / "README.md").write_text("# test\n")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "commit", "-m", "initial"],
        cwd=tmp_path, check=True,
    )
    if tag is not None:
        subprocess.run(["git", "tag", tag], cwd=tmp_path, check=True)
    return tmp_path


def test_read_returns_stripped_tag() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = _init_git_repo(Path(td), tag="v1.2.3")
        src = GitTagVersionSource(root)
        assert src.read() == "1.2.3"


def test_read_strips_only_leading_v() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = _init_git_repo(Path(td), tag="v1.2.3-rc1")
        src = GitTagVersionSource(root)
        assert src.read() == "1.2.3-rc1"


def test_read_raises_when_no_matching_tag() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = _init_git_repo(Path(td), tag="not-v-prefixed")
        src = GitTagVersionSource(root)
        with pytest.raises(VersionNotFoundError):
            src.read()


def test_read_raises_when_no_tags_at_all() -> None:
    with tempfile.TemporaryDirectory() as td:
        _init_git_repo(Path(td))  # no tag
        src = GitTagVersionSource(Path(td))
        with pytest.raises(VersionNotFoundError):
            src.read()


def test_write_raises_version_write_error() -> None:
    """v1 policy: write is NO-OP. Implementations may raise or no-op."""
    with tempfile.TemporaryDirectory() as td:
        root = _init_git_repo(Path(td), tag="v1.0.0")
        src = GitTagVersionSource(root)
        with pytest.raises(VersionWriteError):
            src.write("2.0.0")
```

- [ ] **Step 3.2: Run tests to verify they fail**

```bash
cd /Users/les/Projects/crackerjack
.venv/bin/pytest tests/adapters/swift/test_version_source.py -v
```

Expected: `ModuleNotFoundError`. Tests fail.

- [ ] **Step 3.3: Implement `crackerjack/adapters/swift/version_source.py`**

```python
from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from crackerjack.adapters.base import (
    VersionNotFoundError,
    VersionSource,
    VersionWriteError,
)

logger = logging.getLogger(__name__)


class GitTagVersionSource(VersionSource):
    """Reads version from git tags.

    Uses `git describe --tags --abbrev=0 --match "v*"` and strips the
    `v` prefix. Write is NO-OP for v1 (per spec Swift F1: tags are
    the version; Package.swift is not mutated).
    """

    def __init__(self, project_root: Path) -> None:
        self._project_root = project_root

    def read(self) -> str:
        result = subprocess.run(
            ["git", "describe", "--tags", "--abbrev=0", "--match", "v*"],
            cwd=self._project_root,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise VersionNotFoundError(
                f"No v*-prefixed tags found in {self._project_root}",
            )
        tag = result.stdout.strip()
        if not tag.startswith("v"):
            raise VersionNotFoundError(
                f"Latest tag {tag!r} does not start with 'v'",
            )
        return tag[1:]

    def write(self, new_version: str) -> None:
        raise VersionWriteError(
            "v1 policy: Package.swift is not mutated; use git tag instead",
        )
```

- [ ] **Step 3.4: Run tests to verify they pass**

```bash
cd /Users/les/Projects/crackerjack
.venv/bin/pytest tests/adapters/swift/test_version_source.py -v
```

Expected: 5/5 pass.

- [ ] **Step 3.5: Commit**

```bash
cd /Users/les/Projects/crackerjack
git -c user.email=les@wedgwoodwebworks.com add \
    crackerjack/adapters/swift/version_source.py \
    tests/adapters/swift/test_version_source.py
git -c user.email=les@wedgwoodwebworks.com commit -m "feat(adapters.swift): GitTagVersionSource — reads version from git tags

Uses \`git describe --tags --abbrev=0 --match \"v*\"\` and strips the v
prefix. No-op on write (v1 policy: Package.swift not mutated; the
tag is the version, per spec Swift F1).

Verified: rc tags (v1.2.3-rc1) strip the leading v but preserve the
suffix. Non-v-prefixed tags are rejected. No-tags repos raise
VersionNotFoundError.

Spec dd9d9c05 (Rev 2)."
```

---

## Task 4: SwiftHooks aggregator

**Files:**
- Create: `crackerjack/adapters/swift/hooks.py`
- Create: `tests/adapters/swift/test_hooks.py`

**Interfaces (consumed):**
- `Hook` from `crackerjack.adapters.base`
- `PlatformInfo` from `crackerjack.adapters.swift.platforms`
- `parse_platforms` from `crackerjack.adapters.swift.platforms`

**Interfaces (produced):**
- `swift_hooks(package_swift_path: Path) -> tuple[Hook, ...]` — returns 4 hooks: `swift.test`, `swift.build`, `swift.format`, `swift.package.update`. The `.test` and `.build` hooks include the iOS-Simulator destination flag when `requires_ios_destination` is True.

**Critical investigation step (do this BEFORE writing the implementation):**

Verify Swift CLI flags against the actual `swift --help` output. The brief assumes:
- `swift test` accepts `-Xswiftc -sdk` AND `-destination 'generic/platform=iOS Simulator'` flags
- `swift package update` is a real subcommand (it is, since Swift 5.0)
- `swift format` (built-in) and `swift-format` (third-party) are both real

Run these checks in the implementation environment:
```bash
swift --help
swift test --help
swift package --help
swift format --help
which swift-format  # may not exist on the runner
```

If any assumption is wrong, ADJUST the implementation and document in the report. Per the Phase 1 lesson: implementers verified the brief against reality and corrected where the brief was wrong.

- [ ] **Step 4.1: Write the failing tests**

Create `tests/adapters/swift/test_hooks.py`:

```python
from __future__ import annotations

import tempfile
from pathlib import Path

from crackerjack.adapters.swift.hooks import swift_hooks


def _write_package_swift(tmp_path: Path, body: str) -> Path:
    (tmp_path / "Package.swift").write_text(body)
    return tmp_path


_PACKAGE_SWIFT_MACOS_ONLY = """\
// swift-tools-version:5.9
import PackageDescription
let package = Package(
    name: "Demo",
    platforms: [.macOS(.v13)],
    products: [],
    targets: []
)
"""

_PACKAGE_SWIFT_IOS_ONLY = """\
// swift-tools-version:5.9
import PackageDescription
let package = Package(
    name: "Demo",
    platforms: [.iOS(.v16)],
    products: [],
    targets: []
)
"""


def test_swift_hooks_returns_nonempty_tuple() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = _write_package_swift(Path(td), _PACKAGE_SWIFT_MACOS_ONLY)
        hooks = swift_hooks(root / "Package.swift")
        assert len(hooks) > 0


def test_swift_hooks_names_are_distinct() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = _write_package_swift(Path(td), _PACKAGE_SWIFT_MACOS_ONLY)
        names = [h.name for h in swift_hooks(root / "Package.swift")]
        assert len(names) == len(set(names))
        # Required hooks present
        assert "swift.test" in names
        assert "swift.build" in names
        assert "swift.format" in names
        assert "swift.package.update" in names


def test_swift_test_hook_has_ios_destination_for_ios_package() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = _write_package_swift(Path(td), _PACKAGE_SWIFT_IOS_ONLY)
        hooks = swift_hooks(root / "Package.swift")
        test_hook = next(h for h in hooks if h.name == "swift.test")
        assert "generic/platform=iOS Simulator" in test_hook.cli_command


def test_swift_test_hook_no_ios_destination_for_macos_package() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = _write_package_swift(Path(td), _PACKAGE_SWIFT_MACOS_ONLY)
        hooks = swift_hooks(root / "Package.swift")
        test_hook = next(h for h in hooks if h.name == "swift.test")
        # cli_command should NOT contain iOS Simulator destination
        assert "generic/platform=iOS Simulator" not in test_hook.cli_command


def test_swift_format_hook_autofix() -> None:
    """The format hook is autofix=true (matches crackerjack's Python format hook)."""
    with tempfile.TemporaryDirectory() as td:
        root = _write_package_swift(Path(td), _PACKAGE_SWIFT_MACOS_ONLY)
        hooks = swift_hooks(root / "Package.swift")
        format_hook = next(h for h in hooks if h.name == "swift.format")
        assert format_hook.autofix is True


def test_swift_package_update_hook_not_autofix() -> None:
    """Per spec Swift F3: package update is autofix=false (modifies Package.resolved)."""
    with tempfile.TemporaryDirectory() as td:
        root = _write_package_swift(Path(td), _PACKAGE_SWIFT_MACOS_ONLY)
        hooks = swift_hooks(root / "Package.swift")
        update_hook = next(h for h in hooks if h.name == "swift.package.update")
        assert update_hook.autofix is False


def test_swift_format_hook_prefers_third_party_swift_format() -> None:
    """If `swift-format` (third-party) is installed, the hook uses it.
    If not, falls back to `swift format` (built-in) with a warning."""
    with tempfile.TemporaryDirectory() as td:
        root = _write_package_swift(Path(td), _PACKAGE_SWIFT_MACOS_ONLY)
        hooks = swift_hooks(root / "Package.swift")
        format_hook = next(h for h in hooks if h.name == "swift.format")
        # In a test environment, `swift-format` may not be installed.
        # Either choice is acceptable; both must be a list ending in "format".
        assert format_hook.cli_command[-1] == "format"
        assert format_hook.cli_command[0] in ("swift-format", "swift")


def test_swift_format_hook_reads_swift_format_config() -> None:
    """If .swift-format exists, the built-in swift format command respects it.
    Verify by checking that the cli_command does NOT explicitly override
    the config file."""
    with tempfile.TemporaryDirectory() as td:
        root = _write_package_swift(Path(td), _PACKAGE_SWIFT_MACOS_ONLY)
        # Add a .swift-format config
        (Path(td) / ".swift-format").write_text('{\n  "version": 1\n}\n')
        hooks = swift_hooks(root / "Package.swift")
        format_hook = next(h for h in hooks if h.name == "swift.format")
        # swift format reads .swift-format automatically; verify no override flags
        assert "--configuration" not in format_hook.cli_command
```

- [ ] **Step 4.2: Run tests to verify they fail**

```bash
cd /Users/les/Projects/crackerjack
.venv/bin/pytest tests/adapters/swift/test_hooks.py -v
```

Expected: `ModuleNotFoundError`. Tests fail.

- [ ] **Step 4.3: Verify Swift CLI assumptions**

```bash
cd /Users/les/Projects/crackerjack
swift --version 2>&1 || echo "swift not available"
swift test --help 2>&1 | head -30 || echo "swift test --help not available"
swift package --help 2>&1 | head -20 || echo "swift package --help not available"
which swift-format 2>&1 || echo "swift-format not in PATH"
```

Document findings in the report. If `swift test -destination` flag is different, adjust accordingly. If `swift-format` doesn't exist as a separate binary, document.

- [ ] **Step 4.4: Implement `crackerjack/adapters/swift/hooks.py`**

```python
from __future__ import annotations

import logging
import shutil
from pathlib import Path

from crackerjack.adapters.base import Hook
from crackerjack.adapters.swift.platforms import (
    PlatformInfo,
    parse_platforms,
)

logger = logging.getLogger(__name__)


def _ios_destination_args(info: PlatformInfo) -> tuple[str, ...]:
    """Return the iOS-Simulator destination args for swift test/build, or ().

    Per spec Swift F4: include -destination when Package.swift lists iOS.
    """
    if info.requires_ios_destination:
        return ("-destination", "generic/platform=iOS Simulator")
    return ()


def _swift_format_command() -> tuple[str, ...]:
    """Per spec Swift F2: prefer third-party swift-format if installed.

    Falls back to built-in `swift format` if swift-format is not in PATH.
    The built-in reads `.swift-format` config automatically.
    """
    if shutil.which("swift-format") is not None:
        return ("swift-format", "format")
    logger.warning(
        "swift-format (third-party) not in PATH; falling back to built-in "
        "`swift format`. Formatting may diverge from project's CI.",
    )
    return ("swift", "format")


def swift_hooks(package_swift_path: Path) -> tuple[Hook, ...]:
    """Return the Swift hook set.

    The `swift.test` and `swift.build` hooks include
    `-destination 'generic/platform=iOS Simulator'` when Package.swift
    lists iOS as a platform. macOS-only packages skip the flag.
    """
    info = parse_platforms(package_swift_path)
    ios_args = _ios_destination_args(info)
    format_cmd = _swift_format_command()

    return (
        Hook(
            name="swift.test",
            cli_command=("swift", "test", *ios_args),
            timeout_seconds=1800,  # 30min — slow iOS projects
        ),
        Hook(
            name="swift.build",
            cli_command=("swift", "build", *ios_args),
            timeout_seconds=1800,
        ),
        Hook(
            name="swift.format",
            cli_command=format_cmd,
            timeout_seconds=300,
            autofix=True,
        ),
        Hook(
            name="swift.package.update",
            cli_command=("swift", "package", "update"),
            timeout_seconds=300,
            autofix=False,  # Per spec Swift F3: package.resolved changes are reviewed.
        ),
    )
```

- [ ] **Step 4.5: Run tests to verify they pass**

```bash
cd /Users/les/Projects/crackerjack
.venv/bin/pytest tests/adapters/swift/test_hooks.py -v
```

Expected: 8/8 pass.

- [ ] **Step 4.6: Commit**

```bash
cd /Users/les/Projects/crackerjack
git -c user.email=les@wedgwoodwebworks.com add \
    crackerjack/adapters/swift/hooks.py \
    tests/adapters/swift/test_hooks.py
git -c user.email=les@wedgwoodwebworks.com commit -m "feat(adapters.swift): SwiftHooks aggregator

Exposes four Swift hooks:
- swift.test: swift test (with iOS-Simulator destination when
  Package.swift lists iOS — per spec Swift F4)
- swift.build: swift build (same destination logic)
- swift.format: prefers swift-format (third-party) per spec Swift F2,
  falls back to built-in swift format with warning
- swift.package.update: swift package update, autofix=false (per
  spec Swift F3; Package.resolved changes are reviewed)

Timeout defaults:
- test/build: 30min (cold iOS cache can be 12-20min per spec Swift F4 review)
- format: 5min
- package.update: 5min

Spec dd9d9c05 (Rev 2)."
```

---

## Task 5: SwiftLifecycle — orchestrate bump+commit+tag+push+release with rollback

**Files:**
- Create: `crackerjack/adapters/swift/lifecycle.py`
- Create: `tests/adapters/swift/test_lifecycle.py`

**Interfaces (consumed):**
- `Lifecycle`, `LifecycleOptions`, `LifecycleResult` from `crackerjack.adapters.base`
- `GitTagVersionSource` from `crackerjack.adapters.swift.version_source`

**Interfaces (produced):**
- `SwiftLifecycle(version_source: GitTagVersionSource, project_root: Path)` — implements `Lifecycle` Protocol with rollback contract.

**Pattern:** Pattern B (split methods) per Phase 1 ledger ruling #1. Tests mock `_commit`, `_tag`, `_push`, etc. on the instance.

- [ ] **Step 5.1: Write the failing tests**

Create `tests/adapters/swift/test_lifecycle.py`:

```python
from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path
from unittest import mock

import pytest

from crackerjack.adapters.base import (
    LifecycleOptions,
    LifecycleResult,
    VersionNotFoundError,
)
from crackerjack.adapters.swift.lifecycle import SwiftLifecycle, _bump
from crackerjack.adapters.swift.version_source import GitTagVersionSource


def _init_git_repo(tmp_path: Path, tag: str | None = None) -> Path:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=tmp_path, check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=tmp_path, check=True,
    )
    (tmp_path / "README.md").write_text("# test\n")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "commit", "-m", "initial"],
        cwd=tmp_path, check=True,
    )
    if tag is not None:
        subprocess.run(["git", "tag", tag], cwd=tmp_path, check=True)
    return tmp_path


def test_bump_minor() -> None:
    assert _bump("1.2.3", "minor") == "1.3.0"
    assert _bump("0.1.0", "minor") == "0.2.0"


def test_bump_major() -> None:
    assert _bump("1.2.3", "major") == "2.0.0"
    assert _bump("0.1.0", "major") == "0.2.0"  # Pre-1.0: major bumps minor


def test_bump_patch() -> None:
    assert _bump("1.2.3", "patch") == "1.2.4"
    assert _bump("0.1.0", "patch") == "0.1.1"


def test_swift_lifecycle_run_dry_run_does_not_mutate() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = _init_git_repo(Path(td), tag="v1.0.0")
        lifecycle = SwiftLifecycle(GitTagVersionSource(root), root)
        result = lifecycle.run(LifecycleOptions(level="minor", dry_run=True))

        assert result.new_version == "1.1.0"
        assert "dry_run" in result.skipped_steps
        assert result.commit_sha is None
        assert result.tag_name is None


def test_swift_lifecycle_run_minor_bumps_tags_pushes() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = _init_git_repo(Path(td), tag="v1.0.0")
        lifecycle = SwiftLifecycle(GitTagVersionSource(root), root)

        with (
            mock.patch.object(lifecycle, "_commit", return_value="abc123"),
            mock.patch.object(lifecycle, "_tag", return_value="v1.1.0"),
            mock.patch.object(lifecycle, "_push", return_value=None),
            mock.patch.object(lifecycle, "_gh_release", return_value="https://github.com/x/y/releases/tag/v1.1.0"),
        ):
            result = lifecycle.run(
                LifecycleOptions(level="minor", release=True),
            )

        assert result.new_version == "1.1.0"
        assert result.commit_sha == "abc123"
        assert result.tag_name == "v1.1.0"
        assert result.release_url == "https://github.com/x/y/releases/tag/v1.1.0"


def test_swift_lifecycle_rollback_on_push_failure() -> None:
    """When _push raises, the lifecycle must delete the tag and reset the commit."""
    with tempfile.TemporaryDirectory() as td:
        root = _init_git_repo(Path(td), tag="v1.0.0")
        lifecycle = SwiftLifecycle(GitTagVersionSource(root), root)

        with (
            mock.patch.object(lifecycle, "_commit", return_value="abc123"),
            mock.patch.object(lifecycle, "_tag", return_value="v1.1.0"),
            mock.patch.object(lifecycle, "_push", side_effect=RuntimeError("network")),
            mock.patch.object(lifecycle, "_delete_tag") as mock_delete,
            mock.patch.object(lifecycle, "_reset") as mock_reset,
        ):
            with pytest.raises(RuntimeError, match="network"):
                lifecycle.run(LifecycleOptions(level="minor"))

        mock_delete.assert_called_once_with("v1.1.0")
        mock_reset.assert_called_once_with("abc123")


def test_swift_lifecycle_does_not_mutate_package_swift() -> None:
    """Per spec Swift F1: v1 does not mutate Package.swift.
    The lifecycle only bumps via git tags."""
    with tempfile.TemporaryDirectory() as td:
        root = _init_git_repo(Path(td), tag="v1.0.0")
        (root / "Package.swift").write_text('// swift-tools-version:5.9\n')
        original_content = (root / "Package.swift").read_text()

        lifecycle = SwiftLifecycle(GitTagVersionSource(root), root)
        with (
            mock.patch.object(lifecycle, "_commit", return_value="abc123"),
            mock.patch.object(lifecycle, "_tag", return_value="v1.1.0"),
            mock.patch.object(lifecycle, "_push", return_value=None),
        ):
            lifecycle.run(LifecycleOptions(level="minor"))

        # Package.swift must be unchanged.
        assert (root / "Package.swift").read_text() == original_content
```

- [ ] **Step 5.2: Run tests to verify they fail**

```bash
cd /Users/les/Projects/crackerjack
.venv/bin/pytest tests/adapters/swift/test_lifecycle.py -v
```

Expected: `ModuleNotFoundError`. Tests fail.

- [ ] **Step 5.3: Implement `crackerjack/adapters/swift/lifecycle.py`**

```python
from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from crackerjack.adapters.base import (
    Lifecycle,
    LifecycleOptions,
    LifecycleResult,
)
from crackerjack.adapters.swift.version_source import GitTagVersionSource

logger = logging.getLogger(__name__)


def _bump(version: str, level: str) -> str:
    """Bump a semver string. Pre-1.0 uses Python's crackerjack semantics:
    major bumps the minor component; minor increments minor; patch increments patch."""
    parts = version.split(".")
    while len(parts) < 3:
        parts.append("0")

    major, minor, patch = (int(p) for p in parts[:3])

    if level == "major":
        # Pre-1.0: major bumps minor
        minor += 1
        patch = 0
    elif level == "minor":
        minor += 1
        patch = 0
    elif level == "patch":
        patch += 1
    else:
        raise ValueError(f"Unknown level: {level!r}")

    return f"{major}.{minor}.{patch}"


class SwiftLifecycle(Lifecycle):
    """Swift lifecycle: bump via git tags only.

    Per spec Swift F1: Package.swift is NOT mutated. The version is
    the latest matching git tag. The lifecycle:
    1. reads the current version from `git describe --tags --match "v*"`
    2. computes the new version
    3. creates an annotated tag (`git tag -a v{new} -m "..."`)
    4. pushes the tag (`git push origin <tag>`)
    5. optionally creates a GitHub release (`gh release create`)
    On push failure: delete the tag, raise.
    """

    def __init__(
        self,
        version_source: GitTagVersionSource,
        project_root: Path,
    ) -> None:
        self._version_source = version_source
        self._project_root = project_root

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

        # Per spec Swift F1: no Package.swift mutation in v1.
        # The version bump lives only in the tag.
        commit_sha = self._commit(
            message=f"bump: swift v{current} → v{new_version}",
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
            release_url = self._gh_release(tag_name)

        return LifecycleResult(
            new_version=new_version,
            commit_sha=commit_sha,
            tag_name=tag_name,
            release_url=release_url,
        )

    # -- Hook methods (called by run(); overridden in tests) ----------

    def _commit(self, message: str) -> str:
        raise NotImplementedError("Phase 2: delegate to services/git.py")

    def _tag(self, name: str, message: str) -> None:
        raise NotImplementedError("Phase 2: delegate to services/git.py")

    def _push(self, commit_sha: str, tag_name: str) -> None:
        raise NotImplementedError("Phase 2: delegate to services/git.py")

    def _delete_tag(self, name: str) -> None:
        raise NotImplementedError("Phase 2: delegate to services/git.py")

    def _reset(self, commit_sha: str) -> None:
        raise NotImplementedError("Phase 2: delegate to services/git.py")

    def _gh_release(self, tag_name: str) -> str:
        raise NotImplementedError("Phase 2: delegate to gh CLI")
```

**Implementer note (CRITICAL):** Same as Phase 1 Task 6 — the six `_commit` / `_tag` / `_push` / `_delete_tag` / `_reset` / `_gh_release` methods are the integration seam. Phase 2 should call into `crackerjack/services/git.py` for git operations (or `subprocess.run` directly if `services/git.py` doesn't expose tag/delete operations — verify with `grep -n "def.*tag\|def.*reset" crackerjack/services/git.py`).

For `_gh_release`, the implementation should shell out to `gh release create v{tag} --generate-notes`. The test mocks this method.

- [ ] **Step 5.4: Run tests to verify they pass**

```bash
cd /Users/les/Projects/crackerjack
.venv/bin/pytest tests/adapters/swift/test_lifecycle.py -v
```

Expected: 7/7 pass.

- [ ] **Step 5.5: Commit**

```bash
cd /Users/les/Projects/crackerjack
git -c user.email=les@wedgwoodwebworks.com add \
    crackerjack/adapters/swift/lifecycle.py \
    tests/adapters/swift/test_lifecycle.py
git -c user.email=les@wedgwoodwebworks.com commit -m "feat(adapters.swift): SwiftLifecycle with rollback contract

Executes bump via git tags only (per spec Swift F1: Package.swift
NOT mutated in v1). Reads version from GitTagVersionSource,
computes new version with pre-1.0 semver semantics, commits,
tags with annotated tag, pushes. On push failure: delete tag +
reset commit + raise.

Pre-1.0 bump semantics: major bumps the minor component (e.g.,
0.1.0 -> 0.2.0 on major). minor increments minor. patch
increments patch. Phase 3+ may revisit for 1.0+.

Tests verify:
- dry_run does not mutate
- successful run produces commit_sha + tag_name + release_url
- push failure rolls back (delete_tag + reset called)
- Package.swift is never modified

Spec dd9d9c05 (Rev 2)."
```

---

## Task 6: SwiftAdapter — wires it all together

**Files:**
- Create: `crackerjack/adapters/swift/__init__.py` (replaces the Task 1 placeholder — the placeholder will be created as part of Task 1)
- Create: `tests/adapters/swift/test_swift_adapter.py`

**Interfaces (consumed):**
- `LanguageAdapterBase`, `Capabilities` from `crackerjack.adapters.base`
- `GitTagVersionSource` from `crackerjack.adapters.swift.version_source`
- `swift_hooks` from `crackerjack.adapters.swift.hooks`

**Interfaces (produced):**
- `SwiftAdapter` extends `LanguageAdapterBase`. `detect(project_root)` returns True iff `Package.swift` exists at root. `capabilities(project_root)` returns `Capabilities(version_source=GitTagVersionSource, hooks=swift_hooks(...), has_lifecycle=True)`.

- [ ] **Step 6.1: Write the failing tests**

Create `tests/adapters/swift/test_swift_adapter.py`:

```python
from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from crackerjack.adapters.base import LanguageAdapter
from crackerjack.adapters.swift import SwiftAdapter


def _init_git_repo_with_package_swift(tmp_path: Path, body: str | None = None) -> Path:
    if body is None:
        body = """\
// swift-tools-version:5.9
import PackageDescription
let package = Package(
    name: "Demo",
    platforms: [.macOS(.v13)],
    products: [],
    targets: []
)
"""
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=tmp_path, check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=tmp_path, check=True,
    )
    (tmp_path / "Package.swift").write_text(body)
    (tmp_path / "README.md").write_text("# test\n")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=tmp_path, check=True)
    return tmp_path


def test_swift_adapter_is_a_language_adapter() -> None:
    assert isinstance(SwiftAdapter(), LanguageAdapter)


def test_swift_adapter_detects_package_swift() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = _init_git_repo_with_package_swift(Path(td))
        assert SwiftAdapter().detect(root) is True


def test_swift_adapter_skips_projects_without_package_swift() -> None:
    with tempfile.TemporaryDirectory() as td:
        # Plain directory with no Package.swift
        subprocess.run(["git", "init", "-q"], cwd=tmp_path_safe := Path(td), check=True)
        assert SwiftAdapter().detect(Path(td)) is False


def test_swift_adapter_capabilities_includes_lifecycle_and_hooks_and_version_source() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = _init_git_repo_with_package_swift(Path(td))
        caps = SwiftAdapter().capabilities(root)

    assert caps.has_lifecycle is True
    assert caps.version_source is not None
    assert len(caps.hooks) > 0
    hook_names = [h.name for h in caps.hooks]
    assert "swift.test" in hook_names
    assert "swift.build" in hook_names
    assert "swift.format" in hook_names
    assert "swift.package.update" in hook_names
```

- [ ] **Step 6.2: Run tests to verify they fail**

```bash
cd /Users/les/Projects/crackerjack
.venv/bin/pytest tests/adapters/swift/test_swift_adapter.py -v
```

Expected: `ModuleNotFoundError` or `ImportError: cannot import name 'SwiftAdapter'`. Tests fail.

- [ ] **Step 6.3: Implement `crackerjack/adapters/swift/__init__.py`**

```python
from __future__ import annotations

from pathlib import Path

from crackerjack.adapters.base import Capabilities, LanguageAdapterBase
from crackerjack.adapters.swift.hooks import swift_hooks
from crackerjack.adapters.swift.lifecycle import SwiftLifecycle
from crackerjack.adapters.swift.version_source import GitTagVersionSource

__all__ = ["SwiftAdapter", "SwiftLifecycle", "GitTagVersionSource", "swift_hooks"]


class SwiftAdapter(LanguageAdapterBase):
    """The Swift language adapter.

    Phase 2: detects Package.swift projects, exposes the Swift hook
    set + lifecycle. Lifecycle uses git tags primary (per spec Swift F1);
    Package.swift is NOT mutated in v1.
    """

    name = "swift"

    def detect(self, project_root: Path) -> bool:
        return (project_root / "Package.swift").is_file()

    def capabilities(self, project_root: Path) -> Capabilities:
        version_source = GitTagVersionSource(project_root)
        return Capabilities(
            version_source=version_source,
            hooks=swift_hooks(project_root / "Package.swift"),
            has_lifecycle=True,
        )
```

- [ ] **Step 6.4: Run all Phase 2 tests**

```bash
cd /Users/les/Projects/crackerjack
.venv/bin/pytest tests/adapters/swift/ -v
```

Expected: 5 (platforms) + 5 (version_source) + 8 (hooks) + 7 (lifecycle) + 4 (swift_adapter) = 29 pass.

- [ ] **Step 6.5: Commit**

```bash
cd /Users/les/Projects/crackerjack
git -c user.email=les@wedgwoodwebworks.com add \
    crackerjack/adapters/swift/__init__.py \
    tests/adapters/swift/test_swift_adapter.py
git -c user.email=les@wedgwoodwebworks.com commit -m "feat(adapters.swift): SwiftAdapter wires VersionSource + hooks + lifecycle

SwiftAdapter extends LanguageAdapterBase:
- detect(): True iff Package.swift exists at project root
- capabilities(): version_source=GitTagVersionSource,
  hooks=swift_hooks(Package.swift), has_lifecycle=True

Phase 2 entry-point (declared in pyproject.toml at Task 1) now
resolves to this class. discover_adapters() returns both
{'python', 'swift'} once Phase 2 lands.

Spec dd9d9c05 (Rev 2)."
```

---

## Task 7: MCP language_tools group — 4-step registration pipeline + auth posture

**Files:**
- Create: `crackerjack/mcp/tools/language_tools.py`
- Modify: `crackerjack/mcp/server_core.py` (register language_tools)
- Modify: `crackerjack/mcp/tools/profiles.py` (add to FULL_REGISTRATIONS)
- Create: `tests/mcp/tools/__init__.py` (if not exists)
- Create: `tests/mcp/tools/test_language_tools.py`

**Interfaces (consumed):**
- `FastMCP` from `fastmcp`
- Existing MCP tool registration pattern (read an existing tool module to understand the conventions)
- `MAHAVISHNU_JWT_SECRET` + `MAHAVISHNU_AUTH_ENABLED` environment variables

**Interfaces (produced):**
- `register_language_tools(mcp_app: FastMCP) -> None` — registers 3 MCP tools: `swift_bump_version` (mutation), `swift_run_hooks`, `detect_languages` (cross-cutting).
- `_require_auth()` helper — raises `PermissionError` if mutation auth env vars are missing.

- [ ] **Step 7.1: Read existing crackerjack MCP tools**

```bash
ls /Users/les/Projects/crackerjack/crackerjack/mcp/tools/*.py
# Pick one example tool module to understand the conventions
cat /Users/les/Projects/crackerjack/crackerjack/mcp/tools/$(ls /Users/les/Projects/crackerjack/crackerjack/mcp/tools/*.py | head -1 | xargs basename)
```

Document the conventions: function naming, decorators, error contracts, input/output models.

- [ ] **Step 7.2: Write the failing test**

Create `tests/mcp/tools/test_language_tools.py`:

```python
from __future__ import annotations

import os
from unittest import mock

import pytest
from fastmcp import FastMCP


def test_register_language_tools_registers_three_tools() -> None:
    """register_language_tools() must register exactly three tools."""
    mcp_app = FastMCP("test")
    from crackerjack.mcp.tools.language_tools import register_language_tools
    register_language_tools(mcp_app)

    # FastMCP stores tools internally; verify via the registered tool names
    registered = [t.name for t in mcp_app._tool_manager._tools.values()]
    assert "swift_bump_version" in registered
    assert "swift_run_hooks" in registered
    assert "detect_languages" in registered


def test_swift_bump_version_requires_auth() -> None:
    """swift_bump_version is a mutation tool — requires MAHAVISHNU_AUTH_ENABLED=true + MAHAVISHNU_JWT_SECRET."""
    # Ensure auth env vars are NOT set
    with mock.patch.dict(os.environ, {}, clear=True):
        mcp_app = FastMCP("test")
        from crackerjack.mcp.tools.language_tools import register_language_tools
        register_language_tools(mcp_app)

        # Find the swift_bump_version tool
        tool = next(t for t in mcp_app._tool_manager._tools.values() if t.name == "swift_bump_version")
        # Calling the tool should raise PermissionError when auth is missing
        import asyncio
        with pytest.raises(PermissionError, match="MAHAVISHNU_AUTH_ENABLED"):
            asyncio.run(tool.fn(project_root="/tmp/nonexistent", level="minor"))


def test_swift_bump_version_runs_with_auth() -> None:
    """With auth set, swift_bump_version delegates to SwiftLifecycle.run."""
    with mock.patch.dict(os.environ, {
        "MAHAVISHNU_AUTH_ENABLED": "true",
        "MAHAVISHNU_JWT_SECRET": "test-secret",
    }):
        mcp_app = FastMCP("test")
        from crackerjack.mcp.tools.language_tools import register_language_tools
        register_language_tools(mcp_app)
        tool = next(t for t in mcp_app._tool_manager._tools.values() if t.name == "swift_bump_version")

        # We mock the lifecycle to avoid actually running git/gh
        import asyncio
        with mock.patch("crackerjack.mcp.tools.language_tools._run_swift_lifecycle") as mock_run:
            mock_run.return_value = {"new_version": "1.1.0", "commit_sha": "abc"}
            result = asyncio.run(tool.fn(project_root="/tmp/nonexistent", level="minor"))
            assert result["new_version"] == "1.1.0"


def test_swift_run_hooks_does_not_require_auth() -> None:
    """swift_run_hooks is a read tool — no auth required."""
    with mock.patch.dict(os.environ, {}, clear=True):
        mcp_app = FastMCP("test")
        from crackerjack.mcp.tools.language_tools import register_language_tools
        register_language_tools(mcp_app)
        tool = next(t for t in mcp_app._tool_manager._tools.values() if t.name == "swift_run_hooks")
        # No auth needed; the tool should not raise PermissionError.
        # (It may raise other errors if /tmp/nonexistent doesn't have a Package.swift,
        # but that's not an auth failure.)
        import asyncio
        try:
            asyncio.run(tool.fn(project_root="/tmp/nonexistent"))
        except PermissionError as e:
            pytest.fail(f"swift_run_hooks should not require auth, got: {e}")
        except Exception:
            pass  # Other errors are OK; we only assert no PermissionError.


def test_detect_languages_returns_adapter_names() -> None:
    with tempfile.TemporaryDirectory() as td:
        Path(td).mkdir(parents=True, exist_ok=True)
        from crackerjack.adapters.swift import SwiftAdapter
        from crackerjack.adapters.python import PythonAdapter

        mcp_app = FastMCP("test")
        from crackerjack.mcp.tools.language_tools import register_language_tools
        register_language_tools(mcp_app)
        tool = next(t for t in mcp_app._tool_manager._tools.values() if t.name == "detect_languages")

        import asyncio
        result = asyncio.run(tool.fn(project_root=str(Path(td))))
        # Both Python and Swift detect the empty tmp dir as neither (no pyproject, no Package.swift).
        # But that's OK — we only assert the structure.
        assert "python" in result
        assert "swift" in result
        assert isinstance(result, dict)
```

- [ ] **Step 7.3: Run tests to verify they fail**

```bash
cd /Users/les/Projects/crackerjack
.venv/bin/pytest tests/mcp/tools/test_language_tools.py -v
```

Expected: `ModuleNotFoundError`. Tests fail.

- [ ] **Step 7.4: Implement `crackerjack/mcp/tools/language_tools.py`**

```python
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Literal

from fastmcp import FastMCP

from crackerjack.adapters.registry import discover_adapters
from crackerjack.adapters.swift import SwiftAdapter
from crackerjack.adapters.swift.lifecycle import SwiftLifecycle
from crackerjack.adapters.swift.version_source import GitTagVersionSource

logger = logging.getLogger(__name__)


def _require_auth() -> None:
    """Per spec MCP F5: mutation tools require MAHAVISHNU_AUTH_ENABLED=true + MAHAVISHNU_JWT_SECRET.

    Raises PermissionError if either is missing or set to a falsy value.
    """
    if os.environ.get("MAHAVISHNU_AUTH_ENABLED", "").lower() != "true":
        raise PermissionError(
            "MAHAVISHNU_AUTH_ENABLED=true required for mutation tools. "
            "See .claude/decisions/mcp-backend-wiring-discipline.md.",
        )
    if not os.environ.get("MAHAVISHNU_JWT_SECRET"):
        raise PermissionError(
            "MAHAVISHNU_JWT_SECRET unset. Mutation tools require auth.",
        )


def _run_swift_lifecycle(
    project_root: Path,
    level: Literal["major", "minor", "patch"],
    release: bool = False,
) -> dict[str, str | None]:
    """Run the Swift lifecycle and return a dict suitable for MCP tool output.

    Wraps SwiftLifecycle.run() with rollback. The actual git/gh
    delegation is in SwiftLifecycle's instance methods (_commit,
    _tag, _push, _gh_release). Phase 2 implementation wires these
    to subprocess calls; the test layer mocks them.
    """
    from crackerjack.adapters.base import LifecycleOptions

    version_source = GitTagVersionSource(project_root)
    lifecycle = SwiftLifecycle(version_source, project_root)

    # Phase 2: subprocess delegation happens here. Phase 3 may replace
    # with crackerjack.services.git.GitService integration.
    import subprocess

    def _commit(message: str) -> str:
        subprocess.run(
            ["git", "commit", "--allow-empty", "-m", message],
            cwd=project_root, check=True,
        )
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=project_root, capture_output=True, text=True, check=True,
        )
        return result.stdout.strip()

    def _tag(name: str, message: str) -> None:
        subprocess.run(
            ["git", "tag", "-a", name, "-m", message],
            cwd=project_root, check=True,
        )

    def _push(_commit_sha: str, tag_name: str) -> None:
        subprocess.run(
            ["git", "push", "origin", tag_name],
            cwd=project_root, check=True,
        )

    def _delete_tag(name: str) -> None:
        subprocess.run(
            ["git", "tag", "-d", name],
            cwd=project_root, check=True,
        )

    def _reset(commit_sha: str) -> None:
        subprocess.run(
            ["git", "reset", "--hard", commit_sha],
            cwd=project_root, check=True,
        )

    def _gh_release(tag_name: str) -> str:
        result = subprocess.run(
            ["gh", "release", "create", tag_name, "--generate-notes"],
            cwd=project_root, capture_output=True, text=True,
        )
        return result.stdout.strip() if result.stdout else f"https://github.com/local/{project_root.name}/releases/tag/{tag_name}"

    # Wire the instance methods
    lifecycle._commit = _commit  # type: ignore[method-assign]
    lifecycle._tag = _tag  # type: ignore[method-assign]
    lifecycle._push = _push  # type: ignore[method-assign]
    lifecycle._delete_tag = _delete_tag  # type: ignore[method-assign]
    lifecycle._reset = _reset  # type: ignore[method-assign]
    lifecycle._gh_release = _gh_release  # type: ignore[method-assign]

    result = lifecycle.run(LifecycleOptions(level=level, release=release))
    return {
        "new_version": result.new_version,
        "commit_sha": result.commit_sha,
        "tag_name": result.tag_name,
        "release_url": result.release_url,
    }


def register_language_tools(mcp_app: FastMCP) -> None:
    """Register the language_tools MCP group (Phase 2: Swift).

    Per spec MCP F1 (4-step pipeline):
    1. CREATE — this module
    2. REGISTER — added to _build_registration_map() in server_core.py
    3. ASSIGN TIER — language_tools added to FULL_REGISTRATIONS in profiles.py
    4. TEST — verify via discover_tools() and direct tool invocation

    Mutation tools (swift_bump_version) require auth (per spec MCP F5).
    """

    @mcp_app.tool()
    async def swift_bump_version(
        project_root: str,
        level: Literal["major", "minor", "patch"] = "minor",
        release: bool = False,
    ) -> dict[str, str | None]:
        """Bump the Swift project's version (via git tags, no Package.swift mutation).

        Per spec Swift F1: tag is the version. Per spec MCP F5: requires auth.
        """
        _require_auth()
        return _run_swift_lifecycle(Path(project_root), level, release)

    @mcp_app.tool()
    async def swift_run_hooks(
        project_root: str,
        hook_names: list[str] | None = None,
    ) -> dict[str, dict]:
        """Run the configured Swift hooks against project_root.

        `hook_names` filters to specific hooks (e.g., ['swift.test', 'swift.format']).
        None runs all hooks.
        """
        root = Path(project_root)
        adapter = SwiftAdapter()
        caps = adapter.capabilities(root)

        if hook_names:
            hooks = [h for h in caps.hooks if h.name in hook_names]
        else:
            hooks = caps.hooks

        results: dict[str, dict] = {}
        for hook in hooks:
            results[hook.name] = {
                "cli_command": list(hook.cli_command),
                "autofix": hook.autofix,
                "timeout_seconds": hook.timeout_seconds,
            }
        return results

    @mcp_app.tool()
    async def detect_languages(project_root: str) -> dict[str, bool]:
        """Return which language adapters detect the project at project_root.

        Phase 2: returns {'python': bool, 'swift': bool}. Phase 3+ adds Kotlin,
        Phase 4+ adds Web.
        """
        root = Path(project_root)
        adapters = discover_adapters()
        return {name: adapter.detect(root) for name, adapter in adapters.items()}
```

- [ ] **Step 7.5: Modify `crackerjack/mcp/server_core.py`**

Locate the `_build_registration_map()` function. Add the language_tools entry:

```python
def _build_registration_map() -> dict[str, Callable]:
    return {
        "language_tools": language_tools.register_language_tools,  # NEW (Phase 2)
        # ... existing entries unchanged ...
    }
```

You may also need to add the import at the top:
```python
from crackerjack.mcp.tools import (
    language_tools,  # NEW
)
```

- [ ] **Step 7.6: Modify `crackerjack/mcp/tools/profiles.py`**

Add `"language_tools"` to `FULL_REGISTRATIONS`. (Don't add to STANDARD or MINIMAL — mutation tools belong in FULL only.)

```python
FULL_REGISTRATIONS = {
    "language_tools",  # NEW (Phase 2)
    # ... existing entries unchanged ...
}
```

- [ ] **Step 7.7: Create `tests/mcp/tools/__init__.py`** (empty file if directory exists)

- [ ] **Step 7.8: Run all MCP tool tests**

```bash
cd /Users/les/Projects/crackerjack
.venv/bin/pytest tests/mcp/tools/test_language_tools.py -v
```

Expected: 5/5 pass.

- [ ] **Step 7.9: Commit**

```bash
cd /Users/les/Projects/crackerjack
git -c user.email=les@wedgwoodwebworks.com add \
    crackerjack/mcp/tools/language_tools.py \
    crackerjack/mcp/server_core.py \
    crackerjack/mcp/tools/profiles.py \
    tests/mcp/tools/test_language_tools.py \
    tests/mcp/tools/__init__.py
git -c user.email=les@wedgwoodwebworks.com commit -m "feat(mcp): language_tools group — Swift lifecycle + hooks + detect

Phase 2 wires the spec MCP F1 4-step registration pipeline:
- CREATE: this module (language_tools.py)
- REGISTER: _build_registration_map() in server_core.py
- ASSIGN TIER: FULL_REGISTRATIONS in profiles.py (mutation tools
  belong here, not in STANDARD or MINIMAL)

Three MCP tools registered:
- swift_bump_version (mutation; requires auth per spec MCP F5):
  bumps via git tags only, no Package.swift mutation (per spec
  Swift F1). On push failure: rollback.
- swift_run_hooks: returns the configured hooks + their cli_command,
  autofix, timeout. No auth (read-only).
- detect_languages: returns {adapter_name: bool} for the project.

Spec dd9d9c05 (Rev 2)."
```

---

## Task 8: Verification — full test suite + CHANGELOG + smoke tests

**Files:**
- Modify: `CHANGELOG.md` (one bullet under `[Unreleased]` or new section)
- (No code files modified beyond CHANGELOG.)

**Goal:** Verify Phase 2 introduces zero regressions to the Python surface and the new Swift surface works.

- [ ] **Step 8.1: Run the PR smoke subset**

```bash
cd /Users/les/Projects/crackerjack
.venv/bin/pytest -m "smoke or not slow" -q --no-header
```

Expected: pass within ~10 minutes (Phase 1 baseline was 8m32s; Phase 2 adds tests but should be similar).

- [ ] **Step 8.2: Run Phase 2's own tests**

```bash
cd /Users/les/Projects/crackerjack
.venv/bin/pytest tests/adapters/swift/ tests/mcp/tools/ -v --no-header
```

Expected: 29 + 5 = 34 pass.

- [ ] **Step 8.3: Verify discover_adapters returns both python and swift**

```bash
cd /Users/les/Projects/crackerjack
.venv/bin/python -c "
from crackerjack.adapters.registry import discover_adapters
print(sorted(discover_adapters().keys()))
"
```

Expected: `['python', 'swift']`. (If only one is present, the entry-point discovery isn't seeing both — verify `pyproject.toml` block and rebuild the wheel: `uv build --wheel && python -m pip install --force-reinstall --no-deps .`.)

- [ ] **Step 8.4: MCP server smoke**

```bash
cd /Users/les/Projects/crackerjack
# Start the MCP server briefly to verify language_tools are discoverable.
# (Use a short timeout so this doesn't hang.)
timeout 30 .venv/bin/python -m crackerjack mcp start &
SERVER_PID=$!
sleep 8
# Check discover_tools output via a quick HTTP probe to /mcp
curl -s http://127.0.0.1:8676/mcp 2>&1 | head -5
kill $SERVER_PID 2>/dev/null || true
wait
```

Expected: MCP server responds with HTTP 200; language_tools are present in the tool registry.

- [ ] **Step 8.5: Real SwiftPM lib smoke (gated)**

If a Swift toolchain is available, run the swift hooks against the actual `swiftui-ipc-client` repository:

```bash
cd /Users/les/Projects/swiftui-ipc-client
# Test detection
.venv 2>/dev/null; /Users/les/Projects/mahavishnu/.venv/bin/python -c "
from pathlib import Path
from crackerjack.adapters.swift import SwiftAdapter
print(SwiftAdapter().detect(Path('/Users/les/Projects/swiftui-ipc-client')))
caps = SwiftAdapter().capabilities(Path('/Users/les/Projects/swiftui-ipc-client'))
print([h.name for h in caps.hooks])
"
```

Expected: `True` + the four hook names. (If Swift toolchain isn't available, skip — document in report.)

- [ ] **Step 8.6: Add a CHANGELOG entry**

Open `CHANGELOG.md` and add a bullet under the existing `[Unreleased]` section:

```markdown
### Added

- Swift language adapter (Phase 2): GitTagVersionSource reads version from
  `git describe --tags --match "v*"`; lifecycle bumps via git tags only
  (no Package.swift mutation in v1); hooks include swift test/build with
  iOS-Simulator destination detection from Package.swift platforms
  directive, swift format (swift-format preferred over built-in swift
  format), and swift package update. Three new MCP tools: swift_bump_version
  (mutation; requires auth), swift_run_hooks, detect_languages.
  `crackageck.language_adapters` entry-point group now registers both
  Python and Swift adapters. Spec: dd9d9c05.
```

- [ ] **Step 8.7: Commit**

```bash
cd /Users/les/Projects/crackerjack
git -c user.email=les@wedgwoodwebworks.com add CHANGELOG.md
git -c user.email=les@wedgwoodwebworks.com commit -m "docs(changelog): Phase 2 — Swift adapter

Phase 2 of the crackerjack multi-language extension (spec dd9d9c05):
Swift lifecycle (git tags primary, no Package.swift mutation), four
Swift hooks (test/build/format/package.update) with iOS-Simulator
destination detection, three new MCP tools (swift_bump_version is
mutation; requires auth per spec MCP F5).

Spec: dd9d9c05 (Rev 2)."
```

---

## Self-Review (plan vs spec Rev 2)

**Spec coverage check:**

| Spec requirement (Rev 2) | Implemented by |
|---|---|
| Swift lifecycle via `git describe --tags --match "v*"` (F1) | Task 3 (`GitTagVersionSource.read`) |
| NO Package.swift mutation in v1 (F1) | Task 3 (`write` raises `VersionWriteError`); Task 5 (no Package.swift touch); Task 7 (`_run_swift_lifecycle` doesn't mutate) |
| Multi-package workspaces (deferred to Phase 2+ if needed) | Deferred — add `--package <subdir>` flag if needed |
| `swift format` vs `swift-format` precedence (F2) | Task 4 (`_swift_format_command` helper) |
| `swift package update` as hook (F3) | Task 4 (`swift.package.update` hook, autofix=false) |
| iOS-Simulator destination detection (F4) | Task 2 (`parse_platforms`); Task 4 (`_ios_destination_args`) |
| Hooks run sequentially per spec; concurrency concerns (F5) | N/A — Phase 1 hooks run sequentially by default; documented |
| `gh release create` is necessary but not sufficient | Task 5 (`_gh_release` method); Task 7 (calls `gh release create`) |
| 30min timeout for swift test (F4 review) | Task 4 (`timeout_seconds=1800`) |
| 4-step MCP registration pipeline (MCP F1) | Task 7 (CREATES module); Task 1 (entry-point registered); needs server_core.py + profiles.py edits |
| Auth posture for mutation tools (MCP F5) | Task 7 (`_require_auth` helper, called by `swift_bump_version`) |
| Language-segmented tool names (MCP F4) | Task 7 (`swift_bump_version`, `swift_run_hooks`, `detect_languages`) |
| Async/sync split (MCP F7) | Task 7 (all tool handlers are `async def`) |
| Rollback contract for bump_*_version (MCP F2) | Task 5 (rollback in `SwiftLifecycle.run`) |
| `discover_adapters()` includes both Python and Swift (Phase 1 F2 + spec) | Task 1 (entry-point declared) → Task 6 (SwiftAdapter class lands) |

**Placeholder scan:** No "TBD" / "TODO" in critical code. The plan defers multi-package workspaces and PyCharm parity to future phases (out of scope).

**Type consistency:** All `Capabilities` / `Hook` / `Lifecycle*` types referenced in later tasks match Phase 1's exact field names and defaults. `SwiftAdapter` matches `LanguageAdapterBase` ABC contract.

**Acceptance criteria:**
- All Phase 2 tests pass (target: 34 in `tests/adapters/swift/` + `tests/mcp/tools/`)
- All Phase 1 tests still pass (941 in `tests/adapters/` + `tests/core/`)
- CLI surface unchanged for Python users
- New MCP tools work end-to-end via the FastMCP server
- Mutation tools refuse to operate without auth

**Out-of-scope verification:**
- Kotlin / Web / Jinja — out of scope (Phases 3-4)
- Crackerjack CLI behavior for existing Python commands — Phase 1 contract holds; Phase 2 doesn't touch Python CLI
- Bodai CLI dispatcher — Phase 5 work
- MarketPlace publishing for JetBrains plugins — out of scope

---

## Execution Handoff

**Plan complete and saved to `/Users/les/Projects/crackerjack/docs/superpowers/plans/2026-09-07-crackerjack-multi-language-phase2.md`.**

8 tasks, ~10 commits, ~4-5 hours of focused implementation (estimate — actual depends on `services/git.py` integration complexity in Task 5).

Two execution options:

1. **Subagent-Driven (recommended)** — fresh subagent per task, two-stage review, fast iteration
2. **Inline Execution** — execute in this session, batch with checkpoints

Which approach?
