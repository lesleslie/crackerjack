#!/usr/bin/env python3
"""Simple test to validate V2 system imports and initialization."""
import asyncio
from crackerjack.agents import AnalysisCoordinator, FixerCoordinator
from crackerjack.models.fix_plan import FixPlan, ChangeSpec
from crackerjack.agents.base import Issue, IssueType, Priority


async def main():
    print("Testing V2 System Initialization...")

    # Test AnalysisCoordinator initialization
    try:
        analysis_coordinator = AnalysisCoordinator(max_concurrent=2, project_path=".")
        print("✅ AnalysisCoordinator initialized")
    except Exception as e:
        print(f"❌ AnalysisCoordinator failed: {e}")
        return

    # Test FixerCoordinator initialization
    try:
        fixer_coordinator = FixerCoordinator(project_path=".")
        print("✅ FixerCoordinator initialized")
    except Exception as e:
        print(f"❌ FixerCoordinator failed: {e}")
        return

    # Create a sample FixPlan
    sample_plan = FixPlan(
        file_path="test.py",
        issue_type="COMPLEXITY",
        changes=[
            ChangeSpec(
                line_range=(1, 10),
                old_code="def old_func():\n    pass",
                new_code="def new_func():\n    return True",
                reason="Test change"
            )
        ],
        rationale="Test plan",
        risk_level="low",
        validated_by="test"
    )

    print(f"✅ Created sample FixPlan: {sample_plan.file_path}")
    print("\n📊 SUCCESS: V2 System initialization validated!")


if __name__ == "__main__":
    asyncio.run(main())
