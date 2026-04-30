import tkinter as tk
from tkinter import ttk, messagebox
from datetime import date
from typing import Optional

from tkcalendar import DateEntry

# --- MODELE / API ---
from ..models.invoice import (
    get_payment_methods, get_statuses, get_invoice_types,
    get_organizations, get_services,
    create_invoice, update_invoice, delete_invoice, invoice_can_be_deleted,
    get_invoice_full, add_detail, update_detail, delete_detail,
    get_ksef_submissions_for_invoice,
    validate_correction_link,
)

ISO_FMT = "%Y-%m-%d"
PADX = 8
PADY = 6


class InvoiceCrud(tk.Toplevel):
    """
    Okno edycji faktury (nagłówek + pozycje).
    Wywołaj load_invoice(invoice_id), by załadować istniejącą fakturę.
    """

    # ------------------------- INIT -------------------------
    def __init__(self, master=None):
        super().__init__(master)
        self.title("Faktura – edycja")
        self.geometry("980x680")
        self.resizable(True, True)

        # mapy lookup – wypełniane w _load_lookups
        self._org_map = {}
        self._org_rev = {}
        self._pm_map = {}
        self._pm_rev = {}
        self._status_map = {}
        self._status_rev = {}
        self._type_map = {}
        self._type_rev = {}
        self._svc_map = {}
        self._svc_rev = {}
        self._svc_labels: list[str] = []

        # zmienne GUI
        self._init_vars()

        # budowa UI i lookups
        self._build_widgets()
        self._load_lookups()

        self._loaded_company_id: Optional[int] = None
        self._loaded_customer_id: Optional[int] = None

        # czysty formularz
        self.on_new()

    # --------------------- VARS & WIDGETS -------------------
    def _init_vars(self):
        # header
        self.var_invoice_id = tk.StringVar()
        self.var_name = tk.StringVar()
        self.var_company = tk.StringVar()
        self.var_customer = tk.StringVar()
        self.var_payment = tk.StringVar()
        self.var_status = tk.StringVar()
        self.var_type = tk.StringVar()
        self.var_is_add_addr = tk.IntVar(value=0)
        self.var_corrected_id = tk.StringVar()
        self.var_correction_reason = tk.StringVar()

        # details
        self.var_detail_id = tk.StringVar()
        self.var_service = tk.StringVar()
        self.var_quantity = tk.StringVar()

    def _build_widgets(self):
        # ---- Formularz nagłówka ----
        frm = ttk.LabelFrame(self, text="Nagłówek")
        frm.pack(fill=tk.X, padx=10, pady=10)

        for c in range(8):
            frm.grid_columnconfigure(c, weight=0)
        frm.grid_columnconfigure(1, weight=1)
        frm.grid_columnconfigure(3, weight=1)
        frm.grid_columnconfigure(5, weight=1)
        frm.grid_columnconfigure(7, weight=1)

        # ID
        ttk.Label(frm, text="ID:").grid(row=0, column=0, sticky=tk.E, padx=PADX, pady=PADY)
        ttk.Entry(frm, textvariable=self.var_invoice_id, width=10, state="readonly")\
            .grid(row=0, column=1, sticky="w", padx=PADX, pady=PADY)

        # Nazwa
        ttk.Label(frm, text="Nazwa:").grid(row=0, column=2, sticky=tk.E, padx=PADX, pady=PADY)
        ttk.Entry(frm, textvariable=self.var_name)\
            .grid(row=0, column=3, columnspan=5, sticky="ew", padx=PADX, pady=PADY)

        # Sprzedawca
        ttk.Label(frm, text="Sprzedawca:").grid(row=1, column=0, sticky=tk.E, padx=PADX, pady=PADY)
        self.cb_company = ttk.Combobox(frm, textvariable=self.var_company, state="readonly")
        self.cb_company.grid(row=1, column=1, sticky="ew", padx=PADX, pady=PADY)

        # Nabywca
        ttk.Label(frm, text="Nabywca:").grid(row=1, column=2, sticky=tk.E, padx=PADX, pady=PADY)
        self.cb_customer = ttk.Combobox(frm, textvariable=self.var_customer, state="readonly")
        self.cb_customer.grid(row=1, column=3, sticky="ew", padx=PADX, pady=PADY)

        # Metoda płatności
        ttk.Label(frm, text="Płatność:").grid(row=1, column=4, sticky=tk.E, padx=PADX, pady=PADY)
        self.cb_payment = ttk.Combobox(frm, textvariable=self.var_payment, state="readonly")
        self.cb_payment.grid(row=1, column=5, sticky="ew", padx=PADX, pady=PADY)

        # Status
        ttk.Label(frm, text="Status:").grid(row=1, column=6, sticky=tk.E, padx=PADX, pady=PADY)
        self.cb_status = ttk.Combobox(frm, textvariable=self.var_status, state="readonly")
        self.cb_status.grid(row=1, column=7, sticky="ew", padx=PADX, pady=PADY)

        # Typ
        ttk.Label(frm, text="Typ:").grid(row=2, column=0, sticky=tk.E, padx=PADX, pady=PADY)
        self.cb_type = ttk.Combobox(frm, textvariable=self.var_type, state="readonly")
        self.cb_type.grid(row=2, column=1, sticky="ew", padx=PADX, pady=PADY)

        # Adres dodatkowy (checkbox)
        ttk.Checkbutton(frm, text="Użyć adresu dodatkowego nabywcy", variable=self.var_is_add_addr)\
            .grid(row=2, column=2, columnspan=2, sticky="w", padx=PADX, pady=PADY)

        # Daty (DateEntry — wybór z kalendarza)
        _cal_kw = {"firstweekday": "monday"}
        ttk.Label(frm, text="Data wyst.:").grid(row=3, column=0, sticky=tk.E, padx=PADX, pady=PADY)
        self._de_create_date = DateEntry(
            frm,
            width=12,
            date_pattern="yyyy-mm-dd",
            calendar_kw=_cal_kw,
        )
        self._de_create_date.grid(row=3, column=1, sticky="w", padx=PADX, pady=PADY)

        ttk.Label(frm, text="Data sprzedaży:").grid(row=3, column=2, sticky=tk.E, padx=PADX, pady=PADY)
        self._de_sales_date = DateEntry(
            frm,
            width=12,
            date_pattern="yyyy-mm-dd",
            calendar_kw=_cal_kw,
        )
        self._de_sales_date.grid(row=3, column=3, sticky="w", padx=PADX, pady=PADY)

        ttk.Label(frm, text="Termin płat.:").grid(row=3, column=4, sticky=tk.E, padx=PADX, pady=PADY)
        self._de_payment_date = DateEntry(
            frm,
            width=12,
            date_pattern="yyyy-mm-dd",
            calendar_kw=_cal_kw,
        )
        self._de_payment_date.grid(row=3, column=5, sticky="w", padx=PADX, pady=PADY)

        ttk.Label(frm, text="Koryguje fakturę (ID):").grid(row=4, column=0, sticky=tk.E, padx=PADX, pady=PADY)
        ttk.Entry(frm, textvariable=self.var_corrected_id, width=12).grid(
            row=4, column=1, sticky="w", padx=PADX, pady=PADY
        )
        ttk.Label(frm, text="Przyczyna korekty:").grid(row=4, column=2, sticky=tk.E, padx=PADX, pady=PADY)
        ttk.Entry(frm, textvariable=self.var_correction_reason, width=52).grid(
            row=4, column=3, columnspan=5, sticky="ew", padx=PADX, pady=PADY
        )

        self._frm_ksef = ttk.LabelFrame(self, text="KSeF — historia wysyłek (API)")
        self._frm_ksef.pack(fill=tk.X, padx=10, pady=(0, 10))
        self._txt_ksef = tk.Text(
            self._frm_ksef,
            height=4,
            wrap=tk.WORD,
            state="disabled",
            font=("Segoe UI", 9),
        )
        self._txt_ksef.pack(fill=tk.X, padx=8, pady=8)

        # Przyciski
        btns = ttk.Frame(self)
        btns.pack(fill=tk.X, padx=10, pady=(0, 10))
        ttk.Button(btns, text="Nowa faktura", command=self.on_new).pack(side=tk.LEFT, padx=5)
        ttk.Button(btns, text="Zapisz", command=self.on_save).pack(side=tk.LEFT, padx=5)
        self.btn_delete = ttk.Button(btns, text="Usuń", command=self.on_delete)
        self.btn_delete.pack(side=tk.LEFT, padx=5)

        # ---- Detale (pozycje) – JEDYNA sekcja ----
        frm_d = ttk.LabelFrame(self, text="Pozycje")
        frm_d.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        frm_d.grid_columnconfigure(0, weight=1)
        frm_d.grid_rowconfigure(1, weight=1)

        # Formularz pozycji
        row_f = ttk.Frame(frm_d)
        row_f.grid(row=0, column=0, sticky="ew", padx=5, pady=5)
        for c in range(9):
            row_f.grid_columnconfigure(c, weight=0)
        # Pole usługi dostaje większość dostępnej szerokości.
        row_f.grid_columnconfigure(3, weight=1)

        ttk.Label(row_f, text="DetailId:").grid(row=0, column=0, sticky=tk.E, padx=PADX, pady=PADY)
        ttk.Entry(row_f, textvariable=self.var_detail_id, width=10, state="readonly")\
            .grid(row=0, column=1, sticky="w", padx=PADX, pady=PADY)

        ttk.Label(row_f, text="Usługa:").grid(row=0, column=2, sticky=tk.E, padx=PADX, pady=PADY)
        self.cb_service = ttk.Combobox(
            row_f,
            textvariable=self.var_service,
            state="normal",
            width=48,
            postcommand=self._refresh_service_filter_values,
        )
        self.cb_service.grid(row=0, column=3, sticky="ew", padx=PADX, pady=PADY)
        self.cb_service.bind("<KeyRelease>", self._on_service_search)

        ttk.Label(row_f, text="Ilość:").grid(row=0, column=4, sticky=tk.E, padx=PADX, pady=PADY)
        ttk.Entry(row_f, textvariable=self.var_quantity, width=12)\
            .grid(row=0, column=5, sticky="w", padx=PADX, pady=PADY)

        ttk.Button(row_f, text="Dodaj", command=self.on_add_detail).grid(row=0, column=6, padx=5, pady=PADY)
        ttk.Button(row_f, text="Zmień", command=self.on_update_detail).grid(row=0, column=7, padx=5, pady=PADY)
        ttk.Button(row_f, text="Usuń", command=self.on_delete_detail).grid(row=0, column=8, padx=5, pady=PADY)

        # Tabela pozycji (z kolumnami dopasowanymi do _fill_details_table)
        table_frame = ttk.Frame(frm_d)
        table_frame.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=1)

        self.tree_details = ttk.Treeview(
            table_frame,
            columns=(
                "InvoiceDetailId","ServiceName","UnitCode","Quantity",
                "UnitPrice","TaxValue","Netto","VAT","Brutto"
            ),
            show="headings",
            selectmode="browse"
        )

        heads = [
            ("InvoiceDetailId","ID",70,"e"),
            ("ServiceName","Usługa",260,"w"),
            ("UnitCode","Jm",60,"center"),
            ("Quantity","Ilość",80,"e"),
            ("UnitPrice","Cena",90,"e"),
            ("TaxValue","VAT %",70,"e"),
            ("Netto","Netto",100,"e"),
            ("VAT","VAT",100,"e"),
            ("Brutto","Brutto",110,"e"),
        ]
        for key, label, w, anchor in heads:
            self.tree_details.heading(key, text=label)
            self.tree_details.column(key, width=w, anchor=anchor, stretch=True)

        self.tree_details.bind("<<TreeviewSelect>>", self.on_select_detail)
        self.tree_details.grid(row=0, column=0, sticky="nsew")

        yscroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree_details.yview)
        xscroll = ttk.Scrollbar(table_frame, orient="horizontal", command=self.tree_details.xview)
        self.tree_details.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set) 
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")


    # ---------------------- LOOKUPS -------------------------
    def _load_lookups(self):
        # Organizacje
        org_rows = get_organizations()
        self._org_map = {(row["Name"] or f"Org {row['OrganizationId']}"): row["OrganizationId"] for row in org_rows}
        self._org_rev = {v: k for k, v in self._org_map.items()}
        self.cb_company["values"] = list(self._org_map.keys())
        self.cb_customer["values"] = list(self._org_map.keys())

        # Płatności
        pm_rows = get_payment_methods()
        self._pm_map = {row["Name"]: row["PaymentMethodId"] for row in pm_rows}
        self._pm_rev = {v: k for k, v in self._pm_map.items()}
        self.cb_payment["values"] = list(self._pm_map.keys())

        # Statusy
        st_rows = get_statuses()
        self._status_map = { row["Name"]: row["StatusId"] for row in st_rows }
        self._status_rev = { v: k for k, v in self._status_map.items() }
        self.cb_status["values"] = list(self._status_map.keys())

        # Typy FV
        tp_rows = get_invoice_types()
        self._type_map = {row["Name"]: row["TypeId"] for row in tp_rows}
        self._type_rev = {v: k for k, v in self._type_map.items()}
        self.cb_type["values"] = list(self._type_map.keys())

        # Usługi
        svc_rows = get_services()
        self._svc_map = {row["Name"]: row["ServiceId"] for row in svc_rows}
        self._svc_rev = {v: k for k, v in self._svc_map.items()}
        self._svc_labels = list(self._svc_map.keys())
        self.cb_service["values"] = self._svc_labels

        print(f"[DEBUG] lookups: org={len(self._org_map)}, pm={len(self._pm_map)}, st={len(self._status_map)}, tp={len(self._type_map)}, svc={len(self._svc_map)}")

    # ---------------------- HELPERS -------------------------
    def _today(self) -> str:
        return date.today().strftime(ISO_FMT)

    @staticmethod
    def _coerce_iso_date(val) -> date:
        if val is None:
            return date.today()
        t = str(val).strip()[:10]
        if len(t) >= 10 and t[4] == "-" and t[7] == "-":
            try:
                return date.fromisoformat(t)
            except ValueError:
                pass
        return date.today()

    def _date_str_from_entry(self, de: DateEntry) -> str:
        return de.get_date().strftime(ISO_FMT)

    def _refresh_service_filter_values(self) -> None:
        """Odświeża listę usług zgodnie z aktualnym filtrem wpisanym w comboboxie."""
        query = (self.var_service.get() or "").strip().lower()
        if not query:
            self.cb_service["values"] = self._svc_labels
            return
        filtered = [label for label in self._svc_labels if query in label.lower()]
        self.cb_service["values"] = filtered

    def _on_service_search(self, _evt=None) -> None:
        self._refresh_service_filter_values()

    def clear_form(self):
        # header
        self.var_invoice_id.set("")
        self.var_name.set("")
        self.var_is_add_addr.set(0)
        for v in (self.var_company, self.var_customer, self.var_payment, self.var_status, self.var_type):
            v.set("")
        # dates
        td = date.today()
        self._de_create_date.set_date(td)
        self._de_sales_date.set_date(td)
        self._de_payment_date.set_date(td)
        self.var_corrected_id.set("")
        self.var_correction_reason.set("")
        # details form
        self.var_detail_id.set("")
        self.var_service.set("")
        self.var_quantity.set("")
        # table
        for i in self.tree_details.get_children():
            self.tree_details.delete(i)
        self._loaded_company_id = None
        self._loaded_customer_id = None
        self._refresh_ksef_panel(None)
        self._refresh_delete_button_state()

    def _refresh_delete_button_state(self):
        if not getattr(self, "btn_delete", None):
            return
        vid = (self.var_invoice_id.get() or "").strip()
        if not vid or self._loaded_company_id is None or self._loaded_customer_id is None:
            self.btn_delete.configure(state="disabled")
            return
        try:
            inv_id = int(vid)
        except (ValueError, TypeError):
            self.btn_delete.configure(state="disabled")
            return
        ok, _msg = invoice_can_be_deleted(inv_id, self._loaded_company_id, self._loaded_customer_id)
        self.btn_delete.configure(state="normal" if ok else "disabled")

    def _refresh_ksef_panel(self, invoice_id: Optional[int] = None):
        if not hasattr(self, "_txt_ksef"):
            return
        self._txt_ksef.configure(state="normal")
        self._txt_ksef.delete("1.0", tk.END)
        if invoice_id is None:
            self._txt_ksef.insert(
                "1.0",
                "Brak powiązanych wysyłek KSeF (zapis w bazie po udanym „Wyślij do KSeF” z listy faktur).",
            )
        else:
            rows = get_ksef_submissions_for_invoice(invoice_id)
            if not rows:
                self._txt_ksef.insert("1.0", "Brak zapisów wysyłki KSeF dla tej faktury.")
            else:
                lines = []
                for row in rows:
                    ref = row["ReferenceNumber"]
                    sat = row["SentAt"] or ""
                    if "T" in sat:
                        sat = sat.replace("T", " ", 1)[:19]
                    lines.append(f"{sat} — {ref}")
                self._txt_ksef.insert("1.0", "\n".join(lines))
        self._txt_ksef.configure(state="disabled")

    def _set_defaults_if_available(self):
        if self.cb_company["values"]:
            self.cb_company.set(self.cb_company["values"][0])
        if self.cb_customer["values"]:
            self.cb_customer.set(self.cb_customer["values"][0])
        if self.cb_payment["values"]:
            self.cb_payment.set(self.cb_payment["values"][0])
        if self.cb_status["values"]:
            prefer = next((lbl for lbl in self.cb_status["values"] if "Szkic" in lbl or "SZKIC" in lbl.upper()), None)
            self.cb_status.set(prefer or self.cb_status["values"][0])
        if self.cb_type["values"]:
            self.cb_type.set(self.cb_type["values"][0])

    def _header_ids(self) -> Optional[dict]:
        """Zwraca słownik ID nagłówka na podstawie aktualnych wyborów w comboboxach."""
        try:
            company_id = self._org_map[self.var_company.get()]
            customer_id = self._org_map[self.var_customer.get()]
            payment_method_id = self._pm_map[self.var_payment.get()]
            status_id = self._status_map[self.var_status.get()]   # ← TU
            type_id = self._type_map[self.var_type.get()]
            return dict(
                CompanyId=company_id,
                CustomerId=customer_id,
                PaymentMethodId=payment_method_id,
                StatusId=status_id,
                TypeId=type_id
            )
        except KeyError:
            messagebox.showwarning("Walidacja", "Uzupełnij poprawnie Sprzedawcę, Nabywcę, Płatność, Status i Typ.")
            return None

    # ---------------------- LOAD / SAVE ---------------------
    def _clear_details_table(self):
        for i in self.tree_details.get_children():
            self.tree_details.delete(i)

    def _fill_details_table(self, details_rows):
        """Wypełnia tabelę; oczekuje kolumn jak w get_invoice_full -> details."""
        self._clear_details_table()
        count = 0
        for d in details_rows:
            qty = float(d["Quantity"] or 0)
            price = float(d["UnitPrice"] or 0)
            tax = float(d["TaxValue"] or 0)
            net = price * qty
            vat = round(net * tax / 100.0, 2)
            brutto = net + vat
            self.tree_details.insert(
                "",
                "end",
                values=(
                    d["InvoiceDetailId"],
                    d["ServiceName"],
                    d["UnitCode"],
                    f"{qty:.2f}",
                    f"{price:.2f}",
                    f"{tax:.2f}",
                    f"{net:.2f}",
                    f"{vat:.2f}",
                    f"{brutto:.2f}",
                )
            )
            count += 1
        print(f"[DEBUG] _fill_details_table: inserted {count} rows")

    def load_invoice(self, invoice_id: int):
        """Ładuje nagłówek i pozycje istniejącej faktury."""
        print(f"[DEBUG] InvoiceCrud.load_invoice({invoice_id})")
        self._current_invoice_id = int(invoice_id)

        header, details = get_invoice_full(invoice_id)
        if header is None:
            print(f"[DEBUG] load_invoice: header is None for id={invoice_id}")
            messagebox.showerror("Błąd", f"Nie znaleziono faktury ID = {invoice_id}")
            return


        # Nagłówek -> formularz
        self.var_invoice_id.set(header["InvoiceId"])
        self.var_name.set(header["Name"] or "")
        self._de_create_date.set_date(self._coerce_iso_date(header.get("CreateDate")))
        self._de_sales_date.set_date(self._coerce_iso_date(header.get("SalesDate")))
        self._de_payment_date.set_date(self._coerce_iso_date(header.get("PaymentDate")))

        # Comboboxy po ID (reverse mapy z _load_lookups)
        self.var_company.set(self._org_rev.get(header["CompanyId"], ""))
        self.var_customer.set(self._org_rev.get(header["CustomerId"], ""))
        self.var_payment.set(self._pm_rev.get(header["PaymentMethodId"], ""))
        self.var_status.set(self._status_rev.get(header["StatusId"], ""))
        self.var_type.set(self._type_rev.get(header["TypeId"], ""))

        cid = header.get("CorrectedInvoiceId")
        if cid is not None:
            try:
                self.var_corrected_id.set(str(int(cid)))
            except (TypeError, ValueError):
                self.var_corrected_id.set("")
        else:
            self.var_corrected_id.set("")
        self.var_correction_reason.set(header.get("CorrectionReason") or "")

        # Detale -> tabela
        print(f"[DEBUG] load_invoice: details rows = {len(details)} for id={invoice_id}")
        self._fill_details_table(details)
        self._loaded_company_id = int(header["CompanyId"])
        self._loaded_customer_id = int(header["CustomerId"])
        self._refresh_ksef_panel(invoice_id)
        self._refresh_delete_button_state()

    def prepare_correction_from(self, base_invoice_id: int):
        """Nowa faktura typu Korekta, powiązana z fakturą base_invoice_id (lista główna)."""
        self.on_new()
        self.var_corrected_id.set(str(int(base_invoice_id)))
        kname = next((n for n in self._type_map if "korekt" in n.lower()), None)
        if kname:
            self.var_type.set(kname)
        h, _ = get_invoice_full(int(base_invoice_id))
        if not h:
            messagebox.showerror("Korekta", f"Nie znaleziono faktury ID={base_invoice_id}.")
            return
        self.var_company.set(self._org_rev.get(h["CompanyId"], ""))
        self.var_customer.set(self._org_rev.get(h["CustomerId"], ""))
        self.var_name.set("")
        self.var_invoice_id.set("")
        td = date.today()
        self._de_create_date.set_date(td)
        self._de_sales_date.set_date(td)
        self._de_payment_date.set_date(td)
        self._clear_details_table()
        self._refresh_ksef_panel(None)

    def on_new(self):
        """Przygotuj czysty formularz."""
        self.clear_form()
        self._set_defaults_if_available()

    def on_save(self):
        ids = self._header_ids()
        if not ids:
            return
        name = self.var_name.get().strip() or None
        type_name = (self.var_type.get() or "").lower()
        is_kor = "korekt" in type_name
        corr_id = None
        reason = (self.var_correction_reason.get() or "").strip() or None
        if is_kor:
            raw = (self.var_corrected_id.get() or "").strip()
            if not raw:
                messagebox.showwarning("Walidacja", "Typ „Korekta”: wpisz ID faktury korygowanej.")
                return
            try:
                corr_id = int(raw)
            except ValueError:
                messagebox.showwarning("Walidacja", "ID faktury korygowanej musi być liczbą całkowitą.")
                return
            try:
                cur_id = int(self.var_invoice_id.get()) if self.var_invoice_id.get() else None
                validate_correction_link(
                    company_id=ids["CompanyId"],
                    customer_id=ids["CustomerId"],
                    corrected_invoice_id=corr_id,
                    current_invoice_id=cur_id,
                )
            except ValueError as e:
                messagebox.showwarning("Korekta", str(e))
                return
        try:
            if not self.var_invoice_id.get():
                # CREATE
                new_id = create_invoice(
                    company_id=ids["CompanyId"],
                    customer_id=ids["CustomerId"],
                    payment_method_id=ids["PaymentMethodId"],
                    status_id=ids["StatusId"],
                    type_id=ids["TypeId"],
                    is_additional_address=int(self.var_is_add_addr.get() or 0),
                    name=name,
                    create_date=self._date_str_from_entry(self._de_create_date) or None,
                    sales_date=self._date_str_from_entry(self._de_sales_date) or None,
                    payment_date=self._date_str_from_entry(self._de_payment_date) or None,
                    corrected_invoice_id=corr_id if is_kor else None,
                    correction_reason=reason if is_kor else None,
                )
                self.var_invoice_id.set(str(new_id))
                self._loaded_company_id = int(ids["CompanyId"])
                self._loaded_customer_id = int(ids["CustomerId"])
                self._refresh_ksef_panel(new_id)
                self._refresh_delete_button_state()
                messagebox.showinfo("Sukces", f"Utworzono fakturę (ID={new_id}).")
            else:
                # UPDATE
                inv_id = int(self.var_invoice_id.get())
                ok = update_invoice(
                    inv_id,
                    CompanyId=ids["CompanyId"],
                    CustomerId=ids["CustomerId"],
                    PaymentMethodId=ids["PaymentMethodId"],
                    StatusId=ids["StatusId"],
                    TypeId=ids["TypeId"],
                    IsAdditionalAddress=int(self.var_is_add_addr.get() or 0),
                    Name=name,
                    CreateDate=self._date_str_from_entry(self._de_create_date),
                    SalesDate=self._date_str_from_entry(self._de_sales_date),
                    PaymentDate=self._date_str_from_entry(self._de_payment_date),
                    CorrectedInvoiceId=corr_id if is_kor else None,
                    CorrectionReason=reason if is_kor else None,
                )
                if ok:
                    self._loaded_company_id = int(ids["CompanyId"])
                    self._loaded_customer_id = int(ids["CustomerId"])
                    messagebox.showinfo("Sukces", "Zapisano zmiany.")
                    self._refresh_ksef_panel(inv_id)
                    self._refresh_delete_button_state()
                else:
                    messagebox.showwarning("Uwaga", "Brak zmian lub faktura nie istnieje.")
        except Exception as e:
            messagebox.showerror("Błąd zapisu", str(e))

    def on_delete(self):
        if not self.var_invoice_id.get():
            messagebox.showwarning("Walidacja", "Brak wybranej faktury do usunięcia.")
            return
        inv_id = int(self.var_invoice_id.get())
        if self._loaded_company_id is None or self._loaded_customer_id is None:
            messagebox.showwarning("Walidacja", "Brak danych faktury — odśwież okno.")
            return
        ok, reason = invoice_can_be_deleted(inv_id, self._loaded_company_id, self._loaded_customer_id)
        if not ok:
            messagebox.showwarning("Usuwanie", reason)
            return
        if not messagebox.askyesno("Potwierdzenie", f"Usunąć fakturę ID={inv_id}? Operacja nieodwracalna."):
            return
        try:
            if delete_invoice(inv_id):
                messagebox.showinfo("Sukces", "Usunięto fakturę.")
                self.on_new()
            else:
                messagebox.showwarning("Uwaga", "Nie znaleziono faktury do usunięcia.")
        except Exception as e:
            messagebox.showerror("Błąd usuwania", str(e))

    # --------------------- DETAILS CRUD ---------------------
    def on_select_detail(self, _evt=None):
        sel = self.tree_details.selection()
        if not sel:
            return
        vals = self.tree_details.item(sel[0], "values")
        # kolumny: 0=DetailId, 1=ServiceName, 2=UnitCode, 3=Quantity, ...
        self.var_detail_id.set(vals[0] or "")
        self.cb_service.set(vals[1] or "")
        self.var_quantity.set(vals[3] or "")

    def _require_invoice_id(self) -> Optional[int]:
        if not self.var_invoice_id.get():
            messagebox.showwarning("Walidacja", "Najpierw zapisz nagłówek faktury (musi mieć ID).")
            return None
        return int(self.var_invoice_id.get())

    def _service_id_from_ui(self) -> Optional[int]:
        lbl = self.var_service.get()
        if not lbl or lbl not in self._svc_map:
            messagebox.showwarning("Walidacja", "Wybierz usługę z listy.")
            return None
        return self._svc_map[lbl]

    def _quantity_from_ui(self) -> Optional[float]:
        try:
            q = float(str(self.var_quantity.get()).replace(",", "."))
            return q
        except ValueError:
            messagebox.showwarning("Walidacja", "Ilość musi być liczbą (np. 1.00).")
            return None

    def on_add_detail(self):
        inv_id = self._require_invoice_id()
        if inv_id is None:
            return
        srv_id = self._service_id_from_ui()
        if srv_id is None:
            return
        qty = self._quantity_from_ui()
        if qty is None:
            return
        try:
            new_id = add_detail(inv_id, srv_id, qty)
            self.load_invoice(inv_id)  # odśwież listę pozycji + sumy
            messagebox.showinfo("Sukces", f"Dodano pozycję (ID={new_id}).")
        except Exception as e:
            messagebox.showerror("Błąd dodawania pozycji", str(e))

    def on_update_detail(self):
        if not self.var_detail_id.get():
            messagebox.showwarning("Walidacja", "Wybierz pozycję do aktualizacji.")
            return
        inv_id = self._require_invoice_id()
        if inv_id is None:
            return
        srv_id = self._service_id_from_ui()
        if srv_id is None:
            return
        qty = self._quantity_from_ui()
        if qty is None:
            return
        try:
            ok = update_detail(int(self.var_detail_id.get()), service_id=srv_id, quantity=qty)
            if ok:
                self.load_invoice(inv_id)
                messagebox.showinfo("Sukces", "Zaktualizowano pozycję.")
            else:
                messagebox.showwarning("Uwaga", "Brak zmian lub pozycja nie istnieje.")
        except Exception as e:
            messagebox.showerror("Błąd aktualizacji pozycji", str(e))

    def on_delete_detail(self):
        if not self.var_detail_id.get():
            messagebox.showwarning("Walidacja", "Wybierz pozycję do usunięcia.")
            return
        inv_id = self._require_invoice_id()
        if inv_id is None:
            return
        if not messagebox.askyesno("Potwierdzenie", f"Usunąć pozycję ID={self.var_detail_id.get()}?"):
            return
        try:
            ok = delete_detail(int(self.var_detail_id.get()))
            if ok:
                self.load_invoice(inv_id)
                messagebox.showinfo("Sukces", "Usunięto pozycję.")
            else:
                messagebox.showwarning("Uwaga", "Nie znaleziono pozycji do usunięcia.")
        except Exception as e:
            messagebox.showerror("Błąd usuwania pozycji", str(e))
