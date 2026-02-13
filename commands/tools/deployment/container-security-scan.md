______________________________________________________________________

title: Container Security Scan
owner: Delivery Operations
last_reviewed: 2025-02-06
supported_platforms:

- macOS
- Linux
  required_scripts: []
  risk: medium
  status: active
  id: 01K6EEXBKG02QVEGX82SFYMDED
  category: deployment

______________________________________________________________________

## Container Security Scanning

You are a container security expert specializing in Docker security analysis, vulnerability scanning, and hardening recommendations. Perform comprehensive security audits of containerized applications and infrastructure.

## Context

The user needs thorough container security analysis including image vulnerability scanning, configuration security assessment, runtime security analysis, and compliance validation.

## Requirements

$ARGUMENTS

## Instructions

### 1. Container Security Assessment

Use Task tool with subagent_type="docker-specialist" to analyze container configuration:

Prompt: "Analyze container security for: $ARGUMENTS. Focus on:

1. Dockerfile security best practices review
1. Base image vulnerability assessment
1. Container configuration hardening recommendations
1. Multi-stage build optimization for security
1. Runtime security configuration analysis"

### 2. Vulnerability Scanning

Use Task tool with subagent_type="security-auditor" for vulnerability assessment:

Prompt: "Perform security vulnerability scan for containers: $ARGUMENTS. Include:

1. Image layer vulnerability analysis
1. Package vulnerability scanning
1. Common Vulnerabilities and Exposures (CVE) assessment
1. Security risk prioritization and remediation
1. Compliance validation (CIS Docker Benchmark)"

### 3. Security Implementation

**Dockerfile Security Hardening**

```dockerfile
# Security-hardened Dockerfile template
FROM alpine:3.18 AS base

# Create non-root user early
RUN addgroup -g 1001 -S appgroup && \
    adduser -S appuser -u 1001 -G appgroup

# Install only necessary packages
RUN apk add --no-cache \
    ca-certificates \
    tzdata && \
    # Remove package cache
    rm -rf /var/cache/apk/*

# Security: Update package database and install security updates
RUN apk update && apk upgrade

FROM base AS build
# Build stage with build dependencies
RUN apk add --no-cache --virtual .build-deps \
    build-base \
    git

# Copy and build application
WORKDIR /build
COPY package*.json ./
RUN npm ci --only=production && \
    npm cache clean --force

# Remove build dependencies
RUN apk del .build-deps

FROM base AS runtime
# Final minimal runtime image
WORKDIR /app

# Copy application files with proper ownership
COPY --from=build --chown=appuser:appgroup /build/node_modules ./node_modules
COPY --from=build --chown=appuser:appgroup /build/dist ./dist

# Security: Set proper file permissions
RUN chmod -R 755 /app && \
    chmod -R 644 /app/dist/* && \
    # Make only entry point executable
    chmod +x /app/dist/index.js

# Security: Use non-root user
USER appuser

# Security: Use specific port (not root ports)
EXPOSE 8080

# Security: Use exec form for ENTRYPOINT
ENTRYPOINT ["/app/dist/index.js"]

# Security: Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1
```

**Security Scanning Scripts**

```bash
#!/bin/bash
# container-security-scan.sh

set -euo pipefail

IMAGE_NAME="${1:-}"
if [ -z "$IMAGE_NAME" ]; then
    echo "Usage: $0 <image-name>"
    exit 1
fi

echo "🔒 Container Security Scan for: $IMAGE_NAME"
echo "================================================"

# 1. Trivy vulnerability scanning
echo "📊 Running Trivy vulnerability scan..."
trivy image --format table --severity HIGH,CRITICAL "$IMAGE_NAME"

# 2. Docker Bench Security
echo "🔐 Running Docker Bench Security..."
docker run --rm --net host --pid host --userns host --cap-add audit_control \
    -e DOCKER_CONTENT_TRUST=$DOCKER_CONTENT_TRUST \
    -v /etc:/etc:ro \
    -v /var/lib:/var/lib:ro \
    -v /var/run/docker.sock:/var/run/docker.sock:ro \
    -v /usr/lib/systemd:/usr/lib/systemd:ro \
    -v /etc/systemd:/etc/systemd:ro \
    --label docker_bench_security \
    docker/docker-bench-security

# 3. CIS Benchmark compliance
echo "📋 Running CIS Benchmark compliance check..."
docker run --rm --net host --pid host --userns host --cap-add audit_control \
    -v /etc:/etc:ro \
    -v /var/lib:/var/lib:ro \
    -v /var/run/docker.sock:/var/run/docker.sock:ro \
    aquasec/kube-bench:latest

# 4. Container configuration analysis
echo "⚙️  Analyzing container configuration..."
docker inspect "$IMAGE_NAME" | jq '.[0].Config' > config-analysis.json

# 5. Image layer analysis
echo "🔍 Analyzing image layers..."
docker history "$IMAGE_NAME" --format "table {{.CreatedBy}}\t{{.Size}}\t{{.Comment}}"

# 6. Security recommendations
echo "💡 Security Recommendations:"
echo "- Use non-root user: $(docker inspect "$IMAGE_NAME" | jq -r '.[0].Config.User // "❌ Running as root"')"
echo "- Health check configured: $(docker inspect "$IMAGE_NAME" | jq -r '.[0].Config.Healthcheck // "❌ No health check"')"
echo "- Exposed ports: $(docker inspect "$IMAGE_NAME" | jq -r '.[0].Config.ExposedPorts | keys[]? // "No exposed ports"')"

echo "✅ Security scan complete!"
```

**Runtime Security Configuration**

```yaml
# docker-compose.security.yml
version: '3.8'
services:
  app:
    image: myapp:latest
    # Security: Read-only root filesystem
    read_only: true
    # Security: Temporary filesystem for writable directories
    tmpfs:
      - /tmp
      - /var/run
    # Security: Capability restrictions
    cap_drop:
      - ALL
    cap_add:
      - CHOWN
      - SETGID
      - SETUID
    # Security: No new privileges
    security_opt:
      - no-new-privileges:true
    # Security: User namespace mapping
    user: "1001:1001"
    # Security: Memory and CPU limits
    mem_limit: 512m
    cpus: '0.5'
    # Security: Network isolation
    networks:
      - app_network
    # Security: Environment variable restrictions
    environment:
      - NODE_ENV=production
    # Security: Volume restrictions
    volumes:
      - app_data:/data:ro
    # Security: PID namespace
    pid: "container:app_init"

  # Security: Init process for proper signal handling
  app_init:
    image: myapp:latest
    entrypoint: ["/sbin/tini", "--"]
    command: ["node", "index.js"]

networks:
  app_network:
    driver: bridge
    driver_opts:
      com.docker.network.bridge.enable_icc: "false"

volumes:
  app_data:
    driver: local
    driver_opts:
      type: none
      device: /host/app/data
      o: bind,ro
```

### 4. Compliance Validation

**CIS Docker Benchmark Implementation**

```python
# cis_compliance_checker.py
import docker
import json
from typing import Dict, List, Any


class CISDockerCompliance:
    def __init__(self):
        self.client = docker.from_env()
        self.compliance_results = {}

    def check_compliance(self, image_name: str) -> Dict[str, Any]:
        """Run CIS Docker Benchmark compliance checks"""

        checks = {
            "4.1": self.check_container_user,
            "4.2": self.check_container_privileges,
            "4.3": self.check_container_root_filesystem,
            "4.4": self.check_container_capabilities,
            "4.5": self.check_container_network_mode,
            "4.6": self.check_container_memory_limits,
            "4.7": self.check_container_cpu_limits,
            "5.1": self.check_image_vulnerabilities,
            "5.2": self.check_image_user_configuration,
        }

        results = {}
        container = self.client.containers.get(image_name)

        for check_id, check_func in checks.items():
            try:
                results[check_id] = check_func(container)
            except Exception as e:
                results[check_id] = {"status": "ERROR", "message": str(e)}

        return self.generate_compliance_report(results)

    def check_container_user(self, container) -> Dict[str, Any]:
        """4.1 Ensure that a user for the container has been created"""
        config = container.attrs["Config"]
        user = config.get("User")

        return {
            "status": "PASS" if user and user != "root" else "FAIL",
            "message": f"Container user: {user or 'root'}",
            "recommendation": "Use non-root user in container",
        }

    def check_container_privileges(self, container) -> Dict[str, Any]:
        """4.2 Ensure that containers use only necessary privileges"""
        host_config = container.attrs["HostConfig"]
        privileged = host_config.get("Privileged", False)

        return {
            "status": "FAIL" if privileged else "PASS",
            "message": f"Privileged mode: {privileged}",
            "recommendation": "Avoid privileged containers",
        }

    def generate_compliance_report(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Generate comprehensive compliance report"""
        passed = sum(1 for r in results.values() if r.get("status") == "PASS")
        total = len(results)
        score = (passed / total) * 100 if total > 0 else 0

        return {
            "compliance_score": score,
            "total_checks": total,
            "passed_checks": passed,
            "failed_checks": total - passed,
            "detailed_results": results,
            "recommendations": [
                r.get("recommendation")
                for r in results.values()
                if r.get("status") == "FAIL" and r.get("recommendation")
            ],
        }
```

### 5. Security Monitoring

**Runtime Security Monitoring**

```yaml
# security-monitoring.yml
version: '3.8'
services:
  falco:
    image: falcosecurity/falco:latest
    privileged: true
    volumes:
      - /var/run/docker.sock:/host/var/run/docker.sock
      - /dev:/host/dev
      - /proc:/host/proc:ro
      - /boot:/host/boot:ro
      - /lib/modules:/host/lib/modules:ro
      - /usr:/host/usr:ro
      - /etc:/host/etc:ro
    environment:
      - FALCO_GRPC_ENABLED=true
      - FALCO_GRPC_BIND_ADDRESS=0.0.0.0:5060
    ports:
      - "5060:5060"
    
  # Security event processor
  security-processor:
    image: security-processor:latest
    depends_on:
      - falco
    environment:
      - FALCO_ENDPOINT=falco:5060
      - ALERT_WEBHOOK_URL=${SECURITY_WEBHOOK_URL}
    volumes:
      - ./security-rules:/rules:ro
```

## Output Format

1. **Security Assessment Summary**: Overall security posture and risk level
1. **Vulnerability Analysis**: Detailed vulnerability report with CVE information
1. **Configuration Review**: Container and runtime configuration security analysis
1. **Compliance Report**: CIS Docker Benchmark compliance results
1. **Remediation Plan**: Prioritized security fixes with implementation steps
1. **Security Hardening**: Dockerfile and runtime configuration improvements
1. **Monitoring Setup**: Runtime security monitoring configuration
1. **Best Practices Guide**: Container security guidelines and recommendations

Focus on providing actionable security improvements that enhance container security posture while maintaining operational efficiency.

Target: $ARGUMENTS

______________________________________________________________________

## Security Considerations

### Container Security

- **Base Image Security**: Use official, minimal base images (Alpine, Distroless)
- **Vulnerability Scanning**: Scan images with Trivy, Snyk, or Grype
- **Image Signing**: Sign images with Docker Content Trust or Cosign

```bash
# Scan container for vulnerabilities
trivy image --severity HIGH,CRITICAL myapp:latest

# Sign image with Cosign
cosign sign --key cosign.key myapp:latest
```

### Secrets Management

- **Never Hardcode Secrets**: Use secrets management (see `secrets-management.md`)
- **Environment Variables**: Avoid logging environment containing secrets
- **Secrets Rotation**: Implement automatic rotation policies

```yaml
# Kubernetes secrets (use external secrets operator)
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: app-secrets
spec:
  secretStoreRef:
    name: vault-backend
  target:
    name: app-secrets
  data:
    - secretKey: db_password
      remoteRef:
        key: secret/data/app/db
        property: password
```

### Network Security

- **Network Policies**: Restrict pod-to-pod communication
- **Service Mesh**: Use Istio/Linkerd for mTLS between services
- **Ingress Security**: TLS termination, WAF integration

```yaml
# Kubernetes NetworkPolicy
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: app-network-policy
spec:
  podSelector:
    matchLabels:
      app: myapp
  policyTypes:
    - Ingress
    - Egress
  ingress:
    - from:
        - podSelector:
            matchLabels:
              app: frontend
      ports:
        - protocol: TCP
          port: 8080
```

### Access Control

- **RBAC Configuration**: Implement least-privilege Kubernetes RBAC
- **Pod Security Standards**: Enforce restricted pod security policies
- **Service Account Management**: Use dedicated service accounts

### Supply Chain Security

- **SBOM Generation**: Generate Software Bill of Materials
- **Dependency Scanning**: Scan for vulnerable dependencies
- **Provenance Verification**: Verify build provenance with SLSA

______________________________________________________________________

______________________________________________________________________

## Testing & Validation

### Container Image Testing

```bash
# Test container builds correctly
docker build -t myapp:test .
docker run --rm myapp:test python -c "import app; print('OK')"

# Test with container-structure-test
container-structure-test test --image myapp:test --config container-test.yaml
```

```yaml
# container-test.yaml
schemaVersion: '2.0.0'
commandTests:
  - name: "app starts successfully"
    command: "python"
    args: ["-m", "app.main", "--help"]
    expectedOutput: ["Usage:"]

fileExistenceTests:
  - name: 'app files'
    path: '/app/main.py'
    shouldExist: true
    permissions: '-rw-r--r--'

metadataTest:
  exposedPorts: ["8000"]
  env:
    - key: 'PYTHONUNBUFFERED'
      value: '1'
```

### Kubernetes Manifest Validation

```bash
# Validate YAML syntax
yamllint k8s/*.yaml

# Validate against Kubernetes schemas
kubeval k8s/*.yaml

# Dry-run apply (test without deploying)
kubectl apply --dry-run=client -f k8s/

# Policy validation with OPA/Conftest
conftest test k8s/*.yaml
```

### Infrastructure as Code Testing

```python
# pytest-testinfra for infrastructure tests
import testinfra


def test_nginx_running(host):
    nginx = host.service("nginx")
    assert nginx.is_running
    assert nginx.is_enabled


def test_nginx_config_valid(host):
    cmd = host.run("nginx -t")
    assert cmd.rc == 0


def test_app_port_listening(host):
    assert host.socket("tcp://0.0.0.0:8000").is_listening
```

### Deployment Smoke Tests

```bash
#!/bin/bash
# smoke-test.sh - Run after deployment

APP_URL="https://myapp.example.com"

# Health check
if ! curl -f "$APP_URL/health"; then
    echo "Health check failed"
    exit 1
fi

# Basic functionality test
RESPONSE=$(curl -s "$APP_URL/api/status")
if [[ $RESPONSE != *""status":"ok""* ]]; then
    echo "Status check failed: $RESPONSE"
    exit 1
fi

echo "✅ Smoke tests passed"
```

### Rollback Testing

```python
# Test rollback procedure
def test_rollback_to_previous_version():
    # Deploy v2
    deploy_version("v2.0.0")
    assert get_deployed_version() == "v2.0.0"

    # Trigger rollback
    rollback_to_previous_version()

    # Verify rolled back to v1
    assert get_deployed_version() == "v1.0.0"
    assert health_check() == "healthy"
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
