from .db import init_db
from .ui.main_app import MainApp

def main():
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
