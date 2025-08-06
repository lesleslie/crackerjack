import json
import subprocess
import typing as t
from pathlib import Path

from rich.console import Console

from .filesystem import FileSystemService
from .git import GitService


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
        self, target_path: Path | None = None, force: bool = False
    ) -> dict[str, t.Any]:
        if target_path is None:
            target_path = Path.cwd()

        results = self._create_results_dict(target_path)

        try:
            config_files = self._get_config_files()
            project_name = target_path.name

            for file_name, should_replace in config_files.items():
                self._process_config_file(
                    file_name, should_replace, project_name, target_path, force, results
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

    def _get_config_files(self) -> dict[str, bool]:
        return {
            ".pre-commit-config.yaml": True,
            "pyproject.toml": True,
            "CLAUDE.md": True,
            "RULES.md": True,
            "mcp.json": False,  # Special handling: mcp.json -> .mcp.json with merging
        }

    def _process_config_file(
        self,
        file_name: str,
        should_replace: bool,
        project_name: str,
        target_path: Path,
        force: bool,
        results: dict[str, t.Any],
    ) -> None:
        # Special handling for mcp.json -> .mcp.json
        if file_name == "mcp.json":
            self._process_mcp_config(target_path, force, results)
            return

        source_file = self.pkg_path.parent / file_name
        target_file = target_path / file_name

        if not source_file.exists():
            self._handle_missing_source_file(file_name, results)
            return

        try:
            if not self._should_copy_file(target_file, force, file_name, results):
                return

            content = self._read_and_process_content(
                source_file, should_replace, project_name
            )

            self._write_file_and_track(target_file, content, file_name, results)

        except Exception as e:
            self._handle_file_processing_error(file_name, e, results)

    def _should_copy_file(
        self, target_file: Path, force: bool, file_name: str, results: dict[str, t.Any]
    ) -> bool:
        if target_file.exists() and not force:
            t.cast(list[str], results["files_skipped"]).append(file_name)
            self.console.print(
                f"[yellow]⚠️[/yellow] Skipped {file_name} (already exists)"
            )
            return False
        return True

    def _read_and_process_content(
        self, source_file: Path, should_replace: bool, project_name: str
    ) -> str:
        content = source_file.read_text()

        if should_replace and project_name != "crackerjack":
            content = content.replace("crackerjack", project_name)

        return content

    def _write_file_and_track(
        self, target_file: Path, content: str, file_name: str, results: dict[str, t.Any]
    ) -> None:
        target_file.write_text(content)
        t.cast(list[str], results["files_copied"]).append(file_name)

        try:
            self.git_service.add_files([str(target_file)])
        except Exception as e:
            self.console.print(f"[yellow]⚠️[/yellow] Could not git add {file_name}: {e}")

        self.console.print(f"[green]✅[/green] Copied {file_name}")

    def _handle_missing_source_file(
        self, file_name: str, results: dict[str, t.Any]
    ) -> None:
        error_msg = f"Source file not found: {file_name}"
        t.cast(list[str], results["errors"]).append(error_msg)
        self.console.print(f"[yellow]⚠️[/yellow] {error_msg}")

    def _handle_file_processing_error(
        self, file_name: str, error: Exception, results: dict[str, t.Any]
    ) -> None:
        error_msg = f"Failed to copy {file_name}: {error}"
        t.cast(list[str], results["errors"]).append(error_msg)
        results["success"] = False
        self.console.print(f"[red]❌[/red] {error_msg}")

    def _print_summary(self, results: dict[str, t.Any]) -> None:
        if results["success"]:
            self.console.print(
                f"[green]🎉 Project initialized successfully ! [/green] "
                f"Copied {len(t.cast(list[str], results['files_copied']))} files"
            )
        else:
            self.console.print(
                "[red]❌ Project initialization completed with errors[/red]"
            )

    def _handle_initialization_error(
        self, results: dict[str, t.Any], error: Exception
    ) -> None:
        results["success"] = False
        t.cast(list[str], results["errors"]).append(f"Initialization failed: {error}")
        self.console.print(f"[red]❌[/red] Initialization failed: {error}")

    def check_uv_installed(self) -> bool:
        try:
            result = subprocess.run(
                ["uv", " -- version"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def _process_mcp_config(
        self, target_path: Path, force: bool, results: dict[str, t.Any]
    ) -> None:
        """Handle special processing for mcp.json -> .mcp.json with merging."""
        # Source: mcp.json in crackerjack package (contains servers to add to projects)
        source_file = self.pkg_path / "mcp.json"
        # Target: .mcp.json in target project
        target_file = target_path / ".mcp.json"

        if not source_file.exists():
            self._handle_missing_source_file("mcp.json", results)
            return

        try:
            # Load the crackerjack MCP servers to add
            with source_file.open("r") as f:
                source_config = json.load(f)

            if not isinstance(source_config.get("mcpServers"), dict):
                self._handle_file_processing_error(
                    "mcp.json",
                    ValueError("Invalid mcp.json format: missing mcpServers"),
                    results,
                )
                return

            crackerjack_servers = source_config["mcpServers"]

            # If target .mcp.json doesn't exist, create it with crackerjack servers
            if not target_file.exists():
                target_config = {"mcpServers": crackerjack_servers}
                self._write_mcp_config_and_track(target_file, target_config, results)
                self.console.print(
                    "[green]✅[/green] Created .mcp.json with crackerjack MCP servers"
                )
                return

            # If target exists and force=False, skip unless we're merging
            if target_file.exists() and not force:
                # Always merge crackerjack servers into existing config
                self._merge_mcp_config(target_file, crackerjack_servers, results)
                return

            # If force=True, replace entirely with crackerjack servers
            target_config = {"mcpServers": crackerjack_servers}
            self._write_mcp_config_and_track(target_file, target_config, results)
            self.console.print(
                "[green]✅[/green] Updated .mcp.json with crackerjack MCP servers"
            )

        except Exception as e:
            self._handle_file_processing_error(".mcp.json", e, results)

    def _merge_mcp_config(
        self,
        target_file: Path,
        crackerjack_servers: dict[str, t.Any],
        results: dict[str, t.Any],
    ) -> None:
        """Merge crackerjack servers into existing .mcp.json."""
        try:
            # Load existing config
            with target_file.open("r") as f:
                existing_config = json.load(f)

            if not isinstance(existing_config.get("mcpServers"), dict):
                existing_config["mcpServers"] = {}

            # Merge crackerjack servers (they override existing ones with same name)
            existing_servers = existing_config["mcpServers"]
            updated_servers = {}

            for name, config in crackerjack_servers.items():
                if name in existing_servers:
                    self.console.print(
                        f"[yellow]🔄[/yellow] Updating existing MCP server: {name}"
                    )
                else:
                    self.console.print(
                        f"[green]➕[/green] Adding new MCP server: {name}"
                    )
                updated_servers[name] = config

            # Merge into existing config
            existing_servers.update(updated_servers)

            # Write the merged config
            self._write_mcp_config_and_track(target_file, existing_config, results)

            t.cast(list[str], results["files_copied"]).append(".mcp.json (merged)")

        except Exception as e:
            self._handle_file_processing_error(".mcp.json (merge)", e, results)

    def _write_mcp_config_and_track(
        self, target_file: Path, config: dict[str, t.Any], results: dict[str, t.Any]
    ) -> None:
        """Write MCP config file and track in results."""
        with target_file.open("w") as f:
            json.dump(config, f, indent=2)

        t.cast(list[str], results["files_copied"]).append(".mcp.json")

        # Try to git add the file
        try:
            self.git_service.add_files([str(target_file)])
        except Exception as e:
            self.console.print(f"[yellow]⚠️[/yellow] Could not git add .mcp.json: {e}")

    def validate_project_structure(self) -> bool:
        required_indicators = [
            self.pkg_path / "pyproject.toml",
            self.pkg_path / "setup.py",
        ]

        return any(path.exists() for path in required_indicators)
