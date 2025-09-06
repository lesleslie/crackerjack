#!/usr/bin/env python3
"""Unit tests for Pydantic parameter validation models.

Following crackerjack testing patterns:
- Comprehensive coverage of validation scenarios
- Clear test names describing expected behavior
- Property-based testing for edge cases
"""

import pytest
from pydantic import ValidationError
from session_mgmt_mcp.parameter_models import (
    CommandExecutionParams,
    ConceptSearchParams,
    CrackerjackExecutionParams,
    FileSearchParams,
    ReflectionStoreParams,
    SearchQueryParams,
    TagParams,
    TeamCreationParams,
    TeamReflectionParams,
    TeamSearchParams,
    TeamUserParams,
    WorkingDirectoryParams,
    validate_mcp_params,
)


class TestWorkingDirectoryParams:
    """Test working directory parameter validation."""

    def test_valid_working_directory(self):
        """Test valid working directory paths."""
        # Current directory
        params = WorkingDirectoryParams(working_directory=".")
        assert params.working_directory == "."

        # None value
        params = WorkingDirectoryParams(working_directory=None)
        assert params.working_directory is None

        # Existing directory (assuming current dir exists)
        import os

        current_dir = os.getcwd()
        params = WorkingDirectoryParams(working_directory=current_dir)
        assert params.working_directory == current_dir

    def test_path_expansion(self):
        """Test home directory path expansion."""
        params = WorkingDirectoryParams(working_directory="~/")
        # Should expand tilde to home directory
        import os

        expected = os.path.expanduser("~/")
        assert params.working_directory == expected

    def test_empty_string_becomes_none(self):
        """Test empty string working directory becomes None."""
        params = WorkingDirectoryParams(working_directory="")
        assert params.working_directory is None

        params = WorkingDirectoryParams(working_directory="   ")
        assert params.working_directory is None

    def test_nonexistent_directory_error(self):
        """Test validation error for non-existent directory."""
        with pytest.raises(ValidationError) as exc_info:
            WorkingDirectoryParams(working_directory="/nonexistent/path/12345")

        assert "Working directory does not exist" in str(exc_info.value)

    def test_file_instead_of_directory_error(self):
        """Test validation error when path is a file, not directory."""
        # Create a temporary file for testing
        import tempfile

        with tempfile.NamedTemporaryFile() as tmp_file:
            with pytest.raises(ValidationError) as exc_info:
                WorkingDirectoryParams(working_directory=tmp_file.name)

            assert "Working directory is not a directory" in str(exc_info.value)


class TestTagParams:
    """Test tag parameter validation."""

    def test_valid_tags(self):
        """Test valid tag formats."""
        valid_tags = [
            ["python", "async"],
            ["bug-fix", "critical"],
            ["feature_request"],
            ["ui", "frontend", "react"],
        ]

        for tags in valid_tags:
            params = TagParams(tags=tags)
            assert params.tags == [tag.lower() for tag in tags]

    def test_none_tags(self):
        """Test None tags value."""
        params = TagParams(tags=None)
        assert params.tags is None

    def test_empty_list_becomes_none(self):
        """Test empty tag list becomes None."""
        params = TagParams(tags=[])
        assert params.tags is None

    def test_tag_normalization(self):
        """Test tag normalization (lowercase, strip)."""
        params = TagParams(tags=["  PYTHON  ", "Async-Await", "Database_ORM"])
        assert params.tags == ["python", "async-await", "database_orm"]

    def test_skip_empty_tags(self):
        """Test empty strings in tags are skipped."""
        params = TagParams(tags=["python", "", "  ", "async"])
        assert params.tags == ["python", "async"]

    def test_invalid_tag_characters(self):
        """Test validation error for invalid tag characters."""
        invalid_tags = [
            ["valid", "invalid@tag"],  # @ symbol
            ["python", "tag with spaces"],  # spaces
            ["good", "bad!tag"],  # exclamation
        ]

        for tags in invalid_tags:
            with pytest.raises(ValidationError):
                TagParams(tags=tags)

    def test_tag_too_long(self):
        """Test validation error for tags that are too long."""
        long_tag = "a" * 51  # Max is 50 characters
        with pytest.raises(ValidationError) as exc_info:
            TagParams(tags=[long_tag])

        assert "Tag too long" in str(exc_info.value)

    def test_non_string_tag_error(self):
        """Test validation error for non-string tags."""
        with pytest.raises(ValidationError):
            TagParams(tags=["valid", 123])  # Number instead of string


class TestReflectionStoreParams:
    """Test reflection storage parameter validation."""

    def test_valid_reflection(self):
        """Test valid reflection parameters."""
        params = ReflectionStoreParams(
            content="This is a valid reflection about Python async patterns.",
            tags=["python", "async"],
        )
        assert params.content.strip() == params.content
        assert params.tags == ["python", "async"]

    def test_content_length_validation(self):
        """Test content length validation."""
        # Test minimum length (should pass)
        params = ReflectionStoreParams(content="x")
        assert params.content == "x"

        # Test maximum length (should pass)
        max_content = "x" * 50000
        params = ReflectionStoreParams(content=max_content)
        assert len(params.content) == 50000

        # Test over maximum length (should fail)
        over_max_content = "x" * 50001
        with pytest.raises(ValidationError):
            ReflectionStoreParams(content=over_max_content)

    def test_empty_content_error(self):
        """Test validation error for empty content."""
        with pytest.raises(ValidationError):
            ReflectionStoreParams(content="")

        with pytest.raises(ValidationError):
            ReflectionStoreParams(content="   ")  # Whitespace only

    def test_tags_optional(self):
        """Test that tags parameter is optional."""
        params = ReflectionStoreParams(content="Valid content")
        assert params.tags is None


class TestSearchQueryParams:
    """Test search query parameter validation."""

    def test_valid_search_params(self):
        """Test valid search parameters."""
        params = SearchQueryParams(
            query="python async patterns", limit=20, project="my-project", min_score=0.8
        )
        assert params.query == "python async patterns"
        assert params.limit == 20
        assert params.project == "my-project"
        assert params.min_score == 0.8

    def test_default_values(self):
        """Test default parameter values."""
        params = SearchQueryParams(query="test")
        assert params.query == "test"
        assert params.limit == 10  # Default
        assert params.project is None  # Default
        assert params.min_score == 0.7  # Default

    def test_query_validation(self):
        """Test query string validation."""
        # Valid queries
        valid_queries = [
            "simple query",
            "query with numbers 123",
            "special-chars_allowed.here",
            "x" * 1000,  # Max length
        ]

        for query in valid_queries:
            params = SearchQueryParams(query=query)
            assert params.query == query

        # Invalid queries
        with pytest.raises(ValidationError):
            SearchQueryParams(query="")  # Empty

        with pytest.raises(ValidationError):
            SearchQueryParams(query="   ")  # Whitespace only

        with pytest.raises(ValidationError):
            SearchQueryParams(query="x" * 1001)  # Over max length

    def test_limit_validation(self):
        """Test limit parameter validation."""
        # Valid limits
        params = SearchQueryParams(query="test", limit=1)
        assert params.limit == 1

        params = SearchQueryParams(query="test", limit=1000)
        assert params.limit == 1000

        # Invalid limits
        with pytest.raises(ValidationError):
            SearchQueryParams(query="test", limit=0)  # Below minimum

        with pytest.raises(ValidationError):
            SearchQueryParams(query="test", limit=1001)  # Above maximum

    def test_min_score_validation(self):
        """Test min_score parameter validation."""
        # Valid scores
        params = SearchQueryParams(query="test", min_score=0.0)
        assert params.min_score == 0.0

        params = SearchQueryParams(query="test", min_score=1.0)
        assert params.min_score == 1.0

        # Invalid scores
        with pytest.raises(ValidationError):
            SearchQueryParams(query="test", min_score=-0.1)  # Below minimum

        with pytest.raises(ValidationError):
            SearchQueryParams(query="test", min_score=1.1)  # Above maximum


class TestTeamUserParams:
    """Test team user parameter validation."""

    def test_valid_team_user(self):
        """Test valid team user parameters."""
        params = TeamUserParams(
            user_id="user123",
            username="john_doe",
            role="contributor",
            email="john@example.com",
        )
        assert params.user_id == "user123"
        assert params.username == "john_doe"
        assert params.role == "contributor"
        assert params.email == "john@example.com"

    def test_default_role(self):
        """Test default role assignment."""
        params = TeamUserParams(user_id="user123", username="john")
        assert params.role == "contributor"

    def test_valid_roles(self):
        """Test all valid role values."""
        valid_roles = ["owner", "admin", "moderator", "contributor", "viewer"]

        for role in valid_roles:
            params = TeamUserParams(user_id="user123", username="john", role=role)
            assert params.role == role

    def test_invalid_role(self):
        """Test validation error for invalid role."""
        with pytest.raises(ValidationError):
            TeamUserParams(user_id="user123", username="john", role="invalid_role")

    def test_email_validation(self):
        """Test email validation."""
        # Valid emails
        valid_emails = [
            "user@example.com",
            "test.user+tag@domain.co.uk",
            "simple@test.io",
        ]

        for email in valid_emails:
            params = TeamUserParams(user_id="user123", username="john", email=email)
            assert params.email == email

        # None email (optional)
        params = TeamUserParams(user_id="user123", username="john", email=None)
        assert params.email is None

        # Empty email becomes None
        params = TeamUserParams(user_id="user123", username="john", email="")
        assert params.email is None

        # Invalid emails
        invalid_emails = [
            "notanemail",
            "@example.com",
            "user@",
            "user@.com",
            "x" * 255 + "@example.com",  # Too long
        ]

        for email in invalid_emails:
            try:
                params = TeamUserParams(user_id="user123", username="john", email=email)
                # If we get here, validation didn't fail as expected
                pytest.fail(
                    f"Expected validation error for email '{email}' but got: {params.email}"
                )
            except ValidationError:
                # This is expected
                pass


class TestValidateMcpParams:
    """Test the validate_mcp_params helper function."""

    def test_successful_validation(self):
        """Test successful parameter validation."""
        params = {"query": "test query", "limit": 5, "min_score": 0.8}

        validated = validate_mcp_params(SearchQueryParams, **params)

        assert validated["query"] == "test query"
        assert validated["limit"] == 5
        assert validated["min_score"] == 0.8

    def test_validation_error_handling(self):
        """Test validation error handling with helpful messages."""
        params = {
            "query": "",  # Invalid: empty
            "limit": 0,  # Invalid: below minimum
            "min_score": 1.5,  # Invalid: above maximum
        }

        with pytest.raises(ValueError, match="Parameter validation failed") as exc_info:
            validate_mcp_params(SearchQueryParams, **params)

        error_message = str(exc_info.value)
        assert "Parameter validation failed" in error_message
        # Should contain details about multiple validation errors

    def test_exclude_none_values(self):
        """Test that None values are excluded from results."""
        params = {"query": "test", "project": None}

        validated = validate_mcp_params(SearchQueryParams, **params)

        assert "query" in validated
        assert "project" not in validated  # None values excluded


class TestCommandExecutionParams:
    """Test command execution parameter validation."""

    def test_valid_command_params(self):
        """Test valid command execution parameters."""
        params = CommandExecutionParams(
            command="lint", args="--fix --verbose", timeout=600
        )
        assert params.command == "lint"
        assert params.args == "--fix --verbose"
        assert params.timeout == 600

    def test_default_values(self):
        """Test default parameter values."""
        params = CommandExecutionParams(command="test")
        assert params.command == "test"
        assert params.args == ""  # Default
        assert params.timeout == 300  # Default

    def test_timeout_validation(self):
        """Test timeout parameter validation."""
        # Valid timeouts
        params = CommandExecutionParams(command="test", timeout=1)
        assert params.timeout == 1

        params = CommandExecutionParams(command="test", timeout=3600)
        assert params.timeout == 3600

        # Invalid timeouts
        with pytest.raises(ValidationError):
            CommandExecutionParams(command="test", timeout=0)  # Below minimum

        with pytest.raises(ValidationError):
            CommandExecutionParams(command="test", timeout=3601)  # Above maximum


class TestCrackerjackExecutionParams:
    """Test crackerjack-specific execution parameters."""

    def test_inherits_command_params(self):
        """Test that crackerjack params inherit from command params."""
        params = CrackerjackExecutionParams(
            command="lint",
            args="--fix",
            timeout=600,
            working_directory=".",
            ai_agent_mode=True,
        )

        # Command execution fields
        assert params.command == "lint"
        assert params.args == "--fix"
        assert params.timeout == 600

        # Working directory field
        assert params.working_directory == "."

        # Crackerjack-specific field
        assert params.ai_agent_mode is True

    def test_default_ai_agent_mode(self):
        """Test default AI agent mode."""
        params = CrackerjackExecutionParams(command="test")
        assert params.ai_agent_mode is False


# Integration tests
class TestParameterModelIntegration:
    """Test parameter models working together in realistic scenarios."""

    def test_team_reflection_workflow(self):
        """Test a complete team reflection workflow with validation."""
        # Create team user
        user_params = TeamUserParams(
            user_id="dev001",
            username="alice_developer",
            role="contributor",
            email="alice@company.com",
        )

        # Create team
        team_params = TeamCreationParams(
            team_id="team_backend",
            name="Backend Development Team",
            description="Team focused on backend services and APIs",
            owner_id="dev001",
        )

        # Add team reflection
        reflection_params = TeamReflectionParams(
            content="Discovered that connection pooling significantly improves database performance under high load",
            author_id="dev001",
            team_id="team_backend",
            project_id="user_service",
            tags=["database", "performance", "connection-pooling"],
            access_level="team",
        )

        # Search team knowledge
        search_params = TeamSearchParams(
            query="database performance",
            user_id="dev001",
            team_id="team_backend",
            project_id="user_service",
            limit=10,
            min_score=0.7,
        )

        # All validations should pass
        assert user_params.user_id == "dev001"
        assert team_params.team_id == "team_backend"
        assert reflection_params.content is not None
        assert search_params.query == "database performance"

    def test_search_workflow_validation(self):
        """Test search workflow with different parameter models."""
        # Basic search
        basic_search = SearchQueryParams(
            query="python async patterns", limit=20, min_score=0.8
        )

        # File search
        file_search = FileSearchParams(
            file_path="src/async_utils.py", limit=15, project="backend_service"
        )

        # Concept search
        concept_search = ConceptSearchParams(
            concept="connection pooling",
            include_files=True,
            limit=25,
            project="backend_service",
        )

        # All should validate successfully
        assert basic_search.query == "python async patterns"
        assert file_search.file_path == "src/async_utils.py"
        assert concept_search.concept == "connection pooling"

    def test_validation_consistency(self):
        """Test that validation is consistent across similar parameters."""
        # All these should have consistent limit validation
        search_params = SearchQueryParams(query="test", limit=50)
        file_params = FileSearchParams(file_path="test.py", limit=50)
        concept_params = ConceptSearchParams(concept="testing", limit=50)

        assert search_params.limit == 50
        assert file_params.limit == 50
        assert concept_params.limit == 50

        # All should fail with same limit validation
        with pytest.raises(ValidationError):
            SearchQueryParams(query="test", limit=0)
        with pytest.raises(ValidationError):
            FileSearchParams(file_path="test.py", limit=0)
        with pytest.raises(ValidationError):
            ConceptSearchParams(concept="testing", limit=0)


if __name__ == "__main__":
    pytest.main([__file__])
