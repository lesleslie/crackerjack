# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Claude Session Management MCP (Model Context Protocol) server that provides comprehensive session management functionality for Claude Code across any project. It operates as a standalone MCP server with its own isolated environment to avoid dependency conflicts.

## Development Commands

### Installation & Setup

```bash
# Install all dependencies (development + optional)
uv sync --group dev --extra embeddings

# Install minimal dependencies only
uv sync

# Run server directly as a module
python -m session_mgmt_mcp.server

# Run server with debug logging
PYTHONPATH=. python -m session_mgmt_mcp.server --debug

# Verify installation
python -c "from session_mgmt_mcp.server import mcp; print('✅ MCP server ready')"
python -c "from session_mgmt_mcp.reflection_tools import ReflectionDatabase; print('✅ Memory system ready')"
```

### Quick Start Development

```bash
# Complete development setup in one command
uv sync --group dev --extra embeddings && \
  python tests/scripts/run_tests.py --quick && \
  crackerjack lint
```

### Code Quality & Linting

```bash
# Lint and format code (uses Ruff with strict settings)
crackerjack lint

# Run type checking
crackerjack typecheck

# Security scanning
crackerjack security

# Code complexity analysis
crackerjack complexity

# Full quality analysis
crackerjack analyze
```

### Testing & Development

```bash
# Run comprehensive test suite with coverage
python tests/scripts/run_tests.py

# Quick smoke tests for development (recommended during coding)
python tests/scripts/run_tests.py --quick

# Run specific test categories
python tests/scripts/run_tests.py --unit           # Unit tests only
python tests/scripts/run_tests.py --integration    # Integration tests only
python tests/scripts/run_tests.py --performance    # Performance tests only
python tests/scripts/run_tests.py --security       # Security tests only

# Run single test file with verbose output
pytest tests/unit/test_session_permissions.py -v -s

# Run tests with parallel execution (faster)
python tests/scripts/run_tests.py --parallel

# Coverage-only mode (no test execution)
python tests/scripts/run_tests.py --coverage-only

# Development debugging mode (keeps test data)
python tests/scripts/run_tests.py --verbose --no-cleanup

# Fail build if coverage below 85%
python tests/scripts/run_tests.py --fail-on-coverage --min-coverage 85.0

# Run tests with custom timeout
python tests/scripts/run_tests.py --timeout 300
```

### Development Workflow Commands

```bash
# Pre-commit workflow (run before any commit)
uv sync --group dev --extra embeddings && \
  crackerjack lint && \
  python tests/scripts/run_tests.py --quick && \
  crackerjack typecheck

# Full quality gate (run before PR)
python tests/scripts/run_tests.py --fail-on-coverage && \
  crackerjack security && \
  crackerjack complexity

# Debug server issues
python -c "
import logging
logging.basicConfig(level=logging.DEBUG)
from session_mgmt_mcp.server import mcp
print('Server debug check complete')
"
```

## Architecture Overview

### Core Components

1. **server.py** (~3,319 lines - modular organization in progress): Main MCP server implementation

   - FastMCP server setup and tool registration
   - Session lifecycle management (init, checkpoint, end, status)
   - Permissions management system with trusted operations
   - Project context analysis and health monitoring
   - Git integration for automatic checkpoint commits (recently fixed)
   - **Architecture**: Organized into focused tools/ modules with server.py coordinating registration

1. **reflection_tools.py**: Memory & conversation search system

   - **DuckDB Database**: Conversation storage with FLOAT[384] vector embeddings
   - **Local ONNX Model**: all-MiniLM-L6-v2 for semantic search (no external API calls)
   - **Async Architecture**: Executor threads prevent blocking on embedding generation
   - **Fallback Strategy**: Text search when ONNX/transformers unavailable
   - **Performance**: Optimized for concurrent access with connection pooling

1. **crackerjack_integration.py**: Code quality integration layer

   - Real-time parsing of Crackerjack tool outputs
   - Progress tracking and test result analysis
   - Quality metrics aggregation and trend analysis

1. **context_manager.py**: Session context and state management

1. **memory_optimizer.py**: Long-running session optimization

   - Conversation compaction and memory usage reduction
   - Token usage tracking and optimization strategies

1. **team_knowledge.py**: Collaborative knowledge sharing with access control

### Advanced Components

- **multi_project_coordinator.py**: Cross-project session coordination

  - **Data Models**: `ProjectGroup` and `ProjectDependency` dataclasses with type safety
  - **Relationship Types**: `related`, `continuation`, `reference` with semantic meaning
  - **Cross-Project Search**: Dependency-aware result ranking across related projects
  - **Use Case**: Coordinate microservices, monorepo modules, or related repositories

- **token_optimizer.py**: Context window and response management

  - **`TokenOptimizer`**: tiktoken-based accurate token counting for GPT models
  - **Response Chunking**: Auto-split responses >4000 tokens with cache keys
  - **`ChunkResult`**: Structured pagination with metadata and continuation support
  - **Metrics Collection**: `TokenUsageMetrics` for optimization insights

- **search_enhanced.py**: Advanced search capabilities

  - **Faceted Search**: Filter by project, time, author, content type
  - **Aggregations**: Statistical analysis of search results
  - **Full-Text Indexing**: FTS5 support in DuckDB for complex queries

- **interruption_manager.py**: Context preservation

  - **Smart Detection**: File system monitoring and activity pattern analysis
  - **Context Snapshots**: Automatic state preservation during interruptions
  - **Recovery**: Session restoration with minimal context loss

- **serverless_mode.py**: External storage integration

  - **Storage Backends**: Redis, S3-compatible, local file system
  - **Session Serialization**: Stateless operation with external persistence
  - **Multi-Instance**: Support for distributed Claude Code deployments

### Key Design Patterns & Architectural Decisions

#### 1. **Async-First Architecture**

- **Database Operations**: All DuckDB operations use executor threads to prevent blocking
- **Embedding Generation**: ONNX inference runs asynchronously with proper resource management
- **MCP Tool Pattern**: `@mcp.tool()` decorators handle async/await automatically
- **Connection Pooling**: DuckDB connections reused efficiently across requests

#### 2. **Graceful Degradation Strategy**

- **Optional Dependencies**: Falls back gracefully when `onnxruntime`/`transformers` unavailable
- **Search Fallback**: Text search when embeddings fail, maintaining functionality
- **Memory Constraints**: Automatic chunking and compression for resource-limited environments
- **Error Recovery**: Continues operation despite individual component failures

#### 3. **Local-First Privacy Design**

- **No External APIs**: All embeddings generated locally via ONNX
- **Local Storage**: DuckDB file-based storage in `~/.claude/` directory
- **Zero Network Dependencies**: Functions without internet for core features
- **User Data Control**: Complete data sovereignty with local processing

#### 4. **Type-Safe Data Modeling**

```python
@dataclass
class ProjectDependency:
    source_project: str
    target_project: str
    dependency_type: Literal["related", "continuation", "reference"]
    description: Optional[str] = None
```

- **Dataclass Architecture**: Immutable, type-safe data structures throughout
- **Enum Constraints**: Typed relationships prevent invalid state combinations
- **Pydantic Integration**: Runtime validation with automatic serialization

#### 5. **Performance-Optimized Vector Search**

```sql
-- DuckDB vector similarity with index support
SELECT content, array_cosine_similarity(embedding, $1) as similarity
FROM conversations
WHERE similarity > 0.7
ORDER BY similarity DESC, timestamp DESC
LIMIT 20;
```

- **Vector Indexing**: FLOAT[384] arrays with similarity search optimization
- **Hybrid Search**: Combines semantic similarity with temporal relevance
- **Result Ranking**: Time-decay weighting favors recent conversations

### Session Management Workflow

1. **Initialization** (`init` tool):

   - Sets up ~/.claude directory structure
   - Syncs UV dependencies and generates requirements.txt
   - Analyzes project context and calculates maturity score
   - Sets up session permissions and auto-checkpoints

1. **Quality Monitoring** (`checkpoint` tool):

   - Calculates multi-factor quality score (project health, permissions, tools)
   - Creates automatic Git commits with checkpoint metadata
   - Provides workflow optimization recommendations

1. **Session Cleanup** (`end` tool):

   - Generates session handoff documentation
   - Performs final quality assessment
   - Cleans up session artifacts

### Memory System Architecture

- **DuckDB Schema**: Core tables with vector support:

  ```sql
  CREATE TABLE conversations (
      id TEXT PRIMARY KEY,
      content TEXT,
      embedding FLOAT[384],  -- all-MiniLM-L6-v2 vectors
      project TEXT,
      timestamp TIMESTAMP
  );

  CREATE TABLE reflections (
      id TEXT PRIMARY KEY,
      content TEXT,
      embedding FLOAT[384],
      tags TEXT[]
  );
  ```

- **Vector Search Implementation**:

  - **Local ONNX Model**: all-MiniLM-L6-v2 with 384-dimensional vectors
  - **Cosine Similarity**: `array_cosine_similarity(embedding, query_vector)` in DuckDB
  - **Fallback Strategy**: Text search when embeddings unavailable or ONNX missing
  - **Async Execution**: Embedding generation runs in executor threads to avoid blocking

- **Multi-Project Coordination**:

  - `ProjectGroup` and `ProjectDependency` tables for relationship modeling
  - Cross-project search with dependency-aware result ranking
  - Session linking with typed relationships (`continuation`, `reference`, `related`)

## Configuration & Integration

### MCP Configuration (.mcp.json)

```json
{
  "mcpServers": {
    "session-mgmt": {
      "command": "python",
      "args": ["-m", "session_mgmt_mcp.server"],
      "cwd": "/path/to/session-mgmt-mcp",
      "env": {
        "PYTHONPATH": "/path/to/session-mgmt-mcp"
      }
    }
  }
}
```

### Directory Structure

The server uses the ~/.claude directory for data storage:

- **~/.claude/logs/**: Session management logging
- **~/.claude/data/**: Reflection database storage

### Environment Variables

- `PWD`: Used to detect current working directory

## Development Notes

### Dependencies & Isolation

- Uses isolated virtual environment to prevent conflicts
- Required: `fastmcp>=2.0.0`, `duckdb>=0.9.0`
- Optional: `onnxruntime`, `transformers` (for semantic search)
- Falls back gracefully when optional dependencies unavailable

### Testing Architecture

The project uses a comprehensive pytest-based testing framework with four main test categories:

**Test Structure:**

- **Unit Tests** (`tests/unit/`): Core functionality testing

  - Session permissions and lifecycle management
  - Reflection database operations with async/await patterns
  - Mock fixtures for isolated component testing

- **Integration Tests** (`tests/integration/`): Complete MCP workflow validation

  - End-to-end session management workflows
  - MCP tool registration and execution
  - Database integrity with concurrent operations

- **Performance Tests** (`tests/performance/`): Database and system performance

  - Bulk operation benchmarking with memory profiling
  - Concurrent access patterns under load
  - Performance regression detection with baselines

- **Security Tests** (`tests/security/`): Permission system validation

  - SQL injection prevention for DuckDB operations
  - Input sanitization across MCP tool parameters
  - Rate limiting and permission boundary testing

**Key Testing Features:**

- Async/await support for MCP server testing
- Temporary database fixtures with automatic cleanup
- Data factories for realistic test data generation
- Performance metrics collection and baseline comparison
- Mock MCP server creation for isolated testing

## Available MCP Tools

### Session Management Tools

- **`init`** (`mcp__session-mgmt__init`) - Complete session initialization with project analysis
- **`checkpoint`** (`mcp__session-mgmt__checkpoint`) - Mid-session quality assessment and optimization
- **`end`** (`mcp__session-mgmt__end`) - Complete session cleanup with learning capture
- **`status`** (`mcp__session-mgmt__status`) - Current session status with health checks
- **`permissions`** (`mcp__session-mgmt__permissions`) - Manage trusted operations

### Memory & Reflection Tools

- **`reflect_on_past`** (`mcp__session-mgmt__reflect_on_past`) - Search past conversations with semantic similarity
- **`store_reflection`** (`mcp__session-mgmt__store_reflection`) - Store important insights with tagging
- **`search_nodes`** (`mcp__session-mgmt__search_nodes`) - Advanced search through stored knowledge
- **`quick_search`** (`mcp__session-mgmt__quick_search`) - Fast overview search with count and top result
- **`search_summary`** (`mcp__session-mgmt__search_summary`) - Get aggregated insights without individual results
- **`get_more_results`** (`mcp__session-mgmt__get_more_results`) - Pagination support for large result sets
- **`search_by_file`** (`mcp__session-mgmt__search_by_file`) - Find conversations about specific files
- **`search_by_concept`** (`mcp__session-mgmt__search_by_concept`) - Search for development concepts
- **`reflection_stats`** (`mcp__session-mgmt__reflection_stats`) - Get statistics about stored knowledge

## Token Optimization and Response Chunking

The server includes sophisticated token management to handle large responses:

**Token Management Architecture**:

- **`TokenOptimizer`** class with tiktoken integration for accurate token counting
- **Response Chunking**: Automatically splits responses >4000 tokens into paginated chunks
- **`ChunkResult`** dataclass structure:
  ```python
  @dataclass
  class ChunkResult:
      chunks: List[str]  # Paginated content chunks
      total_chunks: int  # Total number of chunks
      current_chunk: int  # Current chunk index
      cache_key: str  # Unique cache identifier
      metadata: Dict[str, Any]  # Additional context
  ```

**Usage Pattern for Large Responses**:

```python
# Large response automatically chunked
result = await some_large_operation()
if result.get("chunked"):
    print(f"Response chunked: {result['current_chunk']}/{result['total_chunks']}")
    # Use get_cached_chunk tool to retrieve additional chunks
```

## Server Architecture Notes

✅ **Modular Architecture**: server.py is ~3,319 lines with tools organized in focused modules

### Current Modular Structure

The server is organized into focused modules:

```
session_mgmt_mcp/
├── server.py (main FastMCP setup and tool registration)
├── core/
│   └── session_manager.py (session state management)
├── tools/ (modular tool implementations)
│   ├── session_tools.py (init, checkpoint, end, status)
│   ├── memory_tools.py (reflection and search tools)
│   ├── search_tools.py (advanced search capabilities)
│   ├── crackerjack_tools.py (quality integration)
│   ├── llm_tools.py (LLM provider management)
│   └── team_tools.py (collaborative features)
├── utils/ (shared utilities)
│   ├── git_operations.py (Git commit functions)
│   ├── logging.py (SessionLogger)
│   └── quality_utils.py (quality assessment)
└── reflection_tools.py (DuckDB-based memory system)
```

## Integration with Crackerjack

This project integrates deeply with [Crackerjack](https://github.com/lesleslie/crackerjack) for code quality and development workflow automation:

- **Quality Commands**: Use `crackerjack lint`, `crackerjack typecheck`, etc. for code quality
- **MCP Integration**: Crackerjack is configured as an MCP server in .mcp.json
- **Progress Tracking**: `crackerjack_integration.py` provides real-time analysis parsing
- **Test Integration**: Crackerjack handles test execution, this project handles results analysis

## Development Guidelines

### Adding New MCP Tools

1. Define function with `@mcp.tool()` decorator in appropriate tools/ module
1. Add corresponding prompt with `@mcp.prompt()` for slash command support
1. Import and register in main server.py
1. Update status() tool to report new functionality
1. Add tests in appropriate test category

### Extending Memory System

1. Add new table schemas in reflection_tools.py:\_ensure_tables()
1. Implement storage/retrieval methods in ReflectionDatabase class
1. Add corresponding MCP tools in tools/memory_tools.py
1. Update reflection_stats() to include new metrics
1. Add performance tests for new operations

### Testing New Features

1. Add unit tests for individual functions in `tests/unit/`
1. Add integration tests for MCP tool workflows in `tests/integration/`
1. Add performance tests for database operations in `tests/performance/`
1. Add security tests for input validation in `tests/security/`
1. Use `tests/fixtures/` for test data factories and mock fixtures
1. Ensure 85% minimum coverage is maintained via `python tests/scripts/run_tests.py --fail-on-coverage`

## Configuration Files

### pyproject.toml Configuration

The project uses modern Python tooling with strict quality settings:

- **Python 3.13+** required with latest language features
- **Ruff**: Code formatting and linting with complexity limits (max 13)
- **Pytest**: Comprehensive testing with async/await, coverage, and benchmarking
- **Optional Dependencies**: `[embeddings]` for semantic search, `[dev]` for development tools

### MCP Server Configuration

The `.mcp.json` shows integration with multiple MCP servers:

- **session-mgmt**: This server (local development mode with uvx)
- **crackerjack**: Code quality tools and workflow automation
- **ast-grep**: Code analysis and pattern matching
- Plus additional servers for GitHub, GitLab, memory, etc.

### Testing Configuration (conftest.py)

- Async/await support for MCP server testing
- Temporary database fixtures with automatic cleanup
- Mock MCP server creation for isolated testing
- Performance baseline comparisons

## Modern Development Patterns

### 1. **Async/Await Best Practices**

```python
# ✅ Correct: Use executor for blocking operations
async def generate_embedding(text: str) -> np.ndarray:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _sync_embedding_generation, text)


# ❌ Avoid: Blocking the event loop
async def bad_embedding(text: str) -> np.ndarray:
    return onnx_session.run(None, {"input": text})  # Blocks event loop
```

### 2. **Database Connection Management**

```python
# ✅ Correct: Context manager with connection pooling
async def store_conversation(content: str) -> str:
    async with ReflectionDatabase() as db:
        return await db.store_conversation(content)


# ✅ Correct: Batch operations for efficiency
async def bulk_store(conversations: List[str]) -> List[str]:
    async with ReflectionDatabase() as db:
        return await db.bulk_store_conversations(conversations)
```

### 3. **Error Handling Strategy**

```python
# ✅ Correct: Graceful degradation with logging
async def search_with_fallback(query: str) -> List[SearchResult]:
    try:
        # Try semantic search first
        return await semantic_search(query)
    except (ImportError, RuntimeError) as e:
        logger.info(f"Semantic search unavailable: {e}. Using text search.")
        return await text_search(query)
    except Exception as e:
        logger.error(f"Search failed: {e}")
        return []
```

### 4. **MCP Tool Development Pattern**

```python
@mcp.tool()
async def example_tool(param1: str, param2: Optional[int] = None) -> Dict[str, Any]:
    """
    Tool description for Claude Code.

    Args:
        param1: Required parameter with clear description
        param2: Optional parameter with default value

    Returns:
        Structured response with success/error handling
    """
    try:
        # Validate inputs
        if not param1.strip():
            return {"success": False, "error": "param1 cannot be empty"}

        # Perform operation with proper async handling
        result = await perform_async_operation(param1, param2)

        return {
            "success": True,
            "data": result,
            "metadata": {
                "timestamp": datetime.now().isoformat(),
                "execution_time_ms": 42,
            },
        }

    except Exception as e:
        logger.error(f"Tool execution failed: {e}")
        return {"success": False, "error": str(e)}
```

## Troubleshooting Guide

### Common Issues & Solutions

#### 1. **MCP Server Not Loading**

```bash
# Check imports
python -c "import session_mgmt_mcp; print('✅ Package imports successfully')"

# Verify FastMCP setup
python -c "from session_mgmt_mcp.server import mcp; print('✅ MCP server configured')"

# Check for missing dependencies
python -c "
try:
    import duckdb, numpy, tiktoken
    print('✅ Core dependencies available')
except ImportError as e:
    print(f'❌ Missing dependency: {e}')
"
```

#### 2. **Memory/Embedding Issues**

```bash
# Test embedding system
python -c "
from session_mgmt_mcp.reflection_tools import ReflectionDatabase
import asyncio

async def test():
    try:
        async with ReflectionDatabase() as db:
            result = await db.test_embedding_system()
            print(f'✅ Embedding system: {result}')
    except Exception as e:
        print(f'⚠️ Embedding fallback mode: {e}')

asyncio.run(test())
"

# Install embedding dependencies if missing
uv sync --extra embeddings
```

#### 3. **Database Connection Problems**

```bash
# Check DuckDB installation
python -c "import duckdb; print(f'✅ DuckDB version: {duckdb.__version__}')"

# Test database connection
python -c "
import duckdb
conn = duckdb.connect(':memory:')
print('✅ DuckDB connection successful')
conn.close()
"

# Check file permissions
ls -la ~/.claude/data/ 2>/dev/null || echo "Creating ~/.claude/data/" && mkdir -p ~/.claude/data/
```

#### 4. **Performance Issues**

```bash
# Run performance diagnostics
python tests/scripts/run_tests.py --performance --verbose

# Check memory usage patterns
python -c "
import psutil
import os
print(f'Memory usage: {psutil.Process(os.getpid()).memory_info().rss / 1024 / 1024:.1f} MB')
"

# Enable detailed logging
PYTHONPATH=. python -m session_mgmt_mcp.server --debug
```

### Development Environment Setup Issues

#### **UV Package Manager**

```bash
# Verify UV installation
uv --version || curl -LsSf https://astral.sh/uv/install.sh | sh

# Reset environment if corrupted
rm -rf .venv && uv sync --group dev --extra embeddings

# Check for conflicting dependencies
uv pip check
```

#### **Python Version Compatibility**

```bash
# Verify Python 3.13+ requirement
python --version  # Should be 3.13+

# Check for async/await compatibility
python -c "
import sys
print(f'Python {sys.version}')
assert sys.version_info >= (3, 13), 'Python 3.13+ required'
print('✅ Python version compatible')
"
```

### Coding Standards & Best Practices

#### Core Philosophy (from RULES.md)

- **EVERY LINE OF CODE IS A LIABILITY**: The best code is no code
- **DRY (Don't Repeat Yourself)**: If you write it twice, you're doing it wrong
- **YAGNI (You Ain't Gonna Need It)**: Build only what's needed NOW
- **KISS (Keep It Simple, Stupid)**: Complexity is the enemy of maintainability

#### Type Safety Requirements

- **Always use comprehensive type hints** with modern Python 3.13+ syntax
- **Import typing as `import typing as t`** and prefix all typing references
- **Use built-in collection types**: `list[str]` instead of `t.List[str]`
- **Use pipe operator for unions**: `str | None` instead of `Optional[str]`

#### Development Practices

1. **Always use async/await** for database and file operations
1. **Test with both embedding and fallback modes** during development
1. **Include comprehensive error handling** with graceful degradation
1. **Use type hints and dataclasses** for data modeling
1. **Follow the testing pattern**: unit → integration → performance → security
1. **Run pre-commit workflow** before any commits
1. **Monitor token usage** and response chunking during development
1. **Test cross-project coordination** features with multiple repositories

<!-- CRACKERJACK INTEGRATION START -->

# Crackerjack Integration for session-mgmt-mcp

This project uses crackerjack for Python project management and quality assurance.

## Recommended Claude Code Agents

For optimal development experience with this crackerjack-enabled project, use these specialized agents:

### **Primary Agents (Use for all Python development)**

- **🏗️ crackerjack-architect**: Expert in crackerjack's modular architecture and Python project management patterns. **Use PROACTIVELY** for all feature development, architectural decisions, and ensuring code follows crackerjack standards from the start.

- **🐍 python-pro**: Modern Python development with type hints, async/await patterns, and clean architecture

- **🧪 pytest-hypothesis-specialist**: Advanced testing patterns, property-based testing, and test optimization

### **Task-Specific Agents**

- **🧪 crackerjack-test-specialist**: Advanced testing specialist for complex testing scenarios and coverage optimization
- **🏗️ backend-architect**: System design, API architecture, and service integration patterns
- **🔒 security-auditor**: Security analysis, vulnerability detection, and secure coding practices

### **Agent Usage Patterns**

```bash
# Start development with crackerjack-compliant architecture
Task tool with subagent_type="crackerjack-architect" for feature planning

# Implement with modern Python best practices
Task tool with subagent_type="python-pro" for code implementation

# Add comprehensive testing
Task tool with subagent_type="pytest-hypothesis-specialist" for test development

# Security review before completion
Task tool with subagent_type="security-auditor" for security analysis
```

**💡 Pro Tip**: The crackerjack-architect agent automatically ensures code follows crackerjack patterns from the start, eliminating the need for retrofitting and quality fixes.

## Crackerjack Quality Standards

This project follows crackerjack's clean code philosophy:

### **Core Principles**

- **EVERY LINE OF CODE IS A LIABILITY**: The best code is no code
- **DRY (Don't Repeat Yourself)**: If you write it twice, you're doing it wrong
- **YAGNI (You Ain't Gonna Need It)**: Build only what's needed NOW
- **KISS (Keep It Simple, Stupid)**: Complexity is the enemy of maintainability

### **Quality Rules**

- **Cognitive complexity ≤13** per function (automatically enforced)
- **Coverage ratchet system**: Never decrease coverage, always improve toward 100%
- **Type annotations required**: All functions must have return type hints
- **Security patterns**: No hardcoded paths, proper temp file handling
- **Python 3.13+ modern patterns**: Use `|` unions, pathlib over os.path

## Development Workflow

### **Quality Commands**

```bash
# Quality checks (fast feedback during development)
python -m crackerjack

# With comprehensive testing
python -m crackerjack -t

# AI agent mode with autonomous fixing
python -m crackerjack --ai-agent -t

# Full release workflow
python -m crackerjack -a patch
```

### **Recommended Workflow**

1. **Plan with crackerjack-architect**: Ensure proper architecture from the start
1. **Implement with python-pro**: Follow modern Python patterns
1. **Test comprehensively**: Use pytest-hypothesis-specialist for robust testing
1. **Run quality checks**: `python -m crackerjack -t` before committing
1. **Security review**: Use security-auditor for final validation

## Important Instructions

- **Use crackerjack-architect agent proactively** for all significant code changes
- **Never reduce test coverage** - the ratchet system only allows improvements
- **Follow crackerjack patterns** - the tools will enforce quality automatically
- **Leverage AI agent auto-fixing** - `python -m crackerjack --ai-agent -t` for autonomous quality fixes

______________________________________________________________________

*This project is enhanced by crackerjack's intelligent Python project management.*

<!-- CRACKERJACK INTEGRATION END -->
