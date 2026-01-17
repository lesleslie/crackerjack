#!/usr/bin/env python3
"""
Documentation cleanup utility for crackerjack project.

This script identifies and organizes documentation files based on their type:
- Implementation plans (stay in root or docs/)
- Completion reports (move to docs/archive/completion-reports/)
- Audit/investigation docs (move to appropriate archive subdirs)
- Temporary sprint docs (move to docs/archive/sprints-and-fixes/)

Usage:
    python scripts/docs_cleanup.py --dry-run  # Preview changes
    python scripts/docs_cleanup.py --execute    # Execute cleanup
"""

import argparse
import re
from pathlib import Path
from typing import Dict, List


class DocCleanupAnalyzer:
    """Analyzes documentation files and categorizes them for cleanup."""

    # File patterns and their destinations
    CATEGORIES = {
        "keep_in_root": {
            "patterns": [
                r"^README\.md$",
                r"^CHANGELOG\.md$",
                r"^CLAUDE\.md$",
                r"^AGENTS\.md$",
                r"^RULES\.md$",
                r"^SECURITY\.md$",
                r"^QWEN\.md$",
                r"DOCS_ORGANIZATION\.md$",
                r"DOCS_CLEANUP_GUIDELINES\.md$",
                r"MCP_GLOBAL_MIGRATION_GUIDE\.md$",
                r"MIGRATION_GUIDE_.*\.md$",
                r"SKILL_SYSTEM\.md$",
                r"STRUCTURED_LOGGING\.md$",
                r"performance-baseline\.md$",
                r"PHASE_.*_COMPLETION\.md$",
                r"PYPROJECT_TIMEOUT_IMPLEMENTATION\.md$",
                r"HOOK_ISSUE_COUNT_(ROOT_CAUSE|DISPLAY_OPTIONS)\.md$",
                r"refurb_creosote_behavior\.md$",
            ],
            "destination": None,  # Keep in root
            "reason": "Core documentation or completion milestones",
        },
        "keep_in_docs": {
            "patterns": [
                r"AI_FIX_EXPECTED_BEHAVIOR\.md$",  # User-facing, referenced by CLAUDE.md
            ],
            "destination": "docs/",
            "reason": "User-facing documentation referenced by CLAUDE.md",
        },
        "implementation_plans": {
            "patterns": [
                r".*_PLAN\.md$",
                r".*_plan\.md$",
                r"TY_MIGRATION_PLAN\.md$",
                r"implementation-plan-.*\.md$",
                r".*_REFACTORING_PLAN.*\.md$",
                r"refactoring-.*-plan\.md$",
                r".*-plan-.*\.md$",
            ],
            "destination": "docs/",  # Keep in docs root as active plans
            "reason": "Active implementation plans (not completed)",
        },
        "completion_reports": {
            "patterns": [
                r".*_COMPLETE\.md$",
                r".*_COMPLETION\.md$",
                r".*_FINAL_REPORT\.md$",
                r".*_SUMMARY\.md$",
                r".*_COMPLETION_REPORT\.md$",
                r".*_REPORT\.md$",
                r".*_report\.md$",
                r".*_[A-Z]+_REPORT.*\.md$",
            ],
            "destination": "docs/archive/completion-reports/",
            "reason": "Historical completion reports",
        },
        "audits": {
            "patterns": [
                r".*_AUDIT\.md$",
                r"AUDIT_.*\.md$",
            ],
            "destination": "docs/archive/audits/",
            "reason": "Audit documentation",
        },
        "investigations": {
            "patterns": [
                r".*_investigation\.md$",
                r".*_INVESTIGATION\.md$",
                r".*-investigation\.md$",
            ],
            "destination": "docs/archive/investigations/",
            "reason": "Investigation reports",
        },
        "fixes": {
            "patterns": [
                r".*_FIXES?\.md$",
                r".*_fix\.md$",
                r".*_RESOLUTION\.md$",
            ],
            "destination": "docs/archive/sprints-and-fixes/",
            "reason": "Fix documentation",
        },
        "sprints_and_fixes": {
            "patterns": [
                r".*_PROGRESS\.md$",
                r".*_PROGRESS$",
                r"FINAL_.*\.md$",
                r".*_CONQUEST.*\.md$",
                r".*_AGENT_.*\.md$",
                r"ZUBAN_.*\.md$",
                r"PHASE_.*_PLAN\.md$",
            ],
            "destination": "docs/archive/sprints-and-fixes/",
            "reason": "Sprint progress and temporary documents",
        },
        "implementation_reports": {
            "patterns": [
                r"progress-.*\.md$",
                r".*-implementation\.md$",
            ],
            "destination": "docs/archive/implementation-reports/",
            "reason": "Implementation progress reports",
        },
        "analysis": {
            "patterns": [
                r".*_ANALYSIS\.md$",
                r".*_analysis\.md$",
                r".*_violations\.md$",
                r".*-summary\.md$",
            ],
            "destination": "docs/archive/analysis/",
            "reason": "Analysis documents and summaries",
        },
    }

    def __init__(self, docs_root: Path):
        self.docs_root = docs_root

    def categorize_file(self, filepath: Path) -> tuple[str, str] | None:
        """Categorize a single file and return (category, destination)."""
        filename = filepath.name

        for category, config in self.CATEGORIES.items():
            for pattern in config["patterns"]:
                if re.match(pattern, filename, re.IGNORECASE):
                    return (category, config["destination"])

        return None

    def analyze(self) -> Dict[str, List[Dict]]:
        """Analyze all markdown files in docs root."""
        results = {
            "keep_in_root": [],
            "keep_in_docs": [],
            "implementation_plans": [],
            "move_to_archive": [],
            "uncategorized": [],
        }

        md_files = list(self.docs_root.glob("*.md"))

        for filepath in md_files:
            categorization = self.categorize_file(filepath)

            if categorization is None:
                results["uncategorized"].append({
                    "file": filepath.name,
                    "path": str(filepath),
                })
            elif categorization[0] == "keep_in_root":
                results["keep_in_root"].append({
                    "file": filepath.name,
                    "path": str(filepath),
                    "reason": self.CATEGORIES["keep_in_root"]["reason"],
                })
            elif categorization[1] is None:
                # Keep in same location
                category = categorization[0]
                results[category].append({
                    "file": filepath.name,
                    "path": str(filepath),
                    "reason": self.CATEGORIES[category]["reason"],
                })
            else:
                results["move_to_archive"].append({
                    "file": filepath.name,
                    "path": str(filepath),
                    "destination": categorization[1],
                    "category": categorization[0],
                    "reason": self.CATEGORIES[categorization[0]]["reason"],
                })

        return results

    def generate_report(self, results: Dict) -> str:
        """Generate a human-readable cleanup report."""
        lines = []
        lines.append("=" * 80)
        lines.append("DOCUMENTATION CLEANUP ANALYSIS")
        lines.append("=" * 80)
        lines.append("")

        # Keep in root
        lines.append(f"✅ KEEP IN ROOT: {len(results['keep_in_root'])} files")
        lines.append("-" * 80)
        for item in results["keep_in_root"]:
            lines.append(f"  • {item['file']}")
            lines.append(f"    Reason: {item['reason']}")
        lines.append("")

        # Keep in docs (but not root)
        if results.get("keep_in_docs"):
            lines.append(f"✅ KEEP IN DOCS/: {len(results['keep_in_docs'])} files")
            lines.append("-" * 80)
            for item in results["keep_in_docs"]:
                lines.append(f"  • {item['file']}")
                lines.append(f"    Reason: {item['reason']}")
            lines.append("")

        # Implementation plans
        if results.get("implementation_plans"):
            lines.append(f"📋 IMPLEMENTATION PLANS: {len(results['implementation_plans'])} files")
            lines.append("-" * 80)
            for item in results["implementation_plans"]:
                lines.append(f"  • {item['file']}")
                lines.append(f"    Reason: {item['reason']}")
            lines.append("")

        # Move to archive
        lines.append(f"📦 MOVE TO ARCHIVE: {len(results['move_to_archive'])} files")
        lines.append("-" * 80)

        # Group by destination
        by_destination = {}
        for item in results["move_to_archive"]:
            dest = item["destination"]
            if dest not in by_destination:
                by_destination[dest] = []
            by_destination[dest].append(item)

        for dest, files in sorted(by_destination.items()):
            lines.append(f"\n  → {dest} ({len(files)} files)")
            for item in files:
                lines.append(f"     • {item['file']} ({item['category']})")

        lines.append("")

        # Uncategorized
        if results["uncategorized"]:
            lines.append(f"❓ UNCATEGORIZED: {len(results['uncategorized'])} files")
            lines.append("-" * 80)
            for item in results["uncategorized"]:
                lines.append(f"  • {item['file']}")
            lines.append("")

        # Summary
        total = len(results["keep_in_root"]) + len(results.get("keep_in_docs", [])) + \
                len(results.get("implementation_plans", [])) + len(results["move_to_archive"]) + \
                len(results["uncategorized"])

        lines.append("=" * 80)
        lines.append("SUMMARY")
        lines.append("=" * 80)
        lines.append(f"Total files analyzed: {total}")
        lines.append(f"Keep in root: {len(results['keep_in_root'])}")
        lines.append(f"Keep in docs/: {len(results.get('keep_in_docs', []))}")
        lines.append(f"Implementation plans: {len(results.get('implementation_plans', []))}")
        lines.append(f"Move to archive: {len(results['move_to_archive'])}")
        lines.append(f"Uncategorized: {len(results['uncategorized'])}")
        lines.append("")

        return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Analyze and clean up documentation files"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes"
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Execute the cleanup (moves files to archive)"
    )
    parser.add_argument(
        "--docs-root",
        type=Path,
        default=Path.cwd() / "docs",
        help="Path to docs directory (default: cwd/docs)"
    )

    args = parser.parse_args()

    if not args.dry_run and not args.execute:
        parser.print_help()
        return 1

    analyzer = DocCleanupAnalyzer(args.docs_root)
    results = analyzer.analyze()
    report = analyzer.generate_report(results)

    print(report)

    if args.execute:
        print("=" * 80)
        print("EXECUTING CLEANUP...")
        print("=" * 80)
        print("NOTE: Archive directory is gitignored - files moved there will not")
        print("      be tracked by git. This is intentional for historical docs.")
        print("")
        print("This would move files, but for safety, please review the dry-run")
        print("output first and manually move files if needed.")
        print("")
        # TODO: Implement actual file movement
        # for item in results["move_to_archive"]:
        #     src = Path(item["path"])
        #     dst = args.docs_root / item["destination"] / src.name
        #     dst.parent.mkdir(parents=True, exist_ok=True)
        #     src.rename(dst)
        #     print(f"  ✓ Moved {src.name} → {item['destination']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
