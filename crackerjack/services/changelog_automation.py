import re
import typing as t
from datetime import datetime
from pathlib import Path

from rich.console import Console


class ChangelogEntry:
    def __init__(
        self,
        entry_type: str,
        description: str,
        commit_hash: str = "",
        breaking_change: bool = False,
    ) -> None:
        self.type = entry_type
        self.description = description
        self.commit_hash = commit_hash
        self.breaking_change = breaking_change

    def to_markdown(self) -> str:
        prefix = "**BREAKING:** " if self.breaking_change else ""
        return f"- {prefix}{self.description}"


class ChangelogGenerator:
    def __init__(
        self,
        console: Console | None = None,
        git_service: t.Any = None,
    ) -> None:
        self.console = console or Console()
        self.git = git_service

        self.type_mappings = {
            "feat": "Added",
            "fix": "Fixed",
            "docs": "Documentation",
            "style": "Changed",
            "refactor": "Changed",
            "test": "Testing",
            "chore": "Internal",
            "perf": "Performance",
            "build": "Build",
            "ci": "CI/CD",
            "revert": "Reverted",
        }

        self.conventional_commit_pattern = re.compile(  # REGEX OK: conventional commit parsing
            r"^(?P<type>\w+)(?:\((?P<scope>[^)]+)\))?(?P<breaking>!)?:\s*(?P<description>.+)$"
        )

        self.breaking_change_pattern = (
            re.compile(  # REGEX OK: breaking change detection
                r"BREAKING\s*CHANGE[:]\s*(.+)", re.IGNORECASE | re.MULTILINE
            )
        )

    def parse_commit_message(
        self, commit_message: str, commit_hash: str = ""
    ) -> ChangelogEntry | None:
        lines = commit_message.strip().split("\n")
        header = lines[0].strip()
        body = "\n".join(lines[1:]).strip() if len(lines) > 1 else ""

        match = self.conventional_commit_pattern.match(header)
        if not match:
            return self._parse_non_conventional_commit(header, body, commit_hash)

        commit_type = match.group("type").lower()
        scope = match.group("scope") or ""
        breaking_marker = match.group("breaking") == "!"
        description = match.group("description").strip()

        breaking_in_body = bool(self.breaking_change_pattern.search(body))
        breaking_change = breaking_marker or breaking_in_body

        changelog_section = self.type_mappings.get(commit_type, "Changed")

        formatted_description = self._format_description(
            description, scope, commit_type
        )

        return ChangelogEntry(
            entry_type=changelog_section,
            description=formatted_description,
            commit_hash=commit_hash,
            breaking_change=breaking_change,
        )

    def _parse_non_conventional_commit(
        self, header: str, body: str, commit_hash: str
    ) -> ChangelogEntry | None:
        header_lower = header.lower()

        if any(
            keyword in header_lower for keyword in ("add", "new", "create", "implement")
        ):
            entry_type = "Added"
        elif any(
            keyword in header_lower for keyword in ("fix", "bug", "resolve", "correct")
        ):
            entry_type = "Fixed"
        elif any(
            keyword in header_lower
            for keyword in ("update", "change", "modify", "improve")
        ):
            entry_type = "Changed"
        elif any(keyword in header_lower for keyword in ("remove", "delete", "drop")):
            entry_type = "Removed"
        elif any(keyword in header_lower for keyword in ("doc", "readme", "comment")):
            entry_type = "Documentation"
        else:
            entry_type = "Changed"

        breaking_change = bool(self.breaking_change_pattern.search(body))

        return ChangelogEntry(
            entry_type=entry_type,
            description=header,
            commit_hash=commit_hash,
            breaking_change=breaking_change,
        )

    def _format_description(
        self, description: str, scope: str, commit_type: str
    ) -> str:
        description = description[0].upper() + description[1:] if description else ""

        if scope:
            if scope.lower() not in description.lower():
                description = f"{scope}: {description}"

        return description

    def generate_changelog_entries(
        self, since_version: str | None = None, target_file: Path | None = None
    ) -> dict[str, list[ChangelogEntry]]:
        try:
            git_result = self._get_git_commits(since_version)
            if not git_result:
                return {}

            return self._parse_commits_to_entries(git_result)

        except Exception as e:
            self.console.print(f"[red]❌[/red] Error generating changelog entries: {e}")
            return {}

    def _get_git_commits(self, since_version: str | None = None) -> str | None:
        git_command = self._build_git_log_command(since_version)

        result = self.git._run_git_command(git_command)
        if result.returncode != 0:
            self.console.print(
                f"[yellow]⚠️[/yellow] Failed to get git log: {result.stderr}"
            )
            return None

        return result.stdout

    def _build_git_log_command(self, since_version: str | None = None) -> list[str]:
        if since_version:
            return [
                "log",
                f"{since_version}..HEAD",
                "--oneline",
                "--no-merges",
            ]

        return ["log", "-50", "--oneline", "--no-merges"]

    def _parse_commits_to_entries(
        self, git_output: str
    ) -> dict[str, list[ChangelogEntry]]:
        entries_by_type: dict[str, list[ChangelogEntry]] = {}

        for line in git_output.strip().split("\n"):
            if not line.strip():
                continue

            entry = self._process_commit_line(line)
            if entry:
                self._add_entry_to_collection(entry, entries_by_type)

        return entries_by_type

    def _process_commit_line(self, line: str) -> ChangelogEntry | None:
        parts = line.strip().split(" ", 1)
        if len(parts) < 2:
            return None

        commit_hash = parts[0]
        commit_message = parts[1]

        full_message = self._get_full_commit_message(commit_hash, commit_message)

        return self.parse_commit_message(full_message, commit_hash)

    def _get_full_commit_message(self, commit_hash: str, fallback_message: str) -> str:
        full_commit_result = self.git._run_git_command(
            ["show", "--format=%B", "--no-patch", commit_hash]
        )

        return (
            full_commit_result.stdout
            if full_commit_result.returncode == 0
            else fallback_message
        )

    def _add_entry_to_collection(
        self, entry: ChangelogEntry, entries_by_type: dict[str, list[ChangelogEntry]]
    ) -> None:
        if entry.type not in entries_by_type:
            entries_by_type[entry.type] = []
        entries_by_type[entry.type].append(entry)

    def update_changelog(
        self,
        changelog_path: Path,
        new_version: str,
        entries_by_type: dict[str, list[ChangelogEntry]] | None = None,
    ) -> bool:
        try:
            if entries_by_type is None:
                entries_by_type = self.generate_changelog_entries()

            if not entries_by_type:
                self.console.print("[yellow]ℹ️[/yellow] No new changelog entries to add")
                return True

            existing_content = ""
            if changelog_path.exists():
                existing_content = changelog_path.read_text(encoding="utf-8")

            new_section = self._generate_changelog_section(new_version, entries_by_type)

            updated_content = self._insert_new_section(existing_content, new_section)

            changelog_path.write_text(updated_content, encoding="utf-8")

            self.console.print(
                f"[green]✅[/green] Updated {changelog_path.name} with {len(entries_by_type)} sections"
            )
            return True

        except Exception as e:
            self.console.print(f"[red]❌[/red] Failed to update changelog: {e}")
            return False

    def _generate_changelog_section(
        self, version: str, entries_by_type: dict[str, list[ChangelogEntry]]
    ) -> str:
        today = datetime.now().strftime("%Y-%m-%d")
        section_lines = [f"## [{version}] - {today}", ""]

        section_order = [
            "Added",
            "Changed",
            "Fixed",
            "Removed",
            "Performance",
            "Security",
            "Deprecated",
            "Documentation",
            "Testing",
            "Build",
            "CI/CD",
            "Internal",
        ]

        for section_name in section_order:
            if section_name in entries_by_type:
                entries = entries_by_type[section_name]
                if entries:
                    section_lines.extend((f"### {section_name}", ""))

                    entries.sort(
                        key=lambda e: (not e.breaking_change, e.description.lower())
                    )

                    for entry in entries:
                        section_lines.append(entry.to_markdown())
                    section_lines.append("")

        return "\n".join(section_lines)

    def _insert_new_section(self, existing_content: str, new_section: str) -> str:
        if not existing_content.strip():
            header = """# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

"""
            return header + new_section

        lines = existing_content.split("\n")
        insert_index = 0

        for i, line in enumerate(lines):
            if line.strip().startswith("## ["):
                insert_index = i
                break
        else:
            insert_index = len(lines)

        new_lines = (
            lines[:insert_index] + new_section.split("\n") + lines[insert_index:]
        )
        return "\n".join(new_lines)

    def generate_changelog_from_commits(
        self, changelog_path: Path, version: str, since_version: str | None = None
    ) -> bool:
        self.console.print(
            f"[cyan]📝[/cyan] Generating changelog entries for version {version}..."
        )

        entries = self.generate_changelog_entries(since_version)
        if not entries:
            self.console.print("[yellow]ℹ️[/yellow] No changelog entries generated")
            return True

        self._display_changelog_preview(entries)

        return self.update_changelog(changelog_path, version, entries)

    def _display_changelog_preview(
        self, entries_by_type: dict[str, list[ChangelogEntry]]
    ) -> None:
        self.console.print("[cyan]📋[/cyan] Changelog preview:")

        for section_name, entries in entries_by_type.items():
            if entries:
                self.console.print(f"[bold]{section_name}:[/bold]")
                for entry in entries[:3]:
                    self.console.print(f" {entry.to_markdown()}")
                if len(entries) > 3:
                    self.console.print(f" [dim]... and {len(entries) - 3} more[/dim]")
                self.console.print()
