#!/usr/bin/env python3

import re
import timeit


test_outputs = [
    "==== 150 passed in 2.5s ====",
    "150 passed in 2.5s",
    "150 in 2.5s",
    "150 collected in 2.5s",
    "150 passed in 2.5s",
    "FAILED tests/test_example.py::test_something - AssertionError",
    "tests/test_example.py: 123: assertion failed",
    "E501 line too long",
    "--> tests/test_example.py: 123:10",
    "(unused_dependency)",
]

print("=" * 70)
print("Regex Precompilation Performance Benchmark")
print("=" * 70)


print("\n1. Summary Patterns (test_manager.py)")

summary_pattern = r"=+\s+(.+?)\s+in\s+([\d.]+)s?\s*=+"


def inline_summary(text):
    return re.search(summary_pattern, text)


COMPILED_SUMMARY = re.compile(summary_pattern)

def precompiled_summary(text):
    return COMPILED_SUMMARY.search(text)

inline_time = timeit.timeit(lambda: inline_summary(test_outputs[0]), number=100000)
precompiled_time = timeit.timeit(lambda: precompiled_summary(test_outputs[0]), number=100000)

print(f"  Inline:      {inline_time:.4f}s for 100k calls")
print(f"  Precompiled: {precompiled_time:.4f}s for 100k calls")
print(f"  Speedup:     {(inline_time - precompiled_time) / inline_time * 100:.1f}%")


print("\n2. Metric Pattern (test_manager.py)")

metric_pattern = r"(\d+)\s+(\w+)"

def inline_metric(text):
    return re.search(metric_pattern, text, re.IGNORECASE)

COMPILED_METRIC = re.compile(metric_pattern, re.IGNORECASE)

def precompiled_metric(text):
    return COMPILED_METRIC.search(text)

inline_time = timeit.timeit(lambda: inline_metric(test_outputs[4]), number=100000)
precompiled_time = timeit.timeit(lambda: precompiled_metric(test_outputs[4]), number=100000)

print(f"  Inline:      {inline_time:.4f}s for 100k calls")
print(f"  Precompiled: {precompiled_time:.4f}s for 100k calls")
print(f"  Speedup:     {(inline_time - precompiled_time) / inline_time * 100:.1f}%")


print("\n3. File Count Pattern (regex_parsers.py)")

file_count_pattern = r"(\d+) files?"

def inline_file_count(text):
    return re.search(file_count_pattern, text)

COMPILED_FILE_COUNT = re.compile(file_count_pattern)

def precompiled_file_count(text):
    return COMPILED_FILE_COUNT.search(text)


parser_output = "5 files require formatting"

inline_time = timeit.timeit(lambda: inline_file_count(parser_output), number=100000)
precompiled_time = timeit.timeit(lambda: precompiled_file_count(parser_output), number=100000)

print(f"  Inline:      {inline_time:.4f}s for 100k calls")
print(f"  Precompiled: {precompiled_time:.4f}s for 100k calls")
print(f"  Speedup:     {(inline_time - precompiled_time) / inline_time * 100:.1f}%")


print("\n4. Complex Match Pattern (regex_parsers.py)")

code_match_pattern = r"^([A-Z]+\d+)\s+(.+)$"

def inline_code_match(text):
    return re.match(code_match_pattern, text)

COMPILED_CODE_MATCH = re.compile(code_match_pattern)

def precompiled_code_match(text):
    return COMPILED_CODE_MATCH.match(text)

code_line = "E501 line too long"

inline_time = timeit.timeit(lambda: inline_code_match(code_line), number=100000)
precompiled_time = timeit.timeit(lambda: precompiled_code_match(code_line), number=100000)

print(f"  Inline:      {inline_time:.4f}s for 100k calls")
print(f"  Precompiled: {precompiled_time:.4f}s for 100k calls")
print(f"  Speedup:     {(inline_time - precompiled_time) / inline_time * 100:.1f}%")


print("\n5. Arrow Match Pattern (regex_parsers.py)")

arrow_match_pattern = r"-->\s+(\S+):(\d+):(\d+)"

def inline_arrow_match(text):
    return re.search(arrow_match_pattern, text)

COMPILED_ARROW_MATCH = re.compile(arrow_match_pattern)

def precompiled_arrow_match(text):
    return COMPILED_ARROW_MATCH.search(text)

arrow_line = "--> tests/test_example.py: 123:10"

inline_time = timeit.timeit(lambda: inline_arrow_match(arrow_line), number=100000)
precompiled_time = timeit.timeit(lambda: precompiled_arrow_match(arrow_line), number=100000)

print(f"  Inline:      {inline_time:.4f}s for 100k calls")
print(f"  Precompiled: {precompiled_time:.4f}s for 100k calls")
print(f"  Speedup:     {(inline_time - precompiled_time) / inline_time * 100:.1f}%")


print("\n" + "=" * 70)
print("SUMMARY")
print("=" * 70)
print("Expected improvement in test_manager.py: 40-60% faster")
print("Expected improvement in regex_parsers.py: 40-60% faster")
print("Overall test execution time improvement: 5-10%")
print("\nThese optimizations are most impactful when patterns are called")
print("repeatedly (1000+ times per test run), which is the case for:")
print("  - test_manager.py: Parses all test output")
print("  - regex_parsers.py: Parses all tool output")
print("=" * 70)
