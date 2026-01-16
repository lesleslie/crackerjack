"""Tests for reflection loop pattern capture and learning."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from crackerjack.reflection_loop import (
    CommitResult,
    Pattern,
    ReflectionLoop,
    get_reflection_loop,
)


@pytest.fixture
def temp_storage_path(tmp_path: Path) -> Path:
    """Create a temporary storage path for patterns."""
    return tmp_path / "patterns.json"


@pytest.fixture
def reflection_loop(temp_storage_path: Path) -> ReflectionLoop:
    """Create a ReflectionLoop instance with temporary storage."""
    return ReflectionLoop(storage_path=temp_storage_path)


@pytest.fixture
def successful_commit_result() -> CommitResult:
    """Create a sample successful commit result."""
    return CommitResult(
        success=True,
        quality_metrics={
            "security_score": 0.9,
            "performance_score": 0.85,
            "test_coverage": 0.92,
            "documentation_score": 0.88,
        },
        problem_context={
            "error_type": "ImportError",
            "files_changed": ["src/main.py"],
            "commit_message": "Fix missing import",
        },
        applied_fix={
            "description": "Added missing import statement",
            "type": "import_fix",
            "changes": "Added 'from typing import Optional'",
        },
    )


@pytest.fixture
def failed_commit_result() -> CommitResult:
    """Create a sample failed commit result."""
    return CommitResult(
        success=False,
        quality_metrics={
            "security_score": 0.9,  # High security, but test_coverage is low
            "performance_score": 0.85,
            "test_coverage": 0.5,  # This triggers 'testing' category
            "documentation_score": 0.8,
        },
        problem_context={
            "error_type": "AttributeError",
            "files_changed": ["src/api.py"],
            "commit_message": "Attempt fix for attribute error",
        },
        applied_fix={
            "description": "Added getattr wrapper",
            "type": "workaround",
        },
        error_message="AttributeError: 'Response' object has no attribute 'status'",
    )


class TestReflectionLoop:
    """Tests for ReflectionLoop class."""

    def test_init_creates_storage_file(
        self, reflection_loop: ReflectionLoop, temp_storage_path: Path
    ) -> None:
        """Test that initializing ReflectionLoop creates storage file."""
        assert temp_storage_path.exists()
        data = json.loads(temp_storage_path.read_text())
        assert "patterns" in data
        assert isinstance(data["patterns"], list)

    def test_init_loads_existing_patterns(
        self, temp_storage_path: Path
    ) -> None:
        """Test that ReflectionLoop loads existing patterns."""
        # Create existing pattern file
        existing_patterns = {
            "patterns": [
                {
                    "pattern_type": "solution",
                    "category": "testing",
                    "context": {"error_type": "test_failure"},
                    "solution": {"description": "Added test case"},
                    "outcome_score": 0.9,
                    "created_at": "2025-01-15T10:00:00",
                    "last_applied": None,
                    "application_count": 0,
                    "feedback_score": 0.0,
                }
            ]
        }
        temp_storage_path.write_text(json.dumps(existing_patterns, indent=2))

        # Create ReflectionLoop and verify patterns loaded
        loop = ReflectionLoop(storage_path=temp_storage_path)
        assert len(loop.patterns) == 1
        assert loop.patterns[0].pattern_type == "solution"
        assert loop.patterns[0].category == "testing"

    def test_capture_success_pattern(
        self, reflection_loop: ReflectionLoop, successful_commit_result: CommitResult
    ) -> None:
        """Test capturing a successful pattern."""
        initial_count = len(reflection_loop.patterns)

        reflection_loop.analyze_commit(successful_commit_result)

        assert len(reflection_loop.patterns) == initial_count + 1

        pattern = reflection_loop.patterns[-1]
        assert pattern.pattern_type == "solution"
        assert pattern.category == "general"  # Inferred from quality metrics
        assert pattern.outcome_score > 0.8  # Should be high for good metrics
        assert pattern.solution is not None
        assert pattern.solution.get("description") == "Added missing import statement"

    def test_capture_failure_pattern(
        self, reflection_loop: ReflectionLoop, failed_commit_result: CommitResult
    ) -> None:
        """Test capturing a failure pattern."""
        initial_count = len(reflection_loop.patterns)

        reflection_loop.analyze_commit(failed_commit_result)

        assert len(reflection_loop.patterns) == initial_count + 1

        pattern = reflection_loop.patterns[-1]
        assert pattern.pattern_type == "anti_pattern"
        assert pattern.category == "testing"  # Low test_coverage (0.5)
        assert pattern.outcome_score == 0.0  # Failures have 0 score
        assert pattern.solution is None  # No solution for failure

    def test_infer_category_security(self, reflection_loop: ReflectionLoop) -> None:
        """Test category inference for security issues."""
        result = CommitResult(
            success=True,
            quality_metrics={"security_score": 0.5},  # Low security score
            problem_context={"error_type": "SQLInjection"},
            applied_fix={"description": "Used parameterized query"},
        )

        reflection_loop.analyze_commit(result)

        assert reflection_loop.patterns[-1].category == "security"

    def test_infer_category_performance(
        self, reflection_loop: ReflectionLoop
    ) -> None:
        """Test category inference for performance issues."""
        result = CommitResult(
            success=True,
            quality_metrics={"performance_score": 0.6},  # Low performance score
            problem_context={"error_type": "SlowQuery"},
            applied_fix={"description": "Added database index"},
        )

        reflection_loop.analyze_commit(result)

        assert reflection_loop.patterns[-1].category == "performance"

    def test_find_similar_patterns(
        self, reflection_loop: ReflectionLoop, successful_commit_result: CommitResult
    ) -> None:
        """Test finding similar patterns."""
        # Capture a pattern
        reflection_loop.analyze_commit(successful_commit_result)

        # Search for similar patterns with matching context
        # Use identical context to ensure match
        similar = reflection_loop.find_similar_patterns(
            current_context={
                "problem": "ImportError",  # Match the stored context
                "files_changed": ["src/main.py"],
                "quality_metrics": successful_commit_result.quality_metrics,
            },
            threshold=0.3,  # Lower threshold to allow match
        )

        assert len(similar) > 0
        assert similar[0].pattern_type == "solution"

    def test_find_similar_patterns_threshold(
        self, reflection_loop: ReflectionLoop
    ) -> None:
        """Test that similarity threshold filters results."""
        # Create a pattern with specific context
        result = CommitResult(
            success=True,
            quality_metrics={"test_coverage": 0.9},
            problem_context={"error_type": "TypeError", "module": "api"},
            applied_fix={"description": "Fixed type annotation"},
        )
        reflection_loop.analyze_commit(result)

        # Search with different context - should not match
        similar = reflection_loop.find_similar_patterns(
            current_context={"error_type": "ValueError", "module": "utils"},
            threshold=0.8,  # High threshold
        )

        assert len(similar) == 0  # No matches with different context

    def test_apply_pattern_updates_metadata(
        self, reflection_loop: ReflectionLoop
    ) -> None:
        """Test that applying a pattern updates its metadata."""
        # Create a pattern
        result = CommitResult(
            success=True,
            quality_metrics={"test_coverage": 0.85},
            problem_context={"error_type": "ImportError"},
            applied_fix={"description": "Added import"},
        )
        reflection_loop.analyze_commit(result)

        pattern_id = 0  # First pattern
        initial_count = reflection_loop.patterns[pattern_id].application_count
        initial_score = reflection_loop.patterns[pattern_id].feedback_score

        # Apply pattern with success outcome
        reflection_loop.apply_pattern(
            pattern_id=pattern_id, outcome="success", feedback="Worked perfectly"
        )

        # Verify updates
        assert reflection_loop.patterns[pattern_id].application_count == initial_count + 1
        assert reflection_loop.patterns[pattern_id].feedback_score > initial_score
        assert reflection_loop.patterns[pattern_id].last_applied is not None

    def test_apply_pattern_failure_decreases_score(
        self, reflection_loop: ReflectionLoop
    ) -> None:
        """Test that failed pattern application decreases feedback score."""
        # Create a pattern
        result = CommitResult(
            success=True,
            quality_metrics={"test_coverage": 0.85},
            problem_context={"error_type": "ImportError"},
            applied_fix={"description": "Added import"},
        )
        reflection_loop.analyze_commit(result)

        # First apply with success to increase score above 0
        pattern_id = 0
        reflection_loop.apply_pattern(pattern_id=pattern_id, outcome="success")
        score_after_success = reflection_loop.patterns[pattern_id].feedback_score

        # Now apply with failure outcome
        reflection_loop.apply_pattern(pattern_id=pattern_id, outcome="failure")

        # Verify score decreased from the success score
        assert reflection_loop.patterns[pattern_id].feedback_score < score_after_success

    def test_generate_improvements(
        self, reflection_loop: ReflectionLoop
    ) -> None:
        """Test generating improvement suggestions."""
        # Create mixed results
        success_result = CommitResult(
            success=True,
            quality_metrics={"test_coverage": 0.95},  # Excellent
            problem_context={"error_type": "ImportError"},
            applied_fix={"description": "Added import"},
        )

        failure_result = CommitResult(
            success=False,
            quality_metrics={"test_coverage": 0.5},
            problem_context={"error_type": "SyntaxError"},
            applied_fix=None,
            error_message="Invalid syntax",
        )

        improvements = reflection_loop.generate_improvements(
            [success_result, failure_result]
        )

        assert len(improvements) > 0
        assert any("Excellent test coverage" in imp for imp in improvements)
        assert any("Common error pattern" in imp for imp in improvements)

    def test_persistence(
        self, reflection_loop: ReflectionLoop, successful_commit_result: CommitResult
    ) -> None:
        """Test that patterns are persisted to storage."""
        # Add a pattern
        reflection_loop.analyze_commit(successful_commit_result)

        # Create new ReflectionLoop instance (should load from storage)
        new_loop = ReflectionLoop(storage_path=reflection_loop.storage_path)

        assert len(new_loop.patterns) == 1
        assert new_loop.patterns[0].pattern_type == "solution"

    def test_calculate_similarity(self, reflection_loop: ReflectionLoop) -> None:
        """Test similarity calculation between contexts."""
        context1 = {"error_type": "ImportError", "module": "main"}
        context2 = {"error_type": "ImportError", "module": "utils"}
        context3 = {"error_type": "ValueError", "module": "main"}

        # context1 and context2 share 1 key (error_type)
        similarity1 = reflection_loop._calculate_similarity(context1, context2)
        assert similarity1 > 0

        # context1 and context3 share 1 key (module)
        similarity2 = reflection_loop._calculate_similarity(context1, context3)
        assert similarity2 > 0

        # All three contexts share different combinations
        # But context1 vs context2 should equal context1 vs context3
        assert similarity1 == similarity2


class TestGetReflectionLoop:
    """Tests for singleton pattern."""

    def test_singleton_returns_same_instance(self) -> None:
        """Test that get_reflection_loop returns singleton instance."""
        loop1 = get_reflection_loop()
        loop2 = get_reflection_loop()

        assert loop1 is loop2

    def test_singleton_persists_patterns(self) -> None:
        """Test that singleton persists patterns across calls."""
        loop1 = get_reflection_loop()

        result = CommitResult(
            success=True,
            quality_metrics={"test_coverage": 0.9},
            problem_context={"error_type": "TestError"},
            applied_fix={"description": "Added test"},
        )

        loop1.analyze_commit(result)

        # Get singleton again and verify pattern persists
        loop2 = get_reflection_loop()
        assert len(loop2.patterns) > 0
