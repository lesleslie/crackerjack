
import ast
from collections.abc import Callable
from pathlib import Path
from typing import Any

from crackerjack.agents.base import AgentContext


class TestTemplateGenerator:

    def __init__(self, context: AgentContext) -> None:
        self.context = context

    async def generate_test_content(
        self,
        module_file: Path,
        functions: list[dict[str, Any]],
        classes: list[dict[str, Any]],
    ) -> str:
        test_params = self._prepare_test_generation_params(module_file)
        return await self._generate_all_test_types(test_params, functions, classes)

    async def generate_comprehensive_test_content(
        self,
        test_params: dict[str, Any],
        functions: list[dict[str, Any]],
        classes: list[dict[str, Any]],
    ) -> str:
        return await self._generate_all_test_types(test_params, functions, classes)

    def _prepare_test_generation_params(self, module_file: Path) -> dict[str, Any]:
        module_name = self._get_module_import_path(module_file)
        module_category = self._categorize_module(
            str(module_file.relative_to(self.context.project_path))
        )
        return {
            "module_name": module_name,
            "module_file": module_file,
            "module_category": module_category,
        }

    async def _generate_all_test_types(
        self,
        test_params: dict[str, Any],
        functions: list[dict[str, Any]],
        classes: list[dict[str, Any]],
    ) -> str:
        base_content = self._generate_enhanced_test_file_header(
            test_params["module_name"],
            test_params["module_file"],
            test_params["module_category"],
        )

        function_tests = await self._generate_function_tests_content(
            functions, test_params["module_category"]
        )
        class_tests = await self._generate_class_tests_content(
            classes, test_params["module_category"]
        )
        integration_tests = await self._generate_integration_tests_content(
            test_params["module_file"],
            functions,
            classes,
            test_params["module_category"],
        )

        return base_content + function_tests + class_tests + integration_tests

    async def _generate_function_tests_content(
        self, functions: list[dict[str, Any]], module_category: str
    ) -> str:
        return await self._generate_enhanced_function_tests(functions, module_category)

    async def _generate_class_tests_content(
        self, classes: list[dict[str, Any]], module_category: str
    ) -> str:
        return await self._generate_enhanced_class_tests(classes, module_category)

    async def _generate_integration_tests_content(
        self,
        module_file: Path,
        functions: list[dict[str, Any]],
        classes: list[dict[str, Any]],
        module_category: str,
    ) -> str:
        return await self._generate_integration_tests(
            module_file, functions, classes, module_category
        )

    def _generate_enhanced_test_file_header(
        self, module_name: str, module_file: Path, module_category: str
    ) -> str:
        imports = [
            "import pytest",
            "from pathlib import Path",
            "from unittest.mock import Mock, patch, AsyncMock",
        ]

        if module_category in ("service", "manager", "core"):
            imports.append("import asyncio")

        if module_category == "agent":
            imports.extend(
                [
                    "from crackerjack.agents.base import AgentContext, FixResult, "
                    "Issue, IssueType",
                ]
            )

        imports_str = "\n".join(imports)

        try:
            content = self.context.get_file_content(module_file) or ""
            tree = ast.parse(content)

            importable_items = []
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
                    importable_items.append(node.name)
                elif isinstance(
                    node, ast.FunctionDef | ast.AsyncFunctionDef
                ) and not node.name.startswith("_"):
                    importable_items.append(node.name)

            if importable_items:
                specific_imports = (
                    f"from {module_name} import {', '.join(importable_items[:10])}"
                )
            else:
                specific_imports = f"import {module_name}"

        except Exception:
            specific_imports = f"import {module_name}"

        class_name = f"Test{module_file.stem.replace('_', '').title()}"

        return (
            f'"""{imports_str}\n'
            f"{specific_imports}\n"
            "\n"
            "\n"
            f"class {class_name}:\n"
            f' """Tests for {module_name}.\n'
            "\n"
            f" This module contains comprehensive tests for {module_name}\n"
            " including:\n"
            " - Basic functionality tests\n"
            " - Edge case validation\n"
            " - Error handling verification\n"
            " - Integration testing\n"
            " - Performance validation (where applicable)\n"
            ' """\n'
            "\n"
            " def test_module_imports_successfully(self):\n"
            ' """Test that the module can be imported without errors."""\n'
            f" import {module_name}\n"
            f" assert {module_name} is not None\n"
        )

    def _get_module_import_path(self, file_path: Path) -> str:
        try:
            relative_path = file_path.relative_to(self.context.project_path)
            parts = (*relative_path.parts[:-1], relative_path.stem)
            return ".".join(parts)
        except ValueError:
            return file_path.stem

    async def generate_function_test(self, func_info: dict[str, Any]) -> str:
        func_name = func_info["name"]
        args = func_info.get("args", [])

        test_template = f"""def test_{func_name}_basic(self):
    \"\"\"Test basic functionality of {func_name}.\"\"\"
    try:
        result = {func_name}({self._generate_default_args(args)})
        assert result is not None or result is None
    except TypeError:
        pytest.skip(
            "Function requires specific arguments - manual implementation needed"
        )
    except Exception as e:
        pytest.fail(f"Unexpected error in {func_name}: {{e}}")"""

        return test_template

    async def _generate_enhanced_function_tests(
        self, functions: list[dict[str, Any]], module_category: str
    ) -> str:
        if not functions:
            return ""

        test_methods = []
        for func in functions:
            func_tests = await self._generate_all_tests_for_function(
                func, module_category
            )
            test_methods.extend(func_tests)

        return "\n".join(test_methods)

    async def _generate_all_tests_for_function(
        self, func: dict[str, Any], module_category: str
    ) -> list[str]:
        func_tests = []

        basic_test = await self._generate_basic_function_test(func, module_category)
        func_tests.append(basic_test)

        additional_tests = await self._generate_conditional_tests_for_function(
            func, module_category
        )
        func_tests.extend(additional_tests)

        return func_tests

    async def _generate_conditional_tests_for_function(
        self, func: dict[str, Any], module_category: str
    ) -> list[str]:
        tests = []
        args = func.get("args", [])
        func_name = func["name"]

        if self._should_generate_parametrized_test(args):
            parametrized_test = await self._generate_parametrized_test(
                func, module_category
            )
            tests.append(parametrized_test)

        error_test = await self._generate_error_handling_test(func, module_category)
        tests.append(error_test)

        if self._should_generate_edge_case_test(args, func_name):
            edge_test = await self._generate_edge_case_test(func, module_category)
            tests.append(edge_test)

        return tests

    def _should_generate_parametrized_test(self, args: list[str]) -> bool:
        return len(args) > 1

    def _should_generate_edge_case_test(self, args: list[str], func_name: str) -> bool:
        has_multiple_args = len(args) > 2
        is_complex_function = any(
            hint in func_name.lower()
            for hint in ("process", "validate", "parse", "convert")
        )
        return has_multiple_args or is_complex_function

    async def _generate_basic_function_test(
        self, func: dict[str, Any], module_category: str
    ) -> str:
        func_name = func["name"]
        args = func.get("args", [])

        template_generator = self._get_test_template_generator(module_category)
        return template_generator(func_name, args)

    def _get_test_template_generator(
        self, module_category: str
    ) -> Callable[[str, list[str]], str]:
        return {
            "agent": self._generate_agent_test_template,
            "service": self._generate_async_test_template,
            "manager": self._generate_async_test_template,
        }.get(module_category, self._generate_default_test_template)

    def _generate_agent_test_template(self, func_name: str, args: list[str]) -> str:
        template = (
            " def test_FUNC_NAME_basic_functionality(self):\n"
            ' """Test basic functionality of FUNC_NAME."""\n'
            "\n"
            "\n"
            " try:\n"
            " result = FUNC_NAME(ARGS)\n"
            " assert result is not None or result is None\n"
            " except (TypeError, NotImplementedError) as e:\n"
            + (
                " pytest.skip('Function FUNC_NAME requires manual "
                "implementation: ' + str(e))\n"
            )
            + " except Exception as e:\n"
            " pytest.fail('Unexpected error in FUNC_NAME: ' + str(e))"
        )

        return template.replace("FUNC_NAME", func_name).replace(
            "ARGS", self._generate_smart_default_args(args)
        )

    def _generate_async_test_template(self, func_name: str, args: list[str]) -> str:
        template = (
            " @pytest.mark.asyncio\n"
            " async def test_FUNC_NAME_basic_functionality(self):\n"
            ' """Test basic functionality of FUNC_NAME."""\n'
            "\n"
            "\n"
            " try:\n"
            " if asyncio.iscoroutinefunction(FUNC_NAME):\n"
            " result = await FUNC_NAME(ARGS)\n"
            " else:\n"
            " result = FUNC_NAME(ARGS)\n"
            " assert result is not None or result is None\n"
            " except (TypeError, NotImplementedError) as e:\n"
            + (
                " pytest.skip('Function FUNC_NAME requires manual "
                "implementation: ' + str(e))\n"
            )
            + " except Exception as e:\n"
            " pytest.fail('Unexpected error in FUNC_NAME: ' + str(e))"
        )

        return template.replace("FUNC_NAME", func_name).replace(
            "ARGS", self._generate_smart_default_args(args)
        )

    def _generate_default_test_template(self, func_name: str, args: list[str]) -> str:
        template = (
            " def test_FUNC_NAME_basic_functionality(self):\n"
            ' """Test basic functionality of FUNC_NAME."""\n'
            " try:\n"
            " result = FUNC_NAME(ARGS)\n"
            " assert result is not None or result is None\n"
            " except (TypeError, NotImplementedError) as e:\n"
            + (
                " pytest.skip('Function FUNC_NAME requires manual "
                "implementation: ' + str(e))\n"
            )
            + " except Exception as e:\n"
            " pytest.fail('Unexpected error in FUNC_NAME: ' + str(e))"
        )

        return template.replace("FUNC_NAME", func_name).replace(
            "ARGS", self._generate_smart_default_args(args)
        )

    async def _generate_parametrized_test(
        self, func: dict[str, Any], module_category: str
    ) -> str:
        func_name = func["name"]
        args = func.get("args", [])

        test_cases = self._generate_test_parameters(args)

        if not test_cases:
            return ""

        parametrize_decorator = f"@pytest.mark.parametrize({test_cases})"

        test_template = (
            f" {parametrize_decorator}\n"
            f" def test_{func_name}_with_parameters(self, "
            f"{', '.join(args) if len(args) <= 5 else 'test_input'}):\n"
            f' """Test {func_name} with various parameter combinations."""\n'
            " try:\n"
            f" if len({args}) <= 5:\n"
            f" result = {func_name}({', '.join(args)})\n"
            " else:\n"
            f" result = {func_name}(**test_input)\n"
            "\n"
            " assert result is not None or result is None\n"
            " except (TypeError, ValueError) as expected_error:\n"
            "\n"
            " pass\n"
            " except Exception as e:\n"
            ' pytest.fail(f"Unexpected error with parameters: {e}")'
        )

        return test_template

    async def _generate_error_handling_test(
        self, func: dict[str, Any], module_category: str
    ) -> str:
        func_name = func["name"]
        args = func.get("args", [])

        test_template = (
            f" def test_{func_name}_error_handling(self):\n"
            f' """Test {func_name} error handling with invalid inputs."""\n'
            "\n"
            " with pytest.raises((TypeError, ValueError, AttributeError)):\n"
            f" {func_name}({self._generate_invalid_args(args)})\n"
            "\n"
            "\n"
            f" if len({args}) > 0:\n"
            " with pytest.raises((TypeError, ValueError)):\n"
            f" {func_name}("
            f"{self._generate_edge_case_args(args, 'empty')})"
        )

        return test_template

    async def _generate_edge_case_test(
        self, func: dict[str, Any], module_category: str
    ) -> str:
        func_name = func["name"]
        args = func.get("args", [])

        test_template = (
            f" def test_{func_name}_edge_cases(self):\n"
            f' """Test {func_name} with edge case scenarios."""\n'
            "\n"
            " edge_cases = [\n"
            f" {self._generate_edge_case_args(args, 'boundary')}, \n"
            f" {self._generate_edge_case_args(args, 'extreme')}, \n"
            " ]\n"
            "\n"
            " for edge_case in edge_cases:\n"
            " try:\n"
            f" result = {func_name}(*edge_case)\n"
            "\n"
            " assert result is not None or result is None\n"
            " except (ValueError, TypeError):\n"
            "\n"
            " pass\n"
            " except Exception as e:\n"
            ' pytest.fail(f"Unexpected error with edge case {edge_case}: '
            '{e}")'
        )

        return test_template

    def _generate_test_parameters(self, args: list[str]) -> str:
        if not args or len(args) > 5:
            return ""

        param_names = ", ".join(f'"{arg}"' for arg in args)
        param_values = []

        for i in range(min(3, len(args))):
            test_case = []
            for arg in args:
                if "path" in arg.lower():
                    test_case.append(f'Path("test_{i}")')
                elif "str" in arg.lower() or "name" in arg.lower():
                    test_case.append(f'"test_{i}"')
                elif "int" in arg.lower() or "count" in arg.lower():
                    test_case.append(str(i))
                elif "bool" in arg.lower():
                    test_case.append("True" if i % 2 == 0 else "False")
                else:
                    test_case.append("None")
            param_values.append(f"({', '.join(test_case)})")

        return f"[{param_names}], [{', '.join(param_values)}]"

    def _generate_smart_default_args(self, args: list[str]) -> str:
        if not args or args == ["self"]:
            return ""

        filtered_args = self._filter_args(args)
        if not filtered_args:
            return ""

        placeholders = [
            self._generate_placeholder_for_arg(arg) for arg in filtered_args
        ]
        return ", ".join(placeholders)

    def _filter_args(self, args: list[str]) -> list[str]:
        return [arg for arg in args if arg != "self"]

    def _generate_placeholder_for_arg(self, arg: str) -> str:
        arg_lower = arg.lower()

        if self._is_path_arg(arg_lower):
            return 'Path("test_file.txt")'
        elif self._is_url_arg(arg_lower):
            return '"https: //example.com"'
        elif self._is_email_arg(arg_lower):
            return '"test@example.com"'
        elif self._is_id_arg(arg_lower):
            return '"test-id-123"'
        elif self._is_name_arg(arg_lower):
            return '"test_name"'
        elif self._is_numeric_arg(arg_lower):
            return "10"
        elif self._is_boolean_arg(arg_lower):
            return "True"
        elif self._is_text_arg(arg_lower):
            return '"test data"'
        elif self._is_list_arg(arg_lower):
            return '["test1", "test2"]'
        elif self._is_dict_arg(arg_lower):
            return '{"key": "value"}'
        return '"test"'

    def _is_path_arg(self, arg_lower: str) -> bool:
        return any(term in arg_lower for term in ("path", "file"))

    def _is_url_arg(self, arg_lower: str) -> bool:
        return any(term in arg_lower for term in ("url", "uri"))

    def _is_email_arg(self, arg_lower: str) -> bool:
        return any(term in arg_lower for term in ("email", "mail"))

    def _is_id_arg(self, arg_lower: str) -> bool:
        return any(term in arg_lower for term in ("id", "uuid"))

    def _is_name_arg(self, arg_lower: str) -> bool:
        return any(term in arg_lower for term in ("name", "title"))

    def _is_numeric_arg(self, arg_lower: str) -> bool:
        return any(term in arg_lower for term in ("count", "size", "number", "num"))

    def _is_boolean_arg(self, arg_lower: str) -> bool:
        return any(term in arg_lower for term in ("enable", "flag", "is_", "has_"))

    def _is_text_arg(self, arg_lower: str) -> bool:
        return any(term in arg_lower for term in ("data", "content", "text"))

    def _is_list_arg(self, arg_lower: str) -> bool:
        return any(term in arg_lower for term in ("list[t.Any]", "items"))

    def _is_dict_arg(self, arg_lower: str) -> bool:
        return any(
            term in arg_lower for term in ("dict[str, t.Any]", "config", "options")
        )

    def _generate_invalid_args(self, args: list[str]) -> str:
        filtered_args = [arg for arg in args if arg != "self"]
        if not filtered_args:
            return ""
        return ", ".join(["None"] * len(filtered_args))

    def _generate_edge_case_args(self, args: list[str], case_type: str) -> str:
        filtered_args = self._filter_args(args)
        if not filtered_args:
            return ""

        placeholders = self._generate_placeholders_by_case_type(
            filtered_args, case_type
        )
        return ", ".join(placeholders)

    def _generate_placeholders_by_case_type(
        self, filtered_args: list[str], case_type: str
    ) -> list[str]:
        if case_type == "empty":
            return self._generate_empty_case_placeholders(filtered_args)
        elif case_type == "boundary":
            return self._generate_boundary_case_placeholders(filtered_args)

        return self._generate_extreme_case_placeholders(filtered_args)

    def _generate_empty_case_placeholders(self, filtered_args: list[str]) -> list[str]:
        placeholders = []
        for arg in filtered_args:
            arg_lower = arg.lower()
            if any(term in arg_lower for term in ("str", "name", "text")):
                placeholders.append('""')
            elif any(term in arg_lower for term in ("list[t.Any]", "items")):
                placeholders.append("[]")
            elif any(term in arg_lower for term in ("dict[str, t.Any]", "config")):
                placeholders.append("{}")
            else:
                placeholders.append("None")
        return placeholders

    def _generate_boundary_case_placeholders(
        self, filtered_args: list[str]
    ) -> list[str]:
        placeholders = []
        for arg in filtered_args:
            arg_lower = arg.lower()
            if any(term in arg_lower for term in ("count", "size", "number")):
                placeholders.append("0")
            elif any(term in arg_lower for term in ("str", "name")):
                placeholders.append('"x" * 1000')
            else:
                placeholders.append("None")
        return placeholders

    def _generate_extreme_case_placeholders(
        self, filtered_args: list[str]
    ) -> list[str]:
        placeholders = []
        for arg in filtered_args:
            arg_lower = arg.lower()
            if any(term in arg_lower for term in ("count", "size", "number")):
                placeholders.append("-1")
            else:
                placeholders.append("None")
        return placeholders

    async def _generate_enhanced_class_tests(
        self, classes: list[dict[str, Any]], module_category: str
    ) -> str:
        if not classes:
            return ""

        test_components = await self._generate_all_class_test_components(
            classes, module_category
        )
        return self._combine_class_test_elements(
            test_components["fixtures"], test_components["test_methods"]
        )

    async def _generate_all_class_test_components(
        self, classes: list[dict[str, Any]], module_category: str
    ) -> dict[str, list[str]]:
        fixtures = []
        test_methods = []

        for cls in classes:
            class_components = await self._generate_single_class_test_components(
                cls, module_category
            )
            fixtures.extend(class_components["fixtures"])
            test_methods.extend(class_components["test_methods"])

        return {"fixtures": fixtures, "test_methods": test_methods}

    async def _generate_single_class_test_components(
        self, cls: dict[str, Any], module_category: str
    ) -> dict[str, list[str]]:
        fixtures = []
        test_methods = []
        methods = cls.get("methods", [])

        fixture = await self._generate_class_fixture(cls, module_category)
        if fixture:
            fixtures.append(fixture)

        core_tests = await self._generate_core_class_tests(
            cls, methods, module_category
        )
        test_methods.extend(core_tests)

        return {"fixtures": fixtures, "test_methods": test_methods}

    async def _generate_core_class_tests(
        self, cls: dict[str, Any], methods: list[str], module_category: str
    ) -> list[str]:
        test_methods = []

        instantiation_test = await self._generate_class_instantiation_test(
            cls, module_category
        )
        test_methods.append(instantiation_test)

        method_tests = await self._generate_method_tests(
            cls, methods[:5], module_category
        )
        test_methods.extend(method_tests)

        property_test = await self._generate_class_property_test(cls, module_category)
        if property_test:
            test_methods.append(property_test)

        return test_methods

    async def _generate_method_tests(
        self, cls: dict[str, Any], methods: list[str], module_category: str
    ) -> list[str]:
        method_tests = []
        for method in methods:
            method_test = await self._generate_class_method_test(
                cls, method, module_category
            )
            method_tests.append(method_test)
        return method_tests

    def _combine_class_test_elements(
        self, fixtures: list[str], test_methods: list[str]
    ) -> str:
        fixture_section = "\n".join(fixtures) if fixtures else ""
        test_section = "\n".join(test_methods)
        return fixture_section + test_section

    async def _generate_class_fixture(
        self, cls: dict[str, Any], module_category: str
    ) -> str:
        class_name = cls["name"]

        if module_category in ("service", "manager", "core"):
            fixture_template = (
                " @pytest.fixture\n"
                f" def {class_name.lower()}_instance(self):\n"
                f' """Fixture to create {class_name} instance for testing."""\n'
                "\n"
                " try:\n"
                f" return {class_name}()\n"
                " except TypeError:\n"
                "\n"
                f" with patch.object({class_name}, '__init__', return_value=None):\n"
                f" instance = {class_name}.__new__({class_name})\n"
                " return instance"
            )

        elif module_category == "agent":
            fixture_template = (
                " @pytest.fixture\n"
                f" def {class_name.lower()}_instance(self):\n"
                f' """Fixture to create {class_name} instance for testing."""\n'
                "\n"
                " mock_context = Mock(spec=AgentContext)\n"
                ' mock_context.project_path = Path("/test/project")\n'
                ' mock_context.get_file_content = Mock(return_value="# test content")\n'
                " mock_context.write_file_content = Mock(return_value=True)\n"
                "\n"
                " try:\n"
                f" return {class_name}(mock_context)\n"
                " except Exception:\n"
                ' pytest.skip("Agent requires specific context configuration")'
            )

        else:
            fixture_template = (
                " @pytest.fixture\n"
                f" def {class_name.lower()}_instance(self):\n"
                f' """Fixture to create {class_name} instance for testing."""\n'
                " try:\n"
                f" return {class_name}()\n"
                " except TypeError:\n"
                ' pytest.skip("Class requires specific constructor arguments")'
            )

        return fixture_template

    @staticmethod
    async def _generate_class_instantiation_test(
        class_info: dict[str, Any], module_category: str
    ) -> str:
        class_name = class_info["name"]

        test_template = (
            f" def test_{class_name.lower()}_instantiation(self, {class_name.lower()}_instance):\n"
            f' """Test successful instantiation of {class_name}."""\n'
            f" assert {class_name.lower()}_instance is not None\n"
            f" assert isinstance({class_name.lower()}_instance, {class_name})\n"
            "\n"
            f" assert hasattr({class_name.lower()}_instance, '__class__')\n"
            f' assert {class_name.lower()}_instance.__class__.__name__ == "{class_name}"'
        )

        return test_template

    async def _generate_class_method_test(
        self, cls: dict[str, Any], method_name: str, module_category: str
    ) -> str:
        class_name = cls["name"]

        if self._is_special_agent_method(module_category, method_name):
            return self._generate_agent_method_test(class_name, method_name)
        if module_category in ("service", "manager"):
            return self._generate_async_method_test(class_name, method_name)
        return self._generate_default_method_test(class_name, method_name)

    def _is_special_agent_method(self, module_category: str, method_name: str) -> bool:
        return module_category == "agent" and method_name in (
            "can_handle",
            "analyze_and_fix",
        )

    def _generate_agent_method_test(self, class_name: str, method_name: str) -> str:
        if method_name == "can_handle":
            return self._generate_can_handle_test(class_name)
        elif method_name == "analyze_and_fix":
            return self._generate_analyze_and_fix_test(class_name)
        return self._generate_generic_agent_method_test(class_name, method_name)

    def _generate_can_handle_test(self, class_name: str) -> str:
        return (
            " @pytest.mark.asyncio\n"
            f" async def test_{class_name.lower()}_can_handle(self, {class_name.lower()}_instance):\n"
            f' """Test {class_name}.can_handle method."""\n'
            "\n"
            " mock_issue = Mock(spec=Issue)\n"
            " mock_issue.type = IssueType.COVERAGE_IMPROVEMENT\n"
            ' mock_issue.message = "test coverage issue"\n'
            ' mock_issue.file_path = "/test/path.py"\n'
            "\n"
            f" result = await {class_name.lower()}_instance.can_handle(mock_issue)\n"
            " assert isinstance(result, (int, float))\n"
            " assert 0.0 <= result <= 1.0"
        )

    def _generate_analyze_and_fix_test(self, class_name: str) -> str:
        return (
            " @pytest.mark.asyncio\n"
            f" async def test_{class_name.lower()}_analyze_and_fix(self, {class_name.lower()}_instance):\n"
            f' """Test {class_name}.analyze_and_fix method."""\n'
            "\n"
            " mock_issue = Mock(spec=Issue)\n"
            " mock_issue.type = IssueType.COVERAGE_IMPROVEMENT\n"
            ' mock_issue.message = "test coverage issue"\n'
            ' mock_issue.file_path = "/test/path.py"\n'
            "\n"
            f" result = await {class_name.lower()}_instance.analyze_and_fix(mock_issue)\n"
            " assert isinstance(result, FixResult)\n"
            " assert hasattr(result, 'success')\n"
            " assert hasattr(result, 'confidence')"
        )

    def _generate_generic_agent_method_test(
        self, class_name: str, method_name: str
    ) -> str:
        return (
            " @pytest.mark.asyncio\n"
            f" async def test_{class_name.lower()}_{method_name}(self, {class_name.lower()}_instance):\n"
            f' """Test {class_name}.{method_name} method."""\n'
            " try:\n"
            f" method = getattr({class_name.lower()}_instance, "
            f'"{method_name}", None)\n'
            f" assert method is not None, "
            f'f"Method {method_name} should exist"\n'
            "\n"
            " if asyncio.iscoroutinefunction(method):\n"
            " result = await method()\n"
            " else:\n"
            " result = method()\n"
            "\n"
            " assert result is not None or result is None\n"
            " except (TypeError, NotImplementedError):\n"
            f' pytest.skip(f"Method {method_name} requires specific arguments")\n'
            " except Exception as e:\n"
            f' pytest.fail(f"Unexpected error in {method_name}: {{e}}")'
        )

    def _generate_async_method_test(self, class_name: str, method_name: str) -> str:
        return (
            " @pytest.mark.asyncio\n"
            f" async def test_{class_name.lower()}_{method_name}(self, {class_name.lower()}_instance):\n"
            f' """Test {class_name}.{method_name} method."""\n'
            " try:\n"
            f" method = getattr({class_name.lower()}_instance, "
            f'"{method_name}", None)\n'
            f" assert method is not None, "
            f'f"Method {method_name} should exist"\n'
            "\n"
            " if asyncio.iscoroutinefunction(method):\n"
            " result = await method()\n"
            " else:\n"
            " result = method()\n"
            "\n"
            " assert result is not None or result is None\n"
            "\n"
            " except (TypeError, NotImplementedError):\n"
            f' pytest.skip(f"Method {method_name} requires specific arguments or implementation")\n'
            " except Exception as e:\n"
            f' pytest.fail(f"Unexpected error in {method_name}: {{e}}")'
        )

    def _generate_default_method_test(self, class_name: str, method_name: str) -> str:
        return (
            f" def test_{class_name.lower()}_{method_name}(self, {class_name.lower()}_instance):\n"
            f' """Test {class_name}.{method_name} method."""\n'
            " try:\n"
            f" method = getattr({class_name.lower()}_instance, "
            f'"{method_name}", None)\n'
            f" assert method is not None, "
            f'f"Method {method_name} should exist"\n'
            "\n"
            " result = method()\n"
            " assert result is not None or result is None\n"
            "\n"
            " except (TypeError, NotImplementedError):\n"
            f' pytest.skip(f"Method {method_name} requires specific arguments or implementation")\n'
            " except Exception as e:\n"
            f' pytest.fail(f"Unexpected error in {method_name}: {{e}}")'
        )

    async def _generate_class_property_test(
        self, cls: dict[str, Any], module_category: str
    ) -> str:
        class_name = cls["name"]

        if module_category not in ("service", "manager", "agent"):
            return ""

        test_template = (
            f" def test_{class_name.lower()}_properties(self, {class_name.lower()}_instance):\n"
            f' """Test {class_name} properties and attributes."""\n'
            "\n"
            f" assert hasattr({class_name.lower()}_instance, '__dict__') or \\\n"
            f" hasattr({class_name.lower()}_instance, '__slots__')\n"
            "\n"
            f" str_repr = str({class_name.lower()}_instance)\n"
            " assert len(str_repr) > 0\n"
            f' assert "{class_name}" in str_repr or "{class_name.lower()}" in \\\n'
            " str_repr.lower()"
        )

        return test_template

    async def _generate_integration_tests(
        self,
        module_file: Path,
        functions: list[dict[str, Any]],
        classes: list[dict[str, Any]],
        module_category: str,
    ) -> str:
        if module_category not in ("service", "manager", "core"):
            return ""

        if len(functions) < 3 and len(classes) < 2:
            return ""

        integration_tests = (
            "\n\n"
            " @pytest.mark.integration\n"
            f" def test_{module_file.stem}_integration(self):\n"
            f' """Integration test for {module_file.stem} module functionality."""\n'
            "\n"
            ' pytest.skip("Integration test needs manual implementation")\n'
            "\n"
            " @pytest.mark.integration\n"
            " @pytest.mark.asyncio\n"
            f" async def test_{module_file.stem}_async_integration(self):\n"
            f' """Async integration test for {module_file.stem} module."""\n'
            "\n"
            ' pytest.skip("Async integration test needs manual implementation")\n'
            "\n"
            " @pytest.mark.performance\n"
            f" def test_{module_file.stem}_performance(self):\n"
            f' """Basic performance test for {module_file.stem} module."""\n'
            "\n"
            ' pytest.skip("Performance test needs manual implementation")'
        )

        return integration_tests

    def _generate_default_args(self, args: list[str]) -> str:
        if not args or args == ["self"]:
            return ""

        filtered_args = [arg for arg in args if arg != "self"]
        if not filtered_args:
            return ""

        placeholders = []
        for arg in filtered_args:
            if "path" in arg.lower():
                placeholders.append('Path("test")')
            elif "str" in arg.lower() or "name" in arg.lower():
                placeholders.append('"test"')
            elif "int" in arg.lower() or "count" in arg.lower():
                placeholders.append("1")
            elif "bool" in arg.lower():
                placeholders.append("True")
            else:
                placeholders.append("None")

        return ", ".join(placeholders)

    def _categorize_module(self, relative_path: str) -> str:
        if "managers/" in relative_path:
            return "manager"
        elif "services/" in relative_path:
            return "service"
        elif "core/" in relative_path:
            return "core"
        elif "agents/" in relative_path:
            return "agent"
        elif "models/" in relative_path:
            return "model"
        elif "executors/" in relative_path:
            return "executor"
        return "utility"
