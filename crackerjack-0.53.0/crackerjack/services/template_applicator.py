import typing as t
from pathlib import Path

import tomli
import tomli_w
from rich.console import Console

from .template_detector import TemplateDetector


class TemplateApplicator:
    def __init__(
        self,
        console: t.Any | None = None,
        detector: TemplateDetector | None = None,
    ) -> None:
        self.console = console or Console()
        self.detector = detector or TemplateDetector(self.console)

        self.crackerjack_root = Path(__file__).parent.parent.parent
        self.templates_dir = self.crackerjack_root / "templates"

    def _select_template(
        self,
        project_path: Path,
        template_name: str | None,
        interactive: bool,
    ) -> str:
        if template_name:
            return self.detector.detect_template(
                project_path,
                manual_override=template_name,
            )

        auto_detected = self.detector.detect_template(project_path)
        if interactive:
            return self.detector.prompt_manual_selection(auto_detected)

        self.console.print(
            f"[green]✓[/green] Auto-detected template: [cyan]{auto_detected}[/cyan]",
        )
        return auto_detected

    def _load_and_prepare_template(
        self,
        template_name: str,
        package_name: str,
        project_path: Path,
        force: bool,
    ) -> dict[str, t.Any] | None:
        template_path = self.templates_dir / f"pyproject-{template_name}.toml"
        if not template_path.exists():
            return None

        with template_path.open("rb") as f:
            template_config = tomli.load(f)

        template_config = self._replace_placeholders(
            template_config,
            package_name,
            project_path,
        )

        pyproject_path = project_path / "pyproject.toml"
        if pyproject_path.exists() and not force:
            return self._smart_merge_configs(
                template_config,
                pyproject_path,
            )
        return template_config

    def apply_template(
        self,
        project_path: Path,
        *,
        template_name: str | None = None,
        package_name: str | None = None,
        interactive: bool = True,
        force: bool = False,
    ) -> dict[str, t.Any]:
        result: dict[str, t.Any] = {
            "success": False,
            "template_used": None,
            "errors": [],
            "modifications": [],
        }

        try:
            selected_template = self._select_template(
                project_path, template_name, interactive
            )
            result["template_used"] = selected_template

            if package_name is None:
                package_name = self._detect_package_name(project_path)

            if not package_name:
                result["errors"].append("Could not detect package name")
                return result

            merged_config = self._load_and_prepare_template(
                selected_template,
                package_name,
                project_path,
                force,
            )

            if merged_config is None:
                result["errors"].append(
                    f"Template file not found: {self.templates_dir / f'pyproject-{selected_template}.toml'}"
                )
                return result

            pyproject_path = project_path / "pyproject.toml"
            if pyproject_path.exists() and not force:
                result["modifications"].append("Smart merged with existing config")
            else:
                result["modifications"].append("Applied full template (new config)")

            with pyproject_path.open("wb") as f:
                tomli_w.dump(merged_config, f)

            result["success"] = True
            self.console.print(
                f"[green]✅ Applied {selected_template} template to {pyproject_path}[/green]",
            )

        except Exception as e:
            result["errors"].append(f"Template application failed: {e}")
            self.console.print(f"[red]❌ Error: {e}[/red]")

        return result

    def _detect_package_name(self, project_path: Path) -> str | None:
        from contextlib import suppress

        pyproject_path = project_path / "pyproject.toml"
        if pyproject_path.exists():
            with suppress(Exception):
                with pyproject_path.open("rb") as f:
                    config = tomli.load(f)
                project_name = config.get("project", {}).get("name")
                if project_name:
                    return project_name.replace("-", "_")

        return project_path.name.replace("-", "_")

    def _replace_placeholders(
        self,
        config: dict[str, t.Any],
        package_name: str,
        project_path: Path,
    ) -> dict[str, t.Any]:
        import json

        config_str = json.dumps(config)

        config_str = config_str.replace("<PACKAGE_NAME>", package_name)

        if "mcp" in package_name.lower() or (project_path / ".mcp.json").exists():
            import hashlib

            hash_val = int(hashlib.md5(package_name.encode()).hexdigest()[:4], 16)
            http_port = 3000 + (hash_val % 10000)
            ws_port = http_port - 1

            config_str = config_str.replace('"<MCP_HTTP_PORT>"', str(http_port))
            config_str = config_str.replace('"<MCP_WEBSOCKET_PORT>"', str(ws_port))

        config_replaced: dict[str, t.Any] = json.loads(config_str)
        return config_replaced

    def _smart_merge_configs(
        self,
        template_config: dict[str, t.Any],
        existing_path: Path,
    ) -> dict[str, t.Any]:
        with existing_path.open("rb") as f:
            existing_config = tomli.load(f)

        merged = existing_config.copy()

        if "tool" in template_config:
            if "tool" not in merged:
                merged["tool"] = {}

            for tool_name, tool_config in template_config["tool"].items():
                if tool_name not in merged["tool"]:
                    merged["tool"][tool_name] = tool_config
                    self.console.print(f"[green]+[/green] Added [tool.{tool_name}]")
                else:
                    merged["tool"][tool_name] = self._merge_tool_section(
                        merged["tool"][tool_name],
                        tool_config,
                        f"tool.{tool_name}",
                    )

        return merged

    def _merge_tool_section(
        self,
        existing: dict[str, t.Any],
        template: dict[str, t.Any],
        section_name: str,
    ) -> dict[str, t.Any]:
        merged = existing.copy()

        for key, value in template.items():
            if key not in merged:
                merged[key] = value
                self.console.print(f"[green]+[/green] Added [{section_name}].{key}")
            elif key == "markers" and isinstance(value, list):
                existing_markers = set(existing.get("markers", []))
                for marker in value:
                    if marker not in existing_markers:
                        merged["markers"] = merged.get("markers", []) + [marker]
                        self.console.print(
                            f"[green]+[/green] Added test marker: {marker.split(':')[0]}",
                        )
            elif isinstance(value, dict) and isinstance(merged.get(key), dict):
                merged[key] = self._merge_nested_dict(
                    merged[key],
                    value,
                    f"{section_name}.{key}",
                )

        return merged

    def _merge_nested_dict(
        self,
        existing: dict[str, t.Any],
        template: dict[str, t.Any],
        section_name: str,
    ) -> dict[str, t.Any]:
        merged = existing.copy()

        for key, value in template.items():
            if key not in merged:
                merged[key] = value
                self.console.print(f"[green]+[/green] Added [{section_name}].{key}")
            elif isinstance(value, dict) and isinstance(merged.get(key), dict):
                merged[key] = self._merge_nested_dict(
                    merged[key],
                    value,
                    f"{section_name}.{key}",
                )

        return merged

    def get_available_templates(self) -> list[str]:
        return [
            TemplateDetector.TEMPLATE_MINIMAL,
            TemplateDetector.TEMPLATE_LIBRARY,
            TemplateDetector.TEMPLATE_FULL,
        ]
