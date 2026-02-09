# Crackerjack Service Dependencies

## Overview

Crackerjack is designed as a **standalone quality control tool** with minimal external dependencies. It operates independently without requiring any running services, making it easy to integrate into any development workflow.

## Required Services

**None** - Crackerjack is a standalone tool that runs without any external services.

## External Tool Dependencies

Crackerjack integrates with various code quality tools to provide comprehensive checking capabilities. These tools are executed as subprocesses and are **not running services**.

### Quality Tools

| Tool | Purpose | Required | Version |
|------|---------|----------|---------|
| **ruff** | Fast Python linter and formatter | Yes | >=0.1.0 |
| **pytest** | Testing framework | Yes | >=7.0.0 |
| **bandit** | Security linter | Optional | >=1.7.0 |
| **safety** | Dependency vulnerability scanner | Optional | >=2.0.0 |
| **creosote** | Unused dependency detector | Optional | >=0.1.0 |
| **refurb** | Modern Python suggestions | Optional | >=1.0.0 |
| **codespell** | Typo detector | Optional | >=2.0.0 |
| **complexipy** | Complexity checker | Optional | >=0.1.0 |
| **coverage** | Code coverage tool | Yes | >=6.0 |
| **mypy** | Type checker | Optional | >=1.0.0 |

### Installation

```bash
# Install Crackerjack with core dependencies
pip install crackerjack

# Install with all optional tools
pip install crackerjack[all]

# Install with specific tool sets
pip install crackerjack[test]    # Testing tools
pip install crackerjack[security] # Security tools
pip install crackerjack[ai]      # AI auto-fix tools
```

## Optional Integrations

### CI/CD Platforms

Crackerjack can generate configuration files for various CI/CD platforms, but does not require them to run.

#### Supported Platforms

- **GitHub Actions** - `.github/workflows/crackerjack.yml`
- **GitLab CI** - `.gitlab-ci.yml`
- **Azure Pipelines** - `azure-pipelines.yml`
- **CircleCI** - `.circleci/config.yml`
- **Travis CI** - `.travis.yml`

#### Usage

```bash
# Initialize CI/CD configuration
crackerjack init-ci --platform github

# This generates configuration files only
# Crackerjack does not depend on the CI/CD service
```

### AI Services (Optional)

For AI auto-fix features, Crackerjack can integrate with external AI services. These are **optional** and Crackerjack works perfectly without them.

#### Supported Providers

| Provider | Purpose | API Key Required |
|----------|---------|------------------|
| **OpenAI** | Code fixing and suggestions | Yes (`OPENAI_API_KEY`) |
| **Anthropic** | Claude-powered fixes | Yes (`ANTHROPIC_API_KEY`) |
| **Ollama** | Local model execution | No (local only) |

#### Configuration

```toml
# crackerjack.toml
[ai_fix]
enabled = true
provider = "openai"  # or "anthropic" or "ollama"
model = "gpt-4"
api_key_env = "OPENAI_API_KEY"
max_fixes = 10
dry_run = false
```

#### Environment Variables

```bash
# OpenAI
export OPENAI_API_KEY="sk-..."

# Anthropic
export ANTHROPIC_API_KEY="sk-ant-..."

# Ollama (local, no API key needed)
export OLLAMA_BASE_URL="http://localhost:11434"
```

### MCP Integration

Crackerjack can run as an MCP server for integration with AI tools and IDEs. This is an **optional feature** - Crackerjack does not depend on MCP clients to function.

#### MCP Server Commands

```bash
# Start MCP server
crackerjack mcp start

# Check status
crackerjack mcp status

# Run health probe
crackerjack mcp health

# Stop MCP server
crackerjack mcp stop
```

#### MCP Configuration

Crackerjack uses FastMCP for MCP server functionality. The server is **self-contained** and does not require external MCP infrastructure.

**MCP Tools Exposed**:

- `run_check` - Execute specific quality check
- `run_all_checks` - Execute all configured checks
- `get_status` - Get current quality status
- `get_metrics` - Get quality metrics
- `ai_fix` - Apply AI-powered fixes

### Storage Backends (Optional)

Crackerjack can optionally store metrics and history in various backends. By default, it uses local files.

#### Default Storage (No Service Required)

```toml
[storage]
type = "local"
history_file = ".crackerjack/history.json"
metrics_db = ".crackerjack/metrics.db"
```

#### Optional Storage Backends

| Backend | Purpose | Service Required |
|---------|---------|------------------|
| **SQLite** | Local metrics storage | No (embedded) |
| **PostgreSQL** | Centralized metrics | Yes (PostgreSQL server) |
| **Redis** | Caching and distributed locking | Yes (Redis server) |
| **S3** | Long-term storage | Yes (AWS S3) |

#### PostgreSQL Configuration

```toml
[storage]
type = "postgresql"
connection_string = "postgresql://user:pass@localhost/crackerjack"
```

#### Redis Configuration

```toml
[storage]
type = "redis"
connection_string = "redis://localhost:6379"
```

#### S3 Configuration

```toml
[storage]
type = "s3"
bucket = "crackerjack-metrics"
region = "us-west-2"
```

## Dependency Graph

```
┌─────────────────────────────────────────────────────────────┐
│                      Crackerjack Core                        │
│                  (No services required)                     │
└─────────────────────────────────────────────────────────────┘
                            │
                            ├─────────────────────────────────┐
                            │                                 │
                            ▼                                 ▼
              ┌─────────────────────┐           ┌─────────────────────┐
              │  External Tools     │           │  Optional Services  │
              │  (Subprocesses)     │           │                     │
              ├─────────────────────┤           ├─────────────────────┤
              │ ruff                │           │ CI/CD Platforms     │
              │ pytest              │           │  (config gen only)  │
              │ bandit              │           │                     │
              │ safety              │           │ AI Services         │
              │ coverage            │           │  (optional)         │
              │ mypy                │           │                     │
              └─────────────────────┘           │ Storage Backends    │
                                               │  (optional)         │
                                               │                     │
                                               │ MCP Clients         │
                                               │  (optional)         │
                                               └─────────────────────┘
```

## Runtime Requirements

### System Requirements

- **Python**: >=3.9
- **OS**: Linux, macOS, Windows
- **Memory**: 512MB minimum (1GB recommended)
- **Disk**: 100MB for installation

### Network Requirements

- **Online**: Not required (except for AI features and initial package installation)
- **Firewall**: No inbound ports required
- **Outbound**: Optional for AI services and storage backends

### Permissions

- **File System**: Read access to project files, write access to `.crackerjack/` directory
- **Network**: Optional outbound access for AI services
- **Execution**: Permission to execute quality tools (ruff, pytest, etc.)

## Installation Scenarios

### Scenario 1: Minimal Installation (Local Development)

```bash
# Install core only
pip install crackerjack

# No services required
# Works offline
```

### Scenario 2: Full Installation (Team Development)

```bash
# Install with all tools
pip install crackerjack[all]

# Optional: Set up AI auto-fix
export OPENAI_API_KEY="sk-..."

# Optional: Set up shared metrics storage
export CRACKERJACK_STORAGE_TYPE="postgresql"
export CRACKERJACK_DB_URL="postgresql://..."
```

### Scenario 3: CI/CD Integration

```bash
# In CI/CD pipeline
- pip install crackerjack
- crackerjack init-ci --platform github
- crackerjack run

# No services required in CI/CD
# Uses CI/CD environment variables
```

### Scenario 4: MCP Server Mode

```bash
# Start MCP server for IDE integration
crackerjack mcp start

# No external MCP services required
# Self-contained MCP server
```

## Verification

### Check Dependencies

```bash
# Verify installation
crackerjack --version

# Check available tools
crackerjack tools list

# Check configuration
crackerjack config show

# Test quality checks
crackerjack run --dry-run
```

### Test External Tools

```bash
# Test ruff
ruff --version

# Test pytest
pytest --version

# Test bandit (if installed)
bandit --version

# Test coverage
coverage --version
```

### Test Optional Services

```bash
# Test AI service connection
crackerjack test-ai

# Test storage backend
crackerjack test-storage

# Test MCP server
crackerjack mcp health
```

## Troubleshooting

### Tool Not Found

```bash
# Error: ruff not found
# Solution: Install missing tool
pip install ruff

# Or install all tools
pip install crackerjack[all]
```

### AI Service Not Available

```bash
# Error: AI service connection failed
# Solution 1: Check API key
echo $OPENAI_API_KEY

# Solution 2: Test connection
crackerjack test-ai

# Solution 3: Disable AI features
crackerjack config set ai_fix.enabled false
```

### Storage Backend Not Available

```bash
# Error: Cannot connect to PostgreSQL
# Solution 1: Check connection string
crackerjack config show storage

# Solution 2: Fall back to local storage
crackerjack config set storage.type local
```

### MCP Server Not Starting

```bash
# Error: MCP server failed to start
# Solution 1: Check port availability
crackerjack mcp status

# Solution 2: Check logs
crackerjack logs --filter mcp

# Solution 3: Restart server
crackerjack mcp restart
```

## Best Practices

### Development

1. **Use local storage** for development (no services required)
1. **Install all tools** for comprehensive checking: `pip install crackerjack[all]`
1. **Enable AI auto-fix** only when needed (adds latency and cost)
1. **Use quality gates** to enforce standards before commits

### CI/CD

1. **Minimal installation** in CI/CD: `pip install crackerjack`
1. **Generate CI/CD config** with `crackerjack init-ci`
1. **Use strict quality gates** for production branches
1. **Cache dependencies** between runs for faster execution

### Team Collaboration

1. **Commit crackerjack.toml** to repository for consistent configuration
1. **Use shared storage backend** (PostgreSQL, Redis) for team metrics
1. **Standardize quality gates** across all projects
1. **Integrate with pre-commit hooks** for immediate feedback

### Production

1. **Run in offline mode** when possible (no AI services)
1. **Use dedicated storage backend** for metrics and history
1. **Monitor execution time** and optimize check configuration
1. **Set appropriate timeouts** for each check

## Related Documentation

- **[QUICKSTART.md](../QUICKSTART.md)** - Get started quickly
- **[ARCHITECTURE.md](../ARCHITECTURE.md)** - Architecture overview
- **[docs/guides/ci-cd-integration.md](ci-cd-integration.md)** - CI/CD setup guide
- **[docs/reference/cli-reference.md](cli-reference.md)** - CLI command reference

## Support

For issues related to:

- **Crackerjack itself**: Create issue on GitHub
- **External tools**: Check tool documentation (ruff, pytest, etc.)
- **AI services**: Check provider status (OpenAI, Anthropic)
- **Storage backends**: Check service documentation (PostgreSQL, Redis)
