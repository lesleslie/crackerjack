from __future__ import annotations

import logging
import typing as t
from contextlib import suppress
from dataclasses import dataclass, field
from pathlib import Path
from unittest.mock import Mock

from crackerjack.config.settings import CrackerjackSettings, DocUpdateSettings
from crackerjack.models.protocols import GitInterface

if t.TYPE_CHECKING:
    from crackerjack.models.protocols import (
        ConsoleInterface as Console,
    )

logger = logging.getLogger(__name__)


@dataclass
class CodeChange:
    file_path: str
    change_type: str
    old_content: str | None = None
    new_content: str | None = None
    line_number: int | None = None
    docstring: str | None = None
    is_api_change: bool = False


@dataclass
class DocUpdate:
    doc_file: str
    original_content: str
    updated_content: str
    change_summary: str
    confidence: float = 0.0


@dataclass
class DocUpdateResult:
    success: bool
    files_updated: int = 0
    total_files: int = 0
    updated_files: list[str] = field(default_factory=list)
    skipped_files: list[str] = field(default_factory=list)
    change_summary: str = ""
    summary: str = ""
    error_message: str = ""
    dry_run: bool = False


class DocUpdateService:
    def __init__(
        self,
        console: Console,
        pkg_path: Path,
        git_service: GitInterface,
        settings: CrackerjackSettings | None = None,
    ) -> None:
        self.console = console
        self.pkg_path = pkg_path
        self.git_service = git_service
        self._settings = settings

    @property
    def settings(self) -> DocUpdateSettings:
        if self._settings is None:
            from crackerjack.config import load_settings
            from crackerjack.config.settings import CrackerjackSettings

            self._settings = load_settings(CrackerjackSettings)
        return self._settings.doc_updates

    def _run_git_command(self, args: list[str]) -> Mock:
        import subprocess

        cmd = ["git", *args]
        try:
            result = subprocess.run(
                cmd,
                cwd=self.pkg_path,
                capture_output=True,
                text=True,
                check=False,
            )
            mock_result = Mock()
            mock_result.success = result.returncode == 0
            mock_result.stdout = result.stdout
            mock_result.stderr = result.stderr
            mock_result.returncode = result.returncode
            return mock_result
        except Exception as e:
            logger.error(f"Failed to run git command: {e}")
            mock_result = Mock()
            mock_result.success = False
            mock_result.stderr = str(e)
            return mock_result

    def update_documentation(
        self,
        dry_run: bool = False,
    ) -> DocUpdateResult:
        if not self.settings.enabled:
            return DocUpdateResult(
                success=True,
                summary="Documentation updates disabled via settings",
            )

        if self.settings.ai_powered and not self.settings.api_key:
            return DocUpdateResult(
                success=False,
                error_message="AI-powered updates enabled but ANTHROPIC_API_KEY not set",
            )

        self.console.print("[cyan]Analyzing code changes...[/cyan]")

        changes = self._analyze_code_changes()
        if not changes:
            return DocUpdateResult(
                success=True,
                summary="No code changes detected since last publish",
            )

        self.console.print(f"[green]Found {len(changes)} code changes[/green]")

        updates = (
            self._generate_doc_updates(changes) if self.settings.ai_powered else []
        )
        if not updates:
            return DocUpdateResult(
                success=True,
                summary="No documentation updates generated",
                total_files=len(changes),
            )

        self.console.print(
            f"[green]Generated {len(updates)} documentation updates[/green]"
        )

        if dry_run:
            summary = self._generate_dry_run_summary(updates)
            return DocUpdateResult(
                success=True,
                files_updated=len(updates),
                total_files=len(updates),
                updated_files=[u.doc_file for u in updates],
                summary=summary,
                dry_run=True,
            )

        applied_count = self._apply_doc_updates(updates)

        if applied_count > 0:
            self._create_update_commits(updates[:applied_count])

        summary = self._generate_update_summary(updates, applied_count)

        return DocUpdateResult(
            success=True,
            files_updated=applied_count,
            total_files=len(updates),
            updated_files=[u.doc_file for u in updates[:applied_count]],
            summary=summary,
        )

    def _analyze_code_changes(self) -> list[CodeChange]:
        changes: list[CodeChange] = []

        try:
            diff_output = self._get_git_diff()

            if not diff_output:
                return changes

            changes = self._parse_git_diff(diff_output)

        except Exception as e:
            logger.error(f"Failed to analyze code changes: {e}")
            self.console.print(
                f"[yellow]Warning: Could not analyze changes: {e}[/yellow]"
            )

        return changes

    def _get_git_diff(self) -> str:
        try:
            result = self._run_git_command(["diff", "HEAD~1", "HEAD"])

            if result.success:
                return result.stdout

            result = self._run_git_command(["diff", "HEAD"])

            return result.stdout if result.success else ""

        except Exception as e:
            logger.error(f"Failed to get git diff: {e}")
            return ""

    def _parse_git_diff(self, diff_output: str) -> list[CodeChange]:
        changes = []
        current_file = None
        change_type = None

        for line in diff_output.splitlines():
            if line.startswith("diff --git"):
                parts = line.split()
                if len(parts) >= 4:
                    current_file = parts[3].strip("b/")
                    change_type = "modified"

            elif line.startswith("new file"):
                current_file = line.split()[-1].strip("b/")
                change_type = "added"

            elif line.startswith("deleted file"):
                current_file = line.split()[-1].strip("b/")
                change_type = "deleted"

            elif line.startswith("@@") and current_file:
                if current_file and change_type:
                    changes.append(
                        CodeChange(
                            file_path=current_file,
                            change_type=change_type,
                            line_number=self._extract_line_number(line),
                        )
                    )

        return changes

    def _extract_line_number(self, hunk_header: str) -> int | None:
        with suppress(Exception):
            import re

            match = re.search(r"\+\s*(\d+)", hunk_header)
            if match:
                return int(match.group(1))

        return None

    def _generate_doc_updates(
        self,
        changes: list[CodeChange],
    ) -> list[DocUpdate]:
        if not self.settings.api_key:
            logger.warning("ANTHROPIC_API_KEY not set, skipping AI updates")
            return []

        updates = []

        try:
            import anthropic

            client = anthropic.Anthropic(api_key=self.settings.api_key)

            doc_files = self._identify_doc_files()

            for doc_file in doc_files:
                try:
                    doc_path = self.pkg_path / doc_file
                    if not doc_path.exists():
                        continue

                    original_content = doc_path.read_text()

                    prompt = self._build_update_prompt(
                        doc_file, original_content, changes
                    )

                    response = client.messages.create(
                        model=self.settings.model,
                        max_tokens=self.settings.max_tokens,
                        messages=[
                            {
                                "role": "user",
                                "content": prompt,
                            }
                        ],
                    )

                    content_block = response.content[0]
                    if hasattr(content_block, "text"):
                        updated_content = content_block.text
                    else:
                        logger.error(
                            f"Unexpected content block type: {type(content_block)}"
                        )
                        continue

                    confidence = self._calculate_confidence(
                        original_content, updated_content
                    )

                    updates.append(
                        DocUpdate(
                            doc_file=doc_file,
                            original_content=original_content,
                            updated_content=updated_content,
                            change_summary=f"AI-generated updates for {doc_file}",
                            confidence=confidence,
                        )
                    )

                except Exception as e:
                    logger.error(f"Failed to generate update for {doc_file}: {e}")
                    continue

        except ImportError:
            logger.error("anthropic package not installed")
            self.console.print(
                "[yellow]Warning: anthropic package not installed, "
                "install with: uv add anthropic[/yellow]"
            )
        except Exception as e:
            logger.error(f"Failed to generate doc updates: {e}")

        return updates

    def _identify_doc_files(self) -> list[str]:
        doc_files = []

        for pattern in self.settings.doc_patterns:
            if "*" in pattern:
                from glob import glob

                matches = glob(str(self.pkg_path / pattern), recursive=True)
                doc_files.extend(
                    [
                        str(Path(m).relative_to(self.pkg_path))
                        for m in matches
                        if Path(m).is_file()
                    ]
                )
            else:
                doc_path = self.pkg_path / pattern
                if doc_path.is_file():
                    doc_files.append(pattern)

        return sorted(set(doc_files))

    def _build_update_prompt(
        self,
        doc_file: str,
        current_content: str,
        changes: list[CodeChange],
    ) -> str:
        relevant_changes = [c for c in changes if self._is_change_relevant(c, doc_file)]

        prompt = f"""Update the following documentation file based on the code changes provided.

Documentation file: {doc_file}

Current content:
```
{current_content}
```

Code changes:
"""
        for change in relevant_changes[:10]:
            prompt += f"\n- {change.file_path} ({change.change_type})"
            if change.docstring:
                prompt += f"\n  Docstring: {change.docstring[:100]}..."

        prompt += """

Please update the documentation to reflect these code changes. Maintain the existing style and format. Only update sections that are actually affected by the changes. Preserve any manual annotations or examples.

Return the complete updated documentation file content:"""

        return prompt

    def _is_change_relevant(self, change: CodeChange, doc_file: str) -> bool:
        return True

    def _calculate_confidence(
        self,
        original: str,
        updated: str,
    ) -> float:
        if len(updated) < len(original) * 0.5:
            return 0.5

        if len(updated) > len(original) * 3:
            return 0.7

        return 0.85

    def _apply_doc_updates(self, updates: list[DocUpdate]) -> int:
        applied_count = 0

        for update in updates:
            try:
                if update.confidence < 0.5:
                    self.console.print(
                        f"[yellow]Skipping {update.doc_file} "
                        f"(confidence: {update.confidence:.2f})[/yellow]"
                    )
                    continue

                doc_path = self.pkg_path / update.doc_file
                doc_path.write_text(update.updated_content)

                self.console.print(f"[green]✓[/green] Updated: {update.doc_file}")

                applied_count += 1

            except Exception as e:
                logger.error(f"Failed to apply update to {update.doc_file}: {e}")
                self.console.print(
                    f"[red]✗[/red] Failed to update {update.doc_file}: {e}"
                )

        return applied_count

    def _create_update_commits(self, updates: list[DocUpdate]) -> None:
        for update in updates:
            try:
                self.git_service.add_files([update.doc_file])

                commit_msg = (
                    f"docs: update {update.doc_file}\n\n{update.change_summary}"
                )

                self.git_service.commit(commit_msg)

                logger.info(f"Created commit for {update.doc_file}")

            except Exception as e:
                logger.error(f"Failed to create commit for {update.doc_file}: {e}")

    def _generate_dry_run_summary(self, updates: list[DocUpdate]) -> str:
        lines = [
            "Documentation Updates (Dry Run)",
            "=" * 40,
            f"Files to update: {len(updates)}",
        ]

        for update in updates[:10]:
            lines.append(f"  - {update.doc_file} (confidence: {update.confidence:.2f})")

        if len(updates) > 10:
            lines.append(f"  ... and {len(updates) - 10} more")

        return "\n".join(lines)

    def _generate_update_summary(
        self,
        updates: list[DocUpdate],
        applied_count: int,
    ) -> str:
        lines = [
            "Documentation Updates Complete",
            "=" * 40,
            f"Files updated: {applied_count}/{len(updates)}",
        ]

        if applied_count < len(updates):
            lines.append(f"Files skipped: {len(updates) - applied_count}")

        return "\n".join(lines)
