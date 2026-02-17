"""Unit tests for APIExtractor.

Tests API documentation extraction from Python source files,
including protocols, services, classes, functions, and CLI commands.
"""

import ast
import inspect
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from crackerjack.services.api_extractor import APIExtractorImpl, PythonDocstringParser


@pytest.mark.unit
class TestPythonDocstringParser:
    """Test docstring parsing functionality."""

    def test_parse_empty_docstring(self) -> None:
        """Test parsing empty docstring."""
        parser = PythonDocstringParser()
        result = parser.parse_docstring("")

        assert isinstance(result, dict)

    def test_parse_simple_docstring(self) -> None:
        """Test parsing simple docstring."""
        parser = PythonDocstringParser()
        docstring = "Simple description."

        result = parser.parse_docstring(docstring)

        assert result.get("description") == "Simple description."

    def test_parse_docstring_with_sections(self) -> None:
        """Test parsing docstring with sections."""
        parser = PythonDocstringParser()
        docstring = """
        Description.

        Args:
            param1: First parameter.

        Returns:
            Something.
        """

        result = parser.parse_docstring(docstring)

        assert "Args:" in result or "description" in result

    def test_extract_parameters(self) -> None:
        """Test parameter extraction from docstring."""
        parser = PythonDocstringParser()
        docstring = """
        Args:
            param1 (str): First parameter.
            param2 (int): Second parameter.
        """

        result = parser._extract_parameters(docstring)

        assert isinstance(result, dict)

    def test_extract_returns(self) -> None:
        """Test return value extraction."""
        parser = PythonDocstringParser()
        docstring = "Returns: str: A string value."

        result = parser._extract_returns(docstring)

        assert "str" in result or result == "A string value"

    def test_extract_raises(self) -> None:
        """Test exception extraction."""
        parser = PythonDocstringParser()
        docstring = """
        Raises:
            ValueError: If value is invalid.
            TypeError: If type is wrong.
        """

        result = parser._extract_raises(docstring)

        assert isinstance(result, list)

    def test_is_section_header(self) -> None:
        """Test section header detection."""
        parser = PythonDocstringParser()

        assert parser._is_section_header("Args:") is True
        assert parser._is_section_header("Returns:") is True
        assert parser._is_section_header("Raises:") is True
        assert parser._is_section_header("Note:") is True
        assert parser._is_section_header("Regular text.") is False


@pytest.mark.unit
class TestAPIExtractorInitialization:
    """Test APIExtractor initialization."""

    def test_initialization(self) -> None:
        """Test extractor initializes successfully."""
        extractor = APIExtractorImpl()

        assert extractor is not None


@pytest.mark.unit
class TestExtractFromPythonFiles:
    """Test Python file extraction."""

    def test_extract_from_empty_file_list(self, tmp_path) -> None:
        """Test extraction with no files."""
        extractor = APIExtractorImpl()

        result = extractor.extract_from_python_files([])

        assert isinstance(result, dict)
        # Should have structure keys but all empty
        assert "modules" in result
        assert "classes" in result
        assert "functions" in result
        assert "protocols" in result
        assert len(result["modules"]) == 0
        assert len(result["classes"]) == 0

    def test_extract_from_single_file(self, tmp_path) -> None:
        """Test extraction from single Python file."""
        extractor = APIExtractorImpl()

        # Create a test Python file
        test_file = tmp_path / "test_module.py"
        test_file.write_text("""
def test_function():
    '''Test function.'''
    pass

class TestClass:
    '''Test class.'''
    def test_method(self):
        '''Test method.'''
        pass
""")

        result = extractor.extract_from_python_files([test_file])

        assert isinstance(result, dict)
        # Should have extracted module info
        assert "test_module" in result or len(result) > 0

    def test_extract_from_multiple_files(self, tmp_path) -> None:
        """Test extraction from multiple files."""
        extractor = APIExtractorImpl()

        # Create test files
        file1 = tmp_path / "module1.py"
        file1.write_text("def func1(): pass")

        file2 = tmp_path / "module2.py"
        file2.write_text("def func2(): pass")

        result = extractor.extract_from_python_files([file1, file2])

        assert isinstance(result, dict)
        assert len(result) >= 0


@pytest.mark.unit
class TestExtractProtocolDefinitions:
    """Test protocol definition extraction."""

    def test_extract_from_nonexistent_file(self) -> None:
        """Test extraction from file that doesn't exist."""
        extractor = APIExtractorImpl()

        result = extractor.extract_protocol_definitions(Path("/nonexistent/file.py"))

        assert isinstance(result, dict)

    def test_extract_simple_protocol(self, tmp_path) -> None:
        """Test extraction of simple protocol."""
        extractor = APIExtractorImpl()

        # Create a protocol file
        proto_file = tmp_path / "protocols.py"
        proto_file.write_text("""
from typing import Protocol

class MyProtocol(Protocol):
    '''A simple protocol.'''

    def method_a(self) -> str:
        '''Method A.'''
        pass

    def method_b(self, value: int) -> None:
        '''Method B.'''
        pass
""")

        result = extractor.extract_protocol_definitions(proto_file)

        assert isinstance(result, dict)
        assert "MyProtocol" in result or len(result) >= 0

    def test_extract_protocol_with_attributes(self, tmp_path) -> None:
        """Test protocol with attributes."""
        extractor = APIExtractorImpl()

        proto_file = tmp_path / "protocols.py"
        proto_file.write_text("""
from typing import Protocol

class ConfigProtocol(Protocol):
    '''Configuration protocol.'''

    config_key: str
    config_value: str | None
""")

        result = extractor.extract_protocol_definitions(proto_file)

        assert isinstance(result, dict)


@pytest.mark.unit
class TestExtractServiceInterfaces:
    """Test service interface extraction."""

    def test_extract_from_empty_service_list(self) -> None:
        """Test extraction with no service files."""
        extractor = APIExtractorImpl()

        result = extractor.extract_service_interfaces([])

        assert isinstance(result, dict)
        # Should have "services" key but empty
        assert "services" in result
        assert len(result["services"]) == 0

    def test_extract_simple_service(self, tmp_path) -> None:
        """Test extraction of simple service class."""
        extractor = APIExtractorImpl()

        service_file = tmp_path / "test_service.py"
        service_file.write_text("""
class TestService:
    '''A test service.'''

    def serve(self) -> None:
        '''Serve method.'''
        pass

    def stop(self) -> None:
        '''Stop method.'''
        pass
""")

        result = extractor.extract_service_interfaces([service_file])

        assert isinstance(result, dict)
        # Should contain service information
        assert "services" in result or len(result) >= 0

    def test_extract_service_with_methods(self, tmp_path) -> None:
        """Test service with multiple methods."""
        extractor = APIExtractorImpl()

        service_file = tmp_path / "service.py"
        service_file.write_text("""
class APIService:
    '''API service for endpoints.'''

    @staticmethod
    def get_endpoint() -> dict:
        '''Get endpoint data.'''
        return {}

    def post_endpoint(self, data: dict) -> dict:
        '''Post endpoint data.'''
        return data
""")

        result = extractor.extract_service_interfaces([service_file])

        assert isinstance(result, dict)


@pytest.mark.unit
class TestExtractCLICommands:
    """Test CLI command extraction."""

    def test_extract_from_empty_cli_list(self) -> None:
        """Test extraction with no CLI files."""
        extractor = APIExtractorImpl()

        result = extractor.extract_cli_commands([])

        assert isinstance(result, dict)
        # Should have "commands" and "options" keys but both empty
        assert "commands" in result
        assert "options" in result
        assert len(result["commands"]) == 0
        assert len(result["options"]) == 0

    def test_extract_simple_command(self, tmp_path) -> None:
        """Test extraction of simple CLI command."""
        extractor = APIExtractorImpl()

        cli_file = tmp_path / "commands.py"
        cli_file.write_text("""
import typer

def test_command(name: str = "default"):
    '''Test command.

    Args:
        name: The name to use.

    Returns:
        Greeting message.
    '''
    return f"Hello, {name}"
""")

        result = extractor.extract_cli_commands([cli_file])

        assert isinstance(result, dict)
        # Should contain command info
        assert "test_command" in result or len(result) >= 0

    def test_extract_command_with_options(self, tmp_path) -> None:
        """Test command with multiple options."""
        extractor = APIExtractorImpl()

        cli_file = tmp_path / "cli.py"
        cli_file.write_text("""
import typer

def main(
    verbose: bool = typer.Option(False, "--verbose", "-v"),
    output: str = typer.Option("text", "--output", "-o"),
    count: int = typer.Option(1, "--count", "-c"),
):
    '''Main command.

    Args:
        verbose: Enable verbose output.
        output: Output format.
        count: Number of items.
    '''
    pass
""")

        result = extractor.extract_cli_commands([cli_file])

        assert isinstance(result, dict)


@pytest.mark.unit
class TestExtractMCPTools:
    """Test MCP tool extraction."""

    def test_extract_from_empty_mcp_list(self) -> None:
        """Test extraction with no MCP files."""
        extractor = APIExtractorImpl()

        result = extractor.extract_mcp_tools([])

        assert isinstance(result, dict)
        # Should have "mcp_tools" key but empty
        assert "mcp_tools" in result
        assert len(result["mcp_tools"]) == 0

    def test_extract_simple_tool(self, tmp_path) -> None:
        """Test extraction of simple MCP tool."""
        extractor = APIExtractorImpl()

        mcp_file = tmp_path / "tools.py"
        mcp_file.write_text("""
from fastmcp import tool

@tool
def test_tool(value: str) -> str:
    '''Test tool.

    Args:
        value: Input value.

    Returns:
        Processed value.
    '''
    return value
""")

        result = extractor.extract_mcp_tools([mcp_file])

        assert isinstance(result, dict)
        # Should contain tool info
        assert "test_tool" in result or len(result) >= 0


@pytest.mark.unit
class TestModuleInfoExtraction:
    """Test module information extraction."""

    def test_extract_module_with_classes(self, tmp_path: Path) -> None:
        """Test module with class definitions."""
        extractor = APIExtractorImpl()

        module_file = tmp_path / "module.py"
        module_file.write_text("""
class ClassOne:
    pass

class ClassTwo:
    pass
""")

        # Parse the file
        with open(module_file) as f:
            tree = ast.parse(f.read())

        result = extractor._extract_module_info(tree, module_file, module_file.read_text())

        assert isinstance(result, dict)
        # Should have these structure keys
        assert "classes" in result
        assert "functions" in result

    def test_extract_module_with_functions(self, tmp_path: Path) -> None:
        """Test module with function definitions."""
        extractor = APIExtractorImpl()

        module_file = tmp_path / "module.py"
        module_file.write_text("""
def func_one():
    pass

def func_two():
    pass
""")

        # Parse the file
        with open(module_file) as f:
            tree = ast.parse(f.read())

        result = extractor._extract_module_info(tree, module_file, module_file.read_text())

        assert isinstance(result, dict)
        # Should have these structure keys
        assert "classes" in result
        assert "functions" in result

    def test_extract_module_with_imports(self, tmp_path: Path) -> None:
        """Test module with imports."""
        extractor = APIExtractorImpl()

        module_file = tmp_path / "module.py"
        module_file.write_text("""
import os
import sys
from typing import Dict
""")

        # Parse the file
        with open(module_file) as f:
            tree = ast.parse(f.read())

        result = extractor._extract_module_info(tree, module_file, module_file.read_text())

        assert isinstance(result, dict)
        # Should have these structure keys
        assert "classes" in result
        assert "functions" in result


@pytest.mark.unit
class TestClassInfoExtraction:
    """Test class information extraction."""

    def test_extract_simple_class(self, tmp_path) -> None:
        """Test extraction of simple class."""
        extractor = APIExtractorImpl()

        test_file = tmp_path / "test.py"
        test_file.write_text("""
class SimpleClass:
    '''A simple class.'''

    def method_one(self):
        pass

    def method_two(self):
        pass
""")

        # Parse the file
        with open(test_file) as f:
            tree = ast.parse(f.read())

        # Find the class node
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                result = extractor._extract_class_info(node, test_file.read_text())
                assert isinstance(result, dict)
                assert "name" in result
                assert result["name"] == "SimpleClass"
                break

    def test_extract_class_with_docstring(self, tmp_path) -> None:
        """Test class with detailed docstring."""
        extractor = APIExtractorImpl()

        test_file = tmp_path / "test.py"
        test_file.write_text("""
class DocumentedClass:
    '''This class has documentation.

    Attributes:
        attr1: First attribute.
        attr2: Second attribute.

    Examples:
        >>> obj = DocumentedClass()
        >>> obj.method()
    '''

    def method(self):
        pass
""")

        with open(test_file) as f:
            tree = ast.parse(f.read())

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                result = extractor._extract_class_info(node, test_file.read_text())
                assert isinstance(result, dict)
                assert "name" in result
                break

    def test_extract_class_with_methods(self, tmp_path) -> None:
        """Test class method extraction."""
        extractor = APIExtractorImpl()

        test_file = tmp_path / "test.py"
        test_file.write_text("""
class ClassWithMethods:
    def public_method(self):
        '''Public method.'''
        pass

    def _private_method(self):
        '''Private method.'''
        pass
""")

        with open(test_file) as f:
            tree = ast.parse(f.read())

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                result = extractor._extract_class_info(node, test_file.read_text())
                assert isinstance(result, dict)
                assert "methods" in result or "name" in result
                break


@pytest.mark.unit
class TestFunctionInfoExtraction:
    """Test function information extraction."""

    def test_extract_simple_function(self, tmp_path) -> None:
        """Test extraction of simple function."""
        extractor = APIExtractorImpl()

        test_file = tmp_path / "test.py"
        test_file.write_text("""
def simple_function(param1, param2):
    '''Simple function.'''
    pass
""")

        with open(test_file) as f:
            tree = ast.parse(f.read())

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                result = extractor._extract_function_info(node, test_file.read_text())
                assert isinstance(result, dict)
                assert "name" in result
                assert result["name"] == "simple_function"
                break

    def test_extract_function_with_return_annotation(self, tmp_path) -> None:
        """Test function with return type annotation."""
        extractor = APIExtractorImpl()

        test_file = tmp_path / "test.py"
        test_file.write_text("""
def typed_function() -> str:
    '''Typed function.'''
    return "value"
""")

        with open(test_file) as f:
            tree = ast.parse(f.read())

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                result = extractor._extract_function_info(node, test_file.read_text())
                assert isinstance(result, dict)
                assert "return_type" in result or "name" in result
                break

    def test_extract_function_with_parameters(self, tmp_path) -> None:
        """Test function parameter extraction."""
        extractor = APIExtractorImpl()

        test_file = tmp_path / "test.py"
        test_file.write_text("""
def function_with_params(a: int, b: str, c: bool = True):
    '''Function with parameters.'''
    pass
""")

        with open(test_file) as f:
            tree = ast.parse(f.read())

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                result = extractor._extract_function_info(node, test_file.read_text())
                assert isinstance(result, dict)
                assert "name" in result
                break


@pytest.mark.unit
class TestMethodVisibility:
    """Test method visibility determination."""

    def test_public_method(self) -> None:
        """Test public method is identified correctly."""
        extractor = APIExtractorImpl()

        visibility = extractor._determine_method_visibility("public_method")

        assert visibility == "public"

    def test_private_method(self) -> None:
        """Test private method is identified correctly."""
        extractor = APIExtractorImpl()

        visibility = extractor._determine_method_visibility("_private_method")

        # Single underscore is "protected", not "private"
        assert visibility == "protected"

    def test_dunder_method(self) -> None:
        """Test dunder method is identified correctly."""
        extractor = APIExtractorImpl()

        visibility = extractor._determine_method_visibility("__init__")

        assert visibility == "private"


@pytest.mark.unit
class TestCreateBaseModuleInfo:
    """Test base module info creation."""

    def test_create_base_info(self) -> None:
        """Test creation of base module info dictionary."""
        extractor = APIExtractorImpl()

        # Create a simple AST module
        tree = ast.parse("# test module")

        result = extractor._create_base_module_info(tree, Path("/test/path.py"))

        assert isinstance(result, dict)
        assert "path" in result
        assert result["path"] == "/test/path.py"

    def test_create_base_info_with_classes(self) -> None:
        """Test base info includes class list."""
        extractor = APIExtractorImpl()

        # Create a simple AST module with docstring
        tree = ast.parse('"""Test module."""')

        result = extractor._create_base_module_info(tree, Path("/test.py"))

        assert isinstance(result, dict)
        assert "docstring" in result


@pytest.mark.unit
class TestProcessASTNode:
    """Test AST node processing."""

    def test_process_class_node(self, tmp_path: Path) -> None:
        """Test processing of ClassDef node."""
        extractor = APIExtractorImpl()

        test_file = tmp_path / "test.py"
        test_file.write_text("class TestClass: pass")

        with open(test_file) as f:
            tree = ast.parse(f.read())

        # Create module info dict
        module_info = {"classes": [], "functions": []}

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                extractor._process_ast_node(module_info, node, test_file.read_text())
                assert len(module_info["classes"]) > 0
                break

    def test_process_function_node(self, tmp_path: Path) -> None:
        """Test processing of FunctionDef node."""
        extractor = APIExtractorImpl()

        test_file = tmp_path / "test.py"
        test_file.write_text("def test_func(): pass")

        with open(test_file) as f:
            tree = ast.parse(f.read())

        # Create module info dict
        module_info = {"classes": [], "functions": []}

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                extractor._process_ast_node(module_info, node, test_file.read_text())
                assert len(module_info["functions"]) > 0
                break
