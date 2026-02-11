# Git Semantic Search - Usage Examples

## MCP Tool Examples

### Example 1: Search for Security-Related Commits

```python
# Via MCP client
result = await mcp_client.call_tool(
    "search_git_history",
    {
        "query": "security fixes and vulnerability patches",
        "limit": 15,
        "days_back": 90,
    }
)

# Result includes commits related to security even if they don't
# contain the exact words "security" or "vulnerability"
```

**Why use semantic search?**
- Finds commits about "auth bugs" when searching for "security issues"
- Discovers "XSS prevention" commits when searching for "injection fixes"
- Retrieves "hardening" changes when searching for "security improvements"

### Example 2: Find Hotfix Patterns

```python
result = await mcp_client.call_tool(
    "find_workflow_patterns",
    {
        "pattern_description": "urgent hotfix commits after releases",
        "days_back": 180,
        "min_frequency": 5,
    }
)

# Detects patterns like:
# - Multiple "fix: critical bug" commits within 48 hours of release
# - Recurring fixes in the same module after releases
# - Bypassed PR process for urgent fixes
```

**Use cases**:
- Identify unstable features needing more testing
- Discover release process issues
- Find modules requiring better review

### Example 3: Get Merge Conflict Recommendations

```python
result = await mcp_client.call_tool(
    "recommend_git_practices",
    {
        "focus_area": "merge_conflicts",
        "days_back": 60,
    }
)

# Returns prioritized recommendations:
# Priority 5: "Reduce Merge Conflicts"
#   - Evidence: 25% conflict rate
#   - Steps: ["Implement trunk-based development", ...]
#   - Impact: "Faster integration, reduced risk"
```

**Focus areas available**:
- `general`: Overall repository health
- `branching`: Branch strategy optimization
- `commit_quality`: Conventional commit adoption
- `merge_conflicts`: Conflict reduction strategies
- `velocity`: Development velocity improvement
- `breaking_changes`: Breaking change mitigation

## Direct Python API Examples

### Example 1: Natural Language Search

```python
from crackerjack.integration import create_git_semantic_search

searcher = create_git_semantic_search(
    repo_path="/path/to/your/repo",
    config=GitSemanticSearchConfig(
        similarity_threshold=0.7,  # Higher threshold = more strict
        max_results=20,
    )
)

# Search for performance-related commits
results = await searcher.search_git_history(
    query="performance optimizations and speed improvements",
    limit=10,
    days_back=60,
)

# Process results
for result in results["results"]:
    print(f"Commit: {result['commit_hash'][:8]}")
    print(f"Message: {result['message']}")
    print(f"Author: {result['author']}")
    print(f"Tags: {', '.join(result['semantic_tags'])}")
    print("-" * 40)

searcher.close()
```

### Example 2: Detect Recurring Bug Patterns

```python
# Find patterns of recurring bug fixes
patterns = await searcher.find_workflow_patterns(
    pattern_description="bugs that were fixed multiple times",
    days_back=120,
    min_frequency=3,
)

for pattern in patterns["patterns"]:
    print(f"Pattern: {pattern['pattern_name']}")
    print(f"Frequency: {pattern['frequency']} occurrences")
    print(f"Confidence: {pattern['confidence']:.1%}")
    print(f"Description: {pattern['description']}")

    # Show example commits
    for example in pattern['examples'][:3]:
        print(f"  - {example['commit_hash'][:8]}: {example['message']}")
    print()
```

### Example 3: Practice Recommendations

```python
# Get comprehensive practice recommendations
recommendations = await searcher.recommend_git_practices(
    focus_area="general",
    days_back=90,
)

print(f"Found {recommendations['recommendations_count']} recommendations\n")

for rec in recommendations['recommendations']:
    print(f"Priority {rec['priority']}/5: {rec['title']}")
    print(f"Type: {rec['type']}")
    print(f"Impact: {rec['potential_impact']}")

    if rec.get('metric_baseline'):
        print(f"Baseline: {rec['metric_baseline']}")

    print("Actionable Steps:")
    for i, step in enumerate(rec['actionable_steps'], 1):
        print(f"  {i}. {step}")
    print("-" * 60)
```

### Example 4: Custom Configuration

```python
from crackerjack.integration import GitSemanticSearchConfig, create_git_semantic_search

# Configure for high-precision search
config = GitSemanticSearchConfig(
    embedding_model="sentence-transformers/all-MiniLM-L6-v2",
    similarity_threshold=0.8,  # Very strict matching
    max_results=50,
    auto_index=True,
    index_interval_hours=12,  # Re-index twice daily
)

searcher = create_git_semantic_search(
    repo_path="/path/to/repo",
    config=config,
)

# Use searcher...
```

## Real-World Scenarios

### Scenario 1: Onboarding New Developer

**Problem**: New developer needs to understand recent authentication changes.

**Solution**:
```python
results = await searcher.search_git_history(
    query="authentication system changes and improvements",
    limit=20,
    days_back=90,
)

# Results show all auth-related commits including:
# - "feat: add OAuth2 support"
# - "refactor: improve password hashing"
# - "fix: resolve session timeout issue"
```

### Scenario 2: Identifying Technical Debt

**Problem**: Need to find code that gets frequently fixed.

**Solution**:
```python
patterns = await searcher.find_workflow_patterns(
    pattern_description="recurring fixes in the same module",
    days_back=180,
    min_frequency=4,
)

# Reveals patterns like:
# - "Parser Pattern" (7 occurrences)
#   Description: Frequent fixes to parser logic
#   Indicates: Technical debt, needs refactoring
```

### Scenario 3: Improving Team Workflow

**Problem**: High merge conflict rate slowing development.

**Solution**:
```python
recommendations = await searcher.recommend_git_practices(
    focus_area="merge_conflicts",
    days_back=60,
)

# Provides actionable recommendations:
# Priority 5: Reduce Merge Conflicts
#   Current: 25% conflict rate
#   Target: <10% conflict rate
#   Steps:
#     1. Implement trunk-based development
#     2. Require PR reviews before merge
#     3. Use feature flags instead of long branches
```

### Scenario 4: Release Preparation

**Problem**: Need to find all breaking changes for release notes.

**Solution**:
```python
results = await searcher.search_git_history(
    query="breaking changes and API modifications",
    limit=50,
    days_back=30,
)

# Semantic search finds:
# - Direct "BREAKING CHANGE:" commits
# - Major refactor PRs
# - API signature changes
# - Database migration commits
```

## Advanced Usage

### Combining Search and Pattern Detection

```python
# Step 1: Find problematic area
results = await searcher.search_git_history(
    query="memory leaks and resource issues",
    limit=20,
    days_back=60,
)

# Step 2: Analyze patterns in those results
if results["results_count"] > 3:
    patterns = await searcher.find_workflow_patterns(
        pattern_description="memory leak fixes",
        days_back=60,
        min_frequency=3,
    )

    # Step 3: Get recommendations
    recommendations = await searcher.recommend_git_practices(
        focus_area="general",
        days_back=60,
    )

    # Combine insights for comprehensive analysis
```

### Monitoring Repository Health Over Time

```python
import asyncio
from datetime import datetime, timedelta

async def weekly_health_check(repo_path: str):
    searcher = create_git_semantic_search(repo_path)

    recommendations = await searcher.recommend_git_practices(
        focus_area="general",
        days_back=7,  # Last week
    )

    priority_sum = sum(r['priority'] for r in recommendations['recommendations'])
    issue_count = len(recommendations['recommendations'])

    print(f"Weekly Health Score:")
    print(f"  Issues Found: {issue_count}")
    print(f"  Priority Score: {priority_sum}")
    print(f"  Status: {'NEEDS ATTENTION' if priority_sum > 10 else 'HEALTHY'}")

    searcher.close()

# Run weekly
asyncio.run(weekly_health_check("/path/to/repo"))
```

## Tips for Best Results

### Effective Query Writing

1. **Be specific but natural**:
   - ✓ "memory leaks in parser"
   - ✗ "parser" (too broad)

2. **Use domain language**:
   - ✓ "authentication security issues"
   - ✗ "auth problems" (semantic search finds same)

3. **Include context**:
   - ✓ "UI performance optimizations for mobile"
   - ✗ "performance" (too generic)

### Pattern Detection

1. **Use longer time windows**:
   - 90-180 days for pattern detection
   - Shorter windows may miss patterns

2. **Adjust min_frequency**:
   - Higher (5-10) for major patterns
   - Lower (2-3) for subtle patterns

3. **Review example commits**:
   - Patterns include top examples
   - Helps validate pattern relevance

### Recommendation Focus

1. **Start with `general`**:
   - Gets overall repository health
   - Then drill into specific areas

2. **Check priority scores**:
   - 5: Critical, address immediately
   - 3-4: Important, plan soon
   - 1-2: Nice to have

3. **Review actionable steps**:
   - Recommendations include concrete steps
   - Prioritize based on team capacity

## Integration with CI/CD

### Example: Pre-Release Health Check

```bash
#!/bin/bash
# pre_release_check.sh

# Check repository health before release
python - <<'PYTHON'
import asyncio
from crackerjack.integration import create_git_semantic_search

async def check():
    searcher = create_git_semantic_search(".")

    # Check for recent breaking changes
    results = await searcher.search_git_history(
        query="breaking changes",
        limit=50,
        days_back=30,
    )

    breaking_count = results["results_count"]
    if breaking_count > 5:
        print(f"WARNING: {breaking_count} breaking changes detected")
        print("Consider updating major version")

    searcher.close()

asyncio.run(check())
PYTHON
```

## Troubleshooting

### No Results Found

**Issue**: Search returns no results

**Solutions**:
1. Lower `similarity_threshold` (try 0.5)
2. Increase `days_back` window
3. Use more general query terms
4. Check repository has commits in time window

### Patterns Not Detected

**Issue**: No patterns found

**Solutions**:
1. Lower `min_frequency` (try 2-3)
2. Increase `days_back` (try 180 days)
3. Use more specific pattern description
4. Check repository has sufficient commit history

### Recommendations Too Generic

**Issue**: Recommendations don't seem relevant

**Solutions**:
1. Use specific `focus_area` instead of `general`
2. Ensure sufficient history (`days_back` >= 60)
3. Check repository matches best practices
4. Review metric baselines for context
