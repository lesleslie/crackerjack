---
title: Stop the Gate Killing Healthy Test Runs, and Stop It Rewriting the Plan Index
description: The gate's test phase reported "Total Tests 0" and killed healthy runs at 60 seconds, because the executor treated an empty read on a non-blocking pipe as end-of-stream and measured its stall detector from the start of the run rather than from the last output; and plan_index_sync emitted a plan index that mdformat rewrote on every run, because the generator did not produce formatter-stable output. Both are fixed and pinned by tests.
audience: crackerjack maintainer
created: 2026-11-07
status: active
role: implementation
topic: quality-gate
date: 2026-11-07
last_reviewed: 2026-11-07
superseded_by: null
blocks_on: []
---

# Gate Timeout and Plan-Index Stability

Two defects that made the quality gate lie about itself. Both are in the
gate's own machinery, not in the code being checked, which is why they
survived so long: in each case the gate reported a *result* rather than
failing to produce one.

## 1. The test phase killed healthy runs and lost their output

### Symptom

The gate's test phase reported `Total Tests 0` and "Failed test
execution", with every comprehensive hook failing at once:

```
FileNotFoundError: [Errno 2] No such file or directory
```

and, separately, a parallel run that was killed at exactly 60 seconds
and reported as a timeout:

```
DEBUG: parallel_result.returncode=-1, _did_xdist_timeout=True
⚠️ Parallel execution timed out or failed, falling back to sequential...
```

### Root cause

Three things compounded, and each one alone would have been survivable.

**a. An empty read was treated as end-of-stream.** The executor reads
the child's stdout on a *non-blocking* pipe. On such a pipe `readline()`
returns `""` whenever the writer has not produced a complete line yet
-- which is the normal state between two tests, and during collection.
The reader did:

```python
line = self._read_line_with_timeout(stdout, timeout)
if not line:
    break          # ← an empty read was read as EOF
```

Measured on this tree (`readline()` on an `O_NONBLOCK` pipe with no data
pending): it returns `''`. It does not raise `EAGAIN`, so the
`except IOError` branch below never ran.

The read loop therefore ended at the *first gap in output*. Everything
after that was lost: the per-test counts never arrived, the run state
was never written, and the still-running process was left to be dealt
with by the completion timeout.

**b. The stall detector measured from the start of the run.** The
timestamp that says "when did we last see output" was updated inside
`_process_line`, which received it *by value*:

```python
def _process_line(self, line, ..., last_output_time: float) -> None:
    ...
    last_output_time = time.time()   # ← updates a local copy only
```

The caller's `last_output_time` never moved. So
`elapsed_since_output > timeout` was really
`elapsed_since_start > timeout`, and the detector terminated any run
that took longer than the timeout -- no matter how much output it was
producing. Ruff had been flagging the dead assignment (F841) all along;
the gate's ruff hook auto-fixes it, which is why it never reached a
reviewer as a defect.

**c. One number served as three budgets.** `xdist_timeout_seconds`
(60) was used as the stall budget, as the total budget for the parallel
attempt (`process.wait(timeout=...)`), and as the budget for the
sequential retry's *total* runtime. A slow-but-healthy run and a hung
run were indistinguishable, because "slow" and "hung" were the same
test.

**d. The failure heuristic matched every healthy run.** The fallback
also looked for the bare words `"xdist"`, `"timeout"` and `"hung"` in
the output. pytest prints its plugin list in its own header:

```
plugins: cov-7.1.0, testmon-2.3.0, xdist-3.8.0, timeout-2.4.0, ...
```

so *both* `"xdist"` and `"timeout"` match every run — the header names
the xdist plugin and the pytest-timeout plugin. The heuristic was
dormant only because the reader dropped the output; with the reader
fixed it would have classified every successful parallel run as a
failure, thrown the result away, and re-run the whole suite
sequentially. The indicators have to name the failure: `worker
crashed`, `workers did not finish`, `node down`, `worker timeout`.

### Measurement

The output cadence of a real parallel run, measured on this tree:

| Moment | Elapsed |
|---|---|
| first output (pytest's session header) | **69.5 s** |
| run finished | 70.0 s |

So the normal silence before the first line is ~70 s: `uv run` resolves
the environment, pytest imports, and the workers collect. A 60 s stall
budget cannot survive that, which is why every parallel run was
terminated. 300 s is comfortably above it.

### Fix

- `_read_stdout_loop` and `_read_stderr_loop` treat an empty read as
  "nothing right now". Only a terminated process means end-of-stream.
- `_process_line` returns the refreshed timestamp so the caller
  actually sees it, and the stall detector measures from the last
  output.
- The two budgets are separated. `timeout` is the run's total budget;
  `stall_timeout` is how long the run may be *silent* before it is
  treated as hung. The parallel attempt gets the same total budget as
  the sequential one, so it is never killed for being slow.
- `xdist_timeout_seconds` becomes `xdist_stall_timeout_seconds`
  (60 → 300), sized from the measurement above.
- The failure indicators name the failure instead of the tool.

### Known limit

`--dist=loadfile` gives each worker whole files, so an incremental
selection that touches fewer files than there are workers starves some
of them, and xdist raises `RuntimeError: Unexpectedly no active workers
available`. That is an INTERNALERROR (exit 3), which the exit-code
fallback already routes to a sequential retry — correctly, but the
parallel attempt is then wasted work. Capping the worker count by the
selection size is a separate change.

### Verification

`tests/unit/managers/test_xdist_fallback.py` gains a class that runs a
real child process which prints, pauses for a second, and prints again:
both lines must be captured and the exit code must be 0. That test
fails against the old reader, which drops the second line. A second
class pins the failure indicators: a healthy run whose header merely
mentions `xdist` and `timeout` must not be classified as a failure.

## 2. `plan_index_sync` and mdformat disagreed about the same file

### Symptom

Every gate run left `docs/plans/PLAN_INDEX.md` dirty:

```
-| Role \ Lifecycle | draft | active | ... |
+| Role \\ Lifecycle | draft | active | ... |
```

The file changed on every run, and in whichever direction the last tool
to touch it left it.

### Root cause

The generator emitted a single backslash in the distribution table
header; mdformat -- the repo's formatter, and a gate hook over `docs/`
-- escapes it to two. The generator also left a blank line at the end of
the file, which mdformat strips.

Both are the same defect seen from two sides: **the generator was not
producing formatter-stable output.** A generated file has to be what the
formatter would produce, or the two tools will fight over it forever.

Verified that mdformat is idempotent on the escaped form: running it
twice leaves the file unchanged.

### Fix

- The header emits the escaped form.
- The trailing blank line is gone, so the file ends with a single
  newline.

### Verification

`tests/unit/test_plan_index_sync.py::test_rendered_output_survives_mdformat_unchanged`
renders the index, runs it through `mdformat.text()`, and asserts the
two are byte-identical. The test fails against the old generator. This
is the strongest available guard: it fails if *either* side drifts.

## Integration Contract

- **Triggered from**: `crackerjack run -v -t` (test phase) and the
  `mdformat` fast hook.
- **Returns to / updates**: the test phase's exit code and per-test
  counts; `docs/plans/PLAN_INDEX.md`.
- **Demonstrable by**: `crackerjack run -v -t` reporting a non-zero
  test count, and a second consecutive run leaving the tree clean.
- **Rollback signal**: the test phase reporting `Total Tests 0` again,
  or `PLAN_INDEX.md` differing after a run.
- **Observability added**: the parallel attempt now prints its stall
  timeout and its run budget separately, so "was it killed for being
  slow or for being hung?" is answerable from the log.

## Out of scope

The 21 test failures that `main` already has (protocol `runtime_checkable`
asserts, a stale hardcoded tool count, a renamed `mypy_timeout` field,
doc drift, MCP stub drift). They predate this work and are a separate
change.
