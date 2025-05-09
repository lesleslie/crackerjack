# Using Crackerjack with AI Agents

Crackerjack provides seamless integration with AI assistants like Claude, ChatGPT, and other LLM-based tools through its dedicated AI agent mode. This document explains how to leverage these features for enhanced AI-assisted Python development.

## AI Agent Mode Overview

AI agent mode transforms Crackerjack's output into structured, machine-readable formats that AI assistants can easily parse and reason about, enabling them to provide more accurate guidance and automation.

### Enabling AI Agent Mode

You can enable AI agent mode by adding the `--ai-agent` flag to any Crackerjack command:

```bash
# Run tests with AI agent mode enabled
python -m crackerjack --ai-agent --test

# Run a full development cycle with AI agent mode
python -m crackerjack --ai-agent -a minor
```

### Key Benefits

When AI agent mode is enabled, Crackerjack:

1. Outputs results in structured JSON format for reliable parsing
2. Provides clear status indicators for each operation (running, success, failed)
3. Includes detailed action tracking to help AI assistants understand the workflow
4. Reduces noise and formats output specifically for machine consumption

## Structured Output Format

Crackerjack's AI agent mode produces a series of JSON objects that follow a consistent schema, making it easy for AI assistants to track progress and understand results.

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
    {"action": "clean_code", "status": "success", "duration": 0.87}
  ],
  "total_duration": 6.04,
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

For AI systems that execute Crackerjack as a subprocess, the JSON output can be easily parsed:

```python
import json
import subprocess

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

    return {
        "success": summary.get("success", False) if summary else False,
        "operations": operations,
        "summary": summary
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
3. **Failure Analysis**: AI parses test failures and suggests fixes
4. **Implementation Guidance**: AI provides targeted implementation advice based on test results

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
