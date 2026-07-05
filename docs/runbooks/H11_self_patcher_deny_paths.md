# H11 — SELFPATCHER_DENY_PATHS missing 10 critical files

**Audit finding**: HANDOFF.md (2026-06-26 audit, lines 116-148).
**Severity**: High.
**Affected module**: `crackerjack/services/self_patcher.py`.
**Status**: Fixed 2026-06-27.

## Problem

`SELFPATCHER_DENY_PATHS` is the trust gate that decides whether an
auto-generated `ImprovementProposal` diff may be applied to Crackerjack's own
working tree. Before this fix it only listed the canonical crackerjack-specific
paths (`crackerjack/services/self_patcher.py`, `pyproject.toml`, etc.). That
left 10 critical paths unprotected, including:

| Path kind | Example |
|--------------------------|--------------------------------------------|
| Failure metrics repo | `*failure_metrics_repository.py` |
| Constitution | `*constitution.py` |
| Overseer | `*overseer.py` (e.g. `improvement_overseer.py`) |
| Hooks | `*hooks.py` (e.g. `crackerjack/config/hooks.py`) |
| Config tree | Anything under `*/config/` |
| Security tree | Anything under `*/security/` |
| Settings tree | Anything under `*/settings/` |
| MCP server config | Any path containing `mcp_server` |
| Env file | `.env` |
| Build manifest | `pyproject.toml` |

The original list also used exact-path matching, which only protected files
in this repo — it could not protect the same logical files when `SelfPatcher`
runs against a sibling repo (mahavishnu, akosha, dhara, session-buddy).

## Resolution

The deny list is now pattern-based. The matcher (`_path_matches_deny`) handles
four pattern styles:

1. **Directory prefix** (entry ends in `/`) — matches anything under that tree.
   Example: `config/` matches `crackerjack/config/anything.py`,
   `mahavishnu/config/anything.py`, etc.
1. **Basename match** — entry compared against the path's basename.
   Example: `hooks.py` matches `crackerjack/config/hooks.py`,
   `mahavishnu/config/hooks.py`, `anything/hooks.py`.
1. **Path fragment substring** — entry is searched for anywhere in the path.
   Example: `mcp_server` matches `crackerjack/mcp_server_config.json`,
   `mahavishnu/mcp_server.toml`.
1. **Exact / suffix match** — entry equals the path or is a path-prefix.
   Example: `.env` matches `/repo/.env`, `crackerjack/.env`.
   Example: `pyproject.toml` matches `repo/pyproject.toml`,
   `crackerjack/pyproject.toml`.

This keeps the canonical crackerjack-relative entries (`crackerjack/services/self_patcher.py`)
working for backward compatibility AND extends protection to the rest of the
ecosystem at the same time.

## Files touched

- `crackerjack/services/self_patcher.py` — expanded `SELFPATCHER_DENY_PATHS`,
  added `_path_matches_deny()` helper, refactored `_diff_touches_deny_path`.
- `tests/unit/services/test_self_patcher_deny_paths.py` — 21 new tests:
  10 entries-present + 10 pattern-matches + 1 allow-path sanity check.
- `docs/reference/CONFIGURATION.md` — documents the deny-list expansion.
- `docs/runbooks/H11_self_patcher_deny_paths.md` — this runbook.

## Verification

```bash
pytest tests/unit/services/test_self_patcher_deny_paths.py -v --no-cov
pytest tests/unit/services/test_self_patcher.py -v --no-cov  # regression
```

Both files must be green. The matching test class is
`TestSelfPatcherDenyPathsAuditH11` (10 entries-present assertions) and
`TestSelfPatcherDenyPathMatching` (10 deny-by-pattern assertions + 1 allow
sanity check).

## Adding new entries

To extend the deny list further (e.g. a new sensitive file class discovered in
a future audit):

1. Pick the right pattern style — directory prefix, basename, path fragment,
   or exact/suffix. Prefer the most general form so the entry works across
   repos.
1. Append to `SELFPATCHER_DENY_PATHS` in `crackerjack/services/self_patcher.py`.
1. Add at least one assertion in
   `tests/unit/services/test_self_patcher_deny_paths.py` that proves the
   pattern actually denies a representative path.
1. Add a cross-repo example (e.g. `some_repo/<denied_path>`) so the test
   would catch a future regression that accidentally reverts to exact matching.
1. Update the table in this runbook so future operators know what is covered.
