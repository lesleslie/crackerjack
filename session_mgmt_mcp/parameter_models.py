#!/usr/bin/env python3
"""Pydantic parameter validation models for MCP tools.

This module provides reusable parameter validation models that can be integrated
with FastMCP @mcp.tool() decorators to ensure type safety and consistent
validation across all MCP tools.

Following crackerjack patterns:
- EVERY LINE IS A LIABILITY: Focused, single-responsibility models
- DRY: Reusable validation patterns across tools
- KISS: Simple, clear validation without over-engineering
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


# Helper functions for common validation patterns
def validate_non_empty_string(v: Any, field_name: str) -> str:
    """Validate and normalize non-empty string."""
    if not isinstance(v, str):
        return v
    stripped = v.strip()
    if not stripped:
        msg = f"{field_name} cannot be empty"
        raise ValueError(msg)
    return stripped


def validate_and_expand_path(v: Any, field_name: str) -> str:
    """Validate and expand file paths."""
    if not isinstance(v, str):
        return v
    if field_name.endswith(("_path", "_directory")):
        expanded = os.path.expanduser(v.strip()) if v.strip() else v
        if (
            field_name.endswith("_directory")
            and expanded
            and not Path(expanded).is_absolute()
        ):
            # For directory fields, ensure absolute paths
            expanded = str(Path(expanded).resolve())
        return expanded
    return v


# Core parameter models for common patterns
class WorkingDirectoryParams(BaseModel):
    """Standard working directory parameter."""

    working_directory: str | None = Field(
        default=None,
        description="Optional working directory override (defaults to PWD environment variable or current directory)",
        examples=[".", "/Users/username/project", "~/Projects/my-app"],
    )

    @field_validator("working_directory")
    @classmethod
    def validate_working_directory(cls, v: str | None) -> str | None:
        """Validate working directory exists if provided."""
        if v is not None:
            v = v.strip()
            if not v:
                return None
            # Expand user paths
            expanded = os.path.expanduser(v)
            if not os.path.exists(expanded):
                msg = f"Working directory does not exist: {expanded}"
                raise ValueError(msg)
            if not Path(expanded).is_dir():
                msg = f"Working directory is not a directory: {expanded}"
                raise ValueError(msg)
            return expanded
        return v


class ProjectContextParams(BaseModel):
    """Project context parameters."""

    project: str | None = Field(
        default=None,
        description="Optional project identifier for scoped operations",
        min_length=1,
        max_length=200,
        examples=["my-app", "session-mgmt-mcp", "microservice-auth"],
    )

    @field_validator("project")
    @classmethod
    def validate_project(cls, v: str | None) -> str | None:
        """Validate project identifier."""
        if v is not None:
            v = v.strip()
            if not v:
                return None
        return v


class SearchLimitParams(BaseModel):
    """Standard search and pagination parameters."""

    limit: int = Field(
        default=10, ge=1, le=1000, description="Maximum number of results to return"
    )

    offset: int = Field(
        default=0, ge=0, description="Number of results to skip for pagination"
    )


class TimeRangeParams(BaseModel):
    """Time range parameters for filtering."""

    days: int = Field(
        default=7,
        ge=1,
        le=3650,  # 10 years max
        description="Number of days to look back",
    )


class ScoreThresholdParams(BaseModel):
    """Score threshold parameters for relevance filtering."""

    min_score: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Minimum relevance score threshold (0.0-1.0)",
    )


class TagParams(BaseModel):
    """Tag parameter validation."""

    tags: list[str] | None = Field(
        default=None,
        description="Optional list of tags for categorization",
        examples=[["python", "async"], ["bug", "critical"], ["feature", "ui"]],
    )

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v: list[str] | None) -> list[str] | None:
        """Validate tag format and content."""
        if v is None:
            return None

        if not isinstance(v, list):
            msg = "Tags must be a list of strings"
            raise TypeError(msg)

        validated_tags = []
        for tag in v:
            if not isinstance(tag, str):
                msg = "Each tag must be a string"
                raise TypeError(msg)

            tag = tag.strip().lower()
            if not tag:
                continue  # Skip empty tags

            if len(tag) > 50:
                msg = f"Tag too long (max 50 chars): {tag}"
                raise ValueError(msg)

            # Basic tag format validation
            if not tag.replace("-", "").replace("_", "").isalnum():
                msg = f"Tags must contain only letters, numbers, hyphens, and underscores: {tag}"
                raise ValueError(msg)

            validated_tags.append(tag)

        return validated_tags if validated_tags else None


class IDParams(BaseModel):
    """ID parameter validation for various entity types."""

    id: str = Field(
        description="Unique identifier",
        min_length=1,
        max_length=100,
        examples=["abc123", "session_20250106", "reflection-456"],
    )

    @field_validator("id")
    @classmethod
    def validate_id_format(cls, v: str) -> str:
        """Validate ID format."""
        v = v.strip()
        if not v:
            msg = "ID cannot be empty"
            raise ValueError(msg)
        # Allow alphanumeric, hyphens, underscores, and dots
        if not v.replace("-", "").replace("_", "").replace(".", "").isalnum():
            msg = (
                "ID must contain only letters, numbers, hyphens, underscores, and dots"
            )
            raise ValueError(msg)
        return v


class FilePathParams(BaseModel):
    """File path parameter validation."""

    file_path: str = Field(
        description="Path to a file",
        min_length=1,
        examples=["README.md", "src/main.py", "/absolute/path/file.txt"],
    )

    @field_validator("file_path")
    @classmethod
    def validate_file_path(cls, v: str) -> str:
        """Validate file path format."""
        v = v.strip()
        if not v:
            msg = "File path cannot be empty"
            raise ValueError(msg)

        # Basic path validation - don't require file to exist (might not exist yet)
        if "\x00" in v:
            msg = "File path cannot contain null characters"
            raise ValueError(msg)

        return v


class CommandExecutionParams(BaseModel):
    """Command execution parameters."""

    command: str = Field(
        description="Command to execute",
        min_length=1,
        max_length=1000,
        examples=["lint", "test", "analyze"],
    )

    args: str = Field(
        default="",
        max_length=2000,
        description="Command arguments as space-separated string",
    )

    timeout: int = Field(
        default=300, ge=1, le=3600, description="Command timeout in seconds"
    )

    @field_validator("command")
    @classmethod
    def validate_command(cls, v: str) -> str:
        """Validate command string."""
        v = v.strip()
        if not v:
            msg = "Command cannot be empty"
            raise ValueError(msg)
        return v


class BooleanFlagParams(BaseModel):
    """Common boolean flag parameters."""

    force: bool = Field(
        default=False, description="Force operation, bypassing safety checks"
    )

    verbose: bool = Field(default=False, description="Enable verbose output")

    dry_run: bool = Field(
        default=False, description="Show what would be done without executing"
    )


# Specific MCP tool parameter models
class SessionInitParams(WorkingDirectoryParams):
    """Parameters for session initialization."""

    # Just uses working_directory from base


class SessionStatusParams(WorkingDirectoryParams):
    """Parameters for session status check."""

    # Just uses working_directory from base


class ReflectionStoreParams(BaseModel):
    """Parameters for storing reflections."""

    content: str = Field(
        description="Content to store as reflection",
        min_length=1,
        max_length=50000,
        examples=["Learned that async/await patterns improve database performance"],
    )

    tags: list[str] | None = Field(
        default=None, description="Optional tags for categorization"
    )

    @field_validator("content")
    @classmethod
    def validate_content(cls, v: str) -> str:
        """Validate reflection content."""
        v = v.strip()
        if not v:
            msg = "Content cannot be empty"
            raise ValueError(msg)
        return v

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v: list[str] | None) -> list[str] | None:
        """Use the TagParams validation."""
        return TagParams(tags=v).tags


class SearchQueryParams(ProjectContextParams, SearchLimitParams, ScoreThresholdParams):
    """Parameters for search operations."""

    query: str = Field(
        description="Search query text",
        min_length=1,
        max_length=1000,
        examples=["python async patterns", "database migration", "error handling"],
    )

    @field_validator("query")
    @classmethod
    def validate_query(cls, v: str) -> str:
        """Validate search query."""
        v = v.strip()
        if not v:
            msg = "Query cannot be empty"
            raise ValueError(msg)
        return v


class FileSearchParams(SearchLimitParams, ProjectContextParams):
    """Parameters for file-based search."""

    file_path: str = Field(
        description="File path to search for in conversations",
        min_length=1,
        examples=["src/main.py", "README.md", "config/database.yml"],
    )

    @field_validator("file_path")
    @classmethod
    def validate_file_path(cls, v: str) -> str:
        """Validate file path for search."""
        v = v.strip()
        if not v:
            msg = "File path cannot be empty"
            raise ValueError(msg)
        return v


class ConceptSearchParams(SearchLimitParams, ProjectContextParams):
    """Parameters for concept-based search."""

    concept: str = Field(
        description="Development concept to search for",
        min_length=1,
        max_length=200,
        examples=["authentication", "caching", "error handling", "async patterns"],
    )

    include_files: bool = Field(
        default=True, description="Include related files in search results"
    )

    @field_validator("concept")
    @classmethod
    def validate_concept(cls, v: str) -> str:
        """Validate concept query."""
        v = v.strip()
        if not v:
            msg = "Concept cannot be empty"
            raise ValueError(msg)
        return v


class CrackerjackExecutionParams(CommandExecutionParams, WorkingDirectoryParams):
    """Parameters for crackerjack command execution."""

    ai_agent_mode: bool = Field(
        default=False, description="Enable AI agent mode for autonomous fixing"
    )


class CrackerjackHistoryParams(TimeRangeParams, WorkingDirectoryParams):
    """Parameters for crackerjack execution history."""

    command_filter: str = Field(
        default="", max_length=100, description="Filter commands by name"
    )


class TeamUserParams(BaseModel):
    """Parameters for team user operations."""

    user_id: str = Field(
        description="Unique user identifier", min_length=1, max_length=100
    )

    username: str = Field(description="Display username", min_length=1, max_length=100)

    role: Literal["owner", "admin", "moderator", "contributor", "viewer"] = Field(
        default="contributor", description="User role in the team"
    )

    email: str | None = Field(default=None, description="Optional email address")

    @field_validator("user_id", "username")
    @classmethod
    def validate_required_strings(cls, v: str) -> str:
        """Validate required string fields."""
        v = v.strip()
        if not v:
            msg = "Field cannot be empty"
            raise ValueError(msg)
        return v

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str | None) -> str | None:
        """Basic email validation."""
        if v is None:
            return None

        v = v.strip()
        if not v:
            return None

        # Basic email format validation
        if len(v) > 254:  # RFC 5321 limit
            msg = "Email address too long"
            raise ValueError(msg)

        # Must contain exactly one @ symbol
        if v.count("@") != 1:
            msg = "Invalid email format"
            raise ValueError(msg)

        local, domain = v.split("@")

        # Local part cannot be empty
        if not local:
            msg = "Invalid email format"
            raise ValueError(msg)

        # Domain part must contain at least one dot and cannot be empty
        if not domain or "." not in domain:
            msg = "Invalid email format"
            raise ValueError(msg)

        # Domain cannot start or end with dot
        if domain.startswith(".") or domain.endswith("."):
            msg = "Invalid email format"
            raise ValueError(msg)

        return v


class TeamCreationParams(BaseModel):
    """Parameters for team creation."""

    team_id: str = Field(
        description="Unique team identifier", min_length=1, max_length=100
    )

    name: str = Field(description="Team display name", min_length=1, max_length=200)

    description: str = Field(
        description="Team description", min_length=1, max_length=1000
    )

    owner_id: str = Field(
        description="User ID of the team owner", min_length=1, max_length=100
    )

    @field_validator("team_id", "name", "description", "owner_id")
    @classmethod
    def validate_required_strings(cls, v: str) -> str:
        """Validate required string fields."""
        v = v.strip()
        if not v:
            msg = "Field cannot be empty"
            raise ValueError(msg)
        return v


class TeamReflectionParams(ReflectionStoreParams):
    """Parameters for team reflection operations."""

    author_id: str = Field(
        description="ID of the reflection author", min_length=1, max_length=100
    )

    team_id: str | None = Field(
        default=None,
        description="Optional team ID for team-specific reflections",
        min_length=1,
        max_length=100,
    )

    project_id: str | None = Field(
        default=None,
        description="Optional project ID for project-specific reflections",
        min_length=1,
        max_length=100,
    )

    access_level: Literal["private", "team", "public"] = Field(
        default="team", description="Access level for the reflection"
    )

    @field_validator("author_id")
    @classmethod
    def validate_author_id(cls, v: str) -> str:
        """Validate author ID."""
        v = v.strip()
        if not v:
            msg = "Author ID cannot be empty"
            raise ValueError(msg)
        return v

    @field_validator("team_id", "project_id")
    @classmethod
    def validate_optional_ids(cls, v: str | None) -> str | None:
        """Validate optional ID fields."""
        if v is not None:
            v = v.strip()
            if not v:
                return None
        return v


class TeamSearchParams(SearchQueryParams):
    """Parameters for team knowledge search."""

    user_id: str = Field(
        description="ID of the user performing the search", min_length=1, max_length=100
    )

    team_id: str | None = Field(
        default=None,
        description="Optional team ID to scope the search",
        min_length=1,
        max_length=100,
    )

    project_id: str | None = Field(
        default=None,
        description="Optional project ID to scope the search",
        min_length=1,
        max_length=100,
    )

    @field_validator("user_id")
    @classmethod
    def validate_user_id(cls, v: str) -> str:
        """Validate user ID."""
        v = v.strip()
        if not v:
            msg = "User ID cannot be empty"
            raise ValueError(msg)
        return v

    @field_validator("team_id", "project_id")
    @classmethod
    def validate_optional_ids(cls, v: str | None) -> str | None:
        """Validate optional ID fields."""
        if v is not None:
            v = v.strip()
            if not v:
                return None
        return v


# Validation helper functions
def validate_mcp_params(model_class: type[BaseModel], **params) -> dict[str, Any]:
    """Helper function to validate MCP tool parameters using a Pydantic model.

    Args:
        model_class: The Pydantic model class to use for validation
        **params: Parameter values to validate

    Returns:
        Dictionary of validated parameters

    Raises:
        ValueError: If validation fails with detailed error messages

    Example:
        @mcp.tool()
        async def search_reflections(**params) -> str:
            validated = validate_mcp_params(SearchQueryParams, **params)
            query = validated['query']
            limit = validated['limit']
            # ... rest of implementation

    """
    try:
        validated_model = model_class(**params)
        return validated_model.model_dump(exclude_none=True)
    except Exception as e:
        # Convert Pydantic validation errors to more user-friendly messages
        if hasattr(e, "errors"):
            error_messages = []
            for error in e.errors():
                field = error.get("loc", ["unknown"])[-1]
                msg = error.get("msg", "validation error")
                error_messages.append(f"{field}: {msg}")
            msg = f"Parameter validation failed: {'; '.join(error_messages)}"
            raise ValueError(msg) from e
        msg = f"Parameter validation failed: {e!s}"
        raise ValueError(msg) from e


def create_mcp_validator(model_class: type[BaseModel]):
    """Decorator factory to create MCP tool parameter validators.

    Args:
        model_class: The Pydantic model class to use for validation

    Returns:
        Decorator function that validates parameters before tool execution

    Example:
        @mcp.tool()
        @create_mcp_validator(SearchQueryParams)
        async def search_reflections(**params) -> str:
            # params are already validated here
            query = params['query']
            limit = params['limit']
            # ... implementation

    """

    def decorator(func):
        async def wrapper(**params):
            validated_params = validate_mcp_params(model_class, **params)
            return await func(**validated_params)

        # Preserve function metadata
        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__
        wrapper.__annotations__ = func.__annotations__

        return wrapper

    return decorator
