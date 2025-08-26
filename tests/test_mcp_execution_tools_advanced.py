"""
Advanced functional tests for MCP Execution Tools.

This module provides sophisticated testing of MCP execution tools,
auto-fixing workflows, and AI agent coordination.
Targets 845 lines with 0% coverage for maximum impact.
"""

import asyncio
import json
import time
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from crackerjack.mcp.tools.execution_tools import (
    AnalysisContext,
    AnalysisResult,
    AutoFixResult,
    ErrorAnalyzer,
    ExecutionResult,
    FixPattern,
    IterationContext,
    IterationResult,
    SmartErrorAnalyzer,
    execute_crackerjack_with_auto_fix,
    run_crackerjack_stage,
)


class TestAnalysisContext:
    """Tests for analysis context functionality."""

    def test_analysis_context_creation(self) -> None:
        """Test analysis context creation and initialization."""
        context = AnalysisContext(
            iteration=3,
            hook_errors=["Type error in models.py", "Import error in utils.py"],
            test_failures=["test_user_creation failed", "test_data_validation failed"],
            previous_fixes=["Added type hints", "Fixed import order"],
            codebase_state={"coverage": 42.5, "complexity": 15}
        )
        
        assert context.iteration == 3
        assert len(context.hook_errors) == 2
        assert len(context.test_failures) == 2
        assert len(context.previous_fixes) == 2
        assert context.codebase_state["coverage"] == 42.5

    def test_analysis_context_empty_initialization(self) -> None:
        """Test analysis context with empty data."""
        context = AnalysisContext(
            iteration=1,
            hook_errors=[],
            test_failures=[],
            previous_fixes=[]
        )
        
        assert context.iteration == 1
        assert len(context.hook_errors) == 0
        assert len(context.test_failures) == 0
        assert len(context.previous_fixes) == 0
        assert context.codebase_state is None

    def test_analysis_context_serialization(self) -> None:
        """Test analysis context serialization to dict."""
        context = AnalysisContext(
            iteration=2,
            hook_errors=["Error 1"],
            test_failures=["Test fail 1"],
            previous_fixes=["Fix 1"],
            codebase_state={"metric": "value"}
        )
        
        data = context.to_dict()
        
        assert data["iteration"] == 2
        assert data["hook_errors"] == ["Error 1"]
        assert data["test_failures"] == ["Test fail 1"]
        assert data["previous_fixes"] == ["Fix 1"]
        assert data["codebase_state"]["metric"] == "value"

    def test_analysis_context_deserialization(self) -> None:
        """Test analysis context creation from dict."""
        data = {
            "iteration": 4,
            "hook_errors": ["Error A", "Error B"],
            "test_failures": ["Test failure"],
            "previous_fixes": ["Fix A", "Fix B", "Fix C"],
            "codebase_state": {"lines": 1000, "functions": 50}
        }
        
        context = AnalysisContext.from_dict(data)
        
        assert context.iteration == 4
        assert context.hook_errors == ["Error A", "Error B"]
        assert len(context.previous_fixes) == 3
        assert context.codebase_state["lines"] == 1000


class TestFixPattern:
    """Tests for fix pattern functionality."""

    def test_fix_pattern_creation(self) -> None:
        """Test fix pattern creation and initialization."""
        pattern = FixPattern(
            pattern_id="type-error-fix",
            pattern_name="Type Error Resolution",
            error_patterns=["Type .* is not assignable", "Missing type annotation"],
            fix_template="Add type annotation: {variable}: {type}",
            confidence=0.85,
            success_rate=0.92
        )
        
        assert pattern.pattern_id == "type-error-fix"
        assert pattern.pattern_name == "Type Error Resolution"
        assert len(pattern.error_patterns) == 2
        assert pattern.confidence == 0.85
        assert pattern.success_rate == 0.92

    def test_fix_pattern_matches_error(self) -> None:
        """Test fix pattern error matching."""
        pattern = FixPattern(
            pattern_id="import-fix",
            pattern_name="Import Error Fix",
            error_patterns=[r"cannot import name '(\w+)'", r"No module named '(\w+)'"],
            fix_template="Fix import: from {module} import {name}",
            confidence=0.9
        )
        
        # Test positive matches
        assert pattern.matches_error("cannot import name 'MyClass'")
        assert pattern.matches_error("No module named 'missing_module'")
        
        # Test negative match
        assert not pattern.matches_error("Type error in variable assignment")

    def test_fix_pattern_generate_fix(self) -> None:
        """Test fix generation from pattern."""
        pattern = FixPattern(
            pattern_id="variable-fix",
            pattern_name="Variable Declaration Fix",
            error_patterns=[r"Variable '(\w+)' is not defined"],
            fix_template="Initialize variable: {variable} = {default_value}",
            confidence=0.8
        )
        
        error_message = "Variable 'user_count' is not defined"
        fix_suggestion = pattern.generate_fix(
            error_message,
            context={"default_value": "0", "variable": "user_count"}
        )
        
        assert "user_count" in fix_suggestion
        assert "Initialize variable" in fix_suggestion

    def test_fix_pattern_with_multiple_captures(self) -> None:
        """Test fix pattern with multiple capture groups."""
        pattern = FixPattern(
            pattern_id="method-fix",
            pattern_name="Method Definition Fix",
            error_patterns=[r"Method '(\w+)' of class '(\w+)' not found"],
            fix_template="Add method {method} to class {class_name}",
            confidence=0.7
        )
        
        error = "Method 'calculate_total' of class 'Order' not found"
        assert pattern.matches_error(error)
        
        fix = pattern.generate_fix(error, context={"method": "calculate_total", "class_name": "Order"})
        assert "calculate_total" in fix
        assert "Order" in fix


class TestAnalysisResult:
    """Tests for analysis result functionality."""

    def test_analysis_result_creation(self) -> None:
        """Test analysis result creation and initialization."""
        result = AnalysisResult(
            context=AnalysisContext(iteration=1, hook_errors=[], test_failures=[], previous_fixes=[]),
            identified_patterns=["pattern1", "pattern2"],
            recommended_fixes=["Fix A", "Fix B", "Fix C"],
            confidence_score=0.88,
            estimated_fix_time=45.0
        )
        
        assert result.context.iteration == 1
        assert len(result.identified_patterns) == 2
        assert len(result.recommended_fixes) == 3
        assert result.confidence_score == 0.88
        assert result.estimated_fix_time == 45.0

    def test_analysis_result_prioritize_fixes(self) -> None:
        """Test fix prioritization in analysis result."""
        fixes = [
            {"description": "Fix critical error", "priority": "high", "impact": 0.9},
            {"description": "Fix minor warning", "priority": "low", "impact": 0.3},
            {"description": "Fix moderate issue", "priority": "medium", "impact": 0.6}
        ]
        
        result = AnalysisResult(
            context=AnalysisContext(iteration=1, hook_errors=[], test_failures=[], previous_fixes=[]),
            identified_patterns=[],
            recommended_fixes=fixes,
            confidence_score=0.8
        )
        
        prioritized = result.get_prioritized_fixes()
        
        # Should be ordered by priority and impact
        assert prioritized[0]["priority"] == "high"
        assert prioritized[-1]["priority"] == "low"

    def test_analysis_result_to_summary(self) -> None:
        """Test analysis result summary generation."""
        context = AnalysisContext(
            iteration=2,
            hook_errors=["Type error", "Import error"],
            test_failures=["Test 1 failed"],
            previous_fixes=["Previous fix"]
        )
        
        result = AnalysisResult(
            context=context,
            identified_patterns=["type-error", "import-error"],
            recommended_fixes=["Add types", "Fix imports"],
            confidence_score=0.85,
            estimated_fix_time=30.0
        )
        
        summary = result.to_summary()
        
        assert summary["iteration"] == 2
        assert summary["total_errors"] == 3  # 2 hook + 1 test
        assert summary["patterns_found"] == 2
        assert summary["fixes_recommended"] == 2
        assert summary["confidence"] == 0.85


class TestAutoFixResult:
    """Tests for auto-fix result functionality."""

    def test_auto_fix_result_creation(self) -> None:
        """Test auto-fix result creation."""
        result = AutoFixResult(
            fixes_applied=["Fixed type error", "Added import"],
            files_modified=["models.py", "utils.py"],
            success_rate=0.95,
            execution_time=12.5,
            remaining_issues=["Complex logic needs review"]
        )
        
        assert len(result.fixes_applied) == 2
        assert len(result.files_modified) == 2
        assert result.success_rate == 0.95
        assert result.execution_time == 12.5
        assert len(result.remaining_issues) == 1

    def test_auto_fix_result_is_successful(self) -> None:
        """Test auto-fix success determination."""
        # Successful fix result
        success_result = AutoFixResult(
            fixes_applied=["Fix 1", "Fix 2"],
            files_modified=["file.py"],
            success_rate=0.9,
            remaining_issues=[]
        )
        
        assert success_result.is_successful()
        
        # Failed fix result
        failed_result = AutoFixResult(
            fixes_applied=[],
            files_modified=[],
            success_rate=0.1,
            remaining_issues=["Major error"]
        )
        
        assert not failed_result.is_successful()

    def test_auto_fix_result_merge(self) -> None:
        """Test merging multiple auto-fix results."""
        result1 = AutoFixResult(
            fixes_applied=["Fix A"],
            files_modified=["file1.py"],
            success_rate=0.8,
            execution_time=10.0
        )
        
        result2 = AutoFixResult(
            fixes_applied=["Fix B", "Fix C"],
            files_modified=["file2.py", "file3.py"],
            success_rate=0.9,
            execution_time=15.0
        )
        
        merged = AutoFixResult.merge([result1, result2])
        
        assert len(merged.fixes_applied) == 3
        assert len(merged.files_modified) == 3
        assert merged.execution_time == 25.0
        # Success rate should be weighted average or calculated appropriately


class TestIterationResult:
    """Tests for iteration result functionality."""

    def test_iteration_result_creation(self) -> None:
        """Test iteration result creation."""
        result = IterationResult(
            iteration=3,
            analysis_result=AnalysisResult(
                context=AnalysisContext(iteration=3, hook_errors=[], test_failures=[], previous_fixes=[]),
                identified_patterns=[],
                recommended_fixes=[],
                confidence_score=0.8
            ),
            auto_fix_result=AutoFixResult(
                fixes_applied=["Fix applied"],
                files_modified=["file.py"],
                success_rate=0.9
            ),
            hook_results={"ruff-check": True, "pyright": False},
            test_results={"passed": 45, "failed": 3, "total": 48},
            execution_time=120.5
        )
        
        assert result.iteration == 3
        assert result.execution_time == 120.5
        assert result.hook_results["ruff-check"] is True
        assert result.test_results["passed"] == 45

    def test_iteration_result_is_converged(self) -> None:
        """Test iteration convergence determination."""
        # Converged result (all checks pass)
        converged_result = IterationResult(
            iteration=2,
            analysis_result=AnalysisResult(
                context=AnalysisContext(iteration=2, hook_errors=[], test_failures=[], previous_fixes=[]),
                identified_patterns=[],
                recommended_fixes=[],
                confidence_score=1.0
            ),
            auto_fix_result=AutoFixResult(
                fixes_applied=[],
                files_modified=[],
                success_rate=1.0,
                remaining_issues=[]
            ),
            hook_results={"ruff-check": True, "pyright": True},
            test_results={"passed": 50, "failed": 0, "total": 50}
        )
        
        assert converged_result.is_converged()
        
        # Non-converged result (still has failures)
        non_converged_result = IterationResult(
            iteration=1,
            analysis_result=AnalysisResult(
                context=AnalysisContext(iteration=1, hook_errors=["Error"], test_failures=[], previous_fixes=[]),
                identified_patterns=[],
                recommended_fixes=[],
                confidence_score=0.5
            ),
            auto_fix_result=AutoFixResult(
                fixes_applied=[],
                files_modified=[],
                success_rate=0.5,
                remaining_issues=["Issue remains"]
            ),
            hook_results={"pyright": False},
            test_results={"passed": 40, "failed": 5, "total": 45}
        )
        
        assert not non_converged_result.is_converged()

    def test_iteration_result_get_summary(self) -> None:
        """Test iteration result summary generation."""
        result = IterationResult(
            iteration=1,
            analysis_result=AnalysisResult(
                context=AnalysisContext(iteration=1, hook_errors=["Error 1"], test_failures=["Test fail"], previous_fixes=[]),
                identified_patterns=["pattern1"],
                recommended_fixes=["Fix 1"],
                confidence_score=0.7
            ),
            auto_fix_result=AutoFixResult(
                fixes_applied=["Applied fix"],
                files_modified=["file.py"],
                success_rate=0.8
            ),
            hook_results={"ruff-check": True, "pyright": False},
            test_results={"passed": 42, "failed": 8, "total": 50},
            execution_time=95.0
        )
        
        summary = result.get_summary()
        
        assert summary["iteration"] == 1
        assert summary["hooks_passed"] == 1
        assert summary["hooks_failed"] == 1
        assert summary["tests_passed"] == 42
        assert summary["tests_failed"] == 8
        assert summary["fixes_applied"] == 1
        assert summary["execution_time"] == 95.0


class TestSmartErrorAnalyzer:
    """Tests for smart error analysis functionality."""

    @pytest.fixture
    def analyzer(self) -> SmartErrorAnalyzer:
        """Create a smart error analyzer for testing."""
        return SmartErrorAnalyzer()

    def test_analyzer_initialization(self, analyzer: SmartErrorAnalyzer) -> None:
        """Test analyzer initialization."""
        assert analyzer is not None
        assert len(analyzer.fix_patterns) > 0
        assert analyzer.learning_enabled is True

    def test_analyzer_analyze_context(self, analyzer: SmartErrorAnalyzer) -> None:
        """Test context analysis functionality."""
        context = AnalysisContext(
            iteration=1,
            hook_errors=["Type error: cannot assign str to int", "Import error: module not found"],
            test_failures=["test_calculation failed: division by zero"],
            previous_fixes=[]
        )
        
        result = analyzer.analyze_context(context)
        
        assert isinstance(result, AnalysisResult)
        assert result.context == context
        assert len(result.identified_patterns) > 0
        assert len(result.recommended_fixes) > 0
        assert 0.0 <= result.confidence_score <= 1.0

    def test_analyzer_pattern_matching(self, analyzer: SmartErrorAnalyzer) -> None:
        """Test error pattern matching."""
        errors = [
            "TypeError: expected int, got str",
            "ImportError: No module named 'missing_package'",
            "AttributeError: 'NoneType' object has no attribute 'value'"
        ]
        
        matches = []
        for error in errors:
            patterns = analyzer._find_matching_patterns(error)
            matches.extend(patterns)
        
        assert len(matches) > 0
        # Should find patterns for common error types

    def test_analyzer_fix_generation(self, analyzer: SmartErrorAnalyzer) -> None:
        """Test fix generation from error analysis."""
        context = AnalysisContext(
            iteration=1,
            hook_errors=["F401: 'unused_import' imported but unused"],
            test_failures=[],
            previous_fixes=[]
        )
        
        result = analyzer.analyze_context(context)
        
        assert len(result.recommended_fixes) > 0
        # Should generate fix for unused import
        fix_descriptions = [str(fix) for fix in result.recommended_fixes]
        assert any("import" in fix.lower() for fix in fix_descriptions)

    def test_analyzer_confidence_scoring(self, analyzer: SmartErrorAnalyzer) -> None:
        """Test confidence score calculation."""
        # High-confidence scenario (common patterns)
        high_confidence_context = AnalysisContext(
            iteration=1,
            hook_errors=["F401: 'os' imported but unused", "E302: expected 2 blank lines"],
            test_failures=[],
            previous_fixes=[]
        )
        
        high_result = analyzer.analyze_context(high_confidence_context)
        
        # Low-confidence scenario (complex or unknown patterns)
        low_confidence_context = AnalysisContext(
            iteration=1,
            hook_errors=["Complex logic error in advanced_calculation()"],
            test_failures=["Intermittent test failure in parallel execution"],
            previous_fixes=[]
        )
        
        low_result = analyzer.analyze_context(low_confidence_context)
        
        # High-confidence should be higher than low-confidence
        assert high_result.confidence_score > low_result.confidence_score

    def test_analyzer_learning_from_fixes(self, analyzer: SmartErrorAnalyzer) -> None:
        """Test learning from successful fixes."""
        # Apply a fix and learn from it
        original_pattern_count = len(analyzer.fix_patterns)
        
        success_context = AnalysisContext(
            iteration=2,
            hook_errors=[],
            test_failures=[],
            previous_fixes=["Fixed custom error by adding validation"]
        )
        
        # Simulate learning from successful fix
        analyzer._learn_from_success("Custom error pattern", "Fixed custom error by adding validation", 0.95)
        
        # Should either update existing pattern or add new one
        assert len(analyzer.fix_patterns) >= original_pattern_count

    def test_analyzer_time_estimation(self, analyzer: SmartErrorAnalyzer) -> None:
        """Test fix time estimation."""
        context = AnalysisContext(
            iteration=1,
            hook_errors=["Simple formatting error", "Complex type annotation needed"],
            test_failures=["Basic test assertion failed"],
            previous_fixes=[]
        )
        
        result = analyzer.analyze_context(context)
        
        assert result.estimated_fix_time > 0
        assert result.estimated_fix_time < 3600  # Should be reasonable (< 1 hour)


class TestExecutionResult:
    """Tests for execution result functionality."""

    def test_execution_result_creation(self) -> None:
        """Test execution result creation."""
        iterations = [
            IterationResult(
                iteration=1,
                analysis_result=AnalysisResult(
                    context=AnalysisContext(iteration=1, hook_errors=["Error"], test_failures=[], previous_fixes=[]),
                    identified_patterns=[],
                    recommended_fixes=[],
                    confidence_score=0.7
                ),
                auto_fix_result=AutoFixResult(
                    fixes_applied=["Fix 1"],
                    files_modified=["file.py"],
                    success_rate=0.8
                ),
                hook_results={},
                test_results={"passed": 40, "failed": 10},
                execution_time=60.0
            )
        ]
        
        result = ExecutionResult(
            iterations=iterations,
            final_success=True,
            total_execution_time=60.0,
            convergence_achieved=True
        )
        
        assert len(result.iterations) == 1
        assert result.final_success is True
        assert result.total_execution_time == 60.0
        assert result.convergence_achieved is True

    def test_execution_result_statistics(self) -> None:
        """Test execution result statistics calculation."""
        iterations = [
            IterationResult(
                iteration=1,
                analysis_result=AnalysisResult(
                    context=AnalysisContext(iteration=1, hook_errors=[], test_failures=[], previous_fixes=[]),
                    identified_patterns=[],
                    recommended_fixes=[],
                    confidence_score=0.8
                ),
                auto_fix_result=AutoFixResult(
                    fixes_applied=["Fix A", "Fix B"],
                    files_modified=["file1.py"],
                    success_rate=0.9
                ),
                hook_results={"ruff-check": True, "pyright": False},
                test_results={"passed": 45, "failed": 5},
                execution_time=30.0
            ),
            IterationResult(
                iteration=2,
                analysis_result=AnalysisResult(
                    context=AnalysisContext(iteration=2, hook_errors=[], test_failures=[], previous_fixes=[]),
                    identified_patterns=[],
                    recommended_fixes=[],
                    confidence_score=0.9
                ),
                auto_fix_result=AutoFixResult(
                    fixes_applied=["Fix C"],
                    files_modified=["file2.py"],
                    success_rate=1.0
                ),
                hook_results={"ruff-check": True, "pyright": True},
                test_results={"passed": 50, "failed": 0},
                execution_time=20.0
            )
        ]
        
        result = ExecutionResult(
            iterations=iterations,
            final_success=True,
            total_execution_time=50.0,
            convergence_achieved=True
        )
        
        stats = result.get_statistics()
        
        assert stats["total_iterations"] == 2
        assert stats["total_fixes_applied"] == 3
        assert stats["total_files_modified"] == 2
        assert stats["final_test_success_rate"] == 1.0  # 50/50 in final iteration
        assert stats["average_iteration_time"] == 25.0


class TestMCPExecutionToolsIntegration:
    """Integration tests for MCP execution tools."""

    @pytest.mark.asyncio
    async def test_execute_crackerjack_with_auto_fix_integration(self) -> None:
        """Test full integration of crackerjack execution with auto-fix."""
        with patch('crackerjack.mcp.tools.execution_tools.run_workflow') as mock_workflow:
            with patch('crackerjack.mcp.tools.execution_tools.SmartErrorAnalyzer') as mock_analyzer_class:
                # Setup mocks
                mock_analyzer = Mock()
                mock_analyzer.analyze_context.return_value = AnalysisResult(
                    context=AnalysisContext(iteration=1, hook_errors=[], test_failures=[], previous_fixes=[]),
                    identified_patterns=["pattern1"],
                    recommended_fixes=["Fix suggestion"],
                    confidence_score=0.8,
                    estimated_fix_time=30.0
                )
                mock_analyzer_class.return_value = mock_analyzer
                
                mock_workflow.return_value = {
                    "success": True,
                    "hook_results": [{"name": "ruff-check", "success": True}],
                    "test_results": {"passed": 50, "failed": 0, "total": 50}
                }
                
                # Execute
                result = await execute_crackerjack_with_auto_fix(
                    max_iterations=2,
                    confidence_threshold=0.7
                )
                
                assert result.final_success is True
                assert len(result.iterations) > 0

    @pytest.mark.asyncio
    async def test_run_crackerjack_stage_integration(self) -> None:
        """Test running specific crackerjack stages."""
        with patch('crackerjack.mcp.tools.execution_tools.execute_stage') as mock_execute:
            mock_execute.return_value = {
                "success": True,
                "stage": "hooks",
                "results": {"hooks_passed": 5, "hooks_failed": 0},
                "execution_time": 25.0
            }
            
            result = await run_crackerjack_stage(
                stage="hooks",
                options={"fast_only": True}
            )
            
            assert result["success"] is True
            assert result["stage"] == "hooks"
            assert result["execution_time"] == 25.0

    @pytest.mark.asyncio
    async def test_error_analyzer_real_world_scenario(self) -> None:
        """Test error analyzer with real-world error scenarios."""
        analyzer = SmartErrorAnalyzer()
        
        # Realistic error scenario
        context = AnalysisContext(
            iteration=1,
            hook_errors=[
                "E501: line too long (88 > 87 characters)",
                "F401: 'typing' imported but unused",
                "Type error: Argument of type 'str | None' cannot be assigned to parameter of type 'str'"
            ],
            test_failures=[
                "test_user_registration FAILED - assert None is not None",
                "test_data_validation FAILED - KeyError: 'required_field'"
            ],
            previous_fixes=[],
            codebase_state={"coverage": 38.5, "complexity": 22}
        )
        
        result = analyzer.analyze_context(context)
        
        assert len(result.recommended_fixes) > 0
        assert result.confidence_score > 0.5  # Should have reasonable confidence
        assert result.estimated_fix_time > 0
        
        # Should identify common patterns
        assert len(result.identified_patterns) > 0

    def test_performance_with_large_error_sets(self) -> None:
        """Test performance with large numbers of errors."""
        analyzer = SmartErrorAnalyzer()
        
        # Generate large error set
        hook_errors = [f"Error {i}: Type mismatch in function_{i}" for i in range(100)]
        test_failures = [f"test_function_{i} FAILED - assertion error" for i in range(50)]
        
        context = AnalysisContext(
            iteration=1,
            hook_errors=hook_errors,
            test_failures=test_failures,
            previous_fixes=[]
        )
        
        start_time = time.time()
        result = analyzer.analyze_context(context)
        end_time = time.time()
        
        # Should complete analysis in reasonable time (< 5 seconds for 150 errors)
        assert end_time - start_time < 5.0
        assert len(result.recommended_fixes) > 0
        assert result.confidence_score > 0

    @pytest.mark.asyncio
    async def test_concurrent_analysis_execution(self) -> None:
        """Test concurrent analysis and fix execution."""
        analyzer = SmartErrorAnalyzer()
        
        # Multiple contexts for concurrent analysis
        contexts = [
            AnalysisContext(
                iteration=i,
                hook_errors=[f"Error in module_{i}"],
                test_failures=[],
                previous_fixes=[]
            )
            for i in range(5)
        ]
        
        # Analyze concurrently
        start_time = time.time()
        tasks = [asyncio.create_task(asyncio.to_thread(analyzer.analyze_context, ctx)) for ctx in contexts]
        results = await asyncio.gather(*tasks)
        end_time = time.time()
        
        assert len(results) == 5
        assert all(isinstance(r, AnalysisResult) for r in results)
        # Concurrent execution should be faster than sequential
        assert end_time - start_time < 10.0

    def test_fix_pattern_database_consistency(self) -> None:
        """Test fix pattern database consistency and integrity."""
        analyzer = SmartErrorAnalyzer()
        
        # Verify all patterns have required fields
        for pattern in analyzer.fix_patterns:
            assert pattern.pattern_id is not None
            assert len(pattern.pattern_id) > 0
            assert pattern.pattern_name is not None
            assert len(pattern.error_patterns) > 0
            assert 0.0 <= pattern.confidence <= 1.0
            
        # Verify pattern uniqueness
        pattern_ids = [p.pattern_id for p in analyzer.fix_patterns]
        assert len(pattern_ids) == len(set(pattern_ids))  # No duplicates

    @pytest.mark.asyncio
    async def test_iterative_improvement_workflow(self) -> None:
        """Test iterative improvement workflow simulation."""
        analyzer = SmartErrorAnalyzer()
        
        # Simulate multiple iterations with decreasing errors
        iteration_contexts = [
            AnalysisContext(
                iteration=1,
                hook_errors=["Error A", "Error B", "Error C"],
                test_failures=["Test 1", "Test 2"],
                previous_fixes=[]
            ),
            AnalysisContext(
                iteration=2,
                hook_errors=["Error B"],  # Error A fixed
                test_failures=["Test 2"],  # Test 1 fixed
                previous_fixes=["Fixed Error A", "Fixed Test 1"]
            ),
            AnalysisContext(
                iteration=3,
                hook_errors=[],  # All errors fixed
                test_failures=[],  # All tests fixed
                previous_fixes=["Fixed Error A", "Fixed Test 1", "Fixed Error B", "Fixed Test 2"]
            )
        ]
        
        results = []
        for context in iteration_contexts:
            result = analyzer.analyze_context(context)
            results.append(result)
        
        # Should show improvement trend
        assert len(results) == 3
        assert results[0].confidence_score <= results[1].confidence_score <= results[2].confidence_score
        assert len(results[2].recommended_fixes) <= len(results[0].recommended_fixes)