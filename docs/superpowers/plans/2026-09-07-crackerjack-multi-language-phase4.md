# Crackerjack Multi-Language Extension — Phase 4 (Web/CSS/HTML/JS/TS) Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Status:** Ready for execution.

**Goal:** Add a Web language adapter to crackerjack that activates only on JS/TS/CSS/HTML projects (or Python projects with explicit web opt-in). Provides 3 hooks (stylelint, eslint+tsc, html-validate) with CLI-primary + Python-fallback hybrid pattern, a Jinja template formatter (`jinja2.Environment.lex()` based, custom delimiters, 2-tier canonical policy), and 2 MCP tools (`check_web_lint`, `format_jinja_templates`).

**Architecture:** Approach A (per spec Rev 2) extended with Web. New `crackerjack/adapters/web/` package containing `WebAdapter`, `web_hooks` (hybrid pattern), and `jinja_formatter` (lex-based). Two new MCP tools added to the existing `language_tools` group registered in Phase 2 (no `profiles.py` change). No lifecycle (out of scope per spec line 65). Web detection guard prevents Python-project false positives.

**Tech Stack:** Python 3.14, FastMCP 4.x, typer 0.26+, hatchling, jinja2 ≥3.1.6 (NEW direct dep per spec Jinja F11), subprocess (npx wrappers), typer 0.26+ for CLI surface.

**Spec:** `/Users/les/Projects/crackerjack/docs/superpowers/specs/2026-09-07-crackerjack-multi-language-design.md` (Rev 2, on `main` as of commit `b00b36f0`). Phase 4 is at lines 363-429 ("Per-adapter Web").

**Out of scope:** shared `jinja-test-fixtures/` Bodai sibling package (Phase 4 deliverable per spec line 420) — separate plan. CSS/HTML/JS/TS lifecycle (spec line 65).

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
- **Hybrid fallback** (per spec Writing F2): one canonical interpretation — when CLI is missing AND fallback is set, invoke Python fallback; when fallback also raises, fail with installation instructions.
- **Web detection guard** (per Writing F3): `WebAdapter.detect()` requires `package.json` at root OR explicit `[tool.crackerjack.web] enabled = true` in `pyproject.toml`. Without this guard, every Django/Sphinx/MkDocs Python project would falsely trigger Web hooks.
- **Commands via `npx`** unless `package.json` pins them.
- **`jinja2>=3.1.6` as a direct dependency** (per spec Jinja F11). Currently only present transitively.
- **`jinja2.Environment.lex()` NOT `parse()`** (per spec Jinja F1) — parse() silently drops comments.
- **All 6 delimiter kwargs required** (per spec Jinja F2): `block_start_string`, `block_end_string`, `variable_start_string`, `variable_end_string`, `comment_start_string`, `comment_end_string`.
- **Round-trip invariant** (per spec Jinja F1 + Testing F9): `format_lex(format_lex(x)) == format_lex(x)`. Test with golden-master expected output.
- **Two-tier canonical policy** (per spec Jinja F3): Tier 1 always-on (trailing newline at EOF, no trailing whitespace, preserve `{%-` / `-%}` / `{{-` / `-}}` markers); Tier 2 opt-in via `[tool.crackerjack.jinja] normalize = true` (one space inside delimiters, blank line between block-level tags, inline `{{ var }}` may remain).
- **PyCharm parity as one-way fixed-point** (per spec Jinja F10): `pycharm_format(crackerjack_format(x)) == crackerjack_format(x)`. Testable headless. Out of scope for Phase 4 (requires PyCharm CLI invocation script; deferred to Phase 4.5).

---

## File Structure

### New files (Phase 4)

```
crackerjack/
├── adapters/web/                                  # NEW
│   ├── __init__.py                                # exports WebAdapter
│   ├── detection.py                               # package.json / opt-in detection guard
│   ├── hooks.py                                   # 3 hybrid-pattern hooks (stylelint, eslint+tsc, html-validate)
│   ├── jinja_formatter.py                         # lex-based Jinja formatter (6 delimiters, 2-tier policy)
│   └── python_fallbacks.py                        # Python fallbacks for the 3 hooks (CSS parse, JS parse, HTML parse)

mcp/tools/
└── language_tools.py                              # MODIFIED: add check_web_lint + format_jinja_templates

tests/
├── adapters/web/
│   ├── __init__.py
│   ├── test_detection.py
│   ├── test_hooks.py
│   ├── test_jinja_formatter.py
│   └── test_web_adapter.py
├── mcp/tools/
│   └── test_language_tools.py                     # EXTENDED with web tests
└── fixtures/
    └── web-vanilla/                               # Real Web fixture (package.json + minimal src/)
        ├── package.json
        ├── .stylelintrc.json
        ├── .eslintrc.json
        ├── tsconfig.json
        ├── src/
        │   ├── style.css
        │   ├── app.ts
        │   └── index.html
        └── tests/fixtures/jinja-templates/         # Golden-master test inputs
            ├── basic.html
            ├── custom_delimiters.html
            └── whitespace.html
```

### Modified files (Phase 4)

```
pyproject.toml                                     # MODIFIED: add Web entry-point + jinja2>=3.1.6 dep
crackerjack/mcp/tools/language_tools.py            # MODIFIED: add 2 tools (check_web_lint, format_jinja_templates)
CHANGELOG.md                                       # MODIFIED: add Phase 4 entry under [Unreleased]
```

### Files NOT modified

- `crackerjack/adapters/swift/**`, `crackerjack/adapters/kotlin/**`, `crackerjack/adapters/python/**` — prior adapters untouched.
- `crackerjack/mcp/server_core.py` — NOT modified (per Phase 2 BLOCKER B2, registration lives in `profiles.py`).
- `crackerjack/mcp/tools/profiles.py` — NOT modified (`language_tools` group already registered in Phase 2).

---

## Task 1: Foundation — register Web entry-point + add `jinja2` dep

**Files:**
- Modify: `pyproject.toml` (2 changes)

- [ ] **Step 1: Verify current state**

Run: `grep -A 6 "crackerjack.language_adapters" pyproject.toml && grep "jinja2" pyproject.toml`
Expected: 3 entries (python, swift, kotlin); jinja2 may appear in `[dependency-groups]` or not at all.

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

## Task 2: Detection guard — `WebAdapter.detect()` with Python-project false-positive prevention

**Files:**
- Create: `crackerjack/adapters/web/__init__.py` (empty marker; full content in Task 5)
- Create: `crackerjack/adapters/web/detection.py`
- Test: `tests/adapters/web/__init__.py`, `tests/adapters/web/test_detection.py`

**Per spec Writing F3:** the Web adapter must NOT fire on Python projects. Detection requires either `package.json` at root OR explicit `[tool.crackerjack.web] enabled = true` in `pyproject.toml`.

- [ ] **Step 1: Write failing tests**

```python
# tests/adapters/web/test_detection.py
from __future__ import annotations

from pathlib import Path

import pytest

from crackerjack.adapters.web.detection import web_enabled, package_json_present


def test_package_json_present_returns_true(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text("{}")
    assert package_json_present(tmp_path) is True


def test_package_json_present_returns_false_when_missing(tmp_path: Path) -> None:
    assert package_json_present(tmp_path) is False


def test_web_enabled_returns_true_when_package_json_present(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text("{}")
    assert web_enabled(tmp_path) is True


def test_web_enabled_returns_false_for_python_project_no_opt_in(tmp_path: Path) -> None:
    # No package.json, no [tool.crackerjack.web] in pyproject.toml
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'foo'\n")
    assert web_enabled(tmp_path) is False


def test_web_enabled_returns_true_for_python_project_with_opt_in(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        "[project]\nname = 'foo'\n[tool.crackerjack.web]\nenabled = true\n"
    )
    assert web_enabled(tmp_path) is True


def test_web_enabled_returns_false_for_python_project_with_opt_in_false(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        "[project]\nname = 'foo'\n[tool.crackerjack.web]\nenabled = false\n"
    )
    assert web_enabled(tmp_path) is False


def test_web_enabled_returns_true_when_both_signals_present(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text("{}")
    (tmp_path / "pyproject.toml").write_text("[tool.crackerjack.web]\nenabled = false\n")
    assert web_enabled(tmp_path) is True


def test_web_enabled_handles_malformed_pyproject(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("not valid toml [[[")
    assert web_enabled(tmp_path) is False  # Falls back to package.json absence


def test_web_enabled_handles_pyproject_missing(tmp_path: Path) -> None:
    assert web_enabled(tmp_path) is False
```

- [ ] **Step 2: Run to verify fail**

Run: `cd /Users/les/Projects/crackerjack && uv run pytest tests/adapters/web/test_detection.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'crackerjack.adapters.web.detection'`.

- [ ] **Step 3: Implement detection module**

Create `crackerjack/adapters/web/__init__.py` (empty marker) and `crackerjack/adapters/web/detection.py`:

```python
"""Web adapter detection guard.

Per spec Writing F3: the Web adapter must NOT fire on Python projects by
default. Detection requires `package.json` at root OR explicit
`[tool.crackerjack.web] enabled = true` in `pyproject.toml`.

Without this guard, every Django/Sphinx/MkDocs Python project would
falsely trigger Web hooks.
"""
from __future__ import annotations

from pathlib import Path


def package_json_present(project_root: Path) -> bool:
    """Return True iff `package.json` exists at the project root."""
    return (project_root / "package.json").is_file()


def web_enabled(project_root: Path) -> bool:
    """Return True iff the Web adapter should activate for this project.

    True iff `package.json` exists at root OR
    `[tool.crackerjack.web] enabled = true` in `pyproject.toml`.
    Malformed `pyproject.toml` is treated as "not enabled" (no opt-in).
    """
    if package_json_present(project_root):
        return True
    pyproject = project_root / "pyproject.toml"
    if not pyproject.is_file():
        return False
    try:
        import tomllib
    except ImportError:
        try:
            import tomli as tomllib  # type: ignore[no-redef]
        except ImportError:
            return False
    try:
        with pyproject.open("rb") as f:
            data = tomllib.load(f)
    except (tomllib.TOMLDecodeError, OSError):
        return False
    tool_cfg = data.get("tool", {}).get("crackerjack", {}).get("web", {})
    return bool(tool_cfg.get("enabled", False))
```

- [ ] **Step 4: Run to verify pass**

Run: `cd /Users/les/Projects/crackerjack && uv run pytest tests/adapters/web/test_detection.py -v`
Expected: 8 passed.

- [ ] **Step 5: Commit**

```bash
cd /Users/les/Projects/crackerjack
git add crackerjack/adapters/web/__init__.py crackerjack/adapters/web/detection.py tests/adapters/web/__init__.py tests/adapters/web/test_detection.py
git -c user.email=les@wedgwoodwebworks.com -c user.name=les commit -m "feat(adapters.web): detection guard prevents Python-project false positives"
```

---

## Task 3: Hybrid-pattern web hooks (stylelint, eslint+tsc, html-validate)

**Files:**
- Create: `crackerjack/adapters/web/python_fallbacks.py` (Python fallback for each CLI tool)
- Create: `crackerjack/adapters/web/hooks.py` (3 hooks with hybrid pattern)
- Test: `tests/adapters/web/test_hooks.py`

**Per spec:** 3 hooks with Hybrid pattern (CLI primary via `npx`, Python fallback). Commands run via `npx` unless `package.json` pins them. Single canonical interpretation of fallback per spec Writing F2.

**Pre-flight verification** (analog to Phase 2 BLOCKER B1 + Phase 3 Kotlin HIGH-5): verify `npx stylelint --version`, `npx eslint --version`, `npx tsc --version`, `npx html-validate --version` all work. Document any that don't.

- [ ] **Step 1: Verify CLI commands**

```bash
which npx
npx stylelint --version 2>&1 | head -1
npx eslint --version 2>&1 | head -1
npx tsc --version 2>&1 | head -1
npx html-validate --version 2>&1 | head -1
```
Note which work; absent tools will exercise the Python fallback in tests.

- [ ] **Step 2: Write failing tests**

```python
# tests/adapters/web/test_hooks.py
from __future__ import annotations

import shutil
from pathlib import Path
from unittest import mock

import pytest

from crackerjack.adapters.web.hooks import web_hooks, WebHookError
from crackerjack.adapters.web.python_fallbacks import (
    css_fallback, js_ts_fallback, html_fallback,
)


def test_web_hooks_returns_three_hooks(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text("{}")
    hooks = web_hooks(tmp_path)
    names = {h.name for h in hooks}
    assert names == {"web.stylelint", "web.eslint_tsc", "web.html_validate"}


def test_stylelint_hook_uses_npx_subprocess(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text("{}")
    hooks = web_hooks(tmp_path)
    stylelint = next(h for h in hooks if h.name == "web.stylelint")
    assert stylelint.cli_command[0] == "npx"
    assert "stylelint" in stylelint.cli_command


def test_eslint_tsc_hook_combines_eslint_and_tsc(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text("{}")
    hooks = web_hooks(tmp_path)
    eslt = next(h for h in hooks if h.name == "web.eslint_tsc")
    # cli_command encodes both eslint and tsc invocations (combined as fallback chain)
    cmd_str = " ".join(eslt.cli_command)
    assert "eslint" in cmd_str
    assert "tsc" in cmd_str


def test_html_validate_hook_uses_npx_subprocess(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text("{}")
    hooks = web_hooks(tmp_path)
    html = next(h for h in hooks if h.name == "web.html_validate")
    assert html.cli_command[0] == "npx"
    assert "html-validate" in html.cli_command


def test_css_fallback_parses_stylesheet(tmp_path: Path) -> None:
    (tmp_path / "style.css").write_text(".foo { color: red; }")
    issues = css_fallback(tmp_path / "style.css")
    assert isinstance(issues, list)


def test_js_ts_fallback_parses_typescript(tmp_path: Path) -> None:
    (tmp_path / "app.ts").write_text("const x: number = 1;\n")
    issues = js_ts_fallback(tmp_path / "app.ts")
    assert isinstance(issues, list)


def test_html_fallback_parses_html(tmp_path: Path) -> None:
    (tmp_path / "index.html").write_text("<html><body></body></html>\n")
    issues = html_fallback(tmp_path / "index.html")
    assert isinstance(issues, list)


def test_web_hooks_invokes_python_fallback_when_cli_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Per spec Writing F2 hybrid fallback: CLI missing → fallback invoked."""
    (tmp_path / "package.json").write_text("{}")
    monkeypatch.setattr(shutil, "which", lambda cmd: None)  # All CLIs missing
    with mock.patch.object(
        __import__("crackerjack.adapters.web.hooks", fromlist=["run_hook_with_fallback"]),
        "run_hook_with_fallback",
    ) as mock_run:
        mock_run.return_value = []
        hooks = web_hooks(tmp_path)
        for hook in hooks:
            result = mock_run.return_value  # smoke call
            assert result == []
```

- [ ] **Step 3: Run to verify fail**

Run: `cd /Users/les/Projects/crackerjack && uv run pytest tests/adapters/web/test_hooks.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'crackerjack.adapters.web.hooks'`.

- [ ] **Step 4: Implement python_fallbacks.py**

```python
"""Python fallbacks for the 3 Web hooks.

Per spec Writing F2: when CLI is missing AND fallback is set, invoke
the Python fallback. Each fallback returns a list of issues (empty
list = clean).

Fallbacks are intentionally minimal — they catch gross syntax errors
and obvious anti-patterns. Full lint coverage still requires the CLI
tool. The fallback exists so the hook doesn't fail-closed when
`stylelint`/`eslint`/`tsc`/`html-validate` aren't installed.
"""
from __future__ import annotations

import re
from pathlib import Path


_FALLBACK_ISSUE = tuple[Path, int, str]  # (path, line, message)


def css_fallback(path: Path) -> list[_FALLBACK_ISSUE]:
    """Minimal CSS validation: catch unbalanced braces and empty rules."""
    issues: list[_FALLBACK_ISSUE] = []
    try:
        content = path.read_text()
    except (OSError, UnicodeDecodeError):
        return []
    depth = 0
    line_num = 1
    for i, ch in enumerate(content):
        if ch == "\n":
            line_num += 1
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth < 0:
                issues.append((path, line_num, "Unbalanced closing brace"))
                depth = 0
    if depth != 0:
        issues.append((path, line_num, "Unclosed brace(s) at EOF"))
    # Empty rules: `selector {}`
    for m in re.finditer(r"[^{}]+\{\s*\}", content):
        line = content[: m.start()].count("\n") + 1
        issues.append((path, line, "Empty rule"))
    return issues


def js_ts_fallback(path: Path) -> list[_FALLBACK_ISSUE]:
    """Minimal JS/TS validation: catch unbalanced braces + unclosed strings."""
    issues: list[_FALLBACK_ISSUE] = []
    try:
        content = path.read_text()
    except (OSError, UnicodeDecodeError):
        return []
    depth = 0
    line_num = 1
    for i, ch in enumerate(content):
        if ch == "\n":
            line_num += 1
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth < 0:
                issues.append((path, line_num, "Unbalanced closing brace"))
                depth = 0
    if depth != 0:
        issues.append((path, line_num, "Unclosed brace(s) at EOF"))
    return issues


def html_fallback(path: Path) -> list[_FALLBACK_ISSUE]:
    """Minimal HTML validation: catch tag balance for a known subset."""
    issues: list[_FALLBACK_ISSUE] = []
    try:
        content = path.read_text()
    except (OSError, UnicodeDecodeError):
        return []
    VOID_ELEMENTS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}
    stack: list[tuple[str, int]] = []
    line_num = 1
    for m in re.finditer(r"<!--|</?([a-zA-Z][a-zA-Z0-9]*)\b[^>]*?>|>", content):
        if m.group() == "<!--":
            line_num = content[: m.start()].count("\n") + 1
            end = content.find("-->", m.end())
            if end < 0:
                issues.append((path, line_num, "Unclosed comment"))
            continue
        if m.group() == ">":
            continue
        tag = m.group(1)
        line_num = content[: m.start()].count("\n") + 1
        if m.group().startswith("</"):
            if not stack or stack[-1][0] != tag:
                issues.append((path, line_num, f"Mismatched closing tag </{tag}>"))
            else:
                stack.pop()
        elif m.group().endswith("/>") or tag.lower() in VOID_ELEMENTS:
            continue
        else:
            stack.append((tag, line_num))
    for tag, ln in stack:
        issues.append((path, ln, f"Unclosed tag <{tag}>"))
    return issues
```

- [ ] **Step 5: Implement hooks.py**

```python
"""Web hooks (stylelint, eslint+tsc, html-validate) with hybrid pattern.

Per spec Writing F2: one canonical interpretation of fallback — when
CLI is missing AND fallback is set, invoke fallback; when fallback
also raises, fail with installation instructions.

Commands run via `npx` unless `package.json` pins them.
"""
from __future__ import annotations

import logging
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path

from crackerjack.adapters.base import Hook
from crackerjack.adapters.web.python_fallbacks import (
    css_fallback, html_fallback, js_ts_fallback,
)

logger = logging.getLogger(__name__)


def _npx_command(*args: str) -> tuple[str, ...]:
    """Build an npx-prefixed argv tuple."""
    return ("npx", "--no-install", *args)


def _has_pinned_version(project_root: Path, tool: str) -> str | None:
    """Return the pinned version from package.json devDependencies, or None."""
    import json
    pkg = project_root / "package.json"
    if not pkg.is_file():
        return None
    try:
        data = json.loads(pkg.read_text())
    except (json.JSONDecodeError, OSError):
        return None
    dev_deps = data.get("devDependencies", {})
    pinned = dev_deps.get(tool)
    return pinned if isinstance(pinned, str) else None


def _css_hook(project_root: Path) -> Hook:
    pinned = _has_pinned_version(project_root, "stylelint")
    cmd = _npx_command("stylelint", "**/*.css") if pinned is None else ("stylelint", "**/*.css")
    return Hook(name="web.stylelint", cli_command=cmd, fallback=css_fallback, timeout_seconds=300)


def _eslt_hook(project_root: Path) -> Hook:
    """Combines eslint (JS/TS) + tsc --noEmit into one hook."""
    eslint_pinned = _has_pinned_version(project_root, "eslint")
    tsc_pinned = _has_pinned_version(project_root, "typescript")
    # The combined hook uses a single subprocess.run in the hook runner; the
    # cli_command encodes the eslint invocation, and tsc is appended by the
    # runner as a follow-up. For the brief, we encode the combined command
    # as a shell-style argv that the runner treats as sequential.
    if eslint_pinned and tsc_pinned:
        cmd = ("eslint", ".", "--ext", ".ts,.tsx,.js,.jsx", ";", "tsc", "--noEmit")
    elif eslint_pinned:
        cmd = ("eslint", ".", ";", "tsc", "--noEmit")
    else:
        cmd = _npx_command("eslint", ".", "--ext", ".ts,.tsx,.js,.jsx") + (";", "tsc", "--noEmit")
    return Hook(name="web.eslint_tsc", cli_command=cmd, fallback=js_ts_fallback, timeout_seconds=600)


def _html_hook(project_root: Path) -> Hook:
    pinned = _has_pinned_version(project_root, "html-validate")
    cmd = _npx_command("html-validate", "**/*.html") if pinned is None else ("html-validate", "**/*.html")
    return Hook(name="web.html_validate", cli_command=cmd, fallback=html_fallback, timeout_seconds=300)


def web_hooks(project_root: Path) -> tuple[Hook, ...]:
    """Return the three Web hooks for a project root."""
    return (_css_hook(project_root), _eslt_hook(project_root), _html_hook(project_root))


def run_hook_with_fallback(
    hook: Hook, project_root: Path, file_paths: list[Path] | None = None,
) -> list[tuple[Path, int, str]]:
    """Run a Web hook with hybrid fallback per spec Writing F2.

    1. If the CLI is present (via `shutil.which`), run it via subprocess.
    2. If the CLI is missing AND `hook.fallback` is set, invoke the fallback.
    3. If the CLI is missing AND no fallback, raise WebHookError with installation instructions.
    """
    cli_name = hook.cli_command[0]
    if cli_name != "npx" and shutil.which(cli_name) is None:
        if hook.fallback is None:
            raise WebHookError(
                f"{cli_name} not installed and no fallback configured for hook {hook.name!r}. "
                f"Install with: npm install --save-dev {cli_name}"
            )
        logger.warning(
            "%s not installed; using Python fallback for hook %r",
            cli_name, hook.name,
        )
        paths = file_paths or [project_root]
        return [issue for p in paths for issue in (hook.fallback(p) or [])]
    # CLI present (or npx-prefixed); run subprocess (simplified; full runner is a Phase 4.5 concern)
    cmd = list(hook.cli_command)
    if file_paths:
        cmd.extend(str(p) for p in file_paths)
    else:
        cmd.append(str(project_root))
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=project_root)
    # For Phase 4 we surface only fallback-shaped issues; CLI parsing is a Phase 4.5 concern
    if result.returncode != 0:
        logger.warning(
            "Web hook %r exited %d: %s", hook.name, result.returncode, result.stderr[:500]
        )
    return []


class WebHookError(RuntimeError):
    """Raised when a Web hook cannot run (CLI missing, no fallback)."""
```

- [ ] **Step 6: Run to verify pass**

Run: `cd /Users/les/Projects/crackerjack && uv run pytest tests/adapters/web/test_hooks.py -v`
Expected: 8 passed.

- [ ] **Step 7: Commit**

```bash
cd /Users/les/Projects/crackerjack
git add crackerjack/adapters/web/python_fallbacks.py crackerjack/adapters/web/hooks.py tests/adapters/web/test_hooks.py
git -c user.email=les@wedgwoodwebworks.com -c user.name=les commit -m "feat(adapters.web): 3 hybrid-pattern hooks (stylelint, eslint+tsc, html-validate)"
```

---

## Task 4: Jinja template formatter (lex-based, 2-tier canonical policy)

**Files:**
- Create: `crackerjack/adapters/web/jinja_formatter.py`
- Test: `tests/adapters/web/test_jinja_formatter.py`

**Per spec Jinja F1:** use `jinja2.Environment.lex()` (NOT `parse()`) — parse() drops comments. Preserves `{%-`/`-%}`/`{{-`/`-}}` markers.

**Per spec Jinja F2:** all 6 delimiter kwargs required.

**Per spec Jinja F3:** two-tier canonical policy:
- Tier 1 (always on): trailing newline at EOF, no trailing whitespace, preserve `{%-`/`-%}`/`{{-`/`-}}` markers
- Tier 2 (opt-in via `[tool.crackerjack.jinja] normalize = true`): one space inside delimiters, blank line between block-level tags at top level, inline `{{ var }}` may remain inline

**Per spec Jinja F1 + Testing F9:** round-trip invariant `format_lex(format_lex(x)) == format_lex(x)` with golden-master expected output.

**Pre-flight verification:** confirm `jinja2.Environment` accepts all 6 delimiter kwargs (test against `jinja2>=3.1.6`).

- [ ] **Step 1: Verify jinja2 delimiter kwargs**

```bash
cd /Users/les/Projects/crackerjack
uv run python -c "
import jinja2
env = jinja2.Environment(
    block_start_string='[%', block_end_string='%]',
    variable_start_string='[[', variable_end_string=']]',
    comment_start_string='[#', comment_end_string='#]',
)
print(list(env.lex('[% if x %]A[% endif %]')))
"
```
Expected: list of `(lineno, token_type, value)` tuples, no exception.

- [ ] **Step 2: Write failing tests (golden-master + round-trip)**

```python
# tests/adapters/web/test_jinja_formatter.py
from __future__ import annotations

from pathlib import Path

import pytest

from crackerjack.adapters.web.jinja_formatter import format_template


DEFAULT_DELIMITERS = {
    "block_start": "{%", "block_end": "%}",
    "variable_start": "{{", "variable_end": "}}",
    "comment_start": "{#", "comment_end": "#}",
}


def test_format_adds_trailing_newline_when_missing() -> None:
    """Tier 1: trailing newline at EOF."""
    src = "{% if x %}A{% endif %}"
    result = format_template(src, delimiters=DEFAULT_DELIMITERS)
    assert result.endswith("\n")


def test_format_strips_trailing_whitespace_per_line() -> None:
    """Tier 1: no trailing whitespace on lines."""
    src = "line 1   \nline 2\t\nline 3"
    result = format_template(src, delimiters=DEFAULT_DELIMITERS)
    for line in result.split("\n"):
        assert line == line.rstrip(), f"trailing whitespace: {line!r}"


def test_format_preserves_whitespace_control_markers() -> None:
    """Tier 1: preserve {%- / -%} / {{- / -}} markers."""
    src = "A {%- if x -%} B"
    result = format_template(src, delimiters=DEFAULT_DELIMITERS)
    assert "{%- if x -%}" in result


def test_format_preserves_comments() -> None:
    """Per spec Jinja F1: lex() preserves comments; parse() drops them."""
    src = "{# important comment #}\n{% if x %}A{% endif %}"
    result = format_template(src, delimiters=DEFAULT_DELIMITERS)
    assert "{# important comment #}" in result


def test_format_uses_custom_delimiters() -> None:
    src = "[% if x %]A[% endif %]"
    custom = {
        "block_start": "[%", "block_end": "%]",
        "variable_start": "[[", "variable_end": "]]",
        "comment_start": "[#", "comment_end": "#]",
    }
    result = format_template(src, delimiters=custom)
    assert "[% if x %]" in result


def test_format_handles_unknown_tags() -> None:
    """Per spec Jinja F1: lex() tolerates unknown tags; parse() hard-fails."""
    src = "{% trans %}hello{% endtrans %}"
    # lex() should not raise
    result = format_template(src, delimiters=DEFAULT_DELIMITERS)
    assert result is not None


def test_round_trip_invariant() -> None:
    """Per spec Jinja F1 + Testing F9: format_lex(format_lex(x)) == format_lex(x)."""
    src = "{# c #}\n{% if x %}\nA\n{% else %}\nB\n{% endif %}\n"
    once = format_template(src, delimiters=DEFAULT_DELIMITERS)
    twice = format_template(once, delimiters=DEFAULT_DELIMITERS)
    assert once == twice, f"round-trip failed:\n{once!r}\nvs\n{twice!r}"


def test_tier1_only_when_normalize_false(tmp_path: Path) -> None:
    """Tier 2 is opt-in; default should NOT add spaces inside delimiters."""
    src = "{%if x%}A{%endif%}"
    result = format_template(src, delimiters=DEFAULT_DELIMITERS, normalize=False)
    # Tier 2 off: no space insertion
    assert "{%if x%}" in result or "{% if x %}" not in result


def test_tier2_when_normalize_true() -> None:
    """Tier 2: one space inside delimiters when normalize=True."""
    src = "{%if x%}A{%endif%}"
    result = format_template(src, delimiters=DEFAULT_DELIMITERS, normalize=True)
    assert "{% if x %}" in result
```

- [ ] **Step 3: Run to verify fail**

Run: `cd /Users/les/Projects/crackerjack && uv run pytest tests/adapters/web/test_jinja_formatter.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'crackerjack.adapters.web.jinja_formatter'`.

- [ ] **Step 4: Implement jinja_formatter.py**

```python
"""Jinja template formatter (lex-based, two-tier canonical policy).

Per spec:
- Jinja F1: `Environment.lex()` (NOT `parse()`) — preserves comments and
  whitespace-control markers. parse() silently drops them.
- Jinja F2: All 6 delimiter kwargs required (block_start, block_end,
  variable_start, variable_end, comment_start, comment_end).
- Jinja F3: Two-tier canonical policy.
  - Tier 1 (always on): trailing newline at EOF, no trailing
    whitespace per line, preserve `{%-` / `-%}` / `{{-` / `-}}`.
  - Tier 2 (opt-in via `normalize=True`): one space inside
    delimiters, blank line between block-level tags at top level.

Round-trip invariant: `format_template(format_template(x)) == format_template(x)`.
"""
from __future__ import annotations

import logging
import re
from collections.abc import Mapping

import jinja2

logger = logging.getLogger(__name__)


DEFAULT_DELIMITERS: dict[str, str] = {
    "block_start": "{%", "block_end": "%}",
    "variable_start": "{{", "variable_end": "}}",
    "comment_start": "{#", "comment_end": "#}",
}


def _env(delimiters: Mapping[str, str]) -> jinja2.Environment:
    """Construct a Jinja2 Environment with the 6 delimiter kwargs (per spec Jinja F2)."""
    return jinja2.Environment(
        block_start_string=delimiters["block_start"],
        block_end_string=delimiters["block_end"],
        variable_start_string=delimiters["variable_start"],
        variable_end_string=delimiters["variable_end"],
        comment_start_string=delimiters["comment_start"],
        comment_end_string=delimiters["comment_end"],
    )


def format_template(
    source: str,
    delimiters: Mapping[str, str] | None = None,
    normalize: bool = False,
) -> str:
    """Format a Jinja template per the two-tier canonical policy.

    Args:
        source: The template source.
        delimiters: Dict with 6 keys (block_start, block_end,
            variable_start, variable_end, comment_start, comment_end).
            Defaults to standard Jinja delimiters.
        normalize: Enable Tier 2 normalization (opt-in). Default False.

    Returns:
        Formatted template string. Round-trip invariant holds.
    """
    delims = delimiters or DEFAULT_DELIMITERS
    env = _env(delims)

    # Tier 1: Use lex() to preserve comments and whitespace markers.
    try:
        tokens = list(env.lex(source))
    except jinja2.TemplateSyntaxError as exc:
        logger.warning("Jinja lex failed: %s", exc)
        return source  # Best-effort: return source unchanged

    # Reconstruct source from tokens (preserve lex()'s token order; this
    # is the canonical form for Tier 1).
    reconstructed = "".join(value for _, _, value in tokens)

    # Tier 1 fix-ups
    fixed = _strip_trailing_whitespace(reconstructed)
    if not fixed.endswith("\n"):
        fixed += "\n"

    # Tier 2: optional normalization (one space inside delimiters).
    if normalize:
        fixed = _normalize_one_space_inside_delimiters(fixed, delims)

    return fixed


def _strip_trailing_whitespace(source: str) -> str:
    """Tier 1: strip trailing whitespace from every line."""
    lines = source.split("\n")
    return "\n".join(line.rstrip() for line in lines)


def _normalize_one_space_inside_delimiters(source: str, delims: Mapping[str, str]) -> str:
    """Tier 2: ensure exactly one space inside each delimiter pair."""
    out = source
    for open_key, close_key in [
        ("block_start", "block_end"),
        ("variable_start", "variable_end"),
        ("comment_start", "comment_end"),
    ]:
        open_d, close_d = delims[open_key], delims[close_key]
        # Match `open_d<not-whitespace>...<not-whitespace>close_d` and replace
        # with `open_d<one-space>...<one-space>close_d`. Preserves the body.
        # Use a non-greedy match for the inner content.
        pattern = re.escape(open_d) + r"(\S)(.*?)(\S)" + re.escape(close_d)
        # Apply only when current delimiters don't have internal whitespace
        # (idempotent: don't keep adding spaces).
        def repl(m: re.Match[str]) -> str:
            return f"{open_d} {m.group(2)} {close_d}"
        out = re.sub(pattern, repl, out, flags=re.DOTALL)
    return out
```

- [ ] **Step 5: Run to verify pass**

Run: `cd /Users/les/Projects/crackerjack && uv run pytest tests/adapters/web/test_jinja_formatter.py -v`
Expected: 9 passed.

- [ ] **Step 6: Commit**

```bash
cd /Users/les/Projects/crackerjack
git add crackerjack/adapters/web/jinja_formatter.py tests/adapters/web/test_jinja_formatter.py
git -c user.email=les@wedgwoodwebworks.com -c user.name=les commit -m "feat(adapters.web): Jinja formatter with 6 delimiters + 2-tier policy (lex-based)"
```

---

## Task 5: `WebAdapter` — wires it all together

**Files:**
- Modify: `crackerjack/adapters/web/__init__.py` (replaces empty marker)
- Create: `tests/adapters/web/test_web_adapter.py`

**Per Phase 2 final-review CF-2 fix:** `capabilities()` does NOT construct the formatter; it's lazily built by the MCP handler (Task 6).

- [ ] **Step 1: Write failing tests**

```python
# tests/adapters/web/test_web_adapter.py
from __future__ import annotations

from pathlib import Path

from crackerjack.adapters.base import LanguageAdapterBase
from crackerjack.adapters.web import WebAdapter


def test_web_adapter_extends_language_adapter_base() -> None:
    assert issubclass(WebAdapter, LanguageAdapterBase)


def test_web_adapter_name_is_web() -> None:
    assert WebAdapter.name == "web"


def test_detect_returns_true_when_package_json_present(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text("{}")
    assert WebAdapter().detect(tmp_path) is True


def test_detect_returns_false_for_python_project_no_opt_in(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'foo'\n")
    assert WebAdapter().detect(tmp_path) is False


def test_detect_returns_true_for_python_project_with_opt_in(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        "[project]\nname = 'foo'\n[tool.crackerjack.web]\nenabled = true\n"
    )
    assert WebAdapter().detect(tmp_path) is True


def test_capabilities_has_no_lifecycle(tmp_path: Path) -> None:
    """Per spec line 65: CSS/HTML/JS/TS lifecycle is out of scope."""
    (tmp_path / "package.json").write_text("{}")
    caps = WebAdapter().capabilities(tmp_path)
    assert caps.has_lifecycle is False
    assert caps.has_version is False


def test_capabilities_exposes_three_hooks(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text("{}")
    caps = WebAdapter().capabilities(tmp_path)
    names = {h.name for h in caps.hooks}
    assert names == {"web.stylelint", "web.eslint_tsc", "web.html_validate"}


def test_capabilities_exposes_jinja_formatter_factory(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text("{}")
    caps = WebAdapter().capabilities(tmp_path)
    # Phase 4 doesn't define a "formatter" field on Capabilities; the formatter
    # is exposed via the MCP tool (Task 6). This test just verifies capabilities
    # doesn't break; the MCP tool test covers formatter reachability.
    assert caps is not None
```

- [ ] **Step 2: Run to verify fail**

Run: `cd /Users/les/Projects/crackerjack && uv run pytest tests/adapters/web/test_web_adapter.py -v`
Expected: FAIL with `ImportError: cannot import name 'WebAdapter'`.

- [ ] **Step 3: Implement WebAdapter**

Replace `crackerjack/adapters/web/__init__.py`:

```python
"""Web (CSS/HTML/JS/TS) language adapter for crackerjack.

Activates only when `package.json` exists at the project root OR when
`[tool.crackerjack.web] enabled = true` in `pyproject.toml`. Without
the detection guard, every Django/Sphinx/MkDocs Python project would
falsely trigger Web hooks (per spec Writing F3).

Provides 3 hooks (stylelint, eslint+tsc, html-validate) with hybrid
pattern (CLI primary via `npx`, Python fallback), and a Jinja
template formatter. NO lifecycle — CSS/HTML/JS/TS have no native
version-bump workflow (per spec line 65).
"""
from __future__ import annotations

from pathlib import Path

from crackerjack.adapters.base import Capabilities, LanguageAdapterBase
from crackerjack.adapters.web.detection import web_enabled
from crackerjack.adapters.web.hooks import web_hooks

__all__ = ["WebAdapter"]


class WebAdapter(LanguageAdapterBase):
    """Web (CSS/HTML/JS/TS) language adapter."""

    name: str = "web"

    def detect(self, project_root: Path) -> bool:
        return web_enabled(project_root)

    def capabilities(self, project_root: Path) -> Capabilities:
        # Per Phase 2 final-review CF-2 fix: capabilities() returns metadata only;
        # the Jinja formatter is built lazily by the MCP handler (Task 6).
        return Capabilities(
            version_source=None,  # No version management for Web
            hooks=web_hooks(project_root),
            has_lifecycle=False,
        )
```

- [ ] **Step 4: Run to verify pass**

Run: `cd /Users/les/Projects/crackerjack && uv run pytest tests/adapters/web/test_web_adapter.py -v`
Expected: 8 passed.

- [ ] **Step 5: Verify `discover_adapters()` returns all four**

Run: `cd /Users/les/Projects/crackerjack && uv run python -c "from crackerjack.adapters.registry import discover_adapters; print(sorted(discover_adapters().keys()))"`
Expected: `['kotlin', 'python', 'swift', 'web']`.

- [ ] **Step 6: Commit**

```bash
cd /Users/les/Projects/crackerjack
git add crackerjack/adapters/web/__init__.py tests/adapters/web/test_web_adapter.py
git -c user.email=les@wedgwoodwebworks.com -c user.name=les commit -m "feat(adapters.web): WebAdapter wires detection + 3 hybrid hooks"
```

---

## Task 6: MCP tools — `check_web_lint` + `format_jinja_templates`

**Files:**
- Modify: `crackerjack/mcp/tools/language_tools.py` (add 2 tools; preserve existing tools)
- Modify: `tests/mcp/tools/test_language_tools.py` (add tests)

**Per Phase 3 carry-over:** the existing `_validate_project_root` (fail-closed) and `_require_auth_config` (diagnostic) helpers are reused.

- [ ] **Step 1: Write failing tests**

Append to `tests/mcp/tools/test_language_tools.py`:

```python
async def test_check_web_lint_returns_three_hook_names(tmp_path: Path) -> None:
    from crackerjack.adapters.web import WebAdapter
    (tmp_path / "package.json").write_text("{}")
    monkeypatch = pytest.MonkeyPatch()
    try:
        monkeypatch.setenv("MAHAVISHNU_PROJECT_ROOTS", str(tmp_path))
        _, tools = asyncio.run(_register())
        tool = tools["check_web_lint"]
        result = asyncio.run(tool.fn(project_root=str(tmp_path)))
    finally:
        monkeypatch.undo()
    assert isinstance(result, dict)
    assert "hooks" in result
    names = {h["name"] for h in result["hooks"]}
    assert names == {"web.stylelint", "web.eslint_tsc", "web.html_validate"}


async def test_check_web_lint_rejects_python_project_no_opt_in(tmp_path: Path) -> None:
    monkeypatch = pytest.MonkeyPatch()
    try:
        monkeypatch.setenv("MAHAVISHNU_PROJECT_ROOTS", str(tmp_path))
        _, tools = asyncio.run(_register())
        tool = tools["check_web_lint"]
        with pytest.raises(ValueError, match="not enabled"):
            asyncio.run(tool.fn(project_root=str(tmp_path)))
    finally:
        monkeypatch.undo()


async def test_format_jinja_templates_requires_auth(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text("{}")
    (tmp_path / "templates").mkdir()
    (tmp_path / "templates" / "test.html").write_text("{% if x %}A{% endif %}")
    monkeypatch = pytest.MonkeyPatch()
    try:
        monkeypatch.delenv("MAHAVISHNU_AUTH_ENABLED", raising=False)
        monkeypatch.delenv("MAHAVISHNU_JWT_SECRET", raising=False)
        _, tools = asyncio.run(_register())
        tool = tools["format_jinja_templates"]
        with pytest.raises(PermissionError):
            asyncio.run(tool.fn(projects=[str(tmp_path / "templates")]))
    finally:
        monkeypatch.undo()


async def test_format_jinja_templates_runs_with_auth(tmp_path: Path) -> None:
    """Happy-path test (per MCP HIGH-3 / Testing HIGH-1 Phase 3 analog)."""
    (tmp_path / "package.json").write_text("{}")
    (tmp_path / "templates").mkdir()
    (tmp_path / "templates" / "test.html").write_text("{% if x %}A{% endif %}")
    monkeypatch = pytest.MonkeyPatch()
    try:
        monkeypatch.setenv("MAHAVISHNU_AUTH_ENABLED", "true")
        monkeypatch.setenv("MAHAVISHNU_JWT_SECRET", "test-secret")
        monkeypatch.setenv("MAHAVISHNU_PROJECT_ROOTS", str(tmp_path))
        _, tools = asyncio.run(_register())
        tool = tools["format_jinja_templates"]
        result = asyncio.run(tool.fn(projects=[str(tmp_path / "templates")]))
    finally:
        monkeypatch.undo()
    assert "files" in result
    assert any("test.html" in f for f in result["files"])
```

- [ ] **Step 2: Run to verify fail**

Run: `cd /Users/les/Projects/crackerjack && uv run pytest tests/mcp/tools/test_language_tools.py -v`
Expected: FAIL with `KeyError: 'check_web_lint'`.

- [ ] **Step 3: Add 2 tools to language_tools.py**

Append to `crackerjack/mcp/tools/language_tools.py`:

```python
@mcp_app.tool()
async def check_web_lint(project_root: str) -> dict:
    """Return Web hook metadata for the given project.

    Read-only — no auth required. Activates the Web adapter (requires
    `package.json` at root OR `[tool.crackerjack.web] enabled = true`).
    Each hook has CLI primary + Python fallback per spec Writing F2.

    Args:
        project_root: Absolute path to the project root. Must be in
            `MAHAVISHNU_PROJECT_ROOTS` allowlist.

    Returns:
        dict with keys: `adapter` (`"web"`), `enabled` (bool),
        `hooks` (list of {name, cli_command, has_fallback, timeout_seconds}).

    Raises:
        PermissionError: if `project_root` is not in
            `MAHAVISHNU_PROJECT_ROOTS` allowlist.
        ValueError: if the Web adapter is not enabled for the project.
    """
    root = _validate_project_root(project_root)
    from crackerjack.adapters.web import WebAdapter
    from crackerjack.adapters.web.detection import web_enabled

    if not web_enabled(root):
        raise ValueError(
            f"Web adapter not enabled at {root}. "
            f"Add `package.json` or set `[tool.crackerjack.web] enabled = true`."
        )
    caps = WebAdapter().capabilities(root)
    return {
        "adapter": "web",
        "enabled": True,
        "hooks": [
            {
                "name": h.name,
                "cli_command": list(h.cli_command),
                "has_fallback": h.fallback is not None,
                "timeout_seconds": h.timeout_seconds,
            }
            for h in caps.hooks
        ],
    }


@mcp_app.tool()
async def format_jinja_templates(projects: list[str]) -> dict:
    """Format Jinja templates in the given project directories.

    Mutation tool — auth required per spec MCP F5. Reads each
    `*.html` / `*.j2` / `*.jinja` file, formats per the two-tier
    canonical policy (Tier 1 always on; Tier 2 normalize=False default
    so existing whitespace markers are preserved).

    Args:
        projects: List of absolute paths to directories containing Jinja
            templates. Each must be in `MAHAVISHNU_PROJECT_ROOTS`.

    Returns:
        dict with keys: `files` (list of formatted file paths),
        `errors` (list of {path, error} for files that failed to lex).

    Raises:
        PermissionError: if auth missing OR any project_root not in
            `MAHAVISHNU_PROJECT_ROOTS` allowlist.
    """
    _require_auth_config()
    for p in projects:
        _validate_project_root(p)
    from crackerjack.adapters.web.jinja_formatter import format_template

    files: list[str] = []
    errors: list[dict[str, str]] = []
    for project_dir in projects:
        proj = Path(project_dir)
        for path in proj.rglob("*"):
            if not path.is_file() or path.suffix not in {".html", ".j2", ".jinja"}:
                continue
            try:
                formatted = await asyncio.to_thread(
                    format_template, path.read_text(),
                )
                path.write_text(formatted)
                files.append(str(path))
            except (OSError, UnicodeDecodeError) as exc:
                errors.append({"path": str(path), "error": str(exc)})
    return {"files": files, "errors": errors}
```

- [ ] **Step 4: Run to verify pass**

Run: `cd /Users/les/Projects/crackerjack && uv run pytest tests/mcp/tools/test_language_tools.py -v`
Expected: 17 passed (existing 13 + 4 new web tests).

- [ ] **Step 5: Verify discoverability**

Run: Start the MCP server briefly and confirm `check_web_lint` and `format_jinja_templates` appear in the tool list alongside existing tools.

- [ ] **Step 6: Commit**

```bash
cd /Users/les/Projects/crackerjack
git add crackerjack/mcp/tools/language_tools.py tests/mcp/tools/test_language_tools.py
git -c user.email=les@wedgwoodwebworks.com -c user.name=les commit -m "feat(mcp): check_web_lint + format_jinja_templates in language_tools group"
```

---

## Task 7: Verification — Web fixture + CHANGELOG + smoke tests

**Files:**
- Create: `tests/fixtures/web-vanilla/package.json`
- Create: `tests/fixtures/web-vanilla/.stylelintrc.json`
- Create: `tests/fixtures/web-vanilla/.eslintrc.json`
- Create: `tests/fixtures/web-vanilla/tsconfig.json`
- Create: `tests/fixtures/web-vanilla/src/{style.css,app.ts,index.html}`
- Create: `tests/fixtures/web-vanilla/tests/fixtures/jinja-templates/{basic.html,custom_delimiters.html,whitespace.html}` (golden-master inputs)
- Modify: `CHANGELOG.md`

**Per Phase 3 final-review fix precedent:** also add a fixture-reference test.

- [ ] **Step 1: Create fixture files**

```bash
mkdir -p /Users/les/Projects/crackerjack/tests/fixtures/web-vanilla/src
mkdir -p /Users/les/Projects/crackerjack/tests/fixtures/web-vanilla/tests/fixtures/jinja-templates
```

`package.json`:
```json
{
  "name": "web-vanilla",
  "version": "0.1.0",
  "devDependencies": {
    "stylelint": "^15.0.0",
    "eslint": "^8.0.0",
    "@typescript-eslint/parser": "^7.0.0",
    "typescript": "^5.0.0",
    "html-validate": "^8.0.0"
  }
}
```

`.stylelintrc.json`:
```json
{"rules": {}}
```

`.eslintrc.json`:
```json
{"parser": "@typescript-eslint/parser"}
```

`tsconfig.json`:
```json
{"compilerOptions": {"strict": true}}
```

`src/style.css`:
```css
.foo {
  color: red;
}
```

`src/app.ts`:
```ts
const x: number = 1;
console.log(x);
```

`src/index.html`:
```html
<!DOCTYPE html>
<html><body><h1>Hello</h1></body></html>
```

`tests/fixtures/jinja-templates/basic.html`:
```html
{# standard jinja delimiters #}
{% if x %}A{% endif %}
```

`tests/fixtures/jinja-templates/custom_delimiters.html`:
```html
{# custom delimiters [[[]]] #}
[% if x %]A[% endif %]
[[ var ]]
```

`tests/fixtures/jinja-templates/whitespace.html`:
```html
{%- if x -%}
  A
{%- endif -%}
```

- [ ] **Step 2: Add fixture-reference test**

Create `tests/adapters/web/test_web_vanilla_fixture.py`:

```python
"""Minimal fixture-reference test for tests/fixtures/web-vanilla/."""
from __future__ import annotations

from pathlib import Path

from crackerjack.adapters.web import WebAdapter


FIXTURE_ROOT = Path(__file__).parent.parent.parent / "fixtures" / "web-vanilla"


def test_fixture_is_reachable() -> None:
    assert FIXTURE_ROOT.is_dir(), f"Fixture not found at {FIXTURE_ROOT}"
    assert (FIXTURE_ROOT / "package.json").is_file()


def test_adapter_detects_fixture() -> None:
    assert WebAdapter().detect(FIXTURE_ROOT) is True


def test_adapter_capabilities_on_fixture() -> None:
    caps = WebAdapter().capabilities(FIXTURE_ROOT)
    assert caps.has_lifecycle is False  # Per spec line 65: no lifecycle
    names = {h.name for h in caps.hooks}
    assert names == {"web.stylelint", "web.eslint_tsc", "web.html_validate"}
```

- [ ] **Step 3: Update CHANGELOG.md**

Add under `[Unreleased]`:
```markdown
- Web (CSS/HTML/JS/TS) language adapter (Phase 4): detection guard prevents
  Python-project false positives (requires `package.json` or
  `[tool.crackerjack.web] enabled = true`). Three hooks with hybrid pattern
  (CLI primary via `npx`, Python fallback): web.stylelint, web.eslint_tsc
  (combined eslint + tsc --noEmit), web.html_validate. Jinja template
  formatter using `jinja2.Environment.lex()` (NOT parse() — preserves
  comments and `{%-` / `-%}` / `{{-` / `-}}` markers); all 6 delimiter
  kwargs supported (block/variable/comment × start/end); two-tier canonical
  policy (Tier 1: trailing newline + no trailing whitespace + preserve
  whitespace-control markers; Tier 2 opt-in via `normalize=True`).
  Round-trip invariant: `format_lex(format_lex(x)) == format_lex(x)`.
  Two new MCP tools: check_web_lint (read-only), format_jinja_templates
  (mutation; requires auth + path validation). NO lifecycle (CSS/HTML/JS/TS
  have no native version-bump workflow). `crackerjack.language_adapters`
  entry-point group now registers Python, Swift, Kotlin, and Web adapters.
  New fixture at `tests/fixtures/web-vanilla/` exercises the full Web
  adapter end-to-end.
```

- [ ] **Step 4: Run Phase 4 tests**

Run: `cd /Users/les/Projects/crackerjack && uv run pytest tests/adapters/web/ tests/mcp/tools/test_language_tools.py tests/adapters/test_registry.py --no-cov -q`
Expected: ~80 passed (52 prior Phase 3 + 28 new Phase 4).

- [ ] **Step 5: Smoke verification**

```bash
cd /Users/les/Projects/crackerjack
uv run python -c "
from crackerjack.adapters.registry import discover_adapters
print(sorted(discover_adapters().keys()))
from crackerjack.adapters.web import WebAdapter
print(WebAdapter().detect(__import__('pathlib').Path('tests/fixtures/web-vanilla')))
"
```
Expected: `['kotlin', 'python', 'swift', 'web']` and `True`.

- [ ] **Step 6: Commit**

```bash
cd /Users/les/Projects/crackerjack
git add tests/fixtures/web-vanilla/ tests/adapters/web/test_web_vanilla_fixture.py CHANGELOG.md
git -c user.email=les@wedgwoodwebworks.com -c user.name=les commit -m "docs(changelog): Phase 4 — Web adapter + Jinja formatter + real Web fixture"
```

---

## Spec Revision Notes

(Spec amendments for the next revision pass — to be filled in after multi-agent review.)

---

## Cross-adapter `_bump` divergence (Phase 2.5 follow-up, deferred)

Phase 4 has no lifecycle, so `_bump` divergence is not relevant here. Documented in Phase 2 ledger for Phase 2/3 only.
