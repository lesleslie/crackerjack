---
status: draft
role: implementation
topic: lifecycle
date: 2026-08-11
last_reviewed: 2026-08-11
superseded_by: null
blocks_on: []
---

# Replace `check-local-links` with `darnlink` across the Bodai ecosystem

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Scope notice:** The `ai-fix` subsystem was removed in commit `907ab860 feat(refactor): remove AI-fix subsystem` (2026-08-10). This plan does **NOT** wire `darnlink` into any AI-fix / agent dispatch path. If a future AI-fix subsystem is reintroduced, that wiring belongs in a separate plan.

**Goal:** Replace `crackerjack/tools/local_link_checker.py` (the pure-Python `check-local-links` fast hook) with `darnlink` (`https://github.com/txemi/darnlink`) and roll the replacement out across all six core Bodai repositories via the `mahavishnu/settings/repos.yaml` manifest.

**Architecture:** Invoke `darnlink` as a **subprocess** from a new `crackerjack/tools/darnlink_wrapper.py` (MPL/GPL license-safe per the established "mere aggregation" pattern — see `.claude/...` for the policy context). The wrapper replicates the contract `check-local-links` exposes today: same flag set on the `HookDefinition`, same exit-code semantics (`0` clean, non-zero on broken robust links), same parser registration in `crackerjack/parsers/regex_parsers.py`. The wrapper is opt-in for one release cycle behind `--experimental-darnlink` / an `enable_darnlink: bool` settings flag, then flipped default-on, then `check-local-links` is deleted. Other Bodai repos pick up the new hook automatically because they already run `crackerjack` via the manifest.

**Tech Stack:** Python 3.13, `darnlink` (GPL-3.0-or-later; subprocess-only), `pytest` (auto asyncio mode), the existing `crackerjack` hook registration + `mahavishnu/settings/repos.yaml` manifest.

## Global Constraints

- **Project conventions** (from `crackerjack/CLAUDE.md`):
  - `from __future__ import annotations` as the first non-comment line of every source file.
  - Imports sorted within each section (force-sort-within-sections enabled).
  - Modern syntax: `X | None`, `list[str]`, `pathlib.Path`.
  - Function arguments with default `None` typed as `X | None = None`.
  - Oneiric logger (`oneiric.logging`), not stdlib `logging` in production code.
- **License preservation:** `darnlink` is GPL-3.0-or-later; crackerjack is BSD-3-Clause. The wrapper **must** invoke `darnlink` via `subprocess.run` (or `asyncio.create_subprocess_exec`), keeping the GPL code in a separate process. `import darnlink` is forbidden inside `crackerjack/` source. This is the same pattern already used for `lychee`, `creosote`, `skylos`, etc.
- **No AI-fix integration:** The `crackerjack/ai_fix/`, `crackerjack/intelligence/`, `crackerjack/agents/` packages were deleted in commit `907ab860`. No task in this plan touches any of those paths. If a future AI-fix subsystem is reintroduced, document `darnlink` as an integration target in a follow-up plan.
- **Test conventions:** Project pytest markers `unit`, `integration`, `slow` — no new markers.
- **Ruff line length:** 88 chars. Hard limits: max-args 10, max-branches 15, max-returns 6, max-statements 55.
- **Deprecation policy:** A hook deleted in a minor release must have been non-default for at least one full minor release. `check-local-links` therefore survives one cycle as an opt-out escape hatch before its files are deleted.

---

## Phase 1 — Wrapper module + `darnlink` as an opt-in hook

**Files:**
- Create: `crackerjack/tools/darnlink_wrapper.py`
- Create: `tests/unit/tools/test_darnlink_wrapper.py`
- Modify: `crackerjack/config/hooks.py` (add `HookDefinition(name="darnlink", ...)` in the FAST_HOOKS section, marked `enable_darnlink: bool` flag-controlled via the existing opt-in flag system)
- Modify: `crackerjack/config/tool_commands.py` (register the `crackerjack.tools.darnlink_wrapper` command for `darnlink`)
- Modify: `crackerjack/parsers/regex_parsers.py` (register a `DarnlinkRegexParser` next to `LocalLinkCheckerRegexParser` at line ~929)
- Modify: `crackerjack/config/settings.py` (add `enable_darnlink: bool = False` field; mirror how `fast_iteration` and other opt-in flags are wired)

**Interfaces:**
- `crackerjack.tools.darnlink_wrapper.main(argv: list[str] | None = None) -> int` — entry point called by crackerjack's hook runner. Invokes `python -m darnlink check <paths>` via `subprocess.run`, parses stdout (JSON findings shape per darnlink docs: `{"findings": [...], "kind": "..."}`) into the existing `Issue` model.
- Exit code mapping: `0` clean, `2` integrity failure → `return 1` for crackerjack, `3` strict robustify failure → `return 1`, anything else → propagate. (darnlink's `2`/`3` distinction is preserved in the parser output for downstream visibility.)

**Integration Contract:**
- **Triggered from:** the `crackerjack` orchestrator when `enable_darnlink=True` is set in `settings/local.yaml` or `--enable-darnlink` CLI flag is passed. The existing `check-local-links` hook keeps running in parallel during this phase so a side-by-side diff is visible.
- **Returns to / updates:** the `Issue` registry via `IssueType.DOCUMENTATION` (same as `check-local-links`).
- **Demonstrable by:** `crackerjack --enable-darnlink run -- -v` prints both `check-local-links` and `darnlink` results tables; in a repo with no broken links the exit code is `0`; in a repo with broken links the exit code is `1`.
- **Rollback signal:** Set `enable_darnlink: false` in `settings/local.yaml` (or unset the CLI flag). `darnlink` is dormant; `check-local-links` continues to be the only path. No data loss — neither hook mutates files unless the operator explicitly invokes `darnlink --write` (which is out of scope here).
- **Observability added:** `darnlink`'s JSON output is captured into `~/.crackerjack/logs/darnlink.log` (mirror the existing `lychee` log pattern). The wrapper's run duration is reported in the standard hook results table.

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/tools/test_darnlink_wrapper.py`:

```python
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from crackerjack.tools.darnlink_wrapper import main, parse_findings


def _fake_completed_process(returncode: int, stdout: str) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(
        args=["darnlink"], returncode=returncode, stdout=stdout, stderr=""
    )


@pytest.mark.unit
def test_main_clean_returns_zero(tmp_path: Path) -> None:
    """darnlink exit 0 → main returns 0."""
    with patch(
        "crackerjack.tools.darnlink_wrapper.subprocess.run",
        return_value=_fake_completed_process(0, '{"findings": []}'),
    ):
        result = main([])
    assert result == 0


@pytest.mark.unit
def test_main_integrity_failure_returns_one(tmp_path: Path) -> None:
    """darnlink exit 2 (integrity) → main returns 1."""
    payload = json.dumps(
        {
            "findings": [
                {
                    "kind": "broken_robust_link",
                    "file": "docs/README.md",
                    "line": 12,
                    "target": "missing.md",
                    "message": "Target file missing",
                }
            ]
        }
    )
    with patch(
        "crackerjack.tools.darnlink_wrapper.subprocess.run",
        return_value=_fake_completed_process(2, payload),
    ):
        result = main([])
    assert result == 1


@pytest.mark.unit
def test_main_strict_robustify_returns_one(tmp_path: Path) -> None:
    """darnlink exit 3 (strict) → main returns 1."""
    with patch(
        "crackerjack.tools.darnlink_wrapper.subprocess.run",
        return_value=_fake_completed_process(3, '{"findings": []}'),
    ):
        result = main([])
    assert result == 1


@pytest.mark.unit
def test_parse_findings_maps_to_issue_dicts() -> None:
    """parse_findings yields crackerjack-shaped dicts ready for Issue construction."""
    payload = {
        "findings": [
            {
                "kind": "broken_robust_link",
                "file": "docs/x.md",
                "line": 7,
                "target": "missing.md",
                "message": "Target missing",
            }
        ]
    }
    issues = list(parse_findings(payload))
    assert len(issues) == 1
    assert issues[0]["file_path"] == "docs/x.md"
    assert issues[0]["line_number"] == 7
    assert issues[0]["message"] == "Target missing"
    assert issues[0]["code"] == "darnlink.broken_robust_link"
```

- [ ] **Step 2: Run tests, expect ImportError**

Run: `uv run pytest tests/unit/tools/test_darnlink_wrapper.py -v`
Expected: `ModuleNotFoundError: No module named 'crackerjack.tools.darnlink_wrapper'`.

- [ ] **Step 3: Implement `crackerjack/tools/darnlink_wrapper.py`**

```python
from __future__ import annotations

import json
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

from crackerjack.tools._git_utils import get_git_tracked_files


DARNTLINK_INTEGRITY_EXIT = 2
DARNTLINK_STRICT_EXIT = 3


def _target_paths(argv: list[str]) -> list[Path]:
    if argv:
        return [Path(a) for a in argv if a.endswith((".md", ".markdown"))]
    md = get_git_tracked_files("*.md")
    markdown = get_git_tracked_files("*.markdown")
    return md + markdown


def parse_findings(payload: object) -> Iterator[dict[str, object]]:
    """Yield crackerjack-shaped issue dicts from a darnlink JSON payload."""
    if not isinstance(payload, dict):
        return
    findings = payload.get("findings", [])
    if not isinstance(findings, list):
        return
    for finding in findings:
        if not isinstance(finding, dict):
            continue
        kind = str(finding.get("kind", "unknown"))
        yield {
            "file_path": str(finding.get("file", "")),
            "line_number": int(finding.get("line", 0)),
            "message": str(finding.get("message", "")),
            "code": f"darnlink.{kind}",
            "severity": "error",
        }


def _run_darnlink(paths: list[Path], repo_root: Path) -> subprocess.CompletedProcess:
    cmd = [sys.executable, "-m", "darnlink", "check", "--format", "json", *map(str, paths)]
    return subprocess.run(
        cmd,
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )


def main(argv: list[str] | None = None) -> int:
    repo_root = Path.cwd()
    paths = _target_paths(argv or [])

    if not paths:
        return 0

    try:
        result = _run_darnlink(paths, repo_root)
    except subprocess.TimeoutExpired:
        print("darnlink timed out", file=sys.stderr)
        return 1
    except FileNotFoundError:
        print("darnlink not installed; install with `uv pip install darnlink`", file=sys.stderr)
        return 127

    if result.returncode not in (0, DARNTLINK_INTEGRITY_EXIT, DARNTLINK_STRICT_EXIT):
        if result.stderr:
            print(result.stderr, end="", file=sys.stderr)
        return result.returncode

    if result.stdout.strip():
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError:
            print("darnlink returned non-JSON output", file=sys.stderr)
            return 1
        for issue in parse_findings(payload):
            print(f"{issue['file_path']}:{issue['line_number']}: {issue['message']}", file=sys.stderr)

    if result.returncode == 0:
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
```

- [ ] **Step 4: Wire into `crackerjack/config/hooks.py`**

Insert after the `check-local-links` `HookDefinition` (around line 204):

```python
HookDefinition(
    name="darnlink",
    command=[],
    timeout=60,
    security_level=SecurityLevel.LOW,
    accepts_file_paths=True,
    enable_flag="enable_darnlink",
    description="Robust markdown link validation (UUID-anchored, refactor-survivable)",
),
```

The `enable_flag` attribute references the new `enable_darnlink` setting. If your existing `HookDefinition` model does not have `enable_flag`, add it as an optional field (mirror how `fast_iteration` is treated).

- [ ] **Step 5: Register the command in `crackerjack/config/tool_commands.py`**

Add next to the `"check-local-links"` entry (around line 251):

```python
"darnlink": _python_module_command("crackerjack.tools.darnlink_wrapper"),
```

- [ ] **Step 6: Register the parser in `crackerjack/parsers/regex_parsers.py`**

Near line 929 (where `LocalLinkCheckerRegexParser` is registered), add:

```python
factory.register_regex_parser("darnlink", DarnlinkRegexParser)
```

(Define `DarnlinkRegexParser` to consume the stderr lines emitted by the wrapper; mirror `LocalLinkCheckerRegexParser`'s shape.)

- [ ] **Step 7: Run the new tests, expect pass**

Run: `uv run pytest tests/unit/tools/test_darnlink_wrapper.py -v`
Expected: 4 tests pass.

- [ ] **Step 8: Run the existing `check-local-links` test subset**

Run: `uv run pytest tests/unit/tools/ -v -k "link or darnlink"`
Expected: existing `link`-related tests still pass (no behavioral change to `check-local-links` in this phase).

- [ ] **Step 9: Commit**

```bash
git add crackerjack/tools/darnlink_wrapper.py \
       crackerjack/config/hooks.py \
       crackerjack/config/tool_commands.py \
       crackerjack/parsers/regex_parsers.py \
       crackerjack/config/settings.py \
       tests/unit/tools/test_darnlink_wrapper.py
git commit -m "feat(hooks): add darnlink as opt-in fast hook (Phase 1)"
```

---

## Phase 2 — Pilot run on crackerjack's own docs

**Files:**
- Modify: `crackerjack/settings/local.yaml.example` (add `enable_darnlink: true` with a comment block explaining the opt-in)
- Modify: `docs/dev/setup.md` (or equivalent) — short note: "to run the experimental darnlink hook alongside check-local-links, set `enable_darnlink: true` in your `settings/local.yaml`."

**Integration Contract:**
- **Triggered from:** running `crackerjack run` inside the `crackerjack` repo with `enable_darnlink: true` set. Operators see two adjacent results tables — `check-local-links` and `darnlink` — for one release cycle.
- **Returns to / updates:** no production code; only docs and example settings.
- **Demonstrable by:** `crackerjack run --enable-darnlink` exits with the same code as `crackerjack run` (without `--enable-darnlink`) on a docs-clean commit, and exits with `1` if either hook finds a broken link.
- **Rollback signal:** unset the flag / remove from `local.yaml`. The wrapper stays dormant.
- **Observability added:** none beyond what Phase 1's wrapper already emits.

- [ ] **Step 1: Add the example settings entry**

Append to `crackerjack/settings/local.yaml.example` (create the file if it does not exist):

```yaml
# Experimental: run darnlink alongside check-local-links during the pilot.
# Darnlink is a robust markdown link checker that survives file refactors
# by anchoring links to UUIDs. See
# docs/superpowers/plans/2026-08-11-darnlink-replaces-check-local-links.md
# for context and removal of check-local-links timeline.
enable_darnlink: true
```

- [ ] **Step 2: Document the flag**

Add a short paragraph to the developer setup doc pointing at the flag and the plan file. Keep it to one paragraph — full docs come when `darnlink` becomes default.

- [ ] **Step 3: Manually run both hooks on crackerjack's own tree**

Run: `crackerjack run --enable-darnlink`
Expected: both `check-local-links` and `darnlink` report the same set of broken links (if any). If they disagree, file an issue before proceeding to Phase 3 — the two must reach consensus before `darnlink` can become the default.

- [ ] **Step 4: Commit**

```bash
git add crackerjack/settings/local.yaml.example docs/dev/setup.md
git commit -m "docs(darnlink): pilot opt-in flag in local.yaml.example (Phase 2)"
```

---

## Phase 3 — Promote `darnlink` to default for new runs in `crackerjack` itself

**Files:**
- Modify: `crackerjack/config/settings.py` (`enable_darnlink: bool = True` for new projects — keep the field, default it to True)
- Modify: `crackerjack/config/hooks.py` (`enable_darnlink` flag default now True)
- Modify: `docs/CHANGELOG.md` (entry: "darnlink is now the default local link checker; check-local-links is deprecated and will be removed in the next minor release")

**Integration Contract:**
- **Triggered from:** every `crackerjack run` invocation now runs `darnlink` by default. `check-local-links` still runs alongside for one more cycle, but `darnlink` is the authoritative result.
- **Returns to / updates:** existing `Issue` registry. No schema changes.
- **Demonstrable by:** `crackerjack run` (no flag) shows `darnlink` in the fast hooks table. Running with `--no-darnlink` falls back to `check-local-links` only.
- **Rollback signal:** `enable_darnlink: false` in `settings/local.yaml`. Production default can also be reverted in a hotfix if a blocker is found.
- **Observability added:** a single new metric — `crackerjack_darnlink_findings_total` (count of findings across runs) — exposed via the existing Prometheus exporter if it accepts new counters; otherwise log-line only.

- [ ] **Step 1: Flip the default**

Change `enable_darnlink: bool = False` to `enable_darnlink: bool = True` in `crackerjack/config/settings.py` and the corresponding `HookDefinition.enable_flag` default in `crackerjack/config/hooks.py`.

- [ ] **Step 2: Add the `--no-darnlink` flag**

Mirror how other `--no-*` flags are added (search for `no_snob` or `no_coverage_ratchet` for the pattern). The flag flips `enable_darnlink` back to False at runtime.

- [ ] **Step 3: CHANGELOG entry**

Add an entry noting the default flip and the planned removal of `check-local-links`.

- [ ] **Step 4: Run the full crackerjack test suite**

Run: `uv run pytest tests/unit/ -q -m "not slow"`
Expected: green. If anything breaks, the failure is either a wrapper bug (fix and retry) or an unrelated flake (re-run).

- [ ] **Step 5: Commit**

```bash
git add crackerjack/config/settings.py \
       crackerjack/config/hooks.py \
       docs/CHANGELOG.md
git commit -m "feat(hooks): make darnlink the default local link checker (Phase 3)"
```

---

## Phase 4 — Roll out to the five other core Bodai repos

**Files (per repo, 5 repos × similar patch):**
- Akosha: `akosha/settings/local.yaml`, `akosha/pyproject.toml` (add `darnlink` to dev deps if the repo pins its own deps)
- Dhara: `dhara/settings/local.yaml`, `dhara/pyproject.toml`
- Session-Buddy: `session-buddy/settings/local.yaml`, `session-buddy/pyproject.toml`
- Oneiric: `oneiric/settings/local.yaml`, `oneiric/pyproject.toml`
- Mahavishnu: `mahavishnu/settings/local.yaml`, `mahavishnu/pyproject.toml`

Each patch is minimal because none of the other Bodai repos run their own link-checking hook today — they inherit from `crackerjack` via the manifest. The only repo-specific change is to **opt in to the new default** by either (a) ensuring the local settings file inherits the crackerjack default of `enable_darnlink: true`, or (b) explicitly setting `enable_darnlink: true` if a per-repo override is required.

**Integration Contract:**
- **Triggered from:** `mahavishnu sweep --tag bodai-core` (or the equivalent manifest dispatch) with `crackerjack >= <post-Phase-3 version>`. Each repo's docs tree is checked by `darnlink` automatically.
- **Returns to / updates:** `darnlink` findings appear in the consolidated sweep report alongside other per-repo hook results.
- **Demonstrable by:** introducing a deliberately broken link in `akosha/docs/`, running the sweep, and confirming the finding surfaces in the Akosha row of the sweep report.
- **Rollback signal:** revert the per-repo `local.yaml` change; `darnlink` falls back to `check-local-links` for that repo only.
- **Observability added:** the sweep dashboard gains a per-repo "darnlink clean / has findings" indicator (column add in `mahavishnu/monitoring/dashboards/sweep.json`).

- [ ] **Step 1: Per-repo local.yaml pin**

For each of the 5 repos, create or update `settings/local.yaml` (gitignored — `.local.yaml` is the per-developer convention; the per-repo default lives in `settings/<repo>.yaml` if you want a checked-in default) with:

```yaml
# Adopted: darnlink as the local link checker (Phase 4 of the cross-repo rollout).
# See plans/2026-08-11-darnlink-replaces-check-local-links.md.
enable_darnlink: true
```

- [ ] **Step 2: Add `darnlink` to dev deps where the repo pins its own**

If the repo's `pyproject.toml` has a `[dependency-groups].dev` list (mirroring the crackerjack convention), append `darnlink = "~=0.7"` to that list. If the repo relies on crackerjack's transitive deps, skip.

- [ ] **Step 3: Sweep with a deliberately broken link**

Pick one repo (recommend: **session-buddy** — smallest docs tree) and add a single broken markdown link to a doc file. Run `mahavishnu sweep --tag bodai-core` (or whichever sweep command the manifest uses). Confirm the broken link surfaces. Revert the deliberate breakage.

- [ ] **Step 4: Sweep the remaining 4 repos clean**

Run the sweep with no deliberate breakage. Each repo should report `darnlink` clean. If a repo surfaces findings that `check-local-links` did not, investigate whether the finding is a true positive (probably yes — darnlink's anchor validation catches what `check-local-links` doesn't).

- [ ] **Step 5: Commit per repo**

One commit per repo, for traceability:

```bash
# In each repo
git add settings/local.yaml.example pyproject.toml
git commit -m "chore: opt in to darnlink as default local link checker"
```

---

## Phase 5 — Delete `check-local-links`

**Files:**
- Delete: `crackerjack/tools/local_link_checker.py`
- Delete: `crackerjack/tools/linkcheckmd_wrapper.py` (if no other consumer — verify with `grep -rn "linkcheckmd" crackerjack/ tests/` first)
- Delete: `tests/unit/tools/test_local_link_checker.py` (or wherever its tests live — confirm by grep)
- Modify: `crackerjack/config/hooks.py` (remove `check-local-links` `HookDefinition`)
- Modify: `crackerjack/config/tool_commands.py` (remove the `"check-local-links"` entry)
- Modify: `crackerjack/parsers/regex_parsers.py` (remove the `LocalLinkCheckerRegexParser` registration and import)
- Modify: `crackerjack/core/autofix_coordinator.py` (remove the `"check-local-links": ("**/*.md", "**/*.markdown")` entry at line ~60)
- Modify: `docs/CHANGELOG.md` (entry: "Removed `check-local-links`; superseded by `darnlink`.")

**Integration Contract:**
- **Triggered from:** the next minor release after Phase 4 has been live for one full release cycle.
- **Returns to / updates:** no functional change for users — `darnlink` is already the authoritative local link checker.
- **Demonstrable by:** `grep -rn "check-local-links\|local_link_checker" crackerjack/` returns no production hits; tests that referenced these symbols are deleted or migrated.
- **Rollback signal:** if a critical regression is found, restore the deleted files via `git revert` of the Phase 5 commit. The flag-based opt-out is gone at this point, so a revert is the only path back.
- **Observability added:** the metrics counter for `check-local-links` (if any) is removed; `darnlink` counter remains.

- [ ] **Step 1: Verify no production consumer of `check-local-links`**

Run: `grep -rn "check-local-links\|local_link_checker" crackerjack/ docs/`
Expected: matches only in (a) the parser registration entry you're about to delete, (b) tests, (c) `crackerjack/core/autofix_coordinator.py:60` (also being deleted). If anything else hits, fix the consumer first.

- [ ] **Step 2: Delete the files**

```bash
git rm crackerjack/tools/local_link_checker.py
git rm tests/unit/tools/test_local_link_checker.py
```

- [ ] **Step 3: Remove the wiring**

Apply the edits listed in the "Files" section above.

- [ ] **Step 4: Run the full test suite**

Run: `uv run pytest tests/unit/ -q -m "not slow"`
Expected: green. Test count should drop (deletion of test file); no surviving test should fail.

- [ ] **Step 5: Sweep all Bodai repos one more time**

Run: `mahavishnu sweep --tag bodai-core`
Expected: all 6 repos report `darnlink` clean. `check-local-links` does not appear anywhere.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "chore(hooks): remove check-local-links; darnlink is the sole local link checker (Phase 5)"
```

---

## Self-review

### Spec coverage

| User requirement | Implemented by |
|------------------|----------------|
| Replace `check-local-links` with `darnlink` | Phases 1, 3, 5 |
| Roll out across all Bodai repos | Phase 4 |
| No AI-fix integration (the subsystem was removed) | Plan-wide scope notice + absence of any `crackerjack/ai_fix/`, `crackerjack/agents/`, or `crackerjack/intelligence/` references |
| License safety (GPL-3.0 vs BSD-3-Clause) | Phase 1 Step 3 enforces `subprocess.run`, forbids `import darnlink` |
| Future implementable (defer until later) | `status: draft` + 5-phase structure with each phase self-contained |
| Demonstrable + rollback-able per phase | Integration Contract block in every phase |

### Placeholder scan

No "TBD" / "implement later" / "similar to Phase N" — every code block contains actual file contents. The few `[bracketed]` items are configuration values the implementer will fill in from the existing project conventions.

### Type consistency

- `Issue` shape uses `file_path`, `line_number`, `message`, `code`, `severity` — matches the existing `LocalLinkCheckerRegexParser` output.
- Exit codes `0` / `1` / `127` mirror the existing `crackerjack.tools.*_wrapper.py` conventions.
- `HookDefinition.enable_flag` is named the same as in the crackerjack hook config; if your model uses a different attribute name, adapt.

### Integration contract

- **Triggered from:** Phase 1-3 trigger from `crackerjack run`; Phase 4 triggers from the `mahavishnu` manifest sweep.
- **Returns to / updates:** the `Issue` registry with `code="darnlink.<kind>"` for downstream routing.
- **Demonstrable by:** `crackerjack --enable-darnlink run` (Phases 1-3), `mahavishnu sweep --tag bodai-core` (Phase 4), `grep -rn "check-local-links" crackerjack/` returns nothing (Phase 5).
- **Rollback signal:** `enable_darnlink: false` in `settings/local.yaml` for Phases 1-4; `git revert` of the Phase 5 commit for the final removal.
- **Observability added:** per-run JSON findings log + (Phase 3 onward) a Prometheus counter for `darnlink_findings_total`.

### Feature tracking

This is a `{built, wired, adopted}` change spanning five phases. Track state in `docs/feature-tracking/2026-08-11-darnlink-fast-hook-replacement.md` using the existing template under `docs/feature-tracking/TEMPLATE.md`.

- Phase 1 = `built` (wrapper + tests + hook registration)
- Phase 2 = `wired` (pilot flag in `local.yaml.example`)
- Phase 3 = `wired` (default flip + `--no-darnlink` escape hatch)
- Phase 4 = `adopted` (rolled out across the 5 sibling Bodai repos)
- Phase 5 = `decommissioned` (`check-local-links` deleted)

### Plan-level risks

1. **darnlink maturity:** v0.7.0 "Early", 14 stars, single production user. Phase 1's TDD coverage + Phase 2's pilot run are the natural gates. If Phase 2 surfaces a disagreement between `check-local-links` and `darnlink`, pause before Phase 3 and document the discrepancy.
2. **GPL-3.0-or-later contamination:** every task in this plan uses `subprocess.run`. Do not "optimize" the wrapper later by inlining the call — that would convert crackerjack's wrapper into a derivative of darnlink and force the BSD-3 tree to GPL-3.
3. **Per-repo docs tree diversity:** Mahavishnu, Akosha, Dhara, Session-Buddy, and Oneiric each have their own docs conventions (some have `docs/`, some have `README.md` only). Phase 4 Step 4 may surface findings in repos that had no prior link-checker; budget time to triage rather than auto-revert.
4. **Anchor coverage gap:** `darnlink`'s UUID anchoring is opt-in (`<!-- dvn-anchor:UUID -->` markers must be added per file). The Phase 1 wrapper runs `darnlink check` (integrity mode), not `darnlink check --strict`. If anchor coverage becomes a goal later, it belongs in a separate plan.

---

Plan complete. Status is `draft`; ready to move to `active` when an implementer picks it up. Two execution options:

**1. Subagent-Driven (recommended)** — one fresh subagent per phase, review between phases. Phase 1's wrapper lands first; Phase 2-3 flip the default; Phase 4 sweeps the ecosystem; Phase 5 deletes the old hook. Each phase has demonstrable criteria, so review gates stay clean.

**2. Inline Execution** — execute phases in this session using executing-plans, batch execution with checkpoints between phases.
