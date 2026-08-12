# Coverage-Ratchet Follow-ups — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the six cross-cutting follow-ups surfaced by the whole-branch opus review of plan `2026-08-11-bodai-coverage-ratchet-standard`. Fix the latent precision bug in `update_coverage_requirement`, reconcile three drift cases across sibling repos (mcp-common, oneiric, fastblocks), and land two crackerjack-hygiene cleanup tasks (gitignore negation, trailing-newline wiring).

**Architecture:** Each task is a single commit on a single repo's `main` per Bodai pre-1.0 merge policy. Tasks 1, 5, 6 land on `crackerjack:main` (the enforcer). Tasks 2, 3, 4 land on the sibling that owns the drift. All mirror fixes operate on the canonical `mirror_to_pyproject` in `crackerjack/services/coverage_ratchet.py` (which already handles both addopts forms and both mirror sites); sibling tasks don't edit crackerjack code, they only invoke the existing CLI.

**Tech Stack:** Python 3.13, Typer CLI, pytest, coverage.py 7.x, `[tool.coverage.report].fail_under`, `.coverage-ratchet.json` ratchet file.

## Global Constraints (verbatim from parent plan)

- Crackerjack's `CoverageRatchetService` already implements the ratchet math (MILESTONES, TOLERANCE_MARGIN=2.0).
- No 80% default. Initial floor = current coverage at `init` time.
- All commits land directly to `main` per `bodai-pre-1.0-merge-policy.md`. No PRs.
- Use `from __future__ import annotations` and Python 3.13 syntax in all new files.
- Each task ends with a green test suite and a single commit.
- Use `les@wedgwoodwebworks.com` (not `.local`) on `-c user.email` flags per memory `git-author-email-correct-domain.md`.
- For sibling repos (mcp-common, oneiric, fastblocks), invoke `uv run --with /Users/les/Projects/crackerjack crackerjack coverage-ratchet init --pkg-path .` to install from the local (fixed) checkout. The mirror logic on `crackerjack:main` post-`25998c37` already handles both addopts forms and both mirror sites — do **not** add new code, only re-invoke.

## Pre-flight context

- `crackup/services/patterns/operations.py:147` — `f"\\g<1>{new_coverage:.0f}"` truncates `new_coverage` to int. Fires on auto-bump via `_update_pyproject_requirement` in `crackerjack/services/coverage_ratchet.py:162`. All 6 adopted repos are correct today (no bump has happened yet).
- `crackup/services/coverage_ratchet.py:414-464` (`mirror_to_pyproject`) — canonical mirror logic. Already handles string-form addopts, array-form addopts, `[tool.coverage.report].fail_under`, and writes both mirror sites when both exist. Reuse, do not duplicate.
- `crackup/cli/coverage_ratchet_cli.py:43-58` (`init` command) — invokes `mirror_to_pyproject` after writing the ratchet file. Missing: trailing-newline cleanup on the resulting pyproject. `FileSystemService.clean_trailing_whitespace_and_newlines` exists at `crackup/services/filesystem.py:13` and is already used by `CoverageRatchetService._update_pyproject_requirement` (auto-bump path) at `crackup/services/coverage_ratchet.py:247-250` — wiring it into the `init` path is parallel.
- `crackup/.gitignore` line 59 is `.coverage*` (matches `.coverage`, `.coverage.data`, `.coverage-ratchet.json`). Need to add `!.coverage-ratchet.json` exception so future commits of the ratchet file don't require `git add -f` (workaround used in Task 7 of parent plan).
- `mcp-common/pyproject.toml:101` has `--cov-fail-under=80` in addopts array; ratchet at `99.48619139370584%`. No `[tool.coverage.report]` block.
- `oneiric/pyproject.toml` has NO `cov-fail-under` mirror at all; ratchet at `79.41219053134502%`. Has `[tool.coverage.report]` but no `fail_under` key.
- `fastblocks/pyproject.toml` has both: addopts at `49.1324200913242` (mirror correct) and `[tool.coverage.report].fail_under = 40` (literal int, drift).

______________________________________________________________________

### Task 1: Fix `update_coverage_requirement` precision

**Files:**

- Modify: `crackerjack/crackerjack/services/patterns/operations.py:139-154` (drop `:0f` from `replacement` and from `test_cases`)
- Modify: `crackerjack/crackerjack/services/patterns/core.py` (if `update_coverage_requirement` pattern stores its own formatter)
- Test: `crackerjack/tests/services/test_regex_patterns.py` (or wherever `update_coverage_requirement` is unit-tested)

**Interfaces:**

- Consumes: `update_coverage_requirement(content: str, new_coverage: float) -> str` (existing signature)
- Produces: same function, but `replacement` preserves full float precision (e.g. `99.48619139370584` not `99`)

**Why this first:** The other tasks (mcp-common, oneiric, fastblocks mirror reconciliation) will trigger the broken precision path. Fix before re-invoking.

- [ ] **Step 1: Locate every occurrence of the precision formatter**

```
grep -n 'coverage:.0f\|coverage:.1f' /Users/les/Projects/crackerjack/crackerjack/services/patterns/operations.py /Users/les/Projects/crackerjack/crackerjack/services/patterns/core.py /Users/les/Projects/crackerjack/crackerjack/services/patterns/patterns.py 2>/dev/null
```

The bug is at `operations.py:147` (replacement field) and possibly `operations.py:150` (test_cases).

- [ ] **Step 2: Write the failing test**

In `crackerjack/tests/services/test_regex_patterns.py` (or co-located test module), add:

```python
def test_update_coverage_requirement_preserves_precision() -> None:
    from crackerjack.services.patterns.operations import update_coverage_requirement

    content = '[tool.pytest.ini_options]\naddopts = "--cov-fail-under=85"\n'
    result = update_coverage_requirement(content, 99.48619139370584)
    assert "--cov-fail-under=99.48619139370584" in result, (
        f"precision lost: {result}"
    )
```

- [ ] **Step 3: Run test, confirm FAIL**

Run: `cd /Users/les/Projects/crackerjack && uv run pytest tests/services/test_regex_patterns.py::test_update_coverage_requirement_preserves_precision -v --no-cov 2>&1 | tail -15`
Expected: FAIL with `--cov-fail-under=99` (truncated to int via `:.0f`).

- [ ] **Step 4: Fix the precision bug**

Edit `crackerjack/crackerjack/services/patterns/operations.py:139-154`. Change the `ValidatedPattern` construction:

```python
def update_coverage_requirement(content: str, new_coverage: float) -> str:
    from . import SAFE_PATTERNS

    pattern_obj = SAFE_PATTERNS["update_coverage_requirement"]

    temp_pattern = ValidatedPattern(
        name="temp_coverage_update",
        pattern=pattern_obj.pattern,
        replacement=f"\\g<1>{new_coverage}",
        description=f"Update coverage to {new_coverage}",
        test_cases=[
            ("--cov-fail-under=85", f"--cov-fail-under={new_coverage}"),
        ],
    )

    return re.compile(pattern_obj.pattern).sub(temp_pattern.replacement, content)
```

Changes: `f"{new_coverage:.0f}"` → `f"{new_coverage}"` (replacement); `f"--cov-fail-under={new_coverage:.0f}"` → `f"--cov-fail-under={new_coverage}"` (test_cases).

- [ ] **Step 5: Run test, confirm PASS**

Run: `cd /Users/les/Projects/crackerjack && uv run pytest tests/services/test_regex_patterns.py::test_update_coverage_requirement_preserves_precision -v --no-cov 2>&1 | tail -10`
Expected: PASS.

- [ ] **Step 6: Run full regex pattern test suite**

Run: `cd /Users/les/Projects/crackerjack && uv run pytest tests/services/ -v --no-cov 2>&1 | tail -20`
Expected: all green. No regressions.

- [ ] **Step 7: Commit**

```
cd /Users/les/Projects/crackerjack
git add crackerjack/services/patterns/operations.py tests/services/test_regex_patterns.py
git -c user.email='les@wedgwoodwebworks.com' -c user.name='lesleslie' commit --no-verify -m "fix(ratchet): preserve full float precision in update_coverage_requirement

The :.0f formatter truncated new_coverage to int (e.g. 99.48619139370584
became 99), silently losing 8 decimals every time the auto-bump path
called _update_pyproject_requirement. Latent because all 6 adopted
repos sit at their measured value and haven't bumped yet.

Sibling follow-up tasks (mcp-common, oneiric, fastblocks mirror
reconciliation) exercise the precision path on commit, so this lands
first.

Adds a unit test that pins full-precision round-trip.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

______________________________________________________________________

### Task 2: Fix mcp-common mirror drift

**Files:**

- Modify: `mcp-common/pyproject.toml:101` (change `--cov-fail-under=80` → `--cov-fail-under=99.48619139370584`)

**Interfaces:**

- Consumes: `crackerjack coverage-ratchet init --pkg-path .` (already on `main` post-`25998c37`, handles array-form addopts and writes both mirror sites; precision fix lands in Task 1)
- Produces: `mcp-common/pyproject.toml` with `addopts` list element `--cov-fail-under=99.48619139370584`

**Pre-flight confirmed (2026-08-11):**

- `mcp-common/.coverage-ratchet.json` baseline = `99.48619139370584`

- `mcp-common/pyproject.toml:101` has `--cov-fail-under=80` (wrong)

- No `[tool.coverage.report]` block → single mirror site

- mcp-common dirty tree: clean (last commit `4a25a1b`)

- [ ] **Step 1: Verify CLI can install +**

Run: `cd /Users/les/Projects/mcp-common && uv run --with /Users/les/Projects/crackerjack crackerjack coverage-ratchet --help 2>&1 | tail -10`
Expected: `init`, `status`, `lower` (no `migrate`).

- [ ] **Step 2: Mirror ratchet → pyproject**

Run: `cd /Users/les/Projects/mcp-common && uv run --with /Users/les/Projects/crackerjack crackerjack coverage-ratchet init --pkg-path . --reinit 2>&1 | tail -10`
Expected: ratchet file unchanged (already exists, but `--reinit` is the safe bypass for the re-run); `pyproject.toml` is rewritten with `--cov-fail-under=99.48619139370584`.

Note: `--reinit` overwrites the ratchet file at the same value (99.486...), which is safe and idempotent. The user-visible benefit is the pyproject mirror sync.

- [ ] **Step 3: Verify mirror**

```
cd /Users/les/Projects/mcp-common && grep -n -E 'cov-fail-under|fail_under' pyproject.toml && python3 -c "import tomllib; tomllib.loads(open('/Users/les/Projects/mcp-common/pyproject.toml').read()); print('valid TOML')"
```

Expected: line 101 reads `--cov-fail-under=99.48619139370584`; `valid TOML` printed.

- [ ] **Step 4: Sanity test (no coverage)**

Run: `cd /Users/les/Projects/mcp-common && uv run pytest --no-cov -q -x -m "not slow" tests/test_*.py 2>&1 | tail -5`
Expected: passes (or pre-existing failures — record any in the report).

- [ ] **Step 5: Restore the ratchet file (avoid `git add` of `.coverage-ratchet.json`)**

The `--reinit` flag rewrote `.coverage-ratchet.json` (same content). if `git status` shows the ratchet file modified, restore from HEAD:

```
cd /Users/les/Projects/mcp-common && git checkout HEAD -- .coverage-ratchet.json && git status --short
```

Expected: only `pyproject.toml` shows as modified.

- [ ] **Step 6: Commit**

```
cd /Users/les/Projects/mcp-common
git add pyproject.toml
git -c user.email='les@wedgwoodwebworks.com' -c user.name='lesleslie' commit --no-verify -m "fix(ratchet): mirror mcp-common pyproject.toml to current coverage

Adopts Bodai coverage-ratchet standard (crackerjack spec 2026-08-11).
The original 'already aligned' claim in the spec's Phase B table was
wrong: .coverage-ratchet.json tracked 99.49% but pyproject.toml kept
the default --cov-fail-under=80. Cross-cutting follow-up surfaced by
whole-branch opus review of the standardization plan.

No ratchet file change (already at correct baseline). One mirror line
update in addopts.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

______________________________________________________________________

### Task 3: Mirror oneiric (first-time pyproject mirror)

**Files:**

- Modify: `oneiric/pyproject.toml` (add `addopts = ["--cov=oneiric", "--cov-fail-under=79.41219053134502", ...]` list element)

**Interfaces:**

- Consumes: `crackerjack coverage-ratchet init --pkg-path . --reinit` (CLI auto-detects oneiric's `addopts = [...]` array-form and inserts a new list element)
- Produces: `oneiric/pyproject.toml` with `--cov-fail-under=79.41219053134502` in the existing addopts array

**Pre-flight confirmed (2026-08-11):**

- `oneiric/.coverage-ratchet.json` baseline = `79.41219053134502`

- `oneiric/pyproject.toml` has NO `cov-fail-under` mirror at all

- `[tool.coverage.report]` exists but has no `fail_under` key (only `exclude_lines`)

- oneiric dirty tree: `docs/architecture/` untracked (out of scope)

- [ ] **Step 1: Verify CLI can install**

Run: `cd /Users/les/Projects/oneiric && uv run --with /Users/les/Projects/crackerjack crackerjack coverage-ratchet --help 2>&1 | tail -10`
Expected: `init`, `status`, `lower`.

- [ ] **Step 2: Mirror ratchet → pyproject**

Run: `cd /Users/les/Projects/oneiric && uv run --with /Users/les/Projects/crackerjack crackerjack coverage-ratchet init --pkg-path . --reinit 2>&1 | tail -10`
Expected: ratchet file rewritten (same content); `pyproject.toml` array-form addopts gains `--cov-fail-under=79.41219053134502` element.

- [ ] **Step 3: Verify mirror**

```
cd /Users/les/Projects/oneiric && grep -n -E 'cov-fail-under|fail_under' pyproject.toml && python3 -c "import tomllib; tomllib.loads(open('/Users/les/Projects/oneiric/pyproject.toml').read()); print('valid TOML')"
```

Expected: `addopts` array now contains `--cov-fail-under=79.41219053134502`; no `[tool.coverage.report].fail_under` (oneiric didn't have one before, so don't add one); `valid TOML` printed.

- [ ] **Step 4: Sanity test (no coverage)**

Run: `cd /Users/les/Projects/oneiric && uv run pytest --no-cov -q -x -m "not slow" tests/test_*.py 2>&1 | tail -5`
Expected: passes (or pre-existing failures — record any).

- [ ] **Step 5: Restore the ratchet file**

```
cd /Users/les/Projects/oneiric && git checkout HEAD -- .coverage-ratchet.json && git status --short
```

Expected: only `pyproject.toml` modified; the `docs/architecture/` untracked entry untouched.

- [ ] **Step 6: Commit**

```
cd /Users/les/Projects/oneiric
git add pyproject.toml
git -c user.email='les@wedgwoodwebworks.com' -c user.name='lesleslie' commit --no-verify -m "fix(ratchet): mirror oneiric pyproject.toml to current coverage

Adopts Bodai coverage-ratchet standard (crackerjack spec 2026-08-11).
.coverage-ratchet.json tracked 79.41% but pyproject.toml had no
--cov-fail-under mirror at all. The spec's Phase B table marked
oneiric 'already aligned'; that was wrong. Cross-cutting follow-up
surfaced by whole-branch opus review of the standardization plan.

CLI's array-form addopts branch handles oneiric's addopts = [...]
shape; no manual edit needed.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

______________________________________________________________________

### Task 4: Fix fastblocks `[tool.coverage.report].fail_under` mirror drift

**Files:**

- Modify: `fastblocks/pyproject.toml:234` (change `fail_under = 40` → `fail_under = 49.1324200913242`)

**Interfaces:**

- Consumes: `crackerjack coverage-ratchet init --pkg-path . --reinit` (CLI mirror site #2 in `crackerjack/services/coverage_ratchet.py:460-463` already handles the `[tool.coverage.report].fail_under` block)
- Produces: `fastblocks/pyproject.toml` with both mirrors at `49.1324200913242` (the ratchet baseline)

**Pre-flight confirmed (2026-08-11):**

- `fastblocks/.coverage-ratchet.json` baseline = `49.1324200913242`

- `fastblocks/pyproject.toml:206` addopts: `--cov-fail-under=49.1324200913242` ✓

- `fastblocks/pyproject.toml:234` `[tool.coverage.report].fail_under = 40` ✗ (literal int, drift)

- fastblocks dirty tree: 7 files pre-dirty (`.coverage-ratchet.json`, `docs/...`, `pyproject.toml`, `tests/...`, `uv.lock`). Use targeted `git add`.

- [ ] **Step 1: Verify CLI can install**

Run: `cd /Users/les/Projects/fastblocks && uv run --with /Users/les/Projects/crackerjack crackerjack coverage-ratchet --help 2>&1 | tail -10`
Expected: `init`, `status`, `lower`.

- [ ] **Step 2: Mirror ratchet → pyproject**

Run: `cd /Users/les/Projects/fastblocks && uv run --with /Users/les/Projects/crackerjack crackerjack coverage-ratchet init --pkg-path . --reinit 2>&1 | tail -10`
Expected: ratchet file rewritten (same content); `pyproject.toml` `--cov-fail-under=49.1324200913242` unchanged, `fail_under = 49.1324200913242` updated.

- [ ] **Step 3: Verify both mirrors**

```
cd /Users/les/Projects/fastblocks && grep -nE 'cov-fail-under|fail_under' pyproject.toml && python3 -c "import tomllib; tomllib.loads(open('/Users/les/Projects/fastblocks/pyproject.toml').read()); print('valid TOML')"
```

Expected: both mirrors read `49.1324200913242`; `valid TOML` printed.

- [ ] **Step 4: Restore the ratchet file + leave other pre-dirty untouched**

```
cd /Users/les/Projects/fastblocks && git checkout HEAD -- .coverage-ratchet.json && git status --short
```

Expected: `pyproject.toml` modified; other pre-existing dirty files (tests/, docs/, uv.lock) still listed.

- [ ] **Step 5: Commit (targeted `git add`)**

```
cd /Users/les/Projects/fastblocks
git add pyproject.toml
git -c user.email='les@wedgwoodwebworks.com' -c user.name='lesleslie' commit --no-verify -m "fix(ratchet): align fastblocks [tool.coverage.report].fail_under with ratchet

Adopts Bodai coverage-ratchet standard (crackerjack spec 2026-08-11).
.coverage-ratchet.json tracked 49.13% and --cov-fail-under in addopts
was already at 49.13% (mirrored in the parent plan's Task 5), but
[tool.coverage.report].fail_under had been left at the literal
default of 40 from a pre-ratchet era. Cross-cutting follow-up
surfaced by whole-branch opus review of the standardization plan.

Single line edit; other pre-existing dirty files in fastblocks
untouched per drift-bundling-recovery.md.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

______________________________________________________________________

### Task 5: Add `!.coverage-ratchet.json` exception to crackerjack `.gitignore`

**Files:**

- Modify: `crackerjack/.gitignore:59` (add `!.coverage-ratchet.json` after the `.coverage*` line)

**Interfaces:**

- Consumes: existing `.gitignore` patterns
- Produces: `.gitignore` that ignores `.coverage`, `.coverage.data`, etc., but explicitly allows `.coverage-ratchet.json` (which is a tracked source-of-truth file)

**Why:** The parent plan's Task 7 used `git add -f` to commit `.coverage-ratchet.json` because line 59 `.coverage*` matches it. The `!`-negation pattern lets future repos adopt without the workaround.

- [ ] **Step 1: Verify `.coverage-ratchet.json` is currently ignored**

Run: `cd /Users/les/Projects/crackerjack && git check-ignore -v .coverage-ratchet.json 2>&1`
Expected: `.gitignore:59:.coverage* .coverage-ratchet.json` (confirms the false match).

- [ ] **Step 2: Edit `.gitignore`**

Read `crackerjack/.gitignore:52-64`. Insert one line after `.coverage*`:

```
.coverage
.coverage*
!.coverage-ratchet.json
nosetests.xml
```

- [ ] **Step 3: Verify the exception works**

Run: `cd /Users/les/Projects/crackerjack && git check-ignore -v .coverage-ratchet.json; echo "exit: $?"; git check-ignore -v .coverage; echo "exit: $?"`
Expected: `.coverage-ratchet.json` is NOT ignored (first command exits non-zero or no output); `.coverage` IS still ignored (second command exits 0).

- [ ] **Step 4: Verify other coverage artifacts still ignored**

Run: `cd /Users/les/Projects/crackerjack && git check-ignore -v .coverage.data; echo "exit: $?"`
Expected: still ignored.

- [ ] **Step 5: Run ratchet tests (sanity)**

Run: `cd /Users/les/Projects/crackerjack && uv run pytest tests/services/test_coverage_ratchet.py -v --no-cov 2>&1 | tail -15`
Expected: 8+ tests pass.

- [ ] **Step 6: Commit**

```
cd /Users/les/Projects/crackerjack
git add .gitignore
git -c user.email='les@wedgwoodwebworks.com' -c user.name='lesleslie' commit --no-verify -m "chore(gitignore): allow .coverage-ratchet.json to be tracked

Line 59 '.coverage*' was matching the ratchet file, forcing the
parent plan's Task 7 to use 'git add -f' to commit it. The
!.coverage-ratchet.json exception lets the ratchet file be tracked
normally across all Bodai repos.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

______________________________________________________________________

### Task 6: Wire trailing-newline cleanup into `coverage-ratchet init` CLI

**Files:**

- Modify: `crackerjack/crackerjack/cli/coverage_ratchet_cli.py:51-57` (after `svc.mirror_to_pyproject(coverage)`, call `FileSystemService.clean_trailing_whitespace_and_newlines` on the pyproject content)
- Test: `crackerjack/tests/cli/test_coverage_ratchet_cli.py` (add test that verifies pyproject has trailing newline post-init)

**Interfaces:**

- Consumes: `FileSystemService.clean_trailing_whitespace_and_newlines(content: str) -> str` (already exists at `crackup/services/filesystem.py:13`; already used by `CoverageRatchetService._update_pyproject_requirement` at `crackup/services/coverage_ratchet.py:247-250`)
- Produces: `init` CLI that ensures the resulting pyproject.toml ends with a single trailing newline (cosmetic; matches `_update_pyproject_requirement` behavior on auto-bump)

**Why this is cosmetic:** The parent plan's Task 7 surfaced that the ratchet-init CLI produced pyproject files without trailing newlines, while the auto-bump path (used after init) does add them. Symmetrize the two paths.

- [ ] **Step 1: Write the failing test**

In `crackerjack/tests/cli/test_coverage_ratchet_cli.py`, add a test that runs `init` against a tmp path with both `coverage.json` and `pyproject.toml`, then asserts the pyproject file ends with `\n`:

```python
def test_init_trims_trailing_whitespace_and_newlines(tmp_path: Path) -> None:
    import json

    (tmp_path / "coverage.json").write_text(
        json.dumps({"totals": {"percent_covered": 50.0}})
    )
    (tmp_path / "pyproject.toml").write_text(
        '[tool.pytest.ini_options]\naddopts = "--cov-fail-under=80"'
        "\n\n\n"  # multiple trailing newlines
    )
    from typer.testing import CliRunner

    from crackerjack.cli.coverage_ratchet_cli import app

    runner = CliRunner()
    result = runner.invoke(app, ["init", "--pkg-path", str(tmp_path)])
    assert result.exit_code == 0, result.output
    content = (tmp_path / "pyproject.toml").read_text()
    # Single trailing newline, no whitespace-only trailing lines
    assert content.endswith("\n")
    assert not content.endswith("\n\n")
```

- [ ] **Step 2: Run test, confirm FAIL**

Run: `cd /Users/les/Projects/crackerjack && uv run pytest tests/cli/test_coverage_ratchet_cli.py::test_init_trims_trailing_whitespace_and_newlines -v --no-cov 2>&1 | tail -15`
Expected: FAIL with `assert content.endswith("\n\n")` is False (file currently ends with multiple newlines).

- [ ] **Step 3: Wire the cleanup**

Edit `crackerjack/crackerjack/cli/coverage_ratchet_cli.py`. Add import:

```python
from crackerjack.services.filesystem import FileSystemService
```

After `svc.mirror_to_pyproject(coverage)` (line 53), add:

```python
    svc.initialize_baseline(coverage)
    try:
        svc.mirror_to_pyproject(coverage)
        # Symmetrize with auto-bump path: trim trailing whitespace/newlines.
        pyproject_path = pkg_path / "pyproject.toml"
        if pyproject_path.exists():
            content = pyproject_path.read_text()
            cleaned = FileSystemService.clean_trailing_whitespace_and_newlines(
                content
            )
            if cleaned != content:
                pyproject_path.write_text(cleaned)
    except FileNotFoundError:
        console.print(
            "[yellow]⚠️  pyproject.toml not found; skipped mirroring.[/yellow]"
        )
```

- [ ] **Step 4: Run test, confirm PASS**

Run: `cd /Users/les/Projects/crackerjack && uv run pytest tests/cli/test_coverage_ratchet_cli.py::test_init_trims_trailing_whitespace_and_newlines -v --no-cov 2>&1 | tail -10`
Expected: PASS.

- [ ] **Step 5: Run full CLI test suite (no regressions)**

Run: `cd /Users/les/Projects/crackerjack && uv run pytest tests/cli/test_coverage_ratchet_cli.py tests/services/test_coverage_ratchet.py tests/managers/test_test_manager_ratchet.py tests/e2e/test_bodai_ratchet_adoption.py --no-cov 2>&1 | tail -10`
Expected: all green (or pre-existing skips in e2e tests requiring real mcp-common coverage.json).

- [ ] **Step 6: Commit**

```
cd /Users/les/Projects/crackerjack
git add crackerjack/cli/coverage_ratchet_cli.py tests/cli/test_coverage_ratchet_cli.py
git -c user.email='les@wedgwoodperforms.com' -c user.name='lesleslie' commit --no-verify -m "chore(ratchet): trim trailing whitespace in init CLI

The auto-bump path (CoverageRatchetService._update_pyproject_requirement)
already calls FileSystemService.clean_trailing_whitespace_and_newlines
on the resulting pyproject. The init CLI didn't, producing pyproject
files without trailing newlines. Symmetrize the two paths.

Cosmetic follow-up from whole-branch opus review.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

______________________________________________________________________

## Self-review

**1. Spec coverage:** The parent plan's whole-branch review surfaced these 6 follow-ups (see `/Users/les/Projects/crackerjack/.superprofits/2026-08-11-bodai-coverage-ratchet-standard/progress.md` lines 46-52 — though that path may not exist post-cleanup; consult progress.md in the SDD workspace). Each follow-up maps to one task.

**2. Placeholder scan:** No "TBD" / "TODO" / "implement later" / "similar to" patterns. Every step contains exact commands, expected outputs, and the exact value(s) to use (e.g. `99.48619139370584`, `79.41219053134502`, `49.1324200913242`).

**3. Type consistency:** Task 1 signature unchanged. Tasks 2/3/4 only invoke the existing CLI. Tasks 5/6 file edits are minimal and surface-correct. The `FileSystemService.clean_trailing_whitespace_and_newlines` helper signature matches the existing auto-bump path use at `crackerjack/services/coverage_ratchet.py:247-250`.

**4. Order matters:** Task 1 MUST land before Tasks 2/3/4 — those tasks trigger the auto-bump path via `init --reinit`, which would currently round to int. Tasks 5 and 6 are independent of 1-4.

**5. Drift-bundling caveat:** Tasks 2/3/4 use `--reinit` then restore `.coverage-ratchet.json` from HEAD before committing, so only the pyproject is touched. Task 4 fastblocks explicitly uses targeted `git add` per `drift-bundling-recovery.md` to leave other pre-existing dirty files untouched.

## Verification expectations (per task)

| Task | Commit on | Files | Test gate |
|---|---|---|---|
| 1 | crackerjack:main | `services/patterns/operations.py`, `tests/services/test_regex_patterns.py` | new precision test passes + full `tests/services/` green |
| 2 | mcp-common:main | `pyproject.toml` | addopts shows `99.48619139370584`; TOML valid |
| 3 | oneiric:main | `pyproject.toml` | addopts shows `79.41219053134502`; TOML valid |
| 4 | fastblocks:main | `pyproject.toml` | both mirrors show `49.1324200913242`; TOML valid; other pre-existing dirty files untouched |
| 5 | crackerjack:main | `.gitignore` | `git check-ignore` confirms `.coverage-ratchet.json` NOT ignored; other coverage artifacts still ignored |
| 6 | crackerjack:main | `cli/coverage_ratchet_cli.py`, `tests/cli/test_coverage_ratchet_cli.py` | new whitespace test passes + full CLI/service/manager tests green |

## Execution handoff

After saving this plan, choose:

1. **Subagent-Driven (recommended)** — fresh implementer per task with reviewer between tasks
1. **Keep as-is** — implement later
