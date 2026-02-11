# Git Embedding Implementation Plan

## Overview
Extend issue_embedder.py to support git analytics data types (GitCommitData, GitBranchEvent, WorkflowEvent), extend AkoshaMCP client with git-specific search methods, and update vector store schema for git embeddings.

## Current State Analysis

### Existing Components

1. **issue_embedder.py** (`crackerjack/memory/issue_embedder.py`)
   - Currently supports `Issue` type from `crackerjack.agents.base`
   - Uses sentence-transformers for neural embeddings (384 dimensions)
   - Has fallback TF-IDF embedder
   - Provides batch embedding and similarity computation

2. **akosha_integration.py** (`crackerjack/integration/akosha_integration.py`)
   - Has `GitEvent` dataclass (commit_hash, timestamp, author_name, message, event_type, semantic_tags)
   - Has `GitVelocityMetrics` dataclass
   - Implements `AkoshaClientProtocol` with NoOp, Direct, and MCP variants
   - Has `AkoshaGitIntegration` for indexing git history

3. **mahavishnu_integration.py** (`crackerjack/integration/mahavishnu_integration.py`)
   - Has `RepositoryVelocity`, `RepositoryHealth`, `CrossProjectPattern` dataclasses
   - Implements portfolio-level git analytics aggregation

## Missing Components (To Be Created)

### 1. Git Analytics Data Types

Need to define in `crackerjack/models/git_analytics.py`:

```python
@dataclass(frozen=True)
class GitCommitData:
    commit_hash: str
    timestamp: datetime
    author_name: str
    author_email: str
    message: str
    files_changed: list[str]
    insertions: int
    deletions: int
    is_conventional: bool
    conventional_type: str | None
    conventional_scope: str | None
    has_breaking_change: bool
    is_merge: bool
    branch: str

@dataclass(frozen=True)
class GitBranchEvent:
    event_type: Literal["created", "deleted", "merged", "rebased"]
    branch_name: str
    timestamp: datetime
    author_name: str
    commit_hash: str
    source_branch: str | None  # For merges
    metadata: dict[str, Any]

@dataclass(frozen=True)
class WorkflowEvent:
    event_type: Literal["ci_started", "ci_success", "ci_failure", "deploy_started", "deploy_success", "deploy_failure"]
    workflow_name: str
    timestamp: datetime
    status: Literal["pending", "running", "success", "failure", "cancelled"]
    commit_hash: str
    branch: str
    duration_seconds: int | None
    metadata: dict[str, Any]
```

### 2. Extended IssueEmbedder

Modify `crackerjack/memory/issue_embedder.py`:

- Create generic `EmbeddableData` protocol
- Add `embed_git_commit()`, `embed_git_branch_event()`, `embed_workflow_event()` methods
- Create `_build_git_commit_text()`, `_build_git_branch_event_text()`, `_build_workflow_event_text()` helpers
- Add batch embedding support for git types
- Extend `IssueEmbedderProtocol` to include git methods

### 3. Extended AkoshaMCP Client

Modify `crackerjack/integration/akosha_integration.py`:

- Add `search_git_commits()` method to `AkoshaClientProtocol`
- Add `search_git_branches()` method to `AkoshaClientProtocol`
- Add `search_workflow_events()` method to `AkoshaClientProtocol`
- Implement git-specific filtering (by author, date range, file, branch)
- Add `index_git_commit()`, `index_git_branch_event()`, `index_workflow_event()` helpers

### 4. Vector Store Schema Updates

Define metadata schema for git embeddings:

```python
# Git commit metadata schema
{
    "type": "git_commit",
    "repository": str,
    "commit_hash": str,
    "author_name": str,
    "author_email": str,
    "timestamp": str (ISO 8601),
    "branch": str,
    "is_conventional": bool,
    "conventional_type": str | None,
    "has_breaking_change": bool,
    "files_changed": list[str],
    "tags": list[str],  # e.g., ["type:feat", "scope:api", "breaking"]
}

# Git branch event metadata schema
{
    "type": "git_branch_event",
    "repository": str,
    "event_type": str,  # created, deleted, merged, rebased
    "branch_name": str,
    "timestamp": str (ISO 8601),
    "author_name": str,
    "commit_hash": str,
}

# Workflow event metadata schema
{
    "type": "workflow_event",
    "repository": str,
    "event_type": str,  # ci_started, ci_success, etc.
    "workflow_name": str,
    "timestamp": str (ISO 8601),
    "status": str,
    "commit_hash": str,
    "branch": str,
}
```

## Implementation Order

### Phase 1: Data Models (Priority 1)
1. Create `crackerjack/models/git_analytics.py`
2. Define `GitCommitData`, `GitBranchEvent`, `WorkflowEvent` dataclasses
3. Add `to_searchable_text()` methods to each class
4. Add unit tests for data models

### Phase 2: IssueEmbedder Extension (Priority 1)
1. Create `EmbeddableData` protocol
2. Add git embedding methods to `IssueEmbedder`
3. Add batch embedding support for git types
4. Update `IssueEmbedderProtocol`
5. Add unit tests for git embeddings

### Phase 3: AkoshaMCP Client Extension (Priority 2)
1. Add git search methods to `AkoshaClientProtocol`
2. Implement methods in `DirectAkoshaClient`, `MCPAkoshaClient`, `NoOpAkoshaClient`
3. Add git-specific indexing helpers
4. Add unit tests for git search

### Phase 4: Integration & Testing (Priority 3)
1. Create integration tests for full workflow
2. Create demo script showing git search capabilities
3. Update documentation
4. Verify vector store schema compatibility

## Dependencies

- No new dependencies required (uses existing sentence-transformers)
- Requires `numpy`, `sentence-transformers` (already in dependencies)
- Requires `akosha` package for DirectAkoshaClient (optional)

## Testing Strategy

1. **Unit Tests**: Test each data model and embedding method independently
2. **Integration Tests**: Test end-to-end git indexing and search
3. **Performance Tests**: Verify batch embedding performance
4. **Schema Validation**: Ensure metadata schemas are consistent

## Success Criteria

1. All git data types can be embedded
2. Git-specific search methods work correctly
3. Vector store schema is properly extended
4. Backward compatibility maintained (existing Issue embeddings still work)
5. Test coverage > 80% for new code
