______________________________________________________________________

## status: draft role: implementation date: 2026-07-17 last_reviewed: 2026-07-17 superseded_by: null blocks_on: [] topic: lifecycle

# AI-Fix Comprehensive-Stage Overhaul — Design

- **Status:** Draft for review
- **Author:** brainstormed with Claude (Opus 4.7), session 2026-05-20
- **Scope:** Crackerjack's `_apply_comprehensive_stage_fixes` path and the agent coordinator behind it
- **Non-goals:** Changes to the fast-stage fixer, hook discovery, or pre-commit-stage gating

______________________________________________________________________

## 1. Problem

The comprehensive AI-fix stage in Crackerjack has two pain points:

1. **Wall-clock latency.** Comprehensive runs serialize: `ruff --fix` → `ruff format` → per-issue agent dispatch → re-run hooks → repeat. With 10–40 residual issues, the LLM cost dominates wall-clock and is mostly avoidable.
1. **Observability is brittle.** The current UI is line-by-line `logger.info(...)` from inside the coordinator. Once anything runs concurrently the output is unreadable. Operators cannot answer "which agent is doing what right now?" or "is iteration 3 actually making progress?" from the terminal.

Today's flow (simplified):

```
comprehensive hooks fail
  -> _execute_fast_fixes  (ruff check --fix, ruff format)  [serial subprocess]
  -> _apply_ai_agent_fixes
       per-issue:
         _score_all_specialists   (scans every registered agent)
         _handle_with_single_agent (calls LLM via bridge)
         apply diff
  -> re-run comprehensive hooks
  -> repeat until clean or max_iterations
```

Both problems share a root cause: there is no structured event model, so neither concurrency nor a real UI can be added cleanly.

## 2. Goals

- Reduce comprehensive AI-fix wall-clock by **≥3×** on typical Bodai-ecosystem repos.
- Reduce LLM invocation count by **≥40%** via expanded deterministic pre-flight.
- Replace flat logging with a Rich `Live` dashboard that remains legible under concurrency.
- Preserve the "Crackerjack works standalone" invariant — no hard dependency on Mahavishnu or the other Bodai components.
- Make every behavior change measurable (events emitted, JSONL written per run).

## 3. Non-goals

- Replacing the agent registry or the existing `SubAgent` interface.
- Restructuring `hook_lock_manager.py` beyond extending it with a `FileEditLock`.
- Changing how comprehensive hooks themselves are defined or invoked.
- Building a separate web UI (the existing WebSocket server at port 8686 is reused as-is).

## 4. Design overview

The overhaul ships in four phases, each independently deployable.

| Phase | Theme | What lands | Win |
|------|-------|-----------|-----|
| 0 | Event bus | Structured events, JSONL sink, replaces `logger.info` calls | Foundation |
| 1 | Pre-flight expansion | Configurable static fixers run before any LLM | Fewer LLM calls |
| 2 | Parallel agent dispatch | File-locked, bounded-concurrency agent execution | Wall-clock speed |
| 3 | Rich `Live` TUI | Dashboard subscribed to event bus | Observability |
| 4 | Mahavishnu offload (optional) | Threshold-based pool dispatch | Scaling reserve |

Each phase is a self-contained PR-able unit. The Bodai integrations described in §8 attach to phases 0–4 without changing their core contracts.

## 5. Architecture

### 5.1 Event bus (Phase 0)

A new module `crackerjack/core/ai_fix_events.py` defines:

```python
@dataclass(frozen=True)
class AIFixEvent:
    run_id: str
    ts: float  # monotonic seconds since run start
    iteration: int
    kind: str

@dataclass(frozen=True)
class IterationStarted(AIFixEvent): strategy: str; issue_count: int
@dataclass(frozen=True)
class PreflightStarted(AIFixEvent): tools: list[str]
@dataclass(frozen=True)
class PreflightFinished(AIFixEvent): per_tool: dict[str, dict[str, int]]
@dataclass(frozen=True)
class IssueQueued(AIFixEvent): issue_id: str; hook: str; file: str
@dataclass(frozen=True)
class AgentDispatched(AIFixEvent): issue_id: str; agent: str
@dataclass(frozen=True)
class IssueResolved(AIFixEvent): issue_id: str; agent: str; duration_s: float
@dataclass(frozen=True)
class IssueFailed(AIFixEvent): issue_id: str; agent: str; reason: str
@dataclass(frozen=True)
class IterationFinished(AIFixEvent): resolved: int; failed: int; deferred: int
```

The bus itself is `AIFixEventBus` — async pub/sub, in-memory, with subscriber sinks:

- `LoggingSink` (default) — converts each event back into the equivalent `logger.info` line, preserving today's behavior for CI runs.
- `JsonlSink` — writes every event to `.crackerjack/runs/<run_id>/events.jsonl` for postmortems and replay.
- `MetricsSink` — bumps counters in the existing `performance_tracker.py`.
- `RichLiveSink` (Phase 3) — drives the dashboard.
- `WebSocketSink` (Phase 0/3) — relays to the existing WebSocket server on 8686.

`AutofixCoordinator.__init__` accepts an optional `event_bus` (default: a new instance with `LoggingSink` + `JsonlSink` subscribed). Every existing `self.logger.info("...")` call inside `autofix_coordinator.py` and `agents/coordinator.py` becomes `self.bus.emit(Event(...))`.

### 5.2 Pre-flight fixer (Phase 1)

`crackerjack/core/preflight.py` introduces `PreflightFixer`:

```python
class PreflightFixer:
    def __init__(self, config: PreflightConfig, bus: AIFixEventBus, pkg_path: Path): ...
    async def run(self) -> PreflightReport: ...
```

`PreflightReport` includes per-tool deltas (`files_changed`, `bytes_changed`, `estimated_issues_resolved`). Steps run *sequentially* (they share files) but every step is timed and emitted as a `PreflightFinished` event.

Configuration in `settings/ai_fix.yaml` (new file, loaded by Crackerjack config layer):

```yaml
ai_fix:
  preflight:
    ruff_check: true
    ruff_format: true
    ruff_unsafe_fixes: false
    ruff_select_extra: []          # e.g. ["SIM", "PT", "UP"]
    autoflake_unused: true
    refurb_safe_policies: true
    docformatter: false
    timeout_s: 60
```

After pre-flight, comprehensive hooks are re-run. The set of failing hooks at that point becomes the input to Phase 2.

### 5.3 Parallel agent dispatch (Phase 2)

Three new pieces:

**(a) `FileEditLock` in `executors/hook_lock_manager.py`** — async context manager keyed by `Path.resolve()`. Held during the entire agent invocation for a given file (LLM call + diff application). Two agents on different files run concurrently; two on the same file serialize.

**(b) `IssueClusterer` in `agents/issue_clusterer.py`** — groups residual issues into edit units:

```python
@dataclass
class EditUnit:
    file: Path
    issues: list[Issue]
    primary_hook: str
    estimated_complexity: int
```

Clustering rule: same file → same unit. Two issues in the same file with the same `root_symbol` are still one unit. Unit complexity is the sum of per-issue estimated complexity (used later for scheduling).

**(c) `ParallelDispatcher` in `agents/parallel_dispatcher.py`**:

```python
class ParallelDispatcher:
    def __init__(self, coordinator, locks, bus, max_concurrency=8): ...
    async def dispatch(self, units: list[EditUnit]) -> DispatchResult: ...
```

Implementation: `asyncio.Semaphore(max_concurrency)` + `asyncio.gather(..., return_exceptions=True)`. Each unit:

1. Acquires `FileEditLock(unit.file)`.
1. Emits `AgentDispatched`.
1. Calls `coordinator._handle_with_single_agent(...)`.
1. Applies diff if successful.
1. Emits `IssueResolved` / `IssueFailed`.
1. Releases the lock.

`max_concurrency` defaults to `min(8, os.cpu_count() or 4)` and is configurable via `ai_fix.parallelism.max_concurrency`.

**Early exit:** the dispatcher checks resolution ratio every 5 seconds; if `resolved / total >= 0.5 AND elapsed >= 15s`, it cancels the remaining tasks, releases their locks, and the iteration ends with surviving units deferred to the next iteration.

### 5.4 Rich Live dashboard (Phase 3)

`crackerjack/ui/ai_fix_dashboard.py` defines `AIFixDashboard` — a `RichLiveSink` subscriber that maintains an internal model of the run and renders via `rich.live.Live(refresh_per_second=10, transient=True)`.

Layout:

```
┌─ Crackerjack · Comprehensive AI Fix · run a7b3c1 ─────────────────┐
│ iteration 2/10 · strategy balanced · elapsed 00:42 · ETA ~02:10   │
├───────────────────────────────────────────────────────────────────┤
│ Hook         Issues   Status                                      │
│ zuban           7     ████░░░  4/7 fixed   ⏵ type_specialist       │
│ bandit          3     ███      3/3 fixed   ✔                       │
│ refurb         12     ██░░░░░  2/12 fixed  ⏵ refurb_agent (x3)     │
│ complexipy      4     ░░░░     queued                              │
├───────────────────────────────────────────────────────────────────┤
│ workers 3/8 · subprocesses 1 · cache 64% hits · preflight saved 27 │
└───────────────────────────────────────────────────────────────────┘
last activity: refurb_agent fixed crackerjack/core/app.py:142 (1.8s)
```

Per-issue subprocess stdout/stderr lands in `.crackerjack/runs/<run_id>/<issue_id>.log`. The dashboard surfaces the last line of each active log as the "last activity" hint.

Activation: dashboard is on iff `sys.stdout.isatty() and not env('CI') and not env('CRACKERJACK_NO_TUI')`. CLI flag `--ai-fix-tui=auto|on|off` overrides.

### 5.5 Mahavishnu offload (Phase 4, optional)

`crackerjack/integration/mahavishnu_pool_dispatcher.py` implements the same `Dispatcher` interface as `ParallelDispatcher` but routes via `mcp__mahavishnu__pool_route_execute`. Threshold logic in the coordinator chooses:

```python
def choose_dispatcher(units: list[EditUnit], history: RunHistory) -> Dispatcher:
    if config.parallelism.strategy == "local":
        return ParallelDispatcher(...)
    if config.parallelism.strategy == "mahavishnu_pool":
        return MahavishnuPoolDispatcher(...)
    # auto
    if len(units) >= config.pool_threshold_issues:
        return MahavishnuPoolDispatcher(...)
    if history.estimated_duration_s(units) >= config.pool_threshold_seconds:
        return MahavishnuPoolDispatcher(...)
    return ParallelDispatcher(...)
```

`MahavishnuPoolDispatcher` emits the same events; the TUI works unchanged.

## 6. Data flow

```
comprehensive hooks (initial)
   │ failures
   ▼
PreflightFixer.run()                  ─── PreflightStarted/Finished events
   │ residual failures
   ▼
re-run comprehensive hooks
   │ residual failures
   ▼
IssueClusterer.cluster()              ─── IssueQueued events
   │ EditUnits
   ▼
choose_dispatcher() ── auto/local/pool
   │
   ▼
Dispatcher.dispatch(units)            ─── AgentDispatched / IssueResolved /
   │   file-locked, bounded            IssueFailed events
   │   concurrency
   ▼
re-run comprehensive hooks            ─── IterationFinished event
   │
   └── until clean or max_iterations
```

## 7. Configuration

New `settings/ai_fix.yaml` (merged into existing Crackerjack config):

```yaml
ai_fix:
  events:
    jsonl_sink: true
    websocket_sink: true
  preflight:
    ruff_check: true
    ruff_format: true
    ruff_unsafe_fixes: false
    ruff_select_extra: []
    autoflake_unused: true
    refurb_safe_policies: true
    timeout_s: 60
  parallelism:
    strategy: auto              # local | mahavishnu_pool | auto
    max_concurrency: 8
    early_exit_ratio: 0.5
    early_exit_elapsed_s: 15
    pool_threshold_issues: 12
    pool_threshold_seconds: 30
    pool_url: "http://localhost:8680/mcp"
    pool_selector: "least_loaded"
  tui:
    mode: auto                  # auto | on | off
    refresh_per_second: 10
```

All keys have defaults that preserve current behavior; the file is optional.

## 8. Bodai integrations (additive, opt-in)

Beyond Mahavishnu pools, several other ecosystem features map cleanly onto this work. Each is **opt-in**, **fails open**, and emits events through the same bus so the TUI surfaces them automatically.

### 8.1 Mahavishnu treesitter tools

Mahavishnu exposes `mcp__mahavishnu__treesitter_extract_symbols`, `treesitter_find_usages`, and `treesitter_batch_analyze`. The `IssueClusterer` can use these to refine clusters: two issues on the same `root_symbol` *across files* (e.g. a missing import cascading into 12 zuban errors) become one cluster sent to one agent. Falls back to the file-only clustering when Mahavishnu is unreachable.

### 8.2 Akosha pattern search

`mcp__akosha__search_code_patterns` lets us ask, before invoking an LLM: "Has any repo in the ecosystem fixed an issue with this signature before?" When a high-confidence pattern match exists, the dispatcher can apply the prior fix directly (deterministic) instead of dispatching to an agent. Emits a new `PatternReused` event so the TUI shows how many issues were resolved from prior knowledge.

### 8.3 Session-Buddy reflection and `capture_successful_pattern`

After every `IssueResolved`, the dispatcher posts the `(issue_signature, agent, diff, hook)` tuple to `mcp__session-buddy__capture_successful_pattern`. Closes the loop with §8.2: today's fix becomes tomorrow's deterministic match. Also feeds `mcp__session-buddy__record_fix_success` for learning telemetry.

### 8.4 Dhara persistent fix registry

The captured patterns above persist via `mcp__dhara__put` into an `ai_fix_registry` namespace. Dhara's ACID guarantees mean parallel Crackerjack instances across repos can safely write to the same registry, and `mcp__dhara__record_time_series` tracks duration/success-rate trends per issue type — feeding both the local TUI ETA and the ecosystem-wide quality dashboards.

### 8.5 OpenTelemetry trace ingestion

Each run's `events.jsonl` can be re-emitted as OTel spans into Mahavishnu's `OtelIngester` (`mahavishnu/ingesters/otel_ingester.py`). With pgvector storage, you can semantically search across runs: "show me iterations where refurb_agent took >30s." Useful for performance regression detection without bespoke tooling.

### 8.6 Mahavishnu `pycharm_tools`

For interactive (non-CI) runs, `mcp__mahavishnu__pycharm_list_problems` can supplement comprehensive-hook output with JetBrains-detected issues that pre-commit hooks don't surface. Treat it as an additional pre-flight signal source, not a replacement.

### 8.7 TurboQuant embedding compression

`mahavishnu/ingesters/turboquant_compressor.py` is already wired as a default-on compressor (see commits `45c881f` and `1c1b7b5`). The captured patterns in §8.3/§8.4 use it transparently — embeddings of issue signatures stay compact in shared storage, keeping cross-repo search cheap at scale.

### 8.8 Existing WebSocket server (port 8686)

The Crackerjack WebSocket server at 8686 is already in use. The `WebSocketSink` from §5.1 simply publishes events to existing channels (`workflow:<run_id>`, `global`). No new ports, no new servers. Any consumer — Mahavishnu workflow dashboards, custom browser tools — can subscribe with zero coupling.

### Summary of which Bodai feature lands in which phase

| Bodai feature | Crackerjack phase | Effort |
|---------------|-------------------|--------|
| WebSocket sink (8686) | 0 | Trivial |
| Akosha pattern lookup | 1 (pre-flight extension) | Medium |
| Session-Buddy capture + reflection | 2 (after dispatcher succeeds) | Low |
| Treesitter clustering | 2 (clusterer enhancement) | Medium |
| Dhara persistent registry | 2/3 (alongside capture) | Low |
| OTel ingestion | 3 (postrun) | Low |
| PyCharm problems | 1 (preflight signal) | Low |
| TurboQuant | implicit (via §8.3/§8.4) | None |

All eight are **off by default** and gated behind `ai_fix.bodai.<feature>` config keys. If any Bodai component is unreachable, the relevant call no-ops, emits a `BodaiUnavailable` event, and the pipeline continues.

## 9. Error handling and rollback

- Every agent invocation is wrapped in `try/except`; failures emit `IssueFailed` with the exception class and abbreviated message. Other units proceed.
- Diff application is atomic per file: a `FileEditLock` holder takes a hash of the file before editing; if its diff fails to apply cleanly, the file is restored and the unit is marked failed.
- `JsonlSink` flushes after every event; a crash mid-run leaves a recoverable transcript.
- Mahavishnu/Akosha/Session-Buddy/Dhara calls all use `asyncio.wait_for(..., timeout=5)` and fall back to the local path on timeout.

## 10. Testing strategy

- **Phase 0:** unit tests for `AIFixEventBus` (subscribe/emit ordering, sink lifecycle), `JsonlSink` (write durability under crash), `LoggingSink` (byte-identical to current logger output for a fixed event stream).
- **Phase 1:** golden-file tests — fixture repos with known comprehensive failures; assert `PreflightReport` resolves the deterministic subset and only the LLM-required subset reaches Phase 2.
- **Phase 2:** property-based tests with Hypothesis — generate sets of `EditUnit`s with random file/concurrency configurations, assert no two units edit the same file concurrently, no diffs are lost, and `DispatchResult` accounts for every input unit.
- **Phase 3:** snapshot tests of the rendered dashboard for fixed event sequences (Rich exposes `Console.export_text()`).
- **Phase 4:** integration test that spawns a `MahavishnuPool` locally and confirms the dispatcher produces identical `DispatchResult` to local mode for the same inputs.

Regression baseline: a fixture suite of 10 Bodai repos at known dirty states. Each phase must (a) not regress the fix success rate, and (b) hit its wall-clock target on this suite.

## 11. Risks and open questions

1. **Diff conflicts inside a single file when one agent fixes multiple issues.** Mitigation: cluster all issues for one file into one agent invocation (already in design), but the LLM still has to produce one coherent patch.
1. **Subprocess stdout under Rich `Live`.** Mitigation: redirect to per-issue log files; surface last line in the dashboard.
1. **Pattern-reuse correctness (§8.2).** A "matching" prior fix may not be safe in a new context. Mitigation: confidence threshold + always re-run the relevant comprehensive hook after applying a reused pattern.
1. **Phase 2's early-exit could starve slow agents.** Mitigation: deferred units carry forward to the next iteration with strategy-aware priority; they don't disappear.
1. **Open question:** should `max_iterations` change in light of much-faster iterations? Current default may now allow too many cycles. Recommend re-tuning after Phase 2 data is in.

## 12. Rollout plan

1. **Land Phase 0** behind no flag — purely additive event bus, zero behavior change.
1. **Land Phase 1** behind `ai_fix.preflight.*` config — defaults preserve current behavior. Enable `ruff_select_extra` on a single Bodai repo first to validate.
1. **Land Phase 2** behind `ai_fix.parallelism.strategy=local` with `max_concurrency=1` as default, then raise to 8 after a soak.
1. **Land Phase 3** with `tui.mode=off` default; flip to `auto` after dogfooding.
1. **Land Phase 4** with `strategy=auto` only after Mahavishnu pool routing is exercised in a non-Crackerjack workflow first.

## 13. Success metrics

- Wall-clock for comprehensive AI fix on a 10-repo benchmark: ≥3× faster (target), ≥2× faster (acceptable).
- LLM invocation count: ≥40% reduction (target), ≥25% (acceptable).
- TUI lighthouse: zero overlapping-output complaints in dogfood week; subjective "looks better" from at least three users.
- Cross-repo pattern reuse rate (§8.2): trend upward over four weeks of capture.

## 14. Appendix — files touched

New:

- `crackerjack/core/ai_fix_events.py`
- `crackerjack/core/preflight.py`
- `crackerjack/agents/issue_clusterer.py`
- `crackerjack/agents/parallel_dispatcher.py`
- `crackerjack/integration/mahavishnu_pool_dispatcher.py` (Phase 4)
- `crackerjack/ui/ai_fix_dashboard.py`
- `crackerjack/integration/bodai/{akosha,dhara,session_buddy,treesitter}.py`
- `settings/ai_fix.yaml`

Modified:

- `crackerjack/core/autofix_coordinator.py` — accept `event_bus`, replace `logger.info` calls
- `crackerjack/agents/coordinator.py` — same, plus dispatcher injection
- `crackerjack/executors/hook_lock_manager.py` — add `FileEditLock`
- `crackerjack/websocket/server.py` — add channel for `ai_fix` events
- `crackerjack/cli/*` — add `--ai-fix-tui` and `--ai-fix-strategy` flags
