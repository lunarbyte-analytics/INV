from .app_env import load_settings
from .db import init_db
from .ui.main_app import MainApp


def main():
    load_settings()
    init_db()
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    app = MainApp()
    app.mainloop()

if __name__ == "__main__":
    main()
