#!/usr/bin/env python3
"""
Debug script to understand hook execution
"""

import time
from pathlib import Path

from crackerjack.managers.hook_manager import HookManagerImpl

# Initialize hook manager
pkg_path = Path.cwd()
hook_manager = HookManagerImpl(pkg_path=pkg_path, verbose=True)

# Run fast hooks and examine the results
print("Running fast hooks...")
start_time = time.time()
results = hook_manager.run_fast_hooks()
end_time = time.time()

print(f"Total execution time: {end_time - start_time:.2f}s")
print(f"Number of hook results: {len(results)}")

for i, result in enumerate(results):
    print(f"Hook {i + 1}: {result.name}")
    print(f"  Status: {result.status}")
    print(f"  Duration: {result.duration:.2f}s")
    print(f"  Files processed: {result.files_processed}")
    print(f"  Issues found: {len(result.issues_found) if result.issues_found else 0}")
    print()
