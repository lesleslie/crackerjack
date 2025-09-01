import subprocess
import typing as t
from pathlib import Path

from rich.console import Console

from crackerjack.dynamic_config import DynamicConfigGenerator, generate_config_for_mode
from crackerjack.models.protocols import OptionsProtocol


class ConfigurationService:
    def __init__(self, console: Console, pkg_path: Path) -> None:
        self.console = console
        self.pkg_path = pkg_path
        self.config_generator = DynamicConfigGenerator()

    def update_precommit_config(self, options: OptionsProtocol) -> bool:
        """Update pre-commit configuration and dynamic config versions."""
        try:
            # Generate config first
            mode = self._determine_config_mode(options)
            config_temp_path = generate_config_for_mode(mode)
            if not config_temp_path:
                self.console.print("[yellow]⚠️ No configuration generated[/yellow]")
                return False

            config_file = self.pkg_path / ".pre-commit-config.yaml"
            config_content = config_temp_path.read_text()
            # Clean trailing whitespace and ensure single trailing newline
            from crackerjack.services.filesystem import FileSystemService

            config_content = FileSystemService.clean_trailing_whitespace_and_newlines(
                config_content
            )
            config_file.write_text(config_content)

            self._temp_config_path = config_temp_path
            self.console.print("[green]✅[/green] Pre-commit configuration generated")

            # Run pre-commit autoupdate if requested via -u flag
            if getattr(options, "update_precommit", False):
                success = self._run_precommit_autoupdate()
                if success:
                    self.console.print("[green]✅[/green] Pre-commit hooks updated")
                else:
                    self.console.print(
                        "[yellow]⚠️[/yellow] Pre-commit autoupdate had issues"
                    )

                # Also update dynamic config versions
                self._update_dynamic_config_versions()

            return True
        except Exception as e:
            self.console.print(
                f"[red]❌[/red] Failed to generate pre-commit config: {e}",
            )
            return False

    def get_temp_config_path(self) -> Path | None:
        return getattr(self, "_temp_config_path", None)

    def _determine_config_mode(self, options: OptionsProtocol) -> str:
        if options.experimental_hooks:
            return "experimental"
        if hasattr(options, "test") and options.test:
            return "comprehensive"
        return "comprehensive"

    def validate_config(self) -> bool:
        try:
            config_file = self.pkg_path / ".pre-commit-config.yaml"
            if not config_file.exists():
                self.console.print(
                    "[yellow]⚠️ No pre-commit configuration found[/yellow]",
                )
                return False
            import yaml

            with config_file.open() as f:
                yaml_result = yaml.safe_load(f)
                _ = (
                    t.cast("dict[str, t.Any]", yaml_result)
                    if yaml_result is not None
                    else {}
                )
            self.console.print("[green]✅[/green] Pre-commit configuration is valid")
            return True
        except Exception as e:
            self.console.print(f"[red]❌[/red] Configuration validation failed: {e}")
            return False

    def backup_config(self) -> Path | None:
        try:
            config_file = self.pkg_path / ".pre-commit-config.yaml"
            if not config_file.exists():
                return None
            import time

            timestamp = int(time.time())
            backup_file = self.pkg_path / f".pre-commit-config.yaml.backup.{timestamp}"
            backup_file.write_text(config_file.read_text())
            self.console.print(
                f"[cyan]💾[/cyan] Configuration backed up to {backup_file.name}",
            )
            return backup_file
        except Exception as e:
            self.console.print(
                f"[yellow]⚠️[/yellow] Failed to backup configuration: {e}",
            )
            return None

    def restore_config(self, backup_file: Path) -> bool:
        try:
            if not backup_file.exists():
                self.console.print(
                    f"[red]❌[/red] Backup file not found: {backup_file}",
                )
                return False
            config_file = self.pkg_path / ".pre-commit-config.yaml"
            config_file.write_text(backup_file.read_text())
            self.console.print(
                f"[green]✅[/green] Configuration restored from {backup_file.name}",
            )
            return True
        except Exception as e:
            self.console.print(f"[red]❌[/red] Failed to restore configuration: {e}")
            return False

    def get_config_info(self) -> dict[str, t.Any]:
        try:
            config_file = self.pkg_path / ".pre-commit-config.yaml"
            if not config_file.exists():
                return {"exists": False}
            import yaml

            with config_file.open() as f:
                yaml_result = yaml.safe_load(f)
                config_data = (
                    t.cast("dict[str, t.Any]", yaml_result)
                    if isinstance(yaml_result, dict)
                    else {}
                )
            repos = config_data.get("repos", [])
            if not isinstance(repos, list):
                repos = []
            hook_count = sum(
                len(repo.get("hooks", [])) for repo in repos if isinstance(repo, dict)
            )
            stat = config_file.stat()

            return {
                "exists": True,
                "file_size": stat.st_size,
                "modified_time": stat.st_mtime,
                "repo_count": len([r for r in repos if isinstance(r, dict)]),
                "hook_count": hook_count,
                "repos": [
                    {
                        "repo": repo.get("repo", "unknown"),
                        "rev": repo.get("rev", "unknown"),
                        "hooks": len(repo.get("hooks", [])),
                    }
                    for repo in repos
                    if isinstance(repo, dict)
                ],
            }
        except Exception as e:
            return {"exists": True, "error": str(e)}

    def update_pyproject_config(self, options: OptionsProtocol) -> bool:
        try:
            pyproject_file = self.pkg_path / "pyproject.toml"
            if not pyproject_file.exists():
                self.console.print("[yellow]⚠️ No pyproject.toml found[/yellow]")
                return False
            from tomllib import loads

            from tomli_w import dumps

            with pyproject_file.open() as f:
                content = f.read()
            config = loads(content)
            if "tool" not in config:
                config["tool"] = {}
            if "ruff" not in config["tool"]:
                config["tool"]["ruff"] = {
                    "target-version": "py313",
                    "line-length": 88,
                    "fix": True,
                    "unsafe-fixes": True,
                    "show-fixes": True,
                    "output-format": "full",
                }
                config["tool"]["ruff"]["format"] = {"docstring-code-format": True}
                config["tool"]["ruff"]["lint"] = {
                    "extend-select": ["C901", "F", "I", "UP"],
                    "ignore": ["E402", "F821"],
                    "fixable": ["ALL"],
                }
            if "pytest" not in config["tool"]:
                config["tool"]["pytest"] = {
                    "ini_options": {
                        "asyncio_mode": "auto",
                        "timeout": 300,
                        "addopts": "--cov=crackerjack --cov-report=term",
                        "markers": [
                            "unit: marks test as a unit test",
                            "benchmark: mark test as a benchmark",
                            "integration: marks test as an integration test",
                            "no_leaks: detect asyncio task leaks",
                        ],
                    },
                }
            # Clean the content before writing to prevent hook failures
            from crackerjack.services.filesystem import FileSystemService

            content = dumps(config)
            content = FileSystemService.clean_trailing_whitespace_and_newlines(content)
            with pyproject_file.open("w") as f:
                f.write(content)
            self.console.print("[green]✅[/green] pyproject.toml configuration updated")
            return True
        except Exception as e:
            self.console.print(f"[red]❌[/red] Failed to update pyproject.toml: {e}")
            return False

    def _run_precommit_autoupdate(self) -> bool:
        """Run pre-commit autoupdate to get latest hook versions."""
        import subprocess

        try:
            self.console.print("[cyan]🔄[/cyan] Running pre-commit autoupdate...")
            result = self._execute_precommit_autoupdate()

            if result.returncode == 0:
                self._display_autoupdate_results(result.stdout)
                return True
            else:
                self._handle_autoupdate_error(result.stderr)
                return False

        except subprocess.TimeoutExpired:
            self.console.print("[red]❌[/red] Pre-commit autoupdate timed out")
            return False
        except Exception as e:
            self.console.print(
                f"[red]❌[/red] Failed to run pre-commit autoupdate: {e}"
            )
            return False

    def _execute_precommit_autoupdate(self) -> subprocess.CompletedProcess[str]:
        """Execute the pre-commit autoupdate command."""

        return subprocess.run(
            ["uv", "run", "pre-commit", "autoupdate"],
            cwd=self.pkg_path,
            capture_output=True,
            text=True,
            timeout=60,
        )

    def _display_autoupdate_results(self, stdout: str) -> None:
        """Display updated versions if any."""
        if self._has_updates(stdout):
            for line in stdout.split("\n"):
                if self._is_update_line(line):
                    self.console.print(f"[dim]  {line.strip()}[/dim]")

    def _has_updates(self, stdout: str) -> bool:
        """Check if the output contains update information."""
        stdout_lower = stdout.lower()
        return "updating" in stdout_lower or "updated" in stdout_lower

    def _is_update_line(self, line: str) -> bool:
        """Check if a line contains update information."""
        return "updating" in line.lower() or "->" in line

    def _handle_autoupdate_error(self, stderr: str) -> None:
        """Handle pre-commit autoupdate error output."""
        if stderr:
            self.console.print(
                f"[yellow]Pre-commit autoupdate stderr:[/yellow] {stderr}"
            )

    def _update_dynamic_config_versions(self) -> None:
        """Update hardcoded versions in dynamic_config.py based on .pre-commit-config.yaml."""
        try:
            self.console.print("[cyan]🔄[/cyan] Updating dynamic config versions...")

            version_updates = self._extract_version_updates()
            if version_updates:
                self._update_dynamic_config_file(version_updates)

        except Exception as e:
            self.console.print(
                f"[yellow]⚠️[/yellow] Failed to update dynamic config versions: {e}"
            )

    def _extract_version_updates(self) -> dict[str, str]:
        """Extract version mappings from .pre-commit-config.yaml."""
        config_file = self.pkg_path / ".pre-commit-config.yaml"
        if not config_file.exists():
            return {}

        import yaml

        with config_file.open() as f:
            config = yaml.safe_load(f)

        if not config or "repos" not in config:
            return {}

        version_updates = {}
        repos = config.get("repos", []) if isinstance(config, dict) else []
        for repo in repos:
            repo_url = repo.get("repo", "")
            rev = repo.get("rev", "")
            if repo_url and rev:
                version_updates[repo_url] = rev

        return version_updates

    def _update_dynamic_config_file(self, version_updates: dict[str, str]) -> None:
        """Update dynamic_config.py with version mappings."""
        dynamic_config_path = self.pkg_path / "crackerjack" / "dynamic_config.py"
        if dynamic_config_path.exists():
            self._apply_version_updates(dynamic_config_path, version_updates)

    def _apply_version_updates(
        self, config_path: Path, version_updates: dict[str, str]
    ) -> None:
        """Apply version updates to dynamic_config.py."""
        try:
            content = config_path.read_text()
            updated = False

            for repo_url, new_rev in version_updates.items():
                # Find and update the revision for this repo
                import re

                pattern = rf'("repo": "{re.escape(repo_url)}".*?"rev": )"([^"]+)"'
                replacement = rf'\1"{new_rev}"'

                new_content = re.sub(pattern, replacement, content, flags=re.DOTALL)
                if new_content != content:
                    content = new_content
                    updated = True
                    self.console.print(f"[dim]  Updated {repo_url} to {new_rev}[/dim]")

            if updated:
                config_path.write_text(content)
                self.console.print("[green]✅[/green] Dynamic config versions updated")

        except Exception as e:
            self.console.print(
                f"[yellow]⚠️[/yellow] Failed to apply version updates: {e}"
            )
