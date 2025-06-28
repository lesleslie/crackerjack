# Using Crackerjack with AI Agents

Crackerjack provides seamless integration with AI assistants like Claude, ChatGPT, and other LLM-based tools through its dedicated AI agent mode. This document explains how to leverage these features for enhanced AI-assisted Python development.

## AI Agent Mode Overview

AI agent mode transforms Crackerjack's output into structured, machine-readable formats that AI assistants can easily parse and reason about, enabling them to provide more accurate guidance and automation.

### Enabling AI Agent Mode

You can enable AI agent mode by adding the `--ai-agent` flag to any Crackerjack command:

```bash
# Run tests with AI agent mode enabled
python -m crackerjack --ai-agent --test

# Run benchmark tests with AI agent mode
python -m crackerjack --ai-agent --test --benchmark

# Run benchmark regression tests with AI agent mode
python -m crackerjack --ai-agent --test --benchmark-regression

# Run benchmark regression tests with custom threshold (10%)
python -m crackerjack --ai-agent --test --benchmark-regression --benchmark-regression-threshold=10.0

# Run a full development cycle with AI agent mode
python -m crackerjack --ai-agent -a minor
```

### Key Benefits

When AI agent mode is enabled, Crackerjack:

1. Outputs results in structured JSON format for reliable parsing
2. Provides clear status indicators for each operation (running, success, failed)
3. Includes detailed action tracking to help AI assistants understand the workflow
4. Reduces noise and formats output specifically for machine consumption
5. Generates machine-readable output files for test results, coverage, and benchmarks

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
    output_format="json"  # Ensure JSON output even for non-AI-agent operations
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
        text=True
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
                    "status": "failed" if case.find("failure") is not None else "passed"
                }
                for case in root.findall(".//testcase")
            ]
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
        "structured_data": structured_data
    }
```

## AI-Assisted Development Workflows

Crackerjack's AI agent mode enables powerful workflows for AI-assisted development:

### Code Quality Improvement

1. **AI Analysis**: AI assistant analyzes code and suggests improvements
2. **Targeted Execution**: `python -m crackerjack --ai-agent --clean`
3. **Structured Feedback**: AI parses results to identify which files were modified
4. **Intelligent Review**: AI explains the changes made and why they improve the code

### Test-Driven Development

1. **Test Creation**: AI helps write tests for new functionality
2. **Verification**: `python -m crackerjack --ai-agent --test -s`
3. **Structured Analysis**: AI parses `test-results.xml` and `coverage.json` files for detailed insights
4. **Failure Analysis**: AI analyzes test failures from JUnit XML with precise file locations and error details
5. **Coverage-Driven Implementation**: AI uses coverage data to identify untested code paths and suggest implementation priorities
6. **Implementation Guidance**: AI provides targeted implementation advice based on structured test results

### Continuous Improvement

1. **Project Scan**: `python -m crackerjack --ai-agent --verbose`
2. **Opportunity Identification**: AI analyzes output to find improvement opportunities
3. **Recommendation**: AI suggests specific improvements with rationale
4. **Implementation**: AI assists with implementing the suggested changes

These workflows demonstrate how Crackerjack's structured output enables AI assistants to provide more contextual, accurate, and helpful guidance throughout the development process.

## Future Directions

The integration between Crackerjack and AI assistants continues to evolve. Future enhancements may include:

- **Semantic Code Understanding**: Providing AI-friendly representations of code structure
- **Contextual Suggestions**: Enabling AI to make more targeted recommendations based on project context
- **Interactive Workflows**: Supporting multi-step AI-guided processes with feedback loops
- **Custom AI Plugins**: Allowing developers to create specialized AI integrations for Crackerjack

## Conclusion

Crackerjack's AI agent integration represents a step toward more intelligent, context-aware development tools. By providing structured, machine-readable output, Crackerjack enables AI assistants to better understand your Python projects and provide more valuable assistance.

Whether you're using AI to help with code reviews, test development, or project maintenance, Crackerjack's AI agent mode provides the structured data needed for AI tools to deliver meaningful insights and recommendations.

For questions, suggestions, or contributions to Crackerjack's AI integration features, please open an issue or pull request on the [GitHub repository](https://github.com/lesleslie/crackerjack).
