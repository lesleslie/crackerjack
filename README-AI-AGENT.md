# Using Crackerjack with AI Agents

Crackerjack provides seamless integration with AI assistants like Claude, ChatGPT, and other LLM-based tools through its dedicated AI agent mode. This document explains how to leverage these features for enhanced AI-assisted Python development.

## AI Agent Mode Overview

AI agent mode provides **intelligent, iterative code fixing** that goes far beyond structured output. The AI agent automatically detects issues, applies fixes, and validates results through multiple iterations until code quality is achieved.

### Core AI Agent Workflow

**CRITICAL**: The AI agent follows a strict iteration protocol to ensure fixes are properly applied and validated:

1. **Fast Hooks** (Formatting) → Retry once if any fail
1. **Collect ALL Test Failures** → Don't stop on first failure
1. **Collect ALL Hook Issues** → Don't stop on first failure
1. **Apply AI Fixes** → Process all collected issues in batch
1. **Validate in Next Iteration** → Repeat until all checks pass (max 10 iterations)

This ensures that **fixes are applied between iterations**, not just the same checks repeated.

### Specialized Sub-Agent Architecture

Crackerjack includes **9 specialized sub-agents** that automatically detect and fix different types of code quality issues:

#### Performance & Code Quality Agents

- **PerformanceAgent**: Automatically optimizes performance anti-patterns

  - Transforms `list += [item]` → `list.append(item)`
  - Optimizes string concatenation → list.append + join patterns
  - Detects and comments on nested loops and expensive operations

- **RefactoringAgent**: Reduces complexity and removes dead code

  - Breaks down complex functions (cognitive complexity ≤15)
  - Removes unused imports, variables, and functions
  - Extracts common patterns into reusable utilities

- **DRYAgent**: Eliminates code duplication

  - Detects duplicate code patterns
  - Suggests extracting common functionality
  - Recommends base classes and mixins

#### Specialized Fix Agents

- **DocumentationAgent**: Maintains documentation consistency and changelogs

  - Auto-generates changelog entries from git commits during version bumps
  - Ensures consistent agent counts and references across all .md files
  - Updates README examples when APIs change
  - Integrates with publish workflow for automatic documentation updates

- **SecurityAgent**: Fixes security vulnerabilities

  - Removes hardcoded paths and unsafe operations
  - Applies security best practices

- **ImportOptimizationAgent**: Optimizes import statements

  - Consolidates and reorganizes imports
  - Removes unused imports and dead code

- **FormattingAgent**: Handles code style and formatting

- **TestCreationAgent**: Fixes test failures and improves coverage

- **TestSpecialistAgent**: Manages complex testing scenarios

#### Automatic Code Transformation

These agents don't just provide recommendations—they **actually modify your code** to fix issues automatically, similar to how advanced IDEs apply quick fixes. The AI coordination system routes issues to the most appropriate agent based on confidence scoring.

### Enabling AI Agent Mode

**Recommended AI Agent Workflow:**

```bash
# Standard AI agent mode with iterative fixing and testing (RECOMMENDED)
python -m crackerjack --ai-agent -t

# AI agent mode with full debugging output
python -m crackerjack --ai-debug -t

# Other AI agent commands
python -m crackerjack --ai-agent --test --benchmark
python -m crackerjack --ai-agent -a minor
```

### MCP Server Integration

**For real-time progress monitoring and enhanced AI integration:**

```bash
# Step 1: Start WebSocket progress server (separate terminal)
python -m crackerjack --start-websocket-server

# Step 2: Use MCP tools in Claude with `/crackerjack:run`
# Progress available at: ws://localhost:8675/ws/progress/{job_id}
```

**Available MCP Tools:**

- `execute_crackerjack`: Start iterative auto-fixing workflow
- `get_job_progress`: Get current progress for running jobs
- `get_comprehensive_status`: Get complete system status

### Key Benefits

When AI agent mode is enabled, Crackerjack:

1. **Intelligent Code Fixing**: Automatically applies fixes between iterations (not just detects issues)
1. **Iterative Validation**: Each iteration validates fixes from the previous iteration
1. **Batch Processing**: Collects ALL issues before applying fixes (no early exit on first failure)
1. **Real-time Progress**: WebSocket-based progress monitoring with iteration boundaries
1. **Structured Output**: JSON format for reliable AI assistant parsing
1. **Comprehensive Coverage**: Tests + hooks + quality checks in coordinated workflow

## AI Agent Iteration Protocol

### How the Iteration Workflow Works

The AI agent follows a **strict sequence** in each iteration:

```
Iteration 1:
├── Fast Hooks (formatting) → Retry if needed
├── Collect ALL test failures (don't stop on first)
├── Collect ALL hook issues (don't stop on first)
├── Apply AI fixes for ALL collected issues
└── Move to Iteration 2

Iteration 2:
├── Fast Hooks → Validate previous fixes worked
├── Collect remaining test failures
├── Collect remaining hook issues
├── Apply AI fixes for remaining issues
└── Continue until success or max iterations (10)
```

### Critical Success Factors

- **No Early Exit**: Issues are collected completely before fixing
- **Batch Fixing**: All issues processed together for optimal results
- **Fix Validation**: Next iteration proves previous fixes worked
- **Progress Boundaries**: Clear iteration boundaries for monitoring

### Workflow Implementation

This iteration logic is implemented in:

- `AsyncWorkflowOrchestrator._execute_ai_agent_workflow_async()`
- Used automatically when `--ai-agent` flag is enabled
- Compatible with MCP server WebSocket progress reporting

## Structured Output Format

Crackerjack's AI agent mode produces both console output and structured files that AI assistants can easily parse and analyze.

### Generated Output Files

When running tests with `--ai-agent`, Crackerjack automatically generates the following machine-readable files:

- **`test-results.xml`**: JUnit XML format test results with detailed test outcomes, timing, and failure information
- **`coverage.json`**: JSON coverage report with line-by-line coverage data and summary statistics
- **`benchmark.json`**: Benchmark results in JSON format (when `--benchmark` or `--benchmark-regression` is used)

These files enable AI assistants to:

- Parse test results programmatically without regex parsing of console output
- Access detailed coverage information for each source file
- Analyze benchmark performance data and trends
- Generate targeted recommendations based on test failures and coverage gaps

#### Example Console Output

When tests complete in AI agent mode, Crackerjack displays the generated file locations:

```
✅ Tests passed successfully!

📄 Structured test results: test-results.xml
📊 Coverage report: coverage.json
⏱️  Benchmark results: benchmark.json
```

This clear indication helps AI assistants locate and process the structured data files.

### Console Output Schema

In addition to the generated files, Crackerjack's AI agent mode produces a series of JSON objects that follow a consistent schema, making it easy for AI assistants to track progress and understand results.

### Operation Status Updates

During execution, Crackerjack emits status updates for each operation:

```json
{"status": "running", "action": "tests", "timestamp": "2025-05-10T14:32:15Z"}
```

### Operation Results

When an operation completes, Crackerjack reports the outcome:

#### Success Example

```json
{
  "status": "success",
  "action": "tests",
  "duration": 3.42,
  "details": "All 24 tests passed"
}
```

#### Failure Example

```json
{
  "status": "failed",
  "action": "tests",
  "returncode": 1,
  "error": "Test failures in test_validation.py",
  "duration": 2.18
}
```

### Execution Summary

At the end of all operations, Crackerjack provides a comprehensive summary:

```json
{
  "status": "complete",
  "package": "your_package_name",
  "version": "0.3.2",
  "actions": [
    {"action": "setup_package", "status": "success", "duration": 0.21},
    {"action": "update_project", "status": "success", "duration": 1.54},
    {"action": "run_tests", "status": "success", "duration": 3.42},
    {"action": "run_benchmarks", "status": "success", "duration": 2.18, "details": "All benchmarks passed. Average improvement: 3.2%"},
    {"action": "benchmark_regression", "status": "success", "duration": 1.75, "details": "No significant regressions detected (threshold: 5.0%)"},
    {"action": "clean_code", "status": "success", "duration": 0.87}
  ],
  "total_duration": 9.97,
  "success": true
}
```

This structured format allows AI assistants to:

- Track the progress of long-running operations
- Identify which specific actions succeeded or failed
- Provide targeted assistance based on detailed error information
- Maintain context across multiple commands

## Environment Variables

When AI agent mode is enabled, Crackerjack sets the following environment variables:

- `AI_AGENT=1`: Signals to all components that structured output should be used
- `CRACKERJACK_STRUCTURED_OUTPUT=1`: Enables JSON formatting in all output streams
- `PYTEST_REPORT_FORMAT=json`: Configures pytest to output results in JSON format

These environment variables ensure that all tools in the pipeline produce machine-readable output.

## Programmatic Integration

### Using Crackerjack in AI-Powered Applications

For developers building AI-powered coding assistants or automation tools, Crackerjack provides a clean programmatic API:

```python
import typing as t
from pathlib import Path
from rich.console import Console
from crackerjack import create_crackerjack_runner


class AIAssistantOptions:
    def __init__(self):
        # Enable AI agent mode
        self.ai_agent = True

        # Configure operations
        self.test = True
        self.clean = True
        self.verbose = True

        # Benchmark options
        self.benchmark = False  # Run tests in benchmark mode
        self.benchmark_regression = False  # Fail tests if benchmarks regress
        self.benchmark_regression_threshold = 5.0  # Threshold for regression (%)

        # Other options as needed
        self.skip_hooks = False
        self.no_config_updates = False


# Create a runner with custom output handling
runner = create_crackerjack_runner(
    console=Console(force_terminal=True),
    pkg_path=Path.cwd(),
    python_version="3.13",
    output_format="json",  # Ensure JSON output even for non-AI-agent operations
)

# Process with structured result handling
result = runner.process(AIAssistantOptions())

# Access structured results programmatically
if result.success:
    print(f"All operations completed successfully in {result.total_duration:.2f}s")
    for action in result.actions:
        print(f"- {action.name}: {action.status} ({action.duration:.2f}s)")
else:
    print(f"Operation failed: {result.failed_action.name}")
    print(f"Error: {result.failed_action.error}")
```

### Parsing Crackerjack Output in AI Applications

For AI systems that execute Crackerjack as a subprocess, both the console output and generated files can be easily parsed:

```python
import json
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path


def run_crackerjack_with_ai(command):
    """Run a Crackerjack command and parse the structured output."""
    result = subprocess.run(
        ["python", "-m", "crackerjack", "--ai-agent"] + command.split(),
        capture_output=True,
        text=True,
    )

    # Parse the JSON output lines
    operations = []
    for line in result.stdout.splitlines():
        try:
            data = json.loads(line.strip())
            operations.append(data)
        except json.JSONDecodeError:
            continue

    # The last JSON object is the summary
    summary = operations[-1] if operations else None

    # Parse generated files if they exist
    structured_data = {}

    # Parse JUnit XML test results
    if Path("test-results.xml").exists():
        tree = ET.parse("test-results.xml")
        root = tree.getroot()
        structured_data["test_results"] = {
            "tests": int(root.get("tests", 0)),
            "failures": int(root.get("failures", 0)),
            "errors": int(root.get("errors", 0)),
            "time": float(root.get("time", 0.0)),
            "test_cases": [
                {
                    "name": case.get("name"),
                    "classname": case.get("classname"),
                    "time": float(case.get("time", 0.0)),
                    "status": "failed"
                    if case.find("failure") is not None
                    else "passed",
                }
                for case in root.findall(".//testcase")
            ],
        }

    # Parse JSON coverage report
    if Path("coverage.json").exists():
        with open("coverage.json") as f:
            structured_data["coverage"] = json.load(f)

    # Parse benchmark results
    if Path("benchmark.json").exists():
        with open("benchmark.json") as f:
            structured_data["benchmarks"] = json.load(f)

    return {
        "success": summary.get("success", False) if summary else False,
        "operations": operations,
        "summary": summary,
        "structured_data": structured_data,
    }
```

## AI-Assisted Development Workflows

### Autonomous Code Quality Improvement (Recommended)

**Primary Workflow:**

```bash
python -m crackerjack --ai-agent -t
```

**What Happens:**

1. **Iteration 1-N**: AI agent automatically collects ALL issues (tests + hooks)
1. **Batch Fixing**: AI applies fixes for all collected issues simultaneously
1. **Validation**: Next iteration validates fixes worked and finds remaining issues
1. **Completion**: Process repeats until all quality checks pass (or 10 iterations max)

**Benefits:**

- **Fully Autonomous**: No manual intervention required
- **Intelligent Fixing**: Real code modifications, not just detection
- **Comprehensive**: Handles tests, formatting, security, complexity, typing

### MCP-Enhanced Workflows

**With real-time progress monitoring:**

```bash
# Terminal 1: Start progress server
python -m crackerjack --start-websocket-server

# Terminal 2: Use Claude with /crackerjack:run
# Real-time progress at ws://localhost:8675/ws/progress/{job_id}
```

### Legacy Structured Output Workflows

**For custom AI integrations:**

1. **Structured Analysis**: AI parses `test-results.xml` and `coverage.json`
1. **Failure Analysis**: AI analyzes JUnit XML with precise error details
1. **Coverage-Driven**: AI uses coverage data for implementation priorities
1. **Custom Processing**: AI processes JSON output for specialized workflows

## Future Directions

The integration between Crackerjack and AI assistants continues to evolve. Future enhancements may include:

- **Semantic Code Understanding**: Providing AI-friendly representations of code structure
- **Contextual Suggestions**: Enabling AI to make more targeted recommendations based on project context
- **Interactive Workflows**: Supporting multi-step AI-guided processes with feedback loops
- **Custom AI Plugins**: Allowing developers to create specialized AI integrations for Crackerjack

## Technical Documentation

For developers implementing AI agent integration or debugging workflow issues:

- **[AI-AGENT-RULES.md](AI-AGENT-RULES.md)**: Technical specification of the iteration protocol, implementation details, and error patterns to avoid
- **[RULES.md](RULES.md)**: Complete code quality standards and AI agent integration guidelines
- **[CLAUDE.md](CLAUDE.md)**: Project-specific AI agent configuration and usage patterns

## Conclusion

Crackerjack's AI agent integration represents a significant advancement in intelligent, autonomous code quality improvement. The **iterative fixing protocol** ensures that AI agents don't just detect issues—they actually fix them and validate the results.

Key advantages:

- **Autonomous Operation**: Fixes code without manual intervention
- **Intelligent Validation**: Each iteration proves previous fixes worked
- **Real-time Monitoring**: WebSocket progress tracking for long-running workflows
- **Comprehensive Coverage**: Tests, formatting, security, complexity, and typing

Whether you're using the MCP server integration with Claude or building custom AI tools, Crackerjack's AI agent mode provides the autonomous fixing capabilities needed for maintainable, high-quality Python code.

For questions, suggestions, or contributions to Crackerjack's AI integration features, please open an issue or pull request on the [GitHub repository](https://github.com/lesleslie/crackerjack).
