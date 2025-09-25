"""Semantic enhancement helpers for AI agents.

This module provides shared utilities for integrating semantic search
capabilities into existing agents, enabling them to discover related
code patterns and make more informed decisions.
"""

import typing as t
from dataclasses import dataclass
from pathlib import Path

from ..models.semantic_models import SearchQuery, SemanticConfig
from ..services.vector_store import VectorStore


@dataclass
class SemanticInsight:
    """Container for semantic analysis results."""

    query: str
    related_patterns: list[dict[str, t.Any]]
    similarity_threshold: float
    total_matches: int
    high_confidence_matches: int
    session_id: str | None = None
    timestamp: str | None = None

    def to_session_data(self) -> dict[str, t.Any]:
        """Convert insight to session-storable data."""
        return {
            "query": self.query,
            "related_patterns": self.related_patterns[:3],  # Limit for storage
            "similarity_threshold": self.similarity_threshold,
            "total_matches": self.total_matches,
            "high_confidence_matches": self.high_confidence_matches,
            "session_id": self.session_id,
            "timestamp": self.timestamp,
        }


class SemanticEnhancer:
    """Helper class to add semantic capabilities to existing agents."""

    def __init__(self, project_path: Path) -> None:
        self.project_path = project_path
        self._vector_store: VectorStore | None = None
        self._config = self._create_semantic_config()
        self._session_insights: dict[str, SemanticInsight] = {}

    @staticmethod
    def _create_semantic_config() -> SemanticConfig:
        """Create semantic search configuration."""
        return SemanticConfig(
            embedding_model="sentence-transformers/all-MiniLM-L6-v2",
            chunk_size=512,
            chunk_overlap=50,
            max_search_results=10,
            similarity_threshold=0.7,
            embedding_dimension=384,
        )

    def _get_vector_store(self) -> VectorStore:
        """Get or create vector store instance."""
        if self._vector_store is None:
            db_path = self._get_persistent_db_path()
            self._vector_store = VectorStore(self._config, db_path=db_path)
        return self._vector_store

    def _get_persistent_db_path(self) -> Path:
        """Get the path to the persistent semantic search database."""
        db_path = self.project_path / ".crackerjack" / "semantic_index.db"
        db_path.parent.mkdir(exist_ok=True)
        return db_path

    async def find_similar_patterns(
        self,
        query: str,
        current_file: Path | None = None,
        min_similarity: float = 0.6,
        max_results: int = 5,
    ) -> SemanticInsight:
        """Find similar code patterns using semantic search.

        Args:
            query: Search query (code snippet, function signature, or description)
            current_file: File to exclude from results (to avoid self-matches)
            min_similarity: Minimum similarity threshold (0.0-1.0)
            max_results: Maximum number of results to return

        Returns:
            SemanticInsight with related patterns and analysis
        """
        vector_store = self._get_vector_store()

        search_query = SearchQuery(
            query=query,
            max_results=max_results,
            min_similarity=min_similarity,
            file_types=["py"],
        )

        try:
            results = vector_store.search(search_query)

            # Filter out results from current file if specified
            if current_file:
                results = [
                    result for result in results if result.file_path != current_file
                ]

            # Categorize results by confidence
            high_confidence = [
                result for result in results if result.similarity_score >= 0.8
            ]

            # Convert to pattern format
            patterns = [
                {
                    "file_path": str(result.file_path),
                    "content": result.content[:300],  # Truncate for readability
                    "similarity_score": result.similarity_score,
                    "lines": f"{result.start_line}-{result.end_line}",
                    "file_type": result.file_type,
                    "confidence_level": "high"
                    if result.similarity_score >= 0.8
                    else "medium",
                }
                for result in results
            ]

            return SemanticInsight(
                query=query,
                related_patterns=patterns,
                similarity_threshold=min_similarity,
                total_matches=len(patterns),
                high_confidence_matches=len(high_confidence),
            )

        except Exception:
            # Return empty insight on error
            return SemanticInsight(
                query=query,
                related_patterns=[],
                similarity_threshold=min_similarity,
                total_matches=0,
                high_confidence_matches=0,
            )

    async def find_duplicate_patterns(
        self, code_snippet: str, current_file: Path | None = None
    ) -> SemanticInsight:
        """Find potential code duplicates using semantic similarity.

        Args:
            code_snippet: Code snippet to find duplicates for
            current_file: File to exclude from results

        Returns:
            SemanticInsight focused on potential duplicates
        """
        insight = await self.find_similar_patterns(
            query=code_snippet,
            current_file=current_file,
            min_similarity=0.75,  # Higher threshold for duplicates
            max_results=8,
        )

        # Store insight for session continuity
        await self.store_insight_to_session(insight, "DuplicateDetection")
        return insight

    async def find_refactoring_opportunities(
        self, function_signature: str, current_file: Path | None = None
    ) -> SemanticInsight:
        """Find similar functions for refactoring opportunities.

        Args:
            function_signature: Function signature or description
            current_file: File to exclude from results

        Returns:
            SemanticInsight focused on refactoring opportunities
        """
        return await self.find_similar_patterns(
            query=function_signature,
            current_file=current_file,
            min_similarity=0.6,
            max_results=6,
        )

    async def find_implementation_examples(
        self, pattern_description: str, current_file: Path | None = None
    ) -> SemanticInsight:
        """Find implementation examples for a given pattern.

        Args:
            pattern_description: Description of the pattern to find
            current_file: File to exclude from results

        Returns:
            SemanticInsight with implementation examples
        """
        return await self.find_similar_patterns(
            query=pattern_description,
            current_file=current_file,
            min_similarity=0.5,  # Lower threshold for broader examples
            max_results=10,
        )

    def enhance_recommendations(
        self,
        base_recommendations: list[str],
        semantic_insight: SemanticInsight,
    ) -> list[str]:
        """Enhance existing recommendations with semantic insights.

        Args:
            base_recommendations: Original agent recommendations
            semantic_insight: Semantic analysis results

        Returns:
            Enhanced recommendations including semantic insights
        """
        enhanced = base_recommendations.copy()

        if semantic_insight.total_matches > 0:
            # Add semantic-based recommendations
            if semantic_insight.high_confidence_matches > 0:
                enhanced.append(
                    f"Semantic analysis found {semantic_insight.high_confidence_matches} "
                    f"highly similar patterns - consider consolidation"
                )

            # Add pattern discovery insights
            if semantic_insight.total_matches >= 3:
                enhanced.append(
                    f"Found {semantic_insight.total_matches} related patterns "
                    f"across codebase - review for consistency"
                )

            # Add specific file references for high-confidence matches
            high_conf_files = {
                pattern["file_path"]
                for pattern in semantic_insight.related_patterns
                if pattern["confidence_level"] == "high"
            }

            if high_conf_files:
                file_list = ", ".join(Path(f).name for f in sorted(high_conf_files)[:3])
                if len(high_conf_files) > 3:
                    file_list += f" (+{len(high_conf_files) - 3} more)"

                enhanced.append(f"Similar implementations found in: {file_list}")

        return enhanced

    def get_semantic_context_summary(self, insight: SemanticInsight) -> str:
        """Generate a summary of semantic context for logging.

        Args:
            insight: Semantic analysis results

        Returns:
            Human-readable summary string
        """
        if insight.total_matches == 0:
            return "No similar patterns found in semantic analysis"

        high_conf_pct = (
            insight.high_confidence_matches / insight.total_matches * 100
            if insight.total_matches > 0
            else 0
        )

        return (
            f"Semantic context: {insight.total_matches} similar patterns found "
            f"({insight.high_confidence_matches} high-confidence, {high_conf_pct:.0f}%)"
        )

    async def store_insight_to_session(
        self, insight: SemanticInsight, agent_type: str
    ) -> bool:
        """Store semantic insight to session for continuity.

        Args:
            insight: Semantic insight to store
            agent_type: Type of agent storing the insight

        Returns:
            True if stored successfully, False otherwise
        """
        try:
            # Create a unique session key for this insight
            session_key = f"{agent_type}_{hash(insight.query)}"

            # Store in local cache
            self._session_insights[session_key] = insight

            return True
        except Exception:
            return False


def create_semantic_enhancer(project_path: Path) -> SemanticEnhancer:
    """Factory function to create a semantic enhancer.

    Args:
        project_path: Path to the project root

    Returns:
        Configured SemanticEnhancer instance
    """
    return SemanticEnhancer(project_path)


async def get_session_enhanced_recommendations(
    base_recommendations: list[str], agent_type: str, project_path: Path
) -> list[str]:
    """Get enhanced recommendations based on session insights.

    Args:
        base_recommendations: Original recommendations
        agent_type: Type of agent requesting enhancements
        project_path: Path to the project root

    Returns:
        Enhanced recommendations with session context
    """
    try:
        enhancer = create_semantic_enhancer(project_path)

        # Try to find stored insights for this agent type
        session_insights = [
            insight
            for key, insight in enhancer._session_insights.items()
            if key.startswith(agent_type)
        ]

        if not session_insights:
            return base_recommendations

        enhanced = base_recommendations.copy()

        # Add session-based recommendations
        total_patterns = sum(insight.total_matches for insight in session_insights)
        if total_patterns > 5:
            enhanced.append(
                f"Session context: {total_patterns} similar patterns found "
                "across recent analyses - consider broader refactoring"
            )

        return enhanced

    except Exception:
        # Fallback to original recommendations on error
        return base_recommendations
