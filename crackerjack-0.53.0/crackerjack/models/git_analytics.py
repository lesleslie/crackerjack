from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal


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
    repository: str
    tags: list[str] = field(default_factory=list)

    def to_searchable_text(self) -> str:
        parts = [
            f"commit: {self.message}",
            f"by {self.author_name}",
            f"branch: {self.branch}",
        ]

        if self.is_conventional and self.conventional_type:
            parts.append(f"type: {self.conventional_type}")

        if self.conventional_scope:
            parts.append(f"scope: {self.conventional_scope}")

        if self.has_breaking_change:
            parts.append("breaking change")

        if self.is_merge:
            parts.append("merge commit")

        if self.files_changed:
            parts.append(f"files: {', '.join(self.files_changed[:5])}")
            if len(self.files_changed) > 5:
                parts.append(f"and {len(self.files_changed) - 5} more files")

        if self.tags:
            parts.append(f"tags: {', '.join(self.tags)}")

        return ". ".join(parts)

    def to_metadata(self) -> dict[str, Any]:
        return {
            "type": "git_commit",
            "repository": self.repository,
            "commit_hash": self.commit_hash,
            "author_name": self.author_name,
            "author_email": self.author_email,
            "timestamp": self.timestamp.isoformat(),
            "branch": self.branch,
            "is_conventional": self.is_conventional,
            "conventional_type": self.conventional_type,
            "conventional_scope": self.conventional_scope,
            "has_breaking_change": self.has_breaking_change,
            "is_merge": self.is_merge,
            "files_changed": self.files_changed,
            "insertions": self.insertions,
            "deletions": self.deletions,
            "tags": self.tags,
        }


@dataclass(frozen=True)
class GitBranchEvent:
    event_type: Literal["created", "deleted", "merged", "rebased"]
    branch_name: str
    timestamp: datetime
    author_name: str
    commit_hash: str
    source_branch: str | None
    repository: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_searchable_text(self) -> str:
        parts = [
            f"{self.event_type} branch: {self.branch_name}",
            f"by {self.author_name}",
        ]

        if self.source_branch:
            parts.append(f"from {self.source_branch}")

        if self.metadata:
            if "pull_request" in self.metadata:
                parts.append(f"PR: {self.metadata['pull_request']}")
            if "reason" in self.metadata:
                parts.append(f"reason: {self.metadata['reason']}")

        return ". ".join(parts)

    def to_metadata(self) -> dict[str, Any]:
        return {
            "type": "git_branch_event",
            "repository": self.repository,
            "event_type": self.event_type,
            "branch_name": self.branch_name,
            "timestamp": self.timestamp.isoformat(),
            "author_name": self.author_name,
            "commit_hash": self.commit_hash,
            "source_branch": self.source_branch,
            **self.metadata,
        }


@dataclass(frozen=True)
class WorkflowEvent:
    event_type: Literal[
        "ci_started",
        "ci_success",
        "ci_failure",
        "deploy_started",
        "deploy_success",
        "deploy_failure",
    ]
    workflow_name: str
    timestamp: datetime
    status: Literal["pending", "running", "success", "failure", "cancelled"]
    commit_hash: str
    branch: str
    repository: str
    duration_seconds: int | None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_searchable_text(self) -> str:
        parts = [
            f"{self.event_type}: {self.workflow_name}",
            f"status: {self.status}",
            f"branch: {self.branch}",
        ]

        if self.duration_seconds:
            minutes = self.duration_seconds // 60
            seconds = self.duration_seconds % 60
            parts.append(f"duration: {minutes}m {seconds}s")

        if self.metadata:
            if "error" in self.metadata:
                parts.append(f"error: {self.metadata['error']}")
            if "stage" in self.metadata:
                parts.append(f"stage: {self.metadata['stage']}")
            if "environment" in self.metadata:
                parts.append(f"environment: {self.metadata['environment']}")

        return ". ".join(parts)

    def to_metadata(self) -> dict[str, Any]:
        return {
            "type": "workflow_event",
            "repository": self.repository,
            "event_type": self.event_type,
            "workflow_name": self.workflow_name,
            "timestamp": self.timestamp.isoformat(),
            "status": self.status,
            "commit_hash": self.commit_hash,
            "branch": self.branch,
            "duration_seconds": self.duration_seconds,
            **self.metadata,
        }


__all__ = [
    "GitCommitData",
    "GitBranchEvent",
    "WorkflowEvent",
]
