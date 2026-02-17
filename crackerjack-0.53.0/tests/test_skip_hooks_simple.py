#!/usr/bin/env python3
"""Simple test script to verify that -s/--skip-hooks option is available."""

import subprocess
import sys


def test_skip_hooks_option_exists() -> bool:
    """Test that the -s/--skip-hooks option exists in help output."""
    # Get help output
    result = subprocess.run([
        sys.executable, "-m", "crackerjack",
        "--help",
    ], check=False, capture_output=True, text=True)

    if result.returncode != 0:
        return False

    # Check if skip-hooks option is mentioned
    help_output = result.stdout
    if "--skip-hooks" in help_output and "-s" in help_output:
        # Show the relevant part of help
        lines = help_output.split("\n")
        for line in lines:
            if "--skip-hooks" in line or "-s" in line:
                pass
        return True
    return False


def test_skip_hooks_functionality() -> bool | None:
    """Test that skip_hooks attribute exists in OptionsProtocol."""
    try:
        # Import the OptionsProtocol
        from crackerjack.models.protocols import OptionsProtocol

        # Check if skip_hooks attribute exists
        return bool(hasattr(OptionsProtocol, "skip_hooks"))
    except Exception as e:
        return False


if __name__ == "__main__":

    success1 = test_skip_hooks_option_exists()
    success2 = test_skip_hooks_functionality()

    if success1 and success2:
        sys.exit(0)
    else:
        sys.exit(1)
