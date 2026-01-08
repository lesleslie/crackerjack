import ast
import inspect
import re
import typing as t
from pathlib import Path

from ..core.console import CrackerjackConsole
from ..models.protocols import APIExtractorProtocol
from .regex_patterns import SAFE_PATTERNS


class PythonDocstringParser:
    def __init__(self) -> None:
        self.google_param_pattern = SAFE_PATTERNS[
            "extract_google_docstring_params"
        ]._get_compiled_pattern()
        self.sphinx_param_pattern = SAFE_PATTERNS[
            "extract_sphinx_docstring_params"
        ]._get_compiled_pattern()
        self.returns_pattern = SAFE_PATTERNS[
            "extract_docstring_returns"
        ]._get_compiled_pattern()

    def parse_docstring(self, docstring: str | None) -> dict[str, t.Any]:
        if not docstring:
            return {"description": "", "parameters": {}, "returns": "", "raises": []}

        docstring = inspect.cleandoc(docstring)

        lines = docstring.split("\n")
        description_lines = []
        for line in lines:
            if line.strip() and not self._is_section_header(line):
                description_lines.append(line)
            elif description_lines:
                break

        description = "\n".join(description_lines).strip()

        parameters = self._extract_parameters(docstring)

        returns = self._extract_returns(docstring)

        raises = self._extract_raises(docstring)

        return {
            "description": description,
            "parameters": parameters,
            "returns": returns,
            "raises": raises,
        }

    def _is_section_header(self, line: str) -> bool:
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
        parameters = {}

        google_matches = self.google_param_pattern.findall(docstring)
        for param_name, param_desc in google_matches:
            parameters[param_name] = param_desc.strip()

        if not parameters:
            sphinx_matches = self.sphinx_param_pattern.findall(docstring)
            for param_name, param_desc in sphinx_matches:
                parameters[param_name] = param_desc.strip()

        return parameters

    def _extract_returns(self, docstring: str) -> str:
        match = self.returns_pattern.search(docstring)
        if match:
            return match.group(1).strip()
        return ""

    def _extract_raises(self, docstring: str) -> list[str]:
        raises_pattern = re.compile(  # REGEX OK: exception extraction
            r"(?:Raises?|Raise):\s*(.+?)(?=\n\n|\n\w+:|\Z)", re.MULTILINE | re.DOTALL
        )
        match = raises_pattern.search(docstring)
        if match:
            raises_text = match.group(1).strip()

            raises_list = [
                line.strip() for line in raises_text.split("\n") if line.strip()
            ]
            return raises_list
        return []


class APIExtractorImpl(APIExtractorProtocol):
    def __init__(self) -> None:
        self.console = CrackerjackConsole()
        self.docstring_parser = PythonDocstringParser()

    def extract_from_python_files(self, files: list[Path]) -> dict[str, t.Any]:
        api_data: dict[str, t.Any] = {
            "modules": {},
            "classes": {},
            "functions": {},
            "protocols": {},
        }

        for file_path in files:
            if not file_path.exists() or file_path.suffix != ".py":
                continue

            try:
                source_code = Path(file_path).read_text(encoding="utf-8")

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
        if not protocol_file.exists():
            return {}

        try:
            source_code = Path(protocol_file).read_text(encoding="utf-8")

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
        services = {}

        for file_path in service_files:
            if not file_path.exists() or file_path.suffix != ".py":
                continue

            try:
                source_code = Path(file_path).read_text(encoding="utf-8")

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
        cli_data: dict[str, t.Any] = {"commands": {}, "options": {}}

        for file_path in cli_files:
            if not file_path.exists() or file_path.suffix != ".py":
                continue

            try:
                source_code = Path(file_path).read_text(encoding="utf-8")

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
        mcp_tools = {}

        for file_path in mcp_files:
            if not file_path.exists():
                continue

            try:
                if file_path.suffix == ".py":
                    source_code = Path(file_path).read_text(encoding="utf-8")
                    tree = ast.parse(source_code)
                    tool_info = self._extract_mcp_python_tools(tree, source_code)
                elif file_path.suffix == ".md":
                    markdown_content = Path(file_path).read_text(encoding="utf-8")
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
        module_info = self._create_base_module_info(tree, file_path)
        self._populate_module_components(module_info, tree, source_code)
        return module_info

    def _create_base_module_info(
        self, tree: ast.AST, file_path: Path
    ) -> dict[str, t.Any]:
        docstring = (
            ast.get_docstring(tree)
            if isinstance(
                tree, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef
            )
            else None
        )
        return {
            "path": str(file_path),
            "docstring": docstring,
            "classes": [],
            "functions": [],
            "imports": [],
        }

    def _populate_module_components(
        self, module_info: dict[str, t.Any], tree: ast.AST, source_code: str
    ) -> None:
        for node in ast.walk(tree):
            self._process_ast_node(module_info, node, source_code)

    def _process_ast_node(
        self, module_info: dict[str, t.Any], node: ast.AST, source_code: str
    ) -> None:
        if isinstance(node, ast.ClassDef):
            class_info = self._extract_class_info(node, source_code)
            module_info["classes"].append(class_info)
        elif isinstance(node, ast.FunctionDef):
            func_info = self._extract_function_info(node, source_code)
            module_info["functions"].append(func_info)
        elif isinstance(node, ast.Import | ast.ImportFrom):
            import_info = self._extract_import_info(node)
            module_info["imports"].append(import_info)

    def _extract_class_info(
        self, node: ast.ClassDef, source_code: str
    ) -> dict[str, t.Any]:
        docstring = ast.get_docstring(node)
        parsed_doc = self.docstring_parser.parse_docstring(docstring)

        class_info = self._build_base_class_info(node, parsed_doc)
        self._extract_class_methods(class_info, node, source_code)

        return class_info

    def _build_base_class_info(
        self, node: ast.ClassDef, parsed_doc: dict[str, t.Any]
    ) -> dict[str, t.Any]:
        return {
            "name": node.name,
            "docstring": parsed_doc,
            "base_classes": [self._get_node_name(base) for base in node.bases],
            "methods": [],
            "properties": [],
            "is_protocol": self._is_protocol_class(node),
        }

    def _extract_class_methods(
        self, class_info: dict[str, t.Any], node: ast.ClassDef, source_code: str
    ) -> None:
        for item in node.body:
            if isinstance(item, ast.FunctionDef):
                method_info = self._extract_function_info(item, source_code)
                method_info["is_method"] = True
                method_info["visibility"] = self._determine_method_visibility(item.name)
                class_info["methods"].append(method_info)

    def _determine_method_visibility(self, method_name: str) -> str:
        if method_name.startswith("_") and not method_name.startswith("__"):
            return "protected"
        elif method_name.startswith("__"):
            return "private"
        return "public"

    def _extract_function_info(
        self, node: ast.FunctionDef, source_code: str
    ) -> dict[str, t.Any]:
        docstring = ast.get_docstring(node)
        parsed_doc = self.docstring_parser.parse_docstring(docstring)

        parameters = []
        for arg in node.args.args:
            param_info = {
                "name": arg.arg,
                "annotation": self._get_annotation_string(arg.annotation),
                "description": parsed_doc["parameters"].get(arg.arg, ""),
            }
            parameters.append(param_info)

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
        docstring = ast.get_docstring(node)
        parsed_doc = self.docstring_parser.parse_docstring(docstring)

        protocol_info: dict[str, t.Any] = {
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
                method_info["is_abstract"] = True
                if isinstance(protocol_info["methods"], list):
                    protocol_info["methods"].append(method_info)

        return protocol_info

    def _extract_service_info(
        self, tree: ast.AST, file_path: Path, source_code: str
    ) -> dict[str, t.Any] | None:
        service_info = self._create_service_info_structure(file_path)
        self._populate_service_classes(service_info, tree, source_code)
        return service_info if service_info["classes"] else None

    def _create_service_info_structure(self, file_path: Path) -> dict[str, t.Any]:
        return {
            "path": str(file_path),
            "classes": [],
            "functions": [],
            "protocols_implemented": [],
        }

    def _populate_service_classes(
        self, service_info: dict[str, t.Any], tree: ast.AST, source_code: str
    ) -> None:
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                self._process_service_class(service_info, node, source_code)

    def _process_service_class(
        self, service_info: dict[str, t.Any], node: ast.ClassDef, source_code: str
    ) -> None:
        class_info = self._extract_class_info(node, source_code)
        self._extract_implemented_protocols(service_info, node)
        self._add_class_to_service_info(service_info, class_info)

    def _extract_implemented_protocols(
        self, service_info: dict[str, t.Any], node: ast.ClassDef
    ) -> None:
        for base in node.bases:
            base_name = self._get_node_name(base)
            if "Protocol" in base_name and isinstance(
                service_info["protocols_implemented"], list
            ):
                service_info["protocols_implemented"].append(base_name)

    def _add_class_to_service_info(
        self, service_info: dict[str, t.Any], class_info: dict[str, t.Any]
    ) -> None:
        if isinstance(service_info["classes"], list):
            service_info["classes"].append(class_info)

    def _extract_cli_info(self, tree: ast.AST, source_code: str) -> dict[str, t.Any]:
        cli_info: dict[str, t.Any] = {"options": [], "commands": [], "arguments": []}

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                self._extract_class_cli_options(node, cli_info)

        return cli_info

    def _extract_class_cli_options(
        self, class_node: ast.ClassDef, cli_info: dict[str, t.Any]
    ) -> None:
        for item in class_node.body:
            if self._is_cli_field(item) and isinstance(item, ast.AnnAssign):
                field_info = self._create_cli_field_info(item)
                if field_info and isinstance(cli_info["options"], list):
                    cli_info["options"].append(field_info)

    def _is_cli_field(self, item: ast.stmt) -> bool:
        return isinstance(item, ast.AnnAssign) and item.target is not None

    def _create_cli_field_info(self, item: ast.AnnAssign) -> dict[str, t.Any] | None:
        field_name = getattr(item.target, "id", None)
        if not field_name:
            return None

        return {
            "name": field_name,
            "type": self._get_annotation_string(item.annotation),
            "description": "",
        }

    def _extract_mcp_python_tools(
        self, tree: ast.AST, source_code: str
    ) -> dict[str, t.Any] | None:
        tools = []

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                func_info = self._extract_function_info(node, source_code)
                if "mcp" in func_info["name"].lower() or any(
                    "tool" in dec.lower() for dec in func_info["decorators"]
                ):
                    tools.append(func_info)

        return {"tools": tools} if tools else None

    def _extract_mcp_markdown_docs(self, content: str) -> dict[str, t.Any]:
        sections: list[dict[str, t.Any]] = []
        current_section: dict[str, t.Any] | None = None

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
        return "Protocol" in [self._get_node_name(base) for base in node.bases] or any(
            self._get_node_name(decorator) == "runtime_checkable"
            for decorator in node.decorator_list
        )

    def _get_node_name(self, node: ast.AST) -> str:
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return f"{self._get_node_name(node.value)}.{node.attr}"
        elif isinstance(node, ast.Constant):
            return str(node.value)
        return ""

    def _get_annotation_string(self, annotation: ast.AST | None) -> str:
        if annotation is None:
            return ""

        try:
            return self._process_annotation_node(annotation)
        except Exception:
            return "Any"

    def _process_annotation_node(self, annotation: ast.AST) -> str:
        if isinstance(annotation, ast.Name):
            return annotation.id
        elif isinstance(annotation, ast.Attribute):
            return self._process_attribute_annotation(annotation)
        elif isinstance(annotation, ast.Subscript):
            return self._process_subscript_annotation(annotation)
        elif isinstance(annotation, ast.BinOp) and isinstance(annotation.op, ast.BitOr):
            return self._process_union_annotation(annotation)
        elif isinstance(annotation, ast.Constant):
            return str(annotation.value)
        elif isinstance(annotation, ast.Tuple):
            return self._process_tuple_annotation(annotation)
        return self._get_fallback_annotation(annotation)

    def _process_attribute_annotation(self, annotation: ast.Attribute) -> str:
        return f"{self._get_node_name(annotation.value)}.{annotation.attr}"

    def _process_subscript_annotation(self, annotation: ast.Subscript) -> str:
        value = self._get_node_name(annotation.value)
        slice_val = self._get_annotation_string(annotation.slice)
        return f"{value}[{slice_val}]"

    def _process_union_annotation(self, annotation: ast.BinOp) -> str:
        left = self._get_annotation_string(annotation.left)
        right = self._get_annotation_string(annotation.right)
        return f"{left} | {right}"

    def _process_tuple_annotation(self, annotation: ast.Tuple) -> str:
        elements = [self._get_annotation_string(elt) for elt in annotation.elts]
        return f"({', '.join(elements)})"

    def _get_fallback_annotation(self, annotation: ast.AST) -> str:
        return ast.unparse(annotation) if hasattr(ast, "unparse") else "Any"

    def _extract_import_info(
        self, node: ast.Import | ast.ImportFrom
    ) -> dict[str, t.Any]:
        if isinstance(node, ast.Import):
            return {
                "type": "import",
                "names": [alias.name for alias in node.names],
                "from": None,
            }

        return {
            "type": "from_import",
            "from": node.module,
            "names": [alias.name for alias in node.names] if node.names else ["*"],
            "level": node.level,
        }
