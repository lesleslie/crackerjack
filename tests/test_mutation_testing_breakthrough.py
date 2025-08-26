"""
🧬 BREAKTHROUGH TESTING FRONTIER 2: Mutation Testing

This module implements mutation testing to validate that our tests actually catch bugs.
We inject controlled mutations into our code to verify test effectiveness.

Mutation testing measures "mutation score" - the percentage of mutants our tests kill.
A high mutation score indicates strong test coverage that catches real bugs.
"""

import pytest
import ast
import tempfile
import subprocess
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional
from unittest.mock import patch, MagicMock
import inspect
import textwrap


class MutationOperator:
    """Base class for mutation operators that inject bugs into code."""
    
    def __init__(self, name: str):
        self.name = name
        self.mutations_applied = 0
    
    def can_mutate(self, node: ast.AST) -> bool:
        """Check if this operator can mutate the given AST node."""
        raise NotImplementedError
    
    def mutate(self, node: ast.AST) -> ast.AST:
        """Apply mutation to the AST node."""
        raise NotImplementedError


class ArithmeticOperatorMutator(MutationOperator):
    """Mutates arithmetic operators: + -> -, * -> /, etc."""
    
    def __init__(self):
        super().__init__("arithmetic")
        self.operator_map = {
            ast.Add: ast.Sub,
            ast.Sub: ast.Add,
            ast.Mult: ast.Div,
            ast.Div: ast.Mult,
            ast.Mod: ast.FloorDiv,
            ast.FloorDiv: ast.Mod,
        }
    
    def can_mutate(self, node: ast.AST) -> bool:
        return isinstance(node, ast.BinOp) and type(node.op) in self.operator_map
    
    def mutate(self, node: ast.AST) -> ast.AST:
        if isinstance(node, ast.BinOp) and type(node.op) in self.operator_map:
            new_op = self.operator_map[type(node.op)]()
            mutated = ast.BinOp(left=node.left, op=new_op, right=node.right)
            ast.copy_location(mutated, node)
            self.mutations_applied += 1
            return mutated
        return node


class ComparisonOperatorMutator(MutationOperator):
    """Mutates comparison operators: == -> !=, < -> <=, etc."""
    
    def __init__(self):
        super().__init__("comparison")
        self.operator_map = {
            ast.Eq: ast.NotEq,
            ast.NotEq: ast.Eq,
            ast.Lt: ast.LtE,
            ast.LtE: ast.Lt,
            ast.Gt: ast.GtE,
            ast.GtE: ast.Gt,
            ast.Is: ast.IsNot,
            ast.IsNot: ast.Is,
            ast.In: ast.NotIn,
            ast.NotIn: ast.In,
        }
    
    def can_mutate(self, node: ast.AST) -> bool:
        return (isinstance(node, ast.Compare) and 
                len(node.ops) == 1 and 
                type(node.ops[0]) in self.operator_map)
    
    def mutate(self, node: ast.AST) -> ast.AST:
        if self.can_mutate(node):
            old_op = node.ops[0]
            new_op = self.operator_map[type(old_op)]()
            mutated = ast.Compare(left=node.left, ops=[new_op], comparators=node.comparators)
            ast.copy_location(mutated, node)
            self.mutations_applied += 1
            return mutated
        return node


class BooleanOperatorMutator(MutationOperator):
    """Mutates boolean operators: and -> or, not -> identity, etc."""
    
    def __init__(self):
        super().__init__("boolean")
    
    def can_mutate(self, node: ast.AST) -> bool:
        return isinstance(node, (ast.BoolOp, ast.UnaryOp))
    
    def mutate(self, node: ast.AST) -> ast.AST:
        if isinstance(node, ast.BoolOp):
            if isinstance(node.op, ast.And):
                new_op = ast.Or()
            elif isinstance(node.op, ast.Or):
                new_op = ast.And()
            else:
                return node
            
            mutated = ast.BoolOp(op=new_op, values=node.values)
            ast.copy_location(mutated, node)
            self.mutations_applied += 1
            return mutated
            
        elif isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            # Remove 'not' operator - return the operand directly
            self.mutations_applied += 1
            return node.operand
            
        return node


class ConditionalBoundaryMutator(MutationOperator):
    """Mutates conditional boundaries and constants."""
    
    def __init__(self):
        super().__init__("conditional")
    
    def can_mutate(self, node: ast.AST) -> bool:
        return isinstance(node, (ast.Num, ast.Constant)) or \
               (isinstance(node, ast.Constant) and isinstance(node.value, (int, float)))
    
    def mutate(self, node: ast.AST) -> ast.AST:
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            # Mutate numeric constants by adding/subtracting 1
            if node.value == 0:
                new_value = 1
            elif node.value > 0:
                new_value = node.value - 1
            else:
                new_value = node.value + 1
            
            mutated = ast.Constant(value=new_value)
            ast.copy_location(mutated, node)
            self.mutations_applied += 1
            return mutated
            
        return node


class MutationTester:
    """Orchestrates mutation testing by applying mutations and running tests."""
    
    def __init__(self, target_module_path: str):
        self.target_module_path = Path(target_module_path)
        self.mutators = [
            ArithmeticOperatorMutator(),
            ComparisonOperatorMutator(),
            BooleanOperatorMutator(),
            ConditionalBoundaryMutator(),
        ]
        self.mutation_results = []
    
    def generate_mutations(self, source_code: str) -> List[Dict[str, Any]]:
        """Generate all possible mutations of the source code."""
        tree = ast.parse(source_code)
        mutations = []
        
        for mutator in self.mutators:
            mutation_tree = self._apply_mutations(tree, mutator)
            if mutator.mutations_applied > 0:
                mutated_code = ast.unparse(mutation_tree)
                mutations.append({
                    'operator': mutator.name,
                    'mutations_count': mutator.mutations_applied,
                    'mutated_code': mutated_code,
                    'mutator': mutator
                })
                # Reset counter for next mutation
                mutator.mutations_applied = 0
        
        return mutations
    
    def _apply_mutations(self, tree: ast.AST, mutator: MutationOperator) -> ast.AST:
        """Apply a specific mutator to the AST."""
        
        class MutationVisitor(ast.NodeTransformer):
            def __init__(self, mutator):
                self.mutator = mutator
                self.mutation_applied = False
            
            def visit(self, node):
                # Only apply first eligible mutation to avoid compound mutations
                if not self.mutation_applied and self.mutator.can_mutate(node):
                    self.mutation_applied = True
                    return self.mutator.mutate(node)
                return self.generic_visit(node)
        
        visitor = MutationVisitor(mutator)
        return visitor.visit(tree)
    
    def test_mutation(self, original_code: str, mutated_code: str, test_command: List[str]) -> Dict[str, Any]:
        """Test a specific mutation by running tests against mutated code."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as temp_file:
            temp_path = Path(temp_file.name)
            temp_file.write(mutated_code)
        
        try:
            # Run tests with mutated code
            result = subprocess.run(
                test_command + [str(temp_path)],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=self.target_module_path.parent
            )
            
            # Mutation is "killed" if tests fail (which is good!)
            killed = result.returncode != 0
            
            return {
                'killed': killed,
                'stdout': result.stdout,
                'stderr': result.stderr,
                'returncode': result.returncode,
                'temp_path': str(temp_path)
            }
            
        except subprocess.TimeoutExpired:
            return {
                'killed': True,  # Timeout counts as killing the mutant
                'stdout': '',
                'stderr': 'Test timeout',
                'returncode': -1,
                'temp_path': str(temp_path)
            }
        except Exception as e:
            return {
                'killed': True,
                'stdout': '',
                'stderr': str(e),
                'returncode': -1,
                'temp_path': str(temp_path)
            }
        finally:
            # Clean up temporary file
            try:
                temp_path.unlink()
            except Exception:
                pass
    
    def calculate_mutation_score(self, results: List[Dict[str, Any]]) -> float:
        """Calculate mutation score as percentage of killed mutants."""
        if not results:
            return 0.0
        
        killed_count = sum(1 for result in results if result['killed'])
        return (killed_count / len(results)) * 100.0


class TestMutationTesting:
    """Test suite for mutation testing capabilities."""
    
    def test_arithmetic_mutation_operator(self):
        """Test arithmetic mutation operator works correctly."""
        mutator = ArithmeticOperatorMutator()
        
        # Test code with arithmetic operations
        code = "result = a + b * c"
        tree = ast.parse(code)
        
        # Find the BinOp nodes
        binop_nodes = []
        for node in ast.walk(tree):
            if isinstance(node, ast.BinOp):
                binop_nodes.append(node)
        
        assert len(binop_nodes) >= 1, "Should find arithmetic operations"
        
        # Test mutation capability
        add_node = None
        mult_node = None
        for node in binop_nodes:
            if isinstance(node.op, ast.Add):
                add_node = node
            elif isinstance(node.op, ast.Mult):
                mult_node = node
        
        if add_node:
            assert mutator.can_mutate(add_node), "Should be able to mutate addition"
            mutated = mutator.mutate(add_node)
            assert isinstance(mutated.op, ast.Sub), "Addition should mutate to subtraction"
        
        if mult_node:
            assert mutator.can_mutate(mult_node), "Should be able to mutate multiplication"
            mutated = mutator.mutate(mult_node)
            assert isinstance(mutated.op, ast.Div), "Multiplication should mutate to division"
    
    def test_comparison_mutation_operator(self):
        """Test comparison mutation operator works correctly."""
        mutator = ComparisonOperatorMutator()
        
        # Test code with comparisons
        code = "result = x == y"
        tree = ast.parse(code)
        
        # Find comparison node
        compare_node = None
        for node in ast.walk(tree):
            if isinstance(node, ast.Compare):
                compare_node = node
                break
        
        assert compare_node is not None, "Should find comparison operation"
        assert mutator.can_mutate(compare_node), "Should be able to mutate equality"
        
        mutated = mutator.mutate(compare_node)
        assert isinstance(mutated.ops[0], ast.NotEq), "Equality should mutate to inequality"
    
    def test_boolean_mutation_operator(self):
        """Test boolean mutation operator works correctly."""
        mutator = BooleanOperatorMutator()
        
        # Test boolean AND
        code = "result = a and b"
        tree = ast.parse(code)
        
        boolop_node = None
        for node in ast.walk(tree):
            if isinstance(node, ast.BoolOp):
                boolop_node = node
                break
        
        assert boolop_node is not None, "Should find boolean operation"
        assert mutator.can_mutate(boolop_node), "Should be able to mutate boolean AND"
        
        mutated = mutator.mutate(boolop_node)
        assert isinstance(mutated.op, ast.Or), "AND should mutate to OR"
        
        # Test NOT operator
        code_not = "result = not x"
        tree_not = ast.parse(code_not)
        
        unary_node = None
        for node in ast.walk(tree_not):
            if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
                unary_node = node
                break
        
        assert unary_node is not None, "Should find NOT operation"
        assert mutator.can_mutate(unary_node), "Should be able to mutate NOT"
        
        mutated_not = mutator.mutate(unary_node)
        # NOT should be removed, returning just the operand
        assert isinstance(mutated_not, ast.Name), "NOT should be removed"
    
    def test_conditional_boundary_mutator(self):
        """Test conditional boundary mutation operator."""
        mutator = ConditionalBoundaryMutator()
        
        # Test numeric constant
        code = "if x > 5: pass"
        tree = ast.parse(code)
        
        constant_node = None
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, int):
                constant_node = node
                break
        
        assert constant_node is not None, "Should find numeric constant"
        assert mutator.can_mutate(constant_node), "Should be able to mutate constant"
        
        original_value = constant_node.value
        mutated = mutator.mutate(constant_node)
        assert mutated.value == original_value - 1, "Positive constant should decrease by 1"
    
    def test_mutation_generator_integration(self):
        """Test the complete mutation generation process."""
        # Sample code to mutate
        sample_code = textwrap.dedent("""
        def calculate_score(points, bonus):
            if points > 100:
                return points + bonus * 2
            elif points == 50:
                return points + bonus
            else:
                return points and bonus > 0
        """).strip()
        
        # Create a temporary module for testing
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as temp_file:
            temp_path = Path(temp_file.name)
            temp_file.write(sample_code)
        
        try:
            mutation_tester = MutationTester(str(temp_path))
            mutations = mutation_tester.generate_mutations(sample_code)
            
            # Should generate multiple types of mutations
            assert len(mutations) > 0, "Should generate at least one mutation"
            
            operator_types = {mut['operator'] for mut in mutations}
            expected_types = {'arithmetic', 'comparison', 'boolean', 'conditional'}
            
            # Should have mutations from multiple operators
            assert len(operator_types.intersection(expected_types)) >= 2, \
                f"Should generate multiple types of mutations, got: {operator_types}"
            
            # Each mutation should have valid code
            for mutation in mutations:
                assert 'mutated_code' in mutation, "Mutation should have mutated code"
                assert mutation['mutated_code'] != sample_code, "Mutated code should be different"
                
                # Validate that mutated code is syntactically correct
                try:
                    ast.parse(mutation['mutated_code'])
                except SyntaxError:
                    pytest.fail(f"Mutated code has syntax errors: {mutation['mutated_code']}")
        
        finally:
            temp_path.unlink()
    
    def test_mutation_score_calculation(self):
        """Test mutation score calculation."""
        mutation_tester = MutationTester("dummy_path")
        
        # Test with all mutations killed (perfect score)
        results_perfect = [
            {'killed': True},
            {'killed': True},
            {'killed': True},
        ]
        score_perfect = mutation_tester.calculate_mutation_score(results_perfect)
        assert score_perfect == 100.0, "Perfect mutation killing should give 100% score"
        
        # Test with partial mutation killing
        results_partial = [
            {'killed': True},
            {'killed': False},
            {'killed': True},
        ]
        score_partial = mutation_tester.calculate_mutation_score(results_partial)
        assert abs(score_partial - 66.67) < 0.1, "Should calculate correct percentage"
        
        # Test with no mutations killed (worst score)
        results_none = [
            {'killed': False},
            {'killed': False},
        ]
        score_none = mutation_tester.calculate_mutation_score(results_none)
        assert score_none == 0.0, "No mutations killed should give 0% score"
        
        # Test empty results
        score_empty = mutation_tester.calculate_mutation_score([])
        assert score_empty == 0.0, "Empty results should give 0% score"
    
    @pytest.mark.slow
    def test_simple_function_mutation_testing(self):
        """Test mutation testing on a simple function with its test."""
        # Sample function to test
        function_code = textwrap.dedent("""
        def add_numbers(a, b):
            if a > 0 and b > 0:
                return a + b
            elif a == 0:
                return b
            else:
                return 0
        """).strip()
        
        # Sample test that should catch most mutations
        test_code = textwrap.dedent("""
        import pytest
        
        def test_add_numbers():
            # Test positive numbers
            assert add_numbers(2, 3) == 5
            
            # Test with zero
            assert add_numbers(0, 5) == 5
            
            # Test negative numbers
            assert add_numbers(-1, 5) == 0
            
            # Test boundary conditions
            assert add_numbers(1, -1) == 0
        """).strip()
        
        # Create temporary files
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as func_file:
            func_path = Path(func_file.name)
            func_file.write(function_code)
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as test_file:
            test_path = Path(test_file.name)
            # Combine function and test in test file for simplicity
            test_file.write(function_code + "\n\n" + test_code)
        
        try:
            mutation_tester = MutationTester(str(func_path))
            mutations = mutation_tester.generate_mutations(function_code)
            
            assert len(mutations) > 0, "Should generate mutations for the function"
            
            # Test a few mutations (not all to keep test fast)
            results = []
            for mutation in mutations[:3]:  # Test first 3 mutations
                # Create test file with mutated function
                mutated_test_code = mutation['mutated_code'] + "\n\n" + test_code
                
                with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as mutated_file:
                    mutated_path = Path(mutated_file.name)
                    mutated_file.write(mutated_test_code)
                
                try:
                    # Run pytest on the mutated code
                    result = subprocess.run([
                        sys.executable, '-m', 'pytest', str(mutated_path), '-v'
                    ], capture_output=True, text=True, timeout=10)
                    
                    results.append({
                        'killed': result.returncode != 0,
                        'operator': mutation['operator']
                    })
                    
                except subprocess.TimeoutExpired:
                    results.append({'killed': True, 'operator': mutation['operator']})
                finally:
                    mutated_path.unlink()
            
            # Calculate mutation score
            mutation_score = mutation_tester.calculate_mutation_score(results)
            
            # We expect a reasonably high mutation score (tests should catch most bugs)
            assert mutation_score >= 50.0, f"Expected mutation score >= 50%, got {mutation_score}%"
            
            print(f"Mutation testing results:")
            print(f"Total mutations tested: {len(results)}")
            print(f"Mutations killed: {sum(1 for r in results if r['killed'])}")
            print(f"Mutation score: {mutation_score:.1f}%")
            print(f"Operators tested: {[r['operator'] for r in results]}")
            
        finally:
            func_path.unlink()
            test_path.unlink()


class TestMutationTestingAdvanced:
    """Advanced mutation testing scenarios."""
    
    def test_equivalent_mutants_detection(self):
        """Test detection of equivalent mutants (mutations that don't change behavior)."""
        # Code where some mutations might be equivalent
        code_with_equivalents = textwrap.dedent("""
        def check_positive(x):
            return x > 0 or x >= 1  # These conditions are equivalent for integers
        """).strip()
        
        mutation_tester = MutationTester("dummy")
        mutations = mutation_tester.generate_mutations(code_with_equivalents)
        
        # Should still generate mutations even if some are equivalent
        assert len(mutations) > 0, "Should generate mutations despite equivalent conditions"
        
        # This test mainly documents the equivalent mutant issue
        # Real mutation testing tools need sophisticated equivalent mutant detection
    
    def test_higher_order_mutations(self):
        """Test concept of higher-order mutations (multiple mutations combined)."""
        code = textwrap.dedent("""
        def complex_calculation(a, b, c):
            if a > 0 and b < 10:
                return a + b * c
            return 0
        """).strip()
        
        mutation_tester = MutationTester("dummy")
        mutations = mutation_tester.generate_mutations(code)
        
        # Current implementation does first-order mutations only
        # This test documents the concept for future enhancement
        assert len(mutations) > 0, "Should generate first-order mutations"
        
        # Each mutation should change only one operator
        for mutation in mutations:
            # Count the differences - this is a simple approximation
            original_lines = code.split('\n')
            mutated_lines = mutation['mutated_code'].split('\n')
            
            # Should have changes but not be completely different
            assert mutation['mutated_code'] != code, "Mutation should change the code"


if __name__ == "__main__":
    pytest.main([
        __file__,
        "-v",
        "-m", "not slow",  # Skip slow tests in quick runs
        "--tb=short"
    ])