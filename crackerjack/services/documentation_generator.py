"""Service for generating documentation from extracted API data."""

import typing as t
from pathlib import Path
from string import Template

from acb.console import Console
from acb.depends import Inject, depends

from ..models.protocols import DocumentationGeneratorProtocol


class MarkdownTemplateRenderer:
    """Simple template renderer for markdown documentation."""

    def __init__(self) -> None:
        self.built_in_templates = self._init_builtin_templates()

    def _init_builtin_templates(self) -> dict[str, Template]:
        """Initialize built-in template strings."""
        return {
            "api_reference": Template(self._get_api_reference_template()),
            "function_doc": Template(self._get_function_doc_template()),
            "class_doc": Template(self._get_class_doc_template()),
            "protocol_doc": Template(self._get_protocol_doc_template()),
            "module_doc": Template(self._get_module_doc_template()),
        }

    def render_template(self, template_name: str, context: dict[str, t.Any]) -> str:
        """Render a template with the given context."""
        if template_name in self.built_in_templates:
            template = self.built_in_templates[template_name]
            return template.safe_substitute(context)

        # Try to load external template file
        template_path = Path(f"templates/{template_name}")
        if template_path.exists():
            content = template_path.read_text(encoding="utf-8")
            template = Template(content)
            return template.safe_substitute(context)

        raise ValueError(f"Template '{template_name}' not found")

    def _get_api_reference_template(self) -> str:
        """Get the API reference template."""
        return """# API Reference

## Overview
$overview

## Protocols
$protocols_section

## Services
$services_section

## Managers
$managers_section

## Generated on: $timestamp
"""

    def _get_function_doc_template(self) -> str:
        """Get the function documentation template."""
        return """### $name

$description

**Parameters:**
$parameters

**Returns:** $returns

**Example:**
```python
$example
```

"""

    def _get_class_doc_template(self) -> str:
        """Get the class documentation template."""
        return """## $name

$description

**Base Classes:** $base_classes

### Methods

$methods

"""

    def _get_protocol_doc_template(self) -> str:
        """Get the protocol documentation template."""
        return """## $name (Protocol)

$description

**Runtime Checkable:** $runtime_checkable

### Required Methods

$methods

"""

    def _get_module_doc_template(self) -> str:
        """Get the module documentation template."""
        return """# $module_name

$description

## Classes

$classes

## Functions

$functions

"""


class DocumentationGeneratorImpl(DocumentationGeneratorProtocol):
    """Implementation of documentation generation from extracted API data."""

    @depends.inject
    def __init__(self, console: Inject[Console]) -> None:
        self.console = console
        self.renderer = MarkdownTemplateRenderer()

    def generate_api_reference(self, api_data: dict[str, t.Any]) -> str:
        """Generate complete API reference documentation."""
        overview = self._generate_overview(api_data)
        protocols_section = self._generate_protocols_section(
            api_data.get("protocols", {})
        )
        services_section = self._generate_services_section(api_data.get("services", {}))
        managers_section = self._generate_managers_section(api_data.get("managers", {}))

        from datetime import datetime

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        context = {
            "overview": overview,
            "protocols_section": protocols_section,
            "services_section": services_section,
            "managers_section": managers_section,
            "timestamp": timestamp,
        }

        return self.renderer.render_template("api_reference", context)

    def generate_user_guide(self, template_context: dict[str, t.Any]) -> str:
        """Generate user guide documentation."""
        sections: list[str] = []

        # Generate getting started section
        if "installation" in template_context:
            sections.extend(
                ("## Getting Started\n", template_context["installation"], "\n")
            )

        # Generate usage examples
        if "examples" in template_context:
            sections.append("## Usage Examples\n")
            for example in template_context["examples"]:
                sections.extend(
                    (
                        f"### {example.get('title', 'Example')}\n",
                        f"{example.get('description', '')}\n",
                    )
                )
                if "code" in example:
                    sections.append(f"```bash\n{example['code']}\n```\n")
                sections.append("\n")

        # Generate configuration section
        if "configuration" in template_context:
            sections.extend(
                ("## Configuration\n", template_context["configuration"], "\n")
            )

        return "".join(sections)

    def generate_changelog_update(self, version: str, changes: dict[str, t.Any]) -> str:
        """Generate changelog entry for a version."""
        from datetime import datetime

        today = datetime.now().strftime("%Y-%m-%d")

        lines = [f"## [{version}] - {today}\n"]

        # Order sections by importance
        section_order = [
            ("Added", "added"),
            ("Changed", "changed"),
            ("Fixed", "fixed"),
            ("Removed", "removed"),
            ("Security", "security"),
            ("Deprecated", "deprecated"),
        ]

        for section_title, section_key in section_order:
            if section_key in changes and changes[section_key]:
                lines.append(f"### {section_title}\n")
                for change in changes[section_key]:
                    lines.append(f"- {change}\n")
                lines.append("\n")

        return "".join(lines)

    def render_template(self, template_path: Path, context: dict[str, t.Any]) -> str:
        """Render a template file with the given context."""
        if not template_path.exists():
            raise FileNotFoundError(f"Template not found: {template_path}")

        content = template_path.read_text(encoding="utf-8")
        template = Template(content)
        return template.safe_substitute(context)

    def generate_cross_references(
        self, api_data: dict[str, t.Any]
    ) -> dict[str, list[str]]:
        """Generate cross-reference mappings for API components."""
        cross_refs = {}

        # Extract all API names
        all_names = set()

        # Add protocol names
        protocols = api_data.get("protocols", {})
        all_names.update(protocols.keys())

        # Add class names from modules
        modules = api_data.get("modules", {})
        for module_data in modules.values():
            all_names.update(
                class_info["name"] for class_info in module_data.get("classes", [])
            )
            all_names.update(
                func_info["name"] for func_info in module_data.get("functions", [])
            )

        # Generate cross-references by finding mentions
        for name in all_names:
            refs = self._find_references_to_name(name, api_data)
            if refs:
                cross_refs[name] = refs

        return cross_refs

    def _generate_overview(self, api_data: dict[str, t.Any]) -> str:
        """Generate overview section for API documentation."""
        stats = self._calculate_api_stats(api_data)

        overview_lines = [
            "This document provides comprehensive API reference for all protocols, services, and managers in the codebase.\n",
            f"**Total Protocols:** {stats['protocols']}\n",
            f"**Total Classes:** {stats['classes']}\n",
            f"**Total Functions:** {stats['functions']}\n",
            f"**Total Modules:** {stats['modules']}\n",
        ]

        return "".join(overview_lines)

    def _generate_protocols_section(self, protocols: dict[str, t.Any]) -> str:
        """Generate the protocols section of API documentation."""
        if not protocols:
            return "No protocols found.\n"

        sections = []
        for protocol_name, protocol_info in protocols.items():
            context = {
                "name": protocol_name,
                "description": protocol_info.get("docstring", {}).get(
                    "description", "No description provided."
                ),
                "runtime_checkable": "Yes"
                if protocol_info.get("runtime_checkable", False)
                else "No",
                "methods": self._format_methods(protocol_info.get("methods", [])),
            }
            sections.append(self.renderer.render_template("protocol_doc", context))

        return "".join(sections)

    def _generate_services_section(self, services: dict[str, t.Any]) -> str:
        """Generate the services section of API documentation."""
        if not services:
            return "No services found.\n"

        sections: list[str] = []
        for service_name, service_info in services.items():
            sections.extend(
                (
                    f"## {service_name}\n",
                    f"**Path:** `{service_info.get('path', 'Unknown')}`\n\n",
                )
            )

            if service_info.get("protocols_implemented"):
                sections.append("**Implements Protocols:**\n")
                for protocol in service_info["protocols_implemented"]:
                    sections.append(f"- {protocol}\n")
                sections.append("\n")

            # Add classes from this service
            for class_info in service_info.get("classes", []):
                context = {
                    "name": class_info["name"],
                    "description": class_info.get("docstring", {}).get(
                        "description", "No description provided."
                    ),
                    "base_classes": ", ".join(class_info.get("base_classes", []))
                    or "None",
                    "methods": self._format_methods(class_info.get("methods", [])),
                }
                sections.append(self.renderer.render_template("class_doc", context))

        return "".join(sections)

    def _generate_managers_section(self, managers: dict[str, t.Any]) -> str:
        """Generate the managers section of API documentation."""
        # Similar to services but focused on manager-specific functionality
        return self._generate_services_section(managers)  # Reuse services logic for now

    def _format_methods(self, methods: list[dict[str, t.Any]]) -> str:
        """Format method information for documentation."""
        if not methods:
            return "No methods defined.\n"

        formatted_methods = []
        for method in methods:
            method_lines = [f"#### `{method['name']}`\n"]

            # Add description
            description = method.get("docstring", {}).get(
                "description", "No description provided."
            )
            method_lines.append(f"{description}\n")

            # Add parameters
            parameters = method.get("parameters", [])
            if parameters:
                method_lines.append("**Parameters:**\n")
                for param in parameters:
                    param_type = param.get("annotation", "Any")
                    param_desc = param.get("description", "No description")
                    method_lines.append(
                        f"- `{param['name']}` ({param_type}): {param_desc}\n"
                    )

            # Add return type
            return_annotation = method.get("return_annotation", "")
            if return_annotation:
                method_lines.append(f"**Returns:** {return_annotation}\n")

            method_lines.append("\n")
            formatted_methods.append("".join(method_lines))

        return "".join(formatted_methods)

    def _calculate_api_stats(self, api_data: dict[str, t.Any]) -> dict[str, int]:
        """Calculate statistics about the API data."""
        stats = {"protocols": 0, "classes": 0, "functions": 0, "modules": 0}

        # Count protocols
        protocols = api_data.get("protocols", {})
        stats["protocols"] = len(protocols)

        # Count modules, classes, and functions
        modules = api_data.get("modules", {})
        stats["modules"] = len(modules)

        for module_data in modules.values():
            stats["classes"] += len(module_data.get("classes", []))
            stats["functions"] += len(module_data.get("functions", []))

        return stats

    def _find_references_to_name(
        self, name: str, api_data: dict[str, t.Any]
    ) -> list[str]:
        """Find all places where an API component is referenced."""
        references = []

        # Search in protocols
        protocol_refs = self._find_protocol_references(
            name, api_data.get("protocols", {})
        )
        references.extend(protocol_refs)

        # Search in modules/classes
        module_refs = self._find_module_references(name, api_data.get("modules", {}))
        references.extend(module_refs)

        return references

    def _find_protocol_references(
        self, name: str, protocols: dict[str, t.Any]
    ) -> list[str]:
        """Find references in protocol definitions."""
        references = []

        for protocol_name, protocol_info in protocols.items():
            method_refs = self._find_protocol_method_references(
                name, protocol_name, protocol_info.get("methods", [])
            )
            references.extend(method_refs)

        return references

    def _find_protocol_method_references(
        self, name: str, protocol_name: str, methods: list[dict[str, t.Any]]
    ) -> list[str]:
        """Find references in protocol method signatures."""
        references = []

        for method in methods:
            # Check parameters
            param_refs = self._find_method_parameter_references(
                name,
                f"{protocol_name}.{method['name']}()",
                method.get("parameters", []),
            )
            references.extend(param_refs)

            # Check return type
            if name in method.get("return_annotation", ""):
                references.append(f"{protocol_name}.{method['name']}() return type")

        return references

    def _find_module_references(
        self, name: str, modules: dict[str, t.Any]
    ) -> list[str]:
        """Find references in module class definitions."""
        references = []

        for module_data in modules.values():
            class_refs = self._find_class_references(
                name, module_data.get("classes", [])
            )
            references.extend(class_refs)

        return references

    def _find_class_references(
        self, name: str, classes: list[dict[str, t.Any]]
    ) -> list[str]:
        """Find references in class definitions."""
        references = []

        for class_info in classes:
            # Check base classes
            if name in class_info.get("base_classes", []):
                references.append(f"{class_info['name']} base class")

            # Check method signatures
            method_refs = self._find_class_method_references(
                name, class_info["name"], class_info.get("methods", [])
            )
            references.extend(method_refs)

        return references

    def _find_class_method_references(
        self, name: str, class_name: str, methods: list[dict[str, t.Any]]
    ) -> list[str]:
        """Find references in class method signatures."""
        references = []

        for method in methods:
            param_refs = self._find_method_parameter_references(
                name, f"{class_name}.{method['name']}()", method.get("parameters", [])
            )
            references.extend(param_refs)

        return references

    def _find_method_parameter_references(
        self, name: str, method_name: str, parameters: list[dict[str, t.Any]]
    ) -> list[str]:
        """Find references in method parameters."""
        return [
            f"{method_name} parameter"
            for param in parameters
            if name in param.get("annotation", "")
        ]
