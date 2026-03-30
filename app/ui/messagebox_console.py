"""Każdy komunikat z okienka messagebox jest powielany na stderr z prefiksem [WARNING]."""
from __future__ import annotations

import sys
import tkinter.messagebox as _mb


def _log_popup(title: str, message: str | None) -> None:
    t = (title or "").strip()
    m = (message or "").replace("\r\n", "\n").rstrip()
    if m:
        print(f"[WARNING] {t}: {m}", file=sys.stderr, flush=True)
    else:
        print(f"[WARNING] {t}", file=sys.stderr, flush=True)


def _wrap(name: str):
    orig = getattr(_mb, name)

    def wrapped(*args, **kwargs):
        title = kwargs.get("title")
        if title is None and len(args) >= 1:
            title = args[0]
        message = kwargs.get("message")
        if message is None and len(args) >= 2:
            message = args[1]
        _log_popup(str(title or ""), str(message) if message is not None else None)
        return orig(*args, **kwargs)

    wrapped.__name__ = name
    wrapped.__doc__ = getattr(orig, "__doc__", None)
    return wrapped


def _patch() -> None:
    for name in (
        "showinfo",
        "showwarning",
        "showerror",
        "askquestion",
        "askokcancel",
        "askyesno",
        "askretrycancel",
    ):
        if hasattr(_mb, name):
            setattr(_mb, name, _wrap(name))


_patch()
