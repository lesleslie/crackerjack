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
- [Agent System](features/AI_AGENT_SYSTEM.md) - AI-powered auto-fixing

## Key Features

- **Protocol-Based Architecture**: Loose coupling, easy testing
- **AI Agent Integration**: 12 specialized agents for auto-fixing issues
- **Quality Gates**: Comprehensive checks (ruff, pytest, bandit, etc.)
- **High-Performance Tools**: Rust-powered static analysis (Skylos, Zuban)

## Documentation Index

### Architecture
- [Protocol-Based Design](architecture/protocols.md)
- [Layered Architecture](architecture/layered-design.md)
- [Decision Records](../adr/)

### API Reference
- [Protocols](api/reference.md#protocols)
- [Services](api/reference.md#services)
- [Managers](api/reference.md#managers)

### Quality
- [Quality Gates](quality/gates.md)
- [Test Coverage](quality/coverage.md)
- [Performance](quality/performance.md)

### Guides
- [Testing Guide](guides/testing.md)
- [Contributing](guides/contributing.md)
- [CLI Reference](../CLI_REFERENCE.md)
