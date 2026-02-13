# Vector Database Integration for Skill Discovery & Usage Optimization

**Status**: Implementation Plan
**Author**: Data Scientist Agent
**Date**: 2025-02-10
**Related Systems**: Crackerjack skills metrics, Session-Buddy vector search, Akosha vector DB

______________________________________________________________________

## Executive Summary

**Problem**: Users struggle to discover the right skills for their needs, and current skill metrics only track usage counts without learning from effectiveness patterns.

**Solution**: Integrate semantic vector search with existing skill metrics to create an intelligent recommendation system that learns from:

1. Skill content (semantic similarity)
1. Usage patterns (what works when)
1. Session context (what skills succeeded in similar situations)

**Expected Impact**:

- 40-60% improvement in skill discovery accuracy
- 30-50% reduction in failed skill invocations
- 2-3x faster skill selection workflow

______________________________________________________________________

## 1. Current System Analysis

### 1.1 Existing Components

**Skills System** (`crackerjack/skills/`):

- `agent_skills.py`: 12 AI specialist agents with metadata
- `metrics.py`: Tracks invocations, completion rates, durations
- `mcp_skills.py`: MCP tool integration

**Vector Infrastructure**:

- `services/vector_store.py`: SQLite-based vector storage
- `services/ai/embeddings.py`: Multi-backend embedding generation (Ollama, ONNX, fallback)
- `models/semantic_models.py`: Pydantic models for embeddings

**Session-Buddy Integration**:

- `session_buddy/reflection/embeddings.py`: 384-dim embeddings using all-MiniLM-L6-v2
- `session_buddy/reflection/search.py`: Semantic search with cosine similarity
- DuckDB backend for vector operations

### 1.2 Skill File Format

Skills are markdown files with frontmatter:

```yaml
---
name: n8n-node-configuration
description: Operation-aware node configuration guidance...
---
# Skill Content

## Core Concepts
## Workflow
## Examples
...
```

**Key Sections to Index**:

1. Frontmatter metadata (name, description)
1. Core Concepts (semantic meaning)
1. Workflow patterns (when to use)
1. Examples (problem-solution pairs)

### 1.3 Current Metrics Schema

```python
@dataclass
class SkillInvocation:
    skill_name: str
    invoked_at: str
    workflow_path: str | None
    completed: bool
    duration_seconds: float | None
    follow_up_actions: list[str]
    error_type: str | None


@dataclass
class SkillMetrics:
    skill_name: str
    total_invocations: int
    completed_invocations: int
    completion_rate: float
    avg_duration_seconds: float
    workflow_paths: dict[str, int]
    common_errors: dict[str, int]
    follow_up_actions: dict[str, int]
```

**Limitation**: No correlation between context and effectiveness.

______________________________________________________________________

## 2. Implementation Architecture

### 2.1 System Overview

```
User Query/Context
        ↓
┌───────────────────────────────────────┐
│  Skill Recommendation Engine          │
│  - Query → Embedding                  │
│  - Multi-factor scoring               │
│  - Context-aware ranking              │
└───────────────────────────────────────┘
        ↓
        ├─────────────────────────────────────┐
        │                                     │
        ↓                                     ↓
┌──────────────────────┐         ┌──────────────────────┐
│ Vector Store         │         │ Metrics Store        │
│ (Akosha/SQLite)      │         │ (JSON metrics)       │
│                      │         │                      │
│ - Skill embeddings   │         │ - Completion rates   │
│ - Usage patterns     │         │ - Error patterns     │
│ - Session contexts   │         │ - Duration data      │
└──────────────────────┘         └──────────────────────┘
        ↓                                     ↓
        └─────────────────────────────────────┘
                        ↓
              ┌─────────────────┐
              │ Ranked Skills   │
              │ with confidence │
              └─────────────────┘
```

### 2.2 Data Flow

```
1. SKILL INDEXING (One-time + Incremental)
   Skill File → Parse → Chunk → Embed → Store in Vector DB

2. METRICS TRACKING (Ongoing)
   Skill Execution → Context + Result → Update Metrics

3. SESSION CONTEXT (Ongoing)
   Session Activity → Embed → Store in Session-Buddy

4. RECOMMENDATION (On-demand)
   User Query → Embed → Search Vector DB
   → Combine with Metrics → Re-rank → Return
```

______________________________________________________________________

## 3. Embedding Strategy for Skills

### 3.1 What to Index

**Hierarchical Chunking Strategy**:

```python
# Level 1: Metadata chunk (highest weight)
metadata_chunk = f"""
Skill: {name}
Description: {description}
Category: {category}
Tags: {tags}
Purpose: {one_line_summary}
"""

# Level 2: Core Concepts (medium weight)
concepts_chunk = """
## Core Concepts
{extracted_concepts}
"""

# Level 3: Workflow Patterns (contextual weight)
workflow_chunk = """
## When to Use This Skill
{workflow_triggers}
## Typical Workflow
{workflow_steps}
"""

# Level 4: Examples (problem-solution pairs)
example_chunks = """
### Problem: {user_problem}
### Solution: {skill_application}
### Result: {expected_outcome}
"""
```

**Chunking Parameters**:

- Chunk size: 500 characters (matches `SemanticConfig.chunk_size`)
- Overlap: 50 characters
- Maximum chunks per skill: 20 (prevents over-indexing)

### 3.2 Embedding Model Selection

**Recommended**: `all-MiniLM-L6-v2` (already in use)

**Why**:

- 384 dimensions (fast similarity computation)
- Good balance of semantic understanding and speed
- Already integrated via session-buddy
- Works well for technical documentation

**Alternative**: `nomic-embed-text` (via Ollama)

- Higher dimensionality (768)
- Better for code-heavy content
- Requires Ollama backend

### 3.3 Skill Update Handling

**Incremental Re-indexing**:

```python
def index_skill(skill_file: Path, vector_store: VectorStore) -> None:
    # 1. Compute file hash
    current_hash = embedding_service.get_file_hash(skill_file)

    # 2. Check if re-indexing needed
    if not vector_store._needs_reindexing(skill_file, current_hash):
        logger.debug(f"Skill {skill_file} unchanged, skipping")
        return

    # 3. Remove old embeddings
    vector_store.remove_file(skill_file)

    # 4. Parse and chunk
    chunks = parse_and_chunk_skill(skill_file)

    # 5. Generate embeddings
    embeddings = embedding_service.generate_embeddings_batch(chunks)

    # 6. Store with metadata
    for chunk, embedding in zip(chunks, embeddings):
        vector_store._store_embeddings(
            [
                EmbeddingVector(
                    file_path=skill_file,
                    chunk_id=generate_chunk_id(skill_file, chunk),
                    content=chunk,
                    embedding=embedding,
                    metadata={
                        "skill_name": skill_name,
                        "chunk_type": "metadata|concept|workflow|example",
                        "weight": get_chunk_weight(chunk_type),
                        "file_hash": current_hash,
                    },
                )
            ]
        )
```

______________________________________________________________________

## 4. Semantic Skill Search Implementation

### 4.1 Core Search Algorithm

**File**: `crackerjack/skills/skill_search.py`

```python
from crackerjack.models.semantic_models import SearchQuery, SearchResult
from crackerjack.services.vector_store import VectorStore
from crackerjack.skills.metrics import SkillMetricsTracker


class SkillSearchEngine:
    """Semantic skill search with metric-based re-ranking."""

    def __init__(
        self,
        vector_store: VectorStore,
        metrics_tracker: SkillMetricsTracker,
    ) -> None:
        self.vector_store = vector_store
        self.metrics_tracker = metrics_tracker

    async def find_skills(
        self,
        query: str,
        max_results: int = 5,
        min_similarity: float = 0.6,
    ) -> list[SkillRecommendation]:
        """Find skills by semantic similarity + effectiveness.

        Args:
            query: User's problem description
            max_results: Maximum skills to return
            min_similarity: Minimum semantic similarity (0-1)

        Returns:
            Ranked list of skills with confidence scores
        """
        # 1. Semantic search (vector similarity)
        search_query = SearchQuery(
            query=query,
            max_results=max_results * 2,  # Get more for re-ranking
            min_similarity=min_similarity,
            file_types=[".md"],
        )

        semantic_results = self.vector_store.search(search_query)

        # 2. Group by skill
        skill_scores = self._group_by_skill(semantic_results)

        # 3. Apply metrics-based re-ranking
        recommendations = self._rank_with_metrics(skill_scores)

        # 4. Return top N
        return recommendations[:max_results]

    def _group_by_skill(
        self,
        results: list[SearchResult],
    ) -> dict[str, float]:
        """Group chunks by skill and aggregate scores.

        Weighting:
        - Metadata chunks: 1.5x (most relevant)
        - Concept chunks: 1.2x (good match)
        - Workflow chunks: 1.0x (neutral)
        - Example chunks: 0.8x (specific cases)
        """
        skill_scores: dict[str, float] = {}

        for result in results:
            skill_name = extract_skill_name(result.file_path)
            chunk_type = result.metadata.get("chunk_type", "unknown")
            weight = CHUNK_WEIGHTS.get(chunk_type, 1.0)

            if skill_name not in skill_scores:
                skill_scores[skill_name] = 0.0

            skill_scores[skill_name] += result.similarity_score * weight

        # Normalize by number of chunks
        for skill_name in skill_scores:
            skill_scores[skill_name] /= max(1, count_chunks_for_skill(skill_name))

        return skill_scores

    def _rank_with_metrics(
        self,
        skill_scores: dict[str, float],
    ) -> list[SkillRecommendation]:
        """Re-rank skills based on effectiveness metrics.

        Scoring Formula:
        final_score = semantic_score * (1.0 + effectiveness_bonus)

        Effectiveness Bonus:
        - Completion rate > 90%: +0.2
        - Completion rate > 80%: +0.1
        - Completion rate < 50%: -0.2
        - High error rate: -0.1
        """
        recommendations = []

        for skill_name, semantic_score in skill_scores.items():
            metrics = self.metrics_tracker.get_skill_metrics(skill_name)

            if not metrics:
                # No metrics yet, use semantic score only
                effectiveness_bonus = 0.0
                confidence = "low"
            else:
                # Calculate effectiveness bonus
                completion_rate = metrics.completion_rate()

                if completion_rate >= 90:
                    effectiveness_bonus = 0.2
                    confidence = "high"
                elif completion_rate >= 80:
                    effectiveness_bonus = 0.1
                    confidence = "medium"
                elif completion_rate < 50:
                    effectiveness_bonus = -0.2
                    confidence = "low"
                else:
                    effectiveness_bonus = 0.0
                    confidence = "medium"

                # Penalize high error rates
                if metrics.common_errors:
                    error_rate = (
                        sum(metrics.common_errors.values()) / metrics.total_invocations
                    )
                    if error_rate > 0.2:
                        effectiveness_bonus -= 0.1
                        confidence = "low"

            final_score = semantic_score * (1.0 + effectiveness_bonus)

            recommendations.append(
                SkillRecommendation(
                    skill_name=skill_name,
                    confidence_score=final_score,
                    confidence_level=confidence,
                    semantic_score=semantic_score,
                    effectiveness_bonus=effectiveness_bonus,
                    reasoning=f"Semantic match ({semantic_score:.2f}) "
                    f"+ effectiveness bonus ({effectiveness_bonus:+.2f})",
                )
            )

        # Sort by final score
        recommendations.sort(key=lambda r: r.confidence_score, reverse=True)
        return recommendations


@dataclass
class SkillRecommendation:
    """Recommended skill with confidence breakdown."""

    skill_name: str
    confidence_score: float  # Final score (0-1+)
    confidence_level: str  # "high" | "medium" | "low"
    semantic_score: float  # Pure vector similarity
    effectiveness_bonus: float  # Metrics adjustment
    reasoning: str  # Human-readable explanation


CHUNK_WEIGHTS = {
    "metadata": 1.5,
    "concept": 1.2,
    "workflow": 1.0,
    "example": 0.8,
}
```

### 4.2 Usage Pattern Learning

**Enhanced Metrics Tracking**:

```python
@dataclass
class EnhancedSkillInvocation(SkillInvocation):
    """Extended invocation with context."""

    # Existing fields
    skill_name: str
    invoked_at: str
    workflow_path: str | None
    completed: bool
    duration_seconds: float | None
    follow_up_actions: list[str]
    error_type: str | None

    # New fields for learning
    user_query: str  # What problem user described
    context_embedding: list[float] | None  # Session context
    alternative_skills: list[str] | None  # Other skills considered
    selected_from_rank: int  # Position in recommendation list


class ContextualSkillTracker(SkillMetricsTracker):
    """Enhanced tracker with context awareness."""

    def track_invocation_with_context(
        self,
        skill_name: str,
        user_query: str,
        context_embedding: list[float] | None = None,
        alternatives: list[str] | None = None,
        rank: int = 1,
        workflow_path: str | None = None,
    ) -> Callable[[], None]:
        """Track skill with full context for learning."""

        invocation = EnhancedSkillInvocation(
            skill_name=skill_name,
            invoked_at=datetime.now().isoformat(),
            workflow_path=workflow_path,
            user_query=user_query,
            context_embedding=context_embedding,
            alternative_skills=alternatives,
            selected_from_rank=rank,
        )

        self._invocations.append(invocation)

        def completer(
            *,
            completed: bool = True,
            follow_up_actions: list[str] | None = None,
            error_type: str | None = None,
        ) -> None:
            invocation.completed = completed
            invocation.follow_up_actions = follow_up_actions or []
            invocation.error_type = error_type
            invocation.duration_seconds = (
                datetime.now() - datetime.fromisoformat(invocation.invoked_at)
            ).total_seconds()

            self._update_aggregates(invocation)
            self._learn_from_context(invocation)  # NEW!
            self._save()

        return completer

    def _learn_from_context(self, invocation: EnhancedSkillInvocation) -> None:
        """Extract patterns from successful/failed invocations.

        Learning rules:
        1. If skill selected from rank > 3 and succeeded:
           → Boost semantic similarity for this query type
        2. If skill failed but alternative succeeded:
           → Penalize this skill for this query type
        3. If specific workflow path always succeeds:
           → Recommend this path for similar queries
        """
        if not invocation.completed:
            return

        # Rule 1: Late rank success
        if invocation.selected_from_rank > 3 and invocation.completed:
            logger.info(
                f"Skill {invocation.skill_name} succeeded from rank "
                f"{invocation.selected_from_rank}, consider boosting for: "
                f"{invocation.user_query[:50]}..."
            )
            # Store positive pattern
            self._store_pattern(
                query=invocation.user_query,
                skill=invocation.skill_name,
                outcome="success",
                context_type="late_rank",
            )

        # Rule 2: Alternative analysis
        if invocation.alternative_skills:
            for alt_skill in invocation.alternative_skills:
                if not invocation.completed:
                    # This skill failed, check if alternative would succeed
                    alt_metrics = self.get_skill_metrics(alt_skill)
                    if alt_metrics and alt_metrics.completion_rate() > 80:
                        logger.info(
                            f"Skill {invocation.skill_name} failed, "
                            f"alternative {alt_skill} has high success rate"
                        )
                        self._store_pattern(
                            query=invocation.user_query,
                            skill=alt_skill,
                            outcome="preferred_alternative",
                        )

        # Rule 3: Workflow path learning
        if invocation.workflow_path:
            workflow_success_rate = self._get_workflow_success_rate(
                invocation.skill_name,
                invocation.workflow_path,
            )
            if workflow_success_rate > 0.9:
                logger.info(
                    f"Workflow path '{invocation.workflow_path}' has "
                    f"{workflow_success_rate:.0%} success rate for "
                    f"{invocation.skill_name}"
                )
                self._store_pattern(
                    query=invocation.user_query,
                    skill=invocation.skill_name,
                    outcome="optimal_workflow",
                    workflow_path=invocation.workflow_path,
                )

    def _store_pattern(
        self,
        query: str,
        skill: str,
        outcome: str,
        context_type: str = "",
        workflow_path: str | None = None,
    ) -> None:
        """Store learned pattern for future recommendations."""
        # Implementation: Store in separate patterns.json
        # This feeds into the recommendation engine
        pass
```

______________________________________________________________________

## 5. Integration with Session-Buddy

### 5.1 Session Context Embeddings

**Why**: Skills used in similar session contexts are likely to be relevant again.

**Implementation**:

```python
# In session-buddy/reflection/embeddings.py


async def embed_session_context(
    db: DuckDBPyConnection,
    session_id: str,
    recent_conversations: int = 10,
) -> list[float] | None:
    """Generate embedding for recent session context.

    Args:
        db: Database connection
        session_id: Session identifier
        recent_conversations: Number of recent messages to include

    Returns:
        Session context embedding (384-dim vector) or None
    """
    # 1. Fetch recent conversations
    sql = """
        SELECT content, embedding
        FROM conversations
        WHERE session_id = ?
        ORDER BY timestamp DESC
        LIMIT ?
    """
    results = db.execute(sql, [session_id, recent_conversations]).fetchall()

    if not results:
        return None

    # 2. Aggregate embeddings (mean pooling)
    embeddings = [
        json.loads(row[1])
        for row in results
        if row[1]  # Has pre-computed embedding
    ]

    if not embeddings:
        return None

    # 3. Mean pooling
    import numpy as np

    aggregated = np.mean(embeddings, axis=0)

    # 4. Normalize
    normalized = aggregated / np.linalg.norm(aggregated)

    return normalized.tolist()


# In crackerjack/skills/skill_search.py


class SkillSearchEngine:
    def __init__(
        self,
        vector_store: VectorStore,
        metrics_tracker: SkillMetricsTracker,
        session_db: DuckDBPyConnection | None = None,
    ) -> None:
        self.vector_store = vector_store
        self.metrics_tracker = metrics_tracker
        self.session_db = session_db

    async def find_skills_with_session_context(
        self,
        query: str,
        session_id: str | None = None,
        max_results: int = 5,
    ) -> list[SkillRecommendation]:
        """Find skills using both query and session context.

        Scoring:
        final_score = 0.7 * query_similarity + 0.3 * context_similarity
        """
        # 1. Standard semantic search
        recommendations = await self.find_skills(query, max_results)

        # 2. Add session context boost if available
        if session_id and self.session_db:
            context_embedding = await embed_session_context(
                self.session_db,
                session_id,
            )

            if context_embedding:
                recommendations = self._boost_by_session_context(
                    recommendations,
                    context_embedding,
                )

        return recommendations

    def _boost_by_session_context(
        self,
        recommendations: list[SkillRecommendation],
        context_embedding: list[float],
    ) -> list[SkillRecommendation]:
        """Boost skills that were used in similar contexts.

        For each recommended skill:
        1. Fetch past invocations with context embeddings
        2. Compute similarity to current context
        3. Boost if similar contexts led to success
        """
        for rec in recommendations:
            metrics = self.metrics_tracker.get_skill_metrics(rec.skill_name)
            if not metrics:
                continue

            # Get past invocations with context
            past_invocations = [
                inv
                for inv in self._get_invocations_with_context(rec.skill_name)
                if inv.context_embedding
            ]

            if not past_invocations:
                continue

            # Compute context similarities
            import numpy as np

            similarities = [
                np.dot(
                    context_embedding,
                    inv.context_embedding,
                )
                / (
                    np.linalg.norm(context_embedding)
                    * np.linalg.norm(inv.context_embedding)
                )
                for inv in past_invocations
                if inv.context_embedding
            ]

            # Average similarity for successful invocations only
            successful_sims = [
                sim for inv, sim in zip(past_invocations, similarities) if inv.completed
            ]

            if successful_sims:
                avg_context_similarity = np.mean(successful_sims)

                # Boost score if context matches successful past uses
                if avg_context_similarity > 0.8:
                    context_boost = 0.15
                    rec.reasoning += (
                        f" + context boost (used successfully in similar sessions)"
                    )
                    rec.confidence_score += context_boost

        # Re-sort after boosting
        recommendations.sort(key=lambda r: r.confidence_score, reverse=True)
        return recommendations
```

### 5.2 Skill Usage as Session Reflections

**Store skill usage in session-buddy**:

```python
# After skill execution
await store_reflection(
    db=session_db,
    content=f"Used skill '{skill_name}' for: {user_query}",
    tags=["skill_usage", skill_name, "success" if completed else "failed"],
    embedding=await generate_embedding(f"Skill: {skill_name}\nPurpose: {user_query}"),
    metadata={
        "skill_name": skill_name,
        "completed": completed,
        "duration_seconds": duration,
        "workflow_path": workflow_path,
    },
)
```

**Benefits**:

- Skills become searchable in session history
- Can correlate skill usage with project success
- Enables "what skills work for this project?" queries

______________________________________________________________________

## 6. Recommendation Algorithm

### 6.1 Multi-Factor Scoring

**Final Score Formula**:

```
confidence_score = (
    semantic_score * 0.6 +           # Vector similarity
    effectiveness_score * 0.3 +      # Metrics-based
    context_boost * 0.1              # Session context
) * penalty_factors
```

**Component Breakdown**:

```python
def calculate_recommendation_score(
    semantic_score: float,
    metrics: SkillMetrics | None,
    context_similarity: float | None,
    user_query: str,
) -> tuple[float, str]:
    """Calculate final recommendation score.

    Returns:
        (final_score, reasoning)
    """
    # 1. Semantic score (base)
    score = semantic_score * 0.6
    reasoning = [f"Semantic: {semantic_score:.2f}"]

    # 2. Effectiveness score (from metrics)
    if metrics:
        effectiveness = calculate_effectiveness(metrics)
        score += effectiveness * 0.3
        reasoning.append(f"Effectiveness: {effectiveness:.2f}")
    else:
        score += 0.5 * 0.3  # Neutral for new skills
        reasoning.append("Effectiveness: unknown (new skill)")

    # 3. Context boost (from session)
    if context_similarity and context_similarity > 0.8:
        context_boost = context_similarity * 0.1
        score += context_boost
        reasoning.append(f"Context: {context_boost:.2f} (similar session)")

    # 4. Apply penalties
    # Penalty: Low completion rate
    if metrics and metrics.completion_rate() < 50:
        penalty = 0.8
        reasoning.append(f"Penalty: low completion rate")
        score *= penalty

    # Penalty: High error rate for this query type
    if metrics and has_error_pattern_for_query(metrics, user_query):
        penalty = 0.7
        reasoning.append(f"Penalty: similar queries failed before")
        score *= penalty

    return score, " + ".join(reasoning)


def calculate_effectiveness(metrics: SkillMetrics) -> float:
    """Calculate effectiveness score from metrics (0-1).

    Factors:
    - Completion rate: 50% weight
    - Average duration (inverse): 20% weight
    - Error rate (inverse): 30% weight
    """
    completion_score = metrics.completion_rate() / 100

    # Duration score (faster is better, capped at 60s)
    avg_duration = metrics.avg_duration_seconds()
    duration_score = max(0.0, 1.0 - (avg_duration / 60))

    # Error score (lower is better)
    error_rate = (
        sum(metrics.common_errors.values()) / metrics.total_invocations
        if metrics.total_invocations > 0
        else 0
    )
    error_score = 1.0 - error_rate

    effectiveness = completion_score * 0.5 + duration_score * 0.2 + error_score * 0.3

    return max(0.0, min(1.0, effectiveness))
```

### 6.2 Handling Edge Cases

**New Skills (No Metrics)**:

- Use semantic score only
- Apply "new skill bonus" (+10%) to encourage exploration
- Mark as "experimental" in UI

**Stale Skills (Not Used Recently)**:

- Apply time decay to effectiveness score
- Recent invocations weighted 2x more than old
- Prevents obsolete skills from dominating

**Context Mismatch**:

- If session context suggests different skill category
- Apply cross-domain penalty (-20%)
- Example: DevOps skill suggested during frontend session

______________________________________________________________________

## 7. Implementation Roadmap

### Phase 1: Core Infrastructure (Week 1)

**Tasks**:

1. ✅ Review existing vector store and embedding services
1. ✅ Design skill parsing and chunking strategy
1. ✅ Implement `SkillSearchEngine` with semantic search
1. ⬜ Add enhanced metrics tracking with context

**Deliverables**:

- `crackerjack/skills/skill_search.py`
- `crackerjack/skills/skill_parser.py`
- Unit tests for parsing and search

**Success Criteria**:

- Can index a skill markdown file
- Can retrieve skills by semantic similarity
- Metrics integration functional

### Phase 2: Metrics Integration (Week 2)

**Tasks**:

1. ⬜ Implement `ContextualSkillTracker`
1. ⬜ Add pattern learning from invocations
1. ⬜ Create effectiveness score calculator
1. ⬜ Integrate with existing metrics system

**Deliverables**:

- `crackerjack/skills/contextual_tracker.py`
- `crackerjack/skills/effectiveness.py`
- Migration script for existing metrics

**Success Criteria**:

- Tracks skill invocations with context
- Learns from success/failure patterns
- Effectiveness scores improve ranking

### Phase 3: Session-Buddy Integration (Week 3)

**Tasks**:

1. ⬜ Implement session context embedding
1. ⬜ Add skill usage to reflections
1. ⬜ Create cross-system search
1. ⬜ Handle session-buddy as optional dependency

**Deliverables**:

- `session_buddy/reflection/skills.py`
- `crackerjack/skills/session_integration.py`
- MCP tool for skill recommendations

**Success Criteria**:

- Session context improves recommendations
- Skills searchable in session history
- Works without session-buddy installed

### Phase 4: Production Readiness (Week 4)

**Tasks**:

1. ⬜ Performance optimization (caching, batching)
1. ⬜ Error handling and fallbacks
1. ⬜ CLI commands for skill management
1. ⬜ Documentation and examples

**Deliverables**:

- `crackerjack/skills/__init__.py` (public API)
- CLI commands: `python -m crackerjack skills index|search|stats`
- Documentation: `docs/VECTOR_SKILLS_GUIDE.md`

**Success Criteria**:

- \<100ms search latency
- Graceful fallbacks for missing components
- 100% test coverage for new code

______________________________________________________________________

## 8. Testing Strategy

### 8.1 Unit Tests

```python
# tests/skills/test_skill_search.py


def test_skill_parsing():
    """Test skill markdown parsing."""
    skill = parse_skill_file("test_skill.md")
    assert skill.name == "test-skill"
    assert len(skill.chunks) > 0


def test_semantic_search():
    """Test semantic skill retrieval."""
    engine = SkillSearchEngine(mock_vector_store, mock_tracker)

    results = await engine.find_skills(
        query="I need to fix type errors in Python",
        max_results=3,
    )

    assert len(results) <= 3
    assert results[0].confidence_score > 0.5
    assert results[0].skill_name in ["python-type-fixing", "crackerjack-run"]


def test_metrics_ranking():
    """Test metrics-based re-ranking."""
    # Skill A: High semantic similarity, low completion rate
    # Skill B: Medium semantic similarity, high completion rate

    # Expected: Skill B should rank higher
    results = await engine.find_skills("fix errors")

    assert results[0].skill_name == "skill-b"
    assert "effectiveness bonus" in results[0].reasoning


def test_session_context_boost():
    """Test session context boosting."""
    # Set up: Skill X used successfully in similar session

    results = await engine.find_skills_with_session_context(
        query="database optimization",
        session_id="test-session",
    )

    # Skill X should be boosted
    skill_x = next(r for r in results if r.skill_name == "skill-x")
    assert "context boost" in skill_x.reasoning
```

### 8.2 Integration Tests

```python
# tests/skills/test_skill_integration.py


async def test_full_workflow():
    """Test end-to-end skill recommendation."""
    # 1. Index skills
    await index_skills_directory(
        Path(".claude/skills"),
        vector_store,
    )

    # 2. Track some usage
    tracker = ContextualSkillTracker()
    complete = tracker.track_invocation_with_context(
        skill_name="crackerjack-run",
        user_query="fix type errors",
        session_id="test-session",
    )
    complete(completed=True, follow_up_actions=["git commit"])

    # 3. Search with context
    engine = SkillSearchEngine(vector_store, tracker, session_db)
    results = await engine.find_skills_with_session_context(
        query="I have type checking issues",
        session_id="test-session",
    )

    # 4. Verify
    assert len(results) > 0
    assert results[0].confidence_score > 0.6
    assert results[0].confidence_level in ["high", "medium"]


async def test_fallback_without_session_buddy():
    """Test graceful degradation without session-buddy."""
    engine = SkillSearchEngine(
        vector_store,
        tracker,
        session_db=None,  # No session-buddy
    )

    # Should still work, just without context boost
    results = await engine.find_skills("database query")

    assert len(results) > 0
    assert all("context boost" not in r.reasoning for r in results)
```

### 8.3 Performance Tests

```python
# tests/skills/test_performance.py


def test_search_latency():
    """Test search performance under load."""
    import time

    engine = SkillSearchEngine(vector_store, tracker, session_db)

    # Warm-up
    await engine.find_skills("test query")

    # Benchmark
    start = time.time()
    for _ in range(100):
        await engine.find_skills("random query")
    elapsed = time.time() - start

    avg_latency_ms = (elapsed / 100) * 1000

    assert avg_latency_ms < 100, f"Search too slow: {avg_latency_ms:.1f}ms"


def test_indexing_performance():
    """Test skill indexing performance."""
    skills_dir = Path(".claude/skills")
    skill_count = len(list(skills_dir.glob("*.md")))

    start = time.time()
    await index_skills_directory(skills_dir, vector_store)
    elapsed = time.time() - start

    avg_per_skill = elapsed / skill_count

    assert avg_per_skill < 1.0, f"Indexing too slow: {avg_per_skill:.2f}s per skill"
```

______________________________________________________________________

## 9. Performance Considerations

### 9.1 Optimization Strategies

**Embedding Caching**:

- Cache skill embeddings in vector store (already done)
- Cache query embeddings for common queries (TTL: 1 hour)
- Use `functools.lru_cache` for embedding generation

**Batch Processing**:

- Use `generate_embeddings_batch()` for multiple skills
- Parallelize chunk embedding with `asyncio.gather()`
- Process skill files in parallel (limit to 4 concurrent)

**Vector Store Optimization**:

- Index on `file_type` and `chunk_id` (already done)
- Consider HNSW indexing for faster similarity search
- Pre-compute norms for cosine similarity

**Metrics Caching**:

- Cache effectiveness scores (TTL: 5 minutes)
- Re-compute only on new invocations
- Store computed scores in metrics JSON

### 9.2 Scalability Estimates

**Assumptions**:

- 100 skills
- 20 chunks per skill
- 384-dimensional embeddings
- 10,000 invocations tracked

**Storage Requirements**:

- Embeddings: 100 skills × 20 chunks × 384 × 4 bytes = ~3 MB
- Metadata: ~100 KB
- Metrics JSON: ~500 KB
- **Total**: \<5 MB (very manageable)

**Query Performance**:

- Embedding generation: ~50ms (Ollama) or ~10ms (ONNX)
- Vector similarity search: ~20ms (SQLite) or ~5ms (DuckDB)
- Metrics lookup: ~5ms (JSON file)
- **Total latency**: \<100ms per query

**Throughput**:

- Indexing: ~1 skill/second
- Search: ~10 queries/second
- Scales linearly with skill count

______________________________________________________________________

## 10. CLI Interface

### 10.1 Skill Management Commands

```bash
# Index all skills
python -m crackerjack skills index

# Search for skills
python -m crackerjack skills search "fix type errors"

# View skill statistics
python -m crackerjack skills stats

# Re-index specific skill
python -m crackerjack skills reindex skill-name

# Clear skill index
python -m crackerjack skills clear-index
```

### 10.2 Interactive Recommendations

```python
# In Python code
from crackerjack.skills import recommend_skill

# Get recommendation
result = await recommend_skill(
    query="I need to fix type errors in my Python code",
    session_id="current-session",
    max_results=3,
)

for rec in results:
    print(f"{rec.skill_name}: {rec.confidence_score:.2f}")
    print(f"  Reasoning: {rec.reasoning}")
    print(f"  Confidence: {rec.confidence_level}")
```

### 10.3 MCP Tool Integration

```python
# Add to crackerjack/mcp/tools/skill_tools.py


@mcp_tool()
async def recommend_skill_tool(
    query: str,
    session_id: str | None = None,
    max_results: int = 5,
) -> list[dict]:
    """Recommend skills based on query and context.

    Args:
        query: Problem description or task
        session_id: Optional session context
        max_results: Maximum recommendations

    Returns:
        Ranked skill recommendations with confidence scores
    """
    engine = get_skill_search_engine()
    results = await engine.find_skills_with_session_context(
        query=query,
        session_id=session_id,
        max_results=max_results,
    )

    return [rec.to_dict() for rec in results]
```

______________________________________________________________________

## 11. Monitoring & Evaluation

### 11.1 Metrics to Track

**Recommendation Quality**:

- Acceptance rate: % of recommendations that user accepts
- First-position accuracy: % of times top recommendation is used
- Average rank of selected skill

**Effectiveness Learning**:

- Improvement in completion rates over time
- Reduction in failed invocations
- Faster skill selection (time to find right skill)

**Performance**:

- Average search latency
- Indexing time per skill
- Cache hit rates

### 11.2 A/B Testing Plan

**Control**: Current keyword-based skill search (if exists)
**Treatment**: Semantic + metrics-based recommendations

**Metrics**:

- Primary: Task completion rate
- Secondary: Time to find skill, user satisfaction

**Duration**: 2 weeks of usage

### 11.3 Continuous Learning Loop

```
User interacts with skills
        ↓
Track invocations with context
        ↓
Compute effectiveness scores
        ↓
Update recommendation weights
        ↓
Monitor quality metrics
        ↓
Tune algorithm if needed
        ↓
Repeat
```

______________________________________________________________________

## 12. Risk Mitigation

### 12.1 Potential Issues

**Issue 1: Semantic Search Returns Irrelevant Results**

- **Mitigation**: High minimum similarity threshold (0.6)
- **Fallback**: Keyword-based search on metadata
- **Validation**: Human review of top results for common queries

**Issue 2: Cold Start Problem (No Metrics for New Skills)**

- **Mitigation**: Use semantic score only for new skills
- **Exploration bonus**: +10% boost for first 10 invocations
- **Manual rating**: Allow users to rate skill usefulness

**Issue 3: Session-Buddy Not Available**

- **Mitigation**: Make session-buddy optional
- **Graceful degradation**: Work without context boost
- **Clear logging**: Warn when context unavailable

**Issue 4: Embedding Model Bias**

- **Mitigation**: Use well-tested model (all-MiniLM-L6-v2)
- **Validation**: Test against diverse skill descriptions
- **Fallback**: Allow model swapping in config

### 12.2 Rollback Plan

If vector search causes issues:

1. Disable via config: `enable_skill_search = false`
1. Fallback to existing skill selection
1. Preserve metrics for later analysis
1. Debug with verbose logging

______________________________________________________________________

## 13. Open Questions

1. **Skill Location**: Where are Crackerjack's skill files stored?

   - Need to scan for `.md` files with skill frontmatter
   - Likely in `.claude/skills/` or similar

1. **MCP Integration**: Should recommendations be exposed via MCP?

   - **Recommendation**: Yes, for Claude Code integration
   - Tool name: `recommend_skill`

1. **Multi-Project Skills**: How to handle project-specific skills?

   - Store in project-local `.claude/skills/`
   - Index separately, merge in search results
   - Boost local skills in recommendations

1. **Skill Versioning**: How to handle skill updates?

   - File hash-based re-indexing (already implemented)
   - Track skill evolution in metrics
   - Archive old versions for comparison

______________________________________________________________________

## 14. Next Steps

### Immediate Actions

1. **Discovery**: Find all skill markdown files in codebase

   ```bash
   find /Users/les/Projects/crackerjack -name "*.md" -path "*skills*"
   ```

1. **Prototype**: Implement basic skill search

   - Parse one skill file
   - Generate embeddings
   - Test semantic search

1. **Integration**: Connect with existing metrics

   - Extend `SkillMetricsTracker` with context
   - Implement effectiveness scoring

1. **Test**: Validate with real queries

   - "I need to fix type errors"
   - "Database optimization"
   - "Code quality checks"

### Success Metrics

- Week 1: Can search skills by semantic meaning
- Week 2: Metrics improve ranking accuracy
- Week 3: Session context provides relevant boosts
- Week 4: Production-ready with \<100ms latency

______________________________________________________________________

## 15. Code Examples

### Example 1: Basic Usage

```python
from crackerjack.skills.skill_search import SkillSearchEngine
from crackerjack.services.vector_store import VectorStore
from crackerjack.skills.metrics import SkillMetricsTracker
from crackerjack.models.semantic_models import SemanticConfig

# Initialize
config = SemanticConfig()
vector_store = VectorStore(config)
metrics = SkillMetricsTracker()
engine = SkillSearchEngine(vector_store, metrics)

# Search for skills
results = await engine.find_skills(
    query="I need to fix type errors in Python",
    max_results=3,
)

# Display recommendations
for rec in results:
    print(f"{rec.skill_name}: {rec.confidence_score:.2f} ({rec.confidence_level})")
    print(f"  {rec.reasoning}\n")
```

### Example 2: Track with Context

```python
from crackerjack.skills.contextual_tracker import ContextualSkillTracker

tracker = ContextualSkillTracker()

# Start tracking
complete = tracker.track_invocation_with_context(
    skill_name="crackerjack-run",
    user_query="I have type checking errors",
    session_id="my-project-session",
    alternatives=["python-type-fixing", "mypy-tool"],
    rank=1,
)

# ... skill executes ...

# Mark complete
complete(
    completed=True,
    follow_up_actions=["git commit", "push changes"],
)
```

### Example 3: Session-Aware Search

```python
# With session context
results = await engine.find_skills_with_session_context(
    query="optimize database queries",
    session_id="current-session-id",
    max_results=5,
)

# Results boosted by:
# - Past skill usage in this session
# - Similar successful sessions
# - Project-specific patterns
```

______________________________________________________________________

## Appendix A: Data Model

### Skill Metadata Schema

```python
@dataclass
class ParsedSkill:
    """Parsed skill markdown file."""

    name: str
    description: str
    category: str
    tags: list[str]
    chunks: list[SkillChunk]

    def __hash__(self) -> int:
        return hash(self.name)


@dataclass
class SkillChunk:
    """Text chunk from skill file."""

    content: str
    chunk_type: Literal["metadata", "concept", "workflow", "example"]
    weight: float
    metadata: dict[str, Any]
```

### Enhanced Metrics Schema

```python
@dataclass
class UsagePattern:
    """Learned pattern from skill usage."""

    pattern_id: str
    query_type: str  # "fix type errors", "database optimization", etc.
    skill_name: str
    outcome: Literal["success", "failure", "preferred_alternative"]
    confidence: float
    sample_count: int
    last_updated: datetime
```

______________________________________________________________________

## Appendix B: Configuration

### New Config Options

Add to `settings/crackerjack.yaml`:

```yaml
# Skill Search Configuration
skill_search:
  enabled: true
  vector_db_path: ".session-buddy/skill_vectors.db"
  indexing:
    chunk_size: 500
    chunk_overlap: 50
    max_chunks_per_skill: 20
  search:
    default_max_results: 5
    min_similarity_threshold: 0.6
    semantic_weight: 0.6
    effectiveness_weight: 0.3
    context_weight: 0.1
  learning:
    enable_pattern_learning: true
    exploration_bonus: 0.1
    time_decay_days: 30
```

______________________________________________________________________

## Appendix C: References

- **Vector Store**: `crackerjack/services/vector_store.py`
- **Embeddings**: `crackerjack/services/ai/embeddings.py`
- **Metrics**: `crackerjack/skills/metrics.py`
- **Session-Buddy Search**: `/Users/les/Projects/session-buddy/session_buddy/reflection/search.py`
- **Session-Buddy Embeddings**: `/Users/les/Projects/session-buddy/session_buddy/reflection/embeddings.py`
- **Semantic Models**: `crackerjack/models/semantic_models.py`

______________________________________________________________________

**Document Version**: 1.0
**Last Updated**: 2025-02-10
**Status**: Ready for Implementation
