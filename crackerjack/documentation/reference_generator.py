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
    MARKDOWN = "markdown"
    HTML = "html"
    JSON = "json"
    YAML = "yaml"
    RST = "rst"


@dataclass
class ParameterInfo:
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
    name: str
    description: str
    category: str
    parameters: list[ParameterInfo] = field(default_factory=list)
    examples: list[dict[str, str]] = field(default_factory=list)
    related_commands: list[str] = field(default_factory=list)
    aliases: list[str] = field(default_factory=list)
    deprecated: bool = False
    added_in_version: str | None = None

    common_workflows: list[str] = field(default_factory=list)
    prerequisites: list[str] = field(default_factory=list)
    side_effects: list[str] = field(default_factory=list)

    ai_context: dict[str, t.Any] = field(default_factory=dict[str, t.Any])
    success_patterns: list[str] = field(default_factory=list)
    failure_patterns: list[str] = field(default_factory=list)


@dataclass
class CommandReference:
    commands: dict[str, CommandInfo]
    categories: dict[str, list[str]]
    workflows: dict[str, list[str]]
    generated_at: datetime = field(default_factory=datetime.now)
    version: str = "unknown"

    def get_commands_by_category(self, category: str) -> list[CommandInfo]:
        return [cmd for cmd in self.commands.values() if cmd.category == category]

    def get_command_by_name(self, name: str) -> CommandInfo | None:
        if name in self.commands:
            return self.commands[name]

        for cmd in self.commands.values():
            if name in cmd.aliases:
                return cmd

        return None


class ReferenceGenerator:
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
        self.logger.info(f"Generating command reference from: {cli_module_path}")

        commands = await self._analyze_cli_module(cli_module_path)

        if include_examples:
            commands = await self._enhance_with_examples(commands)

        if include_workflows:
            commands = await self._enhance_with_workflows(commands)

        categories = self._categorize_commands(commands)

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
        commands = {}

        try:
            module_file = Path(module_path)
            if not module_file.exists():
                raise FileNotFoundError(f"CLI module not found: {module_path}")

            source_code = module_file.read_text()

            tree = ast.parse(source_code)

            commands = self._extract_commands_from_ast(tree)

        except Exception as e:
            self.logger.error(f"Failed to analyze CLI module: {e}")

        return commands

    def _extract_commands_from_ast(self, tree: ast.AST) -> dict[str, CommandInfo]:
        commands: dict[str, CommandInfo] = {}
        visitor = self._create_command_visitor(commands)
        visitor.visit(tree)
        return commands

    def _create_command_visitor(
        self, commands: dict[str, CommandInfo]
    ) -> ast.NodeVisitor:
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
        for decorator in node.decorator_list:
            if self._is_command_decorator(decorator):
                command_info = self._extract_command_from_function(node)
                if command_info:
                    commands[command_info.name] = command_info

    def _is_command_decorator(self, decorator: ast.AST) -> bool:
        if isinstance(decorator, ast.Name):
            return decorator.id in ("command", "click_command")
        elif isinstance(decorator, ast.Attribute):
            return decorator.attr in ("command", "callback")
        return False

    def _extract_command_from_function(
        self, node: ast.FunctionDef
    ) -> CommandInfo | None:
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
        parameters = []
        for arg in node.args.args:
            if arg.arg != "self":
                param_info = self._extract_parameter_info(arg, node)
                parameters.append(param_info)
        return parameters

    def _extract_docstring(self, node: ast.FunctionDef) -> str | None:
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
        default_index = arg_index - defaults_start
        default_node = func_node.args.defaults[default_index]
        if isinstance(default_node, ast.Constant):
            return default_node.value, False
        return None, True

    async def _enhance_with_examples(
        self, commands: dict[str, CommandInfo]
    ) -> dict[str, CommandInfo]:
        for command in commands.values():
            self._add_basic_example(command)
            self._add_parameter_examples(command)
        return commands

    def _add_basic_example(self, command: CommandInfo) -> None:
        basic_example = f"python -m crackerjack --{command.name}"
        command.examples.append(
            {
                "description": f"Basic {command.name} usage",
                "command": basic_example,
            }
        )

    def _add_parameter_examples(self, command: CommandInfo) -> None:
        basic_example = f"python -m crackerjack --{command.name}"

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
        if isinstance(param.default_value, bool):
            return f"--{param.name}"
        return f"--{param.name} {param.default_value}"

    async def _enhance_with_workflows(
        self, commands: dict[str, CommandInfo]
    ) -> dict[str, CommandInfo]:
        workflow_patterns = self._get_workflow_patterns()

        for command in commands.values():
            self._assign_command_workflows(command, workflow_patterns)
            self._add_ai_context_to_command(command)

        return commands

    def _get_workflow_patterns(self) -> dict[str, list[str]]:
        return {
            "development": ["test", "format", "lint", "type-check"],
            "release": ["version", "build", "publish", "tag"],
            "maintenance": ["clean", "update", "optimize", "backup"],
            "monitoring": ["status", "health", "metrics", "logs"],
        }

    def _assign_command_workflows(
        self, command: CommandInfo, workflow_patterns: dict[str, list[str]]
    ) -> None:
        for workflow, patterns in workflow_patterns.items():
            if any(pattern in command.name for pattern in patterns):
                command.common_workflows.append(workflow)

    def _add_ai_context_to_command(self, command: CommandInfo) -> None:
        if "test" in command.name:
            self._add_test_ai_context(command)
        elif "format" in command.name or "lint" in command.name:
            self._add_quality_ai_context(command)

    def _add_test_ai_context(self, command: CommandInfo) -> None:
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
        categories: dict[str, list[str]] = {}
        category_patterns = self._get_category_patterns()

        for command in commands.values():
            category = self._determine_command_category(command, category_patterns)
            command.category = category
            self._add_command_to_category(categories, category, command.name)

        return categories

    def _get_category_patterns(self) -> dict[str, list[str]]:
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
        for category, patterns in category_patterns.items():
            if any(pattern in command.name for pattern in patterns):
                return category
        return "general"

    def _add_command_to_category(
        self, categories: dict[str, list[str]], category: str, command_name: str
    ) -> None:
        if category not in categories:
            categories[category] = []
        categories[category].append(command_name)

    def _generate_workflows(
        self, commands: dict[str, CommandInfo]
    ) -> dict[str, list[str]]:
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
        lines = [
            "# Command Reference",
            "",
            f"Generated: {reference.generated_at.strftime('%Y-%m-%d %H:%M:%S')}",
            f"Version: {reference.version}",
            "",
            "## Categories",
            "",
        ]

        lines.extend(self._render_markdown_toc(reference.categories))
        lines.append("")

        lines.extend(self._render_markdown_categories(reference))

        if reference.workflows:
            lines.extend(self._render_markdown_workflows(reference.workflows))

        return "\n".join(lines)

    def _render_markdown_toc(self, categories: dict[str, list[str]]) -> list[str]:
        return [
            f"- [{category.title()}](#{category.replace('_', '-')})"
            for category in categories
        ]

    def _render_markdown_categories(self, reference: CommandReference) -> list[str]:
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
        lines = [
            f"### `{command.name}`",
            "",
            command.description,
            "",
        ]

        if command.parameters:
            param_lines = self._render_command_parameters_markdown(command.parameters)
            lines.extend(param_lines)

        if command.examples:
            example_lines = self._render_command_examples_markdown(command.examples)
            lines.extend(example_lines)

        if command.related_commands:
            related_lines = self._render_command_related_markdown(
                command.related_commands
            )
            lines.extend(related_lines)

        return lines

    def _render_command_parameters_markdown(
        self, parameters: list[ParameterInfo]
    ) -> list[str]:
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
        return [
            "**Related commands:** "
            + ", ".join(f"`{cmd}`" for cmd in related_commands),
            "",
        ]

    def _render_html(self, reference: CommandReference) -> str:
        html_parts = [
            self._render_html_header(
                reference.generated_at.strftime("%Y-%m-%d %H:%M:%S")
            ),
            self._render_html_commands(reference),
            "</body></html>",
        ]
        return "".join(html_parts)

    def _render_html_header(self, generated_at: str) -> str:
        return f"""<!DOCTYPE html>
<html>
<head>
    <title>Command Reference</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; }}
        .command {{ margin-bottom: 2em; }}
        .parameter {{ margin-left: 1em; }}
        code {{ background-color:
        pre {{ background-color:
    </style>
</head>
<body>
    <h1>Command Reference</h1>
    <p>Generated: {generated_at}</p>
"""

    def _render_html_commands(self, reference: CommandReference) -> str:
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
        html = f"<h2>{category.title()}</h2>"
        html += self._render_html_category_commands(commands, command_names)
        return html

    def _render_html_category_commands(
        self, commands: dict[str, CommandInfo], command_names: list[str]
    ) -> str:
        html_parts = []
        for command_name in command_names:
            command = commands[command_name]
            command_html = self._render_single_html_command(command)
            html_parts.append(command_html)
        return "".join(html_parts)

    def _render_single_html_command(self, command: CommandInfo) -> str:
        html = '<div class="command">'
        html += f"<h3><code>{command.name}</code></h3>"
        html += f"<p>{command.description}</p>"
        html += self._render_html_command_parameters(command.parameters)
        html += "</div>"
        return html

    def _render_html_command_parameters(self, parameters: list[ParameterInfo]) -> str:
        if not parameters:
            return ""

        html = "<h4>Parameters:</h4><ul>"
        for param in parameters:
            html += f'<li class="parameter"><code>--{param.name}</code> ({param.type_hint}): {param.description}</li>'
        html += "</ul>"
        return html

    def _render_json(self, reference: CommandReference) -> str:
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
        serialized_commands = {}
        for name, command in commands.items():
            serialized_commands[name] = self._serialize_command(command)
        return serialized_commands

    def _serialize_command(self, command: CommandInfo) -> dict[str, t.Any]:
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
        return [self._serialize_parameter(param) for param in parameters]

    def _serialize_parameter(self, param: ParameterInfo) -> dict[str, t.Any]:
        return {
            "name": param.name,
            "type": param.type_hint,
            "default": param.default_value,
            "description": param.description,
            "required": param.required,
        }

    def _render_yaml(self, reference: CommandReference) -> str:
        import yaml

        json_data = self._render_json(reference)
        import json

        data = json.loads(json_data)

        return yaml.dump(data, default_flow_style=False, sort_keys=False)

    def _render_rst(self, reference: CommandReference) -> str:
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
