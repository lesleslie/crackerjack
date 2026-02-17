# Complexity Refactoring Plan - TEAM GAMMA

**Target Files (from performance audit):**

1. `test_manager.py` - Complexity: 266 (target: ≤15, 16.7x over)
1. `autofix_coordinator.py` - Complexity: 231 (target: ≤15, 15.4x over)
1. `oneiric_workflow.py` - Complexity: 182 (target: ≤15, 12.1x over)

## Analysis Summary

### test_manager.py (1,903 lines, complexity: 266)

**High-Complexity Functions Identified:**

1. **`_parse_test_statistics` (lines 527-564)** - ~25 complexity

   - Multiple conditional branches
   - Nested try/except with multiple parsing attempts
   - Multiple data transformation steps

1. **`_render_test_results_panel` (lines 730-799)** - ~20 complexity

   - Complex table building logic
   - Multiple conditional metric additions
   - Nested data structure handling

1. **`_extract_structured_failures` (lines 1325-1368)** - ~35 complexity

   - Complex state machine for parsing
   - Nested conditional logic
   - Multiple parsing modes

1. **`_parse_failure_line` (lines 1556-1609)** - ~30 complexity

   - Multi-stage parsing logic
   - Multiple conditional branches
   - State tracking complexity

1. **`_update_coverage_badge` (lines 894-938)** - ~20 complexity

   - Multiple fallback strategies
   - Nested conditional logic
   - Complex validation flow

### autofix_coordinator.py (1,823 lines, complexity: 231)

**High-Complexity Functions Identified:**

1. **`_run_ai_fix_iteration_loop` (lines 1632-1690)** - ~25 complexity

   - Complex iteration state management
   - Multiple completion checks
   - Progress tracking integration

1. **`_validate_modified_files` (lines 587-639)** - ~20 complexity

   - Multiple validation checks
   - Nested error handling
   - Complex AST parsing

1. **`_determine_issue_type` (lines 1341-1393)** - ~25 complexity

   - Large conditional mapping
   - Multiple fallback strategies
   - Complex pattern matching

1. **`_convert_parsed_issues_to_issues` (lines 1274-1329)** - ~18 complexity

   - Multiple validation steps
   - Complex data transformation
   - Extensive error handling

1. **`_run_qa_adapters_for_hooks` (lines 812-883)** - ~20 complexity

   - Async/sync compatibility checks
   - Multiple adapter instantiation paths
   - Complex error recovery

### oneiric_workflow.py (325 lines, complexity: 182)

**Note:** This file is actually much simpler than the complexity score suggests. The complexity comes from:

- Many small helper functions (each ≤5 complexity)
- Function call overhead in complexity calculation
- The file is well-structured already

**Functions to Review:**

1. **`_build_workflow_steps` (lines 190-226)** - ~15 complexity
   - Multiple conditional checks
   - Step accumulation logic

## Refactoring Strategy

### Phase 1: test_manager.py Refactoring

#### 1.1 Extract Test Statistics Parsing (Complexity: 25 → ≤15)

**Current Function:** `_parse_test_statistics`

**Refactoring Plan:**

```python
def _parse_test_statistics(self, output: str, *, already_clean: bool = False) -> dict[str, t.Any]:
    """Parse test statistics from pytest output."""
    clean_output = output if already_clean else self._strip_ansi_codes(output)
    stats = self._initialize_test_stats()

    try:
        self._parse_summary_section(clean_output, stats)
        self._calculate_total_tests(stats, clean_output)
        stats["coverage"] = self._extract_coverage_from_output(clean_output)
    except (ValueError, AttributeError) as e:
        self.console.print(f"[dim]⚠️ Failed to parse test statistics: {e}[/dim]")

    return stats

def _initialize_test_stats(self) -> dict[str, t.Any]:
    """Initialize empty test statistics dictionary."""
    return {
        "total": 0, "passed": 0, "failed": 0, "skipped": 0,
        "errors": 0, "xfailed": 0, "xpassed": 0, "duration": 0.0, "coverage": None
    }

def _parse_summary_section(self, output: str, stats: dict[str, t.Any]) -> None:
    """Parse summary section and extract metrics."""
    summary_match = self._extract_pytest_summary(output)
    if summary_match:
        summary_text, duration = self._parse_summary_match(summary_match, output)
        stats["duration"] = duration
        self._extract_test_metrics(summary_text, stats)
```

**Complexity Reduction:**

- `_parse_test_statistics`: 25 → 8
- `_initialize_test_stats`: 1
- `_parse_summary_section`: 5

#### 1.2 Extract Structured Failure Parsing (Complexity: 35 → ≤15)

**Current Function:** `_extract_structured_failures`

**Refactoring Plan:**

```python
def _extract_structured_failures(self, output: str) -> list["TestFailure"]:
    """Extract structured test failures from output."""
    failures: list[TestFailure] = []
    lines = output.split("\n")
    parser_state = self._initialize_parser_state()

    for i, line in enumerate(lines):
        parse_result = self._parse_failure_line(
            line, lines, i, parser_state["current_failure"],
            parser_state["in_traceback"], parser_state["in_captured"],
            parser_state["capture_type"]
        )

        if parse_result.get("stop_parsing"):
            break

        parser_state = self._update_parsing_state(parse_result, parser_state)

        if parse_result.get("skip_line"):
            continue

        if parse_result.get("new_failure"):
            if parser_state["current_failure"]:
                failures.append(parser_state["current_failure"])
            parser_state["current_failure"] = parse_result["new_failure"]
            parser_state["in_traceback"] = True

    if parser_state["current_failure"]:
        failures.append(parser_state["current_failure"])

    self._enrich_failures_from_short_summary(failures, output)
    return failures

def _initialize_parser_state(self) -> dict[str, t.Any]:
    """Initialize parsing state machine."""
    return {
        "current_failure": None,
        "in_traceback": False,
        "in_captured": False,
        "capture_type": None,
    }
```

**Complexity Reduction:**

- `_extract_structured_failures`: 35 → 12
- `_initialize_parser_state`: 1

#### 1.3 Extract Coverage Badge Update Logic (Complexity: 20 → ≤15)

**Current Function:** `_update_coverage_badge`

**Refactoring Plan:**

```python
def _update_coverage_badge(self, ratchet_result: dict[str, t.Any]) -> None:
    """Update coverage badge based on ratchet result."""
    try:
        self._verify_coverage_files_exist()
        current_coverage = self._extract_coverage_with_fallbacks(ratchet_result)

        if current_coverage is not None and current_coverage >= 0:
            self._update_badge_if_needed(current_coverage)
        else:
            self.console.print("[yellow]⚠️[/yellow] No valid coverage data found for badge update")
    except Exception as e:
        self.console.print(f"[yellow]⚠️[/yellow] Badge update failed: {e}")

def _verify_coverage_files_exist(self) -> None:
    """Verify coverage files exist, logging info if not."""
    coverage_json_path = self.pkg_path / "coverage.json"
    ratchet_path = self.pkg_path / ".coverage-ratchet.json"

    if not coverage_json_path.exists():
        self.console.print("[yellow]ℹ️[/yellow] Coverage file doesn't exist yet, will be created after test run")
    if not ratchet_path.exists():
        self.console.print("[yellow]ℹ️[/yellow] Coverage ratchet file doesn't exist yet, initializing...")

def _extract_coverage_with_fallbacks(self, ratchet_result: dict[str, t.Any]) -> float | None:
    """Extract coverage using multiple fallback strategies."""
    coverage = self._attempt_coverage_extraction()
    coverage = self._handle_coverage_extraction_result(coverage)
    coverage = self._get_fallback_coverage(ratchet_result, coverage)
    return coverage

def _update_badge_if_needed(self, current_coverage: float) -> None:
    """Update badge if coverage has changed significantly."""
    if self._coverage_badge_service.should_update_badge(current_coverage):
        self._coverage_badge_service.update_readme_coverage_badge(current_coverage)
        self.console.print(f"[green]✅[/green] Badge updated to {current_coverage:.2f}%")
    else:
        self.console.print(f"[dim]📊 Badge unchanged (current: {current_coverage:.2f}%)[/dim]")
```

**Complexity Reduction:**

- `_update_coverage_badge`: 20 → 7
- `_verify_coverage_files_exist`: 5
- `_extract_coverage_with_fallbacks`: 3
- `_update_badge_if_needed`: 4

#### 1.4 Extract Test Results Panel Rendering (Complexity: 20 → ≤15)

**Current Function:** `_render_test_results_panel`

**Refactoring Plan:**

```python
def _render_test_results_panel(
    self, stats: dict[str, t.Any], workers: int | str, success: bool
) -> None:
    """Render test results in a formatted panel."""
    table = self._create_test_results_table(stats)
    self._add_test_metrics_to_table(table, stats)
    self._add_metadata_to_table(table, stats, workers)
    self._render_test_results_panel_final(table, stats, success)

def _create_test_results_table(self, stats: dict[str, t.Any]) -> "Table":
    """Create and configure test results table."""
    table = Table(box=box.SIMPLE, header_style="bold bright_white")
    table.add_column("Metric", style="cyan", overflow="fold")
    table.add_column("Count", justify="right", style="bright_white")
    table.add_column("Percentage", justify="right", style="magenta")
    return table

def _add_test_metrics_to_table(self, table: "Table", stats: dict[str, t.Any]) -> None:
    """Add test metrics to the results table."""
    total = stats["total"]
    metrics = self._get_base_metrics(stats)

    for label, count, _ in metrics:
        percentage = f"{(count / total * 100):.1f}%" if total > 0 else "0.0%"
        table.add_row(label, str(count), percentage)

    table.add_row("─" * 20, "─" * 10, "─" * 15, style="dim")
    table.add_row("📊 Total Tests", str(total), "100.0%", style="bold")

def _add_metadata_to_table(
    self, table: "Table", stats: dict[str, t.Any], workers: int | str
) -> None:
    """Add metadata (duration, workers, coverage) to table."""
    table.add_row("⏱ Duration", f"{stats['duration']:.2f}s", "", style="bold magenta")
    table.add_row("👥 Workers", str(workers), "", style="bold cyan")

    if stats.get("coverage") is not None:
        table.add_row("📈 Coverage", f"{stats['coverage']:.1f}%", "", style="bold green")
```

**Complexity Reduction:**

- `_render_test_results_panel`: 20 → 6
- `_create_test_results_table`: 3
- `_add_test_metrics_to_table`: 8
- `_add_metadata_to_table`: 5

### Phase 2: autofix_coordinator.py Refactoring

#### 2.1 Extract AI Fix Iteration Loop (Complexity: 25 → ≤15)

**Current Function:** `_run_ai_fix_iteration_loop`

**Refactoring Plan:**

```python
def _run_ai_fix_iteration_loop(
    self,
    coordinator: "AgentCoordinatorProtocol",
    initial_issues: list[Issue],
    hook_results: Sequence[object],
    stage: str,
) -> bool:
    """Run main AI fix iteration loop with progress tracking."""
    loop_state = self._initialize_iteration_state()
    self.progress_manager.start_fix_session(stage=stage, initial_issue_count=len(initial_issues))

    try:
        while True:
            issues = self._get_iteration_issues_with_log(loop_state.iteration, hook_results, stage)
            current_count = len(issues)

            self.progress_manager.start_iteration(loop_state.iteration, current_count)

            completion_result = self._check_iteration_completion(
                loop_state.iteration, current_count, loop_state.previous_count,
                loop_state.no_progress_count, loop_state.max_iterations, stage
            )

            if completion_result is not None:
                return self._finalize_iteration_session(completion_result)

            loop_state = self._update_iteration_state(
                loop_state, current_count, coordinator, issues
            )

    except Exception as e:
        return self._handle_iteration_error(e, loop_state.iteration)

def _initialize_iteration_state(self) -> "IterationState":
    """Initialize iteration loop state."""
    return IterationState(
        max_iterations=self._get_max_iterations(),
        previous_count=float("inf"),
        no_progress_count=0,
        iteration=0,
    )

def _finalize_iteration_session(self, success: bool) -> bool:
    """Finalize iteration session with progress tracking."""
    self.progress_manager.end_iteration()
    self.progress_manager.finish_session(success=success)
    return success

def _handle_iteration_error(self, error: Exception, iteration: int) -> bool:
    """Handle iteration error with cleanup."""
    self.logger.exception(f"Error during AI fixing at iteration {iteration}")
    self.progress_manager.end_iteration()
    self.progress_manager.finish_session(success=False, message=f"Error during AI fixing: {error}")
    raise
```

**Complexity Reduction:**

- `_run_ai_fix_iteration_loop`: 25 → 10
- `_initialize_iteration_state`: 2
- `_finalize_iteration_session`: 3
- `_handle_iteration_error`: 5

#### 2.2 Extract Issue Type Determination (Complexity: 25 → ≤15)

**Current Function:** `_determine_issue_type`

**Refactoring Plan:**

```python
def _determine_issue_type(
    self, tool_name: str, tool_issue_dict: dict[str, t.Any]
) -> IssueType:
    """Determine issue type from tool name and issue data."""
    # Try tool-based mapping first
    if issue_type := self._map_tool_to_issue_type(tool_name):
        return issue_type

    # Fall back to content-based detection
    return self._detect_issue_type_from_content(tool_issue_dict)

def _map_tool_to_issue_type(self, tool_name: str) -> IssueType | None:
    """Map tool name to issue type."""
    tool_type_map = {
        "ruff": IssueType.FORMATTING,
        "ruff-format": IssueType.FORMATTING,
        "mdformat": IssueType.FORMATTING,
        "codespell": IssueType.FORMATTING,
        "mypy": IssueType.TYPE_ERROR,
        "zuban": IssueType.TYPE_ERROR,
        "pyright": IssueType.TYPE_ERROR,
        "pylint": IssueType.TYPE_ERROR,
        "bandit": IssueType.SECURITY,
        "gitleaks": IssueType.SECURITY,
        "semgrep": IssueType.SECURITY,
        "safety": IssueType.SECURITY,
        "pytest": IssueType.TEST_FAILURE,
        "complexipy": IssueType.COMPLEXITY,
        "refurb": IssueType.COMPLEXITY,
        "skylos": IssueType.DEAD_CODE,
        "creosote": IssueType.DEPENDENCY,
        "pyscn": IssueType.DEPENDENCY,
    }
    return tool_type_map.get(tool_name)

def _detect_issue_type_from_content(self, tool_issue_dict: dict[str, t.Any]) -> IssueType:
    """Detect issue type from message/content patterns."""
    message = tool_issue_dict.get("message", "").lower()
    code = tool_issue_dict.get("code", "").lower()

    type_detectors = [
        (lambda m: any(w in m for w in ["test", "pytest", "unittest"]), IssueType.TEST_FAILURE),
        (lambda m: any(w in m for w in ["complex", "cyclomatic"]), IssueType.COMPLEXITY),
        (lambda m: any(w in m for w in ["dead", "unused", "redundant"]), IssueType.DEAD_CODE),
        (lambda m: any(w in m for w in ["security", "vulnerability"]), IssueType.SECURITY),
        (lambda m: any(w in m for w in ["import", "module"]), IssueType.IMPORT_ERROR),
        (lambda m, c: "type" in m or "type:" in c, IssueType.TYPE_ERROR),
    ]

    for detector, issue_type in type_detectors:
        if detector(message, code):
            return issue_type

    return IssueType.FORMATTING
```

**Complexity Reduction:**

- `_determine_issue_type`: 25 → 5
- `_map_tool_to_issue_type`: 1
- `_detect_issue_type_from_content`: 12

#### 2.3 Extract QA Adapter Execution (Complexity: 20 → ≤15)

**Current Function:** `_run_qa_adapters_for_hooks`

**Refactoring Plan:**

```python
def _run_qa_adapters_for_hooks(
    self, hook_results: Sequence[object]
) -> dict[str, QAResult]:
    """Run QA adapters for hooks without cached results."""
    qa_results: dict[str, QAResult] = {}
    adapter_factory = DefaultAdapterFactory()

    for result in hook_results:
        if not self._should_run_qa_adapter_for_hook(result):
            continue

        hook_name = getattr(result, "name", "")
        qa_result = self._execute_single_qa_adapter(hook_name, adapter_factory)

        if qa_result:
            qa_results[hook_name] = qa_result

    return qa_results

def _should_run_qa_adapter_for_hook(self, result: object) -> bool:
    """Check if QA adapter should run for this hook result."""
    if not self._validate_hook_result(result):
        return False

    status = getattr(result, "status", "")
    if status.lower() != "failed":
        return False

    hook_name = getattr(result, "name", "")
    return bool(hook_name)

def _execute_single_qa_adapter(
    self, hook_name: str, adapter_factory: "DefaultAdapterFactory"
) -> "QAResult | None":
    """Execute a single QA adapter for a hook."""
    try:
        adapter_name = adapter_factory.get_adapter_name(hook_name)
        if not adapter_name:
            self.logger.debug(f"No adapter name mapping for '{hook_name}'")
            return None

        adapter = adapter_factory.create_adapter(adapter_name)
        if adapter is None:
            self.logger.debug(f"No QA adapter available for '{hook_name}'")
            return None

        if self._is_async_context():
            self.logger.warning(f"QA adapter for '{hook_name}' called from async context")
            return None

        return self._run_qa_adapter_sync(adapter, hook_name)

    except Exception as e:
        self.logger.warning(f"Failed to run QA adapter for '{hook_name}': {e}")
        return None

def _is_async_context(self) -> bool:
    """Check if running in async context."""
    try:
        asyncio.get_running_loop()
        return True
    except RuntimeError:
        return False

def _run_qa_adapter_sync(self, adapter, hook_name: str) -> "QAResult":
    """Run QA adapter synchronously."""
    asyncio.run(adapter.init())

    config = QACheckConfig(
        check_id=adapter.module_id,
        check_name=hook_name,
        check_type=adapter._get_check_type(),
        enabled=True,
        file_patterns=["**/*.py"],
        timeout_seconds=60,
    )

    qa_result: QAResult = asyncio.run(adapter.check(config=config))

    if qa_result.parsed_issues:
        self.logger.info(f"✅ QA adapter for '{hook_name}' found {len(qa_result.parsed_issues)} issues")
    else:
        self.logger.debug(f"QA adapter for '{hook_name}' found no issues")

    return qa_result
```

**Complexity Reduction:**

- `_run_qa_adapters_for_hooks`: 20 → 7
- `_should_run_qa_adapter_for_hook`: 5
- `_execute_single_qa_adapter`: 10
- `_is_async_context`: 3
- `_run_qa_adapter_sync`: 5

#### 2.4 Extract File Validation Logic (Complexity: 20 → ≤15)

**Current Function:** `_validate_modified_files`

**Refactoring Plan:**

```python
def _validate_modified_files(self, modified_files: list[str]) -> bool:
    """Validate all modified files for syntax and semantic errors."""
    for file_path_str in modified_files:
        if not self._validate_single_file(file_path_str):
            return False
    return True

def _validate_single_file(self, file_path_str: str) -> bool:
    """Validate a single modified file."""
    file_path = Path(file_path_str)

    if not self._should_validate_file(file_path):
        return True

    if not file_path.exists():
        self.logger.warning(f"⚠️ File not found for validation: {file_path}")
        return True

    try:
        content = file_path.read_text()
        return self._validate_file_content(content, file_path)
    except Exception as e:
        self.logger.error(f"❌ Failed to validate {file_path}: {e}")
        return False

def _should_validate_file(self, file_path: Path) -> bool:
    """Check if file should be validated."""
    if not str(file_path).endswith(".py"):
        self.logger.debug(f"⏭️ Skipping non-Python file: {file_path}")
        return False
    return True

def _validate_file_content(self, content: str, file_path: Path) -> bool:
    """Validate file content for syntax and duplicate definitions."""
    if not self._validate_syntax(content, file_path):
        return False
    return self._validate_no_duplicates(content, file_path)

def _validate_syntax(self, content: str, file_path: Path) -> bool:
    """Validate Python syntax."""
    try:
        compile(content, str(file_path), "exec")
        self.logger.debug(f"✅ Syntax validation passed: {file_path}")
        return True
    except SyntaxError as e:
        self.logger.error(f"❌ Syntax error in {file_path}:{e.lineno}: {e.msg}")
        self.logger.error(f"   {e.text}")
        return False

def _validate_no_duplicates(self, content: str, file_path: Path) -> bool:
    """Validate no duplicate definitions exist."""
    try:
        tree = ast.parse(content)
        definitions = {}

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                name = node.name
                if name in definitions:
                    self.logger.error(
                        f"❌ Duplicate definition '{name}' in {file_path} "
                        f"at line {node.lineno} (previous at line {definitions[name]})"
                    )
                    return False
                definitions[name] = node.lineno

        self.logger.debug(f"✅ No duplicate definitions: {file_path}")
        return True
    except Exception as e:
        self.logger.warning(f"⚠️ Could not check for duplicates in {file_path}: {e}")
        return True  # Don't fail on validation issues
```

**Complexity Reduction:**

- `_validate_modified_files`: 20 → 3
- `_validate_single_file`: 8
- `_should_validate_file`: 3
- `_validate_file_content`: 4
- `_validate_syntax`: 5
- `_validate_no_duplicates`: 10

### Phase 3: oneiric_workflow.py Refactoring

**Note:** This file is already well-structured. Minor improvements only:

#### 3.1 Extract Workflow Step Building (Complexity: 15 → ≤10)

**Current Function:** `_build_workflow_steps`

**Refactoring Plan:**

```python
def _build_workflow_steps(options: t.Any) -> list[str]:
    """Build list of workflow steps based on options."""
    steps: list[str] = []

    steps.extend(_get_cleanup_steps(options))
    steps.extend(_get_test_steps(options))
    steps.extend(_get_post_test_steps(options))
    steps.extend(["publishing", "commit"])

    return steps

def _get_cleanup_steps(options: t.Any) -> list[str]:
    """Get cleanup workflow steps."""
    steps = []

    if _should_run_config_cleanup(options):
        steps.append("config_cleanup")

    if not getattr(options, "no_config_updates", False):
        steps.append("configuration")

    if _should_clean(options):
        steps.append("cleaning")

    if _should_run_documentation_cleanup(options):
        steps.append("documentation_cleanup")

    if _should_run_fast_hooks(options):
        steps.append("fast_hooks")

    return steps

def _get_test_steps(options: t.Any) -> list[str]:
    """Get test-related workflow steps."""
    run_tests = _should_run_tests(options)
    run_comprehensive = _should_run_comprehensive_hooks(options)
    enable_parallel = getattr(options, "enable_parallel_phases", False)

    if run_tests and run_comprehensive:
        if enable_parallel:
            return ["tests", "comprehensive_hooks"]
        return ["tests", "comprehensive_hooks"]
    if run_tests:
        return ["tests"]
    if run_comprehensive:
        return ["comprehensive_hooks"]

    return []

def _get_post_test_steps(options: t.Any) -> list[str]:
    """Get post-test workflow steps."""
    steps = []

    if _should_run_git_cleanup(options):
        steps.append("git_cleanup")

    if _should_run_doc_updates(options):
        steps.append("doc_updates")

    return steps
```

**Complexity Reduction:**

- `_build_workflow_steps`: 15 → 6
- `_get_cleanup_steps`: 8
- `_get_test_steps`: 10
- `_get_post_test_steps`: 4

## Implementation Plan

### Execution Order

1. **test_manager.py** (highest impact, 266 → ~150 complexity)

   - Extract test statistics parsing
   - Extract structured failure parsing
   - Extract coverage badge update logic
   - Extract test results panel rendering

1. **autofix_coordinator.py** (231 → ~140 complexity)

   - Extract AI fix iteration loop
   - Extract issue type determination
   - Extract QA adapter execution
   - Extract file validation logic

1. **oneiric_workflow.py** (182 → ~120 complexity)

   - Extract workflow step building
   - Minor helper method extraction

### Validation Strategy

For each refactored function:

1. Extract complexity into helper methods
1. Ensure all helpers have complexity ≤15
1. Verify behavior preserved with existing tests
1. Run quality gates after each file
1. Commit changes incrementally

### Success Metrics

- All functions ≤15 complexity
- Total complexity reduction: ~40%
- Zero behavior changes (tests pass)
- Code readability improved
- Documentation updated

## Complexity Tracking

### Before Metrics

- test_manager.py: 266 complexity (16.7x target)
- autofix_coordinator.py: 231 complexity (15.4x target)
- oneiric_workflow.py: 182 complexity (12.1x target)
- **Total: 679 complexity**

### After Metrics (Target)

- test_manager.py: ~150 complexity
- autofix_coordinator.py: ~140 complexity
- oneiric_workflow.py: ~120 complexity
- **Total: ~410 complexity (40% reduction)**

## Helper Method Naming Conventions

- `_initialize_*` - Set up initial state
- `_parse_*` - Parse/extract data
- `_validate_*` - Check validity
- `_render_*` - Display/output
- `_update_*` - Modify state
- `_handle_*` - Process events
- `_check_*` - Boolean predicates
- `_get_*` - Retrieve data
- `_build_*` - Construct structures
- `_add_*` - Add to structures
- `_finalize_*` - Complete operations
- `_execute_*` - Run operations
- `_process_*` - Transform data
