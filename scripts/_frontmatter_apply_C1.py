"""C1 sweep: prepend YAML frontmatter to crackerjack loose + nested docs.

User-authorized (P7.B plan-lifecycle-unification playbook). Mechanical.

Mirrors mahavishnu's _orphan_sweep_C1_2.py and session-buddy's
_frontmatter_apply_C1.py but adapts to crackerjack's sprawling flat
docs/ + 28+ subdir layout (no 6-store).

Reads each file, prepends a uniform frontmatter block + adds a trailing HTML
legacy comment on the existing Status line so the validator's --allow-nonstandard
mode stays green.
"""

from __future__ import annotations

from pathlib import Path

FM_TEMPLATE = (
    "---\n"
    "status: {status}\n"
    "role: {role}\n"
    "date: 2026-07-17\n"
    "last_reviewed: 2026-07-17\n"
    "superseded_by: null\n"
    "blocks_on: []\n"
    "topic: {topic}\n"
    "---\n"
    "\n"
)

REPO_ROOT = Path("/Users/les/Projects/crackerjack")


# Per-subdir default (status, role, topic). Anything not in ASSIGNMENTS
# uses the longest matching prefix.
SUBDIR_DEFAULTS: list[tuple[str, tuple[str, str, str]]] = [
    ("docs/schemas/", ("active", "canonical", "lifecycle")),
    ("docs/adr/", ("active", "canonical", "architecture")),
    ("docs/architecture/", ("active", "canonical", "architecture")),
    ("docs/api/", ("active", "canonical", "mcp-design")),
    ("docs/audits/", ("complete", "historical", "lifecycle")),
    ("docs/decisions/", ("active", "canonical", "lifecycle")),
    ("docs/design/", ("active", "canonical", "architecture")),
    ("docs/development/", ("active", "canonical", "architecture")),
    ("docs/diagrams/", ("active", "canonical", "architecture")),
    ("docs/examples/", ("active", "canonical", "mcp-design")),
    ("docs/features/", ("active", "canonical", "lifecycle")),
    ("docs/fixes/", ("complete", "historical", "lifecycle")),
    ("docs/followups/", ("active", "implementation", "lifecycle")),
    ("docs/guides/", ("active", "canonical", "lifecycle")),
    ("docs/implementation/", ("complete", "historical", "lifecycle")),
    ("docs/implementation-plans/", ("complete", "historical", "lifecycle")),
    ("docs/patterns/", ("active", "canonical", "architecture")),
    ("docs/performance/", ("active", "canonical", "observability")),
    ("docs/plans/", ("complete", "historical", "lifecycle")),
    ("docs/prompts/", ("active", "canonical", "lifecycle")),
    ("docs/quality/", ("active", "canonical", "mcp-design")),
    ("docs/refactoring/", ("complete", "historical", "architecture")),
    ("docs/reference/", ("active", "canonical", "mcp-design")),
    ("docs/reviews/", ("complete", "historical", "lifecycle")),
    ("docs/runbooks/", ("active", "canonical", "lifecycle")),
    ("docs/superpowers/plans/", ("active", "implementation", "lifecycle")),
    ("docs/superpowers/specs/", ("active", "implementation", "lifecycle")),
    ("docs/superpowers/triage/", ("active", "implementation", "lifecycle")),
]


# Per-file explicit assignments (status, role, topic).
# Filename-keyed overrides for files whose content disagrees with the subdir
# default. Examples: shipped plans, active guides, recently authored ADRs.
ASSIGNMENTS: dict[str, tuple[str, str, str]] = {
    # ----- Loose docs at docs/ root -----
    "docs/ARCHITECTURE.md": ("active", "canonical", "architecture"),
    "docs/CLI_REFERENCE.md": ("active", "canonical", "mcp-design"),
    "docs/QUICK_START.md": ("active", "canonical", "lifecycle"),
    "docs/MIGRATION_GUIDE.md": ("active", "canonical", "lifecycle"),
    "docs/MIGRATION_GUIDE_0.47.0.md": ("complete", "historical", "lifecycle"),
    "docs/IMPLEMENTATION_STATUS.md": ("active", "canonical", "lifecycle"),
    "docs/PROFILES_QUICK_REFERENCE.md": ("active", "canonical", "mcp-design"),
    "docs/PROTOCOL_DOCUMENTATION_PLAN.md": ("complete", "historical", "mcp-design"),
    "docs/PROTOCOL_DX_ASSESSMENT.md": ("complete", "historical", "mcp-design"),
    "docs/MAHAVISHNU_POOL_INTEGRATION.md": ("complete", "canonical", "mcp-design"),
    "docs/MAHAVISHNU_POOL_QUICKSTART.md": ("complete", "canonical", "mcp-design"),
    "docs/MCP_GLOBAL_MIGRATION_GUIDE.md": ("complete", "historical", "mcp-design"),
    "docs/MCP_SERVER_AUDIT.md": ("complete", "historical", "mcp-design"),
    "docs/MCP_SERVER_INVESTIGATION.md": ("complete", "historical", "mcp-design"),
    "docs/SKILL_SYSTEM.md": ("active", "canonical", "lifecycle"),
    "docs/STRUCTURED_LOGGING.md": ("active", "canonical", "observability"),
    "docs/ERROR_HANDLING_STANDARD.md": ("active", "canonical", "error-handling"),
    "docs/ERROR_HANDLING_MIGRATION_GUIDE.md": (
        "complete",
        "historical",
        "error-handling",
    ),
    "docs/error_handling_refactoring_plan.md": (
        "complete",
        "historical",
        "error-handling",
    ),
    "docs/PERFORMANCE_OPTIMIZATION_PLAN.md": (
        "complete",
        "historical",
        "observability",
    ),
    "docs/PERFORMANCE_DIAGRAMS.md": ("complete", "historical", "observability"),
    "docs/PERFORMANCE_PHASE_2_1_REGEX_PRECOMPILATION.md": (
        "complete",
        "historical",
        "observability",
    ),
    "docs/performance-baseline.md": ("complete", "historical", "observability"),
    "docs/JSON_PARSING_ARCHITECTURE.md": ("active", "canonical", "mcp-design"),
    "docs/JSON_PARSING_IMPLEMENTATION.md": ("complete", "historical", "mcp-design"),
    "docs/JSON_PARSING_PERFORMANCE.md": ("complete", "historical", "mcp-design"),
    "docs/QUALITY_SCANNING_STRATEGY.md": ("active", "canonical", "mcp-design"),
    "docs/ADMIN_SHELL.md": ("active", "canonical", "mcp-design"),
    "docs/DOCS_CLEANUP_GUIDELINES.md": ("active", "canonical", "lifecycle"),
    "docs/DOCS_ORGANIZATION.md": ("active", "canonical", "lifecycle"),
    # AI_FIX historical reports (most are historical)
    "docs/AI_FIX_ADAPTER_FIX.md": ("complete", "historical", "lifecycle"),
    "docs/AI_FIX_ARCHITECTURAL_FIX.md": ("complete", "historical", "lifecycle"),
    "docs/AI_FIX_BROKEN_PATTERNS.md": ("complete", "historical", "lifecycle"),
    "docs/AI_FIX_BUGS.md": ("complete", "historical", "lifecycle"),
    "docs/AI_FIX_DOCUMENTATION_LINKS.md": ("complete", "historical", "lifecycle"),
    "docs/AI_FIX_EXECUTION_TRACE.md": ("complete", "historical", "lifecycle"),
    "docs/AI_FIX_EXPECTED_BEHAVIOR.md": ("complete", "historical", "lifecycle"),
    "docs/AI_FIX_FAILURE_ANALYSIS.md": ("complete", "historical", "lifecycle"),
    "docs/AI_FIX_INVESTIGATION.md": ("complete", "historical", "lifecycle"),
    "docs/AI_FIX_ISSUES_RESOLUTION.md": ("complete", "historical", "lifecycle"),
    "docs/AI_FIX_METRICS_REVIEW.md": ("complete", "historical", "lifecycle"),
    "docs/AI_FIX_PRODUCTION_TEST_DEBUG.md": ("complete", "historical", "lifecycle"),
    "docs/AI_FIX_REFACTOR_PLAN.md": ("complete", "historical", "lifecycle"),
    "docs/AI_FIX_REGRESSION_CORPUS.md": ("complete", "historical", "lifecycle"),
    "docs/AI_FIX_ROOT_CAUSE_ANALYSIS.md": ("complete", "historical", "lifecycle"),
    "docs/AI_FIX_SAFETY_VALIDATION_IMPLEMENTED.md": (
        "complete",
        "historical",
        "lifecycle",
    ),
    "docs/AI_FIX_SHADOWING_DAMAGE.md": ("complete", "historical", "lifecycle"),
    "docs/AI_FIX_TEST_FAILURE_IMPLEMENTATION_PLAN.md": (
        "complete",
        "historical",
        "lifecycle",
    ),
    "docs/AI_FIX_VALIDATION_ISSUES.md": ("complete", "historical", "lifecycle"),
    # Adapter test / fix plans
    "docs/ADAPTER_PROTOCOL_FIX_PLAN.md": ("complete", "historical", "mcp-design"),
    "docs/ADAPTER_TEST_COVERAGE_PLAN.md": ("complete", "historical", "mcp-design"),
    "docs/AGENT_B_IMPORT_UNION_FIXES.md": ("complete", "historical", "lifecycle"),
    "docs/AGENT_COORDINATION_ARCHITECTURE_ANALYSIS.md": (
        "complete",
        "historical",
        "lifecycle",
    ),
    "docs/AGENT_COORDINATION_FIX_PLAN.md": ("complete", "historical", "lifecycle"),
    "docs/AGENT_TEST_COVERAGE_PLAN.md": ("complete", "historical", "lifecycle"),
    "docs/AGENT_TEST_DELIVERY.md": ("complete", "historical", "lifecycle"),
    "docs/ASYNC_ADAPTER_FALLBACK_ANALYSIS.md": ("complete", "historical", "lifecycle"),
    # Audits
    "docs/AUDIT_HOOKS_TOOLS.md": ("complete", "historical", "lifecycle"),
    "docs/AUDIT_RESULTS.md": ("complete", "historical", "lifecycle"),
    "docs/CLI_OPTIONS_AUDIT.md": ("complete", "historical", "lifecycle"),
    # Bandit / complexipy investigations
    "docs/bandit-performance-investigation.md": (
        "complete",
        "historical",
        "observability",
    ),
    "docs/complexipy_adapter_fix.md": ("complete", "historical", "lifecycle"),
    "docs/COMPLEXIPY_PARSER_FIX.md": ("complete", "historical", "lifecycle"),
    "docs/comprehensive_hooks_audit.md": ("complete", "historical", "lifecycle"),
    # Batchprocessor
    "docs/BATCHPROCESSOR_TROUBLESHOOTING.md": ("active", "canonical", "lifecycle"),
    "docs/BATCHPROCESSOR_USER_GUIDE.md": ("active", "canonical", "lifecycle"),
    # Checkpoints and sessions (all historical)
    "docs/CHECKPOINT_2026-02-05_FINAL.md": ("complete", "historical", "persistence"),
    "docs/CHECKPOINT_ANALYSIS_2026-02-05.md": ("complete", "historical", "persistence"),
    "docs/SESSION_CHECKPOINT_2025-01-22_PT2.md": (
        "complete",
        "historical",
        "persistence",
    ),
    "docs/SESSION_CHECKPOINT_2025-01-22.md": ("complete", "historical", "persistence"),
    "docs/SESSION_CHECKPOINT_2025-01-30.md": ("complete", "historical", "persistence"),
    # Hook optimization plans
    "docs/CHECK_YAML_AI_FIX_BUG_FIX.md": ("complete", "historical", "lifecycle"),
    "docs/COMP_HOOKS_OPTIMIZATION_PLAN.md": ("complete", "historical", "lifecycle"),
    "docs/FAST_HOOKS_OPTIMIZATION_PLAN.md": ("complete", "historical", "lifecycle"),
    "docs/HOOK_ISSUE_COUNT_DISPLAY_OPTIONS.md": ("complete", "historical", "lifecycle"),
    "docs/HOOK_ISSUE_COUNT_ROOT_CAUSE.md": ("complete", "historical", "lifecycle"),
    "docs/ISSUE_COUNT_BUGFIX.md": ("complete", "historical", "lifecycle"),
    "docs/INTEGRAL_SCANNING_OPTIONS.md": ("complete", "historical", "lifecycle"),
    # Complexity / refactoring plans
    "docs/COMPLEXITY_REFACTORING_PLAN_2025-12-31.md": (
        "complete",
        "historical",
        "architecture",
    ),
    "docs/COMPLEXITY_REFACTORING_PLAN_GAMMA.md": (
        "complete",
        "historical",
        "architecture",
    ),
    "docs/complexity_refactoring_plan.md": ("complete", "historical", "architecture"),
    "docs/refactoring-plan-complexity-violations.md": (
        "complete",
        "historical",
        "architecture",
    ),
    "docs/workflow_orchestrator_refactoring_plan.md": (
        "complete",
        "historical",
        "architecture",
    ),
    # Cross-cutting plans / audits
    "docs/COMPREHENSIVE_REMEDIATION_PLAN.md": ("complete", "historical", "lifecycle"),
    "docs/CONFIG_CONSOLIDATION_AUDIT.md": ("complete", "historical", "oneiric-config"),
    "docs/CROSS_PROJECT_CONFIG_AUDIT.md": ("complete", "historical", "oneiric-config"),
    "docs/health_check_implementation_plan.md": ("complete", "historical", "lifecycle"),
    # Implementation plans
    "docs/implementation-plan-logging-progress-fixes.md": (
        "complete",
        "historical",
        "observability",
    ),
    "docs/implementation-status.md": ("complete", "historical", "lifecycle"),
    # Final plans
    "docs/FINAL_ZUBAN_CONQUEST_PLAN.md": ("complete", "historical", "lifecycle"),
    "docs/PHASE_5-7_IMPLEMENTATION_PLAN.md": ("complete", "historical", "lifecycle"),
    "docs/PYPROJECT_TIMEOUT_IMPLEMENTATION.md": ("complete", "historical", "lifecycle"),
    "docs/MANAGER_TEST_IMPLEMENTATION_PLAN.md": ("complete", "historical", "lifecycle"),
    # Progress / UI plans
    "docs/progress-bar-implementation.md": ("complete", "historical", "lifecycle"),
    "docs/progress-indicator-analysis.md": ("complete", "historical", "lifecycle"),
    # Remediation / shell
    "docs/REMEDIATION_PLAN_2026-02-05.md": ("complete", "historical", "lifecycle"),
    "docs/SHELL_ADAPTER_FIX.md": ("complete", "historical", "lifecycle"),
    # Reporting tools
    "docs/reporting_tools_fix.md": ("complete", "historical", "lifecycle"),
    "docs/reporting_tools_investigation.md": ("complete", "historical", "lifecycle"),
    # Python / refurb
    "docs/python-improvements-summary.md": ("complete", "historical", "lifecycle"),
    "docs/python-review-logging-progress-implementation.md": (
        "complete",
        "historical",
        "observability",
    ),
    "docs/refurb_creosote_behavior.md": ("complete", "historical", "lifecycle"),
    # Ruff / zuban
    "docs/RUFF_CHECK_AI_FIX_BUG_FIX.md": ("complete", "historical", "lifecycle"),
    "docs/ZUBAN_TYPE_CHECKING_FIXES.md": ("complete", "historical", "lifecycle"),
    "docs/ULID_MIGRATION_ANALYSIS.md": ("complete", "historical", "lifecycle"),
    # Test plans
    "docs/TEST_AI_FIX_IMPLEMENTATION_JAN_2025.md": (
        "complete",
        "historical",
        "lifecycle",
    ),
    "docs/TEST_AI_STAGE_IMPLEMENTATION.md": ("complete", "historical", "lifecycle"),
    "docs/TEST_COVERAGE_PLAN_CORE.md": ("complete", "historical", "lifecycle"),
    "docs/TEST_COVERAGE_RESULTS.md": ("complete", "historical", "lifecycle"),
    "docs/TEST_COVERAGE_SERVICES_LAYER.md": ("complete", "historical", "lifecycle"),
    "docs/TEST_PARSING_FIX.md": ("complete", "historical", "lifecycle"),
    "docs/TOOLS_PARSERS_TEST_PLAN.md": ("complete", "historical", "lifecycle"),
    "docs/TOOLS_PARSERS_TEST_STATUS.md": ("complete", "historical", "lifecycle"),
    "docs/test_selection.md": ("complete", "historical", "lifecycle"),
    "docs/task-breakdown.md": ("complete", "historical", "lifecycle"),
    # Display / error
    "docs/ERROR_DETAILS_DISPLAY_FIX.md": ("complete", "historical", "lifecycle"),
    # Team / coordination
    "docs/TEAM_COORDINATION_DIAGRAM.md": ("complete", "historical", "lifecycle"),
    # Warnings / agents
    "docs/WARNING_AGENT_INTEGRATION.md": ("complete", "historical", "lifecycle"),
    "docs/WARNING_SUPPRESSION_AGENT_DESIGN.md": ("complete", "historical", "lifecycle"),
    # Ecosystem / symbiotic
    "docs/symbiotic-ecosystem-quick-start.md": ("active", "canonical", "lifecycle"),
    # ----- docs/ root indexes -----
    "docs/README.md": ("active", "canonical", "lifecycle"),
    "docs/index.md": ("active", "canonical", "lifecycle"),
    # ----- docs/plans/ (mostly historical plans) -----
    "docs/plans/2025-02-12-multi-agent-ai-fix-quality-system-design.md": (
        "complete",
        "historical",
        "lifecycle",
    ),
    "docs/plans/2025-02-12-multi-agent-ai-fix-quality-system.md": (
        "complete",
        "historical",
        "lifecycle",
    ),
    "docs/plans/2026-02-12-v2-multi-agent-quality-system.md": (
        "complete",
        "historical",
        "lifecycle",
    ),
    "docs/plans/2026-02-22-ast-transform-engine-design.md": (
        "complete",
        "historical",
        "lifecycle",
    ),
    "docs/plans/2026-05-30-ai-fix-dashboard-wiring.md": (
        "complete",
        "historical",
        "lifecycle",
    ),
    "docs/plans/2026-06-27-ty-cleanup-and-ai-fix.md": (
        "complete",
        "historical",
        "lifecycle",
    ),
    "docs/plans/2026-07-06-ai-fix-tier-architecture.md": (
        "shipped",
        "implementation",
        "lifecycle",
    ),
    "docs/plans/AI_FIX_IMPROVEMENT_PLAN.md": ("complete", "historical", "lifecycle"),
    "docs/plans/swarm-autofix-integration.md": ("complete", "historical", "lifecycle"),
    # ----- docs/superpowers/ ----- (recent plans/specs)
    "docs/superpowers/plans/2026-05-20-phase-0-event-bus-plan.md": (
        "active",
        "implementation",
        "lifecycle",
    ),
    "docs/superpowers/plans/2026-06-02-ai-fix-display-loop-bugs.md": (
        "active",
        "implementation",
        "lifecycle",
    ),
    "docs/superpowers/plans/2026-06-03-dhara-mcp-migration.md": (
        "active",
        "implementation",
        "lifecycle",
    ),
    "docs/superpowers/plans/2026-06-29-ty-ratchet-cleanup.md": (
        "active",
        "implementation",
        "lifecycle",
    ),
    "docs/superpowers/plans/2026-07-08-fix-sandbox-integration.md": (
        "active",
        "implementation",
        "lifecycle",
    ),
    "docs/superpowers/plans/2026-07-10-libcst-surgeon-extract-method-fallback.md": (
        "active",
        "implementation",
        "lifecycle",
    ),
    "docs/superpowers/plans/2026-07-10-output-validator-traceback-details.md": (
        "active",
        "implementation",
        "lifecycle",
    ),
    "docs/superpowers/plans/2026-07-10-validation-coordinator-serialization.md": (
        "active",
        "implementation",
        "lifecycle",
    ),
    "docs/superpowers/plans/2026-07-11-ai-fix-e501-post-processor.md": (
        "active",
        "implementation",
        "lifecycle",
    ),
    "docs/superpowers/plans/2026-07-11-ai-fix-no-op-circuit-breaker.md": (
        "active",
        "implementation",
        "lifecycle",
    ),
    "docs/superpowers/plans/2026-07-11-ai-fix-regen-timeout.md": (
        "active",
        "implementation",
        "lifecycle",
    ),
    "docs/superpowers/plans/2026-07-12-eventbridge-publisher.md": (
        "active",
        "implementation",
        "lifecycle",
    ),
    # specs use draft until accepted
    "docs/superpowers/specs/2026-05-20-ai-fix-comprehensive-overhaul-design.md": (
        "draft",
        "implementation",
        "lifecycle",
    ),
    "docs/superpowers/specs/2026-06-03-dhara-mcp-migration-design.md": (
        "draft",
        "implementation",
        "lifecycle",
    ),
    "docs/superpowers/specs/2026-06-29-ty-ratchet-cleanup-design.md": (
        "draft",
        "implementation",
        "lifecycle",
    ),
    "docs/superpowers/specs/2026-07-07-ai-fix-improvement-design.md": (
        "draft",
        "implementation",
        "lifecycle",
    ),
    "docs/superpowers/specs/2026-07-08-fix-sandbox-integration-design.md": (
        "draft",
        "implementation",
        "lifecycle",
    ),
    "docs/superpowers/specs/2026-07-10-libcst-surgeon-extract-method-fallback-design.md": (
        "draft",
        "implementation",
        "lifecycle",
    ),
    "docs/superpowers/specs/2026-07-10-output-validator-traceback-details-design.md": (
        "draft",
        "implementation",
        "lifecycle",
    ),
    "docs/superpowers/specs/2026-07-10-validation-coordinator-serialization-design.md": (
        "draft",
        "implementation",
        "lifecycle",
    ),
    "docs/superpowers/specs/2026-07-11-ai-fix-e501-post-processor-design.md": (
        "draft",
        "implementation",
        "lifecycle",
    ),
    "docs/superpowers/specs/2026-07-11-ai-fix-no-op-circuit-breaker-design.md": (
        "draft",
        "implementation",
        "lifecycle",
    ),
    "docs/superpowers/specs/2026-07-11-ai-fix-regen-timeout-design.md": (
        "draft",
        "implementation",
        "lifecycle",
    ),
}


# Files / directories excluded from normalization.
EXCLUDED_DIRS = {
    ".git",
    ".venv",
    "node_modules",
    "docs/archive",
    "docs/.backups",
    "docs/.oneiric_cache",
    "scripts",
    ".pytest_cache",
    ".complexipy_cache",
    ".claude-plugin",
    ".claude",
    ".superpowers",
    "playwright-mcp",
    "settings",
    ".playwright-mcp",
    ".backups",
}

EXCLUDED_PATHS = {
    "docs/plans/PLAN_INDEX.md",
    "CLAUDE.md",
    "AGENTS.md",
    "README.md",  # top-level README (project, not docs)
}

# Schemas carry their own special frontmatter (set by the schema apply path).
SCHEMA_PATHS = {
    "docs/schemas/document-frontmatter-v1.md",
    "docs/schemas/topic-vocabulary-v1.md",
}

SCHEMA_FM = (
    "---\n"
    "status: active\n"
    "role: canonical\n"
    "topic: lifecycle\n"
    "date: 2026-07-17\n"
    "last_reviewed: 2026-07-17\n"
    "superseded_by: null\n"
    "blocks_on: []\n"
    "---\n"
    "\n"
)


def add_legacy_comment(text: str) -> str:
    """Append a trailing HTML legacy comment on the first 'Status:' / '**Status**' line.

    Mirrors _orphan_sweep_C1_2.py — only touches the first match.
    """
    lines = text.splitlines(keepends=True)
    for i, line in enumerate(lines):
        stripped = line.strip()
        # Match `**Status:**`, `**Status**`, `**Status** ...`, `## Status` etc.
        if stripped.startswith("**Status") and "Status" in stripped:
            original = stripped.rstrip("\n")
            if "<!-- legacy status" not in original:
                lines[i] = (
                    original + "  <!-- legacy status — see YAML frontmatter -->\n"
                )
            break
    return "".join(lines)


def is_excluded(rel: str) -> bool:
    if rel in EXCLUDED_PATHS:
        return True
    for d in EXCLUDED_DIRS:
        if d and rel.startswith(d.rstrip("/") + "/"):
            return True
    return False


def resolve_assignment(rel: str) -> tuple[str, str, str] | None:
    """Return (status, role, topic) or None if no assignment."""
    if rel in ASSIGNMENTS:
        return ASSIGNMENTS[rel]
    # Longest prefix wins among SUBDIR_DEFAULTS.
    best: tuple[str, str, str] | None = None
    best_len = -1
    for prefix, default in SUBDIR_DEFAULTS:
        if rel.startswith(prefix) and len(prefix) > best_len:
            best = default
            best_len = len(prefix)
    return best


def collect_targets() -> list[Path]:
    """Walk repo, return every .md under docs/ that should be normalized."""
    paths: list[Path] = []
    docs_root = REPO_ROOT / "docs"
    if not docs_root.is_dir():
        return paths
    for p in sorted(docs_root.rglob("*.md")):
        rel = p.relative_to(REPO_ROOT).as_posix()
        if is_excluded(rel):
            continue
        paths.append(p)
    return paths


def main() -> None:
    targets = collect_targets()
    results: list[tuple[str, str, str, str]] = []
    skipped: list[tuple[str, str]] = []

    # Schema files: special-case apply (status: active, role: canonical,
    # topic: lifecycle). Per playbook Step 3.
    for rel in SCHEMA_PATHS:
        path = REPO_ROOT / rel
        if not path.is_file():
            continue
        original = path.read_text(encoding="utf-8")
        if original.lstrip().startswith("---\n"):
            continue
        path.write_text(SCHEMA_FM + original, encoding="utf-8")
        results.append((rel, "active", "canonical", "lifecycle"))

    for path in targets:
        rel = path.relative_to(REPO_ROOT).as_posix()
        if rel in SCHEMA_PATHS:
            continue
        try:
            original = path.read_text(encoding="utf-8")
        except OSError as exc:
            skipped.append((rel, f"read-error: {exc}"))
            continue
        if original.lstrip().startswith("---\n"):
            skipped.append((rel, "already-framed"))
            continue
        assignment = resolve_assignment(rel)
        if assignment is None:
            skipped.append((rel, "no-assignment"))
            continue
        status, role, topic = assignment
        frontmatter = FM_TEMPLATE.format(status=status, role=role, topic=topic)
        body_with_comment = add_legacy_comment(original)
        new_content = frontmatter + body_with_comment
        path.write_text(new_content, encoding="utf-8")
        results.append((rel, status, role, topic))

    print(f"\nEdited {len(results)} files:")
    for rel, st, rl, tp in results:
        print(f"  {rel}: status={st} role={rl} topic={tp}")
    print(f"\nSkipped {len(skipped)} files:")
    for rel, reason in skipped:
        print(f"  {rel}: {reason}")


if __name__ == "__main__":
    main()
