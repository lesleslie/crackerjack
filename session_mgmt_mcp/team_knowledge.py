"""Team Knowledge Base module for shared reflection database with permissions.

This module provides team collaboration features including:
- Shared reflection database with user permissions
- Team access control and role management
- Collaborative knowledge sharing
- Team-specific conversation organization
"""

import hashlib
import importlib.util
import json
import logging
import sqlite3
import threading
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any

DUCKDB_AVAILABLE = importlib.util.find_spec("duckdb") is not None
AIOFILES_AVAILABLE = importlib.util.find_spec("aiofiles") is not None

logger = logging.getLogger(__name__)


class UserRole(Enum):
    """User roles in team knowledge base."""

    VIEWER = "viewer"
    CONTRIBUTOR = "contributor"
    MODERATOR = "moderator"
    ADMIN = "admin"


class AccessLevel(Enum):
    """Access levels for knowledge base content."""

    PRIVATE = "private"
    TEAM = "team"
    PROJECT = "project"
    PUBLIC = "public"


@dataclass
class TeamUser:
    """Team user information."""

    user_id: str
    username: str
    email: str | None
    role: UserRole
    teams: list[str]
    created_at: datetime
    last_active: datetime
    permissions: dict[str, bool]


@dataclass
class TeamReflection:
    """Team-shared reflection with access control."""

    id: str
    content: str
    tags: list[str]
    access_level: AccessLevel
    team_id: str | None
    project_id: str | None
    author_id: str
    created_at: datetime
    updated_at: datetime
    votes: int
    viewers: set[str]
    editors: set[str]


@dataclass
class Team:
    """Team information and configuration."""

    team_id: str
    name: str
    description: str
    owner_id: str
    members: set[str]
    projects: set[str]
    created_at: datetime
    settings: dict[str, Any]


class TeamKnowledgeManager:
    """Manages team knowledge base with permissions and access control."""

    def __init__(self, db_path: str | None = None) -> None:
        """Initialize team knowledge manager."""
        self.db_path = db_path or str(
            Path.home() / ".claude" / "data" / "team_knowledge.db",
        )
        self._lock = threading.Lock()
        self._init_database()

    def _init_database(self) -> None:
        """Initialize SQLite database for team knowledge."""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY,
                    username TEXT UNIQUE NOT NULL,
                    email TEXT,
                    role TEXT NOT NULL,
                    teams TEXT,  -- JSON array
                    created_at TIMESTAMP,
                    last_active TIMESTAMP,
                    permissions TEXT  -- JSON object
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS teams (
                    team_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT,
                    owner_id TEXT NOT NULL,
                    members TEXT,  -- JSON array
                    projects TEXT,  -- JSON array
                    created_at TIMESTAMP,
                    settings TEXT,  -- JSON object
                    FOREIGN KEY (owner_id) REFERENCES users(user_id)
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS team_reflections (
                    id TEXT PRIMARY KEY,
                    content TEXT NOT NULL,
                    tags TEXT,  -- JSON array
                    access_level TEXT NOT NULL,
                    team_id TEXT,
                    project_id TEXT,
                    author_id TEXT NOT NULL,
                    created_at TIMESTAMP,
                    updated_at TIMESTAMP,
                    votes INTEGER DEFAULT 0,
                    viewers TEXT,  -- JSON array
                    editors TEXT,  -- JSON array
                    FOREIGN KEY (author_id) REFERENCES users(user_id),
                    FOREIGN KEY (team_id) REFERENCES teams(team_id)
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS access_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    resource_id TEXT,
                    resource_type TEXT,
                    timestamp TIMESTAMP,
                    details TEXT  -- JSON object
                )
            """)

            # Create indices
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_reflections_team ON team_reflections(team_id)",
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_reflections_project ON team_reflections(project_id)",
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_reflections_author ON team_reflections(author_id)",
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_reflections_access ON team_reflections(access_level)",
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_access_logs_user ON access_logs(user_id)",
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_access_logs_timestamp ON access_logs(timestamp)",
            )

    async def create_user(
        self,
        user_id: str,
        username: str,
        email: str | None = None,
        role: UserRole = UserRole.CONTRIBUTOR,
    ) -> TeamUser:
        """Create a new team user."""
        user = TeamUser(
            user_id=user_id,
            username=username,
            email=email,
            role=role,
            teams=[],
            created_at=datetime.now(),
            last_active=datetime.now(),
            permissions=self._get_default_permissions(role),
        )

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO users (user_id, username, email, role, teams, created_at, last_active, permissions)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    user.user_id,
                    user.username,
                    user.email,
                    user.role.value,
                    json.dumps(user.teams),
                    user.created_at,
                    user.last_active,
                    json.dumps(user.permissions),
                ),
            )

        await self._log_access(
            user_id,
            "user_created",
            user_id,
            "user",
            {"role": role.value},
        )
        return user

    async def create_team(
        self,
        team_id: str,
        name: str,
        description: str,
        owner_id: str,
    ) -> Team:
        """Create a new team."""
        team = Team(
            team_id=team_id,
            name=name,
            description=description,
            owner_id=owner_id,
            members={owner_id},
            projects=set(),
            created_at=datetime.now(),
            settings={"auto_approve_members": False, "public_reflections": True},
        )

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO teams (team_id, name, description, owner_id, members, projects, created_at, settings)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    team.team_id,
                    team.name,
                    team.description,
                    team.owner_id,
                    json.dumps(list(team.members)),
                    json.dumps(list(team.projects)),
                    team.created_at,
                    json.dumps(team.settings),
                ),
            )

        # Add owner to team
        await self._add_user_to_team(owner_id, team_id)
        await self._log_access(
            owner_id,
            "team_created",
            team_id,
            "team",
            {"name": name},
        )
        return team

    async def add_team_reflection(
        self,
        content: str,
        author_id: str,
        tags: list[str] | None = None,
        access_level: AccessLevel = AccessLevel.TEAM,
        team_id: str | None = None,
        project_id: str | None = None,
    ) -> str:
        """Add reflection to team knowledge base."""
        reflection_id = hashlib.sha256(
            f"{content}{author_id}{time.time()}".encode(),
        ).hexdigest()[:16]

        reflection = TeamReflection(
            id=reflection_id,
            content=content,
            tags=tags or [],
            access_level=access_level,
            team_id=team_id,
            project_id=project_id,
            author_id=author_id,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            votes=0,
            viewers=set(),
            editors=set(),
        )

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO team_reflections
                (id, content, tags, access_level, team_id, project_id, author_id, created_at, updated_at, votes, viewers, editors)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    reflection.id,
                    reflection.content,
                    json.dumps(reflection.tags),
                    reflection.access_level.value,
                    reflection.team_id,
                    reflection.project_id,
                    reflection.author_id,
                    reflection.created_at,
                    reflection.updated_at,
                    reflection.votes,
                    json.dumps(list(reflection.viewers)),
                    json.dumps(list(reflection.editors)),
                ),
            )

        await self._log_access(
            author_id,
            "reflection_created",
            reflection_id,
            "reflection",
            {"team_id": team_id, "access_level": access_level.value},
        )
        return reflection_id

    async def search_team_reflections(
        self,
        query: str,
        user_id: str,
        team_id: str | None = None,
        project_id: str | None = None,
        tags: list[str] | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Search team reflections with access control."""
        user_teams = await self._get_user_teams(user_id)

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            # Build query with access control
            where_conditions = ["1=1"]
            params = []

            # Access control: user can see public, team reflections they have access to, or their own
            access_condition = """(
                access_level = 'public' OR
                (access_level = 'team' AND team_id IN ({}) AND team_id IS NOT NULL) OR
                author_id = ?
            )""".format(",".join("?" * len(user_teams)))
            where_conditions.append(access_condition)
            params.extend(user_teams)
            params.append(user_id)

            # Content search
            if query:
                where_conditions.append("(content LIKE ? OR tags LIKE ?)")
                params.extend([f"%{query}%", f"%{query}%"])

            # Team filter
            if team_id:
                where_conditions.append("team_id = ?")
                params.append(team_id)

            # Project filter
            if project_id:
                where_conditions.append("project_id = ?")
                params.append(project_id)

            # Tag filter
            if tags:
                tag_conditions = []
                for tag in tags:
                    tag_conditions.append("tags LIKE ?")
                    params.append(f"%{tag}%")
                where_conditions.append(f"({' OR '.join(tag_conditions)})")

            query_sql = f"""
                SELECT * FROM team_reflections
                WHERE {" AND ".join(where_conditions)}
                ORDER BY votes DESC, created_at DESC
                LIMIT ?
            """
            params.append(limit)

            cursor = conn.execute(query_sql, params)
            results = []

            for row in cursor.fetchall():
                result = dict(row)
                result["tags"] = json.loads(result["tags"] or "[]")
                result["viewers"] = json.loads(result["viewers"] or "[]")
                result["editors"] = json.loads(result["editors"] or "[]")
                results.append(result)

        await self._log_access(
            user_id,
            "reflections_searched",
            None,
            "search",
            {"query": query, "results_count": len(results)},
        )
        return results

    async def vote_reflection(
        self,
        reflection_id: str,
        user_id: str,
        vote_delta: int = 1,
    ) -> bool:
        """Vote on a team reflection."""
        if not await self._can_access_reflection(reflection_id, user_id):
            return False

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                UPDATE team_reflections
                SET votes = votes + ?, updated_at = ?
                WHERE id = ?
            """,
                (vote_delta, datetime.now(), reflection_id),
            )

        await self._log_access(
            user_id,
            "reflection_voted",
            reflection_id,
            "reflection",
            {"vote_delta": vote_delta},
        )
        return True

    async def join_team(
        self,
        user_id: str,
        team_id: str,
        requester_id: str | None = None,
    ) -> bool:
        """Request to join a team or add user to team."""
        team = await self._get_team(team_id)
        if not team:
            return False

        # Check if requester has permission to add users
        if requester_id and requester_id != user_id:
            if not await self._can_manage_team(requester_id, team_id):
                return False

        await self._add_user_to_team(user_id, team_id)
        await self._log_access(
            user_id,
            "team_joined",
            team_id,
            "team",
            {"requester_id": requester_id},
        )
        return True

    async def get_team_stats(self, team_id: str, user_id: str) -> dict[str, Any] | None:
        """Get team statistics and activity."""
        if not await self._can_access_team(user_id, team_id):
            return None

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            # Get team info
            team_row = conn.execute(
                "SELECT * FROM teams WHERE team_id = ?",
                (team_id,),
            ).fetchone()
            if not team_row:
                return None

            team_data = dict(team_row)
            team_data["members"] = json.loads(team_data["members"] or "[]")
            team_data["projects"] = json.loads(team_data["projects"] or "[]")

            # Get reflection stats
            reflection_stats = conn.execute(
                """
                SELECT
                    COUNT(*) as total_reflections,
                    COUNT(DISTINCT author_id) as active_contributors,
                    SUM(votes) as total_votes,
                    AVG(votes) as avg_votes
                FROM team_reflections
                WHERE team_id = ?
            """,
                (team_id,),
            ).fetchone()

            # Get recent activity
            recent_activity = conn.execute(
                """
                SELECT COUNT(*) as recent_reflections
                FROM team_reflections
                WHERE team_id = ? AND created_at > ?
            """,
                (team_id, datetime.now() - timedelta(days=7)),
            ).fetchone()

            stats = {
                "team": dict(team_data),
                "member_count": len(team_data["members"]),
                "project_count": len(team_data["projects"]),
                "reflection_stats": dict(reflection_stats),
                "recent_activity": dict(recent_activity),
            }

        await self._log_access(user_id, "team_stats_viewed", team_id, "team", {})
        return stats

    async def get_user_permissions(self, user_id: str) -> dict[str, Any]:
        """Get user's current permissions and team memberships."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            user_row = conn.execute(
                "SELECT * FROM users WHERE user_id = ?",
                (user_id,),
            ).fetchone()

            if not user_row:
                return {}

            user_data = dict(user_row)
            user_data["teams"] = json.loads(user_data["teams"] or "[]")
            user_data["permissions"] = json.loads(user_data["permissions"] or "{}")

            # Get team details
            team_details = []
            if user_data["teams"]:
                placeholders = ",".join("?" * len(user_data["teams"]))
                team_rows = conn.execute(
                    f"SELECT team_id, name, description FROM teams WHERE team_id IN ({placeholders})",
                    user_data["teams"],
                ).fetchall()
                team_details = [dict(row) for row in team_rows]

        return {
            "user": user_data,
            "teams": team_details,
            "can_create_teams": user_data["permissions"].get("create_teams", False),
            "can_moderate": user_data["permissions"].get("moderate_content", False),
        }

    # Private helper methods

    def _get_default_permissions(self, role: UserRole) -> dict[str, bool]:
        """Get default permissions for user role."""
        base_permissions = {
            "read_reflections": True,
            "create_reflections": False,
            "vote_reflections": False,
            "join_teams": False,
            "create_teams": False,
            "moderate_content": False,
            "admin_access": False,
        }

        if role == UserRole.CONTRIBUTOR:
            base_permissions.update(
                {
                    "create_reflections": True,
                    "vote_reflections": True,
                    "join_teams": True,
                },
            )
        elif role == UserRole.MODERATOR:
            base_permissions.update(
                {
                    "create_reflections": True,
                    "vote_reflections": True,
                    "join_teams": True,
                    "create_teams": True,
                    "moderate_content": True,
                },
            )
        elif role == UserRole.ADMIN:
            base_permissions.update(dict.fromkeys(base_permissions.keys(), True))

        return base_permissions

    async def _add_user_to_team(self, user_id: str, team_id: str) -> None:
        """Add user to team."""
        with sqlite3.connect(self.db_path) as conn:
            # Update team members
            team_row = conn.execute(
                "SELECT members FROM teams WHERE team_id = ?",
                (team_id,),
            ).fetchone()
            if team_row:
                members = set(json.loads(team_row[0] or "[]"))
                members.add(user_id)
                conn.execute(
                    "UPDATE teams SET members = ? WHERE team_id = ?",
                    (json.dumps(list(members)), team_id),
                )

            # Update user teams
            user_row = conn.execute(
                "SELECT teams FROM users WHERE user_id = ?",
                (user_id,),
            ).fetchone()
            if user_row:
                teams = json.loads(user_row[0] or "[]")
                if team_id not in teams:
                    teams.append(team_id)
                    conn.execute(
                        "UPDATE users SET teams = ?, last_active = ? WHERE user_id = ?",
                        (json.dumps(teams), datetime.now(), user_id),
                    )

    async def _get_user_teams(self, user_id: str) -> list[str]:
        """Get teams user belongs to."""
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT teams FROM users WHERE user_id = ?",
                (user_id,),
            ).fetchone()
            return json.loads(row[0] or "[]") if row else []

    async def _get_team(self, team_id: str) -> dict[str, Any] | None:
        """Get team information."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM teams WHERE team_id = ?",
                (team_id,),
            ).fetchone()
            if row:
                team_data = dict(row)
                team_data["members"] = set(json.loads(team_data["members"] or "[]"))
                team_data["projects"] = set(json.loads(team_data["projects"] or "[]"))
                team_data["settings"] = json.loads(team_data["settings"] or "{}")
                return team_data
            return None

    async def _can_access_reflection(self, reflection_id: str, user_id: str) -> bool:
        """Check if user can access reflection."""
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                """
                SELECT access_level, team_id, author_id FROM team_reflections
                WHERE id = ?
            """,
                (reflection_id,),
            ).fetchone()

            if not row:
                return False

            access_level, team_id, author_id = row

            # Author can always access
            if author_id == user_id:
                return True

            # Public reflections accessible to all
            if access_level == AccessLevel.PUBLIC.value:
                return True

            # Team reflections require team membership
            if access_level == AccessLevel.TEAM.value and team_id:
                user_teams = await self._get_user_teams(user_id)
                return team_id in user_teams

            return False

    async def _can_access_team(self, user_id: str, team_id: str) -> bool:
        """Check if user can access team."""
        user_teams = await self._get_user_teams(user_id)
        return team_id in user_teams

    async def _can_manage_team(self, user_id: str, team_id: str) -> bool:
        """Check if user can manage team."""
        team = await self._get_team(team_id)
        if not team:
            return False

        # Team owner can manage
        if team["owner_id"] == user_id:
            return True

        # Check if user has admin permissions
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT permissions FROM users WHERE user_id = ?",
                (user_id,),
            ).fetchone()
            if row:
                permissions = json.loads(row[0] or "{}")
                return permissions.get("admin_access", False) or permissions.get(
                    "moderate_content",
                    False,
                )

        return False

    async def _log_access(
        self,
        user_id: str,
        action: str,
        resource_id: str | None,
        resource_type: str,
        details: dict[str, Any],
    ) -> None:
        """Log user access for audit trail."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO access_logs (user_id, action, resource_id, resource_type, timestamp, details)
                VALUES (?, ?, ?, ?, ?, ?)
            """,
                (
                    user_id,
                    action,
                    resource_id,
                    resource_type,
                    datetime.now(),
                    json.dumps(details),
                ),
            )


# Global instance
_team_knowledge_manager = None


def get_team_knowledge_manager() -> TeamKnowledgeManager:
    """Get global team knowledge manager instance."""
    global _team_knowledge_manager
    if _team_knowledge_manager is None:
        _team_knowledge_manager = TeamKnowledgeManager()
    return _team_knowledge_manager


# Public API functions for MCP tools
async def create_team_user(
    user_id: str,
    username: str,
    email: str | None = None,
    role: str = "contributor",
) -> dict[str, Any]:
    """Create a new team user."""
    manager = get_team_knowledge_manager()
    user_role = UserRole(role.lower())
    user = await manager.create_user(user_id, username, email, user_role)
    return asdict(user)


async def create_team(
    team_id: str,
    name: str,
    description: str,
    owner_id: str,
) -> dict[str, Any]:
    """Create a new team."""
    manager = get_team_knowledge_manager()
    team = await manager.create_team(team_id, name, description, owner_id)
    return {
        "team_id": team.team_id,
        "name": team.name,
        "description": team.description,
        "owner_id": team.owner_id,
        "member_count": len(team.members),
        "project_count": len(team.projects),
        "created_at": team.created_at.isoformat(),
        "settings": team.settings,
    }


async def add_team_reflection(
    content: str,
    author_id: str,
    tags: list[str] | None = None,
    access_level: str = "team",
    team_id: str | None = None,
    project_id: str | None = None,
) -> str:
    """Add reflection to team knowledge base."""
    manager = get_team_knowledge_manager()
    level = AccessLevel(access_level.lower())
    return await manager.add_team_reflection(
        content,
        author_id,
        tags,
        level,
        team_id,
        project_id,
    )


async def search_team_knowledge(
    query: str,
    user_id: str,
    team_id: str | None = None,
    project_id: str | None = None,
    tags: list[str] | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Search team reflections with access control."""
    manager = get_team_knowledge_manager()
    return await manager.search_team_reflections(
        query,
        user_id,
        team_id,
        project_id,
        tags,
        limit,
    )


async def join_team(
    user_id: str,
    team_id: str,
    requester_id: str | None = None,
) -> bool:
    """Join a team or add user to team."""
    manager = get_team_knowledge_manager()
    return await manager.join_team(user_id, team_id, requester_id)


async def get_team_statistics(team_id: str, user_id: str) -> dict[str, Any] | None:
    """Get team statistics and activity."""
    manager = get_team_knowledge_manager()
    return await manager.get_team_stats(team_id, user_id)


async def get_user_team_permissions(user_id: str) -> dict[str, Any]:
    """Get user's permissions and team memberships."""
    manager = get_team_knowledge_manager()
    return await manager.get_user_permissions(user_id)


async def vote_on_reflection(
    reflection_id: str,
    user_id: str,
    vote_delta: int = 1,
) -> bool:
    """Vote on a team reflection."""
    manager = get_team_knowledge_manager()
    return await manager.vote_reflection(reflection_id, user_id, vote_delta)
