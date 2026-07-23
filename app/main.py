"""Punkt wejścia aplikacji (uruchom z katalogu projektu: `python main.py` albo `python -m app.main`)."""
from __future__ import annotations

import sys
from pathlib import Path

# Umożliwia `python app/main.py` (bez pakietu nadrzędnego w ścieżce importów).
if __name__ == "__main__" and not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Przed importem UI: każdy tkinter.messagebox loguje na stderr [WARNING]
import app.ui.messagebox_console  # noqa: F401

from app.app_env import load_settings
from app.db import init_db
from app.ui.main_app import MainApp


def main():
    load_settings()
    init_db()
    try:
        from ctypes import windll

        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    app = MainApp()
    _apply_window_icon(app)
    app.mainloop()


def _apply_window_icon(app: MainApp) -> None:
    """Ikona okna / paska zadań (assets/inv.ico lub inv.png)."""
    root = Path(__file__).resolve().parent.parent
    ico = root / "assets" / "inv.ico"
    png = root / "assets" / "inv.png"
    try:
        if ico.is_file():
            app.iconbitmap(default=str(ico))
    except Exception:
        pass
    try:
        if png.is_file():
            import tkinter as tk

            img = tk.PhotoImage(file=str(png))
            app.iconphoto(True, img)
            app._app_icon_image = img  # referencja, żeby GC nie usunął
    except Exception:
        pass


if __name__ == "__main__":
    main()
