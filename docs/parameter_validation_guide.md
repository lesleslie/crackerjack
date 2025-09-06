# Parameter Validation Guide for Session-MGMT-MCP

This guide demonstrates how to integrate Pydantic parameter validation models with existing MCP tools for improved type safety and error handling.

## Overview

The `session_mgmt_mcp.parameter_models` module provides:

- **Reusable Pydantic models** for common parameter patterns
- **Type-safe validation** with descriptive error messages
- **Consistent constraints** across all MCP tools
- **Integration helpers** for easy adoption

## Quick Start

### 1. Basic Parameter Validation

```python
from session_mgmt_mcp.parameter_models import SearchQueryParams, validate_mcp_params


@mcp.tool()
async def search_reflections(
    query: str, limit: int = 10, project: str | None = None, min_score: float = 0.7
) -> str:
    try:
        # Validate all parameters at once
        validated = validate_mcp_params(
            SearchQueryParams,
            query=query,
            limit=limit,
            project=project,
            min_score=min_score,
        )

        # Use validated parameters (guaranteed to be valid)
        query = validated["query"]  # Non-empty, 1-1000 chars
        limit = validated["limit"]  # 1-1000 range
        project = validated.get("project")  # None or valid project name
        min_score = validated["min_score"]  # 0.0-1.0 range

        # Implementation with confidence in parameter validity...
        return f"Searching for '{query}' with limit {limit}"

    except ValueError as e:
        return f"❌ Parameter validation error: {e}"
```

### 2. Available Parameter Models

#### Core Models

- `WorkingDirectoryParams` - Standard working directory validation
- `ProjectContextParams` - Project identifier validation
- `SearchLimitParams` - Pagination and limits
- `TimeRangeParams` - Time-based filtering
- `ScoreThresholdParams` - Relevance scoring
- `TagParams` - Tag format validation
- `IDParams` - Entity identifier validation
- `FilePathParams` - File path validation

#### Composite Models

- `SearchQueryParams` - Complete search parameters
- `ReflectionStoreParams` - Reflection storage parameters
- `FileSearchParams` - File-based search parameters
- `ConceptSearchParams` - Concept search parameters
- `TeamUserParams` - Team user management
- `TeamCreationParams` - Team creation
- `CrackerjackExecutionParams` - Command execution

## Migration Examples

### Before: Manual Validation

```python
@mcp.tool()
async def store_reflection(content: str, tags: list[str] | None = None) -> str:
    # Manual validation - error-prone and inconsistent
    if not content or not content.strip():
        return "❌ Content cannot be empty"

    if len(content) > 50000:
        return "❌ Content too long (max 50,000 characters)"

    if tags:
        for tag in tags:
            if not isinstance(tag, str):
                return "❌ Tags must be strings"
            if len(tag) > 50:
                return "❌ Tag too long"
            if not tag.replace("-", "").replace("_", "").isalnum():
                return "❌ Invalid tag format"

    # Implementation...
```

### After: Pydantic Validation

```python
from session_mgmt_mcp.parameter_models import ReflectionStoreParams, validate_mcp_params


@mcp.tool()
async def store_reflection(content: str, tags: list[str] | None = None) -> str:
    try:
        # All validation in one line
        validated = validate_mcp_params(
            ReflectionStoreParams, content=content, tags=tags
        )

        # Parameters are guaranteed valid
        content = validated["content"]  # Non-empty, 1-50,000 chars
        tags = validated.get("tags")  # None or valid tag list

        # Implementation...
        return f"✅ Stored reflection with {len(tags) if tags else 0} tags"

    except ValueError as e:
        return f"❌ {e}"
```

## Validation Features

### 1. String Validation

```python
# Non-empty strings with length limits
content: str = Field(min_length=1, max_length=50000)

# Trimmed and normalized
query: str  # Automatically stripped of whitespace

# Pattern validation for special fields
email: str  # Basic email format validation
```

### 2. Path Validation

```python
# Automatic path expansion
working_directory: str  # ~/project -> /Users/user/project

# Existence validation
working_directory: str  # Must exist and be a directory

# Format validation
file_path: str  # No null characters, basic format checks
```

### 3. Numeric Constraints

```python
# Range validation
limit: int = Field(ge=1, le=1000)  # 1-1000 inclusive
min_score: float = Field(ge=0.0, le=1.0)  # 0.0-1.0 inclusive
timeout: int = Field(ge=1, le=3600)  # 1 second to 1 hour
```

### 4. Tag Validation

```python
# Automatic normalization
tags: ["Python", "  ASYNC  "] -> ["python", "async"]

# Format validation
valid_tags = ["python", "async-await", "database_orm"]
invalid_tags = ["python!", "tag with spaces", "tag@symbol"]

# Length limits
max_tag_length = 50  # characters
```

### 5. Enum Validation

```python
# Strict enum validation
role: Literal["owner", "admin", "moderator", "contributor", "viewer"]
access_level: Literal["private", "team", "public"]
dependency_type: Literal["uses", "extends", "references", "shares_code"]
```

## Best Practices

### 1. Use Appropriate Models

```python
# For simple working directory operations
validate_mcp_params(WorkingDirectoryParams, working_directory=wd)

# For search operations
validate_mcp_params(SearchQueryParams, query=q, limit=l, min_score=s)

# For team operations
validate_mcp_params(TeamUserParams, user_id=uid, username=name, role=role)
```

### 2. Handle Validation Errors Gracefully

```python
@mcp.tool()
async def my_tool(**params) -> str:
    try:
        validated = validate_mcp_params(MyParamsModel, **params)
        # ... implementation
    except ValueError as e:
        # Log the error for debugging
        logger.warning(f"Parameter validation failed: {e}")
        # Return user-friendly error
        return f"❌ Invalid parameters: {e}"
    except Exception as e:
        # Handle unexpected errors
        logger.exception(f"Tool execution failed: {e}")
        return f"❌ Tool execution failed: {e}"
```

### 3. Leverage Validation Features

```python
# Use path expansion
params = WorkingDirectoryParams(working_directory="~/project")
expanded_path = params.working_directory  # /Users/user/project

# Use tag normalization
params = TagParams(tags=["  Python  ", "ASYNC"])
normalized_tags = params.tags  # ["python", "async"]

# Use None exclusion
validated = validate_mcp_params(SearchParams, query="test", project=None)
# 'project' key won't be in validated dict
```

## Error Messages

The validation system provides clear, actionable error messages:

```python
# Empty content
"❌ Parameter validation failed: content: ensure this value has at least 1 characters"

# Invalid score range
"❌ Parameter validation failed: min_score: ensure this value is less than or equal to 1.0"

# Invalid tag format
"❌ Parameter validation failed: tags: Tags must contain only letters, numbers, hyphens, and underscores: invalid@tag"

# Multiple validation errors
"❌ Parameter validation failed: query: ensure this value has at least 1 characters; limit: ensure this value is greater than or equal to 1"
```

## Testing Parameter Models

```python
import pytest
from pydantic import ValidationError
from session_mgmt_mcp.parameter_models import SearchQueryParams


def test_valid_search_params():
    """Test valid parameter validation."""
    params = SearchQueryParams(query="python async", limit=20, min_score=0.8)
    assert params.query == "python async"
    assert params.limit == 20
    assert params.min_score == 0.8


def test_invalid_search_params():
    """Test invalid parameter validation."""
    with pytest.raises(ValidationError):
        SearchQueryParams(query="", limit=0)  # Empty query, invalid limit


def test_parameter_defaults():
    """Test default parameter values."""
    params = SearchQueryParams(query="test")
    assert params.limit == 10  # Default
    assert params.min_score == 0.7  # Default
```

## Integration with FastMCP

The parameter models are designed to work seamlessly with FastMCP's `@mcp.tool()` decorator:

```python
@mcp.tool()
async def enhanced_search(
    query: str, limit: int = 10, project: str | None = None, min_score: float = 0.7
) -> str:
    """Enhanced search with parameter validation.

    Args:
        query: Search query text (1-1,000 chars)
        limit: Maximum results to return (1-1,000)
        project: Optional project identifier (1-200 chars)
        min_score: Minimum relevance score (0.0-1.0)
    """
    # Validation and implementation...
```

## Custom Parameter Models

Create custom models for specific use cases:

```python
from pydantic import BaseModel, Field
from session_mgmt_mcp.parameter_models import NonEmptyStringMixin, PathValidationMixin


class CustomToolParams(BaseModel, NonEmptyStringMixin, PathValidationMixin):
    """Custom parameters for specialized tool."""

    tool_specific_field: str = Field(
        min_length=1, max_length=100, description="Tool-specific parameter"
    )

    optional_path: str | None = Field(
        default=None, description="Optional path that will be expanded"
    )

    complexity_level: Literal["simple", "moderate", "complex"] = Field(
        default="moderate", description="Complexity level for processing"
    )
```

## Migration Checklist

- [ ] **Identify parameter patterns** in existing tools
- [ ] **Choose appropriate parameter models** from the library
- [ ] **Add validation calls** to tool implementations
- [ ] **Update error handling** to use validation errors
- [ ] **Add parameter documentation** with constraints
- [ ] **Write tests** for parameter validation
- [ ] **Update tool docstrings** with parameter details

## Benefits

✅ **Type Safety**: Guaranteed parameter validity
✅ **Consistency**: Same validation patterns across tools
✅ **User Experience**: Clear, actionable error messages
✅ **Developer Experience**: Less boilerplate validation code
✅ **Maintainability**: Centralized validation logic
✅ **Testing**: Easy to test parameter edge cases

## Examples in Action

See the complete examples in:

- `session_mgmt_mcp/tools/validated_memory_tools.py` - Full integration examples
- `tests/unit/test_parameter_models.py` - Comprehensive test suite
- `session_mgmt_mcp/parameter_models.py` - All available models and utilities
