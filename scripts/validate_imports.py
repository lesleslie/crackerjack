#!/usr/bin/env python
"""Validate that all crackerjack modules can be imported successfully."""

import importlib
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Critical modules that must import successfully
CRITICAL_MODULES = [
    "crackerjack.cli.facade",
    "crackerjack.cli.interactive",
    "crackerjack.cli.handlers",
    "crackerjack.cli.handlers.main_handlers",
    "crackerjack.mcp.context",
    "crackerjack.mcp.tools.core_tools",
    "crackerjack.mcp.tools.workflow_executor",
    "crackerjack.core.session_coordinator",
    "crackerjack.services.memory_optimizer",
    "crackerjack.config",
    "crackerjack.managers.test_manager",
    "crackerjack.core.autofix_coordinator",
]


def validate_imports():
    """Validate that all critical modules can be imported."""
    failed = []
    succeeded = []

    print("🔍 Validating critical module imports...\n")

    for module_name in CRITICAL_MODULES:
        try:
            importlib.import_module(module_name)
            succeeded.append(module_name)
            print(f"✅ {module_name}")
        except Exception as e:
            failed.append((module_name, str(e)))
            print(f"❌ {module_name}: {e}")

    print(
        f"\n📊 Results: {len(succeeded)}/{len(CRITICAL_MODULES)} modules imported successfully"
    )

    if failed:
        print(f"\n🔴 {len(failed)} Import Errors:")
        for module, error in failed:
            print(f"  ❌ {module}: {error}")
        return False

    print("\n✅ All critical modules imported successfully!")
    return True


if __name__ == "__main__":
    success = validate_imports()
    sys.exit(0 if success else 1)
