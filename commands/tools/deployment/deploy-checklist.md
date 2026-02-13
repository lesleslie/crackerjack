______________________________________________________________________

title: Deploy Checklist
owner: Delivery Operations
last_reviewed: 2025-02-06
supported_platforms:

- macOS
- Linux
  required_scripts: []
  risk: medium
  status: active
  id: 01K6EEXBQBEGC9TDX73Y7YQVSY
  category: deployment

______________________________________________________________________

## Deployment Checklist and Configuration

Generate deployment configuration and checklist for: $ARGUMENTS

Create comprehensive deployment artifacts:

1. **Pre-Deployment Checklist**:

   - [ ] All tests passing
   - [ ] Security scan completed
   - [ ] Performance benchmarks met
   - [ ] Documentation updated
   - [ ] Database migrations tested
   - [ ] Rollback plan documented
   - [ ] Monitoring alerts configured
   - [ ] Load testing completed

1. **Infrastructure Configuration**:

   - Docker/containerization setup
   - Kubernetes manifests
   - Terraform/IaC scripts
   - Environment variables
   - Secrets management
   - Network policies
   - Auto-scaling rules

1. **CI/CD Pipeline**:

   - GitHub Actions/GitLab CI
   - Build optimization
   - Test parallelization
   - Security scanning
   - Image building
   - Deployment stages
   - Rollback automation

1. **Database Deployment**:

   - Migration scripts
   - Backup procedures
   - Connection pooling
   - Read replica setup
   - Failover configuration
   - Data seeding
   - Version compatibility

1. **Monitoring Setup**:

   - Application metrics
   - Infrastructure metrics
   - Log aggregation
   - Error tracking
   - Uptime monitoring
   - Custom dashboards
   - Alert channels

1. **Security Configuration**:

   - SSL/TLS setup
   - API key rotation
   - CORS policies
   - Rate limiting
   - WAF rules
   - Security headers
   - Vulnerability scanning

1. **Post-Deployment**:

   - [ ] Smoke tests
   - [ ] Performance validation
   - [ ] Monitoring verification
   - [ ] Documentation published
   - [ ] Team notification
   - [ ] Customer communication
   - [ ] Metrics baseline

Include environment-specific configurations (dev, staging, prod) and disaster recovery procedures.

______________________________________________________________________

## Environment-Specific Checklists

### Development Environment

```yaml
# dev-deployment.yml
environment: development
checks:
  pre_deployment:
    - name: "Code Review"
      required: false
      automated: true
      command: "gh pr view --json reviewDecision"

    - name: "Unit Tests"
      required: true
      automated: true
      command: "pytest tests/unit --cov=src --cov-report=term-missing"

    - name: "Linting"
      required: true
      automated: true
      command: "ruff check src/ && black --check src/"

    - name: "Type Checking"
      required: false
      automated: true
      command: "mypy src/"

  deployment:
    strategy: "rolling"
    replicas: 1
    resources:
      cpu: "500m"
      memory: "512Mi"

  post_deployment:
    - name: "Health Check"
      endpoint: "https://dev.example.com/health"
      expected_status: 200
      timeout: 30

    - name: "Smoke Tests"
      required: true
      command: "pytest tests/smoke --env=dev"
```

### Staging Environment

```yaml
# staging-deployment.yml
environment: staging
checks:
  pre_deployment:
    - name: "All Tests Passing"
      required: true
      automated: true
      command: "pytest tests/ --cov=src --cov-fail-under=80"

    - name: "Security Scan"
      required: true
      automated: true
      command: "bandit -r src/ && safety check"

    - name: "Performance Benchmarks"
      required: true
      automated: true
      command: "locust -f tests/load/locustfile.py --headless -u 100 -r 10 --run-time 5m"

    - name: "Database Migrations Tested"
      required: true
      manual: true
      checklist:
        - "Migrations run successfully on staging DB copy"
        - "Rollback tested and verified"
        - "Data integrity checks passed"

  deployment:
    strategy: "blue-green"
    replicas: 2
    resources:
      cpu: "1000m"
      memory: "1Gi"

    canary:
      enabled: true
      percentage: 10
      duration: "15m"

  post_deployment:
    - name: "Integration Tests"
      required: true
      command: "pytest tests/integration --env=staging"

    - name: "E2E Tests"
      required: true
      command: "playwright test --project=staging"

    - name: "Performance Validation"
      required: true
      thresholds:
        p95_latency: "< 200ms"
        error_rate: "< 0.1%"
        throughput: "> 1000 req/s"
```

### Production Environment

```yaml
# prod-deployment.yml
environment: production
checks:
  pre_deployment:
    - name: "Change Approval"
      required: true
      manual: true
      approvers: ["tech-lead", "product-manager"]

    - name: "Staging Validation Complete"
      required: true
      manual: true
      duration: "24 hours minimum in staging"

    - name: "Rollback Plan Documented"
      required: true
      manual: true
      template: "docs/rollback-template.md"

    - name: "Database Backup Verified"
      required: true
      automated: true
      command: "scripts/verify-backup.sh production"

    - name: "Communication Sent"
      required: true
      manual: true
      channels: ["#engineering", "#product", "#support"]

  deployment:
    strategy: "canary"
    replicas: 10
    resources:
      cpu: "2000m"
      memory: "4Gi"

    canary:
      enabled: true
      steps:
        - percentage: 5
          duration: "30m"
        - percentage: 25
          duration: "1h"
        - percentage: 50
          duration: "1h"
        - percentage: 100

    auto_rollback:
      enabled: true
      conditions:
        - "error_rate > 1%"
        - "p99_latency > 1000ms"
        - "5xx_errors > 10 per minute"

  post_deployment:
    - name: "Canary Analysis"
      required: true
      automated: true
      metrics:
        - "error_rate"
        - "latency_p50"
        - "latency_p95"
        - "latency_p99"

    - name: "Business Metrics Validation"
      required: true
      duration: "2 hours"
      metrics:
        - "conversion_rate"
        - "revenue_per_user"
        - "active_users"

    - name: "Support Readiness"
      required: true
      manual: true
      checklist:
        - "Support team briefed on changes"
        - "Known issues documented"
        - "Escalation path confirmed"
```

______________________________________________________________________

## CI/CD Pipeline Examples

### GitHub Actions Deployment

```yaml
# .github/workflows/deploy.yml
name: Deploy to Production

on:
  push:
    branches: [main]
  workflow_dispatch:
    inputs:
      environment:
        description: 'Environment to deploy to'
        required: true
        type: choice
        options:
          - development
          - staging
          - production

jobs:
  pre-deployment-checks:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Run Tests
        run: |
          python -m pytest tests/ --cov=src --cov-fail-under=80

      - name: Security Scan
        run: |
          pip install bandit safety
          bandit -r src/
          safety check

      - name: Build Docker Image
        run: |
          docker build -t app:${{ github.sha }} .

      - name: Scan Image
        uses: aquasecurity/trivy-action@master
        with:
          image-ref: 'app:${{ github.sha }}'
          severity: 'CRITICAL,HIGH'

  deploy-staging:
    needs: pre-deployment-checks
    if: github.event_name == 'push' && github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    environment: staging
    steps:
      - name: Deploy to Staging
        run: |
          kubectl set image deployment/app app=app:${{ github.sha }} -n staging
          kubectl rollout status deployment/app -n staging --timeout=5m

      - name: Run Smoke Tests
        run: |
          pytest tests/smoke --env=staging

  deploy-production:
    needs: deploy-staging
    if: github.event.inputs.environment == 'production'
    runs-on: ubuntu-latest
    environment: production
    steps:
      - name: Create Backup
        run: |
          ./scripts/backup-database.sh production

      - name: Deploy Canary
        run: |
          kubectl apply -f k8s/canary-deployment.yml

      - name: Monitor Canary
        run: |
          python scripts/monitor-canary.py --duration 30m

      - name: Promote or Rollback
        run: |
          if python scripts/check-metrics.py --threshold pass; then
            kubectl set image deployment/app app=app:${{ github.sha }} -n production
          else
            kubectl rollout undo deployment/app -n production
            exit 1
          fi
```

### Infrastructure as Code (Terraform)

```hcl
# terraform/main.tf - Deployment Configuration

variable "environment" {
  type = string
}

variable "app_version" {
  type = string
}

resource "kubernetes_deployment" "app" {
  metadata {
    name      = "app"
    namespace = var.environment
    labels = {
      app     = "myapp"
      version = var.app_version
      env     = var.environment
    }
  }

  spec {
    replicas = var.environment == "production" ? 10 : 2

    strategy {
      type = var.environment == "production" ? "RollingUpdate" : "Recreate"

      rolling_update {
        max_surge       = "25%"
        max_unavailable = "0"
      }
    }

    selector {
      match_labels = {
        app = "myapp"
      }
    }

    template {
      metadata {
        labels = {
          app     = "myapp"
          version = var.app_version
        }
      }

      spec {
        container {
          name  = "app"
          image = "myregistry/app:${var.app_version}"

          resources {
            requests = {
              cpu    = var.environment == "production" ? "2000m" : "500m"
              memory = var.environment == "production" ? "4Gi" : "512Mi"
            }
            limits = {
              cpu    = var.environment == "production" ? "4000m" : "1000m"
              memory = var.environment == "production" ? "8Gi" : "1Gi"
            }
          }

          liveness_probe {
            http_get {
              path = "/health"
              port = 8080
            }
            initial_delay_seconds = 30
            period_seconds        = 10
            failure_threshold     = 3
          }

          readiness_probe {
            http_get {
              path = "/ready"
              port = 8080
            }
            initial_delay_seconds = 10
            period_seconds        = 5
            failure_threshold     = 2
          }
        }
      }
    }
  }
}
```

______________________________________________________________________

## Rollback Procedures

### Automated Rollback Script

```bash
#!/bin/bash
# scripts/rollback.sh

set -euo pipefail

ENVIRONMENT=${1:-production}
REASON=${2:-"Manual rollback"}

echo "🔄 Starting rollback for $ENVIRONMENT"
echo "Reason: $REASON"

# 1. Capture current state
CURRENT_VERSION=$(kubectl get deployment app -n $ENVIRONMENT -o jsonpath='{.spec.template.spec.containers[0].image}')
echo "Current version: $CURRENT_VERSION"

# 2. Get previous stable version
PREVIOUS_VERSION=$(kubectl rollout history deployment/app -n $ENVIRONMENT | tail -2 | head -1 | awk '{print $1}')
echo "Rolling back to revision: $PREVIOUS_VERSION"

# 3. Create snapshot before rollback
echo "Creating pre-rollback snapshot..."
kubectl get all -n $ENVIRONMENT -o yaml > rollback-snapshot-$(date +%s).yaml

# 4. Execute rollback
echo "Executing rollback..."
kubectl rollout undo deployment/app -n $ENVIRONMENT --to-revision=$PREVIOUS_VERSION

# 5. Wait for rollback to complete
echo "Waiting for rollback to complete..."
kubectl rollout status deployment/app -n $ENVIRONMENT --timeout=5m

# 6. Verify health
echo "Verifying application health..."
for i in {1..10}; do
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" https://$ENVIRONMENT.example.com/health)
  if [ "$STATUS" == "200" ]; then
    echo "✅ Health check passed"
    break
  fi
  echo "Attempt $i/10: Health check returned $STATUS, retrying..."
  sleep 10
done

# 7. Notify team
echo "Sending notifications..."
curl -X POST $SLACK_WEBHOOK_URL \
  -H 'Content-Type: application/json' \
  -d "{
    \"text\": \"🔄 Rollback completed for $ENVIRONMENT\",
    \"blocks\": [
      {
        \"type\": \"section\",
        \"text\": {
          \"type\": \"mrkdwn\",
          \"text\": \"*Rollback Summary*\n• Environment: $ENVIRONMENT\n• From: $CURRENT_VERSION\n• To: Revision $PREVIOUS_VERSION\n• Reason: $REASON\"
        }
      }
    ]
  }"

echo "✅ Rollback complete"
```

### Database Rollback

```python
# scripts/db_rollback.py
import psycopg2
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class DatabaseRollback:
    """Handle database migration rollbacks"""

    def __init__(self, connection_string: str):
        self.conn = psycopg2.connect(connection_string)
        self.cursor = self.conn.cursor()

    def create_snapshot(self, snapshot_name: str):
        """Create database snapshot before changes"""
        logger.info(f"Creating snapshot: {snapshot_name}")

        self.cursor.execute(f"""
            CREATE DATABASE {snapshot_name}_snapshot
            WITH TEMPLATE current_database;
        """)
        self.conn.commit()

    def rollback_migration(self, target_version: str):
        """Rollback to specific migration version"""
        logger.info(f"Rolling back to version: {target_version}")

        # Get current version
        self.cursor.execute(
            "SELECT version FROM schema_migrations ORDER BY version DESC LIMIT 1"
        )
        current_version = self.cursor.fetchone()[0]

        logger.info(f"Current version: {current_version}")

        # Get migrations to rollback
        self.cursor.execute(
            """
            SELECT version, down_script FROM schema_migrations
            WHERE version > %s
            ORDER BY version DESC
        """,
            (target_version,),
        )

        migrations_to_rollback = self.cursor.fetchall()

        # Execute rollback scripts
        for version, down_script in migrations_to_rollback:
            logger.info(f"Rolling back migration {version}")
            self.cursor.execute(down_script)

            # Remove from migrations table
            self.cursor.execute(
                "DELETE FROM schema_migrations WHERE version = %s", (version,)
            )

        self.conn.commit()
        logger.info("Rollback complete")

    def verify_data_integrity(self) -> bool:
        """Verify database integrity after rollback"""
        checks = [
            "SELECT COUNT(*) FROM users WHERE email IS NULL",  # Should be 0
            "SELECT COUNT(*) FROM orders WHERE user_id NOT IN (SELECT id FROM users)",  # Should be 0
        ]

        for check in checks:
            self.cursor.execute(check)
            result = self.cursor.fetchone()[0]
            if result != 0:
                logger.error(f"Integrity check failed: {check}")
                return False

        logger.info("All integrity checks passed")
        return True
```

______________________________________________________________________

## Monitoring Verification

### Post-Deployment Monitoring Script

```python
# scripts/verify_deployment.py
import requests
import time
from dataclasses import dataclass
from typing import List, Dict


@dataclass
class HealthCheck:
    name: str
    url: str
    expected_status: int
    timeout: int = 30


@dataclass
class MetricCheck:
    name: str
    query: str  # Prometheus query
    threshold: float
    comparison: str  # gt, lt, eq


class DeploymentVerifier:
    """Verify deployment health and metrics"""

    def __init__(self, environment: str):
        self.environment = environment
        self.prometheus_url = f"https://prometheus.{environment}.example.com"

    def verify_health_endpoints(self, checks: List[HealthCheck]) -> bool:
        """Verify all health endpoints"""
        print(f"\n🏥 Verifying health endpoints for {self.environment}...")

        all_healthy = True
        for check in checks:
            try:
                response = requests.get(check.url, timeout=check.timeout)
                status = "✅" if response.status_code == check.expected_status else "❌"
                print(f"{status} {check.name}: {response.status_code}")

                if response.status_code != check.expected_status:
                    all_healthy = False

            except requests.RequestException as e:
                print(f"❌ {check.name}: Failed - {e}")
                all_healthy = False

        return all_healthy

    def verify_metrics(self, checks: List[MetricCheck]) -> bool:
        """Verify Prometheus metrics"""
        print(f"\n📊 Verifying metrics for {self.environment}...")

        all_passed = True
        for check in checks:
            try:
                response = requests.get(
                    f"{self.prometheus_url}/api/v1/query", params={"query": check.query}
                )
                data = response.json()
                value = float(data["data"]["result"][0]["value"][1])

                passed = self._compare_metric(value, check.threshold, check.comparison)
                status = "✅" if passed else "❌"

                print(
                    f"{status} {check.name}: {value} {check.comparison} {check.threshold}"
                )

                if not passed:
                    all_passed = False

            except Exception as e:
                print(f"❌ {check.name}: Failed - {e}")
                all_passed = False

        return all_passed

    def _compare_metric(self, value: float, threshold: float, comparison: str) -> bool:
        """Compare metric value against threshold"""
        if comparison == "gt":
            return value > threshold
        elif comparison == "lt":
            return value < threshold
        elif comparison == "eq":
            return value == threshold
        return False


# Usage
if __name__ == "__main__":
    verifier = DeploymentVerifier("production")

    # Health checks
    health_checks = [
        HealthCheck("API Health", "https://api.prod.example.com/health", 200),
        HealthCheck(
            "Database Connection", "https://api.prod.example.com/health/db", 200
        ),
        HealthCheck(
            "Cache Connection", "https://api.prod.example.com/health/cache", 200
        ),
    ]

    # Metric checks
    metric_checks = [
        MetricCheck(
            "Error Rate",
            'sum(rate(http_requests_total{status=~"5.."}[5m]))',
            0.01,
            "lt",
        ),
        MetricCheck(
            "P95 Latency",
            "histogram_quantile(0.95, http_request_duration_seconds_bucket)",
            0.2,
            "lt",
        ),
        MetricCheck(
            "Active Pods", 'count(kube_pod_status_phase{phase="Running"})', 10, "gt"
        ),
    ]

    health_ok = verifier.verify_health_endpoints(health_checks)
    metrics_ok = verifier.verify_metrics(metric_checks)

    if health_ok and metrics_ok:
        print("\n✅ Deployment verification passed")
        exit(0)
    else:
        print("\n❌ Deployment verification failed")
        exit(1)
```

______________________________________________________________________

## Related Agents

**Primary Orchestrators**:

- `deployment-engineer` - End-to-end deployment strategy
- `docker-specialist` - Container optimization and security
- `terraform-specialist` - Infrastructure as Code

**Quality & Testing**:

- `qa-strategist` - Test strategy and execution
- `observability-incident-lead` - Performance validation

**Operations**:

- `observability-incident-lead` - Monitoring and alerting
- `architecture-council` - System design and scaling

______________________________________________________________________

## Best Practices

1. **Progressive Deployment**: Use canary or blue-green strategies for production
1. **Automated Rollback**: Define clear rollback triggers and automate when possible
1. **Environment Parity**: Keep dev/staging/prod as similar as possible
1. **Immutable Infrastructure**: Deploy new versions, don't modify existing
1. **Database Migrations**: Always test migrations with rollback procedures
1. **Monitoring First**: Ensure monitoring is in place before deploying
1. **Communication**: Notify all stakeholders before production changes
1. **Backup Verification**: Verify backups exist and are restorable
1. **Feature Flags**: Use flags to control feature rollout independently of deployment
1. **Post-Deployment Validation**: Run comprehensive checks after every deployment

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
