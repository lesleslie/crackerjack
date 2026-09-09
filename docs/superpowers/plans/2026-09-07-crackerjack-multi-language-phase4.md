# Crackerjack Multi-Language Extension — Phase 4 (Web/CSS/HTML/JS/TS) Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Status:** Rev 2 — Ready for execution after multi-agent review fixes applied.
> **Rev 1 reviews:** `docs/superpowers/plans/reviews/2026-09-07-phase4-{a11y,api,mcp,security,simplification,testing,web,writing}.md`

**Goal:** Add a Web language adapter to crackerjack that activates only on JS/TS/CSS/HTML projects (or Python projects with explicit web opt-in). Provides 4 CLI hooks (stylelint, eslint, tsc, html-validate) with JSON output parsing, a Tier-1-only Jinja template formatter (`jinja2.Environment.lex()` for validation + raw source string ops for canonicalization), and 2 MCP tools (`check_web_lint`, `format_jinja_templates`).

**Architecture:** Approach A (per spec Rev 2) extended with Web. New `crackerjack/adapters/web/` package containing `WebAdapter`, `web_hooks` (CLI primary, JSON-parsed), and `jinja_formatter` (Tier 1 only). Two new MCP tools added to the existing `language_tools` group registered in Phase 2 (no `profiles.py` change). No lifecycle (out of scope per spec line 65). Web detection guard prevents Python-project false positives. Phase 4 deliberately omits Python fallbacks (Swift/Kotlin precedent) and Tier 2 normalization (deferred to a future phase that can afford golden-masters).

**Tech Stack:** Python 3.14, FastMCP 4.x, hatchling, jinja2 ≥3.1.6 (NEW direct dep per spec Jinja F11), subprocess (npx wrappers), tomllib (stdlib).

**Spec:** `/Users/les/Projects/crackerjack/docs/superpowers/specs/2026-09-07-crackerjack-multi-language-design.md` (Rev 2, on `main` as of commit `b00b36f0`). Phase 4 is at lines 363-429 ("Per-adapter Web").

**Out of scope:** shared `jinja-test-fixtures/` Bodai sibling package (Phase 4 deliverable per spec line 420) — separate plan. CSS/HTML/JS/TS lifecycle (spec line 65). Jinja Tier 2 normalization (deferred; see Spec Revision Notes). PyCharm parity script (spec Jinja F10) — separate plan. CLI subcommand for `crackerjack web jinja format` — separate plan.

---

## Global Constraints

Verbatim from the spec and project (carries forward from Phase 3):

- **Python 3.14** with `from __future__ import annotations` as the first non-comment line of every source file.
- **Modern syntax**: `X | None`, `list[str]`, `pathlib.Path`.
- **Default-`None` args typed `X | None = None`** (mypy `no_implicit_optional = true`).
- **No `assert` in production code** (`crackerjack/adapters/web/**/*.py` is production).
- **No `Any`** in production code. Tests may use `Any` for mocks.
- **`logger.exception(...)`** in `except` blocks.
- **All I/O async.** Subprocess via `asyncio.to_thread` or `loop.run_in_executor`. Sync only at CLI entry points.
- **argv list, no shell** for all subprocess invocations. `--` separator before user-influenced positionals.
- **Imports sorted within each section** (stdlib → third-party → first-party).
- **Remove unused imports and dead code immediately** (Ruff F401 / UP).
- **`@runtime_checkable` Protocol** for `LanguageAdapter` (per spec API F1).
- **`Hook` only requires `name` and `cli_command`**; all other fields default (per spec API F6).
- **4-step MCP registration pipeline** — Phase 4 tools added to existing `language_tools` group (Phase 2 registration covers; no `profiles.py` change needed).
- **Per-invocation auth check for mutation tools** (per spec MCP F5) — Phase 3 fixed `_validate_project_root` to fail-closed; Phase 4 reuses the fixed helpers.
- **Module docstring required** on every new Python file (per Phase 3 Writing HIGH-3).
- **`monkeypatch.setattr` mandate** per spec Testing F3.
- **Author email `les <les@wedgwoodwebworks.com>`** for every commit (NOT `.local`).
- **CLI-only hooks** (Phase 4 decision — see Spec Revision Notes): no Python fallbacks. When CLI is missing, raise `WebHookError` with installation instructions (Swift/Kotlin precedent).
- **Web detection guard** (per Writing F3): `WebAdapter.detect()` requires `package.json` at root OR explicit `[tool.crackerjack.web] enabled = true` in `pyproject.toml`. The MCP tool layer MUST also enforce this guard (per Phase 3 MCP review MEDIUM 1 + Phase 4 MCP HIGH 1).
- **`npx --no` (modern spelling)** is the swap for the legacy `--no-install` alias.
- **`jinja2>=3.1.6` as a direct dependency** (per spec Jinja F11). Currently only present transitively.
- **`jinja2.Environment.lex()` is used ONLY as a validation gate** (per spec Jinja F1 + Rev 2 corrections): lex detects `TemplateSyntaxError` and reports; canonicalization runs on raw source string via simple line-level operations. Comments preserved by construction (we never touch text outside the trailing-whitespace line fix-ups).
- **`keep_trailing_newline=True`** on the `Environment` constructor to prevent the lexer from stripping trailing newlines during validation.
- **All 6 delimiter kwargs required** (per spec Jinja F2): `block_start_string`, `block_end_string`, `variable_start_string`, `variable_end_string`, `comment_start_string`, `comment_end_string`.
- **Tier 1 canonical policy** (per spec Jinja F3): trailing newline at EOF, no trailing whitespace per line, preserve `{%-` / `-%}` / `{{-` / `-}}` markers. Always-on.
- **Tier 2 normalization is deferred** to a future phase (see Spec Revision Notes). Tier 1 is what users get by default and therefore the tier that must be right.

---

## File Structure

### New files (Phase 4)

```
crackerjack/
└── adapters/web/                                  # NEW
    ├── __init__.py                                # WebAdapter + web_enabled() (no detection.py module)
    ├── hooks.py                                   # 4 CLI hooks (stylelint, eslint, tsc, html-validate) with JSON parsing
    └── jinja_formatter.py                         # lex-as-validation + Tier 1 raw-source string ops

mcp/tools/
└── language_tools.py                              # MODIFIED: add check_web_lint + format_jinja_templates (nested inside register_language_tools)

tests/
├── adapters/web/
│   ├── __init__.py
│   ├── test_detection.py                          # 8 tests: package.json + opt-in guard
│   ├── test_hooks.py                              # 9 tests: 4 hook names, 4 CLI-missing branches, JSON parsing smoke
│   ├── test_jinja_formatter.py                    # 7 tests: Tier 1 rules + golden-master via fixtures + custom delimiters
│   └── test_web_adapter.py                        # 8 tests: WebAdapter contract
├── mcp/tools/
│   └── test_language_tools.py                     # EXTENDED with 4 web tests (sync, mock.patch.dict pattern)
├── adapters/
│   └── test_registry.py                           # EXTENDED: test_discover_adapters_includes_web
└── fixtures/
    ├── web-vanilla/                               # Real Web fixture (package.json + minimal src/)
    │   ├── package.json
    │   ├── .stylelintrc.json
    │   ├── .eslintrc.json
    │   ├── tsconfig.json
    │   ├── src/
    │   │   ├── style.css
    │   │   ├── app.ts
    │   │   └── index.html
    │   └── templates/                             # Jinja test inputs (NOT nested under tests/)
    │       ├── basic.html
    │       ├── custom_delimiters.html
    │       └── whitespace.html
    └── jinja-templates/                           # Golden-master corpus (separate from web-vanilla so non-Web projects can use it)
        ├── basic.html.j2                          # input
        ├── basic.html.j2.expected                 # golden output
        ├── custom_delimiters.html.j2              # input
        ├── custom_delimiters.html.j2.expected     # golden output
        ├── whitespace.html.j2                     # input
        └── whitespace.html.j2.expected            # golden output
```

### Modified files (Phase 4)

```
pyproject.toml                                     # MODIFIED: add Web entry-point + jinja2>=3.1.6 dep
crackerjack/mcp/tools/language_tools.py            # MODIFIED: add 2 tools (check_web_lint, format_jinja_templates) nested inside register_language_tools
tests/mcp/tools/test_language_tools.py             # MODIFIED: extend with 4 sync web tests; update detect_languages to assert all 4 adapters
tests/adapters/test_registry.py                    # MODIFIED: add test_discover_adapters_includes_web
CHANGELOG.md                                       # MODIFIED: add Phase 4 entry under [Unreleased]
```

### Files NOT modified

- `crackerjack/adapters/swift/**`, `crackerjack/adapters/kotlin/**`, `crackerjack/adapters/python/**` — prior adapters untouched.
- `crackerjack/mcp/server_core.py` — NOT modified (per Phase 2 BLOCKER B2, registration lives in `profiles.py`).
- `crackerjack/mcp/tools/profiles.py` — NOT modified (`language_tools` group already registered in Phase 2).
- `crackerjack/adapters/web/detection.py` — INTENTIONALLY ABSENT. Detection logic is in `web/__init__.py` (~12 lines) to match the Swift/Kotlin precedent (no detection module).
- `crackerjack/adapters/web/python_fallbacks.py` — INTENTIONALLY ABSENT. Phase 4 ships CLI-only hooks; Swift/Kotlin precedent.

---

## Task 1: Foundation — register Web entry-point + add `jinja2` dep

**Files:**
- Modify: `pyproject.toml` (2 changes)

- [ ] **Step 1: Verify current state**

Run: `grep -A 6 "crackerjack.language_adapters" pyproject.toml && grep "jinja2" pyproject.toml`
Expected: 3 entries (kotlin, python, swift); jinja2 may appear in `[dependency-groups]` or not at all.

- [ ] **Step 2: Add Web entry-point**

In `pyproject.toml`, under `[project.entry-points."crackerjack.language_adapters"]`, add:
```toml
web = "crackerjack.adapters.web:WebAdapter"
```
Keep alphabetical (kotlin, python, swift, web).

- [ ] **Step 3: Add `jinja2` direct dependency**

Per spec Jinja F11. In `pyproject.toml` `[project.dependencies]`:
```toml
"jinja2>=3.1.6",
```
Place near other web/jinja-adjacent deps; alphabetical within section.

- [ ] **Step 4: Verify**

Run: `grep -A 6 "crackerjack.language_adapters" pyproject.toml && grep "jinja2" pyproject.toml`
Expected: 4 entries (kotlin, python, swift, web); jinja2 now in `[project.dependencies]`.

- [ ] **Step 5: Install new dep**

Run: `cd /Users/les/Projects/crackerjack && uv sync`

- [ ] **Step 6: Commit**

```bash
cd /Users/les/Projects/crackerjack
git add pyproject.toml uv.lock
git -c user.email=les@wedgwoodwebworks.com -c user.name=les commit -m "feat(adapters): register Web entry-point + add jinja2>=3.1.6 direct dep"
```

---

## Task 2: Detection guard — `WebAdapter.detect()` folded into `__init__.py`

**Files:**
- Create: `crackerjack/adapters/web/__init__.py` (WebAdapter + `web_enabled()`; full content lands in Task 5)
- Create: `crackerjack/adapters/web/detection.py` — **INTENTIONALLY NOT CREATED**. Detection logic lives in `__init__.py` (~12 lines) to match Swift/Kotlin precedent.
- Test: `tests/adapters/web/__init__.py`, `tests/adapters/web/test_detection.py`

Per spec Writing F3 + Phase 4 simplification F10: detection logic is in `__init__.py` (no separate module). Swift and Kotlin inline `(project_root / "Package.swift").is_file()` and the build.gradle checks respectively — no detection module. Phase 4 matches.

- [ ] **Step 1: Write failing tests**

```python
# tests/adapters/web/__init__.py
"""Web adapter test package."""
```

```python
# tests/adapters/web/test_detection.py
"""Detection guard tests — Web adapter must NOT fire on Python projects without opt-in (per spec Writing F3)."""
from __future__ import annotations

from pathlib import Path

import pytest

from crackerjack.adapters.web import package_json_present, web_enabled


class TestPackageJsonPresent:
    def test_returns_true_when_present(self, tmp_path: Path) -> None:
        (tmp_path / "package.json").write_text("{}")
        assert package_json_present(tmp_path) is True

    def test_returns_false_when_missing(self, tmp_path: Path) -> None:
        assert package_json_present(tmp_path) is False


class TestWebEnabled:
    def test_true_when_package_json_present(self, tmp_path: Path) -> None:
        (tmp_path / "package.json").write_text("{}")
        assert web_enabled(tmp_path) is True

    def test_false_for_python_project_no_opt_in(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'foo'\n")
        assert web_enabled(tmp_path) is False

    def test_true_for_python_project_with_opt_in(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text(
            "[project]\nname = 'foo'\n[tool.crackerjack.web]\nenabled = true\n"
        )
        assert web_enabled(tmp_path) is True

    def test_package_json_wins_over_opt_in_false(self, tmp_path: Path) -> None:
        (tmp_path / "package.json").write_text("{}")
        (tmp_path / "pyproject.toml").write_text(
            "[tool.crackerjack.web]\nenabled = false\n"
        )
        assert web_enabled(tmp_path) is True

    def test_opt_in_false_without_package_json_is_false(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text(
            "[tool.crackerjack.web]\nenabled = false\n"
        )
        assert web_enabled(tmp_path) is False

    def test_malformed_pyproject_returns_false(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text("not valid toml {{{")
        assert web_enabled(tmp_path) is False

    def test_missing_pyproject_returns_false(self, tmp_path: Path) -> None:
        assert web_enabled(tmp_path) is False
```

- [ ] **Step 2: Run tests to verify failure**

Run: `cd /Users/les/Projects/crackerjack && /Users/les/Projects/crackerjack/.venv/bin/pytest tests/adapters/web/test_detection.py -v`
Expected: ImportError (no `crackerjack.adapters.web` yet) or 8 errors.

- [ ] **Step 3: Write minimal `__init__.py`**

```python
# crackerjack/adapters/web/__init__.py
"""Web language adapter (CSS / HTML / JS / TS).

The Web adapter activates only on projects with `package.json` at root or an
explicit `[tool.crackerjack.web] enabled = true` opt-in. This prevents
false-positive activation on Django / Sphinx / MkDocs Python projects.

Phase 4 ships CLI-only hooks (no Python fallbacks) — Swift/Kotlin precedent.
"""
from __future__ import annotations

import tomllib
from pathlib import Path


def package_json_present(project_root: Path) -> bool:
    """Return True if `package.json` exists at the project root."""
    return (project_root / "package.json").is_file()


def _opt_in_enabled(project_root: Path) -> bool:
    """Return True if `[tool.crackerjack.web] enabled = true` in pyproject.toml."""
    pyproject = project_root / "pyproject.toml"
    if not pyproject.is_file():
        return False
    try:
        with pyproject.open("rb") as f:
            data = tomllib.load(f)
    except (OSError, tomllib.TOMLDecodeError):
        return False
    tool = data.get("tool", {})
    crackerjack = tool.get("crackerjack", {})
    web = crackerjack.get("web", {})
    return bool(web.get("enabled", False))


def web_enabled(project_root: Path) -> bool:
    """Return True if the Web adapter should activate for this project.

    Per spec Writing F3: `package.json` at root OR `[tool.crackerjack.web] enabled = true`.
    """
    return package_json_present(project_root) or _opt_in_enabled(project_root)


# WebAdapter is added in Task 5.
__all__ = ["package_json_present", "web_enabled", "WebAdapter"]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/les/Projects/crackerjack && /Users/les/Projects/crackerjack/.venv/bin/pytest tests/adapters/web/test_detection.py -v`
Expected: 8 passed.

- [ ] **Step 5: Commit**

```bash
cd /Users/les/Projects/crackerjack
git add crackerjack/adapters/web/__init__.py tests/adapters/web/__init__.py tests/adapters/web/test_detection.py
git -c user.email=les@wedgwoodwebworks.com -c user.name=les commit -m "feat(adapters.web): detection guard (package.json OR [tool.crackerjack.web] opt-in)"
```

---

## Task 3: CLI hooks — 4 hooks with JSON output parsing (no Python fallbacks)

**Files:**
- Create: `crackerjack/adapters/web/hooks.py`
- Test: `tests/adapters/web/test_hooks.py`

Per Phase 4 simplification F6 (5 lenses agree): drop Python fallbacks. Swift/Kotlin precedent: `cli_required=True, fallback=None`. Hooks fail with installation instructions when CLI is missing. This makes spec Testing F3's two-path pair **N/A** for Phase 4 — explicitly stated in Spec Revision Notes.

Per Phase 4 convergent finding (API CRITICAL, Web BLOCKER-5, Writing HIGH-2, Security F-4, Testing LOW-3): split `web.eslint_tsc` into `web.eslint` + `web.tsc` (4 hooks total). Independent timeouts, independent pass/fail, JS-only projects naturally drop `web.tsc`.

Per Phase 4 Web BLOCKER-3 + Security F-4: one `_resolve(project_root, tool)` function replaces `_npx_command` + `_has_pinned_version` + the inverted `cli_name != "npx"` guard. Resolution order: `node_modules/.bin/<tool>` → `PATH` → `npx --no` (modern spelling). When resolution returns `None`, raise `WebHookError` with install instructions.

Per Phase 4 Web HIGH-1: parse JSON output from `stylelint -f json`, `eslint -f json`, `html-validate -f json`, and line-oriented `tsc --noEmit` output into the `(path, line, message)` shape. Without parsing, hooks always return `[]` (false-green via `mcp-surface-health-illusion`).

- [ ] **Step 1: Verify CLI tools available (best-effort, skip on failure)**

Run:
```bash
which npx node 2>&1 || echo "npx/node not available"
```

If `npx` is unavailable, log and proceed — Task 3 tests exercise the CLI-missing path and must work without npx installed.

- [ ] **Step 2: Write failing tests**

```python
# tests/adapters/web/__init__.py  (already created in Task 2)
"""Web adapter test package."""
```

```python
# tests/adapters/web/test_hooks.py
"""Hook construction + CLI-missing branch + JSON output parsing smoke."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest import mock

import pytest

from crackerjack.adapters.web.hooks import (
    WebHookError,
    _parse_stylelint_json,
    _parse_eslint_json,
    _parse_html_validate_json,
    _parse_tsc_output,
    _resolve,
    web_hooks,
)


class TestResolve:
    def test_node_modules_bin_wins(self, tmp_path: Path) -> None:
        (tmp_path / "node_modules" / ".bin" / "stylelint").mkdir(parents=True)
        (tmp_path / "node_modules" / ".bin" / "stylelint" / "stylelint").write_text("#!/bin/sh\n")
        assert _resolve(tmp_path, "stylelint") == (
            str(tmp_path / "node_modules" / ".bin" / "stylelint" / "stylelint"),
        )

    def test_path_wins_when_no_node_modules(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("shutil.which", lambda cmd: f"/usr/bin/{cmd}" if cmd == "stylelint" else None)
        assert _resolve(tmp_path, "stylelint") == ("/usr/bin/stylelint",)

    def test_npx_fallback(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("shutil.which", lambda cmd: "/usr/bin/npx" if cmd == "npx" else None)
        assert _resolve(tmp_path, "stylelint") == ("npx", "--no", "stylelint")

    def test_returns_none_when_all_paths_missing(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("shutil.which", lambda cmd: None)
        assert _resolve(tmp_path, "stylelint") is None


class TestWebHooks:
    def test_returns_four_hooks(self, tmp_path: Path) -> None:
        (tmp_path / "package.json").write_text("{}")
        hooks = web_hooks(tmp_path)
        names = {h.name for h in hooks}
        assert names == {
            "web.stylelint",
            "web.eslint",
            "web.tsc",
            "web.html_validate",
        }

    def test_hooks_have_no_fallback(self, tmp_path: Path) -> None:
        (tmp_path / "package.json").write_text("{}")
        hooks = web_hooks(tmp_path)
        assert all(h.fallback is None for h in hooks)

    def test_hooks_use_timeout_seconds(self, tmp_path: Path) -> None:
        (tmp_path / "package.json").write_text("{}")
        hooks = web_hooks(tmp_path)
        for h in hooks:
            assert h.timeout_seconds > 0

    def test_webhook_error_raised_when_resolve_fails(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        (tmp_path / "package.json").write_text("{}")
        monkeypatch.setattr("shutil.which", lambda cmd: None)
        with pytest.raises(WebHookError, match="npm install"):
            web_hooks(tmp_path)


class TestJsonParsers:
    def test_stylelint_json_parses_one_warning(self) -> None:
        payload = json.dumps(
            [{"source": "x.css", "warnings": [{"line": 3, "text": "no-empty-rules"}]}]
        )
        issues = _parse_stylelint_json(payload, Path("/proj"))
        assert len(issues) == 1
        assert issues[0][1] == 3  # line

    def test_eslint_json_parses_messages(self) -> None:
        payload = json.dumps(
            [{"filePath": "/proj/a.ts", "messages": [{"line": 7, "message": "no-unused-vars"}]}]
        )
        issues = _parse_eslint_json(payload, Path("/proj"))
        assert len(issues) == 1

    def test_html_validate_json_parses_messages(self) -> None:
        payload = json.dumps(
            [{"filePath": "/proj/a.html", "messages": [{"line": 2, "message": "no-trailing-whitespace"}]}]
        )
        issues = _parse_html_validate_json(payload, Path("/proj"))
        assert len(issues) == 1

    def test_tsc_output_parses_errors(self) -> None:
        out = "a.ts(5,10): error TS2304: Cannot find name 'foo'.\n"
        issues = _parse_tsc_output(out, Path("/proj"))
        assert len(issues) == 1
        assert "TS2304" in issues[0][2]

    def test_tsc_output_returns_empty_when_clean(self) -> None:
        assert _parse_tsc_output("", Path("/proj")) == []
```

- [ ] **Step 3: Run tests to verify failure**

Run: `cd /Users/les/Projects/crackerjack && /Users/les/Projects/crackerjack/.venv/bin/pytest tests/adapters/web/test_hooks.py -v`
Expected: ImportError or 12 failures.

- [ ] **Step 4: Write `hooks.py`**

```python
# crackerjack/adapters/web/hooks.py
"""Web hooks: stylelint, eslint, tsc, html-validate.

Phase 4 ships CLI-only hooks with JSON output parsing. When the CLI is missing,
`WebHookError` is raised with installation instructions — Swift/Kotlin precedent
(no Python fallbacks). This keeps the false-positive surface small (Python
fallbacks for brace counting etc. are naive and false-positive on real files).

Per Phase 4 spec amendments:
- `web.eslint_tsc` was split into `web.eslint` + `web.tsc` (independent
  pass/fail, independent timeouts).
- `_resolve(project_root, tool)` is the single resolver; replaces the
  inverted `cli_name != "npx"` guard.
- Modern `npx --no` spelling replaces the legacy `--no-install` alias.
"""
from __future__ import annotations

import json
import logging
import re
import shutil
import subprocess
from collections.abc import Mapping
from pathlib import Path

from crackerjack.core.adapters.base import Hook

logger = logging.getLogger(__name__)

HookIssue = tuple[Path, int, str]


class WebHookError(RuntimeError):
    """Raised when a Web hook cannot run (CLI missing)."""


def _resolve(project_root: Path, tool: str) -> tuple[str, ...] | None:
    """Resolve how to invoke `tool` for `project_root`.

    Order: `node_modules/.bin/<tool>` → `PATH` → `npx --no <tool>` → `None`.
    Returns the argv tuple, or `None` if the tool is unresolvable.
    """
    nm_bin = project_root / "node_modules" / ".bin" / tool
    if nm_bin.is_file():
        return (str(nm_bin),)
    on_path = shutil.which(tool)
    if on_path is not None:
        return (on_path,)
    if shutil.which("npx") is not None:
        return ("npx", "--no", tool)
    return None


def _build_hook(
    name: str,
    project_root: Path,
    tool: str,
    *extra_args: str,
    timeout_seconds: int = 300,
) -> Hook:
    """Resolve `tool` and build a `Hook`. Raise `WebHookError` if unresolvable."""
    cmd = _resolve(project_root, tool)
    if cmd is None:
        raise WebHookError(
            f"Cannot resolve {tool!r} for project {project_root}. "
            f"Install Node.js (https://nodejs.org) and run "
            f"`npm install --save-dev {tool}`."
        )
    argv = (*cmd, *extra_args, str(project_root))
    return Hook(name=name, cli_command=argv, fallback=None, timeout_seconds=timeout_seconds)


def web_hooks(project_root: Path) -> tuple[Hook, ...]:
    """Build the four Web hooks for `project_root`."""
    return (
        _build_hook("web.stylelint", project_root, "stylelint", "**/*.css"),
        _build_hook("web.eslint", project_root, "eslint", ".", "--ext", ".ts,.tsx,.js,.jsx"),
        _build_hook("web.tsc", project_root, "tsc", "--noEmit", timeout_seconds=600),
        _build_hook("web.html_validate", project_root, "html-validate", "**/*.html"),
    )


# --- JSON / line-oriented output parsers ---


def _parse_stylelint_json(stdout: str, project_root: Path) -> list[HookIssue]:
    """Parse `stylelint -f json` output into `HookIssue` triples."""
    try:
        payload = json.loads(stdout) if stdout.strip() else []
    except json.JSONDecodeError:
        return []
    issues: list[HookIssue] = []
    for entry in payload:
        path = Path(entry.get("source", str(project_root)))
        for warning in entry.get("warnings", []):
            issues.append((path, int(warning.get("line", 0)), str(warning.get("text", ""))))
    return issues


def _parse_eslint_json(stdout: str, project_root: Path) -> list[HookIssue]:
    """Parse `eslint -f json` output into `HookIssue` triples."""
    try:
        payload = json.loads(stdout) if stdout.strip() else []
    except json.JSONDecodeError:
        return []
    issues: list[HookIssue] = []
    for entry in payload:
        path = Path(entry.get("filePath", str(project_root)))
        for msg in entry.get("messages", []):
            issues.append((path, int(msg.get("line", 0)), str(msg.get("message", ""))))
    return issues


def _parse_html_validate_json(stdout: str, project_root: Path) -> list[HookIssue]:
    """Parse `html-validate -f json` output into `HookIssue` triples."""
    try:
        payload = json.loads(stdout) if stdout.strip() else []
    except json.JSONDecodeError:
        return []
    issues: list[HookIssue] = []
    for entry in payload:
        path = Path(entry.get("filePath", str(project_root)))
        for msg in entry.get("messages", []):
            issues.append((path, int(msg.get("line", 0)), str(msg.get("message", ""))))
    return issues


_TSC_LINE = re.compile(r"^(?P<path>[^()]+)\((?P<line>\d+),(?P<col>\d+)\):\s+(?P<severity>error|warning)\s+(?P<code>TS\d+):\s+(?P<msg>.+)$")


def _parse_tsc_output(stdout: str, project_root: Path) -> list[HookIssue]:
    """Parse `tsc --noEmit` line-oriented output into `HookIssue` triples."""
    issues: list[HookIssue] = []
    for line in stdout.splitlines():
        m = _TSC_LINE.match(line.strip())
        if m:
            path = Path(m.group("path"))
            issues.append((path, int(m.group("line")), f"{m.group('code')}: {m.group('msg')}"))
    return issues


__all__ = [
    "HookIssue",
    "WebHookError",
    "_parse_eslint_json",
    "_parse_html_validate_json",
    "_parse_stylelint_json",
    "_parse_tsc_output",
    "_resolve",
    "web_hooks",
]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /Users/les/Projects/crackerjack && /Users/les/Projects/crackerjack/.venv/bin/pytest tests/adapters/web/test_hooks.py -v`
Expected: 12 passed.

- [ ] **Step 6: Commit**

```bash
cd /Users/les/Projects/crackerjack
git add crackerjack/adapters/web/hooks.py tests/adapters/web/test_hooks.py
git -c user.email=les@wedgwoodwebworks.com -c user.name=les commit -m "feat(adapters.web): 4 CLI hooks with JSON parsing, _resolve() resolver, WebHookError on missing CLI"
```

---

## Task 4: Jinja formatter — Tier 1 only (raw source string ops + lex validation)

**Files:**
- Create: `crackerjack/adapters/web/jinja_formatter.py`
- Test: `tests/adapters/web/test_jinja_formatter.py`

Per Phase 4 convergent finding (Simplification F2 + Web BLOCKER-1, 4 lenses agree): **Tier 1 must operate on the raw source string, NOT on lex tokens.** Joining lex token values is fundamentally lossy — `lex()` strips whitespace control markers into token values, so joining replays the strip. Tier 1's three rules (trailing newline, strip trailing whitespace, preserve markers) are pure text operations that need no tokenization.

Per Phase 4 Simplification F1 + Web BLOCKER-2 + A11y F2 + Writing HIGH-1: **Tier 2 normalization is deferred.** The regex-based implementation fundamentally corrupts templates (`{%if x%}` → `{% f  %}`). Tier 2 needs golden-master-driven design in a future phase.

Per Phase 4 Simplification F2 + Web BLOCKER-1: `lex()` is used ONLY as a validation gate. If lex raises `TemplateSyntaxError`, return the source unchanged (best-effort) and surface the failure to the MCP caller (Task 6 threads `errors` back).

Per Phase 4 F8 + A11y F1: `_load_jinja_config(project_root)` reads `[tool.crackerjack.jinja]` from pyproject.toml for the 6 delimiter keys. Defaults to standard delimiters when missing.

- [ ] **Step 1: Verify jinja2 ≥3.1.6 installed**

Run: `cd /Users/les/Projects/crackerjack && /Users/les/Projects/crackerjack/.venv/bin/python -c "import jinja2; print(jinja2.__version__)"`
Expected: 3.1.6 or higher.

- [ ] **Step 2: Write failing tests**

```python
# tests/adapters/web/test_jinja_formatter.py
"""Jinja formatter: lex-as-validation + Tier 1 raw-source string ops.

Phase 4 ships Tier 1 only. Tier 2 normalization is deferred to a future phase
that can afford golden-master-driven design.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from crackerjack.adapters.web.jinja_formatter import (
    DEFAULT_DELIMITERS,
    JINJA_SUFFIXES,
    _apply_tier1,
    _env,
    _load_jinja_config,
    format_template,
)


class TestApplyTier1:
    def test_adds_trailing_newline(self) -> None:
        assert _apply_tier1("hello").endswith("\n")

    def test_idempotent_when_already_canonical(self) -> None:
        assert _apply_tier1("hello\n") == "hello\n"

    def test_strips_trailing_whitespace_per_line(self) -> None:
        assert _apply_tier1("a   \nb\n").splitlines() == ["a", "b"]

    def test_preserves_marker_surrounding_text(self) -> None:
        # Tier 1 must NOT touch text adjacent to {%- / -%} markers.
        src = "A {%- if x -%} B\n"
        assert _apply_tier1(src) == "A {%- if x -%} B\n"

    def test_normalizes_crlf_to_lf(self) -> None:
        # Phase 4 normalizes CRLF → LF (Python's splitlines() strips line
        # terminators; we rejoin with LF only). CRLF preservation is out of
        # scope for Phase 4 (deferred; see Spec Revision Notes #8).
        assert _apply_tier1("hello\r\n") == "hello\n"


class TestFormatTemplate:
    def test_lex_failure_returns_source_unchanged(self) -> None:
        """Mismatched delimiters raise TemplateSyntaxError; format_template catches and returns src."""
        src = "{% if x %}A{% endif %}"
        custom_delims = {
            "block_start": "[%", "block_end": "%]",
            "variable_start": "[[", "variable_end": "]]",
            "comment_start": "[#", "comment_end": "#]",
        }
        # Source uses `{%` but env expects `[%`. env.lex() raises TemplateSyntaxError;
        # format_template catches and returns src unchanged.
        assert format_template(src, delimiters=custom_delims) == src

    def test_default_delimiters_round_trip(self) -> None:
        src = "{# c #}\n{% if x %}\nA\n{% else %}\nB\n{% endif %}\n"
        once = format_template(src)
        twice = format_template(once)
        assert once == twice
        assert once.endswith("\n")

    def test_unknown_tag_is_tolerated(self) -> None:
        # `{% trans %}` is valid Jinja but not configured; lex returns text tokens.
        # Tier 1 must not corrupt surrounding content.
        src = "before {% trans %}hello{% endtrans %} after\n"
        once = format_template(src)
        assert "before" in once and "after" in once


class TestLoadJinjaConfig:
    def test_missing_pyproject_returns_defaults(self, tmp_path: Path) -> None:
        delims, normalize = _load_jinja_config(tmp_path)
        assert delims == DEFAULT_DELIMITERS

    def test_writes_delimiters_from_pyproject(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text(
            "[tool.crackerjack.jinja]\n"
            'block_start = "[%"\n'
            'block_end = "%]"\n'
            'variable_start = "[["\n'
            'variable_end = "]]"\n'
            'comment_start = "[#"\n'
            'comment_end = "#]"\n'
        )
        delims, _ = _load_jinja_config(tmp_path)
        assert delims["block_start"] == "[%"

    def test_malformed_pyproject_returns_defaults(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text("not valid toml {{{")
        delims, _ = _load_jinja_config(tmp_path)
        assert delims == DEFAULT_DELIMITERS


class TestJinjaSuffixes:
    def test_suffixes_match_policy(self) -> None:
        assert JINJA_SUFFIXES == frozenset({".html", ".j2", ".jinja"})
```

- [ ] **Step 3: Run tests to verify failure**

Run: `cd /Users/les/Projects/crackerjack && /Users/les/Projects/crackerjack/.venv/bin/pytest tests/adapters/web/test_jinja_formatter.py -v`
Expected: ImportError or 10 failures.

- [ ] **Step 4: Write `jinja_formatter.py`**

```python
# crackerjack/adapters/web/jinja_formatter.py
"""Jinja template formatter — Tier 1 only.

Phase 4 ships the always-on Tier 1 canonicalization:
- Trailing newline at EOF.
- No trailing whitespace per line.
- Preserve `{%-` / `-%}` / `{{-` / `-}}` markers AND surrounding text.

Tier 2 normalization (`[tool.crackerjack.jinja] normalize = true`) is deferred
to a future phase. The Phase 4 design choice was to use raw-source string ops
instead of `lex()` token reconstruction — token values lose the very whitespace
control that Tier 1 rule 3 promises to preserve. `Environment.lex()` is still
called as a syntax-validation gate; on `TemplateSyntaxError`, the source is
returned unchanged.

Per-project delimiter config (`[tool.crackerjack.jinja]` in pyproject.toml) is
loaded by `_load_jinja_config` — see spec Jinja F2 / Data Flow step 3.
"""
from __future__ import annotations

import logging
import tomllib
from collections.abc import Mapping
from pathlib import Path

import jinja2

logger = logging.getLogger(__name__)

JINJA_SUFFIXES: frozenset[str] = frozenset({".html", ".j2", ".jinja"})

DEFAULT_DELIMITERS: Mapping[str, str] = {
    "block_start": "{%",
    "block_end": "%}",
    "variable_start": "{{",
    "variable_end": "}}",
    "comment_start": "{#",
    "comment_end": "#}",
}

_REQUIRED_DELIMITER_KEYS = frozenset(DEFAULT_DELIMITERS.keys())


def _env(delimiters: Mapping[str, str]) -> jinja2.Environment:
    """Construct a Jinja2 Environment with the 6 delimiter kwargs.

    `keep_trailing_newline=True` is set so the lexer's validation pass does
    not silently strip a trailing newline.
    """
    return jinja2.Environment(
        block_start_string=delimiters["block_start"],
        block_end_string=delimiters["block_end"],
        variable_start_string=delimiters["variable_start"],
        variable_end_string=delimiters["variable_end"],
        comment_start_string=delimiters["comment_start"],
        comment_end_string=delimiters["comment_end"],
        keep_trailing_newline=True,
    )


def _apply_tier1(source: str) -> str:
    """Apply Tier 1 canonicalization rules to the raw source string.

    Rules (per spec Jinja F3 Tier 1):
    1. Trailing newline at EOF.
    2. Strip trailing whitespace from each line.
    3. Preserve `{%-` / `-%}` / `{{-` / `-}}` markers (untouched by construction;
       we only operate on line-level trailing whitespace).
    """
    lines = source.splitlines()
    lines = [line.rstrip() for line in lines]
    out = "\n".join(lines)
    if source.endswith("\n"):
        out += "\n"
    elif out:
        out += "\n"
    return out


def format_template(
    source: str,
    delimiters: Mapping[str, str] | None = None,
) -> str:
    """Format `source` per Tier 1 rules. `lex()` validates; if it raises,
    `source` is returned unchanged.

    Phase 4 ships Tier 1 only. The `normalize` parameter is REMOVED from Rev 1;
    Tier 2 is deferred to a future phase.
    """
    delims = delimiters or DEFAULT_DELIMITERS
    env = _env(delims)
    try:
        list(env.lex(source))
    except jinja2.TemplateSyntaxError:
        logger.warning("Jinja lex failed; returning source unchanged")
        return source
    return _apply_tier1(source)


def _load_delimiters_from_pyproject(project_root: Path) -> Mapping[str, str] | None:
    """Read `[tool.crackerjack.jinja]` and return the 6 delimiter keys, or None if absent/malformed."""
    pyproject = project_root / "pyproject.toml"
    if not pyproject.is_file():
        return None
    try:
        with pyproject.open("rb") as f:
            data = tomllib.load(f)
    except (OSError, tomllib.TOMLDecodeError):
        return None
    section = data.get("tool", {}).get("crackerjack", {}).get("jinja", {})
    if not isinstance(section, dict):
        return None
    if not _REQUIRED_DELIMITER_KEYS.issubset(section):
        return None
    return {key: str(section[key]) for key in _REQUIRED_DELIMITER_KEYS}


def _load_jinja_config(project_root: Path) -> tuple[Mapping[str, str], bool]:
    """Return `(delimiters, normalize)` for `project_root`.

    `delimiters` is the 6-key mapping. `normalize` is always False in Phase 4
    (Tier 2 deferred). Defaults to standard delimiters when the config is absent.
    """
    delims = _load_delimiters_from_pyproject(project_root) or DEFAULT_DELIMITERS
    return delims, False


__all__ = [
    "DEFAULT_DELIMITERS",
    "JINJA_SUFFIXES",
    "_apply_tier1",
    "_env",
    "_load_jinja_config",
    "format_template",
]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /Users/les/Projects/crackerjack && /Users/les/Projects/crackerjack/.venv/bin/pytest tests/adapters/web/test_jinja_formatter.py -v`
Expected: 10 passed.

- [ ] **Step 6: Commit**

```bash
cd /Users/les/Projects/crackerjack
git add crackerjack/adapters/web/jinja_formatter.py tests/adapters/web/test_jinja_formatter.py
git -c user.email=les@wedgwoodwebworks.com -c user.name=les commit -m "feat(adapters.web): Tier 1 Jinja formatter (raw-source ops + lex validation; Tier 2 deferred)"
```

---

## Task 5: `WebAdapter` — wire detection + hooks into `Capabilities`

**Files:**
- Modify: `crackerjack/adapters/web/__init__.py` (add WebAdapter class; existing `web_enabled` stays)
- Test: `tests/adapters/web/test_web_adapter.py`

Per Phase 4 simplification F11: `WebAdapter.capabilities()` constructs nothing heavy (no formatter, no lifecycle). Mirrors Swift's `name = "swift"` bare-assignment style. Kotlin uses `name: str = "kotlin"` annotated; either style is functionally equivalent (both inherit the `ClassVar[str]` annotation from `LanguageAdapterBase`).

Per spec line 65: no lifecycle for Web. `has_lifecycle=False` and `version_source=None`.

- [ ] **Step 1: Write failing tests**

```python
# tests/adapters/web/test_web_adapter.py
"""WebAdapter contract tests."""
from __future__ import annotations

from pathlib import Path

import pytest

from crackerjack.adapters.base import LanguageAdapterBase
from crackerjack.adapters.web import WebAdapter, web_hooks


class TestWebAdapter:
    def test_extends_language_adapter_base(self) -> None:
        assert issubclass(WebAdapter, LanguageAdapterBase)

    def test_name_is_web(self) -> None:
        assert WebAdapter().name == "web"

    def test_detect_returns_true_when_package_json_present(self, tmp_path: Path) -> None:
        (tmp_path / "package.json").write_text("{}")
        assert WebAdapter().detect(tmp_path) is True

    def test_detect_returns_false_for_python_project_no_opt_in(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'foo'\n")
        assert WebAdapter().detect(tmp_path) is False

    def test_detect_returns_true_for_python_project_with_opt_in(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text(
            "[project]\nname = 'foo'\n[tool.crackerjack.web]\nenabled = true\n"
        )
        assert WebAdapter().detect(tmp_path) is True

    def test_capabilities_has_no_lifecycle(self, tmp_path: Path) -> None:
        (tmp_path / "package.json").write_text("{}")
        caps = WebAdapter().capabilities(tmp_path)
        assert caps.has_lifecycle is False
        assert caps.has_version is False

    def test_capabilities_exposes_four_hooks(self, tmp_path: Path) -> None:
        (tmp_path / "package.json").write_text("{}")
        caps = WebAdapter().capabilities(tmp_path)
        names = {h.name for h in caps.hooks}
        assert names == {
            "web.stylelint",
            "web.eslint",
            "web.tsc",
            "web.html_validate",
        }

    def test_capabilities_hooks_match_web_hooks_function(self, tmp_path: Path) -> None:
        (tmp_path / "package.json").write_text("{}")
        caps = WebAdapter().capabilities(tmp_path)
        assert caps.hooks == web_hooks(tmp_path)
```

- [ ] **Step 2: Run tests to verify failure**

Run: `cd /Users/les/Projects/crackerjack && /Users/les/Projects/crackerjack/.venv/bin/pytest tests/adapters/web/test_web_adapter.py -v`
Expected: ImportError (no `WebAdapter`) or 8 failures.

- [ ] **Step 3: Add `WebAdapter` to `__init__.py`**

Append to `crackerjack/adapters/web/__init__.py`:

```python
# At the top of the file (after the existing imports):
from crackerjack.core.adapters.base import Capabilities, LanguageAdapterBase

from crackerjack.adapters.web.hooks import web_hooks


# At the bottom of the file:
class WebAdapter(LanguageAdapterBase):
    """Web (CSS/HTML/JS/TS) language adapter.

    Phase 4 ships CLI-only hooks with no lifecycle (per spec line 65).
    """

    name = "web"

    def detect(self, project_root: Path) -> bool:
        """Return True iff the Web adapter should activate for `project_root`."""
        return web_enabled(project_root)

    def capabilities(self, project_root: Path) -> Capabilities:
        """Return the Web adapter's capabilities for `project_root`."""
        return Capabilities(
            version_source=None,  # No version management for Web
            hooks=web_hooks(project_root),
            has_lifecycle=False,
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/les/Projects/crackerjack && /Users/les/Projects/crackerjack/.venv/bin/pytest tests/adapters/web/test_web_adapter.py -v`
Expected: 8 passed.

- [ ] **Step 5: Run full Web test suite**

Run: `cd /Users/les/Projects/crackerjack && /Users/les/Projects/crackerjack/.venv/bin/pytest tests/adapters/web/ -v`
Expected: 38 passed (8 + 12 + 10 + 8).

- [ ] **Step 6: Commit**

```bash
cd /Users/les/Projects/crackerjack
git add crackerjack/adapters/web/__init__.py tests/adapters/web/test_web_adapter.py
git -c user.email=les@wedgwoodwebworks.com -c user.name=les commit -m "feat(adapters.web): WebAdapter wires detection + 4 hooks into Capabilities"
```

---

## Task 6: MCP tools — `check_web_lint` + `format_jinja_templates` (nested, sync tests, with detection guard + dry_run)

**Files:**
- Modify: `crackerjack/mcp/tools/language_tools.py` (add 2 tools nested inside `register_language_tools`)
- Modify: `tests/mcp/tools/test_language_tools.py` (extend with 4 sync web tests; update `test_detect_languages_returns_adapter_names`)
- Modify: `tests/adapters/test_registry.py` (add `test_discover_adapters_includes_web`)

Per Phase 4 MCP HIGH 1: `format_jinja_templates` MUST enforce the Web detection guard at the MCP layer (mirrors Kotlin pattern at `language_tools.py:288-293`). A Python project without opt-in cannot have its Jinja templates rewritten.

Per Phase 4 Web BLOCKER-6: tool wrappers are nested `async def` inside `register_language_tools`, with `@mcp_app.tool()` on the nested function. NOT module scope (which would be a NameError).

Per Phase 4 MCP HIGH 4 + A11y F4 + F1 + F8: `format_jinja_templates` accepts `dry_run: bool = True` default (Phase 3 `kotlin_bump_version` precedent). Loads `[tool.crackerjack.jinja]` via `_load_jinja_config` for each project. Symlink guard: skip symlinks.

Per Phase 4 MCP MEDIUM 3: imports at module top (not inline). Per Phase 4 Web BLOCKER-7: tests are sync `def` matching the file's existing 13 tests; use `mock.patch.dict(os.environ, {...}, clear=True)` not `pytest.MonkeyPatch()`.

Per Phase 4 MCP MEDIUM 2: `test_detect_languages_returns_adapter_names` must now assert `"kotlin" in result` AND `"web" in result` (Phase 3 carry-over + Phase 4).

Per Phase 4 MCP HIGH 2: happy-path test reads back the file to verify mutation actually happened (Phase 2 fake-green prevention).

- [ ] **Step 1: Write failing tests**

Extend `tests/mcp/tools/test_language_tools.py` with the following 4 tests (plus update existing assertions):

```python
# At the top of test_language_tools.py, add:
import os
from unittest import mock

from crackerjack.adapters.web import WebAdapter


# Update test_detect_languages_returns_adapter_names to assert ALL FOUR adapters:
def test_detect_languages_returns_adapter_names():
    """All four adapters must register (Phase 3 carry-over: kotlin; Phase 4: web)."""
    # ... existing test body, but the assertion should now be:
    assert "python" in result
    assert "swift" in result
    assert "kotlin" in result  # Phase 3 carry-over
    assert "web" in result     # Phase 4


# Add these four new tests at the end of the file:

def test_check_web_lint_returns_four_hook_names(tmp_path, monkeypatch):
    """Phase 4: check_web_lint returns the 4-hook metadata for a Web project."""
    (tmp_path / "package.json").write_text("{}")
    monkeypatch.setenv("MAHAVISHNU_PROJECT_ROOTS", str(tmp_path))
    _, tools = _register()
    tool = tools["check_web_lint"]
    result = asyncio.run(tool.fn(project_root=str(tmp_path)))
    assert isinstance(result, dict)
    assert "hooks" in result
    names = {h["name"] for h in result["hooks"]}
    assert names == {
        "web.stylelint",
        "web.eslint",
        "web.tsc",
        "web.html_validate",
    }


def test_check_web_lint_rejects_python_project_no_opt_in(tmp_path, monkeypatch):
    """Phase 4: check_web_lint raises ValueError on a Python project without opt-in (per Writing F3)."""
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'foo'\n")
    monkeypatch.setenv("MAHAVISHNU_PROJECT_ROOTS", str(tmp_path))
    _, tools = _register()
    tool = tools["check_web_lint"]
    with pytest.raises(ValueError, match="Web adapter not enabled"):
        asyncio.run(tool.fn(project_root=str(tmp_path)))


def test_format_jinja_templates_requires_auth(tmp_path, monkeypatch):
    """Phase 4: format_jinja_templates raises PermissionError when auth env vars unset."""
    (tmp_path / "package.json").write_text("{}")
    monkeypatch.setenv("MAHAVISHNU_PROJECT_ROOTS", str(tmp_path))
    monkeypatch.delenv("MAHAVISHNU_AUTH_ENABLED", raising=False)
    monkeypatch.delenv("MAHAVISHNU_JWT_SECRET", raising=False)
    _, tools = _register()
    tool = tools["format_jinja_templates"]
    with pytest.raises(PermissionError):
        asyncio.run(tool.fn(projects=[str(tmp_path)]))


def test_format_jinja_templates_runs_with_auth(tmp_path, monkeypatch):
    """Phase 4: format_jinja_templates actually rewrites the file on disk."""
    (tmp_path / "package.json").write_text("{}")
    test_file = tmp_path / "test.html"
    original = "{% if x %}A{% endif %}"
    test_file.write_text(original)

    monkeypatch.setenv("MAHAVISHNU_AUTH_ENABLED", "true")
    monkeypatch.setenv("MAHAVISHNU_JWT_SECRET", "x" * 64)
    monkeypatch.setenv("MAHAVISHNU_PROJECT_ROOTS", str(tmp_path))
    _, tools = _register()
    tool = tools["format_jinja_templates"]
    result = asyncio.run(tool.fn(projects=[str(tmp_path)], dry_run=False))

    # Verify mutation actually happened (Phase 2 fake-green prevention).
    assert result["errors"] == []
    assert any("test.html" in f for f in result["files"])
    rewritten = test_file.read_text()
    assert rewritten != original
    assert rewritten.endswith("\n")  # Tier 1 trailing-newline rule


# Extend tests/adapters/test_registry.py with:
def test_discover_adapters_includes_web():
    """Phase 4: discover_adapters() must include the Web adapter."""
    from crackerjack.adapters.registry import discover_adapters
    adapters = discover_adapters()
    assert "web" in adapters
    assert isinstance(adapters["web"], WebAdapter)
```

- [ ] **Step 2: Run tests to verify failure**

Run: `cd /Users/les/Projects/crackerjack && /Users/les/Projects/crackerjack/.venv/bin/pytest tests/mcp/tools/test_language_tools.py tests/adapters/test_registry.py -v -k "web or detect_languages or discover_adapters_includes_web"`
Expected: 5 failures (the new tests; the updated `test_detect_languages_returns_adapter_names` also fails on the `"web" in result` assertion).

- [ ] **Step 3: Add the two MCP tools**

At the top of `crackerjack/mcp/tools/language_tools.py`, add the imports (with the existing top-level imports sorted):

```python
from crackerjack.adapters.web import WebAdapter, web_enabled
from crackerjack.adapters.web.jinja_formatter import JINJA_SUFFIXES, _load_jinja_config, format_template
from crackerjack.adapters.web.hooks import _parse_eslint_json, _parse_html_validate_json, _parse_stylelint_json, _parse_tsc_output
```

(`_apply_tier1` removed from the import list — it was a leftover from an earlier draft; only `format_template` and `_load_jinja_config` are used by the MCP tool.)

Inside `register_language_tools(mcp_app: FastMCP) -> None:`, after the existing Phase 3 tools and before any closing statement, add the two web tools:

```python
    @mcp_app.tool()
    async def check_web_lint(project_root: str) -> dict:
        """Return Web hook metadata for the given project (read-only, no auth).

        Activates the Web adapter (requires `package.json` at root OR
        `[tool.crackerjack.web] enabled = true`). Each hook is CLI-primary with
        JSON output parsing per spec Writing F2.

        Args:
            project_root: Absolute path to the project root. Must be in
                `MAHAVISHNU_PROJECT_ROOTS` allowlist.

        Returns:
            dict with keys: `adapter` (`"web"`), `enabled` (bool), `hooks`
            (list of {name, cli_command, timeout_seconds}).

        Raises:
            PermissionError: if `project_root` is not in
                `MAHAVISHNU_PROJECT_ROOTS` allowlist.
            ValueError: if the Web adapter is not enabled for the project.
        """
        root = _validate_project_root(project_root)
        if not web_enabled(root):
            raise ValueError(
                f"Web adapter not enabled at {root}. "
                f"Add `package.json` or set `[tool.crackerjack.web] enabled = true`."
            )
        hooks = [
            {
                "name": h.name,
                "cli_command": list(h.cli_command),
                "timeout_seconds": h.timeout_seconds,
            }
            for h in WebAdapter().capabilities(root).hooks
        ]
        return {"adapter": "web", "enabled": True, "hooks": hooks}

    @mcp_app.tool()
    async def format_jinja_templates(
        projects: list[str],
        dry_run: bool = True,
    ) -> dict:
        """Format Jinja templates in the given project directories (mutation; auth required).

        Phase 4 ships Tier 1 only (trailing newline + no trailing whitespace).
        Tier 2 normalization is deferred. Per-project delimiter config is read
        from `[tool.crackerjack.jinja]` in pyproject.toml.

        Args:
            projects: List of project root directories to scan.
            dry_run: If True (default), return the list of files that would be
                reformatted without writing. If False, write the reformatted
                content back to disk.

        Returns:
            dict with keys: `files` (rewritten paths), `errors` (per-file
            failure records), `mode` (`"dry_run"` or `"write"`).

        Raises:
            PermissionError: if auth env vars are not configured.
            ValueError: if any project is not Web-enabled (per Writing F3).
        """
        _require_auth_config()
        for project_dir in projects:
            _validate_project_root(project_dir)
        files: list[str] = []
        errors: list[dict[str, str]] = []
        for project_dir in projects:
            root = Path(project_dir)
            if not web_enabled(root):
                raise ValueError(
                    f"Web adapter not enabled at {root}. "
                    f"Add `package.json` or set `[tool.crackerjack.web] enabled = true`."
                )
            delims, _ = await asyncio.to_thread(_load_jinja_config, root)
            for path in root.rglob("*"):
                # Symlink guard: do not follow symlinks (Security F-1).
                if path.is_symlink():
                    continue
                if not path.is_file() or path.suffix not in JINJA_SUFFIXES:
                    continue
                try:
                    raw = await asyncio.to_thread(path.read_text)
                    formatted = await asyncio.to_thread(format_template, raw, delims)
                    if formatted != raw and not dry_run:
                        await asyncio.to_thread(path.write_text, formatted)
                    files.append(str(path))
                except (OSError, UnicodeDecodeError) as exc:
                    errors.append({"path": str(path), "kind": type(exc).__name__, "error": str(exc)})
        return {"files": files, "errors": errors, "mode": "dry_run" if dry_run else "write"}
```

- [ ] **Step 4: Update `test_register_language_tools_registers_three_tools` → `_seven_tools`**

Find the existing assertion in `tests/mcp/tools/test_language_tools.py` and update it to assert all 7 tool names (swift_bump_version, swift_list_hooks, detect_languages, kotlin_bump_version, kotlin_list_hooks, check_web_lint, format_jinja_templates). Note: existing test name is "three_tools" because Phase 2 had 3 tools; Phase 3 (Kotlin) silently failed to rename it (carry-over).

- [ ] **Step 5: Run all MCP tests to verify they pass**

Run: `cd /Users/les/Projects/crackerjack && /Users/les/Projects/crackerjack/.venv/bin/pytest tests/mcp/tools/test_language_tools.py tests/adapters/test_registry.py -v`
Expected: All pass (13 prior + 4 new web = 17 in test_language_tools.py, plus the 1 new test_registry.py entry = 18 total).

- [ ] **Step 6: Commit**

```bash
cd /Users/les/Projects/crackerjack
git add crackerjack/mcp/tools/language_tools.py tests/mcp/tools/test_language_tools.py tests/adapters/test_registry.py
git -c user.email=les@wedgwoodwebworks.com -c user.name=les commit -m "feat(mcp): check_web_lint (read-only) + format_jinja_templates (dry_run default, Web guard, symlink safe)"
```

---

## Task 7: Verification — fixtures + golden-master corpus + CHANGELOG + smoke

**Files:**
- Create: `tests/fixtures/web-vanilla/{package.json,.stylelintrc.json,.eslintrc.json,tsconfig.json,src/style.css,src/app.ts,src/index.html}`
- Create: `tests/fixtures/web-vanilla/templates/{basic.html,custom_delimiters.html,whitespace.html}` (NOT nested under tests/)
- Create: `tests/fixtures/jinja-templates/{basic,custom_delimiters,whitespace}.html.j2` + matching `.expected` siblings (golden-master corpus)
- Modify: `CHANGELOG.md` (add Phase 4 entry under [Unreleased])
- Create: `tests/adapters/web/test_web_vanilla_fixture.py`

Per Phase 4 Testing HIGH-2 + Simplification F9: golden-master Jinja tests are mandatory. The Rev 1 fixtures were decorative — Rev 2 creates real golden outputs and tests them.

Per Phase 4 simplification F9: Jinja templates live in `tests/fixtures/web-vanilla/templates/` (NOT `tests/fixtures/web-vanilla/tests/fixtures/jinja-templates/` — the Rev 1 nesting was wrong). The golden-master corpus lives at `tests/fixtures/jinja-templates/` as a separate top-level fixture set.

Per Phase 4 Testing HIGH-3 (decorative fixture): add real-CLI smoke tests gated on availability.

- [ ] **Step 1: Create web-vanilla fixture**

Create the following files (content elided; standard fixture content — `package.json` with `stylelint ^15`, `eslint ^8`, `typescript ^5`, `html-validate ^8` pinned; minimal `.stylelintrc.json`, `.eslintrc.json`, `tsconfig.json`; minimal `src/style.css` with one valid rule and one invalid, `src/app.ts` clean, `src/index.html` valid).

```bash
mkdir -p tests/fixtures/web-vanilla/src
mkdir -p tests/fixtures/web-vanilla/templates
# (Create each file; minimal content per Web fixture convention.)
```

Templates (NOT under tests/fixtures/ nesting):

`tests/fixtures/web-vanilla/templates/basic.html`:
```
{# standard comment #}
{% if x %}
A
{% else %}
B
{% endif %}
```

`tests/fixtures/web-vanilla/templates/custom_delimiters.html`:
```
[% if x %]
A
[% endif %]
```

`tests/fixtures/web-vanilla/templates/whitespace.html`:
```
A {%- if x -%} B
{%- endif -%}
```

- [ ] **Step 2: Create golden-master Jinja corpus**

Create three input files plus three matching `.expected` siblings. The `.expected` files are the canonical outputs of `format_template` on the inputs — they are committed and tested against. (This requires running `format_template` once and committing the output.)

```bash
mkdir -p tests/fixtures/jinja-templates
# (Create each input file + generate its .expected sibling by running format_template once
# in the venv and capturing the output.)
```

After creating, add a parametrized golden-master test to `tests/adapters/web/test_jinja_formatter.py`:

```python
@pytest.mark.parametrize(
    "fixture_name",
    ["basic.html.j2", "custom_delimiters.html.j2", "whitespace.html.j2"],
)
class TestGoldenMaster:
    CORPUS = Path(__file__).parent.parent.parent / "fixtures" / "jinja-templates"

    def test_format_matches_golden_master(self, fixture_name: str) -> None:
        """Per spec Testing F9: round-trip + golden-master expected output."""
        src = (self.CORPUS / fixture_name).read_text()
        expected = (self.CORPUS / f"{fixture_name}.expected").read_text()
        actual = format_template(src)
        assert actual == expected
        # Round-trip: golden output is its own fixed point.
        assert format_template(actual) == actual
```

Run: `cd /Users/les/Projects/crackerjack && /Users/les/Projects/crackerjack/.venv/bin/pytest tests/adapters/web/test_jinja_formatter.py -v`
Expected: 13 passed (10 + 3 golden-master).

- [ ] **Step 3: Create fixture-reference tests**

```python
# tests/adapters/web/test_web_vanilla_fixture.py
"""Web fixture smoke + fixture-reference contract."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from crackerjack.adapters.web import WebAdapter
from crackerjack.adapters.web.hooks import web_hooks

FIXTURE = Path(__file__).parent.parent.parent / "fixtures" / "web-vanilla"


class TestFixtureDetection:
    def test_fixture_exists(self) -> None:
        assert FIXTURE.is_dir()

    def test_adapter_detects_fixture(self) -> None:
        assert WebAdapter().detect(FIXTURE) is True

    def test_capabilities_exposes_four_hooks(self) -> None:
        caps = WebAdapter().capabilities(FIXTURE)
        assert len(caps.hooks) == 4


@pytest.mark.real_web_smoke
class TestRealCli:
    """Opt-in smoke tests: skipped if npx or the per-tool CLI is unavailable."""

    def test_stylelint_runs_against_fixture(self) -> None:
        if shutil.which("npx") is None:
            pytest.skip("npx not available")
        result = subprocess.run(
            ["npx", "--no", "stylelint", str(FIXTURE / "src" / "style.css")],
            capture_output=True,
            text=True,
            cwd=FIXTURE,
        )
        # stylelint exits 0 (clean) or 2 (issues found). Anything else = crash.
        assert result.returncode in (0, 2), f"stylelint crashed: {result.stderr}"

    def test_tsc_compiles_fixture(self) -> None:
        if shutil.which("npx") is None:
            pytest.skip("npx not available")
        result = subprocess.run(
            ["npx", "--no", "tsc", "--noEmit"],
            capture_output=True,
            text=True,
            cwd=FIXTURE,
        )
        assert result.returncode == 0, f"tsc failed: {result.stderr}"
```

Add the `real_web_smoke` marker to `pyproject.toml`:
```toml
[tool.pytest.ini_options]
markers = [
    "real_web_smoke: requires npx + stylelint + eslint + tsc + html-validate",
]
```

- [ ] **Step 4: Run full Phase 4 test suite**

Run: `cd /Users/les/Projects/crackerjack && /Users/les/Projects/crackerjack/.venv/bin/pytest tests/adapters/web/ tests/mcp/tools/test_language_tools.py tests/adapters/test_registry.py --cov=crackerjack.adapters.web --cov=crackerjack.mcp.tools.language_tools --cov-report=term-missing -q`
Expected: ~55 passed (8 detection + 12 hooks + 13 formatter + 8 adapter + 17 mcp + 1 registry + ~4 fixture reference = ~63); coverage ≥ 89%.

- [ ] **Step 5: Run crackerjack quality gate**

Run: `cd /Users/les/Projects/crackerjack && /Users/les/Projects/crackerjack/.venv/bin/python -m crackerjack run -p minor --no-commit`
Expected: All quality checks pass.

- [ ] **Step 6: Update CHANGELOG**

Add to `CHANGELOG.md` under `## [Unreleased]`:

```markdown
### Added (Phase 4)

- Web language adapter (`crackerjack.adapters.web`): activates on projects with
  `package.json` at root OR `[tool.crackerjack.web] enabled = true` opt-in.
- 4 CLI hooks: `web.stylelint`, `web.eslint`, `web.tsc`, `web.html_validate`.
  Each emits issues via JSON output parsing (`stylelint -f json`,
  `eslint -f json`, `html-validate -f json`, `tsc --noEmit` line-oriented).
  When the CLI is unresolvable, `WebHookError` is raised with install
  instructions (Swift/Kotlin precedent — no Python fallbacks).
- Jinja template formatter (`format_template`): Tier 1 only (trailing newline
  + no trailing whitespace + preserve `{%-` / `-%}` markers). Uses
  `Environment.lex()` as a syntax-validation gate; Tier 2 normalization
  (`[tool.crackerjack.jinja] normalize = true`) is deferred.
- 2 new MCP tools: `check_web_lint` (read-only, returns hook metadata) and
  `format_jinja_templates` (mutation, `dry_run=True` default, per-project
  delimiter config from `[tool.crackerjack.jinja]`, symlink guard).
- `jinja2>=3.1.6` direct dependency (was previously transitive).

### Changed

- `crackerjack.language_adapters` entry-point group now includes the Web adapter
  (joining Python, Swift, and Kotlin from earlier phases).

### Not yet shipped

- Tier 2 normalization (`[tool.crackerjack.jinja] normalize = true`).
- Shared `jinja-test-fixtures/` Bodai sibling package (spec line 420).
- PyCharm parity script (spec Jinja F10).
- CLI subcommand `crackerjack web jinja format` (CLI mirror per spec).
```

- [ ] **Step 7: Final commit**

```bash
cd /Users/les/Projects/crackerjack
git add tests/fixtures/web-vanilla/ tests/fixtures/jinja-templates/ tests/adapters/web/test_web_vanilla_fixture.py CHANGELOG.md pyproject.toml
git -c user.email=les@wedgwoodwebworks.com -c user.name=les commit -m "test(adapters.web): web-vanilla fixture + golden-master Jinja corpus + Phase 4 CHANGELOG"
```

---

## Self-Review

| Spec item | Plan coverage | Status |
|---|---|---|
| Web detection guard (Writing F3) | Task 2 | ✓ |
| Hooks: stylelint, eslint, tsc, html-validate (no fused) | Task 3 | ✓ (split per API CRITICAL / Web BLOCKER-5) |
| CLI-only hooks, no Python fallbacks | Task 3 | ✓ (Simplification F6 + Swift/Kotlin precedent) |
| Hook JSON output parsing | Task 3 parsers | ✓ (closes `mcp-surface-health-illusion` per Web HIGH-1) |
| Modern `npx --no` spelling | Task 3 `_resolve` | ✓ (closes MEDIUM-4) |
| `_resolve()` single resolver replaces inverted guard | Task 3 | ✓ (closes Web BLOCKER-3 + Security F-4) |
| Hybrid pattern note: Phase 4 ships non-hybrid | Spec Revision Notes | ✓ (explicit) |
| MCP tool wrappers nested inside `register_language_tools` | Task 6 | ✓ (closes Web BLOCKER-6) |
| MCP tool imports at module top | Task 6 | ✓ (closes MCP MEDIUM-3) |
| MCP tests sync `def` with `mock.patch.dict(os.environ, ..., clear=True)` | Task 6 | ✓ (closes Web BLOCKER-7 + Simplification F3) |
| `format_jinja_templates` enforces Web detection at MCP layer | Task 6 | ✓ (closes MCP HIGH 1 + A11y F12) |
| `format_jinja_templates` reads `[tool.crackerjack.jinja]` config | Task 6 | ✓ (closes A11y F1 + Web HIGH-4) |
| `format_jinja_templates` `dry_run=True` default + symlink guard | Task 6 | ✓ (closes A11y F4 + Security F-1) |
| Happy-path test reads back file mutation | Task 6 | ✓ (closes MCP HIGH 2) |
| `test_detect_languages_returns_adapter_names` asserts all 4 adapters | Task 6 | ✓ (closes MCP MEDIUM 2 + Phase 3 carry-over) |
| Jinja F1: `lex()` for validation, Tier 1 raw-source ops | Task 4 | ✓ (closes Web BLOCKER-1 + Simplification F2) |
| Tier 2 deferred | Spec Revision Notes | ✓ (closes Web BLOCKER-2 + Simplification F1 — 5 lenses agree) |
| Jinja F2: all 6 delimiter kwargs | Task 4 `_env` | ✓ |
| `keep_trailing_newline=True` | Task 4 `_env` | ✓ (closes Simplification F12) |
| Round-trip invariant + golden-master | Task 7 | ✓ (closes Testing HIGH-2 + Web HIGH-6 + Simplification F9) |
| `jinja2>=3.1.6` direct dep | Task 1 | ✓ |
| `WebHookError` raised + tested | Task 3 | ✓ (closes Writing LOW-5 / A11y F16) |
| No lifecycle (spec line 65) | Task 5 | ✓ |
| `has_lifecycle=False` and `version_source=None` | Task 5 | ✓ |
| `name = "web"` (mirrors Swift's bare-assignment style; Kotlin uses annotated form — both work) | Task 5 | ✓ (closes Web MEDIUM-5) |
| `detection.py` folded into `__init__.py` | Task 2 | ✓ (closes Simplification F10) |
| No `python_fallbacks.py` module | Task 3 absent | ✓ (closes Simplification F6) |
| Real-CLI smoke tests gated on availability | Task 7 | ✓ (closes Testing HIGH-3) |
| CHANGELOG entry with structured categories | Task 7 | ✓ (closes A11y F9) |
| Spec Revision Notes populated | Below | ✓ |
| Self-Review section | This section | ✓ |
| `default_pii_severity` / `default_test_mode` carried over | N/A | ✓ |
| `_validate_project_root` reuse (Phase 3 fail-closed) | Task 6 | ✓ (per Phase 3 ruling) |
| `_require_auth_config` reuse | Task 6 | ✓ (per Phase 3 ruling) |
| `monkeypatch.setattr` for test env isolation | Task 2-7 | ✓ (per spec Testing F3) |
| No shell, argv list only | Task 3 | ✓ (per Global Constraints) |

## Spec Revision Notes

The following items deviate from spec Rev 2 (`b00b36f0`) and require a spec amendment in the next revision pass:

1. **Tier 2 normalization deferred.** Spec Jinja F3 lists Tier 2 ("one space inside delimiters, blank line between block-level tags") as opt-in via `[tool.crackerjack.jinja] normalize = true`. Phase 4 ships **Tier 1 only**. The Phase 4 multi-agent review (5 lenses: Writing HIGH-1, Web BLOCKER-2, Simplification F1 + Q3, A11y F2) independently reproduced that the regex-based Tier 2 implementation fundamentally corrupts templates (`{%if x%}` → `{% f  %}`). Tier 2 needs a token-walk implementation + golden-master corpus to ship safely. `format_template` therefore omits the `normalize` parameter. The `_load_jinja_config` helper returns `(delimiters, False)` for the second value; `False` is the always-on Tier 1 mode.

2. **No Python fallbacks for hooks.** Spec Writing F2 implies Phase 4 hooks may have Python fallbacks (the "Hybrid pattern (CLI primary, Python fallback)" wording). Phase 4 ships **CLI-only hooks** with `cli_required=True, fallback=None` per the Swift/Kotlin precedent. The Phase 4 review (5 lenses: Simplification F6, Web HIGH-7, Testing F1 carry-over, A11y F5, Web BLOCKER-3) independently concluded the brace-counting and HTML regex fallbacks are naive, produce false positives on real code, and are unreachable in the default npx-prefixed configuration. When CLI resolution returns `None`, `WebHookError` is raised with install instructions. Spec Testing F3's "mandatory two-path pair per hook" is therefore **N/A** for Phase 4 — explicitly recorded so the spec's Testing F3 wording can be amended in the next revision pass.

3. **`web.eslint_tsc` split into `web.eslint` + `web.tsc`.** Spec Web section line 365 says "eslint + tsc --noEmit" as a single bullet but never names a single combined hook. Phase 4 multi-agent review (5 lenses: API CRITICAL, Web BLOCKER-5, Writing HIGH-2, Security F-4, Testing LOW-3) independently found that the `Hook.cli_command` shape is single-argv-one-hook, and a literal `";"` in argv list is not interpreted as a command separator by `subprocess.run`. Phase 4 splits into 4 hooks total: `web.stylelint`, `web.eslint`, `web.tsc`, `web.html_validate`. Independent timeouts and pass/fail; a JS-only project naturally drops `web.tsc`.

4. **`detection.py` module absent.** Spec line 96-101 names the module-only entry-point form. Phase 4 follows Swift/Kotlin precedent: no `detection.py` module. `web_enabled()` and `package_json_present()` are in `crackerjack/adapters/web/__init__.py` (~12 lines). Keeps the Phase 4 adapter symmetric with the other two adapters.

5. **PyCharm parity script deferred.** Spec Jinja F10 lists PyCharm parity as a Phase 4 acceptance criterion. Phase 4 ships without it; deferred to a separate plan that can script PyCharm CLI invocation.

6. **CLI subcommand for `crackerjack web jinja format` deferred.** Spec line 55 requires "CLI + MCP mirror for every new feature"; spec Data Flow line 572 names the CLI subcommand. Phase 4 ships the MCP tool only; CLI subcommand deferred to a separate plan.

7. **Shared `jinja-test-fixtures/` Bodai sibling package deferred.** Spec line 420 lists this as the "Phase 4 deliverable". Phase 4 ships 3 inline fixture files inside `tests/fixtures/web-vanilla/templates/` + a 6-file golden-master corpus at `tests/fixtures/jinja-templates/` instead. When the sibling package lands, the inline fixtures migrate.

8. **CRLF preservation deferred.** Spec Jinja F1 caveat says "lex() normalizes CRLF → LF — preserve CRLF flag from raw input if needed." Phase 4 does not currently handle CRLF inputs; `_apply_tier1("hello\r\n")` returns `"hello\n"` because Python's `str.splitlines()` strips the line terminator. The spec wording is ambiguous on whether preservation is mandatory — recorded here so the next spec revision can clarify.

9. **Spec line 713 acceptance target deferred.** Spec line 713 names "Test on `fastblocks`, `splashstand`" as a Phase 4 acceptance criterion. Phase 4 ships only a synthetic `tests/fixtures/web-vanilla/` fixture; real-world fastblocks and splashstand validation is deferred to a separate plan (or to Phase 5 if these repos become available locally).

---

REVIEW_COMPLETE
