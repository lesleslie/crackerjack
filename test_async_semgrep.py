#!/usr/bin/env python3
"""
Test script to verify the async hook executor semgrep parsing works correctly.
"""

from crackerjack.executors.async_hook_executor import AsyncHookExecutor
from acb.console import Console
from pathlib import Path


def test_async_semgrep_parsing():
    console = Console()
    pkg_path = Path.cwd()
    executor = AsyncHookExecutor(console, pkg_path)

    # Real semgrep JSON output with no issues (from our uvx test)
    real_output = '{"version":"1.142.1","results":[],"errors":[],"paths":{"scanned":["crackerjack/executors/__init__.py","crackerjack/executors/async_hook_executor.py","crackerjack/executors/cached_hook_executor.py","crackerjack/executors/hook_executor.py","crackerjack/executors/hook_lock_manager.py","crackerjack/executors/individual_hook_executor.py","crackerjack/executors/lsp_aware_hook_executor.py","crackerjack/executors/progress_hook_executor.py","crackerjack/executors/tool_proxy.py"]},"time":{"rules":[],"rules_parse_time":0.7443020343780518,"profiling_times":{"config_time":1.739394187927246,"core_time":8.478798151016235,"ignores_time":0.0006811618804931641,"total_time":10.220367193222046},"parsing_time":{"total_time":0.0,"per_file_time":{"mean":0.0,"std_dev":0.0},"very_slow_stats":{"time_ratio":0.0,"count_ratio":0.0},"very_slow_files":[]},"scanning_time":{"total_time":12.600207328796387,"per_file_time":{"mean":1.4000230365329318,"std_dev":0.7653713795983244},"very_slow_stats":{"time_ratio":0.7006601626139328,"count_ratio":0.4444444444444444},"very_slow_files":[{"fpath":"crackerjack/executors/tool_proxy.py","ftime":1.5670270919799805},{"fpath":"crackerjack/executors/individual_hook_executor.py","ftime":1.6694810390472412},{"fpath":"crackerjack/executors/async_hook_executor.py","ftime":2.4843451976776123},{"fpath":"crackerjack/executors/hook_executor.py","ftime":3.107609987258911}]},"matching_time":{"total_time":0.0,"per_file_and_rule_time":{"mean":0.0,"std_dev":0.0},"very_slow_stats":{"time_ratio":0.0,"count_ratio":0.0},"very_slow_rules_on_files":[]},"tainting_time":{"total_time":0.0,"per_def_and_rule_time":{"mean":0.0,"std_dev":0.0},"very_slow_stats":{"time_ratio":0.0,"count_ratio":0.0},"very_slow_rules_on_defs":[]},"fixpoint_timeouts":[],"prefiltering":{"project_level_time":0.0,"file_level_time":0.0,"rules_with_project_prefilters_ratio":0.0,"rules_with_file_prefilters_ratio":0.9933774834437086,"rules_selected_ratio":0.061074319352465045,"rules_matched_ratio":0.061074319352465045},"targets":[],"total_bytes":0,"max_memory_bytes":273760448},"engine_requested":"OSS","skipped_rules":[]}'

    print(f"Testing async executor semgrep parsing with real output...")
    parsed = executor._parse_semgrep_output_async(real_output)
    print(f"  Files processed: {parsed}")
    print(f"  Expected: 0 (no issues found)")
    print(f"  Result: {'PASS' if parsed == 0 else 'FAIL'}")
    print()

    # Test with semgrep output that has issues
    output_with_issues = '{"version":"1.142.1","results":[{"path":"file1.py","check_id":"test-rule","line":10},{"path":"file2.py","check_id":"test-rule","line":20},{"path":"file1.py","check_id":"another-rule","line":15}],"errors":[],"paths":{"scanned":["file1.py","file2.py","file3.py"]}}'

    parsed_with_issues = executor._parse_semgrep_output_async(output_with_issues)
    print(f"Testing async executor semgrep parsing with issues...")
    print(f"  Files processed: {parsed_with_issues}")
    print(f"  Expected: 2 (two unique files with issues)")
    print(f"  Result: {'PASS' if parsed_with_issues == 2 else 'FAIL'}")
    print()

    # Test with the generic parsing method to see the difference
    result_with_generic = executor._parse_hook_output(0, real_output, "not-semgrep")
    result_with_semgrep_special = executor._parse_hook_output(0, real_output, "semgrep")
    print(f"Testing parsing behavior:")
    print(f"  Generic parsing for semgrep output: {result_with_generic['files_processed']}")
    print(f"  Semgrep-specific parsing: {result_with_semgrep_special['files_processed']}")
    print(f"  Difference: {'PASS - semgrep logic correctly returns 0' if result_with_semgrep_special['files_processed'] == 0 and result_with_generic['files_processed'] != 0 else 'MAYBE - both might return 0'}")
    print()


if __name__ == "__main__":
    test_async_semgrep_parsing()
