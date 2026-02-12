# Contributing Guide

Guide to contributing to Crackerjack.

## Development Workflow

### 1. Setup
```bash
git clone <your-fork>
cd crackerjack
uv pip install -e ".[neural,dev]"
```

### 2. Make Changes
- Edit code following [Protocol-Based Design](../architecture/protocols.md)
- Add tests for new functionality
- Update documentation

### 3. Quality Checks
```bash
# Full workflow with AI auto-fixing
python -m crackerjack run --ai-fix --run-tests

# Skip hooks during iteration
python -m crackerjack run --skip-hooks
```

### 4. Commit
```bash
git add .
git commit -m "feat: add new feature"
```

## Code Standards

### Architecture Compliance
- ✅ Import protocols from `models/protocols.py`
- ✅ Constructor injection for all dependencies
- ❌ No factory functions like `get_test_manager()`
- ❌ No global singletons

### Quality Rules
- **Complexity ≤15** per function
- **Type annotations required**
- **No hardcoded paths** (use `tempfile`)
- **No shell=True** in subprocess

## Testing Requirements

- New code needs corresponding tests
- Coverage must not decrease (ratchet system)
- Prefer synchronous config tests over async

## Pull Request Process

1. Update documentation
2. Pass all quality gates
3. Request review via `/crackerjack:review-pr`

## See Also

- [Testing Guide](testing.md)
- [Architecture](../architecture/protocols.md)
- [CLAUDE.md](../README.md)
