# Crackerjack Style Rules

## Code Quality & Style

- **Use Static Typing Everywhere**

  - Always include comprehensive type hints
  - Use modern typing syntax with the pipe operator (`|`) for unions instead of `Optional[T]`
  - Import typing as `import typing as t` and prefix all typing references with `t.`
  - Never import individual types directly from typing (e.g., avoid `from typing import List, Dict, Optional`)
  - Always use the `t.` prefix for all typing-related types
  - Use built-in collection types directly instead of typing equivalents:
    - Use `list[str]` instead of `t.List[str]`
    - Use `dict[str, int]` instead of `t.Dict[str, int]`
    - Use `tuple[int, ...]` instead of `t.Tuple[int, ...]`

- **Modern Python Features**

  - Target Python 3.13+ features and syntax
  - Use f-strings instead of other string formatting methods
  - Prefer `pathlib.Path` over `os.path` for file operations

- **Clean Code Architecture**

  - Write modular functions that do one thing well
  - **NO DOCSTRINGS**: Never add docstrings to any code - the codebase standard is to have no docstrings (they are automatically removed by the `-x` flag)
  - Avoid unnecessary line comments - use them sparingly only for complex logic
  - Use protocols (`t.Protocol`) instead of abstract base classes
  - Choose clear, descriptive variable and function names that make the code self-documenting

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
  - Use UV for dependency management
  - Implement pytest for testing with timeout handling

- **Use UV for Tool Execution**

  - Always use `uv run` to execute tools within the project's virtual environment
  - Run pytest with `uv run pytest` instead of calling pytest directly
  - Execute tools like pyright, ruff, and crackerjack through UV: `uv run pyright`
  - Ensures consistent tool versions and environment isolation

- **Pre-Commit Hook Configuration**

  - Enforce a comprehensive set of pre-commit hooks for quality control:
    - Pyright for static type checking
    - Ruff for linting and formatting
    - Vulture for detecting unused code
    - Creosote for identifying unused dependencies
    - Complexipy for code complexity analysis
    - Codespell for spell checking
    - Autotyping for type annotation
    - Refurb for Python code modernization
    - Bandit for security vulnerabilities
  - Run hooks with `uv run pre-commit run --all-files` during development
  - Configure hooks in `.pre-commit-config.yaml` with exact versions
  - Ensure all code passes pre-commit checks before submitting

- **Specific Tool Compliance Standards**

  - **Refurb (FURB Rules):**

    - **FURB109**: ALWAYS use tuples `()` instead of lists `[]` for `in` membership testing
    - **FURB120**: Never pass default values that match the function's default (e.g., `None` for optional parameters)
    - Use modern Python patterns and built-ins consistently

  - **Pyright Type Checking:**

    - **reportMissingParameterType**: ALL function parameters MUST have complete type annotations
    - **reportArgumentType**: Protocol implementations must include ALL required properties with correct types
    - Use explicit type annotations for all function parameters and return types

  - **Complexipy Code Complexity:**

    - Keep cognitive complexity under 20 per function/method
    - Break complex methods into 3-5 smaller helper functions with single responsibilities
    - Use descriptive function names that explain their purpose

  - **Bandit Security:**

    - Never use dangerous functions like `eval()`, `exec()`, or `subprocess.shell=True`
    - Use `secrets` module for cryptographic operations, never `random`
    - Always specify encoding when opening files

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
  - Never create files directly on the filesystem in tests
    - Always use `tempfile` module for temporary files and directories
    - Use pytest's `tmp_path` and `tmp_path_factory` fixtures
    - Clean up any generated resources after tests complete
    - Tests should be isolated and not affect the surrounding environment
    - Avoid hard-coded paths in tests that point to the real filesystem

- **Code Quality Validation**

  - Code should pass all quality checks when run through crackerjack
  - The ultimate goal is to run `python -m crackerjack -x -t` without any errors
  - This validates proper typing, formatting, linting, and test success
  - Consider code incomplete until it passes this validation

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

## Additional Best Practices

- **Performance Considerations**

  - Use profiling tools to identify bottlenecks in critical code paths
  - Benchmark and compare alternative implementations for optimization
  - Favor readability over micro-optimizations except for demonstrated hot spots
  - Document any non-obvious optimizations with comments explaining the rationale

- **Python Version Strategy**

  - Target only the latest stable Python release (3.13+)
  - Adopt new language features as soon as they become available
  - Do not maintain backward compatibility with older Python versions
  - Regularly update codebases to take advantage of new language improvements
  - Plan to upgrade within weeks of a new Python release

- **Documentation Minimalism**

  - Keep documentation focused on "why" rather than "what" the code does
  - Document APIs at the module or class level rather than individual functions
  - Use type hints to replace most parameter documentation
  - Create examples for complex functionality instead of verbose explanations

- **Testing Philosophy**

  - Write tests for behavior, not implementation details
  - Focus on testing public interfaces rather than private functions
  - Use property-based testing for algorithmic code where appropriate
  - Separate unit tests, integration tests, and benchmarks
  - Aim for complete test coverage of critical paths but avoid test-for-test's-sake
  - Use asyncio exclusively for async testing; do not test with trio compatibility
  - Configure pytest with asyncio_mode="auto" for simpler async testing

- **Dependency Management**

  - Keep external dependencies to a minimum
  - Pin exact versions in lockfiles but use range specifications in pyproject.toml
  - Regularly audit dependencies for security issues
  - Prefer standard library solutions when reasonable
  - Favor dependencies that support the latest Python version

- **Code Review Standards**

  - All code should be reviewed before merging
  - Automate style and formatting checks to focus reviews on substance
  - Look for edge cases and error handling in reviews
  - Ensure tests adequately cover the changes

- **Session Progress Tracking**

  - Use `--track-progress` flag for complex development workflows
  - Always enable progress tracking when working with AI assistants
  - Keep progress files for debugging and session recovery
  - Use descriptive progress file names for important sessions: `--progress-file release-v1.0.md`
  - Combine with AI agent mode for maximum visibility: `--track-progress --ai-agent`
  - Progress files should be included in .gitignore to avoid committing session state
  - Use `--resume-from` to continue interrupted sessions rather than starting over

## AI Assistant Self-Maintenance

- **Quality Standards Maintenance**

  - AI assistants should update CLAUDE.md and RULES.md weekly or after pre-commit failures
  - Learn from new Refurb rules (FURB codes), Pyright errors (reportXxx), and Complexipy thresholds
  - Add newly discovered error patterns to documentation with code examples
  - Test all documentation updates by running `python -m crackerjack --comprehensive`
  - Prioritize frequently occurring error patterns as **CRITICAL** standards

- **Self-Learning Protocol**

  - When encountering new pre-commit failures, extract the error pattern and add to standards
  - Format new patterns with "Bad" and "Good" code examples
  - Update the "AI Code Generation Best Practices" checklist in CLAUDE.md
  - Ensure RULES.md stays synchronized with CLAUDE.md standards
  - Monitor tool version updates and incorporate new rules as they emerge
