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


class TestGitBranchEventSearchableTextPartialBranches:
    """Tests covering false branches in GitBranchEvent.to_searchable_text metadata keys."""

    def test_searchable_text_metadata_without_pull_request(self) -> None:
        """Verify to_searchable_text when metadata lacks 'pull_request' key."""
        timestamp = datetime(2026, 5, 16, 10, 30, 0)
        event = GitBranchEvent(
            event_type="rebased",
            branch_name="feature/x",
            timestamp=timestamp,
            author_name="Jane Doe",
            commit_hash="abc123",
            source_branch="main",
            repository="my-repo",
            metadata={"reason": "rebased onto main"},
        )
        text = event.to_searchable_text()
        assert "PR:" not in text
        assert "reason: rebased onto main" in text

    def test_searchable_text_metadata_without_reason(self) -> None:
        """Verify to_searchable_text when metadata lacks 'reason' key."""
        timestamp = datetime(2026, 5, 16, 10, 30, 0)
        event = GitBranchEvent(
            event_type="merged",
            branch_name="feature/y",
            timestamp=timestamp,
            author_name="Jane Doe",
            commit_hash="abc123",
            source_branch="develop",
            repository="my-repo",
            metadata={"pull_request": "#42"},
        )
        text = event.to_searchable_text()
        assert "PR: #42" in text
        assert "reason:" not in text

    def test_searchable_text_metadata_with_unrelated_keys(self) -> None:
        """Verify to_searchable_text when metadata has no recognized keys."""
        timestamp = datetime(2026, 5, 16, 10, 30, 0)
        event = GitBranchEvent(
            event_type="deleted",
            branch_name="stale/branch",
            timestamp=timestamp,
            author_name="Jane Doe",
            commit_hash="abc123",
            source_branch=None,
            repository="my-repo",
            metadata={"ci_run": "ci-789", "deploy_target": "prod"},
        )
        text = event.to_searchable_text()
        assert "PR:" not in text
        assert "reason:" not in text
        assert "deleted branch: stale/branch" in text
        assert "by Jane Doe" in text


class TestWorkflowEventSearchableTextPartialBranches:
    """Tests covering false branches in WorkflowEvent.to_searchable_text metadata keys."""

    def test_searchable_text_metadata_without_error(self) -> None:
        """Verify to_searchable_text when metadata lacks 'error' key."""
        timestamp = datetime(2026, 5, 16, 10, 30, 0)
        event = WorkflowEvent(
            event_type="ci_success",
            workflow_name="test-suite",
            timestamp=timestamp,
            status="success",
            commit_hash="abc123",
            branch="main",
            repository="my-repo",
            duration_seconds=60,
            metadata={"stage": "build", "environment": "ci"},
        )
        text = event.to_searchable_text()
        assert "error:" not in text
        assert "stage: build" in text
        assert "environment: ci" in text

    def test_searchable_text_metadata_without_stage(self) -> None:
        """Verify to_searchable_text when metadata lacks 'stage' key."""
        timestamp = datetime(2026, 5, 16, 10, 30, 0)
        event = WorkflowEvent(
            event_type="deploy_success",
            workflow_name="deploy-prod",
            timestamp=timestamp,
            status="success",
            commit_hash="abc123",
            branch="main",
            repository="my-repo",
            duration_seconds=180,
            metadata={"error": "none", "environment": "production"},
        )
        text = event.to_searchable_text()
        assert "error: none" in text
        assert "stage:" not in text
        assert "environment: production" in text

    def test_searchable_text_metadata_without_environment(self) -> None:
        """Verify to_searchable_text when metadata lacks 'environment' key."""
        timestamp = datetime(2026, 5, 16, 10, 30, 0)
        event = WorkflowEvent(
            event_type="ci_failure",
            workflow_name="lint",
            timestamp=timestamp,
            status="failure",
            commit_hash="abc123",
            branch="develop",
            repository="my-repo",
            duration_seconds=45,
            metadata={"error": "syntax error", "stage": "lint"},
        )
        text = event.to_searchable_text()
        assert "error: syntax error" in text
        assert "stage: lint" in text
        assert "environment:" not in text

    def test_searchable_text_metadata_with_only_error(self) -> None:
        """Verify to_searchable_text when metadata has only 'error' key."""
        timestamp = datetime(2026, 5, 16, 10, 30, 0)
        event = WorkflowEvent(
            event_type="ci_failure",
            workflow_name="test",
            timestamp=timestamp,
            status="failure",
            commit_hash="abc123",
            branch="main",
            repository="my-repo",
            duration_seconds=30,
            metadata={"error": "OOM"},
        )
        text = event.to_searchable_text()
        assert "error: OOM" in text
        assert "stage:" not in text
        assert "environment:" not in text

    def test_searchable_text_metadata_with_unrelated_keys(self) -> None:
        """Verify to_searchable_text when metadata has no recognized keys."""
        timestamp = datetime(2026, 5, 16, 10, 30, 0)
        event = WorkflowEvent(
            event_type="ci_started",
            workflow_name="test",
            timestamp=timestamp,
            status="pending",
            commit_hash="abc123",
            branch="main",
            repository="my-repo",
            duration_seconds=10,
            metadata={"runner": "linux-x64", "region": "us-west-2"},
        )
        text = event.to_searchable_text()
        assert "error:" not in text
        assert "stage:" not in text
        assert "environment:" not in text
        assert "ci_started: test" in text


class TestGitCommitDataEdgeCases:
    """Tests covering edge cases in GitCommitData."""

    def test_to_searchable_text_empty_files(self) -> None:
        """Verify to_searchable_text when files_changed is empty list."""
        timestamp = datetime(2026, 5, 16, 10, 30, 0)
        commit = GitCommitData(
            commit_hash="abc123",
            timestamp=timestamp,
            author_name="Jane Doe",
            author_email="jane@example.com",
            message="chore: empty commit",
            files_changed=[],
            insertions=0,
            deletions=0,
            is_conventional=True,
            conventional_type="chore",
            conventional_scope=None,
            has_breaking_change=False,
            is_merge=False,
            branch="main",
            repository="my-repo",
        )
        text = commit.to_searchable_text()
        assert "files:" not in text
        assert "more files" not in text

    def test_to_searchable_text_exactly_five_files(self) -> None:
        """Verify to_searchable_text when files_changed has exactly 5 files."""
        timestamp = datetime(2026, 5, 16, 10, 30, 0)
        files = [f"file{i}.py" for i in range(5)]
        commit = GitCommitData(
            commit_hash="abc123",
            timestamp=timestamp,
            author_name="Jane Doe",
            author_email="jane@example.com",
            message="refactor: clean up",
            files_changed=files,
            insertions=10,
            deletions=10,
            is_conventional=True,
            conventional_type="refactor",
            conventional_scope=None,
            has_breaking_change=False,
            is_merge=False,
            branch="main",
            repository="my-repo",
        )
        text = commit.to_searchable_text()
        assert "file0.py" in text
        assert "file4.py" in text
        assert "more files" not in text

    def test_to_searchable_text_six_files_truncates(self) -> None:
        """Verify to_searchable_text truncates when 6+ files."""
        timestamp = datetime(2026, 5, 16, 10, 30, 0)
        files = [f"file{i}.py" for i in range(6)]
        commit = GitCommitData(
            commit_hash="abc123",
            timestamp=timestamp,
            author_name="Jane Doe",
            author_email="jane@example.com",
            message="refactor: large refactor",
            files_changed=files,
            insertions=60,
            deletions=60,
            is_conventional=True,
            conventional_type="refactor",
            conventional_scope=None,
            has_breaking_change=False,
            is_merge=False,
            branch="main",
            repository="my-repo",
        )
        text = commit.to_searchable_text()
        assert "file0.py" in text
        assert "and 1 more files" in text

    def test_to_searchable_text_with_empty_tags_list(self) -> None:
        """Verify to_searchable_text when tags is an empty list."""
        timestamp = datetime(2026, 5, 16, 10, 30, 0)
        commit = GitCommitData(
            commit_hash="abc123",
            timestamp=timestamp,
            author_name="Jane Doe",
            author_email="jane@example.com",
            message="chore: no tags",
            files_changed=[],
            insertions=0,
            deletions=0,
            is_conventional=True,
            conventional_type="chore",
            conventional_scope=None,
            has_breaking_change=False,
            is_merge=False,
            branch="main",
            repository="my-repo",
            tags=[],
        )
        text = commit.to_searchable_text()
        assert "tags:" not in text

    def test_to_metadata_empty_files(self) -> None:
        """Verify to_metadata preserves empty files_changed list."""
        timestamp = datetime(2026, 5, 16, 10, 30, 0)
        commit = GitCommitData(
            commit_hash="abc123",
            timestamp=timestamp,
            author_name="Jane Doe",
            author_email="jane@example.com",
            message="empty commit",
            files_changed=[],
            insertions=0,
            deletions=0,
            is_conventional=False,
            conventional_type=None,
            conventional_scope=None,
            has_breaking_change=False,
            is_merge=False,
            branch="main",
            repository="my-repo",
        )
        metadata = commit.to_metadata()
        assert metadata["files_changed"] == []
        assert metadata["insertions"] == 0
        assert metadata["deletions"] == 0

    def test_to_metadata_preserves_unicode(self) -> None:
        """Verify to_metadata preserves unicode characters."""
        timestamp = datetime(2026, 5, 16, 10, 30, 0)
        commit = GitCommitData(
            commit_hash="abc123",
            timestamp=timestamp,
            author_name="李雷",
            author_email="lilei@example.com",
            message="feat: add 中文 support",
            files_changed=["模块.py"],
            insertions=1,
            deletions=0,
            is_conventional=True,
            conventional_type="feat",
            conventional_scope=None,
            has_breaking_change=False,
            is_merge=False,
            branch="main",
            repository="my-repo",
        )
        metadata = commit.to_metadata()
        assert metadata["author_name"] == "李雷"
        assert metadata["files_changed"] == ["模块.py"]


class TestGitBranchEventEdgeCases:
    """Tests covering edge cases in GitBranchEvent."""

    def test_to_searchable_text_empty_metadata_dict(self) -> None:
        """Verify to_searchable_text with empty metadata dict (falsy)."""
        timestamp = datetime(2026, 5, 16, 10, 30, 0)
        event = GitBranchEvent(
            event_type="created",
            branch_name="feature/z",
            timestamp=timestamp,
            author_name="Jane Doe",
            commit_hash="abc123",
            source_branch=None,
            repository="my-repo",
            metadata={},
        )
        text = event.to_searchable_text()
        assert "PR:" not in text
        assert "reason:" not in text
        assert "created branch: feature/z" in text

    def test_to_metadata_empty_metadata(self) -> None:
        """Verify to_metadata with empty metadata dict."""
        timestamp = datetime(2026, 5, 16, 10, 30, 0)
        event = GitBranchEvent(
            event_type="deleted",
            branch_name="old/branch",
            timestamp=timestamp,
            author_name="Jane Doe",
            commit_hash="abc123",
            source_branch=None,
            repository="my-repo",
            metadata={},
        )
        metadata = event.to_metadata()
        assert metadata["type"] == "git_branch_event"
        assert metadata["source_branch"] is None
        assert metadata["event_type"] == "deleted"

    def test_to_metadata_with_extra_fields(self) -> None:
        """Verify to_metadata merges multiple extra metadata fields."""
        timestamp = datetime(2026, 5, 16, 10, 30, 0)
        event = GitBranchEvent(
            event_type="merged",
            branch_name="feature/w",
            timestamp=timestamp,
            author_name="Jane Doe",
            commit_hash="abc123",
            source_branch="develop",
            repository="my-repo",
            metadata={
                "pull_request": "#99",
                "reviewer": "John",
                "approved_at": "2026-05-16T11:00:00",
            },
        )
        metadata = event.to_metadata()
        assert metadata["pull_request"] == "#99"
        assert metadata["reviewer"] == "John"
        assert metadata["approved_at"] == "2026-05-16T11:00:00"


class TestWorkflowEventEdgeCases:
    """Tests covering edge cases in WorkflowEvent."""

    def test_to_searchable_text_duration_under_one_minute(self) -> None:
        """Verify to_searchable_text with duration_seconds < 60."""
        timestamp = datetime(2026, 5, 16, 10, 30, 0)
        event = WorkflowEvent(
            event_type="ci_success",
            workflow_name="lint",
            timestamp=timestamp,
            status="success",
            commit_hash="abc123",
            branch="main",
            repository="my-repo",
            duration_seconds=42,
        )
        text = event.to_searchable_text()
        assert "duration: 0m 42s" in text

    def test_to_searchable_text_zero_duration_skipped(self) -> None:
        """Verify to_searchable_text with duration_seconds=0 is skipped."""
        timestamp = datetime(2026, 5, 16, 10, 30, 0)
        event = WorkflowEvent(
            event_type="ci_started",
            workflow_name="test",
            timestamp=timestamp,
            status="pending",
            commit_hash="abc123",
            branch="main",
            repository="my-repo",
            duration_seconds=0,
        )
        text = event.to_searchable_text()
        assert "duration:" not in text

    def test_to_searchable_text_empty_metadata_dict(self) -> None:
        """Verify to_searchable_text with empty metadata dict (falsy)."""
        timestamp = datetime(2026, 5, 16, 10, 30, 0)
        event = WorkflowEvent(
            event_type="ci_started",
            workflow_name="test",
            timestamp=timestamp,
            status="running",
            commit_hash="abc123",
            branch="main",
            repository="my-repo",
            duration_seconds=30,
            metadata={},
        )
        text = event.to_searchable_text()
        assert "error:" not in text
        assert "stage:" not in text
        assert "environment:" not in text
        assert "duration: 0m 30s" in text

    def test_to_metadata_empty_metadata(self) -> None:
        """Verify to_metadata with empty metadata dict."""
        timestamp = datetime(2026, 5, 16, 10, 30, 0)
        event = WorkflowEvent(
            event_type="ci_success",
            workflow_name="test",
            timestamp=timestamp,
            status="success",
            commit_hash="abc123",
            branch="main",
            repository="my-repo",
            duration_seconds=120,
            metadata={},
        )
        metadata = event.to_metadata()
        assert metadata["type"] == "workflow_event"
        assert metadata["duration_seconds"] == 120
        assert metadata["event_type"] == "ci_success"

    def test_to_metadata_preserves_unicode(self) -> None:
        """Verify to_metadata preserves unicode values."""
        timestamp = datetime(2026, 5, 16, 10, 30, 0)
        event = WorkflowEvent(
            event_type="deploy_failure",
            workflow_name="deploy",
            timestamp=timestamp,
            status="failure",
            commit_hash="abc123",
            branch="main",
            repository="my-repo",
            duration_seconds=60,
            metadata={"error": "失敗"},
        )
        metadata = event.to_metadata()
        assert metadata["error"] == "失敗"


class TestEqualityAndHashability:
    """Tests for equality and hashability of frozen dataclasses."""

    def test_git_commit_data_equality(self) -> None:
        """Verify two GitCommitData with same fields are equal."""
        timestamp = datetime(2026, 5, 16, 10, 30, 0)
        commit1 = GitCommitData(
            commit_hash="abc123",
            timestamp=timestamp,
            author_name="Jane",
            author_email="j@example.com",
            message="msg",
            files_changed=["a.py"],
            insertions=1,
            deletions=0,
            is_conventional=False,
            conventional_type=None,
            conventional_scope=None,
            has_breaking_change=False,
            is_merge=False,
            branch="main",
            repository="repo",
        )
        commit2 = GitCommitData(
            commit_hash="abc123",
            timestamp=timestamp,
            author_name="Jane",
            author_email="j@example.com",
            message="msg",
            files_changed=["a.py"],
            insertions=1,
            deletions=0,
            is_conventional=False,
            conventional_type=None,
            conventional_scope=None,
            has_breaking_change=False,
            is_merge=False,
            branch="main",
            repository="repo",
        )
        assert commit1 == commit2

    def test_git_branch_event_equality(self) -> None:
        """Verify two GitBranchEvent with same fields are equal."""
        timestamp = datetime(2026, 5, 16, 10, 30, 0)
        event1 = GitBranchEvent(
            event_type="created",
            branch_name="feat",
            timestamp=timestamp,
            author_name="Jane",
            commit_hash="abc",
            source_branch=None,
            repository="repo",
        )
        event2 = GitBranchEvent(
            event_type="created",
            branch_name="feat",
            timestamp=timestamp,
            author_name="Jane",
            commit_hash="abc",
            source_branch=None,
            repository="repo",
        )
        assert event1 == event2

    def test_workflow_event_equality(self) -> None:
        """Verify two WorkflowEvent with same fields are equal."""
        timestamp = datetime(2026, 5, 16, 10, 30, 0)
        event1 = WorkflowEvent(
            event_type="ci_started",
            workflow_name="test",
            timestamp=timestamp,
            status="running",
            commit_hash="abc",
            branch="main",
            repository="repo",
            duration_seconds=None,
        )
        event2 = WorkflowEvent(
            event_type="ci_started",
            workflow_name="test",
            timestamp=timestamp,
            status="running",
            commit_hash="abc",
            branch="main",
            repository="repo",
            duration_seconds=None,
        )
        assert event1 == event2

    def test_git_commit_data_inequality(self) -> None:
        """Verify GitCommitData with different fields are not equal."""
        timestamp = datetime(2026, 5, 16, 10, 30, 0)
        commit1 = GitCommitData(
            commit_hash="abc123",
            timestamp=timestamp,
            author_name="Jane",
            author_email="j@example.com",
            message="msg",
            files_changed=["a.py"],
            insertions=1,
            deletions=0,
            is_conventional=False,
            conventional_type=None,
            conventional_scope=None,
            has_breaking_change=False,
            is_merge=False,
            branch="main",
            repository="repo",
        )
        commit2 = GitCommitData(
            commit_hash="abc123",
            timestamp=timestamp,
            author_name="Jane",
            author_email="j@example.com",
            message="msg",
            files_changed=["a.py"],
            insertions=1,
            deletions=0,
            is_conventional=False,
            conventional_type=None,
            conventional_scope=None,
            has_breaking_change=False,
            is_merge=False,
            branch="main",
            repository="repo2",
        )
        assert commit1 != commit2
