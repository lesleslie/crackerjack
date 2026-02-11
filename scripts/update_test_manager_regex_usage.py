#!/usr/bin/env python3

import re

with open("crackerjack/managers/test_manager.py") as f:
    content = f.read()


replacements = []


old_summary_loop = r"""        for pattern in summary_patterns:
            match = re\.search\(pattern, output\)"""
new_summary_loop = """        for compiled_pattern in SUMMARY_PATTERNS:
            match = compiled_pattern.search(output)"""
content = re.sub(old_summary_loop, new_summary_loop, content)
replacements.append("Summary patterns loop")


old_metric = (
    r"metric_match = re\.search\(metric_pattern, summary_text, re\.IGNORECASE\)"
)
new_metric = "metric_match = METRIC_PATTERN.search(summary_text)"
content = re.sub(old_metric, new_metric, content)
replacements.append("Metric pattern")


old_collected = r'collected_match = re\.search\(r"(\d+)\\s\+collected", summary_text, re\.IGNORECASE\)'
new_collected = "collected_match = COLLECTED_PATTERN.search(summary_text)"
content = re.sub(old_collected, new_collected, content)
replacements.append("Collected pattern")


old_failure_match = r'failure_match = re\.match\(r"\^\(\.\+?\)\\s\+\(FAILED\|ERROR\|SKIPPED\|SKIP\)", line\)'
new_failure_match = "failure_match = FAILURE_MATCH_PATTERN.match(line)"
content = re.sub(old_failure_match, new_failure_match, content)
replacements.append("Failure match pattern")


old_coverage = (
    r'test_path = re\.sub\(r"\\s\*\\\[\\s\\d\+\%\)\\\$", "", test_path\)\.strip\(\)'
)
new_coverage = 'test_path = COVERAGE_PERCENTAGE_PATTERN.sub("", test_path).strip()'
content = re.sub(old_coverage, new_coverage, content)
replacements.append("Coverage percentage pattern")


old_location = (
    r'location_match = re\.match\(r"\^\(\.\+?\\.py\):\(\\d\+\):\\s\*\(\.\*\)\$", line\)'
)
new_location = "location_match = LOCATION_PATTERN.match(line)"
content = re.sub(old_location, new_location, content)
replacements.append("Location pattern")


old_summary_failure = (
    r'match = re\.match\(r"\^FAILED\\s\+\(\.\+?\)\\s\+-\\s\+\(\.\+\)\$", line\)'
)
new_summary_failure = "match = SUMMARY_FAILURE_PATTERN.match(line)"
content = re.sub(old_summary_failure, new_summary_failure, content)
replacements.append("Summary failure pattern")


old_ellipsis = (
    r'error_message = re\.sub\(r"\\\.\\\.\\\$", "", error_message\)\.strip\(\)'
)
new_ellipsis = 'error_message = ELLIPSIS_PATTERN.sub("", error_message).strip()'
content = re.sub(old_ellipsis, new_ellipsis, content)
replacements.append("Ellipsis pattern")


old_failed = r'match2 = re\.search\(r"FAILED\\s\+\(\.\+?\)\\s\+-", line\)'
new_failed = "match2 = FAILED_PATTERN.search(line)"
content = re.sub(old_failed, new_failed, content)
replacements.append("FAILED pattern")


with open("crackerjack/managers/test_manager.py", "w") as f:
    f.write(content)

print(f"✓ Updated {len(replacements)} regex usages in test_manager.py:")
for i, replacement in enumerate(replacements, 1):
    print(f"  {i}. {replacement}")
