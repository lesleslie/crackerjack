#!/usr/bin/env python3

import sys  # noqa: I001


with open(sys.argv[1]) as f:
    content = f.read()


lines = content.split("\n")


start_line = None
for i, line in enumerate(lines, 1):
    if i >= 848 and i <= 861:

        if not line.strip():
            if "async def execute_fix_plan" in line:
                start_line = i + 1
                break


if start_line is not None:

    lines.insert(start_line, "    " + " " * 4)


with open(sys.argv[1], "w") as f:
    f.write("".join(lines))

print(f"Fixed indentation in {sys.argv[1]}")
