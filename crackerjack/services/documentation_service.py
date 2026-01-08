import typing as t
from pathlib import Path

from rich.console import Console

from ..models.protocols import (
    APIExtractorProtocol,
    DocumentationGeneratorProtocol,
    DocumentationServiceProtocol,
)
from .api_extractor import APIExtractorImpl
from .documentation_generator import DocumentationGeneratorImpl


class DocumentationServiceImpl(DocumentationServiceProtocol):
    def __init__(
        self,
        pkg_path: Path,
        api_extractor: APIExtractorProtocol | None = None,
        doc_generator: DocumentationGeneratorProtocol | None = None,
    ) -> None:
        self.pkg_path = pkg_path
        self.api_extractor = api_extractor or APIExtractorImpl()
        self.doc_generator = doc_generator or DocumentationGeneratorImpl()
        self.console = Console()

        self.docs_dir = pkg_path / "docs"
        self.generated_docs_dir = self.docs_dir / "generated"
        self.api_docs_dir = self.generated_docs_dir / "api"
        self.guides_dir = self.generated_docs_dir / "guides"

        self._ensure_directories()

    def _categorize_source_files(
        self, source_paths: list[Path]
    ) -> dict[str, list[Path]]:
        python_files = [p for p in source_paths if p.suffix == ".py"]

        return {
            "python": python_files,
            "protocol": [p for p in python_files if p.name == "protocols.py"],
            "service": [p for p in python_files if "/services/" in str(p)],
            "manager": [p for p in python_files if "/managers/" in str(p)],
            "cli": [p for p in python_files if "/cli/" in str(p)],
            "mcp": [
                p
                for p in source_paths
                if "/mcp/" in str(p) or p.suffix in (".py", ".md")
            ],
        }

    def _extract_specialized_apis(
        self, categorized_files: dict[str, list[Path]]
    ) -> dict[str, t.Any]:
        api_data = {}

        if categorized_files["protocol"]:
            for protocol_file in categorized_files["protocol"]:
                protocol_data = self.api_extractor.extract_protocol_definitions(
                    protocol_file
                )
                api_data.update(protocol_data)

        if categorized_files["service"]:
            service_data = self.api_extractor.extract_service_interfaces(
                categorized_files["service"]
            )
            api_data.update(service_data)

        if categorized_files["manager"]:
            manager_data = self.api_extractor.extract_service_interfaces(
                categorized_files["manager"]
            )
            if "services" in manager_data:
                api_data["managers"] = manager_data["services"]

        if categorized_files["cli"]:
            cli_data = self.api_extractor.extract_cli_commands(categorized_files["cli"])
            api_data.update(cli_data)

        if categorized_files["mcp"]:
            mcp_data = self.api_extractor.extract_mcp_tools(categorized_files["mcp"])
            api_data.update(mcp_data)

        return api_data

    def extract_api_documentation(self, source_paths: list[Path]) -> dict[str, t.Any]:
        self.console.print(
            "[cyan]📖[/cyan] Extracting API documentation from source files..."
        )

        categorized_files = self._categorize_source_files(source_paths)
        api_data = {}

        if categorized_files["python"]:
            python_data = self.api_extractor.extract_from_python_files(
                categorized_files["python"]
            )
            api_data.update(python_data)

        api_data.update(self._extract_specialized_apis(categorized_files))

        self.console.print(
            f"[green]✅[/green] Extracted documentation from {len(source_paths)} files"
        )
        return api_data

    def generate_documentation(
        self, template_name: str, context: dict[str, t.Any]
    ) -> str:
        try:
            return self.doc_generator.render_template(Path(template_name), context)
        except (FileNotFoundError, ValueError):
            return self.doc_generator.generate_api_reference(context)

    def validate_documentation(self, doc_paths: list[Path]) -> list[dict[str, str]]:
        issues = []

        for doc_path in doc_paths:
            if not doc_path.exists():
                issues.append(
                    {
                        "type": "missing_file",
                        "path": str(doc_path),
                        "message": "Documentation file does not exist",
                    }
                )
                continue

            try:
                content = doc_path.read_text(encoding="utf-8")

                broken_links = self._check_internal_links(content, doc_path)
                issues.extend(broken_links)

                empty_sections = self._check_empty_sections(content, doc_path)
                issues.extend(empty_sections)

                outdated_refs = self._check_version_references(content, doc_path)
                issues.extend(outdated_refs)

            except Exception as e:
                issues.append(
                    {
                        "type": "read_error",
                        "path": str(doc_path),
                        "message": f"Could not read file: {e}",
                    }
                )

        return issues

    def update_documentation_index(self) -> bool:
        try:
            index_path = self.docs_dir / "INDEX.md"

            api_docs = (
                list[t.Any](self.api_docs_dir.glob("*.md"))
                if self.api_docs_dir.exists()
                else []
            )
            guide_docs = (
                list[t.Any](self.guides_dir.glob("*.md"))
                if self.guides_dir.exists()
                else []
            )
            root_docs = [
                f
                for f in self.docs_dir.glob("*.md")
                if f.name not in ("INDEX.md", "README.md")
            ]

            index_content = self._generate_index_content(
                api_docs, guide_docs, root_docs
            )

            index_path.write_text(index_content, encoding="utf-8")

            self.console.print(
                f"[green]✅[/green] Updated documentation index at {index_path}"
            )
            return True

        except Exception as e:
            self.console.print(
                f"[red]❌[/red] Failed to update documentation index: {e}"
            )
            return False

    def get_documentation_coverage(self) -> dict[str, t.Any]:
        source_files = self._find_source_files()

        api_data = self.extract_api_documentation(source_files)

        total_items, documented_items = self._count_documentation_items(api_data)

        coverage_percentage = (
            (documented_items / total_items * 100) if total_items > 0 else 0.0
        )

        return {
            "total_items": total_items,
            "documented_items": documented_items,
            "coverage_percentage": coverage_percentage,
            "undocumented_items": total_items - documented_items,
        }

    def _find_source_files(self) -> list[Path]:
        source_files = list[t.Any](self.pkg_path.glob("**/*.py"))
        return [
            f for f in source_files if not any(part.startswith(".") for part in f.parts)
        ]

    def _count_documentation_items(self, api_data: dict[str, t.Any]) -> tuple[int, int]:
        total_items = 0
        documented_items = 0

        protocol_total, protocol_documented = self._count_protocol_items(
            api_data.get("protocols", {})
        )
        total_items += protocol_total
        documented_items += protocol_documented

        module_total, module_documented = self._count_module_items(
            api_data.get("modules", {})
        )
        total_items += module_total
        documented_items += module_documented

        return total_items, documented_items

    def _count_protocol_items(self, protocols: dict[str, t.Any]) -> tuple[int, int]:
        total_items = 0
        documented_items = 0

        for protocol_info in protocols.values():
            total_items += 1
            if protocol_info.get("docstring", {}).get("description"):
                documented_items += 1

            method_total, method_documented = self._count_method_items(
                protocol_info.get("methods", [])
            )
            total_items += method_total
            documented_items += method_documented

        return total_items, documented_items

    def _count_module_items(self, modules: dict[str, t.Any]) -> tuple[int, int]:
        total_items = 0
        documented_items = 0

        for module_data in modules.values():
            class_total, class_documented = self._count_class_items(
                module_data.get("classes", [])
            )
            total_items += class_total
            documented_items += class_documented

            func_total, func_documented = self._count_function_items(
                module_data.get("functions", [])
            )
            total_items += func_total
            documented_items += func_documented

        return total_items, documented_items

    def _count_class_items(self, classes: list[dict[str, t.Any]]) -> tuple[int, int]:
        total_items = 0
        documented_items = 0

        for class_info in classes:
            total_items += 1
            if class_info.get("docstring", {}).get("description"):
                documented_items += 1

            method_total, method_documented = self._count_method_items(
                class_info.get("methods", [])
            )
            total_items += method_total
            documented_items += method_documented

        return total_items, documented_items

    def _count_function_items(
        self, functions: list[dict[str, t.Any]]
    ) -> tuple[int, int]:
        total_items = len(functions)
        documented_items = sum(
            1
            for func_info in functions
            if func_info.get("docstring", {}).get("description")
        )
        return total_items, documented_items

    def _count_method_items(self, methods: list[dict[str, t.Any]]) -> tuple[int, int]:
        total_items = len(methods)
        documented_items = sum(
            1 for method in methods if method.get("docstring", {}).get("description")
        )
        return total_items, documented_items

    def generate_full_api_documentation(self) -> bool:
        try:
            self.console.print(
                "[cyan]📚[/cyan] Generating complete API documentation..."
            )

            source_files = list[t.Any](self.pkg_path.glob("**/*.py"))
            source_files = [
                f
                for f in source_files
                if not any(part.startswith(".") for part in f.parts)
            ]

            api_data = self.extract_api_documentation(source_files)

            api_reference = self.doc_generator.generate_api_reference(api_data)
            api_ref_path = self.api_docs_dir / "API_REFERENCE.md"
            api_ref_path.write_text(api_reference, encoding="utf-8")

            if "protocols" in api_data:
                protocol_docs = self._generate_protocol_documentation(
                    api_data["protocols"]
                )
                protocol_path = self.api_docs_dir / "PROTOCOLS.md"
                protocol_path.write_text(protocol_docs, encoding="utf-8")

            if "services" in api_data:
                service_docs = self._generate_service_documentation(
                    api_data["services"]
                )
                service_path = self.api_docs_dir / "SERVICES.md"
                service_path.write_text(service_docs, encoding="utf-8")

            if "commands" in api_data:
                cli_docs = self._generate_cli_documentation(api_data["commands"])
                cli_path = self.api_docs_dir / "CLI_REFERENCE.md"
                cli_path.write_text(cli_docs, encoding="utf-8")

            cross_refs = self.doc_generator.generate_cross_references(api_data)
            if cross_refs:
                cross_ref_path = self.api_docs_dir / "CROSS_REFERENCES.md"
                cross_ref_content = self._format_cross_references(cross_refs)
                cross_ref_path.write_text(cross_ref_content, encoding="utf-8")

            self.update_documentation_index()

            self.console.print(
                "[green]🎉[/green] API documentation generation completed!"
            )
            return True

        except Exception as e:
            self.console.print(
                f"[red]❌[/red] Failed to generate API documentation: {e}"
            )
            return False

    def _ensure_directories(self) -> None:
        directories = [
            self.docs_dir,
            self.generated_docs_dir,
            self.api_docs_dir,
            self.guides_dir,
        ]

        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)

    def _check_internal_links(
        self, content: str, doc_path: Path
    ) -> list[dict[str, str]]:
        from .regex_patterns import SAFE_PATTERNS

        issues = []

        link_pattern = SAFE_PATTERNS["extract_markdown_links"]._get_compiled_pattern()
        matches = link_pattern.findall(content)

        for link_text, link_path in matches:
            if link_path.startswith(("http://", "https://", "mailto:")):
                continue

            if link_path.startswith("/"):
                target_path = self.pkg_path / link_path.lstrip("/")
            else:
                target_path = doc_path.parent / link_path

            if not target_path.exists():
                issues.append(
                    {
                        "type": "broken_link",
                        "path": str(doc_path),
                        "message": f"Broken internal link: [{link_text}]({link_path})",
                    }
                )

        return issues

    def _check_empty_sections(
        self, content: str, doc_path: Path
    ) -> list[dict[str, str]]:
        import re

        issues = []

        empty_section_pattern = re.compile(  # REGEX OK: markdown section parsing
            r"(#{1, 6}\s+[^\n]+)\n\s*(#{1, 6}\s+[^\n]+)", re.MULTILINE
        )
        matches = empty_section_pattern.findall(content)

        for header1, header2 in matches:
            issues.append(
                {
                    "type": "empty_section",
                    "path": str(doc_path),
                    "message": f"Empty section found: {header1.strip()}",
                }
            )

        return issues

    def _check_version_references(
        self, content: str, doc_path: Path
    ) -> list[dict[str, str]]:
        from .regex_patterns import SAFE_PATTERNS

        issues = []

        version_pattern = SAFE_PATTERNS[
            "extract_version_numbers"
        ]._get_compiled_pattern()
        matches = version_pattern.findall(content)

        for version in matches:
            if version != "1.0.0":
                issues.append(
                    {
                        "type": "outdated_version",
                        "path": str(doc_path),
                        "message": f"Potentially outdated version reference: {version}",
                    }
                )

        return issues

    def _generate_index_content(
        self, api_docs: list[Path], guide_docs: list[Path], root_docs: list[Path]
    ) -> str:
        lines = [
            "# Documentation Index\n\n",
            "This is the complete documentation index for the project.\n\n",
        ]

        if api_docs:
            lines.append("## API Documentation\n\n")
            for doc in sorted(api_docs):
                relative_path = doc.relative_to(self.docs_dir)
                lines.append(f"- [{doc.stem}]({relative_path})\n")
            lines.append("\n")

        if guide_docs:
            lines.append("## User Guides\n\n")
            for doc in sorted(guide_docs):
                relative_path = doc.relative_to(self.docs_dir)
                lines.append(f"- [{doc.stem}]({relative_path})\n")
            lines.append("\n")

        if root_docs:
            lines.append("## Additional Documentation\n\n")
            for doc in sorted(root_docs):
                lines.append(f"- [{doc.stem}]({doc.name})\n")
            lines.append("\n")

        return "".join(lines)

    def _generate_protocol_documentation(self, protocols: dict[str, t.Any]) -> str:
        lines = ["# Protocol Reference\n\n"]
        lines.append(
            "This document describes all protocol interfaces used in the codebase.\n\n"
        )

        for protocol_name, protocol_info in sorted(protocols.items()):
            lines.append(f"## {protocol_name}\n\n")

            description = protocol_info.get("docstring", {}).get(
                "description", "No description provided."
            )
            lines.append(f"{description}\n\n")

            if protocol_info.get("runtime_checkable"):
                lines.append("**Runtime Checkable:** Yes\n\n")

            methods = protocol_info.get("methods", [])
            if methods:
                lines.append("### Required Methods\n\n")
                for method in methods:
                    lines.append(f"#### `{method['name']}`\n\n")
                    method_desc = method.get("docstring", {}).get(
                        "description", "No description provided."
                    )
                    lines.append(f"{method_desc}\n\n")

                    params = method.get("parameters", [])
                    param_strings = []
                    for param in params:
                        param_type = param.get("annotation", "Any")
                        param_strings.append(f"{param['name']}: {param_type}")

                    return_type = method.get("return_annotation", "Any")
                    signature = f"def {method['name']}({', '.join(param_strings)}) -> {return_type}"
                    lines.append(f"```python\n{signature}\n```\n\n")

            lines.append("---\n\n")

        return "".join(lines)

    def _generate_service_documentation(self, services: dict[str, t.Any]) -> str:
        lines = ["# Service Reference\n\n"]
        lines.append(
            "This document describes all service implementations in the codebase.\n\n"
        )

        for service_name, service_info in sorted(services.items()):
            service_section = self._generate_service_section(service_name, service_info)
            lines.extend(service_section)

        return "".join(lines)

    def _generate_service_section(
        self, service_name: str, service_info: dict[str, t.Any]
    ) -> list[str]:
        lines: list[str] = []
        lines.extend(
            (
                f"## {service_name}\n\n",
                f"**Location:** `{service_info.get('path', 'Unknown')}`\n\n",
            )
        )

        if service_info.get("protocols_implemented"):
            protocol_lines = self._generate_protocols_implemented(
                service_info["protocols_implemented"]
            )
            lines.extend(protocol_lines)

        class_lines = self._generate_service_classes(service_info.get("classes", []))
        lines.extend(class_lines)

        return lines

    def _generate_protocols_implemented(self, protocols: list[str]) -> list[str]:
        lines = ["**Implements:**\n"]
        for protocol in protocols:
            lines.append(f"- {protocol}\n")
        lines.append("\n")
        return lines

    def _generate_service_classes(self, classes: list[dict[str, t.Any]]) -> list[str]:
        lines = []

        for class_info in classes:
            lines.append(f"### {class_info['name']}\n\n")
            description = class_info.get("docstring", {}).get(
                "description", "No description provided."
            )
            lines.append(f"{description}\n\n")

            public_method_lines = self._generate_public_methods(
                class_info.get("methods", [])
            )
            lines.extend(public_method_lines)

        return lines

    def _generate_public_methods(self, methods: list[dict[str, t.Any]]) -> list[str]:
        public_methods = [m for m in methods if m.get("visibility") == "public"]

        if not public_methods:
            return []

        lines = ["**Public Methods:**\n"]
        for method in public_methods:
            method_desc = method.get("docstring", {}).get("description", "")
            lines.append(f"- `{method['name']}`: {method_desc}\n")
        lines.append("\n")

        return lines

    def _generate_cli_documentation(self, commands: dict[str, t.Any]) -> str:
        lines = ["# CLI Reference\n\n"]
        lines.append(
            "This document describes all command-line options and usage patterns.\n\n"
        )

        for command_name, command_info in sorted(commands.items()):
            lines.append(f"## {command_name}\n\n")

            options = command_info.get("options", [])
            if options:
                lines.append("### Available Options\n\n")
                for option in options:
                    lines.append(
                        f"- `--{option['name']}` ({option['type']}): {option.get('description', 'No description')}\n"
                    )
                lines.append("\n")

        return "".join(lines)

    def _format_cross_references(self, cross_refs: dict[str, list[str]]) -> str:
        lines = ["# Cross References\n\n"]
        lines.append(
            "This document shows where API components are used throughout the codebase.\n\n"
        )

        for name, references in sorted(cross_refs.items()):
            if references:
                lines.extend((f"## {name}\n\n", "**Referenced in:**\n"))
                for ref in references:
                    lines.append(f"- {ref}\n")
                lines.append("\n")

        return "".join(lines)
