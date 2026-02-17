#!/usr/bin/env python3

import argparse
import re
from pathlib import Path


class DocCleanupAnalyzer:
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
            "destination": None,
            "reason": "Core documentation or completion milestones",
        },
        "keep_in_docs": {
            "patterns": [
                r"AI_FIX_EXPECTED_BEHAVIOR\.md$",
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
            "destination": "docs/",
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
        filename = filepath.name

        for category, config in self.CATEGORIES.items():
            for pattern in config["patterns"]:
                if re.match(pattern, filename, re.IGNORECASE):
                    return (category, config["destination"])

        return None

    def analyze(self) -> dict[str, list[dict]]:
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
                results["uncategorized"].append(
                    {
                        "file": filepath.name,
                        "path": str(filepath),
                    }
                )
            elif categorization[0] == "keep_in_root":
                results["keep_in_root"].append(
                    {
                        "file": filepath.name,
                        "path": str(filepath),
                        "reason": self.CATEGORIES["keep_in_root"]["reason"],
                    }
                )
            elif categorization[1] is None:
                category = categorization[0]
                results[category].append(
                    {
                        "file": filepath.name,
                        "path": str(filepath),
                        "reason": self.CATEGORIES[category]["reason"],
                    }
                )
            else:
                results["move_to_archive"].append(
                    {
                        "file": filepath.name,
                        "path": str(filepath),
                        "destination": categorization[1],
                        "category": categorization[0],
                        "reason": self.CATEGORIES[categorization[0]]["reason"],
                    }
                )

        return results

    def generate_report(self, results: dict) -> str:
        lines = []
        lines.extend(["=" * 80, "DOCUMENTATION CLEANUP ANALYSIS", "=" * 80, ""])

        lines.extend(
            [f"✅ KEEP IN ROOT: {len(results['keep_in_root'])} files", "-" * 80]
        )
        for item in results["keep_in_root"]:
            lines.extend([f"  • {item['file']}", f"    Reason: {item['reason']}"])
        lines.append("")

        if results.get("keep_in_docs"):
            lines.extend(
                [f"✅ KEEP IN DOCS/: {len(results['keep_in_docs'])} files", "-" * 80]
            )
            for item in results["keep_in_docs"]:
                lines.extend([f"  • {item['file']}", f"    Reason: {item['reason']}"])
            lines.append("")

        if results.get("implementation_plans"):
            lines.extend(
                [
                    f"📋 IMPLEMENTATION PLANS: {len(results['implementation_plans'])} files",
                    "-" * 80,
                ]
            )
            for item in results["implementation_plans"]:
                lines.extend([f"  • {item['file']}", f"    Reason: {item['reason']}"])
            lines.append("")

        archive_categories = [
            "completion_reports",
            "audits",
            "investigations",
            "fixes",
            "sprints_and_fixes",
            "implementation_reports",
            "analysis",
        ]

        total_archive = sum(len(results.get(cat, [])) for cat in archive_categories)
        lines.extend([f"📦 MOVE TO ARCHIVE: {total_archive} files", "-" * 80])

        for category in archive_categories:
            files = results.get(category, [])
            if files:
                if files and "reason" in files[0]:
                    lines.append(
                        f"\n  → {category.replace('_', '-').title()} ({len(files)} files)"
                    )
                    for item in files:
                        lines.append(f"     • {item['file']}")

        lines.extend(
            [f"📦 MOVE TO ARCHIVE: {len(results['move_to_archive'])} files", "-" * 80]
        )

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

        if results["uncategorized"]:
            lines.extend(
                [f"❓ UNCATEGORIZED: {len(results['uncategorized'])} files", "-" * 80]
            )
            for item in results["uncategorized"]:
                lines.append(f"  • {item['file']}")
            lines.append("")

        total = (
            len(results["keep_in_root"])
            + len(results.get("keep_in_docs", []))
            + len(results.get("implementation_plans", []))
            + total_archive
            + len(results["move_to_archive"])
            + len(results["uncategorized"])
        )

        lines.extend(
            [
                "=" * 80,
                "SUMMARY",
                "=" * 80,
                f"Total files analyzed: {total}",
                f"Keep in root: {len(results['keep_in_root'])}",
                f"Keep in docs/: {len(results.get('keep_in_docs', []))}",
                f"Implementation plans: {len(results.get('implementation_plans', []))}",
                f"Move to archive: {total_archive}",
                f"Implementation plans: {len(results.get('implementation_plans', []))}",
                f"Move to archive: {len(results['move_to_archive'])}",
                f"Uncategorized: {len(results['uncategorized'])}",
                "",
            ]
        )

        return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Analyze documentation organization")
    parser = argparse.ArgumentParser(
        description="Analyze and clean up documentation files"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Execute the cleanup (moves files to archive)",
    )
    parser.add_argument(
        "--docs-root",
        type=Path,
        default=Path.cwd() / "docs",
        help="Path to docs directory (default: cwd/docs)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show analysis without making changes (default behavior)",
    )

    args = parser.parse_args()

    analyzer = DocCleanupAnalyzer(args.docs_root)
    results = analyzer.analyze()
    report = analyzer.generate_report(results)

    print(report)

    if results["uncategorized"]:
        print(
            "⚠️  Uncategorized files found. Consider adding patterns to "
            "DocumentationCategorizer.CATEGORIES in crackerjack/services/doc_categorizer.py"
        )
    if args.execute:
        print("=" * 80)
        print("EXECUTING CLEANUP...")
        print("=" * 80)
        print("NOTE: Archive directory is gitignored - files moved there will not")
        print("      be tracked by git. This is intentional for historical docs.")
        print()
        print("This would move files, but for safety, please review the dry-run")
        print("output first and manually move files if needed.")
        print()
        # TODO: Implement actual file movement

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
