# ADR 004: Workflow Session Controller Extraction

**Status:** Accepted  
**Date:** 2025-10-17  
**Deciders:** Architecture Council  
**Context**

`WorkflowPipeline` in `crackerjack/core/workflow_orchestrator.py` has grown past
2,100 lines with deeply nested responsibilities. Session startup logic (session
tracking, LSP orchestration, hook configuration) made `_initialize_workflow_session`
sprawl across dozens of helper methods, exacerbating the single-responsibility
violation called out in the Phase 3 review.

**Decision**

Introduce a dedicated `SessionController` that owns session bootstrap tasks.
`WorkflowPipeline` now delegates to `SessionController.initialize`, which
invokes the existing helper methods. This allows future PRs to migrate the
helpers into self-contained controllers without destabilising the pipeline.

**Consequences**

- ✅ Session orchestration logic moves out of the monolithic pipeline class,
  reducing immediate complexity and creating an extension point for further
  decomposition.
- ✅ Enables targeted testing of session bootstrap behaviour by addressing the
  controller directly.
- ⚠️ Helpers still live on `WorkflowPipeline`; subsequent refactors will migrate
  them into the controller and add unit tests.

**Next Steps**

1. Move LSP and hook-manager helpers into `SessionController` with focused tests.
2. Extract phase execution into a `PhaseController` to mirror the session split.
3. Update `WORKFLOW-ARCHITECTURE.md` once controllers own the majority of the
   orchestration responsibilities.
