#!/usr/bin/env python3


with open("crackerjack/parsers/regex_parsers.py") as f:
    lines = f.readlines()


insert_after = None
for i, line in enumerate(lines):
    if line.strip() == "logger = logging.getLogger(__name__)":
        insert_after = i
        break

if insert_after is None:
    print("ERROR: Could not find logger line")
    exit(1)


new_patterns = """
import re


FILE_COUNT_PATTERN = re.compile(r"(\\d+) files?")
PAREN_PATTERN = re.compile(r"\\(([^)]+)\\)")
LINE_PATTERN = re.compile(r"line (\\d+)")
CODE_MATCH_PATTERN = re.compile(r"^([A-Z]+\\d+)\\s+(.+)$")
ARROW_MATCH_PATTERN = re.compile(r"-->\\s+(\\S+):(\\d+):(\\d+)")
"""


lines.insert(insert_after + 1, new_patterns)


with open("crackerjack/parsers/regex_parsers.py", "w") as f:
    f.writelines(lines)

print(f"✓ Added precompiled patterns to regex_parsers.py after line {insert_after + 1}")


with open("crackerjack/parsers/regex_parsers.py") as f:
    content = f.read()

replacements = []


old1 = 'match = re.search(r"(\\d+) files?", output)'
new1 = "match = FILE_COUNT_PATTERN.search(output)"
if old1 in content:
    content = content.replace(old1, new1)
    replacements.append("File count pattern")


old2 = 'match = re.search(r"\\(([^)]+)\\)", line)'
new2 = "match = PAREN_PATTERN.search(line)"
if old2 in content:
    content = content.replace(old2, new2)
    replacements.append("Paren pattern")


old3 = 'match = re.search(r"line (\\d+)", message)'
new3 = "match = LINE_PATTERN.search(message)"
if old3 in content:
    content = content.replace(old3, new3)
    replacements.append("Line pattern")


old4 = 'code_match = re.match(r"^([A-Z]+\\d+)\\s+(.+)$", code_line)'
new4 = "code_match = CODE_MATCH_PATTERN.match(code_line)"
if old4 in content:
    content = content.replace(old4, new4)
    replacements.append("Code match pattern")


old5 = 'arrow_match = re.search(r"-->\\s+(\\S+):(\\d+):(\\d+)", arrow_line)'
new5 = "arrow_match = ARROW_MATCH_PATTERN.search(arrow_line)"
if old5 in content:
    content = content.replace(old5, new5)
    replacements.append("Arrow match pattern")


with open("crackerjack/parsers/regex_parsers.py", "w") as f:
    f.write(content)

print(f"✓ Updated {len(replacements)} regex usages in regex_parsers.py:")
for i, replacement in enumerate(replacements, 1):
    print(f"  {i}. {replacement}")
