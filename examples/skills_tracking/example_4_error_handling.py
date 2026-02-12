"""
Example 4: Error Handling and Graceful Degradation

Demonstrates how to:
1. Handle tracking errors gracefully
2. Fallback when tracking unavailable
3. Use NoOp tracker for testing

Use case: Robust error handling in production
"""

import logging
from pathlib import Path
from crackerjack.agents.base import AgentContext
from crackerjack.integration.skills_tracking import (
    NoOpSkillsTracker,
    create_skills_tracker,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main() -> None:
    """Error handling and graceful degradation example."""
    print("=== Example 4: Error Handling and Graceful Degradation ===\n")

    # Example 1: No-op tracker (disabled tracking)
    print("Example 1: No-Op Tracker (Disabled)\n")
    print("Use case: Testing, development, or when tracking not needed\n")

    no_op_tracker = NoOpSkillsTracker()
    context = AgentContext(
        project_path=Path.cwd(),
        skills_tracker=no_op_tracker,
    )

    # Try to track - returns None immediately
    completer = context.track_skill_invocation(
        skill_name="TestAgent",
        user_query="Test query"
    )

    if completer is None:
        print("✅ Tracking disabled (completer is None)")
        print("   Zero overhead - no database operations\n")

    # Example 2: Graceful error handling
    print("Example 2: Graceful Error Handling\n")
    print("Use case: Production resilience when tracking fails\n")

    try:
        tracker = create_skills_tracker(
            session_id="example-session-4",
            enabled=True,
            backend="direct",
        )

        context = AgentContext(
            project_path=Path.cwd(),
            skills_tracker=tracker,
        )

        # Attempt tracking with error handling
        completer = context.track_skill_invocation(
            skill_name="RefactoringAgent",
            user_query="Fix complexity",
        )

        if completer:
            print("✅ Tracking started successfully")

            try:
                # Simulate work
                print("   Performing work...")

                # Complete tracking with error handling
                completer(completed=True)
                print("✅ Tracking completed successfully")

            except Exception as e:
                # Log but don't crash
                logger.warning(f"Failed to complete tracking: {e}")
                print("⚠️  Tracking completion failed, but work succeeded")

        else:
            print("⚠️  Tracking not available, continuing without tracking")

    except Exception as e:
        # Log error but continue execution
        logger.error(f"Tracking initialization failed: {e}")
        print(f"❌ Tracking failed: {e}")
        print("✓ Continuing execution without tracking\n")

    # Example 3: Safe recommendation retrieval
    print("Example 3: Safe Recommendation Retrieval\n")
    print("Use case: Always return valid results, even on errors\n")

    try:
        tracker = create_skills_tracker(
            session_id="example-session-4",
            enabled=True,
        )

        context = AgentContext(
            project_path=Path.cwd(),
            skills_tracker=tracker,
        )

        # Get recommendations with error handling
        recommendations = context.get_skill_recommendations(
            user_query="Fix type errors",
            limit=5,
        )

        if recommendations:
            print(f"✅ Got {len(recommendations)} recommendations")
            for rec in recommendations[:3]:  # Show top 3
                print(f"   • {rec['skill_name']}: {rec['similarity_score']:.2f}")
        else:
            print("⚠️  No recommendations available")
            print("   Possible causes:")
            print("   - Database empty (no historical data)")
            print("   - Tracking disabled")
            print("   - Query too specific")

    except Exception as e:
        logger.error(f"Recommendation retrieval failed: {e}")
        print(f"❌ Failed to get recommendations: {e}")
        print("✓ Using fallback agent selection\n")

    # Example 4: Validation before tracking
    print("Example 4: Validation Before Tracking\n")
    print("Use case: Ensure tracker is available before using\n")

    tracker = create_skills_tracker(
        session_id="example-session-4",
        enabled=True,
    )

    # Validate tracker
    if not tracker.is_enabled():
        print("⚠️  Tracking disabled, skipping...")
        return

    backend = tracker.get_backend()
    print(f"✅ Tracker enabled: {backend}")

    if backend == "none":
        print("⚠️  No-op tracker, skipping tracking...")
        return

    # Safe to proceed with tracking
    context = AgentContext(
        project_path=Path.cwd(),
        skills_tracker=tracker,
    )

    completer = context.track_skill_invocation(
        skill_name="TestAgent",
        user_query="Test",
    )

    if completer:
        print("✅ Tracking successful")
        completer(completed=True)
    else:
        print("⚠️  Tracking returned None (unexpected)")

    # Example 5: Fallback to no-op on error
    print("\n\nExample 5: Fallback to No-Op on Error\n")
    print("Use case: Ensure system works even if tracking completely fails\n")

    try:
        tracker = create_skills_tracker(
            session_id="example-session-4",
            enabled=True,
            backend="direct",
        )
        print(f"✅ Tracker created: {tracker.get_backend()}")

    except Exception as e:
        logger.warning(f"Tracker creation failed, using no-op: {e}")
        print(f"⚠️  Tracker creation failed: {e}")
        print("   Falling back to no-op tracker...")

        # Fallback to no-op
        tracker = NoOpSkillsTracker()

    # Continue with fallback tracker
    context = AgentContext(
        project_path=Path.cwd(),
        skills_tracker=tracker,
    )

    completer = context.track_skill_invocation(
        skill_name="FallbackAgent",
        user_query="Test with fallback",
    )

    if completer:
        print("✅ Tracking with fallback successful")
        completer(completed=True)
    else:
        print("✓ Fallback tracker is no-op (expected)")

    # Summary
    print("\n=== Summary ===")
    print("✅ Demonstrated error handling patterns:")
    print("   1. No-op tracker for disabled tracking")
    print("   2. Graceful error handling in tracking")
    print("   3. Safe recommendation retrieval")
    print("   4. Validation before tracking")
    print("   5. Fallback to no-op on error")
    print("\n✅ System remains functional even when tracking fails")


if __name__ == "__main__":
    main()
