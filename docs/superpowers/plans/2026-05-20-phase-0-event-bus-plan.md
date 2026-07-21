______________________________________________________________________

## status: active role: implementation date: 2026-07-17 last_reviewed: 2026-07-17 superseded_by: null blocks_on: [] topic: lifecycle

# Phase 0 Implementation Plan — AI-Fix Event Bus

- **Status:** Reviewed — ready for implementation
- **Reviewed by:** 3 parallel agents (architecture, code quality, test strategy) 2026-05-20
- **Spec:** [`docs/superpowers/specs/2026-05-20-ai-fix-comprehensive-overhaul-design.md`](../specs/2026-05-20-ai-fix-comprehensive-overhaul-design.md) §5.1
- **Scope:** Phase 0 only. No behavior changes from the user's perspective; foundation for Phases 1–4.
- **Estimated effort:** 1.5–2 days (Task 3 re-estimated after logger.warning audit; see note)
- **Risk:** Low

## Goal

Introduce a structured event model for the AI-fix stage. Every existing `logger.info(...)` and `logger.warning(...)` call inside the autofix coordinator and agent coordinator (comprehensive path only) becomes `bus.emit(EventType(...))`. Default sinks reproduce today's logger output and write a JSONL transcript. No user-visible change except:

1. A new `.crackerjack/runs/<run_id>/events.jsonl` artifact appears per run.
1. The `alive_progress` bar in the AI-fix stage is **removed**.

Note: `AIFixProgressManager`'s Rich panel methods (`start_fix_session`, `start_iteration`, `_render_header_panel`, `_render_footer_panel`, etc.) are **not** part of the alive_progress bar — they produce separate Rich console output and are **preserved unchanged** in Phase 0. Only the `alive_bar` call inside `progress_context` is removed.

## Acceptance criteria

1. `crackerjack run -t` on a fixture repo with comprehensive failures produces an `events.jsonl` with every iteration's lifecycle captured.
1. Stdout under default config matches pre-change output for every line that isn't the removed `alive_bar` progress bar. Rich panel output from `AIFixProgressManager` is unchanged.
1. The `alive_progress` bar no longer renders during the AI-fix stage.
1. New unit tests pass; no existing tests regress (including the patched `progress_manager.log_event` sites in `test_core_autofix_coordinator.py:549,608,662`).
1. `ruff`, `mypy`, and the project's complexity gate all pass on new files.

## Work breakdown

### Task 1 — Event types and bus (~3 hours)

Create `crackerjack/core/ai_fix_events.py`.

**Critical:** do NOT use `field(init=False)` for `kind` on a frozen dataclass base with inheritance — Python's dataclass machinery breaks at runtime and mypy strict rejects it. Use `ClassVar[str]` instead, which is a class discriminant, not per-instance state.

```python
from __future__ import annotations
import time
import uuid
from dataclasses import dataclass, field
from typing import ClassVar

@dataclass(frozen=True)
class AIFixEvent:
    run_id: str
    iteration: int
    ts: float = field(default_factory=time.time)   # wall-clock, not monotonic

@dataclass(frozen=True)
class RunStarted(AIFixEvent):
    kind: ClassVar[str] = "run_started"
    config_snapshot: dict[str, object] = field(default_factory=dict)

@dataclass(frozen=True)
class IterationStarted(AIFixEvent):
    kind: ClassVar[str] = "iteration_started"
    strategy: str = ""
    issue_count: int = 0

# ... PreflightStarted, PreflightFinished,
#     IssueQueued, AgentDispatched, IssueResolved, IssueFailed,
#     IterationFinished, RunFinished
```

Use `time.time()` (wall-clock) not `time.monotonic()` so JSONL timestamps are human-readable in postmortems. Use frozen dataclasses for hashability and safety under the future Phase 2 concurrent context.

Then `crackerjack/core/ai_fix_event_bus.py`:

```python
from __future__ import annotations
import logging
from typing import Protocol
import uuid
import datetime

class Sink(Protocol):
    async def handle(self, event: AIFixEvent) -> None: ...

class AIFixEventBus:
    def __init__(self) -> None:
        self._sinks: list[Sink] = []
        self._logger = logging.getLogger(__name__)

    def subscribe(self, sink: Sink) -> None:
        self._sinks.append(sink)

    def unsubscribe(self, sink: Sink) -> None:
        self._sinks.remove(sink)

    async def emit(self, event: AIFixEvent) -> None:
        for sink in self._sinks:
            try:
                await sink.handle(event)
            except Exception:
                self._logger.exception("Sink %s raised on event %s", type(sink).__name__, type(event).__name__)

    def new_run_id(self) -> str:
        ts = datetime.datetime.now().strftime("%Y-%m-%d-%H%M")
        return f"{ts}-{uuid.uuid4().hex[:4]}"
```

**Run ID format:** `2026-05-20-1342-a7b3` — timestamp-prefixed for chronological sorting of `.crackerjack/runs/`.

**Why async emit + per-sink try/except:** Phase 2 will have concurrent agents calling `emit` from many tasks. Sync emit would force every concurrent task to serialize behind sink I/O. Per-sink exception isolation means a flaky WebSocket can't break the JSONL transcript.

### Task 2 — Default sinks (~3 hours)

Create `crackerjack/core/ai_fix_sinks.py`:

**`LoggingSink`** — receives events, formats them as the pre-existing log lines, calls `logger.info`. Goal: preserve today's stdout for the default config. Implement event-to-string formatters as a `dict[str, Callable]` keyed on `event.kind` (not a match statement — simpler under complexipy).

**`JsonlSink`** — async file writer. **Opens its file lazily on the first `RunStarted` event**, not at construction, because the `run_id` used in the path is not known at bus construction time. File path: `.crackerjack/runs/<run_id>/events.jsonl`. Creates the directory with `parents=True, exist_ok=True`. Serializes with `json.dumps(dataclasses.asdict(event), default=str)` — the `default=str` handles `Path`, `Enum`, `datetime`, and other non-JSON-serializable field types (mirrors the existing pattern at `autofix_coordinator.py:273`). Flushes after every write.

**`MetricsSink`** — no-op stub: `async def handle(self, event: AIFixEvent) -> None: return`. Phase 1 fills it in. Must be a no-op (not `NotImplementedError`) — it is subscribed by default.

### Task 3 — Wire the bus through coordinators (~6 hours, re-estimated)

Re-estimated from 4h to 6h: full audit of `autofix_coordinator.py` shows ~15 `logger.warning` calls in addition to `logger.info` inside the comprehensive path — significantly more than the original ~12 total count.

**Pre-task audit (do first, before touching code):** grep both coordinator files for `self.logger.info\|self.logger.warning` inside the comprehensive path. Document the complete list before starting replacements.

Modify `crackerjack/core/autofix_coordinator.py`:

- Add optional `event_bus: AIFixEventBus | None = None` to `AutofixCoordinator.__init__`. If `None`, construct a default bus with `LoggingSink` + `JsonlSink` + `MetricsSink` subscribed. Construct the default **lazily** — inside `apply_autofix_for_hooks`, not `__init__` — so tests can inject a fake bus without the default being created first.
- Set `self._run_id = self.bus.new_run_id()` at the top of `apply_autofix_for_hooks`.
- Replace each `self.logger.info(...)` and `self.logger.warning(...)` in the comprehensive path with `await self.bus.emit(Event(...))`.
- **Leave untouched:** `self.logger` calls in the fast path, `_run_fix_command`, `_handle_command_result`, and any code outside the comprehensive stage.

Modify `crackerjack/agents/coordinator.py`:

- Accept same bus via constructor injection.
- Replace `logger.info(f"Handling {len(issues)} issues ...")` → `IterationStarted` emit.
- Replace per-agent `logger.info(...)` → `AgentDispatched` / `IssueResolved` / `IssueFailed`.

**Existing test patch sites — must update (not ignore):**

`tests/test_core_autofix_coordinator.py` patches `progress_manager.log_event` at lines 549, 608, 662. After Phase 0, those patches intercept nothing and tests silently pass while covering nothing. Update these tests to assert against `bus.emit` call counts via an injected `MagicMock`-backed bus, or assert on `LoggingSink` output captured via `caplog`.

### Task 4 — Remove the `alive_progress` bar (~1 hour)

**Sequencing is critical — follow this order:**

1. Remove the `alive_bar` import from `crackerjack/services/ai_fix_progress.py:10`.
1. Replace `progress_context` with a no-op `@contextmanager` that yields `None` (keeps call-site API stable).
1. Make `update_bar_text` a no-op.
1. Update the call site `crackerjack/core/autofix_coordinator.py:3834` — leave `progress_context(...)` call in place, it now yields `None` harmlessly.
1. **Only after steps 1–4 pass `ruff`/`mypy`:** audit `pyproject.toml` for any other consumers of `alive_progress`. Grep confirms `ai_fix_progress.py:10` is the only import. Remove `alive-progress` from `pyproject.toml` dependencies and run `uv sync` to verify the lock file updates cleanly.

**Scope note:** `AIFixProgressManager`'s remaining methods (`start_fix_session`, `start_iteration`, `end_iteration`, `_render_header_panel`, `_render_footer_panel`, `_neon_print`) are Rich-based console output — they are **not** alive_progress and are **not** touched. Only the `alive_bar` call inside `progress_context` is removed.

### Task 5 — Tests (~4 hours, expanded from 3h)

New tests under `tests/core/`:

**`test_ai_fix_event_bus.py`:**

- Subscribe/emit ordering: two sinks, assert both receive events in subscription order.
- Sink-exception isolation: first sink raises, assert second sink still receives the event.
- Zero-sink emit: no error.
- `new_run_id` format: matches `YYYY-MM-DD-HHMM-xxxx` pattern and is unique across 1000 calls.
- Concurrent `emit`: assert no deadlock / no dropped events under `asyncio.gather` with 20 concurrent emitters.

**`test_ai_fix_sinks.py`:**

- `JsonlSink` lazy open: no file created before first `RunStarted` event; file exists after.
- `JsonlSink` directory creation: sink with path under non-existent parent creates it (`parents=True`).
- `JsonlSink` JSONL durability: write N events, drop sink without graceful flush, reopen file, assert each line parses as valid JSON (do NOT use kill/SIGKILL — write events then let sink go out of scope, then reopen).
- `JsonlSink` non-serializable fields: `config_snapshot` containing a `Path` serializes without error (tests `default=str`).
- `LoggingSink` output: for a synthetic 3-event sequence, assert `caplog` contains the expected message strings.
- `MetricsSink` stub: `handle(event)` returns without raising.

**`test_autofix_coordinator_events.py`:**

- Inject a recording bus (thin list-appending sink), run comprehensive path on a fixture, assert emitted event sequence matches the spec §5.1 event list **in order** (not just "contains").
- No `alive_bar` output: assert no line in captured stdout contains `"⚡"` or `"█"`.
- Existing `progress_manager.log_event` patch sites (lines 549, 608, 662): rewrite to inject recording bus and assert corresponding event types are emitted instead.

**Integration test audit (pre-task):** search `tests/` for assertions on `"⚡"`, `"AI-FIX"`, `alive_bar` output glyphs. Update any found before Phase 0 is considered done.

### Task 6 — Documentation (~30 minutes)

- Add a short README section to `crackerjack/core/` describing the event bus contract and how to add a new sink (one paragraph + snippet).
- Note the JSONL artifact path in `CLAUDE.md` so future sessions know about `.crackerjack/runs/<run_id>/events.jsonl`.
- Add `CHANGELOG.md` entry noting `alive_progress` bar removal and the new JSONL run transcript.

## Out of scope for Phase 0

- WebSocket sink — deferred to Phase 3.
- Any concurrency, pre-flight expansion, pool routing.
- Reintroducing visual progress — deferred to Phase 3 (Rich Live dashboard).
- Removal of `progress_context` call-sites — left as harmless no-ops; cleanup PR later.
- `start_fix_session`, `start_iteration`, Rich panel methods in `AIFixProgressManager` — untouched.

## Validation order

1. Full logger/warning audit on both coordinator files (pre-task, not post-task).
1. Integration test audit for alive_bar output assertions.
1. `pytest tests/core/test_ai_fix_event_bus.py tests/core/test_ai_fix_sinks.py` (new, fast).
1. `pytest tests/test_core_autofix_coordinator.py` — must pass, including the rewritten patch-site tests.
1. `crackerjack run -t` against a fixture dirty repo → inspect `events.jsonl`, confirm timestamps are human-readable, confirm no `alive_bar` output.
1. `crackerjack run` (full quality gate) — ruff, mypy, complexipy, bandit, refurb all green.

## Rollback plan

The bus, sinks, and event types are additive modules. The behavior changes are:

1. Replacement of `logger.info`/`logger.warning` calls inside the comprehensive path with `bus.emit` (still produce log lines via `LoggingSink`).
1. `progress_context` becomes a no-op.
1. `alive_progress` dep removed.

Rollback = revert coordinator hunks + restore `alive_bar` in `progress_context` + re-add dep to `pyproject.toml`. New modules can stay as dead code.

## Resolved decisions (from open questions)

1. **Bus default sinks:** `LoggingSink + JsonlSink + MetricsSink` always-on. No opt-out.
1. **Run ID format:** timestamp-prefixed `2026-05-20-1342-a7b3` for sortable `.crackerjack/runs/` directories.
1. **`alive_progress` dep:** remove from `pyproject.toml` after confirming no other consumers (only import is `ai_fix_progress.py:10`).

## File inventory

**New:**

- `crackerjack/core/ai_fix_events.py`
- `crackerjack/core/ai_fix_event_bus.py`
- `crackerjack/core/ai_fix_sinks.py`
- `tests/core/test_ai_fix_event_bus.py`
- `tests/core/test_ai_fix_sinks.py`
- `tests/core/test_autofix_coordinator_events.py`

**Modified:**

- `crackerjack/core/autofix_coordinator.py` — accept bus, replace comprehensive-path `logger.info`/`warning` calls
- `crackerjack/agents/coordinator.py` — same
- `crackerjack/services/ai_fix_progress.py` — `progress_context` + `update_bar_text` → no-ops; remove `alive_bar` import
- `pyproject.toml` — remove `alive-progress` dependency
- `tests/test_core_autofix_coordinator.py` — rewrite `progress_manager.log_event` patch sites (lines 549, 608, 662)
- `CLAUDE.md` — add JSONL artifact note
- `CHANGELOG.md` — note bar removal and JSONL transcript
