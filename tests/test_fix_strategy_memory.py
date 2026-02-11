"""Test fix strategy memory functionality."""

import pytest
import numpy as np
import tempfile
from pathlib import Path

from crackerjack.memory.fix_strategy_storage import FixStrategyStorage
from crackerjack.agents.base import Issue, IssueType, Priority, FixResult


@pytest.fixture
def temp_db():
    """Create temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)
    yield db_path
    # Cleanup is handled by delete=False and OS


@pytest.fixture
def storage(temp_db):
    """Create FixStrategyStorage instance with temp database."""
    return FixStrategyStorage(db_path=temp_db)


def test_record_and_retrieve_fix_attempt(storage):
    """Test recording and retrieving fix attempts."""
    issue = Issue(
        type=IssueType.TYPE_ERROR,
        severity=Priority.MEDIUM,
        message="incompatible type XYZ",
        file_path="crackerjack/core/xyz.py",
    )

    result = FixResult(
        success=True,
        confidence=0.8,
        fixes_applied=["Added type annotation"],
    )

    # Record attempt
    storage.record_attempt(
        issue=issue,
        result=result,
        agent_used="RefactoringAgent",
        strategy="add_type_annotation",
        issue_embedding=np.random.rand(384).astype(np.float32),
    )

    # Verify it was stored
    stats = storage.get_statistics()
    assert stats["total_attempts"] == 1
    assert stats["successful_attempts"] == 1


def test_find_similar_issues(storage):
    """Test finding similar historical issues."""
    # Create some test data
    embedding1 = np.random.rand(384).astype(np.float32)
    embedding2 = np.random.rand(384).astype(np.float32)
    embedding3 = np.random.rand(384).astype(np.float32)

    storage.record_attempt(
        issue=Issue(
            type=IssueType.TYPE_ERROR,
            severity=Priority.HIGH,
            message="NameError: name 'foo' is not defined",
            file_path="test.py",
        ),
        result=FixResult(success=True, confidence=0.9),
        agent_used="TestAgent",
        strategy="define_variable",
        issue_embedding=embedding1,
    )

    storage.record_attempt(
        issue=Issue(
            type=IssueType.TYPE_ERROR,
            severity=Priority.HIGH,
            message="NameError: name 'bar' is not defined",
            file_path="test.py",
        ),
        result=FixResult(success=False, confidence=0.3),
        agent_used="TestAgent",
        strategy="define_variable",
        issue_embedding=embedding2,
    )

    storage.record_attempt(
        issue=Issue(
            type=IssueType.FORMATTING,
            severity=Priority.LOW,
            message="Line too long",
            file_path="test.py",
        ),
        result=FixResult(success=True, confidence=0.7),
        agent_used="FormattingAgent",
        strategy="wrap_line",
        issue_embedding=embedding3,
    )

    # Find similar to NameError issues (should find first two)
    query_embedding = np.random.rand(384).astype(np.float32)
    similar = storage.find_similar_issues(
        issue_embedding=query_embedding,
        issue_type=IssueType.TYPE_ERROR.value,
        k=5,
        min_similarity=0.0,  # Get all results
    )

    # Should have at least some results
    assert len(similar) >= 2
    # All should be TYPE_ERROR (filtered by type)
    for attempt in similar[:2]:
        assert attempt.issue_type == IssueType.TYPE_ERROR.value


def test_cosine_similarity(storage):
    """Test cosine similarity calculation."""
    # Two identical vectors should have similarity 1.0
    vec1 = np.array([1.0, 2.0, 3.0], dtype=np.float32)
    vec2 = np.array([1.0, 2.0, 3.0], dtype=np.float32)

    similarity = FixStrategyStorage._cosine_similarity(vec1, vec2)
    assert abs(similarity - 1.0) < 0.001  # Allow floating point error

    # Two orthogonal vectors should have low similarity
    vec3 = np.array([1.0, 0.0, 0.0], dtype=np.float32)
    vec4 = np.array([0.0, 1.0, 0.0], dtype=np.float32)

    similarity = FixStrategyStorage._cosine_similarity(vec3, vec4)
    assert similarity < 0.1  # Should be near zero


def test_strategy_recommendation(storage):
    """Test strategy recommendation logic."""
    # Create successful and failed attempts for same issue type
    embedding = np.random.rand(384).astype(np.float32)

    # Record successful attempt with RefactoringAgent
    storage.record_attempt(
        issue=Issue(
            type=IssueType.COMPLEXITY,
            severity=Priority.HIGH,
            message="Function too long",
        ),
        result=FixResult(success=True, confidence=0.8),
        agent_used="RefactoringAgent",
        strategy="extract_function",
        issue_embedding=embedding,
    )

    # Record another successful attempt with same agent:strategy
    storage.record_attempt(
        issue=Issue(
            type=IssueType.COMPLEXITY,
            severity=Priority.HIGH,
            message="Function too long",
        ),
        result=FixResult(success=True, confidence=0.9),
        agent_used="RefactoringAgent",
        strategy="extract_function",
        issue_embedding=embedding,
    )

    # Record failed attempt
    storage.record_attempt(
        issue=Issue(
            type=IssueType.COMPLEXITY,
            severity=Priority.HIGH,
            message="Function too long",
        ),
        result=FixResult(success=False, confidence=0.4),
        agent_used="OtherAgent",
        strategy="unknown_strategy",
        issue_embedding=embedding,
    )

    # Get recommendation
    issue = Issue(
        type=IssueType.COMPLEXITY,
        severity=Priority.HIGH,
        message="Function too long",
    )

    recommendation = storage.get_strategy_recommendation(
        issue=issue,
        issue_embedding=embedding,
        k=10,
    )

    # Should recommend RefactoringAgent:extract_function (most successful)
    assert recommendation is not None
    agent_strategy, confidence = recommendation
    assert "RefactoringAgent" in agent_strategy
    assert "extract_function" in agent_strategy
    assert confidence > 0.7  # High confidence due to multiple successes


def test_statistics_calculation(storage):
    """Test overall statistics calculation."""
    # Create mix of successful and failed attempts
    embedding = np.random.rand(384).astype(np.float32)

    for i in range(10):
        storage.record_attempt(
            issue=Issue(
                type=IssueType.TYPE_ERROR,
                severity=Priority.MEDIUM,
                message=f"Error message {i}",
            ),
            result=FixResult(success=(i % 2 == 0), confidence=0.7),
            agent_used=["RefactoringAgent", "FormattingAgent"][i % 2],
            strategy=f"strategy_{i % 5}",
            issue_embedding=embedding,
        )

    stats = storage.get_statistics()

    # Verify totals
    assert stats["total_attempts"] == 10
    # 5 out of 10 were successful (i % 2 == 0)
    assert stats["successful_attempts"] == 5
    # Success rate should be 0.5
    assert abs(stats["overall_success_rate"] - 0.5) < 0.01

    # Check top strategies
    top_strategies = stats.get("top_strategies", [])
    assert len(top_strategies) > 0


def test_database_cleanup(storage):
    """Test database connection cleanup."""
    # Verify connection is open
    assert storage.conn is not None

    # Close and reopen
    storage.close()
    assert storage.conn is None

    # Create new storage instance
    storage2 = FixStrategyStorage(db_path=storage.db_path)
    assert storage2.conn is not None

    # Cleanup
    storage2.close()


def test_empty_database(storage):
    """Test behavior with empty database."""
    # Query for recommendations when no data
    embedding = np.random.rand(384).astype(np.float32)
    issue = Issue(
        type=IssueType.TYPE_ERROR,
        severity=Priority.HIGH,
        message="Test issue",
    )

    similar = storage.find_similar_issues(
        issue_embedding=embedding,
        k=5,
    )
    assert similar == []  # No results

    recommendation = storage.get_strategy_recommendation(
        issue=issue,
        issue_embedding=embedding,
    )
    assert recommendation is None  # No recommendation

    stats = storage.get_statistics()
    assert stats["total_attempts"] == 0
