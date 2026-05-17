"""Tests for git_analytics module."""

from __future__ import annotations

from datetime import datetime

import pytest

from crackerjack.models.git_analytics import (
    GitBranchEvent,
    GitCommitData,
    WorkflowEvent,
)


class TestGitCommitData:
    """Tests for GitCommitData frozen dataclass."""

    def test_minimal_git_commit_data(self) -> None:
        """Verify minimal GitCommitData creation."""
        timestamp = datetime(2026, 5, 16, 10, 30, 0)
        commit = GitCommitData(
            commit_hash="abc123",
            timestamp=timestamp,
            author_name="John Doe",
            author_email="john@example.com",
            message="feat: add new feature",
            files_changed=["file1.py", "file2.py"],
            insertions=50,
            deletions=10,
            is_conventional=True,
            conventional_type="feat",
            conventional_scope=None,
            has_breaking_change=False,
            is_merge=False,
            branch="main",
            repository="my-repo",
        )
        assert commit.commit_hash == "abc123"
        assert commit.author_name == "John Doe"
        assert commit.tags == []

    def test_git_commit_data_full(self) -> None:
        """Verify GitCommitData with all fields."""
        timestamp = datetime(2026, 5, 16, 10, 30, 0)
        tags = ["v1.0.0", "release"]
        commit = GitCommitData(
            commit_hash="def456",
            timestamp=timestamp,
            author_name="Jane Smith",
            author_email="jane@example.com",
            message="feat(api)!: breaking change in API",
            files_changed=["api.py", "tests.py"],
            insertions=100,
            deletions=50,
            is_conventional=True,
            conventional_type="feat",
            conventional_scope="api",
            has_breaking_change=True,
            is_merge=False,
            branch="develop",
            repository="api-service",
            tags=tags,
        )
        assert commit.commit_hash == "def456"
        assert commit.conventional_scope == "api"
        assert commit.has_breaking_change is True
        assert commit.tags == tags

    def test_git_commit_data_frozen(self) -> None:
        """Verify GitCommitData is frozen (immutable)."""
        timestamp = datetime(2026, 5, 16, 10, 30, 0)
        commit = GitCommitData(
            commit_hash="abc123",
            timestamp=timestamp,
            author_name="John Doe",
            author_email="john@example.com",
            message="test",
            files_changed=[],
            insertions=0,
            deletions=0,
            is_conventional=False,
            conventional_type=None,
            conventional_scope=None,
            has_breaking_change=False,
            is_merge=False,
            branch="main",
            repository="test-repo",
        )
        with pytest.raises(AttributeError):
            commit.author_name = "Modified"  # type: ignore

    def test_git_commit_data_to_searchable_text_basic(self) -> None:
        """Verify to_searchable_text() with basic commit."""
        timestamp = datetime(2026, 5, 16, 10, 30, 0)
        commit = GitCommitData(
            commit_hash="abc123",
            timestamp=timestamp,
            author_name="John Doe",
            author_email="john@example.com",
            message="fix: resolve bug",
            files_changed=["bug.py"],
            insertions=10,
            deletions=5,
            is_conventional=False,
            conventional_type=None,
            conventional_scope=None,
            has_breaking_change=False,
            is_merge=False,
            branch="main",
            repository="my-repo",
        )
        text = commit.to_searchable_text()
        assert "commit: fix: resolve bug" in text
        assert "by John Doe" in text
        assert "branch: main" in text

    def test_git_commit_data_to_searchable_text_conventional(self) -> None:
        """Verify to_searchable_text() includes conventional commit info."""
        timestamp = datetime(2026, 5, 16, 10, 30, 0)
        commit = GitCommitData(
            commit_hash="abc123",
            timestamp=timestamp,
            author_name="John Doe",
            author_email="john@example.com",
            message="feat(auth): add JWT support",
            files_changed=["auth.py"],
            insertions=50,
            deletions=0,
            is_conventional=True,
            conventional_type="feat",
            conventional_scope="auth",
            has_breaking_change=False,
            is_merge=False,
            branch="develop",
            repository="my-repo",
        )
        text = commit.to_searchable_text()
        assert "type: feat" in text
        assert "scope: auth" in text

    def test_git_commit_data_to_searchable_text_breaking_change(self) -> None:
        """Verify to_searchable_text() includes breaking change indicator."""
        timestamp = datetime(2026, 5, 16, 10, 30, 0)
        commit = GitCommitData(
            commit_hash="abc123",
            timestamp=timestamp,
            author_name="John Doe",
            author_email="john@example.com",
            message="feat!: breaking API change",
            files_changed=["api.py"],
            insertions=100,
            deletions=50,
            is_conventional=True,
            conventional_type="feat",
            conventional_scope=None,
            has_breaking_change=True,
            is_merge=False,
            branch="develop",
            repository="my-repo",
        )
        text = commit.to_searchable_text()
        assert "breaking change" in text

    def test_git_commit_data_to_searchable_text_merge(self) -> None:
        """Verify to_searchable_text() indicates merge commits."""
        timestamp = datetime(2026, 5, 16, 10, 30, 0)
        commit = GitCommitData(
            commit_hash="abc123",
            timestamp=timestamp,
            author_name="John Doe",
            author_email="john@example.com",
            message="Merge pull request #123",
            files_changed=["file1.py", "file2.py"],
            insertions=100,
            deletions=50,
            is_conventional=False,
            conventional_type=None,
            conventional_scope=None,
            has_breaking_change=False,
            is_merge=True,
            branch="main",
            repository="my-repo",
        )
        text = commit.to_searchable_text()
        assert "merge commit" in text

    def test_git_commit_data_to_searchable_text_many_files(self) -> None:
        """Verify to_searchable_text() truncates file list."""
        timestamp = datetime(2026, 5, 16, 10, 30, 0)
        files = [f"file{i}.py" for i in range(10)]
        commit = GitCommitData(
            commit_hash="abc123",
            timestamp=timestamp,
            author_name="John Doe",
            author_email="john@example.com",
            message="refactor: update all files",
            files_changed=files,
            insertions=500,
            deletions=500,
            is_conventional=True,
            conventional_type="refactor",
            conventional_scope=None,
            has_breaking_change=False,
            is_merge=False,
            branch="develop",
            repository="my-repo",
        )
        text = commit.to_searchable_text()
        assert "file0.py" in text
        assert "and 5 more files" in text

    def test_git_commit_data_to_searchable_text_with_tags(self) -> None:
        """Verify to_searchable_text() includes tags."""
        timestamp = datetime(2026, 5, 16, 10, 30, 0)
        commit = GitCommitData(
            commit_hash="abc123",
            timestamp=timestamp,
            author_name="John Doe",
            author_email="john@example.com",
            message="release: version 1.0.0",
            files_changed=[],
            insertions=0,
            deletions=0,
            is_conventional=True,
            conventional_type="release",
            conventional_scope=None,
            has_breaking_change=False,
            is_merge=False,
            branch="main",
            repository="my-repo",
            tags=["v1.0.0", "stable"],
        )
        text = commit.to_searchable_text()
        assert "tags: v1.0.0, stable" in text

    def test_git_commit_data_to_metadata(self) -> None:
        """Verify to_metadata() serialization."""
        timestamp = datetime(2026, 5, 16, 10, 30, 0)
        commit = GitCommitData(
            commit_hash="abc123",
            timestamp=timestamp,
            author_name="John Doe",
            author_email="john@example.com",
            message="feat: add feature",
            files_changed=["file.py"],
            insertions=50,
            deletions=10,
            is_conventional=True,
            conventional_type="feat",
            conventional_scope="core",
            has_breaking_change=False,
            is_merge=False,
            branch="main",
            repository="my-repo",
        )
        metadata = commit.to_metadata()
        assert metadata["type"] == "git_commit"
        assert metadata["commit_hash"] == "abc123"
        assert metadata["author_name"] == "John Doe"
        assert metadata["repository"] == "my-repo"
        assert metadata["timestamp"] == "2026-05-16T10:30:00"
        assert metadata["is_conventional"] is True
        assert metadata["conventional_type"] == "feat"

    def test_git_commit_data_to_metadata_with_tags(self) -> None:
        """Verify to_metadata() includes tags."""
        timestamp = datetime(2026, 5, 16, 10, 30, 0)
        commit = GitCommitData(
            commit_hash="abc123",
            timestamp=timestamp,
            author_name="John Doe",
            author_email="john@example.com",
            message="test",
            files_changed=[],
            insertions=0,
            deletions=0,
            is_conventional=False,
            conventional_type=None,
            conventional_scope=None,
            has_breaking_change=False,
            is_merge=False,
            branch="main",
            repository="test-repo",
            tags=["v1.0", "release"],
        )
        metadata = commit.to_metadata()
        assert metadata["tags"] == ["v1.0", "release"]


class TestGitBranchEvent:
    """Tests for GitBranchEvent frozen dataclass."""

    def test_minimal_git_branch_event(self) -> None:
        """Verify minimal GitBranchEvent creation."""
        timestamp = datetime(2026, 5, 16, 10, 30, 0)
        event = GitBranchEvent(
            event_type="created",
            branch_name="feature/new",
            timestamp=timestamp,
            author_name="Jane Doe",
            commit_hash="xyz789",
            source_branch=None,
            repository="my-repo",
        )
        assert event.event_type == "created"
        assert event.branch_name == "feature/new"
        assert event.metadata == {}

    def test_git_branch_event_full(self) -> None:
        """Verify GitBranchEvent with all fields."""
        timestamp = datetime(2026, 5, 16, 10, 30, 0)
        metadata = {"pull_request": "#456", "reason": "feature implementation"}
        event = GitBranchEvent(
            event_type="merged",
            branch_name="feature/new",
            timestamp=timestamp,
            author_name="Jane Doe",
            commit_hash="xyz789",
            source_branch="develop",
            repository="my-repo",
            metadata=metadata,
        )
        assert event.event_type == "merged"
        assert event.source_branch == "develop"
        assert event.metadata == metadata

    def test_git_branch_event_frozen(self) -> None:
        """Verify GitBranchEvent is frozen."""
        timestamp = datetime(2026, 5, 16, 10, 30, 0)
        event = GitBranchEvent(
            event_type="created",
            branch_name="test",
            timestamp=timestamp,
            author_name="John",
            commit_hash="abc123",
            source_branch=None,
            repository="test-repo",
        )
        with pytest.raises(AttributeError):
            event.branch_name = "modified"  # type: ignore

    def test_git_branch_event_all_event_types(self) -> None:
        """Verify GitBranchEvent with all event_type values."""
        timestamp = datetime(2026, 5, 16, 10, 30, 0)
        event_types = ["created", "deleted", "merged", "rebased"]
        for event_type in event_types:
            event = GitBranchEvent(
                event_type=event_type,  # type: ignore
                branch_name="test",
                timestamp=timestamp,
                author_name="John",
                commit_hash="abc123",
                source_branch=None,
                repository="test-repo",
            )
            assert event.event_type == event_type

    def test_git_branch_event_to_searchable_text_basic(self) -> None:
        """Verify to_searchable_text() for basic event."""
        timestamp = datetime(2026, 5, 16, 10, 30, 0)
        event = GitBranchEvent(
            event_type="created",
            branch_name="feature/auth",
            timestamp=timestamp,
            author_name="Jane Doe",
            commit_hash="xyz789",
            source_branch=None,
            repository="my-repo",
        )
        text = event.to_searchable_text()
        assert "created branch: feature/auth" in text
        assert "by Jane Doe" in text

    def test_git_branch_event_to_searchable_text_with_source(self) -> None:
        """Verify to_searchable_text() includes source branch."""
        timestamp = datetime(2026, 5, 16, 10, 30, 0)
        event = GitBranchEvent(
            event_type="merged",
            branch_name="feature/auth",
            timestamp=timestamp,
            author_name="Jane Doe",
            commit_hash="xyz789",
            source_branch="develop",
            repository="my-repo",
        )
        text = event.to_searchable_text()
        assert "from develop" in text

    def test_git_branch_event_to_searchable_text_with_metadata(self) -> None:
        """Verify to_searchable_text() includes metadata info."""
        timestamp = datetime(2026, 5, 16, 10, 30, 0)
        metadata = {"pull_request": "#123", "reason": "feature complete"}
        event = GitBranchEvent(
            event_type="merged",
            branch_name="feature/auth",
            timestamp=timestamp,
            author_name="Jane Doe",
            commit_hash="xyz789",
            source_branch="develop",
            repository="my-repo",
            metadata=metadata,
        )
        text = event.to_searchable_text()
        assert "PR: #123" in text
        assert "reason: feature complete" in text

    def test_git_branch_event_to_metadata(self) -> None:
        """Verify to_metadata() serialization."""
        timestamp = datetime(2026, 5, 16, 10, 30, 0)
        event = GitBranchEvent(
            event_type="created",
            branch_name="feature/new",
            timestamp=timestamp,
            author_name="Jane Doe",
            commit_hash="xyz789",
            source_branch="main",
            repository="my-repo",
        )
        metadata = event.to_metadata()
        assert metadata["type"] == "git_branch_event"
        assert metadata["event_type"] == "created"
        assert metadata["branch_name"] == "feature/new"
        assert metadata["author_name"] == "Jane Doe"
        assert metadata["repository"] == "my-repo"
        assert metadata["timestamp"] == "2026-05-16T10:30:00"

    def test_git_branch_event_to_metadata_merges_custom_metadata(self) -> None:
        """Verify to_metadata() includes custom metadata fields."""
        timestamp = datetime(2026, 5, 16, 10, 30, 0)
        custom_meta = {"pull_request": "#789", "reviewer": "John"}
        event = GitBranchEvent(
            event_type="merged",
            branch_name="feature/auth",
            timestamp=timestamp,
            author_name="Jane Doe",
            commit_hash="xyz789",
            source_branch="develop",
            repository="my-repo",
            metadata=custom_meta,
        )
        metadata = event.to_metadata()
        assert metadata["pull_request"] == "#789"
        assert metadata["reviewer"] == "John"


class TestWorkflowEvent:
    """Tests for WorkflowEvent frozen dataclass."""

    def test_minimal_workflow_event(self) -> None:
        """Verify minimal WorkflowEvent creation."""
        timestamp = datetime(2026, 5, 16, 10, 30, 0)
        event = WorkflowEvent(
            event_type="ci_started",
            workflow_name="test-suite",
            timestamp=timestamp,
            status="running",
            commit_hash="abc123",
            branch="main",
            repository="my-repo",
            duration_seconds=None,
        )
        assert event.event_type == "ci_started"
        assert event.workflow_name == "test-suite"
        assert event.duration_seconds is None
        assert event.metadata == {}

    def test_workflow_event_full(self) -> None:
        """Verify WorkflowEvent with all fields."""
        timestamp = datetime(2026, 5, 16, 10, 30, 0)
        metadata = {"stage": "integration", "environment": "staging"}
        event = WorkflowEvent(
            event_type="deploy_success",
            workflow_name="deploy-to-staging",
            timestamp=timestamp,
            status="success",
            commit_hash="abc123",
            branch="develop",
            repository="my-repo",
            duration_seconds=300,
            metadata=metadata,
        )
        assert event.duration_seconds == 300
        assert event.status == "success"
        assert event.metadata == metadata

    def test_workflow_event_frozen(self) -> None:
        """Verify WorkflowEvent is frozen."""
        timestamp = datetime(2026, 5, 16, 10, 30, 0)
        event = WorkflowEvent(
            event_type="ci_started",
            workflow_name="test",
            timestamp=timestamp,
            status="running",
            commit_hash="abc123",
            branch="main",
            repository="test-repo",
            duration_seconds=None,
        )
        with pytest.raises(AttributeError):
            event.workflow_name = "modified"  # type: ignore

    def test_workflow_event_all_event_types(self) -> None:
        """Verify WorkflowEvent with all event_type values."""
        timestamp = datetime(2026, 5, 16, 10, 30, 0)
        event_types = [
            "ci_started",
            "ci_success",
            "ci_failure",
            "deploy_started",
            "deploy_success",
            "deploy_failure",
        ]
        for event_type in event_types:
            event = WorkflowEvent(
                event_type=event_type,  # type: ignore
                workflow_name="test",
                timestamp=timestamp,
                status="success",
                commit_hash="abc123",
                branch="main",
                repository="test-repo",
                duration_seconds=None,
            )
            assert event.event_type == event_type

    def test_workflow_event_all_status_values(self) -> None:
        """Verify WorkflowEvent with all status values."""
        timestamp = datetime(2026, 5, 16, 10, 30, 0)
        statuses = ["pending", "running", "success", "failure", "cancelled"]
        for status in statuses:
            event = WorkflowEvent(
                event_type="ci_started",
                workflow_name="test",
                timestamp=timestamp,
                status=status,  # type: ignore
                commit_hash="abc123",
                branch="main",
                repository="test-repo",
                duration_seconds=None,
            )
            assert event.status == status

    def test_workflow_event_to_searchable_text_basic(self) -> None:
        """Verify to_searchable_text() for basic workflow."""
        timestamp = datetime(2026, 5, 16, 10, 30, 0)
        event = WorkflowEvent(
            event_type="ci_started",
            workflow_name="test-suite",
            timestamp=timestamp,
            status="running",
            commit_hash="abc123",
            branch="main",
            repository="my-repo",
            duration_seconds=None,
        )
        text = event.to_searchable_text()
        assert "ci_started: test-suite" in text
        assert "status: running" in text
        assert "branch: main" in text

    def test_workflow_event_to_searchable_text_with_duration(self) -> None:
        """Verify to_searchable_text() formats duration."""
        timestamp = datetime(2026, 5, 16, 10, 30, 0)
        event = WorkflowEvent(
            event_type="ci_success",
            workflow_name="test-suite",
            timestamp=timestamp,
            status="success",
            commit_hash="abc123",
            branch="main",
            repository="my-repo",
            duration_seconds=125,
        )
        text = event.to_searchable_text()
        assert "duration: 2m 5s" in text

    def test_workflow_event_to_searchable_text_duration_minutes_only(self) -> None:
        """Verify to_searchable_text() with duration in full minutes."""
        timestamp = datetime(2026, 5, 16, 10, 30, 0)
        event = WorkflowEvent(
            event_type="deploy_success",
            workflow_name="deploy",
            timestamp=timestamp,
            status="success",
            commit_hash="abc123",
            branch="main",
            repository="my-repo",
            duration_seconds=600,
        )
        text = event.to_searchable_text()
        assert "duration: 10m 0s" in text

    def test_workflow_event_to_searchable_text_with_metadata(self) -> None:
        """Verify to_searchable_text() includes metadata."""
        timestamp = datetime(2026, 5, 16, 10, 30, 0)
        metadata = {
            "error": "timeout",
            "stage": "integration",
            "environment": "staging",
        }
        event = WorkflowEvent(
            event_type="ci_failure",
            workflow_name="test-suite",
            timestamp=timestamp,
            status="failure",
            commit_hash="abc123",
            branch="develop",
            repository="my-repo",
            duration_seconds=120,
            metadata=metadata,
        )
        text = event.to_searchable_text()
        assert "error: timeout" in text
        assert "stage: integration" in text
        assert "environment: staging" in text

    def test_workflow_event_to_metadata(self) -> None:
        """Verify to_metadata() serialization."""
        timestamp = datetime(2026, 5, 16, 10, 30, 0)
        event = WorkflowEvent(
            event_type="ci_success",
            workflow_name="test-suite",
            timestamp=timestamp,
            status="success",
            commit_hash="abc123",
            branch="main",
            repository="my-repo",
            duration_seconds=150,
        )
        metadata = event.to_metadata()
        assert metadata["type"] == "workflow_event"
        assert metadata["event_type"] == "ci_success"
        assert metadata["workflow_name"] == "test-suite"
        assert metadata["status"] == "success"
        assert metadata["branch"] == "main"
        assert metadata["repository"] == "my-repo"
        assert metadata["timestamp"] == "2026-05-16T10:30:00"
        assert metadata["duration_seconds"] == 150

    def test_workflow_event_to_metadata_merges_custom_metadata(self) -> None:
        """Verify to_metadata() includes custom metadata fields."""
        timestamp = datetime(2026, 5, 16, 10, 30, 0)
        custom_meta = {"error": "out of memory", "logs_url": "http://logs.example.com"}
        event = WorkflowEvent(
            event_type="deploy_failure",
            workflow_name="deploy-prod",
            timestamp=timestamp,
            status="failure",
            commit_hash="abc123",
            branch="main",
            repository="my-repo",
            duration_seconds=60,
            metadata=custom_meta,
        )
        metadata = event.to_metadata()
        assert metadata["error"] == "out of memory"
        assert metadata["logs_url"] == "http://logs.example.com"
