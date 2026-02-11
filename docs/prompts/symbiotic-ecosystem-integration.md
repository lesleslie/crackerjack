# Symbiotic Ecosystem Integration Implementation Prompt

**Context:**
You are implementing the symbiotic ecosystem integration plan from `~/.claude/plans/spicy-nibbling-meteor.md`. This plan adds AI-powered workflow optimization across the entire development ecosystem.

**Your Tasks:**

## Phase 1: Foundation (Week 1-2)

### Task 1: Git Metrics Collector
- Create `crackerjack/memory/git_metrics_collector.py`
- Parse `git log` output for:
  - Commits with hash, author, timestamp, message
  - Branch creation/deletion events
  - Merge operations
- Calculate metrics:
  - Commit velocity (commits/hour/day)
  - Branch switch frequency
  - Merge conflict rate
- Store metrics in SQLite time-series database
- Use ACID for performance (transactional writes)
- Schema: `git_metrics` table with indexes on (repository_path, timestamp) and (metric_type)

### Task 2: Fix Strategy Memory
- Create `crackerjack/memory/fix_strategy_storage.py`
- SQLite database with ACID for concurrency
- Record every fix attempt:
  - Issue type, message, file path, line number, stage
  - Agent used (RefactoringAgent, SecurityAgent, etc.)
  - Strategy selected
  - Success/failure
  - Issue embedding (384-dim vector)
  - Timestamp, session ID
- Create `get_velocity(repository, days_back=30)` → returns average commits/day
- Create `get_repository_health(repository)` → returns PR count, stale branches
- Implement confidence calculation from similarity scores

### Task 3: Issue Embedder
- Create `crackerjack/memory/issue_embedder.py`
- Use sentence-transformers (all-MiniLM-L6-v2 model)
- Convert issues to 384-dim embeddings
- Features:
  - Issue type (encoded)
  - Issue message (semantic text)
  - File path (semantic)
  - Stage (semantic)
- Store embeddings in NumPy format for fast cosine similarity

### Task 4: Strategy Recommender
- Create `crackerjack/memory/strategy_recommender.py`
- Load similar historical issues from FixStrategyStorage
- Calculate cosine similarity between current issue and history
- Filter by minimum similarity threshold (0.3)
- Weight voting by:
  - Historical success rate (boost score)
  - Click-through rate for recommendations
- Return (agent_strategy, confidence) tuple
- Update strategy effectiveness summary after each fix

## Phase 2: Integration (Week 2)

### Task 5: Akosha Integration
- **Goal**: Enable semantic search over git history
- In `akosha/`:
  - Add git history embedder index
  - Add natural language query interface
  - Implement semantic search with embeddings
  - Add query optimization learning (click-through, ranking)
  - Extend `SessionMetrics` with git velocity data
- Crackerjack uses Akosha's semantic search for strategy recommendations

### Task 6: Session-Buddy Integration
- **Goal**: Track workflow metrics correlated with git patterns
- In `session_buddy/`:
  - Extend `SessionMetrics` dataclass with:
    - `git_velocity`: dict (project → commits/day)
    - `branch_switch_frequency`: dict (project → switches/day)
    - `merge_conflict_rate`: dict (project → conflicts/day)
  - Add Mahavishnu aggregation API client
  - Store metrics in DuckDB (permanent storage)
  - Create dashboard views for velocity trends

### Task 7: Mahavishnu Integration
- **Goal**: Cross-project aggregation and intelligence
- In `mahavishnu/`:
  - Add `mcp/tools/git_analytics.py`:
    - `get_git_velocity_dashboard(project_paths)` → per-project velocity
    - `get_repository_health(repo_path)` → stale PRs, branches
    - `get_cross_project_patterns(days_back=90)` → patterns across repos
  - Create aggregation queries combining:
    - Git metrics (from Dhruva time-series)
    - Workflow performance (from Session-Buddy)
    - Quality scores (from Session-Buddy)
  - Update WebSocket broadcasters to use aggregated metrics
  - Create Grafana dashboard JSON (`docs/grafana/Symbiotic-Ecosystem.json`)

### Phase 3: Learning & Optimization (Week 3-4)

### Task 8: Skill Strategy Effectiveness Tracking
- In `crackerjack/integration/skills_tracking.py`:
  - Add to `SessionMetrics` dataclass:
    - `skill_success_rate`: dict (skill → success %)
    - `last_attempted`: timestamp
    - `most_effective_skills`: list
  - Track skill invocation effectiveness
  - Update with context from current issue (project, language, complexity)

### Task 9: Continuous Learning
- In `crackerjack/memory/`:
  - Record fix outcomes in FixStrategyMemory
  - Strengthen successful patterns (increase weight in similarity search)
  - Weaken failed patterns (decrease weight)
  - Retrain/recommend models based on latest data

### Dependencies

**Required Python Packages:**
- `sentence-transformers` (>=2.2.0)
- `llama-index` (for embeddings, optional)
- `numpy` (vector operations)
- `sqlite3` (time-series databases)
- `duckdb` (Session-Buddy storage)
- `pydantic` (data validation)

**MCP Tools to Add:**
- `git_metrics_collector` - Parse and store git activity
- `semantic_search` - Query git history with embeddings
- `strategy_recommender` - Recommend fix strategies
- `skill_tracker` - Monitor AI effectiveness
- `cross_project_analytics` - Aggregate across repositories

### Testing

Create comprehensive test suite in `tests/integration/test_symbiotic_ecosystem.py`:
- Git metrics accuracy (compare with git log)
- Fix strategy CRUD operations
- Issue embedding quality (semantic similarity)
- Strategy recommendation relevance (historical success correlation)
- End-to-end: Crackerjack → Akosha semantic search → results → Mahavishnu aggregation
- Performance: <100ms for embedding generation, <500ms for similarity search

### Documentation

Create `docs/symbiotic-ecosystem.md` with:
- Architecture overview
- Data flow diagrams
- Configuration guide
- Deployment checklist
- Success metrics tracking dashboard

---

**Success Criteria:**
- All 30+ tasks implemented across 3 phases
- 8 new components created
- Integration with Akosha, Session-Buddy, Mahavishnu
- 100+ integration tests passing
- Comprehensive documentation
- Performance benchmarks met

**Execute using parallel agents** for speed, or sequential if you prefer!

---

**This is your complete implementation prompt. Read this file and execute!**