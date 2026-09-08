# Crackerjack Multi-Language Extension

> **Status:** Rev 2 — post-11-agent-review. All blocker + high findings from the review at `docs/superpowers/specs/reviews/2026-09-07-*.md` are incorporated.
> **Architecture:** Approach A — Language Adapters as first-class packages.
> **Phase 0 design; Phase 1 (foundation + Python refactor) is next.**

## Revision history

- **Rev 2 (this commit):** Post-review revisions.
  - **10 blocker findings fixed**: Swift lifecycle approach (git tags primary, no Package.swift mutation), Kotlin version-source regex (probe `pluginVersion`/`projectVersion`/`version` with `\b` anchors, verify via Gradle), Kotlin hook task-existence probe, Jinja formatter architecture (`Environment.lex()` not `parse()`, all 6 delimiter kwargs, semantics-preserving tier, explicit `jinja2` dep), API design (`@runtime_checkable` Protocol + `LanguageAdapterBase` ABC + `capabilities()` dataclass), MCP registration (4-step pipeline enumerated), MCP auth posture pinned.
  - **12+ high findings fixed**: Swift `swift-format` vs `swift format` precedence, `swift package update` as a hook, iOS-Simulator destination detection, MCP rollback contract on `bump_*_version`, MCP test fixture rebuild step, MCP async/sync split, Phase 1 budget/cache spec, hybrid two-path test plan, shared `FakeHookRunner`, Web detection false-positive guard, Phase 1 refactor scope naming, hybrid fallback single-interpretation, Jinja two-tier canonical policy, PyCharm parity is one-way fixed-point.
- **Rev 1:** Initial design (commit `16a8ecb7`).

## Goal

Extend crackerjack from a Python-only quality + lifecycle tool into a **multi-language, multi-domain** tool that covers the languages the Bodai ecosystem now uses: Swift, Kotlin/Gradle, and web assets (CSS/HTML/JS/TS, including Jinja templates with custom delimiters).

The objective is **same operational surface, more languages**: `crackerjack run`, `crackerjack run -p minor`, the hooks pipeline, and the MCP server (port 8676) work uniformly across language boundaries, with per-language adapters discovered via Python entry points.

## Motivation

The Bodai ecosystem now includes:

- **1 Swift-only repo** (`swiftui-ipc-client/`) — just shipped v0.1.1
- **1 Kotlin/Gradle JetBrains plugin** (`jinja2-custom-delimiters/`) — Les-authored
- **Multiple Python web stacks** (`fastblocks/`, `splashstand/`, `mdinject/`) with HTML/CSS/JS/TS assets
- **CSS/HTML/JS/TS** scattered across fastblocks and other Python web projects
- **Jinja templates with custom delimiters** (`[%`, `[[`, `[#`) in fastblocks

crackerjack today has no path to manage any of these. Quality hooks (`crackerjack run`) and lifecycle (`crackerjack run -p minor`) are Python-only. The MCP server exposes only Python tooling.

## Scope

### In scope (v0.81+)

**Swift** (Phase 2):
- **Lifecycle**: read version from `git describe --tags --match "v*"` → bump → commit → tag → push → `gh release create`. **No Package.swift mutation in v1.** SwiftSyntax-based in-file version reading is deferred to v2 (real use case needed).
- **Hooks**: `swift test`, `swift build`, `swift format` (built-in fallback), `swift package update`. All argv-list invocations (no shell). iOS-Simulator destination detected from `Package.swift` `platforms:` directive.
- **MCP tools**: `swift_bump_version` (mutation; auth required), `swift_run_hooks`, `detect_languages`.

**Kotlin/Gradle** (Phase 3):
- **Lifecycle**: read version via `GradlePropertiesVersionSource` (probe `pluginVersion`/`projectVersion`/`version` with `\b` anchors; fall back to `build.gradle.kts` scan; verify via `./gradlew properties`) → bump → commit → tag → push → `gh release create`. JetBrains Marketplace publishing is OUT of scope.
- **Hooks**: `kotlin.ktlint`, `kotlin.detekt`, `kotlin.test`. All use `./gradlew --no-daemon --no-configuration-cache`. Task-existence probe before invocation (skip-with-warning if absent).
- **MCP tools**: `kotlin_bump_version` (mutation; auth required), `kotlin_run_hooks`.

**Web (CSS/HTML/JS/TS)** (Phase 4):
- **Hooks only**: `stylelint` (CSS), `eslint` + `tsc --noEmit` (JS/TS), `html-validate` (HTML).
- **Jinja template formatter** (Python, ~250-400 LOC): handles custom delimiters `[%`, `[[`, `[#` etc. via `jinja2.Environment.lex()` (NOT `parse()`).
- **MCP tools**: `check_web_lint`, `format_jinja_templates`.

**Cross-cutting** (Phase 1):
- **Language auto-detection** from project marker files (with Web detection guarded against Python-project false-positives)
- **Adapter registry** via Python entry points (`crackerjack.language_adapters`)
- **Hybrid implementation** strategy: external CLI primary, Python fallback (single canonical interpretation; see Error Handling)
- **CLI + MCP mirror** for every new feature
- **4-step MCP tool registration pipeline** (see MCP Integration)

### Out of scope (deferred)

- Package.swift in-place version mutation (v1 uses git tags; v2 may add SwiftSyntax-based reads if needed)
- JetBrains Marketplace automated publishing (manual or future plan)
- Rust/Go support (trivial extension; defer)
- Per-project hook config (disable individual hooks via config; defer to v0.82)
- Watch mode (real-time hook running on file change)
- CSS/HTML/JS/TS lifecycle (no native version-bump workflow)
- Swift dependency upgrade via `swift package update` — actually IN scope (Phase 2 hook)
- Direct parity with PyCharm formatter output — IN scope is the **one-way fixed-point claim**: `crackerjack output → pycharm format → no changes`. See Canonical Jinja Whitespace Policy.

## Architecture — Approach A

### Package layout

```
crackerjack/
├── adapters/                              # NEW
│   ├── __init__.py
│   ├── base.py                            # Protocol + ABC + Hook / VersionSource / Lifecycle / Capabilities types
│   ├── registry.py                        # Entry-point discovery
│   ├── python/                            # REFACTOR existing logic into this shape
│   ├── swift/                             # NEW (Phase 2)
│   ├── kotlin/                            # NEW (Phase 3)
│   └── web/                               # NEW (Phase 4)
│       ├── css_hooks.py
│       ├── js_hooks.py
│       ├── html_hooks.py
│       └── jinja_formatter.py             # Python Jinja-aware formatter using Environment.lex()
└── core/
    └── language_detector.py               # NEW: auto-detect with Python-project guard for Web
```

### Entry-point registration

In `crackerjack/pyproject.toml`:

```toml
[project.entry-points."crackerjack.language_adapters"]
python = "crackerjack.adapters.python"
swift = "crackerjack.adapters.swift"
kotlin = "crackerjack.adapters.kotlin"
web = "crackerjack.adapters.web"
```

## Language Adapter Contract (Rev 2 — rewritten per API F1, F3, F6, F8, F9)

### Adapter Protocol

```python
import abc
from typing import ClassVar, Protocol, runtime_checkable

@runtime_checkable
class LanguageAdapter(Protocol):
    """Protocol for crackerjack language adapters.

    Subclass `LanguageAdapterBase` (recommended) for shared validation
    and registry integration, or implement this protocol directly.
    The @runtime_checkable decorator enables isinstance() validation
    for third-party adapter loaders.
    """

    name: ClassVar[str]  # kebab-case, used in CLI subcommands and MCP tool names

    def detect(self, project_root: Path) -> bool:
        """Return True if this adapter applies to the project."""

    def capabilities(self, project_root: Path) -> "Capabilities":
        """Single source of truth for what this adapter offers."""
```

### Capabilities (per API F3)

Replaces the four-method Protocol decomposition (`detect()` / `version_source()` / `hooks()` / `lifecycle()`). One method, one return value, no `None`-vs-empty ambiguity:

```python
@dataclass(frozen=True)
class Capabilities:
    version_source: VersionSource | None = None
    hooks: tuple[Hook, ...] = ()          # Empty tuple (not list) if no hooks
    has_lifecycle: bool = False            # Explicit flag; no Optional confusion

    @property
    def has_version(self) -> bool:
        return self.version_source is not None
```

`version_source = None` is explicit "no version management"; `has_lifecycle = False` is explicit "no bump/tag/push".

### LanguageAdapterBase (per API F2)

```python
class LanguageAdapterBase(abc.ABC):
    """Recommended base class for third-party LanguageAdapter authors.

    Subclassing is preferred over raw Protocol implementation for
    non-trivial adapters. Provides shared name validation, capability
    folding, and registry integration.
    """

    name: ClassVar[str]  # Subclass must set

    @abc.abstractmethod
    def detect(self, project_root: Path) -> bool: ...

    @abc.abstractmethod
    def capabilities(self, project_root: Path) -> Capabilities: ...
```

### Hook (per API F6)

Only `name` and `cli_command` required; all other fields default:

```python
@dataclass(frozen=True)
class Hook:
    name: str
    cli_command: tuple[str, ...]                # argv list, no shell
    fallback: Callable | None = None            # Python fallback if CLI missing
    timeout_seconds: int = 600                  # 10-min default
    autofix: bool = False                       # Manual review by default
    cli_required: bool = True                   # If True and CLI missing, fail
```

### VersionSource (per API F8)

```python
class VersionSourceError(Exception):
    """Base class for version source errors."""

class VersionNotFoundError(VersionSourceError):
    """The version could not be located in the source file."""

class VersionWriteError(VersionSourceError):
    """The version was successfully parsed but could not be written back."""


class VersionSource(Protocol):
    def read(self) -> str:
        """Read the current version. Raise VersionNotFoundError if not found."""

    def write(self, new_version: str) -> None:
        """Write a new version. Raise VersionWriteError on failure.

        Implementations MUST verify by reading back after writing.
        """
```

### Lifecycle (per API F9)

Single method, not five decomposed ones. Rollback handled internally:

```python
@dataclass(frozen=True)
class LifecycleOptions:
    level: Literal["major", "minor", "patch"]
    commit: bool = True
    tag: bool = True
    push: bool = True
    release: bool = False
    dry_run: bool = False


@dataclass(frozen=True)
class LifecycleResult:
    new_version: str
    commit_sha: str | None
    tag_name: str | None
    release_url: str | None
    skipped_steps: tuple[str, ...] = ()


class Lifecycle(Protocol):
    def run(self, options: LifecycleOptions) -> LifecycleResult:
        """Execute bump+commit+tag+push+release with rollback on failure.

        On any failure mid-flow: delete tag, reset commit, raise.
        Caller receives exception with context; can retry with
        dry_run=True to test.
        """
```

## Per-adapter Swift (Rev 2 — rewritten per Swift F1, F2, F3, F4)

**Detect**: `Package.swift` present at project root.

**VersionSource** (`version_source.py`):

```python
class GitTagVersionSource:
    """Primary version source: git tags.

    Uses `git describe --tags --abbrev=0 --match "v*"` and strips
    the `v` prefix. If no tag matches, raises VersionNotFoundError.

    Write path: NO-OP for v1. Tags are the version; Package.swift
    is not mutated. (Per Swift F1 — regex on Package.swift would
    silently corrupt dependency ranges.)
    """

    def read(self) -> str:
        result = subprocess.run(
            ["git", "describe", "--tags", "--abbrev=0", "--match", "v*"],
            cwd=self._project_root,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise VersionNotFoundError("No v*-prefixed tags found")
        return result.stdout.strip().lstrip("v")

    def write(self, new_version: str) -> None:
        raise NotImplementedError(
            "v1 policy: Package.swift is not mutated; use git tag instead"
        )
```

SwiftSyntax-based in-file version reading is **deferred to v2** until a real use case appears. When needed, use SwiftSyntax's `PackageDescription` AST (not regex).

**Multi-package workspaces** (Swift 5.9+): `crackerjack run -p minor --package <subdir>` flag disambiguates which package to version.

**Hooks** (`hooks.py`):

- `swift.test` → `swift test`. Parses `Package.swift` `platforms:` directive; if iOS-only or includes iOS, adds `-destination 'generic/platform=iOS Simulator'`. (Per Swift F4.)
- `swift.build` → `swift build`. Same destination logic.
- `swift.format` → if `swift-format` (third-party) is installed, invoke that and read `.swift-format` config; else fall back to `swift format` (built-in) with warning that formatting may diverge from project's CI. (Per Swift F2.)
- `swift.package.update` → `swift package update`. `autofix=false`. Reports `Package.resolved` diff in output. (Per Swift F3.)

No Python fallback for any of these. CLI required.

**Lifecycle** (`lifecycle.py`): uses `Lifecycle.run(LifecycleOptions)` with rollback per the contract.

## Per-adapter Kotlin (Rev 2 — rewritten per Kotlin F1, F2)

**Detect**: `build.gradle.kts` or `build.gradle` present at project root.

**VersionSource** (`version_source.py`):

```python
class GradlePropertiesVersionSource:
    """Probe gradle.properties for version, with multiple key conventions.

    Order (anchored with \b): pluginVersion, projectVersion, version.
    Falls back to build.gradle.kts scan. Always verifies via Gradle
    (Gradle is source of truth).
    """

    _PROBE_KEYS = ("pluginVersion", "projectVersion", "version")

    def read(self) -> str:
        # 1. Probe gradle.properties
        properties_path = self._project_root / "gradle.properties"
        if properties_path.exists():
            content = properties_path.read_text()
            for key in self._PROBE_KEYS:
                m = re.search(rf"\b{re.escape(key)}\s*=\s*(\S+?)[,\s]*$", content, re.MULTILINE)
                if m:
                    return m.group(1)
        # 2. Fall back to build.gradle.kts scan
        for gradle_file in ("build.gradle.kts", "build.gradle"):
            path = self._project_root / gradle_file
            if path.exists():
                content = path.read_text()
                m = re.search(r'^\s*version\s*=\s*"([^"]+)"', content, re.MULTILINE)
                if m:
                    return m.group(1)
        # 3. Final fallback: Gradle as source of truth
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
```

**Hooks** (`hooks.py`):

```python
class GradleTaskProbe:
    """Detect whether a Gradle task exists before invoking it."""

    def has_task(self, task_name: str) -> bool:
        result = subprocess.run(
            ["./gradlew", "tasks", "--all", "-q", "--no-daemon", "--no-configuration-cache"],
            cwd=self._project_root, capture_output=True, text=True,
        )
        return bool(re.search(rf"^{re.escape(task_name)}\s+", result.stdout, re.MULTILINE))
```

- `kotlin.ktlint` → probe for `ktlintCheck` task (and `ktlintFormat` for autofix). If absent, skip-with-warning.
- `kotlin.detekt` → probe for `detekt`. Same.
- `kotlin.test` → `./gradlew test`. Always present if Kotlin plugin applied.

All Gradle invocations pass `--no-daemon --no-configuration-cache` for CI subprocess reliability.

**Lifecycle**: same `Lifecycle.run(LifecycleOptions)` pattern as Swift.

## Per-adapter Web (Rev 2 — Jinja formatter rewritten per Jinja F1, F2, F3, F7, F10, F11)

**Hooks**: `stylelint` (CSS), `eslint` + `tsc --noEmit` (JS/TS), `html-validate` (HTML). Hybrid pattern (CLI primary, Python fallback). Commands run via `npx` unless `package.json` pins them.

**Web detection guard** (per Writing F3): the Web adapter **does not fire** on Python projects by default. Detection requires `package.json` at project root OR explicit `[tool.crackerjack.web] enabled = true` in `pyproject.toml`. Without this, every Django/Sphinx/MkDocs Python project would falsely trigger Web hooks.

### Jinja formatter (massive rewrite)

**Why `Environment.lex()` not `Environment.parse()`** (per Jinja F1):

`Environment.parse()` returns an AST with **no unparser**. The AST silently drops comments, `-`/`+` whitespace-control markers, and `{% raw %}` boundaries. A formatter built on `parse()` would delete every comment in every template.

`Environment.lex()` returns a stream of `(lineno, token_type, value)` tuples that preserves all of that. Caveats:

- `lex()` strips the trailing newline if the source ends without one — restore from raw input.
- `lex()` normalizes CRLF → LF — preserve CRLF flag from raw input if needed.
- `lex()` tolerates unknown tags (extension tags like `{% trans %}`, `{% loopcontrols %}`) — `parse()` hard-fails on these (per Jinja F7). fastblocks loads `i18n` + `loopcontrols` extensions at runtime; `lex()` survives even when extensions aren't loaded.

**Delimiter config** (per Jinja F2):

`Environment(block_start_string='[%')` raises `TemplateSyntaxError: unexpected ']'`. The spec previously specified 3 delimiter kwargs; **all 6 are required**:

```python
env = jinja2.Environment(
    block_start_string=config["block_start"],       # e.g., "[%"
    block_end_string=config["block_end"],           # e.g., "%]"
    variable_start_string=config["variable_start"], # e.g., "[["
    variable_end_string=config["variable_end"],     # e.g., "]]"
    comment_start_string=config["comment_start"],   # e.g., "[#"
    comment_end_string=config["comment_end"],       # e.g., "#]"
)
```

fastblocks sets all 6 in `fastblocks/adapters/templates/jinja2.py:803-808`. Source of truth.

**Two-tier canonical policy** (per Jinja F3):

Rules 2, 4, and 5 of the original policy **change rendered output** because inter-tag whitespace is program output in Jinja (`{% if a %}A{% endif %}{% if b %}B{% endif %}` renders `AB`; inserting Rule 2's blank line makes it `A\n\nB`). Rules split by semantics-preserving:

**Tier 1 — semantics-preserving (always on):**
1. Trailing newline at EOF
2. No trailing whitespace on lines
3. Preserve existing whitespace stripping (`{%-` / `-%}` / `{{-` / `-}}`)

**Tier 2 — output-affecting (opt-in via `[tool.crackerjack.jinja] normalize = true`):**
4. "One space inside delimiters"
5. Blank line between block-level tags at the top level
6. Inline `{{ var }}` may remain inline

**Round-trip invariant** (per Testing F9 + Jinja F1): `format_lex(format_lex(x)) == format_lex(x)`. Test asserts this for every fixture, with **golden-master expected output** (not just "idempotence" which is weaker than it looks).

**PyCharm parity** (per Jinja F10):

PyCharm parity as "identical output" is **unachievable**. `jinja2-custom-delimiters` (Kotlin/Gradle JetBrains plugin) does **not** have its own formatter — it converts delimiters and delegates to **PyCharm Professional's** built-in Jinja2 formatter, behind a paid license gate (per `plugin.xml:14-19`).

Replace the bidirectional parity claim with a **one-way fixed-point claim**: `pycharm_format(crackerjack_format(x)) == crackerjack_format(x)`. Testable, headless, requires only a PyCharm CLI invocation script.

**Phase 4 deliverable**: shared `jinja-test-fixtures/` Bodai sibling package with 30+ input templates and golden-master expected outputs. Both `crackerjack format` and PyCharm (via reproducible script) tested against the same corpus.

**Explicit dependency** (per Jinja F11):

```toml
# pyproject.toml
"jinja2>=3.1.6",
```

`jinja2` is currently NOT declared — it appears in `.venv` only via `fastapi[standard]`, `nbconvert`, `transformers`. Any of those could be removed and silently break the Jinja formatter. Must be a direct dep.

## MCP Integration (Rev 2 — rewritten per MCP F1, F2, F3, F5, F7)

### 4-step registration pipeline (CRITICAL — per MCP F1)

For each new tool group, **all four steps** must be done. Skipping any step silently produces invisible tools.

1. **Create** `crackerjack/mcp/tools/<group>_tools.py` exporting `register_<group>_tools(mcp_app: FastMCP) -> None`:

   ```python
   # crackerjack/mcp/tools/language_tools.py
   from fastmcp import FastMCP

   def register_language_tools(mcp_app: FastMCP) -> None:
       @mcp_app.tool()
       async def swift_bump_version(...) -> dict: ...

       @mcp_app.tool()
       async def kotlin_format_jinja(...) -> dict: ...
   ```

2. **Register** in `_build_registration_map()` in `crackerjack/mcp/server_core.py` (line 204-224):

   ```python
   from crackerjack.mcp.tools import (
       language_tools,  # NEW
   )

   def _build_registration_map() -> dict[str, Callable]:
       return {
           "language_tools": language_tools.register_language_tools,  # NEW
           # ... existing entries ...
       }
   ```

3. **Assign tier** in `crackerjack/mcp/tools/profiles.py` (line 79-115):

   ```python
   FULL_REGISTRATIONS = {
       "language_tools",  # NEW
       # ... existing entries ...
   }
   STANDARD_REGISTRATIONS = { /* language_tools NOT here */ }
   MINIMAL_REGISTRATIONS = { /* language_tools NOT here */ }
   ```

   Reasoning: mutation tools belong in `FULL_REGISTRATIONS` only (more conservative default).

4. Each tool wrapper uses `@mcp_app.tool()` decorator on a nested `async def`. No top-level tool functions.

### Auth posture (per MCP F5)

Mutation tools require `MAHAVISHNU_JWT_SECRET` + `MAHAVISHNU_AUTH_ENABLED=true`. Read tools follow the existing pattern (no auth in v1). Bodai auth-standardization (`project_bodai_auth_standardization.md`) covers the cross-cutting fix; until that's done, mutation tools must check for env vars at startup and refuse to operate if absent.

```python
def _require_auth() -> None:
    if not os.environ.get("MAHAVISHNU_AUTH_ENABLED") == "true":
        raise PermissionError("MAHAVISHNU_AUTH_ENABLED=true required for mutation tools")
    if not os.environ.get("MAHAVISHNU_JWT_SECRET"):
        raise PermissionError("MAHAVISHNU_JWT_SECRET unset")
```

### Rollback contract (per MCP F2)

`Lifecycle.run()` returns `LifecycleResult` with explicit `skipped_steps`. On failure mid-flow, rollback is best-effort: delete tag, reset commit, re-raise. The 2026-08-24 git incident pattern (`crackerjack/services/git.py:63-65, 639`) is acknowledged; this design is the fix.

```python
def run(self, options: LifecycleOptions) -> LifecycleResult:
    commit_sha = None
    tag_name = None
    try:
        commit_sha = self._commit(...)
        tag_name = f"v{new}"
        self._tag(tag_name)
        self._push(commit_sha, tag_name)
        if options.release:
            release_url = self._gh_release(tag_name)
        return LifecycleResult(new, commit_sha, tag_name, release_url)
    except Exception:
        if tag_name:
            self._delete_tag(tag_name)
        if commit_sha:
            self._reset(commit_sha)
        raise
```

### Async/sync split (per MCP F7)

All MCP tool handlers are `async def` (per project CLAUDE.md "All I/O is async"). The Jinja formatter runs inside `asyncio.to_thread` so it doesn't block the event loop on multi-file passes:

```python
@mcp_app.tool()
async def format_jinja_templates(paths: list[str]) -> dict:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _format_sync, paths)
```

### Tool naming (per MCP F4)

Language-segmented to avoid Bodai umbrella collisions:
- `swift_bump_version` (not `bump_swift_version`)
- `kotlin_run_hooks` (not `run_kotlin_hooks`)
- `format_jinja_templates` (Jinja-specific)
- `detect_languages` (cross-cutting, lives in Phase 1)

### Test fixture rebuild (per MCP F3)

`_tool_registry_keys.json` (43 tools pinned) and `_tool_groups_mapping.json` will break when 7 new tools land. Add a fixture-rebuild step to Phase 5 (polish) or run as a pre-Phase-2 task:

```bash
python -m crackerjack.tools.refresh_tool_registry_fixtures
```

## Data Flow (Rev 2 — rollback semantics)

### `crackerjack run -p minor` on `swiftui-ipc-client` (iOS-only SwiftPM project)

1. CLI parses args: `-p minor`, project root
2. `core/language_detector.detect(project_root)` returns `[SwiftAdapter()]`
3. `SwiftAdapter.capabilities(project_root)` returns `Capabilities(version_source=GitTagVersionSource, hooks=(swift.test, swift.build, swift.format, swift.package.update), has_lifecycle=True)`
4. Lifecycle phase: `SwiftLifecycle.run(LifecycleOptions(level="minor", release=True))`:
   - `version_source.read()` → `"0.1.1"` (from `git describe --tags --match "v*"`)
   - Bump to `"0.2.0"`
   - (No Package.swift mutation in v1)
   - `git add . && git commit -m "bump: swift v0.1.1 → v0.2.0"`
   - `git tag -a v0.2.0 -m "..."`
   - `git push origin main --tags`
   - `gh release create v0.2.0 --generate-notes`
   - On any failure: rollback (delete tag, reset commit via `git reset --hard HEAD~1`)
   - Return `LifecycleResult(new_version="0.2.0", commit_sha="abc123", tag_name="v0.2.0", release_url="https://...")`
5. Hooks phase: `swift.test`, `swift.build`, `swift.format`, `swift.package.update`
   - `swift.test` detects iOS-only platforms; adds `-destination 'generic/platform=iOS Simulator'`
   - `swift.format` detects no `.swift-format` config; falls back to `swift format` (built-in) with warning
6. Report: lifecycle + hooks results

### `crackerjack run` on `fastblocks` (Python + Web, no iOS, no Kotlin)

1. Detects Python (pyproject.toml) — but NOT Web (no `package.json`, no `[tool.crackerjack.web] enabled = true`)
2. Runs Python hooks (existing ruff, mypy, ty, etc.)
3. Lifecycle runs only for Python (Web has no lifecycle)
4. **No Web hooks fire** — correct behavior (fastblocks's Jinja templates aren't reformatted by crackerjack unless user opts in)

### `crackerjack web jinja format src/templates/` (new subcommand)

1. New subcommand under `web` group
2. Discovers Jinja files matching the path arg
3. Loads delimiter config from `pyproject.toml` `[tool.crackerjack.jinja]` block (all 6 delimiter keys)
4. Calls `JinjaCanonicalFormatter.format(source)` per file (uses `lex()`)
5. Tier 1 changes (always on): trailing newline, no trailing whitespace, preserve stripping
6. Tier 2 changes (opt-in via `normalize = true`): spacing, blank lines, inline matters
7. Reports per-file diff and exit code
8. Round-trip idempotence test asserted for every file

## Error Handling (Rev 2 — single hybrid-fallback interpretation)

| Failure mode | Behavior |
|---|---|
| Lifecycle partial failure | Best-effort rollback (delete tag, reset commit); return `LifecycleResult` with `skipped_steps`; raise |
| CLI not installed (hook with `fallback`) | Invoke Python fallback |
| CLI not installed (hook with `cli_required=True`, no fallback) | Fail with installation instructions |
| Python fallback also missing/fails | Fail with combined installation instructions |
| `VersionSource.read()` returns empty | Raise `VersionNotFoundError`; CLI reports file:line and exits non-zero |
| `VersionSource.write()` fails to read back | Raise `VersionWriteError`; rollback any partial state |
| MCP auth missing for mutation tool | Fail with clear message: "MAHAVISHNU_JWT_SECRET unset; mutation tools require auth" |
| Hook subprocess times out | Fail hook; report timeout duration; allow retry with `--hook-timeout-multiplier=2` |
| `dry_run=True` on lifecycle | All mutations skipped; commit/tag/push return None; result includes `("dry_run",)` in `skipped_steps` |

The "hybrid fallback" rule has **one** canonical interpretation:

> When a hook has `fallback` set AND the CLI is missing (`shutil.which(cmd) is None`), invoke `fallback()`. When fallback also raises or returns False, fail the hook with installation instructions for the CLI.

## Testing Strategy (Rev 2)

### Phase 1 budget and cache (per Testing F7)

```yaml
# pyproject.toml [tool.crackerjack.testing]
phase_1_pr_smoke_minutes: 5
phase_1_full_suite_minutes: 30
phase_1_marker_split:
  pr_check: ["-m", "smoke or not slow"]
  nightly: []
  weekly_full: []
```

CI uses `-n auto` for parallelism. Cache `~/.cache/uv`, `.venv`, and per-test `.build/` dirs.

### Hybrid two-path test plan (per Testing F3)

For every hook with a `fallback`:

```python
def test_swift_test_uses_cli_when_present(monkeypatch, fixture):
    monkeypatch.setattr(shutil, "which", lambda cmd: "/usr/bin/swift" if cmd == "swift" else None)
    result = fixture.run_hook("swift.test")
    assert result.invoked_via == "cli"


def test_swift_test_falls_back_to_python_when_cli_missing(monkeypatch, fixture):
    monkeypatch.setattr(shutil, "which", lambda cmd: None)
    result = fixture.run_hook("swift.test")
    assert result.invoked_via == "python_fallback"
```

This pair is **mandatory** for every hybrid hook. `monkeypatch.setattr(shutil, "which", ...)` is the mandated pattern.

### FakeHookRunner abstraction (per Testing F5)

Shared mock subprocess for 20+ hook wrappers. One abstraction, not per-hook fixtures. Saves significant maintenance burden.

### Cross-language fixture split (per Testing F8)

- `tests/fixtures/swift-lib/` — vanilla SwiftPM library
- `tests/fixtures/swift-ios-app/` — iOS-only package (destination handling)
- `tests/fixtures/gradle-plugin/` — IntelliJ Platform plugin (the Kotlin test fixture, `jinja2-custom-delimiters`)
- `tests/fixtures/gradle-vanilla/` — vanilla Kotlin lib
- `tests/fixtures/web-only/` — pure CSS/HTML project (no Python)
- `tests/fixtures/mixed/` — fastblocks-like (Python + Web)
- `tests/fixtures/real-repo-weekly-smoke/` — actual `swiftui-ipc-client`, `jinja2-custom-delimiters`, `fastblocks` (run weekly, not every PR)

### Jinja corpus + golden-master (per Testing F9)

`jinja2-test-fixtures/` Bodai sibling package (separate repo). 30+ input templates with golden-master expected outputs. Both `crackerjack format` and PyCharm (via reproducible script) tested against the same corpus.

Round-trip invariant: `format_lex(format_lex(x)) == format_lex(x)`. Test asserts with golden-master expected output for every fixture.

### PyCharm parity = Phase 4 deliverable (per Testing F4)

PyCharm CLI test framework (when available) OR a documented reproducible script. The "documentation note" fallback is **removed** — this is now a Phase 4 acceptance criterion.

### mcp-common testing helpers verification (per Testing F2)

Before Phase 2 implementation, verify `mcp-common` exposes the testing helpers the spec assumes. If not, the MCP test strategy needs to either (a) use a different helper library or (b) write minimal test utilities. **This is a Phase 2 scope-creep risk and must be resolved before Phase 2 begins.**

## Migration Plan (Rev 2)

### Phase 1 — Foundation (no behavior change)

- Add `adapters/base.py`, `adapters/registry.py`, `core/language_detector.py`
- Refactor existing Python logic into `adapters/python/` (preserves all behavior)
- Use `@runtime_checkable` Protocol + `LanguageAdapterBase` ABC (per API F1)
- Replace 4-method Protocol with `capabilities()` dataclass (per API F3)
- Add `Lifecycle` + `LifecycleOptions` + `LifecycleResult` types (per API F9)
- Add `VersionSourceError` exception hierarchy (per API F8)
- Enumerate MCP 4-step registration pipeline (foundation work; no new tools yet)
- Verify: full crackerjack test suite passes within budget (5min PR smoke, 30min nightly) (per Testing F7)
- **Name the modules being moved** (per Writing F1): `crackerjack/cli/`, `crackerjack/managers/`, `crackerjack/services/` (lifecycle-relevant subsets) refactor into `adapters/python/` first; CLI-facing surface unchanged.
- No new commands, no new behavior, just internal reorg

### Phase 2 — Swift

- Implement Swift adapter
- GitTagVersionSource as primary; Package.swift mutation DEFERRED to v2 (per Swift F1)
- iOS-Simulator destination detection (per Swift F4)
- `swift-format` (third-party) preferred over `swift format` (built-in); read `.swift-format` config (per Swift F2)
- `swift.package.update` hook (per Swift F3)
- `Lifecycle.run()` with rollback
- Register MCP tools via 4-step pipeline (per MCP F1)
- `_tool_registry_keys.json` rebuild step (per MCP F3)
- Auth posture for `swift_bump_version` (per MCP F5)
- **Pre-Phase-2 gate**: verify `mcp-common` testing helpers exist (per Testing F2)
- Test on `swiftui-ipc-client` (iOS-only) and `mdinject` Swift app

### Phase 3 — Kotlin/Gradle

- Implement Kotlin adapter
- `GradlePropertiesVersionSource` with `pluginVersion`/`projectVersion`/`version` probe order + `\b` anchors (per Kotlin F1)
- Verify via `./gradlew properties` (Gradle is source of truth)
- `GradleTaskProbe` for task-existence (per Kotlin F2)
- `--no-daemon --no-configuration-cache` for CI invocations
- Test on `jinja2-custom-delimiters` (the named Phase 3 fixture)
- Register MCP tools

### Phase 4 — Web + Jinja

- Implement Web adapter (stylelint, eslint, tsc, html-validate)
- Web detection guard against Python projects (per Writing F3): require `package.json` OR `[tool.crackerjack.web] enabled = true`
- Jinja formatter rewrite using `Environment.lex()` (per Jinja F1, F2, F3, F7)
- All 6 delimiter kwargs configured (per Jinja F2)
- Two-tier canonical policy: semantics-preserving always on, output-affecting opt-in (per Jinja F3)
- PyCharm parity = one-way fixed-point claim, not identical output (per Jinja F10)
- Explicit `jinja2>=3.1.6` dependency (per Jinja F11)
- Phase 4 deliverable: reproducible PyCharm parity script + shared `jinja-test-fixtures/` Bodai package (per Testing F4)
- Test on `fastblocks`, `splashstand`
- Coordinate with `jinja2-custom-delimiters` (same author) on canonical policy + corpus

### Phase 5 — Polish

- Update `BODAI_REPO_REGISTRY.md` with `language:` column
- Update crackerjack README + docs
- Rebuild `_tool_registry_keys.json` and `_tool_groups_mapping.json` (per MCP F3)
- Bodai umbrella integration: new language tools added to `bodai` CLI dispatch table
- Cross-package Jinja parity test corpus published

## Open Questions (Rev 2)

### Resolved by review

- ~~Web hooks scope~~ — linter + Jinja-aware auto-format
- ~~Jinja formatter scope~~ — bundled in `crackerjack.adapters.web`
- ~~MCP tool surface~~ — CLI + MCP mirror
- ~~Package.swift mutation in v1~~ — NO (use git tags only)
- ~~Python-like subprocess security~~ — argv list, no shell
- ~~Swift package update in scope~~ — yes, as a hook

### Still open

- PyCharm CLI test framework availability for parity verification (PyCharm Pro license required)
- JetBrains Marketplace publishing for Kotlin plugins (out of scope, manual or future plan)
- Watch mode (real-time hook running)
- Per-project hook disable config (`[tool.crackerjack.disabled_hooks]`)
- Rust/Go support (defer until a Bodai project needs it)
- PyCharm parity script location (Bodai sibling package or vendored?)

## Risks (Rev 2)

| Risk | Mitigation |
|---|---|
| Phase 1 refactor breaks 11K+ tests | PR smoke (`-m "smoke or not slow"`, 5min budget); full nightly (30min); cache strategy |
| Hybrid pattern test surface (20 wrappers) | Shared `FakeHookRunner` abstraction (per Testing F5) |
| PyCharm parity disagreement with `jinja2-custom-delimiters` | One-way fixed-point claim; both packages converge via shared corpus |
| Swift version source ambiguity | Git tags primary; in-file version DEFERRED to v2 (with SwiftSyntax when needed) |
| Kotlin `pluginVersion` drift | Always verify via `./gradlew properties` (Gradle is source of truth) |
| Web detection false-positives on Python projects | Require `package.json` OR explicit `[tool.crackerjack.web] enabled = true` (per Writing F3) |
| MCP tool invisibility | 4-step pipeline enumerated + fixture rebuild step (per MCP F1, F3) |
| Hybrid fallback interpretation drift | Single canonical definition (per Writing F2) |
| Auth gap on mutation MCP tools | Env-var check at startup; refuse operation if absent (per MCP F5) |
| `jinja2` not a declared dep | Add to `pyproject.toml` (per Jinja F11) |
| `mcp-common` testing helpers missing | Verify pre-Phase-2 (per Testing F2); fall back to minimal test utilities |

## Compatibility Notes

- Python 3.14 minimum (crackerjack already requires this)
- `jinja2>=3.1.6` (NEW: explicit dep)
- For Swift/Kotlin version sources: no TOML parsing; regex with `\b` anchors + read-back verification + Gradle/git as source of truth
- MCP tools: 4-step registration pipeline (NOT just `register under existing crackerjack.mcp.tools`)
- Bodai umbrella entry-point (`bodai.apps`) already exists; new language tools added to dispatch table

## See also

- 11 review files at `docs/superpowers/specs/reviews/2026-09-07-{lens}.md`
- Existing crackerjack specs in `docs/superpowers/specs/` — refactor patterns
- `BODAI_REPO_REGISTRY.md` — language column addition
- `jinja2-custom-delimiters` plugin.xml — delimiter conversion contract
- memory `multi-agent-review-catches-blind-spots.md` — pattern for spec review
