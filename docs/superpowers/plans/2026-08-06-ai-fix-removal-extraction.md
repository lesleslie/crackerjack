# AI-Fix Removal + Mechanical Fixer Extraction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove crackerjack's four unstable, overlapping AI-fix orchestration subsystems (`agents/` coordinators, `ai_fix/`, `intelligence/`, `memory/`, `skills/`) while extracting and preserving the ~75-85% of `agents/` that is genuine deterministic fixer logic (AST transforms, regex rewrites, CLI wrapping), leaving crackerjack a leaner, stable tool-runner with a versioned `--json` contract.

**Architecture:** Deterministic fixer logic moves out of the `SubAgent`/coordinator framework into a new `crackerjack/fixers/` package of plain, framework-free callables. Shared issue vocabulary (`Issue`, `IssueType`, `Priority`, `FixResult`) moves to a new leaf module `crackerjack/models/issues.py` with zero dependency on anything being deleted. Everything else in `agents/`, plus all of `ai_fix/`, `intelligence/`, `memory/`, `skills/`, and the AI-specific code in `core/autofix_coordinator.py`/`core/phase_coordinator.py`, is deleted outright.

**Tech Stack:** Python 3.13+, pytest, ruff, ast/libcst (existing dependencies — no new ones), Pydantic (for the versioned JSON schema).

**Reference spec:** [docs/superpowers/specs/2026-08-06-ai-fix-removal-external-loop-design.md](../specs/2026-08-06-ai-fix-removal-external-loop-design.md)

## Global Constraints

- Never `git commit --amend`; always new commits (repo convention).
- Coverage ratchet (CLAUDE.md): "targets 100%, never decrease" — must be explicitly recalculated as part of this plan, not left to drift.
- No placeholders, TODOs, or dummy data (CLAUDE.md rule #3).
- Protocol-based DI: any surviving code importing from `crackerjack/models/protocols.py` must continue to import protocols, not concrete classes (CLAUDE.md architectural pattern).
- Only modify what's in scope; do not refactor unrelated code encountered along the way (CLAUDE.md rule #1).

## Scope note

This plan covers spec sections 1a, 1b, 2, 3, and 4 (extraction, shared vocabulary, `--json` contract, destructive removal, post-delete verification) — everything that happens **inside the crackerjack repository**. Spec sections 5 and 6 (the external loop driver and the Akosha logging hook, which live **outside** crackerjack) are a separate, independent plan: `docs/superpowers/plans/2026-08-06-ai-fix-external-loop.md`, because they depend on this plan's `--json` contract existing first and are otherwise a fully separate piece of software with its own test cycle.

## File Structure

**New files:**
- `crackerjack/models/issues.py` — `Issue`, `IssueType`, `Priority`, `FixResult`, and the versioned JSON output schema (extracted/redefined from `agents/base.py`).
- `crackerjack/fixers/__init__.py` — package marker + fixer registry (plain dict, no framework).
- `crackerjack/fixers/refactoring.py` — from `agents/refactoring_agent.py`.
- `crackerjack/fixers/performance.py` — from `agents/performance_agent.py`.
- `crackerjack/fixers/security.py` — from `agents/security_agent.py`.
- `crackerjack/fixers/documentation.py` — from `agents/documentation_agent.py`.
- `crackerjack/fixers/test_creation.py` — from `agents/test_creation_agent.py`.
- `crackerjack/fixers/dry.py` — from `agents/dry_agent.py`.
- `crackerjack/fixers/formatting.py` — from `agents/formatting_agent.py`.
- `crackerjack/fixers/import_optimization.py` — from `agents/import_optimization_agent.py`.
- `crackerjack/fixers/test_specialist.py` — from `agents/test_specialist_agent.py`.
- `crackerjack/fixers/refurb.py` — from `agents/refurb_agent.py`.
- `crackerjack/fixers/dead_code.py` — from `agents/dead_code_removal_agent.py`.
- `crackerjack/fixers/type_errors.py` — from `agents/type_error_specialist.py`.
- `crackerjack/fixers/anti_pattern.py` — from `agents/anti_pattern_agent.py`.
- `crackerjack/fixers/dependency.py` — from `agents/dependency_agent.py`.
- `crackerjack/fixers/architecture.py` — deterministic subset of `agents/architect_agent.py`.
- `crackerjack/fixers/semantic.py` — from `agents/semantic_agent.py`.
- `crackerjack/fixers/ast_transform/` — from `agents/helpers/ast_transform/` (patterns/, surgeons/, validator.py — moved as-is, these are already framework-free).
- `crackerjack/fixers/helpers/` — from `agents/helpers/refactoring/`, `agents/helpers/test_creation/`, `agents/helpers/performance/` (moved as-is).

**Deleted (whole packages/files):**
- `crackerjack/agents/` in its entirety (after extraction tasks below relocate the keepers) — includes `coordinator.py`, `enhanced_coordinator.py`, `fixer_coordinator.py`, `analysis_coordinator.py`, `validation_coordinator.py`, `parallel_dispatcher.py`, `claude_code_bridge.py`, `enhanced_proactive_agent.py`, `base.py`, `tracker.py`, and everything else not listed as extracted above.
- `crackerjack/ai_fix/` in its entirety.
- `crackerjack/intelligence/` in its entirety.
- `crackerjack/memory/` in its entirety.
- `crackerjack/skills/` in its entirety.

**Modified:**
- `crackerjack/models/protocols.py` — remove `AgentCoordinatorProtocol`, `AgentTrackerProtocol`, `AgentRegistryProtocol`.
- `crackerjack/core/autofix_coordinator.py` — remove AI-specific methods (list built during Task 30).
- `crackerjack/core/phase_coordinator.py` — remove AI-specific methods (list built during Task 30).
- `crackerjack/core/proactive_workflow.py`, `crackerjack/core/tier3_factory.py`, `crackerjack/documentation/dual_output_generator.py`, `crackerjack/services/batch_processor.py`, `crackerjack/services/agent_delegator.py`, `crackerjack/mcp/tools/skill_tools.py` — repointed off deleted orchestration.
- `crackerjack/adapters/format/ruff.py`, `crackerjack/parsers/{base,factory,json_parsers,lychee_parser,regex_parsers}.py` — import path repointed to `crackerjack/models/issues.py`.
- `crackerjack/__main__.py` — remove `--ai-fix` flag and its wiring.
- Eight files in `docs/superpowers/specs/` — frontmatter `superseded_by` set to this design's spec filename.

---

### Task 1: Baseline safety net

**Files:**
- None modified — this task only records state.

**Interfaces:** N/A (verification task).

- [ ] **Step 1: Confirm working tree is clean**

Run: `git status --short`
Expected: no output (clean tree). If not clean, stop and ask the user before proceeding — do not stash/discard silently.

- [ ] **Step 2: Record the current full test suite result**

Run: `python -m crackerjack run --run-tests 2>&1 | tee /tmp/crackerjack-baseline-$(date +%Y%m%d).log`

(Note: per repo constraints, `Date.now()`-style dynamic timestamps aren't available in Workflow scripts, but this is a plain shell command in an interactive session, so `date` is fine here.)

Record pass/fail counts and current coverage percentage from the output — paste them into a scratch note for comparison after Task 31 (final verification).

- [ ] **Step 3: Tag the pre-removal state**

```bash
git tag pre-ai-fix-removal
```

This is a cheap, reversible checkpoint — not a branch, just a tag for `git diff pre-ai-fix-removal..HEAD` reference later.

---

### Task 2: Create the shared issue vocabulary module

**Files:**
- Create: `crackerjack/models/issues.py`
- Test: `tests/unit/models/test_issues.py`
- Reference: `crackerjack/agents/base.py` (source of the four types — read this file in full before starting; it is 357 lines)

**Interfaces:**
- Produces: `Issue`, `IssueType` (Enum), `Priority` (Enum), `FixResult` — importable as `from crackerjack.models.issues import Issue, IssueType, Priority, FixResult`. These must be structurally identical (same fields, same enum values) to the current definitions in `agents/base.py`, since ~30 files depend on their exact shape.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/models/test_issues.py
from crackerjack.models.issues import Issue, IssueType, Priority, FixResult


def test_issue_type_has_no_agents_dependency():
    import crackerjack.models.issues as mod
    import inspect

    source = inspect.getsource(mod)
    assert "crackerjack.agents" not in source
    assert "crackerjack.ai_fix" not in source
    assert "crackerjack.intelligence" not in source
    assert "crackerjack.memory" not in source


def test_issue_constructs_with_expected_fields():
    issue = Issue(
        id="test-1",
        type=IssueType.FORMATTING,
        priority=Priority.MEDIUM,
        message="test message",
        file_path="foo.py",
    )
    assert issue.type is IssueType.FORMATTING


def test_fix_result_constructs():
    result = FixResult(success=True, fixed_issues=[], remaining_issues=[])
    assert result.success is True
```

(Adjust the `Issue`/`FixResult` constructor arguments in this test to match whatever fields `agents/base.py` actually defines — read the real dataclass/field list first; the test above is illustrative of the *shape* of the check, not a literal copy to paste blind.)

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/models/test_issues.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'crackerjack.models.issues'`

- [ ] **Step 3: Extract the four types verbatim**

Copy the full class/enum definitions of `Issue`, `IssueType`, `Priority`, `FixResult` from `crackerjack/agents/base.py` into `crackerjack/models/issues.py`, unchanged field-for-field. Do **not** copy `SubAgent`, `AgentContext`, `AgentRegistry`, or the module-level `agent_registry` singleton — those are deleted in Task 28, not relocated.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/models/test_issues.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add crackerjack/models/issues.py tests/unit/models/test_issues.py
git commit -m "feat(models): extract Issue/IssueType/Priority/FixResult into dependency-free module"
```

---

### Task 3: Define the versioned `--json` output schema

**Files:**
- Modify: `crackerjack/models/issues.py` (add schema)
- Test: `tests/unit/models/test_issues.py` (add golden-file test)
- Create: `tests/unit/models/fixtures/json_output_v1.json` (golden file)
- Reference: locate the current `--json` output construction — search `crackerjack/__main__.py` around the `json_output` option (line ~788) and follow it into whatever core module actually serializes results (likely `core/autofix_coordinator.py` or `core/phase_coordinator.py` — confirm exact location before writing this task's implementation).

**Interfaces:**
- Consumes: `Issue`, `IssueType`, `Priority`, `FixResult` from Task 2.
- Produces: `CrackerjackRunResult` (Pydantic model) with a `schema_version: str = "1"` field, importable as `from crackerjack.models.issues import CrackerjackRunResult`. This is what the external loop (separate plan) parses.

- [ ] **Step 1: Read the current `--json` output code path**

Run: `grep -rn "json_output" crackerjack/__main__.py crackerjack/core/*.py`

Identify exactly what dict/object is currently serialized to JSON today. Do not guess — this determines the schema's real current shape.

- [ ] **Step 2: Write the failing golden-file test**

```python
# tests/unit/models/test_issues.py (append)
import json
from pathlib import Path
from crackerjack.models.issues import CrackerjackRunResult

GOLDEN = Path(__file__).parent / "fixtures" / "json_output_v1.json"


def test_run_result_matches_golden_schema():
    result = CrackerjackRunResult(
        schema_version="1",
        success=False,
        issues=[],
        summary={"total": 0, "fixed": 0, "remaining": 0},
    )
    payload = json.loads(result.model_dump_json())
    golden = json.loads(GOLDEN.read_text())
    assert set(payload.keys()) == set(golden.keys())
    assert payload["schema_version"] == golden["schema_version"]
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/unit/models/test_issues.py::test_run_result_matches_golden_schema -v`
Expected: FAIL — `CrackerjackRunResult` and the golden fixture don't exist yet.

- [ ] **Step 4: Implement `CrackerjackRunResult` and write the golden fixture**

```python
# crackerjack/models/issues.py (append)
from pydantic import BaseModel


class CrackerjackRunResult(BaseModel):
    schema_version: str = "1"
    success: bool
    issues: list[Issue]
    summary: dict[str, int]
```

```json
// tests/unit/models/fixtures/json_output_v1.json
{
    "schema_version": "1",
    "success": false,
    "issues": [],
    "summary": {"total": 0, "fixed": 0, "remaining": 0}
}
```

- [ ] **Step 5: Wire `CrackerjackRunResult` into the actual `--json` output path found in Step 1**

Replace whatever ad-hoc dict construction currently backs `--json` output with `CrackerjackRunResult(...).model_dump_json()`, preserving every field the current output has today (add fields to the Pydantic model as needed to match — do not drop existing output fields silently).

- [ ] **Step 6: Run test to verify it passes, and manually diff real output**

Run: `pytest tests/unit/models/test_issues.py -v`
Expected: PASS

Run: `python -m crackerjack run --json 2>&1 | tail -1 | python -m json.tool`
Expected: valid JSON containing `"schema_version": "1"` and all fields the pre-change output had.

- [ ] **Step 7: Commit**

```bash
git add crackerjack/models/issues.py tests/unit/models/
git commit -m "feat(models): versioned --json output schema with golden-file contract test"
```

---

### Task 4: Extract `refactoring_agent.py` → `crackerjack/fixers/refactoring.py`

**Files:**
- Read: `crackerjack/agents/refactoring_agent.py` (1,639 lines), `crackerjack/agents/helpers/ast_transform/` (moved in Task 18, but read now for reference)
- Create: `crackerjack/fixers/refactoring.py`
- Test: `tests/fixers/test_refactoring.py` (new; port relevant cases from existing `tests/agents/test_refactoring_agent.py` if present — locate it with `find tests -iname "*refactoring*"`)

**Interfaces:**
- Produces: plain functions, not a class inheriting `SubAgent`. Exact function names are determined by what's actually in the file (e.g., a `_reduce_complexity` method becomes a module-level `reduce_complexity(source: str, issue: Issue) -> FixResult` function) — read the file fully before naming; do not invent signatures that don't correspond to real logic in the source file.

- [ ] **Step 1: Read the full source file**

Read `crackerjack/agents/refactoring_agent.py` completely. Identify every method that does AST/regex transformation work (confirmed present: `_reduce_complexity`, `_extract_nested_conditions`, and others found during the file read) versus every method that exists only for `SubAgent`/coordinator plumbing (`can_handle`, `confidence`, anything referencing `self.context.agent_registry` or `FixResult` dispatch bookkeeping unrelated to the actual transform).

- [ ] **Step 2: Find and read the existing test file**

Run: `find tests -iname "*refactoring_agent*" -o -iname "*refactoring*agent*"`

Read whatever is found. Identify which existing test cases exercise the transform logic (keep, port) versus which exercise `SubAgent`/coordinator dispatch behavior (drop — that framework no longer exists).

- [ ] **Step 3: Write the ported test file with the kept cases**

Port each kept test case into `tests/fixers/test_refactoring.py`, updating imports from `crackerjack.agents.refactoring_agent` to `crackerjack.fixers.refactoring`, and updating call sites from `agent.some_method(...)` to the new plain-function form decided in Step 1. Keep assertions identical — the goal is same behavior, different calling convention.

- [ ] **Step 4: Run the ported tests to verify they fail**

Run: `pytest tests/fixers/test_refactoring.py -v`
Expected: FAIL — `crackerjack.fixers.refactoring` doesn't exist yet.

- [ ] **Step 5: Create `crackerjack/fixers/refactoring.py` with the ported logic**

Copy the transform methods identified in Step 1 into module-level functions in the new file, with `self`/`self.context` references removed or converted to explicit parameters (e.g. `self.context.get_file_content(path)` becomes a `source: str` parameter passed in by the caller). Import only `crackerjack.models.issues` types — no import of anything from `crackerjack.agents`.

- [ ] **Step 6: Run the ported tests to verify they pass**

Run: `pytest tests/fixers/test_refactoring.py -v`
Expected: PASS

- [ ] **Step 7: Verify no dependency leaked back to `agents/`**

Run: `grep -n "crackerjack.agents\|crackerjack.ai_fix\|crackerjack.intelligence\|crackerjack.memory" crackerjack/fixers/refactoring.py`
Expected: no output.

- [ ] **Step 8: Commit**

```bash
git add crackerjack/fixers/refactoring.py tests/fixers/test_refactoring.py
git commit -m "refactor(fixers): extract refactoring_agent transform logic as plain functions"
```

---

### Task 5: Extract `performance_agent.py` → `crackerjack/fixers/performance.py`

**Files:**
- Read: `crackerjack/agents/performance_agent.py`, `crackerjack/agents/helpers/performance/` (the `PerformanceASTAnalyzer` helper)
- Create: `crackerjack/fixers/performance.py`, `crackerjack/fixers/helpers/performance/`
- Test: `tests/fixers/test_performance.py`

**Interfaces:**
- Produces: plain functions wrapping `PerformanceASTAnalyzer`'s AST-based hot-spot detection — exact names determined by reading the file (do not invent signatures not backed by real logic in the source).

- [ ] **Step 1:** Read `crackerjack/agents/performance_agent.py` and `crackerjack/agents/helpers/performance/` in full. Identify every method doing real AST analysis (delegates to `PerformanceASTAnalyzer`) versus `SubAgent`/coordinator plumbing (`can_handle`, `confidence`, dispatch bookkeeping).
- [ ] **Step 2:** Run `find tests -iname "*performance*agent*"` and read what's found. Identify which test cases exercise the AST analysis (keep) versus `SubAgent` dispatch behavior (drop).
- [ ] **Step 3:** Port the kept test cases into `tests/fixers/test_performance.py`, updating imports from `crackerjack.agents.performance_agent` to `crackerjack.fixers.performance` and call sites to the new plain-function form from Step 1.
- [ ] **Step 4:** Run `pytest tests/fixers/test_performance.py -v`. Expected: FAIL (`crackerjack.fixers.performance` doesn't exist yet).
- [ ] **Step 5:** Create `crackerjack/fixers/performance.py` and `crackerjack/fixers/helpers/performance/` with the ported `PerformanceASTAnalyzer` logic as module-level functions, `self`/`self.context` converted to explicit parameters. Import only `crackerjack.models.issues` types.
- [ ] **Step 6:** Run `pytest tests/fixers/test_performance.py -v`. Expected: PASS.
- [ ] **Step 7:** Run `grep -n "crackerjack.agents\|crackerjack.ai_fix\|crackerjack.intelligence\|crackerjack.memory" crackerjack/fixers/performance.py`. Expected: no output.
- [ ] **Step 8:** Commit:
```bash
git add crackerjack/fixers/performance.py crackerjack/fixers/helpers/performance tests/fixers/test_performance.py
git commit -m "refactor(fixers): extract performance_agent AST analysis as plain functions"
```

---

### Task 6: Extract `security_agent.py` → `crackerjack/fixers/security.py`

**Files:**
- Read: `crackerjack/agents/security_agent.py` (1,118 lines)
- Create: `crackerjack/fixers/security.py`
- Test: `tests/fixers/test_security.py`

**Interfaces:**
- Produces: plain functions wrapping the `SAFE_PATTERNS` regex library and `_fix_regex_patterns_project_wide` — exact names determined by reading the file.

- [ ] **Step 1:** Read `crackerjack/agents/security_agent.py` in full. Identify every method doing real regex-based fixing (uses `SAFE_PATTERNS`, `_fix_regex_patterns_project_wide`) versus `SubAgent`/coordinator plumbing.
- [ ] **Step 2:** Run `find tests -iname "*security*agent*"` and read what's found. Identify which test cases exercise the regex fixes (keep) versus dispatch behavior (drop).
- [ ] **Step 3:** Port the kept test cases into `tests/fixers/test_security.py`, updating imports from `crackerjack.agents.security_agent` to `crackerjack.fixers.security` and call sites to match Step 1's plain-function form.
- [ ] **Step 4:** Run `pytest tests/fixers/test_security.py -v`. Expected: FAIL.
- [ ] **Step 5:** Create `crackerjack/fixers/security.py` with the ported `SAFE_PATTERNS`/fix logic as module-level functions, `self.context` references converted to explicit parameters. Import only `crackerjack.models.issues` types.
- [ ] **Step 6:** Run `pytest tests/fixers/test_security.py -v`. Expected: PASS.
- [ ] **Step 7:** Run `grep -n "crackerjack.agents\|crackerjack.ai_fix\|crackerjack.intelligence\|crackerjack.memory" crackerjack/fixers/security.py`. Expected: no output.
- [ ] **Step 8:** Commit:
```bash
git add crackerjack/fixers/security.py tests/fixers/test_security.py
git commit -m "refactor(fixers): extract security_agent regex fixes as plain functions"
```

---

### Task 7: Extract `documentation_agent.py` → `crackerjack/fixers/documentation.py`

**Files:**
- Read: `crackerjack/agents/documentation_agent.py` (888 lines)
- Create: `crackerjack/fixers/documentation.py`
- Test: `tests/fixers/test_documentation.py`

**Interfaces:**
- Produces: plain functions wrapping `_get_commit_messages`/`_generate_changelog_entry` (git-log-based, regex parsing) — exact names determined by reading the file.

- [ ] **Step 1:** Read `crackerjack/agents/documentation_agent.py` in full. Identify every method doing real changelog generation (`_get_commit_messages`, `_generate_changelog_entry`, and any related helpers) versus `SubAgent`/coordinator plumbing. Confirm zero LLM/bridge references remain, per the design investigation's finding.
- [ ] **Step 2:** Run `find tests -iname "*documentation*agent*"` and read what's found. Identify which test cases exercise changelog generation (keep) versus dispatch behavior (drop).
- [ ] **Step 3:** Port the kept test cases into `tests/fixers/test_documentation.py`, updating imports from `crackerjack.agents.documentation_agent` to `crackerjack.fixers.documentation` and call sites to match Step 1's plain-function form.
- [ ] **Step 4:** Run `pytest tests/fixers/test_documentation.py -v`. Expected: FAIL.
- [ ] **Step 5:** Create `crackerjack/fixers/documentation.py` with the ported changelog logic as module-level functions, `self.context` references converted to explicit parameters. Import only `crackerjack.models.issues` types.
- [ ] **Step 6:** Run `pytest tests/fixers/test_documentation.py -v`. Expected: PASS.
- [ ] **Step 7:** Run `grep -n "crackerjack.agents\|crackerjack.ai_fix\|crackerjack.intelligence\|crackerjack.memory" crackerjack/fixers/documentation.py`. Expected: no output.
- [ ] **Step 8:** Commit:
```bash
git add crackerjack/fixers/documentation.py tests/fixers/test_documentation.py
git commit -m "refactor(fixers): extract documentation_agent changelog logic as plain functions"
```

---

### Task 8: Extract `test_creation_agent.py` → `crackerjack/fixers/test_creation.py`

**Files:**
- Read: `crackerjack/agents/test_creation_agent.py` (793 lines), `crackerjack/agents/helpers/test_creation/` (the `TestASTAnalyzer` helper and `test_template_generator.py`)
- Create: `crackerjack/fixers/test_creation.py`, `crackerjack/fixers/helpers/test_creation/`
- Test: `tests/fixers/test_test_creation.py`

**Interfaces:**
- Produces: plain functions wrapping `TestASTAnalyzer`'s `ast.parse`/`ast.walk` scaffolding over `FunctionDef`/`AsyncFunctionDef` nodes — exact names determined by reading the file.

- [ ] **Step 1:** Read `crackerjack/agents/test_creation_agent.py` and `crackerjack/agents/helpers/test_creation/` in full. Identify every method doing real AST-based test scaffolding versus `SubAgent`/coordinator plumbing.
- [ ] **Step 2:** Run `find tests -iname "*test_creation*agent*"` and read what's found. Identify which test cases exercise scaffolding (keep) versus dispatch behavior (drop).
- [ ] **Step 3:** Port the kept test cases into `tests/fixers/test_test_creation.py`, updating imports from `crackerjack.agents.test_creation_agent` to `crackerjack.fixers.test_creation` and call sites to match Step 1's plain-function form.
- [ ] **Step 4:** Run `pytest tests/fixers/test_test_creation.py -v`. Expected: FAIL.
- [ ] **Step 5:** Create `crackerjack/fixers/test_creation.py` and `crackerjack/fixers/helpers/test_creation/` with the ported `TestASTAnalyzer`/`test_template_generator` logic as module-level functions, `self.context` references converted to explicit parameters. Import only `crackerjack.models.issues` types.
- [ ] **Step 6:** Run `pytest tests/fixers/test_test_creation.py -v`. Expected: PASS.
- [ ] **Step 7:** Run `grep -n "crackerjack.agents\|crackerjack.ai_fix\|crackerjack.intelligence\|crackerjack.memory" crackerjack/fixers/test_creation.py`. Expected: no output.
- [ ] **Step 8:** Commit:
```bash
git add crackerjack/fixers/test_creation.py crackerjack/fixers/helpers/test_creation tests/fixers/test_test_creation.py
git commit -m "refactor(fixers): extract test_creation_agent AST scaffolding as plain functions"
```

---

### Task 9: Extract `dry_agent.py` → `crackerjack/fixers/dry.py`

**Files:**
- Read: `crackerjack/agents/dry_agent.py` (589 lines)
- Create: `crackerjack/fixers/dry.py`
- Test: `tests/fixers/test_dry.py`

**Interfaces:**
- Produces: plain functions wrapping `_detect_error_response_patterns`/`_detect_exception_patterns` (regex-driven duplicate detection) — exact names determined by reading the file.

- [ ] **Step 1:** Read `crackerjack/agents/dry_agent.py` in full. Identify every method doing real regex-driven duplicate-pattern detection versus `SubAgent`/coordinator plumbing.
- [ ] **Step 2:** Run `find tests -iname "*dry*agent*"` and read what's found. Identify which test cases exercise the detectors (keep) versus dispatch behavior (drop).
- [ ] **Step 3:** Port the kept test cases into `tests/fixers/test_dry.py`, updating imports from `crackerjack.agents.dry_agent` to `crackerjack.fixers.dry` and call sites to match Step 1's plain-function form.
- [ ] **Step 4:** Run `pytest tests/fixers/test_dry.py -v`. Expected: FAIL.
- [ ] **Step 5:** Create `crackerjack/fixers/dry.py` with the ported detector/fix logic as module-level functions, `self.context` references converted to explicit parameters. Import only `crackerjack.models.issues` types.
- [ ] **Step 6:** Run `pytest tests/fixers/test_dry.py -v`. Expected: PASS.
- [ ] **Step 7:** Run `grep -n "crackerjack.agents\|crackerjack.ai_fix\|crackerjack.intelligence\|crackerjack.memory" crackerjack/fixers/dry.py`. Expected: no output.
- [ ] **Step 8:** Commit:
```bash
git add crackerjack/fixers/dry.py tests/fixers/test_dry.py
git commit -m "refactor(fixers): extract dry_agent duplicate-pattern detectors as plain functions"
```

---

### Task 10: Extract `formatting_agent.py` → `crackerjack/fixers/formatting.py`

**Files:**
- Read: `crackerjack/agents/formatting_agent.py` (506 lines)
- Create: `crackerjack/fixers/formatting.py`
- Test: `tests/fixers/test_formatting.py`

**Interfaces:**
- Produces: plain functions wrapping `_apply_ruff_fixes` (subprocess shell-out to `ruff`) plus manual whitespace/tab fixes — exact names determined by reading the file.

- [ ] **Step 1:** Read `crackerjack/agents/formatting_agent.py` in full. Identify every method doing real formatting work (`_apply_ruff_fixes`, manual whitespace/tab fixes) versus `SubAgent`/coordinator plumbing.
- [ ] **Step 2:** Run `find tests -iname "*formatting*agent*"` and read what's found. Identify which test cases exercise the ruff wrapper/whitespace fixes (keep) versus dispatch behavior (drop).
- [ ] **Step 3:** Port the kept test cases into `tests/fixers/test_formatting.py`, updating imports from `crackerjack.agents.formatting_agent` to `crackerjack.fixers.formatting` and call sites to match Step 1's plain-function form.
- [ ] **Step 4:** Run `pytest tests/fixers/test_formatting.py -v`. Expected: FAIL.
- [ ] **Step 5:** Create `crackerjack/fixers/formatting.py` with the ported ruff-subprocess/whitespace logic as module-level functions, `self.context` references converted to explicit parameters. Import only `crackerjack.models.issues` types.
- [ ] **Step 6:** Run `pytest tests/fixers/test_formatting.py -v`. Expected: PASS.
- [ ] **Step 7:** Run `grep -n "crackerjack.agents\|crackerjack.ai_fix\|crackerjack.intelligence\|crackerjack.memory" crackerjack/fixers/formatting.py`. Expected: no output.
- [ ] **Step 8:** Commit:
```bash
git add crackerjack/fixers/formatting.py tests/fixers/test_formatting.py
git commit -m "refactor(fixers): extract formatting_agent ruff-wrapper logic as plain functions"
```

---

### Task 11: Extract `import_optimization_agent.py` → `crackerjack/fixers/import_optimization.py`

**Files:**
- Read: `crackerjack/agents/import_optimization_agent.py` (2,134 lines — second-largest file in the plan; budget extra time for Step 1)
- Create: `crackerjack/fixers/import_optimization.py`
- Test: `tests/fixers/test_import_optimization.py`

**Interfaces:**
- Produces: plain functions wrapping the `ast`-based import analysis plus `_run_vulture_analysis` (subprocess shell-out to `vulture`) — exact names determined by reading the file.

- [ ] **Step 1:** Read `crackerjack/agents/import_optimization_agent.py` in full — this is the second-largest extraction in the plan, so enumerate every method as a checklist rather than skimming. Identify every method doing real import-optimization work (`ast` usage, `_run_vulture_analysis`) versus `SubAgent`/coordinator plumbing.
- [ ] **Step 2:** Run `find tests -iname "*import_optimization*agent*"` and read what's found. Identify which test cases exercise the ast/vulture logic (keep) versus dispatch behavior (drop).
- [ ] **Step 3:** Port the kept test cases into `tests/fixers/test_import_optimization.py`, updating imports from `crackerjack.agents.import_optimization_agent` to `crackerjack.fixers.import_optimization` and call sites to match Step 1's plain-function form.
- [ ] **Step 4:** Run `pytest tests/fixers/test_import_optimization.py -v`. Expected: FAIL.
- [ ] **Step 5:** Create `crackerjack/fixers/import_optimization.py` with the ported ast/vulture logic as module-level functions, `self.context` references converted to explicit parameters. Import only `crackerjack.models.issues` types.
- [ ] **Step 6:** Run `pytest tests/fixers/test_import_optimization.py -v`. Expected: PASS.
- [ ] **Step 7:** Run `grep -n "crackerjack.agents\|crackerjack.ai_fix\|crackerjack.intelligence\|crackerjack.memory" crackerjack/fixers/import_optimization.py`. Expected: no output.
- [ ] **Step 8:** Commit:
```bash
git add crackerjack/fixers/import_optimization.py tests/fixers/test_import_optimization.py
git commit -m "refactor(fixers): extract import_optimization_agent ast/vulture logic as plain functions"
```

---

### Task 12: Extract `test_specialist_agent.py` → `crackerjack/fixers/test_specialist.py`

**Files:**
- Read: `crackerjack/agents/test_specialist_agent.py` (530 lines)
- Create: `crackerjack/fixers/test_specialist.py`
- Test: `tests/fixers/test_test_specialist.py`

**Interfaces:**
- Produces: plain functions wrapping `_identify_failure_type` (string/regex matching) and templated fixture/import fixes — exact names determined by reading the file.

- [ ] **Step 1:** Read `crackerjack/agents/test_specialist_agent.py` in full. Identify every method doing real failure-type classification and templated fixes versus `SubAgent`/coordinator plumbing.
- [ ] **Step 2:** Run `find tests -iname "*test_specialist*agent*"` and read what's found. Identify which test cases exercise the classification/templating (keep) versus dispatch behavior (drop).
- [ ] **Step 3:** Port the kept test cases into `tests/fixers/test_test_specialist.py`, updating imports from `crackerjack.agents.test_specialist_agent` to `crackerjack.fixers.test_specialist` and call sites to match Step 1's plain-function form.
- [ ] **Step 4:** Run `pytest tests/fixers/test_test_specialist.py -v`. Expected: FAIL.
- [ ] **Step 5:** Create `crackerjack/fixers/test_specialist.py` with the ported classification/templating logic as module-level functions, `self.context` references converted to explicit parameters. Import only `crackerjack.models.issues` types.
- [ ] **Step 6:** Run `pytest tests/fixers/test_test_specialist.py -v`. Expected: PASS.
- [ ] **Step 7:** Run `grep -n "crackerjack.agents\|crackerjack.ai_fix\|crackerjack.intelligence\|crackerjack.memory" crackerjack/fixers/test_specialist.py`. Expected: no output.
- [ ] **Step 8:** Commit:
```bash
git add crackerjack/fixers/test_specialist.py tests/fixers/test_test_specialist.py
git commit -m "refactor(fixers): extract test_specialist_agent failure-type fixes as plain functions"
```

---

### Task 13: Extract `refurb_agent.py` → `crackerjack/fixers/refurb.py`

**Files:**
- Read: `crackerjack/agents/refurb_agent.py` (2,146 lines — the largest single extraction in the plan)
- Create: `crackerjack/fixers/refurb.py`
- Test: `tests/fixers/test_refurb.py`

**Interfaces:**
- Produces: plain functions, one per `_ast_transform_*` method (confirmed present: `_ast_transform_startswith_tuple`, `_ast_transform_membership_tuple`, and at least 8 more — enumerate all of them in Step 1, do not assume only the two named ones exist).

- [ ] **Step 1:** Read `crackerjack/agents/refurb_agent.py` in full. Build an explicit checklist of every `_ast_transform_*` method found (there are 10+) before touching anything else, so none are silently dropped during extraction. Separately identify `SubAgent`/coordinator plumbing to exclude.
- [ ] **Step 2:** Run `find tests -iname "*refurb*agent*"` and read what's found. Cross-check every transform in the Step 1 checklist against the test file — note any transform with no corresponding test coverage (port what exists; flag gaps, don't invent tests for untested transforms beyond what's needed to prove the port is faithful).
- [ ] **Step 3:** Port the kept test cases into `tests/fixers/test_refurb.py`, updating imports from `crackerjack.agents.refurb_agent` to `crackerjack.fixers.refurb` and call sites to match Step 1's plain-function form, one test group per transform.
- [ ] **Step 4:** Run `pytest tests/fixers/test_refurb.py -v`. Expected: FAIL.
- [ ] **Step 5:** Create `crackerjack/fixers/refurb.py` with every checklisted `_ast_transform_*` method ported as a module-level function, `self.context` references converted to explicit parameters. Import only `crackerjack.models.issues` types. Tick off each transform on the Step 1 checklist as it's ported.
- [ ] **Step 6:** Run `pytest tests/fixers/test_refurb.py -v`. Expected: PASS.
- [ ] **Step 7:** Run `grep -n "crackerjack.agents\|crackerjack.ai_fix\|crackerjack.intelligence\|crackerjack.memory" crackerjack/fixers/refurb.py`. Expected: no output. Also confirm the Step 1 checklist is fully ticked off — no transform left behind.
- [ ] **Step 8:** Commit:
```bash
git add crackerjack/fixers/refurb.py tests/fixers/test_refurb.py
git commit -m "refactor(fixers): extract refurb_agent AST transforms as plain functions"
```

---

### Task 14: Extract `dead_code_removal_agent.py` → `crackerjack/fixers/dead_code.py`

**Files:**
- Read: `crackerjack/agents/dead_code_removal_agent.py` (712 lines)
- Create: `crackerjack/fixers/dead_code.py`
- Test: `tests/fixers/test_dead_code.py`

**Interfaces:**
- Produces: plain functions wrapping the `ast`-based dead-code detection and its existing backup/rollback file-edit safety mechanism (preserve this behavior — it's independently valuable) — exact names determined by reading the file.

- [ ] **Step 1:** Read `crackerjack/agents/dead_code_removal_agent.py` in full. Identify every method doing real dead-code detection/removal (including the backup/rollback mechanism) versus `SubAgent`/coordinator plumbing.
- [ ] **Step 2:** Run `find tests -iname "*dead_code*agent*"` and read what's found. Identify which test cases exercise detection/removal/rollback (keep) versus dispatch behavior (drop).
- [ ] **Step 3:** Port the kept test cases into `tests/fixers/test_dead_code.py`, updating imports from `crackerjack.agents.dead_code_removal_agent` to `crackerjack.fixers.dead_code` and call sites to match Step 1's plain-function form.
- [ ] **Step 4:** Run `pytest tests/fixers/test_dead_code.py -v`. Expected: FAIL.
- [ ] **Step 5:** Create `crackerjack/fixers/dead_code.py` with the ported detection/removal/rollback logic as module-level functions, `self.context` references converted to explicit parameters. Import only `crackerjack.models.issues` types.
- [ ] **Step 6:** Run `pytest tests/fixers/test_dead_code.py -v`. Expected: PASS.
- [ ] **Step 7:** Run `grep -n "crackerjack.agents\|crackerjack.ai_fix\|crackerjack.intelligence\|crackerjack.memory" crackerjack/fixers/dead_code.py`. Expected: no output.
- [ ] **Step 8:** Commit:
```bash
git add crackerjack/fixers/dead_code.py tests/fixers/test_dead_code.py
git commit -m "refactor(fixers): extract dead_code_removal_agent AST logic as plain functions"
```

---

### Task 15: Extract `type_error_specialist.py` → `crackerjack/fixers/type_errors.py`

**Files:**
- Read: `crackerjack/agents/type_error_specialist.py` (1,107 lines)
- Create: `crackerjack/fixers/type_errors.py`
- Test: `tests/fixers/test_type_errors.py`

**Interfaces:**
- Produces: plain functions wrapping the `ast.parse`/`ast.Module` splicing logic for Literal-type fixes — exact names determined by reading the file.

- [ ] **Step 1:** Read `crackerjack/agents/type_error_specialist.py` in full. Identify every method doing real AST splicing for type fixes versus `SubAgent`/coordinator plumbing.
- [ ] **Step 2:** Run `find tests -iname "*type_error*specialist*"` and read what's found. Identify which test cases exercise the splicing logic (keep) versus dispatch behavior (drop).
- [ ] **Step 3:** Port the kept test cases into `tests/fixers/test_type_errors.py`, updating imports from `crackerjack.agents.type_error_specialist` to `crackerjack.fixers.type_errors` and call sites to match Step 1's plain-function form.
- [ ] **Step 4:** Run `pytest tests/fixers/test_type_errors.py -v`. Expected: FAIL.
- [ ] **Step 5:** Create `crackerjack/fixers/type_errors.py` with the ported AST-splicing logic as module-level functions, `self.context` references converted to explicit parameters. Import only `crackerjack.models.issues` types.
- [ ] **Step 6:** Run `pytest tests/fixers/test_type_errors.py -v`. Expected: PASS.
- [ ] **Step 7:** Run `grep -n "crackerjack.agents\|crackerjack.ai_fix\|crackerjack.intelligence\|crackerjack.memory" crackerjack/fixers/type_errors.py`. Expected: no output.
- [ ] **Step 8:** Commit:
```bash
git add crackerjack/fixers/type_errors.py tests/fixers/test_type_errors.py
git commit -m "refactor(fixers): extract type_error_specialist AST splicing as plain functions"
```

---

### Task 16: Extract `anti_pattern_agent.py` → `crackerjack/fixers/anti_pattern.py`

**Files:**
- Read: `crackerjack/agents/anti_pattern_agent.py`
- Create: `crackerjack/fixers/anti_pattern.py`
- Test: `tests/fixers/test_anti_pattern.py`

**Interfaces:**
- Produces: plain functions wrapping the `ast`-based anti-pattern detection/fix logic — exact names determined by reading the file.

- [ ] **Step 1:** Read `crackerjack/agents/anti_pattern_agent.py` in full. Identify every method doing real AST-based anti-pattern detection versus `SubAgent`/coordinator plumbing.
- [ ] **Step 2:** Run `find tests -iname "*anti_pattern*agent*"` and read what's found. Identify which test cases exercise detection/fixing (keep) versus dispatch behavior (drop).
- [ ] **Step 3:** Port the kept test cases into `tests/fixers/test_anti_pattern.py`, updating imports from `crackerjack.agents.anti_pattern_agent` to `crackerjack.fixers.anti_pattern` and call sites to match Step 1's plain-function form.
- [ ] **Step 4:** Run `pytest tests/fixers/test_anti_pattern.py -v`. Expected: FAIL.
- [ ] **Step 5:** Create `crackerjack/fixers/anti_pattern.py` with the ported AST logic as module-level functions, `self.context` references converted to explicit parameters. Import only `crackerjack.models.issues` types.
- [ ] **Step 6:** Run `pytest tests/fixers/test_anti_pattern.py -v`. Expected: PASS.
- [ ] **Step 7:** Run `grep -n "crackerjack.agents\|crackerjack.ai_fix\|crackerjack.intelligence\|crackerjack.memory" crackerjack/fixers/anti_pattern.py`. Expected: no output.
- [ ] **Step 8:** Commit:
```bash
git add crackerjack/fixers/anti_pattern.py tests/fixers/test_anti_pattern.py
git commit -m "refactor(fixers): extract anti_pattern_agent AST logic as plain functions"
```

---

### Task 17: Extract `dependency_agent.py` → `crackerjack/fixers/dependency.py`

**Files:**
- Read: `crackerjack/agents/dependency_agent.py`
- Create: `crackerjack/fixers/dependency.py`
- Test: `tests/fixers/test_dependency.py`

**Interfaces:**
- Produces: plain functions wrapping the regex-based `pyproject.toml` dependency removal logic — exact names determined by reading the file.

- [ ] **Step 1:** Read `crackerjack/agents/dependency_agent.py` in full. Identify every method doing real `pyproject.toml` regex editing versus `SubAgent`/coordinator plumbing.
- [ ] **Step 2:** Run `find tests -iname "*dependency*agent*"` and read what's found. Identify which test cases exercise the dependency-removal logic (keep) versus dispatch behavior (drop).
- [ ] **Step 3:** Port the kept test cases into `tests/fixers/test_dependency.py`, updating imports from `crackerjack.agents.dependency_agent` to `crackerjack.fixers.dependency` and call sites to match Step 1's plain-function form.
- [ ] **Step 4:** Run `pytest tests/fixers/test_dependency.py -v`. Expected: FAIL.
- [ ] **Step 5:** Create `crackerjack/fixers/dependency.py` with the ported `pyproject.toml` regex logic as module-level functions, `self.context` references converted to explicit parameters. Import only `crackerjack.models.issues` types.
- [ ] **Step 6:** Run `pytest tests/fixers/test_dependency.py -v`. Expected: PASS.
- [ ] **Step 7:** Run `grep -n "crackerjack.agents\|crackerjack.ai_fix\|crackerjack.intelligence\|crackerjack.memory" crackerjack/fixers/dependency.py`. Expected: no output.
- [ ] **Step 8:** Commit:
```bash
git add crackerjack/fixers/dependency.py tests/fixers/test_dependency.py
git commit -m "refactor(fixers): extract dependency_agent pyproject.toml fixes as plain functions"
```

---

### Task 18: Move `agents/helpers/ast_transform/` and remaining helper support modules as-is

**Files:**
- Move: `crackerjack/agents/helpers/ast_transform/` (including `patterns/`, `surgeons/libcst_surgeon.py` — 1,809 lines, `validator.py`) → `crackerjack/fixers/ast_transform/`
- Move: `crackerjack/agents/helpers/refactoring/code_transformer.py` → `crackerjack/fixers/helpers/refactoring/code_transformer.py` (if not already covered by Task 4's extraction)
- Test: existing tests under `tests/agents/helpers/ast_transform/` (locate with `find tests -path "*ast_transform*"`) move to `tests/fixers/ast_transform/`, import paths updated.

**Interfaces:**
- Consumes: nothing from `agents/` after the move.
- Produces: the same public API these modules already have today (this is a location move, not a rewrite — these files were already found to be framework-free during the design investigation).

- [ ] **Step 1: Verify these modules are genuinely framework-free before moving**

Run: `grep -rn "SubAgent\|AgentContext\|agent_registry\|from crackerjack.agents.coordinator\|from crackerjack.agents.base" crackerjack/agents/helpers/ast_transform/`

Expected: no output, or only `Issue`/`IssueType`/`FixResult` type imports (fine — these get repointed to `crackerjack.models.issues` in Step 2). If anything else shows up, stop and treat that file as needing the full Task-4-style extraction instead of a straight move.

- [ ] **Step 2: Move the directory and repoint type imports**

```bash
git mv crackerjack/agents/helpers/ast_transform crackerjack/fixers/ast_transform
```

Then update any `from crackerjack.agents.base import Issue, IssueType, FixResult` lines found inside the moved files to `from crackerjack.models.issues import Issue, IssueType, FixResult`.

- [ ] **Step 3: Move and repoint the corresponding tests**

```bash
git mv tests/agents/helpers/ast_transform tests/fixers/ast_transform
```

Update import paths inside the moved test files the same way.

- [ ] **Step 4: Run the moved tests**

Run: `pytest tests/fixers/ast_transform/ -v`
Expected: PASS (behavior is unchanged, only import paths moved).

- [ ] **Step 5: Commit**

```bash
git add -A crackerjack/fixers/ast_transform tests/fixers/ast_transform
git commit -m "refactor(fixers): move ast_transform helpers out of agents/ (framework-free, no logic change)"
```

---

### Task 19: Extract the deterministic subset of `architect_agent.py` → `crackerjack/fixers/architecture.py`

**Files:**
- Read: `crackerjack/agents/architect_agent.py` (729 lines)
- Create: `crackerjack/fixers/architecture.py`
- Test: `tests/fixers/test_architecture.py`

**Interfaces:**
- Produces: plain functions for the `TYPE_ERROR`/`DEPENDENCY`/`DOCUMENTATION` fix methods only (confirmed present: `_apply_type_error_fixes`, `_fix_missing_typing_imports`).
- Explicitly drops: the `COMPLEXITY`/`DRY_VIOLATION` branch that returns `{"strategy": "external_specialist_guided", "specialist": "crackerjack-architect"}` and the `execute_with_plan` method that refuses to act on it — this is bucket-B orchestration-deferral logic with no independent value once the coordinator is gone.

- [ ] **Step 1: Read the full source file and confirm the mixed split**

Read `crackerjack/agents/architect_agent.py` in full. Confirm which methods handle `TYPE_ERROR`/`DEPENDENCY`/`DOCUMENTATION` (extract) versus `COMPLEXITY`/`DRY_VIOLATION` (drop, per the design's finding that this branch just defers to an external specialist by name rather than fixing anything).

- [ ] **Step 2: Find and read the existing test file, keep only cases for the extracted methods**

Run: `find tests -iname "*architect*agent*"`

Port test cases covering `_apply_type_error_fixes`/`_fix_missing_typing_imports` only; drop test cases asserting on the `external_specialist_guided` plan-return behavior.

- [ ] **Step 3: Write the ported test file**

As in Task 4 Step 3, targeting `tests/fixers/test_architecture.py`.

- [ ] **Step 4: Run to verify failure**

Run: `pytest tests/fixers/test_architecture.py -v`
Expected: FAIL — module doesn't exist yet.

- [ ] **Step 5: Create `crackerjack/fixers/architecture.py` with only the extracted methods**

- [ ] **Step 6: Run to verify pass**

Run: `pytest tests/fixers/test_architecture.py -v`
Expected: PASS

- [ ] **Step 7: Verify no dependency leaked back to `agents/`**

Run: `grep -n "crackerjack.agents\|crackerjack.ai_fix\|crackerjack.intelligence\|crackerjack.memory\|external_specialist_guided" crackerjack/fixers/architecture.py`
Expected: no output.

- [ ] **Step 8: Commit**

```bash
git add crackerjack/fixers/architecture.py tests/fixers/test_architecture.py
git commit -m "refactor(fixers): extract architect_agent deterministic fixes, drop external-specialist deferral branch"
```

---

### Task 20: Extract `semantic_agent.py` → `crackerjack/fixers/semantic.py`

**Files:**
- Read: `crackerjack/agents/semantic_agent.py`
- Create: `crackerjack/fixers/semantic.py`
- Test: `tests/fixers/test_semantic.py`

**Interfaces:**
- Produces: plain functions wrapping the local `VectorStore`/embedding-search logic (confirmed deterministic — no LLM call for the actual fix, uses `sentence-transformers` for embedding search only).

- [ ] **Step 1: Read the full source file, confirm no coordinator dependency beyond type imports**

Run: `grep -n "SubAgent\|AgentContext\|agent_registry\|claude_code_bridge" crackerjack/agents/semantic_agent.py`

Note every hit — these need to be removed or converted to explicit parameters during extraction. Also identify every method doing real `VectorStore`/embedding-search work versus `SubAgent`/coordinator plumbing.

- [ ] **Step 2:** Run `find tests -iname "*semantic*agent*"` and read what's found. Identify which test cases exercise the `VectorStore`/embedding-search logic (keep) versus dispatch behavior (drop).
- [ ] **Step 3:** Port the kept test cases into `tests/fixers/test_semantic.py`, updating imports from `crackerjack.agents.semantic_agent` to `crackerjack.fixers.semantic` and call sites to match Step 1's plain-function form.
- [ ] **Step 4:** Run `pytest tests/fixers/test_semantic.py -v`. Expected: FAIL.
- [ ] **Step 5:** Create `crackerjack/fixers/semantic.py` with the ported `VectorStore`/embedding-search logic as module-level functions, `self.context` references converted to explicit parameters. Import only `crackerjack.models.issues` types (and `sentence-transformers`/whatever embedding library the source file already depends on — no new dependency).
- [ ] **Step 6:** Run `pytest tests/fixers/test_semantic.py -v`. Expected: PASS.
- [ ] **Step 7:** Run `grep -n "crackerjack.agents\|crackerjack.ai_fix\|crackerjack.intelligence\|crackerjack.memory" crackerjack/fixers/semantic.py`. Expected: no output.
- [ ] **Step 8: Commit**

```bash
git add crackerjack/fixers/semantic.py tests/fixers/test_semantic.py
git commit -m "refactor(fixers): extract semantic_agent VectorStore logic as plain functions"
```

---

### Task 21: Scope `planning_agent.py` — decide what's reusable vs. redundant

**Files:**
- Read: `crackerjack/agents/planning_agent.py` (3,349 lines — largest file in the whole package)

**Interfaces:** N/A — this task produces a decision and a short written note, not code, consumed by Task 22.

This file needs deliberate scrutiny, not a mechanical port (per the design spec's explicit flag). It builds `ChangeSpec`/`FixPlan` objects mechanically (confirmed: uses `ast`, a `SafeRefurbFixer` service, no `claude_code_bridge` import) but its *role* — deciding what to fix and building an execution plan — overlaps with what the external loop (separate plan) now does when it collects `crackerjack run --json` output and decides what to dispatch.

- [ ] **Step 1: Read the full file**

- [ ] **Step 2: Classify each major section**

For each top-level class/function group in the file, classify as:
- **(a) Genuinely reusable fix-plan construction** — e.g., if there's logic that turns "here's a refurb violation" into "here's the exact mechanical edit to make," that's the same kind of thing as the other 15 extracted files and should move to `crackerjack/fixers/planning.py` following the Task 4 pattern.
- **(b) Orchestration-adjacent decision logic** — e.g., anything that decides *which* fixer to run, batches issues, or sequences multi-step repairs across issue types. This duplicates the external loop's role and should be dropped, not ported.

Write the classification as a short markdown list (which methods/classes are (a), which are (b)) — this becomes the input to Task 22's extraction steps, so it must name specific methods, not describe the split abstractly.

- [ ] **Step 3: Get a second read before deleting anything**

Given this is the single largest, most ambiguous file in the plan, do not proceed to Task 22 on a single read. Re-read the (b)-classified sections once more specifically looking for any mechanical logic embedded inside them that would be lost if the whole method is dropped — pull that logic out into the (a) list if found.

---

### Task 22: Extract the (a)-classified portion of `planning_agent.py` → `crackerjack/fixers/planning.py`

**Files:**
- Create: `crackerjack/fixers/planning.py` (only if Task 21 found genuinely reusable (a) content — if Task 21's classification finds nothing qualifies as (a), skip this task and note that in the Task 21 write-up instead)
- Test: `tests/fixers/test_planning.py`

- [ ] **Step 1:** Using Task 21's written classification, list the specific (a)-classified methods/classes to port — do not re-derive the classification, use the decision already recorded.
- [ ] **Step 2:** Run `find tests -iname "*planning*agent*"` and read what's found. Identify which test cases exercise the (a)-classified methods (keep) versus (b)-classified orchestration logic (drop).
- [ ] **Step 3:** Port the kept test cases into `tests/fixers/test_planning.py`, updating imports from `crackerjack.agents.planning_agent` to `crackerjack.fixers.planning` and call sites to the new plain-function form (methods converted from `self`/`self.context` to explicit parameters).
- [ ] **Step 4:** Run `pytest tests/fixers/test_planning.py -v`. Expected: FAIL (`crackerjack.fixers.planning` doesn't exist yet).
- [ ] **Step 5:** Create `crackerjack/fixers/planning.py` containing only the (a)-classified methods, ported as module-level functions with `self`/`self.context` converted to explicit parameters (using the `SafeRefurbFixer` service and `ast`/`ChangeSpec`/`FixPlan` construction already confirmed present in the source). Import only `crackerjack.models.issues` types — no import of anything from `crackerjack.agents`.
- [ ] **Step 6:** Run `pytest tests/fixers/test_planning.py -v`. Expected: PASS.
- [ ] **Step 7:** Run `grep -n "crackerjack.agents\|crackerjack.ai_fix\|crackerjack.intelligence\|crackerjack.memory" crackerjack/fixers/planning.py`. Expected: no output.
- [ ] **Step 8: Commit**

```bash
git add crackerjack/fixers/planning.py tests/fixers/test_planning.py
git commit -m "refactor(fixers): extract genuinely reusable planning_agent fix-plan logic, drop orchestration-adjacent decision code"
```

(If Task 21's classification found nothing qualifying as (a), skip Steps 1-8 entirely and note that outcome in Task 21's write-up instead — do not create an empty module.)

---

### Task 22a: Fix dropped `cwd` pinning across all extracted fixers' `_run_command` helpers

**Files:**
- Modify: every `crackerjack/fixers/*.py` file created by Tasks 4-22 that defines its own subprocess-invoking helper (confirmed present in at least `refactoring.py`, `security.py`, `documentation.py`, `dry.py`, `formatting.py` as of Tasks 4/6/7/9/10 — re-derive the authoritative current list in Step 1 rather than trusting this list, since Tasks 11-22 ran after this task was written and may have introduced more instances of the same pattern)
- Test: extend each affected file's existing test file with one new test covering the project-wide (no explicit file path) invocation path

**Interfaces:** N/A — this is a targeted bug fix across existing modules, not a new interface.

**Background:** During Task 10's review, an independent reviewer found that every extracted fixer's `_run_command`-style helper dropped the original `SubAgent.run_command`'s `cwd=self.context.project_path` pinning (`crackerjack/agents/base.py:307-334`). The extracted functions run subprocesses (`ruff`, `codespell`, whitespace-fixer scripts, etc.) against the calling process's ambient working directory instead of the actual project root. This is dormant today — every real caller in the current codebase passes a specific `issue.file_path`, never triggers the project-wide `target = ["."]` branch — but if that branch is ever exercised (e.g., a future caller, or the external ai-fix-loop's fix-dispatch step operating without a specific file target), the subprocess would silently operate on the wrong directory while any co-located mtime-based "what changed" scan (which correctly threads `project_path` through separately) would look in a different place than the subprocess actually touched. The user's decision (recorded 2026-08-07): fix this once, consolidated, across all affected files in a single task after all extractions are done, rather than patching files one at a time or reopening already-reviewed tasks.

- [ ] **Step 1: Derive the authoritative current list of affected files**

Run: `grep -rln "def _run_command" crackerjack/fixers/*.py`

For each match, read the function and confirm whether it accepts a `cwd`/`project_path`/`project_root` parameter already (some later extraction tasks, e.g. Task 7's `documentation.py`, may have already threaded through a project-root parameter for unrelated reasons per that task's own precedent — check whether it's already passed to the subprocess call specifically, not just accepted as a parameter used elsewhere). Build a checklist of files that are genuinely missing `cwd` pinning on their subprocess calls — do not assume the list in this task's Background section is complete or unchanged.

- [ ] **Step 2: For each affected file, add a `project_root: Path` (or equivalently-named) parameter to the subprocess-invoking helper, threaded through to every caller**

The exact signature change depends on each file's existing structure — follow the pattern already established in `documentation.py` (Task 7), which threads `project_root: Path` through its call chain for a different but structurally identical reason (a load-bearing `AgentContext`-derived value). Every function in the call chain between the fixer's public entry point and the subprocess invocation needs the parameter added and passed through — do not silently default it to `Path.cwd()` inside the low-level helper, since that reintroduces the exact ambiguity being fixed; the caller must supply it explicitly.

- [ ] **Step 3: Pass `cwd=project_root` (or the file's equivalent parameter name) to every subprocess invocation in the affected helper**

This should be the single-line fix per file once Step 2's plumbing is in place — e.g. `subprocess.run(cmd, cwd=project_root, ...)` matching the original `SubAgent.run_command`'s behavior.

- [ ] **Step 4: Add one regression test per affected file covering the project-wide invocation path**

For each file, write a test that invokes the fixer's project-wide path (no specific file target — the `target = ["."]`-equivalent branch) against a `tmp_path`-based fake project structure with a marker file, and asserts the subprocess actually ran with `cwd` set to that `tmp_path` (e.g. via `monkeypatch`-capturing the `subprocess.run` call's `cwd` kwarg, or by having the subprocess act on a file only present under `tmp_path` and confirming it was found/modified there). This is the test coverage gap the original review specifically flagged as missing.

- [ ] **Step 5: Run each affected file's full test suite**

Run: `uv run pytest tests/fixers/test_refactoring.py tests/fixers/test_security.py tests/fixers/test_documentation.py tests/fixers/test_dry.py tests/fixers/test_formatting.py -v` (extend this command with any additional files Step 1 found)
Expected: all PASS, including the new regression tests from Step 4.

- [ ] **Step 6: Run the full `tests/fixers/` suite to confirm no cross-file regression**

Run: `uv run pytest tests/fixers/ -v`
Expected: PASS (matches or exceeds the aggregate pass count from the last extraction task's report).

- [ ] **Step 7: Commit**

```bash
git add crackerjack/fixers/
git commit -m "fix(fixers): thread project_root cwd pinning through all extracted _run_command helpers"
```

---

### Task 23: Delete `claude_code_bridge.py` and `enhanced_proactive_agent.py`

**Files:**
- Delete: `crackerjack/agents/claude_code_bridge.py`, `crackerjack/agents/enhanced_proactive_agent.py`
- Delete corresponding tests: `find tests -iname "*claude_code_bridge*" -o -iname "*enhanced_proactive*"`

**Interfaces:** N/A — pure deletion, no replacement (per spec Non-goals: this is exactly what the external loop's agentic session replaces natively).

- [ ] **Step 1: Confirm nothing outside these two files imports from them, other than known coordinator files already slated for deletion**

Run: `grep -rln "claude_code_bridge\|ClaudeCodeBridge\|enhanced_proactive_agent\|EnhancedProactiveAgent" crackerjack/ --include="*.py" | grep -v __pycache__`

Cross-check every result against the deletion list in this plan's File Structure section — every hit must be a file also being deleted in this plan (Tasks 23-30). If something outside that list depends on these, stop and investigate before deleting.

- [ ] **Step 2: Delete the files and their tests**

```bash
git rm crackerjack/agents/claude_code_bridge.py crackerjack/agents/enhanced_proactive_agent.py
# git rm the test files found in Step 1's search, using their actual paths
```

- [ ] **Step 3: Commit**

```bash
git commit -m "refactor(agents): delete claude_code_bridge + enhanced_proactive_agent (pure LLM-dispatch plumbing, replaced by external loop)"
```

---

### Task 24: Rewrite the 6 behavioral call sites off deleted orchestration

**Files:**
- Modify: `crackerjack/core/proactive_workflow.py`
- Modify: `crackerjack/core/tier3_factory.py`
- Modify: `crackerjack/documentation/dual_output_generator.py`
- Modify: `crackerjack/services/batch_processor.py`
- Modify: `crackerjack/services/agent_delegator.py`
- Modify: `crackerjack/mcp/tools/skill_tools.py`
- Test: run each file's existing test suite before and after.

**Interfaces:**
- Consumes: `crackerjack.models.issues` types (Task 2) where these files need `Issue`/`IssueType`/etc.
- Produces: N/A — each of these files loses its AI-dispatch code path; none is expected to gain a new one in this plan.

- [ ] **Step 1: `core/proactive_workflow.py`**

Read the file. It currently does `self._architect_agent_coordinator = AgentCoordinator(...)`. Remove this instantiation and whatever code path depends on it firing. Run its existing tests before (`find tests -iname "*proactive_workflow*"`) and after to confirm the surrounding non-AI behavior (if any) still works. Commit: `refactor(core): remove AgentCoordinator dependency from proactive_workflow`.

- [ ] **Step 2: `core/tier3_factory.py`**

Read the file (233 lines — the whole thing is a fixing-engine factory: `IterativeFixAgent`, `LocalClaudeSubprocess`, `MahavishnuPool`, `InMemorySkillStore`). Confirm whether anything outside this plan's deletion list still calls into `tier3_factory`. If not (expected, since it only exists to support the deleted `ai_fix`/`intelligence` machinery), delete the file entirely instead of editing it — check with `grep -rln "tier3_factory" crackerjack/ --include="*.py" | grep -v __pycache__` first. Commit: `refactor(core): delete tier3_factory (only supported deleted ai_fix/intelligence machinery)`.

- [ ] **Step 3: `documentation/dual_output_generator.py`**

Read the file. Remove the `AgentCoordinator` import and whatever code path uses it. Run its existing tests (`find tests -iname "*dual_output*"`) before and after. Commit: `refactor(documentation): remove AgentCoordinator dependency from dual_output_generator`.

- [ ] **Step 4: `services/batch_processor.py`**

Read the file. Remove the `ISSUE_TYPE_TO_AGENTS` import from `agents.coordinator` and whatever dispatch logic used that table. Run its existing tests (`find tests -iname "*batch_processor*"`) before and after. Commit: `refactor(services): remove ISSUE_TYPE_TO_AGENTS dispatch-table dependency from batch_processor`.

- [ ] **Step 5: `services/agent_delegator.py`**

Read the file. This one's entire purpose (per its name) is likely AI-agent delegation — confirm with a full read whether the file should be edited or deleted wholesale, same check as Task 24 Step 2. Run `grep -rln "agent_delegator\|AgentDelegator" crackerjack/ --include="*.py" | grep -v __pycache__` to find callers before deciding. Commit: `refactor(services): remove/delete agent_delegator AgentCoordinator dependency` (adjust message to "delete" if the whole file goes).

- [ ] **Step 6: `mcp/tools/skill_tools.py`**

Read the file. It constructs `AgentContext` directly and drives an `agent_skills` registry (`AgentSkillRegistry` from the now-deleted `crackerjack/skills/` package). This MCP tool surface needs the most care of the six — per the DevOps review, failures here surface at MCP request time, not at import/build time. Determine whether the tools this file exposes (list/search/stats on agent skills) have any meaning once there are no more agents to register — if not, remove the tool registrations entirely rather than leaving them silently broken. Cross-reference `crackerjack/mcp/tools/progress_tools.py` and `server_core.py`'s `register_progress_tools` for the same question, per the DevOps review's flag that progress tracking may also depend on the deleted job/iteration state. Commit: `refactor(mcp): remove agent-skills tool registrations (skills/ package deleted)`.

- [ ] **Step 7: Full-suite check after all 6 rewrites**

Run: `pytest tests/ -x -q 2>&1 | tail -40`
Expected: no `ImportError`/`ModuleNotFoundError` referencing `crackerjack.agents.coordinator`, `crackerjack.agents.claude_code_bridge`, `crackerjack.skills`, `crackerjack.ai_fix.tier3_factory`, or similar. Fix any that appear before moving to Task 25.

**Note (added 2026-08-08, mid-execution)**: Task 24's Step 2 escalated `tier3_factory.py` — it turned out to be wired into a live, currently-tested code path (`autofix_coordinator.py`'s `_apply_ai_agent_fixes_v2`), not dormant. Tracing that further revealed `autofix_coordinator.py`'s AI-fix control flow (`_apply_fast_stage_fixes`/`_apply_comprehensive_stage_fixes`, gated on `AI_AGENT` env var) is the actual live `--ai-fix` invocation path — it constructs `AnalysisCoordinator`/`FixerCoordinator`/`ValidationCoordinator` from `crackerjack/agents/` and drives tier-3's `IterativeFixAgent` (`LocalClaudeSubprocess`/`MahavishnuPool`/`SessionBuddySkillStore` — an LLM-dispatch + skill-learning loop never named in the original 4-subsystem spec inventory), all woven into the same methods that handle the coordinator's normal non-AI fallback. Task 28 (originally scoped as a light "remove AI-specific methods" pass, and originally scheduled *after* Task 27's bulk deletion of `agents/` — which was backwards, since `autofix_coordinator.py`'s live imports from `agents/` must be gone *before* `agents/` can be safely deleted) is **superseded by Tasks 24a and 24b below**, inserted here per user decision. Do not run Task 28 as originally written.

---

### Task 24a: Scope `autofix_coordinator.py` + `phase_coordinator.py` + `tier3_factory.py` + `iterative_fix_agent.py` — decide AI-dispatch vs. deterministic-fallback

**Files:**
- Read: `crackerjack/core/autofix_coordinator.py` (5,425 lines, ~226 methods, AI and non-AI interleaved in one class body)
- Read: `crackerjack/core/phase_coordinator.py` (2,242 lines, partially AI-specific — confirmed eager `from crackerjack.agents.base import FixResult` at module level, plus `AgentCoordinator`/`AgentContext`/`AgentTracker` imports)
- Read: `crackerjack/core/tier3_factory.py` (234 lines — confirmed live, wired into `autofix_coordinator.py._attach_tier3_agent`, called unconditionally from `_apply_ai_agent_fixes_v2` whenever there are fixable issues)
- Read: `crackerjack/agents/iterative_fix_agent.py` (496 lines — `IterativeFixAgent`, `LocalClaudeSubprocess`, `MahavishnuPool`, `SessionBuddySkillStore`, `InMemorySkillStore`; the class `tier3_factory.py` builds instances from)

**Interfaces:** N/A — this task produces a decision and a written classification, not code, consumed by Task 24b. Same shape as Task 21's `planning_agent.py` scoping task.

This is the highest-risk, most consequential scoping task in the whole plan: `autofix_coordinator.py`/`phase_coordinator.py` are **not** scheduled for deletion (unlike every other file this plan has touched so far) — they're live, central coordinators that also handle non-AI hook orchestration (formatting, testing phases). Getting the AI-dispatch/deterministic-fallback boundary wrong here risks either leaving dead AI-orchestration code behind, or breaking real, currently-passing non-AI behavior.

- [ ] **Step 1: Read all four files in full.**

- [ ] **Step 2: Trace the live `--ai-fix` control flow precisely.**

Confirmed starting point: `_apply_fast_stage_fixes`/`_apply_comprehensive_stage_fixes` check `os.environ.get("AI_AGENT") == "1"`. When true, they call `_apply_ai_agent_fixes` → `_apply_ai_agent_fixes_v2`, which constructs `AnalysisCoordinator`/`FixerCoordinator`/`ValidationCoordinator` (from `crackerjack/agents/`, all scheduled for deletion in Task 27) and, via `_attach_tier3_agent`, `tier3_factory.build_iterative_agent()` (tier-3). When `AI_AGENT` is unset, the same two methods fall back to `_execute_fast_fixes()` — the deterministic, non-AI path. Map every method reachable from `_apply_ai_agent_fixes_v2`/`_run_v2_ai_fix_iteration_loop` and every method reachable only from the `AI_AGENT`-unset fallback branch.

- [ ] **Step 3: Classify every top-level method in all four files** (matching Task 21's classification format):
  - **(a) AI-dispatch, drop entirely** — anything only reachable through the `AI_AGENT=1` branch: `_apply_ai_agent_fixes`, `_apply_ai_agent_fixes_v2`, `_attach_tier3_agent`, `_run_v2_ai_fix_iteration_loop`, and their exclusive callees; all of `tier3_factory.py`; all of `iterative_fix_agent.py`; `phase_coordinator.py`'s `AgentCoordinator`/`AgentTracker`-touching methods.
  - **(b) Deterministic/non-AI, keep as the unconditional path** — `_execute_fast_fixes` and everything the non-`AI_AGENT` fallback already reaches; all genuine tool-orchestration logic (ruff/pytest/hook-suite sequencing) unrelated to AI fixing.
  - **(c) Shared/ambiguous** — methods called from both branches (e.g. `_collect_fixable_issues`, `_build_ai_fix_scope_files`) — these stay, but any AI-specific parameter/branch inside them gets simplified away in Task 24b.
  Write this as a named-method checklist (not an abstract description) — this becomes Task 24b's exact worklist, same discipline as Task 21.

- [ ] **Step 4: Second read.** Re-read every (a)-classified method once more, specifically hunting for embedded deterministic logic that would be lost if dropped wholesale (matching Task 21's Step 3/4 pattern) — e.g., confirm `_apply_ai_agent_fixes_v2`'s deterministic prepasses (type-tool fix, zuban fix, refurb prepass, `_execute_fast_fixes()` call before AI analysis even starts) are NOT AI-specific and must be preserved/promoted into the unconditional path, not dropped along with the AI dispatch that currently wraps them.

- [ ] **Step 5: Write the classification** to a report file, following Task 21's format (Summary, per-file classification, mechanical logic recovered from (a) sections, uncertain items, recommendation for Task 24b).

---

### Task 24b: Execute Task 24a's classification — remove the `AI_AGENT`-gated AI-fix control flow

**Files:**
- Modify: `crackerjack/core/autofix_coordinator.py`
- Modify: `crackerjack/core/phase_coordinator.py`
- Delete: `crackerjack/core/tier3_factory.py`
- Delete: `crackerjack/agents/iterative_fix_agent.py` (and its corresponding test file — find with `find tests -iname "*iterative_fix_agent*" -o -iname "*tier3*"`)
- Test: run each file's existing test suite before and after every removal batch, matching Task 28's originally-specified incremental discipline.

**Interfaces:** N/A — removes dead/doomed code; whatever public interface these files expose for non-AI hook orchestration must remain intact and passing its existing tests throughout.

- [ ] **Step 1:** Using Task 24a's written classification, remove the (a)-classified methods in small batches (5-10 at a time), testing after each batch — same batching discipline as Task 28's original Step 2. Locate exact test paths with `find tests -iname "*autofix_coordinator*"` / `find tests -iname "*phase_coordinator*"`. Commit after each clean batch.

- [ ] **Step 2:** For every (c)-classified shared method, simplify away the now-unreachable `AI_AGENT`-gated branch, leaving only the deterministic path — per Task 24a's Step 4 finding, make sure any deterministic prepass logic currently nested inside `_apply_ai_agent_fixes_v2` gets preserved/promoted, not deleted along with its AI wrapper.

- [ ] **Step 3:** Remove the `os.environ.get("AI_AGENT") == "1"` branches in `_apply_fast_stage_fixes`/`_apply_comprehensive_stage_fixes` (and any other `AI_AGENT` check found), leaving the deterministic fallback as the only path.

- [ ] **Step 4:** Delete `tier3_factory.py` and `crackerjack/agents/iterative_fix_agent.py` wholesale, plus their test files (`tests/core/test_tier3_factory.py`, and whatever `iterative_fix_agent.py`'s test file is — confirm with `find`).

- [ ] **Step 5:** Verify the `--json` schema (Task 3) still matches: `pytest tests/unit/models/test_issues.py::test_run_result_matches_golden_schema -v`. Expected: PASS.

- [ ] **Step 6: Final full-suite run for both coordinator files.**

Run: `pytest tests/unit/core/ -v`
Expected: PASS, no AI-related imports remain in either file (`grep -n "crackerjack.agents\|crackerjack.ai_fix\|crackerjack.intelligence\|crackerjack.memory\|crackerjack.skills\|tier3_factory\|AI_AGENT" crackerjack/core/autofix_coordinator.py crackerjack/core/phase_coordinator.py` returns nothing beyond inert comments).

- [ ] **Step 7: Commit** (final batch, after Steps 3-6):
```bash
git commit -m "refactor(core): remove AI_AGENT-gated ai-fix control flow from autofix_coordinator/phase_coordinator, delete tier3_factory + iterative_fix_agent"
```

---

### Task 25: Delete `SubAgent`, `agent_registry`, and orchestration protocols

**Files:**
- Modify: `crackerjack/agents/base.py` — remove `SubAgent`, `AgentContext`, `AgentRegistry`, module-level `agent_registry` (the four vocabulary types were already copied out in Task 2 — this task removes the *rest* of the file's contents; the file itself gets deleted in Task 27 along with the rest of `agents/`)
- Modify: `crackerjack/models/protocols.py` — remove `AgentCoordinatorProtocol`, `AgentTrackerProtocol`, `AgentRegistryProtocol`

**Interfaces:** N/A — pure deletion.

- [ ] **Step 1: Confirm nothing outside the deletion list implements or consumes these protocols**

Run: `grep -rln "AgentCoordinatorProtocol\|AgentTrackerProtocol\|AgentRegistryProtocol" crackerjack/ --include="*.py" | grep -v __pycache__`

Every result must be a file already in this plan's deletion list. If not, stop and investigate.

- [ ] **Step 2: Remove the three protocols from `models/protocols.py`**

- [ ] **Step 3: Run the protocol module's tests**

Run: `pytest tests/unit/models/test_protocols.py -v` (or wherever protocol tests live — locate with `find tests -iname "*protocol*"`)
Expected: PASS, no references to the removed protocols remain in the test file (remove any that do).

- [ ] **Step 4: Commit**

```bash
git add crackerjack/models/protocols.py
git commit -m "refactor(models): remove orchestration protocols (AgentCoordinator/Tracker/Registry) — no longer implemented by anything"
```

---

### Task 26: Delete `crackerjack/ai_fix/`, `crackerjack/intelligence/`, `crackerjack/memory/`, `crackerjack/skills/`

**Files:**
- Delete: all four packages in their entirety
- Delete corresponding tests: `tests/test_ai_fix_*.py`, `tests/integration/test_ai_fix_*.py`, `tests/unit/ai_fix/`, `tests/regression/test_check_yaml_ai_fix_regression.py`, `tests/unit/core/test_ai_fix_*.py`, and equivalents for `intelligence/`, `memory/`, `skills/` (locate all with `find tests -iname "*intelligence*" -o -iname "*memory*" -o -iname "*skills*" -o -iname "*ai_fix*"`)

**Interfaces:** N/A — pure deletion.

- [ ] **Step 1: Final cross-check for external dependents**

Run: `grep -rln "from crackerjack.ai_fix\|from crackerjack.intelligence\|from crackerjack.memory\|from crackerjack.skills\|import crackerjack.ai_fix\|import crackerjack.intelligence\|import crackerjack.memory\|import crackerjack.skills" crackerjack/ --include="*.py" | grep -v __pycache__`

Every result must be inside one of the four packages being deleted, or already handled in Task 24 (the 6 behavioral call sites). If anything else shows up, stop and investigate before deleting.

- [ ] **Step 2: Delete the four packages**

```bash
git rm -r crackerjack/ai_fix crackerjack/intelligence crackerjack/memory crackerjack/skills
```

- [ ] **Step 3: Delete their tests**

```bash
# using the actual file list found via the `find` command above
git rm -r <matched test files/directories>
```

- [ ] **Step 4: Full-suite import check**

Run: `python -c "import crackerjack.__main__"` (or equivalent smoke import)
Expected: no `ImportError`.

Run: `pytest tests/ -x -q --collect-only 2>&1 | tail -30`
Expected: no collection errors referencing the deleted packages.

- [ ] **Step 5: Commit**

```bash
git commit -m "refactor: delete ai_fix/, intelligence/, memory/, skills/ (unstable orchestration/learning subsystems, superseded by external loop)"
```

---

### Task 27: Delete the remainder of `crackerjack/agents/`

**Files:**
- Delete: `crackerjack/agents/` in its entirety (everything not already moved to `crackerjack/fixers/` in Tasks 4-20, 22) — includes `coordinator.py`, `enhanced_coordinator.py`, `fixer_coordinator.py`, `analysis_coordinator.py`, `validation_coordinator.py`, `parallel_dispatcher.py`, `tracker.py`, `base.py`, `error_middleware.py`, `performance_tracker.py`, and any remaining agent files not covered above (confirm the full remaining file list with `ls crackerjack/agents/*.py` right before this task — it should only contain coordination/dispatch plumbing at this point).
- Delete corresponding tests: `tests/agents/` remainder not already moved to `tests/fixers/`.

**Interfaces:** N/A — pure deletion.

- [ ] **Step 1: List what's left**

Run: `ls crackerjack/agents/*.py crackerjack/agents/**/*.py 2>/dev/null`

Confirm every remaining file is coordination/dispatch plumbing (not a fixer that should have been extracted in Tasks 4-22). If something unexpected remains, stop and classify it (extract or delete) before proceeding — do not delete unclassified code.

- [ ] **Step 2: Final cross-check for external dependents**

Run: `grep -rln "from crackerjack.agents\|import crackerjack.agents" crackerjack/ --include="*.py" | grep -v __pycache__ | grep -v "^crackerjack/agents/"`

Every result must already be handled by Task 24's rewrites **or Task 24b** (added 2026-08-08: `autofix_coordinator.py`/`phase_coordinator.py`'s imports of `AnalysisCoordinator`/`FixerCoordinator`/`ValidationCoordinator`/`AgentTracker`/etc. are handled by Task 24b, not Task 24 — confirm Task 24b has run before proceeding). If anything is still unhandled, go back and finish Task 24/24b for that file first.

- [ ] **Step 3: Delete**

```bash
git rm -r crackerjack/agents
```

- [ ] **Step 4: Delete remaining tests**

```bash
git rm -r tests/agents  # only if anything remains after Tasks 4-22 moved their portions out
```

- [ ] **Step 5: Full-suite check**

Run: `pytest tests/ -x -q --collect-only 2>&1 | tail -30`
Expected: no collection errors.

- [ ] **Step 6: Commit**

```bash
git commit -m "refactor: delete remainder of agents/ (coordination/dispatch plumbing — deterministic fixers already extracted to crackerjack/fixers/)"
```

---

### Task 28 (SUPERSEDED — do not run): Remove AI-specific methods from `core/autofix_coordinator.py` and `core/phase_coordinator.py`

**Status: superseded by Tasks 24a and 24b (inserted 2026-08-08).** This task was originally scheduled *after* Task 27's bulk deletion of `crackerjack/agents/` — backwards, since `autofix_coordinator.py` has live, eager imports from `crackerjack/agents/` (`AnalysisCoordinator`, `FixerCoordinator`, `ValidationCoordinator` via `_apply_ai_agent_fixes_v2`) that must be removed *before* `agents/` can be safely deleted. Tracing the actual scope during Task 24's execution also revealed this isn't a simple "remove AI-specific methods" pass — the AI-fix control flow (gated on the `AI_AGENT` env var) is woven into the same methods that handle the coordinator's normal non-AI fallback, and additionally drives a previously-unscoped subsystem (`tier3_factory.py`/`iterative_fix_agent.py` — `IterativeFixAgent`/`LocalClaudeSubprocess`/`MahavishnuPool`/`SessionBuddySkillStore`, an LLM-dispatch + skill-learning loop never named in the original 4-subsystem spec inventory). Tasks 24a/24b give this the full scope-then-execute treatment Task 21/22 used for `planning_agent.py`. The section below is preserved for historical reference only — **do not execute it**.

<details>
<summary>Original Task 28 text (superseded, not executed)</summary>

### Task 28 (ORIGINAL, SUPERSEDED): Remove AI-specific methods from `core/autofix_coordinator.py` and `core/phase_coordinator.py`

**Files:**
- Modify: `crackerjack/core/autofix_coordinator.py` (5,425 lines, ~226 methods, AI and non-AI interleaved in one class body)
- Modify: `crackerjack/core/phase_coordinator.py` (2,242 lines, partially AI-specific)
- Test: run each file's existing test suite before and after every removal batch, not just at the end.

**Interfaces:** N/A — this task removes dead code; whatever public interface these files expose for non-AI hook orchestration (formatting, testing phases) must remain intact and passing its existing tests throughout.

This is flagged in the design spec as the highest-risk task in the plan — the 226 methods are not separated by file boundary, so this must be done as a careful, incremental, test-verified pass, not a bulk deletion.

- [ ] **Step 1: Build the method inventory**

Run: `grep -n "    def \|    async def " crackerjack/core/autofix_coordinator.py`

For every method, classify as AI-specific (references `agents.`, `ai_fix.`, `intelligence.`, `memory.`, fixer dispatch, prompt construction, skill/promotion logic) or non-AI (tool orchestration for ruff/pytest/etc. unrelated to fixing). Write this classification down as a checklist before removing anything — this is the same discipline as Task 21's planning_agent.py classification, applied to a bigger, more tangled file.

- [ ] **Step 2: Remove AI-specific methods in small batches, testing after each batch**

For each batch of 5-10 AI-specific methods: remove them, then run `pytest tests/unit/core/test_autofix_coordinator.py -v` (locate exact path with `find tests -iname "*autofix_coordinator*"`). If a non-AI method's test breaks, that method was miscategorized in Step 1 — revert just that removal and re-classify. Commit after each clean batch: `refactor(core): remove AI-specific methods from autofix_coordinator (batch N)`.

- [ ] **Step 3: Repeat Steps 1-2 for `core/phase_coordinator.py`**

Same process, same batching discipline, testing against `find tests -iname "*phase_coordinator*"`. Commit messages: `refactor(core): remove AI-specific methods from phase_coordinator (batch N)`.

- [ ] **Step 4: Verify the `--json` schema (Task 3) still matches**

Run: `pytest tests/unit/models/test_issues.py::test_run_result_matches_golden_schema -v`
Expected: PASS. If this breaks, a removed method was part of the JSON serialization path — restore it or update `CrackerjackRunResult`/the golden fixture deliberately (not accidentally).

- [ ] **Step 5: Final full-suite run for both files**

Run: `pytest tests/unit/core/ -v`
Expected: PASS, no AI-related imports remain in either file (`grep -n "crackerjack.agents\|crackerjack.ai_fix\|crackerjack.intelligence\|crackerjack.memory\|crackerjack.skills" crackerjack/core/autofix_coordinator.py crackerjack/core/phase_coordinator.py` returns nothing).

</details>

---

### Task 29: Remove the `--ai-fix` CLI flag

**Files:**
- Modify: `crackerjack/__main__.py`

**Interfaces:** N/A — removes a CLI option.

- [ ] **Step 1: Locate every reference**

Run: `grep -n "ai_fix\|ai-fix\|setup_ai_agent_env\|max_iterations" crackerjack/__main__.py`

- [ ] **Step 2: Determine whether `max_iterations` is AI-fix-exclusive**

Read the surrounding code for each `max_iterations` hit found in Step 1. If it's only ever consumed by the now-deleted AI-fix loop, remove it alongside the flag. If it's shared by other retry logic (e.g., generic hook-retry unrelated to AI), keep it and only remove the AI-specific wiring.

- [ ] **Step 3: Remove `CLI_OPTIONS["ai_fix"]`, the `ai_fix` parameter, and `setup_ai_agent_env` call**

- [ ] **Step 4: Run the CLI's existing tests**

Run: `find tests -iname "*__main__*" -o -iname "*cli*"` then `pytest <matched files> -v`
Expected: PASS, and `python -m crackerjack run --help` no longer lists `--ai-fix`.

- [ ] **Step 5: Commit**

```bash
git add crackerjack/__main__.py
git commit -m "refactor(cli): remove --ai-fix flag (orchestration it drove has been removed)"
```

---

### Task 30: Recompute the coverage ratchet baseline

**Files:**
- Modify: whatever config file holds the ratchet baseline (locate with `grep -rn "coverage" pyproject.toml crackerjack/config/ 2>/dev/null | grep -i ratchet`, or check `docs/reference/COVERAGE_POLICY.md` referenced in CLAUDE.md for the mechanism)

**Interfaces:** N/A — configuration update.

- [ ] **Step 1: Read `docs/reference/COVERAGE_POLICY.md` to confirm the exact ratchet mechanism**

- [ ] **Step 2: Run the full suite with coverage after all deletions**

Run: `python -m crackerjack run --run-tests`

- [ ] **Step 3: Compare the resulting coverage percentage against the Task 1 baseline**

Both the numerator (lines covered) and denominator (total lines) shrank — the percentage could move either direction. Do not assume it improved; check the actual number.

- [ ] **Step 4: Update the ratchet baseline deliberately, with a comment/commit message explaining the one-time step change**

```bash
git add <ratchet config file>
git commit -m "chore(coverage): recompute ratchet baseline after ai-fix removal (~43K lines + tests deleted)"
```

---

### Task 31: Grep session-buddy for coupling to deleted code

**Files:** None in this repo — this task investigates `/Users/les/Projects/session-buddy` (an additional working directory available in this session).

**Interfaces:** N/A — investigation task; produces a decision on whether this plan's scope needs to expand.

- [ ] **Step 1: Search session-buddy for references to the deleted packages/APIs**

Run: `grep -rln "crackerjack.agents\|crackerjack.ai_fix\|crackerjack.intelligence\|crackerjack.memory\|crackerjack.skills\|agent_skills\|AgentSkillRegistry" /Users/les/Projects/session-buddy --include="*.py" 2>/dev/null`

- [ ] **Step 2: If nothing found, note it and move on**

If the search is empty, the skills-tracking integration CLAUDE.md describes must be looser than direct import coupling (e.g., it consumes crackerjack's MCP tool output at runtime, not a Python import) — no code change needed in session-buddy for this plan.

- [ ] **Step 3: If something is found, stop and scope a follow-up**

Do not silently patch session-buddy as part of this plan — per this plan's Global Constraints and the design spec's Risks section, a real cross-repo dependency here means this plan's scope needs a deliberate expansion decision, not an ad-hoc fix. Report exactly what was found to the user before proceeding further in this plan.

---

### Task 32: Mark the eight superseded specs

**Files:**
- Modify frontmatter (`superseded_by` field) in:
  - `docs/superpowers/specs/2026-07-07-ai-fix-improvement-design.md`
  - `docs/superpowers/specs/2026-07-08-fix-sandbox-integration-design.md`
  - `docs/superpowers/specs/2026-07-10-libcst-surgeon-extract-method-fallback-design.md`
  - `docs/superpowers/specs/2026-07-10-output-validator-traceback-details-design.md`
  - `docs/superpowers/specs/2026-07-10-validation-coordinator-serialization-design.md`
  - `docs/superpowers/specs/2026-07-11-ai-fix-e501-post-processor-design.md`
  - `docs/superpowers/specs/2026-07-11-ai-fix-no-op-circuit-breaker-design.md`
  - `docs/superpowers/specs/2026-07-11-ai-fix-regen-timeout-design.md`

**Interfaces:** N/A — documentation update.

- [ ] **Step 1: For each file, change `superseded_by: null` to `superseded_by: 2026-08-06-ai-fix-removal-external-loop-design.md`**

- [ ] **Step 2: Commit**

```bash
git add docs/superpowers/specs/
git commit -m "docs(superpowers): mark 8 ai-fix specs as superseded by the removal design"
```

---

### Task 33: Post-delete MCP server verification

**Files:** None modified — verification task.

**Interfaces:** N/A.

- [ ] **Step 1: Start the MCP server**

Run: `python -m crackerjack start` (in the background or a separate terminal — note the process needs to be stopped afterward with `python -m crackerjack stop`)

- [ ] **Step 2: Exercise the tool surface directly**

Using whatever MCP client/inspection method is available in this environment, call the tools remaining in `crackerjack/mcp/tools/skill_tools.py` and `crackerjack/mcp/tools/progress_tools.py` after Task 24 Step 6's edits. Confirm they either work correctly or were fully removed (not left registered-but-broken).

- [ ] **Step 3: Check server logs for import errors**

Run: `python -m crackerjack status` and check for any error output referencing deleted modules.

- [ ] **Step 4: Stop the server**

Run: `python -m crackerjack stop`

- [ ] **Step 5: Record the result**

If anything failed, fix it and re-run this task from Step 1 before considering this plan complete — do not mark the plan done on a clean `git diff` alone, per the design spec's explicit instruction to verify by running.

---

### Task 34: Final full-suite verification against baseline

**Files:** None modified — verification task.

**Interfaces:** N/A.

- [ ] **Step 1: Run the full suite**

Run: `python -m crackerjack run --run-tests 2>&1 | tee /tmp/crackerjack-post-removal-$(date +%Y%m%d).log`

- [ ] **Step 2: Compare against the Task 1 baseline log**

Pass/fail counts should match (same tests passing, minus the ones deliberately deleted alongside their subsystems — no *new* failures in surviving tests). Coverage percentage should match Task 30's recomputed ratchet.

- [ ] **Step 3: Diff the total line-count change against the tag from Task 1**

Run: `git diff --stat pre-ai-fix-removal..HEAD | tail -1`

Confirm the net change is a large deletion (expected: tens of thousands of lines removed, a few thousand added in `crackerjack/fixers/` and `crackerjack/models/issues.py`).

- [ ] **Step 4: If everything passes, this plan is complete.** The external loop replacement is a separate plan (`docs/superpowers/plans/2026-08-06-ai-fix-external-loop.md`) that depends on this one's `--json` contract (Task 3) and can now begin.
