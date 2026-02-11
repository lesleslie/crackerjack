#!/usr/bin/env python

import importlib
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


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


def validate_imports() -> bool:
    failed = []
    succeeded = []

    for module_name in CRITICAL_MODULES:
        try:
            importlib.import_module(module_name)
            succeeded.append(module_name)
        except Exception as e:
            failed.append((module_name, str(e)))

    if failed:
        for _module, _error in failed:
            pass
        return False

    return True


if __name__ == "__main__":
    success = validate_imports()
    sys.exit(0 if success else 1)
