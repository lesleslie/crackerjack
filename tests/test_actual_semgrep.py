#!/usr/bin/env python3
"""
Test script to verify the hook output parsing with actual semgrep output.
"""

import tempfile
from pathlib import Path
from crackerjack.executors.hook_executor import HookExecutor
from rich.console import Console
from subprocess import CompletedProcess


def test_actual_semgrep_output():
    # Create a mock HookExecutor
    console = Console()
    pkg_path = Path.cwd()
    executor = HookExecutor(console, pkg_path)

    # Real semgrep output from our uvx test
    real_output = '{"version":"1.142.1","results":[],"errors":[],"paths":{"scanned":["crackerjack/executors/__init__.py","crackerjack/executors/async_hook_executor.py","crackerjack/executors/cached_hook_executor.py","crackerjack/executors/hook_executor.py","crackerjack/executors/hook_lock_manager.py","crackerjack/executors/individual_hook_executor.py","crackerjack/executors/lsp_aware_hook_executor.py","crackerjack/executors/progress_hook_executor.py","crackerjack/executors/tool_proxy.py"]},"time":{"rules":[],"rules_parse_time":0.7443020343780518,"profiling_times":{"config_time":1.739394187927246,"core_time":8.478798151016235,"ignores_time":0.0006811618804931641,"total_time":10.220367193222046},"parsing_time":{"total_time":0.0,"per_file_time":{"mean":0.0,"std_dev":0.0},"very_slow_stats":{"time_ratio":0.0,"count_ratio":0.0},"very_slow_files":[]},"scanning_time":{"total_time":12.600207328796387,"per_file_time":{"mean":1.4000230365329318,"std_dev":0.7653713795983244},"very_slow_stats":{"time_ratio":0.7006601626139328,"count_ratio":0.4444444444444444},"very_slow_files":[{"fpath":"crackerjack/executors/tool_proxy.py","ftime":1.5670270919799805},{"fpath":"crackerjack/executors/individual_hook_executor.py","ftime":1.6694810390472412},{"fpath":"crackerjack/executors/async_hook_executor.py","ftime":2.4843451976776123},{"fpath":"crackerjack/executors/hook_executor.py","ftime":3.107609987258911}]},"matching_time":{"total_time":0.0,"per_file_and_rule_time":{"mean":0.0,"std_dev":0.0},"very_slow_stats":{"time_ratio":0.0,"count_ratio":0.0},"very_slow_rules_on_files":[]},"tainting_time":{"total_time":0.0,"per_def_and_rule_time":{"mean":0.0,"std_dev":0.0},"very_slow_stats":{"time_ratio":0.0,"count_ratio":0.0},"very_slow_rules_on_defs":[]},"fixpoint_timeouts":[],"prefiltering":{"project_level_time":0.0,"file_level_time":0.0,"rules_with_project_prefilters_ratio":0.0,"rules_with_file_prefilters_ratio":0.9933774834437086,"rules_selected_ratio":0.061074319352465045,"rules_matched_ratio":0.061074319352465045},"targets":[],"total_bytes":0,"max_memory_bytes":273760448},"engine_requested":"OSS","skipped_rules":[]}'

    result = CompletedProcess(
        args=["uvx", "semgrep", "--config=p/python", "--json", "crackerjack/executors/"],
        returncode=0,
        stdout=real_output,
        stderr="Ran 151 rules on 9 files: 0 findings."
    )

    parsed = executor._parse_hook_output(result)
    print(f"Test with real semgrep output:")
    print(f"  Files processed: {parsed['files_processed']}")
    print(f"  Expected: 0 (no issues found)")
    print(f"  Result: {'PASS' if parsed['files_processed'] == 0 else 'FAIL'}")
    print(f"  Raw output preview: {real_output[:100]}...")
    print()


def test_semgrep_with_issues():
    """Test with semgrep output that has issues"""
    # Simulated output with some results
    stdout_with_issues = '{"version":"1.142.1","results":[{"path":"test_file1.py","check_id":"python.sqlalchemy.security.sql-injection.sql-injection","line":10},{"path":"test_file2.py","check_id":"python.django.security.audit.xss.audit-xss","line":15},{"path":"test_file1.py","check_id":"python.django.security.injection.runserver.runserver-bind-all-interfaces","line":8}],"errors":[],"paths":{"scanned":["test_file1.py","test_file2.py"]},"time":{}}'

    # Need to recreate the executor for this function
    console = Console()
    pkg_path = Path.cwd()
    executor = HookExecutor(console, pkg_path)

    result = CompletedProcess(
        args=["uvx", "semgrep", "--config=p/python", "--json", "."],
        returncode=1,  # Semgrep returns 1 when issues are found
        stdout=stdout_with_issues,
        stderr=""
    )

    parsed = executor._parse_hook_output(result)
    print(f"Test with semgrep output containing issues:")
    print(f"  Files processed: {parsed['files_processed']}")
    print(f"  Expected: 2 (two unique files with issues)")
    print(f"  Result: {'PASS' if parsed['files_processed'] == 2 else 'FAIL'}")
    print()


if __name__ == "__main__":
    test_actual_semgrep_output()
    test_semgrep_with_issues()
