import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))

from crackerjack.config.hooks import HookDefinition, HookStrategy, HookStage, SecurityLevel
from crackerjack.orchestration.hook_orchestrator import HookOrchestratorAdapter, HookOrchestratorSettings

async def debug_test():
    """Debug the failing test scenario."""

    # Create sample hooks like in the test
    fast_strategy = HookStrategy(
        name="fast",
        hooks=[
            HookDefinition(
                name="ruff-format",
                command=["uv", "run", "ruff", "format"],
                timeout=60,
                stage=HookStage.FAST,
                security_level=SecurityLevel.LOW,
                use_precommit_legacy=False,
            ),
            HookDefinition(
                name="ruff-check",
                command=["uv", "run", "ruff", "check"],
                timeout=60,
                stage=HookStage.FAST,
                security_level=SecurityLevel.MEDIUM,
                use_precommit_legacy=False,
            ),
        ],
        parallel=True,
        max_workers=2,
    )

    settings = HookOrchestratorSettings(execution_mode="acb", enable_caching=False)
    orchestrator = HookOrchestratorAdapter(settings=settings)

    await orchestrator.init()

    results = await orchestrator.execute_strategy(fast_strategy)

    print(f"Number of results: {len(results)}")
    for i, r in enumerate(results):
        print(f"Result {i}: id={r.id}, name={r.name}, status={r.status}")
        print(f"  issues_found: {r.issues_found}, type: {type(r.issues_found)}")
        if hasattr(r, 'issues_count'):
            print(f"  issues_count: {r.issues_count}")
        if hasattr(r, 'files_processed'):
            print(f"  files_processed: {r.files_processed}")
        print(f"  is None: {r.issues_found is None}")
        print(f"  len(): {len(r.issues_found) if hasattr(r, 'issues_found') and r.issues_found is not None else 'N/A'}")
        print("---")

    # Test the actual assertion from the failing test
    condition_results = [(r.issues_found is None or len(r.issues_found) == 0) for r in results]
    print(f"Condition results: {condition_results}")
    print(f"All pass: {all(condition_results)}")

if __name__ == "__main__":
    asyncio.run(debug_test())
