from __future__ import annotations

import asyncio
import logging
import typing as t
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from crackerjack.models.git_analytics import (
    GitBranchEvent,
    GitCommitData,
    WorkflowEvent,
)

if t.TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GitEvent:
    commit_hash: str
    timestamp: datetime
    author_name: str
    message: str
    event_type: str
    semantic_tags: list[str] = field(default_factory=list)
    metadata: dict[str, t.Any] = field(default_factory=dict)

    def to_searchable_text(self) -> str:
        parts = [
            f"{self.event_type}: {self.message}",
            f"by {self.author_name}",
        ]

        if self.semantic_tags:
            parts.append(f"tags: {', '.join(self.semantic_tags)}")

        return ". ".join(parts)


@dataclass(frozen=True)
class GitVelocityMetrics:
    repository_path: str
    period_start: datetime
    period_end: datetime
    total_commits: int
    avg_commits_per_day: float
    avg_commits_per_week: float
    conventional_compliance_rate: float
    breaking_changes: int
    merge_conflict_rate: float
    most_active_hour: int
    most_active_day: int

    def to_searchable_text(self) -> str:
        return (
            f"Repository velocity: {self.avg_commits_per_day:.1f} commits/day, "
            f"{self.avg_commits_per_week:.1f} commits/week, "
            f"{self.conventional_compliance_rate:.1%} conventional compliance, "
            f"{self.breaking_changes} breaking changes, "
            f"{self.merge_conflict_rate:.1%} conflict rate"
        )


@dataclass
class AkoshaClientConfig:
    server_url: str = "http://localhost: 8000"
    timeout_seconds: int = 30
    enable_fallback: bool = True
    max_retries: int = 3


class AkoshaClientProtocol(t.Protocol):
    async def store_memory(
        self,
        content: str,
        metadata: dict[str, t.Any],
        embedding: list[float] | None = None,
    ) -> str: ...

    async def semantic_search(
        self,
        query: str,
        limit: int = 10,
        filters: dict[str, t.Any] | None = None,
    ) -> list[dict[str, t.Any]]: ...

    async def search_git_commits(
        self,
        query: str,
        limit: int = 10,
        filters: dict[str, t.Any] | None = None,
    ) -> list[GitCommitData]: ...

    async def search_git_branch_events(
        self,
        query: str,
        limit: int = 10,
        filters: dict[str, t.Any] | None = None,
    ) -> list[GitBranchEvent]: ...

    async def search_workflow_events(
        self,
        query: str,
        limit: int = 10,
        filters: dict[str, t.Any] | None = None,
    ) -> list[WorkflowEvent]: ...

    def is_connected(self) -> bool: ...


@dataclass
class NoOpAkoshaClient:
    config: AkoshaClientConfig = field(default_factory=AkoshaClientConfig)

    async def store_memory(
        self,
        content: str,
        metadata: dict[str, t.Any],
        embedding: list[float] | None = None,
    ) -> str:
        logger.debug("No-op Akosha client: skipping store_memory")
        return "noop-id"

    async def semantic_search(
        self,
        query: str,
        limit: int = 10,
        filters: dict[str, t.Any] | None = None,
    ) -> list[dict[str, t.Any]]:
        logger.debug("No-op Akosha client: returning empty search results")
        return []

    async def search_git_commits(
        self,
        query: str,
        limit: int = 10,
        filters: dict[str, t.Any] | None = None,
    ) -> list[GitCommitData]:
        logger.debug("No-op Akosha client: returning empty git commits")
        return []

    async def search_git_branch_events(
        self,
        query: str,
        limit: int = 10,
        filters: dict[str, t.Any] | None = None,
    ) -> list[GitBranchEvent]:
        logger.debug("No-op Akosha client: returning empty branch events")
        return []

    async def search_workflow_events(
        self,
        query: str,
        limit: int = 10,
        filters: dict[str, t.Any] | None = None,
    ) -> list[WorkflowEvent]:
        logger.debug("No-op Akosha client: returning empty workflow events")
        return []

    def is_connected(self) -> bool:
        return False


@dataclass
class DirectAkoshaClient:
    config: AkoshaClientConfig = field(default_factory=AkoshaClientConfig)
    _embedding_service: t.Any = field(init=False, default=None)
    _hot_store: t.Any = field(init=False, default=None)
    _initialized: bool = field(init=False, default=False)

    async def initialize(self) -> None:
        if self._initialized:
            return

        try:
            from akosha.processing.embeddings import EmbeddingService
            from akosha.storage.hot_store import HotStore

            self._embedding_service = EmbeddingService()
            await self._embedding_service.initialize()

            self._hot_store = HotStore(max_size_mb=100)

            self._initialized = True
            logger.info("✅ Direct Akosha integration initialized")

        except ImportError as e:
            logger.warning(f"⚠️ Akosha package not available: {e}")
            self._initialized = False

    async def store_memory(
        self,
        content: str,
        metadata: dict[str, t.Any],
        embedding: list[float] | None = None,
    ) -> str:
        if not self._initialized:
            await self.initialize()

        if not self._embedding_service or not self._hot_store:
            logger.debug("Akosha services not available")
            return "unavailable"

        try:
            if embedding is None:
                embedding_array = await self._embedding_service.generate_embedding(
                    content
                )
                embedding = embedding_array.tolist()

            ts = datetime.now().timestamp()
            memory_id = f"git-{metadata.get('commit_hash', 'unknown')}-{ts}"

            from akosha.models import Memory

            memory = Memory(
                id=memory_id,
                content=content,
                metadata=metadata,
                embedding=embedding,
                timestamp=datetime.now().isoformat(),
            )

            await self._hot_store.store(memory)
            logger.debug(f"Stored memory: {memory_id}")

            return memory_id

        except Exception as e:
            logger.error(f"Failed to store memory: {e}")
            return "error"

    async def semantic_search(
        self,
        query: str,
        limit: int = 10,
        filters: dict[str, t.Any] | None = None,
    ) -> list[dict[str, t.Any]]:
        if not self._initialized:
            await self.initialize()

        if not self._embedding_service or not self._hot_store:
            logger.debug("Akosha services not available")
            return []

        try:
            query_embedding = await self._embedding_service.generate_embedding(query)

            results = await self._hot_store.search(
                query_embedding.tolist(),
                limit=limit,
                filters=filters or {},
            )

            return results

        except Exception as e:
            logger.error(f"Failed to perform semantic search: {e}")
            return []

    async def search_git_commits(
        self,
        query: str,
        limit: int = 10,
        filters: dict[str, t.Any] | None = None,
    ) -> list[GitCommitData]:
        results = await self.semantic_search(
            query=query,
            limit=limit,
            filters={"type": "git_commit", **(filters or {})},
        )

        commits = []
        for result in results:
            metadata = result.get("metadata", {})
            if metadata.get("type") == "git_commit":
                commits.append(
                    GitCommitData(
                        commit_hash=metadata["commit_hash"],
                        timestamp=datetime.fromisoformat(metadata["timestamp"]),
                        author_name=metadata["author_name"],
                        author_email=metadata.get("author_email", ""),
                        message=result.get("content", ""),
                        files_changed=metadata.get("files_changed", []),
                        insertions=metadata.get("insertions", 0),
                        deletions=metadata.get("deletions", 0),
                        is_conventional=metadata.get("is_conventional", False),
                        conventional_type=metadata.get("conventional_type"),
                        conventional_scope=metadata.get("conventional_scope"),
                        has_breaking_change=metadata.get("has_breaking_change", False),
                        is_merge=metadata.get("is_merge", False),
                        branch=metadata.get("branch", "main"),
                        repository=metadata["repository"],
                        tags=metadata.get("tags", []),
                    )
                )

        return commits

    async def search_git_branch_events(
        self,
        query: str,
        limit: int = 10,
        filters: dict[str, t.Any] | None = None,
    ) -> list[GitBranchEvent]:
        results = await self.semantic_search(
            query=query,
            limit=limit,
            filters={"type": "git_branch_event", **(filters or {})},
        )

        events = []
        for result in results:
            metadata = result.get("metadata", {})
            if metadata.get("type") == "git_branch_event":
                event_type = metadata.get("event_type", "created")
                if event_type not in ("created", "deleted", "merged", "rebased"):
                    continue

                events.append(
                    GitBranchEvent(
                        event_type=event_type,
                        branch_name=metadata["branch_name"],
                        timestamp=datetime.fromisoformat(metadata["timestamp"]),
                        author_name=metadata["author_name"],
                        commit_hash=metadata["commit_hash"],
                        source_branch=metadata.get("source_branch"),
                        repository=metadata["repository"],
                        metadata={
                            k: v
                            for k, v in metadata.items()
                            if k
                            not in {
                                "type",
                                "event_type",
                                "branch_name",
                                "timestamp",
                                "author_name",
                                "commit_hash",
                                "source_branch",
                                "repository",
                            }
                        },
                    )
                )

        return events

    async def search_workflow_events(
        self,
        query: str,
        limit: int = 10,
        filters: dict[str, t.Any] | None = None,
    ) -> list[WorkflowEvent]:
        results = await self.semantic_search(
            query=query,
            limit=limit,
            filters={"type": "workflow_event", **(filters or {})},
        )

        events = []
        for result in results:
            metadata = result.get("metadata", {})
            if metadata.get("type") == "workflow_event":
                event_type = metadata.get("event_type", "ci_started")
                status = metadata.get("status", "pending")

                events.append(
                    WorkflowEvent(
                        event_type=event_type,
                        workflow_name=metadata["workflow_name"],
                        timestamp=datetime.fromisoformat(metadata["timestamp"]),
                        status=status,
                        commit_hash=metadata["commit_hash"],
                        branch=metadata["branch"],
                        repository=metadata["repository"],
                        duration_seconds=metadata.get("duration_seconds"),
                        metadata={
                            k: v
                            for k, v in metadata.items()
                            if k
                            not in {
                                "type",
                                "event_type",
                                "workflow_name",
                                "timestamp",
                                "status",
                                "commit_hash",
                                "branch",
                                "repository",
                                "duration_seconds",
                            }
                        },
                    )
                )

        return events

    def is_connected(self) -> bool:
        return self._initialized


@dataclass
class MCPAkoshaClient:
    config: AkoshaClientConfig = field(default_factory=AkoshaClientConfig)
    _client: t.Any = field(init=False, default=None)
    _connected: bool = field(init=False, default=False)

    async def initialize(self) -> None:
        if self._connected:
            return

        try:
            # TODO: Implement actual MCP client initialization

            logger.info(f"Connecting to Akosha MCP server at {self.config.server_url}")
            self._connected = True
            logger.info("✅ Akosha MCP client initialized")

        except Exception as e:
            logger.error(f"Failed to initialize MCP client: {e}")
            self._connected = False

    async def store_memory(
        self,
        content: str,
        metadata: dict[str, t.Any],
        embedding: list[float] | None = None,
    ) -> str:
        if not self._connected:
            await self.initialize()

        if not self._connected:
            return "disconnected"

        try:
            # TODO: Implement MCP tool call

            return "mcp-id"

        except Exception as e:
            logger.error(f"MCP store_memory failed: {e}")
            return "error"

    async def semantic_search(
        self,
        query: str,
        limit: int = 10,
        filters: dict[str, t.Any] | None = None,
    ) -> list[dict[str, t.Any]]:
        if not self._connected:
            await self.initialize()

        if not self._connected:
            return []

        try:
            # TODO: Implement MCP tool call

            return []

        except Exception as e:
            logger.error(f"MCP semantic_search failed: {e}")
            return []

    async def search_git_commits(
        self,
        query: str,
        limit: int = 10,
        filters: dict[str, t.Any] | None = None,
    ) -> list[GitCommitData]:
        # TODO: Implement MCP call for git commit search
        return []

    async def search_git_branch_events(
        self,
        query: str,
        limit: int = 10,
        filters: dict[str, t.Any] | None = None,
    ) -> list[GitBranchEvent]:
        # TODO: Implement MCP call for branch event search
        return []

    async def search_workflow_events(
        self,
        query: str,
        limit: int = 10,
        filters: dict[str, t.Any] | None = None,
    ) -> list[WorkflowEvent]:
        # TODO: Implement MCP call for workflow event search
        return []

    def is_connected(self) -> bool:
        return self._connected


@dataclass
class AkoshaGitIntegration:
    client: AkoshaClientProtocol
    repo_path: Path

    async def initialize(self) -> None:
        if hasattr(self.client, "initialize"):
            await self.client.initialize()

    async def index_git_commit(
        self,
        commit: GitCommitData,
    ) -> str:
        searchable_text = commit.to_searchable_text()
        metadata = commit.to_metadata()

        return await self.client.store_memory(
            content=searchable_text,
            metadata=metadata,
        )

    async def index_git_branch_event(
        self,
        event: GitBranchEvent,
    ) -> str:
        searchable_text = event.to_searchable_text()
        metadata = event.to_metadata()

        return await self.client.store_memory(
            content=searchable_text,
            metadata=metadata,
        )

    async def index_workflow_event(
        self,
        event: WorkflowEvent,
    ) -> str:
        searchable_text = event.to_searchable_text()
        metadata = event.to_metadata()

        return await self.client.store_memory(
            content=searchable_text,
            metadata=metadata,
        )
        logger.info(f"Akosha git integration initialized for {self.repo_path}")

    async def index_repository_history(
        self,
        days_back: int = 30,
    ) -> int:
        from crackerjack.memory.git_metrics_collector import GitMetricsCollector

        collector = GitMetricsCollector(
            repo_path=self.repo_path,
        )

        try:
            dashboard = collector.get_velocity_dashboard(days_back=days_back)

            await self._index_velocity_metrics(dashboard)

            indexed_count = 0

            commits = collector.git.get_commits(
                since=dashboard.period_start,
                until=dashboard.period_end,
            )

            for commit in commits:
                await self._index_commit(commit)
                indexed_count += 1

            logger.info(f"Indexed {indexed_count} commits from {self.repo_path}")
            return indexed_count

        finally:
            collector.close()

    async def _index_commit(self, commit: t.Any) -> None:
        git_commit = GitCommitData(
            commit_hash=commit.hash,
            timestamp=commit.author_timestamp,
            author_name=commit.author_name,
            author_email=commit.author_email,
            message=commit.message,
            files_changed=commit.files_changed,
            insertions=commit.insertions,
            deletions=commit.deletions,
            is_conventional=commit.is_conventional,
            conventional_type=commit.conventional_type,
            conventional_scope=commit.conventional_scope,
            has_breaking_change=commit.has_breaking_change,
            is_merge=commit.is_merge,
            branch=commit.branch,
            repository=str(self.repo_path),
            tags=self._extract_semantic_tags(commit),
        )

        await self.index_git_commit(git_commit)

    async def _index_velocity_metrics(self, dashboard: t.Any) -> None:
        metrics = GitVelocityMetrics(
            repository_path=str(self.repo_path),
            period_start=dashboard.period_start,
            period_end=dashboard.period_end,
            total_commits=dashboard.commit_metrics.total_commits,
            avg_commits_per_day=dashboard.commit_metrics.avg_commits_per_day,
            avg_commits_per_week=dashboard.commit_metrics.avg_commits_per_week,
            conventional_compliance_rate=dashboard.commit_metrics.conventional_compliance_rate,
            breaking_changes=dashboard.commit_metrics.breaking_changes,
            merge_conflict_rate=dashboard.merge_metrics.conflict_rate,
            most_active_hour=dashboard.commit_metrics.most_active_hour,
            most_active_day=dashboard.commit_metrics.most_active_day,
        )

        searchable_text = metrics.to_searchable_text()

        await self.client.store_memory(
            content=searchable_text,
            metadata={
                "type": "git_velocity",
                "repository": str(self.repo_path),
                "period_start": dashboard.period_start.isoformat(),
                "period_end": dashboard.period_end.isoformat(),
            },
        )

    def _extract_semantic_tags(self, commit: t.Any) -> list[str]:
        tags = []

        if commit.is_conventional and commit.conventional_type:
            tags.append(f"type:{commit.conventional_type}")

        if commit.conventional_scope:
            tags.append(f"scope:{commit.conventional_scope}")

        if commit.has_breaking_change:
            tags.append("breaking")

        if commit.is_merge:
            tags.append("merge")

        return tags

    async def search_git_history(
        self,
        query: str,
        limit: int = 10,
    ) -> list[GitEvent]:
        results = await self.client.semantic_search(
            query=query,
            limit=limit,
            filters={
                "repository": str(self.repo_path),
            },
        )

        events = []
        for result in results:
            metadata = result.get("metadata", {})
            if metadata.get("type") == "git_commit":
                events.append(
                    GitEvent(
                        commit_hash=metadata["commit_hash"],
                        timestamp=datetime.fromisoformat(metadata["timestamp"]),
                        author_name=metadata.get("author", "Unknown"),
                        message=result.get("content", ""),
                        event_type=metadata.get("event_type", "commit"),
                        semantic_tags=metadata.get("tags", []),
                        metadata=metadata,
                    )
                )

        return events

    async def get_velocity_trends(
        self,
        query: str = "velocity trends",
    ) -> list[GitVelocityMetrics]:
        results = await self.client.semantic_search(
            query=query,
            limit=10,
            filters={
                "type": "git_velocity",
            },
        )

        metrics_list = []
        for result in results:
            metadata = result.get("metadata", {})
            metrics_list.append(
                GitVelocityMetrics(
                    repository_path=metadata["repository"],
                    period_start=datetime.fromisoformat(metadata["period_start"]),
                    period_end=datetime.fromisoformat(metadata["period_end"]),
                    total_commits=metadata.get("total_commits", 0),
                    avg_commits_per_day=metadata.get("avg_commits_per_day", 0.0),
                    avg_commits_per_week=metadata.get("avg_commits_per_week", 0.0),
                    conventional_compliance_rate=metadata.get(
                        "conventional_compliance_rate", 0.0
                    ),
                    breaking_changes=metadata.get("breaking_changes", 0),
                    merge_conflict_rate=metadata.get("merge_conflict_rate", 0.0),
                    most_active_hour=metadata.get("most_active_hour", 0),
                    most_active_day=metadata.get("most_active_day", 0),
                )
            )

        return metrics_list


def create_akosha_client(
    backend: str = "auto",
    config: AkoshaClientConfig | None = None,
) -> AkoshaClientProtocol:
    config = config or AkoshaClientConfig()

    if backend == "auto":
        logger.info("Auto-detecting Akosha backend...")

        try:
            client = DirectAkoshaClient(config=config)

            asyncio.create_task(client.initialize())
            return client
        except Exception:
            logger.info("Direct backend unavailable, trying MCP...")
            client = MCPAkoshaClient(config=config)
            asyncio.create_task(client.initialize())
            return client

    if backend == "direct":
        logger.info("Using direct Akosha integration")
        client = DirectAkoshaClient(config=config)
        asyncio.create_task(client.initialize())
        return client

    if backend == "mcp":
        logger.info("Using MCP Akosha integration")
        client = MCPAkoshaClient(config=config)
        asyncio.create_task(client.initialize())
        return client

    logger.debug(f"Unknown backend '{backend}', using no-op")
    return NoOpAkoshaClient(config=config)


def create_akosha_git_integration(
    repo_path: Path,
    backend: str = "auto",
    config: AkoshaClientConfig | None = None,
) -> AkoshaGitIntegration:
    client = create_akosha_client(backend=backend, config=config)

    return AkoshaGitIntegration(
        client=client,
        repo_path=repo_path,
    )
