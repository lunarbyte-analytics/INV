# app/ui/calendar_view.py
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import date, datetime, timedelta
import calendar

from ..models.custom_days import (
    ensure_table,
    list_for_month,
    add_or_update_day,
    delete_day,
)

PADX = 8
PADY = 6

# ---------- ŚWIĘTA ----------
def calculate_easter_date(year):
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return datetime(year, month, day)

def get_polish_holidays(year):
    easter_sunday = calculate_easter_date(year)
    easter_monday = easter_sunday + timedelta(days=1)
    pentecost = easter_sunday + timedelta(days=49)
    corpus_christi = easter_sunday + timedelta(days=60)
    fixed = [
        (1, 1,  "Nowy Rok"),
        (6, 1,  "Trzech Króli"),
        (1, 5,  "Święto Pracy"),
        (3, 5,  "Święto Konstytucji 3 Maja"),
        (15, 8, "Wniebowzięcie NMP / Święto Wojska Polskiego"),
        (1, 11, "Wszystkich Świętych"),
        (11, 11,"Święto Niepodległości"),
        (25, 12,"Boże Narodzenie (1. dzień)"),
        (26, 12,"Boże Narodzenie (2. dzień)"),
    ]
    if year >= 2025:
        fixed.append((24, 12, "Wigilia"))
    movable = [
        (easter_sunday.day,  easter_sunday.month,  "Wielkanoc (niedziela)"),
        (easter_monday.day,  easter_monday.month,  "Poniedziałek Wielkanocny"),
        (pentecost.day,      pentecost.month,      "Zesłanie Ducha Świętego"),
        (corpus_christi.day, corpus_christi.month, "Boże Ciało"),
    ]
    return fixed + movable

# ---------- KALENDARZ ----------
class CalendarWindow(tk.Toplevel):
    """Miesięczny kalendarz z weekendami, świętami i własnymi dniami wolnymi (z DB)."""

    def __init__(self, master=None, year=None, month=None):
        super().__init__(master)
        self.title("Kalendarz")
        self.geometry("720x480")
        self.resizable(False, False)

        # DB: upewnij się, że tabela istnieje
        try:
            ensure_table()
        except Exception as e:
            print(f"[WARN] ensure_table() error: {e}")

        today = date.today()
        self.year = year or today.year
        self.month = month or today.month

        calendar.setfirstweekday(calendar.MONDAY)

        # cache
        self._holiday_map = {}        # {month: {day: name}}
        self._custom_days_set = set() # dni własne (int) w bieżącym miesiącu
        self._rebuild_holiday_cache()
        self._reload_custom_days()

        # context menu state
        self._ctx_day = None
        self._ctx_label = None

        self._build_widgets()
        self._render_month()

    # ---------- UI ----------
    def _build_widgets(self):
        # Pasek nawigacji
        head = ttk.Frame(self)
        head.pack(fill=tk.X, padx=10, pady=(10, 4))

        ttk.Button(head, text="<<", width=3, command=self._prev_year).pack(side=tk.LEFT, padx=2)
        ttk.Button(head, text="<",  width=3, command=self._prev_month).pack(side=tk.LEFT, padx=2)

        self.lbl_title = ttk.Label(head, text="", font=("Segoe UI", 12, "bold"))
        self.lbl_title.pack(side=tk.LEFT, expand=True, fill=tk.X)

        ttk.Button(head, text=">",  width=3, command=self._next_month).pack(side=tk.RIGHT, padx=2)
        ttk.Button(head, text=">>", width=3, command=self._next_year).pack(side=tk.RIGHT, padx=2)

        # Layout główny
        body = ttk.Frame(self)
        body.pack(expand=True, fill=tk.BOTH, padx=10, pady=(0, 10))

        # SIATKA
        grid_wrap = ttk.Frame(body)
        grid_wrap.pack(side=tk.LEFT, expand=True, fill=tk.BOTH)

        self.grid_frame = ttk.Frame(grid_wrap)
        self.grid_frame.pack(expand=True, fill=tk.BOTH)

        headers = ["Pn", "Wt", "Śr", "Cz", "Pt", "So", "Nd"]
        for col, name in enumerate(headers):
            lbl = ttk.Label(self.grid_frame, text=name, anchor="center", padding=(0, 4))
            lbl.grid(row=0, column=col, sticky="nsew", padx=2, pady=2)

        self.day_labels = []
        for r in range(1, 7):  # do 6 tygodni
            row_labels = []
            for c in range(7):
                lab = tk.Label(
                    self.grid_frame,
                    text="",
                    width=6, height=2,
                    borderwidth=1, relief="solid",
                    anchor="center",
                    font=("Segoe UI", 10)
                )
                lab.grid(row=r, column=c, padx=2, pady=2, sticky="nsew")
                lab.bind("<Button-3>", self._on_day_right_click)   # Windows/Linux
                lab.bind("<ButtonRelease-3>", lambda e: None)
                lab.bind("<Control-Button-1>", self._on_day_right_click)  # macOS

                lab._grid_row = r
                lab._grid_col = c
                row_labels.append(lab)
            self.day_labels.append(row_labels)

        for i in range(7):
            self.grid_frame.columnconfigure(i, weight=1)
        for i in range(1, 7):
            self.grid_frame.rowconfigure(i, weight=1)

        # PANEL BOCZNY
        side = ttk.Frame(body)
        side.pack(side=tk.LEFT, fill=tk.Y, padx=(10, 0))

        ttk.Label(side, text="Zdarzenia w miesiącu", font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(0, 6))
        self.lst_holidays = tk.Listbox(side, width=30, height=16)
        self.lst_holidays.pack(fill=tk.Y, expand=False)

        # Dół: licznik + legenda + przycisk "Dziś"
        foot = ttk.Frame(self)
        foot.pack(fill=tk.X, padx=10, pady=(0, 10))

        # Licznik dni pracujących
        ttk.Label(foot, text="  ").pack(side=tk.LEFT)  # mały odstęp
        self.lbl_workdays = ttk.Label(foot, text="Dni pracujące: …", font=("Segoe UI", 10, "bold"))
        self.lbl_workdays.pack(side=tk.LEFT)

        ttk.Button(foot, text="Dziś", command=self._go_today).pack(side=tk.RIGHT)

        legend = ttk.Frame(foot)
        legend.pack(side=tk.LEFT, padx=(15, 0))
        self._legend_box(legend, "Weekend", self._bg_weekend())
        self._legend_box(legend, "Święto",  self._bg_holiday())
        self._legend_box(legend, "Własny",  self._bg_custom())

        # MENU KONTEKSTOWE
        self._ctx_menu = tk.Menu(self, tearoff=0)


    def _legend_box(self, parent, text, color):
        box = tk.Label(parent, width=2, height=1, bg=color, relief="solid", borderwidth=1)
        box.pack(side=tk.LEFT, padx=(0, 4))
        ttk.Label(parent, text=text).pack(side=tk.LEFT, padx=(0, 10))

    # ---------- CONTEXT MENU ----------
    def _on_day_right_click(self, event):
        lab = event.widget
        day = getattr(lab, "_day", 0)
        if not day:
            return
        self._ctx_day = day
        self._ctx_label = lab
        self._show_context_menu(event.x_root, event.y_root)

    def _show_context_menu(self, x, y):
        self._ctx_menu.delete(0, tk.END)
        day = self._ctx_day
        if day in self._custom_days_set:
            self._ctx_menu.add_command(label="Usuń dzień wolny", command=self._ctx_remove_day)
        else:
            self._ctx_menu.add_command(label="Dodaj dzień wolny", command=self._ctx_add_day)
        self._ctx_menu.post(x, y)

    def _ctx_add_day(self):
        day = self._ctx_day
        if not day:
            return
        try:
            add_or_update_day(self.year, self.month, day, "Własny dzień wolny")
            self._custom_days_set.add(day)
        except Exception as e:
            messagebox.showerror("Baza danych", f"Nie udało się dodać dnia wolnego.\n{e}")
            return
        self._render_month()

    def _ctx_remove_day(self):
        day = self._ctx_day
        if not day:
            return
        try:
            if delete_day(self.year, self.month, day):
                self._custom_days_set.discard(day)
        except Exception as e:
            messagebox.showerror("Baza danych", f"Nie udało się usunąć dnia wolnego.\n{e}")
            return
        self._render_month()

    # ---------- render ----------
    def _render_month(self):
        month_name_pl = [
            "", "Styczeń", "Luty", "Marzec", "Kwiecień", "Maj", "Czerwiec",
            "Lipiec", "Sierpień", "Wrzesień", "Październik", "Listopad", "Grudzień"
        ]
        self.lbl_title.config(text=f"{month_name_pl[self.month]} {self.year}")

        weeks = calendar.monthcalendar(self.year, self.month)
        today = date.today()
        month_holidays = self._holiday_map.get(self.month, {})

        for r in range(6):
            for c in range(7):
                lab = self.day_labels[r][c]
                try:
                    day = weeks[r][c]
                except IndexError:
                    day = 0

                lab._day = day
                if day == 0:
                    lab.config(text="", bg=self._bg_normal(), fg="black", font=("Segoe UI", 10))
                    continue

                is_weekend = c in (5, 6)
                is_custom = (day in self._custom_days_set)
                holiday_name = month_holidays.get(day)

                lab.config(text=str(day), fg="black")

                if is_custom:
                    lab.config(bg=self._bg_custom(), font=("Segoe UI", 10, "bold"))
                elif holiday_name:
                    lab.config(bg=self._bg_holiday(), font=("Segoe UI", 10, "bold"))
                elif is_weekend:
                    lab.config(bg=self._bg_weekend(), font=("Segoe UI", 10))
                else:
                    lab.config(bg=self._bg_normal(), font=("Segoe UI", 10))

                if today.year == self.year and today.month == self.month and today.day == day:
                    lab.config(highlightthickness=2, highlightbackground="#3a86ff")
                else:
                    lab.config(highlightthickness=0, highlightbackground=self._bg_normal())

        self._fill_event_list_for_month()
        
        # Uaktualnij licznik dni pracujących
        try:
            wd = self._count_working_days()
            if hasattr(self, "lbl_workdays"):
                self.lbl_workdays.config(text=f"Dni pracujące: {wd}")
        except Exception as e:
            # cicho logujemy – UI nie powinno się wywalić przez licznik
            print(f"[WARN] workdays calc error: {e}")


    def _fill_event_list_for_month(self):
        self.lst_holidays.delete(0, tk.END)
        month_holidays = self._holiday_map.get(self.month, {})

        for day in sorted(month_holidays.keys()):
            name = month_holidays[day]
            self.lst_holidays.insert(tk.END, f"{day:02d}.{self.month:02d}.{self.year} – {name}")

        for day in sorted(self._custom_days_set):
            self.lst_holidays.insert(tk.END, f"{day:02d}.{self.month:02d}.{self.year} – Własny dzień wolny")

    # ---------- kolory ----------
    def _bg_normal(self):
        return self.cget("bg")
    def _bg_weekend(self):
        return "#ffe9e9"
    def _bg_holiday(self):
        return "#ffc7c7"
    def _bg_custom(self):
        return "#cfe8ff"

    # ---------- nawigacja ----------
    def _prev_month(self):
        if self.month == 1:
            self.month, self.year = 12, self.year - 1
            self._rebuild_holiday_cache()
        else:
            self.month -= 1
        self._reload_custom_days()
        self._render_month()

    def _next_month(self):
        if self.month == 12:
            self.month, self.year = 1, self.year + 1
            self._rebuild_holiday_cache()
        else:
            self.month += 1
        self._reload_custom_days()
        self._render_month()

    def _prev_year(self):
        self.year -= 1
        self._rebuild_holiday_cache()
        self._reload_custom_days()
        self._render_month()

    def _next_year(self):
        self.year += 1
        self._rebuild_holiday_cache()
        self._reload_custom_days()
        self._render_month()

    def _go_today(self):
        t = date.today()
        year_changed = (t.year != self.year)
        self.year, self.month = t.year, t.month
        if year_changed:
            self._rebuild_holiday_cache()
        self._reload_custom_days()
        self._render_month()

    # ---------- święta / własne dni ----------
    def _rebuild_holiday_cache(self):
        self._holiday_map = {}
        for d, m, name in get_polish_holidays(self.year):
            self._holiday_map.setdefault(m, {})[d] = name

    def _reload_custom_days(self):
        """Wczytaj własne dni z DB dla bieżącego (year, month)."""
        self._custom_days_set = set()
        try:
            rows = list_for_month(self.year, self.month)
            for row in rows:
                # obsługa sqlite3.Row (['DayDate']) i tuple ([0] = DayDate)
                ds = row["DayDate"] if hasattr(row, "keys") else row[0]
                day = int(str(ds).split("-")[2])
                self._custom_days_set.add(day)
        except Exception as e:
            print(f"[WARN] list_for_month({self.year},{self.month}) error: {e}")
    
    def _count_working_days(self) -> int:
        """Liczba dni pracujących (pn–pt) w bieżącym (self.year, self.month),
        wyłączając święta i własne dni wolne, jeśli wypadają w pn–pt."""
        import calendar as _cal

        # mapa świąt dla bieżącego miesiąca
        month_holidays = self._holiday_map.get(self.month, {})
        # ile dni w miesiącu
        _, days_in_month = _cal.monthrange(self.year, self.month)

        working = 0
        for d in range(1, days_in_month + 1):
            wd = _cal.weekday(self.year, self.month, d)  # 0=Mon .. 6=Sun
            if wd < 5:  # pn–pt
                if d in month_holidays:
                    continue  # święto w dzień roboczy = niepracujący
                if d in self._custom_days_set:
                    continue  # własny dzień wolny w pn–pt
                working += 1
        return working
