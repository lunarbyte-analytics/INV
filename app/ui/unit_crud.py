import tkinter as tk
from tkinter import ttk, messagebox
from ..models import (
    create_unit,
    get_unit_all,
    get_unit_by_id,
    update_unit,
    delete_unit,
    set_default_unit,
)


class UnitCrud(tk.Toplevel):
    def __init__(self, master=None):
        super().__init__(master)
        self.title("Jednostki – CRUD (SQLite)")
        self.geometry("760x520")
        self.resizable(True, True)
        self._build_widgets(); self.refresh_table()

    def _build_widgets(self):
        frm = ttk.LabelFrame(self, text="Formularz")
        frm.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(frm, text="UnitId:").grid(row=0, column=0, sticky=tk.W, padx=6, pady=6)
        self.var_id = tk.StringVar()
        ttk.Entry(frm, textvariable=self.var_id, width=10, state="readonly").grid(row=0, column=1, sticky=tk.W, padx=6, pady=6)

        ttk.Label(frm, text="Kod:").grid(row=0, column=2, sticky=tk.W, padx=6, pady=6)
        self.var_code = tk.StringVar()
        ttk.Entry(frm, textvariable=self.var_code, width=16).grid(row=0, column=3, sticky=tk.W, padx=6, pady=6)

        ttk.Label(frm, text="Nazwa:").grid(row=1, column=0, sticky=tk.W, padx=6, pady=6)
        self.var_name = tk.StringVar()
        ttk.Entry(frm, textvariable=self.var_name, width=30).grid(row=1, column=1, columnspan=3, sticky=tk.W, padx=6, pady=6)

        self.var_default = tk.IntVar(value=0)
        ttk.Checkbutton(frm, text="Domyślna", variable=self.var_default).grid(row=0, column=4, sticky=tk.W, padx=6, pady=6)

        btns = ttk.Frame(self)
        btns.pack(fill=tk.X, padx=10, pady=(0,10))
        ttk.Button(btns, text="Dodaj", command=self.on_add).pack(side=tk.LEFT, padx=5)
        ttk.Button(btns, text="Aktualizuj zaznaczoną", command=self.on_update).pack(side=tk.LEFT, padx=5)
        ttk.Button(btns, text="Usuń zaznaczoną", command=self.on_delete).pack(side=tk.LEFT, padx=5)
        ttk.Button(btns, text="Ustaw jako domyślną", command=self.on_set_default).pack(side=tk.LEFT, padx=5)
        ttk.Button(btns, text="Wyczyść formularz", command=self.clear_form).pack(side=tk.LEFT, padx=5)
        ttk.Button(btns, text="Odśwież", command=self.refresh_table).pack(side=tk.RIGHT, padx=5)

        self.tree = ttk.Treeview(self, columns=("UnitId", "Code", "Name", "Default"), show="headings")
        for col, text, w, anchor in (("UnitId","UnitId",70,tk.E),("Code","Code",120,tk.W),("Name","Name",360,tk.W),("Default","Default",80,tk.CENTER)):
            self.tree.heading(col, text=text)
            self.tree.column(col, width=w, anchor=anchor)
        self.tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0,10))
        self.tree.bind("<<TreeviewSelect>>", self.on_select_row)

    def refresh_table(self):
        for i in self.tree.get_children():
            self.tree.delete(i)
        for row in get_unit_all():
            self.tree.insert("", tk.END, values=(row["UnitId"], row["Code"], row["Name"], row["DefaultFlag"]))

    def clear_form(self):
        self.var_id.set(""); self.var_code.set(""); self.var_name.set(""); self.var_default.set(0)

    def on_select_row(self, _event=None):
        sel = self.tree.selection()
        if not sel:
            return
        values = self.tree.item(sel[0], "values")
        self.var_id.set(values[0]); self.var_code.set(values[1]); self.var_name.set(values[2]); self.var_default.set(int(values[3]))

    def _validate_inputs(self, require_id=False) -> bool:
        if require_id and not self.var_id.get():
            messagebox.showwarning("Walidacja", "Brak wybranego rekordu."); return False
        if not self.var_name.get().strip():
            messagebox.showwarning("Walidacja", "Nazwa nie może być pusta."); return False
        return True

    def on_add(self):
        if not self._validate_inputs():
            return
        try:
            new_id = create_unit(self.var_code.get().strip(), self.var_name.get().strip(), int(self.var_default.get()))
            self.refresh_table(); self.clear_form(); messagebox.showinfo("Sukces", f"Dodano jednostkę (UnitId={new_id}).")
        except Exception as e:
            messagebox.showerror("Błąd", str(e))

    def on_update(self):
        if not self._validate_inputs(True):
            return
        try:
            unit_id = int(self.var_id.get())
            ok = update_unit(unit_id, code=self.var_code.get().strip(), name=self.var_name.get().strip(), default_flag=int(self.var_default.get()))
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
            unit_id = int(self.var_id.get())
            if messagebox.askyesno("Potwierdzenie", f"Usunąć UnitId={unit_id}?"):
                ok = delete_unit(unit_id)
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
            unit_id = int(self.var_id.get())
            if set_default_unit(unit_id):
                self.refresh_table(); messagebox.showinfo("Sukces", f"Ustawiono domyślną (UnitId={unit_id}).")
            else:
                messagebox.showwarning("Uwaga", "Nie znaleziono rekordu.")
        except Exception as e:
            messagebox.showerror("Błąd", str(e))