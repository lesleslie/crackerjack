# Symbiotic Ecosystem Integration - Detailed Task Breakdown

**Total Estimated Effort:** 120-160 hours (3-4 weeks)
**Parallel Execution Potential:** 3-5 agents simultaneously

______________________________________________________________________

## Phase 1: Foundation Completion (12-16 hours)

**Status:** Core components complete, needs MCP exports and testing

### Task 1.1: Crackerjack MCP Tools (3-4 hours)

**File:** `crackerjack/mcp/tools/git_metrics_tools.py` (NEW)

**Responsibilities:**

```python
"""MCP tools for git metrics collection and analysis."""

from mcp.server import FastMCP
from pathlib import Path
from crackerjack.memory.git_metrics_collector import GitMetricsCollector

mcp = FastMCP("crackerjack-git-metrics")

@mcp.tool()
def collect_git_metrics(
    repo_path: str,
    days_back: int = 30
) -> dict:
    """Collect git metrics for repository.

    Args:
        repo_path: Path to git repository
        days_back: Number of days to analyze (default: 30)

    Returns:
        Dict with commit, branch, and merge metrics
    """
    collector = GitMetricsCollector(Path(repo_path))
    dashboard = collector.get_velocity_dashboard(days_back=days_back)

    return {
        "period_start": dashboard.period_start.isoformat(),
        "period_end": dashboard.period_end.isoformat(),
        "commits": {
            "total": dashboard.commit_metrics.total_commits,
            "per_day": dashboard.commit_metrics.avg_commits_per_day,
            "conventional_rate": dashboard.commit_metrics.conventional_compliance_rate,
        },
        "branches": {
            "total": dashboard.branch_metrics.total_branches,
            "active": dashboard.branch_metrics.active_branches,
            "switches": dashboard.branch_metrics.branch_switches,
        },
        "merges": {
            "total": dashboard.merge_metrics.total_merges,
            "conflicts": dashboard.merge_metrics.total_conflicts,
            "conflict_rate": dashboard.merge_metrics.conflict_rate,
        },
    }

@mcp.tool()
def get_repository_velocity(
    repo_path: str,
    days_back: int = 30
) -> float:
    """Get commit velocity for repository.

    Args:
        repo_path: Path to git repository
        days_back: Number of days to analyze

    Returns:
        Commits per day
    """
    collector = GitMetricsCollector(Path(repo_path))
    metrics = collector.collect_commit_metrics(days_back=days_back)
    return metrics.avg_commits_per_day

@mcp.tool()
def get_repository_health(
    repo_path: str
) -> dict:
    """Get repository health indicators.

    Args:
        repo_path: Path to git repository

    Returns:
        Dict with health metrics (stale branches, conflict rate, etc.)
    """
    collector = GitMetricsCollector(Path(repo_path))
    branch_metrics = collector.collect_branch_activity()
    merge_metrics = collector.collect_merge_patterns()

    return {
        "active_branches": branch_metrics.active_branches,
        "branch_switches": branch_metrics.branch_switches,
        "merge_conflict_rate": merge_metrics.conflict_rate,
        "merge_success_rate": merge_metrics.merge_success_rate,
    }
```

**Acceptance Criteria:**

- [ ] All 3 tools callable via MCP
- [ ] Error handling for invalid repositories
- [ ] Return types match FastMCP schema
- [ ] Security: Path validation to prevent traversal

______________________________________________________________________

### Task 1.2: Fix Strategy MCP Tools (2-3 hours)

**File:** `crackerjack/mcp/tools/fix_strategy_tools.py` (NEW)

**Responsibilities:**

```python
"""MCP tools for fix strategy memory and recommendations."""

from mcp.server import FastMCP
from pathlib import Path
from crackerjack.memory.fix_strategy_storage import FixStrategyStorage
from crackerjack.memory.issue_embedder import IssueEmbedder
from crackerjack.agents.base import Issue

mcp = FastMCP("crackerjack-fix-strategy")

@mcp.tool()
def get_strategy_recommendation(
    issue_type: str,
    issue_message: str,
    file_path: str | None = None,
    stage: str = "unknown",
    db_path: str = ".crackerjack/fix_strategy_memory.db"
) -> dict | None:
    """Get fix strategy recommendation based on historical success.

    Args:
        issue_type: Type of issue (e.g., "type_error", "security")
        issue_message: Issue message
        file_path: Optional file path
        stage: Stage where issue occurred
        db_path: Path to fix strategy database

    Returns:
        Dict with {agent_strategy, confidence} or None
    """
    # Create mock issue
    issue = Issue(
        type=issue_type,
        message=issue_message,
        file_path=file_path,
        stage=stage,
    )

    # Initialize components
    storage = FixStrategyStorage(Path(db_path))
    embedder = IssueEmbedder()

    # Get embedding and recommendation
    embedding = embedder.embed_issue(issue)
    result = storage.get_strategy_recommendation(issue, embedding, k=10)

    if result:
        agent_strategy, confidence = result
        return {
            "agent_strategy": agent_strategy,
            "confidence": confidence,
        }

    return None

@mcp.tool()
def get_strategy_statistics(
    db_path: str = ".crackerjack/fix_strategy_memory.db"
) -> dict:
    """Get overall fix strategy statistics.

    Args:
        db_path: Path to fix strategy database

    Returns:
        Dict with total_attempts, success_rate, top_strategies
    """
    storage = FixStrategyStorage(Path(db_path))
    return storage.get_statistics()

@mcp.tool()
def find_similar_issues(
    issue_type: str,
    issue_message: str,
    k: int = 10,
    min_similarity: float = 0.3,
    db_path: str = ".crackerjack/fix_strategy_memory.db"
) -> list[dict]:
    """Find similar historical issues.

    Args:
        issue_type: Type of issue
        issue_message: Issue message
        k: Number of similar issues to return
        min_similarity: Minimum similarity threshold (0-1)
        db_path: Path to fix strategy database

    Returns:
        List of similar issues with similarity scores
    """
    # Create mock issue and get embedding
    issue = Issue(
        type=issue_type,
        message=issue_message,
        file_path=None,
        stage="unknown",
    )

    embedder = IssueEmbedder()
    embedding = embedder.embed_issue(issue)

    # Find similar issues
    storage = FixStrategyStorage(Path(db_path))
    similar = storage.find_similar_issues(
        embedding,
        issue_type=issue_type,
        k=k,
        min_similarity=min_similarity,
    )

    return [
        {
            "issue_type": att.issue_type,
            "issue_message": att.issue_message,
            "file_path": att.file_path,
            "agent_used": att.agent_used,
            "strategy": att.strategy,
            "success": att.success,
            "confidence": att.confidence,
            "timestamp": att.timestamp,
        }
        for att in similar
    ]
```

**Acceptance Criteria:**

- [ ] All 3 tools callable via MCP
- [ ] Strategy recommendation returns confidence score
- [ ] Similar issues ranked by similarity
- [ ] Statistics include top strategies

______________________________________________________________________

### Task 1.3: Unit Tests for Git Metrics (3-4 hours)

**File:** `tests/unit/test_git_metrics_collector.py` (NEW)

**Test Cases:**

```python
"""Unit tests for git metrics collector."""

import pytest
from pathlib import Path
from datetime import datetime, timedelta
from crackerjack.memory.git_metrics_collector import (
    GitMetricsCollector,
    _ConventionalCommitParser,
)

@pytest.fixture
def temp_repo(tmp_path: Path):
    """Create temporary git repository."""
    import subprocess
    repo = tmp_path / "test_repo"
    repo.mkdir()

    # Initialize git repo
    subprocess.run(["git", "init"], cwd=repo, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=repo,
        check=True
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=repo,
        check=True
    )

    # Create test commit
    test_file = repo / "test.txt"
    test_file.write_text("Hello")
    subprocess.run(["git", "add", "test.txt"], cwd=repo, check=True)
    subprocess.run(
        ["git", "commit", "-m", "feat: add test file"],
        cwd=repo,
        check=True
    )

    return repo

def test_conventional_commit_parser():
    """Test conventional commit parsing."""
    # Test conventional commit
    is_conv, type_, scope, breaking = _ConventionalCommitParser.parse(
        "feat(api): add new endpoint"
    )
    assert is_conv is True
    assert type_ == "feat"
    assert scope == "api"
    assert breaking is False

    # Test breaking change
    is_conv, type_, scope, breaking = _ConventionalCommitParser.parse(
        "feat!: breaking API change"
    )
    assert is_conv is True
    assert breaking is True

    # Test non-conventional
    is_conv, type_, scope, breaking = _ConventionalCommitParser.parse(
        "Add new feature"
    )
    assert is_conv is False
    assert type_ is None

def test_collect_commit_metrics(temp_repo: Path):
    """Test commit metrics collection."""
    collector = GitMetricsCollector(temp_repo)

    metrics = collector.collect_commit_metrics(
        since=datetime.now() - timedelta(days=1),
        until=datetime.now()
    )

    assert metrics.total_commits >= 1
    assert metrics.conventional_commits >= 1
    assert 0 <= metrics.conventional_compliance_rate <= 1
    assert metrics.avg_commits_per_day >= 0

def test_collect_branch_activity(temp_repo: Path):
    """Test branch activity collection."""
    collector = GitMetricsCollector(temp_repo)

    metrics = collector.collect_branch_activity(
        since=datetime.now() - timedelta(days=1)
    )

    assert metrics.total_branches >= 1  # At least main branch
    assert metrics.branch_switches >= 0

def test_velocity_dashboard(temp_repo: Path):
    """Test velocity dashboard generation."""
    collector = GitMetricsCollector(temp_repo)

    dashboard = collector.get_velocity_dashboard(days_back=1)

    assert dashboard.period_start < dashboard.period_end
    assert dashboard.commit_metrics.total_commits >= 0
    assert dashboard.branch_metrics.total_branches >= 0
    assert dashboard.merge_metrics.total_merges >= 0
    assert len(dashboard.trend_data) >= 0

def test_invalid_repository(tmp_path: Path):
    """Test error handling for invalid repository."""
    non_repo = tmp_path / "not_a_repo"
    non_repo.mkdir()

    with pytest.raises(ValueError, match="Not a git repository"):
        GitMetricsCollector(non_repo)
```

**Acceptance Criteria:**

- [ ] 15+ test cases covering all major functions
- [ ] Mock git repository for isolated testing
- [ ] Test error handling (invalid repos, etc.)
- [ ] Test conventional commit parsing
- [ ] Test metrics calculations
- [ ] Coverage > 90%

______________________________________________________________________

### Task 1.4: Unit Tests for Fix Strategy (2-3 hours)

**File:** `tests/unit/test_fix_strategy_storage.py` (NEW)

**Test Cases:**

```python
"""Unit tests for fix strategy storage."""

import pytest
import numpy as np
from pathlib import Path
from crackerjack.memory.fix_strategy_storage import (
    FixStrategyStorage,
    FixAttempt,
)
from crackerjack.agents.base import Issue, FixResult

@pytest.fixture
def storage(tmp_path: Path):
    """Create temporary fix strategy storage."""
    db_path = tmp_path / "test.db"
    return FixStrategyStorage(db_path)

def test_record_and_retrieve_fix_attempt(storage: FixStrategyStorage):
    """Test recording and retrieving fix attempts."""
    issue = Issue(
        type="type_error",
        message="incompatible type",
        file_path="test.py",
        stage="type_checking",
    )

    result = FixResult(
        success=True,
        confidence=0.8,
        fixes_applied=["Added type annotation"],
        remaining_issues=[],
    )

    # Record attempt
    embedding = np.random.rand(384).astype(np.float32)
    storage.record_attempt(
        issue=issue,
        result=result,
        agent_used="RefactoringAgent",
        strategy="add_type_annotation",
        issue_embedding=embedding,
        session_id="test_session",
    )

    # Retrieve similar issues
    similar = storage.find_similar_issues(
        issue_embedding=embedding,
        k=5,
    )

    assert len(similar) >= 1
    assert similar[0].agent_used == "RefactoringAgent"
    assert similar[0].strategy == "add_type_annotation"

def test_strategy_recommendation(storage: FixStrategyStorage):
    """Test strategy recommendation."""
    # Create multiple similar issues with different outcomes
    embedding = np.random.rand(384).astype(np.float32)

    # Record successful attempt
    issue = Issue(
        type="type_error",
        message="type mismatch",
        file_path="test.py",
        stage="type_checking",
    )

    result = FixResult(
        success=True,
        confidence=0.9,
        fixes_applied=["Fixed type"],
        remaining_issues=[],
    )

    storage.record_attempt(
        issue=issue,
        result=result,
        agent_used="RefactoringAgent",
        strategy="fix_type",
        issue_embedding=embedding,
    )

    # Get recommendation
    recommendation = storage.get_strategy_recommendation(
        issue=issue,
        issue_embedding=embedding,
        k=5,
    )

    assert recommendation is not None
    agent_strategy, confidence = recommendation
    assert agent_strategy == "RefactoringAgent:fix_type"
    assert confidence > 0

def test_cosine_similarity():
    """Test cosine similarity calculation."""
    vec_a = np.array([1.0, 0.0, 0.0])
    vec_b = np.array([1.0, 0.0, 0.0])
    vec_c = np.array([0.0, 1.0, 0.0])

    # Identical vectors
    sim_ab = FixStrategyStorage._cosine_similarity(vec_a, vec_b)
    assert sim_ab == pytest.approx(1.0)

    # Orthogonal vectors
    sim_ac = FixStrategyStorage._cosine_similarity(vec_a, vec_c)
    assert sim_ac == pytest.approx(0.0)

def test_statistics(storage: FixStrategyStorage):
    """Test statistics retrieval."""
    # Record some attempts
    for i in range(10):
        issue = Issue(
            type="test_type",
            message=f"test message {i}",
            file_path="test.py",
            stage="test",
        )

        result = FixResult(
            success=(i % 2 == 0),  # 50% success rate
            confidence=0.8,
            fixes_applied=[],
            remaining_issues=[],
        )

        embedding = np.random.rand(384).astype(np.float32)
        storage.record_attempt(
            issue=issue,
            result=result,
            agent_used="TestAgent",
            strategy="test_strategy",
            issue_embedding=embedding,
        )

    stats = storage.get_statistics()

    assert stats["total_attempts"] == 10
    assert stats["successful_attempts"] == 5
    assert stats["overall_success_rate"] == pytest.approx(0.5)
```

**Acceptance Criteria:**

- [ ] 10+ test cases
- [ ] Test CRUD operations
- [ ] Test similarity calculation
- [ ] Test recommendation logic
- [ ] Test statistics aggregation
- [ ] Coverage > 90%

______________________________________________________________________

## Phase 2: Integration (40-50 hours)

### Task 2.1: Akosha Git History Embedder (8-10 hours)

**File:** `akosha/git_history_embedder.py` (NEW)

**Responsibilities:**

```python
"""Git history embedder for semantic search."""

from pathlib import Path
from typing import List, Dict
import numpy as np
from sentence_transformers import SentenceTransformer

class GitHistoryEmbedder:
    """Embed git history for semantic search.

    Features:
    - Index commit messages for natural language search
    - Find similar past commits by semantic similarity
    - Query optimization based on click-through
    """

    def __init__(
        self,
        repo_path: Path,
        model_name: str = "all-MiniLM-L6-v2"
    ):
        self.repo_path = repo_path
        self.model = SentenceTransformer(model_name)
        self.embedding_dim = self.model.get_sentence_embedding_dimension()

        # Load or create index
        self.index_path = repo_path / ".akosha" / "git_history_index.npz"
        self._load_or_create_index()

    def _load_or_create_index(self):
        """Load existing index or create new one."""
        if self.index_path.exists():
            data = np.load(self.index_path)
            self.commits = data["commits"].tolist()
            self.embeddings = data["embeddings"]
        else:
            self.commits = []
            self.embeddings = np.empty((0, self.embedding_dim))

    def index_commits(self, days_back: int = 90) -> int:
        """Index recent commits for semantic search.

        Args:
            days_back: Number of days to index

        Returns:
            Number of commits indexed
        """
        # Get commit history
        commits = self._get_commit_history(days_back)

        if not commits:
            return 0

        # Generate embeddings
        messages = [
            f"{c['message']} | {c['author']} | {c['date']}"
            for c in commits
        ]

        new_embeddings = self.model.encode(
            messages,
            convert_to_numpy=True,
            show_progress_bar=False,
        )

        # Append to index
        self.commits.extend(commits)
        self.embeddings = np.vstack([self.embeddings, new_embeddings])

        # Save index
        self._save_index()

        return len(commits)

    def search(
        self,
        query: str,
        k: int = 10,
        min_similarity: float = 0.3
    ) -> List[Dict]:
        """Search git history by semantic similarity.

        Args:
            query: Natural language query
            k: Number of results to return
            min_similarity: Minimum similarity threshold

        Returns:
            List of matching commits with similarity scores
        """
        if len(self.embeddings) == 0:
            return []

        # Embed query
        query_embedding = self.model.encode(
            [query],
            convert_to_numpy=True,
        )[0]

        # Calculate similarities
        similarities = np.dot(self.embeddings, query_embedding) / (
            np.linalg.norm(self.embeddings, axis=1) *
            np.linalg.norm(query_embedding)
        )

        # Filter and sort
        indices = np.where(similarities >= min_similarity)[0]
        sorted_indices = indices[np.argsort(similarities[indices])[::-1]]

        results = []
        for idx in sorted_indices[:k]:
            results.append({
                "commit": self.commits[idx],
                "similarity": float(similarities[idx]),
            })

        return results

    def _get_commit_history(self, days_back: int) -> List[Dict]:
        """Get commit history from git repository."""
        import subprocess
        from datetime import datetime, timedelta

        since = (datetime.now() - timedelta(days=days_back)).isoformat()

        result = subprocess.run(
            [
                "git", "-C", str(self.repo_path),
                "log", f"--since={since}",
                '--pretty=format:%H|%ai|%an|%s'
            ],
            capture_output=True,
            text=True,
            check=True,
        )

        commits = []
        for line in result.stdout.strip().split("\n"):
            if not line:
                continue

            parts = line.split("|", 3)
            if len(parts) == 4:
                commits.append({
                    "hash": parts[0],
                    "date": parts[1],
                    "author": parts[2],
                    "message": parts[3],
                })

        return commits

    def _save_index(self):
        """Save index to disk."""
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        np.savez(
            self.index_path,
            commits=self.commits,
            embeddings=self.embeddings,
        )
```

**Acceptance Criteria:**

- [ ] Index commits from git log
- [ ] Semantic search returns relevant results
- [ ] Search performance < 500ms
- [ ] Index persistence across restarts

______________________________________________________________________

### Task 2.2: Extend SessionMetrics (2-3 hours)

**File:** `session_buddy/core/workflow_metrics.py` (MODIFY)

**Changes:**

```python
from dataclasses import dataclass, field
from typing import Dict

@dataclass
class SessionMetrics:
    """Extended session metrics with git velocity data."""

    # Existing fields...
    session_id: str
    start_time: datetime
    end_time: datetime | None = None

    # NEW: Git velocity metrics
    git_velocity: Dict[str, float] = field(default_factory=dict)
    """Project -> commits per day"""

    branch_switch_frequency: Dict[str, float] = field(default_factory=dict)
    """Project -> branch switches per day"""

    merge_conflict_rate: Dict[str, float] = field(default_factory=dict)
    """Project -> merge conflicts per day"""

    conventional_compliance: Dict[str, float] = field(default_factory=dict)
    """Project -> conventional commit rate"""

    def get_git_velocity_summary(self) -> Dict:
        """Get aggregated git velocity across all projects."""
        if not self.git_velocity:
            return {"avg_velocity": 0.0, "total_projects": 0}

        total_velocity = sum(self.git_velocity.values())
        avg_velocity = total_velocity / len(self.git_velocity)

        return {
            "avg_velocity": avg_velocity,
            "total_projects": len(self.git_velocity),
            "top_projects": sorted(
                self.git_velocity.items(),
                key=lambda x: x[1],
                reverse=True
            )[:5],
        }
```

**Acceptance Criteria:**

- [ ] Add git metrics fields to SessionMetrics
- [ ] Add summary method for aggregation
- [ ] Backward compatible with existing code

______________________________________________________________________

### Task 2.3: Mahavishnu Aggregation Client (4-5 hours)

**File:** `session_buddy/integrations/mahavishnu_client.py` (NEW)

**Responsibilities:**

```python
"""Mahavishnu aggregation client for git metrics."""

import httpx
from typing import List, Dict
from pathlib import Path

class MahavishnuAggregationClient:
    """Client for fetching aggregated git metrics from Mahavishnu."""

    def __init__(
        self,
        base_url: str = "http://localhost:8680/mcp",
        timeout: float = 30.0,
    ):
        self.base_url = base_url
        self.timeout = timeout
        self.client = httpx.AsyncClient(timeout=timeout)

    async def get_git_velocity_dashboard(
        self,
        project_paths: List[str],
        days_back: int = 30,
    ) -> Dict:
        """Get git velocity dashboard for multiple projects.

        Args:
            project_paths: List of repository paths
            days_back: Number of days to analyze

        Returns:
            Aggregated velocity dashboard
        """
        response = await self.client.post(
            f"{self.base_url}/tools/get_git_velocity_dashboard",
            json={
                "project_paths": project_paths,
                "days_back": days_back,
            },
        )

        response.raise_for_status()
        return response.json()

    async def get_repository_health(
        self,
        repo_path: str,
    ) -> Dict:
        """Get repository health metrics.

        Args:
            repo_path: Path to repository

        Returns:
            Health metrics (stale branches, conflicts, etc.)
        """
        response = await self.client.post(
            f"{self.base_url}/tools/get_repository_health",
            json={"repo_path": repo_path},
        )

        response.raise_for_status()
        return response.json()

    async def get_cross_project_patterns(
        self,
        days_back: int = 90,
    ) -> Dict:
        """Get patterns across all projects.

        Args:
            days_back: Number of days to analyze

        Returns:
            Cross-project pattern analysis
        """
        response = await self.client.post(
            f"{self.base_url}/tools/get_cross_project_patterns",
            json={"days_back": days_back},
        )

        response.raise_for_status()
        return response.json()

    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()
```

**Acceptance Criteria:**

- [ ] Async HTTP client with proper error handling
- [ ] Retry logic for failed requests
- [ ] Timeout handling
- [ ] Type hints for all responses

______________________________________________________________________

### Task 2.4: Velocity Dashboard MCP Tools (4-5 hours)

**File:** `session_buddy/mcp/tools/velocity_dashboard_tools.py` (NEW)

**Responsibilities:**

```python
"""MCP tools for velocity dashboard."""

from mcp.server import FastMCP
from datetime import datetime, timedelta
from session_buddy.integrations.mahavishnu_client import (
    MahavishnuAggregationClient,
)

mcp = FastMCP("session-buddy-velocity-dashboard")

@mcp.tool()
async def get_velocity_trends(
    project_paths: list[str],
    days_back: int = 30,
) -> dict:
    """Get velocity trends for projects.

    Args:
        project_paths: List of repository paths
        days_back: Number of days to analyze

    Returns:
        Velocity trend data with daily breakdown
    """
    client = MahavishnuAggregationClient()

    try:
        dashboard = await client.get_git_velocity_dashboard(
            project_paths, days_back
        )

        # Transform to trend format
        trends = []
        for project_data in dashboard["projects"]:
            trends.append({
                "project": project_data["path"],
                "commits_per_day": project_data["avg_commits_per_day"],
                "trend": project_data["daily_commits"],
            })

        return {
            "period": f"{days_back} days",
            "trends": trends,
        }
    finally:
        await client.close()

@mcp.tool()
async def get_branch_activity(
    project_paths: list[str],
    days_back: int = 7,
) -> dict:
    """Get branch activity metrics.

    Args:
        project_paths: List of repository paths
        days_back: Number of days to analyze

    Returns:
        Branch activity (switches, creations, deletions)
    """
    client = MahavishnuAggregationClient()

    try:
        results = {}
        for path in project_paths:
            health = await client.get_repository_health(path)
            results[path] = {
                "active_branches": health["active_branches"],
                "branch_switches": health["branch_switches"],
            }

        return results
    finally:
        await client.close()
```

**Acceptance Criteria:**

- [ ] All tools return properly formatted data
- [ ] Async/await patterns used correctly
- [ ] Error handling for network failures

______________________________________________________________________

## Summary

**Total Tasks:** 8 major tasks
**Estimated Hours:** 52-69 hours
**Parallelizable:** Yes (Tasks 2.1-2.4 can run in parallel)

**Next Steps:**

1. Complete Phase 1 (Tasks 1.1-1.4) - 12-16 hours
1. Begin Phase 2 (Tasks 2.1-2.4) - 40-50 hours
1. Phase 3: Learning & Optimization - 30-40 hours

______________________________________________________________________

**Last Updated:** 2025-02-11
