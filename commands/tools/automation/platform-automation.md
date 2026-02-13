______________________________________________________________________

title: Platform Automation
owner: Automation Guild
last_reviewed: 2025-02-06
supported_platforms:

- macOS
- Linux
  required_scripts: []
  risk: medium
  status: active
  id: 01K6EEXBC3B1DS9WCRSBVY0SZG
  category: automation

______________________________________________________________________

## Platform-Specific Automation (macOS)

Automate desktop workflows and system integration beyond code development:

[Extended thinking: This tool wraps the reminder_system.py and location_tracker.py toolkits to provide OS-level automation capabilities not available in MCP servers. It focuses on desktop workflow automation, notifications, and system state management.]

## Platform Automation Overview

Use platform-specific toolkits for desktop automation and system integration.

**Automation Categories:**

```python
PLATFORM_CAPABILITIES = {
    "reminder_system": "Smart notifications and scheduling",
    "location_tracking": "Desktop/window/tab state management",
    "workflow_orchestration": "Cross-application automation",
    "system_integration": "macOS-specific feature utilization",
}
```

**Platform Configuration:**

```python
# ~/.claude/toolkits/ configuration
platform_config = {
    "notifications_enabled": True,
    "location_tracking": True,
    "automation_level": "moderate",
    "system_integration": "macos",
}
```

## Reminder System Operations

### Smart Notification Management

**Command:** `python ~/.claude/toolkits/reminder_system.py --create-reminder`

**Functionality:**

- Context-aware development reminders
- Code review and deployment notifications
- Meeting and deadline management
- Task dependency tracking

**Features:**

```python
reminder_types = {
    "code_review": "Remind about pending code reviews",
    "deployment": "Deployment window and rollback reminders",
    "testing": "Test completion and coverage reminders",
    "documentation": "Documentation update notifications",
    "dependencies": "Dependency update and security alerts",
}
```

### Scheduling and Automation

**Command:** `python ~/.claude/toolkits/reminder_system.py --schedule-tasks`

**Functionality:**

- Automated task scheduling based on development cycles
- Smart timing for non-disruptive notifications
- Context-based reminder prioritization
- Integration with calendar systems

## Location Tracking Operations

### Desktop State Management

**Command:** `python ~/.claude/toolkits/location_tracker.py --track-state`

**Functionality:**

- Active application and window tracking
- Development context preservation
- Workspace state snapshots
- Multi-monitor setup management

**State Categories:**

```python
location_states = {
    "active_application": "Currently focused app",
    "window_layout": "Window positions and sizes",
    "workspace_context": "Current project and branch",
    "browser_tabs": "Development-related browser state",
    "editor_sessions": "Code editor state and open files",
}
```

### Context Restoration

**Command:** `python ~/.claude/toolkits/location_tracker.py --restore-context`

**Functionality:**

- Workspace state restoration after interruptions
- Project-specific environment setup
- Browser tab and application positioning
- Development tool configuration loading

## Desktop Workflow Automation

### Cross-Application Coordination

**Integration with automation scripts:**

```bash
# Terminal automation
python ~/.claude/toolkits/workflow_orchestrator.py --automate-iterm

# Browser automation
python ~/.claude/toolkits/workflow_orchestrator.py --manage-browser-tabs

# Development environment setup
python ~/.claude/toolkits/workflow_orchestrator.py --setup-dev-workspace
```

**Automation Patterns:**

- **Morning Setup:** Automatically open development environment
- **Context Switching:** Save/restore state when switching projects
- **End of Day:** Archive work, backup state, cleanup temporary files
- **Meeting Prep:** Minimize distractions, prepare screen sharing

### System Integration Features

#### macOS Notification Center

```python
# Smart notifications with actions
notification_config = {
    "priority_levels": ["low", "normal", "high", "critical"],
    "action_buttons": ["Snooze", "Mark Complete", "Open Project"],
    "sound_profiles": ["silent", "subtle", "urgent"],
    "display_duration": "adaptive",
}
```

#### Shortcuts and Automation

```python
# macOS Shortcuts integration
shortcuts_integration = {
    "development_mode": "Enable Do Not Disturb, open dev tools",
    "code_review_mode": "Open PR browser tabs, enable notifications",
    "presentation_mode": "Clean desktop, start screen recording",
    "focus_mode": "Block distracting apps, enable deep work timer",
}
```

## Integration with Claude Ecosystem

### Workflow Enhancement

1. **Project Initialization:** Automatically setup development environment
1. **Context Preservation:** Maintain state across development sessions
1. **Smart Notifications:** Development-aware reminder system
1. **Automation Triggers:** React to development events and milestones

### Data Integration

- **Session Context:** Coordinate with session-mgmt-mcp for project state
- **Code Quality Events:** React to crackerjack-mcp quality milestones
- **Analytics Integration:** Feed data to usage analytics for workflow optimization
- **State Persistence:** Maintain development context across system restarts

## Value Beyond MCP Servers

**Unique Capabilities:**

- **OS-Level Automation:** Desktop and system workflow automation
- **Physical Environment Management:** Window management, notifications, state
- **Cross-Application Coordination:** Automate workflows spanning multiple apps
- **System Integration:** Native macOS feature utilization

**Complementary to MCP Servers:**

- MCP servers handle code/session management
- Platform automation manages desktop/system workflow
- Combined: Complete development environment automation

## Usage Examples

### Development Session Setup

```bash
# Automated morning development setup
python ~/.claude/toolkits/workflow_orchestrator.py \
    --setup-dev-session \
    --project "claude-ecosystem" \
    --enable-notifications \
    --restore-context
```

### Smart Reminder Configuration

```bash
# Set up development-aware reminders
python ~/.claude/toolkits/reminder_system.py \
    --configure-reminders \
    --context "development" \
    --priority "high" \
    --integrate-calendar
```

### Context Preservation

```bash
# Save current development state
python ~/.claude/toolkits/location_tracker.py \
    --save-state \
    --include-browser-tabs \
    --include-editor-sessions \
    --project-context "current"
```

## Configuration and Setup

### System Requirements

- **macOS 12.0+** for full notification and automation support
- **Accessibility Permissions** for window management
- **Notification Permissions** for smart reminders
- **Automation Permissions** for cross-app coordination

### Privacy Considerations

- **Local Data Only:** All tracking data stays on local system
- **Opt-in Features:** Each tracking capability requires explicit enable
- **Data Retention:** Configurable retention periods for state data
- **Transparency:** Clear logs of all automation actions

### Security Configuration

- **Sandboxed Execution:** Automation scripts run with limited privileges
- **Permission Validation:** Verify system permissions before operations
- **Audit Trail:** Log all automation actions for security review
- **Fail-Safe Modes:** Graceful degradation when permissions unavailable

This toolkit provides comprehensive desktop automation capabilities that complement your MCP-based development workflow automation with OS-level system integration.

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
