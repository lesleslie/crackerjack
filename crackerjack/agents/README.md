> Crackerjack Docs: [Main](../../README.md) | [Crackerjack Package](../README.md)

# Agents (Type Stubs Only)

The full AI-fix agent runtime was removed in the 2026-08-12 refactor
(commit 907ab860) and replaced by the external Workflow tool loop at
`.claude/workflows/ai-fix-loop.js`.

What remains here is a minimal type-stub module (`base.py`) that exports
`AgentContext`, `Issue`, `IssueType`, `Priority`, and `FixResult` for the
handful of fixers/tests that still import these names.

## Related

- [Main Documentation](../../README.md) - Project overview and getting started
- [CLAUDE.md](../../CLAUDE.md) - Architecture and development guidelines
- [Crackerjack Package](../README.md) - Core runtime
