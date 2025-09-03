import os
import subprocess
import sys


def check_terminal_state() -> None:
    for var in ["TERM", "TERM_PROGRAM", "COLORTERM"]:
        os.environ.get(var, "Not set")

    sys.stdout.write("\033[6n")
    sys.stdout.flush()

    try:
        result = subprocess.run(
            ["stty", " - a"], check=False, capture_output=True, text=True
        )
        if result.returncode == 0:
            stty_output = result.stdout
            if "echo" in stty_output and " - echo" not in stty_output:
                pass
            else:
                pass

            if "icanon" in stty_output and " - icanon" not in stty_output:
                pass
            else:
                pass
        else:
            pass
    except Exception:
        pass

    try:
        user_input = input(" > ")
        if user_input:
            pass
        else:
            pass
    except Exception:
        pass


if __name__ == "__main__":
    check_terminal_state()
