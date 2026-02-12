# API Reference

Complete API documentation for Crackerjack.

## Protocols

<details>
<summary>Core Protocols</summary>

### ConsoleInterface
Console output protocol with methods for printing, progress bars, and status updates.

### TestManagerProtocol
Test execution protocol managing pytest integration and coverage tracking.

### AgentTrackerProtocol
Agent invocation tracking for skills metrics and recommendations.

</details>

## Services

<details>
<summary>Service Layer</summary>

### VectorStore
Semantic vector storage for AI-powered code search and fix strategies.

**Key Features**:
- SQLite-based vector storage
- FAISS-like similarity search
- Temporary database support

### SessionCoordinator
Session lifecycle management coordinating quality gates, tests, and cleanup.

**Key Features**:
- Lock file management
- Cleanup handler registration
- Thread-safe operations

### DocumentationGenerator
Markdown documentation generation from docstrings and templates.

**Key Features**:
- Template-based rendering
- Docstring extraction
- Multi-format support

</details>

## Managers

<details>
<summary>Manager Layer</summary>

### HookManager
Orchestrates quality tool execution (fast → comprehensive).

### TestManager
Manages pytest execution with parallel workers and coverage tracking.

### WorkflowOrchestrator
Coordinates multi-phase workflows with dependency management.

</details>

## See Also

- [Protocol-Based Design](../architecture/protocols.md)
- [Architecture Documentation](../architecture/layered-design.md)
