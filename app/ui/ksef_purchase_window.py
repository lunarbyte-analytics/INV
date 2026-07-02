"""Okno: lista faktur zakupowych z KSeF (Subject2) i pobieranie XML."""
from __future__ import annotations

import threading
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any

import tkinter as tk
from tkcalendar import DateEntry

from ..app_env import get_context_organization_id, get_ksef_nip, get_ksef_token
from ..ksef.env_normalize import normalize_ksef_nip, normalize_ksef_token
from ..ksef.fa_import import import_fa_purchase_xml_to_db, import_fa_purchase_xml_file
from ..ksef.invoice_submit import format_ksef_error
from ..ksef.purchase_fetch import (
    download_invoice_xml,
    format_invoice_row,
    max_range_days_warning,
    query_purchase_invoices_metadata,
)
from ..ksef.auth_flow import obtain_access_token
from ..ksef.client import _effective_base_url

_waw_cache: Any = None


def _waw_tz():
    """Europe/Warsaw; na Windows wymaga pakietu `tzdata` (patrz requirements.txt)."""
    global _waw_cache
    if _waw_cache is None:
        try:
            from zoneinfo import ZoneInfo

            _waw_cache = ZoneInfo("Europe/Warsaw")
        except Exception:
            _waw_cache = timezone(timedelta(hours=1))
    return _waw_cache


def _default_dates() -> tuple[date, date]:
    now = datetime.now(_waw_tz())
    start = (now - timedelta(days=30)).replace(hour=0, minute=0, second=0, microsecond=0)
    return start.date(), now.date()


def _waw_datetime_from_date(d: date, *, end_of_day: bool) -> datetime:
    """Początek / koniec dnia w strefie Europe/Warsaw (jak wcześniej _parse_day dla YYYY-MM-DD)."""
    if end_of_day:
        return datetime(d.year, d.month, d.day, 23, 59, 59, 0, tzinfo=_waw_tz())
    return datetime(d.year, d.month, d.day, 0, 0, 0, 0, tzinfo=_waw_tz())


def _to_ksef_iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_waw_tz())
    u = dt.astimezone(timezone.utc).replace(microsecond=0)
    return u.strftime("%Y-%m-%dT%H:%M:%S") + "Z"


def _iter_ksef_date_chunks(
    from_dt: datetime,
    to_dt: datetime,
    *,
    max_months: int = 3,
) -> list[tuple[datetime, datetime]]:
    """
    KSeF waliduje dateRange (metadata) do maks. 3 miesięcy.
    Dzielimy na bezpieczne kawałki <= max_months miesięcy (kalendarzowo).
    """
    if from_dt.tzinfo is None:
        from_dt = from_dt.replace(tzinfo=_waw_tz())
    if to_dt.tzinfo is None:
        to_dt = to_dt.replace(tzinfo=_waw_tz())
    if to_dt < from_dt:
        return []

    def _days_in_month(y: int, m: int) -> int:
        if m == 12:
            nxt = date(y + 1, 1, 1)
        else:
            nxt = date(y, m + 1, 1)
        cur = date(y, m, 1)
        return (nxt - cur).days

    def _add_months(dt: datetime, months: int) -> datetime:
        y = dt.year
        m = dt.month + months
        y += (m - 1) // 12
        m = ((m - 1) % 12) + 1
        d = min(dt.day, _days_in_month(y, m))
        return datetime(y, m, d, dt.hour, dt.minute, dt.second, dt.microsecond, tzinfo=dt.tzinfo)

    chunks: list[tuple[datetime, datetime]] = []
    cur = from_dt
    while cur <= to_dt:
        # Koniec kawałka: tuż przed chwilą "cur + max_months miesięcy"
        next_cut = _add_months(cur, max_months)
        end = min(to_dt, next_cut - timedelta(seconds=1))
        chunks.append((cur, end))
        cur = end + timedelta(seconds=1)
    return chunks


def _ksef_range_exceeds_months(from_dt: datetime, to_dt: datetime, *, max_months: int = 3) -> bool:
    """True jeśli zakres przekracza max_months miesięcy (kalendarzowo)."""
    if from_dt.tzinfo is None:
        from_dt = from_dt.replace(tzinfo=_waw_tz())
    if to_dt.tzinfo is None:
        to_dt = to_dt.replace(tzinfo=_waw_tz())
    if to_dt < from_dt:
        return False
    # Zakres jest OK jeśli to_dt <= (from_dt + max_months miesięcy - 1 sekunda).
    next_cut = _iter_ksef_date_chunks(from_dt, to_dt, max_months=max_months)
    # Jeżeli mamy więcej niż 1 kawałek, to znaczy że przekracza limit.
    return len(next_cut) > 1


class KsefPurchaseWindow(tk.Toplevel):
    def __init__(self, master=None):
        super().__init__(master)
        self.title("KSeF — faktury zakupowe")
        self.geometry("1020x560")
        self.minsize(800, 420)

        self._base_url = _effective_base_url(None)
        # pageOffset w API = indeks strony (0, 1, 2…). Bieżąca strona w tabeli (jedna strona na raz).
        self._current_page = -1  # -1 = jeszcze nie pobrano listy
        self._page_size = 50
        self._has_more = False  # z ostatniej odpowiedzi: czy jest kolejna strona w API
        self._date_type = tk.StringVar(value="PermanentStorage")
        self._sort_order = tk.StringVar(value="Desc")

        frm = ttk.Frame(self, padding=12)
        frm.pack(fill=tk.BOTH, expand=True)

        help_row = ttk.Frame(frm)
        help_row.pack(fill=tk.X, anchor="w")
        btn_help = ttk.Button(help_row, text="?", width=3, command=self._show_purchase_help)
        btn_help.pack(side=tk.LEFT)
        try:
            btn_help.configure(cursor="hand2")
        except tk.TclError:
            pass

        row1 = ttk.Frame(frm)
        row1.pack(fill=tk.X, pady=(10, 4))
        df, dt = _default_dates()
        _cal_kw = {"firstweekday": "monday"}
        ttk.Label(row1, text="Data od:").pack(side=tk.LEFT)
        self._de_from = DateEntry(
            row1,
            width=12,
            date_pattern="yyyy-mm-dd",
            calendar_kw=_cal_kw,
        )
        self._de_from.set_date(df)
        self._de_from.pack(side=tk.LEFT, padx=(6, 16))
        ttk.Label(row1, text="Data do:").pack(side=tk.LEFT)
        self._de_to = DateEntry(
            row1,
            width=12,
            date_pattern="yyyy-mm-dd",
            calendar_kw=_cal_kw,
        )
        self._de_to.set_date(dt)
        self._de_to.pack(side=tk.LEFT, padx=(6, 16))

        ttk.Label(row1, text="Typ daty:").pack(side=tk.LEFT)
        self._cb_date_type = ttk.Combobox(
            row1,
            textvariable=self._date_type,
            values=("PermanentStorage", "Invoicing", "Issue"),
            width=18,
            state="readonly",
        )
        self._cb_date_type.pack(side=tk.LEFT, padx=(6, 16))

        ttk.Label(row1, text="Sort.:").pack(side=tk.LEFT)
        ttk.Combobox(
            row1,
            textvariable=self._sort_order,
            values=("Desc", "Asc"),
            width=6,
            state="readonly",
        ).pack(side=tk.LEFT, padx=6)

        row2 = ttk.Frame(frm)
        row2.pack(fill=tk.X, pady=(4, 8))
        ttk.Label(row2, text=f"API: {self._base_url}", font=("Segoe UI", 8), foreground="#666").pack(
            side=tk.LEFT
        )
        ttk.Label(row2, text="Rozm. strony:").pack(side=tk.LEFT, padx=(24, 0))
        self._var_page_size = tk.StringVar(value="50")
        ttk.Spinbox(row2, from_=10, to=250, textvariable=self._var_page_size, width=6).pack(
            side=tk.LEFT, padx=6
        )

        btn_row = ttk.Frame(frm)
        btn_row.pack(fill=tk.X)
        ttk.Button(btn_row, text="Pobierz listę (od nowa)", command=self._on_fetch_first).pack(
            side=tk.LEFT
        )
        ttk.Label(btn_row, text="  Strony:").pack(side=tk.LEFT, padx=(12, 4))
        self._btn_prev = ttk.Button(
            btn_row,
            text="<",
            width=3,
            command=self._on_page_prev,
            state=tk.DISABLED,
        )
        self._btn_prev.pack(side=tk.LEFT)
        self._lbl_page = ttk.Label(btn_row, text="—", width=12, anchor=tk.CENTER)
        self._lbl_page.pack(side=tk.LEFT, padx=4)
        self._btn_next = ttk.Button(
            btn_row,
            text=">",
            width=3,
            command=self._on_page_next,
            state=tk.DISABLED,
        )
        self._btn_next.pack(side=tk.LEFT)
        for _bn in (self._btn_prev, self._btn_next):
            try:
                _bn.configure(cursor="hand2")
            except tk.TclError:
                pass
        ttk.Button(
            btn_row,
            text="Pobierz XML zaznaczonych…",
            command=self._on_download_selected,
        ).pack(side=tk.LEFT, padx=(16, 0))
        ttk.Button(
            btn_row,
            text="Importuj zaznaczone do bazy",
            command=self._on_import_selected_to_db,
        ).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(
            btn_row,
            text="Importuj wszystkie dokumenty",
            command=self._on_import_all_in_range,
        ).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(
            btn_row,
            text="Importuj plik XML z dysku…",
            command=self._on_import_xml_files,
        ).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(btn_row, text="Zamknij", command=self.destroy).pack(side=tk.RIGHT)

        self._status = tk.StringVar(value="Ustaw zakres dat i kliknij „Pobierz listę”.")
        ttk.Label(frm, textvariable=self._status, font=("Segoe UI", 9)).pack(anchor="w", pady=(8, 4))

        cols = (
            "ksefNumber",
            "invoiceNumber",
            "issueDate",
            "sellerNip",
            "sellerName",
            "grossAmount",
            "currency",
        )
        table_frame = ttk.Frame(frm)
        table_frame.pack(fill=tk.BOTH, expand=True)
        self._tree = ttk.Treeview(
            table_frame,
            columns=cols,
            show="headings",
            selectmode="extended",
            height=14,
        )
        headings = {
            "ksefNumber": "Numer KSeF",
            "invoiceNumber": "Nr faktury",
            "issueDate": "Data wyst.",
            "sellerNip": "NIP sprzedawcy",
            "sellerName": "Sprzedawca",
            "grossAmount": "Brutto",
            "currency": "Waluta",
        }
        widths = {
            "ksefNumber": 280,
            "invoiceNumber": 160,
            "issueDate": 100,
            "sellerNip": 100,
            "sellerName": 220,
            "grossAmount": 90,
            "currency": 60,
        }
        for c in cols:
            self._tree.heading(c, text=headings[c])
            self._tree.column(c, width=widths[c], anchor="w")

        yscroll = ttk.Scrollbar(table_frame, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=yscroll.set)
        self._tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        yscroll.pack(side=tk.RIGHT, fill=tk.Y)
        self._tree.bind("<Button-3>", self._on_tree_right_click)

        self._busy = False

    def _show_purchase_help(self) -> None:
        win = tk.Toplevel(self)
        win.title("Pomoc — faktury zakupowe z KSeF")
        win.transient(self)
        win.resizable(False, False)
        hf = ttk.Frame(win, padding=14)
        hf.pack(fill=tk.BOTH, expand=True)
        msg = (
            "Wyszukiwanie faktur, w których Twój NIP (KSEF_NIP) jest nabywcą (Subject2). "
            "Wymagane uprawnienie InvoiceRead na tokenie oraz konfiguracja w Plik → Ustawienia integracji… "
            "(lub KSEF_TOKEN i KSEF_NIP).\n\n"
            "Import do bazy: na głównym oknie wybierz „Moja firma (kontekst)” — wtedy nabywca z XML "
            "musi pasować do tej organizacji (NIP)."
        )
        ttk.Label(hf, text=msg, wraplength=440, justify=tk.LEFT).pack(anchor=tk.W)
        ttk.Button(hf, text="Zamknij", command=win.destroy).pack(pady=(14, 0))
        win.bind("<Escape>", lambda e: win.destroy())
        win.grab_set()
        win.focus_set()

    def _get_token_nip(self) -> tuple[str, str]:
        tok = normalize_ksef_token(get_ksef_token())
        nip = normalize_ksef_nip(get_ksef_nip())
        return tok, nip

    def _parse_page_size(self) -> int:
        try:
            n = int(self._var_page_size.get().strip())
        except ValueError:
            return 50
        return max(10, min(250, n))

    def _on_fetch_first(self) -> None:
        if self._busy:
            return
        self._fetch_page_at(0)

    def _on_page_prev(self) -> None:
        if self._busy or self._current_page <= 0:
            return
        self._fetch_page_at(self._current_page - 1)

    def _on_page_next(self) -> None:
        if self._busy or not self._has_more:
            return
        self._fetch_page_at(self._current_page + 1)

    def _update_nav_state(self) -> None:
        if self._busy:
            self._btn_prev.configure(state=tk.DISABLED)
            self._btn_next.configure(state=tk.DISABLED)
            self._lbl_page.configure(text="…")
            return
        if self._current_page < 0:
            self._btn_prev.configure(state=tk.DISABLED)
            self._btn_next.configure(state=tk.DISABLED)
            self._lbl_page.configure(text="—")
            return
        self._btn_prev.configure(state=tk.NORMAL if self._current_page > 0 else tk.DISABLED)
        self._btn_next.configure(state=tk.NORMAL if self._has_more else tk.DISABLED)
        self._lbl_page.configure(text=str(self._current_page + 1))

    def _fetch_page_at(self, page_idx: int) -> None:
        tok, nip = self._get_token_nip()
        if not tok or not nip:
            messagebox.showwarning(
                "KSeF",
                "Ustaw KSeF w menu Plik → Ustawienia integracji… lub zmienne KSEF_TOKEN i KSEF_NIP.",
                parent=self,
            )
            return

        d_from = _waw_datetime_from_date(self._de_from.get_date(), end_of_day=False)
        d_to = _waw_datetime_from_date(self._de_to.get_date(), end_of_day=True)

        # API KSeF odrzuca dateRange > 3 miesiące (kalendarzowo).
        if _ksef_range_exceeds_months(d_from, d_to, max_months=3):
            messagebox.showerror(
                "Zakres dat",
                "Zakres dat przekracza 3 miesiące — API KSeF odrzuci zapytanie metadanych.\n\n"
                "Zawęź okres (albo użyj importu „wszystkich”, który dzieli zakres na części).",
                parent=self,
            )
            return

        from_iso = _to_ksef_iso(d_from)
        to_iso = _to_ksef_iso(d_to)
        self._page_size = self._parse_page_size()

        self._busy = True
        self._status.set("Łączenie z KSeF…")
        self._update_nav_state()
        base = self._base_url
        psize = self._page_size
        d_type = self._date_type.get()
        sort_o = self._sort_order.get()

        def work():
            try:
                access = obtain_access_token(base, ksef_token=tok, nip=nip)
                data = query_purchase_invoices_metadata(
                    base,
                    access,
                    date_from_iso=from_iso,
                    date_to_iso=to_iso,
                    date_type=d_type,
                    sort_order=sort_o,
                    page_index=page_idx,
                    page_size=psize,
                )
                invoices: list[dict[str, Any]] = list(data.get("invoices") or [])
                hm = data.get("hasMore")
                if hm is None:
                    hm = data.get("has_more")
                has_more = bool(hm)
                trunc = bool(data.get("isTruncated"))
                hwm = data.get("permanentStorageHwmDate")

                def done():
                    self._apply_fetch_result(invoices, has_more, trunc, hwm, page_idx, psize)

                self.after(0, done)
            except Exception as e:
                msg = format_ksef_error(e)

                def fail():
                    self._busy = False
                    self._status.set("Błąd.")
                    self._update_nav_state()
                    messagebox.showerror("KSeF", msg, parent=self)

                self.after(0, fail)

        threading.Thread(target=work, daemon=True).start()

    def _apply_fetch_result(
        self,
        invoices: list[dict[str, Any]],
        has_more: bool,
        is_truncated: bool,
        hwm: Any,
        page_idx: int,
        psize: int,
    ) -> None:
        self._busy = False
        for i in self._tree.get_children():
            self._tree.delete(i)
        for inv in invoices:
            r = format_invoice_row(inv)
            gross = r["grossAmount"]
            gtxt = f"{gross:.2f}" if isinstance(gross, (int, float)) else str(gross or "")
            self._tree.insert(
                "",
                "end",
                values=(
                    r["ksefNumber"],
                    r["invoiceNumber"],
                    r["issueDate"],
                    r["sellerNip"],
                    (r["sellerName"] or "")[:80],
                    gtxt,
                    r["currency"],
                ),
            )

        self._has_more = has_more
        self._current_page = page_idx
        self._update_nav_state()
        extra = []
        if is_truncated:
            extra.append("isTruncated=true — zawęż daty lub kontynuuj wg dokumentacji API.")
        if hwm:
            extra.append(f"HWM: {hwm}")
        self._status.set(
            f"Strona {page_idx + 1} (po {psize} na stronę): {len(invoices)} faktur w widoku. "
            f"{'Dostępna następna strona (>)' if has_more else 'Ostatnia strona (hasMore=false).'}"
            + (" " + " ".join(extra) if extra else "")
        )

    def _on_tree_right_click(self, event) -> None:
        row = self._tree.identify_row(event.y)
        if row:
            if row not in self._tree.selection():
                self._tree.selection_set(row)
        else:
            return

        menu = tk.Menu(self, tearoff=0)
        menu.add_command(
            label="Kopiuj numer faktury",
            command=self._copy_invoice_number_to_clipboard,
        )
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _copy_invoice_number_to_clipboard(self) -> None:
        sel = self._tree.selection()
        if not sel:
            messagebox.showinfo("KSeF", "Zaznacz wiersz faktury.", parent=self)
            return

        numbers: list[str] = []
        for iid in sel:
            vals = self._tree.item(iid, "values")
            if not vals or len(vals) < 2:
                continue
            num = str(vals[1]).strip()
            if num:
                numbers.append(num)

        if not numbers:
            messagebox.showinfo("KSeF", "Brak numeru faktury w zaznaczonym wierszu.", parent=self)
            return

        self.clipboard_clear()
        self.clipboard_append("\n".join(numbers))
        self.update_idletasks()
        self._status.set(
            f"Skopiowano numer faktury: {numbers[0]}"
            + (f" (+{len(numbers) - 1})" if len(numbers) > 1 else "")
        )

    def _on_download_selected(self) -> None:
        if self._busy:
            return
        sel = self._tree.selection()
        if not sel:
            messagebox.showinfo("KSeF", "Zaznacz co najmniej jeden wiersz.", parent=self)
            return
        folder = filedialog.askdirectory(title="Folder zapisu plików XML")
        if not folder:
            return
        out_dir = Path(folder)
        tok, nip = self._get_token_nip()
        if not tok or not nip:
            messagebox.showwarning(
                "KSeF",
                "Brak tokenu lub NIP. Ustaw w Plik → Ustawienia integracji… lub KSEF_TOKEN / KSEF_NIP.",
                parent=self,
            )
            return

        rows: list[str] = []
        for iid in sel:
            v = self._tree.item(iid, "values")
            if v:
                rows.append(str(v[0]))

        self._busy = True
        self._status.set(f"Pobieranie {len(rows)} plików…")
        base = self._base_url

        def work():
            errors: list[str] = []
            ok_n = 0
            try:
                access = obtain_access_token(base, ksef_token=tok, nip=nip)
                for kn in rows:
                    try:
                        xml = download_invoice_xml(base, access, kn)
                        safe = kn.replace("/", "-").replace("\\", "-")
                        path = out_dir / f"{safe}.xml"
                        path.write_bytes(xml)
                        ok_n += 1
                    except Exception as e:
                        errors.append(f"{kn}: {format_ksef_error(e)}")
            finally:

                def finish():
                    self._busy = False
                    self._status.set(f"Zapisano {ok_n} plików do {out_dir}")
                    if errors:
                        messagebox.showwarning(
                            "Częściowy wynik",
                            f"Zapisano: {ok_n}.\n\nBłędy:\n" + "\n".join(errors[:12]),
                            parent=self,
                        )
                    else:
                        messagebox.showinfo("KSeF", f"Zapisano {ok_n} plików XML.", parent=self)

                self.after(0, finish)

        threading.Thread(target=work, daemon=True).start()

    def _refresh_main_invoice_list(self) -> None:
        m = self.master
        if m is not None and hasattr(m, "refresh_invoice_list"):
            try:
                m.refresh_invoice_list()
            except Exception:
                pass

    def _on_import_selected_to_db(self) -> None:
        if self._busy:
            return
        sel = self._tree.selection()
        if not sel:
            messagebox.showinfo("Import", "Zaznacz co najmniej jeden wiersz.", parent=self)
            return
        tok, nip = self._get_token_nip()
        if not tok or not nip:
            messagebox.showwarning(
                "KSeF",
                "Brak tokenu lub NIP. Ustaw w Plik → Ustawienia integracji… lub KSEF_TOKEN / KSEF_NIP.",
                parent=self,
            )
            return

        rows: list[str] = []
        for iid in sel:
            v = self._tree.item(iid, "values")
            if v:
                rows.append(str(v[0]))

        ctx = get_context_organization_id()
        if ctx is None:
            if not messagebox.askyesno(
                "Import",
                "Na głównym oknie nie wybrano „Moja firma (kontekst)”. "
                "Import utworzy lub dopasuje organizację nabywcy po NIP z XML.\n\nKontynuować?",
                parent=self,
            ):
                return

        self._busy = True
        self._status.set(f"Import do bazy ({len(rows)} faktur)…")
        base = self._base_url

        def work():
            ok_lines: list[str] = []
            err_lines: list[str] = []
            try:
                access = obtain_access_token(base, ksef_token=tok, nip=nip)
                for kn in rows:
                    try:
                        xml = download_invoice_xml(base, access, kn)
                        iid, notes = import_fa_purchase_xml_to_db(
                            xml,
                            buyer_org_id=ctx,
                            ksef_number=kn,
                        )
                        extra = " " + "; ".join(notes) if notes else ""
                        ok_lines.append(f"{kn} → InvoiceId={iid}{extra}")
                    except Exception as e:
                        err_lines.append(f"{kn}: {e!s}")

                def finish():
                    self._busy = False
                    self._refresh_main_invoice_list()
                    self._status.set(
                        f"Import: OK {len(ok_lines)}, błędy {len(err_lines)}."
                    )
                    msg = "\n".join(ok_lines[:20])
                    if err_lines:
                        msg += "\n\n--- Błędy ---\n" + "\n".join(err_lines[:15])
                    messagebox.showinfo("Import do bazy", msg[:8000] or "Brak wyników.", parent=self)

                self.after(0, finish)
            except Exception as e:

                def fail():
                    self._busy = False
                    messagebox.showerror("Import", format_ksef_error(e), parent=self)

                self.after(0, fail)

        threading.Thread(target=work, daemon=True).start()

    def _on_import_all_in_range(self) -> None:
        """Pobiera metadane po wszystkich stronach w wybranym zakresie dat i importuje każdą fakturę do bazy."""
        if self._busy:
            return
        tok, nip = self._get_token_nip()
        if not tok or not nip:
            messagebox.showwarning(
                "KSeF",
                "Brak tokenu lub NIP. Ustaw w Plik → Ustawienia integracji… lub KSEF_TOKEN / KSEF_NIP.",
                parent=self,
            )
            return

        d_from = _waw_datetime_from_date(self._de_from.get_date(), end_of_day=False)
        d_to = _waw_datetime_from_date(self._de_to.get_date(), end_of_day=True)
        warn = max_range_days_warning(d_from, d_to)
        if warn:
            if not messagebox.askyesno(
                "Zakres dat",
                warn
                + "\n\nImport „wszystkich” podzieli zakres na mniejsze części i pobierze je kolejno.\n"
                "Kontynuować?",
                parent=self,
            ):
                return

        if not messagebox.askyesno(
            "Import wszystkich dokumentów",
            "Zostaną pobrane z KSeF i zapisane w bazie wszystkie faktury spełniające kryteria "
            "(wybrany zakres dat, typ daty, sortowanie) — wszystkie strony wyniku z API.\n\n"
            "Może to chwilę potrwać i wykonać wiele żądań.\n\nKontynuować?",
            parent=self,
        ):
            return

        ctx = get_context_organization_id()
        if ctx is None:
            if not messagebox.askyesno(
                "Import",
                "Na głównym oknie nie wybrano „Moja firma (kontekst)”. "
                "Import utworzy lub dopasuje organizację nabywcy po NIP z XML.\n\nKontynuować?",
                parent=self,
            ):
                return

        psize = self._parse_page_size()
        d_type = self._date_type.get()
        sort_o = self._sort_order.get()
        base = self._base_url

        self._busy = True
        self._update_nav_state()
        self._status.set("Import wszystkich — przygotowanie…")

        # Limit stron (API ma też limit ~10k rekordów na zapytanie)
        _MAX_PAGES_SAFETY = 600

        def work():
            ok_lines: list[str] = []
            err_lines: list[str] = []
            ok_n = 0
            truncated = False
            total_meta = 0
            try:
                access = obtain_access_token(base, ksef_token=tok, nip=nip)
                chunks = _iter_ksef_date_chunks(d_from, d_to, max_months=3) or [(d_from, d_to)]
                for chunk_idx, (c_from, c_to) in enumerate(chunks, start=1):
                    from_iso = _to_ksef_iso(c_from)
                    to_iso = _to_ksef_iso(c_to)
                    page_idx = 0
                    while True:
                        if page_idx >= _MAX_PAGES_SAFETY:
                            err_lines.append(
                                f"Przerwano: przekroczono limit bezpieczeństwa ({_MAX_PAGES_SAFETY} stron) "
                                f"dla części {chunk_idx}/{len(chunks)}."
                            )
                            break
                        pi = page_idx

                        def upd_status():
                            self._status.set(
                                f"Import wszystkich — zakres {chunk_idx}/{len(chunks)}, strona API {pi + 1}, "
                                f"pobrano metadanych: {total_meta}, zaimportowano OK: {ok_n}…"
                            )

                        self.after(0, upd_status)

                        data = query_purchase_invoices_metadata(
                            base,
                            access,
                            date_from_iso=from_iso,
                            date_to_iso=to_iso,
                            date_type=d_type,
                            sort_order=sort_o,
                            page_index=page_idx,
                            page_size=psize,
                        )
                        invoices: list[dict[str, Any]] = list(data.get("invoices") or [])
                        total_meta += len(invoices)
                        if bool(data.get("isTruncated")):
                            truncated = True

                        hm = data.get("hasMore")
                        if hm is None:
                            hm = data.get("has_more")
                        has_more = bool(hm)

                        for inv in invoices:
                            kn = (inv.get("ksefNumber") or "").strip()
                            if not kn:
                                continue
                            try:
                                xml = download_invoice_xml(base, access, kn)
                                iid, notes = import_fa_purchase_xml_to_db(
                                    xml,
                                    buyer_org_id=ctx,
                                    ksef_number=kn,
                                )
                                ok_n += 1
                                extra = " " + "; ".join(notes) if notes else ""
                                if len(ok_lines) < 40:
                                    ok_lines.append(f"{kn} → InvoiceId={iid}{extra}")
                            except Exception as e:
                                err_lines.append(f"{kn}: {e!s}")

                        if not has_more:
                            break
                        page_idx += 1

                def finish():
                    self._busy = False
                    self._update_nav_state()
                    self._refresh_main_invoice_list()
                    tail = ""
                    if truncated:
                        tail = "\n\nUwaga: API zwróciło isTruncated=true — część danych może wymagać węższego zakresu dat."
                    self._status.set(
                        f"Import wszystkich zakończony: OK {ok_n}, błędy {len(err_lines)}."
                    )
                    msg = (
                        f"Zaimportowano poprawnie: {ok_n}.\n"
                        f"Błędy: {len(err_lines)}.\n"
                        f"Łącznie rekordów metadanych (wszystkie strony): {total_meta}."
                        f"{tail}"
                    )
                    if ok_lines:
                        msg += "\n\n--- Przykładowe OK (do " + str(len(ok_lines)) + ") ---\n"
                        msg += "\n".join(ok_lines)
                    if err_lines:
                        msg += "\n\n--- Błędy (fragment) ---\n" + "\n".join(err_lines[:25])
                    if len(err_lines) > 25:
                        msg += f"\n… i {len(err_lines) - 25} więcej."
                    messagebox.showinfo("Import wszystkich", msg[:8000], parent=self)

                self.after(0, finish)
            except Exception as e:

                def fail():
                    self._busy = False
                    self._update_nav_state()
                    messagebox.showerror("Import wszystkich", format_ksef_error(e), parent=self)

                self.after(0, fail)

        threading.Thread(target=work, daemon=True).start()

    def _on_import_xml_files(self) -> None:
        if self._busy:
            return
        paths = filedialog.askopenfilenames(
            title="Pliki FA (XML) do importu",
            filetypes=[("XML", "*.xml"), ("Wszystkie", "*.*")],
        )
        if not paths:
            return
        ctx = get_context_organization_id()
        if ctx is None:
            if not messagebox.askyesno(
                "Import",
                "Nie wybrano „Moja firma (kontekst)” na głównym oknie. "
                "Nabywca zostanie utworzony/dopasowany po NIP z pliku.\n\nKontynuować?",
                parent=self,
            ):
                return

        self._busy = True
        self._status.set(f"Import {len(paths)} plików…")

        def work():
            ok_lines: list[str] = []
            err_lines: list[str] = []
            for p in paths:
                try:
                    iid, notes = import_fa_purchase_xml_file(
                        p,
                        buyer_org_id=ctx,
                    )
                    extra = " " + "; ".join(notes) if notes else ""
                    ok_lines.append(f"{Path(p).name} → InvoiceId={iid}{extra}")
                except Exception as e:
                    err_lines.append(f"{Path(p).name}: {e!s}")

            def finish():
                self._busy = False
                self._refresh_main_invoice_list()
                self._status.set(f"Import plików: OK {len(ok_lines)}, błędy {len(err_lines)}.")
                msg = "\n".join(ok_lines[:20])
                if err_lines:
                    msg += "\n\n--- Błędy ---\n" + "\n".join(err_lines[:15])
                messagebox.showinfo("Import z dysku", msg[:8000] or "Brak wyników.", parent=self)

            self.after(0, finish)

        threading.Thread(target=work, daemon=True).start()
