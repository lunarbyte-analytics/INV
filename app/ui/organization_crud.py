import tkinter as tk
from tkinter import ttk, messagebox
from ..models import (
    create_organization, get_organization_all, get_organization_by_id,
    update_organization, delete_organization, get_address_all
)

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
        self.var_org1 = tk.StringVar()
        ttk.Entry(frm, textvariable=self.var_org1)\
            .grid(row=2, column=1, sticky="ew", padx=PADX, pady=PADY)

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
                "OrganizationId", "Name", "Phone", "Email",
                "OrgNbr1", "OrgNbr2", "OrgNbr3",
                "AddressCity", "AddressCountry",
                "BankAccountNbr",
                "AddressId", "AdditionalAddressId"   # ukryte
            ),
            show="headings"
        )

        cols = [
            ("OrganizationId", "ID", 60, tk.E),
            ("Name", "Nazwa", 260, tk.W),
            ("Phone", "Telefon", 140, tk.W),
            ("Email", "Email", 220, tk.W),
            ("OrgNbr1", "NIP", 120, tk.W),
            ("OrgNbr2", "REGON", 120, tk.W),
            ("OrgNbr3", "PESEL", 120, tk.W),
            ("AddressCity", "Miasto", 140, tk.W),
            ("AddressCountry", "Kraj", 120, tk.W),
            ("BankAccountNbr", "Konto", 220, tk.W),
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
            self.tree.insert(
                "",
                tk.END,
                values=(
                    _g(r, "OrganizationId", ""),
                    _g(r, "Name", ""),
                    _g(r, "Phone", ""),
                    _g(r, "Email", ""),
                    _g(r, "OrgNbr1", ""),        # NIP
                    _g(r, "OrgNbr2", ""),        # REGON
                    _g(r, "OrgNbr3", ""),        # PESEL
                    _g(r, "AddressCity", ""),
                    _g(r, "AddressCountry", ""),
                    _g(r, "BankAccountNbr", ""),
                    _g(r, "AddressId", ""),          # ukryte ID
                    _g(r, "AdditionalAddressId", ""),# ukryte ID
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

        # Odtwórz comboboxy na podstawie ukrytych ID
        addr_id = values[10]
        add_addr_id = values[11]

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
