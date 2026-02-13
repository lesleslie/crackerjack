______________________________________________________________________

title: Ai Review
owner: Operations Enablement Guild
last_reviewed: 2025-02-06
supported_platforms:

- macOS
- Linux
  required_scripts: []
  risk: medium
  status: active
  id: 01K6EEXCZEJGV8Y9045QEJ8SC9
  category: workflow

______________________________________________________________________

## AI/ML Code Review

Perform a specialized AI/ML code review for: $ARGUMENTS

Conduct comprehensive review focusing on:

1. **Model Code Quality**:

   - Reproducibility checks
   - Random seed management
   - Data leakage detection
   - Train/test split validation
   - Feature engineering clarity

1. **AI Best Practices**:

   - Prompt injection prevention
   - Token limit handling
   - Cost optimization
   - Fallback strategies
   - Timeout management

1. **Data Handling**:

   - Privacy compliance (PII handling)
   - Data versioning
   - Preprocessing consistency
   - Batch processing efficiency
   - Memory optimization

1. **Model Management**:

   - Version control for models
   - A/B testing setup
   - Rollback capabilities
   - Performance benchmarks
   - Drift detection

1. **LLM-Specific Checks**:

   - Context window management
   - Prompt template security
   - Response validation
   - Streaming implementation
   - Rate limit handling

1. **Vector Database Review**:

   - Embedding consistency
   - Index optimization
   - Query performance
   - Metadata management
   - Backup strategies

1. **Production Readiness**:

   - GPU/CPU optimization
   - Batching strategies
   - Caching implementation
   - Monitoring hooks
   - Error recovery

1. **Testing Coverage**:

   - Unit tests for preprocessing
   - Integration tests for pipelines
   - Model performance tests
   - Edge case handling
   - Mocked LLM responses

Provide specific recommendations with severity levels (Critical/High/Medium/Low). Include code examples for improvements and links to relevant best practices.

______________________________________________________________________

## Security Considerations

### Authentication & Authorization

- **SSO Integration**: Use organization SSO (OAuth 2.0, SAML)
- **Role-Based Access**: Implement RBAC for workflow actions
- **MFA Enforcement**: Require multi-factor authentication for sensitive operations

### Audit Logging

- **Comprehensive Logging**: Log all workflow actions and state changes
- **Immutable Audit Trail**: Store logs in tamper-proof storage
- **Log Retention**: Comply with regulatory retention requirements

```python
# Example: Audit logging for workflows
import structlog

audit_logger = structlog.get_logger("audit")


def log_workflow_action(user_id: str, action: str, resource: str, outcome: str):
    audit_logger.info(
        "workflow_action",
        user_id=user_id,
        action=action,
        resource=resource,
        outcome=outcome,
        timestamp=datetime.utcnow().isoformat(),
        ip_address=get_client_ip(),
    )


# Usage
log_workflow_action(
    user_id="user@example.com",
    action="approve_deployment",
    resource="production",
    outcome="success",
)
```

### Secrets in Workflows

- **Secret Management**: Use secure secret storage (Vault, AWS Secrets Manager)
- **Least Privilege**: Grant minimal required permissions
- **Secret Rotation**: Implement automatic rotation for long-running workflows

### Approval Gates

- **Multi-Party Approval**: Require multiple approvers for critical actions
- **Approval Audit Trail**: Log all approval decisions with justifications
- **Time-Limited Approvals**: Expire approvals after defined period

### Communication Security

- **Encrypted Channels**: Use TLS for all API communications
- **Webhook Verification**: Verify webhook signatures (GitHub, Slack)
- **API Rate Limiting**: Protect against abuse

______________________________________________________________________

______________________________________________________________________

## Testing & Validation

### Workflow Execution Testing

```python
# Test workflow stages
def test_deployment_workflow():
    workflow = DeploymentWorkflow()

    # Test each stage independently
    assert workflow.validate_config() == True
    assert workflow.run_tests() == True
    assert workflow.build_artifacts() == True

    # Test full workflow
    result = workflow.execute()
    assert result.status == "success"
    assert result.deployed_version is not None


# Test workflow with failure handling
def test_workflow_handles_test_failure():
    workflow = DeploymentWorkflow()

    with mock.patch.object(workflow, "run_tests", return_value=False):
        result = workflow.execute()

        assert result.status == "failed"
        assert result.failed_stage == "tests"
        assert result.deployed_version is None  # No deployment occurred
```

### Approval Flow Testing

```python
# Test multi-approver workflow
def test_requires_multiple_approvals():
    pr = PullRequest(id=123)

    # First approval - not enough
    pr.approve(user="alice")
    assert pr.status == "pending"
    assert pr.can_merge == False

    # Second approval - sufficient
    pr.approve(user="bob")
    assert pr.status == "approved"
    assert pr.can_merge == True


def test_approval_timeout():
    pr = PullRequest(id=123, approval_timeout_hours=24)

    pr.approve(user="alice")

    # Simulate time passing
    with freeze_time(datetime.now() + timedelta(hours=25)):
        assert pr.approvals_expired == True
        assert pr.can_merge == False
```

### Integration Testing

```python
# Test workflow integrations
@pytest.mark.integration
def test_github_pr_workflow():
    # Create test PR
    pr = github_client.create_pull_request(
        repo="test/repo", title="Test PR", head="feature", base="main"
    )

    # Trigger workflow
    workflow.on_pr_created(pr)

    # Verify actions taken
    assert github_client.get_pr_labels(pr.number) == ["automated-test"]
    assert github_client.get_pr_assignees(pr.number) == ["reviewer-bot"]

    # Cleanup
    github_client.close_pull_request(pr.number)
```

### Notification Testing

```python
# Test notifications sent correctly
def test_slack_notification_on_deployment():
    with mock.patch("slack_client.post_message") as mock_slack:
        deploy_workflow.execute(version="v1.2.3")

        mock_slack.assert_called_once()
        call_args = mock_slack.call_args[1]

        assert call_args["channel"] == "#deployments"
        assert "v1.2.3" in call_args["text"]
        assert "success" in call_args["text"].lower()
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
