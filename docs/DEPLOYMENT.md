# Deployment Guide

Comprehensive deployment strategies for the Session Management MCP server across different environments and platforms.

## Overview

The Session Management MCP server can be deployed in various configurations, from simple local development setups to enterprise-scale distributed systems.

## Deployment Strategies

### 1. Local Development

**Single-user, single-machine setup for development.**

#### Standard Installation

```bash
# Clone repository
git clone https://github.com/lesleslie/session-mgmt-mcp.git
cd session-mgmt-mcp

# Install with UV (recommended)
uv sync --extra embeddings

# Verify installation
python -c "from session_mgmt_mcp.server import mcp; print('✅ Ready')"
```

#### Claude Code Configuration

```json
# .mcp.json
{
  "mcpServers": {
    "session-mgmt": {
      "command": "python",
      "args": ["-m", "session_mgmt_mcp.server"],
      "cwd": "/absolute/path/to/session-mgmt-mcp",
      "env": {
        "PYTHONPATH": "/absolute/path/to/session-mgmt-mcp",
        "SESSION_MGMT_LOG_LEVEL": "DEBUG"
      }
    }
  }
}
```

#### Development Environment Variables

```bash
# .env.development
export SESSION_MGMT_LOG_LEVEL=DEBUG
export SESSION_MGMT_DATA_DIR="$HOME/.claude/data"
export EMBEDDING_CACHE_SIZE=100
export MAX_WORKERS=2
```

### 2. Production Single Server

**Single-server production deployment with systemd.**

#### System Service Setup

```bash
# Create dedicated user
sudo useradd --system --shell /bin/false --home /opt/session-mgmt session-mgmt

# Create directories
sudo mkdir -p /opt/session-mgmt/{app,data,logs}
sudo chown -R session-mgmt:session-mgmt /opt/session-mgmt
```

#### Systemd Service

```ini
# /etc/systemd/system/session-mgmt-mcp.service
[Unit]
Description=Session Management MCP Server
After=network.target
Wants=network.target

[Service]
Type=simple
User=session-mgmt
Group=session-mgmt
WorkingDirectory=/opt/session-mgmt/app
Environment=SESSION_MGMT_DATA_DIR=/opt/session-mgmt/data
Environment=SESSION_MGMT_LOG_DIR=/opt/session-mgmt/logs
Environment=SESSION_MGMT_LOG_LEVEL=INFO
Environment=PYTHONPATH=/opt/session-mgmt/app
ExecStart=/opt/session-mgmt/app/.venv/bin/python -m session_mgmt_mcp.server
ExecReload=/bin/kill -HUP $MAINPID
KillMode=mixed
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal

# Security settings
NoNewPrivileges=yes
ProtectSystem=strict
ProtectHome=yes
ReadWritePaths=/opt/session-mgmt/data /opt/session-mgmt/logs
PrivateTmp=yes
ProtectKernelTunables=yes
ProtectControlGroups=yes

[Install]
WantedBy=multi-user.target
```

#### Deployment Script

```bash
#!/bin/bash
# deploy-production.sh

set -e

APP_DIR="/opt/session-mgmt/app"
DATA_DIR="/opt/session-mgmt/data"
LOG_DIR="/opt/session-mgmt/logs"

echo "🚀 Deploying Session Management MCP Server"

# Stop service if running
sudo systemctl stop session-mgmt-mcp || true

# Backup current deployment
if [ -d "$APP_DIR" ]; then
    sudo cp -r "$APP_DIR" "$APP_DIR.backup.$(date +%Y%m%d_%H%M%S)"
fi

# Deploy new version
sudo rm -rf "$APP_DIR"
sudo -u session-mgmt git clone https://github.com/lesleslie/session-mgmt-mcp.git "$APP_DIR"
sudo -u session-mgmt bash -c "cd $APP_DIR && uv sync --extra embeddings"

# Set permissions
sudo chown -R session-mgmt:session-mgmt "$APP_DIR"
sudo chmod +x "$APP_DIR/scripts/"*.sh

# Create directories
sudo mkdir -p "$DATA_DIR" "$LOG_DIR"
sudo chown -R session-mgmt:session-mgmt "$DATA_DIR" "$LOG_DIR"

# Reload and start service
sudo systemctl daemon-reload
sudo systemctl enable session-mgmt-mcp
sudo systemctl start session-mgmt-mcp

# Health check
sleep 5
if sudo systemctl is-active --quiet session-mgmt-mcp; then
    echo "✅ Deployment successful"
else
    echo "❌ Deployment failed"
    sudo journalctl -u session-mgmt-mcp --lines=20
    exit 1
fi
```

### 3. Docker Deployment

**Containerized deployment for consistency and portability.**

#### Dockerfile

```dockerfile
FROM python:3.13-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Create app user
RUN groupadd --system app && useradd --system --group app

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY pyproject.toml uv.lock ./

# Install UV and dependencies
RUN pip install uv
RUN uv sync --extra embeddings --no-dev

# Copy application code
COPY . .

# Set ownership
RUN chown -R app:app /app

# Create data directory
RUN mkdir -p /data && chown app:app /data

# Switch to app user
USER app

# Environment variables
ENV SESSION_MGMT_DATA_DIR=/data
ENV SESSION_MGMT_LOG_LEVEL=INFO
ENV PYTHONPATH=/app

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import session_mgmt_mcp.server; print('healthy')" || exit 1

# Expose port (if needed for API mode)
EXPOSE 8000

# Start server
ENTRYPOINT ["python", "-m", "session_mgmt_mcp.server"]
```

#### Docker Compose

```yaml
# docker-compose.yml
version: '3.8'

services:
  session-mgmt:
    build: .
    container_name: session-mgmt-mcp
    restart: unless-stopped
    environment:
      - SESSION_MGMT_DATA_DIR=/data
      - SESSION_MGMT_LOG_LEVEL=INFO
      - EMBEDDING_CACHE_SIZE=1000
      - MAX_WORKERS=4
    volumes:
      - session_data:/data
      - session_logs:/logs
    ports:
      - "8000:8000"  # If API mode enabled
    networks:
      - session-network
    healthcheck:
      test: ["CMD", "python", "-c", "import session_mgmt_mcp.server; print('healthy')"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s

  # Optional: Redis for caching
  redis:
    image: redis:7-alpine
    container_name: session-mgmt-redis
    restart: unless-stopped
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    networks:
      - session-network
    command: redis-server --appendonly yes

  # Optional: PostgreSQL for external storage
  postgres:
    image: postgres:15-alpine
    container_name: session-mgmt-postgres
    restart: unless-stopped
    environment:
      - POSTGRES_DB=sessionmgmt
      - POSTGRES_USER=sessionuser
      - POSTGRES_PASSWORD_FILE=/run/secrets/postgres_password
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./init.sql:/docker-entrypoint-initdb.d/init.sql
    networks:
      - session-network
    secrets:
      - postgres_password

volumes:
  session_data:
    driver: local
  session_logs:
    driver: local
  redis_data:
    driver: local
  postgres_data:
    driver: local

networks:
  session-network:
    driver: bridge

secrets:
  postgres_password:
    file: ./secrets/postgres_password.txt
```

#### Docker Deployment Script

```bash
#!/bin/bash
# docker-deploy.sh

set -e

echo "🐳 Deploying Session Management MCP with Docker"

# Create secrets directory
mkdir -p secrets
echo "$(openssl rand -base64 32)" > secrets/postgres_password.txt
chmod 600 secrets/postgres_password.txt

# Build and deploy
docker compose build --no-cache
docker compose up -d

# Wait for services
echo "⏳ Waiting for services to start..."
sleep 30

# Health check
if docker compose ps | grep -q "Up"; then
    echo "✅ Docker deployment successful"
    docker compose ps
else
    echo "❌ Docker deployment failed"
    docker compose logs
    exit 1
fi

# Show logs
echo "📋 Service logs:"
docker compose logs --tail=20 session-mgmt
```

### 4. Kubernetes Deployment

**Scalable, enterprise-ready Kubernetes deployment.**

#### Namespace and ConfigMap

```yaml
# k8s/namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: session-mgmt
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: session-mgmt-config
  namespace: session-mgmt
data:
  SESSION_MGMT_LOG_LEVEL: "INFO"
  EMBEDDING_CACHE_SIZE: "1000"
  MAX_WORKERS: "4"
  REDIS_URL: "redis://redis-service:6379"
```

#### Secrets

```yaml
# k8s/secrets.yaml
apiVersion: v1
kind: Secret
metadata:
  name: session-mgmt-secrets
  namespace: session-mgmt
type: Opaque
data:
  postgres-password: <base64-encoded-password>
  api-key: <base64-encoded-api-key>
```

#### Persistent Volume Claims

```yaml
# k8s/storage.yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: session-data-pvc
  namespace: session-mgmt
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 10Gi
  storageClassName: fast-ssd
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: session-logs-pvc
  namespace: session-mgmt
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 5Gi
  storageClassName: standard
```

#### Deployment

```yaml
# k8s/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: session-mgmt-mcp
  namespace: session-mgmt
  labels:
    app: session-mgmt-mcp
spec:
  replicas: 3
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxUnavailable: 1
      maxSurge: 1
  selector:
    matchLabels:
      app: session-mgmt-mcp
  template:
    metadata:
      labels:
        app: session-mgmt-mcp
      annotations:
        prometheus.io/scrape: "true"
        prometheus.io/port: "9090"
        prometheus.io/path: "/metrics"
    spec:
      securityContext:
        runAsNonRoot: true
        runAsUser: 1000
        runAsGroup: 1000
        fsGroup: 1000
      containers:
      - name: session-mgmt
        image: session-mgmt-mcp:latest
        imagePullPolicy: Always
        ports:
        - containerPort: 8000
          name: http
        - containerPort: 9090
          name: metrics
        env:
        - name: SESSION_MGMT_DATA_DIR
          value: "/data"
        - name: SESSION_MGMT_LOG_DIR
          value: "/logs"
        envFrom:
        - configMapRef:
            name: session-mgmt-config
        - secretRef:
            name: session-mgmt-secrets
        volumeMounts:
        - name: session-data
          mountPath: /data
        - name: session-logs
          mountPath: /logs
        resources:
          requests:
            memory: "512Mi"
            cpu: "250m"
          limits:
            memory: "2Gi"
            cpu: "1000m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
          timeoutSeconds: 5
          failureThreshold: 3
        readinessProbe:
          httpGet:
            path: /ready
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
          timeoutSeconds: 3
          failureThreshold: 3
        startupProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 10
          timeoutSeconds: 5
          failureThreshold: 30
      volumes:
      - name: session-data
        persistentVolumeClaim:
          claimName: session-data-pvc
      - name: session-logs
        persistentVolumeClaim:
          claimName: session-logs-pvc
      affinity:
        podAntiAffinity:
          preferredDuringSchedulingIgnoredDuringExecution:
          - weight: 100
            podAffinityTerm:
              labelSelector:
                matchExpressions:
                - key: app
                  operator: In
                  values:
                  - session-mgmt-mcp
              topologyKey: kubernetes.io/hostname
```

#### Service and Ingress

```yaml
# k8s/service.yaml
apiVersion: v1
kind: Service
metadata:
  name: session-mgmt-service
  namespace: session-mgmt
  labels:
    app: session-mgmt-mcp
spec:
  type: ClusterIP
  ports:
  - port: 80
    targetPort: 8000
    protocol: TCP
    name: http
  - port: 9090
    targetPort: 9090
    protocol: TCP
    name: metrics
  selector:
    app: session-mgmt-mcp
---
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: session-mgmt-ingress
  namespace: session-mgmt
  annotations:
    nginx.ingress.kubernetes.io/rewrite-target: /
    cert-manager.io/cluster-issuer: letsencrypt-prod
    nginx.ingress.kubernetes.io/rate-limit: "100"
    nginx.ingress.kubernetes.io/rate-limit-window: "1m"
spec:
  tls:
  - hosts:
    - session-mgmt.example.com
    secretName: session-mgmt-tls
  rules:
  - host: session-mgmt.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: session-mgmt-service
            port:
              number: 80
```

#### Horizontal Pod Autoscaler

```yaml
# k8s/hpa.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: session-mgmt-hpa
  namespace: session-mgmt
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: session-mgmt-mcp
  minReplicas: 3
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
  behavior:
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
      - type: Percent
        value: 50
        periodSeconds: 60
    scaleUp:
      stabilizationWindowSeconds: 60
      policies:
      - type: Percent
        value: 100
        periodSeconds: 15
```

#### Kubernetes Deployment Script

```bash
#!/bin/bash
# k8s-deploy.sh

set -e

NAMESPACE="session-mgmt"

echo "☸️ Deploying Session Management MCP to Kubernetes"

# Apply manifests in order
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/storage.yaml
kubectl apply -f k8s/secrets.yaml
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
kubectl apply -f k8s/hpa.yaml

# Wait for deployment
echo "⏳ Waiting for deployment to be ready..."
kubectl wait --for=condition=available --timeout=300s deployment/session-mgmt-mcp -n $NAMESPACE

# Show status
echo "📋 Deployment status:"
kubectl get pods,svc,hpa -n $NAMESPACE

# Health check
echo "🔍 Health check:"
kubectl port-forward -n $NAMESPACE svc/session-mgmt-service 8080:80 &
PORT_FORWARD_PID=$!
sleep 5

if curl -f http://localhost:8080/health; then
    echo "✅ Kubernetes deployment successful"
else
    echo "❌ Health check failed"
    kubectl logs -n $NAMESPACE -l app=session-mgmt-mcp --tail=20
fi

kill $PORT_FORWARD_PID
```

### 5. Cloud Platform Deployments

#### AWS ECS Deployment

```json
{
  "family": "session-mgmt-mcp",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "1024",
  "memory": "2048",
  "executionRoleArn": "arn:aws:iam::account:role/ecsTaskExecutionRole",
  "taskRoleArn": "arn:aws:iam::account:role/ecsTaskRole",
  "containerDefinitions": [
    {
      "name": "session-mgmt",
      "image": "your-account.dkr.ecr.region.amazonaws.com/session-mgmt-mcp:latest",
      "essential": true,
      "portMappings": [
        {
          "containerPort": 8000,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {
          "name": "SESSION_MGMT_DATA_DIR",
          "value": "/data"
        },
        {
          "name": "SESSION_MGMT_LOG_LEVEL",
          "value": "INFO"
        }
      ],
      "secrets": [
        {
          "name": "DATABASE_URL",
          "valueFrom": "arn:aws:secretsmanager:region:account:secret:session-mgmt/database-url"
        }
      ],
      "mountPoints": [
        {
          "sourceVolume": "session-data",
          "containerPath": "/data"
        }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/session-mgmt-mcp",
          "awslogs-region": "us-west-2",
          "awslogs-stream-prefix": "ecs"
        }
      },
      "healthCheck": {
        "command": [
          "CMD-SHELL",
          "python -c 'import session_mgmt_mcp.server; print(\"healthy\")'"
        ],
        "interval": 30,
        "timeout": 5,
        "retries": 3,
        "startPeriod": 60
      }
    }
  ],
  "volumes": [
    {
      "name": "session-data",
      "efsVolumeConfiguration": {
        "fileSystemId": "fs-12345678",
        "rootDirectory": "/",
        "transitEncryption": "ENABLED"
      }
    }
  ]
}
```

#### Google Cloud Run Deployment

```yaml
# cloudrun.yaml
apiVersion: serving.knative.dev/v1
kind: Service
metadata:
  name: session-mgmt-mcp
  namespace: default
  annotations:
    run.googleapis.com/ingress: all
    run.googleapis.com/execution-environment: gen2
spec:
  template:
    metadata:
      annotations:
        autoscaling.knative.dev/minScale: "1"
        autoscaling.knative.dev/maxScale: "10"
        run.googleapis.com/cpu-throttling: "false"
        run.googleapis.com/memory: "2Gi"
        run.googleapis.com/cpu: "1000m"
    spec:
      containerConcurrency: 100
      timeoutSeconds: 300
      containers:
      - image: gcr.io/project-id/session-mgmt-mcp:latest
        ports:
        - containerPort: 8000
        env:
        - name: SESSION_MGMT_DATA_DIR
          value: "/data"
        - name: SESSION_MGMT_LOG_LEVEL
          value: "INFO"
        - name: GOOGLE_CLOUD_PROJECT
          value: "project-id"
        volumeMounts:
        - name: session-data
          mountPath: /data
        resources:
          limits:
            memory: "2Gi"
            cpu: "1000m"
        startupProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 10
          timeoutSeconds: 5
          failureThreshold: 3
      volumes:
      - name: session-data
        csi:
          driver: gcsfuse.csi.storage.gke.io
          volumeAttributes:
            bucketName: session-mgmt-data-bucket
            mountOptions: "implicit-dirs"
```

#### Azure Container Apps

```json
{
  "location": "eastus2",
  "properties": {
    "managedEnvironmentId": "/subscriptions/sub-id/resourceGroups/rg/providers/Microsoft.App/managedEnvironments/env-name",
    "configuration": {
      "ingress": {
        "external": true,
        "targetPort": 8000,
        "allowInsecure": false,
        "traffic": [
          {
            "weight": 100,
            "latestRevision": true
          }
        ]
      },
      "secrets": [
        {
          "name": "database-url",
          "keyVaultUrl": "https://keyvault.vault.azure.net/secrets/database-url"
        }
      ],
      "registries": [
        {
          "server": "registry.azurecr.io",
          "username": "registry-username",
          "passwordSecretRef": "registry-password"
        }
      ]
    },
    "template": {
      "containers": [
        {
          "image": "registry.azurecr.io/session-mgmt-mcp:latest",
          "name": "session-mgmt",
          "env": [
            {
              "name": "SESSION_MGMT_DATA_DIR",
              "value": "/data"
            },
            {
              "name": "SESSION_MGMT_LOG_LEVEL",
              "value": "INFO"
            },
            {
              "name": "DATABASE_URL",
              "secretRef": "database-url"
            }
          ],
          "resources": {
            "cpu": 1,
            "memory": "2Gi"
          },
          "probes": [
            {
              "type": "startup",
              "httpGet": {
                "path": "/health",
                "port": 8000
              },
              "initialDelaySeconds": 10,
              "periodSeconds": 10
            }
          ]
        }
      ],
      "scale": {
        "minReplicas": 1,
        "maxReplicas": 10,
        "rules": [
          {
            "name": "cpu-scaling",
            "custom": {
              "type": "cpu",
              "metadata": {
                "type": "Utilization",
                "value": "70"
              }
            }
          }
        ]
      }
    }
  }
}
```

## Monitoring and Observability

### Prometheus Configuration

```yaml
# prometheus.yml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'session-mgmt-mcp'
    static_configs:
      - targets: ['localhost:9090']
    metrics_path: /metrics
    scrape_interval: 30s

rule_files:
  - "session-mgmt-alerts.yml"

alerting:
  alertmanagers:
    - static_configs:
        - targets:
          - alertmanager:9093
```

### Alert Rules

```yaml
# session-mgmt-alerts.yml
groups:
  - name: session-mgmt
    rules:
      - alert: HighErrorRate
        expr: rate(session_mgmt_errors_total[5m]) > 0.1
        for: 2m
        labels:
          severity: warning
        annotations:
          summary: "High error rate in Session Management MCP"
          description: "Error rate is {{ $value }} errors per second"

      - alert: HighMemoryUsage
        expr: session_mgmt_memory_usage_mb > 1500
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High memory usage"
          description: "Memory usage is {{ $value }}MB"

      - alert: ServiceDown
        expr: up{job="session-mgmt-mcp"} == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Session Management MCP is down"
          description: "Service has been down for more than 1 minute"
```

### Grafana Dashboard

```json
{
  "dashboard": {
    "id": null,
    "title": "Session Management MCP Server",
    "tags": ["session-mgmt", "mcp"],
    "timezone": "browser",
    "panels": [
      {
        "id": 1,
        "title": "Request Rate",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(session_mgmt_requests_total[5m])",
            "legendFormat": "{{method}} {{endpoint}}"
          }
        ],
        "yAxes": [
          {
            "label": "Requests per second"
          }
        ]
      },
      {
        "id": 2,
        "title": "Response Time",
        "type": "graph",
        "targets": [
          {
            "expr": "histogram_quantile(0.95, rate(session_mgmt_request_duration_seconds_bucket[5m]))",
            "legendFormat": "95th percentile"
          },
          {
            "expr": "histogram_quantile(0.50, rate(session_mgmt_request_duration_seconds_bucket[5m]))",
            "legendFormat": "50th percentile"
          }
        ]
      },
      {
        "id": 3,
        "title": "Active Sessions",
        "type": "singlestat",
        "targets": [
          {
            "expr": "session_mgmt_active_sessions"
          }
        ]
      },
      {
        "id": 4,
        "title": "Memory Usage",
        "type": "graph",
        "targets": [
          {
            "expr": "session_mgmt_memory_usage_mb"
          }
        ]
      },
      {
        "id": 5,
        "title": "Error Rate",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(session_mgmt_errors_total[5m])"
          }
        ]
      }
    ]
  }
}
```

## Security Considerations

### Production Security Checklist

- [ ] **TLS/HTTPS**: Enable TLS for all communications
- [ ] **Authentication**: Implement proper authentication mechanism
- [ ] **Authorization**: Role-based access control
- [ ] **Input Validation**: Validate all inputs to prevent injection
- [ ] **Secrets Management**: Use proper secret management systems
- [ ] **Network Security**: Implement proper firewall rules
- [ ] **Container Security**: Scan images for vulnerabilities
- [ ] **Least Privilege**: Run with minimal required permissions
- [ ] **Audit Logging**: Log all security-relevant events
- [ ] **Regular Updates**: Keep dependencies updated

### SSL/TLS Configuration

```nginx
# nginx-ssl.conf
server {
    listen 443 ssl http2;
    server_name session-mgmt.example.com;

    ssl_certificate /etc/ssl/certs/session-mgmt.crt;
    ssl_certificate_key /etc/ssl/private/session-mgmt.key;

    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512:ECDHE-RSA-AES256-GCM-SHA384:DHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;

    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;

    add_header Strict-Transport-Security "max-age=63072000" always;
    add_header X-Content-Type-Options nosniff;
    add_header X-Frame-Options DENY;
    add_header X-XSS-Protection "1; mode=block";

    location / {
        proxy_pass http://session-mgmt-backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## Backup and Disaster Recovery

### Database Backup Strategy

```bash
#!/bin/bash
# backup-database.sh

set -e

BACKUP_DIR="/opt/session-mgmt/backups"
DATE=$(date +%Y%m%d_%H%M%S)
DATA_DIR="/opt/session-mgmt/data"

echo "🔄 Starting database backup"

# Create backup directory
mkdir -p "$BACKUP_DIR"

# Backup DuckDB files
tar -czf "$BACKUP_DIR/database_$DATE.tar.gz" -C "$DATA_DIR" .

# Upload to S3 (optional)
if command -v aws >/dev/null 2>&1; then
    aws s3 cp "$BACKUP_DIR/database_$DATE.tar.gz" \
        s3://session-mgmt-backups/database/
fi

# Cleanup old backups (keep 30 days)
find "$BACKUP_DIR" -name "database_*.tar.gz" -mtime +30 -delete

echo "✅ Backup completed: database_$DATE.tar.gz"
```

### Automated Backup with Cron

```bash
# Add to crontab
0 2 * * * /opt/session-mgmt/scripts/backup-database.sh >> /var/log/session-mgmt-backup.log 2>&1
```

### Disaster Recovery Plan

```bash
#!/bin/bash
# disaster-recovery.sh

set -e

BACKUP_FILE="$1"
DATA_DIR="/opt/session-mgmt/data"
RECOVERY_DIR="/opt/session-mgmt/recovery"

if [ -z "$BACKUP_FILE" ]; then
    echo "Usage: $0 <backup-file>"
    exit 1
fi

echo "🚨 Starting disaster recovery process"

# Stop service
sudo systemctl stop session-mgmt-mcp

# Create recovery directory
mkdir -p "$RECOVERY_DIR"

# Backup current state (in case recovery fails)
if [ -d "$DATA_DIR" ]; then
    mv "$DATA_DIR" "$RECOVERY_DIR/current_$(date +%Y%m%d_%H%M%S)"
fi

# Restore from backup
mkdir -p "$DATA_DIR"
tar -xzf "$BACKUP_FILE" -C "$DATA_DIR"

# Set permissions
chown -R session-mgmt:session-mgmt "$DATA_DIR"

# Start service
sudo systemctl start session-mgmt-mcp

# Health check
sleep 10
if sudo systemctl is-active --quiet session-mgmt-mcp; then
    echo "✅ Disaster recovery successful"
else
    echo "❌ Disaster recovery failed - check logs"
    sudo journalctl -u session-mgmt-mcp --lines=50
    exit 1
fi
```

## Performance Optimization

### Database Optimization

```sql
-- DuckDB optimization settings
PRAGMA memory_limit='2GB';
PRAGMA threads=8;
PRAGMA checkpoint_threshold='1GB';

-- Create optimal indices
CREATE INDEX idx_conversations_project_timestamp
ON conversations(project, timestamp DESC);

CREATE INDEX idx_conversations_embedding
ON conversations USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- Optimize table for vector operations
ALTER TABLE conversations
SET (embedding_compression = 'pq');
```

### Resource Limits

```yaml
# k8s resource limits
resources:
  requests:
    memory: "512Mi"
    cpu: "250m"
  limits:
    memory: "2Gi"
    cpu: "1000m"

# JVM-like settings for memory management
env:
- name: EMBEDDING_HEAP_SIZE
  value: "512m"
- name: CACHE_MAX_SIZE
  value: "256m"
```

### Load Testing

```python
# load-test.py
import asyncio
import aiohttp
import time
from concurrent.futures import ThreadPoolExecutor


async def load_test():
    """Simple load test for the MCP server."""

    async def make_request(session, url):
        async with session.get(url) as response:
            return await response.json()

    async with aiohttp.ClientSession() as session:
        tasks = []

        # Create 100 concurrent requests
        for i in range(100):
            task = make_request(session, "http://localhost:8000/health")
            tasks.append(task)

        start_time = time.time()
        results = await asyncio.gather(*tasks)
        end_time = time.time()

        print(f"Completed 100 requests in {end_time - start_time:.2f} seconds")
        print(
            f"Success rate: {sum(1 for r in results if r.get('status') == 'healthy')}/100"
        )


if __name__ == "__main__":
    asyncio.run(load_test())
```

## Troubleshooting

### Common Deployment Issues

#### Service Won't Start

```bash
# Check service status
sudo systemctl status session-mgmt-mcp

# View logs
sudo journalctl -u session-mgmt-mcp -f

# Check permissions
ls -la /opt/session-mgmt/
sudo -u session-mgmt python -c "import session_mgmt_mcp; print('OK')"
```

#### Memory Issues

```bash
# Check memory usage
free -h
ps aux | grep session-mgmt

# Adjust memory limits
export MAX_MEMORY_MB=1024
sudo systemctl restart session-mgmt-mcp
```

#### Database Connection Issues

```bash
# Check database files
ls -la /opt/session-mgmt/data/

# Test database connection
sudo -u session-mgmt python -c "
import duckdb
conn = duckdb.connect('/opt/session-mgmt/data/reflections.db')
print('Database connection OK')
conn.close()
"
```

### Health Check Scripts

```bash
#!/bin/bash
# health-check.sh

echo "🔍 Session Management MCP Health Check"

# Service status
if systemctl is-active --quiet session-mgmt-mcp; then
    echo "✅ Service is running"
else
    echo "❌ Service is not running"
    exit 1
fi

# Memory check
MEMORY_USAGE=$(ps -o pid,vsz,rss,comm -p $(pgrep -f session-mgmt) | tail -n +2 | awk '{sum+=$3} END {print sum/1024}')
echo "📊 Memory usage: ${MEMORY_USAGE}MB"

# Disk space check
DISK_USAGE=$(df -h /opt/session-mgmt/data | tail -1 | awk '{print $5}' | sed 's/%//')
echo "💽 Disk usage: ${DISK_USAGE}%"

if [ "$DISK_USAGE" -gt 80 ]; then
    echo "⚠️ High disk usage"
fi

# Database check
if sudo -u session-mgmt python -c "
import duckdb
conn = duckdb.connect('/opt/session-mgmt/data/reflections.db')
conn.execute('SELECT COUNT(*) FROM conversations').fetchone()
conn.close()
" >/dev/null 2>&1; then
    echo "✅ Database is accessible"
else
    echo "❌ Database connection failed"
    exit 1
fi

echo "✅ All health checks passed"
```

______________________________________________________________________

**Next Steps:**

- Review [CONFIGURATION.md](CONFIGURATION.md) for advanced configuration options
- See [INTEGRATION.md](INTEGRATION.md) for integrating with existing tools
- Check [MCP_TOOLS_REFERENCE.md](MCP_TOOLS_REFERENCE.md) for complete tool documentation
