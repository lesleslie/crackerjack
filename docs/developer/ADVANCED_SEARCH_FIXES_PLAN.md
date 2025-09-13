# Plan for Fixing Remaining AdvancedSearch Test Failures

## Overview

We currently have 7 failing AdvancedSearch tests out of 24 total tests. This document outlines what needs to be fixed for each failing test and how to approach the implementations.

## Failing Tests Analysis

### 1. test_search_by_content_type

**Issue**: Content type filtering is not properly implemented
**Error**: AttributeError: 'SearchResult' object has no attribute 'content_type'

**Required Fixes**:

- Modify SearchResult class to include content_type attribute
- Implement content_type filtering in search query building
- Add content_type to search metadata extraction

**Implementation Approach**:

1. Add content_type parameter to SearchResult.__init__
1. Update \_execute_search method to extract and use content_type
1. Modify search method to handle content_type parameter
1. Update test expectations to match new implementation

### 2. test_search_with_sorting

**Issue**: Sorting functionality is not properly implemented
**Error**: Missing implementation for sorting options

**Required Fixes**:

- Implement proper sorting in \_execute_search method
- Add support for different sort_by values (relevance, date, project)
- Ensure sorting works with database queries

**Implementation Approach**:

1. Enhance SQL query building to include ORDER BY clauses
1. Add validation for sort_by parameter values
1. Implement relevance sorting algorithm
1. Test with different sorting options

### 3. test_search_with_timeframe and test_search_by_timeframe

**Issue**: Timeframe-based filtering is not implemented
**Error**: Missing implementation for timeframe parameter

**Required Fixes**:

- Implement timeframe parameter handling in search method
- Add timeframe filtering to SQL query conditions
- Handle different timeframe formats (1d, 7d, 30d, etc.)

**Implementation Approach**:

1. Add timeframe parameter to search method signature
1. Implement timeframe parsing and conversion
1. Add timeframe conditions to SQL query
1. Handle edge cases and invalid timeframe formats

### 4. test_search_suggestions

**Issue**: Search suggestions functionality is missing
**Error**: Missing implementation for suggest_completions method

**Required Fixes**:

- Implement suggest_completions method in AdvancedSearchEngine
- Add prefix matching for search terms
- Return suggestions with frequency information

**Implementation Approach**:

1. Query database for terms that match prefix
1. Calculate frequency of terms
1. Return ranked suggestions
1. Handle edge cases (empty query, no matches)

### 5. test_error_handling_malformed_timeframe

**Issue**: Error handling for malformed timeframe is insufficient
**Error**: Missing proper error handling/validation

**Required Fixes**:

- Add validation for timeframe parameter
- Implement proper error responses for invalid formats
- Add logging for malformed inputs

**Implementation Approach**:

1. Add timeframe format validation
1. Catch and handle parsing exceptions
1. Return meaningful error messages
1. Add unit tests for various malformed inputs

### 6. test_search_case_insensitive

**Issue**: Search is not case-insensitive as expected
**Error**: Search results don't match case variations

**Required Fixes**:

- Implement case-insensitive search in SQL queries
- Ensure text matching works regardless of case
- Maintain case sensitivity for specific fields when needed

**Implementation Approach**:

1. Use LOWER() or similar functions in SQL queries
1. Convert search terms to lowercase for comparison
1. Test with various case combinations
1. Ensure performance is not significantly impacted

## Detailed Implementation Plan

### Phase 1: Quick Wins (1-2 hours)

1. **Fix SearchResult content_type attribute**

   - Add content_type parameter to SearchResult.__init__
   - Update all SearchResult instantiations
   - Fix test_search_by_content_type

1. **Add basic timeframe parameter support**

   - Add timeframe parameter to search method
   - Implement basic timeframe parsing
   - Fix test_search_with_timeframe and test_search_by_timeframe

### Phase 2: Medium Complexity Features (2-4 hours)

3. **Implement sorting functionality**

   - Enhance SQL query building with ORDER BY
   - Add support for different sort options
   - Fix test_search_with_sorting

1. **Implement error handling for malformed timeframe**

   - Add validation and error handling
   - Fix test_error_handling_malformed_timeframe

### Phase 3: Advanced Features (4-8 hours)

5. **Implement search suggestions**

   - Create suggest_completions method
   - Add prefix matching and frequency calculation
   - Fix test_search_suggestions

1. **Implement case-insensitive search**

   - Modify SQL queries for case-insensitive matching
   - Test with various case combinations
   - Fix test_search_case_insensitive

## Code Changes Required

### SearchResult Class Modifications

```python
# Add content_type parameter to __init__
def __init__(
    self,
    content_id: str,
    content_type: str,  # NEW
    title: str,
    content: str,
    score: float,
    project: str | None = None,
    timestamp: datetime | None = None,
    metadata: dict[str, Any] | None = None,
    highlights: list[str] | None = None,
    facets: dict[str, Any] | None = None,
) -> None:
```

### Search Method Modifications

```python
# Add timeframe and content_type parameters
async def search(
    self,
    query: str,
    filters: list[SearchFilter] | None = None,
    facets: list[str] | None = None,
    sort_by: str = "relevance",
    limit: int = 20,
    offset: int = 0,
    include_highlights: bool = True,
    timeframe: str | None = None,  # NEW
    content_type: str | None = None,  # NEW
) -> dict[str, Any]:
```

### SQL Query Enhancements

```python
# Add ORDER BY clause for sorting
if sort_by == "date":
    sql += " ORDER BY last_indexed DESC"
elif sort_by == "project":
    sql += " ORDER BY JSON_EXTRACT_STRING(search_metadata, '$.project')"
else:  # relevance
    sql += " ORDER BY LENGTH(indexed_content) DESC"

# Add timeframe filtering
if timeframe:
    # Parse timeframe and add condition
    start_time = self._parse_timeframe(timeframe)
    conditions.append("last_indexed >= ?")
    params.append(start_time)
```

## Testing Strategy

### Unit Tests for New Features

1. Create individual unit tests for each new parameter
1. Test edge cases and error conditions
1. Verify backward compatibility
1. Test performance impact

### Integration Tests

1. Test combination of multiple features (sorting + filtering + timeframe)
1. Test with large datasets
1. Test error scenarios

## Success Criteria

1. All 24 AdvancedSearch tests pass
1. No regression in existing functionality
1. Performance remains acceptable
1. Code follows existing patterns and style
1. Proper documentation and comments added
1. Edge cases handled appropriately

With this systematic approach, we should be able to resolve all remaining test failures and significantly improve the AdvancedSearch functionality.
