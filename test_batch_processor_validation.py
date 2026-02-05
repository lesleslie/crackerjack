#!/usr/bin/env python3

import asyncio
import logging
from pathlib import Path
from uuid import uuid4

from crackerjack.agents.base import AgentContext, Issue, IssueType, Priority
from crackerjack.services.batch_processor import get_batch_processor
from rich.console import Console

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_batch_processor():
    print("=" * 80)
    print("BatchProcessor Validation Test")
    print("=" * 80)


    project_path = Path.cwd()
    context = AgentContext(project_path)
    console = Console()

    processor = get_batch_processor(context, console, max_parallel=2)


    issues = [
        Issue(
            type=IssueType.IMPORT_ERROR,
            severity=Priority.MEDIUM,
            message="ModuleNotFoundError: No module named 'missing_module'",
            file_path="tests/test_example.py",
            line_number=10,
            id=f"issue_{uuid4().hex[:8]}",
        ),
        Issue(
            type=IssueType.IMPORT_ERROR,
            severity=Priority.MEDIUM,
            message="ImportError: cannot import 'test_utils'",
            file_path="tests/test_another.py",
            line_number=15,
            id=f"issue_{uuid4().hex[:8]}",
        ),
        Issue(
            type=IssueType.TEST_FAILURE,
            severity=Priority.HIGH,
            message="fixture 'tmp_path' not found",
            file_path="tests/test_fixtures.py",
            line_number=20,
            id=f"issue_{uuid4().hex[:8]}",
        ),
    ]

    print(f"\nTest Issues:")
    for i, issue in enumerate(issues, 1):
        print(f"  {i}. {issue.message}")
        print(f"     File: {issue.file_path}:{issue.line_number}")

    print(f"\nStarting batch processing...")
    print("-" * 80)


    result = await processor.process_batch(
        issues=issues,
        batch_id="test_batch_001",
        max_retries=1,
        parallel=True,
    )


    print("\n" + "=" * 80)
    print("Validation Results")
    print("=" * 80)


    assert result.total_issues == 3, f"Expected 3 issues, got {result.total_issues}"
    print(f"✅ Total issues processed: {result.total_issues}")


    assert result.status.value in ["completed", "partial", "failed"], \
        f"Invalid status: {result.status.value}"
    print(f"✅ Status: {result.status.value}")


    assert 0 <= result.success_rate <= 1.0, \
        f"Invalid success rate: {result.success_rate}"
    print(f"✅ Success rate: {result.success_rate:.1%}")


    assert len(result.results) == 3, f"Expected 3 results, got {len(result.results)}"
    print(f"✅ Results count: {len(result.results)}")


    for r in result.results:
        assert isinstance(r.success, bool), "success should be bool"
        assert isinstance(r.attempted, bool), "attempted should be bool"
        print(f"  - Issue: {r.issue.message[:50]}")
        print(f"    Attempted: {r.attempted}, Success: {r.success}")

    print("\n" + "=" * 80)
    print("✅ BatchProcessor validation PASSED")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(test_batch_processor())
