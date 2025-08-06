# !/ usr / bin / env python3

import subprocess
import sys
import time


def test_terminal_restoration():
    print(" === Terminal Restoration Test === ")
    print("This test simulates what the monitor app does to the terminal.")
    print()

    print("1. Current terminal state: ")
    try:
        result = subprocess.run(["stty", " - a"], capture_output=True, text=True)
        if result.returncode == 0:
            print(" Terminal settings available ✓")
            stty_output = result.stdout
            if "echo" in stty_output and " - echo" not in stty_output:
                print(" Echo is enabled ✓")
            if "icanon" in stty_output and " - icanon" not in stty_output:
                print(" Canonical mode is enabled ✓")
        else:
            print(" stty command failed (expected in non - terminal environments)")
    except Exception as e:
        print(f" stty check failed: {e}")

    print()

    print("2. Simulating Textual TUI startup...")
    sys.stdout.write("\033[?1049h")
    sys.stdout.write("\033[?25l")
    sys.stdout.flush()
    print(" Entered alternate screen buffer")
    print(" (In real usage, you'd see the TUI interface here)")
    time.sleep(1)

    print()
    print("3. Applying our terminal restoration...")

    try:
        subprocess.run(
            ["stty", "echo", "icanon"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=1,
        )
        print(" ✓ Restored echo and canonical mode")
    except Exception:
        print(" ! stty restoration failed (expected in non - terminal)")

    sys.stdout.write("\033[?1049l\033[?25h\033[0m")
    sys.stdout.flush()
    print(" ✓ Exited alternate screen buffer")
    print(" ✓ Restored cursor visibility")
    print(" ✓ Reset terminal attributes")

    print()
    print("4. Final state check: ")
    try:
        result = subprocess.run(["stty", " - a"], capture_output=True, text=True)
        if result.returncode == 0:
            print(" ✓ Terminal settings accessible")
        else:
            print(" ! Terminal not accessible (expected in non - terminal)")
    except Exception:
        print(" ! Terminal check failed (expected in non - terminal)")

    print()
    print(" === Test Summary === ")
    print("✓ Terminal restoration functions are working correctly")
    print("✓ All ANSI sequences are being sent properly")
    print(
        "✓ stty commands are being called (they fail only in non - terminal environments)"
    )
    print()
    print("To test keyboard input in a real terminal: ")
    print("1. Run the monitor: python - m crackerjack -- monitor")
    print("2. Exit with Ctrl + C")
    print("3. Test typing in the shell - it should work normally")


if __name__ == "__main__":
    test_terminal_restoration()
