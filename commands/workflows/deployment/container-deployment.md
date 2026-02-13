______________________________________________________________________

title: Container Deployment Workflow
owner: Delivery Operations
last_reviewed: 2025-02-06
related_tools:

- commands/tools/development/code-quality/dependency-lifecycle.md
- commands/tools/deployment/release-management.md
- commands/tools/monitoring/observability-lifecycle.md
  risk: high
  status: active
  id: 01K6EF8EGDYJX8PH521SW7TV6R

______________________________________________________________________

## Container Deployment Workflow

[Extended thinking: Deliver secure, observable container deployments with clear roles and guardrails.]

## Overview

Use this workflow to design, secure, and roll out containerized services across environments.

## Prerequisites

- Service architecture draft and deployment environments identified.
- Registry credentials and infrastructure access ready.
- Baseline observability stack available for the target platform.

## Inputs

- `$ARGUMENTS` — service description and goals.
- `$PLATFORMS` — deployment targets (e.g., Kubernetes, ECS, Nomad).
- `$COMPLIANCE_FLAGS` — special requirements (PCI, SOC2, etc.).

## Outputs

- Hardened container image and orchestration manifests.
- Automated CI/CD pipeline with rollback strategy.
- Monitoring and runbook updates aligned to the service.

## Phases

### Phase 0 – Prerequisites Validation

**Before starting deployment work, validate all required access and infrastructure:**

1. **Registry Access Validation:**

   ```bash
   # Verify Docker registry authentication
   docker login $REGISTRY_URL
   # Expected: Login Succeeded

   # Test push permissions (using a test image)
   docker tag alpine:latest $REGISTRY_URL/test:validation
   docker push $REGISTRY_URL/test:validation
   docker rmi $REGISTRY_URL/test:validation
   ```

1. **Infrastructure Access:**

   ```bash
   # Kubernetes access
   kubectl cluster-info
   kubectl auth can-i create deployments --namespace=$TARGET_NAMESPACE
   kubectl auth can-i create services --namespace=$TARGET_NAMESPACE

   # ECS access (if applicable)
   aws ecs describe-clusters --clusters $CLUSTER_NAME
   aws ecs describe-task-definition --task-definition $SERVICE_NAME || echo "No existing task definition"

   # Verify namespace/project exists
   kubectl get namespace $TARGET_NAMESPACE || kubectl create namespace $TARGET_NAMESPACE
   ```

1. **CI/CD Pipeline Access:**

   ```bash
   # GitHub Actions (if applicable)
   gh auth status
   gh workflow list --repo $REPO_NAME

   # GitLab CI (if applicable)
   curl --header "PRIVATE-TOKEN: $GITLAB_TOKEN" \
     "$GITLAB_URL/api/v4/projects/$PROJECT_ID/pipelines"

   # Jenkins (if applicable)
   curl -u $JENKINS_USER:$JENKINS_TOKEN \
     "$JENKINS_URL/api/json?tree=jobs[name]"
   ```

1. **Secrets & Configuration:**

   ```bash
   # Verify required secrets exist
   kubectl get secret $APP_SECRETS_NAME -n $TARGET_NAMESPACE

   # Check configmaps
   kubectl get configmap $APP_CONFIG_NAME -n $TARGET_NAMESPACE

   # Validate environment-specific configs exist
   [ -f "config/$ENVIRONMENT.yaml" ] || echo "ERROR: Missing config for $ENVIRONMENT"
   ```

1. **Observability Stack:**

   ```bash
   # Verify monitoring namespace/resources
   kubectl get namespace monitoring || echo "WARNING: No monitoring namespace"

   # Check Prometheus/Grafana availability
   kubectl get svc -n monitoring | grep -E 'prometheus|grafana'

   # Verify logging infrastructure (if using ELK/Loki)
   kubectl get svc -n logging || echo "WARNING: No logging namespace"
   ```

1. **Network & DNS:**

   ```bash
   # Test DNS resolution
   nslookup $SERVICE_DOMAIN || echo "WARNING: DNS not configured yet"

   # Verify ingress controller
   kubectl get ingressclass

   # Check load balancer availability (cloud-specific)
   kubectl get svc -n ingress-nginx ingress-nginx-controller
   ```

1. **Resource Quotas & Limits:**

   ```bash
   # Check namespace resource quotas
   kubectl describe resourcequota -n $TARGET_NAMESPACE

   # Verify sufficient resources available
   kubectl top nodes
   kubectl describe nodes | grep -A 5 "Allocated resources"
   ```

1. **Compliance & Security Scans:**

   ```bash
   # Verify image scanning is configured
   [ -f ".github/workflows/security-scan.yml" ] || \
   [ -f ".gitlab-ci.yml" ] && grep -q "container_scanning" .gitlab-ci.yml || \
   echo "WARNING: No automated security scanning configured"

   # Check if policy enforcement is active (OPA/Gatekeeper)
   kubectl get constrainttemplates 2>/dev/null || echo "INFO: No policy engine detected"
   ```

**Validation Checklist:**

- [ ] Docker registry authentication successful
- [ ] Push/pull permissions verified
- [ ] Target namespace/cluster accessible
- [ ] CI/CD pipeline credentials valid
- [ ] Required secrets and configmaps exist
- [ ] Monitoring stack accessible
- [ ] DNS/ingress configuration prepared
- [ ] Resource quotas understood and sufficient
- [ ] Security scanning pipeline configured
- [ ] On-call engineer identified and available
- [ ] Rollback procedure documented and tested in staging

**If any validation fails:**

1. Document the missing prerequisite
1. Create task to resolve (assign to appropriate team)
1. Do not proceed to Phase 1 until all critical items are resolved
1. Mark warnings for later resolution if non-blocking

### Phase 1 – Architecture & Planning

- Use Task tool with `subagent_type="architecture-council"` to validate container architecture and dependency graph.
- Engage `developer-enablement-lead` to outline pipeline stages referencing `commands/tools/development/code-quality/dependency-lifecycle.md`.

### Phase 2 – Image Build & Hardening

- Delegate to `docker-specialist` for multi-stage Dockerfile and caching optimizations.
- `security-auditor` defines scanning policies and supply chain checks.

### Phase 3 – CI/CD & Deployment Strategy

- `deployment-engineer` implements automated pipelines and promotion logic.
- `release-manager` aligns deployment windows and approval gates using `commands/tools/deployment/release-management.md`.

### Phase 4 – Observability & Operations

- `observability-incident-lead` configures instrumentation, alerts, and runbooks via `commands/tools/monitoring/observability-lifecycle.md`.
- `customer-success-lead` and `support-analytics-specialist` prepare readiness communications if customer impact is expected.

## Rollback Procedures

### When to Rollback

Initiate rollback immediately if any of the following conditions occur:

- **Critical Metrics Degraded:**

  - Error rate > 5% for > 5 minutes
  - Response time p95 > 2x baseline for > 10 minutes
  - Availability < 99% for the deployment window

- **Service Health Issues:**

  - Container crash loop detected (>3 restarts in 5 minutes)
  - Health check failures > 20%
  - Resource exhaustion (CPU/memory > 90%)

- **Business Impact:**

  - Customer escalations or support ticket spike
  - Revenue-impacting feature degradation
  - Security vulnerability introduced

- **Deployment Failures:**

  - Canary deployment fails health checks
  - Database migration cannot be completed
  - Required dependencies unavailable

### Rollback Decision Matrix

| Deployment Stage | Rollback Type | Estimated Time | Risk Level |
|-----------------|---------------|----------------|------------|
| Canary (< 5% traffic) | Immediate automatic | < 2 minutes | Low |
| Partial (5-50% traffic) | Coordinated manual | 5-10 minutes | Medium |
| Full production | Emergency procedure | 10-30 minutes | High |
| Post-migration | Complex rollback | 30-60 minutes | Very High |

### Rollback Steps by Platform

#### Kubernetes Rollback

1. **Immediate Traffic Stop:**

   ```bash
   # Scale new deployment to zero
   kubectl scale deployment <service-name> --replicas=0 -n <namespace>

   # Or update service selector to previous version
   kubectl patch service <service-name> -n <namespace> -p '{"spec":{"selector":{"version":"<previous-version>"}}}'
   ```

1. **Restore Previous Version:**

   ```bash
   # Rollback deployment to previous revision
   kubectl rollout undo deployment/<service-name> -n <namespace>

   # Monitor rollback status
   kubectl rollout status deployment/<service-name> -n <namespace>
   ```

1. **Verify Health:**

   ```bash
   # Check pod status
   kubectl get pods -n <namespace> -l app=<service-name>

   # Check logs for errors
   kubectl logs -n <namespace> -l app=<service-name> --tail=100

   # Verify endpoints
   kubectl get endpoints <service-name> -n <namespace>
   ```

#### ECS Rollback

1. **Stop Task Definition Update:**

   ```bash
   # Update service to use previous task definition
   aws ecs update-service \
     --cluster <cluster-name> \
     --service <service-name> \
     --task-definition <service-name>:<previous-revision>

   # Force new deployment
   aws ecs update-service \
     --cluster <cluster-name> \
     --service <service-name> \
     --force-new-deployment
   ```

1. **Monitor Rollback:**

   ```bash
   # Watch service events
   aws ecs describe-services \
     --cluster <cluster-name> \
     --services <service-name> \
     --query 'services[0].events[0:10]'
   ```

#### Docker Swarm Rollback

1. **Revert Service:**
   ```bash
   # Rollback to previous version
   docker service rollback <service-name>

   # Monitor progress
   docker service ps <service-name>
   ```

### Database Migration Rollback

**Before deploying**, ensure migrations are reversible:

1. **Check Reversibility:**

   ```bash
   # Verify down migration exists
   ls migrations/*_<migration-name>.down.sql

   # Test rollback in staging
   migrate -path ./migrations -database "$DATABASE_URL" down 1
   ```

1. **Rollback Procedure:**

   ```bash
   # If deployment fails, immediately rollback migration
   migrate -path ./migrations -database "$DATABASE_URL" down 1

   # Verify data integrity
   psql $DATABASE_URL -c "SELECT COUNT(*) FROM critical_tables;"
   ```

1. **Data Safety Checks:**

   - Never drop columns in forward migrations (mark deprecated instead)
   - Always create down migrations that preserve data
   - Test rollback path in staging before production deployment

### Load Balancer / Traffic Management Rollback

#### NGINX Ingress

```bash
# Update ingress to route to previous version
kubectl patch ingress <ingress-name> -n <namespace> --type=json \
  -p='[{"op": "replace", "path": "/spec/rules/0/http/paths/0/backend/service/name", "value": "<service-name-old>"}]'
```

#### AWS ALB

```bash
# Update target group to previous version
aws elbv2 modify-listener \
  --listener-arn <listener-arn> \
  --default-actions Type=forward,TargetGroupArn=<previous-target-group-arn>
```

#### Feature Flag Rollback

```bash
# Disable feature flag immediately
curl -X PATCH https://feature-flags-api/flags/<flag-name> \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"enabled": false}'
```

### Post-Rollback Verification

After executing rollback, verify:

1. **Service Health:**

   - [ ] All containers/pods running and healthy
   - [ ] Health check endpoints returning 200
   - [ ] Error rate < 1%
   - [ ] Response times within baseline

1. **Traffic Validation:**

   - [ ] Load balancer routing to correct version
   - [ ] No traffic hitting failed deployment
   - [ ] Request success rate > 99%

1. **Data Integrity:**

   - [ ] Database migrations rolled back successfully
   - [ ] No data loss or corruption detected
   - [ ] Critical queries executing normally

1. **Monitoring:**

   - [ ] Metrics returned to baseline
   - [ ] No active alerts firing
   - [ ] Dashboards showing healthy status

1. **Communication:**

   - [ ] Incident team notified of rollback completion
   - [ ] Status page updated if customer-facing
   - [ ] Stakeholders informed of next steps

### Rollback Documentation

After each rollback, document:

- **Timestamp:** When rollback was initiated and completed
- **Trigger:** What condition triggered the rollback decision
- **Method:** Which rollback procedure was used
- **Duration:** Total time from detection to full recovery
- **Data Impact:** Any data that was affected or requires remediation
- **Follow-up:** Incident ticket number and postmortem scheduled

### Prevention: Pre-Deployment Checklist

To minimize rollback risk:

- [ ] Canary deployment configured (start with 5% traffic)
- [ ] Automated health checks in place
- [ ] Database migrations tested and reversible
- [ ] Rollback procedure documented and tested in staging
- [ ] Feature flags configured for instant disable
- [ ] On-call engineer identified and available
- [ ] Monitoring dashboards prepared
- [ ] Rollback approval authority clarified

## Handoffs & Follow-Up

- Schedule post-deployment validation to confirm SLOs and cost baselines.
- Capture lessons learned and update container templates for reuse.
