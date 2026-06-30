# Plan: ty-ratchet pipeline cleanup (E.3 + missing-dir)

## Context

The ty-ratchet pipeline has two ad-hoc encodings and one robustness gap that
were deferred from the Option B implementation on 2026-06-29. They form a
coherent batch because all three touch the `ty_ratchet` /
`hook_executor` / `tool_commands` axis and address operator experience.

### Why now

- The negative `files_processed<0` sentinel is a type-safety compromise. It
  hijacks a count field to carry an advisory signal. Any future code that
  reads `files_processed` and assumes it's non-negative (e.g., a progress
  display) will silently misinterpret ty's test-gate diagnostic count.
- The missing-dir case (when `--prod-dir` or `--test-dir` points at a
  non-existent path) produces a confusing `Found 1 diagnostic` (the IO
  error). Operators can't tell "I have 158 prod type errors" from "my package
  dir is wrong."
- The Option B implementation already wired the package-name-driven
  `--prod-dir` / `--test-dir` flags through `tool_commands.py`. Per-project
  `[tool.crackerjack] ty_prod_dir` / `ty_test_dir` pyproject keys are not
  needed by current projects and would be YAGNI.

### Intended outcome

`HookResult.advisory_issues: list[str]` carries the test-gate diagnostic list
explicitly. Missing dirs produce a clear stderr warning and vacuous-pass
gates, so the operator sees the configuration error loudly without the
diagnostic count being polluted by an IO error. The prod-only exit code
contract is preserved.

---

## Approach

Two code changes; no per-project pyproject keys added.

1. **`HookResult.advisory_issues`** — add field, wire it through
   `_parse_ty_ratchet` (producer) and `_display_hook_result` (consumer).
2. **Missing-dir detection** — pre-check `Path(...).is_dir()` before invoking
   `ty`; emit a stderr warning; substitute a zero-result for the gate math.

Both changes preserve the existing prod-gate-controls-exit-code contract and
the test-gate advisory behavior. No CLI surface changes. No new JSON keys
required.

---

## Critical files

### `crackerjack/models/task.py`

Add `advisory_issues` field to `HookResult` (after `qa_result`, line 54):

```python
advisory_issues: list[str] = field(default_factory=list)
```

`list[str]`, default empty list, no validation. Each element is a
concise-format diagnostic line (`path:line:col: severity[code] message`).

### `crackerjack/executors/hook_executor.py`

#### a) `_parse_ty_ratchet` (line 1495) — signature change

Change return type from `int` to `tuple[int, list[str]]`:

```python
def _parse_ty_ratchet(self, output: str) -> tuple[int, list[str]]:
    """Return (files_processed, advisory_issues).

    The advisory list carries the test-ratchet diagnostic lines when the
    test gate fails. Replaces the prior negative-files_processed sentinel
    — see HookResult.advisory_issues for the rationale.
    """
    import re

    test_re = re.compile(
        r"ty ratchet \[split\] test:\s+(?P<status>PASS|FAIL)\s+"
        r"\((?P<count>\d+)/(?P<max>\d+)\)"
    )
    concise_diag_re = re.compile(r"^[\w./-]+:\d+:\d+:\s+(?:error|warning)\[")

    test_failed = False
    for line in output.splitlines():
        line = line.strip()
        if not line:
            continue
        m = test_re.search(line)
        if m and m.group("status") == "FAIL":
            test_failed = True
            break

    if not test_failed:
        return 0, []

    advisories = [
        raw.strip()
        for raw in output.splitlines()
        if concise_diag_re.match(raw.strip())
    ]
    return 0, advisories
```

#### b) `_parse_hook_output` (line 1465) — destructure the tuple

```python
# before:
files_processed = self._parse_ty_ratchet(output)
# ...
return self._create_parse_result(files_processed, result.returncode, output)

# after:
files_processed, advisory_issues = self._parse_ty_ratchet(output)
# ...
parse_result = self._create_parse_result(
    files_processed, result.returncode, output
)
parse_result["advisory_issues"] = advisory_issues
return parse_result
```

This piggybacks on `_create_parse_result` (which already returns a dict) so we
don't widen its signature. `_create_parse_result` (line 1584) gains one key:
`"advisory_issues": []` always present.

#### c) `_create_hook_result_from_process` (line 597) — populate the field

```python
# after the existing _parse_hook_output call (line 623):
parsed_output = self._parse_hook_output(result, hook.name)
# ...
return HookResult(
    # ... existing fields ...,
    advisory_issues=parsed_output.get("advisory_issues", []),
)
```

#### d) `_display_hook_result` (line 1759-1768) — read the new field

```python
# before:
if (
    result.name == "ty"
    and result.status == "passed"
    and result.files_processed < 0
):
    test_count = -result.files_processed
    self.console.print(
        f"⚠️  ty test ratchet FAIL: {test_count} diagnostic(s) in tests/ "
        f"(advisory only; prod gate controls stage)"
    )

# after:
if (
    result.name == "ty"
    and result.status == "passed"
    and result.advisory_issues
):
    self.console.print(
        f"⚠️  ty test ratchet FAIL: {len(result.advisory_issues)} diagnostic(s) "
        f"in tests/ (advisory only; prod gate controls stage)"
    )
```

#### e) Comment update — `_update_status_for_reporting_tools` (line 735-742)

The doc comment currently references the negative sentinel. Update it to
reference `advisory_issues`:

```python
# ty is excluded from the status-flip set because the ratchet's
# prod gate already drives the exit code (see
# crackerjack.tools.ty_ratchet: overall_exit is prod_gate). When
# only the test gate fails, the ratchet returns 0 and the hook
# is "passed" — the test-tail diagnostics are surfaced as
# advisory only via ``HookResult.advisory_issues`` and the
# warning banner in _display_hook_result. Flipping status
# here would regress that documented contract.
```

### `crackerjack/tools/ty_ratchet.py`

#### a) `_run_split` (line 178) — pre-check both dirs

```python
def _run_split(args: argparse.Namespace) -> int:
    prod_max = _read_split_budget(args.pyproject, "ty_max_errors_prod", default=50)
    test_max = _read_split_budget(args.pyproject, "ty_max_errors_test", default=30)

    prod_exists = Path(args.prod_dir).is_dir()
    test_exists = Path(args.test_dir).is_dir()

    if not prod_exists:
        print(
            f"⚠️  ty_ratchet: prod dir {args.prod_dir!r} does not exist; "
            f"treating prod gate as 0/0 (vacuously passing).",
            file=sys.stderr,
        )
    if not test_exists:
        print(
            f"⚠️  ty_ratchet: test dir {args.test_dir!r} does not exist; "
            f"treating test gate as 0/0 (vacuously passing, advisory only).",
            file=sys.stderr,
        )

    prod_result = run_ty(args.prod_dir) if prod_exists else _zero_result()
    test_result = run_ty(args.test_dir) if test_exists else _zero_result()
    # ... rest unchanged ...
```

#### b) New helper `_zero_result` (placed near `run_ty`, line 168)

```python
def _zero_result() -> subprocess.CompletedProcess[str]:
    """Synthetic CompletedProcess with empty output and returncode 0.

    Used when a split-mode dir doesn't exist, so the gate math sees a
    vacuous pass (0 ≤ any_budget) instead of the IO-error diagnostic
    that ``ty`` would emit on a missing path.
    """
    return subprocess.CompletedProcess(
        args=[],
        returncode=0,
        stdout="",
        stderr="",
    )
```

#### c) JSON envelope (line 227) — advertise which dirs were checked

Add `"prod_dir_exists": prod_exists` and `"test_dir_exists": test_exists` to
the `summary` dict. Lets consumers verify the guard fired without re-parsing
stderr. No consumer reads these today; purely additive metadata.

---

## Reused patterns

- `_read_split_budget` (crackerjack/tools/ty_ratchet.py:109) — same hand-rolled
  TOML parser used for the new field defaults. Not adding new keys, so no
  parser change needed.
- `_create_parse_result` (crackerjack/executors/hook_executor.py:1584) —
  already returns a dict; widening to carry `advisory_issues` is a 1-line
  addition.
- The field uses `field(default_factory=list)` per the existing `qa_result` /
  `files_checked` pattern (crackerjack/models/task.py:42, 54).
- Subprocess-result synthesis via `subprocess.CompletedProcess` is used
  elsewhere in `hook_executor.py` (line 520, 1405) for the IO-error path; the
  `_zero_result` helper follows that idiom.

---

## Tests

### `tests/test_hook_executor.py`

#### Update existing tests

Wherever any test class asserts on `result.files_processed < 0` (the prior
sentinel), switch to asserting `result.advisory_issues` is non-empty. Search
the file with `grep -n "files_processed < 0"` to find them. Expected to be
in `TestTyRatchetAdvisoryBanner` or similar (verify during implementation).

#### New tests (`TestHookResultAdvisoryIssuesField` class)

- `test_advisory_issues_default_is_empty_list` — `HookResult()` has
  `advisory_issues == []`
- `test_advisory_issues_field_preserved_through_construction` — explicit
  construction preserves the list reference

#### New tests (`TestParseTyRatchetAdvisorySemantics` class)

- `test_parse_ty_ratchet_returns_zero_files_processed_on_test_fail` —
  ratchet output with `test: FAIL (N/M)` produces `(0, advisories)` not a
  negative files_processed
- `test_parse_ty_ratchet_no_advisories_on_test_pass` — clean output
  produces `(0, [])`
- `test_parse_ty_ratchet_advisories_are_concise_lines` — captured advisory
  lines match the concise-diagnostic regex
- `test_parse_ty_ratchet_filters_out_summary_and_advisory_banner` — the
  `ty ratchet [split] ...` summary lines and the `⚠️ ty:` advisory banner
  do NOT appear in the advisories list

### `tests/tools/test_ty_ratchet.py`

#### New tests (`TestSplitModeMissingDirs` class)

- `test_split_mode_missing_prod_dir_is_vacuous_pass` — `--prod-dir
  ./does_not_exist --test-dir ./tests` → exit 0 (with permissive budgets),
  `prod.diagnostic_count == 0`, stderr contains the warning
- `test_split_mode_missing_test_dir_still_advisory` — missing test dir
  produces `test.diagnostic_count == 0` and the warning
- `test_split_mode_both_dirs_missing_yields_exit_zero` — both missing →
  exit 0, two warnings
- `test_split_mode_json_envelope_includes_dir_existence_flags` — JSON
  contains `prod_dir_exists: false` when missing

### `tests/tools/test_ty_audit.py`

No changes required. Existing tests pass `--split` with valid dirs.

### `tests/test_hook_executor.py` — separate concern

Existing ty-specific tests in this file may exercise the
`_display_hook_result` warning banner. After the field rename, those tests
should still pass because the banner now reads `len(result.advisory_issues)`
rather than `-result.files_processed`. Verify by running the suite after the
edit.

---

## Out-of-scope (explicit deferrals)

- **Per-project `[tool.crackerjack] ty_prod_dir` / `ty_test_dir` keys**:
  deferred. The hook-builder default works for crackerjack/oneiric/mahavishnu.
  If a future project has a divergent layout (`src/foo/`), it can set
  `disabled=True` on the ty hook or pass `--prod-dir` directly.
- **A `--strict` flag** that would turn the vacuous-pass into a config-error
  exit: deferred. The stderr warning is enough for now.
- **Removing the dual status lines in the ratchet's stdout** (`ty ratchet
  [split] prod: PASS/FAIL (N/M)` etc.): out of scope. Those lines are
  consumer-stable; changing them is a separate refactor.

---

## Verification

### Before-the-fix

```bash
cd /Users/les/Projects/crackerjack
python -m crackerjack.tools.ty_ratchet --split --prod-dir ./does_not_exist
# Expect: exit 1, "Found 1 diagnostic" (the IO error).

python -m crackerjack run --tool ty
# Expect: when test-gate fails (which it does — 766 test debt), the
# warning banner reads from files_processed < 0 sentinel. The banner
# works but the encoding is a type-safety compromise.
```

### After-the-fix

```bash
cd /Users/les/Projects/crackerjack
python -m crackerjack.tools.ty_ratchet --split --prod-dir ./does_not_exist --test-dir ./tests
# Expect: exit 0 (with permissive prod budget), stderr has "prod dir
# './does_not_exist' does not exist", JSON has prod_dir_exists: false.

python -m crackerjack run --tool ty
# Expect: warning banner still appears when test-gate fails. Banner
# text now reads "len(advisory_issues) diagnostic(s)". Same external
# behavior, cleaner internal encoding.
```

### Cross-project

```bash
cd /Users/les/Projects/oneiric
python -m crackerjack run --tool ty
# Expect: prod=158 (real debt), test=680 (advisory). Banner prints
# with the test-gate count. No regression vs. Option B verification.

cd /Users/les/Projects/mahavishnu
python -m crackerjack run --tool ty
# Expect: prod=482, test=2056. Same shape as before.
```

### Test suite

```bash
cd /Users/les/Projects/crackerjack
pytest tests/test_hook_executor.py -x -v
pytest tests/tools/test_ty_ratchet.py -x -v
pytest tests/tools/test_ty_audit.py -x -v
pytest tests/test_hook_executor.py tests/tools/test_ty_ratchet.py tests/tools/test_ty_audit.py -x
```

Expected: 80 tests pass (74 prior + 3 E.3 + 3 missing-dir; some existing
tests may shift due to field rename).

---

## Risk summary

- **`HookResult.advisory_issues` field**: low. Pure addition. Default empty
  list means existing HookResult constructions are unaffected. The
  `_create_parse_result` dict gains one key, but no consumer reads it
  besides the new code path.
- **`_parse_ty_ratchet` return-type change**: low. Only one caller
  (`_parse_hook_output`) and it's the one we're editing in the same
  change.
- **Missing-dir vacuous-pass**: low. The new `_zero_result` helper
  produces a result indistinguishable from a clean ty run from the gate
  math's perspective. The stderr warning surfaces the config error.
- **JSON envelope additions** (`prod_dir_exists`, `test_dir_exists`):
  additive; no existing consumer parses them.

---

## Sequencing

Single PR, three commits (or one commit if reviewer prefers unified diff):

1. **E.3 — `HookResult.advisory_issues`**: producer + consumer + field
   addition + tests. Land first because it's the largest blast radius.
2. **Missing-dir detection**: pure addition to `_run_split`. Land second
   because it builds on the prod-only exit-code contract that E.3
   reaffirms.
3. **Skip item 2**: no commit needed.

After both land, run the verification suite to confirm the warning banner
still appears and the prod-only exit-code contract is preserved.