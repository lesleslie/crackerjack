---
status: draft
role: implementation
topic: lifecycle
date: 2026-08-06
last_reviewed: 2026-08-06
superseded_by: null
blocks_on: []
supersedes:
  - 2026-07-07-ai-fix-improvement-design.md
  - 2026-07-08-fix-sandbox-integration-design.md
  - 2026-07-10-libcst-surgeon-extract-method-fallback-design.md
  - 2026-07-10-output-validator-traceback-details-design.md
  - 2026-07-10-validation-coordinator-serialization-design.md
  - 2026-07-11-ai-fix-e501-post-processor-design.md
  - 2026-07-11-ai-fix-no-op-circuit-breaker-design.md
  - 2026-07-11-ai-fix-regen-timeout-design.md
---

# ai-fix removal + external loop replacement — design

**Date:** 2026-08-06
**Status:** Draft, pending user review
**Scope:** Phase 1 only. Covers: (a) extraction of crackerjack's genuinely deterministic fixer logic into standalone, framework-free mechanical fixers, (b) destructive removal of the unstable orchestration/dispatch/learning machinery around it, (c) an external, agent-driven loop outside the crackerjack package to handle whatever residue the mechanical fixers can't, (d) a passive fix-outcome logging hook to Akosha. Explicitly excludes a Mahavishnu pool-worker executor and Akosha active pre-fix querying — those get their own specs, grounded in direct investigation of those repos, after this phase ships and is verified.

## Problem

Crackerjack's `--ai-fix` capability has grown into four separate, overlapping, independently-built orchestration/learning subsystems rather than one coherent design:

1. `crackerjack/agents/` — 75 files, ~35,000 lines. 12+ specialized "fixer" agents plus a coordinator/enhanced_coordinator dispatch layer.
2. `crackerjack/ai_fix/` — 18 files, ~2,850 lines. A second, parallel tiered router (`FixRouter`, `TightenedDispatcher`, `SandboxedDispatcher`) with a `PromotionPipeline`/`SkillStore` for auto-promoting fixers. Designed by [2026-07-07-ai-fix-improvement-design.md](2026-07-07-ai-fix-improvement-design.md).
3. `crackerjack/intelligence/` — 6 files, ~2,500 lines. A *third* orchestrator (`agent_orchestrator.py`, `agent_registry.py`, `agent_selector.py`) plus its own `adaptive_learning.py`.
4. `crackerjack/memory/` — 8 files, ~2,460 lines. A hand-rolled vector-embedding + SQLite persistence layer (`fix_strategy_storage.py` with its own SQL schema, `issue_embedder.py`, `strategy_recommender.py`) for recalling which fix worked before.

Plus `crackerjack/skills/` (1,901 lines, exposes the 12 agents as MCP-discoverable skills) and the true master orchestrator `crackerjack/core/autofix_coordinator.py` — 5,425 lines by itself, a single class spanning ~5,100 lines / 226 methods, directly importing from all four subsystems above.

**Evidence of instability, not just size:**
- 233 commits touched `crackerjack/agents/` in the last 6 months; 19 in the last 30 days.
- `2215e57f fix(ai-fix): break the cascade that grew 12 issues into 19` — the fixer made things actively worse in production.
- `53bb3acc feat(ai-fix): add no-op circuit breaker to skip identical retry plans` — needed loop-detection to stop infinite retries on failed plans.
- Uncommitted `.backup`/`.backup.json` files left in `crackerjack/ai_fix/` from live production patching, never cleaned up.
- The two most recent commits on `main` at design time (`71955ad0`, `51ce350b`) add a "dirty-tree guard" + `.bak` sibling rollback because even the deterministic `ruff --fix` path could corrupt the working tree.
- A prior full rewrite (`f635b9c5 refactor(ai-fix): delete V1 pipeline — single router-driven V2 path`) did not reduce the churn rate afterward.

**Root cause, refined:** the instability is entirely in the *coordination layer* — `agents/coordinator.py`, `agents/enhanced_coordinator.py`, `agents/fixer_coordinator.py`, `agents/analysis_coordinator.py`, `agents/validation_coordinator.py`, `agents/parallel_dispatcher.py`, all of `ai_fix/`, `intelligence/`, `memory/` — which independently, and four separate times, tried to solve "pick the right fix, remember what worked, keep retrying until clean." **It is not in the individual fixer logic.**

A dedicated investigation (Explore agent, classifying every fixer file in `agents/` by reading its actual implementation) found that **roughly 75–85% of the ~35,000 lines in `agents/` is genuine deterministic/mechanical fixing logic** — AST transforms (`refurb_agent.py` has 10+ explicit `_ast_transform_*` methods; `type_error_specialist.py` does `ast.parse`/`ast.Module` splicing; `refactoring_agent.py` does AST-based complexity reduction), regex-driven rewrites (`security_agent.py`'s `SAFE_PATTERNS`, `dry_agent.py`'s duplicate-pattern detectors, `dependency_agent.py`'s `pyproject.toml` edits), or CLI wrapping (`formatting_agent.py` shells out to `ruff`, `import_optimization_agent.py` shells out to `vulture`). **None of this needs an LLM in the loop.** Only `agents/claude_code_bridge.py` (which routes to external Claude Code specialist agents like `refactoring-specialist`, `python-pro`, `security-auditor`) and `agents/enhanced_proactive_agent.py` (a thin wrapper that calls the bridge) are genuine LLM-dispatch plumbing — along with roughly 30% of `architect_agent.py`, which for `COMPLEXITY`/`DRY_VIOLATION` issues just returns a plan naming an external specialist rather than fixing anything itself.

Deleting all of `agents/` as originally scoped would have discarded ~26,000–30,000 lines of working, valuable, dependency-free code to solve a problem that lives one layer up.

## Goals

1. **Extract and preserve** the genuinely deterministic fixer logic as plain, framework-free mechanical fixers — no `SubAgent` base class, no coordinator, no LLM dispatch, callable directly the same way crackerjack already calls `ruff`/`pytest`/other tools.
2. **Remove completely** the unstable orchestration/dispatch/promotion/learning machinery — no partial/incremental deprecation; there is no stable intermediate state to deprecate into.
3. Preserve the shared issue vocabulary (`Issue`, `IssueType`, `Priority`, `FixResult`) that ~30 other files depend on for reporting/parsing, independent of how issues get fixed.
4. Give crackerjack a versioned, tested `--json` contract so an external driver can depend on it safely.
5. Replace the *coordination* capability (not the fixing logic) with an external loop, outside the crackerjack package, that runs the extracted mechanical fixers first and dispatches only the genuine residue to an agentic session — with safety properties (rollback, timeout, audit trail) built in from the start rather than patched in reactively.
6. Log fix outcomes to Akosha (write-only) so the ecosystem's cross-system intelligence layer — not crackerjack itself — becomes the place where "does this help next time" eventually gets answered.

## Non-goals (this phase)

- A Mahavishnu pool-worker executor. Mahavishnu's only existing convergence primitive (`detect_until_dry`) stops on "no *new* findings," not "issue count reaches zero" — reusing it naively reproduces the exact false-green convergence failure crackerjack's circuit breakers exist to prevent — and it is marked `Built: no / Wired: no` in Mahavishnu's own tracking. There's also no worktree isolation wired between pool dispatch and Mahavishnu's `WorktreeCoordinator`. This needs its own grounded spec.
- Akosha active pre-fix querying. `search_all_systems`, the only "have we seen this before" tool, currently returns hardcoded mock results — the real backend (`HotStore.search_similar`) exists but isn't wired to the exposed MCP tool. Querying against it today would silently return fake similarity data. Needs its own spec, owned by the Akosha repo.
- Preserving a single-command `crackerjack run --ai-fix` UX. Explicitly not required.
- Rewriting `core/phase_coordinator.py`'s non-AI responsibilities (formatting/testing phase orchestration) — only its AI-specific code paths are in scope.
- Touching `crackerjack/parsers/*.py` or `crackerjack/adapters/format/ruff.py` beyond repointing their `Issue`/`IssueType` import path — these are type-only consumers and keep their current behavior.
- Re-implementing LLM-dispatch logic (`claude_code_bridge.py`, `enhanced_proactive_agent.py`, the external-consultation branch of `architect_agent.py`) in any form — this is exactly what the external loop's agentic session replaces natively, with zero porting needed.

## Architecture

### 1a. Mechanical fixer extraction (new — the key correction to the original plan)

For each fixer file classified as deterministic (or mixed-mostly-deterministic), strip the `SubAgent`/coordinator/`FixResult`-dispatch scaffolding and re-expose the actual transform logic as plain, directly callable functions — no AI, no orchestration framework, no base-class inheritance:

**Extract as-is (bucket A):** `refactoring_agent.py`, `performance_agent.py`, `security_agent.py`, `documentation_agent.py`, `test_creation_agent.py`, `dry_agent.py`, `formatting_agent.py`, `import_optimization_agent.py`, `test_specialist_agent.py`, `refurb_agent.py`, `dead_code_removal_agent.py`, `type_error_specialist.py`, `anti_pattern_agent.py`, `dependency_agent.py`, and their supporting `agents/helpers/` modules (`helpers/ast_transform/` — including `surgeons/libcst_surgeon.py`, the 1,809-line AST surgery engine — `helpers/refactoring/code_transformer.py`, `helpers/test_creation/*`, `helpers/performance/*`), since these are the mechanical engines the fixer files call into, not scaffolding.

**Extract the deterministic portion only (mixed):**
- `architect_agent.py` — keep the AST/regex fix methods for `TYPE_ERROR`/`DEPENDENCY`/`DOCUMENTATION`; drop the `{"strategy": "external_specialist_guided", ...}` plan-and-defer branch for `COMPLEXITY`/`DRY_VIOLATION` entirely (the external loop's agentic session handles those directly, no plan-object handoff needed).
- `semantic_agent.py` — keep the local `VectorStore`/embedding-search logic (deterministic, not an LLM call); confirm nothing in it depends on the coordinator being deleted.

**Needs extra scrutiny during extraction, not a rubber-stamp port:** `planning_agent.py` (3,349 lines, the largest file in the package). It's mechanically implemented (`ast`, `SafeRefurbFixer`, `ChangeSpec`/`FixPlan` construction, no `claude_code_bridge` import) but its *role* — deciding what to fix and building a plan — overlaps conceptually with what the external loop itself now does (collect issues, decide what to dispatch). Do not port it wholesale; during implementation, identify which parts are genuinely reusable fix-plan construction (keep) versus orchestration-adjacent decision logic now redundant with the external loop (drop).

**Delete outright, no extraction (bucket B):** `agents/claude_code_bridge.py`, `agents/enhanced_proactive_agent.py`, and the external-consultation branch of `architect_agent.py` identified above — this is pure LLM-dispatch plumbing that a capable agentic session replaces with zero loss.

Target shape for the extracted code: plain functions/modules, most naturally organized the same way crackerjack already organizes other deterministic tool wrappers (see `crackerjack/adapters/{format,complexity,type,refactor}/` for the existing pattern) — exact package layout is an implementation-plan decision, not fixed here.

### 1b. Shared vocabulary extraction

`crackerjack/agents/base.py` is not a pure data module — alongside `Issue`, `IssueType`, `Priority`, `FixResult` it also defines `SubAgent` (the ABC all 75 agent files subclass), a module-level `agent_registry` singleton, and `AgentContext`, whose `write_file_content` method runtime-imports `crackerjack.ai_fix.code_post_processor` — i.e. the "shared types" file already reaches into code slated for deletion. `crackerjack/models/protocols.py` similarly carries `AgentCoordinatorProtocol.handle_issues`, `AgentTrackerProtocol`, `AgentRegistryProtocol` — orchestration contracts, not data shapes.

Action: create a new leaf module, `crackerjack/models/issues.py`, containing only `Issue`, `IssueType`, `Priority`, `FixResult`, with **zero imports** from `agents/`, `ai_fix/`, `intelligence/`, `memory/`, or `skills/`. Delete `SubAgent`, `agent_registry`, and the three orchestration protocols outright — do not relocate them; nothing will implement them after this phase. (The extracted mechanical fixers from 1a do not need `SubAgent` or `AgentContext` — they become plain functions taking file paths/content and returning results, decoupled from the agent framework entirely.)

Known non-type-only (behavioral) call sites requiring real rewrites, not import swaps:
- `crackerjack/core/proactive_workflow.py` — instantiates `AgentCoordinator` directly.
- `crackerjack/core/tier3_factory.py` — imports `IterativeFixAgent`, `LocalClaudeSubprocess`, `MahavishnuPool`, `InMemorySkillStore` (a whole fixing-engine factory).
- `crackerjack/documentation/dual_output_generator.py` — imports `AgentCoordinator`.
- `crackerjack/services/batch_processor.py` — imports the `ISSUE_TYPE_TO_AGENTS` dispatch table.
- `crackerjack/services/agent_delegator.py` — imports `AgentCoordinator`/`SubAgent`.
- `crackerjack/mcp/tools/skill_tools.py` — constructs `AgentContext` directly and drives an `agent_skills` registry.

Each of these loses its AI-dispatch code path; where the extracted mechanical fixers from 1a are relevant to what they were doing, they may call those directly instead.

### 2. Versioned `--json` contract

Today's `crackerjack run --json` output is very likely an incidental byproduct of `autofix_coordinator.py`'s internals, not a designed public contract — nothing currently tests its shape. Before any deletion touches that file:

- Define the output schema as a versioned Pydantic model in `crackerjack/models/issues.py` (or an adjacent module), with an explicit `schema_version` field on every payload.
- Add a golden-file contract test in crackerjack's own suite asserting the schema hasn't drifted.

This is what makes "crackerjack doesn't know its external consumer exists" safe rather than fragile — the external loop driver depends on this contract, and crackerjack has no other way to know if it breaks it.

### 3. Destructive removal (coordination/dispatch/learning layers only)

Once steps 1a–2 land: delete `agents/coordinator.py`, `agents/enhanced_coordinator.py`, `agents/fixer_coordinator.py`, `agents/analysis_coordinator.py`, `agents/validation_coordinator.py`, `agents/parallel_dispatcher.py`, `agents/claude_code_bridge.py`, `agents/enhanced_proactive_agent.py`, all remaining files in `agents/` not covered by the 1a extraction, all of `crackerjack/ai_fix/`, `crackerjack/intelligence/`, `crackerjack/memory/`, `crackerjack/skills/`, and the AI-specific methods inside `crackerjack/core/autofix_coordinator.py` / `crackerjack/core/phase_coordinator.py` (the non-AI tool-orchestration methods in those two files are interleaved in the same class bodies and must be individually identified, not assumed separable by file boundary).

Additional steps as part of this same change, per panel findings:
- Recompute the coverage ratchet baseline (CLAUDE.md: "targets 100%, never decrease") — deleting this much code and tests simultaneously moves both sides of that ratio in one commit; this must be a deliberate recalculation, not a surprise on the next `crackerjack run`.
- Grep `session-buddy` (a sibling repo) for coupling to this code before merging — CLAUDE.md documents live skills-tracking integration reading agent-selection data from crackerjack; that coupling is cross-repo and invisible to crackerjack's own test suite.
- Remove the `--ai-fix` CLI flag and its wiring from `crackerjack/__main__.py` (`CLI_OPTIONS["ai_fix"]`, `setup_ai_agent_env`) since the machinery it drives no longer exists; confirm `max_iterations` (`crackerjack/__main__.py:245,463`) is not exclusively AI-fix-scoped before deciding whether it's removed alongside it or kept for other retry uses.
- Mark the eight specs listed in this doc's frontmatter `supersedes` field as superseded by this one.

### 4. Post-delete verification (do not skip — verify by running, not by reading the diff)

Actually start the MCP server (`python -m crackerjack start`) and exercise the tool surface — `crackerjack/mcp/tools/skill_tools.py` and `crackerjack/mcp/tools/progress_tools.py` — after the deletion lands. A clean `git diff` and passing import-compile check will not catch a tool that fails at request time because a registered agent class it depends on no longer exists.

### 5. External loop (Phase 1 executor: local agentic session)

Lives entirely outside the crackerjack package — no new AI-fixing Python code ships inside `crackerjack/` beyond the plain mechanical fixers from 1a. Implemented as a `Workflow` script (or Claude Code skill) that:

1. Calls `crackerjack run --json`, parses the versioned schema from step 2.
2. If clean, stop (success).
3. If not clean and under the iteration cap: snapshot the working tree (git stash or a throwaway commit), dispatch the residual issue list to the current agentic session for fixing (the mechanical fixers from 1a should already have resolved anything they can — either as part of crackerjack's normal hook run, or invoked explicitly by the driver before falling back to the agent), apply the resulting edits.
4. Re-run `crackerjack run --json`. If the issue count did not decrease, roll back the snapshot and stop (regression — do not loop further on a non-improving attempt). If it improved, continue to the next iteration.
5. Stop conditions: issue count reaches zero (success), iteration cap reached (residual failure — report what's left), wall-clock timeout exceeded (abort — in addition to the iteration cap, so a single hung agent call can't hang the whole loop), or a fixer/tooling error (abort with the error surfaced, not silently swallowed).
6. Every iteration's diff (not just an issue count) is written to a durable audit log — file, hunk, iteration number — so a human can review exactly what was auto-changed after the fact.
7. Distinct exit/stop reasons are surfaced by the driver: clean / unfixed-residue / fixer-error / timeout-aborted — not a single pass/fail bit.

The executor step (3, "dispatch to an agentic session") is implemented behind a narrow interface so a Mahavishnu-pool-worker implementation can be substituted later without changing the loop's control flow — but only one implementation (local session) ships in this phase.

### 6. Akosha passive-logging hook

After each successful fix (an iteration that reduced the issue count), the driver calls Akosha's `store_memory` once per fix attempt (not per session or per repo — session-level logging would destroy the issue↔fix mapping). Per the Akosha review:

- The driver generates the embedding itself via `generate_embedding` before calling `store_memory` (no server-side embed-on-write exists).
- `text` is a concise natural-language symptom+fix description, not a raw diff or traceback (embedding quality depends on this).
- `metadata` carries a driver-imposed convention: `rule_id`/tool, repo, outcome, commit — Akosha has no first-class issue→fix→outcome schema, so structure only survives if the driver provides it consistently.
- This is write-only in this phase. No pre-fix querying against `search_all_systems` — see Non-goals.

## Sequencing / order of operations

1. Extract mechanical fixer logic (1a) into plain, framework-free functions; extract shared vocabulary (1b) into `crackerjack/models/issues.py`; delete `SubAgent`/`agent_registry`/orchestration protocols; rewrite the 6 behavioral call sites.
2. Define and test the versioned `--json` schema.
3. Destructive removal of the coordination/dispatch/learning layers + `ai_fix/`/`intelligence/`/`memory/`/`skills/` + AI-specific code in the two core coordinator files; remove the `--ai-fix` CLI flag; recompute coverage ratchet; grep session-buddy for coupling; mark superseded specs.
4. Post-delete verification: run the MCP server, exercise `skill_tools.py`/`progress_tools.py` directly.
5. Build the external Phase-1 loop driver (Workflow script), including snapshot/rollback, timeout, audit log, distinct stop reasons, and invocation of the extracted mechanical fixers ahead of any agentic dispatch.
6. Wire the Akosha passive-logging call into the driver.
7. Validate end-to-end against this repo's own real failures (fast + comprehensive hooks) before considering this phase done.

## Testing / verification plan

- Golden-file contract test for the `--json` schema (crackerjack's own suite).
- Existing tests for the extracted mechanical fixers (a subset of the ~40 test files touching `agents/`) are ported alongside their logic, adapted to the new framework-free call signatures — not discarded with the coordinator tests.
- Existing crackerjack test suite must pass after removal, with the coverage ratchet baseline explicitly recalculated and committed, not left to drift.
- Manual MCP-server smoke test post-removal (step 4 above) — not automatable in this phase, must be done by hand.
- The external loop driver is validated against real, current failures in this repo (not synthetic ones) as the acceptance test for Phase 1: run it against whatever `crackerjack run --json` currently reports, confirm it converges to clean or reports a legible residual-failure reason within the iteration/timeout caps, and confirm rollback actually restores working-tree state on an injected regression.

## Risks and open questions

- The 1a extraction is real, non-trivial engineering work — roughly 15 files and their `helpers/` dependencies need careful scaffolding-stripping, not a mechanical move. Budget it as the largest single piece of this phase, not a quick preamble to the "real" deletion work.
- `planning_agent.py` specifically needs a design decision during implementation (see Architecture 1a) on what's genuinely reusable versus redundant with the external loop's own issue-collection role.
- `core/autofix_coordinator.py`'s 226 methods are interleaved (AI and non-AI in the same class body) — separating them carries real risk of orphaned dead code that static analysis won't reliably catch inside a still-referenced class. Treat this as a manual, careful pass, not a mechanical deletion.
- The session-buddy cross-repo coupling has not yet been directly verified (grep pending in step 3) — if it's deeper than a read-only skills-tracking dependency, this spec's scope may need to expand to include a session-buddy-side change, which would itself need its own grounding before being added here.
- No decision yet on where the `Workflow` script / skill for the Phase-1 loop lives (crackerjack repo's `.claude/`, a shared location, or elsewhere), or the final package location for the extracted mechanical fixers (candidate: alongside the existing `crackerjack/adapters/` pattern) — to be resolved in the implementation plan.

## Future work (explicitly deferred, each gets its own grounded spec)

- Mahavishnu pool-worker executor, contingent on a real fix-until-clean primitive (`open_issue_count == 0` stop condition, not `detect_until_dry`) and worktree-per-batch isolation wired between pool dispatch and `WorktreeCoordinator`.
- Akosha active pre-fix querying, contingent on `search_all_systems` being wired to `HotStore.search_similar` instead of returning mock data.
- Wiring the Phase-1 driver to use both of the above once they exist, via the executor interface already established in this phase.
