# Crackerjack API Reference

This document provides documentation for the Crackerjack Python Project Management Toolkit API.

## Overview

Crackerjack provides both a modern, unified API and legacy compatibility interfaces. The modern API is designed for ease of use, type safety, and comprehensive functionality.

**Note**: The unified API provides comprehensive functionality for programmatic access to all Crackerjack features.

## Quick Start

### Modern API (Recommended)

```python
from crackerjack import CrackerjackAPI, WorkflowOptions

# Create API instance
api = CrackerjackAPI()

# Run quality checks
result = api.run_quality_checks()
print(f"Quality checks passed: {result.success}")

# Clean code
cleaning_results = api.clean_code()
print(f"Cleaned {len(cleaning_results)} files")

# Run tests with coverage
test_result = api.run_tests(coverage=True)
print(f"Tests passed: {test_result.success}")
```

### Convenience Functions

```python
from crackerjack import run_quality_checks, clean_code, run_tests, publish_package

# Simple operations
result = run_quality_checks(fast_only=True)
clean_code(backup=True)
test_result = run_tests(coverage=True)
publish_result = publish_package(version_bump="patch", dry_run=True)
```

## Core API Classes

### CrackerjackAPI

The main API class providing unified access to all Crackerjack functionality.

```python
class CrackerjackAPI:
    def __init__(
        self,
        project_path: Path | None = None,
        console: Console | None = None,
        verbose: bool = False,
    ):
        pass
```

**Parameters:**

- `project_path`: Path to the project directory (default: current directory)
- `console`: Rich console instance for output (default: auto-created)
- `verbose`: Enable verbose output

#### Methods

##### run_quality_checks()

Run code quality checks including linting, formatting, and security analysis.

```python
def run_quality_checks(
    self, fast_only: bool = False, autofix: bool = True
) -> QualityCheckResult:
    pass
```

**Parameters:**

- `fast_only`: Only run fast hooks (formatting, basic linting)
- `autofix`: Attempt to automatically fix issues (default: True)

**Returns:** `QualityCheckResult` object with detailed results

**🚧 Current Status**: Simplified implementation - detailed hook results and comprehensive error analysis are planned for future releases.

**Example:**

```python
api = CrackerjackAPI()
result = api.run_quality_checks()

if result.success:
    print("✅ All quality checks passed!")
else:
    print(f"❌ Issues found: {result.errors}")
```

##### clean_code()

Clean code by removing docstrings, comments, and extra whitespace.

```python
def clean_code(
    self, target_dir: Path | None = None, backup: bool = True
) -> list[CleaningResult]:
    pass
```

**Parameters:**

- `target_dir`: Directory to clean (default: project directory)
- `backup`: Create backup files before cleaning

**Returns:** List of `CleaningResult` objects for each processed file

**Example:**

```python
api = CrackerjackAPI()
results = api.clean_code(backup=True)

for result in results:
    if result.success:
        print(f"✅ Cleaned {result.file_path}")
        print(f"   Size: {result.original_size} → {result.cleaned_size} bytes")
```

##### run_tests()

Run tests with optional coverage reporting.

```python
def run_tests(
    self, coverage: bool = False, workers: int | None = None, timeout: int | None = None
) -> TestResult:
    pass
```

**Parameters:**

- `coverage`: Enable coverage reporting
- `workers`: Number of test workers (default: auto-detect)
- `timeout`: Test timeout in seconds

**Returns:** `TestResult` with detailed test execution results

**✅ Fully Implemented**: Returns complete test results including pass/fail counts, coverage percentage, duration, and detailed error information.

**Example:**

```python
api = CrackerjackAPI()
result = api.run_tests(coverage=True, workers=4)

print(f"Tests passed: {result.success}")
# Note: Detailed counts and coverage extraction are planned features
```

##### publish_package()

Publish package to PyPI with optional version bumping.

```python
def publish_package(
    self, version_bump: str | None = None, dry_run: bool = False
) -> PublishResult:
    pass
```

**Parameters:**

- `version_bump`: Version bump type ("patch", "minor", "major")
- `dry_run`: Perform a dry run without actual publishing

**Returns:** `PublishResult` with publishing details

**✅ Fully Implemented**: Returns complete publishing results including version information, target repositories, and detailed error handling with dry-run support.

**Example:**

```python
api = CrackerjackAPI()

# Dry run first
dry_result = api.publish_package(version_bump="patch", dry_run=True)
if dry_result.success:
    # Actual publish
    result = api.publish_package(version_bump="patch")
    print(f"Published successfully: {result.success}")
    # Note: Detailed version and publishing info are planned features
```

##### run_interactive_workflow()

Run an interactive workflow with user prompts.

```python
def run_interactive_workflow(self, options: WorkflowOptions | None = None) -> bool:
    pass
```

**Parameters:**

- `options`: Workflow options (default: minimal workflow)

**Returns:** True if workflow completed successfully

**Example:**

```python
api = CrackerjackAPI()
options = api.create_workflow_options(
    clean=True, test=True, publish="pypi", bump="patch"
)

success = api.run_interactive_workflow(options)
```

##### create_workflow_options()

Create workflow options with type safety.

```python
def create_workflow_options(
    self,
    clean: bool = False,
    test: bool = False,
    publish: str | None = None,
    bump: str | None = None,
    commit: bool = False,
    create_pr: bool = False,
    **kwargs: Any,
) -> WorkflowOptions:
    pass
```

**Parameters:**

- `clean`: Enable code cleaning
- `test`: Enable testing
- `publish`: Publishing target ("pypi", etc.)
- `bump`: Version bump type ("patch", "minor", "major")
- `commit`: Enable git commit
- `create_pr`: Enable PR creation
- `**kwargs`: Additional options

**Returns:** `WorkflowOptions` instance

##### get_project_info()

Get information about the current project.

```python
def get_project_info(self) -> dict[str, Any]:
    pass
```

**Returns:** Dictionary with project information

**Example:**

```python
api = CrackerjackAPI()
info = api.get_project_info()

print(f"Python project: {info['is_python_project']}")
print(f"Git repository: {info['is_git_repo']}")
print(f"Python files: {info['python_files_count']}")
```

## Result Classes

### QualityCheckResult

Result of quality checks execution.

```python
@dataclass
class QualityCheckResult:
    success: bool  # Overall success status
    fast_hooks_passed: bool  # Fast hooks (formatting, basic linting) status
    comprehensive_hooks_passed: bool  # Comprehensive hooks status
    errors: list[str]  # List of error messages
    warnings: list[str]  # List of warning messages
    duration: float  # Execution duration in seconds
```

### TestResult

Result of test execution.

```python
@dataclass
class TestResult:
    success: bool  # Overall test success
    passed_count: int  # Number of passed tests
    failed_count: int  # Number of failed tests
    coverage_percentage: float  # Test coverage percentage
    duration: float  # Execution duration in seconds
    errors: list[str]  # List of error messages
```

### PublishResult

Result of package publishing.

```python
@dataclass
class PublishResult:
    success: bool  # Publishing success status
    version: str  # Published version number
    published_to: list[str]  # List of publishing targets
    errors: list[str]  # List of error messages
```

### CleaningResult

Result of cleaning a single file.

```python
@dataclass
class CleaningResult:
    file_path: Path  # Path to the cleaned file
    success: bool  # Cleaning success status
    steps_completed: list[str]  # List of completed cleaning steps
    steps_failed: list[str]  # List of failed cleaning steps
    warnings: list[str]  # List of warnings
    original_size: int  # Original file size in bytes
    cleaned_size: int  # Cleaned file size in bytes
```

## Configuration Classes

### WorkflowOptions

Configuration for workflow execution.

```python
@dataclass
class WorkflowOptions:
    clean: bool = False  # Enable code cleaning
    test: bool = False  # Enable testing
    publish: str | None = None  # Publishing target
    bump: str | None = None  # Version bump type
    commit: bool = False  # Enable git commit
    create_pr: bool = False  # Enable PR creation
    interactive: bool = True  # Interactive mode
    dry_run: bool = False  # Dry run mode
```

## Convenience Functions

### run_quality_checks()

Convenience function to run quality checks.

```python
def run_quality_checks(
    project_path: Path | None = None, fast_only: bool = False
) -> QualityCheckResult:
    pass
```

### clean_code()

Convenience function to clean code.

```python
def clean_code(
    project_path: Path | None = None, backup: bool = True
) -> list[CleaningResult]:
    pass
```

### run_tests()

Convenience function to run tests.

```python
def run_tests(project_path: Path | None = None, coverage: bool = False) -> TestResult:
    pass
```

### publish_package()

Convenience function to publish package.

```python
def publish_package(
    project_path: Path | None = None,
    version_bump: str | None = None,
    dry_run: bool = False,
) -> PublishResult:
    pass
```

## Error Handling

All API methods use structured error handling with specific exception types:

```python
from crackerjack import CrackerjackError, ErrorCode

try:
    api = CrackerjackAPI()
    result = api.run_quality_checks()
except CrackerjackError as e:
    print(f"Error {e.code}: {e.message}")
    if e.recovery:
        print(f"Recovery: {e.recovery}")
```

### Error Codes

- `ErrorCode.COMMAND_EXECUTION_ERROR`: Command execution failed
- `ErrorCode.FILE_READ_ERROR`: File reading failed
- `ErrorCode.FILE_WRITE_ERROR`: File writing failed
- `ErrorCode.CLEANING_ERROR`: Code cleaning failed
- `ErrorCode.TEST_EXECUTION_ERROR`: Test execution failed
- `ErrorCode.PUBLISH_ERROR`: Publishing failed
- `ErrorCode.CONFIG_ERROR`: Configuration error
- `ErrorCode.VALIDATION_ERROR`: Validation failed

## Advanced Usage

### Custom Console

```python
from rich.console import Console
from crackerjack import CrackerjackAPI

# Custom console with file output
console = Console(file=open("output.log", "w"))
api = CrackerjackAPI(console=console)
```

### Project-Specific Configuration

```python
from pathlib import Path
from crackerjack import CrackerjackAPI

# Work with specific project
project_path = Path("/path/to/my/project")
api = CrackerjackAPI(project_path=project_path, verbose=True)

# Get project information
info = api.get_project_info()
print(f"Working with: {info['project_path']}")
```

### Workflow Customization

```python
from crackerjack import CrackerjackAPI

api = CrackerjackAPI()

# Create custom workflow
options = api.create_workflow_options(
    clean=True,  # Clean code first
    test=True,  # Run tests
    publish="pypi",  # Publish to PyPI
    bump="minor",  # Minor version bump
    commit=True,  # Commit changes
    create_pr=True,  # Create pull request
)

# Execute custom workflow
success = api.run_interactive_workflow(options)
```

## Migration from Legacy API

### Old API (Deprecated)

```python
from crackerjack import Crackerjack

# Legacy approach
crackerjack = Crackerjack(console=console)
crackerjack.run_pipeline()
```

### New API (Recommended)

```python
from crackerjack import CrackerjackAPI

# Modern approach
api = CrackerjackAPI()
result = api.run_quality_checks()
```

The new API provides:

- ✅ Better type safety
- ✅ Structured return values
- ✅ Comprehensive error handling
- ✅ Simplified interface
- ✅ Enhanced documentation
- ✅ Backward compatibility

## AI Agent Integration

Crackerjack includes powerful AI agent integration for autonomous code quality enforcement. This feature uses the MCP (Model Context Protocol) to enable AI assistants to automatically fix all types of code quality issues.

### Auto-Fixing: AI Agent vs Tool Modes

**IMPORTANT**: There are two distinct auto-fixing approaches in Crackerjack:

#### 1. Hook Auto-Fix Modes (Limited Scope)

Basic formatting tools with `--fix` options:

- `ruff --fix`: Import sorting, basic formatting
- `trailing-whitespace --fix`: Removes trailing whitespace
- `end-of-file-fixer --fix`: Ensures files end with newline

**Limitations:**

- Only handles simple style issues (whitespace, import order, basic formatting)
- Cannot fix type errors, security issues, test failures, or complex code quality problems
- No understanding of code context or business logic

#### 2. AI Agent Auto-Fixing (Comprehensive Intelligence)

The Crackerjack AI agent provides sophisticated automatic fixing:

- **Analyzes ALL error types**: hooks, tests, type checking, security, complexity
- **Reads source code**: Understands context, patterns, and relationships
- **Makes intelligent modifications**: Fixes root causes, not just symptoms
- **Handles complex issues**: Type errors, security vulnerabilities, test failures, refactoring

**Comprehensive Coverage:**

- **Type Errors (pyright)**: Adds missing annotations, fixes type mismatches
- **Security Issues (bandit)**: Removes hardcoded paths, fixes vulnerabilities
- **Dead Code (vulture)**: Removes unused imports, variables, functions
- **Test Failures**: Fixes missing fixtures, import errors, assertions
- **Code Quality (refurb)**: Applies refactoring, reduces complexity
- **All Hook Failures**: Formatting, linting, style issues

### Using AI Agent Auto-Fixing

#### Via MCP Integration

Configure your AI assistant with MCP to use the `/crackerjack:run` slash command:

**For stdio-based MCP clients:**

```json
{
  "mcpServers": {
    "crackerjack": {
      "command": "python",
      "args": ["-m", "crackerjack", "--start-mcp-server"]
    }
  }
}
```

**For WebSocket-based MCP clients:**

- **Server URL**: `ws://localhost:8675`
- **Progress Streaming**: Real-time job monitoring via WebSocket
- **Start Server**: `python -m crackerjack --start-mcp-server`

**Available MCP Tools:**

- `execute_crackerjack`: Start iterative auto-fixing with job tracking
- `get_job_progress`: Real-time progress for running jobs
- `run_crackerjack_stage`: Execute specific workflow stages
- `analyze_errors`: Intelligent error pattern analysis
- `session_management`: Track iteration state and checkpoints

Then use in conversation:

```
User: Fix all code quality issues in this project
AI: I'll use the execute_crackerjack tool to automatically fix all issues.

execute_crackerjack("/crackerjack:run")

[Returns job_id for tracking progress]

get_job_progress(job_id)

[Real-time progress updates until completion]
```

#### Via API

```python
from crackerjack import CrackerjackAPI

# Standard AI agent mode with tests, tracking, and verbose output
api = CrackerjackAPI()
result = api.run_quality_checks(
    ai_agent=True, test=True, track_progress=True, verbose=True
)

# AI agent will automatically analyze and fix issues
# across multiple iterations until all checks pass
```

### AI Agent Workflow

The AI agent runs an iterative fixing process:

1. **🚀 Run All Checks**: Fast hooks, comprehensive hooks, full test suite
1. **🔍 Analyze Failures**: AI parses errors, identifies root causes
1. **🤖 Intelligent Fixes**: AI reads source code, makes targeted changes
1. **🔄 Repeat**: Continue until ALL checks pass (up to 10 iterations)
1. **🎉 Perfect Quality**: Zero manual intervention required

**Key Benefits:**

- **Zero Configuration**: No complex flag combinations needed
- **Complete Automation**: Handles entire quality workflow
- **Intelligent Analysis**: Understands code context and business logic
- **Comprehensive Coverage**: Fixes ALL error types, not just formatting

## Best Practices

1. **Use the Modern API**: The new `CrackerjackAPI` provides better error handling and type safety.

1. **Handle Errors Gracefully**: Always check return values and handle exceptions.

1. **Use Dry Runs**: Test publishing with `dry_run=True` before actual deployment.

1. **AI Agent for Complex Issues**: Use AI agent auto-fixing for comprehensive error resolution rather than manual fixes.

1. **Regular Quality Checks**: Run quality checks frequently during development.

1. **Backup Before Cleaning**: Always use `backup=True` when cleaning code.

1. **Progressive Workflows**: Start with fast checks, then comprehensive validation.

1. **MCP Integration**: Configure AI assistants with MCP for autonomous code quality.

## Comprehensive Usage Examples

### 1. Complete CI/CD Pipeline

**Production-ready CI/CD pipeline with error handling and reporting:**

```python
#!/usr/bin/env python3
"""Production CI/CD pipeline using Crackerjack API."""

import sys
from pathlib import Path
from crackerjack import CrackerjackAPI, CrackerjackError


def ci_cd_pipeline(project_path: Path | None = None) -> bool:
    """
    Complete CI/CD pipeline with comprehensive checks.

    Args:
        project_path: Path to project (default: current directory)

    Returns:
        True if pipeline succeeds, False otherwise
    """
    try:
        # Initialize API with verbose output for CI
        api = CrackerjackAPI(project_path=project_path, verbose=True)

        # Get project information
        project_info = api.get_project_info()
        print(f"🔍 Analyzing project: {project_info['project_path']}")
        print(f"   Python files: {project_info['python_files_count']}")
        print(f"   Has tests: {project_info['has_tests']}")

        # Step 1: Fast quality checks first
        print("\n🚀 Running fast quality checks...")
        fast_result = api.run_quality_checks(fast_only=True, autofix=True)

        if not fast_result.success:
            print(f"❌ Fast checks failed in {fast_result.duration:.2f}s")
            for error in fast_result.errors:
                print(f"   • {error}")
            return False

        print(f"✅ Fast checks passed in {fast_result.duration:.2f}s")

        # Step 2: Comprehensive quality checks
        print("\n🔍 Running comprehensive quality checks...")
        quality_result = api.run_quality_checks(fast_only=False, autofix=True)

        if not quality_result.success:
            print(f"❌ Quality checks failed in {quality_result.duration:.2f}s")
            for error in quality_result.errors:
                print(f"   • {error}")
            for warning in quality_result.warnings:
                print(f"   ⚠️  {warning}")
            return False

        print(f"✅ Quality checks passed in {quality_result.duration:.2f}s")

        # Step 3: Run tests with coverage
        print("\n🧪 Running tests with coverage...")
        test_result = api.run_tests(coverage=True, workers=4, timeout=300)

        if not test_result.success:
            print(f"❌ Tests failed in {test_result.duration:.2f}s")
            for error in test_result.errors:
                print(f"   • {error}")
            return False

        print(f"✅ Tests passed in {test_result.duration:.2f}s")
        print(f"   Coverage: {test_result.coverage_percentage:.1f}%")

        # Step 4: Dry run publishing to verify build
        print("\n📦 Dry run package build...")
        dry_result = api.publish_package(version_bump="patch", dry_run=True)

        if not dry_result.success:
            print("❌ Package build failed")
            for error in dry_result.errors:
                print(f"   • {error}")
            return False

        print("✅ Package build successful")

        # Step 5: Actual publishing (only on main branch)
        import subprocess

        try:
            branch = subprocess.check_output(
                ["git", "branch", "--show-current"], text=True
            ).strip()

            if branch == "main":
                print("\n🚀 Publishing to PyPI...")
                publish_result = api.publish_package(
                    version_bump="patch", dry_run=False
                )

                if publish_result.success:
                    print(f"✅ Published version {publish_result.version}")
                    for target in publish_result.published_to:
                        print(f"   📦 Published to {target}")
                else:
                    print("❌ Publishing failed")
                    for error in publish_result.errors:
                        print(f"   • {error}")
                    return False
            else:
                print(f"⏩ Skipping publish (branch: {branch}, not main)")

        except subprocess.CalledProcessError:
            print("⚠️  Could not determine git branch, skipping publish")

        print("\n🎉 CI/CD pipeline completed successfully!")
        return True

    except CrackerjackError as e:
        print(f"❌ Crackerjack error: {e.message}")
        if e.recovery:
            print(f"💡 Recovery suggestion: {e.recovery}")
        return False

    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False


if __name__ == "__main__":
    success = ci_cd_pipeline()
    sys.exit(0 if success else 1)
```

### 2. Development Workflow Script

**Developer-friendly script for daily code quality checks:**

```python
#!/usr/bin/env python3
"""Developer workflow script for daily use."""

import sys
from pathlib import Path
from crackerjack import CrackerjackAPI, run_quality_checks


def quick_dev_check(project_path: Path | None = None) -> None:
    """Quick development quality check."""
    print("🔍 Running quick development checks...")

    # Use convenience function for simple checks
    result = run_quality_checks(project_path=project_path, fast_only=True)

    if result.success:
        print(f"✅ Code looks good! ({result.duration:.1f}s)")
    else:
        print(f"❌ Issues found ({result.duration:.1f}s):")
        for error in result.errors:
            print(f"   • {error}")

        print("\n💡 Run 'python -m crackerjack --ai-agent' for automatic fixes")


def comprehensive_dev_workflow(project_path: Path | None = None) -> bool:
    """Comprehensive development workflow with cleanup."""
    api = CrackerjackAPI(project_path=project_path, verbose=False)

    print("🧹 Starting comprehensive development workflow...\n")

    # Step 1: Clean code (with backup)
    print("1️⃣ Cleaning code...")
    try:
        cleaning_results = api.clean_code(backup=True)

        if cleaning_results:
            successful = sum(1 for r in cleaning_results if r.success)
            print(f"   ✅ Cleaned {successful}/{len(cleaning_results)} files")

            # Show savings
            total_saved = sum(
                r.original_size - r.cleaned_size for r in cleaning_results if r.success
            )
            if total_saved > 0:
                print(f"   💾 Saved {total_saved:,} bytes")
        else:
            print("   ⏩ No files needed cleaning")

    except Exception as e:
        print(f"   ❌ Cleaning failed: {e}")
        return False

    # Step 2: Quality checks
    print("\n2️⃣ Running quality checks...")
    quality_result = api.run_quality_checks(autofix=True)

    if quality_result.success:
        print(f"   ✅ Quality checks passed ({quality_result.duration:.1f}s)")
    else:
        print(f"   ❌ Quality issues found ({quality_result.duration:.1f}s)")
        for error in quality_result.errors:
            print(f"      • {error}")

    # Step 3: Quick test run
    print("\n3️⃣ Running tests...")
    test_result = api.run_tests(coverage=False, workers=2)

    if test_result.success:
        print(f"   ✅ Tests passed ({test_result.duration:.1f}s)")
    else:
        print(f"   ❌ Tests failed ({test_result.duration:.1f}s)")
        for error in test_result.errors:
            print(f"      • {error}")

    # Summary
    all_passed = quality_result.success and test_result.success
    if all_passed:
        print("\n🎉 All checks passed! Ready to commit.")
    else:
        print("\n🔧 Some issues found. Consider running AI agent for fixes:")
        print("   python -m crackerjack --ai-agent -t")

    return all_passed


def main():
    """Main entry point with command line options."""
    import argparse

    parser = argparse.ArgumentParser(description="Development workflow script")
    parser.add_argument("--quick", "-q", action="store_true", help="Quick checks only")
    parser.add_argument("--path", "-p", type=Path, help="Project path")

    args = parser.parse_args()

    if args.quick:
        quick_dev_check(args.path)
    else:
        success = comprehensive_dev_workflow(args.path)
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
```

### 3. Custom Workflow Builder

**Advanced example showing custom workflow creation:**

```python
"""Custom workflow builder example."""

from pathlib import Path
from crackerjack import CrackerjackAPI


class CustomWorkflowBuilder:
    """Builder for creating custom development workflows."""

    def __init__(self, project_path: Path | None = None):
        self.api = CrackerjackAPI(project_path=project_path, verbose=True)
        self.steps = []
        self.results = {}

    def add_cleaning_step(self, backup: bool = True) -> "CustomWorkflowBuilder":
        """Add code cleaning step."""
        self.steps.append(("clean", {"backup": backup}))
        return self

    def add_quality_checks(
        self, fast_only: bool = False, autofix: bool = True
    ) -> "CustomWorkflowBuilder":
        """Add quality checking step."""
        self.steps.append(("quality", {"fast_only": fast_only, "autofix": autofix}))
        return self

    def add_testing(
        self, coverage: bool = True, workers: int | None = None
    ) -> "CustomWorkflowBuilder":
        """Add testing step."""
        self.steps.append(("test", {"coverage": coverage, "workers": workers}))
        return self

    def add_publishing(
        self, version_bump: str | None = None, dry_run: bool = False
    ) -> "CustomWorkflowBuilder":
        """Add publishing step."""
        self.steps.append(
            ("publish", {"version_bump": version_bump, "dry_run": dry_run})
        )
        return self

    def execute(self) -> dict[str, bool]:
        """Execute all workflow steps."""
        print(f"🚀 Executing custom workflow with {len(self.steps)} steps\n")

        overall_success = True

        for i, (step_name, kwargs) in enumerate(self.steps, 1):
            print(f"Step {i}/{len(self.steps)}: {step_name}")

            try:
                if step_name == "clean":
                    results = self.api.clean_code(**kwargs)
                    success = all(r.success for r in results)
                    self.results[step_name] = {"success": success, "details": results}

                elif step_name == "quality":
                    result = self.api.run_quality_checks(**kwargs)
                    success = result.success
                    self.results[step_name] = {"success": success, "details": result}

                elif step_name == "test":
                    result = self.api.run_tests(**kwargs)
                    success = result.success
                    self.results[step_name] = {"success": success, "details": result}

                elif step_name == "publish":
                    result = self.api.publish_package(**kwargs)
                    success = result.success
                    self.results[step_name] = {"success": success, "details": result}

                if success:
                    print(f"   ✅ {step_name} completed successfully")
                else:
                    print(f"   ❌ {step_name} failed")
                    overall_success = False

            except Exception as e:
                print(f"   💥 {step_name} crashed: {e}")
                self.results[step_name] = {"success": False, "error": str(e)}
                overall_success = False

        print(
            f"\n{'🎉' if overall_success else '❌'} Workflow {'completed' if overall_success else 'failed'}"
        )
        return self.results


# Usage examples:
def main():
    # Example 1: Development workflow
    print("=== Development Workflow ===")
    dev_results = (
        CustomWorkflowBuilder()
        .add_cleaning_step(backup=True)
        .add_quality_checks(fast_only=True, autofix=True)
        .add_testing(coverage=False)
        .execute()
    )

    # Example 2: Release workflow
    print("\n=== Release Workflow ===")
    release_results = (
        CustomWorkflowBuilder()
        .add_quality_checks(fast_only=False, autofix=True)
        .add_testing(coverage=True, workers=4)
        .add_publishing(version_bump="patch", dry_run=True)  # Dry run first
        .execute()
    )

    # Check if dry run succeeded, then do real publish
    if release_results.get("publish", {}).get("success"):
        print("\n=== Actual Publishing ===")
        (
            CustomWorkflowBuilder()
            .add_publishing(version_bump="patch", dry_run=False)
            .execute()
        )


if __name__ == "__main__":
    main()
```

### 4. Error Handling & Recovery

**Comprehensive error handling patterns:**

```python
"""Error handling and recovery patterns."""

import logging
from pathlib import Path
from crackerjack import CrackerjackAPI, CrackerjackError, ErrorCode

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def robust_quality_check(project_path: Path | None = None) -> bool:
    """Quality check with comprehensive error handling."""

    try:
        api = CrackerjackAPI(project_path=project_path, verbose=True)

        # Validate project first
        project_info = api.get_project_info()

        if "error" in project_info:
            logger.error(f"Project validation failed: {project_info['error']}")
            return False

        if not project_info["is_python_project"]:
            logger.warning("Not a Python project, running limited checks")

        # Run quality checks with error handling
        result = api.run_quality_checks(autofix=True)

        if result.success:
            logger.info(f"✅ Quality checks passed in {result.duration:.2f}s")
            return True
        else:
            logger.error("❌ Quality checks failed:")
            for error in result.errors:
                logger.error(f"   • {error}")

            # Attempt recovery strategies
            return attempt_recovery(api, result)

    except CrackerjackError as e:
        logger.error(f"Crackerjack error [{e.code}]: {e.message}")

        # Handle specific error types
        if e.code == ErrorCode.COMMAND_EXECUTION_ERROR:
            logger.info("💡 Try running with --skip-hooks to identify the failing hook")
        elif e.code == ErrorCode.FILE_READ_ERROR:
            logger.info("💡 Check file permissions and disk space")
        elif e.code == ErrorCode.CONFIG_ERROR:
            logger.info("💡 Verify pyproject.toml and .pre-commit-config.yaml")

        if e.recovery:
            logger.info(f"🔧 Suggested recovery: {e.recovery}")

        return False

    except FileNotFoundError as e:
        logger.error(f"File not found: {e}")
        logger.info("💡 Ensure you're in the correct project directory")
        return False

    except PermissionError as e:
        logger.error(f"Permission denied: {e}")
        logger.info("💡 Check file/directory permissions")
        return False

    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        logger.info("💡 Try running with --verbose for more details")
        return False


def attempt_recovery(api: CrackerjackAPI, failed_result) -> bool:
    """Attempt recovery strategies for failed quality checks."""

    logger.info("🔧 Attempting recovery strategies...")

    # Strategy 1: Try fast-only checks first
    logger.info("   Strategy 1: Fast checks only...")
    fast_result = api.run_quality_checks(fast_only=True, autofix=True)

    if fast_result.success:
        logger.info("   ✅ Fast checks passed, trying comprehensive...")
        comp_result = api.run_quality_checks(fast_only=False, autofix=True)
        if comp_result.success:
            logger.info("   ✅ Recovery successful!")
            return True

    # Strategy 2: Try without autofix
    logger.info("   Strategy 2: Manual fixing needed...")
    manual_result = api.run_quality_checks(autofix=False)

    if manual_result.success:
        logger.info("   ✅ Quality checks pass without autofix")
        logger.info("   💡 Manual intervention may be needed for some issues")
        return True

    # Strategy 3: Project info for diagnosis
    logger.info("   Strategy 3: Diagnostic information...")
    project_info = api.get_project_info()

    logger.info(f"   Project details:")
    logger.info(
        f"      Python files: {project_info.get('python_files_count', 'unknown')}"
    )
    logger.info(f"      Has tests: {project_info.get('has_tests', 'unknown')}")
    logger.info(f"      Git repo: {project_info.get('is_git_repo', 'unknown')}")

    logger.error("   ❌ All recovery strategies failed")
    logger.info("   💡 Consider running: python -m crackerjack --ai-agent -t")
    logger.info("   💡 AI agent can automatically fix complex issues")

    return False


def monitoring_example():
    """Example of monitoring and alerting integration."""

    success = robust_quality_check()

    # Integration with monitoring systems
    if not success:
        # Send alert to monitoring system
        logger.error("🚨 Quality check failure - alerting monitoring system")

        # Example: Send to external monitoring
        try:
            # send_alert_to_datadog("crackerjack.quality_check.failed")
            # send_slack_notification("Quality checks failed in project")
            pass
        except Exception as e:
            logger.error(f"Failed to send alert: {e}")

    return success


if __name__ == "__main__":
    import sys

    success = monitoring_example()
    sys.exit(0 if success else 1)
```

### 5. Integration Examples

**Integration with popular development tools:**

```python
"""Integration examples with popular tools."""

import json
import os
import subprocess
from pathlib import Path
from crackerjack import CrackerjackAPI


# GitHub Actions Integration
def github_actions_integration():
    """Example GitHub Actions integration."""

    # Read GitHub environment variables
    github_event = os.getenv("GITHUB_EVENT_NAME")
    github_ref = os.getenv("GITHUB_REF", "")
    is_main_branch = github_ref.endswith("/main")
    is_pr = github_event == "pull_request"

    api = CrackerjackAPI(verbose=True)

    print(f"🔍 GitHub Event: {github_event}")
    print(f"🔍 Branch: {github_ref}")
    print(f"🔍 Is PR: {is_pr}")
    print(f"🔍 Is Main: {is_main_branch}")

    # Different workflows for different events
    if is_pr:
        # PR workflow: Focus on quality and tests
        print("\n📋 Running PR validation workflow...")

        quality_result = api.run_quality_checks(autofix=False)  # No autofix in PR
        test_result = api.run_tests(coverage=True)

        # Set GitHub outputs
        print(f"::set-output name=quality-passed::{quality_result.success}")
        print(f"::set-output name=tests-passed::{test_result.success}")
        print(f"::set-output name=coverage::{test_result.coverage_percentage}")

        # Comment on PR with results (pseudo-code)
        if not quality_result.success or not test_result.success:
            print("::error::Quality checks or tests failed")
            exit(1)

    elif is_main_branch:
        # Main branch: Full workflow with potential publishing
        print("\n🚀 Running main branch workflow...")

        quality_result = api.run_quality_checks(autofix=True)
        test_result = api.run_tests(coverage=True)

        if quality_result.success and test_result.success:
            # Auto-publish on main branch
            publish_result = api.publish_package(version_bump="patch")

            if publish_result.success:
                print(f"🎉 Published version {publish_result.version}")
        else:
            print("::error::Quality checks or tests failed on main branch")
            exit(1)


# Docker Integration
def docker_integration():
    """Example Docker container integration."""

    dockerfile_content = """
FROM python:3.13-slim

WORKDIR /app

# Install UV and Crackerjack
RUN pip install uv crackerjack

# Copy project files
COPY . .

# Install dependencies
RUN uv sync

# Run quality checks
CMD ["python", "-c", "
import sys
from crackerjack import CrackerjackAPI

api = CrackerjackAPI(verbose=True)

# Run comprehensive workflow
quality_ok = api.run_quality_checks().success
tests_ok = api.run_tests(coverage=True).success

if quality_ok and tests_ok:
    print('🎉 All checks passed!')
    sys.exit(0)
else:
    print('❌ Checks failed!')
    sys.exit(1)
"]
"""

    # Write Dockerfile
    Path("Dockerfile").write_text(dockerfile_content)
    print("📝 Created Dockerfile for Crackerjack integration")


# VS Code Integration
def vscode_integration():
    """Example VS Code tasks integration."""

    vscode_tasks = {
        "version": "2.0.0",
        "tasks": [
            {
                "label": "Crackerjack: Quick Check",
                "type": "shell",
                "command": "python",
                "args": [
                    "-c",
                    "from crackerjack import run_quality_checks; run_quality_checks(fast_only=True)",
                ],
                "group": "build",
                "presentation": {
                    "echo": True,
                    "reveal": "always",
                    "focus": False,
                    "panel": "shared",
                },
                "problemMatcher": [],
            },
            {
                "label": "Crackerjack: Full Workflow",
                "type": "shell",
                "command": "python",
                "args": ["-m", "crackerjack", "-t"],
                "group": "test",
                "presentation": {
                    "echo": True,
                    "reveal": "always",
                    "focus": False,
                    "panel": "shared",
                },
            },
            {
                "label": "Crackerjack: AI Agent Fix",
                "type": "shell",
                "command": "python",
                "args": ["-m", "crackerjack", "--ai-agent", "-t"],
                "group": "build",
                "presentation": {
                    "echo": True,
                    "reveal": "always",
                    "focus": false,
                    "panel": "dedicated",
                },
            },
        ],
    }

    # Create .vscode directory and tasks.json
    vscode_dir = Path(".vscode")
    vscode_dir.mkdir(exist_ok=True)

    tasks_file = vscode_dir / "tasks.json"
    tasks_file.write_text(json.dumps(vscode_tasks, indent=2))

    print("📝 Created VS Code tasks for Crackerjack integration")


# Pre-commit Hook Integration
def precommit_integration():
    """Example pre-commit hook integration."""

    precommit_script = '''#!/usr/bin/env python3
"""Pre-commit hook using Crackerjack API."""

import sys
from crackerjack import run_quality_checks

def main():
    print("🔍 Running pre-commit quality checks...")

    # Fast checks only for pre-commit (speed is important)
    result = run_quality_checks(fast_only=True, autofix=True)

    if result.success:
        print(f"✅ Pre-commit checks passed ({result.duration:.1f}s)")
        return 0
    else:
        print(f"❌ Pre-commit checks failed ({result.duration:.1f}s)")
        for error in result.errors:
            print(f"   • {error}")

        print("\\n💡 Run 'python -m crackerjack --ai-agent' to fix issues")
        return 1

if __name__ == "__main__":
    sys.exit(main())
'''

    # Create .git/hooks directory if it doesn't exist
    hooks_dir = Path(".git") / "hooks"
    hooks_dir.mkdir(exist_ok=True)

    # Write pre-commit hook
    precommit_hook = hooks_dir / "pre-commit"
    precommit_hook.write_text(precommit_script)
    precommit_hook.chmod(0o755)  # Make executable

    print("📝 Created Git pre-commit hook with Crackerjack integration")


if __name__ == "__main__":
    print("🔧 Setting up development integrations...")

    # docker_integration()  # Uncomment to create Dockerfile
    # vscode_integration()   # Uncomment to create VS Code tasks
    # precommit_integration() # Uncomment to create pre-commit hook

    # github_actions_integration()  # Run if in GitHub Actions

    print("✅ Integration examples ready!")
```
