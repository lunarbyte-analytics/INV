"""Okno eksportu / importu kopii zapasowej (ZIP → dysk / folder chmury)."""
from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from ..backup import (
    ExportOptions,
    default_backup_filename,
    export_backup,
    import_backup,
    list_backup_member_summary,
    read_backup_manifest,
    suggested_cloud_folders,
)
from ..restart_util import restart_application

PADX = 12
PADY = 8


class BackupWindow(tk.Toplevel):
    def __init__(self, master=None):
        super().__init__(master)
        self.title("Kopia zapasowa / chmura")
        self.geometry("560x480")
        self.minsize(480, 420)
        self.transient(master)
        self.grab_set()

        self._kind = tk.StringVar(value="data")
        self._include_settings = tk.BooleanVar(value=True)
        self._include_reports = tk.BooleanVar(value=False)
        self._restore_settings = tk.BooleanVar(value=True)
        self._restore_reports = tk.BooleanVar(value=True)
        self._restore_app = tk.BooleanVar(value=False)

        self._build()

    def _build(self) -> None:
        frm = ttk.Frame(self, padding=PADX)
        frm.pack(fill="both", expand=True)

        ttk.Label(
            frm,
            text=(
                "Eksport tworzy plik ZIP. Zapisz go w OneDrive, Google Drive lub Dropbox "
                "— chmura zsynchronizuje go automatycznie. Import przywraca dane z ZIP."
            ),
            wraplength=500,
            justify="left",
        ).pack(anchor="w", pady=(0, PADY))

        exp = ttk.LabelFrame(frm, text="Eksport", padding=PADX)
        exp.pack(fill="x", pady=(0, PADY))

        ttk.Radiobutton(
            exp,
            text="Tylko dane (bazy SQLite + ustawienia) — do codziennej kopii",
            variable=self._kind,
            value="data",
        ).pack(anchor="w")
        ttk.Radiobutton(
            exp,
            text="Dane + aplikacja (kod, bat, assets) — przeniesienie na inny PC / pełny backup",
            variable=self._kind,
            value="app",
        ).pack(anchor="w")

        ttk.Checkbutton(
            exp,
            text="Dołącz ustawienia integracji (tokeny KSeF/CEIDG) — plik wrażliwy",
            variable=self._include_settings,
        ).pack(anchor="w", pady=(6, 0))
        ttk.Checkbutton(
            exp,
            text="Dołącz wygenerowane PDF (katalog reports/)",
            variable=self._include_reports,
        ).pack(anchor="w")

        btn_row = ttk.Frame(exp)
        btn_row.pack(fill="x", pady=(PADY, 0))
        ttk.Button(btn_row, text="Zapisz ZIP…", command=self._on_export).pack(side="left")
        ttk.Button(
            btn_row,
            text="Zapisz w folderze chmury…",
            command=self._on_export_cloud,
        ).pack(side="left", padx=(8, 0))

        clouds = suggested_cloud_folders()
        if clouds:
            names = ", ".join(p.name for p in clouds[:3])
            ttk.Label(
                exp,
                text=f"Wykryte foldery chmury: {names}",
                foreground="#555",
            ).pack(anchor="w", pady=(6, 0))

        imp = ttk.LabelFrame(frm, text="Import / przywracanie", padding=PADX)
        imp.pack(fill="x", pady=(0, PADY))

        ttk.Checkbutton(
            imp,
            text="Przywróć ustawienia (tokeny)",
            variable=self._restore_settings,
        ).pack(anchor="w")
        ttk.Checkbutton(
            imp,
            text="Przywróć PDF z reports/",
            variable=self._restore_reports,
        ).pack(anchor="w")
        ttk.Checkbutton(
            imp,
            text="Przywróć także kod aplikacji (nadpisze pliki .py)",
            variable=self._restore_app,
        ).pack(anchor="w")

        ttk.Button(imp, text="Wybierz ZIP i przywróć…", command=self._on_import).pack(
            anchor="w", pady=(PADY, 0)
        )

        ttk.Button(frm, text="Zamknij", command=self.destroy).pack(anchor="e", pady=(PADY, 0))

    def _export_options(self) -> ExportOptions:
        return ExportOptions(
            include_app=self._kind.get() == "app",
            include_settings=self._include_settings.get(),
            include_reports=self._include_reports.get(),
            include_both_databases=True,
        )

    def _on_export(self) -> None:
        opts = self._export_options()
        initial = default_backup_filename(include_app=opts.include_app)
        path = filedialog.asksaveasfilename(
            parent=self,
            title="Zapisz kopię zapasową INV",
            defaultextension=".zip",
            initialfile=initial,
            filetypes=[("Archiwum ZIP", "*.zip"), ("Wszystkie pliki", "*.*")],
        )
        if not path:
            return
        self._do_export(Path(path), opts)

    def _on_export_cloud(self) -> None:
        opts = self._export_options()
        clouds = suggested_cloud_folders()
        initial_dir = str(clouds[0]) if clouds else str(Path.home())
        # Preferuj podfolder INV_backup jeśli istnieje lub da się wskazać katalog
        prefer = Path(initial_dir) / "INV_backup"
        if prefer.is_dir():
            initial_dir = str(prefer)
        path = filedialog.asksaveasfilename(
            parent=self,
            title="Zapisz kopię w folderze chmury (OneDrive / Drive / Dropbox)",
            defaultextension=".zip",
            initialdir=initial_dir,
            initialfile=default_backup_filename(include_app=opts.include_app),
            filetypes=[("Archiwum ZIP", "*.zip"), ("Wszystkie pliki", "*.*")],
        )
        if not path:
            return
        self._do_export(Path(path), opts)

    def _do_export(self, dest: Path, opts: ExportOptions) -> None:
        try:
            self.config(cursor="watch")
            self.update_idletasks()
            result = export_backup(dest, opts)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Eksport", f"Nie udało się utworzyć kopii:\n{exc}", parent=self)
            return
        finally:
            self.config(cursor="")

        msg = f"Zapisano:\n{result.path}\n\nPlików: {len(result.files)}"
        if result.warnings:
            msg += "\n\nUwagi:\n- " + "\n- ".join(result.warnings)
        if opts.include_settings:
            msg += (
                "\n\nUwaga: archiwum może zawierać tokeny KSeF/CEIDG. "
                "Nie udostępniaj go publicznie."
            )
        messagebox.showinfo("Eksport", msg, parent=self)

    def _on_import(self) -> None:
        path = filedialog.askopenfilename(
            parent=self,
            title="Wybierz kopię zapasową INV (ZIP)",
            filetypes=[("Archiwum ZIP", "*.zip"), ("Wszystkie pliki", "*.*")],
        )
        if not path:
            return
        zip_path = Path(path)
        summary = list_backup_member_summary(zip_path)
        try:
            manifest = read_backup_manifest(zip_path)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Import", f"Nie można odczytać ZIP:\n{exc}", parent=self)
            return

        has_app = bool(manifest.get("include_app")) or manifest.get("kind") == "app"
        if has_app and not self._restore_app.get():
            extra = (
                "\n\nArchiwum zawiera kod aplikacji — przywrócone zostaną tylko dane "
                "(chyba że zaznaczysz przywracanie aplikacji)."
            )
        else:
            extra = ""

        ok = messagebox.askyesno(
            "Przywracanie",
            "To nadpisze lokalne bazy (i wybrane pliki).\n"
            "Przed kontynuacją zamknij inne okna edycji.\n\n"
            f"{summary}{extra}\n\nKontynuować?",
            parent=self,
        )
        if not ok:
            return

        try:
            self.config(cursor="watch")
            self.update_idletasks()
            result = import_backup(
                zip_path,
                restore_settings=self._restore_settings.get(),
                restore_reports=self._restore_reports.get(),
                restore_app=self._restore_app.get(),
            )
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Import", f"Przywracanie nie powiodło się:\n{exc}", parent=self)
            return
        finally:
            self.config(cursor="")

        msg = "Przywrócono:\n- " + ("\n- ".join(result.restored) if result.restored else "(brak)")
        if result.warnings:
            msg += "\n\nUwagi:\n- " + "\n- ".join(result.warnings)
        msg += "\n\nAby zobaczyć dane, aplikacja powinna zostać uruchomiona ponownie."
        messagebox.showinfo("Import", msg, parent=self)
        if result.restored and messagebox.askyesno(
            "Restart",
            "Uruchomić aplikację ponownie teraz?",
            parent=self,
        ):
            restart_application()
