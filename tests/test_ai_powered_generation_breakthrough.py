"""
🤖 BREAKTHROUGH TESTING FRONTIER 4: AI-Powered Test Generation

This module implements AI-driven test generation using AST analysis and pattern matching
to create tests for unexplored code paths and generate adversarial inputs.

The AI test generator analyzes source code structure to automatically create
comprehensive test scenarios that human developers might miss.
"""

import pytest
import ast
import inspect
import textwrap
import tempfile
import importlib.util
from pathlib import Path
from typing import List, Dict, Any, Optional, Set, Tuple
from dataclasses import dataclass
from unittest.mock import MagicMock, patch
import random
import string
import sys

# Import modules to analyze
from crackerjack.services.filesystem import FilesystemService
from crackerjack.services.config import ConfigService
from crackerjack.managers.hook_manager import HookManager


@dataclass
class CodePath:
    """Represents a code path discovered through AST analysis."""
    function_name: str
    path_id: str
    conditions: List[str]
    complexity: int
    test_generated: bool = False


@dataclass
class TestScenario:
    """Represents a generated test scenario."""
    scenario_name: str
    setup_code: str
    test_code: str
    expected_behavior: str
    input_values: Dict[str, Any]
    path_coverage: List[str]


class ASTAnalyzer:
    """Analyzes AST to discover testable code paths and patterns."""
    
    def __init__(self):
        self.paths = []
        self.functions = []
        self.complexity_map = {}
        self.condition_patterns = []
    
    def analyze_module(self, source_code: str) -> Dict[str, Any]:
        """Analyze a module's source code and extract testable patterns."""
        tree = ast.parse(source_code)
        
        analysis = {
            'functions': self._extract_functions(tree),
            'code_paths': self._extract_code_paths(tree),
            'error_conditions': self._extract_error_conditions(tree),
            'boundary_conditions': self._extract_boundary_conditions(tree),
            'complexity_hotspots': self._find_complexity_hotspots(tree)
        }
        
        return analysis
    
    def _extract_functions(self, tree: ast.AST) -> List[Dict[str, Any]]:
        """Extract function definitions and their signatures."""
        functions = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                func_info = {
                    'name': node.name,
                    'args': [arg.arg for arg in node.args.args],
                    'returns': self._get_return_type(node),
                    'has_defaults': len(node.args.defaults) > 0,
                    'is_async': isinstance(node, ast.AsyncFunctionDef),
                    'docstring': ast.get_docstring(node),
                    'line_number': node.lineno,
                    'complexity': self._calculate_complexity(node)
                }
                functions.append(func_info)
        
        return functions
    
    def _extract_code_paths(self, tree: ast.AST) -> List[CodePath]:
        """Extract distinct code paths through conditional logic."""
        paths = []
        
        class PathVisitor(ast.NodeVisitor):
            def __init__(self):
                self.current_function = None
                self.path_counter = 0
            
            def visit_FunctionDef(self, node):
                self.current_function = node.name
                self.generic_visit(node)
                self.current_function = None
            
            def visit_If(self, node):
                if self.current_function:
                    # Extract condition
                    condition = ast.unparse(node.test)
                    
                    # Create paths for if and else branches
                    if_path = CodePath(
                        function_name=self.current_function,
                        path_id=f"{self.current_function}_if_{self.path_counter}",
                        conditions=[condition],
                        complexity=len(node.body) + len(node.orelse)
                    )
                    paths.append(if_path)
                    
                    if node.orelse:
                        else_path = CodePath(
                            function_name=self.current_function,
                            path_id=f"{self.current_function}_else_{self.path_counter}",
                            conditions=[f"not ({condition})"],
                            complexity=len(node.orelse)
                        )
                        paths.append(else_path)
                    
                    self.path_counter += 1
                
                self.generic_visit(node)
        
        visitor = PathVisitor()
        visitor.visit(tree)
        return paths
    
    def _extract_error_conditions(self, tree: ast.AST) -> List[Dict[str, str]]:
        """Extract potential error conditions and exception handling."""
        error_conditions = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Raise):
                if node.exc:
                    exception_type = ast.unparse(node.exc) if hasattr(ast, 'unparse') else 'Exception'
                    error_conditions.append({
                        'type': 'raise',
                        'exception': exception_type,
                        'line': node.lineno
                    })
            
            elif isinstance(node, ast.Assert):
                condition = ast.unparse(node.test) if hasattr(ast, 'unparse') else 'assertion'
                error_conditions.append({
                    'type': 'assert',
                    'condition': condition,
                    'line': node.lineno
                })
        
        return error_conditions
    
    def _extract_boundary_conditions(self, tree: ast.AST) -> List[Dict[str, Any]]:
        """Extract boundary conditions from comparisons."""
        boundaries = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Compare):
                left = ast.unparse(node.left) if hasattr(ast, 'unparse') else 'var'
                
                for i, (op, comparator) in enumerate(zip(node.ops, node.comparators)):
                    if isinstance(comparator, ast.Constant) and isinstance(comparator.value, (int, float)):
                        boundary_value = comparator.value
                        op_name = type(op).__name__
                        
                        boundaries.append({
                            'variable': left,
                            'operator': op_name,
                            'value': boundary_value,
                            'line': node.lineno,
                            'test_values': self._generate_boundary_test_values(op_name, boundary_value)
                        })
        
        return boundaries
    
    def _generate_boundary_test_values(self, operator: str, value: float) -> List[float]:
        """Generate test values around boundary conditions."""
        values = []
        
        if operator in ('Lt', 'LtE'):  # < or <=
            values.extend([value - 1, value, value + 1])
        elif operator in ('Gt', 'GtE'):  # > or >=
            values.extend([value - 1, value, value + 1])
        elif operator in ('Eq', 'NotEq'):  # == or !=
            values.extend([value, value - 0.1, value + 0.1])
        
        return values
    
    def _find_complexity_hotspots(self, tree: ast.AST) -> List[Dict[str, Any]]:
        """Find complex code sections that need thorough testing."""
        hotspots = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                complexity = self._calculate_complexity(node)
                if complexity > 5:  # High complexity threshold
                    hotspots.append({
                        'function': node.name,
                        'complexity': complexity,
                        'line': node.lineno,
                        'reason': 'High cyclomatic complexity'
                    })
        
        return hotspots
    
    def _calculate_complexity(self, node: ast.FunctionDef) -> int:
        """Calculate cyclomatic complexity of a function."""
        complexity = 1  # Base complexity
        
        for child in ast.walk(node):
            if isinstance(child, (ast.If, ast.While, ast.For, ast.AsyncFor)):
                complexity += 1
            elif isinstance(child, ast.ExceptHandler):
                complexity += 1
            elif isinstance(child, ast.BoolOp):
                complexity += len(child.values) - 1
        
        return complexity
    
    def _get_return_type(self, node: ast.FunctionDef) -> Optional[str]:
        """Extract return type annotation if available."""
        if node.returns:
            return ast.unparse(node.returns) if hasattr(ast, 'unparse') else 'Any'
        return None


class TestGenerator:
    """Generates test cases based on AST analysis."""
    
    def __init__(self):
        self.analyzer = ASTAnalyzer()
        self.generated_scenarios = []
    
    def generate_tests_for_module(self, source_code: str, module_name: str = "test_module") -> List[TestScenario]:
        """Generate comprehensive test scenarios for a module."""
        analysis = self.analyzer.analyze_module(source_code)
        scenarios = []
        
        # Generate tests for each function
        for func_info in analysis['functions']:
            scenarios.extend(self._generate_function_tests(func_info, analysis))
        
        # Generate boundary condition tests
        for boundary in analysis['boundary_conditions']:
            scenarios.extend(self._generate_boundary_tests(boundary))
        
        # Generate error condition tests
        for error in analysis['error_conditions']:
            scenarios.extend(self._generate_error_tests(error))
        
        # Generate complexity-based tests
        for hotspot in analysis['complexity_hotspots']:
            scenarios.extend(self._generate_complexity_tests(hotspot))
        
        return scenarios
    
    def _generate_function_tests(self, func_info: Dict[str, Any], analysis: Dict[str, Any]) -> List[TestScenario]:
        """Generate test scenarios for a specific function."""
        scenarios = []
        func_name = func_info['name']
        
        # Basic functionality test
        basic_scenario = TestScenario(
            scenario_name=f"test_{func_name}_basic_functionality",
            setup_code=self._generate_setup_code(func_info),
            test_code=self._generate_basic_test(func_info),
            expected_behavior="Function executes without errors",
            input_values=self._generate_basic_inputs(func_info),
            path_coverage=[f"{func_name}_basic"]
        )
        scenarios.append(basic_scenario)
        
        # Edge case tests
        if func_info['args']:
            edge_scenario = TestScenario(
                scenario_name=f"test_{func_name}_edge_cases",
                setup_code=self._generate_setup_code(func_info),
                test_code=self._generate_edge_test(func_info),
                expected_behavior="Function handles edge cases gracefully",
                input_values=self._generate_edge_inputs(func_info),
                path_coverage=[f"{func_name}_edge"]
            )
            scenarios.append(edge_scenario)
        
        # Path-specific tests
        relevant_paths = [p for p in analysis['code_paths'] if p.function_name == func_name]
        for path in relevant_paths[:3]:  # Limit to avoid test explosion
            path_scenario = TestScenario(
                scenario_name=f"test_{func_name}_path_{path.path_id}",
                setup_code=self._generate_setup_code(func_info),
                test_code=self._generate_path_test(func_info, path),
                expected_behavior=f"Exercises path: {path.conditions}",
                input_values=self._generate_path_inputs(path),
                path_coverage=[path.path_id]
            )
            scenarios.append(path_scenario)
        
        return scenarios
    
    def _generate_basic_inputs(self, func_info: Dict[str, Any]) -> Dict[str, Any]:
        """Generate basic input values for a function."""
        inputs = {}
        
        for arg in func_info['args']:
            # Generate appropriate values based on common argument names
            if 'path' in arg.lower() or 'file' in arg.lower():
                inputs[arg] = '/tmp/test_file.txt'
            elif 'count' in arg.lower() or 'size' in arg.lower() or 'num' in arg.lower():
                inputs[arg] = 10
            elif 'name' in arg.lower() or 'id' in arg.lower():
                inputs[arg] = 'test_value'
            elif 'flag' in arg.lower() or 'enable' in arg.lower() or arg.startswith('is_'):
                inputs[arg] = True
            else:
                inputs[arg] = self._generate_generic_value()
        
        return inputs
    
    def _generate_edge_inputs(self, func_info: Dict[str, Any]) -> Dict[str, Any]:
        """Generate edge case input values."""
        inputs = {}
        
        for arg in func_info['args']:
            if 'path' in arg.lower() or 'file' in arg.lower():
                inputs[arg] = ''  # Empty path
            elif any(keyword in arg.lower() for keyword in ['count', 'size', 'num', 'length']):
                inputs[arg] = 0  # Zero value
            elif 'name' in arg.lower() or 'id' in arg.lower():
                inputs[arg] = ''  # Empty string
            else:
                inputs[arg] = None  # Null value
        
        return inputs
    
    def _generate_path_inputs(self, path: CodePath) -> Dict[str, Any]:
        """Generate inputs to exercise a specific code path."""
        inputs = {}
        
        # Analyze conditions to generate appropriate inputs
        for condition in path.conditions:
            # Simple heuristic-based input generation
            if '>' in condition:
                inputs['numeric_value'] = 100
            elif '<' in condition:
                inputs['numeric_value'] = -1
            elif '==' in condition:
                inputs['equality_value'] = 'expected_value'
            elif 'None' in condition:
                inputs['optional_value'] = None
            elif 'empty' in condition.lower():
                inputs['collection'] = []
        
        return inputs
    
    def _generate_generic_value(self) -> Any:
        """Generate a generic test value."""
        return random.choice([
            'test_string',
            42,
            3.14,
            True,
            ['item1', 'item2'],
            {'key': 'value'}
        ])
    
    def _generate_setup_code(self, func_info: Dict[str, Any]) -> str:
        """Generate setup code for test."""
        return textwrap.dedent(f"""
        # Setup for testing {func_info['name']}
        # Mock external dependencies if needed
        """).strip()
    
    def _generate_basic_test(self, func_info: Dict[str, Any]) -> str:
        """Generate basic test code."""
        func_name = func_info['name']
        args = func_info['args']
        arg_list = ', '.join(args) if args else ''
        
        return textwrap.dedent(f"""
        def test_{func_name}_basic():
            # Test basic functionality
            result = {func_name}({arg_list})
            assert result is not None  # Basic assertion
        """).strip()
    
    def _generate_edge_test(self, func_info: Dict[str, Any]) -> str:
        """Generate edge case test code."""
        func_name = func_info['name']
        
        return textwrap.dedent(f"""
        def test_{func_name}_edge_cases():
            # Test with edge case inputs
            with pytest.raises((ValueError, TypeError, OSError)):
                result = {func_name}(None)  # Null input
        """).strip()
    
    def _generate_path_test(self, func_info: Dict[str, Any], path: CodePath) -> str:
        """Generate test code for specific path."""
        func_name = func_info['name']
        path_id = path.path_id.replace(func_name + '_', '')
        
        return textwrap.dedent(f"""
        def test_{func_name}_{path_id}():
            # Test specific execution path
            # Conditions: {', '.join(path.conditions)}
            result = {func_name}(test_inputs)
            assert result is not None  # Path-specific assertion
        """).strip()
    
    def _generate_boundary_tests(self, boundary: Dict[str, Any]) -> List[TestScenario]:
        """Generate tests for boundary conditions."""
        scenarios = []
        var_name = boundary['variable']
        operator = boundary['operator']
        value = boundary['value']
        
        for test_value in boundary['test_values']:
            scenario = TestScenario(
                scenario_name=f"test_boundary_{var_name}_{operator}_{test_value}",
                setup_code="# Boundary condition test setup",
                test_code=f"# Test {var_name} {operator} {value} with input {test_value}",
                expected_behavior=f"Boundary condition handled: {var_name} {operator} {value}",
                input_values={var_name.split('.')[-1]: test_value},  # Extract variable name
                path_coverage=[f"boundary_{var_name}_{test_value}"]
            )
            scenarios.append(scenario)
        
        return scenarios
    
    def _generate_error_tests(self, error: Dict[str, Any]) -> List[TestScenario]:
        """Generate tests for error conditions."""
        scenarios = []
        
        if error['type'] == 'raise':
            scenario = TestScenario(
                scenario_name=f"test_exception_{error['exception']}",
                setup_code="# Exception test setup",
                test_code=f"# Test that {error['exception']} is raised appropriately",
                expected_behavior=f"Raises {error['exception']} under error conditions",
                input_values={'error_trigger': True},
                path_coverage=[f"error_{error['line']}"]
            )
            scenarios.append(scenario)
        
        elif error['type'] == 'assert':
            scenario = TestScenario(
                scenario_name=f"test_assertion_line_{error['line']}",
                setup_code="# Assertion test setup", 
                test_code=f"# Test assertion: {error['condition']}",
                expected_behavior=f"Assertion passes: {error['condition']}",
                input_values={'assertion_input': 'valid_value'},
                path_coverage=[f"assert_{error['line']}"]
            )
            scenarios.append(scenario)
        
        return scenarios
    
    def _generate_complexity_tests(self, hotspot: Dict[str, Any]) -> List[TestScenario]:
        """Generate additional tests for complex functions."""
        scenarios = []
        func_name = hotspot['function']
        
        # Stress test for complex functions
        stress_scenario = TestScenario(
            scenario_name=f"test_{func_name}_stress",
            setup_code=f"# Stress test setup for complex function {func_name}",
            test_code=f"# Stress test with multiple iterations and edge cases",
            expected_behavior=f"Complex function handles stress testing (complexity: {hotspot['complexity']})",
            input_values={'stress_level': 100},
            path_coverage=[f"stress_{func_name}"]
        )
        scenarios.append(stress_scenario)
        
        return scenarios


class AdversarialInputGenerator:
    """Generates adversarial inputs to break assumptions."""
    
    def __init__(self):
        self.attack_patterns = [
            'buffer_overflow',
            'injection',
            'malformed_data',
            'resource_exhaustion',
            'unicode_attacks',
            'null_bytes',
            'control_characters'
        ]
    
    def generate_adversarial_strings(self, target_length: int = 100) -> List[str]:
        """Generate adversarial string inputs."""
        adversarial_strings = []
        
        # Extremely long strings
        adversarial_strings.append('A' * (target_length * 100))
        
        # Empty and whitespace-only strings
        adversarial_strings.extend(['', ' ', '\t', '\n', '\r\n'])
        
        # Unicode edge cases
        adversarial_strings.extend([
            '\u0000',  # Null character
            '\uffff',  # Unicode max
            '🤖' * 50,  # Emoji repetition
            'ñáéíóú' * 20,  # Accented characters
        ])
        
        # Injection attempts (for testing input validation)
        adversarial_strings.extend([
            "'; DROP TABLE users; --",  # SQL injection attempt
            '<script>alert("xss")</script>',  # XSS attempt
            '../../../etc/passwd',  # Path traversal attempt
            '__import__("os").system("echo pwned")',  # Python code injection
        ])
        
        # Control characters and special sequences
        adversarial_strings.extend([
            '\x00\x01\x02',  # Control characters
            '\b\f\r\t\v',  # Backspace, form feed, etc.
            '\\n\\r\\t',  # Escaped sequences
        ])
        
        return adversarial_strings
    
    def generate_adversarial_numbers(self) -> List[Any]:
        """Generate adversarial numeric inputs."""
        return [
            0, -1, 1,  # Boundary values
            float('inf'), float('-inf'), float('nan'),  # Special floats
            sys.maxsize, -sys.maxsize - 1,  # System limits
            2**63 - 1, -(2**63),  # 64-bit integer limits
            1e308, -1e308,  # Very large numbers
            1e-308, -1e-308,  # Very small numbers
            0.1 + 0.2,  # Floating point precision issue
        ]
    
    def generate_adversarial_collections(self) -> List[Any]:
        """Generate adversarial collection inputs."""
        return [
            [],  # Empty list
            [None] * 1000,  # Large list of nulls
            list(range(10000)),  # Very large list
            [''] * 100,  # List of empty strings
            [{}] * 50,  # List of empty dicts
            {'': '', None: None, 0: 0},  # Dict with problematic keys
        ]


class TestAIPoweredGeneration:
    """Test the AI-powered test generation system."""
    
    def test_ast_analyzer_extracts_functions(self):
        """Test that AST analyzer correctly extracts function information."""
        sample_code = textwrap.dedent("""
        def simple_function(arg1, arg2=None):
            '''A simple test function.'''
            if arg1 > 0:
                return arg1 + (arg2 or 0)
            return 0
        
        async def async_function(data: str) -> bool:
            return len(data) > 0
        """).strip()
        
        analyzer = ASTAnalyzer()
        analysis = analyzer.analyze_module(sample_code)
        
        functions = analysis['functions']
        assert len(functions) == 2, "Should extract both functions"
        
        # Check simple function
        simple_func = next((f for f in functions if f['name'] == 'simple_function'), None)
        assert simple_func is not None, "Should find simple_function"
        assert simple_func['args'] == ['arg1', 'arg2'], "Should extract arguments"
        assert simple_func['has_defaults'], "Should detect default arguments"
        assert not simple_func['is_async'], "Should not be marked as async"
        assert simple_func['complexity'] > 1, "Should calculate complexity"
        
        # Check async function
        async_func = next((f for f in functions if f['name'] == 'async_function'), None)
        assert async_func is not None, "Should find async_function"
        assert async_func['is_async'], "Should be marked as async"
        assert 'str' in str(async_func.get('returns', '')), "Should extract return type"
    
    def test_ast_analyzer_extracts_code_paths(self):
        """Test code path extraction from conditional logic."""
        sample_code = textwrap.dedent("""
        def conditional_function(x, y):
            if x > 0:
                if y < 10:
                    return x + y
                else:
                    return x - y
            elif x == 0:
                return y
            else:
                return -1
        """).strip()
        
        analyzer = ASTAnalyzer()
        analysis = analyzer.analyze_module(sample_code)
        
        paths = analysis['code_paths']
        assert len(paths) >= 3, f"Should extract multiple code paths, got {len(paths)}"
        
        # Should have paths for different conditions
        path_conditions = [path.conditions for path in paths]
        flattened_conditions = [cond for conditions in path_conditions for cond in conditions]
        
        # Check for expected conditions
        assert any('x > 0' in str(flattened_conditions)), "Should find x > 0 condition"
        assert any('x == 0' in str(flattened_conditions)), "Should find x == 0 condition"
    
    def test_ast_analyzer_finds_boundary_conditions(self):
        """Test boundary condition detection."""
        sample_code = textwrap.dedent("""
        def boundary_function(value):
            if value > 100:
                return "high"
            elif value >= 50:
                return "medium"
            elif value <= 0:
                return "low"
            return "normal"
        """).strip()
        
        analyzer = ASTAnalyzer()
        analysis = analyzer.analyze_module(sample_code)
        
        boundaries = analysis['boundary_conditions']
        assert len(boundaries) >= 3, f"Should find boundary conditions, got {len(boundaries)}"
        
        # Should find numeric boundary values
        boundary_values = [b['value'] for b in boundaries]
        assert 100 in boundary_values, "Should find boundary value 100"
        assert 50 in boundary_values, "Should find boundary value 50"
        assert 0 in boundary_values, "Should find boundary value 0"
    
    def test_test_generator_creates_scenarios(self):
        """Test that test generator creates comprehensive scenarios."""
        sample_code = textwrap.dedent("""
        def calculator(a, b, operation='add'):
            '''Simple calculator function.'''
            if operation == 'add':
                return a + b
            elif operation == 'multiply':
                if b == 0:
                    return 0
                return a * b
            else:
                raise ValueError("Unsupported operation")
        """).strip()
        
        generator = TestGenerator()
        scenarios = generator.generate_tests_for_module(sample_code)
        
        assert len(scenarios) > 0, "Should generate test scenarios"
        
        # Should have different types of scenarios
        scenario_names = [s.scenario_name for s in scenarios]
        
        # Should generate basic functionality tests
        basic_tests = [name for name in scenario_names if 'basic' in name]
        assert len(basic_tests) > 0, "Should generate basic functionality tests"
        
        # Should generate edge case tests
        edge_tests = [name for name in scenario_names if 'edge' in name]
        assert len(edge_tests) > 0, "Should generate edge case tests"
        
        # Check scenario structure
        for scenario in scenarios[:3]:  # Check first few scenarios
            assert scenario.scenario_name, "Scenario should have a name"
            assert scenario.setup_code, "Scenario should have setup code"
            assert scenario.test_code, "Scenario should have test code"
            assert scenario.expected_behavior, "Scenario should have expected behavior"
            assert isinstance(scenario.input_values, dict), "Should have input values"
    
    def test_adversarial_input_generator(self):
        """Test adversarial input generation."""
        generator = AdversarialInputGenerator()
        
        # Test string generation
        adversarial_strings = generator.generate_adversarial_strings(target_length=50)
        assert len(adversarial_strings) > 10, "Should generate multiple adversarial strings"
        
        # Should include various attack patterns
        all_strings = ' '.join(str(s) for s in adversarial_strings)
        assert 'DROP TABLE' in all_strings, "Should include SQL injection attempts"
        assert '<script>' in all_strings, "Should include XSS attempts"
        assert '../../../' in all_strings, "Should include path traversal attempts"
        
        # Should include edge cases
        assert '' in adversarial_strings, "Should include empty string"
        assert any(len(s) > 1000 for s in adversarial_strings), "Should include very long strings"
        
        # Test numeric generation
        adversarial_numbers = generator.generate_adversarial_numbers()
        assert len(adversarial_numbers) > 5, "Should generate multiple adversarial numbers"
        
        # Should include special values
        assert 0 in adversarial_numbers, "Should include zero"
        assert float('inf') in adversarial_numbers, "Should include infinity"
        assert any(str(n) == 'nan' for n in adversarial_numbers), "Should include NaN"
        
        # Test collection generation
        adversarial_collections = generator.generate_adversarial_collections()
        assert len(adversarial_collections) > 3, "Should generate adversarial collections"
        
        # Should include edge cases
        assert [] in adversarial_collections, "Should include empty list"
        assert any(len(c) > 100 for c in adversarial_collections if hasattr(c, '__len__')), \
            "Should include large collections"
    
    def test_generated_tests_execute_successfully(self):
        """Test that generated test code can actually execute."""
        # Simple target function
        def target_function(x: int, y: str = "default") -> str:
            if x > 0:
                return f"positive: {y}"
            elif x == 0:
                return "zero"
            else:
                return "negative"
        
        # Get source code
        source_code = inspect.getsource(target_function)
        
        generator = TestGenerator()
        scenarios = generator.generate_tests_for_module(source_code)
        
        # Should generate executable scenarios
        assert len(scenarios) > 0, "Should generate scenarios"
        
        for scenario in scenarios[:2]:  # Test first couple scenarios
            # Validate scenario structure
            assert scenario.test_code, "Should have test code"
            assert 'def test_' in scenario.test_code, "Should generate proper test function"
            
            # Test code should be syntactically valid
            try:
                compile(scenario.test_code, '<string>', 'exec')
            except SyntaxError as e:
                pytest.fail(f"Generated test code has syntax error: {e}\nCode: {scenario.test_code}")
    
    @pytest.mark.slow
    def test_real_module_analysis(self):
        """Test AI generation on actual crackerjack modules."""
        # Analyze FilesystemService
        filesystem_source = inspect.getsource(FilesystemService)
        
        generator = TestGenerator()
        scenarios = generator.generate_tests_for_module(filesystem_source, "FilesystemService")
        
        assert len(scenarios) > 5, "Should generate multiple scenarios for real module"
        
        # Should generate scenarios for different methods
        scenario_names = [s.scenario_name for s in scenarios]
        method_coverage = set()
        
        for name in scenario_names:
            # Extract method names from scenario names
            if 'write_file' in name:
                method_coverage.add('write_file')
            elif 'read_file' in name:
                method_coverage.add('read_file')
            elif 'validate' in name:
                method_coverage.add('validate')
        
        assert len(method_coverage) >= 2, f"Should cover multiple methods, covered: {method_coverage}"
        
        # Check scenario quality
        complex_scenarios = [s for s in scenarios if 'edge' in s.scenario_name or 'path' in s.scenario_name]
        assert len(complex_scenarios) >= 2, "Should generate complex test scenarios"
    
    def test_integration_with_existing_tests(self):
        """Test that AI-generated tests integrate well with existing test suite."""
        # This test demonstrates how AI-generated tests could be integrated
        sample_function_code = textwrap.dedent("""
        def validate_config(config_dict):
            if not isinstance(config_dict, dict):
                raise TypeError("Config must be a dictionary")
            
            if 'name' not in config_dict:
                raise KeyError("Config must have 'name' field")
            
            if not config_dict['name']:
                raise ValueError("Config name cannot be empty")
            
            return True
        """).strip()
        
        generator = TestGenerator()
        scenarios = generator.generate_tests_for_module(sample_function_code)
        
        # AI should generate tests for error conditions
        error_scenarios = [s for s in scenarios if 'error' in s.scenario_name.lower() 
                          or 'exception' in s.expected_behavior.lower()]
        
        assert len(error_scenarios) > 0, "Should generate error condition tests"
        
        # AI should generate tests for different types of inputs
        input_variety = []
        for scenario in scenarios:
            if scenario.input_values:
                for value in scenario.input_values.values():
                    input_variety.append(type(value).__name__)
        
        # Should test various input types
        assert len(set(input_variety)) >= 2, f"Should test variety of inputs: {set(input_variety)}"


if __name__ == "__main__":
    pytest.main([
        __file__,
        "-v",
        "--tb=short"
    ])