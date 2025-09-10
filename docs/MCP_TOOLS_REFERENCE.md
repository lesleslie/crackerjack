# MCP Tools Reference

Complete reference guide for all Session Management MCP tools. Use these slash commands directly in Claude Code for comprehensive session management and intelligent conversation memory.

## 🚀 Core Session Management

### `/session-mgmt:start` - Session Initialization

**Purpose**: Complete session setup with project analysis and dependency management

**Usage**:

```
/session-mgmt:start
```

**What it does**:

- ✅ **Project Analysis**: Scans and analyzes your project structure, health, and maturity
- ✅ **Dependency Management**: Syncs UV, npm, pip, and other package managers automatically
- ✅ **Memory System**: Initializes conversation storage with semantic search capabilities
- ✅ **Permission Setup**: Configures trusted operations to reduce future prompts
- ✅ **Quality Baseline**: Establishes project health metrics for monitoring

**Returns**:

- Project context analysis with health score (0-100)
- Dependencies synchronization status
- Memory system initialization confirmation
- Personalized recommendations based on project type

**💡 Best Practice**: Run this at the start of every Claude Code session

______________________________________________________________________

### `/session-mgmt:checkpoint` - Quality Monitoring

**Purpose**: Mid-session quality assessment with workflow optimization

**Usage**:

```
/session-mgmt:checkpoint
```

**What it does**:

- 📊 **Quality Scoring**: Real-time analysis of project health, permissions, and tool availability
- 🔄 **Workflow Analysis**: Detects drift from optimal development patterns
- 📝 **Git Checkpoints**: Automatically creates meaningful commit with progress metadata
- 🎯 **Optimization Tips**: Provides specific recommendations for workflow improvements
- ⏱️ **Progress Tracking**: Monitors development velocity and goal alignment

**Returns**:

- Multi-dimensional quality score breakdown
- Workflow optimization recommendations
- Git checkpoint confirmation (if in repository)
- Personalized productivity insights

**💡 Best Practice**: Run every 30-45 minutes during active development

______________________________________________________________________

### `/session-mgmt:end` - Session Cleanup

**Purpose**: Comprehensive session termination with learning capture

**Usage**:

```
/session-mgmt:end
```

**What it does**:

- 📋 **Handoff Documentation**: Creates detailed session summary for continuity
- 🎓 **Learning Extraction**: Captures key insights, solutions, and patterns discovered
- 🧹 **Workspace Cleanup**: Optimizes temporary files and session artifacts
- 💾 **Memory Persistence**: Ensures all conversations are properly stored and indexed
- 📈 **Final Assessment**: Provides comprehensive session quality report

**Returns**:

- Final quality assessment and session metrics
- Handoff file path for future reference
- Learning insights categorized by type
- Memory persistence confirmation

**💡 Best Practice**: Always run at the end of development sessions

______________________________________________________________________

### `/session-mgmt:status` - Session Overview

**Purpose**: Current session status with comprehensive health checks

**Usage**:

```
/session-mgmt:status
```

**What it does**:

- 🔍 **Session State**: Reports current session status and active features
- 🏗️ **Project Context**: Analyzes current project structure and health
- 🛠️ **Tool Availability**: Lists available MCP tools and their status
- 🧠 **Memory Status**: Shows conversation storage and embedding system health
- 🔐 **Permissions**: Displays trusted operations and security settings

**Returns**:

- Complete session state overview
- Project health diagnostics
- Available tools inventory
- Memory system statistics
- Permission and security status

**💡 Best Practice**: Use when resuming sessions or troubleshooting issues

## 🧠 Memory & Search System

### `/session-mgmt:reflect_on_past` - Conversation Search

**Purpose**: Semantic search through all stored conversations with intelligent ranking

**Usage**:

```
/session-mgmt:reflect_on_past [query] [--limit=10] [--project=current] [--similarity=0.7]
```

**Parameters**:

- `query` (required): What you're looking for (e.g., "authentication implementation", "database migration patterns")
- `limit` (optional): Number of results to return (default: 10, max: 50)
- `project` (optional): Filter by specific project or "current" (default: all projects)
- `similarity` (optional): Minimum similarity score (default: 0.7, range: 0.0-1.0)

**Examples**:

```
/session-mgmt:reflect_on_past how did I implement user authentication?

/session-mgmt:reflect_on_past Redis caching strategies --limit=5 --similarity=0.8

/session-mgmt:reflect_on_past API error handling --project=current
```

**What it does**:

- 🔍 **Semantic Search**: Uses local AI embeddings (all-MiniLM-L6-v2) for meaning-based search
- 📅 **Time Weighting**: Recent conversations get priority in results
- 🎯 **Smart Ranking**: Combines semantic similarity with relevance and recency
- 🏗️ **Cross-Project**: Searches across all your projects unless filtered
- 🔒 **Privacy First**: All processing is local, no external API calls

**Returns**:

- Ranked list of relevant conversation excerpts
- Similarity scores for each result
- Project and timestamp context
- Smart suggestions for refining search

**💡 Best Practice**: Use before starting new implementations to leverage previous work

______________________________________________________________________

### `/session-mgmt:store_reflection` - Save Insights

**Purpose**: Store important insights and solutions for future reference

**Usage**:

```
/session-mgmt:store_reflection [content] [--tags=tag1,tag2,tag3]
```

**Parameters**:

- `content` (required): The insight, solution, or important information to store
- `tags` (optional): Comma-separated tags for organization and retrieval

**Examples**:

```
/session-mgmt:store_reflection "JWT refresh token rotation pattern: use sliding window expiration with Redis storage for optimal security/UX balance" --tags=auth,jwt,security,redis

/session-mgmt:store_reflection "Database migration best practice: always include rollback scripts and test on production-like data volumes"

/session-mgmt:store_reflection "React state management: use Zustand for simple cases, Redux Toolkit for complex state with time-travel debugging" --tags=react,state,frontend
```

**What it does**:

- 💾 **Persistent Storage**: Saves insights to searchable knowledge base
- 🏷️ **Smart Tagging**: Automatically extracts relevant tags from content
- 🔍 **Searchable**: Instantly findable via semantic search
- 📊 **Cross-Reference**: Links to related conversations and contexts
- 🧠 **AI-Enhanced**: Generates embeddings for precise retrieval

**Returns**:

- Confirmation of storage with unique reflection ID
- Applied tags (automatic + manual)
- Embedding generation status
- Storage timestamp and metadata

**💡 Best Practice**: Use immediately after solving complex problems or gaining important insights

______________________________________________________________________

### `/session-mgmt:quick_search` - Fast Overview Search

**Purpose**: Quick search with count and top result for rapid context assessment

**Usage**:

```
/session-mgmt:quick_search [query] [--project=current] [--similarity=0.7]
```

**Examples**:

```
/session-mgmt:quick_search Docker deployment strategies

/session-mgmt:quick_search testing patterns --project=current
```

**What it does**:

- ⚡ **Fast Results**: Returns immediately with count and best match
- 📊 **Overview Mode**: Gives you the lay of the land without detail
- 🎯 **Relevance Check**: Tells you if deeper search is worth it
- 🔄 **Progressive Discovery**: Sets up for detailed search if needed

**Returns**:

- Total count of relevant conversations
- Single best matching result
- Indication if more results are available
- Cache key for retrieving additional results

**💡 Best Practice**: Use first to gauge available context before deeper searches

______________________________________________________________________

### `/session-mgmt:get_more_results` - Pagination

**Purpose**: Retrieve additional results after initial searches

**Usage**:

```
/session-mgmt:get_more_results [query] [--offset=3] [--limit=5]
```

**What it does**:

- 📄 **Pagination**: Efficiently retrieves additional search results
- 🎯 **Consistent Ranking**: Maintains same relevance ordering
- ⚡ **Performance**: Uses cached search state for speed
- 📊 **Progressive Loading**: Load results as needed

## 🔍 Specialized Search Tools

### `/session-mgmt:search_by_file` - File-Specific Search

**Purpose**: Find all conversations that discussed specific files

**Usage**:

```
/session-mgmt:search_by_file [file_path] [--limit=10] [--project=current]
```

**Examples**:

```
/session-mgmt:search_by_file src/auth/middleware.py

/session-mgmt:search_by_file package.json --limit=5

/session-mgmt:search_by_file components/UserDashboard.tsx --project=current
```

**What it does**:

- 📁 **File-Centric**: Finds conversations where specific files were discussed
- 🔍 **Change History**: Shows evolution of file-related decisions
- 🏗️ **Context Reconstruction**: Rebuilds the story of how files developed
- 🔗 **Relationship Mapping**: Shows connections between related files

**💡 Best Practice**: Use before modifying existing files to understand previous decisions

______________________________________________________________________

### `/session-mgmt:search_by_concept` - Concept Search

**Purpose**: Explore conversations about development concepts and patterns

**Usage**:

```
/session-mgmt:search_by_concept [concept] [--include_files] [--limit=10] [--project=current]
```

**Examples**:

```
/session-mgmt:search_by_concept "error handling patterns"

/session-mgmt:search_by_concept authentication --include_files --limit=15

/session-mgmt:search_by_concept "state management" --project=current
```

**What it does**:

- 🎯 **Concept-Focused**: Searches for abstract development concepts
- 📚 **Pattern Discovery**: Finds how concepts were implemented across projects
- 🔗 **Cross-Reference**: Shows related files and implementations when requested
- 🧠 **Knowledge Mining**: Extracts architectural decisions and reasoning

**💡 Best Practice**: Use when exploring how to implement new concepts or patterns

## 📊 Analytics & Insights

### `/session-mgmt:search_summary` - Aggregated Insights

**Purpose**: Get high-level insights without individual result details

**Usage**:

```
/session-mgmt:search_summary [query] [--project=current] [--similarity=0.7]
```

**What it does**:

- 📈 **Aggregated View**: Provides summary statistics and insights
- 🎯 **Pattern Recognition**: Identifies common themes and approaches
- 📊 **Trend Analysis**: Shows evolution of techniques over time
- 🧠 **Knowledge Synthesis**: Combines insights from multiple conversations

**💡 Best Practice**: Use for high-level understanding of how topics have been handled

______________________________________________________________________

### `/session-mgmt:reflection_stats` - Knowledge Base Statistics

**Purpose**: Get comprehensive statistics about your stored knowledge

**Usage**:

```
/session-mgmt:reflection_stats
```

**What it does**:

- 📊 **Storage Overview**: Total conversations, reflections, and projects tracked
- 🧠 **Memory Health**: Embedding coverage and system performance
- 📅 **Timeline**: Oldest to most recent conversation spans
- 💾 **Usage Metrics**: Storage utilization and optimization opportunities

**Returns**:

- Total conversations and reflections stored
- Number of projects tracked
- Embedding system coverage percentage
- Storage size and health metrics
- Timeline of stored knowledge

**💡 Best Practice**: Use periodically to understand the scope of your knowledge base

## 🔧 Advanced Features

### Smart Permission System

The MCP server learns your permission preferences over time:

- ✅ **UV sync operations** - Automatically trusted after first approval
- ✅ **Git operations** - Checkpoint commits become seamless
- ✅ **File operations** - Reading project files for analysis
- ✅ **Quality tools** - Running linters and formatters

### Cross-Project Intelligence

Your knowledge base spans all projects:

- 🔗 **Related Projects**: Automatically identifies connections between repositories
- 📊 **Pattern Mining**: Finds common solutions across different codebases
- 🎯 **Context Bridging**: Applies insights from one project to another
- 🧠 **Cumulative Learning**: Builds expertise that compounds over time

### Token Optimization

Large responses are automatically managed:

- 📄 **Auto-Chunking**: Responses >4000 tokens split into manageable pieces
- 🔄 **Progressive Loading**: Retrieve additional chunks as needed
- 📊 **Smart Summarization**: Important information prioritized
- ⚡ **Performance**: Optimized for Claude Code's context window

## 🚨 Troubleshooting

### Common Issues

#### "Memory system not available"

```bash
# Install embedding dependencies
uv sync --extra embeddings
# or
pip install "session-mgmt-mcp[embeddings]"
```

#### "No conversations found"

- Ensure you've run `/session-mgmt:start` to initialize the database
- Check that `~/.claude/data/` directory exists and is writable

#### "Project not detected"

- Make sure you're in a project directory
- Use the `working_directory` parameter in init if needed
- Verify git repository status if using git features

#### "Permission errors"

- Check file permissions on `~/.claude/` directory
- Verify MCP server configuration in `.mcp.json`
- Use `/session-mgmt:status` to diagnose permission issues

### Performance Tips

- Use `/session-mgmt:quick_search` before full searches to check relevance
- Higher similarity thresholds (0.8-0.9) for more precise results
- Lower thresholds (0.6-0.7) for broader exploration
- Use project filtering for large knowledge bases
- Regular checkpoints improve quality scoring accuracy

## 📚 Related Documentation

- **[Quick Start Guide](QUICK_START.md)** - Get up and running in 5 minutes
- **[MCP Schema Reference](MCP_SCHEMA_REFERENCE.md)** - Complete API reference for AI agents
- **[AI Integration Patterns](AI_INTEGRATION_PATTERNS.md)** - Advanced workflow patterns
- **[Architecture Guide](ARCHITECTURE.md)** - Deep dive into system design
- **[Configuration Reference](CONFIGURATION.md)** - Advanced setup options

______________________________________________________________________

**Need help?** Use `/session-mgmt:status` to diagnose issues or check [GitHub Issues](https://github.com/lesleslie/session-mgmt-mcp/issues) for support.
