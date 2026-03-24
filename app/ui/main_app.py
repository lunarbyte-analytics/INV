import threading
import tkinter as tk
from tkinter import ttk, messagebox

from ..app_env import (
    AppEnvironment,
    get_context_organization_id,
    get_environment,
    is_test_environment,
    set_context_organization_id,
    set_environment,
)
from ..ksef.debug_log import ksef_debug
from ..ksef.invoice_submit import format_ksef_error, send_invoice_to_ksef
from ..restart_util import restart_application
from ..models.invoice import get_invoice_list, get_organizations, update_invoice
from ..reports.invoice_pdf import generate_invoice_pdf, open_preview

from .invoice_crud import InvoiceCrud
from .tax_crud import TaxCrud
from .unit_crud import UnitCrud
from .service_crud import ServiceCrud
from .address_crud import AddressCrud
from .organization_crud import OrganizationCrud
from .calendar_view import CalendarWindow
from .ksef_connection import KsefConnectionWindow
from .ksef_purchase_window import KsefPurchaseWindow


class MainApp(tk.Tk):
    def __init__(self):
        super().__init__()
        title = "Aplikacja – Słowniki i Faktury"
        if is_test_environment():
            title += " [TEST]"
        self.title(title)
        self.geometry("1200x640")
        self._build_env_banner()
        self._build_menu()
        self._invoice_meta: dict[int, tuple[int, int]] = {}
        self._flow_labels = ("Wszystkie", "Tylko sprzedaż", "Tylko zakup")
        self._build_home()
        self.refresh_invoice_list()

    def _build_env_banner(self):
        if not is_test_environment():
            return
        bar = tk.Frame(self, bg="#b84700")
        bar.pack(side=tk.TOP, fill=tk.X)
        tk.Label(
            bar,
            text=(
                "ŚRODOWISKO TESTOWE — używana jest osobna baza (sqllite3_inv_test.db). "
                "To nie jest produkcja."
            ),
            fg="#fff8f0",
            bg="#b84700",
            font=("Segoe UI", 10, "bold"),
            wraplength=1100,
            justify=tk.CENTER,
        ).pack(pady=8, padx=12)

    # ---------------------- MENU ----------------------
    def _build_menu(self):
        menubar = tk.Menu(self)

        m_dict = tk.Menu(menubar, tearoff=0)
        m_dict.add_command(label="Faktury",   command=self.open_invoice_window)
        m_dict.add_command(label="Podatek",   command=self.open_tax_window)
        m_dict.add_command(label="Jednostki", command=self.open_unit_window)
        m_dict.add_command(label="Usługi",    command=self.open_service_window)
        m_dict.add_command(label="Adresy",    command=self.open_address_window)
        m_dict.add_command(label="Organizacje", command=self.open_org_window)
        menubar.add_cascade(label="Słowniki", menu=m_dict)

        m_file = tk.Menu(menubar, tearoff=0)
        m_env = tk.Menu(m_file, tearoff=0)
        self._var_env = tk.StringVar(value=get_environment().value)
        m_env.add_radiobutton(
            label="Produkcyjne (sqllite3_inv.db)",
            variable=self._var_env,
            value=AppEnvironment.PRODUCTION.value,
            command=self._on_environment_radios,
        )
        m_env.add_radiobutton(
            label="Testowe (sqllite3_inv_test.db)",
            variable=self._var_env,
            value=AppEnvironment.TEST.value,
            command=self._on_environment_radios,
        )
        m_file.add_cascade(label="Środowisko", menu=m_env)
        m_file.add_separator()
        m_file.add_command(label="Zakończ", command=self.quit)
        menubar.add_cascade(label="Plik", menu=m_file)

        m_view = tk.Menu(menubar, tearoff=0)
        m_view.add_command(label="Kalendarz", command=self.open_calendar_window)
        menubar.add_cascade(label="Widok", menu=m_view)

        m_ksef = tk.Menu(menubar, tearoff=0)
        m_ksef.add_command(label="Test połączenia", command=self.open_ksef_test_window)
        m_ksef.add_command(
            label="Faktury zakupowe (pobierz z KSeF)",
            command=self.open_ksef_purchase_window,
        )
        menubar.add_cascade(label="KSeF", menu=m_ksef)

        self.config(menu=menubar)

    def _on_environment_radios(self):
        try:
            chosen = AppEnvironment(self._var_env.get())
        except ValueError:
            self._var_env.set(get_environment().value)
            return
        if chosen == get_environment():
            return
        if not messagebox.askyesno(
            "Zmiana środowiska",
            "Zmiana przełączy aplikację na inną bazę danych.\n\n"
            "Aplikacja zostanie zamknięta i uruchomiona ponownie.\n\n"
            "Kontynuować?",
        ):
            self._var_env.set(get_environment().value)
            return
        set_environment(chosen, persist=True)
        restart_application()

    # ---------------------- HOME (lista faktur) ----------------------
    def _org_display_label(self, oid: int, name: str) -> str:
        n = (name or "").strip() or f"Org {oid}"
        return f"{n} (ID {oid})"

    def _populate_context_org_combo(self):
        self._org_labels_to_id: dict[str, int] = {}
        rows = get_organizations()
        labels = ["— Wybierz firmę (kontekst) —"]
        for r in rows:
            oid = int(r["OrganizationId"])
            lab = self._org_display_label(oid, r["Name"] or "")
            self._org_labels_to_id[lab] = oid
            labels.append(lab)
        self.cb_context_org["values"] = labels
        ctx = get_context_organization_id()
        if ctx is not None:
            for lab, oid in self._org_labels_to_id.items():
                if oid == ctx:
                    self.cb_context_org.set(lab)
                    return
        self.cb_context_org.set(labels[0])

    def _on_context_org_selected(self, _evt=None):
        lab = self.cb_context_org.get()
        oid = self._org_labels_to_id.get(lab) if hasattr(self, "_org_labels_to_id") else None
        if lab.startswith("—") or oid is None:
            set_context_organization_id(None)
        else:
            set_context_organization_id(oid)
        self.refresh_invoice_list()

    def _on_flow_filter_selected(self, _evt=None):
        lab = self._var_flow.get()
        ctx = get_context_organization_id()
        if lab in ("Tylko sprzedaż", "Tylko zakup") and ctx is None:
            messagebox.showwarning(
                "Filtr",
                "Aby filtrować sprzedaż lub zakup, najpierw wybierz „Moja firma (kontekst)”.",
                parent=self,
            )
            self._var_flow.set(self._flow_labels[0])
        self.refresh_invoice_list()

    def _build_home(self):
        root = ttk.Frame(self)
        root.pack(expand=True, fill=tk.BOTH)

        ttk.Label(
            root,
            text=(
                "Kolumna „Typ”: względem „Mojej firmy” — Sprzedaż = wystawiasz fakturę, Zakup = otrzymujesz. "
                "Dwuklik/Enter — edycja. Akcje: 🖨️ druk, ✏️ szkic, 📄 wystawiona, 💰 opłacona."
            ),
            font=("Segoe UI", 10),
            wraplength=1100,
        ).pack(pady=(8, 4))

        filter_bar = ttk.Frame(root)
        filter_bar.pack(fill=tk.X, padx=10, pady=(0, 6))
        ttk.Label(filter_bar, text="Moja firma (kontekst):").pack(side=tk.LEFT)
        self.cb_context_org = ttk.Combobox(filter_bar, width=42, state="readonly")
        self.cb_context_org.pack(side=tk.LEFT, padx=(6, 16))
        self.cb_context_org.bind("<<ComboboxSelected>>", self._on_context_org_selected)
        ttk.Label(filter_bar, text="Widok:").pack(side=tk.LEFT)
        self._var_flow = tk.StringVar(value=self._flow_labels[0])
        self.cb_flow = ttk.Combobox(
            filter_bar,
            textvariable=self._var_flow,
            values=self._flow_labels,
            width=18,
            state="readonly",
        )
        self.cb_flow.pack(side=tk.LEFT, padx=6)
        self.cb_flow.bind("<<ComboboxSelected>>", self._on_flow_filter_selected)
        self._populate_context_org_combo()

        # Kontener na tabelę + scrollbary
        table_frame = ttk.Frame(root)
        table_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)

        # Kolumny danych + 4 kolumny akcji
        self._cols_data = (
            "InvoiceId",
            "FlowRole",
            "Name",
            "CreateDate",
            "StatusName",
            "CompanyName",
            "CustomerName",
            "KsefReferenceNumber",
            "KsefSentAt",
        )
        self._cols_actions = ("Print", "ToDraft", "ToIssued", "ToPaid")
        cols = self._cols_data + self._cols_actions

        self.tree_invoices = ttk.Treeview(
            table_frame,
            columns=cols,
            show="headings",
            selectmode="browse"
        )

        # Nagłówki danych
        self.tree_invoices.heading("InvoiceId", text="ID")
        self.tree_invoices.heading("FlowRole", text="Typ")
        self.tree_invoices.heading("Name", text="Numer")
        self.tree_invoices.heading("CreateDate", text="Data")
        self.tree_invoices.heading("StatusName", text="Status")
        self.tree_invoices.heading("CompanyName", text="Sprzedawca")
        self.tree_invoices.heading("CustomerName", text="Nabywca")
        self.tree_invoices.heading("KsefReferenceNumber", text="KSeF — nr ref.")
        self.tree_invoices.heading("KsefSentAt", text="KSeF — wysłano")

        # Nagłówki akcji
        self.tree_invoices.heading("Print", text="🖨️")
        self.tree_invoices.heading("ToDraft", text="✏️")
        self.tree_invoices.heading("ToIssued", text="📄")
        self.tree_invoices.heading("ToPaid", text="💰")

        # Szerokości
        self.tree_invoices.column("InvoiceId", width=60, anchor="e")
        self.tree_invoices.column("FlowRole", width=130, anchor="w")
        self.tree_invoices.column("Name", width=130, anchor="w")
        self.tree_invoices.column("CreateDate", width=100, anchor="center")
        self.tree_invoices.column("StatusName", width=120, anchor="w")
        self.tree_invoices.column("CompanyName", width=200, anchor="w")
        self.tree_invoices.column("CustomerName", width=200, anchor="w")
        self.tree_invoices.column("KsefReferenceNumber", width=280, anchor="w")
        self.tree_invoices.column("KsefSentAt", width=150, anchor="center")

        # Kolumny akcji – węższe
        for c in self._cols_actions:
            self.tree_invoices.column(c, width=40, anchor="center", stretch=False)

        self.tree_invoices.grid(row=0, column=0, sticky="nsew")

        # Scrollbary
        yscroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree_invoices.yview)
        xscroll = ttk.Scrollbar(table_frame, orient="horizontal", command=self.tree_invoices.xview)
        self.tree_invoices.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")

        # Bindy
        self.tree_invoices.bind("<Double-1>", self.on_open_selected_invoice)  # dwuklik
        self.tree_invoices.bind("<Return>",   self.on_open_selected_invoice)  # Enter
        self.tree_invoices.bind("<Button-1>", self.on_tree_click)             # klik w akcje

        # --- DODANY PANEL Z PRZYCISKIEM "ODŚWIEŻ" ---
        btn_panel = ttk.Frame(root)
        btn_panel.pack(fill=tk.X, pady=(0, 6))
        ttk.Button(
            btn_panel,
            text="📤 Wyślij do KSeF",
            command=self.on_send_selected_to_ksef,
        ).pack(side=tk.LEFT, padx=(10, 0))
        ttk.Button(
            btn_panel,
            text="📥 Faktury zakupowe z KSeF",
            command=self.open_ksef_purchase_window,
        ).pack(side=tk.LEFT, padx=(6, 0))
        ttk.Button(btn_panel, text="🔄 Odśwież listę", command=self.refresh_invoice_list).pack(side=tk.RIGHT, padx=10)

        try:
            self.refresh_invoice_list()
        except Exception as e:
            print("[DEBUG] refresh_invoice_list EXC:", e)
            
    # ---------------------- Handlery listy ----------------------
    def on_tree_click(self, event):
        """Klik w komórkę – obsługa kolumn akcji."""
        region = self.tree_invoices.identify("region", event.x, event.y)
        if region != "cell":
            return
        col = self.tree_invoices.identify_column(event.x)  # np. "#7"
        row_id = self.tree_invoices.identify_row(event.y)
        if not row_id:
            return

        values = self.tree_invoices.item(row_id, "values")
        if not values:
            return

        inv_id = int(values[0])
        # 9 kolumn danych, potem akcje:
        # #10 = Print, #11 = ToDraft, #12 = ToIssued, #13 = ToPaid
        try:
            if col == "#10":   # DRUK
                pdf = generate_invoice_pdf(inv_id)
                open_preview(pdf)
                return

            if col == "#11":   # Do Szkic (StatusId=1)
                update_invoice(inv_id, StatusId=1)
                self.refresh_invoice_list()
                return

            if col == "#12":   # Do Wystawiona (StatusId=2)
                update_invoice(inv_id, StatusId=2)
                self.refresh_invoice_list()
                return

            if col == "#13":  # Do Opłacona (StatusId=3)
                update_invoice(inv_id, StatusId=3)
                self.refresh_invoice_list()
                return
        except Exception as e:
            messagebox.showerror("Błąd", str(e))


    def open_calendar(self):
        CalendarWindow(self)

    def open_selected_invoice(self):
        inv_id = self._get_selected_invoice_id()
        if inv_id is None:
            messagebox.showwarning("Wybór", "Zaznacz fakturę na liście.")
            return
        self._open_invoice_window_with_id(inv_id)

    def on_open_selected_invoice(self, _evt=None):
        inv_id = self._get_selected_invoice_id()
        print(f"[DEBUG] on_open_selected_invoice → selected InvoiceId={inv_id}")
        self.open_selected_invoice()

    def _open_invoice_window_with_id(self, invoice_id: int):
        print(f"[DEBUG] _open_invoice_window_with_id({invoice_id})")
        try:
            if getattr(self, "_invoice_win", None) is not None and self._invoice_win.winfo_exists():
                win = self._invoice_win
                win.deiconify()
                win.focus_set()
            else:
                self._invoice_win = InvoiceCrud(self)
                win = self._invoice_win
            win.load_invoice(invoice_id)
            win.focus_set()
        except Exception as e:
            print(f"[DEBUG] _open_invoice_window_with_id EXC: {e}")
            messagebox.showerror("Błąd", f"Nie udało się otworzyć faktury {invoice_id}.\n{e}")

    # ---------------------- Pomocnicze ----------------------
    def _focus_or_new(self, cls):
        for w in self.winfo_children():
            if isinstance(w, cls):
                try:
                    w.focus_force()
                    return True
                except Exception:
                    pass
        return False

    # ---------------------- Otwieranie okien słowników ----------------------
    def open_invoice_window(self):
        if getattr(self, "_invoice_win", None) is not None and self._invoice_win.winfo_exists():
            self._invoice_win.deiconify()
            self._invoice_win.focus_set()
            return
        self._invoice_win = InvoiceCrud(self)
        self._invoice_win.focus_set()

    def open_tax_window(self):
        if not self._focus_or_new(TaxCrud):
            TaxCrud(self)

    def open_unit_window(self):
        if not self._focus_or_new(UnitCrud):
            UnitCrud(self)

    def open_service_window(self):
        if not self._focus_or_new(ServiceCrud):
            ServiceCrud(self)

    def open_address_window(self):
        if not self._focus_or_new(AddressCrud):
            AddressCrud(self)

    def open_org_window(self):
        if not self._focus_or_new(OrganizationCrud):
            OrganizationCrud(self)

    def open_calendar_window(self):
        # jeśli okno już istnieje – przywróć focus
        if getattr(self, "_calendar_win", None) is not None and self._calendar_win.winfo_exists():
            self._calendar_win.deiconify()
            self._calendar_win.focus_set()
            return
        self._calendar_win = CalendarWindow(self)
        self._calendar_win.focus_set()

    def open_ksef_test_window(self):
        if getattr(self, "_ksef_test_win", None) is not None and self._ksef_test_win.winfo_exists():
            self._ksef_test_win.deiconify()
            self._ksef_test_win.focus_set()
            return
        self._ksef_test_win = KsefConnectionWindow(self)
        self._ksef_test_win.focus_set()

    def open_ksef_purchase_window(self):
        if getattr(self, "_ksef_purchase_win", None) is not None and self._ksef_purchase_win.winfo_exists():
            self._ksef_purchase_win.deiconify()
            self._ksef_purchase_win.focus_set()
            return
        self._ksef_purchase_win = KsefPurchaseWindow(self)
        self._ksef_purchase_win.focus_set()

    def _get_selected_invoice_id(self):
        sel = self.tree_invoices.selection()
        if not sel:
            return None
        vals = self.tree_invoices.item(sel[0], "values")
        if not vals:
            return None
        try:
            return int(vals[0])  # 0 = InvoiceId
        except (ValueError, TypeError):
            return None

    def on_send_selected_to_ksef(self):
        inv_id = self._get_selected_invoice_id()
        if inv_id is None:
            messagebox.showwarning("KSeF", "Zaznacz fakturę na liście (jeden wiersz).")
            return
        ctx = get_context_organization_id()
        if ctx is not None:
            meta = self._invoice_meta.get(inv_id)
            if not meta:
                messagebox.showwarning(
                    "KSeF",
                    "Brak danych wiersza — odśwież listę faktur.",
                    parent=self,
                )
                return
            if int(meta[0]) != ctx:
                messagebox.showwarning(
                    "KSeF",
                    "Wybrana faktura nie jest sprzedażową względem wybranej „Mojej firmy”. "
                    "Do KSeF wysyła się tylko własną sprzedaż.",
                    parent=self,
                )
                return

        def work():
            try:
                result = send_invoice_to_ksef(inv_id)

                def _after_result():
                    if result.ok:
                        messagebox.showinfo("KSeF", result.message, parent=self)
                    else:
                        messagebox.showerror("KSeF — dokument odrzucony", result.message, parent=self)
                    self.refresh_invoice_list()

                self.after(0, _after_result)
            except Exception as e:
                ksef_debug(f"Wysyłka KSeF: wyjątek {type(e).__name__}: {e}")
                msg = format_ksef_error(e)
                self.after(
                    0,
                    lambda m=msg: messagebox.showerror(
                        "KSeF — błąd wysyłki", m, parent=self
                    ),
                )

        threading.Thread(target=work, daemon=True).start()

    def refresh_invoice_list(self):
        """Załaduj dane do self.tree_invoices na głównym oknie."""
        if not hasattr(self, "tree_invoices"):
            return
        for i in self.tree_invoices.get_children():
            self.tree_invoices.delete(i)

        ctx = get_context_organization_id()
        lab = self._var_flow.get()
        flow_map = {
            self._flow_labels[0]: None,
            self._flow_labels[1]: "sales",
            self._flow_labels[2]: "purchase",
        }
        ff = flow_map.get(lab)
        if ff in ("sales", "purchase") and ctx is None:
            ff = None
        rows = get_invoice_list(context_org_id=ctx, flow_filter=ff)

        self._invoice_meta = {}
        for r in rows:
            inv_id = int(r["InvoiceId"])
            self._invoice_meta[inv_id] = (int(r["CompanyId"]), int(r["CustomerId"]))
            kref = r["KsefReferenceNumber"] or ""
            sent = r["KsefSentAt"] or ""
            if sent and "T" in sent:
                sent = sent.replace("T", " ", 1)[:19]
            self.tree_invoices.insert(
                "", "end",
                values=(
                    r["InvoiceId"],
                    r["FlowRole"],
                    r["Name"],
                    r["CreateDate"],
                    r["StatusName"],
                    r["CompanyName"],
                    r["CustomerName"],
                    kref,
                    sent,
                    "🖨️", "✏️", "📄", "💰",
                ),
            )
