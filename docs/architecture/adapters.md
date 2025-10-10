# Adapter Architecture & Migration Notes

**Last Updated:** 2025-10-17  
**Maintainers:** Architecture Council, ACB Specialist, CLI Integrations

## Overview

Phase 3.4 introduced the domain-focused service layout for Crackerjack. Service
implementations now live in purpose-specific packages (e.g.
`crackerjack/services/ai`, `crackerjack/services/monitoring`,
`crackerjack/services/quality`) with thin compatibility shims that continue to
expose legacy import paths. Phase 4 requires all new development – and updated
entrypoints – to depend on the domain namespaces so we can safely deprecate the
legacy shims after adoption is complete.

This document records the adapter migration strategy, lists the canonical import
paths, and outlines best practices when wiring dependencies through ACB.

## Canonical Import Paths

| Domain | Preferred Import | Legacy Shim (temporary) | Notes |
|--------|------------------|-------------------------|-------|
| AI & Semantic services | `crackerjack.services.ai.vector_store` | `crackerjack.services.vector_store` | CLI semantic handlers now use the domain path; shim will be removed in Phase 4.3. |
| Monitoring & Telemetry | `crackerjack.services.monitoring.server_manager`<br>`crackerjack.services.monitoring.zuban_lsp_service` | `crackerjack.services.server_manager`<br>`crackerjack.services.zuban_lsp_service` | Monitoring dashboard and CLI operations use the domain namespace. |
| Quality & Baselines | `crackerjack.services.quality.config_template` | `crackerjack.services.config_template` | Used by configuration templating and quality baseline tooling. |

All new adapters added during Phase 4 must follow the same pattern:

1. Place implementations inside the appropriate domain package.
2. Export types/functions via the domain `__init__.py`.
3. Optionally provide a short-term shim in the legacy module (re-export only).
4. Update consumers (CLI, orchestrators, services) to import from the domain.

## CLI Adoption Status

| CLI Module | Status | Notes |
|------------|--------|-------|
| `cache_handlers` | ✅ Legacy path still valid (no domain split required) |
| `handlers` | ✅ Uses monitoring & quality domains for server/config utilities |
| `semantic_handlers` | ✅ Imports vector store via AI domain |

Remaining CLI commands should be audited after each sprint to ensure no new
references to the legacy paths are introduced. ACB dependency graph checks will
flag regressions starting in Phase 4.2.

## Using ACB With Domain Services

The `configure_acb_dependencies` function (see
`crackerjack/core/acb_di_config.py`) registers domain services directly. When
introducing a new adapter or service:

1. Implement the service inside the domain package.
2. Register the type via `ACBDependencyRegistry.register`.
3. Retrieve dependencies using `depends.get(<InterfaceOrClass>)`.
4. Write tests that call `reset_dependencies()` to avoid cross-test leakage.

When a legacy shim is still required (e.g. third-party integrations), annotate
the re-export module with a TODO documenting the removal plan and link to
tracking issues.

## Migration Checklist

- [x] Expose vector store service through AI domain.
- [x] Expose MPC server management helpers through Monitoring domain.
- [x] Expose configuration templating through Quality domain.
- [ ] Update orchestrators to consume only domain imports (Phase 4.2).
- [ ] Remove legacy re-export modules once coverage reaches ≥65% (Phase 4.3).

## References

- `docs/COMPREHENSIVE-IMPROVEMENT-PLAN.md`
- `crackerjack/core/acb_di_config.py`
- `crackerjack/services/ai/__init__.py`
- `crackerjack/services/monitoring/__init__.py`
- `crackerjack/services/quality/__init__.py`
