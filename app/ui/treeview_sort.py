"""Sortowanie ttk.Treeview po kliknięciu w nagłówek kolumny."""
from __future__ import annotations

from typing import Callable


def _sort_key(value: str, *, numeric: bool, as_date: bool):
    s = "" if value is None else str(value).strip()
    if as_date:
        # ISO / „YYYY-MM-DD …” — wystarczy porównanie tekstowe po dacie
        return (s[:19] if s else "", s.casefold())
    if numeric:
        t = s.replace(" ", "").replace(",", ".")
        try:
            return (0, float(t))
        except ValueError:
            return (1, s.casefold())
    return (0, s.casefold())


def bind_treeview_heading_sort(
    tree,
    *,
    columns: tuple[str, ...] | list[str],
    labels: dict[str, str],
    numeric_cols: set[str] | frozenset[str] | None = None,
    date_cols: set[str] | frozenset[str] | None = None,
    state_holder: dict | None = None,
) -> Callable[[str], None]:
    """
    Podpina command do nagłówków: klik = sort asc, drugi klik tej samej kolumny = desc.
    W nagłówku pokazuje strzałkę ▲/▼.
    Zwraca funkcję sortującą (można wywołać ręcznie).
    """
    numeric_cols = frozenset(numeric_cols or ())
    date_cols = frozenset(date_cols or ())
    state = state_holder if state_holder is not None else {"col": None, "reverse": False}

    def _apply_heading_texts() -> None:
        for col in columns:
            base = labels.get(col, col)
            if state["col"] == col:
                mark = " ▼" if state["reverse"] else " ▲"
                tree.heading(col, text=base + mark)
            else:
                tree.heading(col, text=base)

    def sort_by(col: str, *, toggle: bool = True) -> None:
        if toggle:
            if state["col"] == col:
                state["reverse"] = not state["reverse"]
            else:
                state["col"] = col
                state["reverse"] = False
        elif state["col"] is None:
            state["col"] = col
            state["reverse"] = False

        rows = [(tree.set(iid, col), iid) for iid in tree.get_children("")]
        rows.sort(
            key=lambda item: _sort_key(
                item[0],
                numeric=col in numeric_cols,
                as_date=col in date_cols,
            ),
            reverse=bool(state["reverse"]),
        )
        for idx, (_val, iid) in enumerate(rows):
            tree.move(iid, "", idx)
        _apply_heading_texts()

    for col in columns:
        tree.heading(col, text=labels.get(col, col), command=lambda c=col: sort_by(c))
    return sort_by
