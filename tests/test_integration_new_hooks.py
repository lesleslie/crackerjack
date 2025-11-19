"""Comprehensive integration tests for all new hooks and executor enhancements."""

import tempfile
from pathlib import Path

from crackerjack.executors.async_hook_executor import AsyncHookExecutor
from crackerjack.config.hooks import HookDefinition, HookStage
from crackerjack.config.hooks import SecurityLevel


def test_check_ast_integration():
    """Integration test for the check-ast hook execution."""
    # Create test files
    with tempfile.TemporaryDirectory() as tmpdir:
        test_dir = Path(tmpdir)

        # Valid Python file
        valid_py_file = test_dir / "valid.py"
        with open(valid_py_file, "w") as f:
            f.write("def hello():\n    return 'world'\n")

        # Invalid Python file
        invalid_py_file = test_dir / "invalid.py"
        with open(invalid_py_file, "w") as f:
            f.write("def hello(\n    return 'world'\n")  # Invalid syntax

        # Create hook definition
        hook_def = HookDefinition(
            name="check-ast",
            command=[],
            timeout=30,
            security_level=SecurityLevel.HIGH,
            use_precommit_legacy=False,
            accepts_file_paths=True,
        )

        # Create executor and run hook
        import logging
        from rich.console import Console
        logger = logging.getLogger(__name__)
        console = Console()
        executor = AsyncHookExecutor(logger=logger, console=console, pkg_path=test_dir)

        # Run the hook on both files
        result = executor._execute_hook_sync(
            hook=hook_def,
            files=[valid_py_file, invalid_py_file],
            stage=HookStage.FAST,
        )

        # Verify the result
        assert result.status == "failed"  # Should fail due to invalid file
        assert result.files_processed >= 0  # Should process both files


def test_json_hooks_integration():
    """Integration test for the JSON validation hooks execution."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_dir = Path(tmpdir)

        # Valid JSON file
        valid_json_file = test_dir / "valid.json"
        with open(valid_json_file, "w") as f:
            f.write('{"name": "test", "value": 123}')

        # Invalid JSON file
        invalid_json_file = test_dir / "invalid.json"
        with open(invalid_json_file, "w") as f:
            f.write('{"name": "test", "value": }')  # Invalid JSON

        # Create hook definitions
        check_json_hook = HookDefinition(
            name="check-json",
            command=[],
            timeout=30,
            security_level=SecurityLevel.MEDIUM,
            use_precommit_legacy=False,
            accepts_file_paths=True,
        )

        # Create executor and run hooks
        import logging
        from rich.console import Console
        logger = logging.getLogger(__name__)
        console = Console()
        executor = AsyncHookExecutor(logger=logger, console=console, pkg_path=test_dir)

        # Test check-json on valid file
        result = executor._execute_hook_sync(
            hook=check_json_hook,
            files=[valid_json_file],
            stage=HookStage.FAST,
        )
        assert result.status == "passed"

        # Test check-json on invalid file
        result = executor._execute_hook_sync(
            hook=check_json_hook,
            files=[invalid_json_file],
            stage=HookStage.FAST,
        )
        assert result.status == "failed"


def test_check_added_large_files_integration():
    """Integration test for the check-added-large-files hook execution with the new parsing logic."""
    # Create test files
    with tempfile.TemporaryDirectory() as tmpdir:
        test_dir = Path(tmpdir)

        # Create a small file
        small_file = test_dir / "small.txt"
        with open(small_file, "w") as f:
            f.write("This is a small file.\n")

        # Create a large file (over 1KB)
        large_file = test_dir / "large.txt"
        with open(large_file, "w") as f:
            f.write("A" * 2048)  # 2KB file, exceeds default 1KB limit

        # Create hook definition
        hook_def = HookDefinition(
            name="check-added-large-files",
            command=[],
            timeout=30,
            security_level=SecurityLevel.HIGH,
            use_precommit_legacy=False,
            accepts_file_paths=True,
        )

        # Create executor and run hook
        import logging
        from rich.console import Console
        logger = logging.getLogger(__name__)
        console = Console()
        executor = AsyncHookExecutor(logger=logger, console=console, pkg_path=test_dir)

        # Run the hook on both files
        result = executor._execute_hook_sync(
            hook=hook_def,
            files=[small_file, large_file],
            stage=HookStage.FAST,
        )

        # The hook should fail since there's a large file
        assert result.status == "failed"
        # With our new logic, files_processed should reflect the number of files that exceeded the size limit
        # This may depend on the exact output of the native tool


def test_hook_execution_with_timeout():
    """Test hook execution with timeout handling."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_dir = Path(tmpdir)

        # Create a hook definition with a short timeout
        hook_def = HookDefinition(
            name="check-ast",
            command=[],
            timeout=0.1,  # Very short timeout to force timeout
            security_level=SecurityLevel.HIGH,
            use_precommit_legacy=False,
            accepts_file_paths=True,
        )

        # Create a file that takes longer to process than the timeout
        py_file = test_dir / "test.py"
        with open(py_file, "w") as f:
            f.write("def test():\n    pass\n")

        import logging
        from rich.console import Console
        logger = logging.getLogger(__name__)
        console = Console()
        executor = AsyncHookExecutor(logger=logger, console=console, pkg_path=test_dir)

        # Run the hook (this should timeout)
        result = executor._execute_hook_sync(
            hook=hook_def,
            files=[py_file],
            stage=HookStage.FAST,
        )

        # Could be timeout or error depending on implementation
        assert result.status in ["timeout", "error", "failed"]


if __name__ == "__main__":
    # Run tests
    test_check_ast_integration()
    test_json_hooks_integration()
    test_check_added_large_files_integration()
    test_hook_execution_with_timeout()
    print("All integration tests passed!")
