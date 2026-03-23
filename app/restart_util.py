"""Ponowne uruchomienie procesu aplikacji (np. po zmianie środowiska)."""
from __future__ import annotations

import os
import subprocess
import sys


def restart_application() -> None:
    subprocess.Popen([sys.executable, *sys.argv], cwd=os.getcwd())
    os._exit(0)
