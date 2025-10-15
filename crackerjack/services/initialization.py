import json
import subprocess
import typing as t
from pathlib import Path

import tomli
import yaml
from acb.console import Console
from acb.depends import Inject, depends

from crackerjack.models.protocols import ConfigMergeServiceProtocol

from .config_merge import ConfigMergeService
from .filesystem import FileSystemService
from .git import GitService
from .input_validator import get_input_validator, validate_and_sanitize_path


class InitializationService:
    @depends.inject
    def __init__(
        self,
        console: Inject[Console],
        filesystem: FileSystemService,
        git_service: GitService,
        pkg_path: Path,
        config_merge_service: ConfigMergeServiceProtocol | None = None,
    ) -> None:
        self.console = console
        self.filesystem = filesystem
        self.git_service = git_service
        self.pkg_path = pkg_path

        self.config_merge_service = config_merge_service or ConfigMergeService(
            filesystem, git_service
        )

    def initialize_project(self, project_path: str | Path) -> bool:
        try:
            result = self.initialize_project_full(Path(project_path))
            success = result.get("success", False)
            return bool(success)
        except Exception:
            return False

    def setup_git_hooks(self) -> bool:
        try:
            return True
        except Exception:
            return False

    def validate_project_structure(self) -> bool:
        try:
            return True
        except Exception:
            return False

    def initialize_project_full(
        self,
        target_path: Path | None = None,
        force: bool = False,
    ) -> dict[str, t.Any]:
        if target_path is None:
            target_path = Path.cwd()

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

            validator = get_input_validator()
            name_result = validator.validate_project_name(project_name)
            if not name_result.valid:
                results["errors"].append(
                    f"Invalid project name: {name_result.error_message}"
                )
                results["success"] = False
                return results

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
        # Skip pre-commit configuration to prevent hook installation
        return {
            "pyproject.toml": "smart_merge",
            ".gitignore": "smart_merge_gitignore",
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

        # Use crackerjack's project root for template files
        crackerjack_project_root = Path(__file__).parent.parent.parent
        source_file = crackerjack_project_root / file_name
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
            elif merge_strategy == "smart_merge_gitignore":
                self._smart_merge_gitignore(
                    target_file,
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
        # Use crackerjack's project root for template files
        crackerjack_project_root = Path(__file__).parent.parent.parent
        source_file = crackerjack_project_root / "example.mcp.json"

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

    def _generate_project_claude_content(self, project_name: str) -> str:
        return """


This project uses crackerjack for Python project management and quality assurance.


For optimal development experience with this crackerjack - enabled project, use these specialized agents:


- **🏗️ crackerjack-architect**: Expert in crackerjack's modular architecture and Python project management patterns. **Use PROACTIVELY** for all feature development, architectural decisions, and ensuring code follows crackerjack standards from the start.

- **🐍 python-pro**: Modern Python development with type hints, async/await patterns, and clean architecture

- **🧪 pytest-hypothesis-specialist**: Advanced testing patterns, property-based testing, and test optimization


- **🧪 crackerjack-test-specialist**: Advanced testing specialist for complex testing scenarios and coverage optimization
- **🏗️ backend-architect**: System design, API architecture, and service integration patterns
- **🔒 security-auditor**: Security analysis, vulnerability detection, and secure coding practices


```bash

Task tool with subagent_type ="crackerjack-architect" for feature planning


Task tool with subagent_type ="python-pro" for code implementation


Task tool with subagent_type ="pytest-hypothesis-specialist" for test development


Task tool with subagent_type ="security-auditor" for security analysis
```

**💡 Pro Tip**: The crackerjack-architect agent automatically ensures code follows crackerjack patterns from the start, eliminating the need for retrofitting and quality fixes.


This project follows crackerjack's clean code philosophy:


- **EVERY LINE OF CODE IS A LIABILITY**: The best code is no code
- **DRY (Don't Repeat Yourself)**: If you write it twice, you're doing it wrong
- **YAGNI (You Ain't Gonna Need It)**: Build only what's needed NOW
- **KISS (Keep It Simple, Stupid)**: Complexity is the enemy of maintainability


- **Cognitive complexity ≤15 **per function (automatically enforced)
- **Coverage ratchet system**: Never decrease coverage, always improve toward 100%
- **Type annotations required**: All functions must have return type hints
- **Security patterns**: No hardcoded paths, proper temp file handling
- **Python 3.13+ modern patterns**: Use `|` unions, pathlib over os.path


```bash

python -m crackerjack


python -m crackerjack - t


python -m crackerjack - - ai - agent - t


python -m crackerjack - a patch
```


1. **Plan with crackerjack-architect**: Ensure proper architecture from the start
2. **Implement with python-pro**: Follow modern Python patterns
3. **Test comprehensively**: Use pytest-hypothesis-specialist for robust testing
4. **Run quality checks**: `python -m crackerjack -t` before committing
5. **Security review**: Use security-auditor for final validation


- **Use crackerjack-architect agent proactively** for all significant code changes
- **Never reduce test coverage** - the ratchet system only allows improvements
- **Follow crackerjack patterns** - the tools will enforce quality automatically
- **Leverage AI agent auto-fixing** - `python -m crackerjack --ai-agent -t` for autonomous quality fixes

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
        try:
            if file_name == "CLAUDE.md" and project_name != "crackerjack":
                source_content = self._generate_project_claude_content(project_name)
            else:
                source_content = self._read_and_process_content(
                    source_file, True, project_name
                )

            crackerjack_start_marker = "<!-- CRACKERJACK INTEGRATION START -->"
            crackerjack_end_marker = "<!-- CRACKERJACK INTEGRATION END -->"

            merged_content = self.config_merge_service.smart_append_file(
                source_content,
                target_file,
                crackerjack_start_marker,
                crackerjack_end_marker,
                force,
            )

            if target_file.exists():
                existing_content = target_file.read_text()
                if crackerjack_start_marker in existing_content and not force:
                    self._skip_existing_file(
                        f"{file_name} (crackerjack section)", results
                    )
                    return

            target_file.write_text(merged_content)
            t.cast("list[str]", results["files_copied"]).append(
                f"{file_name} (appended)"
            )

            try:
                self.git_service.add_files([str(target_file)])
            except Exception as e:
                self.console.print(
                    f"[yellow]⚠️[/ yellow] Could not git add {file_name}: {e}"
                )

            self.console.print(f"[green]✅[/ green] Appended to {file_name}")

        except Exception as e:
            self._handle_file_processing_error(file_name, e, results)

    def _smart_merge_gitignore(
        self,
        target_file: Path,
        project_name: str,
        force: bool,
        results: dict[str, t.Any],
    ) -> None:
        gitignore_patterns = [
            "# Build/Distribution",
            "/build/",
            "/dist/",
            "*.egg-info/",
            "",
            "# Caches",
            "__pycache__/",
            ".mypy_cache/",
            ".ruff_cache/",
            ".pytest_cache/",
            "",
            "# Coverage",
            ".coverage*",
            "htmlcov/",
            "",
            "# Development",
            ".venv/",
            ".DS_STORE",
            "*.pyc",
            "",
            "# Crackerjack specific",
            "crackerjack-debug-*.log",
            "crackerjack-ai-debug-*.log",
            ".crackerjack-*",
        ]

        try:
            merged_content = self.config_merge_service.smart_merge_gitignore(
                gitignore_patterns, target_file
            )

            target_file.write_text(merged_content)
            t.cast("list[str]", results["files_copied"]).append(".gitignore (merged)")

            try:
                self.git_service.add_files([str(target_file)])
            except Exception as e:
                self.console.print(
                    f"[yellow]⚠️[/ yellow] Could not git add .gitignore: {e}"
                )

            self.console.print("[green]✅[/ green] Smart merged .gitignore")

        except Exception as e:
            self._handle_file_processing_error(".gitignore", e, results)

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
        try:
            with source_file.open("rb") as f:
                source_config = tomli.load(f)

            merged_config = self.config_merge_service.smart_merge_pyproject(
                source_config, target_file, project_name
            )

            self.config_merge_service.write_pyproject_config(merged_config, target_file)

            t.cast("list[str]", results["files_copied"]).append(
                "pyproject.toml (merged)"
            )

            try:
                self.git_service.add_files([str(target_file)])
            except Exception as e:
                self.console.print(
                    f"[yellow]⚠️[/ yellow] Could not git add pyproject.toml: {e}",
                )

            self.console.print("[green]✅[/ green] Smart merged pyproject.toml")

        except Exception as e:
            self._handle_file_processing_error("pyproject.toml", e, results)

    def _smart_merge_pre_commit_config(
        self,
        source_file: Path,
        target_file: Path,
        project_name: str,
        force: bool,
        results: dict[str, t.Any],
    ) -> None:
        try:
            source_config = self._load_source_config(source_file)
            if source_config is None:
                return

            merged_config = self._perform_config_merge(
                source_config, target_file, project_name
            )

            if self._should_skip_merge(target_file, merged_config, results):
                return

            self._write_and_finalize_config(
                merged_config, target_file, source_config, results
            )

        except Exception as e:
            self._handle_file_processing_error(".pre-commit-config.yaml", e, results)

    def _load_source_config(self, source_file: Path) -> dict[str, t.Any] | None:
        with source_file.open() as f:
            loaded_config = yaml.safe_load(f)
            source_config: dict[str, t.Any] = (
                loaded_config if isinstance(loaded_config, dict) else {}
            )

        if not isinstance(source_config, dict):
            self.console.print(
                "[yellow]⚠️[/yellow] Source .pre-commit-config.yaml is not a dictionary, skipping merge"
            )
            return None

        return source_config

    def _perform_config_merge(
        self, source_config: dict[str, t.Any], target_file: Path, project_name: str
    ) -> dict[str, t.Any]:
        return self.config_merge_service.smart_merge_pre_commit_config(
            source_config, target_file, project_name
        )

    def _should_skip_merge(
        self,
        target_file: Path,
        merged_config: dict[str, t.Any],
        results: dict[str, t.Any],
    ) -> bool:
        if not target_file.exists():
            return False

        with target_file.open() as f:
            loaded_config = yaml.safe_load(f)
            old_config: dict[str, t.Any] = (
                loaded_config if isinstance(loaded_config, dict) else {}
            )

        if not isinstance(old_config, dict):
            old_config = {}

        old_repo_count = len(old_config.get("repos", []))
        new_repo_count = len(merged_config.get("repos", []))

        if new_repo_count == old_repo_count:
            self._skip_existing_file(".pre-commit-config.yaml (no new repos)", results)
            return True

        return False

    def _write_and_finalize_config(
        self,
        merged_config: dict[str, t.Any],
        target_file: Path,
        source_config: dict[str, t.Any],
        results: dict[str, t.Any],
    ) -> None:
        self.config_merge_service.write_pre_commit_config(merged_config, target_file)

        t.cast("list[str]", results["files_copied"]).append(
            ".pre-commit-config.yaml (merged)"
        )

        self._git_add_config_file(target_file)
        self._display_merge_success(source_config)

    def _git_add_config_file(self, target_file: Path) -> None:
        try:
            self.git_service.add_files([str(target_file)])
        except Exception as e:
            self.console.print(
                f"[yellow]⚠️[/ yellow] Could not git add .pre-commit-config.yaml: {e}"
            )

    def _display_merge_success(self, source_config: dict[str, t.Any]) -> None:
        source_repo_count = len(source_config.get("repos", []))
        self.console.print(
            f"[green]✅[/ green] Merged .pre-commit-config.yaml ({source_repo_count} repos processed)"
        )
