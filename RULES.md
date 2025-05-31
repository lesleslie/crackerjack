# Crackerjack Style Rules

## Code Quality & Style

- **Use Static Typing Everywhere**
  - Always include comprehensive type hints
  - Use modern typing syntax with the pipe operator (`|`) for unions instead of `Optional[T]`
  - Import typing as `import typing as t` and prefix all typing references with `t.`

- **Modern Python Features**
  - Target Python 3.13+ features and syntax
  - Use f-strings instead of other string formatting methods
  - Prefer `pathlib.Path` over `os.path` for file operations

- **Clean Code Architecture**
  - Write modular functions that do one thing well
  - Avoid unnecessary docstrings and line comments
  - Use protocols (`t.Protocol`) instead of abstract base classes
  - Choose clear, descriptive variable and function names

- **Code Organization**
  - Group related functionality into well-defined classes
  - Use runtime-checkable protocols with `@t.runtime_checkable`
  - Prefer dataclasses for structured data
  - Use type checking with strict enforcement

- **Project Structure**
  - Structure projects with clear separation of concerns
  - Follow standard package layout conventions
  - Use [pyproject.toml](https://github.com/lesleslie/crackerjack/blob/main/pyproject.toml) for all configuration

## Tool Integration

- **Integrate with Quality Tools**
  - Configure code with Ruff for linting and formatting
  - Set up pre-commit hooks for consistent code quality
  - Use PDM with uv for dependency management
  - Implement pytest for testing with timeout handling

- **Automation Focus**
  - Automate repetitive tasks whenever possible
  - Create helpers for common development workflows
  - Implement consistent error handling and reporting

## Development Philosophy

- **Consistency is Key**
  - Maintain uniform style across the entire codebase
  - Standardize import order and grouping
  - Keep a consistent approach to error handling

- **Reliability and Testing**
  - Write comprehensive tests using pytest
  - Add appropriate timeouts to prevent hanging tests
  - Use parallel test execution when appropriate

- **Error Handling**
  - Use structured exception handling with specific exception types
  - Provide meaningful error messages
  - Add appropriate error context for debugging

- **Rich Output**
  - Use the Rich library for console output
  - Provide clear status indicators for operations
  - Format output for readability

- **Opinionated Choices**
  - Enforce a single correct way to accomplish tasks
  - Remove unnecessary flexibility that could lead to inconsistency
  - Value clarity over brevity
