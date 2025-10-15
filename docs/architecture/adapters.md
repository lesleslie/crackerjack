# Adapter Architecture & Migration Notes

**Last Updated:** 2025-10-15
**Maintainers:** Architecture Council, ACB Specialist, CLI Integrations

## Overview

Phase 3 completed the service layer cleanup, removing facade files and standardizing
import paths. All services now use direct import paths from `crackerjack.services.*`
without subdirectory facades. The domain-focused organization (ai/, monitoring/,
quality/ subdirectories) was evaluated but the facade pattern was removed in favor
of flat service imports for simplicity.

This document records the final adapter architecture and canonical import paths
after Phase 3 completion.

## Canonical Import Paths

| Service | Canonical Import Path | Notes |
|---------|----------------------|-------|
| Vector Store | `crackerjack.services.vector_store` | AI/semantic search service |
| Server Manager | `crackerjack.services.server_manager` | MCP server lifecycle management |
| Zuban LSP Service | `crackerjack.services.zuban_lsp_service` | LSP integration for Zuban type checker |
| Config Template | `crackerjack.services.config_template` | Configuration templating utilities |

All new services added during future phases must follow this pattern:

1. Place implementations directly in `crackerjack/services/`
2. Use protocol-based interfaces in `crackerjack/models/protocols.py`
3. Register with ACB dependency injection in `core/container.py`
4. Import using full path: `from crackerjack.services.<service_name> import ...`

## CLI Import Status

| CLI Module | Status | Import Pattern |
|------------|--------|----------------|
| `cache_handlers` | ✅ Complete | Direct service imports |
| `handlers` | ✅ Complete | Uses `services.server_manager` |
| `semantic_handlers` | ✅ Complete | Uses `services.vector_store` |

All CLI modules now use direct service imports without facade indirection.

## Using ACB With Services

The `configure_acb_dependencies` function (see `crackerjack/core/container.py`)
registers services for dependency injection. When introducing a new service:

1. Implement the service directly in `crackerjack/services/`
2. Define a protocol interface in `crackerjack/models/protocols.py`
3. Register the type via ACB's `depends` system in `core/container.py`
4. Retrieve dependencies using `depends.get(<Protocol>)` or `@depends.inject`
5. Write tests that call `reset_dependencies()` to avoid cross-test leakage

## Phase 3 Completion Checklist

- [x] Remove facade files from ai/ and monitoring/ subdirectories
- [x] Standardize all imports to use direct service paths
- [x] Update CLI modules to use canonical import paths
- [x] Remove re-exports from package __init__.py files
- [x] Achieve 26.6% service duplication reduction (94→69 files)

## References

- `docs/UPDATED_ARCHITECTURE_REFACTORING_PLAN.md` - Phase 3 completion details
- `docs/progress/PHASE3_COMPLETION_SUMMARY.md` - Comprehensive Phase 3 report
- `crackerjack/core/container.py` - ACB dependency registration
- `crackerjack/models/protocols.py` - Service protocol definitions
