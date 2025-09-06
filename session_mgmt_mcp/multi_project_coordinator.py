#!/usr/bin/env python3
"""Multi-Project Session Coordination.

Manages relationships and coordination between multiple projects and their sessions.
"""

import asyncio
import hashlib
import json
import time
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationInfo, field_validator

from .reflection_tools import ReflectionDatabase


class ProjectGroup(BaseModel):
    """Represents a group of related projects."""

    id: str = Field(description="Unique identifier for the project group")
    name: str = Field(
        min_length=1, max_length=200, description="Name of the project group"
    )
    description: str = Field(
        default="", max_length=1000, description="Description of the project group"
    )
    projects: list[str] = Field(
        min_length=1, description="List of project identifiers in this group"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata for the project group"
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="When the project group was created",
    )

    @field_validator("projects")
    @classmethod
    def validate_projects(cls, v: list[str]) -> list[str]:
        """Ensure all project names are non-empty."""
        if not v:
            msg = "Project group must contain at least one project"
            raise ValueError(msg)
        for project in v:
            if not project.strip():
                msg = "Project names cannot be empty"
                raise ValueError(msg)
        return [p.strip() for p in v]


class ProjectDependency(BaseModel):
    """Represents a dependency between two projects."""

    id: str = Field(description="Unique identifier for the project dependency")
    source_project: str = Field(
        min_length=1, description="The project that depends on another"
    )
    target_project: str = Field(
        min_length=1, description="The project that is depended upon"
    )
    dependency_type: Literal["uses", "extends", "references", "shares_code"] = Field(
        description="Type of dependency relationship"
    )
    description: str = Field(
        default="",
        max_length=1000,
        description="Description of the dependency relationship",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata for the dependency"
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="When the dependency was created",
    )

    @field_validator("source_project", "target_project")
    @classmethod
    def validate_project_names(cls, v: str) -> str:
        """Ensure project names are non-empty."""
        if not v.strip():
            msg = "Project names cannot be empty"
            raise ValueError(msg)
        return v.strip()

    @field_validator("target_project")
    @classmethod
    def validate_not_self_dependency(cls, v: str, info: ValidationInfo) -> str:
        """Ensure projects don't depend on themselves."""
        if hasattr(info, "data") and info.data and v == info.data.get("source_project"):
            msg = "Project cannot depend on itself"
            raise ValueError(msg)
        return v


class SessionLink(BaseModel):
    """Represents a link between sessions across projects."""

    id: str = Field(description="Unique identifier for the session link")
    source_session_id: str = Field(
        min_length=1, description="The session that links to another"
    )
    target_session_id: str = Field(
        min_length=1, description="The session that is linked to"
    )
    link_type: Literal["related", "continuation", "reference", "dependency"] = Field(
        description="Type of relationship between sessions"
    )
    context: str = Field(
        default="",
        max_length=2000,
        description="Context or reason for the session link",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata for the session link"
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="When the session link was created",
    )

    @field_validator("source_session_id", "target_session_id")
    @classmethod
    def validate_session_ids(cls, v: str) -> str:
        """Ensure session IDs are non-empty."""
        if not v.strip():
            msg = "Session IDs cannot be empty"
            raise ValueError(msg)
        return v.strip()

    @field_validator("target_session_id")
    @classmethod
    def validate_not_self_link(cls, v: str, info: ValidationInfo) -> str:
        """Ensure sessions don't link to themselves."""
        if (
            hasattr(info, "data")
            and info.data
            and v == info.data.get("source_session_id")
        ):
            msg = "Session cannot link to itself"
            raise ValueError(msg)
        return v


class MultiProjectCoordinator:
    """Coordinates sessions and knowledge across multiple projects."""

    def __init__(self, reflection_db: ReflectionDatabase) -> None:
        self.reflection_db = reflection_db
        self.active_project_groups: dict[str, ProjectGroup] = {}
        self.dependency_cache: dict[str, list[ProjectDependency]] = {}
        self.session_links_cache: dict[str, list[SessionLink]] = {}

    async def create_project_group(
        self,
        name: str,
        projects: list[str],
        description: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> ProjectGroup:
        """Create a new project group."""
        group_id = hashlib.md5(f"{name}_{time.time()}".encode()).hexdigest()

        group = ProjectGroup(
            id=group_id,
            name=name,
            description=description,
            projects=projects,
            metadata=metadata or {},
        )

        # Store in database
        await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: self.reflection_db.conn.execute(
                """
                INSERT INTO project_groups (id, name, description, projects, created_at, metadata)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    group.id,
                    group.name,
                    group.description,
                    group.projects,
                    group.created_at,
                    json.dumps(group.metadata),
                ],
            ),
        )

        self.reflection_db.conn.commit()
        self.active_project_groups[group_id] = group

        return group

    async def add_project_dependency(
        self,
        source_project: str,
        target_project: str,
        dependency_type: str,
        description: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> ProjectDependency:
        """Add a dependency relationship between projects."""
        dep_id = hashlib.md5(
            f"{source_project}_{target_project}_{dependency_type}".encode(),
        ).hexdigest()

        dependency = ProjectDependency(
            id=dep_id,
            source_project=source_project,
            target_project=target_project,
            dependency_type=dependency_type,
            description=description,
            metadata=metadata or {},
        )

        # Store in database
        await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: self.reflection_db.conn.execute(
                """
                INSERT INTO project_dependencies
                (id, source_project, target_project, dependency_type, description, created_at, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (id) DO UPDATE SET
                source_project = EXCLUDED.source_project,
                target_project = EXCLUDED.target_project,
                dependency_type = EXCLUDED.dependency_type,
                description = EXCLUDED.description,
                created_at = EXCLUDED.created_at,
                metadata = EXCLUDED.metadata
                """,
                [
                    dependency.id,
                    dependency.source_project,
                    dependency.target_project,
                    dependency.dependency_type,
                    dependency.description,
                    dependency.created_at,
                    json.dumps(dependency.metadata),
                ],
            ),
        )

        self.reflection_db.conn.commit()

        # Clear cache for affected projects
        self._clear_dependency_cache(source_project)
        self._clear_dependency_cache(target_project)

        return dependency

    async def link_sessions(
        self,
        source_session_id: str,
        target_session_id: str,
        link_type: str,
        context: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> SessionLink:
        """Create a link between two sessions across projects."""
        link_id = hashlib.md5(
            f"{source_session_id}_{target_session_id}_{link_type}".encode(),
        ).hexdigest()

        link = SessionLink(
            id=link_id,
            source_session_id=source_session_id,
            target_session_id=target_session_id,
            link_type=link_type,
            context=context,
            metadata=metadata or {},
        )

        # Store in database
        await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: self.reflection_db.conn.execute(
                """
                INSERT INTO session_links
                (id, source_session_id, target_session_id, link_type, context, created_at, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (id) DO UPDATE SET
                source_session_id = EXCLUDED.source_session_id,
                target_session_id = EXCLUDED.target_session_id,
                link_type = EXCLUDED.link_type,
                context = EXCLUDED.context,
                created_at = EXCLUDED.created_at,
                metadata = EXCLUDED.metadata
                """,
                [
                    link.id,
                    link.source_session_id,
                    link.target_session_id,
                    link.link_type,
                    link.context,
                    link.created_at,
                    json.dumps(link.metadata),
                ],
            ),
        )

        self.reflection_db.conn.commit()

        # Clear cache for affected sessions
        self._clear_session_links_cache(source_session_id)
        self._clear_session_links_cache(target_session_id)

        return link

    async def get_project_groups(
        self,
        project: str | None = None,
    ) -> list[ProjectGroup]:
        """Get project groups, optionally filtered by project."""
        sql = "SELECT id, name, description, projects, created_at, metadata FROM project_groups"
        params = []

        if project:
            sql += " WHERE list_contains(projects, ?)"
            params.append(project)

        sql += " ORDER BY created_at DESC"

        results = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: self.reflection_db.conn.execute(sql, params).fetchall(),
        )

        groups = []
        for row in results:
            group = ProjectGroup(
                id=row[0],
                name=row[1],
                description=row[2],
                projects=row[3],
                metadata=json.loads(row[5]) if row[5] else {},
                created_at=row[4],
            )
            groups.append(group)
            self.active_project_groups[group.id] = group

        return groups

    async def get_project_dependencies(
        self,
        project: str,
        direction: str = "both",  # "outbound", "inbound", "both"
    ) -> list[ProjectDependency]:
        """Get dependencies for a project."""
        # Create a unique cache key that includes the direction
        cache_key = f"{project}_{direction}"
        if cache_key in self.dependency_cache:
            return self.dependency_cache[cache_key]

        conditions = []
        params = []

        if direction == "outbound":
            conditions.append("source_project = ?")
            params.append(project)
        elif direction == "inbound":
            conditions.append("target_project = ?")
            params.append(project)
        else:  # both
            conditions.append("(source_project = ? OR target_project = ?)")
            params.extend([project, project])

        sql = f"""
            SELECT id, source_project, target_project, dependency_type, description, created_at, metadata
            FROM project_dependencies
            WHERE {" OR ".join(conditions)}
            ORDER BY created_at DESC
        """

        results = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: self.reflection_db.conn.execute(sql, params).fetchall(),
        )

        dependencies = []
        for row in results:
            dep = ProjectDependency(
                id=row[0],
                source_project=row[1],
                target_project=row[2],
                dependency_type=row[3],
                description=row[4],
                metadata=json.loads(row[6]) if row[6] else {},
                created_at=row[5],
            )
            dependencies.append(dep)

        # Cache with the direction-specific key
        self.dependency_cache[cache_key] = dependencies
        return dependencies

    async def get_session_links(self, session_id: str) -> list[SessionLink]:
        """Get all links for a session."""
        if session_id in self.session_links_cache:
            return self.session_links_cache[session_id]

        sql = """
            SELECT id, source_session_id, target_session_id, link_type, context, created_at, metadata
            FROM session_links
            WHERE source_session_id = ? OR target_session_id = ?
            ORDER BY created_at DESC
        """

        results = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: self.reflection_db.conn.execute(
                sql,
                [session_id, session_id],
            ).fetchall(),
        )

        links = []
        for row in results:
            link = SessionLink(
                id=row[0],
                source_session_id=row[1],
                target_session_id=row[2],
                link_type=row[3],
                context=row[4],
                metadata=json.loads(row[6]) if row[6] else {},
                created_at=row[5],
            )
            links.append(link)

        self.session_links_cache[session_id] = links
        return links

    async def find_related_conversations(
        self,
        current_project: str,
        query: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Find conversations across related projects."""
        # Get project dependencies to find related projects
        dependencies = await self.get_project_dependencies(current_project)
        related_projects = {current_project}

        for dep in dependencies:
            if dep.source_project == current_project:
                related_projects.add(dep.target_project)
            if dep.target_project == current_project:
                related_projects.add(dep.source_project)

        # Search conversations in all related projects
        results = []

        for project in related_projects:
            project_results = await self.reflection_db.search_conversations(
                query=query,
                limit=limit,
                project=project,
            )

            for result in project_results:
                result["source_project"] = project
                result["is_current_project"] = project == current_project
                results.append(result)

        # Sort by relevance score and return top results
        results.sort(key=lambda x: x.get("score", 0), reverse=True)
        return results[:limit]

    async def get_cross_project_insights(
        self,
        projects: list[str],
        time_range_days: int = 30,
    ) -> dict[str, Any]:
        """Get insights across multiple projects."""
        since_date = datetime.now(UTC) - timedelta(days=time_range_days)
        insights = {
            "project_activity": {},
            "common_patterns": [],
            "knowledge_gaps": [],
            "collaboration_opportunities": [],
        }

        # Analyze activity per project
        for project in projects:
            sql = """
                SELECT COUNT(*) as conversation_count,
                       MAX(timestamp) as last_activity,
                       AVG(LENGTH(content)) as avg_content_length
                FROM conversations
                WHERE project = ? AND timestamp >= ?
            """

            result = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.reflection_db.conn.execute(
                    sql,
                    [project, since_date],
                ).fetchone(),
            )

            if result:
                insights["project_activity"][project] = {
                    "conversation_count": result[0],
                    "last_activity": result[1],
                    "avg_content_length": result[2],
                }

        # Find common patterns across projects
        common_patterns = await self._find_common_patterns(projects, since_date)
        insights["common_patterns"] = common_patterns

        return insights

    async def _find_common_patterns(
        self,
        projects: list[str],
        since_date: datetime,
    ) -> list[dict[str, Any]]:
        """Find common patterns across projects."""
        # Simple pattern detection based on common keywords
        patterns = []

        # Get frequent terms across all projects
        sql = """
            SELECT project, content
            FROM conversations
            WHERE project = ANY(?) AND timestamp >= ?
        """

        results = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: self.reflection_db.conn.execute(
                sql,
                [projects, since_date],
            ).fetchall(),
        )

        # Simple keyword frequency analysis
        project_keywords = {}
        for project, content in results:
            if project not in project_keywords:
                project_keywords[project] = {}

            # Extract simple keywords (could be enhanced with NLP)
            words = content.lower().split()
            for word in words:
                if len(word) > 4:  # Skip short words
                    project_keywords[project][word] = (
                        project_keywords[project].get(word, 0) + 1
                    )

        # Find keywords common across multiple projects
        common_keywords = {}
        for project, keywords in project_keywords.items():
            for word, count in keywords.items():
                if word not in common_keywords:
                    common_keywords[word] = []
                common_keywords[word].append((project, count))

        # Filter to keywords present in multiple projects
        for word, project_counts in common_keywords.items():
            if len(project_counts) >= 2:  # Present in at least 2 projects
                patterns.append(
                    {
                        "pattern": word,
                        "projects": [p[0] for p in project_counts],
                        "frequency": sum(p[1] for p in project_counts),
                    },
                )

        # Sort by frequency
        patterns.sort(key=lambda x: x["frequency"], reverse=True)
        return patterns[:10]  # Return top 10 patterns

    def _clear_dependency_cache(self, project: str) -> None:
        """Clear dependency cache for a project."""
        # Remove all cache entries for this project (regardless of direction)
        keys_to_remove = [
            key for key in self.dependency_cache if key.startswith(f"{project}_")
        ]
        for key in keys_to_remove:
            del self.dependency_cache[key]

    def _clear_session_links_cache(self, session_id: str) -> None:
        """Clear session links cache for a session."""
        if session_id in self.session_links_cache:
            del self.session_links_cache[session_id]

    async def cleanup_old_links(self, max_age_days: int = 365):
        """Clean up old session links and dependencies."""
        cutoff_date = datetime.now(UTC) - timedelta(days=max_age_days)

        # Count old links before deletion
        count_before = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: self.reflection_db.conn.execute(
                "SELECT COUNT(*) FROM session_links WHERE created_at < ?",
                [cutoff_date],
            ).fetchone()[0],
        )

        # Clean up old session links
        await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: self.reflection_db.conn.execute(
                "DELETE FROM session_links WHERE created_at < ?",
                [cutoff_date],
            ),
        )

        self.reflection_db.conn.commit()

        # Clear caches
        self.session_links_cache.clear()

        return {
            "deleted_session_links": count_before,
        }
