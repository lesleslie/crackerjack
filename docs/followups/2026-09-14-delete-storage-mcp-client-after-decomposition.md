---
status: complete
role: implementation
topic: integration
date: 2026-09-14
last_reviewed: 2026-09-20
superseded_by: null
blocks_on: []
related:
  - "mahavishnu/docs/plans/2026-09-14-bodai-serverless-readiness-and-component-substitution.md"
---

# Delete the storage MCP client module after Phase 8

**Date:** 2026-09-14
**Pairs with:** commit `47a17617` (`refactor(integration): migrate the storage + session-buddy MCP clients to CommonMCPClient`) which deprecated the module's docstring.

## Why

The standalone KV-backed storage MCP server was being absorbed into
Mahavishnu, Oneiric, AkoSHA, and Crackerjack under the phase-3
decomposition design. Phase 8 of that design retires the server
entirely; no deprecation window (per Bodai pre-1.0 policy and the
design's §4.9 hard-cutover stance).

The storage MCP client module under `crackerjack/integration/` was the
sole in-tree consumer at the transport layer — every other crackerjack
module that talked to that server went through it. So the design's
"every consumer updated in the same commit as the tool's deletion" rule
collapsed to a single in-repo change here.

## What to delete

In a single commit, alongside Phase 8 of the decomposition design:

1. **Delete the storage MCP client module.** It was the only place that
   defined the storage MCP client and its config dataclass.
2. **Production callers** (replace against the Mahavishnu tools; do not shim):
   - `crackerjack/services/failure_metrics_repository.py` — imported the
     storage MCP client for type-hinting; the `record()` and
     `count_similar()` paths need replacement against
     `mcp__mahavishnu__upsert_service` and
     `mcp__mahavishnu__record_event` (per design §4.2 line 91-94).
     Best-effort semantics (return 0 / None on failure) preserved with a
     wrapper around the new SDK.
   - `crackerjack/integration/adapter_learning.py` — imported the storage
     MCP client and its config at the top, and used them in the
     MCP-backed adapter learner. The config loader should switch to
     returning a no-op stub (analogous to the existing
     `NoOpAdapterLearner`) rather than a disabled-config dataclass.
3. **Test files** (delete or rewrite):
   - the storage MCP client test module
   - the MCP-backed adapter learner test module
   - the storage integration test module (the file's other tests that
     don't touch the MCP client may survive)

`crackerjack/integration/__init__.py` does NOT re-export the storage MCP
client or its config class as of the write of this followup (line 18
re-exports `AdapterAttemptRecord` etc. instead). Run
`grep -n "MCPClient" crackerjack/integration/__init__.py` before commit to
confirm nothing has crept in.

## Verification

- `git grep -n "storage_mcp_client" crackerjack/` returns zero hits (no
  stale references).
- `git grep -n "mcp__<storage-server>__" crackerjack/` returns zero hits
  (the only pre-existing matches were in `CHANGELOG.md` archival entries
  and the now-deprecated module docstring).
- The client test module is gone — `pytest` on it exits 1 (file gone) — or
  0 if replaced.
- `crackerjack/python -m audit_orphans.py` shows no new orphans.

## Risks

- **Cross-repo coupling:** the config/client type names leak into the
  public surface via `crackerjack.config.settings`. A deprecation alias in
  the integration directory (e.g. `class StorageMCPConfig(NotImplementedError): pass`)
  keeps imports working for one release cycle if downstream scripts reach
  into crackerjack's python API. Decide based on whether crackerjack
  publishes its integration layer; default to "no alias" per Bodai
  pre-1.0 policy.
- **Test fixtures may reference the disabled config:** the storage
  integration test constructs a disabled client config to verify the
  no-op path; if the migration target is Mahavishnu, replace with a
  `NoOp*` stub.

## Trigger

Execute this followup **in the same commit as Phase 8 of the
decomposition design**. Hard cutover: no deprecation window, no flag, no
backward-compat shim (per project policy and the design's §4.10
historical-data retention table).

If Phase 8 ships before this commit lands, the client's `connect()` calls
all start returning False because the server is gone — make it safe to do
so (`failure_metrics_repository.record()` already handles "storage
unavailable" gracefully at line 41-46, and the adapters in
`adapter_learning.py` log-and-skip rather than raise). So if scheduling
slips, no urgent runtime breakage.
