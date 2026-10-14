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
    "session_artifacts",
    "test_artifacts",
    "temp_files",
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
                r"^CONTRIBUTING\.md$",
                r"^LICENSE$",
                r"^QUICKSTART\.md$",
                r"^ARCHITECTURE\.md$",
                r"^__main__\.py$",
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
                r"^PROFILES_.*\.md$",
            ],
            "destination": None,
            "reason": "Core documentation or completion milestones",
        },
        "keep_in_docs": {
            "patterns": [
                r"AI_FIX_EXPECTED_BEHAVIOR\.md",
                r"^CLAUDE_.*\.md$",
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
                r"REFACTORING_.*\.md",
            ],
            "destination": "implementation-plans",
            "reason": "Archived implementation plans",
        },
        "completion_reports": {
            "patterns": [
                r".*_COMPLETE\.md",
                r".*_COMPLETION\.md",
                r".*_FINAL.*\.md",
                r".*_SUMMARY.*\.md",
                r".*_REPORT\.md",
                r".*_report\.md",
                r".*_[A-Z]+_REPORT.*\.md",
                r".*_RESULTS\.md",
                r"FULL_WORKFLOW_.*\.md",
                r"V2_INTEGRATION_.*\.md",
                r"WORKFLOW_COORDINATOR_.*\.md",
            ],
            "destination": "summaries",
            "reason": "Historical completion reports and summaries",
        },
        "audits": {
            "patterns": [
                r".*_AUDIT\.md",
                r"AUDIT_.*\.md",
            ],
            "destination": "audits",
            "reason": "Audit documentation",
        },
        "investigations": {
            "patterns": [
                r".*_investigation\.md",
                r".*_INVESTIGATION\.md",
                r".*-investigation\.md",
                r"AI_FIX_.*\.md",
            ],
            "destination": "investigations",
            "reason": "Investigation reports",
        },
        "fixes": {
            "patterns": [
                r".*_FIXES?.*\.md",
                r".*_fix\.md",
                r".*_RESOLUTION\.md",
                r".*_APPLIED\.md",
                r"BUGFIX_.*\.md",
                r"FIX_.*\.md",
                r"CRITICAL_.*\.md",
            ],
            "destination": "sprints-and-fixes",
            "reason": "Fix documentation",
        },
        "sprints_and_fixes": {
            "patterns": [
                r".*_PROGRESS\.md",
                r".*_PROGRESS",
                r"FINAL_.*\.md",
                r".*_CONQUEST.*\.md",
                r".*_AGENT_.*\.md",
                r"PHASE_.*_PLAN\.md",
                r"PHASE_.*_STATUS\.md",
                r"PHASE_.*_COMPLETE.*\.md",
                r"BEFORE_AFTER_.*\.md",
                r"ISSUES_AND_.*\.md",
                r"CRACKERJACK_ADMIN.*\.md",
                r"SKILLS_.*\.md",
            ],
            "destination": "sprints-and-fixes",
            "reason": "Sprint progress and temporary documents",
        },
        "implementation_reports": {
            "patterns": [
                r"progress-.*\.md",
                r".*-implementation\.md",
                r".*_IMPLEMENTATION.*\.md",
                r".*_INTEGRATION.*\.md",
                r".*_DELIVERY\.md",
                r"TYPE_ERROR_.*\.md",
            ],
            "destination": "implementation-reports",
            "reason": "Implementation progress reports",
        },
        "analysis": {
            "patterns": [
                r".*_ANALYSIS\.md",
                r".*_analysis\.md",
                r".*_violations\.md",
                r".*-summary\.md",
                r"ARCHITECTURE_.*\.md",
                r"SESSION_.*\.md",
                r"TESTING_.*\.md",
                r"TEST_.*\.md",
                r"COVERAGE_.*\.md",
            ],
            "destination": "analysis",
            "reason": "Analysis documents and summaries",
        },
        "session_artifacts": {
            "patterns": [
                r"^session-.*\.md$",
                r"^SESSION_.*\.md$",
                r"^check_.*\.py$",
                r"^analyze_.*\.py$",
                r"^verify_.*\.py$",
            ],
            "destination": "session-artifacts",
            "reason": "Session and temporary analysis files",
        },
        "test_artifacts": {
            "patterns": [
                r"^test_.*\.py$",
                r"^test_.*\.txt$",
                r"\.backup$",
                r"^coverage\.json$",
                r"^report\.txt$",
                r"^TASK_.*\.txt$",
            ],
            "destination": "test-artifacts",
            "reason": "Test and temporary output files",
        },
        "temp_files": {
            "patterns": [
                r"^fix_.*\.py$",
                r"^complexipy_results_.*\.json$",
                r"^example\.mcp\.json$",
                r"^plugins\.json$",
                r"^pyproject\.toml\.backup$",
                r"^echo$",
            ],
            "destination": "temp-files",
            "reason": "Temporary files that should not be in project root",
        },
    }

    # Directories (relative to docs_root) whose `*.md` files this categorizer
    # scans for archival. The first entry ``.`` represents the project root
    # itself — root-level files are still in scope, they just route under
    # the synthetic ``docs`` archive area. The remaining entries cover
    # the per-area archives that land under
    # ``<area>/.archive/<category>/`` (e.g.
    # ``docs/plans/.archive/implementation-plans/``). Adding a directory
    # here also requires a matching ``!<area>/.archive/`` un-ignore rule
    # in ``.gitignore`` so the moved files stay tracked.
    SCANNED_ARCHIVE_AREAS: tuple[str, ...] = (
        ".",
        "docs",
        "docs/plans",
        "docs/specs",
        "docs/decisions",
    )

    def __init__(self, docs_root: Path) -> None:
        self.docs_root = docs_root

    def derive_archive_area(self, filepath: Path) -> str:
        """Return the archive area (relative to ``self.docs_root``) that a
        file should be archived under, derived from its parent directory.

        A file living in ``docs_root/foo.md`` is treated as belonging to the
        ``docs`` area (so it lands under ``docs/.archive/``). A file in
        ``docs_root/docs/plans/bar.md`` lands under
        ``docs/plans/.archive/``. Files in any other parent fall back to
        ``docs`` — we don't lose data, it just doesn't preserve the
        original subdirectory context.
        """
        try:
            relative = filepath.parent.relative_to(self.docs_root)
        except ValueError:
            return "docs"
        parts = relative.parts
        if not parts:
            return "docs"
        # Prefer the most-specific known area that is a prefix of the file's
        # relative parent.
        for area in sorted(self.SCANNED_ARCHIVE_AREAS, key=len, reverse=True):
            area_parts = tuple(area.split("/"))
            if parts[: len(area_parts)] == area_parts:
                return area
        return "docs"

    def archive_target_path(self, filepath: Path, category_subdir: str) -> Path:
        """Compose the full archive target path for ``filepath`` given its
        category subdir name. The result lives under
        ``<archive_area>/.archive/<category_subdir>/`` relative to the
        docs_root.
        """
        area = self.derive_archive_area(filepath)
        target_dir = self.docs_root / area / ".archive" / category_subdir
        return self._resolve_collision(target_dir / filepath.name)

    @staticmethod
    def _resolve_collision(target_path: Path) -> Path:
        """If ``target_path`` already exists, append a numeric suffix."""
        if not target_path.exists():
            return target_path
        suffixes = "".join(target_path.suffixes)
        stem = target_path.name[: -len(suffixes)] if suffixes else target_path.name
        counter = 1
        while True:
            candidate = target_path.with_name(
                f"{stem}__{counter:03d}{suffixes}"
                if suffixes
                else f"{stem}_{counter:03d}"
            )
            if not candidate.exists():
                return candidate
            counter += 1

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

        all_files = []
        for pattern in ("*.md", "*.py", "*.json", "*.txt", "*.backup"):
            all_files.extend(self.docs_root.glob(pattern))

        root_files = [f for f in all_files if f.parent == self.docs_root]

        for filepath in root_files:
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
        """Return the list of files that should be archived.

        Scans the project root plus every directory in
        :attr:`SCANNED_ARCHIVE_AREAS` (e.g. ``docs/plans``, ``docs/specs``,
        ``docs/decisions``). Files matching ``keep_in_root`` or
        ``keep_in_docs`` categories are excluded.
        """
        archivable: list[Path] = []
        seen: set[Path] = set()

        for area in self.SCANNED_ARCHIVE_AREAS:
            scan_root = self.docs_root / area
            if not scan_root.exists():
                continue
            for md_file in scan_root.glob("*.md"):
                if md_file in seen:
                    continue
                seen.add(md_file)
                result = self.categorize_file(md_file)
                if result.category and result.category not in {
                    "keep_in_root",
                    "keep_in_docs",
                }:
                    archivable.append(md_file)

        # Non-``.md`` artifacts (loose Python / JSON / txt / backup files)
        # only matter at the project root; their archive areas don't
        # compose meaningfully with the per-area scheme.
        other_patterns = ["*.py", "*.json", "*.txt", "*.backup"]
        for pattern in other_patterns:
            for file_path in self.docs_root.glob(pattern):
                if file_path.parent != self.docs_root:
                    continue
                if file_path in seen:
                    continue
                seen.add(file_path)
                result = self.categorize_file(file_path)
                if result.category and result.category not in {
                    "keep_in_root",
                    "keep_in_docs",
                }:
                    archivable.append(file_path)

        return archivable

    def get_archive_subdirectory(self, filepath: Path) -> str | None:
        """Return the category sub-directory for ``filepath``.

        ``CATEGORIES[*].destination`` is now the bare category name (e.g.
        ``"implementation-plans"``); the area prefix is composed by
        :meth:`archive_target_path`. Anything matching a non-``keep``
        category returns its subdirectory name; ``keep_in_root`` and
        ``keep_in_docs`` return ``None`` so the caller skips the file.
        """
        result = self.categorize_file(filepath)
        if not result.category or result.category in {
            "keep_in_root",
            "keep_in_docs",
        }:
            return None
        return result.destination

    def should_keep_in_root(self, filepath: Path) -> bool:
        result = self.categorize_file(filepath)
        return result.category == "keep_in_root"

    def should_keep_in_docs(self, filepath: Path) -> bool:
        result = self.categorize_file(filepath)
        return result.category == "keep_in_docs"
