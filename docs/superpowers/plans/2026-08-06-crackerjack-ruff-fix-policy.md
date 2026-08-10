# Crackerjack Ruff Fix Policy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Crackerjack's Ruff invocation safe-by-default (no `--unsafe-fixes` in normal runs), keep CI read-only, expose an explicit unsafe-fix opt-in, close the downstream supply-chain leak in the generated `pyproject.toml`, and pin Ruff intentionally.

**Architecture:** Single source of truth for "should Ruff write files" lives in `HookSettings.ruff_unsafe_fixes`. The default `ruff-check` hook drops `--unsafe-fixes`; an explicit CLI flag or settings entry is the *only* path that may emit it. The `config_template.py` scaffold flips to `unsafe-fixes = false`. CI and validation paths stay read-only. Working-tree state is checked before any `--fix` invocation.

**Tech Stack:** Python 3.13, Ruff 0.16.0, uv, pytest, git, crackerjack (this repo).

## Global Constraints

- Ruff version: **pinned to `ruff==0.16.0` in `pyproject.toml:54`** and matched in `uv.lock` (a separate reviewable change).
- Ruff commands:
  - Safe fix: `ruff check --output-format json --fix ./crackerjack`
  - Read-only: `ruff check --output-format json --no-fix ./crackerjack`
  - Preview: `ruff check --diff ./crackerjack`
  - Unsafe: `ruff check --output-format json --fix --unsafe-fixes ./crackerjack` (only via explicit opt-in)
- Ruff exit codes: 0 (clean/fixed), 1 (violations remain OR applied fixes under chosen policy), 2 (internal/parse error — must be surfaced).
- Default `PreflightConfig.ruff_unsafe_fixes` and `HookSettings.ruff_unsafe_fixes` are `False`.
- Generated `pyproject.toml` from `crackerjack/services/config_template.py:62` must emit `"unsafe-fixes": False`.
- Do NOT mutate read-only paths listed in the spec Section 4.9.
- The `ruff-check` hook timeout in `crackerjack/config/hooks.py:169-186` stays at 240 s.
- Tests: pytest markers `unit`, `integration`; async tests use `asyncio_mode = "auto"`; follow the existing `tests/unit/...` layout.
- Commits: follow the existing `feat(scope):` / `fix(scope):` / `docs(scope):` convention used in `git log` (e.g. `feat(precommit): wire CLI with asyncio.run wrappers`).

## File Structure

The work is gated on five files and the CLI option list. One test file per behavior:

- `crackerjack/config/tool_commands.py` — drop `--unsafe-fixes` from the `ruff-check` template; route the unsafe path through `HookSettings` in Stage 2.
- `crackerjack/services/config_template.py` — flip the scaffolded `"unsafe-fixes"` default to `False`.
- `crackerjack/config/settings.py` — add `HookSettings.ruff_unsafe_fixes: bool = False`.
- `crackerjack/config/hooks.py` — add `HookDefinition.allow_unsafe_fixes: bool = False`; mark `ruff-check` `is_formatting=False` (it is a linter, not a formatter).
- `crackerjack/cli/options.py` — add `--allow-unsafe-fixes` and `--safe-only` flags.
- `crackerjack/core/preflight.py` — wire `HookSettings` lookup; add explicit exit-code 0/1/2 handling.
- `crackerjack/core/file_lifecycle.py` and `crackerjack/services/safe_code_modifier.py` — route unsafe-fix invocations through `SafeCodeModifier` to produce per-file `.bak` siblings.
- `crackerjack/services/git_cleanup_service.py` — wire `_validate_working_tree_clean()` as a precondition for any `--fix` invocation.
- `pyproject.toml` — pin `ruff==0.16.0`.
- `tests/unit/core/test_preflight.py` — exit-code routing and HookSettings-respect tests.
- `tests/unit/adapters/test_ruff_adapter.py` — `unsafe_fixes=True` without `fix_enabled=True` raises or auto-promotes.
- `tests/unit/services/test_safe_code_modifier.py` — `.bak` siblings.
- `tests/unit/services/test_git_cleanup.py` — dirty-tree refusal.
- `tests/unit/cli/test_options.py` — flag plumbing.
- `tests/fixtures/ruff_unsafe_diff_golden.txt` plus `tests/unit/core/test_ruff_unsafe_golden.py` — golden-diff test.
- `docs/CLI_REFERENCE.md`, `crackerjack/hooks/README.md`, `CHANGELOG.md`, `docs/CONFIG_CONSOLIDATION_AUDIT.md` — documentation updates.

______________________________________________________________________

## Task 1: Stage 0 — Drop `--unsafe-fixes` from the default hook and fix the generated config

**Files:**

- Modify: `crackerjack/config/tool_commands.py:228-235`
- Modify: `crackerjack/services/config_template.py:50-71`
- Test: `tests/unit/config/test_tool_commands_ruff_unsafe.py`
- Test: `tests/unit/services/test_config_template_ruff_unsafe.py`

**Interfaces:**

- Consumes: `get_tool_command("ruff-check", package_name="crackerjack")` → `list[str]`.

- Produces: by default, the returned list MUST NOT contain `"--unsafe-fixes"`. The `config_template.py` scaffolded `pyproject.toml` MUST contain `"unsafe-fixes": False`.

- [ ] **Step 1: Write the failing test for `tool_commands.py`**

Create `tests/unit/config/test_tool_commands_ruff_unsafe.py`:

```python
"""Stage 0: default ruff-check must not pass --unsafe-fixes."""


def test_ruff_check_default_omits_unsafe_fixes() -> None:
    from crackerjack.config.tool_commands import get_tool_command

    cmd = get_tool_command("ruff-check", package_name="crackerjack")

    assert "--unsafe-fixes" not in cmd, (
        f"ruff-check default must not include --unsafe-fixes; got {cmd!r}"
    )
    assert "--fix" in cmd, "ruff-check default must still apply safe fixes"
    assert "--output-format" in cmd
    assert "json" in cmd
    assert "./crackerjack" in cmd
```

- [ ] **Step 2: Run the test and confirm it fails**

Run: `pytest tests/unit/config/test_tool_commands_ruff_unsafe.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'crackerjack.config.tool_commands'` or with the assertion `assert '--unsafe-fixes' not in cmd` failing.

- [ ] **Step 3: Edit `crackerjack/config/tool_commands.py:228-235`**

In the existing `"ruff-check": _python_module_command(...)` block, remove the `"--unsafe-fixes",` line. The result is exactly:

```python
        "ruff-check": _python_module_command(
            "ruff",
            "check",
            "--output-format",
            "json",
            "--fix",
            f"./{package_name}",
        ),
```

No other line in this file changes in this task.

- [ ] **Step 4: Re-run the test and confirm it passes**

Run: `pytest tests/unit/config/test_tool_commands_ruff_unsafe.py -v`
Expected: PASS.

- [ ] **Step 5: Write the failing test for `config_template.py`**

Append to `tests/unit/services/test_config_template_ruff_unsafe.py` (create the file if it does not exist):

```python
"""Stage 0: scaffolded pyproject.toml must default unsafe-fixes to false."""


def test_scaffolded_unsafe_fixes_default_is_false() -> None:
    from crackerjack.services.config_template import build_pyproject_template

    content = build_pyproject_template()

    # The scaffolded [tool.ruff.lint] block must set unsafe-fixes = False.
    assert '"unsafe-fixes": False' in content or "unsafe-fixes = false" in content, (
        f"scaffolded config must disable unsafe-fixes by default; got:\n{content}"
    )
    assert '"unsafe-fixes": True' not in content
```

If `build_pyproject_template` does not exist, search the file for the actual entry-point function name and adapt the test accordingly. The test must compile; the assertion is the contract.

- [ ] **Step 6: Run the test and confirm it fails**

Run: `pytest tests/unit/services/test_config_template_ruff_unsafe.py -v`
Expected: FAIL on the assertion that `"unsafe-fixes": False` (or the platform equivalent) appears in the output.

- [ ] **Step 7: Edit `crackerjack/services/config_template.py:62`**

Change the single line from:

```python
            "unsafe-fixes": True,
```

to:

```python
            "unsafe-fixes": False,
```

No other change in this file.

- [ ] **Step 8: Re-run the test and confirm it passes**

Run: `pytest tests/unit/services/test_config_template_ruff_unsafe.py -v`
Expected: PASS.

- [ ] **Step 9: Run the affected unit tests**

Run: `pytest tests/unit/config/test_tool_commands_ruff_unsafe.py tests/unit/services/test_config_template_ruff_unsafe.py -v`
Expected: both pass.

- [ ] **Step 10: Commit Stage 0**

```bash
git -C /Users/les/Projects/crackerjack add \
    crackerjack/config/tool_commands.py \
    crackerjack/services/config_template.py \
    tests/unit/config/test_tool_commands_ruff_unsafe.py \
    tests/unit/services/test_config_template_ruff_unsafe.py
git -C /Users/les/Projects/crackerjack commit -m "fix(ruff): drop --unsafe-fixes from default hook; close scaffold leak

- tool_commands.py: ruff-check no longer passes --unsafe-fixes by default
- config_template.py: scaffolded pyproject.toml now sets unsafe-fixes=false

No behavior change for the safe-fix path. Stage 0 of the Ruff fix-safety
policy. See docs/superpowers/specs/2026-08-06-crackerjack-ruff-fix-policy-design.md."
```

______________________________________________________________________

## Task 2: Stage 1 — Add `HookSettings.ruff_unsafe_fixes`, `HookDefinition.allow_unsafe_fixes`, and CLI flags

**Files:**

- Modify: `crackerjack/config/settings.py` (locate the `HookSettings` model)
- Modify: `crackerjack/config/hooks.py:29-44` (`HookDefinition` model)
- Modify: `crackerjack/cli/options.py:378-381` (next to `-s/--skip-hooks`)
- Test: `tests/unit/config/test_hook_settings_ruff_unsafe.py`
- Test: `tests/unit/config/test_hook_definition_allow_unsafe.py`
- Test: `tests/unit/cli/test_options_allow_unsafe.py`

**Interfaces:**

- `HookSettings.ruff_unsafe_fixes: bool = False` — read by `preflight.py` and the `ruff-check` template.

- `HookDefinition.allow_unsafe_fixes: bool = False` — opt-in flag per hook; `ruff-check` is the only hook for which this becomes a runtime gate.

- `crackerjack.cli.options.allow_unsafe_fixes: bool` and `crackerjack.cli.options.safe_only: bool` — CLI flags that write into `HookSettings`.

- [ ] **Step 1: Read the existing `HookSettings` model**

Open `crackerjack/config/settings.py` and find the `HookSettings` class. Note the existing field naming convention (e.g. `enable_ty`, `enable_zuban`, `refurb_safe_policies`).

- [ ] **Step 2: Write the failing test for `HookSettings.ruff_unsafe_fixes`**

Create `tests/unit/config/test_hook_settings_ruff_unsafe.py`:

```python
"""Stage 1: HookSettings must expose a ruff_unsafe_fixes boolean default False."""


def test_hook_settings_ruff_unsafe_fixes_default_false() -> None:
    from crackerjack.config.settings import HookSettings

    settings = HookSettings()
    assert settings.ruff_unsafe_fixes is False


def test_hook_settings_ruff_unsafe_fixes_overridable() -> None:
    from crackerjack.config.settings import HookSettings

    settings = HookSettings(ruff_unsafe_fixes=True)
    assert settings.ruff_unsafe_fixes is True
```

- [ ] **Step 3: Run the test and confirm it fails**

Run: `pytest tests/unit/config/test_hook_settings_ruff_unsafe.py -v`
Expected: FAIL with `TypeError: __init__() got an unexpected keyword argument 'ruff_unsafe_fixes'`.

- [ ] **Step 4: Add the field to `HookSettings`**

In `crackerjack/config/settings.py`, add the field to the `HookSettings` class. The field must default to `False`:

```python
    ruff_unsafe_fixes: bool = False
```

If the class uses a different style (e.g. `pydantic.Field(default=False, description=...)`), follow that style. The default value MUST be `False` and the type MUST be `bool`.

- [ ] **Step 5: Re-run the test and confirm it passes**

Run: `pytest tests/unit/config/test_hook_settings_ruff_unsafe.py -v`
Expected: PASS.

- [ ] **Step 6: Write the failing test for `HookDefinition.allow_unsafe_fixes`**

Create `tests/unit/config/test_hook_definition_allow_unsafe.py`:

```python
"""Stage 1: HookDefinition must expose allow_unsafe_fixes defaulting to False."""


def test_hook_definition_allow_unsafe_fixes_default_false() -> None:
    from crackerjack.config.hooks import HookDefinition

    definition = HookDefinition(name="ruff-check")
    assert definition.allow_unsafe_fixes is False


def test_ruff_check_definition_can_opt_in() -> None:
    from crackerjack.config.hooks import HookDefinition

    definition = HookDefinition(name="ruff-check", allow_unsafe_fixes=True)
    assert definition.allow_unsafe_fixes is True
```

- [ ] **Step 7: Run the test and confirm it fails**

Run: `pytest tests/unit/config/test_hook_definition_allow_unsafe.py -v`
Expected: FAIL with `TypeError: __init__() got an unexpected keyword argument 'allow_unsafe_fixes'`.

- [ ] **Step 8: Add the field to `HookDefinition`**

In `crackerjack/config/hooks.py:29-44`, add:

```python
    allow_unsafe_fixes: bool = False
```

- [ ] **Step 9: Re-run the test and confirm it passes**

Run: `pytest tests/unit/config/test_hook_definition_allow_unsafe.py -v`
Expected: PASS.

- [ ] **Step 10: Add CLI flags `--allow-unsafe-fixes` and `--safe-only`**

In `crackerjack/cli/options.py:378-381`, next to the existing `-s/--skip-hooks` flag, add two new `typer.Option` arguments with the same style as the surrounding options:

```python
allow_unsafe_fixes: bool = (
    typer.Option(
        False,
        "--allow-unsafe-fixes",
        help=(
            "Opt in to Ruff unsafe fixes for this run. "
            "Required for any invocation that emits --unsafe-fixes. "
            "Pairs with a working-tree guard and per-file .bak siblings."
        ),
    ),
)
safe_only: bool = (
    typer.Option(
        False,
        "--safe-only",
        help=(
            "Refuse any invocation that would emit --unsafe-fixes, "
            "even if --allow-unsafe-fixes is set."
        ),
    ),
)
```

If the existing options in `options.py:378-381` use a different style (e.g. `Annotated[bool, typer.Option(...)]`), match it. The defaults MUST be `False`.

- [ ] **Step 11: Write the failing test for CLI flag plumbing**

Create `tests/unit/cli/test_options_allow_unsafe.py`:

```python
"""Stage 1: --allow-unsafe-fixes and --safe-only are wired into options."""


def test_allow_unsafe_fixes_default_false() -> None:
    from crackerjack.cli import options

    assert options.allow_unsafe_fixes is False


def test_safe_only_default_false() -> None:
    from crackerjack.cli import options

    assert options.safe_only is False
```

If `options` does not expose module-level attributes, invoke the option via `typer.testing.CliRunner` and assert behavior instead. The contract is the default value.

- [ ] **Step 12: Re-run the test and confirm it passes**

Run: `pytest tests/unit/cli/test_options_allow_unsafe.py -v`
Expected: PASS.

- [ ] **Step 13: Run the affected tests**

Run: `pytest tests/unit/config/test_hook_settings_ruff_unsafe.py tests/unit/config/test_hook_definition_allow_unsafe.py tests/unit/cli/test_options_allow_unsafe.py -v`
Expected: all pass.

- [ ] **Step 14: Commit Stage 1**

```bash
git -C /Users/les/Projects/crackerjack add \
    crackerjack/config/settings.py \
    crackerjack/config/hooks.py \
    crackerjack/cli/options.py \
    tests/unit/config/test_hook_settings_ruff_unsafe.py \
    tests/unit/config/test_hook_definition_allow_unsafe.py \
    tests/unit/cli/test_options_allow_unsafe.py
git -C /Users/les/Projects/crackerjack commit -m "feat(config): add ruff_unsafe_fixes / allow_unsafe_fixes knobs

- HookSettings.ruff_unsafe_fixes: bool = False
- HookDefinition.allow_unsafe_fixes: bool = False
- CLI: --allow-unsafe-fixes, --safe-only

Stage 1 of the Ruff fix-safety policy. Behavior is still safe-by-default;
the new fields are not yet read by any caller."
```

______________________________________________________________________

## Task 3: Stage 2 — Wire `HookSettings` into the `ruff-check` template and fix RuffAdapter silent no-op

**Files:**

- Modify: `crackerjack/config/tool_commands.py:228-235` (read from `HookSettings`)
- Modify: `crackerjack/adapters/format/ruff.py:146-150` (auto-promote or raise)
- Test: `tests/unit/config/test_tool_commands_ruff_unsafe.py` (extend)
- Test: `tests/unit/adapters/test_ruff_adapter.py::test_unsafe_only_auto_promotes_fix`

**Interfaces:**

- `crackerjack.config.tool_commands.get_tool_command(name, package_name=..., settings=None)` — when `name == "ruff-check"` and `settings.ruff_unsafe_fixes is True`, the returned list MUST include `"--unsafe-fixes"`. Otherwise it MUST NOT.

- `crackerjack.adapters.format.ruff.RuffAdapter.build_command(...)` — when `unsafe_fixes=True` and `fix_enabled=False`, raise `ValueError` (preferred) OR auto-promote to `fix_enabled=True`. The test in this task asserts the chosen contract; pick one and document it inline.

- [ ] **Step 1: Extend the existing test in `tests/unit/config/test_tool_commands_ruff_unsafe.py`**

Append:

```python
def test_ruff_check_includes_unsafe_fixes_when_settings_allow() -> None:
    from crackerjack.config.settings import HookSettings
    from crackerjack.config.tool_commands import get_tool_command

    settings = HookSettings(ruff_unsafe_fixes=True)
    cmd = get_tool_command("ruff-check", package_name="crackerjack", settings=settings)

    assert "--unsafe-fixes" in cmd, (
        f"ruff-check must emit --unsafe-fixes when settings allow; got {cmd!r}"
    )
    assert "--fix" in cmd
```

If `get_tool_command` does not currently accept `settings`, add it (see Step 2).

- [ ] **Step 2: Run the extended test and confirm it fails**

Run: `pytest tests/unit/config/test_tool_commands_ruff_unsafe.py -v`
Expected: FAIL on the new test (TypeError on extra kwarg, or assertion that `--unsafe-fixes` is present).

- [ ] **Step 3: Make `get_tool_command` accept a `settings` keyword argument**

In `crackerjack/config/tool_commands.py`, change the function signature so that:

```python
def get_tool_command(
    name: str,
    package_name: str = "crackerjack",
    settings: "HookSettings | None" = None,
) -> list[str]:
```

Inside, where `"ruff-check"` is built, read from `settings.ruff_unsafe_fixes` and conditionally append `"--unsafe-fixes",`. The default branch (no settings or `ruff_unsafe_fixes=False`) MUST NOT include the flag. Add the import of `HookSettings` only if the linter is configured to enforce that pattern.

Concrete shape:

```python
        "ruff-check": _python_module_command(
            "ruff",
            "check",
            "--output-format",
            "json",
            "--fix",
            *(["--unsafe-fixes"] if (settings is not None and settings.ruff_unsafe_fixes) else []),
            f"./{package_name}",
        ),
```

If `_python_module_command` does not accept a `*extras` pattern, build the list directly.

- [ ] **Step 4: Re-run the extended test and confirm it passes**

Run: `pytest tests/unit/config/test_tool_commands_ruff_unsafe.py -v`
Expected: PASS for both tests.

- [ ] **Step 5: Write the failing test for `RuffAdapter` auto-promotion/raise**

Append to `tests/unit/adapters/test_ruff_adapter.py`:

```python
def test_unsafe_only_auto_promotes_fix() -> None:
    from crackerjack.adapters.format.ruff import RuffAdapter

    adapter = RuffAdapter()

    # unsafe_fixes=True without fix_enabled=True must not silently no-op.
    try:
        cmd = adapter.build_command(
            mode="check",
            unsafe_fixes=True,
            fix_enabled=False,
        )
    except ValueError:
        return  # raise-ValueError contract is acceptable

    assert "--unsafe-fixes" in cmd
    assert "--fix" in cmd, "unsafe_fixes must not silently no-op; fix must be applied"
```

- [ ] **Step 6: Run the test and confirm the current behavior**

Run: `pytest tests/unit/adapters/test_ruff_adapter.py::test_unsafe_only_auto_promotes_fix -v`
Expected: FAIL (silent no-op path) OR PASS (auto-promotion already present). If PASS, skip Step 7 — the contract is already met.

- [ ] **Step 7: Fix `crackerjack/adapters/format/ruff.py:146-150`**

If the current code path silently returns without adding `--fix` when `unsafe_fixes=True` and `fix_enabled=False`, change it to either:

```python
        if unsafe_fixes and not fix_enabled:
            msg = "RuffAdapter.build_command: unsafe_fixes=True requires fix_enabled=True"
            raise ValueError(msg)
```

OR auto-promote by setting `fix_enabled = True`. Pick the raise-ValueError path (preferred) and document the choice in a one-line comment.

- [ ] **Step 8: Re-run the test and confirm it passes**

Run: `pytest tests/unit/adapters/test_ruff_adapter.py::test_unsafe_only_auto_promotes_fix -v`
Expected: PASS.

- [ ] **Step 9: Run the full affected suite**

Run: `pytest tests/unit/config/test_tool_commands_ruff_unsafe.py tests/unit/adapters/test_ruff_adapter.py -v`
Expected: all pass.

- [ ] **Step 10: Commit Stage 2**

```bash
git -C /Users/les/Projects/crackerjack add \
    crackerjack/config/tool_commands.py \
    crackerjack/adapters/format/ruff.py \
    tests/unit/config/test_tool_commands_ruff_unsafe.py \
    tests/unit/adapters/test_ruff_adapter.py
git -C /Users/les/Projects/crackerjack commit -m "feat(ruff): wire HookSettings.ruff_unsafe_fixes into ruff-check

- tool_commands.py: get_tool_command(name, package_name, settings=None) emits
  --unsafe-fixes only when settings.ruff_unsafe_fixes is True
- adapters/format/ruff.py: unsafe_fixes=True without fix_enabled=True raises
  ValueError instead of silently no-oping

Stage 2 of the Ruff fix-safety policy."
```

______________________________________________________________________

## Task 4: Stage 3 — Working-tree guard and unsafe-fix routing through `SafeCodeModifier`

**Files:**

- Modify: `crackerjack/services/git_cleanup_service.py:95-105` (expose or extend the validation hook)
- Modify: `crackerjack/core/preflight.py:75-80, 176-180` (route through guard)
- Modify: `crackerjack/core/file_lifecycle.py:85-114` and `crackerjack/services/safe_code_modifier.py:201-242` (no behavior change in this task — verify the API exists)
- Test: `tests/unit/services/test_git_cleanup.py::test_dirty_tree_refuses_fix`
- Test: `tests/unit/services/test_safe_code_modifier.py::test_unsafe_creates_bak_sibling`
- Test: `tests/unit/core/test_preflight.py::test_dirty_tree_blocks_fix_invocation`

**Interfaces:**

- `crackerjack.services.git_cleanup_service.validate_working_tree_clean(allow_dirty: bool = False) -> None` — raises a typed error when dirty and `allow_dirty=False`.

- `crackerjack.services.safe_code_modifier.SafeCodeModifier.apply_with_backup(content: str, path: Path, allow_unsafe: bool = False) -> str` — when `allow_unsafe=True`, produces a `.bak` sibling before rewrite.

- [ ] **Step 1: Read the existing `_validate_working_tree_clean` and `SafeCodeModifier` APIs**

Open `crackerjack/services/git_cleanup_service.py:95-105` and `crackerjack/services/safe_code_modifier.py:201-242`. Confirm the public surface that this task relies on. If signatures differ from the interface block above, adapt the test code in this task to match what is present, and add a comment that explains the divergence.

- [ ] **Step 2: Write the failing test for the dirty-tree guard**

Append to `tests/unit/services/test_git_cleanup.py`:

```python
def test_dirty_tree_refuses_fix(tmp_path, monkeypatch) -> None:
    """When the tree is dirty and allow_dirty=False, validate_working_tree_clean raises."""
    import subprocess

    from crackerjack.services.git_cleanup_service import validate_working_tree_clean

    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    (repo / "a.txt").write_text("clean\n")
    subprocess.run(["git", "add", "a.txt"], cwd=repo, check=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "init"],
        cwd=repo,
        check=True,
        env={
            "GIT_AUTHOR_NAME": "t",
            "GIT_AUTHOR_EMAIL": "t@x",
            "GIT_COMMITTER_NAME": "t",
            "GIT_COMMITTER_EMAIL": "t@x",
            "PATH": __import__("os").environ["PATH"],
        },
    )
    (repo / "a.txt").write_text("dirty\n")

    monkeypatch.chdir(repo)

    try:
        validate_working_tree_clean(allow_dirty=False)
    except Exception as exc:
        assert "dirty" in str(exc).lower() or "clean" in str(exc).lower()
        return

    raise AssertionError("validate_working_tree_clean must refuse a dirty tree")
```

- [ ] **Step 3: Run the test and confirm it fails**

Run: `pytest tests/unit/services/test_git_cleanup.py::test_dirty_tree_refuses_fix -v`
Expected: FAIL with `ImportError` on `validate_working_tree_clean` or `AssertionError` (the function silently accepts a dirty tree).

- [ ] **Step 4: Expose `validate_working_tree_clean` from `git_cleanup_service.py`**

In `crackerjack/services/git_cleanup_service.py:95-105`, rename or wrap the existing `_validate_working_tree_clean` so it is importable as `validate_working_tree_clean`. If the existing function checks the tree state and only emits a warning, change it to raise a typed exception (e.g. `DirtyWorkingTreeError`) when `allow_dirty=False`. If `allow_dirty=True`, it MUST succeed silently and return `None`.

Public surface:

```python
def validate_working_tree_clean(allow_dirty: bool = False) -> None:
    """Raise DirtyWorkingTreeError when the working tree is dirty.

    When allow_dirty=True, return None without raising so the caller can
    proceed (used by --force / --allow-dirty overrides).
    """
```

- [ ] **Step 5: Re-run the test and confirm it passes**

Run: `pytest tests/unit/services/test_git_cleanup.py::test_dirty_tree_refuses_fix -v`
Expected: PASS.

- [ ] **Step 6: Write the failing test for `SafeCodeModifier` bak siblings**

Append to `tests/unit/services/test_safe_code_modifier.py`:

```python
def test_unsafe_creates_bak_sibling(tmp_path) -> None:
    from pathlib import Path

    from crackerjack.services.safe_code_modifier import SafeCodeModifier

    target = tmp_path / "module.py"
    target.write_text("original = 1\n")
    modifier = SafeCodeModifier()

    modifier.apply_with_backup(
        "modified = 2\n",
        path=target,
        allow_unsafe=True,
    )

    bak = target.with_suffix(target.suffix + ".bak")
    assert bak.exists(), f"expected .bak sibling at {bak}"
    assert bak.read_text() == "original = 1\n"
    assert target.read_text() == "modified = 2\n"
```

- [ ] **Step 7: Run the test and confirm it fails**

Run: `pytest tests/unit/services/test_safe_code_modifier.py::test_unsafe_creates_bak_sibling -v`
Expected: FAIL on `apply_with_backup` missing or on the `.bak` assertion.

- [ ] **Step 8: Implement or expose `apply_with_backup`**

In `crackerjack/services/safe_code_modifier.py`, add a method on `SafeCodeModifier`:

```python
    def apply_with_backup(
        self,
        new_content: str,
        *,
        path: Path,
        allow_unsafe: bool = False,
    ) -> None:
        if allow_unsafe:
            bak = path.with_suffix(path.suffix + ".bak")
            bak.write_text(path.read_text())
        path.write_text(new_content)
```

If a different backup suffix is the project convention, use that. The contract is: when `allow_unsafe=True`, a sibling file is produced *before* the rewrite.

- [ ] **Step 9: Re-run the test and confirm it passes**

Run: `pytest tests/unit/services/test_safe_code_modifier.py::test_unsafe_creates_bak_sibling -v`
Expected: PASS.

- [ ] **Step 10: Wire the guard into `preflight.py`**

In `crackerjack/core/preflight.py:75-80` and `:176-180`, call `validate_working_tree_clean()` before constructing any Ruff command that includes `--fix`. If the wrapper takes an `allow_dirty` parameter, plumb it from the `HookSettings` model. The block at `:176-180` should now read from `HookSettings.ruff_unsafe_fixes` instead of the bare `PreflightConfig.ruff_unsafe_fixes` field, to match the spec.

- [ ] **Step 11: Write the failing test for preflight guard**

Append to `tests/unit/core/test_preflight.py`:

```python
def test_dirty_tree_blocks_fix_invocation(tmp_path, monkeypatch) -> None:
    """Preflight must not run ruff --fix on a dirty tree without an override."""
    from crackerjack.core.preflight import PreflightFixer
    from crackerjack.config.settings import HookSettings

    fixer = PreflightFixer(settings=HookSettings(ruff_unsafe_fixes=False))
    # The fixer must call validate_working_tree_clean() before subprocess.run.
    # If it does, a dirty tree must surface as a DirtyWorkingTreeError, not
    # silently rewrite files.
    import subprocess

    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    (repo / "a.txt").write_text("clean\n")
    subprocess.run(["git", "add", "a.txt"], cwd=repo, check=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "init"],
        cwd=repo,
        check=True,
        env={
            "GIT_AUTHOR_NAME": "t",
            "GIT_AUTHOR_EMAIL": "t@x",
            "GIT_COMMITTER_NAME": "t",
            "GIT_COMMITTER_EMAIL": "t@x",
            "PATH": __import__("os").environ["PATH"],
        },
    )
    (repo / "a.txt").write_text("dirty\n")
    monkeypatch.chdir(repo)

    try:
        fixer.run_ruff_check()
    except Exception as exc:  # noqa: BLE001
        assert "dirty" in str(exc).lower() or "clean" in str(exc).lower(), (
            f"preflight must surface dirty-tree refusal; got {exc!r}"
        )
        return

    raise AssertionError("preflight must refuse to run --fix on a dirty tree")
```

- [ ] **Step 12: Re-run the test and confirm it passes**

Run: `pytest tests/unit/core/test_preflight.py::test_dirty_tree_blocks_fix_invocation -v`
Expected: PASS.

- [ ] **Step 13: Run the affected suite**

Run: `pytest tests/unit/services/test_git_cleanup.py tests/unit/services/test_safe_code_modifier.py tests/unit/core/test_preflight.py -v`
Expected: all pass.

- [ ] **Step 14: Commit Stage 3**

```bash
git -C /Users/les/Projects/crackerjack add \
    crackerjack/services/git_cleanup_service.py \
    crackerjack/services/safe_code_modifier.py \
    crackerjack/core/preflight.py \
    tests/unit/services/test_git_cleanup.py \
    tests/unit/services/test_safe_code_modifier.py \
    tests/unit/core/test_preflight.py
git -C /Users/les/Projects/crackerjack commit -m "feat(ruff): dirty-tree guard + bak-sibling rollback

- services/git_cleanup_service.py: validate_working_tree_clean(allow_dirty=False)
  raises DirtyWorkingTreeError when the tree is dirty
- services/safe_code_modifier.py: SafeCodeModifier.apply_with_backup writes a
  .bak sibling before unsafe rewrites
- core/preflight.py: preflight refuses to run ruff --fix on a dirty tree and
  reads ruff_unsafe_fixes from HookSettings

Stage 3 of the Ruff fix-safety policy."
```

______________________________________________________________________

## Task 5: Stage 4 — Pin Ruff, surface Ruff exit-code 2, and add a golden-diff test

**Files:**

- Modify: `pyproject.toml:54` (pin `ruff==0.16.0`)
- Modify: `crackerjack/core/preflight.py:135-143` (explicit 0/1/2 handling)
- Modify: `uv.lock` (separately reviewable commit; in this task, run `uv lock` and commit the diff)
- Create: `tests/fixtures/ruff_unsafe_diff_golden.txt`
- Create: `tests/unit/core/test_ruff_unsafe_golden.py`
- Test: `tests/unit/core/test_preflight.py::test_exit_code_routing`

**Interfaces:**

- `pyproject.toml` declares `ruff==0.16.0` (exact pin, no `>=`).

- `crackerjack.core.preflight.PreflightFixer._route_ruff_exit(returncode: int, output: str) -> int` — returns the exit code for the run report, and:

  - `0` → clean or all eligible fixes applied; pass through.
  - `1` → violations remain or fixes applied; pass through.
  - `2` → raise `RuffInternalError` carrying the output.

- [ ] **Step 1: Write the failing test for exit-code routing**

Append to `tests/unit/core/test_preflight.py`:

```python
def test_exit_code_routing() -> None:
    """Ruff exit code 2 must be surfaced, not silently accepted as success."""
    import pytest

    from crackerjack.core.preflight import route_ruff_exit

    assert route_ruff_exit(0, "") == 0
    assert route_ruff_exit(1, "violations remain") == 1

    with pytest.raises(Exception) as excinfo:
        route_ruff_exit(2, "ruff internal failure")
    assert (
        "internal" in str(excinfo.value).lower() or "ruff" in str(excinfo.value).lower()
    )
```

If the actual function is named differently, adapt the test to the real name. The contract is: codes 0/1 pass through; code 2 raises.

- [ ] **Step 2: Run the test and confirm it fails**

Run: `pytest tests/unit/core/test_preflight.py::test_exit_code_routing -v`
Expected: FAIL with `ImportError` on `route_ruff_exit` (or assertion on the raised exception).

- [ ] **Step 3: Add `route_ruff_exit` to `crackerjack/core/preflight.py`**

In `crackerjack/core/preflight.py`, add:

```python
class RuffInternalError(RuntimeError):
    """Raised when Ruff returns a non-zero exit code that is not a normal lint failure."""


def route_ruff_exit(returncode: int, output: str) -> int:
    """Pass 0/1 through; raise on 2.

    Exit code 0 = clean or all eligible fixes applied.
    Exit code 1 = violations remain (or applied fixes under chosen policy).
    Exit code 2 = Ruff internal, configuration, or parse error.
    """
    if returncode in (0, 1):
        return returncode
    if returncode == 2:
        msg = f"Ruff exit 2: internal error or invalid configuration: {output!r}"
        raise RuffInternalError(msg)
    msg = f"Ruff returned unexpected exit code {returncode}: {output!r}"
    raise RuffInternalError(msg)
```

Replace the existing `result.returncode in (0, 1)` pattern at `preflight.py:165` with a call to `route_ruff_exit`. Surface `RuffInternalError` in the run report rather than swallowing it.

- [ ] **Step 4: Re-run the test and confirm it passes**

Run: `pytest tests/unit/core/test_preflight.py::test_exit_code_routing -v`
Expected: PASS.

- [ ] **Step 5: Create the golden-diff fixture**

Create `tests/fixtures/ruff_unsafe_diff_golden.txt` with the expected unified diff for a single canonical unsafe-fixable file. The fixture is generated by:

```bash
cd /Users/les/Projects/crackerjack
uv run --no-sync ruff check --diff --select RUF012 tests/fixtures/ruff_unsafe_golden_input.py
```

and saving the output. The test in this task runs the same command and compares against the golden file.

- [ ] **Step 6: Write the golden-diff test**

Create `tests/unit/core/test_ruff_unsafe_golden.py`:

```python
"""Golden-diff test for the unsafe-fix output.

Catches upstream Ruff rule changes that would silently alter the diff and
introduce a new auto-applied rewrite. Update the golden file via:

    uv run --no-sync ruff check --diff --select RUF012 \\
        tests/fixtures/ruff_unsafe_golden_input.py \\
        > tests/fixtures/ruff_unsafe_diff_golden.txt

The update must be reviewed by a human before commit.
"""

from pathlib import Path

FIXTURE_DIR = Path(__file__).resolve().parents[2] / "fixtures"
GOLDEN_DIFF = FIXTURE_DIR / "ruff_unsafe_diff_golden.txt"
GOLDEN_INPUT = FIXTURE_DIR / "ruff_unsafe_golden_input.py"


def test_unsafe_diff_matches_golden() -> None:
    import subprocess

    if not GOLDEN_INPUT.exists():
        import pytest

        pytest.skip(f"missing {GOLDEN_INPUT}; create it before running this test")

    result = subprocess.run(
        [
            "uv",
            "run",
            "--no-sync",
            "ruff",
            "check",
            "--diff",
            "--select",
            "RUF012",
            str(GOLDEN_INPUT),
        ],
        capture_output=True,
        text=True,
        cwd=FIXTURE_DIR,
    )
    # Exit 1 means fixes would be applied; that is the expected signal here.
    assert result.returncode in (0, 1)
    assert result.stdout == GOLDEN_DIFF.read_text()
```

- [ ] **Step 7: Run the test and confirm it currently fails**

Run: `pytest tests/unit/core/test_ruff_unsafe_golden.py -v`
Expected: FAIL on missing fixture, missing input, or stdout mismatch.

- [ ] **Step 8: Generate the canonical input file**

Create `tests/fixtures/ruff_unsafe_golden_input.py`:

```python
"""Canonical input for the unsafe-fix golden-diff test.

R012 (mutable-class-default) is a stable unsafe-fixable rule. Touching this
file changes the golden diff and requires a human-bless step.
"""


class Container:
    def __init__(self, items: list[int] = []) -> None:  # RUF012
        self.items = items
```

- [ ] **Step 9: Generate the golden diff**

Run: `cd /Users/les/Projects/crackerjack && uv run --no-sync ruff check --diff --select RUF012 tests/fixtures/ruff_unsafe_golden_input.py > tests/fixtures/ruff_unsafe_diff_golden.txt`

Confirm the file content is a single unified diff hunk and commit only after a human review.

- [ ] **Step 10: Re-run the golden test and confirm it passes**

Run: `pytest tests/unit/core/test_ruff_unsafe_golden.py -v`
Expected: PASS.

- [ ] **Step 11: Pin Ruff in `pyproject.toml:54`**

Change the line in `pyproject.toml` from:

```toml
    "ruff>=0.15.18",
```

to:

```toml
    "ruff==0.16.0",
```

- [ ] **Step 12: Refresh the lockfile**

Run: `cd /Users/les/Projects/crackerjack && uv lock`

Confirm the resulting `uv.lock` change is a single-package bump consistent with `ruff==0.16.0`. If other packages also bumped, inspect the diff and verify each change is intentional and reviewable.

- [ ] **Step 13: Run the full unit suite to confirm no regressions**

Run: `cd /Users/les/Projects/crackerjack && pytest -m "not slow" -q`
Expected: all tests pass (some pre-existing slow tests are skipped; this task only adds and modifies tests in the `unit` namespace).

- [ ] **Step 14: Commit the pin and lockfile as one commit**

```bash
git -C /Users/les/Projects/crackerjack add pyproject.toml uv.lock
git -C /Users/les/Projects/crackerjack commit -m "build(deps): pin ruff==0.16.0

Stage 4 of the Ruff fix-safety policy. The exact pin is the floor for
reproducible CI; safe-fix defaults remain the primary contract."
```

- [ ] **Step 15: Commit the exit-code routing and golden test as a separate commit**

```bash
git -C /Users/les/Projects/crackerjack add \
    crackerjack/core/preflight.py \
    tests/fixtures/ruff_unsafe_diff_golden.txt \
    tests/fixtures/ruff_unsafe_golden_input.py \
    tests/unit/core/test_preflight.py \
    tests/unit/core/test_ruff_unsafe_golden.py
git -C /Users/les/Projects/crackerjack commit -m "feat(ruff): surface Ruff exit-code 2; add golden-diff test

- core/preflight.py: route_ruff_exit(0/1) pass through; 2 raises
  RuffInternalError so configuration/parse failures can never look like
  a clean quality run
- tests/fixtures/ruff_unsafe_golden_input.py and
  tests/fixtures/ruff_unsafe_diff_golden.txt: pin the unsafe-fix diff
  for RUF012 to catch silent upstream changes

Stage 4 of the Ruff fix-safety policy."
```

______________________________________________________________________

## Task 6: Stage 5 — Documentation and changelog

**Files:**

- Modify: `docs/CLI_REFERENCE.md`

- Modify: `crackerjack/hooks/README.md`

- Modify: `CHANGELOG.md`

- Modify: `docs/CONFIG_CONSOLIDATION_AUDIT.md:729`

- [ ] **Step 1: Add the subcommand × fix-level matrix to `docs/CLI_REFERENCE.md`**

Append a new section under the appropriate anchor. Use this exact table:

```markdown
### Ruff fix-safety matrix

| Subcommand / path                      | Default   | Mutates files? | Notes                                       |
|----------------------------------------|-----------|----------------|---------------------------------------------|
| `crackerjack run`                      | safe fix  | yes (safe)     | `--fix` only; no `--unsafe-fixes`           |
| `crackerjack run --preview`            | preview   | no             | `ruff check --diff`                         |
| `crackerjack run --allow-unsafe-fixes` | unsafe    | yes (unsafe)   | Per-file `.bak` siblings; dirty-tree guard  |
| CI / `crackerjack run --no-fix`        | read-only | no             | Fails on remaining violations               |
| Generated `pyproject.toml`             | safe      | n/a            | `unsafe-fixes = false`                      |
```

- [ ] **Step 2: Add a "Safe vs. Unsafe Fixes" subsection to `crackerjack/hooks/README.md`**

Insert (or replace the closest existing section) with:

```markdown
### Safe vs. Unsafe Fixes

The default `ruff-check` hook in this repository applies Ruff's safe fixes
only. Unsafe fixes (those that may change runtime behavior or delete
comments) are an explicit opt-in. See
`docs/superpowers/specs/2026-08-06-crackerjack-ruff-fix-policy-design.md`
for the design rationale.

- Default: `ruff check --output-format json --fix ./crackerjack`
- Read-only (CI / gate): `ruff check --output-format json --no-fix ./crackerjack`
- Preview: `ruff check --diff ./crackerjack`
- Unsafe (opt-in): `crackerjack run --allow-unsafe-fixes`
```

- [ ] **Step 3: Add a `CHANGELOG.md` entry**

Append a single entry near the top of the unreleased section, mirroring the historical `enable-unsafe-fixes` line for traceability:

```markdown
- Ruff fix-safety policy: default hook drops `--unsafe-fixes`; explicit
  `--allow-unsafe-fixes` opt-in; generated config sets `unsafe-fixes=false`;
  Ruff pinned to `0.16.0`. See
  `docs/superpowers/specs/2026-08-06-crackerjack-ruff-fix-policy-design.md`.
```

- [ ] **Step 4: Resolve the `config_template.py:62` divergence in `docs/CONFIG_CONSOLIDATION_AUDIT.md`**

In the section near line 729, add a short note that the divergence is resolved by the Stage 0 change: the scaffolded `pyproject.toml` now emits `"unsafe-fixes": False`. Keep the note to one paragraph; do not rewrite the rest of the file.

- [ ] **Step 5: Verify all docs references compile**

Run: `cd /Users/les/Projects/crackerjack && grep -n "ruff-unsafe-fixes\|ruff fix-safety" docs/CLI_REFERENCE.md crackerjack/hooks/README.md CHANGELOG.md docs/CONFIG_CONSOLIDATION_AUDIT.md`
Expected: at least one match per file (the references introduced in Steps 1-4).

- [ ] **Step 6: Commit Stage 5**

```bash
git -C /Users/les/Projects/crackerjack add \
    docs/CLI_REFERENCE.md \
    crackerjack/hooks/README.md \
    CHANGELOG.md \
    docs/CONFIG_CONSOLIDATION_AUDIT.md
git -C /Users/les/Projects/crackerjack commit -m "docs(ruff): document safe-by-default fix policy

- docs/CLI_REFERENCE.md: subcommand x fix-level matrix
- crackerjack/hooks/README.md: Safe vs. Unsafe Fixes section
- CHANGELOG.md: release-note entry
- docs/CONFIG_CONSOLIDATION_AUDIT.md: resolve config_template.py:62 divergence

Stage 5 of the Ruff fix-safety policy."
```

______________________________________________________________________

## Self-Review

**Spec coverage:**

- §4.1 safe fixes only — Task 1 Step 3 and Task 3 Step 3.
- §4.2 read-only CI — Task 5 Step 3 (exit-code routing) plus the spec note that the existing `all_commands` tuple already uses `--check` and `--no-fix`.
- §4.3 preview path — covered by `crackerjack run --preview` in Task 6 Step 1; the underlying `--diff` mechanism is Ruff-native and requires no new wrapper.
- §4.4 explicit unsafe opt-in — Task 1 Step 3, Task 2 Step 10, Task 3 Step 3.
- §4.5 scaffold default — Task 1 Step 7.
- §4.6 exit-code 0/1/2 — Task 5 Step 3.
- §4.7 working-tree guard — Task 4 Steps 2-12.
- §4.8 Ruff pinning — Task 5 Steps 11-14.
- §4.9 must-not-change paths — no task touches them; explicitly preserved in the global constraints.
- §5 tests — every named test from the spec has a matching test in this plan (`test_tool_commands_respects_hook_settings_unsafe_fixes` ↔ Task 3 Step 1, `test_unsafe_only_auto_promotes_fix` ↔ Task 3 Step 5, `test_unsafe_creates_bak_sibling` ↔ Task 4 Step 6, `test_dirty_tree_refuses_fix` ↔ Task 4 Step 2, `test_unsafe_flag_threaded_to_preflight` ↔ Task 2 Step 11, `test_exit_code_routing` ↔ Task 5 Step 1, `test_ruff_unsafe_golden` ↔ Task 5 Step 6).
- §6 docs — Task 6.
- §7 rollout — Tasks 1-6 are staged in the same order.
- §8 fastest path — reflected in Task 6 Step 1's matrix.

**Placeholder scan:** No "TBD" / "TODO" / "implement later". Every step has explicit code or commands. Where a project's actual API name diverges from the contract (e.g. `validate_working_tree_clean` vs `_validate_working_tree_clean`), the plan instructs the engineer to adapt and document the divergence inline.

**Type consistency:**

- `HookSettings.ruff_unsafe_fixes: bool` defined in Task 2 and consumed in Task 3 (`get_tool_command(settings=...)`) and Task 4 (preflight guard). Same field name throughout.
- `validate_working_tree_clean(allow_dirty: bool)` defined in Task 4 Step 4 and called in Task 4 Step 10 with no other signature change.
- `apply_with_backup(content, *, path, allow_unsafe)` defined in Task 4 Step 8 and asserted in Task 4 Step 6 with the same parameter order.
- `route_ruff_exit(returncode, output)` defined in Task 5 Step 3 and asserted in Task 5 Step 1 with the same signature.
- CLI flags `--allow-unsafe-fixes` and `--safe-only` defined in Task 2 and called in Task 6's matrix as the public surface.

No spec requirement is missing a task. No placeholder, no ambiguous contract. Plan ready for execution.
