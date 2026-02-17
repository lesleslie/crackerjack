import typing as t
from pathlib import Path

import tomli
from rich.console import Console


class TemplateDetector:
    TEMPLATE_MINIMAL = "minimal"
    TEMPLATE_LIBRARY = "library"
    TEMPLATE_FULL = "full"

    def __init__(self, console: t.Any | None = None) -> None:
        self.console = console or Console()

    def detect_template(
        self,
        project_path: Path,
        *,
        manual_override: str | None = None,
    ) -> str:
        if manual_override:
            if manual_override in {
                self.TEMPLATE_MINIMAL,
                self.TEMPLATE_LIBRARY,
                self.TEMPLATE_FULL,
            }:
                return manual_override
            self.console.print(
                f"[yellow]⚠️ Invalid template '{manual_override}', using auto-detection[/yellow]",
            )

        pyproject_path = project_path / "pyproject.toml"
        if not pyproject_path.exists():
            return self.TEMPLATE_MINIMAL

        try:
            with pyproject_path.open("rb") as f:
                config = tomli.load(f)
        except Exception as e:
            self.console.print(
                f"[yellow]⚠️ Could not parse pyproject.toml: {e}[/yellow]",
            )
            return self.TEMPLATE_MINIMAL

        indicators = self._analyze_project(project_path, config)

        if indicators["is_mcp_server"] and not indicators["has_complex_deps"]:
            return self.TEMPLATE_MINIMAL

        if indicators["is_crackerjack"] or indicators["has_ai_agents"]:
            return self.TEMPLATE_FULL

        if indicators["is_library"] or indicators["has_complex_quality_tools"]:
            return self.TEMPLATE_LIBRARY

        return self.TEMPLATE_MINIMAL

    def _analyze_project(
        self,
        project_path: Path,
        config: dict[str, t.Any],
    ) -> dict[str, bool]:
        indicators: dict[str, bool] = {}

        project_name = config.get("project", {}).get("name", "")
        indicators["is_mcp_server"] = (
            "mcp" in project_name.lower()
            or (project_path / ".mcp.json").exists()
            or self._has_mcp_dependencies(config)
        )

        indicators["is_crackerjack"] = project_name == "crackerjack"

        indicators["has_ai_agents"] = self._has_ai_agent_indicators(
            project_path, config
        )

        indicators["has_complex_quality_tools"] = self._has_complex_quality_tools(
            config
        )

        indicators["is_library"] = self._is_library_project(project_path, config)

        indicators["has_complex_deps"] = self._has_complex_dependencies(config)

        return indicators

    def _has_mcp_dependencies(self, config: dict[str, t.Any]) -> bool:
        deps = config.get("project", {}).get("dependencies", [])
        mcp_related = {"fastmcp", "mcp", "mcp-common"}
        return any(
            dep for dep in deps if any(mcp in str(dep).lower() for mcp in mcp_related)
        )

    def _has_ai_agent_indicators(
        self,
        project_path: Path,
        config: dict[str, t.Any],
    ) -> bool:
        agents_dir = project_path / "agents"
        intelligence_dir = project_path / "intelligence"

        if agents_dir.exists() or intelligence_dir.exists():
            return True

        deps = config.get("project", {}).get("dependencies", [])
        ai_keywords = {
            "transformers",
            "onnxruntime",
            "anthropic",
            "openai",
            "nltk",
            "scikit-learn",
        }
        ai_dep_count = sum(
            1
            for dep in deps
            if any(keyword in str(dep).lower() for keyword in ai_keywords)
        )
        return ai_dep_count >= 3

    def _has_complex_quality_tools(self, config: dict[str, t.Any]) -> bool:
        quality_tools = {
            "tool.codespell",
            "tool.refurb",
            "tool.complexipy",
            "tool.vulture",
            "tool.mdformat",
        }
        found_tools = sum(1 for tool in quality_tools if tool in config)
        return found_tools >= 3

    def _is_library_project(
        self,
        project_path: Path,
        config: dict[str, t.Any],
    ) -> bool:
        classifiers = config.get("project", {}).get("classifiers", [])
        has_library_classifier = any("Library" in str(c) for c in classifiers)

        project_name = config.get("project", {}).get("name", "")
        package_name = project_name.replace("-", "_")
        has_package = (project_path / package_name / "__init__.py").exists()

        if has_package:
            py_files = list((project_path / package_name).rglob("*.py"))
            has_multiple_modules = len(py_files) > 3

            return has_library_classifier or has_multiple_modules

        return False

    def _has_complex_dependencies(self, config: dict[str, t.Any]) -> bool:
        deps = config.get("project", {}).get("dependencies", [])
        dep_groups = config.get("dependency-groups", {})

        return len(deps) > 15 or len(dep_groups) > 2

    def get_template_description(self, template: str) -> str:
        descriptions = {
            self.TEMPLATE_MINIMAL: "Minimal MCP Server (basic quality tools, fast setup)",
            self.TEMPLATE_LIBRARY: "Full-Featured Library (comprehensive testing, quality tools)",
            self.TEMPLATE_FULL: "Crackerjack-Level (AI agents, extended timeouts, full tooling)",
        }
        return descriptions.get(template, "Unknown template")

    def prompt_manual_selection(
        self,
        auto_detected: str,
    ) -> str:
        self.console.print("\n[bold]Template Selection[/bold]")
        self.console.print(
            f"[green]✓[/green] Auto-detected: [cyan]{auto_detected}[/cyan] - "
            f"{self.get_template_description(auto_detected)}",
        )

        self.console.print("\nAvailable templates:")
        self.console.print(
            f" 1. [cyan]{self.TEMPLATE_MINIMAL}[/cyan] - {self.get_template_description(self.TEMPLATE_MINIMAL)}"
        )
        self.console.print(
            f" 2. [cyan]{self.TEMPLATE_LIBRARY}[/cyan] - {self.get_template_description(self.TEMPLATE_LIBRARY)}"
        )
        self.console.print(
            f" 3. [cyan]{self.TEMPLATE_FULL}[/cyan] - {self.get_template_description(self.TEMPLATE_FULL)}"
        )
        self.console.print(" 4. Use auto-detected")

        choice = input("\nSelect template (1-4) [4]: ").strip() or "4"

        template_map = {
            "1": self.TEMPLATE_MINIMAL,
            "2": self.TEMPLATE_LIBRARY,
            "3": self.TEMPLATE_FULL,
            "4": auto_detected,
        }

        selected = template_map.get(choice, auto_detected)
        self.console.print(
            f"[green]✓[/green] Using template: [cyan]{selected}[/cyan]",
        )
        return selected
