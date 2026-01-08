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
    AI_REFERENCE = "ai_reference"
    USER_GUIDE = "user_guide"
    API_REFERENCE = "api_reference"
    CHANGELOG = "changelog"
    README = "readme"
    TROUBLESHOOTING = "troubleshooting"
    QUICK_START = "quick_start"


@dataclass
class TemplateContext:
    project_name: str
    project_description: str
    version: str
    author: str

    generated_at: datetime = field(default_factory=datetime.now)
    template_type: TemplateType | None = None

    variables: dict[str, t.Any] = field(default_factory=dict[str, t.Any])
    sections: dict[str, str] = field(default_factory=dict[str, t.Any])

    ai_optimization_level: str = "standard"
    target_audience: str = "developers"

    def get_variable(self, key: str, default: t.Any = None) -> t.Any:
        return self.variables.get(key, default)

    def set_variable(self, key: str, value: t.Any) -> None:
        self.variables[key] = value

    def get_section(self, name: str, default: str = "") -> str:
        return self.sections.get(name, default)

    def set_section(self, name: str, content: str) -> None:
        self.sections[name] = content


@dataclass
class Template:
    name: str
    content: str
    template_type: TemplateType
    variables: list[str] = field(default_factory=list)
    sections: list[str] = field(default_factory=list)
    parent_template: str | None = None
    ai_optimizations: dict[str, t.Any] = field(default_factory=dict[str, t.Any])

    def extract_placeholders(self) -> tuple[list[str], list[str]]:
        var_pattern = SAFE_PATTERNS[
            "extract_template_variables"
        ]._get_compiled_pattern()
        variables = var_pattern.findall(self.content)

        section_pattern = SAFE_PATTERNS[
            "extract_template_sections"
        ]._get_compiled_pattern()
        sections = section_pattern.findall(self.content)

        return list[t.Any](set[t.Any](variables)), list[t.Any](set[t.Any](sections))


class AITemplateEngine:
    def __init__(
        self,
        config_manager: ConfigManagerProtocol,
        logger: LoggerProtocol,
    ):
        self.config_manager = config_manager
        self.logger = logger
        self.templates: dict[str, Template] = {}
        self.template_cache: dict[str, str] = {}

        self._load_builtin_templates()

    def render_template(
        self,
        template_name: str,
        context: TemplateContext,
    ) -> str:
        if template_name not in self.templates:
            raise ValueError(f"Template not found: {template_name}")

        template = self.templates[template_name]

        content = self._apply_inheritance(template, context)

        content = self._apply_ai_optimizations(content, template, context)

        content = self._render_variables(content, context)

        content = self._render_sections(content, context)

        content = self._post_process_content(content, context)

        return content

    def register_template(self, template: Template) -> None:
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
        if not template.parent_template:
            return template.content

        parent = self.templates.get(template.parent_template)
        if not parent:
            self.logger.warning(
                f"Parent template not found: {template.parent_template}"
            )
            return template.content

        parent_content = parent.content

        block_pattern = SAFE_PATTERNS["extract_template_blocks"]._get_compiled_pattern()
        blocks = block_pattern.findall(template.content)

        for block_name, block_content in blocks:
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
        optimizations = template.ai_optimizations

        if optimizations.get("structured_data"):
            content = self._optimize_for_structured_data(content, context)

        if optimizations.get("decision_trees"):
            content = self._optimize_for_decision_trees(content, context)

        if optimizations.get("command_matrices"):
            content = self._optimize_for_command_matrices(content, context)

        if optimizations.get("step_by_step"):
            content = self._optimize_for_step_by_step(content, context)

        return content

    def _render_variables(self, content: str, context: TemplateContext) -> str:
        replacements = {
            "project_name": context.project_name,
            "project_description": context.project_description,
            "version": context.version,
            "author": context.author,
            "generated_at": context.generated_at.strftime("%Y-%m-%d %H:%M:%S"),
        }

        replacements.update(context.variables)

        for var_name, value in replacements.items():
            placeholder = f"{{{{{var_name}}}}}"

            if isinstance(value, dict | list):
                value_str = json.dumps(value, indent=2)
            else:
                value_str = value

            content = content.replace(placeholder, value_str)

        return content

    def _render_sections(self, content: str, context: TemplateContext) -> str:
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
        lines = content.split("\n")
        processed_lines = []

        for line in lines:
            line = line.rstrip()
            processed_lines.append(line)

        content = "\n".join(processed_lines)
        content = SAFE_PATTERNS["normalize_multiple_newlines"].apply(content)

        return content.strip()

    def _optimize_for_structured_data(
        self, content: str, context: TemplateContext
    ) -> str:
        metadata = f"""<!-- AI-Optimized Documentation -->
<!-- Generated: {context.generated_at.isoformat()} -->
<!-- Target Audience: {context.target_audience} -->
<!-- Optimization Level: {context.ai_optimization_level} -->

"""
        return metadata + content

    def _optimize_for_decision_trees(
        self, content: str, context: TemplateContext
    ) -> str:
        decision_markers = {
            "if": "🔄 **Decision Point**:",
            "when": "⚡ **Trigger Condition**:",
            "use": "✅ **Recommended Action**:",
            "avoid": "❌ **Avoid This**:",
        }

        for marker, prefix in decision_markers.items():
            pattern = rf"^(\s*)(.*{re.escape(marker)}.*)$"
            content = re.sub(  # REGEX OK: escaped marker pattern, safe dynamic
                pattern, rf"\1{prefix} \2", content, flags=re.MULTILINE | re.IGNORECASE
            )

        return content

    def _optimize_for_command_matrices(
        self, content: str, context: TemplateContext
    ) -> str:
        def enhance_command_block(match: t.Any) -> str:
            command = match.group(1).strip()
            return f"""```bash

{command}
```"""

        command_pattern = SAFE_PATTERNS[
            "extract_bash_command_blocks"
        ]._get_compiled_pattern()
        return command_pattern.sub(enhance_command_block, content)

    def _optimize_for_step_by_step(self, content: str, context: TemplateContext) -> str:
        step_pattern = SAFE_PATTERNS["extract_step_numbers"]._get_compiled_pattern()

        def enhance_step(match: t.Any) -> str:
            indent, number, text = match.groups()
            return f"{indent}**Step {number}**: {text}"

        return step_pattern.sub(enhance_step, content)

    def _get_ai_reference_template_content(self) -> str:
        return """# {{project_name}} AI Reference

**AI-Optimized Reference for {{project_name}} Architecture and Commands**

Generated: {{generated_at}}
Version: {{version}}


| Command | Use Case | AI Context | Success Pattern |
|---------|----------|-------------|--------------------|
{% section command_matrix %}


```mermaid
graph TD
{% section decision_trees %}
```


| Issue Pattern | Best Agent | Confidence | Command Pattern |
|---------------|------------|------------|--------------------|
{% section agent_matrix %}


{% section error_patterns %}


{% section development_workflow %}


{% section success_indicators %}

---

*This reference is AI-optimized for autonomous operation and quick decision making.*
"""

    def _get_user_guide_template_content(self) -> str:
        return """# {{project_name}} User Guide

Welcome to {{project_name}} - {{project_description}}


**Step 1**: Install {{project_name}}
```bash
pip install {{project_name}}
```

**Step 2**: Verify installation
```bash
{{project_name}} --version
```


{% section quick_start %}


{% section development_workflow %}


{% section release_workflow %}


{% section examples %}


{% section troubleshooting %}


{% section advanced_usage %}

---

For more information, see the [API Reference](api-reference.md) or visit our [GitHub repository]({{repo_url}}).
"""

    def _get_readme_template_content(self) -> str:
        return """# {{project_name}}

{{project_description}}

[![Version](https://img.shields.io/badge/version-{{version}}-blue.svg)]({{repo_url}})
[![Python](https://img.shields.io/badge/python-3.13+-blue.svg)](https://python.org)


{% section features %}


```bash

pip install {{project_name}}


{{project_name}} --help
```


- Python 3.13+
- {{project_name}} dependencies


```bash
pip install {{project_name}}
```


```bash
git clone {{repo_url}}.git
cd {{project_name}}
pip install -e .
```


{% section usage_examples %}


- [User Guide](docs/user-guide.md)
- [API Reference](docs/api-reference.md)
- [Development Guide](docs/development.md)


Contributions are welcome! Please read our [Contributing Guide](CONTRIBUTING.md) for details.


{{license}}


{{author}}
"""

    def _get_changelog_template_content(self) -> str:
        return """# Changelog

All notable changes to {{project_name}} will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).


{% section unreleased_changes %}


{% section added_features %}


{% section changed_features %}


{% section deprecated_features %}


{% section removed_features %}


{% section fixed_issues %}


{% section security_updates %}

---

For a complete history, see [GitHub Releases]({{repo_url}}/releases).
"""
