"""
Session-Buddy Skills Tracking Compatibility Layer.

This module provides skills tracking functionality that integrates with
session-buddy's new API while maintaining backward compatibility with
crackerjack's expected interface.
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger(__name__)


class SkillsTracker:
    """Track AI agent skill invocations and recommendations.

    **Purpose**: Record which agents are selected, user queries, and outcomes
    **Storage**: SQLite database at db_path/skills.db
    **Features**:
    - Track agent invocations with context
    - Store skill recommendations
    - Query historical patterns

    **Usage**:
        ```python
        tracker = SkillsTracker(session_id="my-session", db_path=Path("./data"))
        tracker.track_invocation(
            skill_name="python-pro",
            user_query="Fix this bug",
            workflow_phase="debugging"
        )
        recommendations = tracker.recommend_skills(
            user_query="Need help with Rust",
            limit=5
        )
        ```
    """

    def __init__(
        self,
        session_id: str,
        db_path: Path,
        enable_embeddings: bool = False,
    ) -> None:
        """Initialize skills tracker.

        **Args**:
            session_id: Unique identifier for this session
            db_path: Directory containing skills.db
            enable_embeddings: Whether to use semantic search (requires sentence-transformers)
        """
        self.session_id = session_id
        self.db_path = db_path / "skills.db"
        self.enable_embeddings = enable_embeddings
        self._conn: sqlite3.Connection | None = None

        self._initialize_db()

    def _initialize_db(self) -> None:
        """Create database schema if it doesn't exist."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")

        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS skill_invocations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                skill_name TEXT NOT NULL,
                user_query TEXT,
                workflow_phase TEXT,
                alternatives_considered TEXT,  -- JSON array
                selection_rank INTEGER,
                completed BOOLEAN DEFAULT FALSE,
                error_type TEXT,
                follow_up_actions TEXT,  -- JSON array
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP
            )
            """
        )

        self._conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_session_id
            ON skill_invocations(session_id)
            """
        )

        self._conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_skill_name
            ON skill_invocations(skill_name)
            """
        )

        self._conn.commit()

    def track_invocation(
        self,
        skill_name: str,
        user_query: str | None = None,
        workflow_path: str | None = None,
        alternatives_considered: list[str] | None = None,
        selection_rank: int | None = None,
    ) -> Callable[..., None]:
        """Track a skill invocation and return a completer callback.

        **Args**:
            skill_name: Name of the agent/skill being used
            user_query: User's query that triggered this selection
            workflow_path: Current workflow phase
            alternatives_considered: Other skills that were considered
            selection_rank: Rank of this skill in the selection

        **Returns**: A callable that should be invoked with completion status
        """

        import json

        invocation_id = self._conn.execute(
            """
            INSERT INTO skill_invocations
            (session_id, skill_name, user_query, workflow_phase,
             alternatives_considered, selection_rank)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                self.session_id,
                skill_name,
                user_query,
                workflow_path,
                json.dumps(alternatives_considered or []),
                selection_rank,
            ),
        ).lastrowid

        self._conn.commit()

        logger.debug(
            f"Tracking skill invocation: {skill_name} "
            f"(invocation_id={invocation_id}, session={self.session_id})"
        )

        def completer(
            *,
            completed: bool = True,
            follow_up_actions: list[str] | None = None,
            error_type: str | None = None,
        ) -> None:
            """Mark the invocation as complete with optional details."""
            self._conn.execute(
                """
                UPDATE skill_invocations
                SET completed = ?, error_type = ?, follow_up_actions = ?, completed_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    completed,
                    error_type,
                    json.dumps(follow_up_actions or []),
                    invocation_id,
                ),
            )
            self._conn.commit()

            logger.debug(
                f"Skill invocation completed: {skill_name} "
                f"(completed={completed}, invocation_id={invocation_id})"
            )

        return completer

    def recommend_skills(
        self,
        user_query: str,
        limit: int = 5,
        session_id: str | None = None,
        workflow_phase: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get skill recommendations based on query and historical patterns.

        **Args**:
            user_query: The user's query
            limit: Maximum number of recommendations to return
            session_id: Filter by session (optional)
            workflow_phase: Filter by workflow phase (optional)

        **Returns**: List of recommendation dicts with similarity scores
        """
        # Simple frequency-based recommendations
        # TODO: Add semantic search when embeddings are enabled

        query = f"""
            SELECT skill_name, COUNT(*) as usage_count,
                   AVG(completed) as success_rate
            FROM skill_invocations
            WHERE user_query IS NOT NULL
        """

        params: list[Any] = []

        if session_id:
            query += " AND session_id = ?"
            params.append(session_id)

        if workflow_phase:
            query += " AND workflow_phase = ?"
            params.append(workflow_phase)

        query += f"""
            GROUP BY skill_name
            ORDER BY usage_count DESC, success_rate DESC
            LIMIT ?
        """
        params.append(limit)

        results = self._conn.execute(query, params).fetchall()

        recommendations = [
            {
                "skill_name": row[0],
                "usage_count": row[1],
                "success_rate": row[2],
                "similarity_score": 1.0 - (idx * 0.1),  # Simple ranking
                "reason": f"Used {row[1]} times previously",
            }
            for idx, row in enumerate(results)
        ]

        logger.debug(
            f"Generated {len(recommendations)} recommendations for query: {user_query[:50]}..."
        )

        return recommendations

    def close(self) -> None:
        """Close database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None


def get_session_tracker(
    session_id: str,
    db_path: Path,
    enable_embeddings: bool = False,
) -> SkillsTracker:
    """Get or create a skills tracker for the session.

    **Args**:
        session_id: Unique session identifier
        db_path: Directory for skills database
        enable_embeddings: Enable semantic search (requires sentence-transformers)

    **Returns**: SkillsTracker instance
    """
    return SkillsTracker(
        session_id=session_id,
        db_path=db_path,
        enable_embeddings=enable_embeddings,
    )
