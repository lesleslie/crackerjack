import hashlib
import typing as t
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import tomli
import yaml
from rich.console import Console


@dataclass
class ConfigUpdateInfo:
    config_type: str
    current_version: str
    latest_version: str
    needs_update: bool
    diff_preview: str = ""
    last_updated: datetime | None = None


@dataclass
class ConfigVersion:
    version: str
    config_data: dict[str, t.Any]
    dependencies: list[str] = field(default_factory=list)
    description: str = ""


class ConfigTemplateService:
    """Version-based configuration template management service."""

    def __init__(self, console: Console, pkg_path: Path) -> None:
        self.console = console
        self.pkg_path = pkg_path
        self.templates = self._load_config_templates()

    def _load_config_templates(self) -> dict[str, ConfigVersion]:
        """Load configuration templates as structured data."""
        return {
            "pyproject": self._create_pyproject_template(),
        }

    def _create_pyproject_template(self) -> ConfigVersion:
        """Create pyproject.toml configuration template."""
        return ConfigVersion(
            version="1.2.0",
            description="Modern Python project configuration with Ruff and pytest",
            config_data={"tool": self._build_pyproject_tools()},
        )

    def _build_pyproject_tools(self) -> dict[str, t.Any]:
        """Build pyproject.toml tool configurations."""
        return {
            "ruff": self._build_ruff_config(),
            "pytest": self._build_pytest_config(),
        }

    def _build_ruff_config(self) -> dict[str, t.Any]:
        """Build Ruff configuration."""
        return {
            "target-version": "py313",
            "line-length": 88,
            "fix": True,
            "unsafe-fixes": True,
            "show-fixes": True,
            "output-format": "full",
            "format": {"docstring-code-format": True},
            "lint": {
                "extend-select": ["C901", "F", "I", "UP"],
                "ignore": ["E402", "F821"],
                "fixable": ["ALL"],
            },
        }

    def _build_pytest_config(self) -> dict[str, t.Any]:
        """Build pytest configuration."""
        return {
            "ini_options": {
                "asyncio_mode": "auto",
                "timeout": 300,
                "addopts": "--cov=crackerjack --cov-report=term-missing:skip-covered",
                "testpaths": ["tests"],
                "markers": [
                    "unit: marks test as a unit test",
                    "integration: marks test as an integration test",
                    "no_leaks: detect asyncio task leaks",
                ],
            },
        }

    def get_template(
        self, config_type: str, version: str | None = None
    ) -> ConfigVersion | None:
        """Get configuration template by type and optional version."""
        if config_type not in self.templates:
            return None

        template = self.templates[config_type]
        if version and template.version != version:
            return None

        return template

    def check_updates(self, project_path: Path) -> dict[str, ConfigUpdateInfo]:
        """Check if newer configuration versions are available."""
        updates = {}

        version_file = project_path / ".crackerjack-config.yaml"
        current_versions = self._load_current_versions(version_file)

        for config_type, template in self.templates.items():
            current_version = current_versions.get(config_type, "0.0.0")
            needs_update = self._version_compare(current_version, template.version) < 0

            update_info = ConfigUpdateInfo(
                config_type=config_type,
                current_version=current_version,
                latest_version=template.version,
                needs_update=needs_update,
            )

            if needs_update:
                update_info.diff_preview = self._generate_diff_preview(
                    config_type, project_path
                )

            updates[config_type] = update_info

        return updates

    def _load_current_versions(self, version_file: Path) -> dict[str, str]:
        """Load current configuration versions from tracking file."""
        if not version_file.exists():
            return {}

        try:
            with version_file.open() as f:
                data = yaml.safe_load(f)
                if not isinstance(data, dict):
                    return {}
                configs = data.get("configs", {})
                if not isinstance(configs, dict):
                    return {}
                return {
                    name: config.get("version", "0.0.0")
                    for name, config in configs.items()
                    if isinstance(config, dict)
                }
        except Exception:
            return {}

    def _version_compare(self, version1: str, version2: str) -> int:
        """Compare two semantic versions. Returns -1, 0, or 1."""

        def version_tuple(v: str) -> tuple[int, ...]:
            return tuple(int(x) for x in v.split("."))

        v1_tuple = version_tuple(version1)
        v2_tuple = version_tuple(version2)

        if v1_tuple < v2_tuple:
            return -1
        elif v1_tuple > v2_tuple:
            return 1
        return 0

    def _generate_diff_preview(self, config_type: str, project_path: Path) -> str:
        """Generate a preview of changes that would be made."""
        if config_type == "pyproject":
            config_file = project_path / "pyproject.toml"
        else:
            return "Diff preview not available for this config type"

        if not config_file.exists():
            return f"Would create new {config_file.name} file"

        try:
            with config_file.open() as f:
                content = f.read()
                current_config = tomli.loads(content)

            template = self.get_template(config_type)
            if not template:
                return "Template not found"

            return self._create_config_diff(current_config, template.config_data)
        except Exception as e:
            return f"Error generating diff preview: {e}"

    def _create_config_diff(
        self, current: dict[str, t.Any], new: dict[str, t.Any]
    ) -> str:
        """Create a simple diff between two configurations."""
        changes: list[str] = []
        self._collect_config_changes(current, new, changes)

        if not changes:
            return "No changes detected"

        return "\n".join(changes[:10])  # Limit to first 10 changes

    def _collect_config_changes(
        self,
        current: dict[str, t.Any],
        new: dict[str, t.Any],
        changes: list[str],
        path: str = "",
    ) -> None:
        """Collect configuration changes recursively."""
        self._collect_additions_and_modifications(current, new, changes, path)
        self._collect_removals(current, new, changes, path)

    def _collect_additions_and_modifications(
        self,
        current: dict[str, t.Any],
        new: dict[str, t.Any],
        changes: list[str],
        path: str,
    ) -> None:
        """Collect additions and modifications in configuration."""
        for key, value in new.items():
            key_path = f"{path}.{key}" if path else key

            if key not in current:
                changes.append(f"+ Add {key_path}: {value}")
            elif self._is_nested_dict(value, current[key]):
                self._collect_config_changes(current[key], value, changes, key_path)
            elif current[key] != value:
                changes.append(f"~ Change {key_path}: {current[key]} → {value}")

    def _collect_removals(
        self,
        current: dict[str, t.Any],
        new: dict[str, t.Any],
        changes: list[str],
        path: str,
    ) -> None:
        """Collect removals in configuration."""
        for key in current:
            if key not in new:
                key_path = f"{path}.{key}" if path else key
                changes.append(f"- Remove {key_path}")

    def _is_nested_dict(self, new_value: t.Any, current_value: t.Any) -> bool:
        """Check if both values are dictionaries for nested comparison."""
        return isinstance(new_value, dict) and isinstance(current_value, dict)

    def apply_update(
        self,
        config_type: str,
        project_path: Path,
        interactive: bool = False,
    ) -> bool:
        """Apply configuration update to project."""
        template = self.get_template(config_type)
        if not template:
            self.console.print(f"[red]❌[/red] Template not found: {config_type}")
            return False

        try:
            if config_type == "pyproject":
                return self._apply_pyproject_update(template, project_path, interactive)
            else:
                self.console.print(
                    f"[yellow]⚠️[/yellow] Unsupported config type: {config_type}"
                )
                return False
        except Exception as e:
            self.console.print(f"[red]❌[/red] Failed to apply update: {e}")
            return False

    def _apply_pyproject_update(
        self, template: ConfigVersion, project_path: Path, interactive: bool
    ) -> bool:
        """Apply pyproject.toml configuration update."""
        config_file = project_path / "pyproject.toml"

        if not config_file.exists():
            self.console.print(
                f"[yellow]⚠️[/yellow] pyproject.toml not found at {project_path}"
            )
            return False

        if interactive:
            self.console.print(f"\n[bold cyan]Updating {config_file.name}[/bold cyan]")
            diff = self._generate_diff_preview("pyproject", project_path)
            self.console.print(f"Changes:\n{diff}")

            if not self._confirm_update():
                return False

        try:
            # Read existing config
            with config_file.open() as f:
                content = f.read()
                existing_config = tomli.loads(content)

            # Merge tool sections from template
            if "tool" not in existing_config:
                existing_config["tool"] = {}

            for tool_name, tool_config in template.config_data.get("tool", {}).items():
                existing_config["tool"][tool_name] = tool_config

            # Write back using tomli_w
            from tomli_w import dumps

            updated_content = dumps(existing_config)

            with config_file.open("w") as f:
                f.write(updated_content)

            self._update_version_tracking(project_path, "pyproject", template.version)

            self.console.print(
                f"[green]✅[/green] Updated {config_file.name} to version {template.version}"
            )
            return True
        except Exception as e:
            self.console.print(f"[red]❌[/red] Failed to update pyproject.toml: {e}")
            return False

    def _confirm_update(self) -> bool:
        """Ask user to confirm update."""
        try:
            response = input("\nApply this update? [y/N]: ").strip().lower()
            return response in ("y", "yes")
        except (EOFError, KeyboardInterrupt):
            return False

    def _update_version_tracking(
        self, project_path: Path, config_type: str, version: str
    ) -> None:
        """Update version tracking file."""
        version_file = project_path / ".crackerjack-config.yaml"

        data: dict[str, t.Any] = {"version": "1.0.0", "configs": {}}
        if version_file.exists():
            with suppress(Exception):
                with version_file.open() as f:
                    existing_data = yaml.safe_load(f)
                    if isinstance(existing_data, dict):
                        data = existing_data

        if "configs" not in data:
            data["configs"] = {}

        data["configs"][config_type] = {
            "version": version,
            "last_updated": datetime.now().isoformat(),
        }

        with suppress(Exception):
            with version_file.open("w") as f:
                yaml.dump(data, f, default_flow_style=False, sort_keys=False)

    def _invalidate_cache(self, project_path: Path) -> None:
        """Invalidate cache to ensure fresh environment."""
        # No-op in the new system - cache invalidation handled differently
        pass

    def get_config_hash(self, config_path: Path) -> str:
        """Generate hash of configuration file for cache invalidation."""
        if not config_path.exists():
            return ""

        try:
            content = config_path.read_text()
            return hashlib.sha256(content.encode()).hexdigest()[:16]
        except Exception:
            return ""

    def list_available_templates(self) -> dict[str, str]:
        """List all available configuration templates."""
        return {name: template.description for name, template in self.templates.items()}
