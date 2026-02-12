"""
Example 3: Workflow-Phase-Aware Recommendations

Demonstrates how to:
1. Get recommendations for specific Oneiric workflow phases
2. Compare recommendations across phases
3. Select agents based on phase-specific effectiveness

Use case: Optimize agent selection by workflow phase
"""

from pathlib import Path
from crackerjack.agents.base import AgentContext
from crackerjack.integration.skills_tracking import create_skills_tracker


def main() -> None:
    """Workflow-phase-aware recommendations example."""
    print("=== Example 3: Workflow-Phase-Aware Recommendations ===\n")

    # Step 1: Create tracker
    print("Step 1: Creating skills tracker...")
    tracker = create_skills_tracker(
        session_id="example-session-3",
        enabled=True,
        backend="auto",
    )
    print(f"✅ Tracker created: {tracker.get_backend()}\n")

    # Step 2: Create context
    context = AgentContext(
        project_path=Path.cwd(),
        skills_tracker=tracker,
    )

    # Step 3: Get recommendations for different workflow phases
    print("Step 3: Comparing recommendations across workflow phases...")
    print("=" * 80)

    query = "Fix import errors and organize imports"
    phases = ["fast_hooks", "comprehensive_hooks", "execution"]

    phase_recommendations = {}

    for phase in phases:
        print(f"\n📋 Phase: {phase}")
        print("-" * 80)

        recommendations = context.get_skill_recommendations(
            user_query=query,
            limit=3,
            workflow_phase=phase,
        )

        if not recommendations:
            print("   No recommendations for this phase")
            continue

        phase_recommendations[phase] = recommendations

        for i, rec in enumerate(recommendations, 1):
            print(f"\n   {i}. {rec['skill_name']}")
            print(f"      Similarity:    {rec['similarity_score']:.2f}")
            print(f"      Completion:    {rec['completed']}")
            print(f"      Best Phase:    {rec.get('workflow_phase', 'N/A')}")
            print(f"      Avg Duration:  {rec.get('duration_seconds', 'N/A')}s")

    print("\n" + "=" * 80 + "\n")

    # Step 4: Analyze phase-specific recommendations
    print("Step 4: Analyzing phase-specific recommendations...\n")

    for phase, recs in phase_recommendations.items():
        if not recs:
            continue

        print(f"📊 {phase} Analysis:")
        print(f"   Top Agent:  {recs[0]['skill_name']}")
        print(f"   Similarity: {recs[0]['similarity_score']:.2f}")
        print(f"   Completion: {recs[0]['completed']}")

        # Calculate phase effectiveness score
        completed_count = sum(1 for r in recs if r['completed'])
        effectiveness = completed_count / len(recs)
        print(f"   Effectiveness: {effectiveness:.1%} ({completed_count}/{len(recs)} agents successful)")
        print()

    # Step 5: Select optimal agent for each phase
    print("Step 5: Optimal agent selection by phase...")
    print("=" * 80)

    for phase in phases:
        if phase not in phase_recommendations:
            print(f"\n{phase}: No data")
            continue

        recs = phase_recommendations[phase]

        # Select agent with highest weighted score
        def weighted_score(rec: dict) -> float:
            similarity = rec['similarity_score']
            completed = 1.5 if rec['completed'] else 0.5
            phase_match = 1.2 if rec.get('workflow_phase') == phase else 1.0
            return similarity * completed * phase_match

        best = max(recs, key=weighted_score)
        score = weighted_score(best)

        print(f"\n{phase}:")
        print(f"  Best Agent:  {best['skill_name']}")
        print(f"  Score:       {score:.2f}")
        print(f"  Reason:      Highest weighted score for this phase")

    print("\n" + "=" * 80 + "\n")

    # Step 6: Practical example - agent routing
    print("Step 6: Practical agent routing by phase...\n")

    current_phase = "fast_hooks"  # Simulating current workflow phase
    print(f"Current phase: {current_phase}")
    print(f"Query: {query}\n")

    if current_phase in phase_recommendations:
        recommendations = phase_recommendations[current_phase]

        # Filter to highly effective agents only
        effective_agents = [
            r for r in recommendations
            if r['completed'] and r['similarity_score'] >= 0.7
        ]

        if effective_agents:
            print("✅ Recommended agents (high effectiveness):")
            for agent in effective_agents:
                print(f"   • {agent['skill_name']} (similarity: {agent['similarity_score']:.2f})")
        else:
            print("⚠️  No highly effective agents found for this phase")
            print("   Using best available anyway:")
            print(f"   • {recommendations[0]['skill_name']}")
    else:
        print("⚠️  No recommendations available for this phase")
        print("   Using default agent selection")

    # Summary
    print("\n=== Summary ===")
    print(f"✅ Compared recommendations across {len(phases)} workflow phases")
    print(f"✅ Identified phase-specific optimal agents")
    print(f"✅ Use workflow phase for intelligent agent routing")


if __name__ == "__main__":
    main()
