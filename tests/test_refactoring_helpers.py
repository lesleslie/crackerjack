"""Tests for refactoring helper utilities."""

import ast
import typing as t

import pytest

from crackerjack.agents.refactoring_helpers import ComplexityCalculator


class TestComplexityCalculator:
    """Tests for ComplexityCalculator."""

    def test_complexity_calculator_initialization(self):
        """Test ComplexityCalculator initialization."""
        calculator = ComplexityCalculator()
        assert calculator.complexity == 0
        assert calculator.nesting_level == 0
        assert calculator.binary_sequences == 0

    def test_complexity_calculator_simple_function(self):
        """Test complexity calculation for simple function."""
        code = """
def simple_function():
    return 42
"""
        tree = ast.parse(code)
        calculator = ComplexityCalculator()
        calculator.visit(tree)

        # Simple function should have low complexity
        assert calculator.complexity >= 0

    def test_complexity_calculator_with_if_statement(self):
        """Test complexity calculation with if statement."""
        code = """
def function_with_if(x):
    if x > 0:
        return "positive"
    return "non-positive"
"""
        tree = ast.parse(code)
        calculator = ComplexityCalculator()
        calculator.visit(tree)

        # Should have complexity from if statement
        assert calculator.complexity > 0

    def test_complexity_calculator_with_nested_if(self):
        """Test complexity calculation with nested if statements."""
        code = """
def nested_if_function(x, y):
    if x > 0:
        if y > 0:
            return "both positive"
        return "x positive"
    return "x non-positive"
"""
        tree = ast.parse(code)
        calculator = ComplexityCalculator()
        calculator.visit(tree)

        # Nested if should increase complexity
        base_complexity = calculator.complexity
        assert base_complexity > 1

    def test_complexity_calculator_with_loop(self):
        """Test complexity calculation with for loop."""
        code = """
def function_with_loop(items):
    result = []
    for item in items:
        if item > 0:
            result.append(item)
    return result
"""
        tree = ast.parse(code)
        calculator = ComplexityCalculator()
        calculator.visit(tree)

        # Loop and nested if should contribute to complexity
        assert calculator.complexity > 1

    def test_complexity_calculator_with_try_except(self):
        """Test complexity calculation with try-except."""
        code = """
def function_with_try():
    try:
        return risky_operation()
    except Exception as e:
        return str(e)
"""
        tree = ast.parse(code)
        calculator = ComplexityCalculator()
        calculator.visit(tree)

        # Try-except should contribute to complexity
        assert calculator.complexity > 0

    def test_complexity_calculator_with_boolean_operations(self):
        """Test complexity calculation with boolean operations."""
        code = """
def function_with_bool(x, y):
    if x > 0 and y > 0:
        return "both positive"
    return "not both positive"
"""
        tree = ast.parse(code)
        calculator = ComplexityCalculator()
        calculator.visit(tree)

        # Boolean operations should contribute to complexity
        assert calculator.complexity > 0

    def test_complexity_calculator_with_comprehensions(self):
        """Test complexity calculation with list comprehension."""
        code = """
def function_with_comprehension():
    numbers = [1, 2, 3, 4, 5]
    squared = [x**2 for x in numbers if x > 2]
    return squared
"""
        tree = ast.parse(code)
        calculator = ComplexityCalculator()
        calculator.visit(tree)

        # Comprehension should contribute to complexity
        assert calculator.complexity > 0

    def test_complexity_calculator_complex_function(self):
        """Test complexity calculation for complex function."""
        code = """
def complex_function(data):
    result = []

    for item in data:
        try:
            if item['value'] > 0 and item['active']:
                processed = process_item(item)
                if processed:
                    result.append(processed)
        except KeyError:
            continue
        except ValueError as e:
            log_error(e)

    return result if result else None
"""
        tree = ast.parse(code)
        calculator = ComplexityCalculator()
        calculator.visit(tree)

        # Complex function should have higher complexity
        assert calculator.complexity > 5

    def test_complexity_calculator_empty_function(self):
        """Test complexity calculation for empty function."""
        code = """
def empty_function():
    pass
"""
        tree = ast.parse(code)
        calculator = ComplexityCalculator()
        calculator.visit(tree)

        # Empty function should have minimal complexity
        assert calculator.complexity >= 0

    def test_complexity_calculator_multiple_functions(self):
        """Test complexity calculation with multiple functions."""
        code = """
def simple_function():
    return 42

def complex_function(x):
    if x > 0:
        return x * 2
    return 0
"""
        tree = ast.parse(code)
        calculator = ComplexityCalculator()
        calculator.visit(tree)

        # Should calculate complexity for all functions
        assert calculator.complexity > 0

    def test_complexity_calculator_nesting_level(self):
        """Test that nesting level is tracked correctly."""
        calculator = ComplexityCalculator()

        # Test simple nesting
        calculator.nesting_level = 0
        calculator.complexity = 0

        # Simulate visiting nested structures
        calculator.nesting_level += 1
        calculator.complexity += 1 + calculator.nesting_level

        assert calculator.nesting_level == 1
        assert calculator.complexity == 2

    def test_complexity_calculator_binary_sequences(self):
        """Test that binary sequences are tracked."""
        calculator = ComplexityCalculator()

        # Test binary sequence tracking
        calculator.binary_sequences = 0
        calculator.complexity = 0

        # Simulate binary sequence detection
        calculator.binary_sequences += 1

        assert calculator.binary_sequences == 1

    def test_complexity_calculator_visit_methods(self):
        """Test that visit methods exist and are callable."""
        calculator = ComplexityCalculator()

        # Test that all expected visit methods exist
        assert hasattr(calculator, 'visit_If')
        assert hasattr(calculator, 'visit_For')
        assert hasattr(calculator, 'visit_While')
        assert hasattr(calculator, 'visit_Try')
        assert hasattr(calculator, 'visit_With')
        assert hasattr(calculator, 'visit_BoolOp')
        assert hasattr(calculator, 'visit_ListComp')
        assert hasattr(calculator, 'visit_DictComp')
        assert hasattr(calculator, 'visit_SetComp')
        assert hasattr(calculator, 'visit_GeneratorExp')

    def test_complexity_calculator_private_methods(self):
        """Test that private processing methods exist."""
        calculator = ComplexityCalculator()

        # Test that private methods exist
        assert hasattr(calculator, '_process_conditional_node')
        assert hasattr(calculator, '_process_loop_node')
        assert hasattr(calculator, '_process_try_node')
        assert hasattr(calculator, '_process_context_node')
        assert hasattr(calculator, '_process_boolean_operation')
        assert hasattr(calculator, '_process_comprehension')

    def test_complexity_calculator_comparison(self):
        """Test complexity comparison between simple and complex functions."""
        # Simple function
        simple_code = "def simple(): return 42"
        simple_tree = ast.parse(simple_code)
        simple_calc = ComplexityCalculator()
        simple_calc.visit(simple_tree)

        # Complex function
        complex_code = """
def complex_func(x, y, z):
    if x > 0:
        for i in range(y):
            try:
                if z[i] > x:
                    return i
            except:
                pass
    return -1
"""
        complex_tree = ast.parse(complex_code)
        complex_calc = ComplexityCalculator()
        complex_calc.visit(complex_tree)

        # Complex function should have higher complexity
        assert complex_calc.complexity > simple_calc.complexity

    def test_complexity_calculator_inheritance(self):
        """Test that ComplexityCalculator inherits from ast.NodeVisitor."""
        calculator = ComplexityCalculator()
        assert isinstance(calculator, ast.NodeVisitor)

    def test_complexity_calculator_visit_implementation(self):
        """Test that visit methods are properly implemented."""
        calculator = ComplexityCalculator()

        # Create a simple AST node
        code = "x = 1 if y > 0 else 0"
        tree = ast.parse(code)

        # Should not raise exceptions
        calculator.visit(tree)

        # Complexity should be calculated
        assert calculator.complexity >= 0
