"""Test cases for multiline function definitions in docstring removal."""

import ast

from rich.console import Console
from crackerjack.crackerjack import CodeCleaner


class TestMultilineFunctions:
    def setup_method(self) -> None:
        self.console = Console()
        self.cleaner = CodeCleaner(console=self.console)

    def test_multiline_async_function_with_docstring(self) -> None:
        code = """class BackgroundTaskManager:
    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: t.Any | None,
    ) -> None:
        del exc_type, exc_val, exc_tb
        self.logger.debug("Background task manager shutting down")
        await wait_for_background_tasks(self.cleanup_timeout)
"""
        result = self.cleaner.remove_docstrings(code)
        ast.parse(result)
        assert '"""Clean up background tasks on exit."""' not in result
        assert "del exc_type, exc_val, exc_tb" in result
        assert "self.logger.debug" in result

    def test_multiline_function_with_docstring(self) -> None:
        code = '''def complex_function(
        param1: str,
        param2: int,
        param3: dict[str, Any],
    ) -> bool:
        """This is a complex function with multiple parameters."""
        return True
'''
        result = self.cleaner.remove_docstrings(code)
        ast.parse(result)
        assert (
            '"""This is a complex function with multiple parameters."""' not in result
        )
        assert "return True" in result

    def test_multiline_function_no_docstring(self) -> None:
        code = """def complex_function(
        param1: str,
        param2: int,
        param3: dict[str, Any],
    ) -> bool:
        return True
"""
        result = self.cleaner.remove_docstrings(code)
        ast.parse(result)
        assert "return True" in result
        assert "def complex_function(" in result

    def test_nested_multiline_functions(self) -> None:
        code = """class TestClass:
    def outer_method(
        self,
        param: str,
    ) -> None:
        def inner_function(
            x: int,
            y: int,
        ) -> int:
            return x + y
        return inner_function(1, 2)
"""
        result = self.cleaner.remove_docstrings(code)
        ast.parse(result)
        assert '"""Outer method docstring."""' not in result
        assert '"""Inner function docstring."""' not in result
        assert "return x + y" in result
        assert "return inner_function(1, 2)" in result

    def test_multiline_function_with_decorators(self) -> None:
        code = """class TestClass:
    @property
    @some_decorator(
        param1="value1",
        param2="value2"
    )
    def complex_property(
        self,
    ) -> str:
        return "test"
"""
        result = self.cleaner.remove_docstrings(code)
        ast.parse(result)
        assert (
            '"""Property with complex decorator and multiline signature."""'
            not in result
        )
        assert "@property" in result
        assert "@some_decorator" in result
        assert 'return "test"' in result

    def test_class_with_multiline_init(self) -> None:
        code = '''class ComplexClass:
    """Class docstring."""
    def __init__(
        self,
        param1: str,
        param2: int = 42,
        param3: Optional[dict] = None,
    ) -> None:
        self.param1 = param1
        self.param2 = param2
        self.param3 = param3 or {}
'''
        result = self.cleaner.remove_docstrings(code)
        ast.parse(result)
        assert '"""Class docstring."""' not in result
        assert '"""Initialize the complex class."""' not in result
        assert "self.param1 = param1" in result
        assert "self.param2 = param2" in result
        assert "self.param3 = param3 or {}" in result

    def test_multiline_function_empty_body_gets_pass(self) -> None:
        code = '''def empty_function(
        param1: str,
        param2: int,
    ) -> None:
        """This function only has a docstring."""
'''
        result = self.cleaner.remove_docstrings(code)
        ast.parse(result)
        assert '"""This function only has a docstring."""' not in result
        assert "pass" in result

    def test_complex_real_world_example(self) -> None:
        code = '''class BackgroundTaskManager:
    """Manage background tasks."""
    def __init__(self, cleanup_timeout: float = 30.0) -> None:
        self.cleanup_timeout = cleanup_timeout
        self.logger = depends.get(Logger)
    async def __aenter__(self) -> "BackgroundTaskManager":
        self.logger.debug("Background task manager started")
        return self
    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: t.Any | None,
    ) -> None:
        del exc_type, exc_val, exc_tb
        self.logger.debug("Background task manager shutting down")
        await wait_for_background_tasks(self.cleanup_timeout)
'''
        result = self.cleaner.remove_docstrings(code)
        ast.parse(result)
        assert '"""Manage background tasks."""' not in result
        assert '"""Initialize the background task manager."""' not in result
        assert '"""Enter async context."""' not in result
        assert '"""Clean up background tasks on exit."""' not in result
        assert "self.cleanup_timeout = cleanup_timeout" in result
        assert 'self.logger.debug("Background task manager started")' in result
        assert "del exc_type, exc_val, exc_tb" in result
        assert "await wait_for_background_tasks" in result
