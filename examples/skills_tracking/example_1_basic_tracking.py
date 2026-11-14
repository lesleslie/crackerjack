"""
Example 1: Basic Skills Tracking

Demonstrates how to:
1. Create a skills tracker
2. Track agent invocations
3. Complete tracking with success/failure

Use case: Simple manual tracking outside AgentOrchestrator
"""

from crackerjack.integration.skills_tracking import create_skills_tracker


def main() -> None:
    """Basic skills tracking example."""
    print("=== Example 1: Basic Skills Tracking ===\n")

    # Step 1: Create tracker
    print("Step 1: Creating skills tracker...")
    tracker = create_skills_tracker(
        session_id="example-session-1",
        enabled=True,
        backend="auto",  # Tries MCP, falls back to direct
    )
    print(f"✅ Tracker created: {tracker.get_backend()}")
    print(f"   Enabled: {tracker.is_enabled()}\n")

    # Step 2: Track an agent invocation
    print("Step 2: Tracking agent invocation...")
    completer = tracker.track_invocation(
        skill_name="RefactoringAgent",
        user_query="Fix complexity issues in module X",
        workflow_phase="comprehensive_hooks",
        alternatives_considered=["PerformanceAgent", "DRYAgent"],
        selection_rank=1,  # First choice
    )

    if completer is None:
        print("⚠️  Tracking disabled (completer is None)")
        return

    print("✅ Tracking started")
    print("   Agent: RefactoringAgent")
    print("   Query: Fix complexity issues in module X")
    print("   Phase: comprehensive_hooks\n")

    # Step 3: Simulate work
    print("Step 3: Simulating agent work...")
    import time

    time.sleep(1)  # Simulate 1 second of work
    print("✅ Work completed\n")

    # Step 4: Complete tracking
    print("Step 4: Completing tracking...")
    completer(
        completed=True,
        follow_up_actions=["Run pytest", "Check coverage"],
        error_type=None,
    )
    print("✅ Tracking completed")
    print("   Status: Success")
    print("   Follow-up: Run pytest, Check coverage\n")

    # Summary
    print("=== Summary ===")
    print("✅ Successfully tracked RefactoringAgent invocation")
    print(f"   Backend: {tracker.get_backend()}")
    print("   Session: example-session-1")


if __name__ == "__main__":
    main()
