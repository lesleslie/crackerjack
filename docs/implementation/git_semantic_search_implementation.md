# Git Semantic Search MCP Tools Implementation Plan

## Overview

Add semantic search MCP tools for git workflows in `crackerjack/integration/`. This enables natural language queries over git data using vector embeddings and semantic search.

## Architecture

### Components

1. **Git Semantic Search Module** (`crackerjack/integration/git_semantic_search.py`)
   - Main integration module
   - Bridges GitMetricsCollector with AkoshaMCP for semantic indexing
   - Provides search, pattern detection, and practice recommendations

2. **MCP Tools** (`crackerjack/mcp/tools/git_semantic_tools.py`)
   - `search_git_history`: Natural language search over commits
   - `find_workflow_patterns`: Detect recurring workflow patterns
   - `recommend_git_practices`: AI-powered practice recommendations

3. **Integration with Existing Systems**
   - Uses `GitMetricsCollector` for raw git data
   - Uses `AkoshaGitIntegration` for vector storage and search
   - Follows MCP tool registration pattern

## Data Models

```python
@dataclass
class WorkflowPattern:
    pattern_id: str
    pattern_name: str
    description: str
    frequency: int
    confidence: float
    examples: list[GitEvent]
    semantic_tags: list[str]

@dataclass
class PracticeRecommendation:
    recommendation_type: str
    title: str
    description: str
    priority: int
    evidence: list[GitEvent]
    actionable_steps: list[str]
    potential_impact: str
```

## MCP Tool Specifications

### 1. search_git_history

**Purpose**: Search git history using natural language queries

**Parameters**:
- `query` (str): Natural language query (e.g., "fixes for authentication bugs")
- `limit` (int, default=10): Maximum results to return
- `days_back` (int, default=30): Search window in days
- `repository_path` (str, optional): Path to git repository

**Returns**: JSON with matching commits and similarity scores

**Example Usage**:
```json
{
  "query": "commits about fixing memory leaks",
  "limit": 10,
  "days_back": 60
}
```

### 2. find_workflow_patterns

**Purpose**: Detect recurring patterns in git workflow

**Parameters**:
- `pattern_description` (str): Natural language description of pattern to find
- `days_back` (int, default=90): Analysis window
- `min_frequency` (int, default=3): Minimum occurrences to qualify as pattern
- `repository_path` (str, optional): Path to git repository

**Returns**: JSON with detected patterns, frequency, and examples

**Example Usage**:
```json
{
  "pattern_description": "hotfix commits after releases",
  "days_back": 90,
  "min_frequency": 5
}
```

### 3. recommend_git_practices

**Purpose**: AI-powered recommendations based on repository patterns

**Parameters**:
- `focus_area` (str): Area to focus on (e.g., "branching", "commit quality", "conflict resolution")
- `days_back` (int, default=60): Analysis window
- `repository_path` (str, optional): Path to git repository

**Returns**: JSON with prioritized recommendations and action steps

**Example Usage**:
```json
{
  "focus_area": "merge conflicts",
  "days_back": 60
}
```

## Implementation Steps

1. **Create Data Models** (git_semantic_search.py)
   - WorkflowPattern dataclass
   - PracticeRecommendation dataclass
   - Semantic enrichment functions

2. **Implement Core Functions**
   - `search_git_history()`: Index and search commits
   - `find_workflow_patterns()`: Pattern detection using clustering
   - `recommend_git_practices()`: Rule-based + semantic analysis

3. **Create MCP Tools** (git_semantic_tools.py)
   - Register three tools following semantic_tools.py pattern
   - Input validation using `get_input_validator()`
   - Error handling and JSON responses

4. **Update MCP Server Registration**
   - Add `register_git_semantic_tools()` to tools/__init__.py
   - Call from server_core.py

5. **Testing**
   - Unit tests for pattern detection
   - Integration tests with AkoshaMCP
   - MCP tool invocation tests

## Semantic Indexing Strategy

### Commit Text Enrichment
```python
def enrich_commit_for_search(commit: CommitData) -> str:
    return f"""
    {commit.message}
    Type: {commit.conventional_type or 'unknown'}
    Scope: {commit.conventional_scope or 'none'}
    Breaking: {commit.has_breaking_change}
    Author: {commit.author_name}
    Time: {commit.author_timestamp.strftime('%Y-%m-%d %H:%M')}
    """
```

### Pattern Detection Algorithm
1. Cluster commits by semantic similarity
2. Identify clusters meeting frequency threshold
3. Extract common semantic themes
4. Generate pattern descriptions

### Practice Recommendation Logic
1. Analyze metrics (velocity, conflict rate, compliance)
2. Identify areas deviating from best practices
3. Search for similar solved problems in history
4. Generate contextual recommendations

## Integration Points

- **GitMetricsCollector**: Source of raw git data
- **AkoshaGitIntegration**: Vector storage and semantic search
- **InputValidator**: Security validation for all inputs
- **MCP Server**: Tool registration and invocation

## Configuration

Uses existing `CrackerjackSettings` with potential additions:
```yaml
semantic_git:
  enabled: true
  auto_index: true
  index_interval_hours: 24
  embedding_model: "sentence-transformers/all-MiniLM-L6-v2"
```

## Benefits

1. **Natural Language Discovery**: Find commits by intent, not just keywords
2. **Pattern Recognition**: Automatically detect recurring workflows
3. **Practice Improvement**: Data-driven recommendations
4. **Integration**: Works with existing crackerjack infrastructure
5. **Privacy**: All processing local, no external services

## Files to Create

1. `/Users/les/Projects/crackerjack/crackerjack/integration/git_semantic_search.py`
2. `/Users/les/Projects/crackerjack/crackerjack/mcp/tools/git_semantic_tools.py`

## Files to Modify

1. `/Users/les/Projects/crackerjack/crackerjack/integration/__init__.py` - Add exports
2. `/Users/les/Projects/crackerjack/crackerjack/mcp/tools/__init__.py` - Add registration
3. `/Users/les/Projects/crackerjack/crackerjack/mcp/server_core.py` - Register tools

## Testing Strategy

1. **Unit Tests**: Pattern detection logic
2. **Integration Tests**: AkoshaMCP integration
3. **MCP Tests**: Tool invocation via MCP client
4. **Manual Tests**: Natural language queries

## Dependencies

- Existing: `akosha`, `GitMetricsCollector`, `InputValidator`
- No new external dependencies required

## Security Considerations

- All inputs validated via `InputValidator`
- File paths sanitized before repository access
- No arbitrary code execution
- Repository access respects git permissions
