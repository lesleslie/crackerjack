# Integration Guide

Comprehensive guide for integrating the Session Management MCP server with existing tools, workflows, and development environments.

## Overview

The Session Management MCP server is designed to integrate seamlessly with existing development workflows while providing enhanced session management and memory capabilities.

## Claude Code Integration

### Primary Integration

The Session Management MCP server integrates directly with Claude Code through the MCP (Model Context Protocol).

#### Setup

1. **Install the MCP server**:

   ```bash
   git clone https://github.com/lesleslie/session-mgmt-mcp.git
   cd session-mgmt-mcp
   uv sync --extra embeddings
   ```

1. **Configure Claude Code** (`.mcp.json`):

   ```json
   {
     "mcpServers": {
       "session-mgmt": {
         "command": "python",
         "args": ["-m", "session_mgmt_mcp.server"],
         "cwd": "/absolute/path/to/session-mgmt-mcp",
         "env": {
           "PYTHONPATH": "/absolute/path/to/session-mgmt-mcp"
         }
       }
     }
   }
   ```

1. **Restart Claude Code** to load the MCP server

#### Available Slash Commands

Once configured, these slash commands become available in Claude Code:

```bash
# Session Management
/session-mgmt:start             # Initialize session with project analysis
/session-mgmt:checkpoint        # Mid-session quality assessment
/session-mgmt:end              # Complete session cleanup
/session-mgmt:status           # Current session status

# Memory & Search
/session-mgmt:reflect_on_past   # Search conversation history
/session-mgmt:store_reflection  # Save important insights
/session-mgmt:quick_search     # Fast overview search
/session-mgmt:search_by_file   # Find file-specific conversations
/session-mgmt:search_by_concept # Search by development concepts
```

## Development Tool Integration

### Git Integration

The MCP server provides intelligent Git integration with automatic checkpointing.

#### Automatic Checkpoint Commits

```python
# Automatic checkpoint commits during /session-mgmt:checkpoint
commit_message = f"""checkpoint: {project_name} (quality: {score}/100)

Session: {session_id}
Quality Metrics:
- Project Health: {health}/100
- Permissions: {permissions}/100
- Tools Available: {tools}/100

🤖 Generated with Session Management MCP
"""
```

#### Git Hooks Integration

Create `.git/hooks/pre-commit`:

```bash
#!/bin/bash
# Pre-commit hook with session management

# Run session checkpoint if MCP server available
if command -v python >/dev/null 2>&1; then
    python -c "
import asyncio
from session_mgmt_mcp.server import create_checkpoint
asyncio.run(create_checkpoint())
" 2>/dev/null || echo "Session checkpoint skipped (MCP server not available)"
fi

exit 0
```

### Package Manager Integration

#### UV Package Manager

Automatic dependency synchronization:

```python
async def sync_dependencies():
    """Sync UV dependencies during session init."""
    try:
        result = await asyncio.create_subprocess_exec(
            "uv",
            "sync",
            "--extra",
            "embeddings",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        return await result.communicate()
    except FileNotFoundError:
        logger.warning("UV not found, skipping dependency sync")
```

#### NPM/Yarn Integration

```python
async def sync_node_dependencies(project_path: Path):
    """Sync Node.js dependencies."""
    package_json = project_path / "package.json"
    if package_json.exists():
        if (project_path / "yarn.lock").exists():
            await asyncio.create_subprocess_exec("yarn", "install")
        else:
            await asyncio.create_subprocess_exec("npm", "install")
```

### Crackerjack Integration

Deep integration with the Crackerjack Python project management tool.

#### Quality Assessment

```python
from session_mgmt_mcp.crackerjack_integration import CrackerjackIntegration


class QualityMonitor:
    def __init__(self):
        self.crackerjack = CrackerjackIntegration()

    async def assess_project_quality(self) -> QualityMetrics:
        """Get comprehensive quality metrics."""
        try:
            # Run crackerjack analysis
            report = await self.crackerjack.run_quality_check()

            return QualityMetrics(
                overall_score=report.overall_score,
                complexity_score=report.complexity_score,
                coverage_score=report.coverage_score,
                security_score=report.security_score,
            )
        except Exception as e:
            logger.warning(f"Crackerjack integration failed: {e}")
            return self.fallback_quality_assessment()
```

#### MCP Server Configuration

Add Crackerjack as an additional MCP server:

```json
{
  "mcpServers": {
    "session-mgmt": {
      "command": "python",
      "args": ["-m", "session_mgmt_mcp.server"],
      "cwd": "/path/to/session-mgmt-mcp"
    },
    "crackerjack": {
      "command": "uvx",
      "args": ["crackerjack", "--mcp-mode"],
      "cwd": "."
    }
  }
}
```

## IDE Integration

### VSCode Integration

#### Extension Development

Create a VSCode extension that leverages the MCP server:

```typescript
// src/extension.ts
import * as vscode from 'vscode';
import { MCPClient } from './mcp-client';

export function activate(context: vscode.ExtensionContext) {
    const mcpClient = new MCPClient();

    // Register commands
    const initCommand = vscode.commands.registerCommand(
        'sessionMgmt.init',
        async () => {
            const result = await mcpClient.callTool('init', {
                working_directory: vscode.workspace.rootPath
            });

            vscode.window.showInformationMessage(
                `Session initialized with quality score: ${result.project_context.health_score}/100`
            );
        }
    );

    context.subscriptions.push(initCommand);
}
```

#### Settings Integration

```json
// .vscode/settings.json
{
  "sessionMgmt.autoInit": true,
  "sessionMgmt.checkpointInterval": 30,
  "sessionMgmt.qualityThreshold": 80,
  "sessionMgmt.mcpServerPath": "/path/to/session-mgmt-mcp"
}
```

### JetBrains IDE Integration

#### Plugin Development

```kotlin
// SessionMgmtPlugin.kt
class SessionMgmtPlugin : BaseComponent, ProjectComponent {
    private val mcpClient = MCPClient()

    override fun projectOpened(project: Project) {
        // Auto-initialize session on project open
        if (SessionMgmtSettings.getInstance().autoInit) {
            mcpClient.callTool("init", mapOf(
                "working_directory" to project.basePath
            ))
        }
    }

    override fun projectClosed(project: Project) {
        // Auto-cleanup on project close
        mcpClient.callTool("end")
    }
}
```

## CI/CD Integration

### GitHub Actions Integration

Create workflow that leverages session management:

```yaml
# .github/workflows/quality-gate.yml
name: Quality Gate with Session Management

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  quality-check:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4

    - name: Setup Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.13'

    - name: Install Session Management MCP
      run: |
        git clone https://github.com/lesleslie/session-mgmt-mcp.git /tmp/session-mgmt-mcp
        cd /tmp/session-mgmt-mcp
        pip install -e ".[embeddings]"

    - name: Initialize Session
      run: |
        python -c "
        import asyncio
        from session_mgmt_mcp.tools.session_tools import init

        async def run():
            result = await init(working_directory='.')
            print(f'Quality Score: {result[\"project_context\"][\"health_score\"]}/100')

            if result['project_context']['health_score'] < 80:
                exit(1)

        asyncio.run(run())
        "

    - name: Store Build Insights
      if: always()
      run: |
        python -c "
        import asyncio
        from session_mgmt_mcp.tools.memory_tools import store_reflection

        async def store():
            await store_reflection(
                content='CI/CD build completed with quality analysis',
                tags=['ci', 'quality', 'build']
            )

        asyncio.run(store())
        "
```

### Jenkins Integration

```groovy
// Jenkinsfile
pipeline {
    agent any

    stages {
        stage('Session Init') {
            steps {
                script {
                    sh '''
                    python -c "
                    import asyncio
                    from session_mgmt_mcp.tools.session_tools import init

                    async def jenkins_init():
                        result = await init(working_directory='.')
                        print('Quality Score:', result['project_context']['health_score'])

                    asyncio.run(jenkins_init())
                    "
                    '''
                }
            }
        }

        stage('Quality Gate') {
            steps {
                script {
                    def qualityScore = sh(
                        script: 'python -c "from session_mgmt_mcp import get_quality_score; print(get_quality_score())"',
                        returnStdout: true
                    ).trim().toFloat()

                    if (qualityScore < 80) {
                        error("Quality gate failed: ${qualityScore}/100")
                    }
                }
            }
        }
    }

    post {
        always {
            sh '''
            python -c "
            import asyncio
            from session_mgmt_mcp.tools.session_tools import end
            asyncio.run(end())
            "
            '''
        }
    }
}
```

## Database Integration

### External Database Support

Extend the memory system to support external databases:

#### PostgreSQL Integration

```python
import asyncpg
from typing import Optional


class PostgreSQLMemoryBackend:
    def __init__(self, connection_url: str):
        self.connection_url = connection_url
        self.pool: Optional[asyncpg.Pool] = None

    async def initialize(self):
        """Initialize PostgreSQL connection pool."""
        self.pool = await asyncpg.create_pool(
            self.connection_url, min_size=5, max_size=20
        )

        # Create tables with vector extension
        async with self.pool.acquire() as conn:
            await conn.execute("""
            CREATE EXTENSION IF NOT EXISTS vector;

            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                embedding vector(384),  -- pgvector extension
                project TEXT NOT NULL,
                timestamp TIMESTAMP NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_conversations_embedding
            ON conversations USING ivfflat (embedding vector_cosine_ops);
            """)

    async def store_conversation(
        self, content: str, embedding: list[float], project: str
    ) -> str:
        """Store conversation in PostgreSQL."""
        conversation_id = str(uuid.uuid4())

        async with self.pool.acquire() as conn:
            await conn.execute(
                """
            INSERT INTO conversations (id, content, embedding, project, timestamp)
            VALUES ($1, $2, $3, $4, NOW())
            """,
                conversation_id,
                content,
                embedding,
                project,
            )

        return conversation_id

    async def semantic_search(
        self,
        query_embedding: list[float],
        limit: int = 10,
        similarity_threshold: float = 0.7,
    ) -> list[dict]:
        """Perform vector similarity search."""
        async with self.pool.acquire() as conn:
            results = await conn.fetch(
                """
            SELECT
                content,
                project,
                timestamp,
                1 - (embedding <=> $1) as similarity
            FROM conversations
            WHERE 1 - (embedding <=> $1) > $2
            ORDER BY embedding <=> $1
            LIMIT $3
            """,
                query_embedding,
                similarity_threshold,
                limit,
            )

            return [dict(row) for row in results]
```

#### Redis Integration

```python
import aioredis
import json
import numpy as np


class RedisMemoryBackend:
    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis_url = redis_url
        self.redis: Optional[aioredis.Redis] = None

    async def initialize(self):
        """Initialize Redis connection."""
        self.redis = aioredis.from_url(self.redis_url)

        # Create RediSearch index for vector similarity
        try:
            await self.redis.ft("conversations").create_index(
                [
                    TextField("content"),
                    TagField("project"),
                    VectorField(
                        "embedding",
                        "FLAT",
                        {"TYPE": "FLOAT32", "DIM": 384, "DISTANCE_METRIC": "COSINE"},
                    ),
                ]
            )
        except Exception:
            pass  # Index might already exist

    async def store_conversation(
        self, content: str, embedding: np.ndarray, project: str
    ) -> str:
        """Store conversation in Redis."""
        conversation_id = str(uuid.uuid4())

        await self.redis.hset(
            f"conversation:{conversation_id}",
            mapping={
                "content": content,
                "project": project,
                "embedding": embedding.tobytes(),
                "timestamp": datetime.now().isoformat(),
            },
        )

        return conversation_id

    async def semantic_search(
        self, query_embedding: np.ndarray, limit: int = 10
    ) -> list[dict]:
        """Perform vector similarity search using RediSearch."""
        query = (
            Query(f"*=>[KNN {limit} @embedding $query_vec]")
            .return_fields("content", "project", "timestamp")
            .dialect(2)
        )

        results = await self.redis.ft("conversations").search(
            query, query_params={"query_vec": query_embedding.tobytes()}
        )

        return [doc.__dict__ for doc in results.docs]
```

## API Integration

### REST API Wrapper

Create a REST API wrapper for the MCP server:

```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import asyncio

app = FastAPI(title="Session Management API")


class SearchRequest(BaseModel):
    query: str
    limit: int = 10
    min_score: float = 0.7
    project: str | None = None


class ReflectionRequest(BaseModel):
    content: str
    tags: list[str] = []


@app.post("/api/v1/search")
async def search_conversations(request: SearchRequest):
    """Search conversations via REST API."""
    try:
        from session_mgmt_mcp.tools.memory_tools import reflect_on_past

        result = await reflect_on_past(
            query=request.query,
            limit=request.limit,
            min_score=request.min_score,
            project=request.project,
        )

        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/reflect")
async def store_reflection(request: ReflectionRequest):
    """Store reflection via REST API."""
    try:
        from session_mgmt_mcp.tools.memory_tools import store_reflection

        result = await store_reflection(content=request.content, tags=request.tags)

        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "session-mgmt-api"}
```

### GraphQL API

```python
import strawberry
from strawberry.asgi import GraphQL


@strawberry.type
class SearchResult:
    content: str
    project: str
    timestamp: str
    similarity_score: float


@strawberry.type
class Query:
    @strawberry.field
    async def search_conversations(
        self, query: str, limit: int = 10, min_score: float = 0.7
    ) -> list[SearchResult]:
        """Search conversations via GraphQL."""
        from session_mgmt_mcp.tools.memory_tools import reflect_on_past

        result = await reflect_on_past(query=query, limit=limit, min_score=min_score)

        return [
            SearchResult(
                content=item["content"],
                project=item["project"],
                timestamp=item["timestamp"],
                similarity_score=item["similarity_score"],
            )
            for item in result.get("results", [])
        ]


@strawberry.type
class Mutation:
    @strawberry.field
    async def store_reflection(self, content: str, tags: list[str] = []) -> bool:
        """Store reflection via GraphQL."""
        from session_mgmt_mcp.tools.memory_tools import store_reflection

        result = await store_reflection(content=content, tags=tags)
        return result.get("success", False)


schema = strawberry.Schema(query=Query, mutation=Mutation)
app = GraphQL(schema)
```

## Monitoring Integration

### Prometheus Integration

Export metrics for monitoring:

```python
from prometheus_client import Counter, Histogram, Gauge, start_http_server
import time

# Metrics
REQUESTS_TOTAL = Counter("session_mgmt_requests_total", "Total requests", ["operation"])
REQUEST_DURATION = Histogram(
    "session_mgmt_request_duration_seconds", "Request duration"
)
ACTIVE_SESSIONS = Gauge("session_mgmt_active_sessions", "Active sessions")
MEMORY_USAGE = Gauge("session_mgmt_memory_usage_mb", "Memory usage in MB")


class MetricsCollector:
    def __init__(self):
        self.start_time = time.time()

    def record_request(self, operation: str, duration: float):
        """Record request metrics."""
        REQUESTS_TOTAL.labels(operation=operation).inc()
        REQUEST_DURATION.observe(duration)

    def update_active_sessions(self, count: int):
        """Update active session count."""
        ACTIVE_SESSIONS.set(count)

    def update_memory_usage(self, mb: float):
        """Update memory usage."""
        MEMORY_USAGE.set(mb)


# Start metrics server
start_http_server(9090)
metrics = MetricsCollector()
```

### Grafana Dashboard

```json
{
  "dashboard": {
    "title": "Session Management MCP Server",
    "panels": [
      {
        "title": "Request Rate",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(session_mgmt_requests_total[5m])",
            "legendFormat": "{{operation}}"
          }
        ]
      },
      {
        "title": "Response Time",
        "type": "graph",
        "targets": [
          {
            "expr": "session_mgmt_request_duration_seconds",
            "legendFormat": "Response Time"
          }
        ]
      },
      {
        "title": "Active Sessions",
        "type": "singlestat",
        "targets": [
          {
            "expr": "session_mgmt_active_sessions"
          }
        ]
      },
      {
        "title": "Memory Usage",
        "type": "graph",
        "targets": [
          {
            "expr": "session_mgmt_memory_usage_mb"
          }
        ]
      }
    ]
  }
}
```

## Notification Integration

### Slack Integration

Send session notifications to Slack:

```python
from slack_sdk.web.async_client import AsyncWebClient
from slack_sdk.errors import SlackApiError


class SlackNotifier:
    def __init__(self, token: str, channel: str):
        self.client = AsyncWebClient(token=token)
        self.channel = channel

    async def notify_session_start(self, session_data: dict):
        """Notify about session start."""
        try:
            await self.client.chat_postMessage(
                channel=self.channel,
                text=f"🚀 Session started for project: {session_data['project_name']}",
                blocks=[
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"*Session Started*\n"
                            f"Project: `{session_data['project_name']}`\n"
                            f"Quality Score: {session_data['health_score']}/100\n"
                            f"Session ID: `{session_data['session_id']}`",
                        },
                    }
                ],
            )
        except SlackApiError as e:
            logger.error(f"Slack notification failed: {e}")

    async def notify_quality_threshold(self, metrics: dict):
        """Notify when quality drops below threshold."""
        if metrics["overall_score"] < 70:
            await self.client.chat_postMessage(
                channel=self.channel,
                text="⚠️ Quality score dropped below threshold",
                blocks=[
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"*Quality Alert*\n"
                            f"Overall Score: {metrics['overall_score']}/100\n"
                            f"Consider running quality improvements",
                        },
                    }
                ],
            )
```

### Discord Integration

```python
import discord
from discord.ext import commands


class DiscordBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)

    @commands.command(name="session")
    async def session_status(self, ctx):
        """Get current session status."""
        from session_mgmt_mcp.tools.session_tools import status

        result = await status()

        embed = discord.Embed(
            title="Session Status",
            color=discord.Color.green() if result["success"] else discord.Color.red(),
        )

        if result.get("project_context"):
            embed.add_field(
                name="Project", value=result["project_context"]["name"], inline=True
            )
            embed.add_field(
                name="Health Score",
                value=f"{result['project_context']['health_score']}/100",
                inline=True,
            )

        await ctx.send(embed=embed)

    @commands.command(name="search")
    async def search_conversations(self, ctx, *, query: str):
        """Search conversation history."""
        from session_mgmt_mcp.tools.memory_tools import quick_search

        result = await quick_search(query=query)

        if result.get("top_result"):
            embed = discord.Embed(
                title=f"Search: {query}",
                description=result["top_result"]["content"][:500] + "...",
                color=discord.Color.blue(),
            )
            embed.add_field(
                name="Total Results", value=result["total_count"], inline=True
            )
        else:
            embed = discord.Embed(
                title="No Results",
                description=f"No conversations found for: {query}",
                color=discord.Color.orange(),
            )

        await ctx.send(embed=embed)


# Bot setup
bot = DiscordBot()
```

## Testing Integration

### pytest Integration

Create pytest fixtures for testing with the MCP server:

```python
import pytest
import asyncio
from session_mgmt_mcp.server import mcp


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def mcp_server():
    """Create test MCP server instance."""
    # Initialize test server
    test_server = await create_test_server()
    yield test_server
    await test_server.cleanup()


@pytest.fixture
async def test_session(mcp_server):
    """Create test session."""
    result = await mcp_server.call_tool(
        "init", {"working_directory": "/tmp/test-project"}
    )

    yield result["session_id"]

    # Cleanup
    await mcp_server.call_tool("end")


class TestIntegration:
    @pytest.mark.asyncio
    async def test_full_session_workflow(self, mcp_server):
        """Test complete session workflow."""
        # Initialize
        init_result = await mcp_server.call_tool("init")
        assert init_result["success"]

        # Store reflection
        reflection_result = await mcp_server.call_tool(
            "store_reflection",
            {
                "content": "Test insight for integration testing",
                "tags": ["test", "integration"],
            },
        )
        assert reflection_result["success"]

        # Search
        search_result = await mcp_server.call_tool(
            "reflect_on_past", {"query": "integration testing"}
        )
        assert search_result["success"]
        assert len(search_result["results"]) > 0

        # End session
        end_result = await mcp_server.call_tool("end")
        assert end_result["success"]
```

## Security Integration

### OAuth2 Integration

Add authentication to API endpoints:

```python
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
import jwt

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


async def get_current_user(token: str = Depends(oauth2_scheme)):
    """Validate JWT token and return user."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
            )
        return username
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        )


@app.post("/api/v1/search")
async def search_conversations(
    request: SearchRequest, current_user: str = Depends(get_current_user)
):
    """Protected search endpoint."""
    # Implementation with user context
    result = await perform_user_search(request, user=current_user)
    return result
```

### Role-Based Access Control

```python
from enum import Enum


class UserRole(Enum):
    ADMIN = "admin"
    DEVELOPER = "developer"
    READONLY = "readonly"


class PermissionChecker:
    ROLE_PERMISSIONS = {
        UserRole.ADMIN: ["*"],
        UserRole.DEVELOPER: ["search", "store", "checkpoint", "init", "end"],
        UserRole.READONLY: ["search", "status"],
    }

    def check_permission(self, user_role: UserRole, operation: str) -> bool:
        """Check if user role has permission for operation."""
        permissions = self.ROLE_PERMISSIONS.get(user_role, [])
        return "*" in permissions or operation in permissions


async def require_permission(
    operation: str, current_user: str = Depends(get_current_user)
):
    """Dependency to check user permissions."""
    user_role = await get_user_role(current_user)

    if not PermissionChecker().check_permission(user_role, operation):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Insufficient permissions for operation: {operation}",
        )

    return current_user
```

## Deployment Integration

### Docker Compose Integration

Complete stack deployment:

```yaml
# docker-compose.yml
version: '3.8'

services:
  session-mgmt-mcp:
    build: .
    ports:
      - "8000:8000"
    environment:
      - SESSION_MGMT_DATA_DIR=/data
      - SESSION_MGMT_LOG_LEVEL=INFO
      - REDIS_URL=redis://redis:6379
      - POSTGRES_URL=postgresql://user:pass@postgres:5432/sessionmgmt
    volumes:
      - session_data:/data
      - ./logs:/logs
    depends_on:
      - redis
      - postgres
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    restart: unless-stopped

  postgres:
    image: postgres:15-alpine
    environment:
      - POSTGRES_DB=sessionmgmt
      - POSTGRES_USER=user
      - POSTGRES_PASSWORD=pass
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./init.sql:/docker-entrypoint-initdb.d/init.sql
    restart: unless-stopped

  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
    restart: unless-stopped

  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
    volumes:
      - grafana_data:/var/lib/grafana
    restart: unless-stopped

volumes:
  session_data:
  redis_data:
  postgres_data:
  grafana_data:
```

### Kubernetes Integration

```yaml
# k8s/deployment.yml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: session-mgmt-mcp
spec:
  replicas: 3
  selector:
    matchLabels:
      app: session-mgmt-mcp
  template:
    metadata:
      labels:
        app: session-mgmt-mcp
    spec:
      containers:
      - name: session-mgmt
        image: session-mgmt-mcp:latest
        ports:
        - containerPort: 8000
        env:
        - name: SESSION_MGMT_DATA_DIR
          value: "/data"
        - name: REDIS_URL
          valueFrom:
            secretKeyRef:
              name: session-mgmt-secrets
              key: redis-url
        volumeMounts:
        - name: session-data
          mountPath: /data
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /ready
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
      volumes:
      - name: session-data
        persistentVolumeClaim:
          claimName: session-data-pvc
---
apiVersion: v1
kind: Service
metadata:
  name: session-mgmt-service
spec:
  selector:
    app: session-mgmt-mcp
  ports:
  - port: 80
    targetPort: 8000
  type: LoadBalancer
```

## Best Practices

### Integration Checklist

- [ ] **Authentication**: Implement proper authentication for API endpoints
- [ ] **Rate Limiting**: Add rate limiting to prevent abuse
- [ ] **Error Handling**: Comprehensive error handling with meaningful messages
- [ ] **Logging**: Structured logging for debugging and monitoring
- [ ] **Health Checks**: Implement health check endpoints for monitoring
- [ ] **Documentation**: Document all integration endpoints and parameters
- [ ] **Testing**: Integration tests for all external integrations
- [ ] **Security**: Input validation, SQL injection prevention, HTTPS
- [ ] **Monitoring**: Metrics collection and alerting for production
- [ ] **Backup**: Regular backups of conversation data

### Performance Considerations

1. **Connection Pooling**: Use connection pools for databases
1. **Caching**: Implement caching for frequently accessed data
1. **Async Operations**: Use async/await for I/O operations
1. **Resource Limits**: Set appropriate resource limits in production
1. **Load Balancing**: Use load balancers for high availability

### Security Considerations

1. **API Security**: Implement proper authentication and authorization
1. **Input Validation**: Validate all inputs to prevent injection attacks
1. **Network Security**: Use HTTPS and proper network isolation
1. **Secret Management**: Use secret management systems for sensitive data
1. **Audit Logging**: Log all security-relevant events

______________________________________________________________________

**Related Documentation:**

- [QUICK_START.md](QUICK_START.md) - Getting started guide
- [CONFIGURATION.md](CONFIGURATION.md) - Configuration options
- [ARCHITECTURE.md](ARCHITECTURE.md) - System architecture details
- [MCP_TOOLS_REFERENCE.md](MCP_TOOLS_REFERENCE.md) - Complete tool reference
