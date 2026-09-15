---
status: draft
role: implementation
topic: integration
date: 2026-09-14
last_reviewed: 2026-09-14
superseded_by: null
blocks_on:
  - "mahavishnu/docs/superpowers/specs/2026-09-14-dhara-mcp-decomposition-design.md#phase-8"
related:
  - "mahavishnu/docs/plans/2026-09-14-bodai-serverless-readiness-and-component-substitution.md"
---

# Delete `crackerjack/integration/dhara_mcp_client.py` after Phase 8

**Date:** 2026-09-14
**Pairs with:** commit `47a17617` (`refactor(integration): migrate dhara + session-buddy MCP clients to CommonMCPClient`) which deprecated the module's docstring.

## Why

The Dhara MCP server is being absorbed into Mahavishnu, Oneiric, AkoSHA, and Crackerjack per `mahavishnu/docs/superpowers/specs/2026-09-14-dhara-mcp-decomposition-design.md`. Phase 8 of that spec retires the server entirely; no deprecation window (per Bodai pre-1.0 policy and the spec's §4.9 hard-cutover stance).

`crackerjack/integration/dhara_mcp_client.py` is the sole in-tree consumer at the transport layer — every other crackerjack module that talks to Dhara goes through it. So the spec's "every consumer updated in the same commit as the tool's deletion" rule collapses to a single in-repo change here.

## What to delete

In a single commit, alongside Phase 8 of the decomposition spec:

1. **Delete `crackerjack/integration/dhara_mcp_client.py`.** The module is the only place that defines `DharaMCPClient` and `DharaMCPConfig`.
2. **Production callers** (replace against the Mahavishnu tools; do not shim):
   - `crackerjack/services/failure_metrics_repository.py:10` — imports `DharaMCPClient` for type-hinting; the `record()` and `count_similar()` paths need replacement against `mcp__mahavishnu__upsert_service` (was `dhara_upsert_service`, per spec §4.2 line 91-94) and `mcp__mahavishnu__record_event` (was `dhara_record_event`). Best-effort semantics (return 0 / None on failure) preserved with a wrapper around the new SDK.
   - `crackerjack/integration/dhara_integration.py:18` — imports `DharaMCPClient` and `DharaMCPConfig` at the top, uses them in `DharaMCPAdapterLearner`. `_load_dhara_mcp_config()` should switch to returning a no-op stub (analogous to the existing `NoOpAdapterLearner`) rather than a `DharaMCPConfig(enabled=False)` dataclass.
3. **Test files** (delete or rewrite):
   - `tests/integration/dhara_mcp_client_test.py` (refs at `:18`, `:202`, `:216`)
   - `tests/integration/dhara_mcp_adapter_learner_test.py:18`
   - `tests/integration/test_dhara_integration.py:18` (specific references; the file's other Dhara-related tests that don't touch `DharaMCP*` may survive)

`crackerjack/integration/__init__.py` does NOT re-export `DharaMCPClient`/`DharaMCPConfig` as of the write of this followup (line 18 re-exports `AdapterAttemptRecord` etc. instead). Run `grep -n DharaMCP crackerjack/integration/__init__.py` before commit to confirm nothing has crept in.

## Verification

- `git grep -n DharaMCPClient crackerjack/` returns zero hits (no stale references).
- `git grep -n mcp__dhara__ crackerjack/` returns zero hits (the only pre-existing match was in `CHANGELOG.md` archival entries and the now-deprecated module docstring).
- `pytest tests/integration/dhara_mcp_client_test.py` exits 1 (file gone) — or 0 if replaced.
- `crackerjack/python -m audit_orphans.py` shows no new orphans.

## Risks

- **Cross-repo coupling:** the `DharaMCPConfig`/`DharaMCPClient` type names leak into the public surface via `crackerjack.config.settings`. A deprecation alias in the integration directory (e.g. `class DharaMCPConfig(NotImplementedError): pass`) keeps imports working for one release cycle if downstream scripts reach into crackerjack's python API. Decide based on whether crackerjack publishes its integration layer; default to "no alias" per Bodai pre-1.0 policy.
- **Test fixtures may reference `enabled=False` config:** `tests/integration/test_dhara_integration.py:402,438,473,583,606,633` constructs `DharaMCPConfig(enabled=False)` to verify the no-op path; if migration target is Mahavishnu, replace with a `NoOp*` stub.

## Trigger

Execute this followup **in the same commit as Phase 8 of the Dhara decomposition spec**. Hard cutover: no deprecation window, no flag, no backward-compat shim (per project policy and the spec's §4.10 historical-data retention table).

If Phase 8 ships before this commit lands, the `DharaMCPClient.connect()` calls all start returning False because Dhara is gone — make it safe to do so (`failure_metrics_repository.record()` already handles "Dhara unavailable" gracefully at line 41-46, and the adapters in `dhara_integration.py` log-and-skip rather than raise). So if scheduling slips, no urgent runtime breakage.
