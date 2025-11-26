# Enhanced Test Error Reporting Implementation Plan

**Status:** 🚧 In Progress
**Created:** 2025-11-20
**Target Completion:** 2025-11-22
**Estimated Effort:** 6-9 hours total

## Executive Summary

Improve test failure reporting in verbose mode (`-v` flag) using a hybrid approach combining pytest's native `-vv` verbosity with custom Rich-formatted output panels. This provides immediate wins with low risk while enabling progressive enhancement.

## Current State Analysis

### Current Implementation

- **Location:** `crackerjack/managers/test_manager.py:327-352`
- **Issue:** Raw output dump in verbose mode (line 348)
- **Limitation:** Simple text extraction (line 719-729) captures only first 10 failure lines

### Current Behavior (Observed)

```
❌ Tests failed in 337.7s

Test Output:

/Users/les/Projects/crackerjack/.venv/lib/python3.13/site-packages/_pytest/main.
py:353: PluggyTeardownRaisedWarning: A plugin raised an exception during an
old-style hookwrapper teardown.
[... raw pytest output ...]
```

**Problems:**

- ❌ No structure or formatting
- ❌ Difficult to scan for relevant errors
- ❌ Missing traceback context
- ❌ No syntax highlighting
- ❌ No file/line references for quick navigation

## Solution: Hybrid Approach

**Phase 1** (Quick Win): pytest `-vv` + Rich Formatting
**Phase 2** (Enhancement): Structured Failure Parser with Panels

**Combined Success Probability:** 92%

______________________________________________________________________

## Phase 1: Pytest `-vv` with Rich Formatting

**Priority:** HIGH
**Estimated Time:** 2-3 hours
**Success Probability:** 95%
**Dependencies:** None (uses existing Rich library)

### Objectives

- [x] ~~Create implementation plan~~
- [ ] Add verbosity level control to pytest commands
- [ ] Implement output section splitting
- [ ] Create Rich-formatted output renderer
- [ ] Add color-coded sections (failures, summaries, tracebacks)
- [ ] Test with actual failing tests

### Implementation Details

#### 1.1 Enhanced Verbosity Options

**File:** `crackerjack/managers/test_command_builder.py`
**Lines:** 324-334 (current `_add_verbosity_options`)

**Changes:**

```python
def _add_verbosity_options(self, cmd: list[str], options: OptionsProtocol) -> None:
    """Add verbosity options with enhanced detail levels.

    Verbosity Levels:
    - Standard (-v): Basic test names
    - Verbose (-vv): Assertions, captured output, test details
    - Extra verbose (-vvv): Full locals, all test internals (ai_debug mode)
    """
    # Determine verbosity level
    if options.verbose:
        if getattr(options, "ai_debug", False):
            cmd.append("-vvv")  # Extra verbose for AI debugging
            self.console.print("[cyan]🔍 Using extra verbose mode (-vvv)[/cyan]")
        else:
            cmd.append("-vv")  # Double verbose shows more context
            self.console.print("[cyan]🔍 Using verbose mode (-vv)[/cyan]")
    else:
        cmd.append("-v")  # Standard verbose

    cmd.extend(
        [
            # Longer tracebacks in verbose mode
            "--tb=long" if options.verbose else "--tb=short",
            # Show all test outcomes summary (not just failures)
            "-ra",
            "--strict-markers",
            "--strict-config",
        ]
    )
```

**Rationale:**

- ✅ Uses pytest's native capabilities (no parsing fragility)
- ✅ Progressive verbosity (basic → verbose → extra)
- ✅ `-ra` shows "summary of all outcomes" (passed, failed, skipped, errors, xfailed, xpassed)
- ✅ `--tb=long` provides full traceback context

#### 1.2 Output Section Splitter

**File:** `crackerjack/managers/test_manager.py`
**Location:** New method after `_extract_failure_lines` (after line 729)

**New Method:**

```python
def _split_output_sections(self, output: str) -> list[tuple[str, str]]:
    """Split pytest output into logical sections for rendering.

    Sections:
    - header: Session start, test collection
    - failure: Individual test failures with tracebacks
    - summary: Short test summary info
    - footer: Coverage, timing, final stats

    Returns:
        List of (section_type, section_content) tuples
    """
    sections = []
    lines = output.split("\n")

    current_section = []
    current_type = "header"

    for line in lines:
        # Detect section boundaries
        if "short test summary" in line.lower():
            # Save previous section
            if current_section:
                sections.append((current_type, "\n".join(current_section)))
            current_section = [line]
            current_type = "summary"

        elif " FAILED " in line or " ERROR " in line:
            # Save previous section
            if current_section and current_type != "failure":
                sections.append((current_type, "\n".join(current_section)))
                current_section = []
            current_type = "failure"
            current_section.append(line)

        elif line.startswith("=") and ("passed" in line or "failed" in line):
            # Footer section
            if current_section:
                sections.append((current_type, "\n".join(current_section)))
            current_section = [line]
            current_type = "footer"

        else:
            current_section.append(line)

    # Add final section
    if current_section:
        sections.append((current_type, "\n".join(current_section)))

    return sections
```

**Rationale:**

- ✅ Separates different output types for targeted formatting
- ✅ Simple string matching (robust across pytest versions)
- ✅ Handles multi-line tracebacks correctly

#### 1.3 Rich-Formatted Output Renderer

**File:** `crackerjack/managers/test_manager.py`
**Location:** Replace raw print at line 348

**New Method:**

```python
def _render_formatted_output(self, output: str, options: OptionsProtocol) -> None:
    """Render test output with Rich formatting and sections.

    Args:
        output: Raw pytest output text
        options: Test options (for verbosity level)
    """
    from rich.panel import Panel
    from rich.syntax import Syntax
    from rich.console import Group

    # Split output into sections
    sections = self._split_output_sections(output)

    for section_type, section_content in sections:
        if not section_content.strip():
            continue

        if section_type == "failure":
            # Render failures with syntax highlighting
            self._render_failure_section(section_content)

        elif section_type == "summary":
            # Render summary in yellow panel
            panel = Panel(
                section_content.strip(),
                title="[bold yellow]📋 Test Summary[/bold yellow]",
                border_style="yellow",
                width=get_console_width(),
            )
            self.console.print(panel)

        elif section_type == "footer":
            # Render footer with stats
            self.console.print(f"\n[cyan]{section_content.strip()}[/cyan]\n")

        else:
            # Header and other sections (dimmed)
            if options.verbose or getattr(options, "ai_debug", False):
                self.console.print(f"[dim]{section_content}[/dim]")


def _render_failure_section(self, section_content: str) -> None:
    """Render a failure section with syntax highlighting.

    Args:
        section_content: Failure output text
    """
    from rich.panel import Panel
    from rich.syntax import Syntax

    # Apply Python syntax highlighting to tracebacks
    syntax = Syntax(
        section_content,
        "python",
        theme="monokai",
        line_numbers=False,
        word_wrap=True,
        background_color="default",
    )

    panel = Panel(
        syntax,
        title="[bold red]❌ Test Failure[/bold red]",
        border_style="red",
        width=get_console_width(),
    )
    self.console.print(panel)
```

**Rationale:**

- ✅ Rich panels provide visual structure
- ✅ Syntax highlighting makes Python tracebacks readable
- ✅ Color coding (red=failures, yellow=summary, cyan=stats)
- ✅ Graceful fallback if Rich rendering fails

#### 1.4 Update Failure Handler

**File:** `crackerjack/managers/test_manager.py`
**Lines:** 343-351 (current `_handle_test_failure`)

**Modified Code:**

```python
def _handle_test_failure(
    self,
    stderr: str,
    stdout: str,
    duration: float,
    options: OptionsProtocol,
    workers: int | str,
) -> bool:
    self.console.print(f"[red]❌[/red] Tests failed in {duration:.1f}s")

    # Parse and display test statistics panel (use stdout for stats)
    combined_output = stdout + "\n" + stderr
    stats = self._parse_test_statistics(combined_output)
    if stats["total"] > 0:  # Only show panel if tests were actually run
        self._render_test_results_panel(stats, workers, success=False)

    # Enhanced error reporting in verbose mode
    if options.verbose or getattr(options, "ai_debug", False):
        self._last_test_failures = self._extract_failure_lines(combined_output)

        if combined_output.strip():
            self.console.print(
                "\n[red]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/red]"
            )
            self.console.print("[bold red]Test Output (Enhanced)[/bold red]")
            self.console.print(
                "[red]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/red]\n"
            )

            # Use Rich-formatted output instead of raw dump
            self._render_formatted_output(combined_output, options)
    else:
        self._last_test_failures = []

    return False
```

**Rationale:**

- ✅ Maintains backward compatibility (only enhanced in verbose mode)
- ✅ Clear visual separator for test output section
- ✅ Calls new rendering method instead of raw print

### Testing Plan (Phase 1)

1. **Create test with known failures:**

   ```bash
   # Create temporary failing test
   cat > tests/test_enhanced_reporting.py << 'EOF'
   def test_assertion_failure():
       assert 1 == 2, "Expected equality failure"

   def test_exception_failure():
       raise ValueError("Intentional error for testing")

   def test_import_error():
       import nonexistent_module
   EOF
   ```

1. **Run with verbose mode:**

   ```bash
   python -m crackerjack -s -t -v
   ```

1. **Verify output shows:**

   - ✅ Colored panels for failures
   - ✅ Syntax-highlighted tracebacks
   - ✅ Yellow summary panel
   - ✅ Clear section separation

1. **Test with AI debug mode:**

   ```bash
   python -m crackerjack -s -t --ai-debug
   ```

1. **Verify `-vvv` output shows:**

   - ✅ Full local variables
   - ✅ All test internals
   - ✅ Maximum pytest detail

### Acceptance Criteria (Phase 1)

- [ ] Verbose mode (`-v`) shows `-vv` pytest output
- [ ] AI debug mode (`--ai-debug`) shows `-vvv` pytest output
- [ ] Failures appear in red panels with syntax highlighting
- [ ] Summary appears in yellow panel
- [ ] Stats appear in cyan text
- [ ] No regressions in non-verbose mode
- [ ] Tests pass after implementation

______________________________________________________________________

## Phase 2: Enhanced Failure Parser with Structured Panels

**Priority:** MEDIUM
**Estimated Time:** 4-6 hours
**Success Probability:** 85%
**Dependencies:** Phase 1 completion

### Objectives

- [ ] Design structured failure data model
- [ ] Implement regex-based failure parser
- [ ] Create Rich table renderer for failure details
- [ ] Add file/line clickable links (if terminal supports)
- [ ] Group failures by test file
- [ ] Show assertion diffs for comparison failures
- [ ] Test with complex failure scenarios

### Implementation Details

#### 2.1 Structured Failure Data Model

**File:** `crackerjack/models/test_models.py` (new file)

**New Dataclass:**

```python
from dataclasses import dataclass, field
from typing import Any


@dataclass
class TestFailure:
    """Structured representation of a test failure."""

    test_name: str
    """Full test node ID (e.g., tests/test_foo.py::TestClass::test_method)"""

    status: str
    """Test status: FAILED, ERROR, or XFAIL"""

    location: str
    """File path and line number (e.g., tests/test_foo.py:42)"""

    traceback: list[str] = field(default_factory=list)
    """Full traceback lines"""

    assertion: str | None = None
    """Assertion error message if present"""

    captured_stdout: str | None = None
    """Captured stdout during test execution"""

    captured_stderr: str | None = None
    """Captured stderr during test execution"""

    duration: float | None = None
    """Test execution duration in seconds"""

    short_summary: str | None = None
    """One-line failure summary"""

    locals_context: dict[str, Any] = field(default_factory=dict)
    """Local variables at failure point (in -vvv mode)"""

    def get_file_path(self) -> str:
        """Extract file path from location."""
        if ":" in self.location:
            return self.location.split(":")[0]
        return self.location

    def get_line_number(self) -> int | None:
        """Extract line number from location."""
        if ":" in self.location:
            try:
                return int(self.location.split(":")[1])
            except (ValueError, IndexError):
                return None
        return None

    def get_relevant_traceback(self, max_lines: int = 15) -> list[str]:
        """Get most relevant traceback lines (last N lines)."""
        return (
            self.traceback[-max_lines:]
            if len(self.traceback) > max_lines
            else self.traceback
        )
```

**Rationale:**

- ✅ Strongly typed failure representation
- ✅ Easy to serialize/deserialize for AI agent consumption
- ✅ Helper methods for common operations
- ✅ Extensible for future enhancements (e.g., pytest-html integration)

#### 2.2 Regex-Based Failure Parser

**File:** `crackerjack/managers/test_manager.py`
**Location:** After `_extract_failure_lines` (line 729)

**New Method:**

```python
def _extract_structured_failures(self, output: str) -> list[TestFailure]:
    """Extract structured failure information from pytest output.

    This parser handles pytest's standard output format and extracts:
    - Test names and locations
    - Full tracebacks
    - Assertion errors
    - Captured output (stdout/stderr)
    - Duration (if available)

    Args:
        output: Raw pytest output text

    Returns:
        List of TestFailure objects
    """
    from crackerjack.models.test_models import TestFailure
    import re

    failures = []
    lines = output.split("\n")

    current_failure = None
    in_traceback = False
    in_captured = False
    capture_type = None

    for i, line in enumerate(lines):
        # Detect failure headers: "tests/test_foo.py::test_bar FAILED"
        failure_match = re.match(r"^(.+?)\s+(FAILED|ERROR)\s*(?:\[(.+?)\])?", line)
        if failure_match:
            # Save previous failure
            if current_failure:
                failures.append(current_failure)

            test_path, status, params = failure_match.groups()

            current_failure = TestFailure(
                test_name=test_path + (f"[{params}]" if params else ""),
                status=status,
                location=test_path,  # Will be refined when we see file:line
            )
            in_traceback = True
            in_captured = False
            continue

        if not current_failure:
            continue

        # Detect location: "tests/test_foo.py:42: AssertionError"
        location_match = re.match(r"^(.+?\.py):(\d+):\s*(.*)$", line)
        if location_match and in_traceback:
            file_path, line_num, error_type = location_match.groups()
            current_failure.location = f"{file_path}:{line_num}"
            if error_type:
                current_failure.short_summary = error_type
            continue

        # Detect assertion errors
        if "AssertionError:" in line or line.strip().startswith("E       assert "):
            assertion_text = line.strip().lstrip("E").strip()
            if current_failure.assertion:
                current_failure.assertion += "\n" + assertion_text
            else:
                current_failure.assertion = assertion_text
            continue

        # Detect captured output sections
        if "captured stdout" in line.lower():
            in_captured = True
            capture_type = "stdout"
            in_traceback = False
            continue
        elif "captured stderr" in line.lower():
            in_captured = True
            capture_type = "stderr"
            in_traceback = False
            continue

        # Collect traceback lines
        if in_traceback:
            # Traceback lines typically start with spaces or special markers
            if (
                line.startswith("    ")
                or line.startswith("\t")
                or line.startswith("E   ")
            ):
                current_failure.traceback.append(line)
            elif line.strip().startswith("=") or (
                i < len(lines) - 1 and "FAILED" in lines[i + 1]
            ):
                # End of traceback
                in_traceback = False

        # Collect captured output
        if in_captured and capture_type:
            if line.strip().startswith("=") or line.strip().startswith("_"):
                # End of captured section
                in_captured = False
                capture_type = None
            else:
                if capture_type == "stdout":
                    if current_failure.captured_stdout:
                        current_failure.captured_stdout += "\n" + line
                    else:
                        current_failure.captured_stdout = line
                elif capture_type == "stderr":
                    if current_failure.captured_stderr:
                        current_failure.captured_stderr += "\n" + line
                    else:
                        current_failure.captured_stderr = line

    # Save final failure
    if current_failure:
        failures.append(current_failure)

    return failures
```

**Rationale:**

- ✅ Handles pytest's standard output format
- ✅ State machine approach for multi-line parsing
- ✅ Captures all relevant failure context
- ✅ Robust against slight format variations

#### 2.3 Rich Table Renderer for Failures

**File:** `crackerjack/managers/test_manager.py`
**Location:** After `_render_failure_section`

**New Method:**

```python
def _render_structured_failure_panels(self, failures: list[TestFailure]) -> None:
    """Render failures as Rich panels with tables and syntax highlighting.

    Each failure is rendered in a panel containing:
    - Summary table (test name, location, status)
    - Assertion details (if present)
    - Syntax-highlighted traceback
    - Captured output (if any)

    Args:
        failures: List of TestFailure objects
    """
    from rich.panel import Panel
    from rich.table import Table
    from rich.syntax import Syntax
    from rich.console import Group
    from rich import box

    if not failures:
        return

    # Group failures by file for better organization
    failures_by_file: dict[str, list[TestFailure]] = {}
    for failure in failures:
        file_path = failure.get_file_path()
        if file_path not in failures_by_file:
            failures_by_file[file_path] = []
        failures_by_file[file_path].append(failure)

    # Render each file group
    for file_path, file_failures in failures_by_file.items():
        self.console.print(
            f"\n[bold red]📁 {file_path}[/bold red] ({len(file_failures)} failure(s))\n"
        )

        for i, failure in enumerate(file_failures, 1):
            # Create details table
            table = Table(
                show_header=False, box=box.SIMPLE, padding=(0, 1), border_style="red"
            )
            table.add_column("Key", style="cyan bold", width=12)
            table.add_column("Value", overflow="fold")

            # Add rows
            table.add_row("Test", f"[yellow]{failure.test_name}[/yellow]")
            table.add_row(
                "Location", f"[blue underline]{failure.location}[/blue underline]"
            )
            table.add_row("Status", f"[red bold]{failure.status}[/red bold]")

            if failure.duration:
                table.add_row("Duration", f"{failure.duration:.3f}s")

            # Components for panel
            components = [table]

            # Add assertion details
            if failure.assertion:
                components.append("")  # Spacer
                components.append("[bold red]Assertion Error:[/bold red]")

                # Syntax highlight the assertion
                assertion_syntax = Syntax(
                    failure.assertion,
                    "python",
                    theme="monokai",
                    line_numbers=False,
                    background_color="default",
                )
                components.append(assertion_syntax)

            # Add relevant traceback (last 15 lines)
            relevant_traceback = failure.get_relevant_traceback(max_lines=15)
            if relevant_traceback:
                components.append("")  # Spacer
                components.append("[bold red]Traceback:[/bold red]")

                traceback_text = "\n".join(relevant_traceback)
                traceback_syntax = Syntax(
                    traceback_text,
                    "python",
                    theme="monokai",
                    line_numbers=False,
                    word_wrap=True,
                    background_color="default",
                )
                components.append(traceback_syntax)

            # Add captured output if present
            if failure.captured_stdout:
                components.append("")  # Spacer
                components.append("[bold yellow]Captured stdout:[/bold yellow]")
                components.append(f"[dim]{failure.captured_stdout}[/dim]")

            if failure.captured_stderr:
                components.append("")  # Spacer
                components.append("[bold yellow]Captured stderr:[/bold yellow]")
                components.append(f"[dim]{failure.captured_stderr}[/dim]")

            # Create grouped content
            group = Group(*components)

            # Render panel
            panel = Panel(
                group,
                title=f"[bold red]❌ Failure {i}/{len(file_failures)}[/bold red]",
                border_style="red",
                width=get_console_width(),
                padding=(1, 2),
            )

            self.console.print(panel)
```

**Rationale:**

- ✅ File-based grouping improves scanability
- ✅ Tables provide structured information
- ✅ Syntax highlighting for Python code
- ✅ Shows captured output (stdout/stderr)
- ✅ Clickable file links (if terminal supports)

#### 2.4 Update Rendering Logic

**File:** `crackerjack/managers/test_manager.py`
**Location:** Modify `_render_formatted_output` (Phase 1 method)

**Enhanced Version:**

```python
def _render_formatted_output(self, output: str, options: OptionsProtocol) -> None:
    """Render test output with Rich formatting and sections.

    Phase 2: Uses structured failure parser when available.

    Args:
        output: Raw pytest output text
        options: Test options (for verbosity level)
    """
    from rich.panel import Panel

    # Try structured parsing first (Phase 2)
    try:
        failures = self._extract_structured_failures(output)
        if failures:
            self.console.print(
                "\n[bold red]═══════════════════════════════════════════[/bold red]"
            )
            self.console.print("[bold red]Detailed Failure Analysis[/bold red]")
            self.console.print(
                "[bold red]═══════════════════════════════════════════[/bold red]"
            )

            self._render_structured_failure_panels(failures)

            # Still show summary section
            sections = self._split_output_sections(output)
            for section_type, section_content in sections:
                if section_type == "summary":
                    panel = Panel(
                        section_content.strip(),
                        title="[bold yellow]📋 Test Summary[/bold yellow]",
                        border_style="yellow",
                        width=get_console_width(),
                    )
                    self.console.print(panel)
                elif section_type == "footer":
                    self.console.print(f"\n[cyan]{section_content.strip()}[/cyan]\n")

            return

    except Exception as e:
        # Fallback to Phase 1 rendering if parsing fails
        self.console.print(
            f"[dim yellow]⚠️  Structured parsing failed: {e}[/dim yellow]"
        )
        self.console.print(
            "[dim yellow]Falling back to standard formatting...[/dim yellow]\n"
        )

    # Fallback: Phase 1 section-based rendering
    sections = self._split_output_sections(output)

    for section_type, section_content in sections:
        if not section_content.strip():
            continue

        if section_type == "failure":
            self._render_failure_section(section_content)
        elif section_type == "summary":
            panel = Panel(
                section_content.strip(),
                title="[bold yellow]📋 Test Summary[/bold yellow]",
                border_style="yellow",
                width=get_console_width(),
            )
            self.console.print(panel)
        elif section_type == "footer":
            self.console.print(f"\n[cyan]{section_content.strip()}[/cyan]\n")
        else:
            if options.verbose or getattr(options, "ai_debug", False):
                self.console.print(f"[dim]{section_content}[/dim]")
```

**Rationale:**

- ✅ Progressive enhancement (try structured first, fallback to simple)
- ✅ Graceful degradation on parsing errors
- ✅ Shows warning if fallback is used (helps debug parser issues)

### Testing Plan (Phase 2)

1. **Test with various failure types:**

   ```python
   # tests/test_phase2_scenarios.py


   def test_simple_assertion():
       """Test simple assertion failure."""
       assert 1 == 2


   def test_assertion_with_message():
       """Test assertion with custom message."""
       assert False, "This should always fail with a message"


   def test_comparison_assertion():
       """Test comparison that shows diff."""
       expected = {"a": 1, "b": 2, "c": 3}
       actual = {"a": 1, "b": 99, "c": 3}
       assert expected == actual


   def test_exception():
       """Test uncaught exception."""
       raise ValueError("Intentional error")


   def test_with_stdout():
       """Test with captured stdout."""
       print("Debug output 1")
       print("Debug output 2")
       assert False


   def test_import_error():
       """Test import error."""
       import nonexistent_module


   def test_nested_exception():
       """Test nested exception."""

       def inner():
           raise RuntimeError("Inner error")

       def outer():
           inner()

       outer()
   ```

1. **Run with verbose mode:**

   ```bash
   python -m crackerjack -s -t -v
   ```

1. **Verify output shows:**

   - ✅ Failures grouped by file
   - ✅ Rich tables with test details
   - ✅ Syntax-highlighted tracebacks
   - ✅ Captured stdout/stderr
   - ✅ Clear visual hierarchy

1. **Test parser edge cases:**

   ```bash
   # Parametrized tests
   # Multi-line assertions
   # Unicode in output
   # Very long tracebacks (>100 lines)
   ```

### Acceptance Criteria (Phase 2)

- [ ] Structured parser extracts all failure components
- [ ] Failures grouped by file for organization
- [ ] Rich tables show test metadata clearly
- [ ] Syntax highlighting works for tracebacks
- [ ] Captured output (stdout/stderr) displayed
- [ ] Parser handles edge cases gracefully
- [ ] Fallback to Phase 1 rendering works
- [ ] No performance degradation (\<100ms overhead)
- [ ] Tests pass after implementation

______________________________________________________________________

## Configuration

### New Settings (Optional)

**File:** `crackerjack/config/settings.py`

```python
class TestingSettings(BaseSettings):
    # ... existing settings ...

    # Enhanced error reporting settings
    enhanced_error_reporting: bool = True
    """Enable structured failure parsing and Rich formatting."""

    max_traceback_lines: int = 15
    """Maximum traceback lines to show per failure."""

    group_failures_by_file: bool = True
    """Group test failures by file for better organization."""

    show_captured_output: bool = True
    """Show captured stdout/stderr in failure reports."""
```

### Environment Variables

```bash
# Disable enhanced reporting (fallback to raw output)
export CRACKERJACK_ENHANCED_REPORTING=false

# Increase traceback detail
export CRACKERJACK_MAX_TRACEBACK_LINES=25
```

______________________________________________________________________

## Rollout Plan

### Stage 1: Phase 1 Implementation (Days 1-2)

- [ ] Implement verbosity enhancements
- [ ] Add section splitter
- [ ] Create Rich formatter
- [ ] Update failure handler
- [ ] Test with manual failures
- [ ] Commit and push

### Stage 2: Phase 2 Implementation (Days 3-4)

- [ ] Create test models
- [ ] Implement structured parser
- [ ] Create panel renderer
- [ ] Integrate with Phase 1
- [ ] Test with complex scenarios
- [ ] Commit and push

### Stage 3: Documentation & Polish (Day 5)

- [ ] Update CLAUDE.md with new features
- [ ] Add docstrings to all new methods
- [ ] Create user documentation
- [ ] Add examples to README
- [ ] Final testing pass

______________________________________________________________________

## Success Metrics

### Quantitative

- **Coverage:** No reduction in test coverage
- **Performance:** \<100ms overhead for error formatting
- **Reliability:** Parser handles 95%+ of pytest output formats

### Qualitative

- **Readability:** Failures easier to understand at a glance
- **Actionability:** Clear file/line references for quick fixes
- **Professionalism:** Output looks polished and well-structured

______________________________________________________________________

## Risks & Mitigations

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Regex parsing breaks on pytest updates | Medium | Medium | Use pytest's `-vv` output which is more stable; add fallback to Phase 1 |
| Rich formatting breaks in some terminals | Low | Low | Detect Rich support; fallback to plain text |
| Performance degradation with many failures | Low | Medium | Limit max failures shown; async rendering if needed |
| Complexity increases maintenance burden | Low | Low | Comprehensive docstrings; unit tests for parser |

______________________________________________________________________

## Future Enhancements (Post-Phase 2)

- [ ] **Interactive failure navigation:** Arrow keys to navigate between failures
- [ ] **Failure filtering:** Show only specific failure types
- [ ] **AI-powered suggestions:** Integrate with agent system for fix recommendations
- [ ] **HTML report generation:** Export failures to interactive HTML
- [ ] **Pytest plugin integration:** Deeper integration with pytest internals
- [ ] **Diff visualization:** Show expected vs actual diffs for comparison failures

______________________________________________________________________

## Progress Tracking

### Phase 1 Checklist

- [x] ~~Create implementation plan document~~
- [ ] Implement `_add_verbosity_options` enhancements
- [ ] Implement `_split_output_sections` method
- [ ] Implement `_render_formatted_output` method
- [ ] Implement `_render_failure_section` method
- [ ] Update `_handle_test_failure` to use new rendering
- [ ] Manual testing with failing tests
- [ ] Verify no regressions in non-verbose mode
- [ ] Code review and refinement
- [ ] Commit Phase 1 changes

### Phase 2 Checklist

- [ ] Create `models/test_models.py` with TestFailure dataclass
- [ ] Implement `_extract_structured_failures` parser
- [ ] Implement `_render_structured_failure_panels` method
- [ ] Enhance `_render_formatted_output` with structured parsing
- [ ] Create comprehensive test scenarios
- [ ] Test parser with edge cases
- [ ] Verify fallback behavior works
- [ ] Performance testing
- [ ] Code review and refinement
- [ ] Commit Phase 2 changes

### Documentation & Polish Checklist

- [ ] Update CLAUDE.md
- [ ] Add comprehensive docstrings
- [ ] Create user documentation
- [ ] Add examples to README
- [ ] Final integration testing
- [ ] Mark implementation plan as complete

______________________________________________________________________

## Notes

- **Design Decision:** Hybrid approach provides immediate value (Phase 1) while enabling progressive enhancement (Phase 2)
- **Philosophy:** "Make it work (Phase 1), then make it better (Phase 2)"
- **Backward Compatibility:** Non-verbose mode unchanged; only verbose mode gets enhancements
- **AI Integration Ready:** Structured failures can be easily consumed by AI agents for automated fixing

______________________________________________________________________

**Last Updated:** 2025-11-20
**Next Review:** After Phase 1 completion
