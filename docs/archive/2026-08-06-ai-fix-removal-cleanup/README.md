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

The nine files in this directory describe the deleted `crackerjack.agents.*`
subsystem and the pre-removal provider architecture (the multi-provider AI-fix
chain with `ClaudeCodeFixer`, `OpenAICodeFixer`, `QwenCodeFixer`, and
`ProviderFactory`). They were archived during the 2026-09-09 docs audit because
their referenced code no longer exists: `crackerjack.agents.*` was reduced to a
type-stub module (`crackerjack/agents/base.py`) on 2026-08-12 (commit
`907ab860`), and the provider subsystem was replaced by the external Workflow
tool loop at `.claude/workflows/ai-fix-loop.js`. New readers following these
docs would hit `ModuleNotFoundError` or `ImportError` on every referenced class.

## Archived files

- `REMEDIATION_PLAN_2026-02-05.md` — original remediation plan for the
  multi-agent fix chain; references `TestEnvironmentAgent`,
  `DeadCodeRemovalAgent`, and `AgentContext`.
- `IMPLEMENTATION_STATUS.md` — implementation status snapshot; references
  `crackerjack.agents.coordinator` and `DeadCodeRemovalAgent`.
- `AI_FIX_TEST_FAILURE_IMPLEMENTATION_PLAN.md` — AI-fix plan for failing
  tests; references `Issue`, `IssueType`, `TestEnvironmentAgent`.
- `AUDIT_RESULTS.md` — early-2026 audit findings; references
  `AgentContext`, `AgentCoordinator`, and the direct-instantiation pattern
  those classes supported.
- `AI_FIX_INVESTIGATION.md` — investigation log for an AI-fix failure;
  references `crackerjack.agents.coordinator` log records,
  `AgentCoordinator`, and `FormattingAgent`.
- `WARNING_SUPPRESSION_AGENT_DESIGN.md` — design doc for the
  `WarningSuppressionAgent`; the agent class was never reimplemented after
  the 2026-08-12 removal.
- `WARNING_AGENT_INTEGRATION.md` — integration plan for the same warning
  agent; references the deleted `Coordinator` routing entry.
- `PERFORMANCE_OPTIMIZATION_PLAN.md` — performance plan; the snippet on
  line 193 dynamically imports agents from `crackerjack.agents.xxx` at
  runtime, which is impossible after the subsystem collapse.
- `features/PROVIDER_ARCHITECTURE.md` — entire file is the
  `ClaudeCodeFixer` / `OpenAICodeFixer` / `QwenCodeFixer` /
  `ProviderFactory` architecture; no equivalent surface exists in the
  current codebase.

## Why archive (not delete)

These files retain historical context for anyone tracing why the AI-fix
subsystem was removed or what its surface looked like before 2026-08-12.
They are searchable in-place but no longer linked from any active doc
(README, CLI_REFERENCE, MCP_TOOLS_SPECIFICATION, AGENTS.md, etc.). All
forward-references to them in the active docs were either rewritten
(`.superpowers/specs/*`) or are now broken and tracked in
`docs/audits/2026-09-09-crackerjack-docs-audit.md` Category F.

## Pointer

See `docs/audits/2026-09-09-crackerjack-docs-audit.md` Category F
("`crackerjack.agents.*` deleted surface still narratively alive")
for the trigger rationale and a list of broken forward-links.
