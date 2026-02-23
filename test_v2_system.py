#!/usr/bin/env python3
import asyncio
import tempfile
from pathlib import Path


import sys
sys.path.insert(0, str(Path(__file__).parent))

from crackerjack.agents import AnalysisCoordinator, FixerCoordinator
from crackerjack.agents.base import Issue, IssueType, Priority


async def create_sample_issues():
    fd, tmp_path = tempfile.mkstemp(suffix=".py")
    tmp_file = Path(tmp_path)

    with open(fd, 'w') as f:
        f.write("""# Sample file for testing
def hello_world():
    '''A simple function that's too long.'''
    x = 1 + 2
    y = 3
    return x + y
""")
    tmp_file.write_text("""# Sample file for testing
def hello_world():
    '''A simple function that's too long.'''
    x = 1 + 2
    y = 3
    return x + y
""")

    issues = [
        Issue(
            type=IssueType.COMPLEXITY,
            severity=Priority.HIGH,
            message="Function too complex (cyclomatic complexity > 15)",
            id="complexity_1",
            file_path=str(tmp_file),
            line_number=3,
        ),
        Issue(
            type=IssueType.FORMATTING,
            severity=Priority.MEDIUM,
            message="Line too long (exceeds 100 characters)",
            id="formatting_1",
            file_path=str(tmp_file),
            line_number=4,
        ),
        Issue(
            type=IssueType.SECURITY,
            severity=Priority.HIGH,
            message="Hardcoded password detected",
            id="security_1",
            file_path=str(tmp_file),
            line_number=5,
        ),
    ]

    print(f"Created {len(issues)} sample issues in {tmp_file}")
    return issues, tmp_file


async def test_ai_fix_system():
    print("\n" + "="*60)
    print("Testing V2 Multi-Agent AI Fix Quality System")
    print("="*60)


    issues, tmp_file = await create_sample_issues()


    from crackerjack.agents import AnalysisCoordinator, FixerCoordinator
    from crackerjack.agents.validation_coordinator import ValidationCoordinator


    analysis_coordinator = AnalysisCoordinator(max_concurrent=5)
    fixer_coordinator = FixerCoordinator()
    validation_coordinator = ValidationCoordinator(project_path=tmp_file.parent)

    print(f"\n📊 Test Setup")
    print(f"  Issues: {len(issues)}")
    print(f"  Sample file: {tmp_file}")


    print("\n🔍 Stage 1: Analysis")
    print("-" * 40)
    plans = await analysis_coordinator.analyze_issues(issues)

    print(f"  Plans created: {len(plans)}")

    for i, plan in enumerate(plans):
        print(f"  Plan {i+1}: {plan.issue_type} - {plan.risk_level} risk")
        print(f"    Changes: {len(plan.changes)}")
        print(f"    File: {plan.file_path}")


    print("\n🔧 Stage 2: Execution")
    print("-" * 40)

    results = await fixer_coordinator.execute_plans(plans)

    print(f"  Results: {len(results)}")

    success_count = sum(1 for r in results if r.success)
    print(f"  Successful fixes: {success_count}/{len(results)}")


    print("\n" + "="*60)
    print("📊 TEST SUMMARY")
    print(f"  Total issues: {len(issues)}")
    print(f"  Plans created: {len(plans)}")
    print(f"  Execution results: {len(results)}")
    print(f"  Successful fixes: {success_count}")
    print(f"  Success rate: {success_count/len(results)*100:.1f}%")
    print("\n" + "="*60)


    if success_count >= len(issues) * 0.7:
        print("✅ SUCCESS: System meets 70% success rate target")
        print("   Expected: 70-80% success rate")
        print("   Achieved: {:.1f}%".format(success_count/len(issues)*100))
    elif success_count >= len(issues) * 0.4:
        print("⚠️  PARTIAL: System approaching target")
        print("   Expected: 70-80% success rate")
        print("   Achieved: {:.1f}%".format(success_count/len(issues)*100))
    else:
        print("❌ FAILED: System below expectations")
        print("   Expected: 70-80% success rate")
        print("   Achieved: {:.1f}%".format(success_count/len(issues)*100))


    tmp_file.unlink()
    print(f"\n🧹 Cleaned up: {tmp_file}")


if __name__ == "__main__":
    asyncio.run(test_ai_fix_system())
