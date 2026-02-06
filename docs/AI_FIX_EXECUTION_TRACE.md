# AI-Fix Execution Flow Analysis

## Investigation Summary

**Command**: `python -m crackerjack run --comp --ai-fix`
**Issue**: Comprehensive hooks complete with 14 issues, AI-fix achieves 0% reduction
**Root Cause**: Format specifier error during workflow execution

## Complete Execution Flow

### 1. Entry Point: CLI Handler
**File**: `/Users/les/Projects/crackerjack/crackerjack/__main__.py`

```python
@app.command()
def run(
    ai_fix: bool = CLI_OPTIONS["ai_fix"],  # Line 129
    comp: bool = CLI_OPTIONS["comp"],       # Line 154
    # ... other options
):
    settings = load_settings(CrackerjackSettings)
    options = _create_and_configure_options(locals())  # Line 238
    options = _setup_ai_options(locals(), options)      # Line 239

    # Sets environment variables:
    # - AI_AGENT=1
    # - AI_AGENT_DEBUG=1 (if debug)
    # - AI_AGENT_VERBOSE=1 (if debug)

    _execute_workflow_mode(options, job_id=job_id)      # Line 245
```

**Key Points**:
- `ai_fix=True` and `comp=True` flags are captured
- Environment variables set for AI agent mode
- Options object created with all flags

---

### 2. Workflow Mode Selection
**File**: `/Users/les/Projects/crackerjack/crackerjack/cli/facade.py`

```python
class CrackerjackCLIFacade:
    def process(self, options: OptionsProtocol) -> None:
        pipeline = WorkflowPipeline(console=self.console, pkg_path=self.pkg_path)
        success = pipeline.run_complete_workflow_sync(options)  # Line 69
```

**Flow**:
1. Create `WorkflowPipeline` with console and package path
2. Call `run_complete_workflow_sync(options)` with the Options object

---

### 3. Pipeline Orchestration
**File**: `/Users/les/Projects/crackerjack/crackerjack/core/workflow_orchestrator.py`

```python
class WorkflowPipeline:
    def run_complete_workflow_sync(self, options: t.Any) -> bool:
        return asyncio.run(self.run_complete_workflow(options))

    async def run_complete_workflow(self, options: t.Any) -> bool:
        self._initialize_workflow_session(options)

        runtime = build_oneiric_runtime()  # Creates Oneiric DAG
        register_crackerjack_workflow(
            runtime,
            phases=self.phases,
            options=_adapt_options(options),
        )

        result = await runtime.workflow_bridge.execute_dag(
            "crackerjack",
            context={"pkg_path": str(self.pkg_path)},
        )
        return _workflow_result_success(result)
```

**Flow**:
1. Build Oneiric runtime (DAG-based workflow engine)
2. Register crackerjack workflow with phases
3. Execute DAG asynchronously

---

### 4. Workflow DAG Construction
**File**: `/Users/les/Projects/crackerjack/crackerjack/runtime/oneiric_workflow.py`

```python
def register_crackerjack_workflow(
    runtime: OneiricWorkflowRuntime,
    *,
    phases: PhaseCoordinator,
    options: t.Any,
) -> None:
    _register_tasks(runtime, phases, options)
    _register_workflow(runtime, options)
    runtime.workflow_bridge.refresh_dags()

def _build_workflow_steps(options: t.Any) -> list[str]:
    steps: list[str] = []

    if _should_run_fast_hooks(options):     # comp=True → False
        steps.append("fast_hooks")          # SKIPPED

    if _should_run_tests(options) and _should_run_comprehensive_hooks(options):
        steps.extend(("tests", "comprehensive_hooks"))  # ADDED

    elif _should_run_comprehensive_hooks(options):  # True when comp=True
        steps.append("comprehensive_hooks")    # ADDED

    steps.extend(("publishing", "commit"))
    return steps
```

**Result for `--comp --ai-fix`**:
- `fast_hooks`: SKIPPED (because `comp=True`)
- `tests`: SKIPPED (because `run_tests=False`)
- `comprehensive_hooks`: EXECUTED
- `publishing`, `commit`: EXECUTED

---

### 5. Phase Coordinator - Comprehensive Hooks
**File**: `/Users/les/Projects/crackerjack/crackerjack/core/phase_coordinator.py`

```python
@handle_errors
def run_comprehensive_hooks_only(self, options: OptionsProtocol) -> bool:
    # Run comprehensive hooks first
    success = self._execute_hooks_once(
        "comprehensive",
        self.hook_manager.run_comprehensive_hooks,
        options,
        attempt=1,
    )

    # LINE 577: AI-FIX TRIGGER
    if not success and getattr(options, "ai_fix", False):
        self.console.print("\n")
        self.console.print(
            "[bold bright_magenta]🤖 AI AGENT FIXING[/bold bright_magenta]..."
        )

        from crackerjack.core.autofix_coordinator import AutofixCoordinator

        autofix_coordinator = AutofixCoordinator(
            console=self.console,
            pkg_path=self.pkg_path,
            max_iterations=getattr(options, "ai_fix_max_iterations", None),
        )

        # LINE 592: CALL AI-FIX
        ai_fix_success = autofix_coordinator.apply_comprehensive_stage_fixes(
            self._last_hook_results  # HookResult objects
        )

        if ai_fix_success:
            # Retry hooks after AI fixes
            success = self._execute_hooks_once(
                "comprehensive",
                self.hook_manager.run_comprehensive_hooks,
                options,
                attempt=2,
            )
        else:
            self.console.print(
                "[yellow]⚠️[/yellow] AI agents could not fix all issues"
            )

    return success
```

**Key Points**:
- Comprehensive hooks run first (14 issues found)
- `ai_fix=True` triggers AI-fix coordinator
- `_last_hook_results` contains HookResult objects from failed hooks
- If AI-fix succeeds, hooks are re-run (attempt=2)

---

### 6. Autofix Coordinator Entry Point
**File**: `/Users/les/Projects/crackerjack/crackerjack/core/autofix_coordinator.py`

```python
def apply_comprehensive_stage_fixes(self, hook_results: Sequence[object]) -> bool:
    return self._apply_comprehensive_stage_fixes(hook_results)

def _apply_comprehensive_stage_fixes(self, hook_results: Sequence[object]) -> bool:
    ai_agent_enabled = os.environ.get("AI_AGENT") == "1"  # True (set in CLI)

    if ai_agent_enabled:
        self.logger.info("AI agent mode enabled, attempting AI-based fixing")
        return self._apply_ai_agent_fixes(hook_results, stage="comprehensive")

    # ... fallback to non-AI fixes
```

**Flow**:
1. Check `AI_AGENT` environment variable (set to "1" by CLI handler)
2. Call `_apply_ai_agent_fixes()` with hook results

---

### 7. AI Agent Fixing Loop
**File**: `/Users/les/Projects/crackerjack/crackerjack/core/autofix_coordinator.py` (Lines 337-421)

```python
def _apply_ai_agent_fixes(
    self, hook_results: Sequence[object], stage: str = "fast"
) -> bool:
    # 1. Setup coordinator
    context = AgentContext(
        project_path=self.pkg_path,
        subprocess_timeout=300,
    )
    cache = CrackerjackCache()

    coordinator = AgentCoordinator(
        context=context,
        tracker=get_agent_tracker(),
        debugger=get_ai_agent_debugger(),
        cache=cache,
    )

    # 2. Parse hook results to Issue objects
    initial_issues = self._parse_hook_results_to_issues(hook_results)
    self.progress_manager.start_fix_session(
        stage=stage,
        initial_issue_count=len(initial_issues),
    )

    # 3. Iterative fixing loop
    previous_issue_count = float("inf")
    no_progress_count = 0

    iteration = 0
    try:
        while True:
            # LINE 374: Get issues for this iteration
            issues = self._get_iteration_issues(iteration, hook_results, stage)
            current_issue_count = len(issues)

            self.progress_manager.start_iteration(iteration, current_issue_count)

            # LINE 379-384: Zero issues check
            if current_issue_count == 0:
                result = self._handle_zero_issues_case(iteration, stage)
                if result is not None:
                    self.progress_manager.finish_session(success=True)
                    return result  # True if all resolved

            # LINE 386-393: Convergence check
            if self._should_stop_on_convergence(
                current_issue_count,
                previous_issue_count,
                no_progress_count,
            ):
                self.progress_manager.finish_session(success=False)
                return False  # ❌ THIS IS WHERE 0% REDUCTION HAPPENS

            # Update progress tracking
            no_progress_count = self._update_progress_count(
                current_issue_count,
                previous_issue_count,
                no_progress_count,
            )

            # LINE 407: Run AI fix iteration
            if not self._run_ai_fix_iteration(coordinator, issues):
                self.progress_manager.finish_session(success=False)
                return False

            self.progress_manager.end_iteration()

            previous_issue_count = current_issue_count
            iteration += 1
```

**Key Points**:
- Iterative loop with convergence detection
- Convergence threshold: 3 iterations with no progress
- Returns `False` when convergence reached (0% reduction)

---

### 8. Issue Parsing
**File**: `/Users/les/Projects/crackerjack/crackerjack/core/autofix_coordinator.py` (Lines 735-856)

```python
def _parse_hook_results_to_issues(
    self, hook_results: Sequence[object]
) -> list[Issue]:
    self.logger.debug(f"Parsing {len(hook_results)} hook results for issues")

    issues, parsed_counts_by_hook = self._parse_all_hook_results(hook_results)
    self._update_hook_issue_counts(hook_results, parsed_counts_by_hook)
    unique_issues = self._deduplicate_issues(issues)

    self._log_parsing_summary(len(issues), len(unique_issues))
    return unique_issues

def _parse_single_hook_result(self, result: object) -> list[Issue]:
    if not self._validate_hook_result(result):
        return []

    status = getattr(result, "status", "")
    if status.lower() != "failed":
        self.logger.debug(f"Skipping hook with status '{status}' (not failed)")
        return []

    hook_name = getattr(result, "name", "")
    raw_output = self._extract_raw_output(result)

    # LINE 853: Parse using parser factory
    hook_issues = self._parse_hook_to_issues(hook_name, raw_output)
    return hook_issues

def _parse_hook_to_issues(self, hook_name: str, raw_output: str) -> list[Issue]:
    self.logger.debug(f"Parsing hook '{hook_name}'")

    expected_count = self._extract_issue_count(raw_output, hook_name)

    try:
        # LINE 1066: Call parser factory
        issues = self._parser_factory.parse_with_validation(
            tool_name=hook_name,
            output=raw_output,
            expected_count=expected_count,
        )

        self.logger.info(f"Successfully parsed {len(issues)} issues from '{hook_name}'")
        return issues

    except ParsingError as e:
        self.logger.error(f"Parsing failed for '{hook_name}': {e}")
        raise  # ❌ PARSING FAILURE PROPAGATES HERE
```

**Key Points**:
- HookResult objects validated for status="failed"
- Raw output extracted from HookResult
- ParserFactory.parse_with_validation() called
- **ParsingError propagates and breaks the loop**

---

### 9. Parser Factory
**File**: `/Users/les/Projects/crackerjack/crackerjack/parsers/factory.py` (Lines 100-158)

```python
def parse_with_validation(
    self,
    tool_name: str,
    output: str,
    expected_count: int | None = None,
) -> list[Issue]:
    parser = self.create_parser(tool_name)

    is_json = self._is_json_output(output)

    if is_json:
        issues = self._parse_json_output(parser, output, tool_name)
    else:
        issues = self._parse_text_output(parser, output, tool_name)

    # LINE 116: Validate issue count
    if expected_count is not None:
        self._validate_issue_count(issues, expected_count, tool_name, output)

    return issues

def _validate_issue_count(
    self,
    issues: list[Issue],
    expected_count: int,
    tool_name: str,
    output: str,
) -> None:
    actual_count = len(issues)

    if actual_count != expected_count:
        # LINE 158: RAISE PARSING ERROR
        raise ParsingError(
            f"Parser count mismatch for '{tool_name}': "
            f"expected {expected_count} issues, got {actual_count}",
            tool_name=tool_name,
            expected_count=expected_count,
            actual_count=actual_count,
            output=output,
        )
```

**Key Points**:
- Creates parser for tool name (e.g., "ruff", "mypy")
- Parses JSON or text output
- **Validates parsed count against expected count**
- **Raises ParsingError on count mismatch** → This causes agent failure

---

### 10. Agent Coordinator
**File**: `/Users/les/Projects/crackerjack/crackerjack/agents/coordinator.py` (Lines 105-133)

```python
async def handle_issues(self, issues: list[Issue]) -> FixResult:
    if not self.agents:
        self.initialize_agents()

    if not issues:
        return FixResult(success=True, confidence=1.0)

    self.logger.info(f"Handling {len(issues)} issues")

    # Group issues by type
    issues_by_type = self._group_issues_by_type(issues)

    # LINE 117: Create tasks for each issue type
    tasks = list[t.Any](
        starmap(self._handle_issues_by_type, issues_by_type.items()),
    )

    # LINE 120: Run all agent tasks in parallel
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # LINE 122-131: Merge results
    overall_result = FixResult(success=True, confidence=1.0)
    for result in results:
        if isinstance(result, FixResult):
            overall_result = overall_result.merge_with(result)
        else:
            self.logger.error(f"Issue type handling failed: {result}")
            overall_result.success = False
            overall_result.remaining_issues.append(
                f"Type handling failed: {result}",
            )

    return overall_result

async def _handle_issues_by_type(
    self,
    issue_type: IssueType,
    issues: list[Issue],
) -> FixResult:
    self.logger.info(f"Handling {len(issues)} {issue_type.value} issues")

    # LINE 142: Find specialist agents
    specialist_agents = await self._find_specialist_agents(issue_type)
    if not specialist_agents:
        return self._create_no_agents_result(issue_type)

    # LINE 146: Create tasks
    tasks = await self._create_issue_tasks(specialist_agents, issues)
    if not tasks:
        return FixResult(success=False, confidence=0.0)

    # LINE 150: Execute tasks
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return self._merge_fix_results(results)
```

**Key Points**:
- Issues grouped by type (formatting, complexity, security, etc.)
- Specialist agents found for each issue type
- Tasks created and executed in parallel
- Results merged into FixResult

---

### 11. Agent Execution
**File**: `/Users/les/Projects/crackerjack/crackerjack/agents/coordinator.py` (Lines 318-365)

```python
async def _handle_with_single_agent(
    self,
    agent: SubAgent,
    issue: Issue,
) -> FixResult:
    self.logger.info(f"Handling issue with {agent.name}: {issue.message[:100]}")

    issue_hash = self._create_issue_hash(issue)

    # Check cache
    cached_decision = self._coerce_cached_decision(
        self.cache.get_agent_decision(agent.name, issue_hash),
    )
    if cached_decision:
        return cached_decision

    # LINE 335: Check if agent can handle issue
    confidence = await agent.can_handle(issue)
    self.tracker.track_agent_processing(agent.name, issue, confidence)

    self.debugger.log_agent_activity(
        agent_name=agent.name,
        activity="processing_started",
        issue_id=issue.id,
        confidence=confidence,
        metadata={"issue_type": issue.type.value, "severity": issue.severity.value},
    )

    start_time = time.time()

    # LINE 348: Execute agent
    result = await self._execute_agent(agent, issue)

    # ... tracking and result processing
```

**Key Points**:
- Cache checked for previous decisions
- Agent asked if it can handle the issue (confidence score)
- Agent executed with issue context
- Result tracked and returned

---

### 12. Execution Flow Summary

```
1. CLI Handler
   └─> Sets AI_AGENT=1 environment variable
   └─> Creates Options object with ai_fix=True, comp=True

2. WorkflowPipeline
   └─> Builds Oneiric DAG
   └─> Registers workflow phases

3. Oneiric Workflow
   └─> Builds DAG nodes (comprehensive_hooks only)
   └─> Executes comprehensive_hooks phase

4. PhaseCoordinator.run_comprehensive_hooks_only()
   └─> Run comprehensive hooks (14 issues found)
   └─> Check ai_fix=True
   └─> Call AutofixCoordinator.apply_comprehensive_stage_fixes()

5. AutofixCoordinator._apply_ai_agent_fixes()
   ├─> Create AgentCoordinator
   ├─> Parse HookResult objects to Issue objects
   │  └─> ParserFactory.parse_with_validation()
   │     └─> Parse output (JSON/text)
   │     └─> Validate issue count
   │     └─> ❌ RAISE ParsingError IF COUNT MISMATCH
   │
   ├─> Enter iteration loop
   │  ├─> Get issues for iteration
   │  ├─> Check convergence (no progress for 3 iterations)
   │  │  └─> Return False (0% reduction) ❌
   │  │
   │  ├─> Run AI fix iteration
   │  │  └─> AgentCoordinator.handle_issues()
   │  │     └─> Group issues by type
   │  │     └─> Find specialist agents
   │  │     └─> Execute agents
   │  │        └─> agent.can_handle(issue)
   │  │        └─> agent.fix_issue(issue)
   │  │           └─> Modify files
   │  │           └─> Return FixResult
   │  │
   │  └─> Update progress tracking
   │
   └─> Return success/failure
```

---

## Where the Failure Occurs

### Primary Failure Point: Convergence Detection

**Location**: `/Users/les/Projects/crackerjack/crackerjack/core/autofix_coordinator.py:386-393`

```python
if self._should_stop_on_convergence(
    current_issue_count,
    previous_issue_count,
    no_progress_count,
):
    self.progress_manager.finish_session(success=False)
    return False  # ❌ 0% REDUCTION
```

**What happens**:
1. Iteration 0: 14 issues parsed from hook results
2. Agents execute, apply 0 fixes (confidence too low or other issues)
3. Iteration 1: Still 14 issues (no progress)
4. Iteration 2: Still 14 issues (no progress)
5. Iteration 3: Still 14 issues (no progress)
6. **Convergence reached** → Return False → 0% reduction

### Secondary Failure Point: Parsing Errors

**Location**: `/Users/les/Projects/crackerjack/crackerjack/parsers/factory.py:158`

```python
if actual_count != expected_count:
    raise ParsingError(
        f"Parser count mismatch for '{tool_name}': "
        f"expected {expected_count} issues, got {actual_count}",
        ...
    )
```

**What happens**:
1. HookResult contains raw output from tool (e.g., mypy, ruff)
2. Expected count extracted from output (e.g., "Found 14 errors")
3. Parser parses output and returns Issue objects
4. **Count validation fails** (e.g., expected 14, got 12)
5. **ParsingError raised** → Agent loop fails → 0% reduction

---

## Why Agents Achieve 0% Reduction

### Hypothesis 1: Agents Refuse to Fix (Low Confidence)

**Evidence**:
- Agents evaluate issues with `can_handle(issue)`
- Confidence threshold: ≥0.7 required
- If confidence <0.7, agent refuses to fix
- Result: 0 fixes applied, convergence reached

**Flow**:
```python
confidence = await agent.can_handle(issue)
if confidence < 0.7:
    # Agent refuses to fix
    return FixResult(success=False, confidence=confidence)
```

### Hypothesis 2: Parsing Errors Prevent Agent Execution

**Evidence**:
- Format specifier error mentioned in context
- ParsingError raises during issue parsing
- Exception caught, but breaks iteration loop
- Result: Agents never execute, 0 fixes applied

**Flow**:
```python
try:
    issues = self._parser_factory.parse_with_validation(...)
except ParsingError as e:
    self.logger.error(f"Parsing failed: {e}")
    raise  # ❌ Breaks the loop, agents never run
```

### Hypothesis 3: Agent Execution Fails Silently

**Evidence**:
- Agents execute but return FixResult(success=False)
- Files not modified
- Issues remain
- Convergence reached after 3 iterations

**Flow**:
```python
result = await self._execute_agent(agent, issue)
# result.success = False
# result.fixes_applied = []
# result.remaining_issues = [issue]
```

---

## Connection to Format Specifier Error

The "format specifier error" mentioned in the context likely occurs in:

1. **Hook Execution**: Tool output contains format specifiers in error messages
   - Example: `error: invalid format specifier %.0f in format string`
   - This becomes part of HookResult.raw_output

2. **Parsing**: Parser tries to extract expected count from output
   - Example: `Found 14 errors` → expected_count = 14
   - But format specifier error breaks parsing
   - Result: expected_count=None or incorrect value

3. **Validation**: Parser validates count, fails
   - actual_count ≠ expected_count
   - **Raises ParsingError**
   - Agent loop breaks
   - **0% reduction**

---

## Next Steps for Investigation

1. **Enable Debug Logging**
   ```bash
   export AI_AGENT_DEBUG=1
   export AI_AGENT_VERBOSE=1
   python -m crackerjack run --comp --ai-fix --debug
   ```

2. **Check Hook Results**
   - Look at `HookResult.output` for each failed hook
   - Find format specifier errors in raw output
   - Verify expected_count extraction

3. **Check Parser Logs**
   - Look for "Parsing failed" messages
   - Check "expected_count" vs "actual_count" mismatches
   - Find which tool/parser is failing

4. **Check Agent Execution**
   - Look for "Handling issue with X agent" messages
   - Check confidence scores
   - Verify if agents execute at all

5. **Check Fix Results**
   - Look for "FixResult" messages
   - Check "fixes_applied" count
   - Verify files_modified list

---

## Conclusion

The AI-fix 0% reduction issue is caused by:

1. **Primary**: Parsing errors during issue extraction (format specifier error breaks count validation)
2. **Secondary**: Low agent confidence (agents refuse to fix issues)
3. **Tertiary**: Agent execution failures (agents run but don't modify files)

The most likely culprit is the **format specifier error in hook output**, which causes:
- Incorrect expected_count extraction
- Parser validation failure
- ParsingError raised
- Agent loop broken
- **0 fixes applied → 0% reduction**
