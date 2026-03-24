import tkinter as tk
from tkinter import ttk, messagebox
from ..models import (
    create_address,
    get_address_all,
    get_address_by_id,
    update_address,
    delete_address,
)
from ..models.record_source import record_source_label_pl

class AddressCrud(tk.Toplevel):
    def __init__(self, master=None):
        super().__init__(master)
        self.title("Adresy – CRUD (SQLite)")
        self.geometry("900x560")
        self.resizable(True, True)
        self._build_widgets()
        self.refresh_table()

    def _build_widgets(self):
        frm = ttk.LabelFrame(self, text="Formularz")
        frm.pack(fill=tk.X, padx=10, pady=10)

        # ID
        ttk.Label(frm, text="AddressId:").grid(row=0, column=0, sticky=tk.W, padx=6, pady=6)
        self.var_id = tk.StringVar()
        ttk.Entry(frm, textvariable=self.var_id, width=10, state="readonly").grid(row=0, column=1, sticky=tk.W, padx=6, pady=6)

        # AddressType
        ttk.Label(frm, text="Typ adresu:").grid(row=0, column=2, sticky=tk.W, padx=6, pady=6)
        self.var_type = tk.StringVar()
        ttk.Entry(frm, textvariable=self.var_type, width=18).grid(row=0, column=3, sticky=tk.W, padx=6, pady=6)

        # Street
        ttk.Label(frm, text="Ulica:").grid(row=1, column=0, sticky=tk.W, padx=6, pady=6)
        self.var_street = tk.StringVar()
        ttk.Entry(frm, textvariable=self.var_street, width=24).grid(row=1, column=1, sticky=tk.W, padx=6, pady=6)

        ttk.Label(frm, text="Nr:").grid(row=1, column=2, sticky=tk.W, padx=6, pady=6)
        self.var_number = tk.StringVar()
        ttk.Entry(frm, textvariable=self.var_number, width=10).grid(row=1, column=3, sticky=tk.W, padx=6, pady=6)

        # Zip / City / Country
        ttk.Label(frm, text="Kod pocztowy:").grid(row=2, column=0, sticky=tk.W, padx=6, pady=6)
        self.var_zip = tk.StringVar()
        ttk.Entry(frm, textvariable=self.var_zip, width=10).grid(row=2, column=1, sticky=tk.W, padx=6, pady=6)

        ttk.Label(frm, text="Miasto:").grid(row=2, column=2, sticky=tk.W, padx=6, pady=6)
        self.var_city = tk.StringVar()
        ttk.Entry(frm, textvariable=self.var_city, width=18).grid(row=2, column=3, sticky=tk.W, padx=6, pady=6)

        ttk.Label(frm, text="Kraj:").grid(row=3, column=0, sticky=tk.W, padx=6, pady=6)
        self.var_country = tk.StringVar()
        ttk.Entry(frm, textvariable=self.var_country, width=18).grid(row=3, column=1, sticky=tk.W, padx=6, pady=6)

        # Buttons
        btns = ttk.Frame(self)
        btns.pack(fill=tk.X, padx=10, pady=(0, 10))
        ttk.Button(btns, text="Dodaj", command=self.on_add).pack(side=tk.LEFT, padx=5)
        ttk.Button(btns, text="Aktualizuj zaznaczony", command=self.on_update).pack(side=tk.LEFT, padx=5)
        ttk.Button(btns, text="Usuń zaznaczony", command=self.on_delete).pack(side=tk.LEFT, padx=5)
        ttk.Button(btns, text="Wyczyść formularz", command=self.clear_form).pack(side=tk.LEFT, padx=5)
        ttk.Button(btns, text="Odśwież", command=self.refresh_table).pack(side=tk.RIGHT, padx=5)

        # Table
        self.tree = ttk.Treeview(
            self,
            columns=(
                "AddressId",
                "AddressType",
                "StreetName",
                "StreetNumber",
                "ZipCode",
                "City",
                "Country",
                "Source",
            ),
            show="headings",
        )
        for col, text, w, anchor in (
            ("AddressId", "AddressId", 70, tk.E),
            ("AddressType", "AddressType", 100, tk.W),
            ("StreetName", "StreetName", 140, tk.W),
            ("StreetNumber", "StreetNumber", 70, tk.W),
            ("ZipCode", "ZipCode", 80, tk.W),
            ("City", "City", 120, tk.W),
            ("Country", "Country", 100, tk.W),
            ("Source", "Źródło", 90, tk.W),
        ):
            self.tree.heading(col, text=text)
            self.tree.column(col, width=w, anchor=anchor)
        self.tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        self.tree.bind("<<TreeviewSelect>>", self.on_select_row)

    def refresh_table(self):
        for i in self.tree.get_children():
            self.tree.delete(i)
        for r in get_address_all():
            src = r["RecordSource"] if "RecordSource" in r.keys() else "user"
            self.tree.insert(
                "",
                tk.END,
                values=(
                    r["AddressId"],
                    r["AddressType"],
                    r["StreetName"],
                    r["StreetNumber"],
                    r["ZipCode"],
                    r["City"],
                    r["Country"],
                    record_source_label_pl(src),
                ),
            )

    def clear_form(self):
        self.var_id.set("")
        self.var_type.set("")
        self.var_street.set("")
        self.var_number.set("")
        self.var_zip.set("")
        self.var_city.set("")
        self.var_country.set("")

    def on_select_row(self, _event=None):
        sel = self.tree.selection()
        if not sel:
            return
        values = self.tree.item(sel[0], "values")
        self.var_id.set(values[0])
        self.var_type.set(values[1])
        self.var_street.set(values[2])
        self.var_number.set(values[3])
        self.var_zip.set(values[4])
        self.var_city.set(values[5])
        self.var_country.set(values[6])

    def _validate_inputs(self, require_id=False) -> bool:
        if require_id and not self.var_id.get():
            messagebox.showwarning("Walidacja", "Brak wybranego rekordu."); return False
        if not self.var_city.get().strip():
            messagebox.showwarning("Walidacja", "Miasto nie może być puste."); return False
        if not self.var_country.get().strip():
            messagebox.showwarning("Walidacja", "Kraj nie może być pusty."); return False
        return True

    def on_add(self):
        if not self._validate_inputs():
            return
        try:
            new_id = create_address(
                self.var_type.get().strip() or None,
                self.var_street.get().strip() or None,
                self.var_number.get().strip() or None,
                self.var_zip.get().strip() or None,
                self.var_city.get().strip() or None,
                self.var_country.get().strip() or None,
            )
            self.refresh_table()
            self.clear_form()
            messagebox.showinfo("Sukces", f"Dodano adres (AddressId={new_id}).")
        except Exception as e:
            messagebox.showerror("Błąd", str(e))

    def on_update(self):
        if not self._validate_inputs(True):
            return
        try:
            aid = int(self.var_id.get())
            ok = update_address(
                aid,
                address_type=self.var_type.get().strip() or None,
                street_name=self.var_street.get().strip() or None,
                street_number=self.var_number.get().strip() or None,
                zip_code=self.var_zip.get().strip() or None,
                city=self.var_city.get().strip() or None,
                country=self.var_country.get().strip() or None,
            )
            if ok:
                self.refresh_table()
                messagebox.showinfo("Sukces", "Zaktualizowano rekord.")
            else:
                messagebox.showwarning("Uwaga", "Brak zmian lub rekord nie istnieje.")
        except Exception as e:
            messagebox.showerror("Błąd", str(e))

    def on_delete(self):
        if not self.var_id.get():
            messagebox.showwarning("Walidacja", "Wybierz rekord do usunięcia."); return
        try:
            aid = int(self.var_id.get())
            if messagebox.askyesno("Potwierdzenie", f"Usunąć AddressId={aid}?"):
                ok = delete_address(aid)
                if ok:
                    self.refresh_table()
                    self.clear_form()
                    messagebox.showinfo("Sukces", "Usunięto rekord.")
                else:
                    messagebox.showwarning("Uwaga", "Nie znaleziono rekordu do usunięcia.")
        except Exception as e:
            messagebox.showerror("Błąd", str(e))
