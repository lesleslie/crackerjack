#!/usr/bin/env python3
"""
Documentation cleanup utility for crackerjack project.

This script uses the shared DocumentationCategorizer to analyze and categorize
documentation files. It provides the same 100% accuracy as the production
DocumentationCleanup service but doesn't move files - just reports.

Usage:
    python scripts/docs_cleanup.py --dry-run  # Preview changes
    python scripts/docs_cleanup.py --execute    # Execute cleanup (via production service)
"""

import argparse
from pathlib import Path

# Use the shared categorization logic
from crackerjack.services.doc_categorizer import DocumentationCategorizer


class DocCleanupAnalyzer:
    """Analyzes documentation files and categorizes them for cleanup.

    This is now a thin wrapper around DocumentationCategorizer, providing
    a convenient CLI interface with formatted reporting.
    """

    def __init__(self, docs_root: Path):
        """Initialize the analyzer with a documentation root directory.

        Args:
            docs_root: Path to directory containing markdown files
        """
        self.categorizer = DocumentationCategorizer(docs_root)

    def analyze(self) -> dict[str, list[dict]]:
        """Analyze all markdown files in docs root.

        Returns:
            Dictionary with categorized file lists
        """
        return self.categorizer.analyze_all()

    def generate_report(self, results: dict) -> str:
        """Generate a human-readable cleanup report.

        Args:
            results: Categorization results from analyze()

        Returns:
            Formatted report string
        """
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
        lines.append(f"📦 MOVE TO ARCHIVE: {total_archive} files")
        lines.append("-" * 80)

        # Group by destination
        for category in archive_categories:
            files = results.get(category, [])
            if files:
                # Extract destination from first file
                if files and "reason" in files[0]:
                    lines.append(f"\n  → {category.replace('_', '-').title()} ({len(files)} files)")
                    for item in files:
                        lines.append(f"     • {item['file']}")

        lines.append("")

        # Uncategorized
        if results["uncategorized"]:
            lines.append(f"❓ UNCATEGORIZED: {len(results['uncategorized'])} files")
            lines.append("-" * 80)
            for item in results["uncategorized"]:
                lines.append(f"  • {item['file']}")
            lines.append("")

        # Summary
        total = (
            len(results["keep_in_root"])
            + len(results.get("keep_in_docs", []))
            + len(results.get("implementation_plans", []))
            + total_archive
            + len(results["uncategorized"])
        )

        lines.append("=" * 80)
        lines.append("SUMMARY")
        lines.append("=" * 80)
        lines.append(f"Total files analyzed: {total}")
        lines.append(f"Keep in root: {len(results['keep_in_root'])}")
        lines.append(f"Keep in docs/: {len(results.get('keep_in_docs', []))}")
        lines.append(f"Implementation plans: {len(results.get('implementation_plans', []))}")
        lines.append(f"Move to archive: {total_archive}")
        lines.append(f"Uncategorized: {len(results['uncategorized'])}")
        lines.append("")

        return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Analyze documentation organization")
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

    # Note: Actual file movement is now handled by the production DocumentationCleanup service
    # which has backup, rollback, and security features. To execute cleanup, use:
    #   python -m crackerjack run --cleanup-docs
    # or with preview:
    #   python -m crackerjack run --cleanup-docs --docs-dry-run

    if results["uncategorized"]:
        print(
            "⚠️  Uncategorized files found. Consider adding patterns to "
            "DocumentationCategorizer.CATEGORIES in crackerjack/services/doc_categorizer.py"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
