"""AI template engine for structured documentation generation.

This module provides intelligent template generation and processing for AI-optimized
documentation, including context-aware content generation and template inheritance.
"""

import json
import re
import typing as t
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from ..models.protocols import (
    ConfigManagerProtocol,
    LoggerProtocol,
)
from ..services.regex_patterns import SAFE_PATTERNS


class TemplateType(Enum):
    """Types of documentation templates."""

    AI_REFERENCE = "ai_reference"
    USER_GUIDE = "user_guide"
    API_REFERENCE = "api_reference"
    CHANGELOG = "changelog"
    README = "readme"
    TROUBLESHOOTING = "troubleshooting"
    QUICK_START = "quick_start"


@dataclass
class TemplateContext:
    """Context data for template rendering."""

    # Project metadata
    project_name: str
    project_description: str
    version: str
    author: str

    # Documentation metadata
    generated_at: datetime = field(default_factory=datetime.now)
    template_type: TemplateType | None = None

    # Dynamic content
    variables: dict[str, t.Any] = field(default_factory=dict[str, t.Any])
    sections: dict[str, str] = field(default_factory=dict[str, t.Any])

    # AI-specific context
    ai_optimization_level: str = "standard"  # minimal, standard, comprehensive
    target_audience: str = "developers"  # developers, users, maintainers

    def get_variable(self, key: str, default: t.Any = None) -> t.Any:
        """Get a template variable with default fallback."""
        return self.variables.get(key, default)

    def set_variable(self, key: str, value: t.Any) -> None:
        """Set a template variable."""
        self.variables[key] = value

    def get_section(self, name: str, default: str = "") -> str:
        """Get a template section with default fallback."""
        return self.sections.get(name, default)

    def set_section(self, name: str, content: str) -> None:
        """Set a template section."""
        self.sections[name] = content


@dataclass
class Template:
    """Represents a documentation template."""

    name: str
    content: str
    template_type: TemplateType
    variables: list[str] = field(default_factory=list)
    sections: list[str] = field(default_factory=list)
    parent_template: str | None = None
    ai_optimizations: dict[str, t.Any] = field(default_factory=dict[str, t.Any])

    def extract_placeholders(self) -> tuple[list[str], list[str]]:
        """Extract variable and section placeholders from template content.

        Returns:
            Tuple of (variables, sections) found in template
        """
        # Find {{variable}} patterns
        var_pattern = SAFE_PATTERNS[
            "extract_template_variables"
        ]._get_compiled_pattern()
        variables = var_pattern.findall(self.content)

        # Find {% section name %} patterns
        section_pattern = SAFE_PATTERNS[
            "extract_template_sections"
        ]._get_compiled_pattern()
        sections = section_pattern.findall(self.content)

        return list[t.Any](set[t.Any](variables)), list[t.Any](set[t.Any](sections))


class AITemplateEngine:
    """Engine for processing AI-optimized documentation templates."""

    def __init__(
        self,
        config_manager: ConfigManagerProtocol,
        logger: LoggerProtocol,
    ):
        self.config_manager = config_manager
        self.logger = logger
        self.templates: dict[str, Template] = {}
        self.template_cache: dict[str, str] = {}

        # Load built-in templates
        self._load_builtin_templates()

    def render_template(
        self,
        template_name: str,
        context: TemplateContext,
    ) -> str:
        """Render a template with the given context.

        Args:
            template_name: Name of template to render
            context: Template context with variables and sections

        Returns:
            Rendered template content
        """
        if template_name not in self.templates:
            raise ValueError(f"Template not found: {template_name}")

        template = self.templates[template_name]

        # Apply template inheritance if needed
        content = self._apply_inheritance(template, context)

        # Apply AI optimizations based on context
        content = self._apply_ai_optimizations(content, template, context)

        # Render variables
        content = self._render_variables(content, context)

        # Render sections
        content = self._render_sections(content, context)

        # Post-process content
        content = self._post_process_content(content, context)

        return content

    def register_template(self, template: Template) -> None:
        """Register a new template.

        Args:
            template: Template to register
        """
        # Extract placeholders
        variables, sections = template.extract_placeholders()
        template.variables = variables
        template.sections = sections

        self.templates[template.name] = template
        self.logger.debug(f"Registered template: {template.name}")

    def create_ai_reference_template(
        self,
        commands: dict[str, dict[str, t.Any]],
        decision_trees: list[dict[str, t.Any]],
        agent_capabilities: dict[str, dict[str, t.Any]],
    ) -> str:
        """Create AI-optimized reference template.

        Args:
            commands: Command definitions with metadata
            decision_trees: Decision tree structures
            agent_capabilities: Agent capability definitions

        Returns:
            AI reference template content
        """
        context = TemplateContext(
            project_name="{{project_name}}",
            project_description="{{project_description}}",
            version="{{version}}",
            author="{{author}}",
            template_type=TemplateType.AI_REFERENCE,
        )

        context.set_variable("commands", commands)
        context.set_variable("decision_trees", decision_trees)
        context.set_variable("agent_capabilities", agent_capabilities)

        return self.render_template("ai_reference_base", context)

    def create_user_guide_template(
        self,
        workflows: list[dict[str, t.Any]],
        examples: list[dict[str, str]],
        troubleshooting: dict[str, str],
    ) -> str:
        """Create user-friendly guide template.

        Args:
            workflows: Workflow definitions
            examples: Example code/commands
            troubleshooting: Common issues and solutions

        Returns:
            User guide template content
        """
        context = TemplateContext(
            project_name="{{project_name}}",
            project_description="{{project_description}}",
            version="{{version}}",
            author="{{author}}",
            template_type=TemplateType.USER_GUIDE,
            target_audience="users",
        )

        context.set_variable("workflows", workflows)
        context.set_variable("examples", examples)
        context.set_variable("troubleshooting", troubleshooting)

        return self.render_template("user_guide_base", context)

    def _load_builtin_templates(self) -> None:
        """Load built-in template definitions."""
        # AI Reference Base Template
        ai_ref_template = Template(
            name="ai_reference_base",
            template_type=TemplateType.AI_REFERENCE,
            content=self._get_ai_reference_template_content(),
            ai_optimizations={
                "structured_data": True,
                "decision_trees": True,
                "command_matrices": True,
                "pattern_matching": True,
            },
        )
        self.register_template(ai_ref_template)

        # User Guide Base Template
        user_guide_template = Template(
            name="user_guide_base",
            template_type=TemplateType.USER_GUIDE,
            content=self._get_user_guide_template_content(),
            ai_optimizations={
                "step_by_step": True,
                "visual_examples": True,
                "progressive_disclosure": True,
            },
        )
        self.register_template(user_guide_template)

        # README Template
        readme_template = Template(
            name="readme_base",
            template_type=TemplateType.README,
            content=self._get_readme_template_content(),
            ai_optimizations={
                "quick_start": True,
                "feature_highlights": True,
                "installation_matrix": True,
            },
        )
        self.register_template(readme_template)

        # Changelog Template
        changelog_template = Template(
            name="changelog_base",
            template_type=TemplateType.CHANGELOG,
            content=self._get_changelog_template_content(),
            ai_optimizations={
                "semantic_versioning": True,
                "categorized_changes": True,
                "migration_guides": True,
            },
        )
        self.register_template(changelog_template)

    def _apply_inheritance(self, template: Template, context: TemplateContext) -> str:
        """Apply template inheritance if parent template exists.

        Args:
            template: Template to process
            context: Template context

        Returns:
            Content with inheritance applied
        """
        if not template.parent_template:
            return template.content

        parent = self.templates.get(template.parent_template)
        if not parent:
            self.logger.warning(
                f"Parent template not found: {template.parent_template}"
            )
            return template.content

        # Simple block replacement inheritance
        parent_content = parent.content

        # Find blocks in child template
        block_pattern = SAFE_PATTERNS["extract_template_blocks"]._get_compiled_pattern()
        blocks = block_pattern.findall(template.content)

        # Replace blocks in parent content
        for block_name, block_content in blocks:
            # Create dynamic pattern for specific block replacement
            dynamic_pattern = SAFE_PATTERNS["replace_template_block"].pattern.replace(
                "BLOCK_NAME", block_name
            )
            parent_content = (
                re.sub(  # REGEX OK: safe dynamic pattern from SAFE_PATTERNS
                    dynamic_pattern,
                    block_content.strip(),
                    parent_content,
                    flags=re.DOTALL,
                )
            )

        return parent_content

    def _apply_ai_optimizations(
        self,
        content: str,
        template: Template,
        context: TemplateContext,
    ) -> str:
        """Apply AI-specific optimizations to content.

        Args:
            content: Template content
            template: Template definition
            context: Render context

        Returns:
            Optimized content
        """
        optimizations = template.ai_optimizations

        # Structured data optimization
        if optimizations.get("structured_data"):
            content = self._optimize_for_structured_data(content, context)

        # Decision tree optimization
        if optimizations.get("decision_trees"):
            content = self._optimize_for_decision_trees(content, context)

        # Command matrix optimization
        if optimizations.get("command_matrices"):
            content = self._optimize_for_command_matrices(content, context)

        # Step-by-step optimization
        if optimizations.get("step_by_step"):
            content = self._optimize_for_step_by_step(content, context)

        return content

    def _render_variables(self, content: str, context: TemplateContext) -> str:
        """Render template variables in content.

        Args:
            content: Content with variable placeholders
            context: Template context

        Returns:
            Content with variables rendered
        """
        # Render basic project variables
        replacements = {
            "project_name": context.project_name,
            "project_description": context.project_description,
            "version": context.version,
            "author": context.author,
            "generated_at": context.generated_at.strftime("%Y-%m-%d %H:%M:%S"),
        }

        # Add custom variables
        replacements.update(context.variables)

        # Replace variables
        for var_name, value in replacements.items():
            placeholder = f"{{{{{var_name}}}}}"
            # Check if value is a complex type (dict[str, t.Any] or list[t.Any]) that needs JSON serialization
            if isinstance(value, dict | list):
                # For complex data, use JSON representation
                value_str = json.dumps(value, indent=2)
            else:
                value_str = value

            content = content.replace(placeholder, value_str)

        return content

    def _render_sections(self, content: str, context: TemplateContext) -> str:
        """Render template sections in content.

        Args:
            content: Content with section placeholders
            context: Template context

        Returns:
            Content with sections rendered
        """
        # Find section placeholders
        section_pattern = SAFE_PATTERNS[
            "extract_template_sections"
        ]._get_compiled_pattern()

        def replace_section(match: t.Any) -> str:
            section_name = match.group(1)
            return context.get_section(
                section_name, f"<!-- Section {section_name} not found -->"
            )

        return section_pattern.sub(replace_section, content)

    def _post_process_content(self, content: str, context: TemplateContext) -> str:
        """Post-process rendered content for final cleanup.

        Args:
            content: Rendered content
            context: Template context

        Returns:
            Post-processed content
        """
        # Remove empty lines and normalize whitespace
        lines = content.split("\n")
        processed_lines = []

        for line in lines:
            # Remove trailing whitespace
            line = line.rstrip()
            processed_lines.append(line)

        # Join lines and normalize multiple blank lines
        content = "\n".join(processed_lines)
        content = SAFE_PATTERNS["normalize_multiple_newlines"].apply(content)

        return content.strip()

    def _optimize_for_structured_data(
        self, content: str, context: TemplateContext
    ) -> str:
        """Optimize content for structured data consumption by AI.

        Args:
            content: Content to optimize
            context: Template context

        Returns:
            AI-optimized content
        """
        # Add structured metadata at the beginning
        metadata = f"""<!-- AI-Optimized Documentation -->
<!-- Generated: {context.generated_at.isoformat()} -->
<!-- Target Audience: {context.target_audience} -->
<!-- Optimization Level: {context.ai_optimization_level} -->

"""
        return metadata + content

    def _optimize_for_decision_trees(
        self, content: str, context: TemplateContext
    ) -> str:
        """Optimize content for decision tree representation.

        Args:
            content: Content to optimize
            context: Template context

        Returns:
            Decision tree optimized content
        """
        # Add decision tree markers for AI parsing
        # This helps AI assistants identify decision points
        decision_markers = {
            "if": "🔄 **Decision Point**:",
            "when": "⚡ **Trigger Condition**:",
            "use": "✅ **Recommended Action**:",
            "avoid": "❌ **Avoid This**:",
        }

        for marker, prefix in decision_markers.items():
            # Create safe dynamic pattern for each decision marker
            pattern = rf"^(\s*)(.*{re.escape(marker)}.*)$"
            content = re.sub(  # REGEX OK: escaped marker pattern, safe dynamic
                pattern, rf"\1{prefix} \2", content, flags=re.MULTILINE | re.IGNORECASE
            )

        return content

    def _optimize_for_command_matrices(
        self, content: str, context: TemplateContext
    ) -> str:
        """Optimize content for command matrix representation.

        Args:
            content: Content to optimize
            context: Template context

        Returns:
            Command matrix optimized content
        """

        # Add command execution markers
        def enhance_command_block(match: t.Any) -> str:
            command = match.group(1).strip()
            return f"""```bash
# Command: {command.split()[0] if command.split() else "unknown"}
{command}
```"""

        command_pattern = SAFE_PATTERNS[
            "extract_bash_command_blocks"
        ]._get_compiled_pattern()
        return command_pattern.sub(enhance_command_block, content)

    def _optimize_for_step_by_step(self, content: str, context: TemplateContext) -> str:
        """Optimize content for step-by-step processing.

        Args:
            content: Content to optimize
            context: Template context

        Returns:
            Step-by-step optimized content
        """
        # Add step markers to numbered lists
        step_pattern = SAFE_PATTERNS["extract_step_numbers"]._get_compiled_pattern()

        def enhance_step(match: t.Any) -> str:
            indent, number, text = match.groups()
            return f"{indent}**Step {number}**: {text}"

        return step_pattern.sub(enhance_step, content)

    def _get_ai_reference_template_content(self) -> str:
        """Get AI reference template content."""
        return """# {{project_name}} AI Reference

**AI-Optimized Reference for {{project_name}} Architecture and Commands**

Generated: {{generated_at}}
Version: {{version}}

## Quick Command Matrix

### Primary Workflows

| Command | Use Case | AI Context | Success Pattern |
|---------|----------|-------------|--------------------|
{% section command_matrix %}

## AI Decision Trees

```mermaid
graph TD
{% section decision_trees %}
```

## Agent Selection Matrix

### By Issue Type

| Issue Pattern | Best Agent | Confidence | Command Pattern |
|---------------|------------|------------|--------------------|
{% section agent_matrix %}

## Error Pattern Library

### Common Patterns

{% section error_patterns %}

## Workflow Sequences

### Standard Development Cycle

{% section development_workflow %}

## Success Indicators

### Quality Check Success

{% section success_indicators %}

---

*This reference is AI-optimized for autonomous operation and quick decision making.*
"""

    def _get_user_guide_template_content(self) -> str:
        """Get user guide template content."""
        return """# {{project_name}} User Guide

Welcome to {{project_name}} - {{project_description}}

## Getting Started

### Installation

**Step 1**: Install {{project_name}}
```bash
pip install {{project_name}}
```

**Step 2**: Verify installation
```bash
{{project_name}} --version
```

### Quick Start

{% section quick_start %}

## Common Workflows

### Development Workflow

{% section development_workflow %}

### Release Workflow

{% section release_workflow %}

## Examples

{% section examples %}

## Troubleshooting

{% section troubleshooting %}

## Advanced Usage

{% section advanced_usage %}

---

For more information, see the [API Reference](api-reference.md) or visit our [GitHub repository]({{repo_url}}).
"""

    def _get_readme_template_content(self) -> str:
        """Get README template content."""
        return """# {{project_name}}

{{project_description}}

[![Version](https://img.shields.io/badge/version-{{version}}-blue.svg)]({{repo_url}})
[![Python](https://img.shields.io/badge/python-3.13+-blue.svg)](https://python.org)

## Features

{% section features %}

## Quick Start

```bash
# Install
pip install {{project_name}}

# Basic usage
{{project_name}} --help
```

## Installation

### Requirements

- Python 3.13+
- {{project_name}} dependencies

### Install from PyPI

```bash
pip install {{project_name}}
```

### Development Installation

```bash
git clone {{repo_url}}.git
cd {{project_name}}
pip install -e .
```

## Usage

{% section usage_examples %}

## Documentation

- [User Guide](docs/user-guide.md)
- [API Reference](docs/api-reference.md)
- [Development Guide](docs/development.md)

## Contributing

Contributions are welcome! Please read our [Contributing Guide](CONTRIBUTING.md) for details.

## License

{{license}}

## Author

{{author}}
"""

    def _get_changelog_template_content(self) -> str:
        """Get changelog template content."""
        return """# Changelog

All notable changes to {{project_name}} will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

{% section unreleased_changes %}

## [{{version}}] - {{generated_at}}

### Added
{% section added_features %}

### Changed
{% section changed_features %}

### Deprecated
{% section deprecated_features %}

### Removed
{% section removed_features %}

### Fixed
{% section fixed_issues %}

### Security
{% section security_updates %}

---

For a complete history, see [GitHub Releases]({{repo_url}}/releases).
"""
