import tkinter as tk
from tkinter import ttk, messagebox
from ..models import (
    create_service,
    get_service_all,
    get_service_by_id,
    update_service,
    delete_service,
    get_unit_all,
    get_tax_all,
)


class ServiceCrud(tk.Toplevel):
    def __init__(self, master=None):
        super().__init__(master)
        self.title("Usługi – CRUD (SQLite)")
        self.geometry("900x560")
        self.resizable(True, True)
        self._build_widgets(); self.refresh_table(); self._load_lookups()

    def _build_widgets(self):
        frm = ttk.LabelFrame(self, text="Formularz")
        frm.pack(fill=tk.X, padx=10, pady=10)

        # ID
        ttk.Label(frm, text="ServiceId:").grid(row=0, column=0, sticky=tk.W, padx=6, pady=6)
        self.var_id = tk.StringVar()
        ttk.Entry(frm, textvariable=self.var_id, width=10, state="readonly").grid(row=0, column=1, sticky=tk.W, padx=6, pady=6)

        # Name
        ttk.Label(frm, text="Nazwa:").grid(row=0, column=2, sticky=tk.W, padx=6, pady=6)
        self.var_name = tk.StringVar()
        ttk.Entry(frm, textvariable=self.var_name, width=30).grid(row=0, column=3, sticky=tk.W, padx=6, pady=6)

        # Unit
        ttk.Label(frm, text="Jednostka:").grid(row=1, column=0, sticky=tk.W, padx=6, pady=6)
        self.var_unit = tk.StringVar()
        self.cb_unit = ttk.Combobox(frm, textvariable=self.var_unit, state="readonly", width=18)
        self.cb_unit.grid(row=1, column=1, sticky=tk.W, padx=6, pady=6)

        # Tax
        ttk.Label(frm, text="Podatek:").grid(row=1, column=2, sticky=tk.W, padx=6, pady=6)
        self.var_tax = tk.StringVar()
        self.cb_tax = ttk.Combobox(frm, textvariable=self.var_tax, state="readonly", width=18)
        self.cb_tax.grid(row=1, column=3, sticky=tk.W, padx=6, pady=6)

        # UnitPrice
        ttk.Label(frm, text="Cena jedn.:").grid(row=2, column=0, sticky=tk.W, padx=6, pady=6)
        self.var_price = tk.StringVar()
        ttk.Entry(frm, textvariable=self.var_price, width=12).grid(row=2, column=1, sticky=tk.W, padx=6, pady=6)

        # Version
        ttk.Label(frm, text="Wersja:").grid(row=2, column=2, sticky=tk.W, padx=6, pady=6)
        self.var_version = tk.StringVar()
        ttk.Entry(frm, textvariable=self.var_version, width=18).grid(row=2, column=3, sticky=tk.W, padx=6, pady=6)

        # Buttons
        btns = ttk.Frame(self)
        btns.pack(fill=tk.X, padx=10, pady=(0,10))
        ttk.Button(btns, text="Dodaj", command=self.on_add).pack(side=tk.LEFT, padx=5)
        ttk.Button(btns, text="Aktualizuj zaznaczoną", command=self.on_update).pack(side=tk.LEFT, padx=5)
        ttk.Button(btns, text="Usuń zaznaczoną", command=self.on_delete).pack(side=tk.LEFT, padx=5)
        ttk.Button(btns, text="Wyczyść formularz", command=self.clear_form).pack(side=tk.LEFT, padx=5)
        ttk.Button(btns, text="Odśwież", command=self.refresh_table).pack(side=tk.RIGHT, padx=5)

        # Table
        self.tree = ttk.Treeview(
            self,
            columns=("ServiceId","Name","Unit","Tax","UnitPrice","Version"),
            show="headings",
        )
        self.tree.heading("ServiceId", text="ServiceId")
        self.tree.heading("Name", text="Name")
        self.tree.heading("Unit", text="Unit")
        self.tree.heading("Tax", text="Tax")
        self.tree.heading("UnitPrice", text="UnitPrice")
        self.tree.heading("Version", text="Version")
        self.tree.column("ServiceId", width=80, anchor=tk.E)
        self.tree.column("Name", width=260)
        self.tree.column("Unit", width=160)
        self.tree.column("Tax", width=160)
        self.tree.column("UnitPrice", width=100, anchor=tk.E)
        self.tree.column("Version", width=100)
        self.tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0,10))
        self.tree.bind("<<TreeviewSelect>>", self.on_select_row)

    def _load_lookups(self):
        # Units
        units = get_unit_all()
        self._unit_map = {f"{u['Code'] or ''} — {u['Name']}": u["UnitId"] for u in units}
        self.cb_unit["values"] = list(self._unit_map.keys())
        # Taxes
        taxes = get_tax_all()
        self._tax_map = {f"{t['Name']} ({float(t['Value']):.2f}%)": t["TaxId"] for t in taxes}
        self.cb_tax["values"] = list(self._tax_map.keys())

    def refresh_table(self):
        for i in self.tree.get_children():
            self.tree.delete(i)
        for r in get_service_all():
            unit_label = f"{r['UnitCode'] or ''} — {r['UnitName']}"
            tax_label = f"{r['TaxName']} ({float(r['TaxValue']):.2f}%)"
            self.tree.insert("", tk.END, values=(r["ServiceId"], r["Name"], unit_label, tax_label, f"{float(r['UnitPrice']):.2f}", r["Version"]))

    def clear_form(self):
        self.var_id.set(""); self.var_name.set(""); self.var_unit.set(""); self.var_tax.set(""); self.var_price.set(""); self.var_version.set("")

    def on_select_row(self, _event=None):
        sel = self.tree.selection()
        if not sel:
            return
        values = self.tree.item(sel[0], "values")
        self.var_id.set(values[0]); self.var_name.set(values[1]); self.var_unit.set(values[2]); self.var_tax.set(values[3]); self.var_price.set(values[4]); self.var_version.set(values[5])

    def _validate_inputs(self, require_id=False) -> bool:
        if require_id and not self.var_id.get():
            messagebox.showwarning("Walidacja", "Brak wybranego rekordu."); return False
        if not self.var_name.get().strip():
            messagebox.showwarning("Walidacja", "Nazwa nie może być pusta."); return False
        if not self.var_unit.get() or self.var_unit.get() not in self._unit_map:
            messagebox.showwarning("Walidacja", "Wybierz jednostkę z listy."); return False
        if not self.var_tax.get() or self.var_tax.get() not in self._tax_map:
            messagebox.showwarning("Walidacja", "Wybierz podatek z listy."); return False
        try:
            float(self.var_price.get().replace(",", "."))
        except ValueError:
            messagebox.showwarning("Walidacja", "Cena musi być liczbą (np. 99.99)."); return False
        return True

    def on_add(self):
        if not self._validate_inputs():
            return
        try:
            uid = self._unit_map[self.var_unit.get()]
            tid = self._tax_map[self.var_tax.get()]
            new_id = create_service(uid, tid, self.var_name.get().strip(), float(self.var_price.get().replace(",", ".")), self.var_version.get().strip() or None)
            self.refresh_table(); self.clear_form(); messagebox.showinfo("Sukces", f"Dodano usługę (ServiceId={new_id}).")
        except Exception as e:
            messagebox.showerror("Błąd", str(e))

    def on_update(self):
        if not self._validate_inputs(True):
            return
        try:
            sid = int(self.var_id.get())
            uid = self._unit_map[self.var_unit.get()]
            tid = self._tax_map[self.var_tax.get()]
            ok = update_service(sid, unit_id=uid, tax_id=tid, name=self.var_name.get().strip(), unit_price=float(self.var_price.get().replace(",", ".")), version=self.var_version.get().strip() or None)
            if ok:
                self.refresh_table(); messagebox.showinfo("Sukces", "Zaktualizowano rekord.")
            else:
                messagebox.showwarning("Uwaga", "Brak zmian lub rekord nie istnieje.")
        except Exception as e:
            messagebox.showerror("Błąd", str(e))

    def on_delete(self):
        if not self.var_id.get():
            messagebox.showwarning("Walidacja", "Wybierz rekord do usunięcia."); return
        try:
            sid = int(self.var_id.get())
            if messagebox.askyesno("Potwierdzenie", f"Usunąć ServiceId={sid}?"):
                ok = delete_service(sid)
                if ok:
                    self.refresh_table(); self.clear_form(); messagebox.showinfo("Sukces", "Usunięto rekord.")
                else:
                    messagebox.showwarning("Uwaga", "Nie znaleziono rekordu do usunięcia.")
        except Exception as e:
            messagebox.showerror("Błąd", str(e))