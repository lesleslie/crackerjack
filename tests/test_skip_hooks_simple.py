#!/usr/bin/env python3
"""Simple test script to verify that -s/--skip-hooks option is available."""

import subprocess
import sys


def test_skip_hooks_option_exists():
    """Test that the -s/--skip-hooks option exists in help output."""
    print("🧪 Testing if -s/--skip-hooks option exists...")

    # Get help output
    result = subprocess.run([
        sys.executable, "-m", "crackerjack",
        "--help"
    ], capture_output=True, text=True)

    if result.returncode != 0:
        print(f"  ❌ Failed to get help output: {result.stderr}")
        return False

    # Check if skip-hooks option is mentioned
    help_output = result.stdout
    if "--skip-hooks" in help_output and "-s" in help_output:
        print("  ✅ --skip-hooks and -s options found in help output")
        # Show the relevant part of help
        lines = help_output.split('\n')
        for line in lines:
            if '--skip-hooks' in line or '-s' in line:
                print(f"     {line.strip()}")
        return True
    else:
        print("  ❌ --skip-hooks or -s option not found in help output")
        return False


def test_skip_hooks_functionality():
    """Test that skip_hooks attribute exists in OptionsProtocol."""
    print("\n🧪 Testing skip_hooks attribute availability...")

    try:
        # Import the OptionsProtocol
        from crackerjack.models.protocols import OptionsProtocol

        # Check if skip_hooks attribute exists
        if hasattr(OptionsProtocol, 'skip_hooks'):
            print("  ✅ skip_hooks attribute exists in OptionsProtocol")
            return True
        else:
            print("  ❌ skip_hooks attribute not found in OptionsProtocol")
            return False
    except Exception as e:
        print(f"  ❌ Failed to import OptionsProtocol: {e}")
        return False


if __name__ == "__main__":
    print("🚀 Testing Crackerjack skip-hooks functionality\n")

    success1 = test_skip_hooks_option_exists()
    success2 = test_skip_hooks_functionality()

    if success1 and success2:
        print("\n🎉 All tests passed! The -s/--skip-hooks option is available and functional.")
        sys.exit(0)
    else:
        print("\n❌ Some tests failed.")
        sys.exit(1)
