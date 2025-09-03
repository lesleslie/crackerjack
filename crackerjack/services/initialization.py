import json
import subprocess
import typing as t
from pathlib import Path

import tomli
import tomli_w
import yaml
from rich.console import Console

from .filesystem import FileSystemService
from .git import GitService
from .input_validator import get_input_validator, validate_and_sanitize_path


class InitializationService:
    def __init__(
        self,
        console: Console,
        filesystem: FileSystemService,
        git_service: GitService,
        pkg_path: Path,
    ) -> None:
        self.console = console
        self.filesystem = filesystem
        self.git_service = git_service
        self.pkg_path = pkg_path

    def initialize_project(
        self,
        target_path: Path | None = None,
        force: bool = False,
    ) -> dict[str, t.Any]:
        if target_path is None:
            target_path = Path.cwd()

        # Validate target path for security
        try:
            target_path = validate_and_sanitize_path(target_path, allow_absolute=True)
        except Exception as e:
            return {
                "target_path": str(target_path),
                "files_copied": [],
                "files_skipped": [],
                "errors": [f"Invalid target path: {e}"],
                "success": False,
            }

        results = self._create_results_dict(target_path)

        try:
            config_files = self._get_config_files()
            project_name = target_path.name

            # Validate project name
            validator = get_input_validator()
            name_result = validator.validate_project_name(project_name)
            if not name_result.valid:
                results["errors"].append(
                    f"Invalid project name: {name_result.error_message}"
                )
                results["success"] = False
                return results

            # Use sanitized project name
            sanitized_project_name = name_result.sanitized_value

            for file_name, merge_strategy in config_files.items():
                self._process_config_file(
                    file_name,
                    merge_strategy,
                    sanitized_project_name,
                    target_path,
                    force,
                    results,
                )

            self._print_summary(results)

        except Exception as e:
            self._handle_initialization_error(results, e)

        return results

    def _create_results_dict(self, target_path: Path) -> dict[str, t.Any]:
        return {
            "target_path": str(target_path),
            "files_copied": [],
            "files_skipped": [],
            "errors": [],
            "success": True,
        }

    def _get_config_files(self) -> dict[str, str]:
        return {
            ".pre-commit-config.yaml": "smart_merge",
            "pyproject.toml": "smart_merge",
            "CLAUDE.md": "smart_append",
            "RULES.md": "replace_if_missing",
            "example.mcp.json": "special",
        }

    def _process_config_file(
        self,
        file_name: str,
        merge_strategy: str,
        project_name: str,
        target_path: Path,
        force: bool,
        results: dict[str, t.Any],
    ) -> None:
        if file_name == "example.mcp.json":
            self._process_mcp_config(target_path, force, results)
            return

        source_file = self.pkg_path.parent / file_name
        target_file = target_path / file_name

        if not source_file.exists():
            self._handle_missing_source_file(file_name, results)
            return

        try:
            if merge_strategy == "smart_merge":
                self._smart_merge_config(
                    source_file,
                    target_file,
                    file_name,
                    project_name,
                    force,
                    results,
                )
            elif merge_strategy == "smart_append":
                self._smart_append_config(
                    source_file,
                    target_file,
                    file_name,
                    project_name,
                    force,
                    results,
                )
            elif merge_strategy == "replace_if_missing":
                if not target_file.exists() or force:
                    content = self._read_and_process_content(
                        source_file,
                        True,
                        project_name,
                    )
                    self._write_file_and_track(target_file, content, file_name, results)
                else:
                    self._skip_existing_file(file_name, results)
            else:
                if not self._should_copy_file(target_file, force, file_name, results):
                    return
                content = self._read_and_process_content(
                    source_file,
                    True,
                    project_name,
                )
                self._write_file_and_track(target_file, content, file_name, results)

        except Exception as e:
            self._handle_file_processing_error(file_name, e, results)

    def _should_copy_file(
        self,
        target_file: Path,
        force: bool,
        file_name: str,
        results: dict[str, t.Any],
    ) -> bool:
        if target_file.exists() and not force:
            t.cast("list[str]", results["files_skipped"]).append(file_name)
            self.console.print(
                f"[yellow]⚠️[/ yellow] Skipped {file_name} (already exists)",
            )
            return False
        return True

    def _read_and_process_content(
        self,
        source_file: Path,
        should_replace: bool,
        project_name: str,
    ) -> str:
        content = source_file.read_text()

        if should_replace and project_name != "crackerjack":
            content = content.replace("crackerjack", project_name)

        return content

    def _write_file_and_track(
        self,
        target_file: Path,
        content: str,
        file_name: str,
        results: dict[str, t.Any],
    ) -> None:
        target_file.write_text(content)
        t.cast("list[str]", results["files_copied"]).append(file_name)

        try:
            self.git_service.add_files([str(target_file)])
        except Exception as e:
            self.console.print(
                f"[yellow]⚠️[/ yellow] Could not git add {file_name}: {e}"
            )

        self.console.print(f"[green]✅[/ green] Copied {file_name}")

    def _skip_existing_file(self, file_name: str, results: dict[str, t.Any]) -> None:
        t.cast("list[str]", results["files_skipped"]).append(file_name)
        self.console.print(f"[yellow]⚠️[/ yellow] Skipped {file_name} (already exists)")

    def _handle_missing_source_file(
        self,
        file_name: str,
        results: dict[str, t.Any],
    ) -> None:
        error_msg = f"Source file not found: {file_name}"
        t.cast("list[str]", results["errors"]).append(error_msg)
        self.console.print(f"[yellow]⚠️[/ yellow] {error_msg}")

    def _handle_file_processing_error(
        self,
        file_name: str,
        error: Exception,
        results: dict[str, t.Any],
    ) -> None:
        error_msg = f"Failed to copy {file_name}: {error}"
        t.cast("list[str]", results["errors"]).append(error_msg)
        results["success"] = False
        self.console.print(f"[red]❌[/ red] {error_msg}")

    def _print_summary(self, results: dict[str, t.Any]) -> None:
        if results["success"]:
            self.console.print(
                f"[green]🎉 Project initialized successfully ! [/ green] "
                f"Copied {len(t.cast('list[str]', results['files_copied']))} files",
            )
        else:
            self.console.print(
                "[red]❌ Project initialization completed with errors[/ red]",
            )

    def _handle_initialization_error(
        self,
        results: dict[str, t.Any],
        error: Exception,
    ) -> None:
        results["success"] = False
        t.cast("list[str]", results["errors"]).append(f"Initialization failed: {error}")
        self.console.print(f"[red]❌[/ red] Initialization failed: {error}")

    def check_uv_installed(self) -> bool:
        try:
            result = subprocess.run(
                ["uv", "--version"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def _process_mcp_config(
        self,
        target_path: Path,
        force: bool,
        results: dict[str, t.Any],
    ) -> None:
        source_file = self.pkg_path / "example.mcp.json"

        target_file = target_path / ".mcp.json"

        if not source_file.exists():
            self._handle_missing_source_file("example.mcp.json", results)
            return

        try:
            with source_file.open() as f:
                source_config = json.load(f)

            if not isinstance(source_config.get("mcpServers"), dict):
                self._handle_file_processing_error(
                    "example.mcp.json",
                    ValueError("Invalid example.mcp.json format: missing mcpServers"),
                    results,
                )
                return

            crackerjack_servers = source_config["mcpServers"]

            if not target_file.exists():
                target_config = {"mcpServers": crackerjack_servers}
                self._write_mcp_config_and_track(target_file, target_config, results)
                self.console.print(
                    "[green]✅[/ green] Created .mcp.json with crackerjack MCP servers",
                )
                return

            if target_file.exists() and not force:
                self._merge_mcp_config(target_file, crackerjack_servers, results)
                return

            target_config = {"mcpServers": crackerjack_servers}
            self._write_mcp_config_and_track(target_file, target_config, results)
            self.console.print(
                "[green]✅[/ green] Updated .mcp.json with crackerjack MCP servers",
            )

        except Exception as e:
            self._handle_file_processing_error(".mcp.json", e, results)

    def _merge_mcp_config(
        self,
        target_file: Path,
        crackerjack_servers: dict[str, t.Any],
        results: dict[str, t.Any],
    ) -> None:
        try:
            with target_file.open() as f:
                existing_config = json.load(f)

            if not isinstance(existing_config.get("mcpServers"), dict):
                existing_config["mcpServers"] = {}

            existing_servers = existing_config["mcpServers"]
            updated_servers = {}

            for name, config in crackerjack_servers.items():
                if name in existing_servers:
                    self.console.print(
                        f"[yellow]🔄[/ yellow] Updating existing MCP server: {name}",
                    )
                else:
                    self.console.print(
                        f"[green]➕[/ green] Adding new MCP server: {name}",
                    )
                updated_servers[name] = config

            existing_servers.update(updated_servers)

            self._write_mcp_config_and_track(target_file, existing_config, results)

            t.cast("list[str]", results["files_copied"]).append(".mcp.json (merged)")

        except Exception as e:
            self._handle_file_processing_error(".mcp.json (merge)", e, results)

    def _write_mcp_config_and_track(
        self,
        target_file: Path,
        config: dict[str, t.Any],
        results: dict[str, t.Any],
    ) -> None:
        with target_file.open("w") as f:
            json.dump(config, f, indent=2)

        t.cast("list[str]", results["files_copied"]).append(".mcp.json")

        try:
            self.git_service.add_files([str(target_file)])
        except Exception as e:
            self.console.print(f"[yellow]⚠️[/ yellow] Could not git add .mcp.json: {e}")

    def validate_project_structure(self) -> bool:
        required_indicators = [
            self.pkg_path / "pyproject.toml",
            self.pkg_path / "setup.py",
        ]

        return any(path.exists() for path in required_indicators)

    def _generate_project_claude_content(self, project_name: str) -> str:
        return """


This project uses crackerjack for Python project management and quality assurance.


For optimal development experience with this crackerjack - enabled project, use these specialized agents:


- * *🏗️ crackerjack - architect * *: Expert in crackerjack's modular architecture and Python project management patterns. **Use PROACTIVELY **for all feature development, architectural decisions, and ensuring code follows crackerjack standards from the start.

- * *🐍 python - pro * *: Modern Python development with type hints, async / await patterns, and clean architecture

- * *🧪 pytest - hypothesis - specialist * *: Advanced testing patterns, property - based testing, and test optimization


- * *🧪 crackerjack - test - specialist * *: Advanced testing specialist for complex testing scenarios and coverage optimization
- * *🏗️ backend - architect * *: System design, API architecture, and service integration patterns
- * *🔒 security-auditor * *: Security analysis, vulnerability detection, and secure coding practices


```bash

Task tool with subagent_type ="crackerjack - architect" for feature planning


Task tool with subagent_type ="python-pro" for code implementation


Task tool with subagent_type ="pytest - hypothesis-specialist" for test development


Task tool with subagent_type ="security-auditor" for security analysis
```

* *💡 Pro Tip * *: The crackerjack - architect agent automatically ensures code follows crackerjack patterns from the start, eliminating the need for retrofitting and quality fixes.


This project follows crackerjack's clean code philosophy:


- **EVERY LINE OF CODE IS A LIABILITY * *: The best code is no code
- **DRY (Don't Repeat Yourself)* *: If you write it twice, you're doing it wrong
- **YAGNI (You Ain't Gonna Need It)* *: Build only what's needed NOW
- **KISS (Keep It Simple, Stupid)* *: Complexity is the enemy of maintainability


- **Cognitive complexity ≤15 **per function (automatically enforced)
- **Coverage ratchet system * *: Never decrease coverage, always improve toward 100 %
- **Type annotations required * *: All functions must have return type hints
- **Security patterns * *: No hardcoded paths, proper temp file handling
- **Python 3.13 + modern patterns * *: Use `|` unions, pathlib over os.path


```bash

python - m crackerjack


python - m crackerjack - t


python - m crackerjack - - ai - agent - t


python - m crackerjack - a patch
```


1. **Plan with crackerjack - architect * *: Ensure proper architecture from the start
2. **Implement with python - pro * *: Follow modern Python patterns
3. **Test comprehensively * *: Use pytest - hypothesis - specialist for robust testing
4. **Run quality checks * *: `python - m crackerjack - t` before committing
5. **Security review * *: Use security - auditor for final validation


- **Use crackerjack - architect agent proactively **for all significant code changes
- **Never reduce test coverage **- the ratchet system only allows improvements
- **Follow crackerjack patterns **- the tools will enforce quality automatically
- **Leverage AI agent auto - fixing **- `python - m crackerjack - - ai - agent - t` for autonomous quality fixes

- --
* This project is enhanced by crackerjack's intelligent Python project management.*"""

    def _smart_append_config(
        self,
        source_file: Path,
        target_file: Path,
        file_name: str,
        project_name: str,
        force: bool,
        results: dict[str, t.Any],
    ) -> None:
        if file_name == "CLAUDE.md" and project_name != "crackerjack":
            source_content = self._generate_project_claude_content(project_name)
        else:
            source_content = self._read_and_process_content(
                source_file, True, project_name
            )

        if not target_file.exists():
            self._write_file_and_track(target_file, source_content, file_name, results)
            return

        existing_content = target_file.read_text()

        crackerjack_start_marker = "< !- - CRACKERJACK INTEGRATION START-->"
        crackerjack_end_marker = "< !- - CRACKERJACK INTEGRATION END-->"

        if crackerjack_start_marker in existing_content:
            if force:
                start_idx = existing_content.find(crackerjack_start_marker)
                end_idx = existing_content.find(crackerjack_end_marker)
                if end_idx != -1:
                    end_idx += len(crackerjack_end_marker)

                    existing_content = (
                        existing_content[:start_idx] + existing_content[end_idx:]
                    ).strip()
            else:
                self._skip_existing_file(f"{file_name} (crackerjack section)", results)
                return

        merged_content = (
            existing_content.strip() + "\n\n" + crackerjack_start_marker + "\n"
        )
        merged_content += source_content.strip() + "\n"
        merged_content += crackerjack_end_marker + "\n"

        target_file.write_text(merged_content)
        t.cast("list[str]", results["files_copied"]).append(f"{file_name} (appended)")

        try:
            self.git_service.add_files([str(target_file)])
        except Exception as e:
            self.console.print(
                f"[yellow]⚠️[/ yellow] Could not git add {file_name}: {e}"
            )

        self.console.print(f"[green]✅[/ green] Appended to {file_name}")

    def _smart_merge_config(
        self,
        source_file: Path,
        target_file: Path,
        file_name: str,
        project_name: str,
        force: bool,
        results: dict[str, t.Any],
    ) -> None:
        if file_name == "pyproject.toml":
            self._smart_merge_pyproject(
                source_file,
                target_file,
                project_name,
                force,
                results,
            )
        elif file_name == ".pre-commit-config.yaml":
            self._smart_merge_pre_commit_config(
                source_file,
                target_file,
                project_name,
                force,
                results,
            )

        elif not target_file.exists() or force:
            content = self._read_and_process_content(
                source_file,
                True,
                project_name,
            )
            self._write_file_and_track(target_file, content, file_name, results)
        else:
            self._skip_existing_file(file_name, results)

    def _smart_merge_pyproject(
        self,
        source_file: Path,
        target_file: Path,
        project_name: str,
        force: bool,
        results: dict[str, t.Any],
    ) -> None:
        with source_file.open("rb") as f:
            source_config = tomli.load(f)

        if not target_file.exists():
            content = self._read_and_process_content(source_file, True, project_name)
            self._write_file_and_track(target_file, content, "pyproject.toml", results)
            return

        with target_file.open("rb") as f:
            target_config = tomli.load(f)

        self._ensure_crackerjack_dev_dependency(target_config, source_config)

        self._merge_tool_configurations(target_config, source_config, project_name)

        self._remove_fixed_coverage_requirements(target_config)

        import io

        buffer = io.BytesIO()
        tomli_w.dump(target_config, buffer)
        content = buffer.getvalue().decode("utf-8")

        from crackerjack.services.filesystem import FileSystemService

        content = FileSystemService.clean_trailing_whitespace_and_newlines(content)

        with target_file.open("w", encoding="utf-8") as f:
            f.write(content)

        t.cast("list[str]", results["files_copied"]).append("pyproject.toml (merged)")

        try:
            self.git_service.add_files([str(target_file)])
        except Exception as e:
            self.console.print(
                f"[yellow]⚠️[/ yellow] Could not git add pyproject.toml: {e}",
            )

        self.console.print("[green]✅[/ green] Smart merged pyproject.toml")

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
                        f"[green]➕[/ green] Added [tool.{tool_name}] configuration",
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
                f"[yellow]🔄[/ yellow] Updated [tool.{tool_name}] with: {', '.join(updated_keys)}",
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
                f"[green]➕[/ green] Added pytest markers: {len(new_markers)}",
            )

    def _remove_fixed_coverage_requirements(
        self,
        target_config: dict[str, t.Any],
    ) -> None:
        import re

        target_coverage = (
            target_config.get("tool", {}).get("pytest", {}).get("ini_options", {})
        )

        addopts = target_coverage.get("addopts", "")
        if isinstance(addopts, str):
            original_addopts = addopts

            addopts = re.sub(
                r"- - cov - fail-under =\d +\.?\d *\s *", "", addopts
            ).strip()

            addopts = " ".join(addopts.split())

            if original_addopts != addopts:
                target_coverage["addopts"] = addopts
                self.console.print(
                    "[green]🔄[/ green] Removed fixed coverage requirement (using ratchet system)",
                )

        coverage_report = (
            target_config.get("tool", {}).get("coverage", {}).get("report", {})
        )
        if "fail_under" in coverage_report:
            original_fail_under = coverage_report["fail_under"]
            coverage_report["fail_under"] = 0
            self.console.print(
                f"[green]🔄[/ green] Reset coverage.report.fail_under from {original_fail_under} to 0 (ratchet system)",
            )

    def _extract_coverage_requirement(self, addopts: str | list[str]) -> int | None:
        import re

        addopts_str = " ".join(addopts) if isinstance(addopts, list) else addopts
        match = re.search(r"- - cov - fail-under =(\d +)", addopts_str)
        return int(match.group(1)) if match else None

    def _smart_merge_pre_commit_config(
        self,
        source_file: Path,
        target_file: Path,
        project_name: str,
        force: bool,
        results: dict[str, t.Any],
    ) -> None:
        with source_file.open() as f:
            source_config = yaml.safe_load(f)

        if not target_file.exists():
            content = self._read_and_process_content(
                source_file,
                True,
                project_name,
            )

            from crackerjack.services.filesystem import FileSystemService

            content = FileSystemService.clean_trailing_whitespace_and_newlines(content)
            self._write_file_and_track(
                target_file,
                content,
                ".pre-commit-config.yaml",
                results,
            )
            return

        with target_file.open() as f:
            target_config = yaml.safe_load(f)

        if not isinstance(source_config, dict):
            source_config = {}
        if not isinstance(target_config, dict):
            target_config = {}

        source_repos = source_config.get("repos", [])
        target_repos = target_config.get("repos", [])

        existing_repo_urls = {repo.get("repo", "") for repo in target_repos}

        new_repos = [
            repo
            for repo in source_repos
            if repo.get("repo", "") not in existing_repo_urls
        ]

        if new_repos:
            target_repos.extend(new_repos)
            target_config["repos"] = target_repos

            yaml_content = yaml.dump(
                target_config,
                default_flow_style=False,
                sort_keys=False,
                width=float("inf"),
            )
            content = (
                yaml_content.decode()
                if isinstance(yaml_content, bytes)
                else yaml_content
            )

            if content is None:
                content = ""

            from crackerjack.services.filesystem import FileSystemService

            content = FileSystemService.clean_trailing_whitespace_and_newlines(content)

            with target_file.open("w") as f:
                f.write(content)

            t.cast("list[str]", results["files_copied"]).append(
                ".pre-commit-config.yaml (merged)",
            )

            try:
                self.git_service.add_files([str(target_file)])
            except Exception as e:
                self.console.print(
                    f"[yellow]⚠️[/ yellow] Could not git add .pre-commit-config.yaml: {e}",
                )

            self.console.print(
                f"[green]✅[/ green] Merged .pre-commit-config.yaml ({len(new_repos)} new repos)",
            )
        else:
            self._skip_existing_file(".pre-commit-config.yaml (no new repos)", results)

    def _replace_project_name_in_tool_config(
        self, tool_config: dict[str, t.Any], project_name: str
    ) -> dict[str, t.Any]:
        if project_name == "crackerjack":
            return tool_config

        import copy

        result = copy.deepcopy(tool_config)

        return self._replace_project_name_in_config_value(result, project_name)

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
