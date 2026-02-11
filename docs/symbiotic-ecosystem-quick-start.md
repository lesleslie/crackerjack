# Symbiotic Ecosystem - Quick Start Guide

## Overview

The symbiotic ecosystem provides AI-powered workflow optimization by combining:

- **Git Metrics**: Development velocity and pattern tracking
- **Fix Strategy Memory**: Historical success pattern learning
- **Issue Embeddings**: Semantic similarity matching
- **Strategy Recommendations**: Intelligent fix selection
- **Skills Tracking**: Effectiveness monitoring

## Installation

Ensure dependencies are installed:

```bash
# From crackerjack directory
cd /path/to/crackerjack

# Neural embeddings (optional, has TF-IDF fallback)
uv add sentence-transformers

# Or use TF-IDF fallback (no additional deps)
# Works on Python 3.13 + Intel Mac
```

## Quick Start

### 1. Collect Git Metrics

```python
from pathlib import Path
from crackerjack.memory import GitMetricsCollector

# Initialize collector for your repository
collector = GitMetricsCollector(Path.cwd())

# Get velocity dashboard (last 30 days)
dashboard = collector.get_velocity_dashboard(days_back=30)

# Access metrics
print(f"Total commits: {dashboard.commit_metrics.total_commits}")
print(f"Commits per day: {dashboard.commit_metrics.avg_commits_per_day:.1f}")
print(f"Conventional compliance: {dashboard.commit_metrics.conventional_compliance_rate:.1%}")
print(f"Most active hour: {dashboard.commit_metrics.most_active_hour}:00")
print(f"Branch switches: {dashboard.branch_metrics.branch_switches}")
print(f"Merge conflict rate: {dashboard.merge_metrics.conflict_rate:.1%}")

# Trend data
for date, count in dashboard.trend_data[-7:]:
    print(f"{date.date()}: {count} commits")

collector.close()
```

### 2. Record Fix Attempts

```python
from pathlib import Path
from crackerjack.agents.base import Issue, FixResult, IssueType, Priority
from crackerjack.memory import FixStrategyStorage
from crackerjack.memory.issue_embedder import get_issue_embedder
import numpy as np

# Initialize storage
storage = FixStrategyStorage(Path(".crackerjack/fix_strategies.db"))

# Create issue
issue = Issue(
    type=IssueType.COMPLEXITY,
    severity=Priority.HIGH,
    message="Function has cognitive complexity 25",
    file_path="src/processor.py",
    line_number=42,
    stage="fast_hooks",
)

# Generate embedding (neural or TF-IDF fallback)
try:
    embedder = get_issue_embedder()
    embedding = embedder.embed_issue(issue)
except ImportError:
    # Use TF-IDF fallback
    from crackerjack.memory.fallback_embedder import FallbackIssueEmbedder
    embedder = FallbackIssueEmbedder()
    embedding = embedder.embed_issue(issue)

# Record fix attempt
result = FixResult(
    success=True,
    confidence=0.85,
    fixes_applied=["Extracted validate_input() method"],
    remaining_issues=[],
)

storage.record_attempt(
    issue=issue,
    result=result,
    agent_used="RefactoringAgent",
    strategy="extract_method",
    issue_embedding=embedding,
    session_id="dev-session-123",
)
```

### 3. Get Strategy Recommendations

```python
from crackerjack.memory import StrategyRecommender

# Initialize recommender
recommender = StrategyRecommender(storage)

# Get recommendation for current issue
recommendation = recommender.recommend_strategy(
    issue=issue,
    k=10,  # Consider top 10 similar issues
    min_confidence=0.4,  # Minimum confidence threshold
)

if recommendation:
    print(f"Recommended: {recommendation.agent_strategy}")
    print(f"Confidence: {recommendation.confidence:.1%}")
    print(f"Success rate: {recommendation.success_rate:.1%}")
    print(f"Based on {recommendation.sample_count} similar issues")
    print(f"Reasoning: {recommendation.reasoning}")

    # Alternatives
    print("\nAlternatives:")
    for alt_strategy, alt_confidence in recommendation.alternatives:
        print(f"  {alt_strategy}: {alt_confidence:.1%}")
else:
    print("Not enough data for recommendation")
```

### 4. Query Similar Historical Issues

```python
# Find similar issues
similar_issues = storage.find_similar_issues(
    issue_embedding=embedding,
    issue_type=issue.type.value,
    k=5,
    min_similarity=0.3,  # Cosine similarity threshold
)

for attempt in similar_issues:
    print(f"Issue: {attempt.issue_message}")
    print(f"  Agent: {attempt.agent_used}")
    print(f"  Strategy: {attempt.strategy}")
    print(f"  Success: {attempt.success}")
    print(f"  Confidence: {attempt.confidence:.2f}")
    print()
```

### 5. Track Skills with Session-Buddy

```python
from crackerjack.integration.skills_tracking import SessionBuddyDirectTracker

# Initialize tracker
tracker = SessionBuddyDirectTracker(session_id="my-session")

# Track skill invocation
completer = tracker.track_invocation(
    skill_name="RefactoringAgent",
    user_query="Fix complexity issues",
    workflow_phase="fast_hooks",
    project_path="/path/to/project",
    language="python",
    complexity_score=25,
    selection_rank=1,
    alternatives_considered=["SecurityAgent", "PerformanceAgent"],
)

# Mark as completed
completer(
    success=True,
    execution_time_seconds=42.5,
    output_summary="Reduced complexity from 25 to 15",
)

# Get recommendations
recommendations = tracker.get_recommendations(
    user_query="How do I fix complexity?",
    limit=5,
    workflow_phase="fast_hooks",
)

for rec in recommendations:
    print(f"{rec['skill_name']}: {rec['similarity_score']:.2f}")
```

## Data Models

### Git Metrics

```python
@dataclass
class CommitMetrics:
    total_commits: int
    conventional_commits: int
    conventional_compliance_rate: float
    breaking_changes: int
    avg_commits_per_hour: float
    avg_commits_per_day: float
    avg_commits_per_week: float
    most_active_hour: int  # 0-23
    most_active_day: int  # 0=Monday, 6=Sunday
    time_period: timedelta

@dataclass
class BranchMetrics:
    total_branches: int
    active_branches: int
    branch_switches: int
    branches_created: int
    branches_deleted: int
    avg_branch_lifetime_hours: float
    most_switched_branch: str | None

@dataclass
class MergeMetrics:
    total_merges: int
    total_rebases: int
    total_conflicts: int
    conflict_rate: float
    avg_files_per_conflict: float
    most_conflicted_files: list[tuple[str, int]]
    merge_success_rate: float
```

### Strategy Recommendation

```python
@dataclass
class StrategyRecommendation:
    agent_strategy: str  # "AgentName:StrategyName"
    confidence: float  # 0.0 to 1.0
    similarity_score: float  # Cosine similarity
    success_rate: float  # Historical success
    sample_count: int  # Number of similar issues
    alternatives: list[tuple[str, float]]  # [(strategy, confidence), ...]
    reasoning: str  # Human-readable explanation
```

## Configuration

### Git Metrics Storage

```python
# Database location (default: .git/git_metrics.db)
collector = GitMetricsCollector(
    repo_path=Path.cwd(),
    storage_path=Path(".custom/metrics.db"),
)
```

### Fix Strategy Storage

```python
# Database location (custom path)
storage = FixStrategyStorage(Path(".crackerjack/strategies.db"))
```

### Issue Embedder

```python
# Model selection (default: all-MiniLM-L6-v2)
from crackerjack.memory.issue_embedder import get_issue_embedder

embedder = get_issue_embedder(model_name="all-MiniLM-L6-v2")
embedding = embedder.embed_issue(issue)

# Batch processing
embeddings = embedder.embed_batch([issue1, issue2, issue3])
```

## Performance Tips

1. **Use Singleton Embedder**: Model loading is expensive (~2s first time)

   ```python
   embedder = get_issue_embedder()  # Cached globally
   ```

1. **Batch Embeddings**: Process multiple issues at once

   ```python
   embeddings = embedder.embed_batch(issues)  # Faster than loop
   ```

1. **Close Connections**: Always close storage connections

   ```python
   collector.close()
   storage.close()
   ```

1. **Adjust Similarity Threshold**: Lower for more results, higher for precision

   ```python
   similar = storage.find_similar_issues(
       embedding,
       min_similarity=0.2,  # Lower = more results
   )
   ```

## Troubleshooting

### Issue: "No similar issues found"

**Cause**: Not enough historical data or similarity threshold too high

**Solution**:

```python
# Lower threshold
similar = storage.find_similar_issues(
    embedding,
    min_similarity=0.2,  # Was 0.3
)

# Check database size
stats = storage.get_statistics()
print(f"Total attempts: {stats['total_attempts']}")
```

### Issue: "sentence-transformers not available"

**Cause**: Python 3.13 + Intel Mac (no torch wheels)

**Solution**: Use TF-IDF fallback

```python
from crackerjack.memory.fallback_embedder import FallbackIssueEmbedder

embedder = FallbackIssueEmbedder()
embedding = embedder.embed_issue(issue)
```

### Issue: "Git command failed"

**Cause**: Not in a git repository or git not installed

**Solution**:

```python
from pathlib import Path

# Verify git repository
repo_path = Path.cwd()
if not (repo_path / ".git").exists():
    raise ValueError("Not a git repository")

# Initialize collector
collector = GitMetricsCollector(repo_path)
```

## Best Practices

1. **Always Record Attempts**: Track both successes and failures

   ```python
   storage.record_attempt(issue, result, agent, strategy, embedding)
   ```

1. **Use Conventional Commits**: Improves metrics accuracy

   ```bash
   git commit -m "feat: add user authentication"
   git commit -m "fix: resolve login timeout"
   ```

1. **Review Recommendations**: Don't blindly follow suggestions

   ```python
   if recommendation and recommendation.confidence > 0.7:
       # High confidence - likely good choice
       pass
   elif recommendation and recommendation.confidence > 0.4:
       # Medium confidence - consider alternatives
       pass
   else:
       # Low confidence - use own judgment
       pass
   ```

1. **Monitor Metrics**: Regularly check velocity and trends

   ```python
   dashboard = collector.get_velocity_dashboard(days_back=7)
   # Alert if velocity drops
   if dashboard.commit_metrics.avg_commits_per_day < 5:
       print("WARNING: Low commit velocity")
   ```

## Next Steps

1. **Explore Integration**: See `docs/symbiotic-ecosystem.md` for full architecture
1. **Configure Ecosystem**: Set up Akosha, Session-Buddy, Mahavishnu integration
1. **Build Dashboards**: Create Grafana dashboards for metrics visualization
1. **Customize Algorithms**: Adjust recommendation thresholds for your workflow

## Support

- **Issues**: Report bugs to crackerjack repository
- **Documentation**: See `docs/` directory for detailed guides
- **Architecture**: See `ARCHITECTURE.md` for system design

______________________________________________________________________

**Last Updated**: 2026-02-11
**Version**: 1.0.0
