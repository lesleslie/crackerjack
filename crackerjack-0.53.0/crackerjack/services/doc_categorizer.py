from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, TypedDict

logger = logging.getLogger(__name__)


DocCategory = Literal[
    "keep_in_root",
    "keep_in_docs",
    "implementation_plans",
    "completion_reports",
    "audits",
    "investigations",
    "fixes",
    "sprints_and_fixes",
    "implementation_reports",
    "analysis",
    "uncategorized",
]


class CategoryConfig(TypedDict):
    patterns: list[str]
    destination: str | None
    reason: str


@dataclass
class CategoryResult:
    category: DocCategory | None
    destination: str | None
    reason: str


class DocumentationCategorizer:
    CATEGORIES: dict[DocCategory, CategoryConfig] = {
        "keep_in_root": {
            "patterns": [
                r"^README\.md$",
                r"^CHANGELOG\.md$",
                r"^CLAUDE\.md$",
                r"^AGENTS\.md$",
                r"^RULES\.md$",
                r"^SECURITY\.md$",
                r"^QWEN\.md$",
                r"DOCS_ORGANIZATION\.md",
                r"DOCS_CLEANUP_GUIDELINES\.md",
                r"MCP_GLOBAL_MIGRATION_GUIDE\.md",
                r"MIGRATION_GUIDE_.*\.md",
                r"SKILL_SYSTEM\.md",
                r"STRUCTURED_LOGGING\.md",
                r"performance-baseline\.md",
                r"PHASE_.*_COMPLETION\.md",
                r"PYPROJECT_TIMEOUT_IMPLEMENTATION\.md",
                r"HOOK_ISSUE_COUNT_(ROOT_CAUSE|DISPLAY_OPTIONS)\.md",
                r"refurb_creosote_behavior\.md",
            ],
            "destination": None,
            "reason": "Core documentation or completion milestones",
        },
        "keep_in_docs": {
            "patterns": [
                r"AI_FIX_EXPECTED_BEHAVIOR\.md",
            ],
            "destination": "docs/",
            "reason": "User-facing documentation referenced by CLAUDE.md",
        },
        "implementation_plans": {
            "patterns": [
                r".*_PLAN\.md",
                r".*_plan\.md",
                r"TY_MIGRATION_PLAN\.md",
                r"implementation-plan-.*\.md",
                r".*_REFACTORING_PLAN.*\.md",
                r"refactoring-.*-plan\.md",
                r".*-plan-.*\.md",
            ],
            "destination": "docs/",
            "reason": "Active implementation plans (not completed)",
        },
        "completion_reports": {
            "patterns": [
                r".*_COMPLETE\.md",
                r".*_COMPLETION\.md",
                r".*_FINAL_REPORT\.md",
                r".*_SUMMARY\.md",
                r".*_COMPLETION_REPORT\.md",
                r".*_REPORT\.md",
                r".*_report\.md",
                r".*_[A-Z]+_REPORT.*\.md",
            ],
            "destination": "docs/archive/completion-reports/",
            "reason": "Historical completion reports",
        },
        "audits": {
            "patterns": [
                r".*_AUDIT\.md",
                r"AUDIT_.*\.md",
            ],
            "destination": "docs/archive/audits/",
            "reason": "Audit documentation",
        },
        "investigations": {
            "patterns": [
                r".*_investigation\.md",
                r".*_INVESTIGATION\.md",
                r".*-investigation\.md",
            ],
            "destination": "docs/archive/investigations/",
            "reason": "Investigation reports",
        },
        "fixes": {
            "patterns": [
                r".*_FIXES?\.md",
                r".*_fix\.md",
                r".*_RESOLUTION\.md",
            ],
            "destination": "docs/archive/sprints-and-fixes/",
            "reason": "Fix documentation",
        },
        "sprints_and_fixes": {
            "patterns": [
                r".*_PROGRESS\.md",
                r".*_PROGRESS",
                r"FINAL_.*\.md",
                r".*_CONQUEST.*\.md",
                r".*_AGENT_.*\.md",
                r"ZUBAN_.*\.md",
                r"PHASE_.*_PLAN\.md",
            ],
            "destination": "docs/archive/sprints-and-fixes/",
            "reason": "Sprint progress and temporary documents",
        },
        "implementation_reports": {
            "patterns": [
                r"progress-.*\.md",
                r".*-implementation\.md",
            ],
            "destination": "docs/archive/implementation-reports/",
            "reason": "Implementation progress reports",
        },
        "analysis": {
            "patterns": [
                r".*_ANALYSIS\.md",
                r".*_analysis\.md",
                r".*_violations\.md",
                r".*-summary\.md",
            ],
            "destination": "docs/archive/analysis/",
            "reason": "Analysis documents and summaries",
        },
    }

    def __init__(self, docs_root: Path) -> None:
        self.docs_root = docs_root

    def categorize_file(self, filepath: Path) -> CategoryResult:
        filename = filepath.name

        for category, config in self.CATEGORIES.items():
            for pattern in config["patterns"]:
                if re.match(pattern, filename, re.IGNORECASE):
                    return CategoryResult(
                        category=category,
                        destination=config["destination"],
                        reason=config["reason"],
                    )

        return CategoryResult(
            category=None,
            destination=None,
            reason="No matching pattern found",
        )

    def analyze_all(self) -> dict[str, list[dict[str, str]]]:
        results: dict[str, list[dict[str, str]]] = {
            category: []
            for category in list(self.CATEGORIES.keys()) + ["uncategorized"]
        }

        md_files = list(self.docs_root.glob("*.md"))

        for filepath in md_files:
            result = self.categorize_file(filepath)

            file_info: dict[str, str] = {
                "file": filepath.name,
                "path": str(filepath),
            }

            if result.category:
                file_info["reason"] = result.reason
                results[result.category].append(file_info)
            else:
                results["uncategorized"].append(file_info)

        return results

    def get_archivable_files(self) -> list[Path]:
        archivable = []

        for md_file in self.docs_root.glob("*.md"):
            result = self.categorize_file(md_file)

            if result.category and not result.category.startswith("keep_in_"):
                archivable.append(md_file)

        return archivable

    def get_archive_subdirectory(self, filepath: Path) -> str | None:
        result = self.categorize_file(filepath)

        if not result.destination:
            return None

        dest_path = Path(result.destination)
        if "archive" in dest_path.parts:
            idx = dest_path.parts.index("archive")
            if idx + 1 < len(dest_path.parts):
                return dest_path.parts[idx + 1]

        return dest_path.parts[-1] if dest_path.parts else None

    def should_keep_in_root(self, filepath: Path) -> bool:
        result = self.categorize_file(filepath)
        return result.category == "keep_in_root"

    def should_keep_in_docs(self, filepath: Path) -> bool:
        result = self.categorize_file(filepath)
        return result.category == "keep_in_docs"
