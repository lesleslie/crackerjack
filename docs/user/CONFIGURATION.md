# Configuration Reference

Complete configuration guide for the Session Management MCP server with advanced setup options.

## Overview

The Session Management MCP server is designed to work with minimal configuration, but provides extensive customization options for advanced users and enterprise deployments.

## Configuration Files

### Primary Configuration

#### `.mcp.json` - MCP Server Configuration

Location: Project root or `~/.config/claude/` directory

```json
{
  "mcpServers": {
    "session-mgmt": {
      "command": "python",
      "args": ["-m", "session_mgmt_mcp.server"],
      "cwd": "/absolute/path/to/session-mgmt-mcp",
      "env": {
        "PYTHONPATH": "/absolute/path/to/session-mgmt-mcp",
        "SESSION_MGMT_LOG_LEVEL": "INFO",
        "SESSION_MGMT_DATA_DIR": "/custom/data/path",
        "EMBEDDING_MODEL": "all-MiniLM-L6-v2",
        "MAX_MEMORY_MB": "1024"
      }
    }
  }
}
```

#### Alternative: uvx Installation

```json
{
  "mcpServers": {
    "session-mgmt": {
      "command": "uvx",
      "args": ["session-mgmt-mcp"],
      "env": {
        "SESSION_MGMT_LOG_LEVEL": "DEBUG"
      }
    }
  }
}
```

### Secondary Configuration

#### `pyproject.toml` - Project Dependencies

Controls which features are available:

```toml
[project.optional-dependencies]
embeddings = [
    "onnxruntime>=1.16.0",
    "transformers>=4.35.0",
    "numpy>=1.24.0"
]
```

## Environment Variables

### Core Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `SESSION_MGMT_DATA_DIR` | `~/.claude/data/` | Directory for database storage |
| `SESSION_MGMT_LOG_LEVEL` | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR) |
| `SESSION_MGMT_LOG_DIR` | `~/.claude/logs/` | Directory for log files |

### Memory System Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | ONNX model for embeddings |
| `EMBEDDING_CACHE_SIZE` | `1000` | Number of cached embeddings |
| `MAX_MEMORY_MB` | `512` | Maximum memory for embedding model |
| `VECTOR_SIMILARITY_THRESHOLD` | `0.7` | Default similarity threshold |

### Performance Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `MAX_WORKERS` | `4` | Thread pool size for embeddings |
| `DB_CONNECTION_TIMEOUT` | `30` | Database connection timeout (seconds) |
| `CHUNK_SIZE` | `4000` | Token limit before response chunking |
| `MAX_SEARCH_RESULTS` | `50` | Maximum search results per query |

### Security Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `TRUSTED_OPERATIONS` | `[]` | JSON array of auto-approved operations |
| `PERMISSION_TIMEOUT` | `300` | Permission cache timeout (seconds) |
| `RATE_LIMIT_REQUESTS` | `100` | Requests per minute limit |

## Advanced Configuration

### Custom Data Directory Structure

```bash
# Custom data directory setup
export SESSION_MGMT_DATA_DIR="/opt/session-mgmt/data"
mkdir -p "$SESSION_MGMT_DATA_DIR"/{db,cache,temp}
chmod 750 "$SESSION_MGMT_DATA_DIR"
```

### Embedding Model Configuration

#### Using Different ONNX Models

```bash
# Download custom model
wget https://huggingface.co/sentence-transformers/all-MiniLM-L12-v2/resolve/main/model.onnx
export EMBEDDING_MODEL_PATH="/path/to/custom/model.onnx"
```

#### Fallback Configuration

```json
{
  "env": {
    "DISABLE_EMBEDDINGS": "true",
    "FALLBACK_TO_TEXT_SEARCH": "true"
  }
}
```

### Database Configuration

#### Custom DuckDB Settings

```python
# In custom configuration file
DATABASE_CONFIG = {
    "memory_limit": "2GB",
    "threads": 8,
    "checkpoint_threshold": "1GB",
    "wal_autocheckpoint": 1000,
}
```

#### Connection Pooling

```bash
export DB_POOL_SIZE=10
export DB_POOL_MAX_OVERFLOW=20
export DB_POOL_TIMEOUT=30
```

## Production Configuration

### Docker Deployment

```dockerfile
FROM python:3.13-slim

ENV SESSION_MGMT_DATA_DIR=/data/session-mgmt
ENV SESSION_MGMT_LOG_LEVEL=INFO
ENV EMBEDDING_MODEL=all-MiniLM-L6-v2
ENV MAX_WORKERS=8

VOLUME ["/data/session-mgmt"]

COPY . /app
WORKDIR /app
RUN uv sync --extra embeddings

ENTRYPOINT ["python", "-m", "session_mgmt_mcp.server"]
```

### Kubernetes Configuration

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: session-mgmt-config
data:
  SESSION_MGMT_LOG_LEVEL: "INFO"
  EMBEDDING_MODEL: "all-MiniLM-L6-v2"
  MAX_WORKERS: "4"
  VECTOR_SIMILARITY_THRESHOLD: "0.75"
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: session-mgmt-mcp
spec:
  replicas: 2
  selector:
    matchLabels:
      app: session-mgmt-mcp
  template:
    spec:
      containers:
      - name: session-mgmt
        image: session-mgmt-mcp:latest
        envFrom:
        - configMapRef:
            name: session-mgmt-config
        volumeMounts:
        - name: data-volume
          mountPath: /data/session-mgmt
        resources:
          requests:
            memory: "512Mi"
            cpu: "250m"
          limits:
            memory: "2Gi"
            cpu: "1000m"
```

### Load Balancing Configuration

```nginx
upstream session_mgmt_backend {
    server localhost:8000;
    server localhost:8001;
    server localhost:8002;
}

server {
    listen 80;
    server_name session-mgmt.example.com;

    location / {
        proxy_pass http://session_mgmt_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## Multi-Environment Setup

### Development Environment

```bash
# .env.development
SESSION_MGMT_LOG_LEVEL=DEBUG
EMBEDDING_CACHE_SIZE=100
MAX_WORKERS=2
DISABLE_RATE_LIMITING=true
```

### Staging Environment

```bash
# .env.staging
SESSION_MGMT_LOG_LEVEL=INFO
EMBEDDING_CACHE_SIZE=500
MAX_WORKERS=4
TRUSTED_OPERATIONS='["uv_sync", "git_commit"]'
```

### Production Environment

```bash
# .env.production
SESSION_MGMT_LOG_LEVEL=WARNING
EMBEDDING_CACHE_SIZE=2000
MAX_WORKERS=8
RATE_LIMIT_REQUESTS=50
PERMISSION_TIMEOUT=600
```

## Monitoring Configuration

### Health Check Endpoint

```json
{
  "env": {
    "ENABLE_HEALTH_CHECK": "true",
    "HEALTH_CHECK_PORT": "8080"
  }
}
```

### Metrics Collection

```bash
# Prometheus metrics
export ENABLE_METRICS=true
export METRICS_PORT=9090
export METRICS_PATH=/metrics
```

### Logging Configuration

```json
{
  "logging": {
    "version": 1,
    "handlers": {
      "file": {
        "class": "logging.FileHandler",
        "filename": "/var/log/session-mgmt/server.log",
        "formatter": "detailed"
      },
      "syslog": {
        "class": "logging.handlers.SysLogHandler",
        "address": "/dev/log"
      }
    },
    "formatters": {
      "detailed": {
        "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
      }
    }
  }
}
```

## Security Configuration

### Authentication Setup

```bash
# API key authentication
export SESSION_MGMT_API_KEY="your-secure-api-key"
export SESSION_MGMT_REQUIRE_AUTH=true
```

### TLS Configuration

```json
{
  "env": {
    "TLS_CERT_PATH": "/etc/ssl/certs/session-mgmt.crt",
    "TLS_KEY_PATH": "/etc/ssl/private/session-mgmt.key",
    "ENABLE_TLS": "true"
  }
}
```

### Access Control

```bash
# IP whitelist
export ALLOWED_IPS='["127.0.0.1", "10.0.0.0/8", "192.168.0.0/16"]'

# User permissions
export USER_PERMISSIONS='{
  "admin": ["*"],
  "developer": ["search", "store", "checkpoint"],
  "readonly": ["search", "status"]
}'
```

## Backup Configuration

### Database Backup

```bash
# Automated backup script
#!/bin/bash
BACKUP_DIR="/backup/session-mgmt/$(date +%Y%m%d)"
mkdir -p "$BACKUP_DIR"

# Copy database files
cp -r "$SESSION_MGMT_DATA_DIR"/*.db "$BACKUP_DIR/"

# Compress and encrypt
tar -czf "$BACKUP_DIR.tar.gz" "$BACKUP_DIR"
gpg --encrypt --recipient admin@company.com "$BACKUP_DIR.tar.gz"
```

### Automated Backup Schedule

```bash
# Crontab entry
0 2 * * * /usr/local/bin/backup-session-mgmt.sh
```

## Troubleshooting Configuration

### Debug Mode

```bash
# Enable comprehensive debugging
export SESSION_MGMT_LOG_LEVEL=DEBUG
export PYTHONPATH="$PWD"
export EMBEDDING_DEBUG=true
python -m session_mgmt_mcp.server --debug
```

### Performance Profiling

```bash
# Enable performance profiling
export ENABLE_PROFILING=true
export PROFILING_OUTPUT_DIR=/tmp/session-mgmt-profiles/
```

### Memory Debugging

```bash
# Memory leak detection
export PYTHONMALLOC=debug
export PYTHONFAULTHANDLER=1
python -X dev -m session_mgmt_mcp.server
```

## Migration Configuration

### Version Migration

```bash
# Database schema migration
export ENABLE_AUTO_MIGRATION=true
export BACKUP_BEFORE_MIGRATION=true
export MIGRATION_TIMEOUT=300
```

### Data Import/Export

```json
{
  "migration": {
    "import_format": "json",
    "export_format": "json",
    "batch_size": 1000,
    "validate_imports": true
  }
}
```

## Configuration Validation

### Validation Script

```python
#!/usr/bin/env python3
"""Validate Session Management MCP configuration."""

import json
import os
from pathlib import Path


def validate_config():
    """Validate all configuration settings."""

    # Check required paths
    data_dir = Path(os.getenv("SESSION_MGMT_DATA_DIR", "~/.claude/data")).expanduser()
    assert data_dir.exists(), f"Data directory missing: {data_dir}"

    # Check MCP configuration
    mcp_config_path = Path(".mcp.json")
    if mcp_config_path.exists():
        with open(mcp_config_path) as f:
            config = json.load(f)

        assert "session-mgmt" in config.get("mcpServers", {}), (
            "session-mgmt server not configured"
        )

    # Check embedding model availability
    try:
        import onnxruntime
        import transformers

        print("✅ Embedding dependencies available")
    except ImportError:
        print("⚠️ Embedding dependencies missing - text search fallback will be used")

    print("✅ Configuration validation passed")


if __name__ == "__main__":
    validate_config()
```

## Best Practices

### Configuration Management

1. **Use Environment Variables**: Keep sensitive data out of config files
1. **Version Control**: Track configuration changes in git
1. **Environment-Specific**: Use different configs for dev/staging/prod
1. **Documentation**: Document all custom configuration changes
1. **Validation**: Test configuration changes in staging first

### Security Best Practices

1. **Encrypt Sensitive Data**: Use tools like sops or Vault
1. **Rotate Keys**: Regular API key and certificate rotation
1. **Principle of Least Privilege**: Minimal permissions by default
1. **Audit Logs**: Enable comprehensive logging for security events
1. **Network Security**: Use firewalls and VPNs for production

### Performance Optimization

1. **Resource Limits**: Set appropriate memory and CPU limits
1. **Connection Pooling**: Configure database connection pooling
1. **Caching**: Enable embedding caching for better performance
1. **Monitoring**: Track performance metrics and set alerts
1. **Scaling**: Plan for horizontal scaling in high-load scenarios

______________________________________________________________________

**Next Steps**: See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed system architecture and [DEPLOYMENT.md](DEPLOYMENT.md) for deployment strategies.
