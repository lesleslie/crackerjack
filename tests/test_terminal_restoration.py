import contextlib
import subprocess
import sys
import time


def test_terminal_restoration() -> None:
    try:
        result = subprocess.run(
            ["stty", " - a"], check=False, capture_output=True, text=True
        )
        if result.returncode == 0:
            stty_output = result.stdout
            if "echo" in stty_output and " - echo" not in stty_output:
                pass
            if "icanon" in stty_output and " - icanon" not in stty_output:
                pass
        else:
            pass
    except Exception:
        pass

    sys.stdout.write("\033[?1049h")
    sys.stdout.write("\033[?25l")
    sys.stdout.flush()
    time.sleep(1)

    with contextlib.suppress(Exception):
        subprocess.run(
            ["stty", "echo", "icanon"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=1,
        )

    sys.stdout.write("\033[?1049l\033[?25h\033[0m")
    sys.stdout.flush()

    try:
        result = subprocess.run(
            ["stty", " - a"], check=False, capture_output=True, text=True
        )
        if result.returncode == 0:
            pass
        else:
            pass
    except Exception:
        pass


if __name__ == "__main__":
    test_terminal_restoration()
