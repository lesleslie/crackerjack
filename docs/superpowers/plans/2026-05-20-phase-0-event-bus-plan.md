# Phase 0 Implementation Plan — AI-Fix Event Bus

- **Status:** Draft for review
- **Spec:** [`docs/superpowers/specs/2026-05-20-ai-fix-comprehensive-overhaul-design.md`](../specs/2026-05-20-ai-fix-comprehensive-overhaul-design.md) §5.1
- **Scope:** Phase 0 only. No behavior changes from the user's perspective; foundation for Phases 1–4.
- **Estimated effort:** 1–2 days
- **Risk:** Low

## Goal

Introduce a structured event model for the AI-fix stage. Every existing `logger.info(...)` call inside the autofix coordinator and agent coordinator becomes `bus.emit(EventType(...))`. Default sinks reproduce today's logger output and write a JSONL transcript. No user-visible change except:

1. A new `.crackerjack/runs/<run_id>/events.jsonl` artifact appears per run.
2. The `alive_progress` bar in the AI-fix stage is **removed**.

## Acceptance criteria

1. `crackerjack run -t` on a fixture repo with comprehensive failures produces an `events.jsonl` with every iteration's lifecycle captured.
2. Stdout under default config matches pre-change output for every line that *isn't* the removed progress bar.
3. The `alive_progress` bar no longer renders during the AI-fix stage.
4. New unit tests pass; no existing tests regress.
5. `ruff`, `mypy`, and the project's complexity gate all pass on new files.

## Work breakdown

### Task 1 — Event types and bus (~3 hours)

Create `crackerjack/core/ai_fix_events.py`.

```python
from __future__ import annotations
import time
import uuid
from dataclasses import dataclass, field

@dataclass(frozen=True)
class AIFixEvent:
    run_id: str
    iteration: int
    kind: str = field(init=False)
    ts: float = field(default_factory=time.monotonic)

@dataclass(frozen=True)
class RunStarted(AIFixEvent):
    kind: str = "run_started"
    config_snapshot: dict[str, object] = field(default_factory=dict)

# ... IterationStarted, PreflightStarted, PreflightFinished,
#     IssueQueued, AgentDispatched, IssueResolved, IssueFailed,
#     IterationFinished, RunFinished
```

Use frozen dataclasses (hashable, safe under concurrency). One concrete subclass per event kind from the spec §5.1.

Then `crackerjack/core/ai_fix_event_bus.py`:

```python
from typing import Protocol

class Sink(Protocol):
    async def handle(self, event: AIFixEvent) -> None: ...

class AIFixEventBus:
    def __init__(self) -> None:
        self._sinks: list[Sink] = []

    def subscribe(self, sink: Sink) -> None: ...
    def unsubscribe(self, sink: Sink) -> None: ...

    async def emit(self, event: AIFixEvent) -> None:
        for sink in self._sinks:
            try:
                await sink.handle(event)
            except Exception:
                # log and continue — one bad sink doesn't break the run
                ...

    def new_run_id(self) -> str:
        return uuid.uuid4().hex[:8]
```

**Why async emit + per-sink try/except:** Phase 2 will have concurrent agents calling `emit` from many tasks. Sync emit would force every concurrent task to serialize behind sink I/O. Per-sink exception isolation means a flaky WebSocket can't break the JSONL transcript.

### Task 2 — Default sinks (~3 hours)

Create `crackerjack/core/ai_fix_sinks.py`:

- **`LoggingSink`** — receives events, formats them as the pre-existing log lines, calls `logger.info`. Goal: preserve today's stdout for the default config. Implement event-to-string formatters as a dict lookup keyed on `event.kind`.
- **`JsonlSink`** — async file writer to `.crackerjack/runs/<run_id>/events.jsonl`, flushes after every event. Creates the directory if missing. Serializes via `dataclasses.asdict` + `json.dumps`.
- **`MetricsSink`** — stub initially (`async def handle: return`); Phase 0 plumbs the wiring, Phase 1 fills it in.

### Task 3 — Wire the bus through coordinators (~4 hours)

Modify `crackerjack/core/autofix_coordinator.py`:

- Add optional `event_bus: AIFixEventBus | None = None` to `AutofixCoordinator.__init__`. If `None`, construct a default bus with `LoggingSink` + `JsonlSink` subscribed.
- Set `self._run_id = self.bus.new_run_id()` per `apply_autofix_for_hooks` invocation.
- Replace each existing `self.logger.info(...)` and `self.logger.warning(...)` inside the comprehensive path with an equivalent `await self.bus.emit(Event(...))`. Inventory: ~12 calls in `autofix_coordinator.py`, plus ~6 in `agents/coordinator.py`.

Modify `crackerjack/agents/coordinator.py`:

- Accept the same bus via constructor, default-constructed if missing.
- Replace `logger.info(f"Handling {len(issues)} issues (iteration {iteration}, ...)")` with `IterationStarted` emit.
- Replace per-agent `logger.info(...)` with `AgentDispatched` / `IssueResolved` / `IssueFailed`.

**Critical detail:** keep the `self.logger` calls that occur *outside* the comprehensive AI-fix path. Phase 0 is scoped to the comprehensive stage only.

### Task 4 — Remove the `alive_progress` bar (~1 hour)

Delete the progress bar entirely from the AI-fix flow.

- In `crackerjack/services/ai_fix_progress.py`:
  - Remove the `alive_bar` import.
  - Replace `progress_context` with a no-op `@contextmanager` that yields `None` (keeps the call-site API stable to avoid touching every caller).
  - `update_bar_text` becomes a no-op as well.
  - Mark the file's docstring noting the bar was retired in favor of the event bus + future Phase 3 dashboard.
- At the call site `crackerjack/core/autofix_coordinator.py:3834`, leave the `progress_context(...)` call in place — it's now a no-op but harmless. A follow-up cleanup PR can remove dead call-sites.
- Audit `pyproject.toml` for whether `alive_progress` is now an unused dependency. If no other module uses it, remove it; if any does, leave it.

**Rationale:** the user opted to remove rather than trim. Phase 0's `LoggingSink` keeps users informed via log lines. Phase 3's Rich `Live` dashboard restores rich progress visuals on top of the event bus.

### Task 5 — Tests (~3 hours)

New tests under `tests/core/`:

- `test_ai_fix_event_bus.py` — subscribe/emit ordering, multi-sink fan-out, sink-exception isolation, `new_run_id` uniqueness.
- `test_ai_fix_sinks.py` — `JsonlSink` flushes after each event (kill process mid-stream, assert recoverable JSONL); `LoggingSink` produces the expected log lines for a synthetic event sequence.
- `test_autofix_coordinator_events.py` — run the comprehensive path on a fixture; assert (a) `events.jsonl` contains the expected event sequence, (b) the no-op progress bar emits nothing.

Existing test update: `tests/test_core_autofix_coordinator.py` may need to inject a `MagicMock()` bus for tests that asserted on `logger.info` call counts. Any tests that asserted on `alive_bar` output need updating to expect no bar.

### Task 6 — Documentation (~30 minutes)

- Add a short README to `crackerjack/core/` (or extend the existing one) describing the event bus contract and how to add new sinks. One paragraph + a code snippet.
- Note the JSONL artifact in `CLAUDE.md` under the AI-fix section so future Claude sessions know about `.crackerjack/runs/<run_id>/events.jsonl`.
- Add a `CHANGELOG.md` entry noting bar removal so users aren't surprised.

## Out of scope for Phase 0

- WebSocket sink — Phase 0 leaves the existing WebSocket server untouched. The sink can land in Phase 3 alongside the TUI.
- Any concurrency, any pre-flight expansion, any pool routing.
- Reintroducing visual progress — explicitly deferred to Phase 3.
- Removal of `progress_context` call-sites — left as harmless no-ops so the diff stays small; a cleanup PR can remove them later.

## Validation order

1. `pytest tests/core/test_ai_fix_event_bus.py tests/core/test_ai_fix_sinks.py` (new, fast)
2. `pytest tests/test_core_autofix_coordinator.py` (existing, must still pass)
3. `crackerjack run -t` against a fixture dirty repo → inspect `events.jsonl` manually
4. `crackerjack run` (full quality gate) — ruff, mypy, complexipy, bandit, refurb must all be green
5. Visual check: AI-fix stage runs with no progress bar; log lines remain readable

## Rollback plan

The bus, sinks, and event types are additive modules. The behavior changes are:

1. Replacement of `logger.info` calls inside the comprehensive path with `bus.emit` (still produce log lines via `LoggingSink`).
2. `progress_context` becomes a no-op.

Rollback = revert the coordinator hunks and restore `alive_bar` in `progress_context`. New modules can stay as dead code or be removed in a follow-up.

## Open questions for the user

1. **Bus default sinks** — confirm `LoggingSink + JsonlSink` always-on. JSONL adds ~50KB per run; an opt-out is possible but I argue against (postmortem value is too high).
2. **Run ID format** — happy with 8-char hex (`a7b3c1d4`), or prefer timestamp-prefixed (`2026-05-20-1342-a7b3`)?
3. **`alive_progress` dependency** — remove from `pyproject.toml` if no other module uses it, or leave for now?

## File inventory

**New:**

- `crackerjack/core/ai_fix_events.py`
- `crackerjack/core/ai_fix_event_bus.py`
- `crackerjack/core/ai_fix_sinks.py`
- `tests/core/test_ai_fix_event_bus.py`
- `tests/core/test_ai_fix_sinks.py`
- `tests/core/test_autofix_coordinator_events.py`

**Modified:**

- `crackerjack/core/autofix_coordinator.py` — accept bus, replace `logger.info` calls
- `crackerjack/agents/coordinator.py` — same
- `crackerjack/services/ai_fix_progress.py` — `progress_context` and `update_bar_text` become no-ops; remove `alive_progress` import
- `pyproject.toml` — possibly drop `alive_progress` (subject to dependency audit)
- `CLAUDE.md` — add JSONL artifact note
- `CHANGELOG.md` — note bar removal
