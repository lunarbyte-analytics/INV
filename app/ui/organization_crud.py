import threading
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

from ..ceidg.hd_client import (
    CeidgHdError,
    CeidgNoDataError,
    fetch_firma_by_nip,
    flat_firma_for_org,
    get_ceidg_hd_token,
    merge_pref,
    normalize_nip_digits,
)
from ..models import (
    create_organization,
    delete_organization,
    get_address_all,
    get_address_by_id,
    get_organization_all,
    get_organization_by_id,
    update_address,
    update_organization,
)
from ..models.record_source import RECORD_SOURCE_CEIDG_IMPORT, RECORD_SOURCE_USER, record_source_label_pl

PADX = 8
PADY = 6

class OrganizationCrud(tk.Toplevel):
    def __init__(self, master=None):
        super().__init__(master)
        self.title("Organizacje – CRUD (SQLite)")
        self.geometry("1200x660")
        self.resizable(True, True)
        self._build_widgets()
        self._load_lookups()
        self.refresh_table()

    # ----------------------- UI -----------------------
    def _build_widgets(self):
        # --- FORM ---
        frm = ttk.LabelFrame(self, text="Formularz")
        frm.pack(fill=tk.X, padx=10, pady=10)

        for c in range(6):
            frm.grid_columnconfigure(c, weight=0)
        frm.grid_columnconfigure(1, weight=1)
        frm.grid_columnconfigure(3, weight=1)
        frm.grid_columnconfigure(5, weight=1)

        # ID
        ttk.Label(frm, text="ID:").grid(row=0, column=0, sticky=tk.E, padx=PADX, pady=PADY)
        self.var_id = tk.StringVar()
        ttk.Entry(frm, textvariable=self.var_id, width=10, state="readonly")\
            .grid(row=0, column=1, sticky="w", padx=PADX, pady=PADY)

        # Name
        ttk.Label(frm, text="Nazwa:").grid(row=0, column=2, sticky=tk.E, padx=PADX, pady=PADY)
        self.var_name = tk.StringVar()
        ttk.Entry(frm, textvariable=self.var_name)\
            .grid(row=0, column=3, sticky="ew", padx=PADX, pady=PADY)

        # Phone
        ttk.Label(frm, text="Telefon:").grid(row=0, column=4, sticky=tk.E, padx=PADX, pady=PADY)
        self.var_phone = tk.StringVar()
        ttk.Entry(frm, textvariable=self.var_phone)\
            .grid(row=0, column=5, sticky="ew", padx=PADX, pady=PADY)

        # Address
        ttk.Label(frm, text="Adres:").grid(row=1, column=0, sticky=tk.E, padx=PADX, pady=PADY)
        self.var_addr = tk.StringVar()
        self.cb_addr = ttk.Combobox(frm, textvariable=self.var_addr, state="readonly")
        self.cb_addr.grid(row=1, column=1, sticky="ew", padx=PADX, pady=PADY)

        # Additional Address
        ttk.Label(frm, text="Adres dodatkowy:").grid(row=1, column=2, sticky=tk.E, padx=PADX, pady=PADY)
        self.var_add_addr = tk.StringVar()
        self.cb_add_addr = ttk.Combobox(frm, textvariable=self.var_add_addr, state="readonly")
        self.cb_add_addr.grid(row=1, column=3, sticky="ew", padx=PADX, pady=PADY)

        # Email
        ttk.Label(frm, text="Email:").grid(row=1, column=4, sticky=tk.E, padx=PADX, pady=PADY)
        self.var_email = tk.StringVar()
        ttk.Entry(frm, textvariable=self.var_email)\
            .grid(row=1, column=5, sticky="ew", padx=PADX, pady=PADY)

        # NIP / REGON / PESEL
        ttk.Label(frm, text="NIP:").grid(row=2, column=0, sticky=tk.E, padx=PADX, pady=PADY)
        nip_row = ttk.Frame(frm)
        nip_row.grid(row=2, column=1, sticky="ew", padx=PADX, pady=PADY)
        nip_row.columnconfigure(0, weight=1)
        self.var_org1 = tk.StringVar()
        ttk.Entry(nip_row, textvariable=self.var_org1).grid(row=0, column=0, sticky="ew")
        ttk.Button(
            nip_row,
            text="Import z CEIDG (API HD)",
            command=self.on_import_ceidg,
        ).grid(row=0, column=1, padx=(8, 0))

        ttk.Label(frm, text="REGON:").grid(row=2, column=2, sticky=tk.E, padx=PADX, pady=PADY)
        self.var_org2 = tk.StringVar()
        ttk.Entry(frm, textvariable=self.var_org2)\
            .grid(row=2, column=3, sticky="ew", padx=PADX, pady=PADY)

        ttk.Label(frm, text="PESEL:").grid(row=2, column=4, sticky=tk.E, padx=PADX, pady=PADY)
        self.var_org3 = tk.StringVar()
        ttk.Entry(frm, textvariable=self.var_org3)\
            .grid(row=2, column=5, sticky="ew", padx=PADX, pady=PADY)

        # Bank account
        ttk.Label(frm, text="Konto bankowe:").grid(row=3, column=0, sticky=tk.E, padx=PADX, pady=PADY)
        self.var_bank = tk.StringVar()
        ttk.Entry(frm, textvariable=self.var_bank)\
            .grid(row=3, column=1, columnspan=5, sticky="ew", padx=PADX, pady=PADY)

        # --- BUTTONS ---
        btns = ttk.Frame(self)
        btns.pack(fill=tk.X, padx=10, pady=(0, 10))
        ttk.Button(btns, text="Dodaj", command=self.on_add).pack(side=tk.LEFT, padx=5)
        ttk.Button(btns, text="Aktualizuj", command=self.on_update).pack(side=tk.LEFT, padx=5)
        ttk.Button(btns, text="Usuń", command=self.on_delete).pack(side=tk.LEFT, padx=5)
        ttk.Button(btns, text="Odśwież", command=self.refresh_table).pack(side=tk.RIGHT, padx=5)

        # --- TABLE ---
        table_frame = ttk.Frame(self)
        table_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)

        # Dodajemy NIP/REGON/PESEL oraz ukryte AddressId/AdditionalAddressId
        self.tree = ttk.Treeview(
            table_frame,
            columns=(
                "OrganizationId",
                "Name",
                "Phone",
                "Email",
                "OrgNbr1",
                "OrgNbr2",
                "OrgNbr3",
                "AddressCity",
                "AddressCountry",
                "BankAccountNbr",
                "RecordSource",
                "AddressId",
                "AdditionalAddressId",
            ),
            show="headings",
        )

        cols = [
            ("OrganizationId", "ID", 60, tk.E),
            ("Name", "Nazwa", 220, tk.W),
            ("Phone", "Telefon", 120, tk.W),
            ("Email", "Email", 180, tk.W),
            ("OrgNbr1", "NIP", 100, tk.W),
            ("OrgNbr2", "REGON", 100, tk.W),
            ("OrgNbr3", "PESEL", 100, tk.W),
            ("AddressCity", "Miasto", 120, tk.W),
            ("AddressCountry", "Kraj", 100, tk.W),
            ("BankAccountNbr", "Konto", 180, tk.W),
            ("RecordSource", "Źródło", 100, tk.W),
            # ukryte:
            ("AddressId", "AddressId", 0, tk.W),
            ("AdditionalAddressId", "AdditionalAddressId", 0, tk.W),
        ]
        for key, label, width, anchor in cols:
            self.tree.heading(key, text=label)
            self.tree.column(key, width=width, anchor=anchor, stretch=(width != 0))

        self.tree.grid(row=0, column=0, sticky="nsew")
        self.tree.bind("<<TreeviewSelect>>", self.on_select_row)

        yscroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        xscroll = ttk.Scrollbar(table_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")

    # -------------------- DATA --------------------
    def _load_lookups(self):
        addresses = get_address_all()

        def _lbl(a):
            street = " ".join(x for x in [a["StreetName"], a["StreetNumber"]] if x)
            city = a["City"] or ""
            country = a["Country"] or ""
            return f"{city} – {street} ({country})".strip()

        # label -> id oraz id -> label
        self._addr_by_label = {_lbl(a): a["AddressId"] for a in addresses}
        self._label_by_addr = {v: k for k, v in self._addr_by_label.items()}

        vals = list(self._addr_by_label.keys())
        self.cb_addr["values"] = vals
        self.cb_add_addr["values"] = [""] + vals

    def refresh_table(self):
        def _g(row, key, default=None):
            try:
                # sqlite3.Row wspiera row.keys() oraz indeksowanie nazwą
                return row[key] if key in row.keys() else default
            except Exception:
                return default

        for i in self.tree.get_children():
            self.tree.delete(i)

        for r in get_organization_all():
            src = _g(r, "RecordSource", "user")
            self.tree.insert(
                "",
                tk.END,
                values=(
                    _g(r, "OrganizationId", ""),
                    _g(r, "Name", ""),
                    _g(r, "Phone", ""),
                    _g(r, "Email", ""),
                    _g(r, "OrgNbr1", ""),
                    _g(r, "OrgNbr2", ""),
                    _g(r, "OrgNbr3", ""),
                    _g(r, "AddressCity", ""),
                    _g(r, "AddressCountry", ""),
                    _g(r, "BankAccountNbr", ""),
                    record_source_label_pl(src),
                    _g(r, "AddressId", ""),
                    _g(r, "AdditionalAddressId", ""),
                ),
            )

    # ------------------- ACTIONS -------------------
    def on_add(self):
        try:
            addr = self._addr_by_label[self.var_addr.get()]
            add_addr = self._addr_by_label.get(self.var_add_addr.get())
            new_id = create_organization(
                addr, add_addr,
                self.var_name.get().strip() or None,
                self.var_phone.get().strip() or None,
                self.var_email.get().strip() or None,
                self.var_org1.get().strip() or None,
                self.var_org2.get().strip() or None,
                self.var_org3.get().strip() or None,
                self.var_bank.get().strip() or None,
            )
            self.refresh_table()
            messagebox.showinfo("Sukces", f"Dodano organizację (ID={new_id}).")
        except Exception as e:
            messagebox.showerror("Błąd", str(e))

    def on_update(self):
        if not self.var_id.get():
            messagebox.showwarning("Błąd", "Nie wybrano organizacji.")
            return
        try:
            org_id = int(self.var_id.get())
            addr = self._addr_by_label[self.var_addr.get()]
            add_addr = self._addr_by_label.get(self.var_add_addr.get())
            ok = update_organization(
                org_id,
                AddressId=addr,
                AdditionalAddressId=add_addr,
                Name=self.var_name.get().strip() or None,
                Phone=self.var_phone.get().strip() or None,
                Email=self.var_email.get().strip() or None,
                OrgNbr1=self.var_org1.get().strip() or None,
                OrgNbr2=self.var_org2.get().strip() or None,
                OrgNbr3=self.var_org3.get().strip() or None,
                BankAccountNbr=self.var_bank.get().strip() or None,
            )
            if ok:
                self.refresh_table()
                messagebox.showinfo("Sukces", "Zaktualizowano dane organizacji.")
        except Exception as e:
            messagebox.showerror("Błąd", str(e))

    def on_delete(self):
        if not self.var_id.get():
            messagebox.showwarning("Walidacja", "Wybierz rekord do usunięcia.")
            return
        try:
            org_id = int(self.var_id.get())
            if messagebox.askyesno("Potwierdzenie", f"Usunąć OrganizationId={org_id}?"):
                delete_organization(org_id)
                self.refresh_table()
        except Exception as e:
            messagebox.showerror("Błąd", str(e))

    def on_select_row(self, _event=None):
        sel = self.tree.selection()
        if not sel:
            return
        values = self.tree.item(sel[0], "values")

        self.var_id.set(values[0])
        self.var_name.set(values[1])
        self.var_phone.set(values[2])
        self.var_email.set(values[3])
        self.var_org1.set(values[4])   # NIP
        self.var_org2.set(values[5])   # REGON
        self.var_org3.set(values[6])   # PESEL
        self.var_bank.set(values[9])

        # Odtwórz comboboxy na podstawie ukrytych ID (po kolumnie Źródło)
        addr_id = values[11]
        add_addr_id = values[12]

        try:
            addr_id = int(addr_id) if addr_id not in ("", None) else None
        except Exception:
            addr_id = None
        try:
            add_addr_id = int(add_addr_id) if add_addr_id not in ("", None) else None
        except Exception:
            add_addr_id = None

        self.var_addr.set(self._label_by_addr.get(addr_id, "") if addr_id is not None else "")
        self.var_add_addr.set(self._label_by_addr.get(add_addr_id, "") if add_addr_id is not None else "")

    def on_import_ceidg(self):
        raw = (self.var_org1.get() or "").strip()
        if not raw:
            raw = simpledialog.askstring(
                "NIP",
                "Podaj NIP (10 cyfr) do zapytania w Hurtowni danych CEIDG:",
                parent=self,
            )
            if not raw:
                return
            self.var_org1.set(raw.strip())

        try:
            normalize_nip_digits(self.var_org1.get())
        except ValueError as e:
            messagebox.showwarning("NIP", str(e), parent=self)
            return

        if not get_ceidg_hd_token():
            messagebox.showwarning(
                "Token API",
                "Brak tokenu Hurtowni danych CEIDG.\n\n"
                "Zarejestruj się na https://dane.biznes.gov.pl/ i ustaw zmienną środowiskową:\n"
                "  CEIDG_HD_API_TOKEN=<token JWT z portalu>\n\n"
                "(Alternatywnie: BIZNES_GOV_HD_TOKEN)",
                parent=self,
            )
            return

        nip_query = self.var_org1.get()

        def work():
            try:
                firma = fetch_firma_by_nip(nip_query)
                flat = flat_firma_for_org(firma)
                self.after(0, lambda: self._apply_ceidg_import(flat))
            except CeidgNoDataError as e:
                self.after(0, lambda m=str(e): messagebox.showinfo("CEIDG", m, parent=self))
            except CeidgHdError as e:
                self.after(0, lambda m=str(e): messagebox.showerror("CEIDG", m, parent=self))
            except Exception as e:
                self.after(0, lambda m=str(e): messagebox.showerror("CEIDG", m, parent=self))

        threading.Thread(target=work, daemon=True).start()

    def _apply_ceidg_import(self, flat: dict):
        """Uzupełnia puste pola formularza i — jeśli jest zapisany rekord — puste pola w bazie."""
        self._merge_ceidg_into_form(flat)
        vid = (self.var_id.get() or "").strip()
        if not vid:
            messagebox.showinfo(
                "CEIDG",
                "Uzupełniono brakujące pola w formularzu. Kliknij „Dodaj”, aby zapisać nową organizację.",
                parent=self,
            )
            return
        try:
            oid = int(vid)
        except ValueError:
            return

        did_db = self._merge_ceidg_into_db(oid, flat)
        self._load_lookups()
        self.refresh_table()
        for item in self.tree.get_children():
            vals = self.tree.item(item, "values")
            if vals and str(vals[0]) == str(oid):
                self.tree.selection_set(item)
                self.tree.focus(item)
                self.tree.see(item)
                self.on_select_row()
                break

        if did_db:
            messagebox.showinfo(
                "CEIDG",
                "Uzupełniono brakujące dane z Hurtowni CEIDG (zapis w bazie).",
                parent=self,
            )
        else:
            messagebox.showinfo(
                "CEIDG",
                "W bazie nie było pustych pól do uzupełnienia. "
                "Formularz uzupełniono tylko tam, gdzie pola były puste.",
                parent=self,
            )

    def _merge_ceidg_into_form(self, flat: dict):
        def set_if_empty(var: tk.StringVar, val: str | None):
            m = merge_pref(var.get(), val)
            if m is not None:
                var.set(m)

        set_if_empty(self.var_name, flat.get("name"))
        set_if_empty(self.var_phone, flat.get("phone"))
        set_if_empty(self.var_email, flat.get("email"))
        set_if_empty(self.var_org1, flat.get("org_nip"))
        set_if_empty(self.var_org2, flat.get("org_regon"))

    def _merge_ceidg_into_db(self, org_id: int, flat: dict) -> bool:
        """Zwraca True, jeśli wykonano UPDATE w bazie."""
        org = get_organization_by_id(org_id)
        if not org:
            return False

        org_updates: dict = {}
        for col, key in (
            ("Name", "name"),
            ("Phone", "phone"),
            ("Email", "email"),
            ("OrgNbr1", "org_nip"),
            ("OrgNbr2", "org_regon"),
        ):
            m = merge_pref(org[col], flat.get(key))
            if m is not None:
                org_updates[col] = m

        rs = org["RecordSource"] if "RecordSource" in org.keys() else None
        should_tag = rs in (None, "", RECORD_SOURCE_USER)

        addr_id = org["AddressId"]
        addr = get_address_by_id(addr_id) if addr_id else None
        addr_updates: dict = {}
        if addr:
            for sql_col, ukw, flat_key in (
                ("StreetName", "street_name", "street_name"),
                ("StreetNumber", "street_number", "street_number"),
                ("ZipCode", "zip_code", "zip_code"),
                ("City", "city", "city"),
                ("Country", "country", "country"),
            ):
                m = merge_pref(addr[sql_col], flat.get(flat_key))
                if m is not None:
                    addr_updates[ukw] = m

        if should_tag and (org_updates or addr_updates):
            org_updates["RecordSource"] = RECORD_SOURCE_CEIDG_IMPORT

        did = False
        if addr_updates:
            if update_address(addr_id, **addr_updates):
                did = True
        if org_updates:
            if update_organization(org_id, **org_updates):
                did = True
        return did
