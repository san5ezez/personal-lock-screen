"""User-level Winlogon shell wrapper.

Windows starts this file instead of Explorer. After the lock screen exits,
Explorer is restored. The registry setup is performed by install_winlogon.ps1.
"""

import os
import subprocess
import sys
import time
from pathlib import Path


if getattr(sys, "frozen", False):
    # In a PyInstaller one-file executable __file__ points to a temporary
    # extraction directory. The installed files live beside sys.executable.
    BASE_DIR = Path(sys.executable).resolve().parent
else:
    BASE_DIR = Path(__file__).resolve().parent
LOCK_SCREEN_SCRIPT = BASE_DIR / "lock_screen.py"
if BASE_DIR.name.lower() == "winlogon_shell":
    LOCK_SCREEN_EXE = BASE_DIR.parent / "lock_screen" / "lock_screen.exe"
else:
    LOCK_SCREEN_EXE = BASE_DIR / "lock_screen" / "lock_screen.exe"
LEGACY_LOCK_SCREEN_EXE = BASE_DIR / "lock_screen.exe"


def main() -> None:
    environment = os.environ.copy()
    environment["PERSONAL_LOCK_WINLOGON"] = "1"
    if LOCK_SCREEN_EXE.exists():
        command = [str(LOCK_SCREEN_EXE)]
    elif LEGACY_LOCK_SCREEN_EXE.exists():
        command = [str(LEGACY_LOCK_SCREEN_EXE)]
    elif LOCK_SCREEN_SCRIPT.exists():
        command = [sys.executable, str(LOCK_SCREEN_SCRIPT)]
    else:
        subprocess.Popen(["explorer.exe"], close_fds=True)
        return

    # Never allow a malformed packaged path to launch this shell wrapper again.
    if Path(command[0]).resolve() == Path(sys.executable).resolve():
        subprocess.Popen(["explorer.exe"], close_fds=True)
        return

    failures = 0
    while True:
        result = subprocess.run(command, cwd=str(BASE_DIR), env=environment)
        if result.returncode == 0:
            subprocess.Popen(["explorer.exe"], close_fds=True)
            return
        # A crash or forced termination must not be treated as authorization.
        failures += 1
        if failures >= 3:
            subprocess.Popen(["explorer.exe"], close_fds=True)
            return
        time.sleep(1)


if __name__ == "__main__":
    main()
