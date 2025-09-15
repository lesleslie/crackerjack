# Stage Headers Implementation Plan

## Overview

Add consistent stage headers for publishing workflow stages to match the existing formatting used for hooks and tests.

## Current Pattern

```
--------------------------------------------------------------------------------
🔍 HOOKS Running code quality checks
--------------------------------------------------------------------------------

🧪 TESTS Running test suite
--------------------------------------------------------------------------------
```

## New Stages to Add Headers

### 1. Version Bump Stage

- **Emoji**: 📦 (package)
- **Color**: `[bold bright_magenta]`
- **Text**: "BUMP VERSION"
- **Description**: "Updating package version"

### 2. Publish Stage

- **Emoji**: 🚀 (rocket)
- **Color**: `[bold bright_yellow]`
- **Text**: "PUBLISH"
- **Description**: "Publishing to PyPI"

### 3. Git Operations Stage

- **Emoji**: 📤 (outbox)
- **Color**: `[bold bright_green]`
- **Text**: "COMMIT & PUSH"
- **Description**: "Committing and pushing changes"

## Implementation Location

**File**: `/Users/les/Projects/crackerjack/crackerjack/core/phase_coordinator.py`

**Method**: `_execute_publishing_workflow` - will be refactored to include stage headers

## Code Structure

```python
def _display_version_bump_header(self, version_type: str) -> None:
    self.console.print("\n" + "-" * 74)
    self.console.print(
        f"[bold bright_magenta]📦 BUMP VERSION[/bold bright_magenta] [bold bright_white]Updating package version ({version_type})[/bold bright_white]"
    )
    self.console.print("-" * 74 + "\n")


def _display_publish_header(self) -> None:
    self.console.print("\n" + "-" * 74)
    self.console.print(
        "[bold bright_yellow]🚀 PUBLISH[/bold bright_yellow] [bold bright_white]Publishing to PyPI[/bold bright_white]"
    )
    self.console.print("-" * 74 + "\n")


def _display_git_operations_header(self) -> None:
    self.console.print("\n" + "-" * 74)
    self.console.print(
        "[bold bright_green]📤 COMMIT & PUSH[/bold bright_green] [bold bright_white]Committing and pushing changes[/bold bright_white]"
    )
    self.console.print("-" * 74 + "\n")
```

## Integration Points

1. **Before `bump_version()`**: Add version bump header
1. **Before `publish_package()`**: Add publish header
1. **Before git staging/tagging**: Add git operations header

This will create consistent visual separation and clear progress indication for users during the publishing workflow.
