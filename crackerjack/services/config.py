import typing as t
from pathlib import Path

from rich.console import Console

from ..dynamic_config import DynamicConfigGenerator, generate_config_for_mode
from ..models.protocols import OptionsProtocol


class ConfigurationService:
    def __init__(self, console: Console, pkg_path: Path) -> None:
        self.console = console
        self.pkg_path = pkg_path
        self.config_generator = DynamicConfigGenerator()

    def update_precommit_config(self, options: OptionsProtocol) -> bool:
        try:
            mode = self._determine_config_mode(options)
            config_temp_path = generate_config_for_mode(mode)
            if not config_temp_path:
                self.console.print("[yellow]⚠️ No configuration generated[/yellow]")
                return False

            config_file = self.pkg_path / ".pre-commit-config.yaml"
            config_content = config_temp_path.read_text()
            config_file.write_text(config_content)

            self._temp_config_path = config_temp_path
            self.console.print("[green]✅[/green] Pre-commit configuration generated")
            return True
        except Exception as e:
            self.console.print(
                f"[red]❌[/red] Failed to generate pre-commit config: {e}"
            )
            return False

    def get_temp_config_path(self) -> Path | None:
        return getattr(self, "_temp_config_path", None)

    def _determine_config_mode(self, options: OptionsProtocol) -> str:
        if options.experimental_hooks:
            return "experimental"
        elif hasattr(options, "test") and options.test:
            return "comprehensive"
        return "comprehensive"

    def validate_config(self) -> bool:
        try:
            config_file = self.pkg_path / ".pre-commit-config.yaml"
            if not config_file.exists():
                self.console.print(
                    "[yellow]⚠️ No pre-commit configuration found[/yellow]"
                )
                return False
            import yaml

            with config_file.open("r") as f:
                yaml_result = yaml.safe_load(f)
                _ = (
                    t.cast(dict[str, t.Any], yaml_result)
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
                f"[cyan]💾[/cyan] Configuration backed up to {backup_file.name}"
            )
            return backup_file
        except Exception as e:
            self.console.print(
                f"[yellow]⚠️[/yellow] Failed to backup configuration: {e}"
            )
            return None

    def restore_config(self, backup_file: Path) -> bool:
        try:
            if not backup_file.exists():
                self.console.print(
                    f"[red]❌[/red] Backup file not found: {backup_file}"
                )
                return False
            config_file = self.pkg_path / ".pre-commit-config.yaml"
            config_file.write_text(backup_file.read_text())
            self.console.print(
                f"[green]✅[/green] Configuration restored from {backup_file.name}"
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

            with config_file.open("r") as f:
                yaml_result = yaml.safe_load(f)
                config_data = (
                    t.cast(dict[str, t.Any], yaml_result)
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

            with pyproject_file.open("r") as f:
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
                        "addopts": "--cov=crackerjack --cov-report=term --cov-fail-under=42",
                        "markers": [
                            "unit: marks test as a unit test",
                            "benchmark: mark test as a benchmark",
                            "integration: marks test as an integration test",
                            "no_leaks: detect asyncio task leaks",
                        ],
                    }
                }
            with pyproject_file.open("w") as f:
                f.write(dumps(config))
            self.console.print("[green]✅[/green] pyproject.toml configuration updated")
            return True
        except Exception as e:
            self.console.print(f"[red]❌[/red] Failed to update pyproject.toml: {e}")
            return False
