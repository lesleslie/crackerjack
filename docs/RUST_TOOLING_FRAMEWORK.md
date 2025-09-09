# Shared Rust Tooling Framework Design

## Overview

Unified framework for integrating Rust-based tools (Skylos, Zuban) into Crackerjack with shared infrastructure, error handling, and output parsing.

## Architecture

### Core Components

```python
# Base adapter for all Rust tools
class RustToolAdapter(Protocol):
    """Protocol for Rust-based analysis tools."""

    def __init__(self, context: ExecutionContext) -> None: ...
    def get_command_args(self, target_files: list[Path]) -> list[str]: ...
    def parse_output(self, output: str) -> ToolResult: ...
    def supports_json_output(self) -> bool: ...
    def get_tool_version(self) -> str | None: ...
```

### Tool Implementations

#### Skylos Adapter (Dead Code Detection)

```python
@dataclass
class SkylsAdapter(RustToolAdapter):
    """Skylos dead code detection adapter."""

    confidence_threshold: int = 86
    web_dashboard_port: int = 5090

    def get_command_args(self, target_files: list[Path]) -> list[str]:
        args = ["uv", "run", "skylos", "--confidence", str(self.confidence_threshold)]

        # Add JSON mode for AI agents
        if self.context.ai_agent_mode or self.context.ai_debug_mode:
            args.append("--json")

        # Add web dashboard for interactive mode
        if self.context.interactive:
            args.extend(["--web", "--port", str(self.web_dashboard_port)])

        args.extend(str(f) for f in target_files)
        return args

    def parse_output(self, output: str) -> ToolResult:
        if self.context.ai_agent_mode or self.context.ai_debug_mode:
            return self._parse_json_output(output)
        return self._parse_text_output(output)

    def _parse_json_output(self, output: str) -> ToolResult:
        """Parse JSON output for AI agents."""
        try:
            data = json.loads(output)
            issues = []
            for item in data.get("dead_code", []):
                issues.append(
                    DeadCodeIssue(
                        file_path=Path(item["file"]),
                        line_number=item["line"],
                        issue_type=item["type"],
                        name=item["name"],
                        confidence=item.get("confidence", 0.0),
                    )
                )
            return ToolResult(
                success=len(issues) == 0, issues=issues, raw_output=output
            )
        except json.JSONDecodeError as e:
            return ToolResult(
                success=False,
                error=f"Invalid JSON output from Skylos: {e}",
                raw_output=output,
            )
```

#### Zuban Adapter (Type Checking)

```python
@dataclass
class ZubanAdapter(RustToolAdapter):
    """Zuban type checking adapter."""

    strict_mode: bool = True
    mypy_compatibility: bool = True

    def get_command_args(self, target_files: list[Path]) -> list[str]:
        args = ["uv", "run", "zuban"]

        # Mode selection
        if self.mypy_compatibility:
            args.append("zmypy")  # MyPy-compatible mode
        else:
            args.append("check")  # Native Zuban mode

        # Strictness
        if self.strict_mode:
            args.append("--strict")

        # JSON output for AI agents
        if self.context.ai_agent_mode or self.context.ai_debug_mode:
            args.append("--output-format=json")

        # Target files/directories
        if target_files:
            args.extend(str(f) for f in target_files)
        else:
            args.append(".")  # Check entire project

        return args

    def parse_output(self, output: str) -> ToolResult:
        if self.context.ai_agent_mode or self.context.ai_debug_mode:
            return self._parse_json_output(output)
        return self._parse_text_output(output)

    def _parse_json_output(self, output: str) -> ToolResult:
        """Parse JSON output for AI agents."""
        try:
            data = json.loads(output)
            issues = []
            for item in data.get("diagnostics", []):
                issues.append(
                    TypeIssue(
                        file_path=Path(item["file"]),
                        line_number=item["line"],
                        column=item.get("column", 0),
                        severity=item["severity"],
                        message=item["message"],
                        error_code=item.get("code"),
                    )
                )
            return ToolResult(
                success=len([i for i in issues if i.severity == "error"]) == 0,
                issues=issues,
                raw_output=output,
            )
        except json.JSONDecodeError as e:
            return ToolResult(
                success=False,
                error=f"Invalid JSON output from Zuban: {e}",
                raw_output=output,
            )
```

### Unified Hook Manager

```python
class RustToolHookManager:
    """Manages Rust tool execution within Crackerjack hooks."""

    def __init__(self, context: ExecutionContext) -> None:
        self.context = context
        self.adapters: dict[str, RustToolAdapter] = {
            "skylos": SkylsAdapter(context),
            "zuban": ZubanAdapter(context),
        }

    async def execute_tool(
        self, tool_name: str, target_files: list[Path]
    ) -> ToolResult:
        """Execute a Rust tool with unified error handling."""
        adapter = self.adapters.get(tool_name)
        if not adapter:
            raise ValueError(f"Unknown Rust tool: {tool_name}")

        try:
            # Get command arguments
            args = adapter.get_command_args(target_files)

            # Execute with timeout and error handling
            result = await self._run_with_timeout(args, timeout=300)

            # Parse output using adapter
            return adapter.parse_output(result.stdout)

        except subprocess.TimeoutExpired:
            return ToolResult(
                success=False,
                error=f"{tool_name} execution timed out after 300 seconds",
            )
        except Exception as e:
            return ToolResult(
                success=False, error=f"Failed to execute {tool_name}: {e}"
            )

    async def _run_with_timeout(
        self, args: list[str], timeout: int
    ) -> subprocess.CompletedProcess:
        """Run command with timeout and proper error handling."""
        process = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=self.context.project_root,
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=timeout
            )

            return subprocess.CompletedProcess(
                args=args,
                returncode=process.returncode or 0,
                stdout=stdout.decode("utf-8"),
                stderr=stderr.decode("utf-8"),
            )

        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            raise subprocess.TimeoutExpired(args, timeout)
```

### Data Models

```python
@dataclass
class ToolResult:
    """Unified result format for all Rust tools."""

    success: bool
    issues: list[Issue] = field(default_factory=list)
    error: str | None = None
    raw_output: str = ""
    execution_time: float = 0.0
    tool_version: str | None = None


@dataclass
class Issue:
    """Base class for tool issues."""

    file_path: Path
    line_number: int
    message: str
    severity: str = "error"


@dataclass
class DeadCodeIssue(Issue):
    """Skylos dead code detection issue."""

    issue_type: str  # "import", "function", "class", etc.
    name: str
    confidence: float


@dataclass
class TypeIssue(Issue):
    """Zuban type checking issue."""

    column: int
    error_code: str | None = None
```

## Integration Points

### Hook Configuration Updates

```python
# dynamic_config.py updates
RUST_TOOLS = {
    "skylos": {
        "id": "skylos",
        "adapter_class": "SkylsAdapter",
        "repo": "https://github.com/duriantaco/skylos",
        "tier": 3,
        "timeout": 120,
        "file_patterns": ["*.py"],
    },
    "zuban": {
        "id": "zuban",
        "adapter_class": "ZubanAdapter",
        "repo": "https://github.com/zubanls/zuban",
        "tier": 3,
        "timeout": 300,
        "file_patterns": ["*.py"],
    },
}
```

### Error Handling Strategy

1. **Graceful Degradation**: Fall back to text parsing if JSON fails
1. **Timeout Management**: Configurable timeouts per tool
1. **Version Compatibility**: Check tool versions and compatibility
1. **Resource Management**: Proper cleanup of subprocesses

### Testing Framework

```python
class RustToolTestBase:
    """Base test class for Rust tool adapters."""

    def setup_mock_context(self) -> ExecutionContext:
        """Create mock execution context."""
        return ExecutionContext(
            ai_agent_mode=False,
            ai_debug_mode=False,
            interactive=False,
            project_root=Path("/tmp/test_project"),
        )

    def create_sample_output(self, tool_name: str) -> str:
        """Create sample tool output for testing."""
        # Implementation specific to each tool
        pass

    def test_command_generation(self):
        """Test command argument generation."""
        pass

    def test_output_parsing(self):
        """Test output parsing for both text and JSON modes."""
        pass

    def test_error_handling(self):
        """Test error handling and edge cases."""
        pass
```

## Benefits

1. **Code Reuse**: 40% reduction in implementation time through shared components
1. **Consistent API**: Uniform interface for all Rust tools
1. **Easier Testing**: Unified testing framework for all adapters
1. **Maintainability**: Single place for error handling and output parsing logic
1. **Extensibility**: Easy to add new Rust tools following the same pattern

## Implementation Phases

1. **Phase 1**: Create base `RustToolAdapter` protocol and `ToolResult` models
1. **Phase 2**: Implement `SkylsAdapter` and `ZubanAdapter`
1. **Phase 3**: Create `RustToolHookManager` with unified execution
1. **Phase 4**: Update hook configurations to use new adapters
1. **Phase 5**: Comprehensive testing and integration

This framework enables the 40% time savings identified in the consolidation plan by sharing infrastructure between Skylos and Zuban implementations.
