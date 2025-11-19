"""Debug script to check HookResult attributes"""

from crackerjack.models.task import HookResult

# Debug: Create a HookResult just like in our fix
result = HookResult(
    id="test-hook",
    name="test-hook",
    status="passed",
    duration=0.0,
    issues_found=[],  # Initialize with empty list
    files_processed=0,
)

print(f"result.issues_found: {result.issues_found}")
print(f"type(result.issues_found): {type(result.issues_found)}")
print(f"len(result.issues_found): {len(result.issues_found)}")
print(f"result.issues_found is None: {result.issues_found is None}")
print(f"len(result.issues_found) == 0: {len(result.issues_found) == 0}")
print(f"(result.issues_found is None or len(result.issues_found) == 0): {(result.issues_found is None or len(result.issues_found) == 0)}")