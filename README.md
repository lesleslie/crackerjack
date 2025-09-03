# Session Management MCP Server

A dedicated MCP server that provides comprehensive session management functionality for Claude Code sessions across any project.

## Features

- **🚀 Session Initialization**: Complete setup with UV dependency management, project analysis, and automation tools
- **🔍 Quality Checkpoints**: Mid-session quality monitoring with workflow analysis and optimization recommendations
- **🏁 Session Cleanup**: Comprehensive cleanup with learning capture and handoff file creation
- **📊 Status Monitoring**: Real-time session status and project context analysis

## Available MCP Tools

### Session Management

- **`init`** - Comprehensive session initialization including:

  - Project context analysis and health monitoring
  - UV dependency synchronization
  - Session management setup with auto-checkpoints
  - Project maturity scoring and recommendations
  - Permissions management to reduce prompts

- **`checkpoint`** - Mid-session quality assessment with:

  - Real-time quality scoring (project health, permissions, tools)
  - Workflow drift detection and optimization recommendations
  - Progress tracking and goal alignment
  - Automatic git checkpoint commits (if in git repo)

- **`end`** - Complete session cleanup featuring:

  - Final quality checkpoint and assessment
  - Learning capture across key categories
  - Session handoff file creation for continuity
  - Workspace cleanup and optimization

- **`status`** - Current session status including:

  - Project context analysis with health checks
  - Tool availability verification
  - Session management status
  - Available MCP tools listing with diagnostics

### Memory & Reflection System

- **`reflect_on_past`** - Search past conversations and insights with:

  - Semantic similarity search using local embeddings (all-MiniLM-L6-v2)
  - DuckDB-based conversation storage with FLOAT[384] vectors
  - Time-decay prioritization for recent conversations
  - Cross-project conversation history
  - Configurable similarity thresholds and result limits

- **`store_reflection`** - Store important insights for future reference with:

  - Content indexing with semantic embeddings
  - Tagging system for organization
  - Project-specific context tracking
  - Automatic embedding generation (local, no external services)

- **`search_nodes`** - Advanced search capabilities for stored knowledge

- **`quick_search`** - Fast overview search with count and top results

- **`get_more_results`** - Pagination support for large result sets

### Permissions & Trust System

- **`permissions`** - Manage trusted operations to reduce permission prompts:
  - View current trusted operations
  - Trust specific operations (UV sync, Git operations, file management)
  - Reset all permissions when needed

## Installation

### From Source

```bash
# Clone the repository
git clone https://github.com/lesleslie/session-mgmt-mcp.git
cd session-mgmt-mcp

# Install dependencies
uv sync --group dev

# Or use pip
pip install -e ".[embeddings,dev]"
```

### MCP Configuration

Add to your project's `.mcp.json` file:

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

### Alternative: Use Script Entry Point

If installed with pip/uv, you can use the script entry point:

```json
{
  "mcpServers": {
    "session-mgmt": {
      "command": "session-mgmt-mcp",
      "args": [],
      "env": {}
    }
  }
}
```

### Dependencies

**Required**:

- Python 3.13+
- `fastmcp>=2.0.0` - MCP server framework
- `duckdb>=0.9.0` - Conversation storage database
- `numpy>=1.24.0` - Numerical operations for embeddings

**Optional (for semantic search)**:

- `onnxruntime` - Local ONNX model inference
- `transformers` - Tokenizer for embedding models

Install with embedding support:

```bash
uv sync --extra embeddings
# or
pip install "session-mgmt-mcp[embeddings]"
```

## Usage

Once configured, the following slash commands become available in Claude Code:

### Primary Session Commands

- `/session-mgmt:init` - Full session initialization with workspace verification
- `/session-mgmt:checkpoint` - Quality monitoring checkpoint with scoring
- `/session-mgmt:end` - Complete session cleanup with learning capture
- `/session-mgmt:status` - Current status overview with health checks

### Memory & Search Commands

- `/session-mgmt:reflect_on_past` - Search past conversations with semantic similarity
- `/session-mgmt:store_reflection` - Store important insights with tagging
- `/session-mgmt:quick_search` - Fast search with overview results
- `/session-mgmt:permissions` - Manage trusted operations

### Advanced Usage

**Running Server Directly** (for development):

```bash
python -m session_mgmt_mcp.server
# or
session-mgmt-mcp
```

**Testing Memory Features**:

```bash
# The memory system automatically stores conversations and provides:
# - Semantic search across all past conversations
# - Local embedding generation (no external API needed)
# - Cross-project conversation history
# - Time-decay prioritization for recent content
```

## Memory System Architecture

### Built-in Conversation Memory

- **Local Storage**: DuckDB database at `~/.claude/data/reflection.duckdb`
- **Embeddings**: Local ONNX models (all-MiniLM-L6-v2) for semantic search
- **Vector Storage**: FLOAT[384] arrays for similarity matching
- **No External Dependencies**: Everything runs locally for privacy
- **Cross-Project History**: Conversations tagged by project context

### Search Capabilities

- **Semantic Search**: Vector similarity with customizable thresholds
- **Text Fallback**: Standard text search when embeddings unavailable
- **Time Decay**: Recent conversations prioritized in results
- **Project Context**: Filter searches by project or search across all
- **Batch Operations**: Efficient bulk storage and retrieval

## Data Storage

This server manages its data locally in the user's home directory:

- **Memory Storage**: `~/.claude/data/reflection.duckdb`
- **Session Logs**: `~/.claude/logs/`
- **Configuration**: Uses pyproject.toml and environment variables

## Recommended Session Workflow

1. **Initialize Session**: `/session-mgmt:init`

   - UV dependency synchronization
   - Project context analysis and health monitoring
   - Session quality tracking setup
   - Memory system initialization
   - Permission system setup

1. **Monitor Progress**: `/session-mgmt:checkpoint` (every 30-45 minutes)

   - Real-time quality scoring
   - Workflow optimization recommendations
   - Progress tracking and goal alignment
   - Automatic Git checkpoint commits

1. **Search Past Work**: `/session-mgmt:reflect_on_past`

   - Semantic search through project history
   - Find relevant past conversations and solutions
   - Build on previous insights

1. **Store Important Insights**: `/session-mgmt:store_reflection`

   - Capture key learnings and solutions
   - Tag insights for easy retrieval
   - Build project knowledge base

1. **End Session**: `/session-mgmt:end`

   - Final quality assessment
   - Learning capture across categories
   - Session handoff file creation
   - Memory persistence and cleanup

## Benefits

### Comprehensive Coverage

- **Session Quality**: Real-time monitoring and optimization
- **Memory Persistence**: Cross-session conversation retention
- **Project Structure**: Context-aware development workflows

### Reduced Friction

- **Single Command Setup**: One `/session-mgmt:init` sets up everything
- **Local Dependencies**: No external API calls or services required
- **Intelligent Permissions**: Reduces repeated permission prompts
- **Automated Workflows**: Structured processes for common tasks

### Enhanced Productivity

- **Quality Scoring**: Guides session effectiveness
- **Built-in Memory**: Enables building on past work automatically
- **Project Templates**: Accelerates development setup
- **Knowledge Persistence**: Maintains context across sessions

## Troubleshooting

### Common Issues

- **Memory not working**: Install optional dependencies with `pip install "session-mgmt-mcp[embeddings]"`
- **Path errors**: Ensure `cwd` and `PYTHONPATH` are set correctly in `.mcp.json`
- **Permission issues**: Use `/session-mgmt:permissions` to trust operations
- **Project context**: Analyze current project health and structure

### Debug Mode

```bash
# Run with verbose logging
PYTHONPATH=/path/to/session-mgmt-mcp python -m session_mgmt_mcp.server --debug
```
