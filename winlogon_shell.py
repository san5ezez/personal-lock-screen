"""User-level Winlogon shell wrapper.

Windows starts this file instead of Explorer. After the lock screen exits,
Explorer is restored. The registry setup is performed by install_winlogon.ps1.
"""

import os
import subprocess
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
LOCK_SCREEN = BASE_DIR / "lock_screen.py"


def main() -> None:
    environment = os.environ.copy()
    environment["PERSONAL_LOCK_WINLOGON"] = "1"
    subprocess.run([sys.executable, str(LOCK_SCREEN)], cwd=str(BASE_DIR), env=environment)
    subprocess.Popen(["explorer.exe"], close_fds=True)


if __name__ == "__main__":
    main()
