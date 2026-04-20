# AI-Fix Regression Corpus

This document tracks failure shapes observed while running `crackerjack --ai-fix`
across `crackerjack`, `oneiric`, `mcp-common`, and `session-buddy`.

## Generic Workflow Gaps

These are `crackerjack` issues that should be fixed once and then verified by
tests, because they affect multiple repos.

| Shape | Example | Priority | Notes |
| --- | --- | --- | --- |
| Complexity refactor fallback | `C901 register_health_tools is too complex` | High | Refactoring agent needs a non-AST fallback when a direct transform is not available. |
| Import/error rewrite validity | `websocket/client.py` and `websocket/server.py` invalid patch retries | High | Import optimizer must preserve syntax when rewriting import blocks. |
| `__all__` cleanup | `F822 Undefined name ... in __all__` | High | Dead-code agent should remove stale exports instead of retrying a broken plan. |
| Documentation link repair | `check-local-links` broken file links | Medium | Docs agent should rewrite or remove links consistently. |
| Debug visibility | `Unable to auto-fix ...` console spam | Medium | These messages should stay in verbose / `--ai-debug` output only. |

## Repo-Specific Shapes

These are still useful as fixtures, but they should not be treated as generic
workflow bugs unless the same pattern appears elsewhere.

| Repo | Shape | Why it is repo-specific |
| --- | --- | --- |
| `oneiric` | Missing docs targets such as `QUICKSTART.md` and `docs/reference/service-dependencies.md` | The broken link set is tied to that repository's docs layout. |
| `mcp-common` | Websocket client/server import rewrites | The affected files are unique to `mcp-common`, but the underlying rewrite bug is generic. |
| `mcp-common` | `benchmark_baseline.json` large-file failure | The file size is a repo artifact, not a workflow bug. |
| `session-buddy` | `name 'suppress' is not defined` workflow failure | This needs a separate trace in that repo/version; it did not reach a stable AI-fix pass here. |

## Current Priority Order

1. Fix import rewrite validity in `ImportOptimizationAgent`.
1. Fix complexity fallback behavior when the refactoring transformer has no match.
1. Keep documentation fixes and `__all__` cleanup as regression coverage.
1. Re-run the fast-hook AI-fix workflow against `crackerjack` until it is stable.
1. Update downstream repos after the source workflow is reliable.
