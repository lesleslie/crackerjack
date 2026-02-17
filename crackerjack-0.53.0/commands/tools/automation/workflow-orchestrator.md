______________________________________________________________________

title: Workflow Orchestrator
owner: Automation Guild
last_reviewed: 2025-02-06
supported_platforms:

- macOS
- Linux
  required_scripts: []
  risk: medium
  status: active
  id: 01K6EEXBHJWEGWP6CKNXGW4D1B
  category: automation

______________________________________________________________________

## Workflow Orchestrator

Cross-application workflow automation with window management and command coordination:

[Extended thinking: This tool wraps workflow_orchestrator.py to provide complex workflow coordination across multiple applications and windows. It combines window switching, prompting, and command execution for seamless automation workflows.]

## Workflow Orchestration Overview

Orchestrate complex workflows that span multiple applications, windows, and command executions with intelligent coordination.

**Core Orchestration Capabilities:**

```python
ORCHESTRATOR_FEATURES = {
    "window_management": "Switch between iTerm2 windows and tabs",
    "command_coordination": "Execute commands across multiple contexts",
    "workflow_prompting": "Native prompt system for user interaction",
    "state_preservation": "Maintain context across workflow steps",
}
```

## Orchestration Operations

### 1. Cross-Application Workflow Execution

**Command:** `python ~/.claude/automation-tools/workflow_orchestrator.py --workflow-name "$WORKFLOW_NAME"`

**Functionality:**

- **Window Coordination**: Intelligently switch between iTerm2 windows and tabs
- **Command Execution**: Execute commands in specific application contexts
- **User Interaction**: Native prompt system for workflow decisions
- **State Management**: Preserve workflow state across execution steps

**Workflow Configuration:**

```python
workflow_config = {
    "workflow_name": "$WORKFLOW_NAME",
    "execution_context": {
        "target_application": "iTerm2",
        "window_management": True,
        "prompt_integration": True,
    },
    "coordination_settings": {
        "preserve_original_location": True,
        "verification_enabled": True,
        "error_handling": "graceful_fallback",
    },
}
```

### 2. Multi-Window Development Workflows

**Usage Pattern:**

```bash
# Coordinate development across multiple terminal windows
python ~/.claude/automation-tools/workflow_orchestrator.py \
    --workflow-type "development" \
    --target-windows "main,testing,deployment" \
    --preserve-context
```

**Development Workflow Automation:**

- **Code Development**: Execute commands in development window
- **Testing Coordination**: Run tests in dedicated testing window
- **Deployment Management**: Handle deployment in separate window
- **Context Switching**: Seamlessly move between workflow phases

### 3. Interactive Workflow Management

**Command Pattern:**

```bash
# Interactive workflow with user prompts
python ~/.claude/automation-tools/workflow_orchestrator.py \
    --interactive-mode \
    --workflow-config "$ARGUMENTS" \
    --enable-prompting
```

**Interactive Features:**

- **Native Prompts**: macOS native dialog system for user input
- **Decision Points**: Strategic pauses for user decisions
- **Workflow Branching**: Different paths based on user choices
- **Progress Feedback**: Visual feedback on workflow progress

## Integration with Claude Ecosystem

### MCP Server Coordination

**Workflow Integration Points:**

```python
mcp_integration = {
    "session_mgmt": "Coordinate with session lifecycle events",
    "crackerjack": "Integrate with code quality automation phases",
    "monitoring": "Feed workflow metrics to analytics systems",
    "context_preservation": "Maintain state across MCP server operations",
}
```

### Automation Workflow Patterns

#### 1. Development Session Orchestration

```bash
# Comprehensive development session setup
python ~/.claude/automation-tools/workflow_orchestrator.py \
    --workflow "dev-session-setup" \
    --project "$PROJECT_NAME" \
    --include-testing \
    --enable-monitoring
```

**Orchestration Steps:**

1. **Environment Preparation**: Set up development windows and contexts
1. **Project Initialization**: Load project-specific configurations
1. **Tool Coordination**: Integrate with MCP servers and monitoring
1. **Workflow Monitoring**: Track progress and provide feedback

#### 2. Code Review Workflow Coordination

```bash
# Coordinate code review across multiple applications
python ~/.claude/automation-tools/workflow_orchestrator.py \
    --workflow "code-review" \
    --pr-context "$PR_URL" \
    --coordinate-browser \
    --enable-notifications
```

**Review Coordination:**

1. **Browser Management**: Open PR and related documentation
1. **Terminal Coordination**: Checkout branch and run tests
1. **Editor Integration**: Open changed files for review
1. **Communication**: Coordinate with team chat and notifications

#### 3. Deployment Pipeline Orchestration

```bash
# Orchestrate deployment across environments
python ~/.claude/automation-tools/workflow_orchestrator.py \
    --workflow "deployment" \
    --environment "$TARGET_ENV" \
    --enable-verification \
    --rollback-capable
```

**Deployment Coordination:**

1. **Pre-deployment**: Run comprehensive testing and validation
1. **Deployment Execution**: Coordinate deployment across environments
1. **Verification**: Monitor deployment success and health checks
1. **Post-deployment**: Update documentation and notify stakeholders

## Advanced Orchestration Features

### Window State Management

**Intelligent Window Coordination:**

```python
window_management = {
    "state_preservation": "Remember original window/tab locations",
    "context_switching": "Switch between workflow contexts seamlessly",
    "restoration": "Return to original state after workflow completion",
    "error_recovery": "Handle window management errors gracefully",
}
```

### Workflow Verification

**Built-in Verification System:**

```python
verification_features = {
    "command_verification": "Verify commands executed successfully",
    "state_validation": "Validate workflow state transitions",
    "error_detection": "Detect and handle workflow errors",
    "rollback_support": "Support workflow rollback on failures",
}
```

### Native Integration

**macOS Integration:**

```python
native_integration = {
    "applescript_coordination": "Native AppleScript for application control",
    "notification_system": "macOS notification center integration",
    "dialog_system": "Native dialog prompts for user interaction",
    "accessibility_support": "Accessibility API for reliable automation",
}
```

## Configuration and Customization

### Workflow Configuration Files

```json
{
    "workflow_orchestrator": {
        "default_application": "iTerm2",
        "verification_enabled": true,
        "native_prompts": true,
        "error_handling": "interactive",
        "context_preservation": true
    },
    "window_management": {
        "switch_delay": 0.5,
        "verification_timeout": 5.0,
        "restore_original_location": true
    }
}
```

### Integration Requirements

**Dependencies:**

- **iTerm2**: Primary terminal application for window management
- **AppleScript**: Native macOS automation scripting
- **Native Prompt System**: Custom prompt system for user interaction
- **Accessibility Permissions**: Required for reliable window management

**Security Considerations:**

- **Accessibility Permissions**: Required for window control
- **AppleScript Permissions**: Needed for application automation
- **Sandboxed Execution**: Runs with appropriate security boundaries
- **User Confirmation**: Critical actions require user confirmation

## Usage Examples

### Basic Workflow Orchestration

```bash
python ~/.claude/automation-tools/workflow_orchestrator.py \
    --workflow-name "basic-development" \
    --target-context "$ARGUMENTS"
```

### Advanced Multi-Phase Workflow

```bash
python ~/.claude/automation-tools/workflow_orchestrator.py \
    --workflow-config ~/.claude/config/complex-workflow.json \
    --interactive-mode \
    --enable-verification
```

### Integration with MCP Automation

```bash
# Coordinate with crackerjack-mcp server workflow
python ~/.claude/automation-tools/workflow_orchestrator.py \
    --mcp-integration \
    --crackerjack-coordination \
    --session-aware
```

This tool provides comprehensive cross-application workflow orchestration that complements MCP server automation with native macOS integration and intelligent window management.

______________________________________________________________________

## Security Considerations

### Automated Access Control

- **Service Account Security**: Use dedicated service accounts with minimal permissions
- **Credential Management**: Store credentials in secure vaults
- **Access Token Rotation**: Implement automatic token rotation

```python
# Example: Secure service account token retrieval
import hvac


def get_service_account_token(vault_path: str) -> str:
    client = hvac.Client(url=VAULT_URL)
    client.auth.approle.login(role_id=ROLE_ID, secret_id=SECRET_ID)

    secret = client.secrets.kv.v2.read_secret_version(path=vault_path)
    return secret["data"]["data"]["token"]
```

### Automation Approval Workflows

- **Change Approval**: Require approval for automated production changes
- **Dry-Run Mode**: Test automation in read-only mode first
- **Rollback Capabilities**: Implement automatic rollback on failures

### Logging & Monitoring

- **Comprehensive Audit Logs**: Log all automated actions
- **Anomaly Detection**: Alert on unusual automation patterns
- **Rate Limiting**: Prevent runaway automation

### Isolation & Sandboxing

- **Execution Isolation**: Run automation in isolated environments
- **Resource Limits**: Implement CPU/memory limits
- **Network Restrictions**: Limit network access to required endpoints

### Code Security

- **Dependency Scanning**: Scan automation scripts for vulnerabilities
- **Code Review**: Require peer review for automation changes
- **Secret Scanning**: Prevent secrets from being committed (use git-secrets, gitleaks)

______________________________________________________________________

______________________________________________________________________

## Testing & Validation

### Automation Script Testing

```python
# Test automation logic
def test_automated_cleanup():
    # Setup: Create old resources
    create_resource(name="old-1", created_at=days_ago(30))
    create_resource(name="old-2", created_at=days_ago(45))
    create_resource(name="new-1", created_at=days_ago(5))

    # Execute automation
    cleanup_old_resources(age_days=30)

    # Verify old resources deleted, new preserved
    resources = list_resources()
    assert len(resources) == 1
    assert resources[0]["name"] == "new-1"


# Test dry-run mode
def test_dry_run_mode():
    create_resource(name="test-resource")

    result = cleanup_old_resources(age_days=0, dry_run=True)

    # Verify nothing actually deleted
    assert len(list_resources()) == 1

    # But would have been identified
    assert result["would_delete"] == 1
```

### Idempotency Testing

```python
# Test automation is idempotent
def test_automation_idempotent():
    # Run automation twice
    result1 = provision_infrastructure()
    result2 = provision_infrastructure()

    # Second run should be no-op
    assert result1.resources_created == 5
    assert result2.resources_created == 0
    assert result2.status == "already_exists"

    # Final state should be same
    assert get_resource_count() == 5
```

### Error Recovery Testing

```python
# Test automation handles failures gracefully
def test_handles_api_failure():
    with mock.patch("api_client.create_resource") as mock_api:
        mock_api.side_effect = APIException("Service unavailable")

        result = automated_provisioning()

        # Should retry
        assert mock_api.call_count == 3  # Default retry count

        # Should log error
        assert "Service unavailable" in result.error_log

        # Should not leave partial state
        assert get_resource_count() == 0  # Rolled back
```

### Scheduling Testing

```python
# Test cron schedule correctness
from croniter import croniter


def test_automation_schedule():
    schedule = "0 2 * * *"  # Daily at 2 AM

    cron = croniter(schedule, datetime(2025, 1, 1, 0, 0))

    # Verify next runs
    next_run = cron.get_next(datetime)
    assert next_run == datetime(2025, 1, 1, 2, 0)

    next_run = cron.get_next(datetime)
    assert next_run == datetime(2025, 1, 2, 2, 0)
```

______________________________________________________________________

______________________________________________________________________

## Troubleshooting

### Common Issues

**Issue 1: Configuration Errors**

**Symptoms:**

- Tool fails to start or execute
- Missing required parameters
- Invalid configuration values

**Solutions:**

1. Verify all required environment variables are set
1. Check configuration file syntax (YAML, JSON)
1. Review logs for specific error messages
1. Validate file paths and permissions

______________________________________________________________________

**Issue 2: Permission Denied Errors**

**Symptoms:**

- Cannot access files or directories
- Operations fail with permission errors
- Insufficient privileges

**Solutions:**

1. Check file/directory permissions: `ls -la`
1. Run with appropriate user privileges
1. Verify user is in required groups: `groups`
1. Use `sudo` for privileged operations when necessary

______________________________________________________________________

**Issue 3: Resource Not Found**

**Symptoms:**

- "File not found" or "Resource not found" errors
- Missing dependencies
- Broken references

**Solutions:**

1. Verify resource paths are correct (use absolute paths)
1. Check that required files exist before execution
1. Ensure dependencies are installed
1. Review environment-specific configurations

______________________________________________________________________

**Issue 4: Timeout or Performance Issues**

**Symptoms:**

- Operations taking longer than expected
- Timeout errors
- Resource exhaustion (CPU, memory, disk)

**Solutions:**

1. Increase timeout values in configuration
1. Optimize queries or operations
1. Add pagination for large datasets
1. Monitor resource usage: `top`, `htop`, `docker stats`
1. Implement caching where appropriate

______________________________________________________________________

### Getting Help

If issues persist after trying these solutions:

1. **Check Logs**: Review application and system logs for detailed error messages
1. **Enable Debug Mode**: Set `LOG_LEVEL=DEBUG` for verbose output
1. **Consult Documentation**: Review related tool documentation in this directory
1. **Contact Support**: Reach out with:
   - Error messages and stack traces
   - Steps to reproduce
   - Environment details (OS, versions, configuration)
   - Relevant log excerpts

______________________________________________________________________
