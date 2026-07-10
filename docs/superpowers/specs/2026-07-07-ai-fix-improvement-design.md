# ai-fix improvement — design

**Date:** 2026-07-07
**Status:** Approved (revised 2026-07-07 to add PR 0)
**Approach:** C-via-strangler-fig (9 PRs: PR 0 reporting + PRs 1-8 architecture; behavior-preserving; each independently shippable)

## Problem

The crackerjack `--ai-fix` stage currently:

1. **Thrashes on no-op fixes.** When a fixer reports `success=True` but the file is unchanged, the loop regenerates the same plan and retries 3× before failing.
1. **Fires Tier-3 (LLM session) for only 5 ty codes.** Refurb / pymetrica / formatting / dead-code / etc. never reach the LLM, even when mechanical fixers fail.
1. **Decouples fixer success from disk state.** `success=True` is "operation didn't throw," not "bytes differ."
1. **Pymetrica adapter files every metric violation as a `ToolIssue` against the project directory** with `line_number=None`. The analysis pipeline creates 1,000+ `FixPlan`s the fixers can't execute.
1. **Has no classifier at the issue boundary.** Every issue is treated as "try to fix it" regardless of whether it's a line-level defect, an aggregate metric, or a false positive.
1. **Has no learning.** `IterativeFixAgent` has a `SkillStore` protocol designed but never wired in. Successful LLM fixes are not cached. There is no path from "LLM fixed it" to "next time, mechanical fixer handles it."

The compounding effect: a 53-minute `crackerjack run --ai-fix` produced 1,954 no-op fixes, 21 no-progress regenerations, and 3 actual successes (9.7% of attempts).

## Goals (in order of impact)

1. Stop the pymetrica explosion (1,061 issues → 0).
1. Broaden Tier-3 to all issue types (5 → all).
1. Tighten the fixer success signal to "bytes differ on disk."
1. Self-improving loop: LLM fixes → cached skills → auto-promoted mechanical fixers.
1. Clean architecture for the next change (new tiers, providers, coordination patterns are additive, not a debug session).

## Non-goals

- Replacing the AI agents (TypeErrorSpecialist, RefactoringAgent, etc.).
- Touching the comprehensive-hooks stage.
- Cross-repo skill sharing (SessionBuddySkillStore is designed for it; future work).
- A single mega-PR.

## Architecture

```
comprehensive_hooks → issues
                       ↓
[NEW] IssueClassifier          ← classify(issue) → fixable_mechanical | needs_llm | non_fixable
[NEW] IssueLifecycle           ← per-issue state: attempts, results, should_retry
[NEW] FixRouter                ← single source of truth for routing
    ├── [NEW] TightenedFixerDispatcher   ← bytes-differ check
    ├── [NEW] FixerRegistry              ← built-in + auto-promoted fixers
    ├── [EXISTING] Tier-1 mechanical
    ├── [EXISTING] Tier-2 TypeErrorSpecialist (one-shot LLM)
    ├── [BROADENED] Tier-3 IterativeFixAgent   ← remove TIER3_ISSUE_TYPES gate
    └── [EXISTING] SkillStore            ← finally wired in
                       ↓
[NEW] PromotionPipeline         ← skill replayed N times → LLM code-gen → mechanical fixer
[NEW] AutoFixerPRCreator        ← submit generated fixer as PR
                       ↓ (PR merged)
              FixerRegistry picks it up next run
```

## Component specs

### IssueClassifier (NEW — `crackerjack/ai_fix/issue_classifier.py`)

```python
class IssueKind(Enum):
    FIXABLE_MECHANICAL = "fixable_mechanical"
    NEEDS_LLM = "needs_llm"
    NON_FIXABLE = "non_fixable"

def classify(issue: Issue, fixer_registry: FixerRegistry) -> IssueKind:
    # 1. Aggregate metric (pymetrica-*, halstead-*, maintainability-*) → NON_FIXABLE
    # 2. IssueKind already FIXABLE_MECHANICAL? keep
    # 3. Built-in fixer exists? → FIXABLE_MECHANICAL
    # 4. Otherwise → NEEDS_LLM
```

Pure function. No I/O. Decision order is explicit. Aggregates are detected by code prefix; the prefix list lives in a single constant.

### IssueLifecycle (NEW — `crackerjack/ai_fix/issue_lifecycle.py`)

```python
class IssueLifecycle:
    def __init__(self, issue: Issue, kind: IssueKind) -> None: ...
    def record_attempt(self, tier: int, result: FixResult) -> None: ...
    def should_retry(self) -> bool: ...        # False on no-op, on exhaustion, or NON_FIXABLE
    def should_escalate_to_next_tier(self) -> bool: ...
    def classification(self) -> IssueKind: ...
```

Holds the no-op detection (currently in `autofix_coordinator._is_no_op_failure`), the retry budget, and the classification. Defect-#1 logic moves here from `autofix_coordinator`.

### TightenedFixerDispatcher (NEW — `crackerjack/ai_fix/tightened_dispatcher.py`)

```python
async def dispatch_with_bytes_check(fixer: Fixer, plan: FixPlan, target: Path) -> FixResult:
    before = target.read_bytes()
    result = await fixer.execute(plan)
    after = target.read_bytes()
    if result.success and before == after:
        return FixResult(success=False, remaining_issues=["no-op fix: file content unchanged"], ...)
    return result
```

A wrapper, not a class. Called by FixRouter. This is defect-#1's logic at the right layer.

### FixerRegistry (NEW — `crackerjack/ai_fix/fixer_registry.py`)

```python
class FixerRegistry:
    def has_mechanical_fixer(self, issue_type: str) -> bool: ...
    def get(self, issue_type: str) -> Fixer | None: ...
    def register_auto_promoted(self, signature: str, fixer: Fixer) -> None: ...
    def list_signatures(self) -> list[str]: ...
    @classmethod
    def from_disk(cls, auto_fixers_dir: Path) -> "FixerRegistry": ...
```

Replaces `FixerCoordinator.fixers: dict[str, Agent]`. Dynamic: built-in registered at startup, auto-promoted added at runtime. Can be reconstructed from `auto_fixers/` directory.

### FixRouter (NEW — `crackerjack/ai_fix/fix_router.py`)

```python
class FixRouter:
    def __init__(self, registry: FixerRegistry, skill_store: SkillStore,
                 tier2: Tier2Dispatcher, tier3: IterativeFixAgent,
                 classifier: IssueClassifier) -> None: ...
    async def fix(self, issue: Issue) -> FixResult: ...
```

Order: (1) registry lookup → Tier-1 (tightened); (2) SkillStore.find(signature) → replay; (3) Tier-2 one-shot; (4) Tier-3 LLM session (gated by `should_escalate_to_next_tier`, not by type). All wrapped by `IssueLifecycle`.

### SkillStore (EXISTING — wire in)

Already designed in `crackerjack/agents/iterative_fix_agent.py`. Just needs to be called from `FixRouter`. Persistent implementation: future `SessionBuddySkillStore`. For this round: `InMemorySkillStore` is fine.

### BroadenedTier3Dispatcher (replace `TIER3_ISSUE_TYPES` gate)

The current `TIER3_ISSUE_TYPES = frozenset({5 ty codes})` in `fixer_coordinator.py` is replaced by a property: "fires whenever `IssueLifecycle.should_escalate_to_next_tier()` returns True." The `IterativeFixAgent` itself doesn't change.

### PromotionPipeline (NEW — `crackerjack/ai_fix/promotion_pipeline.py`)

```python
class PromotionPipeline:
    def __init__(self, skill_store, llm_client, sandbox_runner, pr_creator): ...
    async def maybe_promote(self, signature: str) -> PromotionResult: ...
```

Triggered when a skill has been replayed successfully `N` times (default 3). Steps: (1) LLM writes a mechanical fixer from the skill's recorded diff + the original error; (2) save to temp; (3) sandbox runs the skill-replay test against the generated fixer; (4) on pass, `pr_creator.create_pr(...)`; (5) on fail, log and skip.

### AutoFixerPRCreator (NEW — `crackerjack/ai_fix/auto_fixer_pr_creator.py`)

Thin wrapper around `gh pr create`. PR body includes: source signature, source skill diff, sandbox test results, "promoted from skill" header. No auto-merge.

### PymetricaAdapter (FIX — `crackerjack/adapters/complexity/pymetrica.py`)

Change `file_path=Path(self.settings.directory)` to: `file_path=Path(file_path)`, `line_number=None`, `code="pymetrica-aggregate"`. The classifier sees the prefix and returns `NON_FIXABLE`. The metric is still visible in reports; the fix-loop skips it.

## Data flow

1. Comprehensive hooks produce `list[Issue]`.
1. `IssueClassifier.classify(issue)` → `IssueKind`.
1. `IssueLifecycle` wraps each issue.
1. `FixRouter.fix(issue)`:
   - Tier-1 via registry, wrapped by `TightenedFixerDispatcher`.
   - On non-effective: `SkillStore.find(signature)` → replay. Record attempt for promotion counter.
   - On non-effective: Tier-2 (one-shot LLM).
   - On non-effective + `should_escalate_to_next_tier()`: Tier-3 (LLM session). On success, `SkillStore.record(signature, Skill(diff))`.
1. IssueLifecycle.classification determines next-iteration handling.
   - `NON_FIXABLE`: tagged, excluded from next iteration.
   - `success=True`: done.
   - Else: depends on retry budget.
1. After the loop: `PromotionPipeline.maybe_promote(signature)` for each skill with count ≥ threshold.
1. Next run: `FixerRegistry.from_disk()` loads promoted fixers. Hot signatures hit Tier-1 directly.

## Error handling

- **LLM session timeout:** `IterativeFixAgent.timeout_seconds=600` already bounded.
- **Malformed LLM diff:** `IterativeFixAgent` returns `FixOutcome(success=False)`. Lifecycle records, doesn't retry.
- **Generated fixer fails sandbox:** `PromotionPipeline` logs, skips. Skill keeps replaying.
- **PR creation fails:** `AutoFixerPRCreator` raises, caught. Generated fixer saved to `auto_fixers/{signature}.py` for human pickup.
- **`claude` CLI missing:** detect at startup, raise before iteration. No silent fallback.
- **Classifier can't decide:** default `NEEDS_LLM` (better to over-route than drop).

## Testing strategy

**Per-component unit tests** (`tests/unit/ai_fix/`):

- `test_issue_classifier.py` — pure function, all branches.
- `test_issue_lifecycle.py` — state machine, no-op flag.
- `test_fix_router.py` — routing decisions, all four tiers, stub deps.
- `test_fixer_registry.py` — built-in + auto-promoted registration.
- `test_tightened_dispatcher.py` — bytes-differ check.
- `test_skill_store.py` — in-memory replay.
- `test_promotion_pipeline.py` — LLM mocked, sandbox real.
- `test_auto_fixer_pr_creator.py` — gh client mocked.
- `test_pymetrica_adapter.py` — new issue format.

**End-to-end test** (`tests/e2e/test_ai_fix_pipeline.py`):

- Fixture codebase with: 1 ty, 1 refurb, 1 pymetrica-aggregate, 1 needs-llm.
- Assert: ty fixed mechanically, refurb via skill, pymetrica-aggregate tagged NON_FIXABLE, needs-llm via Tier-3.
- After N successful replays, assert a promotion PR is created.

**Regression test:** `tests/core/autofix_coordinator_aifix_thrash_test.py` continues to pass.

**Coverage target:** 85% for new code.

## PR sequence (strangler-fig)

| PR | Title | Risk | Ships |
|---|---|---|---|
| **0** | `feat(ai-fix): collapse progress systems + wire event bus` | Low | Live dashboard actually works; verbosity; crash recovery |
| **1** | `fix(pymetrica): stop emitting per-metric issues for aggregate metrics` | Low | 1,061 issues → 0 |
| **2** | `refactor(ai-fix): extract IssueClassifier (read-only)` | Low | Foundation |
| **3** | `feat(ai-fix): TightenedFixerDispatcher — bytes-differ check` | Low | Kills 100% of no-op lies |
| **4** | `refactor(ai-fix): IssueLifecycle (move defect-#1 logic)` | Medium | Per-issue state machine |
| **5** | `feat(ai-fix): FixerRegistry (dynamic built-in + auto-promoted)` | Medium | Foundation for promotion |
| **6** | `feat(ai-fix): FixRouter + broaden tier-3` | Medium | Single source of truth for routing |
| **7** | `feat(ai-fix): wire SkillStore into router` | Low | Cache hit rate: 0 → many |
| **8** | `feat(ai-fix): PromotionPipeline + AutoFixerPRCreator` | High | Self-improving loop |

Each PR is behavior-preserving. The old code is deleted in a cleanup PR after PR-8 ships and is verified equivalent.

______________________________________________________________________

## PR 0 detail: collapse progress systems + wire event bus

**Goal:** Make the live dashboard actually work. Most of the data model exists; what's missing is the wiring, the new event types (FixSession, TierTransitioned), and the verbosity controls.

**In scope:**

1. **Retire `AIFixProgressManager`** (`crackerjack/services/ai_fix_progress.py`, 481 LOC). All callers route through `AIFixDashboard`. The neon-style "AGENT_ICONS" output is replaced by the rich live panel.

1. **Add 3 new event types** to `crackerjack/core/ai_fix_events.py`:

   - `FixSessionStarted` (issue_signature, file, issue_type)
   - `TierTransitioned` (issue_signature, from_tier, to_tier, reason, file)
   - `FixSessionFinished` (issue_signature, file, success, final_tier, total_duration_s, no_op_count)

1. **Wire events from real code paths** (the bulk of the work):
   | Event | Emission site |
   |---|---|
   | `RunStarted` | `crackerjack/cli/handlers/ai_features.py:run_ai_fix()` |
   | `IterationStarted/Finished` | `AutofixCoordinator._run_iteration()` |
   | `AgentDispatched` | `FixerCoordinator._dispatch_plan()` |
   | `IssueResolved/IssueFailed` | `FixerCoordinator._dispatch_plan()` |
   | `FixSessionStarted/Finished` | `AutofixCoordinator._process_issue()` |
   | `TierTransitioned` | **Defer to PR 6** (FixRouter) |

1. **Default bus wiring** in `crackerjack run --ai-fix`. Call `build_default_bus()` from `ai_fix_sinks.py` at run start; subscribe `LoggingSink + JsonlSink + MetricsSink + AIFixDashboard`. Store the bus on the coordinator so events can be emitted.

1. **Verbosity levels**:

   - (default) Live dashboard when TTY; JSONL always; no event log to stdout
   - `-v` Dashboard + per-event log line in the panel
   - `-vv` Dashboard + structured log of every event (current LoggingSink behavior)
   - `-vvv` Dashboard + full JSON event stream to stderr
   - `--ai-fix-debug` All of `-vvv` + a `DebugFileSink` writing to `.crackerjack/runs/{run_id}/debug.log`

1. **Sidecar consumer** for crash recovery:

   - On run start, `run_ai_fix()` checks `.crackerjack/runs/` for orphan `.open` files (left by crashed runs)
   - Logs a warning: "Detected crashed run `<run_id>`. Use `crackerjack replay <run_id>` to view events."
   - Add new top-level command `crackerjack replay <run_id>` using `JsonlSink.restore_run()` to render the static event log

**Out of scope for PR 0 (defer):**

- `TierTransitioned` wiring (requires `FixRouter` from PR 6)
- Hook-progress in the dashboard (was in `AIFixProgressManager`; can be a follow-up)
- Performance aggregation (p50/p95 per agent per tier) — defer until the user asks
- Live diff display when a fix lands

**Files affected:**

- `crackerjack/services/ai_fix_progress.py` — deleted
- `crackerjack/core/ai_fix_events.py` — 3 new event classes
- `crackerjack/core/ai_fix_sinks.py` — new `DebugFileSink` and sidecar check helper
- `crackerjack/ui/ai_fix_dashboard.py` — extend to render the 3 new event types
- `crackerjack/cli/handlers/ai_features.py` — wire bus, parse verbosity, sidecar check
- `crackerjack/core/autofix_coordinator.py` — emit `RunStarted/IterationStarted/Finished/FixSessionStarted/Finished/AgentDispatched/IssueResolved/IssueFailed`
- `crackerjack/agents/fixer_coordinator.py` — emit `AgentDispatched/IssueResolved/IssueFailed`
- `crackerjack/cli/replay.py` (new) — `crackerjack replay <run_id>` command

**Tests:**

- `test_ai_fix_dashboard.py` — new tests for each new event type
- `test_event_bus_wiring.py` — integration: emit an event, assert all sinks received it
- `test_crash_recovery.py` — start a run, kill it, verify sidecar is left, `crackerjack replay` works
- `test_verbosity.py` — at each level, assert the right sinks are active

**Success criteria for PR 0:**

- Run `crackerjack run -v --ai-fix` and the live dashboard shows: per-fix status, per-iteration progress, no-op count, current "in progress" indicator.
- Run `crackerjack run -vvv --ai-fix` and every event lands in a JSONL file at `.crackerjack/runs/{run_id}/events.jsonl`.
- Kill a run mid-iteration; `crackerjack replay <id>` shows the events up to the kill.
- `AIFixProgressManager` is gone; the two progress systems are collapsed to one.

## Success criteria

After all 8 PRs land, re-run `crackerjack run -v --ai-fix` on the current crackerjack codebase:

- pymetrica FixPlans: 0 (vs 1,061 before).
- No-op fixes (defect #1 trigger): ≤ 50 (vs 1,954 before).
- No-progress regenerations (defect #3 trigger): ≤ 10 (vs 21 before).
- Final comprehensive-hooks pass: ≤ 5 residual errors (vs 22 before).

**Run twice in a row:** second run measurably faster (skill replay + auto-promoted fixers).

**After 3 runs:** at least one auto-promoted fixer PR submitted.

**Architectural:**

- `autofix_coordinator.py` shrinks below 4,500 lines.
- `FixRouter` < 500 lines.
- Each new component is independently testable.
- Adding a new tier requires changes in exactly one place.

## Open questions

None — design approved by user 2026-07-07.
