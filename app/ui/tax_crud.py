import tkinter as tk
from tkinter import ttk, messagebox
from ..models import (
    create_tax,
    get_tax_all,
    get_tax_by_id,
    update_tax,
    delete_tax,
    set_default_tax,
)
from ..models.record_source import record_source_label_pl


class TaxCrud(tk.Toplevel):
    def __init__(self, master=None):
        super().__init__(master)
        self.title("Podatek – CRUD (SQLite)")
        self.geometry("700x480")
        self.resizable(True, True)
        self._build_widgets(); self.refresh_table()

    def _build_widgets(self):
        frm = ttk.LabelFrame(self, text="Formularz")
        frm.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(frm, text="TaxId:").grid(row=0, column=0, sticky=tk.W, padx=6, pady=6)
        self.var_id = tk.StringVar()
        ttk.Entry(frm, textvariable=self.var_id, width=10, state="readonly").grid(row=0, column=1, sticky=tk.W, padx=6, pady=6)

        ttk.Label(frm, text="Nazwa:").grid(row=0, column=2, sticky=tk.W, padx=6, pady=6)
        self.var_name = tk.StringVar()
        ttk.Entry(frm, textvariable=self.var_name, width=30).grid(row=0, column=3, sticky=tk.W, padx=6, pady=6)

        ttk.Label(frm, text="Wartość (%):").grid(row=1, column=0, sticky=tk.W, padx=6, pady=6)
        self.var_value = tk.StringVar()
        ttk.Entry(frm, textvariable=self.var_value, width=10).grid(row=1, column=1, sticky=tk.W, padx=6, pady=6)

        self.var_default = tk.IntVar(value=0)
        ttk.Checkbutton(frm, text="Domyślna", variable=self.var_default).grid(row=1, column=3, sticky=tk.W, padx=6, pady=6)

        btns = ttk.Frame(self)
        btns.pack(fill=tk.X, padx=10, pady=(0,10))
        ttk.Button(btns, text="Dodaj", command=self.on_add).pack(side=tk.LEFT, padx=5)
        ttk.Button(btns, text="Aktualizuj zaznaczoną", command=self.on_update).pack(side=tk.LEFT, padx=5)
        ttk.Button(btns, text="Usuń zaznaczoną", command=self.on_delete).pack(side=tk.LEFT, padx=5)
        ttk.Button(btns, text="Ustaw jako domyślną", command=self.on_set_default).pack(side=tk.LEFT, padx=5)
        ttk.Button(btns, text="Wyczyść formularz", command=self.clear_form).pack(side=tk.LEFT, padx=5)
        ttk.Button(btns, text="Odśwież", command=self.refresh_table).pack(side=tk.RIGHT, padx=5)

        self.tree = ttk.Treeview(self, columns=("TaxId", "Name", "Value", "Default", "Source"), show="headings")
        for col, text, w, anchor in (
            ("TaxId", "TaxId", 70, tk.E),
            ("Name", "Name", 220, tk.W),
            ("Value", "Value", 80, tk.E),
            ("Default", "Default", 70, tk.CENTER),
            ("Source", "Źródło", 100, tk.W),
        ):
            self.tree.heading(col, text=text)
            self.tree.column(col, width=w, anchor=anchor)
        self.tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0,10))
        self.tree.bind("<<TreeviewSelect>>", self.on_select_row)

    def refresh_table(self):
        for i in self.tree.get_children():
            self.tree.delete(i)
        for row in get_tax_all():
            src = row["RecordSource"] if "RecordSource" in row.keys() else "user"
            self.tree.insert(
                "",
                tk.END,
                values=(
                    row["TaxId"],
                    row["Name"],
                    f"{float(row['Value']):.2f}",
                    row["DefaultFlag"],
                    record_source_label_pl(src),
                ),
            )

    def clear_form(self):
        self.var_id.set(""); self.var_name.set(""); self.var_value.set(""); self.var_default.set(0)

    def on_select_row(self, _event=None):
        sel = self.tree.selection()
        if not sel:
            return
        values = self.tree.item(sel[0], "values")
        self.var_id.set(values[0])
        self.var_name.set(values[1])
        self.var_value.set(values[2])
        self.var_default.set(int(values[3]))

    def _validate_inputs(self, require_id=False) -> bool:
        if require_id and not self.var_id.get():
            messagebox.showwarning("Walidacja", "Brak wybranego rekordu."); return False
        if not self.var_name.get().strip():
            messagebox.showwarning("Walidacja", "Nazwa nie może być pusta."); return False
        try:
            float(self.var_value.get().replace(",", "."))
        except ValueError:
            messagebox.showwarning("Walidacja", "Wartość musi być liczbą (np. 23.00)."); return False
        return True

    def on_add(self):
        if not self._validate_inputs():
            return
        try:
            new_id = create_tax(self.var_name.get().strip(), float(self.var_value.get().replace(",", ".")), int(self.var_default.get()))
            self.refresh_table(); self.clear_form(); messagebox.showinfo("Sukces", f"Dodano stawkę (TaxId={new_id}).")
        except Exception as e:
            messagebox.showerror("Błąd", str(e))

    def on_update(self):
        if not self._validate_inputs(True):
            return
        try:
            tax_id = int(self.var_id.get())
            ok = update_tax(tax_id, name=self.var_name.get().strip(), value=float(self.var_value.get().replace(",", ".")), default_flag=int(self.var_default.get()))
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
            tax_id = int(self.var_id.get())
            if messagebox.askyesno("Potwierdzenie", f"Usunąć TaxId={tax_id}?"):
                ok = delete_tax(tax_id)
                if ok:
                    self.refresh_table(); self.clear_form(); messagebox.showinfo("Sukces", "Usunięto rekord.")
                else:
                    messagebox.showwarning("Uwaga", "Nie znaleziono rekordu do usunięcia.")
        except Exception as e:
            messagebox.showerror("Błąd", str(e))

    def on_set_default(self):
        if not self.var_id.get():
            messagebox.showwarning("Walidacja", "Wybierz rekord do ustawienia jako domyślny."); return
        try:
            tax_id = int(self.var_id.get())
            if set_default_tax(tax_id):
                self.refresh_table(); messagebox.showinfo("Sukces", f"Ustawiono domyślną (TaxId={tax_id}).")
            else:
                messagebox.showwarning("Uwaga", "Nie znaleziono rekordu.")
        except Exception as e:
            messagebox.showerror("Błąd", str(e))