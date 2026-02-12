# Quality Gates

Crackerjack runs comprehensive quality checks in a **specific workflow order**.

## Workflow Order

### 1. Fast Hooks (~5s)

- **Formatting**: ruff formatting, mdformat
- **Basic Checks**: Import validation, basic linting
- **Retry**: One retry attempt if failed
- **AI-Fix**: Enabled if still failing

### 2. Test Suite

- **Collection**: ALL failures collected (don't stop on first)
- **Parallel**: pytest-xdist with auto-detected workers
- **Coverage**: Ratchet system (never decrease baseline)

### 3. Comprehensive Hooks (~30s)

- **Type Checking**: Zuban (Rust-powered, 20-200x faster)
- **Security**: bandit security audit
- **Complexity**: complexipy (max 15 per function)
- **Dead Code**: Skylos (Rust-powered, 20x faster)
- **AI-Fix**: Batch fixing all collected issues

## Quality Tools

| Tool | Purpose | Timeout |
|-------|---------|----------|
| ruff | Formatting, linting | 60s |
| mdformat | Markdown formatting | 10s |
| zuban | Type checking | 60s |
| bandit | Security audit | 300s |
| complexipy | Complexity analysis | 600s |
| skylos | Dead code detection | 60s |
| pytest | Test execution | 600s |

## See Also

- [CLAUDE.md](../README.md#quality-process) - Complete quality guidelines
