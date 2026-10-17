---
status: archived
role: historical
date: 2026-09-09
last_reviewed: 2026-09-09
superseded_by: null
blocks_on: []
topic: archive-cleanup
---

# Archived docs — 2026-08-06 AI-fix removal cleanup

The forty-seven files in this directory were archived during the 2026-09-09 docs
audit because they directly documented or narrated the deleted AI-fix surface
in `crackerjack.agents.*`, the pre-removal provider architecture
(`ClaudeCodeFixer`, `OpenAICodeFixer`, `QwenCodeFixer`, `ProviderFactory`), or
adjacent subsystems (protocol reference material, batchprocessor usage,
structured-logging guidance, skill-system architecture) that lived alongside
the deleted code and inherited its broken-import failure mode. A small subset
(e.g. `test-coverage.md`, `complexipy_adapter_fix.md`, `README_AUDIT_REPORT.md`)
is not itself about AI-fix/provider but was bundled because its referenced
code path went through the deleted module.

The trigger was the 2026-08-10 commit `907ab860` (`feat(refactor): remove
AI-fix subsystem + verify clean test suite`), which reduced
`crackerjack.agents.*` to a type-stub module (`crackerjack/agents/base.py`).
The provider subsystem was replaced by the external Workflow tool loop at
`.claude/workflows/ai-fix-loop.js`. New readers following any of these docs
would hit `ModuleNotFoundError` or `ImportError` on every referenced class.

## Archived files

The forty-seven files (excluding this README), grouped by category:

### AI-fix subsystem designs (6)

- `2025-02-12-multi-agent-ai-fix-quality-system-design.md` — original
  multi-agent fix-chain design; references `TestEnvironmentAgent`,
  `DeadCodeRemovalAgent`, `AgentContext`.
- `2026-02-12-v2-multi-agent-quality-system.md` — v2 redesign of the same
  multi-agent system; references the agent classes above.
- `2026-07-07-ai-fix-improvement-design.md` — improvement spec for AI-fix;
  references `crackerjack.agents.coordinator`.
- `2026-07-11-ai-fix-e501-post-processor-design.md` — design for an
  E501-flake post-processor step that lived in the deleted subsystem.
- `2026-08-06-ai-fix-removal-external-loop-design.md` — design rationale
  for replacing the in-tree AI-fix system with the external Workflow loop.
- `2026-08-06-ai-fix-removal-extraction.md` — extraction notes for the
  same removal effort.

### ADRs (2)

- `ADR-002-multi-agent-orchestration.md` — ADR that ratified the
  multi-agent orchestration model now superseded by the external loop.
- `ADR-005-agent-skill-routing.md` — ADR for agent→skill routing; the
  agent layer it routed through no longer exists.

### Agent orchestration / coordination (4)

- `AGENT_COORDINATION_ARCHITECTURE_ANALYSIS.md` — architecture analysis
  for the deleted agent coordinator.
- `AGENT_COORDINATION_FIX_PLAN.md` — fix plan for the coordinator.
- `AGENT_PERFORMANCE_TRACKING.md` — performance-tracking design that
  consumed `AgentCoordinator` metrics.
- `AGENT_TEST_COVERAGE_PLAN.md` — coverage plan targeting the deleted
  agent classes.

### AI-fix run history / remediation (9)

- `AI_FIX_BUGS.md`
- `AI_FIX_EXECUTION_TRACE.md`
- `AI_FIX_EXPECTED_BEHAVIOR.md`
- `AI_FIX_FAILURE_ANALYSIS.md`
- `AI_FIX_INVESTIGATION.md`
- `AI_FIX_ISSUES_RESOLUTION.md`
- `AI_FIX_METRICS_REVIEW.md`
- `AI_FIX_REFACTOR_PLAN.md`
- `AI_FIX_TEST_FAILURE_IMPLEMENTATION_PLAN.md`

All reference `crackerjack.agents.coordinator`, `FormattingAgent`,
`TestEnvironmentAgent`, `AgentContext`, or `Issue`/`IssueType` types that
no longer exist after the 2026-08-10 removal.

### Provider architecture (3)

- `QWEN_PROVIDER.md` — QwenCodeFixer provider surface; provider no
  longer exists.
- `PROVIDER_ARCHITECTURE.md` — entire file is the `ClaudeCodeFixer` /
  `OpenAICodeFixer` / `QwenCodeFixer` / `ProviderFactory` architecture;
  no equivalent surface exists in the current codebase.
- `README_AUDIT_REPORT.md` — audit of the provider docs prior to
  archival.

### Batchprocessor docs (2)

- `BATCHPROCESSOR_TROUBLESHOOTING.md` — batchprocessor troubleshooting
  guide; bundled because its code path imported `crackerjack.agents.*`
  at runtime.
- `BATCHPROCESSOR_USER_GUIDE.md` — batchprocessor user guide; same
  reason.

### Protocol reference / review docs (4)

- `PROTOCOL_DOCUMENTATION_REVIEW.md` — review of the protocol
  documentation set.
- `PROTOCOL_EXAMPLES.md` — protocol usage examples.
- `PROTOCOL_QUICK_REFERENCE.md` — protocol quick-reference card.
- `PROTOCOL_REFERENCE_GUIDE.md` — long-form protocol reference.

### Adjacent subsystems tied to the deleted code (5)

- `SKILL_SYSTEM.md` — skill-system architecture that delegated to
  agent routing; agent layer removed.
- `STRUCTURED_LOGGING.md` — structured-logging guide whose runtime
  path imported from `crackerjack.agents.*`.
- `WARNING_AGENT_INTEGRATION.md` — integration plan for the
  warning-suppression agent that was never reimplemented after
  the 2026-08-10 removal.
- `WARNING_SUPPRESSION_AGENT_DESIGN.md` — design doc for the same
  warning agent; the agent class was never reimplemented.
- `swarm-autofix-integration.md` — swarm-mode autofix integration
  notes; references the deleted subsystem.

### Audit, remediation, and status snapshots (5)

- `AUDIT_RESULTS.md` — early-2026 audit findings; references
  `AgentContext`, `AgentCoordinator`, and the direct-instantiation
  pattern those classes supported.
- `REMEDIATION_PLAN_2026-02-05.md` — original remediation plan for the
  multi-agent fix chain; references `TestEnvironmentAgent`,
  `DeadCodeRemovalAgent`, and `AgentContext`.
- `COMPREHENSIVE_REMEDIATION_PLAN.md` — comprehensive remediation
  plan targeting the same deleted surface.
- `IMPLEMENTATION_STATUS.md` — implementation status snapshot;
  references `crackerjack.agents.coordinator` and
  `DeadCodeRemovalAgent`.
- `CHECKPOINT_ANALYSIS_2026-02-05.md` — analysis of a 2026-02-05
  checkpoint for the AI-fix work.
- `EXECUTIVE-SUMMARY.md` — executive summary of the AI-fix program.

### Test and complexity docs bundled with the cleanup (5)

- `test-coverage.md` — coverage analysis; bundled because its
  referenced code path went through the deleted module.
- `complexipy_adapter_fix.md` — complexipy-adapter fix notes; bundled
  for the same reason.
- `COMPLEXITY_REFACTORING_PLAN_GAMMA.md` — complexity refactor plan
  whose target modules were deleted.
- `TEST_IMPLEMENTATION_PLAN.md` — test implementation plan for the
  deleted subsystem.
- `PERFORMANCE_OPTIMIZATION_PLAN.md` — performance plan; the snippet
  on line 193 dynamically imports agents from
  `crackerjack.agents.xxx` at runtime, which is impossible after the
  subsystem collapse.

### Other (1)

- `layer-6-agent-system.md` — agent-system layer description for the
  deleted module.

## Why archive (not delete)

These files retain historical context for anyone tracing why the AI-fix
subsystem was removed or what its surface looked like before 2026-08-10.
They are searchable in-place but no longer linked from any active doc
(README, CLI_REFERENCE, MCP_TOOLS_SPECIFICATION, AGENTS.md, etc.). All
forward-references to them in the active docs were either rewritten
(`.superpowers/specs/*`) or are now broken and tracked in
`docs/audits/2026-09-09-crackerjack-docs-audit.md` Category F.

## Pointer

See `docs/audits/2026-09-09-crackerjack-docs-audit.md` Category F
("`crackerjack.agents.*` deleted surface still narratively alive")
for the trigger rationale and a list of broken forward-links.