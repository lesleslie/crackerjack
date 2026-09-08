# Crackerjack Multi-Language Extension

> **Status:** Draft for user review. Phase 0 of the v0.81+ roadmap.
> **Architecture:** Approach A — Language Adapters as first-class packages.
> **Spec owner:** TBD (crackerjack maintainers).

## Goal

Extend crackerjack from a Python-only quality + lifecycle tool into a
**multi-language, multi-domain** tool that covers the languages the Bodai
ecosystem now uses: Swift, Kotlin/Gradle, and web assets (CSS/HTML/JS/TS,
including Jinja templates with custom delimiters).

The objective is **same operational surface, more languages**: `crackerjack
run`, `crackerjack run -p minor`, the hooks pipeline, and the MCP server
(port 8676) should all work uniformly across language boundaries, with
per-language adapters discovered via Python entry points.

## Motivation

The Bodai ecosystem now includes:

- **1 Swift-only repo** (`swiftui-ipc-client/`) — just shipped v0.1.1
- **1 Kotlin/Gradle JetBrains plugin** (`jinja2-custom-delimiters/`) — Les-authored
- **Multiple Python web stacks** (`fastblocks/`, `splashstand/`, `mdinject/`) with HTML/CSS/JS/TS assets
- **CSS/HTML/JS/TS** scattered across fastblocks and other Python web projects
- **Jinja templates with custom delimiters** (`[%`, `[[`, `[#`) in fastblocks

crackerjack today has no path to manage any of these. Quality hooks
(`crackerjack run`) and lifecycle (`crackerjack run -p minor`) are
Python-only. The MCP server exposes only Python tooling.

## Scope

### In scope (v0.81+)

**Swift** (Phase 2):
- **Lifecycle**: read version from `Package.swift` → bump → git commit → tag → push → `gh release create`
- **Hooks**: `swift test`, `swift build`, `swift format`
- **MCP tools**: `run_swift_hooks`, `bump_swift_version`, `detect_languages`

**Kotlin/Gradle** (Phase 3):
- **Lifecycle**: read version from `gradle.properties` (idiomatic) → bump → commit → tag → push → `gh release create`. JetBrains Marketplace upload is OUT of scope.
- **Hooks**: `ktlint`, `detekt`, `gradle test` (via `./gradlew`)
- **MCP tools**: `run_kotlin_hooks`, `bump_kotlin_version`

**Web (CSS/HTML/JS/TS)** (Phase 4):
- **Hooks only**: `stylelint` (CSS), `eslint` + `tsc --noEmit` (JS/TS), `html-validate` (HTML)
- **Jinja template formatter** (Python, fastblocks-aware): handles custom delimiters `[%`, `[[`, `[#` etc.
- **MCP tools**: `check_web_lint`, `format_jinja_templates`

**Cross-cutting** (Phase 1):
- **Language auto-detection** from project marker files
- **Adapter registry** via Python entry points (`crackerjack.language_adapters`)
- **Hybrid implementation** strategy: external CLI primary, Python fallback
- **CLI + MCP mirror** for every new feature

### Out of scope (deferred)

- Kotlin/JetBrains Marketplace automated publishing (manual or future plan)
- Rust/Go support (trivial extension; defer)
- Per-project hook config (disable individual hooks via config; defer)
- Watch mode (real-time hook running on file change)
- CSS/HTML/JS/TS lifecycle (no native version-bump workflow; web assets are part of consuming projects' lifecycles)
- Swift dependency upgrade (`swift package update`) — separate plan
- IntelliJ-side formatter integration via XML config export — Phase 4 follow-up

## Architecture — Approach A: Language Adapters

### Package layout

```
crackerjack/
├── adapters/                              # NEW
│   ├── __init__.py
│   ├── base.py                            # LanguageAdapter ABC + Hook / VersionSource / Lifecycle types
│   ├── registry.py                        # Entry-point discovery
│   ├── python/                            # REFACTOR existing logic into this shape
│   │   ├── __init__.py
│   │   ├── version_source.py              # reads from pyproject.toml [project] version
│   │   ├── hooks.py                       # ruff, mypy, ty, zuban, complexipy, creosote, bandit, refurb
│   │   └── lifecycle.py                   # bump → commit → tag → push → twine publish
│   ├── swift/                             # NEW (Phase 2)
│   │   ├── __init__.py
│   │   ├── version_source.py              # reads Package.swift version
│   │   ├── hooks.py                       # swift test / build / format
│   │   └── lifecycle.py                   # bump → commit → tag → push → gh release
│   ├── kotlin/                            # NEW (Phase 3)
│   │   ├── __init__.py
│   │   ├── version_source.py              # reads gradle.properties version
│   │   ├── hooks.py                       # ktlint / detekt / gradle test
│   │   └── lifecycle.py                   # bump → commit → tag → push → gh release
│   └── web/                               # NEW (Phase 4)
│       ├── __init__.py
│       ├── css_hooks.py                   # stylelint
│       ├── js_hooks.py                    # eslint, tsc
│       ├── html_hooks.py                  # html-validate
│       └── jinja_formatter.py             # Python Jinja-aware formatter (~200-400 LOC)
└── core/
    └── language_detector.py               # NEW: auto-detect from project files
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

Third-party language adapters (e.g., a future `crackerjack-rust-adapter`)
register themselves by adding the same entry point in their own
`pyproject.toml`.

### LanguageAdapter contract

```python
from pathlib import Path
from typing import Protocol

class LanguageAdapter(Protocol):
    name: str

    def detect(self, project_root: Path) -> bool:
        """Return True if this adapter applies to the project."""

    def version_source(self, project_root: Path) -> VersionSource | None:
        """Where to read/write version. None if no lifecycle support."""

    def hooks(self) -> list[Hook]:
        """Available hooks for this language."""

    def lifecycle(self, project_root: Path) -> Lifecycle | None:
        """Lifecycle steps (bump, tag, push, release). None if no lifecycle."""
```

`Hook`:
```python
@dataclass(frozen=True)
class Hook:
    name: str               # e.g., "swift.test"
    cli_command: tuple[str, ...]
    fallback: Callable | None  # Python fallback if CLI missing
    timeout_seconds: int
    autofix: bool           # Whether fast_hooks should auto-fix
```

`VersionSource`:
```python
class VersionSource(Protocol):
    def read(self) -> str: ...
    def write(self, new_version: str) -> None: ...
```

## Per-adapter responsibilities

### Swift adapter (`crackerjack/adapters/swift/`)

**Detect**: presence of `Package.swift` at project root.

**VersionSource** (`version_source.py`):
- `read()`: parse `Package.swift`, extract the `version:` field from `.product(...)` if present (some SwiftPM libs don't carry a version field). Falls back to `git describe --tags --abbrev=0` if no in-file version.
- `write(new_version)`: regex replacement on the version field. SwiftPM doesn't have a structured parser for non-TOML/Package.swift, so we use regex with verification (read back after write, fail if mismatch).

**Hooks** (`hooks.py`):
- `swift.test` → `swift test`
- `swift.build` → `swift build`
- `swift.format` → `swift format` (autofix=true)

No Python fallback for these — if `swift` is not in PATH, the hook fails with a clear message.

**Lifecycle** (`lifecycle.py`):
- `bump(level)`: VersionSource.write(next_version(current, level)) where `level` is one of `"major" | "minor" | "patch"` (matches Python's `-p` flag semantics). For pre-1.0 versions, the Python semver semantics are preserved (per `crackerjack-p-minor-full-lifecycle.md`).
- `commit`, `tag`, `push`: same as Python lifecycle (reuse core git helpers)
- `release`: `gh release create v{version} --generate-notes`

The CLI surface is `crackerjack run -p {major|minor|patch}` for all languages — the flag has the same meaning regardless of which language's lifecycle runs.

### Kotlin/Gradle adapter (`crackerjack/adapters/kotlin/`)

**Detect**: presence of `build.gradle.kts` or `build.gradle` (Groovy) at project root.

**VersionSource**:
- `read()`: parse `gradle.properties` and read `version=` field. Most idiomatic location for Gradle multi-project builds.
- `write(new_version)`: rewrite `gradle.properties` with new version. For projects without `gradle.properties` (single-module, version in `build.gradle.kts`), fall back to regex on the `version = "..."` line.

**Hooks**:
- `kotlin.ktlint` → `./gradlew ktlintCheck` (with `ktlintFormat` for autofix)
- `kotlin.detekt` → `./gradlew detekt`
- `kotlin.test` → `./gradlew test`

**Lifecycle**: same shape as Swift (bump → commit → tag → push → gh release). Marketplace publishing is out of scope.

### Web adapter (`crackerjack/adapters/web/`)

**Detect**: presence of any `.css`, `.scss`, `.html`, `.ts`, `.tsx`, `.js`, `.jsx`, `.jinja`, `.html.j2`, `.tmpl` files at project root or in `src/templates/`, `templates/`, `assets/`, `static/`. (Detection is shallow — checking for file extensions, not full inventory.)

**Hooks**:
- `web.css.stylelint` → `npx stylelint **/*.css`
- `web.js.eslint` → `npx eslint .`
- `web.js.tsc` → `npx tsc --noEmit`
- `web.html.validate` → `npx html-validate "**/*.html"`
- `web.jinja.format` → in-process Python (see Jinja formatter below)

Hybrid pattern: each hook first checks for the CLI tool, falls back to a Python implementation if the CLI is missing or fails.

**Jinja formatter** (`jinja_formatter.py`):
- Loads the project's Jinja delimiter config from `pyproject.toml` `[tool.crackerjack.jinja]` block. Falls back to auto-detection (scan a sample `.jinja` file for the first non-default delimiter).
- Uses `jinja2.Environment(..., block_start_string=..., variable_start_string=..., comment_start_string=...).parse(source)` to build an AST.
- Reformats with the canonical whitespace policy (below).
- Returns either the original source (already canonical) or the rewritten source.
- Round-trip invariant: `format(parse(format(x))) == format(x)`.

## Canonical Jinja whitespace policy

This policy is shared with `jinja2-custom-delimiters` (the
PyCharm plugin) via documented spec. Both packages converge on these rules:

1. **One space inside delimiters**: `{% if x %}` not `{%if x%}`
2. **Blank line between block-level tags** at the top level (e.g., between two `{% if %}` blocks)
3. **Preserve existing blank lines within content** (don't collapse)
4. **Trailing newline at EOF**
5. **No trailing whitespace on lines**
6. **Inline `{{ var }}` may remain inline**; block-level tags get their own line
7. **Trim `{%- ... -%}` only when the source already trims** (don't introduce new whitespace stripping)

The policy is encoded once in `crackerjack/adapters/web/jinja_canonical.py`
as a `JinjaCanonicalFormatter` class. It's the single source of truth.

### Cross-package parity

`jinja2-custom-delimiters` (Kotlin/IntelliJ plugin) configures PyCharm's
built-in Jinja formatter. PyCharm's formatter is not directly configurable
from outside the IDE. The parity strategy is:

1. Document the canonical policy in both repos (this spec + a doc file in `jinja2-custom-delimiters`)
2. Ship a `crackerjack web jinja export-intellij-style` subcommand that writes the policy as PyCharm code-style XML
3. Add a `jinja-test-fixtures/` directory in each repo (or share via Bodai) with the same input corpus; both formatters must produce identical output

## Data flow

### `crackerjack run -p minor` on a SwiftPM project

1. CLI parses args, locates project root
2. `core/language_detector.detect(project_root)` → `[PythonAdapter(), SwiftAdapter()]`
3. For each adapter, run lifecycle if available (skip Python lifecycle if project is Swift-only):
   - `SwiftAdapter.lifecycle(project_root).bump("minor")`
   - `VersionSource.read()` returns "0.1.1"
   - `VersionSource.write("0.2.0")` rewrites `Package.swift`
4. Git phase (core): `git add .`, `git commit -m "bump: swift v0.1.1 → v0.2.0"`, `git tag -a v0.2.0 -m "..."`, `git push origin main --tags`
5. Optional: `gh release create v0.2.0 --generate-notes`
6. Hooks phase (if --skip-hooks not set): runs all Swift hooks (`swift test`, `swift build`, `swift format`)
7. Report: lifecycle + hooks results

### `crackerjack run` on a fastblocks project (mixed Python + Web)

1. Detects Python (`pyproject.toml`) + Web (`.css`, `.html`, `.jinja` files)
2. Runs Python hooks (existing ruff, mypy, ty, zuban, complexipy, creosote, etc.)
3. Runs Web hooks (stylelint, html-validate, jinja format, optionally eslint/tsc if package.json present)
4. Both contribute to the success/failure report
5. Lifecycle runs only for Python (Web has no lifecycle in this design)

### `crackerjack web jinja format src/templates/`

1. New subcommand under `web` group
2. Discovers Jinja files matching the path arg
3. Loads delimiter config (pyproject `[tool.crackerjack.jinja]` or autodetect)
4. Formats each file in place
5. Reports per-file diffs and exit code

## Error handling

| Failure mode | Behavior |
|---|---|
| CLI not installed (e.g., `swift` not in PATH) | Skip hook with warning; do not fail the gate |
| Python fallback also missing | Fail the gate with installation instructions |
| `VersionSource.write()` fails to read back | Fail the gate (data integrity) |
| Hook subprocess fails | Capture stderr, format as error report, fail the gate (existing pattern) |
| Jinja parse error | Report file:line:col with original error message; do NOT rewrite the file |
| Multiple languages detected, some fail | Aggregate report; per-language sub-results |
| `gh` not installed for release step | Skip release step with warning; tag+push still succeeds |

## Testing strategy

### Unit tests

- Per-adapter unit tests with mocked subprocess (use `unittest.mock`)
- Jinja formatter: round-trip tests (`format(parse(format(x))) == format(x)`)
- Canonical policy: each of the 7 rules has 3+ positive cases and 3+ negative cases
- Version source: round-trip tests (write version, read it back, assert equal)

### Integration tests

- Fixture projects: `tests/fixtures/swift-lib/`, `tests/fixtures/gradle-plugin/`, `tests/fixtures/web-app/`
- Each fixture exercises the full `crackerjack run` end-to-end
- MCP server exposes tools; tests call them via in-process MCP client (`mcp-common` testing helpers)

### Cross-package parity tests (Jinja)

- Shared test corpus in `tests/fixtures/jinja-corpus/` — ~30 input templates covering default delimiters, fastblocks-style `[%`/`[[`/`[#`, edge cases (nested blocks, inline expressions, comments, whitespace stripping)
- Crackerjack Python formatter: passes 100% of corpus
- `jinja2-custom-delimiters` PyCharm integration: documented parity test in that repo (since we can't invoke PyCharm from headless CI, parity is verified manually + via a documentation note)
- Future: headless IntelliJ CLI test framework could automate this

### Regression tests

- All existing crackerjack Python tests must still pass after the Phase 1 refactor
- No behavior change for Python projects

## Migration plan

### Phase 1 — Foundation (no behavior change)

- Add `adapters/base.py`, `adapters/registry.py`, `core/language_detector.py`
- Refactor existing Python logic into `adapters/python/` (preserves all behavior)
- Verify: full crackerjack test suite passes (currently 11K+ tests)
- No new commands, no new behavior, just internal reorg

### Phase 2 — Swift (first new language)

- Implement Swift adapter
- Add entry-point registration in `pyproject.toml`
- Add MCP tools: `run_swift_hooks`, `bump_swift_version`, `detect_languages`
- Test on `swiftui-ipc-client` and `mdinject` Swift app
- Tag and document

### Phase 3 — Kotlin/Gradle

- Implement Kotlin adapter
- Test on `jinja2-custom-delimiters`
- Add MCP tools

### Phase 4 — Web + Jinja

- Implement Web adapter (stylelint, eslint, tsc, html-validate)
- Implement Jinja formatter with canonical policy
- Test on `fastblocks`, `splashstand`
- Coordinate with `jinja2-custom-delimiters` (same author) on canonical policy export

### Phase 5 — Polish

- Update `BODAI_REPO_REGISTRY.md` with a `language:` column to capture Swift-only and Kotlin-only repos
- Update crackerjack README + docs
- Bodai umbrella integration (entry-point already exists; add new tools to `bodai` CLI dispatch table)
- Cross-package Jinja parity test corpus published

## Open questions / future work

- **JetBrains Marketplace publishing** for Kotlin plugins (deferred; current `gh release` is the GitHub side)
- **Per-project hook config**: `[tool.crackerjack.disabled_hooks] = ["web.js.eslint"]` for projects using Biome instead — defer to v0.82
- **Watch mode**: real-time hook running on file change — defer to v0.83
- **Headless PyCharm parity tests** for Jinja formatter — requires IntelliJ CLI test framework; future
- **Rust/Go/Java/etc. support**: trivial extension via the same adapter pattern; defer until a Bodai project needs it
- **Auto-fix safety**: which hooks should be autofix=true vs false? Initial defaults: `swift.format`, `ktlint.format` (if available), `web.jinja.format`. All others require manual review.

## Compatibility notes

- Python 3.14 minimum (crackerjack already requires this)
- jinja2 >= 3.0 for `Environment.parse()` (already a transitive dep)
- For Swift/Kotlin version sources: no TOML parsing needed (these aren't TOML); use regex with read-back verification
- MCP tools: must register under existing `crackerjack.mcp.tools` module to be picked up by the FastMCP server on port 8676
- Bodai umbrella entry-point (`bodai.apps`) already exists; new language tools need to be added to the `bodai` CLI dispatch table (separate small task)

## Risks

1. **Refactor of existing Python logic (Phase 1)**: behavior must not change. Mitigation: golden-master test that runs existing CLI commands against fixture projects and diffs output.
2. **Jinja canonical policy divergence from PyCharm formatter**: PyCharm's formatter is configurable per-project, but our canonical policy is fixed. Mitigation: XML export for PyCharm import; documented parity test.
3. **Swift/Kotlin subprocess hangs**: `--timeout` per hook with reasonable defaults (10 min test, 15 min build).
4. **CLI tool detection false negatives**: e.g., `npx` available but `tsc` not installed in the project. Mitigation: clear error message naming the missing dep, not just "exit 1".

## See also

- Existing specs in `docs/superpowers/specs/` — refactor patterns
- `BODAI_REPO_REGISTRY.md` — language column addition
- `jinja2-custom-delimiters` plugin.xml — delimiter conversion contract
- memory `docs-audit-orphaned-diagram-claims.md` — pattern for honest docs
