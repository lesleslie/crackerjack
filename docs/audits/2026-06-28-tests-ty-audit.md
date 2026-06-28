# ty_audit Triage — tests/ (2026-06-28)

## Summary

- **Total suppressions**: 8
- **Threshold**: 50
- **Triggered**: no

The audit threshold (50) is far above the current count (8). The
"ratchet" view in `crackerjack.tools.ty_ratchet` is the gatekeeper; this
periodic audit is the classification counterpart. The audit ran cleanly
the first time and produced no surprises on the "triggered" axis.

## By diagnostic code

| Code | Count | % |
|------|------:|---:|
| invalid-assignment | 3 | 37.5% |
| unresolved-import | 3 | 37.5% |
| invalid-argument-type | 1 | 12.5% |
| unresolved-attribute | 1 | 12.5% |

Top 5 = all of them (only 4 distinct codes in the dataset).

## By age

| Bucket | Count |
|--------|------:|
| <30 days | 8 |
| 30-90 days | 0 |
| >90 days | 0 |

All 8 suppressions are recent (added within the last day). This matches
the Phase Q.1.E.b commit (`4bb2afc`) that introduced the audit and the
fixtures it depends on.

> **Tool note**: `ty_audit.py`'s inline blame regex (`BLAME_DATE_RE`)
> failed to match the git-blame output for these lines during the
> automated run, so the tool reported `by_age = {<30d: 0, 30-90d: 0,
> >90d: 0}`. The dates were re-derived in this report by running
> `git blame` directly against each suppression and parsing the inner
> parenthetical manually. The bug appears to be in the
> `[^)]*?` non-greedy capture of the author segment — when the author
> is a single short name (`lesleslie`), the engine backtracks past the
> date group instead of matching it. Worth filing as a follow-up;
> does not affect this triage.

## Top 10 files by suppression count

| File | Count |
|------|------:|
| tests/test_agents/test_type_error_specialist.py | 6 |
| tests/tools/test_ty_audit.py | 2 |

Only 2 files contain suppressions; both are tests for the very tools
that *enumerate* or *act on* suppressions.

## Per-suppression breakdown

| File | Line | Code | Snippet (truncated) |
|------|-----:|------|---------------------|
| tests/test_agents/test_type_error_specialist.py | 781 | invalid-assignment | `"""# type: ignore[assignment] -> also add # ty: ignore[invalid-assignment]."""` |
| tests/test_agents/test_type_error_specialist.py | 791 | invalid-assignment | `assert "# ty: ignore[invalid-assignment]" in new_content` |
| tests/test_agents/test_type_error_specialist.py | 797 | invalid-assignment | `content = "x = None  # type: ignore[assignment]  # ty: ignore[invalid-assignment]\n"` |
| tests/test_agents/test_type_error_specialist.py | 861 | unresolved-import | `"""unresolved-import -> append # ty: ignore[unresolved-import]."""` |
| tests/test_agents/test_type_error_specialist.py | 872 | unresolved-import | `assert "# ty: ignore[unresolved-import]" in new_content` |
| tests/test_agents/test_type_error_specialist.py | 876 | unresolved-import | `content = "from crackerjack.foo import Bar  # ty: ignore[unresolved-import]\n"` |
| tests/tools/test_ty_audit.py | 80 | invalid-argument-type | `"x = 1  # ty: ignore[invalid-argument-type]\n"` |
| tests/tools/test_ty_audit.py | 83 | unresolved-attribute | `"w = 4  # ty: ignore[unresolved-attribute]\n",` |

## Unused-suppression detection

`python -m crackerjack.tools.ty_audit tests/ --detect-unused` was also
run. The audit reported **all 8 suppressions as unused** — meaning,
removing the `# ty: ignore[...]` token does not cause `ty` to emit a
diagnostic at that line.

This is expected and **does not indicate real cleanup opportunity**:
every match is inside a Python string literal that *describes* a
suppression, not a suppression that gates code execution. Concrete
examples:

- `tests/tools/test_ty_audit.py:80` — inside a `tmp_path.write_text(...)`
  call that feeds `enumerate_suppressions()` with synthetic input. The
  test asserts the regex picks these up.
- `tests/test_agents/test_type_error_specialist.py:797` — inside a
  `content = "..."` fixture that the `type_error_specialist` agent
  edits (the test verifies the agent appends `# ty: ignore[...]`).
- `tests/test_agents/test_type_error_specialist.py:781, 791, 861, 872`
  — docstring/assertion lines that *contain* the literal text
  `# ty: ignore[...]` as the substring under test.

The audit tool's regex (`#\s*ty:\s*ignore\[([a-z0-9-]+)\]`) is
deliberately permissive: any line containing the pattern counts, even
inside string literals. This is by design — the audit's job is to
enumerate, not to judge context. The classification pass that
distinguishes "real suppression" from "string fixture" is precisely
what R.E was meant to provide.

**No suppressions were dropped.** Per the mission brief, dropping is
permitted only if the test still passes after — and in every one of
these eight cases, the line is a load-bearing test fixture. Removing
the `# ty: ignore[...]` token from the string would change the
substring the test is asserting on and break the test.

## Recommendations

- **No mass-cleanup action required.** Total (8) is well under the
  threshold (50); all entries are recent; none are real code
  suppressions.
- **Audit-tool follow-up**: file a defect against
  `crackerjack/tools/ty_audit.py:BLAME_DATE_RE` so future audits
  produce a non-zero `by_age` without manual intervention. The fix is
  to either (a) split the inner parenthetical on whitespace and pull
  the last three tokens, or (b) use a greedy `.*?` with a positive
  look-behind for `(\d{4}-\d{2}-\d{2}`. Out of scope for R.E.
- **Future triage runs**: if `tests/` ever crosses the 50-suppression
  threshold, re-evaluate the same way: classify each match as
  `code-level suppression` vs `string-literal fixture`. Only the
  former are candidates for dropping.
- **R.F handoff context**: `pytest --collect-only` reports
  **14,985 tests** in the suite (well above the 750-test baseline
  assumed by earlier phases). The R.E audit sampled only files under
  `tests/`; no production files were touched.

## Provenance

- Tool commit: `4bb2afc` (Phase Q.1.E.b)
- Run date: 2026-06-28
- JSON report: `/tmp/ty_audit_report.json` (basic run),
  `/tmp/ty_audit_unused.json` (with `--detect-unused`)
- Suppressions classified as unused: 8 (all string-literal fixtures;
  none dropped)
