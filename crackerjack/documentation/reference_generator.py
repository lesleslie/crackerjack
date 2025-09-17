"""Reference generator for comprehensive command documentation.

This module provides automatic generation of command reference documentation
from CLI definitions, including usage examples, parameter descriptions, and
workflow integration guides.
"""

import ast
import typing as t
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path

from ..models.protocols import (
    ConfigManagerProtocol,
    LoggerProtocol,
)


class ReferenceFormat(Enum):
    """Formats for reference documentation."""

    MARKDOWN = "markdown"
    HTML = "html"
    JSON = "json"
    YAML = "yaml"
    RST = "rst"


@dataclass
class ParameterInfo:
    """Information about a command parameter."""

    name: str
    type_hint: str
    default_value: t.Any
    description: str
    required: bool = False
    choices: list[str] | None = None
    example: str | None = None
    deprecated: bool = False
    added_in_version: str | None = None


@dataclass
class CommandInfo:
    """Information about a CLI command."""

    name: str
    description: str
    category: str
    parameters: list[ParameterInfo] = field(default_factory=list)
    examples: list[dict[str, str]] = field(default_factory=list)
    related_commands: list[str] = field(default_factory=list)
    aliases: list[str] = field(default_factory=list)
    deprecated: bool = False
    added_in_version: str | None = None

    # Workflow integration
    common_workflows: list[str] = field(default_factory=list)
    prerequisites: list[str] = field(default_factory=list)
    side_effects: list[str] = field(default_factory=list)

    # AI optimization
    ai_context: dict[str, t.Any] = field(default_factory=dict[str, t.Any])
    success_patterns: list[str] = field(default_factory=list)
    failure_patterns: list[str] = field(default_factory=list)


@dataclass
class CommandReference:
    """Complete command reference documentation."""

    commands: dict[str, CommandInfo]
    categories: dict[str, list[str]]
    workflows: dict[str, list[str]]
    generated_at: datetime = field(default_factory=datetime.now)
    version: str = "unknown"

    def get_commands_by_category(self, category: str) -> list[CommandInfo]:
        """Get all commands in a specific category.

        Args:
            category: Category name

        Returns:
            List of commands in category
        """
        return [cmd for cmd in self.commands.values() if cmd.category == category]

    def get_command_by_name(self, name: str) -> CommandInfo | None:
        """Get command by name or alias.

        Args:
            name: Command name or alias

        Returns:
            Command info if found, None otherwise
        """
        # Direct name match
        if name in self.commands:
            return self.commands[name]

        # Alias match
        for cmd in self.commands.values():
            if name in cmd.aliases:
                return cmd

        return None


class ReferenceGenerator:
    """Generator for comprehensive command reference documentation."""

    def __init__(
        self,
        config_manager: ConfigManagerProtocol,
        logger: LoggerProtocol,
    ):
        self.config_manager = config_manager
        self.logger = logger

    async def generate_reference(
        self,
        cli_module_path: str,
        output_format: ReferenceFormat = ReferenceFormat.MARKDOWN,
        include_examples: bool = True,
        include_workflows: bool = True,
    ) -> CommandReference:
        """Generate command reference from CLI module.

        Args:
            cli_module_path: Path to CLI module to analyze
            output_format: Output format for documentation
            include_examples: Whether to include usage examples
            include_workflows: Whether to include workflow information

        Returns:
            Generated command reference
        """
        self.logger.info(f"Generating command reference from: {cli_module_path}")

        # Analyze CLI module
        commands = await self._analyze_cli_module(cli_module_path)

        # Enhance with examples if requested
        if include_examples:
            commands = await self._enhance_with_examples(commands)

        # Enhance with workflows if requested
        if include_workflows:
            commands = await self._enhance_with_workflows(commands)

        # Categorize commands
        categories = self._categorize_commands(commands)

        # Generate workflows
        workflows = self._generate_workflows(commands) if include_workflows else {}

        reference = CommandReference(
            commands=commands,
            categories=categories,
            workflows=workflows,
        )

        self.logger.info(f"Generated reference for {len(commands)} commands")
        return reference

    async def render_reference(
        self,
        reference: CommandReference,
        output_format: ReferenceFormat,
        template_name: str | None = None,
    ) -> str:
        """Render command reference to specified format.

        Args:
            reference: Command reference to render
            output_format: Output format
            template_name: Optional template name to use

        Returns:
            Rendered reference documentation
        """
        if output_format == ReferenceFormat.MARKDOWN:
            return self._render_markdown(reference)
        elif output_format == ReferenceFormat.HTML:
            return self._render_html(reference)
        elif output_format == ReferenceFormat.JSON:
            return self._render_json(reference)
        elif output_format == ReferenceFormat.YAML:
            return self._render_yaml(reference)
        elif output_format == ReferenceFormat.RST:
            return self._render_rst(reference)
        else:
            raise ValueError(f"Unsupported format: {output_format}")

    async def _analyze_cli_module(self, module_path: str) -> dict[str, CommandInfo]:
        """Analyze CLI module to extract command information.

        Args:
            module_path: Path to CLI module

        Returns:
            Dictionary of command name to CommandInfo
        """
        commands = {}

        try:
            # Read and parse the module
            module_file = Path(module_path)
            if not module_file.exists():
                raise FileNotFoundError(f"CLI module not found: {module_path}")

            source_code = module_file.read_text()

            # Parse AST
            tree = ast.parse(source_code)

            # Extract command information
            commands = self._extract_commands_from_ast(tree)

        except Exception as e:
            self.logger.error(f"Failed to analyze CLI module: {e}")

        return commands

    def _extract_commands_from_ast(self, tree: ast.AST) -> dict[str, CommandInfo]:
        """Extract command information from AST.

        Args:
            tree: Parsed AST

        Returns:
            Dictionary of commands
        """
        commands: dict[str, CommandInfo] = {}
        visitor = self._create_command_visitor(commands)
        visitor.visit(tree)
        return commands

    def _create_command_visitor(
        self, commands: dict[str, CommandInfo]
    ) -> ast.NodeVisitor:
        """Create AST visitor for command extraction.

        Args:
            commands: Dictionary to populate with commands

        Returns:
            Configured AST visitor
        """

        class CommandVisitor(ast.NodeVisitor):
            def __init__(self, generator: t.Any) -> None:
                self.generator = generator

            def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
                self.generator._process_function_node(node, commands)
                self.generic_visit(node)

        return CommandVisitor(self)

    def _process_function_node(
        self, node: ast.FunctionDef, commands: dict[str, CommandInfo]
    ) -> None:
        """Process function node for command extraction.

        Args:
            node: Function definition node
            commands: Commands dictionary to update
        """
        for decorator in node.decorator_list:
            if self._is_command_decorator(decorator):
                command_info = self._extract_command_from_function(node)
                if command_info:
                    commands[command_info.name] = command_info

    def _is_command_decorator(self, decorator: ast.AST) -> bool:
        """Check if decorator indicates a CLI command.

        Args:
            decorator: AST decorator node

        Returns:
            True if command decorator
        """
        if isinstance(decorator, ast.Name):
            return decorator.id in ("command", "click_command")
        elif isinstance(decorator, ast.Attribute):
            return decorator.attr in ("command", "callback")
        return False

    def _extract_command_from_function(
        self, node: ast.FunctionDef
    ) -> CommandInfo | None:
        """Extract command info from function definition.

        Args:
            node: Function definition node

        Returns:
            Command info or None if extraction fails
        """
        try:
            command_name = node.name.replace("_", "-")
            description = self._extract_docstring(node)
            parameters = self._extract_function_parameters(node)

            return CommandInfo(
                name=command_name,
                description=description or f"Execute {command_name}",
                category="general",
                parameters=parameters,
            )

        except Exception as e:
            self.logger.warning(f"Failed to extract command {node.name}: {e}")
            return None

    def _extract_function_parameters(
        self, node: ast.FunctionDef
    ) -> list[ParameterInfo]:
        """Extract parameter information from function.

        Args:
            node: Function definition node

        Returns:
            List of parameter information
        """
        parameters = []
        for arg in node.args.args:
            if arg.arg != "self":
                param_info = self._extract_parameter_info(arg, node)
                parameters.append(param_info)
        return parameters

    def _extract_docstring(self, node: ast.FunctionDef) -> str | None:
        """Extract docstring from function.

        Args:
            node: Function definition node

        Returns:
            Docstring or None
        """
        if (
            node.body
            and isinstance(node.body[0], ast.Expr)
            and isinstance(node.body[0].value, ast.Constant)
            and isinstance(node.body[0].value.value, str)
        ):
            return node.body[0].value.value.strip()
        return None

    def _extract_parameter_info(
        self, arg: ast.arg, func_node: ast.FunctionDef
    ) -> ParameterInfo:
        """Extract parameter information.

        Args:
            arg: Function argument node
            func_node: Parent function node

        Returns:
            Parameter information
        """
        param_name = arg.arg.replace("_", "-")
        type_hint = ast.unparse(arg.annotation) if arg.annotation else "Any"
        default_value, required = self._extract_default_value(arg, func_node)

        return ParameterInfo(
            name=param_name,
            type_hint=type_hint,
            default_value=default_value,
            description=f"Parameter: {param_name}",
            required=required,
        )

    def _extract_default_value(
        self, arg: ast.arg, func_node: ast.FunctionDef
    ) -> tuple[t.Any, bool]:
        """Extract default value and required status for parameter.

        Args:
            arg: Function argument node
            func_node: Parent function node

        Returns:
            Tuple of (default_value, required)
        """
        defaults_count = len(func_node.args.defaults)
        args_count = len(func_node.args.args)
        defaults_start = args_count - defaults_count

        arg_index = func_node.args.args.index(arg)
        if arg_index >= defaults_start:
            return self._extract_argument_default(arg_index, defaults_start, func_node)

        return None, True

    def _extract_argument_default(
        self, arg_index: int, defaults_start: int, func_node: ast.FunctionDef
    ) -> tuple[t.Any, bool]:
        """Extract default value for a specific argument.

        Args:
            arg_index: Index of the argument
            defaults_start: Index where defaults start
            func_node: Parent function node

        Returns:
            Tuple of (default_value, required)
        """
        default_index = arg_index - defaults_start
        default_node = func_node.args.defaults[default_index]
        if isinstance(default_node, ast.Constant):
            return default_node.value, False
        return None, True

    async def _enhance_with_examples(
        self, commands: dict[str, CommandInfo]
    ) -> dict[str, CommandInfo]:
        """Enhance commands with usage examples.

        Args:
            commands: Commands to enhance

        Returns:
            Enhanced commands with examples
        """
        for command in commands.values():
            self._add_basic_example(command)
            self._add_parameter_examples(command)
        return commands

    def _add_basic_example(self, command: CommandInfo) -> None:
        """Add a basic example for a command."""
        basic_example = f"python -m crackerjack --{command.name}"
        command.examples.append(
            {
                "description": f"Basic {command.name} usage",
                "command": basic_example,
            }
        )

    def _add_parameter_examples(self, command: CommandInfo) -> None:
        """Add parameter examples for a command."""
        # Generate basic examples
        basic_example = f"python -m crackerjack --{command.name}"

        # Add parameter examples
        param_examples = []
        for param in command.parameters:
            if not param.required and param.default_value is not None:
                param_example = self._format_parameter_example(param)
                if param_example:
                    param_examples.append(param_example)

        if param_examples:
            enhanced_example = f"{basic_example} {' '.join(param_examples)}"
            command.examples.append(
                {
                    "description": f"Using {command.name} with parameters",
                    "command": enhanced_example,
                }
            )

    def _format_parameter_example(self, param: ParameterInfo) -> str | None:
        """Format a parameter example."""
        if isinstance(param.default_value, bool):
            return f"--{param.name}"
        return f"--{param.name} {param.default_value}"

    async def _enhance_with_workflows(
        self, commands: dict[str, CommandInfo]
    ) -> dict[str, CommandInfo]:
        """Enhance commands with workflow information.

        Args:
            commands: Commands to enhance

        Returns:
            Enhanced commands with workflow info
        """
        workflow_patterns = self._get_workflow_patterns()

        for command in commands.values():
            self._assign_command_workflows(command, workflow_patterns)
            self._add_ai_context_to_command(command)

        return commands

    def _get_workflow_patterns(self) -> dict[str, list[str]]:
        """Get workflow patterns for command categorization.

        Returns:
            Dictionary mapping workflow names to pattern lists
        """
        return {
            "development": ["test", "format", "lint", "type-check"],
            "release": ["version", "build", "publish", "tag"],
            "maintenance": ["clean", "update", "optimize", "backup"],
            "monitoring": ["status", "health", "metrics", "logs"],
        }

    def _assign_command_workflows(
        self, command: CommandInfo, workflow_patterns: dict[str, list[str]]
    ) -> None:
        """Assign workflows to a command based on name patterns.

        Args:
            command: Command to assign workflows to
            workflow_patterns: Workflow patterns to match against
        """
        for workflow, patterns in workflow_patterns.items():
            if any(pattern in command.name for pattern in patterns):
                command.common_workflows.append(workflow)

    def _add_ai_context_to_command(self, command: CommandInfo) -> None:
        """Add AI context to a command based on its purpose.

        Args:
            command: Command to enhance with AI context
        """
        if "test" in command.name:
            self._add_test_ai_context(command)
        elif "format" in command.name or "lint" in command.name:
            self._add_quality_ai_context(command)

    def _add_test_ai_context(self, command: CommandInfo) -> None:
        """Add AI context for test-related commands."""
        command.ai_context.update(
            {
                "purpose": "quality_assurance",
                "automation_level": "high",
                "ai_agent_compatible": True,
            }
        )
        command.success_patterns.append("All tests passed")
        command.failure_patterns.append("Test failures detected")

    def _add_quality_ai_context(self, command: CommandInfo) -> None:
        """Add AI context for code quality commands."""
        command.ai_context.update(
            {
                "purpose": "code_quality",
                "automation_level": "high",
                "ai_agent_compatible": True,
            }
        )
        command.success_patterns.append("No formatting issues")
        command.failure_patterns.append("Style violations found")

    def _categorize_commands(
        self, commands: dict[str, CommandInfo]
    ) -> dict[str, list[str]]:
        """Categorize commands by purpose.

        Args:
            commands: Commands to categorize

        Returns:
            Dictionary of category to command names
        """
        categories: dict[str, list[str]] = {}
        category_patterns = self._get_category_patterns()

        for command in commands.values():
            category = self._determine_command_category(command, category_patterns)
            command.category = category
            self._add_command_to_category(categories, category, command.name)

        return categories

    def _get_category_patterns(self) -> dict[str, list[str]]:
        """Get category patterns for command classification."""
        return {
            "development": ["test", "format", "lint", "check", "run"],
            "server": ["server", "start", "stop", "restart", "monitor"],
            "release": ["version", "bump", "publish", "build", "tag"],
            "configuration": ["config", "init", "setup", "install"],
            "utilities": ["clean", "help", "info", "status"],
        }

    def _determine_command_category(
        self, command: CommandInfo, category_patterns: dict[str, list[str]]
    ) -> str:
        """Determine the category for a command based on patterns."""
        for category, patterns in category_patterns.items():
            if any(pattern in command.name for pattern in patterns):
                return category
        return "general"

    def _add_command_to_category(
        self, categories: dict[str, list[str]], category: str, command_name: str
    ) -> None:
        """Add command to the specified category."""
        if category not in categories:
            categories[category] = []
        categories[category].append(command_name)

    def _generate_workflows(
        self, commands: dict[str, CommandInfo]
    ) -> dict[str, list[str]]:
        """Generate workflow sequences from commands.

        Args:
            commands: Available commands

        Returns:
            Dictionary of workflow name to command sequence
        """
        workflows = {
            "development_cycle": [
                "format",
                "lint",
                "test",
                "type-check",
            ],
            "release_cycle": [
                "test",
                "lint",
                "version-bump",
                "build",
                "publish",
            ],
            "maintenance_cycle": [
                "clean",
                "update-dependencies",
                "test",
                "optimize",
            ],
        }

        # Filter workflows to only include available commands
        available_workflows = {}
        for workflow_name, command_sequence in workflows.items():
            available_sequence = [
                cmd
                for cmd in command_sequence
                if any(cmd in available_cmd.name for available_cmd in commands.values())
            ]
            if available_sequence:
                available_workflows[workflow_name] = available_sequence

        return available_workflows

    def _render_markdown(self, reference: CommandReference) -> str:
        """Render reference as Markdown.

        Args:
            reference: Command reference

        Returns:
            Markdown formatted reference
        """
        lines = [
            "# Command Reference",
            "",
            f"Generated: {reference.generated_at.strftime('%Y-%m-%d %H:%M:%S')}",
            f"Version: {reference.version}",
            "",
            "## Categories",
            "",
        ]

        # Add table of contents
        lines.extend(self._render_markdown_toc(reference.categories))
        lines.append("")

        # Add commands by category
        lines.extend(self._render_markdown_categories(reference))

        # Add workflows if present
        if reference.workflows:
            lines.extend(self._render_markdown_workflows(reference.workflows))

        return "\n".join(lines)

    def _render_markdown_toc(self, categories: dict[str, list[str]]) -> list[str]:
        """Render table of contents for markdown.

        Args:
            categories: Command categories

        Returns:
            List of TOC lines
        """
        return [
            f"- [{category.title()}](#{category.replace('_', '-')})"
            for category in categories
        ]

    def _render_markdown_categories(self, reference: CommandReference) -> list[str]:
        """Render command categories for markdown."""
        category_lines = []
        for category, command_names in reference.categories.items():
            category_section = self._render_markdown_category(
                category, reference.commands, command_names
            )
            category_lines.extend(category_section)
        return category_lines

    def _render_markdown_category(
        self, category: str, commands: dict[str, CommandInfo], command_names: list[str]
    ) -> list[str]:
        """Render markdown for a single category."""
        category_lines = [
            f"## {category.title()}",
            "",
        ]

        for command_name in command_names:
            command = commands[command_name]
            command_lines = self._render_command_markdown(command)
            category_lines.extend(command_lines)

        return category_lines

    def _render_markdown_workflows(self, workflows: dict[str, list[str]]) -> list[str]:
        """Render workflows section for markdown.

        Args:
            workflows: Workflow definitions

        Returns:
            List of workflow section lines
        """
        workflow_lines = [
            "## Workflows",
            "",
        ]

        for workflow_name, command_sequence in workflows.items():
            workflow_lines.extend(
                [
                    f"### {workflow_name.replace('_', ' ').title()}",
                    "",
                ]
            )

            for i, cmd in enumerate(command_sequence, 1):
                workflow_lines.append(f"{i}. `{cmd}`")

            workflow_lines.append("")

        return workflow_lines

    def _render_command_markdown(self, command: CommandInfo) -> list[str]:
        """Render single command as Markdown."""
        lines = [
            f"### `{command.name}`",
            "",
            command.description,
            "",
        ]

        # Add parameters section
        if command.parameters:
            param_lines = self._render_command_parameters_markdown(command.parameters)
            lines.extend(param_lines)

        # Add examples section
        if command.examples:
            example_lines = self._render_command_examples_markdown(command.examples)
            lines.extend(example_lines)

        # Add related commands section
        if command.related_commands:
            related_lines = self._render_command_related_markdown(
                command.related_commands
            )
            lines.extend(related_lines)

        return lines

    def _render_command_parameters_markdown(
        self, parameters: list[ParameterInfo]
    ) -> list[str]:
        """Render command parameters for markdown."""
        param_lines = [
            "**Parameters:**",
            "",
        ]

        for param in parameters:
            param_line = self._format_parameter_line(param)
            param_lines.append(param_line)

        param_lines.append("")
        return param_lines

    def _format_parameter_line(self, param: ParameterInfo) -> str:
        """Format a single parameter line."""
        required_str = " (required)" if param.required else ""
        default_str = (
            f" (default: {param.default_value})"
            if param.default_value is not None
            else ""
        )
        return f"- `--{param.name}` ({param.type_hint}){required_str}{default_str}: {param.description}"

    def _render_command_examples_markdown(
        self, examples: list[dict[str, str]]
    ) -> list[str]:
        """Render command examples for markdown.

        Args:
            examples: List of examples to render

        Returns:
            List of examples section lines
        """
        example_lines = [
            "**Examples:**",
            "",
        ]

        for example in examples:
            example_lines.extend(
                [
                    f"*{example['description']}:*",
                    "```bash",
                    example["command"],
                    "```",
                    "",
                ]
            )

        return example_lines

    def _render_command_related_markdown(
        self, related_commands: list[str]
    ) -> list[str]:
        """Render related commands for markdown.

        Args:
            related_commands: List of related command names

        Returns:
            List of related commands section lines
        """
        return [
            "**Related commands:** "
            + ", ".join(f"`{cmd}`" for cmd in related_commands),
            "",
        ]

    def _render_html(self, reference: CommandReference) -> str:
        """Render reference as HTML."""
        html_parts = [
            self._render_html_header(
                reference.generated_at.strftime("%Y-%m-%d %H:%M:%S")
            ),
            self._render_html_commands(reference),
            "</body></html>",
        ]
        return "".join(html_parts)

    def _render_html_header(self, generated_at: str) -> str:
        """Render HTML header with styles and metadata."""
        return f"""<!DOCTYPE html>
<html>
<head>
    <title>Command Reference</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; }}
        .command {{ margin-bottom: 2em; }}
        .parameter {{ margin-left: 1em; }}
        code {{ background-color: #f5f5f5; padding: 2px 4px; }}
        pre {{ background-color: #f5f5f5; padding: 10px; }}
    </style>
</head>
<body>
    <h1>Command Reference</h1>
    <p>Generated: {generated_at}</p>
"""

    def _render_html_commands(self, reference: CommandReference) -> str:
        """Render HTML commands by category."""
        html_parts = []
        for category, command_names in reference.categories.items():
            category_html = self._render_html_category(
                category, reference.commands, command_names
            )
            html_parts.append(category_html)
        return "".join(html_parts)

    def _render_html_category(
        self, category: str, commands: dict[str, CommandInfo], command_names: list[str]
    ) -> str:
        """Render HTML for a single category."""
        html = f"<h2>{category.title()}</h2>"
        html += self._render_html_category_commands(commands, command_names)
        return html

    def _render_html_category_commands(
        self, commands: dict[str, CommandInfo], command_names: list[str]
    ) -> str:
        """Render HTML for commands in a category."""
        html_parts = []
        for command_name in command_names:
            command = commands[command_name]
            command_html = self._render_single_html_command(command)
            html_parts.append(command_html)
        return "".join(html_parts)

    def _render_single_html_command(self, command: CommandInfo) -> str:
        """Render HTML for a single command."""
        html = '<div class="command">'
        html += f"<h3><code>{command.name}</code></h3>"
        html += f"<p>{command.description}</p>"
        html += self._render_html_command_parameters(command.parameters)
        html += "</div>"
        return html

    def _render_html_command_parameters(self, parameters: list[ParameterInfo]) -> str:
        """Render HTML for command parameters."""
        if not parameters:
            return ""

        html = "<h4>Parameters:</h4><ul>"
        for param in parameters:
            html += f'<li class="parameter"><code>--{param.name}</code> ({param.type_hint}): {param.description}</li>'
        html += "</ul>"
        return html

    def _render_json(self, reference: CommandReference) -> str:
        """Render reference as JSON."""
        import json

        data: dict[str, t.Any] = {
            "generated_at": reference.generated_at.isoformat(),
            "version": reference.version,
            "categories": reference.categories,
            "workflows": reference.workflows,
            "commands": self._serialize_commands(reference.commands),
        }

        return json.dumps(data, indent=2, default=str)

    def _serialize_commands(self, commands: dict[str, CommandInfo]) -> dict[str, t.Any]:
        """Serialize commands for JSON output."""
        serialized_commands = {}
        for name, command in commands.items():
            serialized_commands[name] = self._serialize_command(command)
        return serialized_commands

    def _serialize_command(self, command: CommandInfo) -> dict[str, t.Any]:
        """Serialize a single command for JSON output."""
        return {
            "name": command.name,
            "description": command.description,
            "category": command.category,
            "parameters": self._serialize_parameters(command.parameters),
            "examples": command.examples,
            "related_commands": command.related_commands,
            "aliases": command.aliases,
        }

    def _serialize_parameters(
        self, parameters: list[ParameterInfo]
    ) -> list[dict[str, t.Any]]:
        """Serialize parameters for JSON output."""
        return [self._serialize_parameter(param) for param in parameters]

    def _serialize_parameter(self, param: ParameterInfo) -> dict[str, t.Any]:
        """Serialize a single parameter for JSON output."""
        return {
            "name": param.name,
            "type": param.type_hint,
            "default": param.default_value,
            "description": param.description,
            "required": param.required,
        }

    def _render_yaml(self, reference: CommandReference) -> str:
        """Render reference as YAML."""
        import yaml

        # Convert to JSON-serializable format first
        json_data = self._render_json(reference)
        import json

        data = json.loads(json_data)

        return yaml.dump(data, default_flow_style=False, sort_keys=False)

    def _render_rst(self, reference: CommandReference) -> str:
        """Render reference as reStructuredText."""
        lines = [
            "Command Reference",
            "=================",
            "",
            f"Generated: {reference.generated_at.strftime('%Y-%m-%d %H:%M:%S')}",
            f"Version: {reference.version}",
            "",
        ]

        lines.extend(self._render_rst_categories(reference))
        return "\n".join(lines)

    def _render_rst_categories(self, reference: CommandReference) -> list[str]:
        """Render RST categories and commands."""
        rst_lines = []

        for category, command_names in reference.categories.items():
            rst_lines.extend(
                [
                    category.title(),
                    "-" * len(category),
                    "",
                ]
            )

            rst_lines.extend(
                self._render_rst_category_commands(reference.commands, command_names)
            )

        return rst_lines

    def _render_rst_category_commands(
        self, commands: dict[str, CommandInfo], command_names: list[str]
    ) -> list[str]:
        """Render RST commands for a category."""
        command_lines = []

        for command_name in command_names:
            command = commands[command_name]
            command_lines.extend(
                [
                    f"``{command.name}``",
                    "^" * (len(command.name) + 4),
                    "",
                    command.description,
                    "",
                ]
            )

            if command.parameters:
                command_lines.extend(
                    self._render_rst_command_parameters(command.parameters)
                )

        return command_lines

    def _render_rst_command_parameters(
        self, parameters: list[ParameterInfo]
    ) -> list[str]:
        """Render RST command parameters."""
        param_lines = [
            "Parameters:",
            "",
        ]

        for param in parameters:
            param_lines.append(
                f"* ``--{param.name}`` ({param.type_hint}): {param.description}"
            )

        param_lines.append("")
        return param_lines
