"""ACB workflow definitions for crackerjack.

This module defines declarative workflow structures for various execution modes
using ACB's WorkflowDefinition and WorkflowStep classes.
"""

from acb.workflows import WorkflowDefinition, WorkflowStep

# Phase 1 POC: Fast hooks workflow
# This is the simplest workflow for proof of concept validation
FAST_HOOKS_WORKFLOW = WorkflowDefinition(
    workflow_id="crackerjack-fast-hooks",
    name="Fast Quality Checks",
    description="Quick formatters, import sorting, and basic static analysis",
    steps=[
        WorkflowStep(
            step_id="config",
            name="Configuration",
            action="run_configuration",
            params={},
            retry_attempts=1,  # Config rarely needs retry
            timeout=30.0,  # Config is fast
        ),
        WorkflowStep(
            step_id="fast_hooks",
            name="Fast Hooks",
            action="run_fast_hooks",
            params={},
            depends_on=["config"],  # Runs after config completes
            retry_attempts=2,  # Retry on transient failures
            timeout=300.0,  # 5 minutes for fast hooks
        ),
    ],
    timeout=600.0,  # 10 minutes total workflow timeout
    retry_failed_steps=True,
    continue_on_error=False,  # Stop on first failure for POC
)

# Phase 2: Standard workflow with phase-level parallelization
# This workflow demonstrates parallel execution of independent phases
STANDARD_WORKFLOW = WorkflowDefinition(
    workflow_id="crackerjack-standard",
    name="Standard Quality Workflow",
    description="Full quality check workflow with parallel phase execution",
    steps=[
        WorkflowStep(
            step_id="config",
            name="Configuration",
            action="run_configuration",
            params={},
            retry_attempts=1,
            timeout=30.0,
        ),
        # Fast hooks and cleaning run in parallel (both depend only on config)
        WorkflowStep(
            step_id="fast_hooks",
            name="Fast Hooks",
            action="run_fast_hooks",
            params={},
            depends_on=["config"],
            retry_attempts=2,
            timeout=300.0,
            parallel=True,  # Can run parallel with cleaning
        ),
        WorkflowStep(
            step_id="cleaning",
            name="Code Cleaning",
            action="run_code_cleaning",
            params={},
            depends_on=["config"],
            retry_attempts=1,
            timeout=180.0,
            skip_on_failure=True,  # Cleaning is optional
            parallel=True,  # Can run parallel with fast_hooks
        ),
        # Comprehensive hooks wait for both fast_hooks and cleaning
        WorkflowStep(
            step_id="comprehensive",
            name="Comprehensive Hooks",
            action="run_comprehensive_hooks",
            params={},
            depends_on=["fast_hooks", "cleaning"],  # Waits for both
            retry_attempts=2,
            timeout=900.0,  # 15 minutes for comprehensive
        ),
    ],
    timeout=1800.0,  # 30 minutes total workflow timeout
    retry_failed_steps=True,
    continue_on_error=False,
)

# Phase 2: Test workflow
# Workflow for --run-tests mode: Full quality workflow WITH tests
TEST_WORKFLOW = WorkflowDefinition(
    workflow_id="crackerjack-test",
    name="Test Execution Workflow",
    description="Full quality workflow: fast hooks → code cleaning → tests → comprehensive hooks",
    steps=[
        WorkflowStep(
            step_id="config",
            name="Configuration",
            action="run_configuration",
            params={},
            retry_attempts=1,
            timeout=30.0,
        ),
        # Fast hooks and cleaning run in parallel (both depend only on config)
        WorkflowStep(
            step_id="fast_hooks",
            name="Fast Hooks",
            action="run_fast_hooks",
            params={},
            depends_on=["config"],
            retry_attempts=2,
            timeout=300.0,
            parallel=True,  # Can run parallel with cleaning
        ),
        WorkflowStep(
            step_id="cleaning",
            name="Code Cleaning",
            action="run_code_cleaning",
            params={},
            depends_on=["config"],
            retry_attempts=1,
            timeout=180.0,
            skip_on_failure=True,  # Cleaning is optional
            parallel=True,  # Can run parallel with fast_hooks
        ),
        # Tests run after fast hooks and cleaning
        WorkflowStep(
            step_id="test_workflow",
            name="Test Execution",
            action="run_test_workflow",
            params={},
            depends_on=["fast_hooks", "cleaning"],  # Waits for both
            retry_attempts=1,  # Tests shouldn't retry automatically
            timeout=1800.0,  # 30 minutes for tests
        ),
        # Comprehensive hooks run after tests complete
        WorkflowStep(
            step_id="comprehensive",
            name="Comprehensive Hooks",
            action="run_comprehensive_hooks",
            params={},
            depends_on=["test_workflow"],  # Waits for tests
            retry_attempts=2,
            timeout=900.0,  # 15 minutes for comprehensive
        ),
    ],
    timeout=3600.0,  # 60 minutes total workflow timeout
    retry_failed_steps=True,
    continue_on_error=False,
)

# Phase 3: Comprehensive workflow with hook-level parallelization
# This workflow runs individual hooks in parallel for maximum performance
COMPREHENSIVE_PARALLEL_WORKFLOW = WorkflowDefinition(
    workflow_id="crackerjack-comprehensive-parallel",
    name="Comprehensive Quality Checks (Parallel)",
    description="Individual hooks run in parallel for maximum performance",
    steps=[
        WorkflowStep(
            step_id="config",
            name="Configuration",
            action="run_configuration",
            params={},
            retry_attempts=1,
            timeout=30.0,
        ),
        # All hooks run in parallel (Phase 3 feature)
        WorkflowStep(
            step_id="zuban",
            name="Type Checking (Zuban)",
            action="run_hook",
            params={"hook_name": "zuban"},
            depends_on=["config"],
            retry_attempts=1,
            timeout=300.0,
            parallel=True,
        ),
        WorkflowStep(
            step_id="bandit",
            name="Security Check (Bandit)",
            action="run_hook",
            params={"hook_name": "bandit"},
            depends_on=["config"],
            retry_attempts=1,
            timeout=300.0,
            parallel=True,
        ),
        WorkflowStep(
            step_id="gitleaks",
            name="Secret Scanning (Gitleaks)",
            action="run_hook",
            params={"hook_name": "gitleaks"},
            depends_on=["config"],
            retry_attempts=1,
            timeout=300.0,
            parallel=True,
        ),
        WorkflowStep(
            step_id="skylos",
            name="Dead Code Detection (Skylos)",
            action="run_hook",
            params={"hook_name": "skylos"},
            depends_on=["config"],
            retry_attempts=1,
            timeout=300.0,
            parallel=True,
        ),
    ],
    timeout=900.0,  # 15 minutes total (much faster than sequential!)
    retry_failed_steps=True,
    continue_on_error=False,
)


def select_workflow_for_options(options: "OptionsProtocol") -> WorkflowDefinition:  # type: ignore[name-defined]
    """Select appropriate workflow based on CLI options.

    Args:
        options: CLI options (Options or compatible protocol)

    Returns:
        WorkflowDefinition matching the requested execution mode
    """
    # Test mode
    if getattr(options, "run_tests", False):
        return TEST_WORKFLOW

    # Fast mode (fast hooks only)
    if getattr(options, "fast", False):
        return FAST_HOOKS_WORKFLOW

    # Comprehensive mode (comp hooks only) - Phase 3 uses parallel version
    if getattr(options, "comp", False):
        # Check if parallel execution is enabled (Phase 3 feature)
        if getattr(options, "parallel_hooks", False):
            return COMPREHENSIVE_PARALLEL_WORKFLOW
        # Phase 1-2: Use standard workflow without parallel hooks
        return FAST_HOOKS_WORKFLOW  # Placeholder for now

    # Default: Standard workflow with phase-level parallelization
    return STANDARD_WORKFLOW
