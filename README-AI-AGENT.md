# Using Crackerjack with AI Agents

Crackerjack includes special features to make it work better with AI agents like Claude, ChatGPT, and other LLM-based assistants. This document explains how to use these features.

## AI Agent Mode

When working with AI agents, you can enable AI agent mode to get structured output that's easier for the agent to parse:

```bash
python -m crackerjack --ai-agent --test
```

This will:

1. Output results in JSON format that AI agents can easily parse
2. Provide structured information about what actions were performed
3. Reduce unnecessary output that might confuse the agent

## Structured Output Format

In AI agent mode, Crackerjack outputs JSON-formatted results that look like this:

```json
{"status": "running", "action": "tests"}
```

When tests complete, it outputs:

```json
{"status": "success", "action": "tests"}
```

Or if tests fail:

```json
{"status": "failed", "action": "tests", "returncode": 1}
```

At the end of all operations, it outputs a summary:

```json
{
  "status": "complete",
  "package": "your_package_name",
  "actions": ["setup_package", "update_project", "run_tests", ...]
}
```

## Environment Variables

AI agent mode sets the following environment variables:

- `AI_AGENT=1`: Indicates that Crackerjack is being run by an AI agent

## Programmatic Usage with AI Agents

When using Crackerjack programmatically with AI agents, you can enable AI agent mode like this:

```python
from pathlib import Path
from rich.console import Console
from crackerjack import create_crackerjack_runner

class MyOptions:
    def __init__(self):
        self.test = True
        self.ai_agent = True  # Enable AI agent mode
        # Other options...

runner = create_crackerjack_runner(
    console=Console(force_terminal=True),
    pkg_path=Path.cwd()
)
runner.process(MyOptions())
```

## Benefits for AI Agents

The AI agent mode provides several benefits:

1. **Structured Output**: JSON-formatted output is easier for AI agents to parse and understand
2. **Clear Status Indicators**: Clear status indicators (running, success, failed, complete) make it easy to track progress
3. **Action Tracking**: The list of actions performed helps AI agents understand what happened
4. **Reduced Noise**: Less unnecessary output means less confusion for the AI agent

## Example AI Agent Workflow

Here's an example of how an AI agent might use Crackerjack:

1. AI agent suggests running tests on a Python project
2. User or agent runs: `python -m crackerjack --ai-agent --test`
3. Agent receives structured JSON output about test status
4. Agent can parse the output to determine if tests passed or failed
5. Agent can provide appropriate next steps based on the test results

This structured approach makes it easier for AI agents to provide accurate and helpful assistance when working with Python projects.
