"""
Example 2: Getting Agent Recommendations

Demonstrates how to:
1. Get agent recommendations for a problem
2. Process recommendation results
3. Use recommendations for agent selection

Use case: Intelligent agent selection based on historical data
"""

from pathlib import Path
from crackerjack.agents.base import AgentContext
from crackerjack.integration.skills_tracking import create_skills_tracker


def main() -> None:
    """Agent recommendations example."""
    print("=== Example 2: Agent Recommendations ===\n")

    # Step 1: Create tracker
    print("Step 1: Creating skills tracker...")
    tracker = create_skills_tracker(
        session_id="example-session-2",
        enabled=True,
        backend="auto",
    )
    print(f"✅ Tracker created: {tracker.get_backend()}\n")

    # Step 2: Create context
    print("Step 2: Creating agent context...")
    context = AgentContext(
        project_path=Path.cwd(),
        skills_tracker=tracker,
    )
    print("✅ Context created\n")

    # Step 3: Get recommendations for a problem
    print("Step 3: Getting agent recommendations...")
    print("   Query: 'Fix type errors in async functions'\n")

    recommendations = context.get_skill_recommendations(
        user_query="Fix type errors in async functions",
        limit=5,
        workflow_phase="comprehensive_hooks",
    )

    if not recommendations:
        print("⚠️  No recommendations returned")
        print("   Possible reasons:")
        print("   - Tracking disabled")
        print("   - No historical data")
        print("   - Database empty")
        return

    print(f"✅ Got {len(recommendations)} recommendations:\n")

    # Step 4: Process recommendations
    print("Step 4: Processing recommendations...")
    print("=" * 80)

    for i, rec in enumerate(recommendations, 1):
        print(f"\nRecommendation #{i}:")
        print(f"  Agent:           {rec['skill_name']}")
        print(f"  Similarity:      {rec['similarity_score']:.2f}")
        print(f"  Completed:      {rec['completed']}")
        print(f"  Avg Duration:    {rec.get('duration_seconds', 'N/A')}s")
        print(f"  Best Phase:      {rec.get('workflow_phase', 'N/A')}")

        # Calculate recommendation score
        score = rec['similarity_score']
        if rec['completed']:
            score *= 1.2  # Boost for successful agents

        print(f"  Recommendation Score: {score:.2f}")

        # Decision threshold
        if score >= 0.8:
            print(f"  ✅ STRONGLY RECOMMENDED")
        elif score >= 0.6:
            print(f"  ✓ Recommended")
        else:
            print(f"  ⚠ Consider with caution")

    print("\n" + "=" * 80 + "\n")

    # Step 5: Select best agent
    print("Step 5: Selecting best agent...")
    best_recommendation = recommendations[0]  # Already sorted by relevance
    print(f"✅ Selected: {best_recommendation['skill_name']}")
    print(f"   Reason: Highest similarity score ({best_recommendation['similarity_score']:.2f})")
    print(f"   Success Rate: {best_recommendation['completed']}\n")

    # Alternative: Weighted selection
    print("Step 6: Alternative - Weighted selection...")
    print("   Considering both similarity and completion rate:")

    def recommendation_score(rec: dict) -> float:
        """Calculate weighted recommendation score."""
        similarity = rec['similarity_score']
        completed = 1.2 if rec['completed'] else 0.8
        return similarity * completed

    sorted_recs = sorted(
        recommendations,
        key=recommendation_score,
        reverse=True
    )

    print(f"\n   Re-ranking based on weighted score:")
    for i, rec in enumerate(sorted_recs[:3], 1):
        score = recommendation_score(rec)
        print(f"   {i}. {rec['skill_name']}: {score:.2f}")

    # Summary
    print("\n=== Summary ===")
    print(f"✅ Got {len(recommendations)} recommendations")
    print(f"✅ Best agent: {best_recommendation['skill_name']}")
    print(f"✅ Use recommendations for intelligent agent selection")


if __name__ == "__main__":
    main()
