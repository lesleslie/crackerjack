# !/ usr / bin / env python3

import os
import subprocess
import sys


def check_terminal_state():
    print(" === Terminal State Check === ")

    print("1. Terminal environment variables: ")
    for var in ["TERM", "TERM_PROGRAM", "COLORTERM"]:
        value = os.environ.get(var, "Not set")
        print(f" {var}: {value}")

    print("\n2. Basic functionality tests: ")
    print(" - Can print to stdout: ✓")

    sys.stdout.write("\033[6n")
    sys.stdout.flush()

    print(" - Terminal is responsive for output: ✓")

    try:
        result = subprocess.run(["stty", " - a"], capture_output=True, text=True)
        if result.returncode == 0:
            print(" - stty output available: ✓")

            stty_output = result.stdout
            if "echo" in stty_output and " - echo" not in stty_output:
                print(" - Echo is enabled: ✓")
            else:
                print(" - Echo is DISABLED: ❌")

            if "icanon" in stty_output and " - icanon" not in stty_output:
                print(" - Canonical mode is enabled: ✓")
            else:
                print(" - Canonical mode is DISABLED: ❌")
        else:
            print(" - stty command failed: ❌")
    except Exception as e:
        print(f" - stty check failed: {e}")

    print("\n3. Test simple input (type 'test' and press Enter): ")
    try:
        user_input = input(" > ")
        if user_input:
            print(f" Input received: '{user_input}' ✓")
        else:
            print(" No input received (empty)")
    except Exception as e:
        print(f" Input test failed: {e} ❌")


if __name__ == "__main__":
    check_terminal_state()
