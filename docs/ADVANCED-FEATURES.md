# Advanced Features Reference

## Crackerjack Power User Guide

This document covers advanced CLI flags and enterprise features not included in the main README. These features are designed for power users, enterprise deployments, CI/CD pipelines, and specialized workflows.

______________________________________________________________________

## Table of Contents

1. \[[#enterprise-features|Enterprise Features]\]
1. \[[#ai--intelligence|AI & Intelligence]\]
1. \[[#documentation-generation|Documentation Generation]\]
1. \[[#quality-analytics|Quality Analytics]\]
1. \[[#monitoring--dashboards|Monitoring & Dashboards]\]
1. \[[#orchestration--execution|Orchestration & Execution]\]
1. \[[#zuban-lsp-integration|Zuban LSP Integration]\]
1. \[[#websocket--servers|WebSocket & Servers]\]
1. \[[#semantic-search|Semantic Search]\]
1. \[[#visualization|Visualization]\]
1. \[[#configuration-management|Configuration Management]\]
1. \[[#coverage--performance|Coverage & Performance]\]
1. \[[#global-locking|Global Locking]\]
1. \[[#experimental-features|Experimental Features]\]

______________________________________________________________________

## Enterprise Features

### Enterprise Optimization Engine

Enable enterprise-scale optimization with resource monitoring and scaling analysis:

```bash
python -m crackerjack --enterprise-optimization
```

**Optimization Profiles**:

```bash
# Balanced optimization (default)
python -m crackerjack --enterprise-optimization --enterprise-profiling balanced

# Performance-focused
python -m crackerjack --enterprise-optimization --enterprise-profiling performance

# Memory-optimized
python -m crackerjack --enterprise-optimization --enterprise-profiling memory

# Throughput-optimized
python -m crackerjack --enterprise-optimization --enterprise-profiling throughput
```

**Generate Enterprise Reports**:

```bash
python -m crackerjack --enterprise-optimization --enterprise-reporting ./reports/enterprise-analysis.json
```

**Use Cases**:

- Large-scale codebases (100k+ lines)
- Multi-service architectures
- Resource-constrained environments
- High-throughput CI/CD pipelines

______________________________________________________________________

## AI & Intelligence

### Contextual AI Assistant

Enable project-specific AI recommendations and insights:

```bash
# Start contextual AI assistant
python -m crackerjack --contextual-ai

# Get AI help for specific queries
python -m crackerjack --ai-help-query "How do I optimize test performance?"

# Control recommendation count
python -m crackerjack --contextual-ai --ai-recommendations 10
```

### Smart Commit Messages (Default)

AI-powered commit message generation (enabled by default):

```bash
# Smart commits (default - AI-generated messages)
python -m crackerjack --smart-commit --commit

# Disable for simple messages
python -m crackerjack --basic-commit --commit
```

### Auto Version Recommendations

AI analyzes changes and recommends semantic version bumps:

```bash
# Analyze changes and recommend version
python -m crackerjack --auto-version

# Since specific version
python -m crackerjack --auto-version --version-since v0.1.0

# Auto-accept recommendation (CI/CD)
python -m crackerjack --auto-version --accept-version
```

**How It Works**:

- Analyzes conventional commits (feat/fix/breaking)
- Detects API-breaking changes
- Provides confidence scores
- Recommends major/minor/patch based on changes

______________________________________________________________________

## Documentation Generation

### Automated API Documentation

Generate comprehensive API docs from source code:

```bash
# Generate API documentation (markdown)
python -m crackerjack --generate-docs

# HTML output
python -m crackerjack --generate-docs --docs-format html

# ReStructuredText (RST)
python -m crackerjack --generate-docs --docs-format rst
```

### Documentation Validation

```bash
# Validate documentation completeness
python -m crackerjack --validate-docs
```

### MkDocs Integration

Generate complete documentation sites with Material theme:

```bash
# Generate MkDocs site
python -m crackerjack --mkdocs-integration

# With development server
python -m crackerjack --mkdocs-integration --mkdocs-serve

# Custom theme
python -m crackerjack --mkdocs-integration --mkdocs-theme readthedocs

# Custom output directory
python -m crackerjack --mkdocs-integration --mkdocs-output ./documentation
```

### Changelog Automation

```bash
# Generate changelog from git commits
python -m crackerjack --generate-changelog

# Since specific version
python -m crackerjack --generate-changelog --changelog-since v0.35.0

# For specific version number
python -m crackerjack --generate-changelog --changelog-version 0.40.0

# Preview without writing
python -m crackerjack --generate-changelog --changelog-dry-run
```

______________________________________________________________________

## Quality Analytics

### ML-Based Anomaly Detection

Detect quality metric anomalies using machine learning:

```bash
# Enable anomaly detection
python -m crackerjack --anomaly-detection

# Adjust sensitivity (1.0=very sensitive, 3.0=less sensitive)
python -m crackerjack --anomaly-detection --anomaly-sensitivity 1.5

# Generate anomaly report
python -m crackerjack --anomaly-detection --anomaly-report ./reports/anomalies.json
```

### Predictive Analytics

Forecast quality metrics and trend analysis:

```bash
# Enable predictive analytics
python -m crackerjack --predictive-analytics

# Predict 20 periods ahead (default: 10)
python -m crackerjack --predictive-analytics --prediction-period 20

# Generate analytics dashboard
python -m crackerjack --predictive-analytics --analytics-dashboard ./dashboard.html
```

**What It Predicts**:

- Test failure rates
- Code complexity trends
- Coverage trajectory
- Quality score forecasts

______________________________________________________________________

## Monitoring & Dashboards

### Enhanced Progress Monitor

Advanced monitoring with MetricCard widgets and modern UI:

```bash
# Start enhanced monitor
python -m crackerjack --enhanced-monitor

# With development mode
python -m crackerjack --enhanced-monitor --dev
```

**Features**:

- Real-time metric cards
- Modern web UI patterns
- Advanced visualization
- Multi-project tracking

### Multi-Project Monitor

Monitor multiple projects with autodiscovery:

```bash
# Start multi-project monitor
python -m crackerjack --monitor
```

**Capabilities**:

- WebSocket polling
- Watchdog services
- Project autodiscovery
- Aggregated metrics

### Comprehensive Dashboard

System metrics, job tracking, and performance monitoring:

```bash
# Start dashboard
python -m crackerjack --dashboard
```

### Unified Dashboard

Real-time WebSocket streaming with comprehensive system metrics:

```bash
# Start unified dashboard (default port: 8675)
python -m crackerjack --unified-dashboard

# Custom port
python -m crackerjack --unified-dashboard --unified-dashboard-port 9000
```

**Access**: http://localhost:8675/

______________________________________________________________________

## Orchestration & Execution

### Advanced Orchestration Mode

Intelligent execution strategies with multi-agent coordination:

```bash
# Enable orchestrated mode
python -m crackerjack --orchestrated
```

### Execution Strategies

```bash
# Batch processing
python -m crackerjack --orchestrated --orchestration-strategy batch

# Individual execution
python -m crackerjack --orchestrated --orchestration-strategy individual

# Adaptive (default - intelligent selection)
python -m crackerjack --orchestrated --orchestration-strategy adaptive

# Selective execution
python -m crackerjack --orchestrated --orchestration-strategy selective
```

### Progress Tracking Levels

```bash
# Basic tracking
python -m crackerjack --orchestrated --orchestration-progress basic

# Detailed tracking
python -m crackerjack --orchestrated --orchestration-progress detailed

# Granular (default)
python -m crackerjack --orchestrated --orchestration-progress granular

# Streaming real-time
python -m crackerjack --orchestrated --orchestration-progress streaming
```

### AI Coordination Modes

```bash
# Single agent (default)
python -m crackerjack --orchestrated --orchestration-ai single-agent

# Multi-agent collaboration
python -m crackerjack --orchestrated --orchestration-ai multi-agent

# Coordinator pattern
python -m crackerjack --orchestrated --orchestration-ai coordinator
```

### Iteration Control

```bash
# Maximum AI fixing iterations (default: 5)
python -m crackerjack --ai-fix --max-iterations 10

# Quick mode (max 3 iterations - for CI/CD)
python -m crackerjack --quick

# Thorough mode (max 8 iterations - for complex refactoring)
python -m crackerjack --thorough
```

______________________________________________________________________

## Zuban LSP Integration

### Zuban LSP Server

Real-time type checking with Language Server Protocol:

```bash
# Start Zuban LSP server
python -m crackerjack --start-zuban-lsp

# Stop LSP server
python -m crackerjack --stop-zuban-lsp

# Restart LSP server
python -m crackerjack --restart-zuban-lsp
```

### LSP Configuration

```bash
# Custom port (default: 8677)
python -m crackerjack --start-zuban-lsp --zuban-lsp-port 9000

# Transport mode (tcp or stdio)
python -m crackerjack --start-zuban-lsp --zuban-lsp-mode stdio

# Custom timeout (default: 30s)
python -m crackerjack --start-zuban-lsp --zuban-lsp-timeout 60
```

### LSP-Optimized Hooks

```bash
# Enable LSP-optimized hook execution
python -m crackerjack --enable-lsp-hooks

# Disable automatic LSP startup
python -m crackerjack --no-zuban-lsp
```

**Benefits**:

- 20-200x faster type checking vs pyright
- Real-time feedback
- Editor integration
- Reduced pre-commit time

______________________________________________________________________

## WebSocket & Servers

### WebSocket Progress Server

```bash
# Start WebSocket server (default port: 8675)
python -m crackerjack --start-websocket-server

# Custom port
python -m crackerjack --start-websocket-server --websocket-port 9000

# Stop WebSocket server
python -m crackerjack --stop-websocket-server

# Restart
python -m crackerjack --restart-websocket-server
```

### Service Watchdog

Monitor and auto-restart servers:

```bash
# Start watchdog for MCP and WebSocket servers
python -m crackerjack --watchdog
```

**Monitors**:

- MCP server health
- WebSocket server status
- Auto-restart on failure
- Service availability

______________________________________________________________________

## Semantic Search

Index and search codebase semantically:

```bash
# Index a file
python -m crackerjack --index path/to/file.py

# Index entire directory
python -m crackerjack --index ./crackerjack

# Perform semantic search
python -m crackerjack --search "similarity calculation"

# View index statistics
python -m crackerjack --semantic-stats

# Remove from index
python -m crackerjack --remove-from-index path/to/file.py
```

**Use Cases**:

- Finding similar code patterns
- Duplicate detection
- Code reuse identification
- Architecture understanding

______________________________________________________________________

## Visualization

### Code Quality Heat Maps

```bash
# Generate error frequency heat map (default)
python -m crackerjack --heatmap

# Complexity heat map
python -m crackerjack --heatmap --heatmap-type complexity

# Quality metrics visualization
python -m crackerjack --heatmap --heatmap-type quality_metrics

# Test failures heat map
python -m crackerjack --heatmap --heatmap-type test_failures
```

### Heat Map Output Formats

```bash
# JSON output
python -m crackerjack --heatmap --heatmap-output ./analysis.json

# CSV format
python -m crackerjack --heatmap --heatmap-output ./data.csv

# HTML visualization
python -m crackerjack --heatmap --heatmap-output ./report.html
```

______________________________________________________________________

## Configuration Management

### Config Template Updates

```bash
# Check for config updates
python -m crackerjack --check-config-updates

# Apply config updates
python -m crackerjack --apply-config-updates

# Interactive mode (with confirmations)
python -m crackerjack --config-interactive

# Show diff preview
python -m crackerjack --diff-config pyproject.toml
```

### Cache Management

```bash
# Refresh pre-commit cache
python -m crackerjack --refresh-cache

# Display cache statistics
python -m crackerjack --cache-stats

# Clear all caches
python -m crackerjack --clear-cache
```

**Cache Types**:

- Hook execution results
- File content hashes
- AI agent decisions
- Pre-commit environments

______________________________________________________________________

## Coverage & Performance

### Coverage Management

```bash
# Show coverage ratchet status
python -m crackerjack --coverage-status

# Set explicit coverage target
python -m crackerjack --coverage-goal 25.0

# Disable coverage ratchet temporarily
python -m crackerjack --no-coverage-ratchet

# Disable automatic coverage boost
python -m crackerjack --no-boost-coverage
```

**Coverage Ratchet**:

- Progressive improvement system
- Never allows decrease
- 2% tolerance for flaky tests
- Targets 100% coverage

______________________________________________________________________

## Global Locking

Control concurrent execution across sessions:

```bash
# Disable global locking (allow concurrent runs)
python -m crackerjack --disable-global-locking

# Custom lock timeout (default: 600s)
python -m crackerjack --global-lock-timeout 1200

# Custom lock directory
python -m crackerjack --global-lock-dir ~/.custom-locks

# Disable stale lock cleanup
python -m crackerjack --no-cleanup-stale-locks
```

**Use Cases**:

- CI/CD parallel builds
- Multi-developer workflows
- Container orchestration
- Distributed systems

______________________________________________________________________

## Experimental Features

### Pre-commit Experimental Hooks

```bash
# Enable experimental hooks framework
python -m crackerjack --experimental-hooks

# Enable pyrefly (experimental type checking)
python -m crackerjack --enable-pyrefly --experimental-hooks

# Enable ty (experimental type verification)
python -m crackerjack --enable-ty --experimental-hooks
```

**⚠️ Warning**: Experimental features may be unstable and are subject to removal if evaluation fails.

### Git & Version Control

```bash
# Skip git tags during version bump
python -m crackerjack --no-git-tags --bump patch

# Skip version consistency checks
python -m crackerjack --skip-version-check --publish
```

______________________________________________________________________

## Shell Completion

```bash
# Install completion for current shell
python -m crackerjack --install-completion

# Show completion script (for manual installation)
python -m crackerjack --show-completion
```

______________________________________________________________________

## Advanced Workflows

### Enterprise CI/CD Pipeline

```bash
# Fast quality checks with AI fixing (CI/CD optimized)
python -m crackerjack --quick --ai-fix --no-boost-coverage --disable-global-locking
```

### Comprehensive Release Workflow

```bash
# Full enterprise release with analytics
python -m crackerjack \
  --thorough \
  --orchestrated \
  --predictive-analytics \
  --anomaly-detection \
  --generate-changelog \
  --auto-version \
  --accept-version \
  --all
```

### Documentation Automation

```bash
# Complete documentation generation pipeline
python -m crackerjack \
  --generate-docs \
  --docs-format html \
  --mkdocs-integration \
  --mkdocs-serve \
  --validate-docs
```

### Quality Analysis Suite

```bash
# Full quality analysis with visualizations
python -m crackerjack \
  --heatmap --heatmap-type quality_metrics \
  --anomaly-detection --anomaly-sensitivity 1.5 \
  --predictive-analytics \
  --analytics-dashboard ./quality-report.html
```

______________________________________________________________________

## Performance Optimization

### Caching Strategy

**Cache Hit Optimization**:

- Pre-commit results cached by file hash
- AI agent decisions memoized
- Semantic index persisted
- Hook environments reused

**When to Clear Cache**:

```bash
# After dependency updates
uv sync && python -m crackerjack --clear-cache

# After pre-commit config changes
python -m crackerjack --refresh-cache

# For clean baseline metrics
python -m crackerjack --clear-cache --benchmark
```

### Parallel Execution

**Optimal Workers**:

```bash
# Auto-detect (default - recommended)
python -m crackerjack --run-tests --test-workers 0

# Disable parallelization (for debugging)
python -m crackerjack --run-tests --test-workers 1

# Custom count (for constrained environments)
python -m crackerjack --run-tests --test-workers 2
```

______________________________________________________________________

## Troubleshooting Advanced Features

### Common Issues

**Zuban LSP Not Starting**:

```bash
# Check LSP status
lsof -i :8677

# Force restart with debug
python -m crackerjack --restart-zuban-lsp --debug
```

**WebSocket Connection Failed**:

```bash
# Verify port availability
lsof -i :8675

# Try alternative port
python -m crackerjack --start-websocket-server --websocket-port 9000
```

**Anomaly Detection False Positives**:

```bash
# Reduce sensitivity
python -m crackerjack --anomaly-detection --anomaly-sensitivity 2.5

# Review historical data
python -m crackerjack --predictive-analytics --prediction-period 30
```

**Enterprise Optimization Performance**:

```bash
# Use memory-optimized profile for large codebases
python -m crackerjack --enterprise-optimization --enterprise-profiling memory

# Generate performance report
python -m crackerjack --enterprise-optimization --enterprise-reporting analysis.json
```

______________________________________________________________________

## Best Practices

### For Enterprise Deployments

1. **Use Global Locking Control**: Configure timeouts appropriate for your infrastructure
1. **Enable Enterprise Optimization**: Profile-based optimization for your environment
1. **Implement Anomaly Detection**: Early warning system for quality regressions
1. **Automate Documentation**: Keep API docs synchronized with code

### For CI/CD Pipelines

1. **Quick Mode**: Use `--quick` for fast feedback loops
1. **Disable Coverage Boost**: Use `--no-boost-coverage` to avoid CI conflicts
1. **Global Locking**: Use `--disable-global-locking` for parallel builds
1. **Auto-accept Versions**: Use `--auto-version --accept-version` for automated releases

### For Development Teams

1. **Zuban LSP**: Integrate for real-time type checking in editors
1. **Semantic Search**: Index codebase for better code discovery
1. **Heat Maps**: Visualize quality patterns for team insights
1. **Contextual AI**: Use `--contextual-ai` for project-specific guidance

______________________________________________________________________

## Migration from Core Features

If you're moving from basic to advanced usage:

**From**: `python -m crackerjack --ai-fix --run-tests`
**To**: `python -m crackerjack --orchestrated --orchestration-strategy adaptive --max-iterations 8`

**From**: `python -m crackerjack --dashboard`
**To**: `python -m crackerjack --unified-dashboard --enhanced-monitor --dev`

**From**: `python -m crackerjack --bump patch --publish`
**To**: `python -m crackerjack --auto-version --accept-version --generate-changelog --all`

______________________________________________________________________

## Feature Maturity Matrix

| Feature | Stability | Recommended For |
|---------|-----------|-----------------|
| Enterprise Optimization | Stable | Production, Large Teams |
| Zuban LSP | Stable | All Environments |
| Predictive Analytics | Beta | Analysis, Planning |
| Anomaly Detection | Beta | QA, Monitoring |
| Semantic Search | Stable | Code Discovery |
| MkDocs Integration | Stable | Documentation Teams |
| Orchestration | Stable | Complex Workflows |
| Heat Maps | Stable | Quality Analysis |
| WebSocket Streaming | Stable | Real-time Monitoring |
| Experimental Hooks | Alpha | Testing Only |

______________________________________________________________________

## Performance Benchmarks

**Typical Execution Times** (medium-sized project):

- **Quick Mode**: 30-45s (3 iterations)
- **Standard Mode**: 60-90s (5 iterations)
- **Thorough Mode**: 120-180s (8 iterations)
- **With Zuban LSP**: 40-70% faster type checking
- **With Caching**: 60-80% improvement on subsequent runs

**Resource Usage**:

- **Memory**: 200-500MB (standard), 500MB-1GB (enterprise)
- **CPU**: Scales with worker count (auto-detected)
- **Disk**: 50-200MB cache (varies by project)

______________________________________________________________________

## Future Roadmap

Planned advanced features (subject to change):

- **Distributed Execution**: Multi-machine workflow orchestration
- **Cloud Integration**: AWS/GCP/Azure native support
- **Advanced ML Models**: Deep learning for code analysis
- **Multi-Language Support**: Expand beyond Python
- **Real-time Collaboration**: Shared monitoring dashboards

______________________________________________________________________

## Support & Resources

- **Documentation Issues**: Check `--validate-docs`
- **Performance Issues**: Use `--enterprise-optimization --enterprise-reporting`
- **Quality Concerns**: Enable `--anomaly-detection --predictive-analytics`
- **Integration Help**: Use `--contextual-ai --ai-help-query "your question"`

For core features, see \[[README|README.md]\].
For developer guidance, see \[[CLAUDE|CLAUDE.md]\].

______________________________________________________________________

**Last Updated**: 2025-10-03
**Coverage**: 103 total CLI flags (100% documented)
**Target Audience**: Power users, enterprise deployments, DevOps teams
