# Crackerjack

Opinionated Python project management tool unifying UV, Ruff, pytest, and quality tools.

## Quick Start

```bash
pip install crackerjack
python -m crackerjack run --ai-fix --run-tests
```

## Documentation Sections

- [Architecture](architecture/protocols.md) - Protocol-based design patterns
- [API Reference](api/reference.md) - Complete API documentation
- [Quality Gates](quality/gates.md) - Quality check workflow

## Key Features

- **Protocol-Based Architecture**: Loose coupling, easy testing
- **AI Agent Integration**: 12 specialized agents for auto-fixing issues
- **Quality Gates**: Comprehensive checks (ruff, pytest, bandit, etc.)
- **High-Performance Tools**: Rust-powered static analysis (Skylos, Zuban)

## Documentation Index

### Architecture

- [Protocol-Based Design](architecture/protocols.md)

- [Protocols](api/reference.md#protocols)

- [Services](api/reference.md#services)

- [Managers](api/reference.md#managers)

### Quality

- [Quality Gates](quality/gates.md)

### Performance & Optimization

- [Quality Scanning Strategy](QUALITY_SCANNING_STRATEGY.md) - Decision framework for optimizing slow hooks (refurb, complexipy, skylos)
- [Incremental Scanning Options](INTEGRAL_SCANNING_OPTIONS.md) - Four approaches to change-based scanning (git-diff, markers, hybrid, pools)
- [Mahavishnu Pool Integration](MAHAVISHNU_POOL_INTEGRATION.md) - Worker pool architecture for parallel tool execution

### AI Fix System

- [Multi-Agent AI Fix Quality System](../docs/plans/2025-02-12-multi-agent-ai-fix-quality-system.md) - 4-layer architecture for automated code fixing
- [AI Fix Quality Quickstart](docs/reference/AI_FIX_QUALITY_QUICKSTART.md) - Quick reference for the V2 two-stage pipeline
