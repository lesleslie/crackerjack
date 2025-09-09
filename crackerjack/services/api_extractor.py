"""Service for extracting API documentation from Python source code."""

import ast
import inspect
import re
import typing as t
from pathlib import Path

from rich.console import Console

from ..models.protocols import APIExtractorProtocol


class PythonDocstringParser:
    """Parser for extracting structured information from Python docstrings."""

    def __init__(self) -> None:
        # Regex patterns for different docstring styles
        self.google_param_pattern = re.compile(
            r"^\s*(\w+)(?:\s*\([^)]+\))?\s*:\s*(.+)$", re.MULTILINE
        )
        self.sphinx_param_pattern = re.compile(r":param\s+(\w+):\s*(.+)$", re.MULTILINE)
        self.returns_pattern = re.compile(
            r"(?:Returns?|Return):\s*(.+?)(?=\n\n|\n\w+:|\Z)", re.MULTILINE | re.DOTALL
        )

    def parse_docstring(self, docstring: str | None) -> dict[str, t.Any]:
        """Parse a docstring and extract structured information."""
        if not docstring:
            return {"description": "", "parameters": {}, "returns": "", "raises": []}

        docstring = inspect.cleandoc(docstring)

        # Extract main description (first paragraph)
        lines = docstring.split("\n")
        description_lines = []
        for line in lines:
            if line.strip() and not self._is_section_header(line):
                description_lines.append(line)
            elif description_lines:
                break

        description = "\n".join(description_lines).strip()

        # Extract parameters
        parameters = self._extract_parameters(docstring)

        # Extract returns
        returns = self._extract_returns(docstring)

        # Extract raises information
        raises = self._extract_raises(docstring)

        return {
            "description": description,
            "parameters": parameters,
            "returns": returns,
            "raises": raises,
        }

    def _is_section_header(self, line: str) -> bool:
        """Check if a line is a docstring section header."""
        line = line.strip().lower()
        headers = [
            "args:",
            "arguments:",
            "parameters:",
            "param:",
            "returns:",
            "yields:",
            "raises:",
            "note:",
            "example:",
        ]
        return any(line.startswith(header) for header in headers)

    def _extract_parameters(self, docstring: str) -> dict[str, str]:
        """Extract parameter documentation from docstring."""
        parameters = {}

        # Try Google style first
        google_matches = self.google_param_pattern.findall(docstring)
        for param_name, param_desc in google_matches:
            parameters[param_name] = param_desc.strip()

        # Try Sphinx style if no Google style found
        if not parameters:
            sphinx_matches = self.sphinx_param_pattern.findall(docstring)
            for param_name, param_desc in sphinx_matches:
                parameters[param_name] = param_desc.strip()

        return parameters

    def _extract_returns(self, docstring: str) -> str:
        """Extract return value documentation from docstring."""
        match = self.returns_pattern.search(docstring)
        if match:
            return match.group(1).strip()
        return ""

    def _extract_raises(self, docstring: str) -> list[str]:
        """Extract exception documentation from docstring."""
        raises_pattern = re.compile(
            r"(?:Raises?|Raise):\s*(.+?)(?=\n\n|\n\w+:|\Z)", re.MULTILINE | re.DOTALL
        )
        match = raises_pattern.search(docstring)
        if match:
            raises_text = match.group(1).strip()
            # Split by lines and clean up
            raises_list = [
                line.strip() for line in raises_text.split("\n") if line.strip()
            ]
            return raises_list
        return []


class APIExtractorImpl(APIExtractorProtocol):
    """Implementation of API documentation extraction from source code."""

    def __init__(self, console: Console) -> None:
        self.console = console
        self.docstring_parser = PythonDocstringParser()

    def extract_from_python_files(self, files: list[Path]) -> dict[str, t.Any]:
        """Extract API documentation from Python files."""
        api_data = {"modules": {}, "classes": {}, "functions": {}, "protocols": {}}

        for file_path in files:
            if not file_path.exists() or file_path.suffix != ".py":
                continue

            try:
                with open(file_path, encoding="utf-8") as f:
                    source_code = f.read()

                tree = ast.parse(source_code)
                module_data = self._extract_module_info(tree, file_path, source_code)
                api_data["modules"][str(file_path)] = module_data

            except Exception as e:
                self.console.print(
                    f"[yellow]Warning: Could not parse {file_path}: {e}[/yellow]"
                )
                continue

        return api_data

    def extract_protocol_definitions(self, protocol_file: Path) -> dict[str, t.Any]:
        """Extract protocol definitions from protocols.py file."""
        if not protocol_file.exists():
            return {}

        try:
            with open(protocol_file, encoding="utf-8") as f:
                source_code = f.read()

            tree = ast.parse(source_code)
            protocols = {}

            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef) and self._is_protocol_class(node):
                    protocol_info = self._extract_protocol_info(node, source_code)
                    protocols[node.name] = protocol_info

            return {"protocols": protocols}

        except Exception as e:
            self.console.print(f"[red]Error extracting protocols: {e}[/red]")
            return {}

    def extract_service_interfaces(self, service_files: list[Path]) -> dict[str, t.Any]:
        """Extract service interfaces and their methods."""
        services = {}

        for file_path in service_files:
            if not file_path.exists() or file_path.suffix != ".py":
                continue

            try:
                with open(file_path, encoding="utf-8") as f:
                    source_code = f.read()

                tree = ast.parse(source_code)
                service_info = self._extract_service_info(tree, file_path, source_code)
                if service_info:
                    services[file_path.stem] = service_info

            except Exception as e:
                self.console.print(
                    f"[yellow]Warning: Could not parse service {file_path}: {e}[/yellow]"
                )
                continue

        return {"services": services}

    def extract_cli_commands(self, cli_files: list[Path]) -> dict[str, t.Any]:
        """Extract CLI command definitions and options."""
        cli_data = {"commands": {}, "options": {}}

        for file_path in cli_files:
            if not file_path.exists() or file_path.suffix != ".py":
                continue

            try:
                with open(file_path, encoding="utf-8") as f:
                    source_code = f.read()

                tree = ast.parse(source_code)
                cli_info = self._extract_cli_info(tree, source_code)
                cli_data["commands"][file_path.stem] = cli_info

            except Exception as e:
                self.console.print(
                    f"[yellow]Warning: Could not parse CLI file {file_path}: {e}[/yellow]"
                )
                continue

        return cli_data

    def extract_mcp_tools(self, mcp_files: list[Path]) -> dict[str, t.Any]:
        """Extract MCP tool definitions and their capabilities."""
        mcp_tools = {}

        for file_path in mcp_files:
            if not file_path.exists():
                continue

            try:
                if file_path.suffix == ".py":
                    with open(file_path, encoding="utf-8") as f:
                        source_code = f.read()
                    tree = ast.parse(source_code)
                    tool_info = self._extract_mcp_python_tools(tree, source_code)
                elif file_path.suffix == ".md":
                    with open(file_path, encoding="utf-8") as f:
                        markdown_content = f.read()
                    tool_info = self._extract_mcp_markdown_docs(markdown_content)
                else:
                    continue

                if tool_info:
                    mcp_tools[file_path.stem] = tool_info

            except Exception as e:
                self.console.print(
                    f"[yellow]Warning: Could not parse MCP file {file_path}: {e}[/yellow]"
                )
                continue

        return {"mcp_tools": mcp_tools}

    def _extract_module_info(
        self, tree: ast.AST, file_path: Path, source_code: str
    ) -> dict[str, t.Any]:
        """Extract information from a Python module."""
        module_info = {
            "path": str(file_path),
            "docstring": ast.get_docstring(tree),
            "classes": [],
            "functions": [],
            "imports": [],
        }

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                class_info = self._extract_class_info(node, source_code)
                module_info["classes"].append(class_info)
            elif isinstance(node, ast.FunctionDef):
                func_info = self._extract_function_info(node, source_code)
                module_info["functions"].append(func_info)
            elif isinstance(node, ast.Import | ast.ImportFrom):
                import_info = self._extract_import_info(node)
                module_info["imports"].append(import_info)

        return module_info

    def _extract_class_info(
        self, node: ast.ClassDef, source_code: str
    ) -> dict[str, t.Any]:
        """Extract information from a class definition."""
        docstring = ast.get_docstring(node)
        parsed_doc = self.docstring_parser.parse_docstring(docstring)

        class_info = {
            "name": node.name,
            "docstring": parsed_doc,
            "base_classes": [self._get_node_name(base) for base in node.bases],
            "methods": [],
            "properties": [],
            "is_protocol": self._is_protocol_class(node),
        }

        for item in node.body:
            if isinstance(item, ast.FunctionDef):
                method_info = self._extract_function_info(item, source_code)
                method_info["is_method"] = True
                if item.name.startswith("_") and not item.name.startswith("__"):
                    method_info["visibility"] = "protected"
                elif item.name.startswith("__"):
                    method_info["visibility"] = "private"
                else:
                    method_info["visibility"] = "public"
                class_info["methods"].append(method_info)

        return class_info

    def _extract_function_info(
        self, node: ast.FunctionDef, source_code: str
    ) -> dict[str, t.Any]:
        """Extract information from a function definition."""
        docstring = ast.get_docstring(node)
        parsed_doc = self.docstring_parser.parse_docstring(docstring)

        # Extract parameter information
        parameters = []
        for arg in node.args.args:
            param_info = {
                "name": arg.arg,
                "annotation": self._get_annotation_string(arg.annotation),
                "description": parsed_doc["parameters"].get(arg.arg, ""),
            }
            parameters.append(param_info)

        # Extract return annotation
        return_annotation = self._get_annotation_string(node.returns)

        func_info = {
            "name": node.name,
            "docstring": parsed_doc,
            "parameters": parameters,
            "return_annotation": return_annotation,
            "is_async": isinstance(node, ast.AsyncFunctionDef),
            "decorators": [
                self._get_node_name(decorator) for decorator in node.decorator_list
            ],
        }

        return func_info

    def _extract_protocol_info(
        self, node: ast.ClassDef, source_code: str
    ) -> dict[str, t.Any]:
        """Extract detailed information from a protocol definition."""
        docstring = ast.get_docstring(node)
        parsed_doc = self.docstring_parser.parse_docstring(docstring)

        protocol_info = {
            "name": node.name,
            "docstring": parsed_doc,
            "methods": [],
            "runtime_checkable": any(
                self._get_node_name(decorator) == "runtime_checkable"
                for decorator in node.decorator_list
            ),
        }

        for item in node.body:
            if isinstance(item, ast.FunctionDef):
                method_info = self._extract_function_info(item, source_code)
                method_info["is_abstract"] = True  # Protocol methods are abstract
                protocol_info["methods"].append(method_info)

        return protocol_info

    def _extract_service_info(
        self, tree: ast.AST, file_path: Path, source_code: str
    ) -> dict[str, t.Any]:
        """Extract service implementation information."""
        service_info = {
            "path": str(file_path),
            "classes": [],
            "functions": [],
            "protocols_implemented": [],
        }

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                class_info = self._extract_class_info(node, source_code)
                # Check if this class implements any protocols
                for base in node.bases:
                    base_name = self._get_node_name(base)
                    if "Protocol" in base_name:
                        service_info["protocols_implemented"].append(base_name)
                service_info["classes"].append(class_info)

        return service_info if service_info["classes"] else None

    def _extract_cli_info(self, tree: ast.AST, source_code: str) -> dict[str, t.Any]:
        """Extract CLI command and option information."""
        cli_info = {"options": [], "commands": [], "arguments": []}

        # Look for Pydantic model fields that represent CLI options
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                for item in node.body:
                    if isinstance(item, ast.AnnAssign) and item.target:
                        field_name = getattr(item.target, "id", None)
                        if field_name:
                            field_info = {
                                "name": field_name,
                                "type": self._get_annotation_string(item.annotation),
                                "description": "",
                            }
                            cli_info["options"].append(field_info)

        return cli_info

    def _extract_mcp_python_tools(
        self, tree: ast.AST, source_code: str
    ) -> dict[str, t.Any]:
        """Extract MCP tool information from Python files."""
        tools = []

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # Look for functions that might be MCP tools
                func_info = self._extract_function_info(node, source_code)
                if "mcp" in func_info["name"].lower() or any(
                    "tool" in dec.lower() for dec in func_info["decorators"]
                ):
                    tools.append(func_info)

        return {"tools": tools} if tools else None

    def _extract_mcp_markdown_docs(self, content: str) -> dict[str, t.Any]:
        """Extract MCP tool documentation from markdown files."""
        # Simple extraction of sections and command examples
        sections = []
        current_section = None

        for line in content.split("\n"):
            if line.startswith("#"):
                if current_section:
                    sections.append(current_section)
                current_section = {"title": line.strip("#").strip(), "content": []}
            elif current_section:
                current_section["content"].append(line)

        if current_section:
            sections.append(current_section)

        return {"sections": sections}

    def _is_protocol_class(self, node: ast.ClassDef) -> bool:
        """Check if a class is a Protocol definition."""
        return "Protocol" in [self._get_node_name(base) for base in node.bases] or any(
            self._get_node_name(decorator) == "runtime_checkable"
            for decorator in node.decorator_list
        )

    def _get_node_name(self, node: ast.AST) -> str:
        """Get the name from an AST node."""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return f"{self._get_node_name(node.value)}.{node.attr}"
        elif isinstance(node, ast.Constant):
            return str(node.value)
        return ""

    def _get_annotation_string(self, annotation: ast.AST | None) -> str:
        """Convert an annotation AST node to a string representation."""
        if annotation is None:
            return ""

        try:
            if isinstance(annotation, ast.Name):
                return annotation.id
            elif isinstance(annotation, ast.Attribute):
                return f"{self._get_node_name(annotation.value)}.{annotation.attr}"
            elif isinstance(annotation, ast.Subscript):
                value = self._get_node_name(annotation.value)
                slice_val = self._get_annotation_string(annotation.slice)
                return f"{value}[{slice_val}]"
            elif isinstance(annotation, ast.BinOp) and isinstance(
                annotation.op, ast.BitOr
            ):
                # Handle Union types with | operator (Python 3.10+)
                left = self._get_annotation_string(annotation.left)
                right = self._get_annotation_string(annotation.right)
                return f"{left} | {right}"
            elif isinstance(annotation, ast.Constant):
                return str(annotation.value)
            elif isinstance(annotation, ast.Tuple):
                elements = [self._get_annotation_string(elt) for elt in annotation.elts]
                return f"({', '.join(elements)})"
            else:
                # Fallback: try to get source code representation
                return ast.unparse(annotation) if hasattr(ast, "unparse") else "Any"
        except Exception:
            return "Any"

    def _extract_import_info(
        self, node: ast.Import | ast.ImportFrom
    ) -> dict[str, t.Any]:
        """Extract import statement information."""
        if isinstance(node, ast.Import):
            return {
                "type": "import",
                "names": [alias.name for alias in node.names],
                "from": None,
            }
        elif isinstance(node, ast.ImportFrom):
            return {
                "type": "from_import",
                "from": node.module,
                "names": [alias.name for alias in node.names] if node.names else ["*"],
                "level": node.level,
            }
        return {}
