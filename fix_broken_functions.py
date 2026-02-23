#!/usr/bin/env python3

import re
from pathlib import Path


def fix_broken_functions(file_path: Path) -> int:
    content = file_path.read_text()
    original_content = content
    fixes = 0

    lines = content.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]

        if re.match(r"    def \w+\(", line):
            j = i + 1
            has_process_calls = False
            while j < len(lines) and not lines[j].strip().startswith("def "):
                if "self._process_" in lines[j] and "()" in lines[j]:
                    has_process_calls = True
                    break
                if lines[j].strip() and not lines[j].strip().startswith("self._"):
                    break
                j += 1

            if has_process_calls:
                k = i + 1
                while k < len(lines) and (
                    not lines[k].strip() or "self._process_" in lines[k]
                ):
                    k += 1

                del lines[i: k]
                fixes += 1

                continue

        i += 1

    content = "\n".join(lines)

    if content != original_content:
        file_path.write_text(content)
        return fixes

    return 0


def main():
    crackerjack_path = Path("crackerjack")
    total_fixes = 0

    for py_file in crackerjack_path.rglob("*.py"):
        fixes = fix_broken_functions(py_file)
        if fixes > 0:
            print(f"Fixed {fixes} broken function(s) in {py_file}")
            total_fixes += fixes

    print(f"\nTotal fixes applied: {total_fixes}")


if __name__ == "__main__":
    main()
