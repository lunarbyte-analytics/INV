import threading
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

from ..ceidg.debug_log import ceidg_debug
from ..ceidg.hd_client import (
    CeidgHdError,
    CeidgNoDataError,
    fetch_firma_by_nip,
    flat_firma_for_org,
    get_ceidg_hd_token,
    normalize_nip_digits,
)
from ..gus.bir_client import (
    GusBirError,
    GusNoDataError,
    fetch_podmiot_by_nip,
    flat_podmiot_for_org,
    get_gus_bir_key,
)
from ..gus.debug_log import gus_debug
from ..models import (
    create_address,
    create_organization,
    delete_organization,
    get_address_all,
    get_address_by_id,
    get_organization_all,
    get_organization_by_id,
    update_address,
    update_organization,
)
from ..models.record_source import (
    RECORD_SOURCE_CEIDG_IMPORT,
    RECORD_SOURCE_GUS_IMPORT,
    record_source_label_pl,
)

PADX = 8
PADY = 6

class OrganizationCrud(tk.Toplevel):
    def __init__(self, master=None):
        super().__init__(master)
        self.title("Organizacje – CRUD (SQLite)")
        self.geometry("1200x760")
        self.resizable(True, True)
        self._editing_addr_id: int | None = None
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

        # Email
        ttk.Label(frm, text="Email:").grid(row=1, column=0, sticky=tk.E, padx=PADX, pady=PADY)
        self.var_email = tk.StringVar()
        ttk.Entry(frm, textvariable=self.var_email)\
            .grid(row=1, column=1, sticky="ew", padx=PADX, pady=PADY)

        # Additional Address (opcjonalnie z listy)
        ttk.Label(frm, text="Adres dodatkowy:").grid(row=1, column=2, sticky=tk.E, padx=PADX, pady=PADY)
        self.var_add_addr = tk.StringVar()
        self.cb_add_addr = ttk.Combobox(frm, textvariable=self.var_add_addr, state="readonly")
        self.cb_add_addr.grid(row=1, column=3, sticky="ew", padx=PADX, pady=PADY)

        # NIP / REGON / PESEL
        ttk.Label(frm, text="NIP:").grid(row=2, column=0, sticky=tk.E, padx=PADX, pady=PADY)
        nip_row = ttk.Frame(frm)
        nip_row.grid(row=2, column=1, sticky="ew", padx=PADX, pady=PADY)
        nip_row.columnconfigure(0, weight=1)
        self.var_org1 = tk.StringVar()
        ttk.Entry(nip_row, textvariable=self.var_org1).grid(row=0, column=0, sticky="ew")
        ttk.Button(
            nip_row,
            text="Import CEIDG / GUS",
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

        # --- Adres główny (wpisywany w tym oknie) ---
        addr_frm = ttk.LabelFrame(frm, text="Adres główny")
        addr_frm.grid(row=4, column=0, columnspan=6, sticky="ew", padx=PADX, pady=(PADY, 2))
        for c in range(6):
            addr_frm.grid_columnconfigure(c, weight=0)
        addr_frm.grid_columnconfigure(1, weight=1)
        addr_frm.grid_columnconfigure(3, weight=1)
        addr_frm.grid_columnconfigure(5, weight=1)

        ttk.Label(addr_frm, text="Załaduj z listy:").grid(
            row=0, column=0, sticky=tk.E, padx=PADX, pady=PADY
        )
        self.var_addr_pick = tk.StringVar()
        self.cb_addr_pick = ttk.Combobox(
            addr_frm, textvariable=self.var_addr_pick, state="readonly"
        )
        self.cb_addr_pick.grid(row=0, column=1, columnspan=3, sticky="ew", padx=PADX, pady=PADY)
        self.cb_addr_pick.bind("<<ComboboxSelected>>", self._on_pick_existing_address)
        ttk.Button(
            addr_frm,
            text="Wyczyść adres",
            command=self._clear_address_fields,
        ).grid(row=0, column=4, columnspan=2, sticky="w", padx=PADX, pady=PADY)

        ttk.Label(addr_frm, text="Ulica:").grid(row=1, column=0, sticky=tk.E, padx=PADX, pady=PADY)
        self.var_street = tk.StringVar()
        ttk.Entry(addr_frm, textvariable=self.var_street)\
            .grid(row=1, column=1, sticky="ew", padx=PADX, pady=PADY)

        ttk.Label(addr_frm, text="Nr:").grid(row=1, column=2, sticky=tk.E, padx=PADX, pady=PADY)
        self.var_street_no = tk.StringVar()
        ttk.Entry(addr_frm, textvariable=self.var_street_no, width=12)\
            .grid(row=1, column=3, sticky="w", padx=PADX, pady=PADY)

        ttk.Label(addr_frm, text="Kod pocztowy:").grid(
            row=1, column=4, sticky=tk.E, padx=PADX, pady=PADY
        )
        self.var_zip = tk.StringVar()
        ttk.Entry(addr_frm, textvariable=self.var_zip, width=12)\
            .grid(row=1, column=5, sticky="w", padx=PADX, pady=PADY)

        ttk.Label(addr_frm, text="Miasto:").grid(row=2, column=0, sticky=tk.E, padx=PADX, pady=PADY)
        self.var_city = tk.StringVar()
        ttk.Entry(addr_frm, textvariable=self.var_city)\
            .grid(row=2, column=1, sticky="ew", padx=PADX, pady=PADY)

        ttk.Label(addr_frm, text="Kraj:").grid(row=2, column=2, sticky=tk.E, padx=PADX, pady=PADY)
        self.var_country = tk.StringVar(value="Polska")
        ttk.Entry(addr_frm, textvariable=self.var_country)\
            .grid(row=2, column=3, sticky="ew", padx=PADX, pady=PADY)

        # --- BUTTONS ---
        btns = ttk.Frame(self)
        btns.pack(fill=tk.X, padx=10, pady=(0, 10))
        ttk.Button(btns, text="Dodaj", command=self.on_add).pack(side=tk.LEFT, padx=5)
        ttk.Button(btns, text="Aktualizuj", command=self.on_update).pack(side=tk.LEFT, padx=5)
        ttk.Button(btns, text="Usuń", command=self.on_delete).pack(side=tk.LEFT, padx=5)
        ttk.Button(btns, text="Wyczyść formularz", command=self.clear_form).pack(side=tk.LEFT, padx=5)
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

        vals = [""] + list(self._addr_by_label.keys())
        self.cb_addr_pick["values"] = vals
        self.cb_add_addr["values"] = vals

    def _clear_address_fields(self):
        self.var_addr_pick.set("")
        self.var_street.set("")
        self.var_street_no.set("")
        self.var_zip.set("")
        self.var_city.set("")
        self.var_country.set("Polska")
        # przy edycji istniejącej org nie gubimy AddressId — aktualizacja nadpisze pola
        if not (self.var_id.get() or "").strip():
            self._editing_addr_id = None

    def _fill_address_fields_from_row(self, addr) -> None:
        if not addr:
            self._clear_address_fields()
            self._editing_addr_id = None
            return
        self._editing_addr_id = int(addr["AddressId"])
        self.var_street.set(addr["StreetName"] or "")
        self.var_street_no.set(addr["StreetNumber"] or "")
        self.var_zip.set(addr["ZipCode"] or "")
        self.var_city.set(addr["City"] or "")
        self.var_country.set(addr["Country"] or "Polska")
        self.var_addr_pick.set(self._label_by_addr.get(self._editing_addr_id, ""))

    def _on_pick_existing_address(self, _event=None):
        label = (self.var_addr_pick.get() or "").strip()
        if not label:
            return
        addr_id = self._addr_by_label.get(label)
        if not addr_id:
            return
        addr = get_address_by_id(addr_id)
        self._fill_address_fields_from_row(addr)

    def _read_address_from_form(self) -> tuple[str, str, str, str, str]:
        street = (self.var_street.get() or "").strip()
        street_no = (self.var_street_no.get() or "").strip()
        zip_code = (self.var_zip.get() or "").strip()
        city = (self.var_city.get() or "").strip()
        country = (self.var_country.get() or "").strip() or "Polska"
        return street, street_no, zip_code, city, country

    def _validate_address_form(self) -> bool:
        _, _, _, city, country = self._read_address_from_form()
        if not city:
            messagebox.showwarning("Walidacja", "Miasto (adres) nie może być puste.", parent=self)
            return False
        if not country:
            messagebox.showwarning("Walidacja", "Kraj (adres) nie może być pusty.", parent=self)
            return False
        return True

    def clear_form(self):
        self.var_id.set("")
        self.var_name.set("")
        self.var_phone.set("")
        self.var_email.set("")
        self.var_org1.set("")
        self.var_org2.set("")
        self.var_org3.set("")
        self.var_bank.set("")
        self.var_add_addr.set("")
        self._editing_addr_id = None
        self._clear_address_fields()
        self.tree.selection_remove(self.tree.selection())

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
        if not self._validate_address_form():
            return
        try:
            street, street_no, zip_code, city, country = self._read_address_from_form()
            # Nowa org: zawsze nowy rekord Address z pól formularza
            # (opcjonalnie: jeśli wybrano z listy i nic nie zmieniono — reuse)
            pick_label = (self.var_addr_pick.get() or "").strip()
            reuse_id = self._addr_by_label.get(pick_label) if pick_label else None
            if reuse_id:
                existing = get_address_by_id(reuse_id)
                same = (
                    existing
                    and (existing["StreetName"] or "") == street
                    and (existing["StreetNumber"] or "") == street_no
                    and (existing["ZipCode"] or "") == zip_code
                    and (existing["City"] or "") == city
                    and (existing["Country"] or "") == country
                )
                addr_id = reuse_id if same else create_address(
                    "Billing", street, street_no, zip_code, city, country
                )
            else:
                addr_id = create_address(
                    "Billing", street, street_no, zip_code, city, country
                )

            add_addr = self._addr_by_label.get((self.var_add_addr.get() or "").strip())
            new_id = create_organization(
                addr_id,
                add_addr,
                self.var_name.get().strip() or None,
                self.var_phone.get().strip() or None,
                self.var_email.get().strip() or None,
                self.var_org1.get().strip() or None,
                self.var_org2.get().strip() or None,
                self.var_org3.get().strip() or None,
                self.var_bank.get().strip() or None,
            )
            self._load_lookups()
            self.refresh_table()
            self.clear_form()
            messagebox.showinfo("Sukces", f"Dodano organizację (ID={new_id}).", parent=self)
        except Exception as e:
            messagebox.showerror("Błąd", str(e), parent=self)

    def on_update(self):
        if not self.var_id.get():
            messagebox.showwarning("Błąd", "Nie wybrano organizacji.", parent=self)
            return
        if not self._validate_address_form():
            return
        try:
            org_id = int(self.var_id.get())
            street, street_no, zip_code, city, country = self._read_address_from_form()
            add_addr = self._addr_by_label.get((self.var_add_addr.get() or "").strip())

            org = get_organization_by_id(org_id)
            addr_id = None
            if org and org["AddressId"]:
                addr_id = int(org["AddressId"])
            elif self._editing_addr_id:
                addr_id = self._editing_addr_id

            if addr_id:
                update_address(
                    addr_id,
                    street_name=street,
                    street_number=street_no,
                    zip_code=zip_code,
                    city=city,
                    country=country,
                )
            else:
                addr_id = create_address(
                    "Billing", street, street_no, zip_code, city, country
                )

            ok = update_organization(
                org_id,
                AddressId=addr_id,
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
                self._editing_addr_id = addr_id
                self._load_lookups()
                self.refresh_table()
                messagebox.showinfo("Sukces", "Zaktualizowano dane organizacji.", parent=self)
        except Exception as e:
            messagebox.showerror("Błąd", str(e), parent=self)
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

        # Odtwórz adresy na podstawie ukrytych ID (po kolumnie Źródło)
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

        self.var_add_addr.set(
            self._label_by_addr.get(add_addr_id, "") if add_addr_id is not None else ""
        )
        if addr_id is not None:
            self._fill_address_fields_from_row(get_address_by_id(addr_id))
        else:
            self._editing_addr_id = None
            self._clear_address_fields()

    def on_import_ceidg(self):
        raw = (self.var_org1.get() or "").strip()
        if not raw:
            raw = simpledialog.askstring(
                "NIP",
                "Podaj NIP (10 cyfr) — najpierw CEIDG, przy braku danych fallback GUS (REGON):",
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

        has_ceidg = bool(get_ceidg_hd_token())
        has_gus = bool(get_gus_bir_key())
        if not has_ceidg and not has_gus:
            messagebox.showwarning(
                "Token / klucz API",
                "Brak tokenu CEIDG i klucza GUS BIR.\n\n"
                "W menu: Plik → Ustawienia integracji… — ustaw token CEIDG "
                "(JWT z https://dane.biznes.gov.pl/) i/lub klucz GUS "
                "(https://api.stat.gov.pl/Home/RegonApi),\n"
                "albo zmienne CEIDG_HD_API_TOKEN / GUS_BIR_API_KEY.",
                parent=self,
            )
            return

        nip_query = self.var_org1.get()

        def work():
            try:
                flat = None
                source = RECORD_SOURCE_CEIDG_IMPORT
                if has_ceidg:
                    try:
                        ceidg_debug(f"import organizacji: zapytanie CEIDG po NIP {nip_query!r}")
                        firma = fetch_firma_by_nip(nip_query)
                        flat = flat_firma_for_org(firma)
                        source = RECORD_SOURCE_CEIDG_IMPORT
                    except CeidgNoDataError as e:
                        ceidg_debug(f"brak w CEIDG — fallback GUS: {e}")
                        flat = None
                    except CeidgHdError as e:
                        self.after(
                            0,
                            lambda m=str(e): messagebox.showerror("CEIDG", m, parent=self),
                        )
                        return

                if flat is None:
                    if not has_gus:
                        self.after(
                            0,
                            lambda: messagebox.showinfo(
                                "CEIDG / GUS",
                                "Nie znaleziono danych w CEIDG, a klucz GUS BIR nie jest ustawiony.\n\n"
                                "Dodaj klucz w Plik → Ustawienia integracji… (GUS_BIR_API_KEY).",
                                parent=self,
                            ),
                        )
                        return
                    try:
                        gus_debug(f"import organizacji: zapytanie GUS po NIP {nip_query!r}")
                        podmiot = fetch_podmiot_by_nip(nip_query)
                        flat = flat_podmiot_for_org(podmiot)
                        source = RECORD_SOURCE_GUS_IMPORT
                    except GusNoDataError as e:
                        self.after(
                            0,
                            lambda m=str(e): messagebox.showinfo("CEIDG / GUS", m, parent=self),
                        )
                        return
                    except GusBirError as e:
                        self.after(
                            0,
                            lambda m=str(e): messagebox.showerror("GUS", m, parent=self),
                        )
                        return

                _parts = [
                    f"{k}={flat.get(k)!r}"
                    for k in ("name", "org_nip", "city")
                    if flat.get(k)
                ]
                if _parts:
                    (ceidg_debug if source == RECORD_SOURCE_CEIDG_IMPORT else gus_debug)(
                        "spłaszczone pola: " + ", ".join(_parts)
                    )
                self.after(0, lambda f=flat, s=source: self._apply_registry_import(f, s))
            except Exception as e:
                self.after(
                    0,
                    lambda m=str(e): messagebox.showerror("Import", m, parent=self),
                )

        threading.Thread(target=work, daemon=True).start()

    def _apply_registry_import(self, flat: dict, source: str = RECORD_SOURCE_CEIDG_IMPORT):
        """Nadpisuje pola formularza (i zapisanej organizacji) danymi z CEIDG/GUS."""
        src_label = "GUS (REGON)" if source == RECORD_SOURCE_GUS_IMPORT else "Hurtowni CEIDG"
        self._merge_ceidg_into_form(flat)
        vid = (self.var_id.get() or "").strip()
        if not vid:
            messagebox.showinfo(
                "Import",
                f"Nadpisano pola formularza danymi z {src_label}. "
                "Kliknij „Dodaj”, aby zapisać nową organizację.",
                parent=self,
            )
            return
        try:
            oid = int(vid)
        except ValueError:
            return

        did_db = self._merge_ceidg_into_db(oid, flat, source=source)
        log = gus_debug if source == RECORD_SOURCE_GUS_IMPORT else ceidg_debug
        log(f"zapis do bazy po imporcie: OrganizationId={oid}, wykonano UPDATE={'tak' if did_db else 'nie'}")
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
                "Import",
                f"Zaktualizowano organizację danymi z {src_label} (nadpisano pola w bazie).",
                parent=self,
            )
        else:
            messagebox.showinfo(
                "Import",
                f"Formularz nadpisano danymi z {src_label}. "
                "W bazie nie było zmian (dane już były aktualne).",
                parent=self,
            )

    @staticmethod
    def _overwrite_value(current: str | None, incoming: str | None) -> str | None:
        """Nowa wartość do zapisu, albo None gdy bez zmian. Puste z rejestru czyści pole."""
        inc = "" if incoming is None else str(incoming).strip()
        cur = "" if current is None else str(current).strip()
        if inc == cur:
            return None
        return inc

    def _merge_ceidg_into_form(self, flat: dict):
        def set_overwrite(var: tk.StringVar, val: str | None):
            var.set("" if val is None else str(val).strip())

        set_overwrite(self.var_name, flat.get("name"))
        set_overwrite(self.var_phone, flat.get("phone"))
        set_overwrite(self.var_email, flat.get("email"))
        set_overwrite(self.var_org1, flat.get("org_nip"))
        set_overwrite(self.var_org2, flat.get("org_regon"))
        set_overwrite(self.var_street, flat.get("street_name"))
        set_overwrite(self.var_street_no, flat.get("street_number"))
        set_overwrite(self.var_zip, flat.get("zip_code"))
        set_overwrite(self.var_city, flat.get("city"))
        set_overwrite(self.var_country, flat.get("country"))

    def _merge_ceidg_into_db(
        self,
        org_id: int,
        flat: dict,
        *,
        source: str = RECORD_SOURCE_CEIDG_IMPORT,
    ) -> bool:
        """Nadpisuje w bazie wszystkie pola mapowane z rejestru. Zwraca True przy UPDATE."""
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
            m = self._overwrite_value(org[col], flat.get(key))
            if m is not None:
                org_updates[col] = m

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
                m = self._overwrite_value(addr[sql_col], flat.get(flat_key))
                if m is not None:
                    addr_updates[ukw] = m

        if org_updates or addr_updates:
            org_updates["RecordSource"] = source

        did = False
        if addr_updates:
            if update_address(addr_id, **addr_updates):
                did = True
        if org_updates:
            if update_organization(org_id, **org_updates):
                did = True
        return did