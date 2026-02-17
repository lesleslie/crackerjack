#!/usr/bin/env python3

import asyncio
import logging
import re
from pathlib import Path

from crackerjack.agents.base import AgentContext, Issue, IssueType, Priority
from crackerjack.agents.dead_code_removal_agent import DeadCodeRemovalAgent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def parse_vulture_output(vulture_output: str) -> list[dict]:
    issues = []
    for line in vulture_output.strip().split("\n"):

        match = re.match(
            r"([^:]+):(\d+):\s+unused\s+(\w+)\s+'?([^']+)'?\s+\((\d+)%\s+confidence\)",
            line,
        )
        if match:
            file_path, line_number, code_type, name, confidence = match.groups()
            issues.append(
                {
                    "file_path": file_path,
                    "line_number": int(line_number),
                    "code_type": code_type,
                    "name": name,
                    "confidence": int(confidence),
                }
            )
    return issues


async def test_dead_code_removal_agent():

    print("=" * 80)
    print("DeadCodeRemovalAgent Validation Test")
    print("=" * 80)


    print("\n[Test 1] Unused import (100% confidence)")
    print("-" * 80)
    await test_single_issue(
        file_path="crackerjack/__main__.py",
        line_number=133,
        code_type="variable",
        name="full_release",
        confidence=100,
        expected_outcome="should_remove",
    )


    print("\n[Test 2] Unused function (60% confidence)")
    print("-" * 80)
    await test_single_issue(
        file_path="crackerjack/__main__.py",
        line_number=70,
        code_type="attribute",
        name="help",
        confidence=60,
        expected_outcome="should_reject_low_confidence",
    )


    print("\n[Test 3] Unused method in adapter (60% confidence)")
    print("-" * 80)
    await test_single_issue(
        file_path="crackerjack/adapters/_output_paths.py",
        line_number=23,
        code_type="method",
        name="get_output_file",
        confidence=60,
        expected_outcome="should_reject_low_confidence",
    )

    print("\n" + "=" * 80)
    print("Validation Test Complete")
    print("=" * 80)


async def test_single_issue(
    file_path: str,
    line_number: int,
    code_type: str,
    name: str,
    confidence: int,
    expected_outcome: str,
):

    issue = Issue(
        type=IssueType.DEAD_CODE,
        severity=Priority.MEDIUM,
        message=f"Unused {code_type}: '{name}' ({confidence}% confidence)",
        file_path=file_path,
        line_number=line_number,
    )

    print(f"Issue: {issue.message}")
    print(f"File: {file_path}:{line_number}")
    print(f"Expected: {expected_outcome}")


    from crackerjack.agents.base import AgentContext

    project_path = Path.cwd()
    context = AgentContext(project_path)
    agent = DeadCodeRemovalAgent(context)


    handle_confidence = await agent.can_handle(issue)
    print(f"Agent confidence: {handle_confidence:.2f}")


    file_full_path = project_path / file_path
    if file_full_path.exists():
        content = context.get_file_content(file_full_path)
        if content:
            safety_result = agent._perform_safety_checks(
                content, code_type, name, line_number
            )

            print(f"\nSafety Analysis:")
            print(f"  Safe to remove: {safety_result['safe_to_remove']}")
            print(f"  Confidence: {safety_result['confidence']:.2f}")
            print(f"  Reasons: {safety_result['reasons']}")
            if safety_result.get("recommendations"):
                print(f"  Recommendations: {safety_result['recommendations']}")


            print(f"\nAttempting fix...")
            fix_result = await agent.analyze_and_fix(issue)

            print(f"Fix result:")
            print(f"  Success: {fix_result.success}")
            print(f"  Confidence: {fix_result.confidence}")
            if fix_result.fixes_applied:
                print(f"  Fixes: {fix_result.fixes_applied}")
            if fix_result.remaining_issues:
                print(f"  Remaining issues: {fix_result.remaining_issues}")
            if fix_result.recommendations:
                print(f"  Recommendations: {fix_result.recommendations}")


            if expected_outcome == "should_remove":
                if fix_result.success:
                    print(f"\n✅ PASS: Code was successfully removed")
                else:
                    print(f"\n⚠️  PARTIAL: Agent declined (safety mechanisms working)")
            else:
                if not fix_result.success:
                    print(f"\n✅ PASS: Agent correctly rejected (low confidence or safety concern)")
                else:
                    print(f"\n⚠️  UNEXPECTED: Agent removed despite expected rejection")

    print()


if __name__ == "__main__":
    asyncio.run(test_dead_code_removal_agent())
