#!/usr/bin/env python3
"""Fix indentation in refactoring_agent.py"""

import sys

# Read the file
with open(sys.argv[1]) as f:
    content = f.read()

# Split into lines
lines = content.split("\n")

# Find the execute_fix_plan method (starts at line 849)
start_line = None
for i, line in enumerate(lines, 1):
    if i >= 848 and i <= 861:
        # Found the method
        if not line.strip():  # Skip empty lines
            if "async def execute_fix_plan" in line:
                start_line = i + 1
                break

# Add indentation to method body
if start_line is not None:
    # Insert 4 spaces at start of method body
    lines.insert(start_line, "    " + " " * 4)

    # Write back
with open(sys.argv[1], "w") as f:
    f.write("".join(lines))

print(f"Fixed indentation in {sys.argv[1]}")
