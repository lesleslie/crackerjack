# Tree-Sitter Quality Adapter

Multi-language code quality checks using tree-sitter for Crackerjack.

## Features

- **Multi-language support**: Python, Go, JavaScript, TypeScript, Rust
- **Error-tolerant parsing**: Works with incomplete or malformed code
- **Complexity metrics**: Cyclomatic complexity, nesting depth, parameters
- **Structural pattern detection**: Functions, classes, imports

## Rules

| Rule | Severity | Description |
|------|----------|-------------|
| TS001 | warning | Cyclomatic complexity exceeds threshold |
| TS002 | warning | Deep nesting exceeds threshold |
| TS003 | info | Too many function parameters |

## Configuration

```yaml
treesitter:
  enabled: true
  max_complexity: 15
  max_nesting_depth: 4
  max_parameters: 7
  supported_extensions:
    - .py
    - .go
    - .js
    - .ts
    - .rs
```

## Dependencies

Requires `mcp-common[treesitter]` to be installed.
