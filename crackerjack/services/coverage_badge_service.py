from contextlib import suppress
from pathlib import Path

from acb.console import Console
from acb.depends import Inject, depends

from .regex_patterns import SAFE_PATTERNS


class CoverageBadgeService:
    """Service for managing coverage badges in README.md files."""

    @depends.inject
    def __init__(self, console: Inject[Console], project_root: Path) -> None:
        self.console = console
        self.project_root = project_root
        self.readme_path = project_root / "README.md"

    def update_readme_coverage_badge(self, coverage_percent: float) -> bool:
        """Update or insert coverage badge in README.md with current coverage percentage."""
        if not self.readme_path.exists():
            self.console.print(
                "[yellow]⚠️[/yellow] README.md not found, skipping badge update"
            )
            return False

        try:
            readme_content = self.readme_path.read_text(encoding="utf-8")
            badge_url = self._generate_badge_url(coverage_percent)

            if self._has_coverage_badge(readme_content):
                updated_content = self._update_existing_badge(readme_content, badge_url)
                action = "updated"
            else:
                updated_content = self._insert_new_badge(readme_content, badge_url)
                action = "added"

            if updated_content != readme_content:
                self.readme_path.write_text(updated_content, encoding="utf-8")
                self.console.print(
                    f"[green]📊[/green] Coverage badge {action}: {coverage_percent:.1f}%"
                )
                return True
            else:
                return False

        except Exception as e:
            self.console.print(f"[red]❌[/red] Failed to update coverage badge: {e}")
            return False

    def _generate_badge_url(self, coverage_percent: float) -> str:
        """Generate shields.io badge URL with appropriate color coding."""
        color = self._get_badge_color(coverage_percent)
        # URL encode the % symbol as %25
        encoded_percent = f"{coverage_percent:.1f}%25"
        return f"https://img.shields.io/badge/coverage-{encoded_percent}-{color}"

    def _get_badge_color(self, coverage_percent: float) -> str:
        """Determine badge color based on coverage percentage."""
        if coverage_percent < 50:
            return "red"
        elif coverage_percent < 80:
            return "yellow"
        return "brightgreen"

    def _has_coverage_badge(self, content: str) -> bool:
        """Check if README already contains a coverage badge."""
        # Use safe pattern for badge detection
        return SAFE_PATTERNS["detect_coverage_badge"].search(content) is not None

    def _update_existing_badge(self, content: str, new_badge_url: str) -> str:
        """Replace existing coverage badge with new one."""
        # Try different safe patterns for badge replacement
        patterns_to_try = [
            "update_coverage_badge_url",
            "update_coverage_badge_any",
            "update_shields_coverage_url",
        ]

        for pattern_name in patterns_to_try:
            pattern_obj = SAFE_PATTERNS[pattern_name]
            # Use the pattern and manually replace NEW_BADGE_URL with actual URL
            temp_content = pattern_obj.apply(content)
            if temp_content != content:
                # Replace placeholder with actual URL
                new_content = temp_content.replace("NEW_BADGE_URL", new_badge_url)
                return new_content

        return content

    def _insert_new_badge(self, content: str, badge_url: str) -> str:
        """Insert new coverage badge in the appropriate location."""
        lines = content.split("\n")

        # Find the badge section (after title, before first heading)
        insert_index = self._find_badge_insertion_point(lines)

        if insert_index is not None:
            coverage_badge = f"![Coverage]({badge_url})"
            lines.insert(insert_index, coverage_badge)
            return "\n".join(lines)
        # Fallback: add after title
        return self._insert_after_title(content, badge_url)

    def _find_badge_insertion_point(self, lines: list[str]) -> int | None:
        """Find the best location to insert the coverage badge."""
        # Look for existing badge lines
        badge_lines = [
            i for i, line in enumerate(lines) if line.strip().startswith(("[![", "!["))
        ]

        if badge_lines:
            # Insert after the last existing badge
            return badge_lines[-1] + 1

        # Look for first non-empty line after title
        title_found = False
        for i, line in enumerate(lines):
            if line.startswith("#") and not title_found:
                title_found = True
                continue
            elif title_found and line.strip() == "":
                continue
            elif title_found and line.strip():
                return i

        return None

    def _insert_after_title(self, content: str, badge_url: str) -> str:
        """Fallback method to insert badge after the title."""
        lines = content.split("\n")

        # Find title line
        for i, line in enumerate(lines):
            if line.startswith("#"):
                # Insert after title with blank line
                coverage_badge = f"![Coverage]({badge_url})"
                if i + 1 < len(lines) and lines[i + 1].strip() == "":
                    lines.insert(i + 2, coverage_badge)
                else:
                    lines.insert(i + 1, "")
                    lines.insert(i + 2, coverage_badge)
                break

        return "\n".join(lines)

    def should_update_badge(self, coverage_percent: float) -> bool:
        """Check if badge should be updated based on coverage change."""
        if not self.readme_path.exists():
            return False

        try:
            content = self.readme_path.read_text(encoding="utf-8")
            current_coverage = self._extract_current_coverage(content)

            if current_coverage is None:
                return True  # No badge exists, should add one

            # Only update if coverage changed by at least 0.01% (more accurate reporting)
            return abs(coverage_percent - current_coverage) >= 0.01

        except Exception:
            return True  # On error, attempt update

    def _extract_current_coverage(self, content: str) -> float | None:
        """Extract current coverage percentage from existing badge."""
        match = SAFE_PATTERNS["extract_coverage_percentage"].search(content)

        if match:
            with suppress(ValueError):
                return float(match.group(1))

        return None
