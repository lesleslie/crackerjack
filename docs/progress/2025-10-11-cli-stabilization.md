# Crackerjack CLI Stabilization – 11 Oct 2025

## What Changed This Session

- Added an ACB-aware cache adapter fallback that logs a warning when the external adapter is missing instead of failing import time.
- Replaced usages of the deprecated `acb.logging` shim with the current logger adapter exposed through `depends.get(Logger)`, and re-implemented `retry`, `with_timeout`, and `validate_args` locally so the decorator surface area stays intact for existing tests.
- Reintroduced the `WorkflowOptions` API (generated from `CrackerjackSettings`) to preserve downstream expectations while moving configuration sources to the new settings object.
- Swapped the legacy `SessionCoordinator` implementation with a small in-repo coordinator class and hooked it into the workflow/pipeline flow to avoid the missing `SessionManager` import.
- Updated global lock handling to wrap the new settings object and supply sensible defaults when the external orchestration config file is absent.
- Removed runtime dependency on `acb.main.get_app` by loading settings directly and registering them via `depends.set`.

## Current Status

- `python -m crackerjack -v` now progresses past the previous cache/logging errors and reaches the orchestration setup step.
- The command still aborts before completing because `HookManagerImpl` (and related tests/docs) expect the removed `OrchestrationConfig` dataclass, so DI now returns raw settings without the helper conversion methods.
- Test suite not re-run after these adjustments; anticipate multiple failures until the orchestration configuration refactor is completed.

## Remaining Work / Next Steps

1. Refactor `HookManagerImpl`, orchestration adapters, and tests to read orchestration-related flags directly from `CrackerjackSettings` (or provide thin compatibility wrappers).
2. Clean up documentation/tests that still import `OrchestrationConfig` or call `.to_orchestrator_settings()`.
3. Re-run `uv run pytest` (plus the CLI sanity command) once orchestration config is aligned, to confirm no regressions.
4. After successful runs, remove the temporary log warning about the missing hybrid cache adapter if the upstream dependency is added back.
