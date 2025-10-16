import copy
import io
import typing as t
from pathlib import Path

import tomli
import tomli_w
import yaml
from acb.console import Console
from acb.depends import Inject, depends
from acb.logger import Logger

from crackerjack.models.protocols import (
    ConfigMergeServiceProtocol,
    FileSystemInterface,
    GitInterface,
)


class ConfigMergeService(ConfigMergeServiceProtocol):
    @depends.inject
    def __init__(
        self,
        console: Inject[Console],
        filesystem: Inject[FileSystemInterface],
        git_service: Inject[GitInterface],
        logger: Inject[Logger],
    ) -> None:
        self.console = console
        self.filesystem = filesystem
        self.git_service = git_service
        self.logger = logger

    def smart_merge_pyproject(
        self,
        source_content: dict[str, t.Any],
        target_path: str | t.Any,
        project_name: str,
    ) -> dict[str, t.Any]:
        target_path = Path(target_path)

        if not target_path.exists():
            return t.cast(
                dict[str, t.Any],
                self._replace_project_name_in_config_value(
                    source_content, project_name
                ),
            )

        with target_path.open("rb") as f:
            target_content = tomli.load(f)

        self._ensure_crackerjack_dev_dependency(target_content, source_content)

        self._merge_tool_configurations(target_content, source_content, project_name)

        self._remove_fixed_coverage_requirements(target_content)

        self.logger.info("Smart merged pyproject.toml", project_name=project_name)
        return target_content

    def smart_merge_pre_commit_config(
        self,
        source_content: dict[str, t.Any],
        target_path: str | t.Any,
        project_name: str,
    ) -> dict[str, t.Any]:
        target_path = Path(target_path)

        if not target_path.exists():
            # Process source content for project-specific references
            processed_source = copy.deepcopy(source_content)
            source_repos = processed_source.get("repos", [])
            processed_source["repos"] = self._process_pre_commit_repos_for_project(
                source_repos, project_name
            )
            return processed_source

        with target_path.open() as f:
            loaded_config = yaml.safe_load(f)
            target_content: dict[str, t.Any] = (
                loaded_config if isinstance(loaded_config, dict) else {}
            )

        if not isinstance(target_content, dict):
            self.logger.warning(
                f"Target config is not a dictionary, using source: {type(target_content)}"
            )
            return source_content

        source_repos = source_content.get("repos", [])
        target_repos = target_content.get("repos", [])

        if not isinstance(target_repos, list):
            target_repos = []

        existing_repo_urls = {
            repo.get("repo", "") for repo in target_repos if isinstance(repo, dict)
        }

        new_repos = [
            repo
            for repo in source_repos
            if isinstance(repo, dict) and repo.get("repo", "") not in existing_repo_urls
        ]

        if new_repos:
            # Replace project-specific references in new repos before adding them
            processed_new_repos = self._process_pre_commit_repos_for_project(
                new_repos, project_name
            )
            target_repos.extend(processed_new_repos)
            target_content["repos"] = target_repos
            self.logger.info(
                "Merged .pre-commit-config.yaml",
                new_repos_count=len(new_repos),
                project_name=project_name,
            )

        return target_content

    def smart_append_file(
        self,
        source_content: str,
        target_path: str | t.Any,
        start_marker: str,
        end_marker: str,
        force: bool = False,
    ) -> str:
        target_path = Path(target_path)

        if not target_path.exists():
            return f"{start_marker}\n{source_content.strip()}\n{end_marker}\n"

        existing_content = target_path.read_text()

        if start_marker in existing_content:
            if force:
                start_idx = existing_content.find(start_marker)
                end_idx = existing_content.find(end_marker)
                if end_idx != -1:
                    end_idx += len(end_marker)
                    existing_content = (
                        existing_content[:start_idx] + existing_content[end_idx:]
                    ).strip()
            else:
                return existing_content

        merged_content = existing_content.strip() + "\n\n" + start_marker + "\n"
        merged_content += source_content.strip() + "\n"
        merged_content += end_marker + "\n"

        self.logger.info("Smart appended file with markers", path=str(target_path))
        return merged_content

    def smart_merge_gitignore(
        self,
        patterns: list[str],
        target_path: str | t.Any,
    ) -> str:
        target_path = Path(target_path)

        if not target_path.exists():
            return self._create_new_gitignore(target_path, patterns)

        lines = target_path.read_text().splitlines()

        parsed_content = self._parse_existing_gitignore_content(lines)

        merged_content = self._build_merged_gitignore_content(parsed_content, patterns)

        target_path.write_text(merged_content)
        new_patterns_count = len(
            [p for p in patterns if p not in parsed_content.existing_patterns]
        )
        all_patterns_count = len(parsed_content.existing_patterns) + new_patterns_count

        self.logger.info(
            "Smart merged .gitignore (cleaned duplicates)",
            new_patterns_count=new_patterns_count,
            total_crackerjack_patterns=all_patterns_count,
        )
        return merged_content

    def _create_new_gitignore(self, target_path: Path, patterns: list[str]) -> str:
        merged_content = "# Crackerjack patterns\n"
        for pattern in patterns:
            merged_content += f"{pattern}\n"
        target_path.write_text(merged_content)
        self.logger.info("Created .gitignore", new_patterns_count=len(patterns))
        return merged_content

    def _parse_existing_gitignore_content(self, lines: list[str]) -> t.Any:
        class ParsedContent:
            def __init__(self) -> None:
                self.cleaned_lines: list[str] = []
                self.existing_patterns: set[str] = set()

        parsed = ParsedContent()
        parser_state = self._init_parser_state()

        for line in lines:
            parser_state = self._process_gitignore_line(line, parsed, parser_state)

        return parsed

    def _init_parser_state(self) -> dict[str, bool]:
        return {
            "inside_crackerjack_section": False,
            "skip_empty_after_crackerjack": False,
        }

    def _process_gitignore_line(
        self, line: str, parsed: t.Any, state: dict[str, bool]
    ) -> dict[str, bool]:
        stripped = line.strip()

        if self._is_crackerjack_header(stripped):
            return self._handle_crackerjack_header(state)

        if self._should_skip_empty_line(stripped, state):
            state["skip_empty_after_crackerjack"] = False
            return state

        state["skip_empty_after_crackerjack"] = False

        self._collect_pattern_if_present(stripped, parsed, state)
        self._add_line_if_non_crackerjack(line, parsed, state)

        return state

    def _handle_crackerjack_header(self, state: dict[str, bool]) -> dict[str, bool]:
        if not state["inside_crackerjack_section"]:
            state["inside_crackerjack_section"] = True
            state["skip_empty_after_crackerjack"] = True
        return state

    def _should_skip_empty_line(self, stripped: str, state: dict[str, bool]) -> bool:
        return state["skip_empty_after_crackerjack"] and not stripped

    def _collect_pattern_if_present(
        self, stripped: str, parsed: t.Any, state: dict[str, bool]
    ) -> None:
        if stripped and not stripped.startswith("#"):
            parsed.existing_patterns.add(stripped)

    def _add_line_if_non_crackerjack(
        self, line: str, parsed: t.Any, state: dict[str, bool]
    ) -> None:
        if not state["inside_crackerjack_section"]:
            parsed.cleaned_lines.append(line)

    def _is_crackerjack_header(self, line: str) -> bool:
        return line in ("# Crackerjack patterns", "# Crackerjack generated files")

    def _build_merged_gitignore_content(
        self, parsed_content: t.Any, new_patterns: list[str]
    ) -> str:
        if parsed_content.cleaned_lines and not parsed_content.cleaned_lines[-1]:
            parsed_content.cleaned_lines.pop()

        merged_content = "\n".join(parsed_content.cleaned_lines)
        if merged_content:
            merged_content += "\n"

        all_crackerjack_patterns = self._get_consolidated_patterns(
            parsed_content.existing_patterns, new_patterns
        )

        if all_crackerjack_patterns:
            merged_content += "\n# Crackerjack patterns\n"
            for pattern in sorted(all_crackerjack_patterns):
                merged_content += f"{pattern}\n"

        return merged_content

    def _get_consolidated_patterns(
        self, existing_patterns: set[str], new_patterns: list[str]
    ) -> list[str]:
        new_patterns_to_add = [p for p in new_patterns if p not in existing_patterns]
        return list[t.Any](existing_patterns) + new_patterns_to_add

    def write_pyproject_config(
        self,
        config: dict[str, t.Any],
        target_path: str | t.Any,
    ) -> None:
        target_path = Path(target_path)

        buffer = io.BytesIO()
        tomli_w.dump(config, buffer)
        content = buffer.getvalue().decode("utf-8")

        from crackerjack.services.filesystem import FileSystemService

        content = FileSystemService.clean_trailing_whitespace_and_newlines(content)

        with target_path.open("w", encoding="utf-8") as f:
            f.write(content)

        self.logger.debug("Wrote pyproject.toml config", path=str(target_path))

    def write_pre_commit_config(
        self,
        config: dict[str, t.Any],
        target_path: str | t.Any,
    ) -> None:
        target_path = Path(target_path)

        yaml_content = yaml.dump(
            config,
            default_flow_style=False,
            sort_keys=False,
            width=float("inf"),
        )
        content = yaml_content

        from crackerjack.services.filesystem import FileSystemService

        content = FileSystemService.clean_trailing_whitespace_and_newlines(content)

        with target_path.open("w") as f:
            f.write(content)

        self.logger.debug("Wrote .pre-commit-config.yaml", path=str(target_path))

    def _ensure_crackerjack_dev_dependency(
        self,
        target_config: dict[str, t.Any],
        source_config: dict[str, t.Any],
    ) -> None:
        if "dependency-groups" not in target_config:
            target_config["dependency-groups"] = {}

        if "dev" not in target_config["dependency-groups"]:
            target_config["dependency-groups"]["dev"] = []

        dev_deps = target_config["dependency-groups"]["dev"]
        if "crackerjack" not in str(dev_deps):
            dev_deps.append("crackerjack")
            self.logger.debug("Added crackerjack to dev dependencies")

    def _merge_tool_configurations(
        self,
        target_config: dict[str, t.Any],
        source_config: dict[str, t.Any],
        project_name: str,
    ) -> None:
        source_tools = source_config.get("tool", {})

        if "tool" not in target_config:
            target_config["tool"] = {}

        target_tools = target_config["tool"]

        tools_to_merge = [
            "ruff",
            "pyright",
            "bandit",
            "vulture",
            "refurb",
            "complexipy",
            "codespell",
            "creosote",
        ]

        for tool_name in tools_to_merge:
            if tool_name in source_tools:
                if tool_name not in target_tools:
                    target_tools[tool_name] = self._replace_project_name_in_tool_config(
                        source_tools[tool_name], project_name
                    )
                    self.console.print(
                        f"[green]➕[/green] Added [tool.{tool_name}] configuration"
                    )
                else:
                    self._merge_tool_settings(
                        target_tools[tool_name],
                        source_tools[tool_name],
                        tool_name,
                        project_name,
                    )

        self._merge_pytest_markers(target_tools, source_tools)

    def _merge_tool_settings(
        self,
        target_tool: dict[str, t.Any],
        source_tool: dict[str, t.Any],
        tool_name: str,
        project_name: str,
    ) -> None:
        updated_keys = []

        for key, value in source_tool.items():
            if key not in target_tool:
                target_tool[key] = self._replace_project_name_in_config_value(
                    value, project_name
                )
                updated_keys.append(key)

        if updated_keys:
            self.console.print(
                f"[yellow]🔄[/yellow] Updated [tool.{tool_name}] with: {', '.join(updated_keys)}"
            )

    def _merge_pytest_markers(
        self,
        target_tools: dict[str, t.Any],
        source_tools: dict[str, t.Any],
    ) -> None:
        if "pytest" not in source_tools or "pytest" not in target_tools:
            return

        source_pytest = source_tools["pytest"]
        target_pytest = target_tools["pytest"]

        if "ini_options" not in source_pytest or "ini_options" not in target_pytest:
            return

        source_markers = source_pytest["ini_options"].get("markers", [])
        target_markers = target_pytest["ini_options"].get("markers", [])

        existing_marker_names = {marker.split(": ")[0] for marker in target_markers}
        new_markers = [
            marker
            for marker in source_markers
            if marker.split(": ")[0] not in existing_marker_names
        ]

        if new_markers:
            target_markers.extend(new_markers)
            self.console.print(
                f"[green]➕[/green] Added pytest markers: {len(new_markers)}"
            )

    def _remove_fixed_coverage_requirements(
        self,
        target_config: dict[str, t.Any],
    ) -> None:
        target_coverage = (
            target_config.get("tool", {}).get("pytest", {}).get("ini_options", {})
        )

        addopts = target_coverage.get("addopts", "")
        if isinstance(addopts, str):
            original_addopts = addopts

            from crackerjack.services.regex_patterns import remove_coverage_fail_under

            addopts = remove_coverage_fail_under(addopts).strip()
            addopts = " ".join(addopts.split())

            if original_addopts != addopts:
                target_coverage["addopts"] = addopts
                self.console.print(
                    "[green]🔄[/green] Removed fixed coverage requirement (using ratchet system)"
                )

        coverage_report = (
            target_config.get("tool", {}).get("coverage", {}).get("report", {})
        )
        if "fail_under" in coverage_report:
            original_fail_under = coverage_report["fail_under"]
            coverage_report["fail_under"] = 0
            self.console.print(
                f"[green]🔄[/green] Reset coverage.report.fail_under from {original_fail_under} to 0 (ratchet system)"
            )

    def _replace_project_name_in_tool_config(
        self, tool_config: dict[str, t.Any], project_name: str
    ) -> dict[str, t.Any]:
        if project_name == "crackerjack":
            return tool_config

        result = copy.deepcopy(tool_config)
        return t.cast(
            dict[str, t.Any],
            self._replace_project_name_in_config_value(result, project_name),
        )

    def _replace_project_name_in_config_value(
        self, value: t.Any, project_name: str
    ) -> t.Any:
        if project_name == "crackerjack":
            return value

        if isinstance(value, str):
            return value.replace("crackerjack", project_name)
        elif isinstance(value, list):
            return [
                self._replace_project_name_in_config_value(item, project_name)
                for item in value
            ]
        elif isinstance(value, dict):
            return {
                key: self._replace_project_name_in_config_value(val, project_name)
                for key, val in value.items()
            }
        return value

    def _process_pre_commit_repos_for_project(
        self, repos: list[dict[str, t.Any]], project_name: str
    ) -> list[dict[str, t.Any]]:
        """Process pre-commit repos to replace project-specific references."""
        if project_name == "crackerjack":
            return repos  # No changes needed for crackerjack itself

        processed_repos = []
        for repo in repos:
            processed_repo = copy.deepcopy(repo)
            self._process_repo_hooks(processed_repo, project_name)
            processed_repos.append(processed_repo)

        return processed_repos

    def _process_repo_hooks(self, repo: dict[str, t.Any], project_name: str) -> None:
        """Process hooks within a repo to replace project-specific references."""
        hooks = repo.get("hooks", [])
        for hook in hooks:
            if isinstance(hook, dict):
                self._process_hook_args(hook, project_name)
                self._process_hook_files(hook, project_name)
                # Special handling for validate-regex-patterns hook - keep it pointing to crackerjack package
                # This should reference the installed crackerjack package, not the current project
                # The entry already uses "uv run python -m crackerjack.tools.validate_regex_patterns"
                # which is correct - it runs from the installed crackerjack package

    def _process_hook_args(self, hook: dict[str, t.Any], project_name: str) -> None:
        """Process hook args to replace project-specific references."""
        if "args" in hook:
            hook["args"] = [
                arg.replace("crackerjack", project_name)
                if isinstance(arg, str)
                else arg
                for arg in hook["args"]
            ]

    def _process_hook_files(self, hook: dict[str, t.Any], project_name: str) -> None:
        """Process hook files pattern to replace project-specific references."""
        if "files" in hook:
            files_pattern = hook["files"]
            if isinstance(files_pattern, str):
                hook["files"] = files_pattern.replace(
                    "^crackerjack/", f"^{project_name}/"
                )
