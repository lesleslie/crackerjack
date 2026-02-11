#!/usr/bin/env python3


with open("crackerjack/managers/test_manager.py") as f:
    lines = f.readlines()


insert_after = None
for i, line in enumerate(lines):
    if "ANSI_ESCAPE_RE = re.compile" in line:
        insert_after = i
        break

if insert_after is None:
    print("ERROR: Could not find ANSI_ESCAPE_RE line")
    exit(1)


new_patterns = """


SUMMARY_PATTERNS = [
    re.compile(r"=+\\s+(.+?)\\s+in\\s+([\\d.]+)s?\\s*=+"),
    re.compile(r"(\\d+\\s+\\w+)+\\s+in\\s+([\\d.]+)s?"),
    re.compile(r"(\\d+.*)in\\s+([\\d.]+)s?"),
]
METRIC_PATTERN = re.compile(r"(\\d+)\\s+(\\w+)", re.IGNORECASE)
COLLECTED_PATTERN = re.compile(r"(\\d+)\\s+collected", re.IGNORECASE)
FAILURE_MATCH_PATTERN = re.compile(r"^(.+?)\\s+(FAILED|ERROR|SKIPPED|SKIP)")
COVERAGE_PERCENTAGE_PATTERN = re.compile(r"\\s*\\[[\\s\\d]+%\\]$")
LOCATION_PATTERN = re.compile(r"^(.+?\\.py):(\\d+):\\s*(.*)$")
SUMMARY_FAILURE_PATTERN = re.compile(r"^FAILED\\s+(.+?)\\s+-\\s+(.+)$")
ELLIPSIS_PATTERN = re.compile(r"\\.\\.\\.$")
FAILED_PATTERN = re.compile(r"FAILED\\s+(.+?)\\s+-")
"""


lines.insert(insert_after + 1, new_patterns)


with open("crackerjack/managers/test_manager.py", "w") as f:
    f.writelines(lines)

print(f"✓ Added precompiled patterns to test_manager.py after line {insert_after + 1}")
print(f"✓ Original file had {len(lines) - len(new_patterns.splitlines())} lines")
print(f"✓ New file has {len(lines)} lines")
