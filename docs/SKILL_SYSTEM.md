# Crackerjack Skills System

## Overview

Crackerjack's Skills System provides a multi-layered architecture that bridges AI agent capabilities with MCP tool integration. The system implements **three complementary approaches** to expose skills:

1. **Agent Skills** (Option 1) - Maps internal agent capabilities to skills
2. **MCP Skills** (Option 2) - Groups existing MCP tools into purpose-based skills
3. **Hybrid Skills** (Option 3) - Combines agents with MCP tool delegation

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Crackerjack Skills System                 │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ Agent Skills │  │  MCP Skills  │  │Hybrid Skills │      │
│  │  (Option 1)  │  │  (Option 2)  │  │  (Option 3)  │      │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘      │
│         │                 │                 │               │
│         └─────────────────┴─────────────────┘               │
│                           │                                 │
│                           ▼                                 │
│              ┌──────────────────────────┐                   │
│              │   Skill Registration     │                   │
│              │   (unified entry point)   │                   │
│              └───────────┬──────────────┘                   │
│                          │                                  │
│                          ▼                                  │
│              ┌──────────────────────────┐                   │
│              │    MCP Server Tools      │                   │
│              │  (8 skill tools exposed) │                   │
│              └──────────────────────────┘                   │
└─────────────────────────────────────────────────────────────┘
```

## Implementation Options

### Option 1: Agent Skills

**Purpose**: Map internal agent capabilities to a skill-based interface

**Key Classes**:
- `AgentSkill` - Wrapper around `SubAgent` with skill metadata
- `AgentSkillRegistry` - Manages and discovers agent skills
- `SkillMetadata` - Rich metadata about agent capabilities

**Usage**:
```python
from crackerjack.skills import AgentSkillRegistry
from crackerjack.agents.base import AgentContext

# Create registry
registry = AgentSkillRegistry()

# Register all agents
context = AgentContext(project_path=Path("."))
registry.register_all_agents(context)

# Find skills for an issue type
from crackerjack.agents.base import IssueType
complexity_skills = registry.get_skills_for_type(IssueType.COMPLEXITY)

# Execute a skill
issue = Issue(type=IssueType.COMPLEXITY, ...)
result = await skill.execute(issue)
```

**Features**:
- ✅ Preserves existing agent architecture
- ✅ Adds skill discovery layer
- ✅ Confidence-based skill matching
- ✅ Batch execution support
- ✅ Performance tracking (execution count, success rate)

### Option 2: MCP Skills

**Purpose**: Group existing MCP tools into purpose-based skills

**Key Classes**:
- `MCPSkill` - Groups related MCP tools
- `MCPSkillRegistry` - Manages MCP skill groups
- `ToolReference` - Metadata about MCP tools

**Predefined Skills**:
```python
MCP_SKILL_GROUPS = {
    "quality_checks": {
        "tools": ["execute_crackerjack", "analyze_errors", ...],
        "domain": "execution",
    },
    "semantic_search": {
        "tools": ["index_file", "search_semantic", ...],
        "domain": "semantic",
    },
    "proactive_agent": {
        "tools": ["plan_development", "validate_architecture", ...],
        "domain": "proactive",
    },
    # ... more skills
}
```

**Usage**:
```python
from crackerjack.skills import MCPSkillRegistry

# Create registry
registry = MCPSkillRegistry()

# Register predefined skills
for skill_data in MCP_SKILL_GROUPS.values():
    registry.register_skill_group(skill_data)

# Search for skills
monitoring_skills = registry.get_skills_by_domain(SkillDomain.MONITORING)

# Get tools in a skill
tools = registry.get_tools_in_skill("quality_checks")
```

**Features**:
- ✅ Better tool discoverability
- ✅ Logical grouping by functionality
- ✅ Domain-based organization
- ✅ Search capabilities
- ✅ No changes to existing tools

### Option 3: Hybrid Skills

**Purpose**: Combine agent capabilities with MCP tool exposure

**Key Classes**:
- `HybridSkill` - Agent skill with MCP tool integration
- `HybridSkillRegistry` - Manages hybrid skills
- `ToolDelegator` - Delegates skill execution to MCP tools

**Usage**:
```python
from crackerjack.skills import HybridSkillRegistry
from crackerjack.agents.base import AgentContext

# Create registry with MCP app
registry = HybridSkillRegistry()
registry.register_mcp_app(mcp_app)

# Register hybrid skills
context = AgentContext(project_path=Path("."))
hybrid_skills = registry.register_all_hybrid_skills(context)

# Execute via MCP tool
result = await registry.execute_via_tool(
    "refactoring_skill_execute",
    issue_type="complexity",
    issue_data={"message": "Complex function", ...},
)
```

**Auto-Generated Tools**:
Each hybrid skill automatically generates 4 MCP tools:
1. `{skill_id}_can_handle` - Check if skill can handle an issue
2. `{skill_id}_execute` - Execute the skill
3. `{skill_id}_batch_execute` - Execute on multiple issues
4. `{skill_id}_get_info` - Get skill information

**Features**:
- ✅ Best of both worlds (agent + tools)
- ✅ Automatic tool generation
- ✅ MCP protocol integration
- ✅ Unified execution interface
- ✅ Tool delegation support

## MCP Server Integration

### Skill System Initialization

The skill system is automatically initialized during MCP server startup:

```python
# In crackerjack/mcp/server_core.py:main()
mcp_app = create_mcp_server(mcp_config)

# Initialize skill system
initialize_skills(project_path, mcp_app)
register_skill_tools(mcp_app)
```

### Exposed MCP Tools

The skill system exposes **8 MCP tools** for skill management:

1. **`list_skills`** - List all available skills
   ```python
   list_skills(skill_type="all")  # "all", "agent", "mcp", "hybrid"
   ```

2. **`get_skill_info`** - Get detailed skill information
   ```python
   get_skill_info(skill_id="abc123", skill_type="agent")
   ```

3. **`search_skills`** - Search for skills by query
   ```python
   search_skills(query="refactoring", search_in="all")
   ```

4. **`get_skills_for_issue`** - Get skills that can handle an issue type
   ```python
   get_skills_for_issue(issue_type="complexity")
   ```

5. **`get_skill_statistics`** - Get registry statistics
   ```python
   get_skill_statistics()
   ```

6. **`execute_skill`** - Execute a skill on an issue
   ```python
   execute_skill(
       skill_id="abc123",
       issue_type="complexity",
       issue_data={"message": "...", "file_path": "..."},
   )
   ```

7. **`find_best_skill`** - Find the best skill for an issue
   ```python
   find_best_skill(issue_type="complexity")
   ```

## Usage Examples

### Example 1: List All Skills

```python
# Via MCP tool
result = await mcp_app.call_tool("list_skills", {"skill_type": "all"})

# Returns:
{
    "agent_skills": [...],
    "mcp_skills": [...],
    "hybrid_skills": [...],
}
```

### Example 2: Find Skills for an Issue

```python
# Via MCP tool
result = await mcp_app.call_tool(
    "get_skills_for_issue",
    {"issue_type": "complexity"},
)

# Returns:
{
    "agent_skills": [
        {
            "skill_id": "skill_abc123",
            "metadata": {
                "name": "RefactoringAgent",
                "category": "code_quality",
                "supported_types": ["complexity", "dead_code"],
            },
        },
    ],
    "hybrid_skills": [...],
}
```

### Example 3: Execute a Skill

```python
# Via MCP tool
result = await mcp_app.call_tool(
    "execute_skill",
    {
        "skill_id": "skill_abc123",
        "issue_type": "complexity",
        "issue_data": {
            "message": "Function too complex",
            "file_path": "src/main.py",
            "line_number": 42,
        },
        "timeout": 30,
    },
)

# Returns:
{
    "skill_name": "RefactoringAgent",
    "success": true,
    "confidence": 0.9,
    "fixes_applied": ["Simplified complex function"],
    "recommendations": ["Consider breaking into smaller functions"],
    "files_modified": ["src/main.py"],
    "execution_time_ms": 150,
}
```

### Example 4: Search for Skills

```python
# Via MCP tool
result = await mcp_app.call_tool(
    "search_skills",
    {"query": "security", "search_in": "all"},
)

# Returns skills matching "security" in names, descriptions, or tags
```

## Available Skills

### Agent Skills (12 total)

| Skill | Category | Issue Types |
|-------|----------|-------------|
| RefactoringAgent | code_quality | complexity, dead_code |
| PerformanceAgent | performance | performance |
| SecurityAgent | security | security |
| FormattingAgent | code_quality | formatting |
| ImportOptimizationAgent | code_quality | import_error |
| TestCreationAgent | testing | test_failure |
| DocumentationAgent | documentation | documentation |
| SemanticAgent | semantic | semantic_context |
| ArchitectAgent | architecture | architecture |
| EnhancedProactiveAgent | proactive | proactive |
| TestSpecialistAgent | testing | test_organization |
| DRYAgent | code_quality | dry_violation |

### MCP Skills (6 groups)

| Skill | Domain | Tools |
|-------|--------|-------|
| quality_checks | execution | execute_crackerjack, analyze_errors, get_agent_suggestions |
| semantic_search | semantic | index_file, search_semantic, get_embeddings, calculate_similarity |
| proactive_agent | proactive | plan_development, validate_architecture, suggest_patterns |
| monitoring | monitoring | get_job_progress, get_comprehensive_status, get_server_stats |
| utilities | utility | clean, config, init_crackerjack, analyze |
| intelligence | intelligence | smart_error_analysis |

## Configuration

### Skill System Configuration

The skill system reads configuration from:

1. **AgentContext** - For agent-based skills
   ```python
   context = AgentContext(
       project_path=Path("."),
       temp_dir=Path(".cache"),
       subprocess_timeout=300,
       max_file_size=10_000_000,
   )
   ```

2. **MCP Server Config** - For tool registration
   ```python
   mcp_config = {
       "http_port": 8676,
       "http_host": "127.0.0.1",
       "http_enabled": False,
   }
   ```

### Disabling Skills

To disable specific skill types, modify `register_all_skills()` call:

```python
# Disable hybrid skills
registries = register_all_skills(
    mcp_app,
    context,
    enable_agent_skills=True,
    enable_mcp_skills=True,
    enable_hybrid_skills=False,  # Disabled
)
```

## Testing

### Running Tests

```bash
# Test all skill components
pytest tests/skills/ -v

# Test specific implementation
pytest tests/skills/test_agent_skills.py -v
pytest tests/skills/test_mcp_skills.py -v

# Run with coverage
pytest tests/skills/ --cov=crackerjack/skills --cov-report=html
```

### Test Coverage

The skill system includes comprehensive tests for:

- ✅ Agent skill creation and execution
- ✅ MCP skill grouping and discovery
- ✅ Hybrid skill tool generation
- ✅ Registry operations (register, search, filter)
- ✅ Skill metadata and serialization
- ✅ Confidence-based matching
- ✅ Batch execution
- ✅ Error handling and edge cases

## Performance Considerations

### Skill Execution

- **Agent Skills**: ~10-100ms per issue (depends on agent complexity)
- **MCP Skills**: Instant (metadata operations only)
- **Hybrid Skills**: ~10-100ms + MCP tool overhead

### Memory Usage

- Each skill: ~1KB metadata + agent instance
- Registry overhead: ~100KB base
- Total for all skills: ~500KB-1MB

### Optimization Tips

1. **Use skill caching** - Skills are cached in registries
2. **Batch operations** - Use `batch_execute()` for multiple issues
3. **Filter by type** - Use `get_skills_for_type()` instead of searching all
4. **Confidence thresholds** - Adjust to reduce unnecessary executions

## Troubleshooting

### Skills Not Appearing

**Problem**: Skills don't show up in MCP tool list

**Solution**:
1. Check MCP server startup logs for "Skill system initialized"
2. Verify agents are registered in `agent_registry`
3. Check for exceptions during skill initialization

### Skill Execution Fails

**Problem**: Skill execution returns errors

**Solution**:
1. Verify issue type matches skill's `supported_types`
2. Check agent's `can_handle()` confidence score
3. Review agent logs for specific errors
4. Increase timeout if needed

### Tools Not Generated

**Problem**: Hybrid skill tools not appearing in MCP

**Solution**:
1. Verify `register_mcp_app()` was called
2. Check `enable_hybrid_skills=True` in registration
3. Review MCP server logs for registration errors

## Future Enhancements

Planned improvements to the skill system:

1. **Skill Composition** - Combine multiple skills into workflows
2. **Skill Learning** - Track success rates and improve matching
3. **Skill Aliases** - Custom names for skill combinations
4. **Skill Versioning** - Support multiple skill versions
5. **Cross-Project Skills** - Share skills between projects
6. **Skill Marketplace** - Community-contributed skills

## Contributing

To add new skills:

1. **For Agent Skills**: Create new `SubAgent` subclass
2. **For MCP Skills**: Add to `MCP_SKILL_GROUPS` dictionary
3. **For Hybrid Skills**: Register in `register_all_hybrid_skills()`

See `tests/skills/` for examples and test patterns.

## References

- **Agent System**: `crackerjack/agents/`
- **MCP Server**: `crackerjack/mcp/`
- **Skill Implementation**: `crackerjack/skills/`
- **Tests**: `tests/skills/`

## License

Part of Crackerjack. See project LICENSE for details.
