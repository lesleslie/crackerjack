"""Measure libcst_surgeon coverage by running tests with manual import of the module.

The project's pytest conftest pollutes sys.modules at load time, which breaks
later tests' string-form monkeypatch.setattr. To avoid that issue and also
side-step the pytest-cov vs coverage.py conflict, this script:

1. Starts coverage.
2. Imports the module under test.
3. Runs the test functions directly via importlib + unittest-style discovery.

It manually loads the test module to avoid pytest's conftest chain.
"""
from __future__ import annotations

import coverage
import importlib
import sys
import traceback

# 1. Start coverage BEFORE any imports
cov = coverage.Coverage(
    source=["crackerjack.agents.helpers.ast_transform.surgeons.libcst_surgeon"],
)
cov.start()

# 2. Import the module under test
mod = importlib.import_module(
    "crackerjack.agents.helpers.ast_transform.surgeons.libcst_surgeon"
)
print(f"Module loaded: {mod.__name__}", file=sys.stderr)

# 3. Load and run test module via importlib
spec = importlib.util.spec_from_file_location(
    "_test_libcst_surgeon",
    "/Users/les/Projects/crackerjack/tests/unit/agents/helpers/ast_transform/surgeons/test_libcst_surgeon.py",
)
test_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(test_mod)
print(f"Test module loaded: {test_mod.__name__}", file=sys.stderr)

# 4. Discover and run all test_* functions
test_funcs = []
for name in dir(test_mod):
    if name.startswith("Test"):
        cls = getattr(test_mod, name)
        if isinstance(cls, type):
            # gather test methods
            for mname in dir(cls):
                if mname.startswith("test_"):
                    test_funcs.append((f"{name}.{mname}", cls, mname))

print(f"Discovered {len(test_funcs)} tests", file=sys.stderr)

passed = failed = 0
errors: list[str] = []
for qualname, cls, mname in test_funcs:
    inst = cls()
    method = getattr(inst, mname)
    try:
        method()
        passed += 1
    except Exception:
        failed += 1
        errors.append(qualname)
        traceback.print_exc()

print(f"\n=== {passed} passed, {failed} failed ===", file=sys.stderr)
if errors:
    print("FAILURES:", file=sys.stderr)
    for e in errors:
        print(f"  {e}", file=sys.stderr)

cov.stop()
cov.save()

print("\n=== COVERAGE REPORT ===", file=sys.stderr)
cov.report()
