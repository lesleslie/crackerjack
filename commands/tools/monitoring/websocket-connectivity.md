______________________________________________________________________

title: Websocket Connectivity
owner: Platform Reliability Guild
last_reviewed: 2025-02-06
supported_platforms:

- macOS
- Linux
  required_scripts: []
  risk: medium
  status: active
  id: 01K6EEXCX1SQH376FZYGBHPCMQ
  category: monitoring

______________________________________________________________________

## WebSocket Connectivity Testing

Comprehensive WebSocket server testing and connectivity verification for MCP servers:

[Extended thinking: This tool wraps check_websocket.py to provide thorough WebSocket connectivity testing, specifically useful for verifying crackerjack-mcp server WebSocket functionality and other MCP server integrations.]

## WebSocket Testing Overview

Professional WebSocket connectivity testing with multi-protocol support and comprehensive diagnostics.

**Core Testing Capabilities:**

```python
WEBSOCKET_TESTING = {
    "port_verification": "Check if WebSocket ports are listening and accessible",
    "connectivity_testing": "Test actual WebSocket connections and handshakes",
    "protocol_validation": "Verify WebSocket protocol compliance and features",
    "integration_testing": "Test MCP server WebSocket integrations",
}
```

## WebSocket Testing Operations

### 1. Port and Service Verification

**Command:** `python ~/.claude/automation-tools/check_websocket.py --check-port 8675`

**Port Verification Features:**

- **Port Listening Check**: Verify if specific ports have active listeners
- **Process Identification**: Identify which process is using WebSocket ports
- **Service Status**: Determine if WebSocket services are running correctly
- **Multiple Port Testing**: Test connectivity across multiple WebSocket ports

**Typical WebSocket Ports:**

```python
websocket_ports = {
    "crackerjack_mcp": 8675,  # Default crackerjack WebSocket MCP server
    "development_tools": 8676,  # Development toolkit WebSocket server
    "monitoring": 8677,  # Monitoring integration WebSocket server
    "custom_mcp_servers": "8678-8680",  # Custom MCP server port range
}
```

### 2. HTTP Endpoint Verification

**Command:** `python ~/.claude/automation-tools/check_websocket.py --check-http`

**HTTP Testing Functionality:**

- **Health Check Endpoints**: Verify HTTP health check endpoints respond
- **API Endpoint Testing**: Test REST API endpoints on WebSocket servers
- **Service Discovery**: Discover available services on WebSocket servers
- **Protocol Negotiation**: Test WebSocket protocol upgrade mechanisms

**Endpoint Testing Pattern:**

```bash
# Test crackerjack-mcp WebSocket server endpoints
python ~/.claude/automation-tools/check_websocket.py \
    --test-endpoints \
    --server "crackerjack" \
    --port 8675 \
    --include-health-checks
```

### 3. WebSocket Connection Testing

**Command:** `python ~/.claude/automation-tools/check_websocket.py --test-websocket ws://localhost:8675`

**WebSocket Connection Features:**

- **Connection Establishment**: Test WebSocket handshake and connection setup
- **Message Exchange**: Verify bidirectional message communication
- **Protocol Compliance**: Test WebSocket protocol standard compliance
- **Error Handling**: Test connection error scenarios and recovery

**WebSocket Test Scenarios:**

```python
websocket_tests = {
    "basic_connection": "Establish and close WebSocket connection",
    "message_exchange": "Send and receive messages bidirectionally",
    "ping_pong": "Test WebSocket ping/pong keepalive mechanism",
    "error_scenarios": "Test connection failures and recovery",
}
```

## MCP Server Integration Testing

### 1. Crackerjack-MCP WebSocket Testing

**Usage Pattern:**

```bash
# Comprehensive crackerjack-mcp WebSocket testing
python ~/.claude/automation-tools/check_websocket.py \
    --test-crackerjack-mcp \
    --verify-progress-streaming \
    --test-job-monitoring \
    --validate-mcp-protocol
```

**Crackerjack-Specific Tests:**

- **Progress Streaming**: Test real-time job progress WebSocket streams
- **Job Discovery**: Verify job discovery and monitoring capabilities
- **MCP Protocol**: Validate MCP protocol compliance over WebSocket
- **Auto-Fix Integration**: Test WebSocket integration with AI auto-fix workflows

### 2. Development Toolkit WebSocket Testing

**Command Pattern:**

```bash
# Test development toolkit WebSocket integrations
python ~/.claude/automation-tools/check_websocket.py \
    --test-dev-toolkit \
    --port "$TOOLKIT_PORT" \
    --verify-tool-discovery \
    --test-command-streaming
```

**Development Toolkit Tests:**

- **Tool Discovery**: Test WebSocket-based tool discovery mechanisms
- **Command Streaming**: Verify command execution streaming over WebSocket
- **Status Updates**: Test real-time status update delivery
- **Error Propagation**: Verify error handling and reporting via WebSocket

### 3. Monitoring Integration Testing

**Integration Testing:**

```bash
# Test monitoring system WebSocket integrations
python ~/.claude/automation-tools/check_websocket.py \
    --test-monitoring \
    --verify-metrics-streaming \
    --test-alert-delivery \
    --validate-dashboard-feeds
```

**Monitoring WebSocket Tests:**

- **Metrics Streaming**: Test real-time metrics delivery
- **Alert Delivery**: Verify alert and notification WebSocket channels
- **Dashboard Data**: Test dashboard data streaming capabilities
- **Analytics Integration**: Verify analytics data WebSocket transmission

## Advanced WebSocket Diagnostics

### Connection Diagnostics

**Comprehensive Connection Analysis:**

```python
connection_diagnostics = {
    "handshake_analysis": "Analyze WebSocket handshake process",
    "protocol_inspection": "Inspect WebSocket protocol headers and negotiation",
    "performance_testing": "Test connection performance and latency",
    "load_testing": "Test WebSocket server under load conditions",
}
```

### Error Scenario Testing

**Error Condition Verification:**

```python
error_testing = {
    "connection_failures": "Test various connection failure scenarios",
    "message_corruption": "Test handling of corrupted or invalid messages",
    "timeout_handling": "Test connection timeout and keepalive mechanisms",
    "recovery_testing": "Test automatic reconnection and recovery",
}
```

### Security Testing

**WebSocket Security Validation:**

```python
security_testing = {
    "origin_validation": "Test origin header validation and security",
    "authentication": "Test WebSocket authentication mechanisms",
    "authorization": "Verify WebSocket authorization and access control",
    "encryption": "Test WSS (WebSocket Secure) connections when available",
}
```

## Integration with Claude Ecosystem

### MCP Server Health Monitoring

**Continuous Health Checks:**

```bash
# Continuous WebSocket health monitoring
python ~/.claude/automation-tools/check_websocket.py \
    --continuous-monitoring \
    --interval 30 \
    --alert-on-failure \
    --log-results ~/.claude/logs/websocket-health.log
```

**Health Monitoring Features:**

- **Periodic Checks**: Regular WebSocket connectivity verification
- **Failure Alerting**: Alert when WebSocket services become unavailable
- **Performance Tracking**: Monitor WebSocket connection performance over time
- **Service Recovery**: Detect when failed services come back online

### Analytics Integration

**WebSocket Analytics:**

```python
websocket_analytics = {
    "connection_metrics": "Track WebSocket connection success rates",
    "performance_data": "Monitor WebSocket latency and throughput",
    "error_analytics": "Analyze WebSocket error patterns and trends",
    "usage_patterns": "Track WebSocket usage across different MCP servers",
}
```

## Configuration and Automation

### Testing Configuration

```json
{
    "websocket_testing": {
        "default_timeout": 5.0,
        "retry_attempts": 3,
        "health_check_interval": 30,
        "performance_monitoring": true
    },
    "mcp_server_endpoints": {
        "crackerjack": "ws://localhost:8675",
        "development_toolkit": "ws://localhost:8676",
        "monitoring": "ws://localhost:8677"
    }
}
```

### Automated Testing Workflows

**Scheduled Testing:**

```bash
# Daily WebSocket health check
python ~/.claude/automation-tools/check_websocket.py \
    --scheduled-check \
    --test-all-mcp-servers \
    --generate-report \
    --email-on-failure
```

**CI/CD Integration:**

```bash
# WebSocket testing in deployment pipeline
python ~/.claude/automation-tools/check_websocket.py \
    --ci-mode \
    --test-deployment-endpoints \
    --fail-on-error \
    --output-junit-xml
```

## Usage Examples

### Basic WebSocket Testing

```bash
# Test specific WebSocket endpoint
python ~/.claude/automation-tools/check_websocket.py \
    --test-endpoint ws://localhost:8675 \
    --timeout 10
```

### Comprehensive MCP Server Testing

```bash
# Test all MCP server WebSocket endpoints
python ~/.claude/automation-tools/check_websocket.py \
    --test-all-mcp-servers \
    --include-performance-tests \
    --generate-detailed-report
```

### Integration with Monitoring

```bash
# WebSocket testing with analytics integration
python ~/.claude/automation-tools/check_websocket.py \
    --test-configuration "$ARGUMENTS" \
    --integrate-analytics \
    --store-results ~/.claude/analytics/websocket-results.json
```

This tool provides comprehensive WebSocket testing capabilities essential for maintaining reliable MCP server integrations and ensuring robust real-time communication channels in your development ecosystem.

______________________________________________________________________

## Security Considerations

### Access Control for Monitoring Data

- **Authentication Required**: Protect monitoring dashboards with SSO
- **RBAC for Metrics**: Implement role-based access to sensitive metrics
- **Audit Logging**: Log access to monitoring systems

### Sensitive Data in Logs

- **PII Redaction**: Automatically redact sensitive data from logs
- **Secret Filtering**: Never log secrets, tokens, or passwords
- **Log Sanitization**: Implement pre-processing to remove sensitive fields

```python
# Example: Log sanitization
import re
from structlog.processors import JSONRenderer

def sanitize_logs(logger, name, event_dict):
    """Remove sensitive data from logs"""
    sensitive_patterns = {
        'password': r'password["']?\s*[:=]\s*["']?[^"'}\s]+',
        'api_key': r'api[_-]?key["']?\s*[:=]\s*["']?[^"'}\s]+',
        'token': r'token["']?\s*[:=]\s*["']?[^"'}\s]+',
    }

    message = str(event_dict.get('event', ''))
    for name, pattern in sensitive_patterns.items():
        message = re.sub(pattern, f'{name}=REDACTED', message, flags=re.IGNORECASE)

    event_dict['event'] = message
    return event_dict
```

### Metrics Security

- **Avoid Sensitive Metrics**: Don't expose PII in metric labels
- **Cardinality Limits**: Prevent cardinality explosions from untrusted inputs
- **Secure Metric Endpoints**: Protect Prometheus/metric endpoints

### Monitoring System Security

- **TLS for Transport**: Encrypt data in transit to monitoring backends
- **Secure Storage**: Encrypt stored logs and metrics
- **Retention Policies**: Define and enforce data retention limits

### Alert Security

- **Secure Alert Channels**: Use encrypted channels (Slack, PagerDuty)
- **Alert Data Filtering**: Don't include sensitive data in alerts
- **Alert Access Control**: Restrict who can modify alert configurations

______________________________________________________________________

______________________________________________________________________

## Testing & Validation

### Monitoring Configuration Testing

```python
# Test Prometheus rules
import yaml
from promtool import validate_rules


def test_prometheus_rules_valid():
    with open("prometheus-rules.yaml") as f:
        rules = yaml.safe_load(f)

    # Validate syntax
    result = validate_rules(rules)
    assert result.is_valid


# Test alert fires correctly
def test_high_cpu_alert_fires():
    # Simulate high CPU metrics
    push_metric("cpu_usage", 95)

    # Wait for alert evaluation
    time.sleep(30)

    # Check alert status
    alerts = get_firing_alerts()
    assert any(a["alertname"] == "HighCPUUsage" for a in alerts)
```

### Log Parsing Testing

```python
# Test log processors
def test_log_parsing():
    log_line = "2025-01-15 12:00:00 INFO user_id=123 action=login status=success"

    parsed = parse_log_line(log_line)

    assert parsed["timestamp"] == "2025-01-15 12:00:00"
    assert parsed["level"] == "INFO"
    assert parsed["user_id"] == "123"
    assert parsed["action"] == "login"


def test_sensitive_data_redaction():
    log_line = "password=secret123 api_key=sk-1234567890"

    redacted = redact_sensitive_data(log_line)

    assert "secret123" not in redacted
    assert "sk-1234567890" not in redacted
    assert "password=REDACTED" in redacted
```

### Dashboard Testing

```python
# Test Grafana dashboard JSON
import json


def test_grafana_dashboard_valid():
    with open("dashboard.json") as f:
        dashboard = json.load(f)

    # Validate structure
    assert "title" in dashboard
    assert "panels" in dashboard
    assert len(dashboard["panels"]) > 0

    # Validate queries
    for panel in dashboard["panels"]:
        if "targets" in panel:
            for target in panel["targets"]:
                assert "expr" in target  # Prometheus query exists
```

### Tracing Validation

```python
# Test distributed trace completeness
def test_trace_spans_complete():
    # Make request that should create trace
    response = requests.get("http://app/api/users/123")

    # Retrieve trace
    trace = get_trace_by_request_id(response.headers["X-Request-ID"])

    # Validate all expected spans exist
    span_names = [span["name"] for span in trace["spans"]]
    assert "http.request" in span_names
    assert "db.query" in span_names
    assert "cache.get" in span_names

    # Validate parent-child relationships
    root_span = trace["spans"][0]
    assert all(s["parent_id"] == root_span["id"] for s in trace["spans"][1:])
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
