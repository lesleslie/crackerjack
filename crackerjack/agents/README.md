> Crackerjack Docs: [Main](<../../README.md>) | [CLAUDE.md](<../../CLAUDE.md>) | [Agents](<./README.md>)

# Agents

Specialized AI agents for autonomous code quality improvement and intelligent refactoring.

## Overview

The agents package contains 12 specialized AI agents that work together to automatically fix code quality issues, improve architecture, and maintain high standards. Each agent focuses on a specific domain (security, performance, documentation, etc.) with confidence-based routing and collaborative problem-solving.

## Core Components

### Coordination & Infrastructure

- **AgentCoordinator**: Routes issues to appropriate specialized agents based on confidence scoring
- **EnhancedAgentCoordinator**: Advanced coordinator with batch processing and collaborative agent modes
- **AgentRegistry**: Central registry for agent discovery and metadata
- **AgentTracker**: Tracks agent activities, success rates, and performance metrics
- **AgentContext**: Dataclass-based context for agent isolation (legacy pattern, predates ACB)
- **BaseAgent**: Abstract base class providing common agent functionality

### Specialized Agents

#### Code Quality Agents

- **RefactoringAgent** (confidence: 0.9)

  - Reduces complexity ≤15 per function
  - Extracts helper methods using SOLID principles
  - Removes dead code and unused variables
  - Primary focus: KISS and DRY principles

- **FormattingAgent** (confidence: 0.8)

  - Code style and import organization
  - Handles ruff, black, isort violations
  - Enforces consistent formatting standards

- **DRYAgent** (confidence: 0.8)

  - Eliminates code duplication
  - Extracts common patterns to utilities
  - Identifies repeated logic across modules

- **ImportOptimizationAgent**

  - Removes unused imports
  - Restructures import statements
  - Optimizes import organization

#### Security & Performance

- **SecurityAgent** (confidence: 0.8)

  - Fixes shell injection vulnerabilities
  - Replaces weak cryptography (MD5/SHA1 → SHA256)
  - Removes insecure random functions
  - Detects unsafe YAML/library usage
  - Masks tokens and credentials

- **PerformanceAgent** (confidence: 0.85)

  - Detects O(n²) patterns and inefficient algorithms
  - Optimizes string building and list concatenation
  - Improves loop efficiency
  - Identifies performance bottlenecks

#### Testing & Documentation

- **TestCreationAgent** (confidence: 0.8)

  - Fixes test failures and missing fixtures
  - Handles dependency issues in tests
  - Improves test coverage

- **TestSpecialistAgent** (confidence: 0.8)

  - Advanced testing scenarios
  - Complex fixture management
  - Integration test patterns

- **DocumentationAgent** (confidence: 0.8)

  - Auto-generates changelogs
  - Maintains .md file consistency
  - Updates documentation with code changes

#### Advanced Intelligence

- **SemanticAgent** (confidence: 0.85)

  - Advanced semantic analysis
  - Code comprehension and context understanding
  - Intelligent refactoring based on business logic
  - Deep code pattern recognition

- **ArchitectAgent** (confidence: 0.85)

  - High-level architectural patterns
  - Design recommendations
  - System-level optimization strategies
  - Cross-module refactoring guidance

- **EnhancedProactiveAgent** (confidence: 0.9)

  - Proactive issue prevention
  - Predictive quality monitoring
  - Preemptive optimization
  - Pattern-based early detection

### Support Infrastructure

- **ClaudeCodeBridge**: Integration with Claude Code via MCP for enhanced AI workflows
- **ErrorMiddleware**: Error handling and retry logic for agent operations
- **Helper Modules**:
  - `performance_helpers.py`: Performance analysis utilities
  - `refactoring_helpers.py`: Refactoring support functions
  - `semantic_helpers.py`: Semantic analysis tools

## Architecture

### AgentContext Pattern (Legacy)

Agents currently use the `AgentContext` dataclass pattern which predates ACB adoption:

```python
@dataclass
class AgentContext:
    project_root: Path
    cache: CrackerjackCache
    console: Console
    settings: CrackerjackSettings
    # ... other context fields
```

**Note:** Phase 4 protocols defined for future migration to ACB dependency injection, but not yet prioritized as agents work well with current pattern.

### Confidence-Based Routing

Issues are routed to agents based on confidence scores (threshold: ≥0.7):

```python
# High-confidence routing
if confidence >= 0.9:
    agent = RefactoringAgent()  # For complexity issues
elif confidence >= 0.85:
    agent = PerformanceAgent()  # For performance issues
```

### Collaborative Mode

Multiple agents can work together on complex cross-cutting concerns:

```python
# Security + Refactoring collaboration
security_fixes = SecurityAgent().analyze(code)
refactored = RefactoringAgent().apply(security_fixes)
```

## Usage

### Via CLI (Recommended)

```bash
# Enable AI auto-fixing with all agents
python -m crackerjack --ai-fix --run-tests

# Debug mode for agent analysis
python -m crackerjack --ai-debug --run-tests
```

### Programmatic Usage

```python
from crackerjack.agents.coordinator import AgentCoordinator
from crackerjack.agents import AgentContext

# Create context
context = AgentContext(
    project_root=Path.cwd(),
    cache=cache,
    console=console,
    settings=settings,
)

# Coordinate fixes
coordinator = AgentCoordinator(context)
fixes = await coordinator.process_issues(issues)
```

### Individual Agent Usage

```python
from crackerjack.agents.security_agent import SecurityAgent

agent = SecurityAgent(context)
result = await agent.analyze_security_issue(
    file_path="path/to/file.py",
    issue="Hardcoded secret detected",
    code_context=code,
)
```

## Agent Compliance Status

Based on Phase 2-4 refactoring audit:

| Component | ACB Compliance | Status | Notes |
|-----------|---------------|--------|-------|
| Agent Classes | 40% | 📋 Legacy | Use `AgentContext` pattern (predates ACB) |
| AgentCoordinator | Low | ⚠️ Needs DI | No dependency injection |
| Helper Modules | N/A | ✅ Stable | Functional utilities |
| Future Migration | Planned | 📋 Backlog | Protocols defined for ACB migration |

## Configuration

Agents are configured via `settings/crackerjack.yaml`:

```yaml
# AI agent settings
ai_fix: true
ai_debug: false
max_iterations: 10
confidence_threshold: 0.7

# Agent-specific settings
ai:
  model: claude-sonnet-4-5-20250929
  temperature: 0.1
  max_tokens: 4096
```

## Performance Metrics

Typical agent performance (per iteration):

- **Batch Processing**: Up to 50 issues per iteration
- **Success Rate**: ~85% first-pass fixes
- **Average Time**: 2-5 seconds per issue
- **Confidence Accuracy**: 92% when threshold ≥0.7

## Best Practices

1. **Start with `--ai-fix`**: Let coordinator route to appropriate agents
1. **Use `--ai-debug`**: Enable detailed logging for troubleshooting
1. **Review Changes**: AI fixes should be reviewed before committing
1. **Iterate Gradually**: Default 10 iterations prevents infinite loops
1. **Trust High Confidence**: Fixes with confidence ≥0.85 are typically safe

## Related

- [Adapters](<../adapters/README.md>) — Quality tools that agents fix issues from
- [Orchestration](<../orchestration/README.md>) — Workflow coordination layer
- [MCP](<../mcp/README.md>) — Model Context Protocol integration
- [AGENTS.md](<../../AGENTS.md>) — Repository guidelines for agent development
- [CLAUDE.md](<../../CLAUDE.md>) — AI agent system overview

## Future Enhancements

- [ ] Migrate to ACB dependency injection (Phase 5+)
- [ ] Implement agent learning from successful fixes
- [ ] Add agent-specific telemetry and metrics
- [ ] Develop agent benchmarking framework
- [ ] Cross-agent pattern sharing and collaboration
