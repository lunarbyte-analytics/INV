"""Okno ustawień integracji: KSeF, CEIDG — zapis w inv_app_settings.json."""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from ..app_env import (
    DEFAULT_CEIDG_HD_API_BASE,
    DEFAULT_KSEF_TEST_BASE_URL,
    get_integration_dict,
    save_integration_dict,
)

PADX = 10
PADY = 8


class IntegrationSettingsWindow(tk.Toplevel):
    def __init__(self, master=None):
        super().__init__(master)
        self.title("Ustawienia integracji (KSeF, CEIDG)")
        self.geometry("720x560")
        self.minsize(560, 480)
        self.transient(master)
        self._build()
        self._load()

    def _build(self) -> None:
        outer = ttk.Frame(self, padding=12)
        outer.pack(fill=tk.BOTH, expand=True)
        outer.rowconfigure(0, weight=1)
        outer.columnconfigure(0, weight=1)

        canvas = tk.Canvas(outer, highlightthickness=0)
        scroll = ttk.Scrollbar(outer, orient=tk.VERTICAL, command=canvas.yview)
        frm = ttk.Frame(canvas)
        frm.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.create_window((0, 0), window=frm, anchor="nw")
        canvas.configure(yscrollcommand=scroll.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns")
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(0, weight=1)

        ttk.Label(
            frm,
            text=(
                "Wartości zapisują się w pliku inv_app_settings.json. "
                "Zmienne środowiskowe (KSEF_TOKEN, KSEF_NIP itd.) mają pierwszeństwo nad tym formularzem."
            ),
            wraplength=640,
            font=("Segoe UI", 9),
            foreground="#444",
        ).grid(row=0, column=0, sticky="w", padx=PADX, pady=(0, 6))

        # --- KSeF ---
        kf = ttk.LabelFrame(frm, text="KSeF")
        kf.grid(row=1, column=0, sticky="ew", padx=PADX, pady=PADY)
        kf.columnconfigure(1, weight=1)

        r = 0
        ttk.Label(kf, text="Token (KSEF_TOKEN):").grid(row=r, column=0, sticky="n", padx=PADX, pady=PADY)
        self._var_ksef_token = tk.StringVar()
        ttk.Entry(kf, textvariable=self._var_ksef_token, width=64, show="•").grid(
            row=r, column=1, sticky="ew", padx=PADX, pady=PADY
        )
        r += 1
        ttk.Label(kf, text="NIP kontekstu (KSEF_NIP):").grid(row=r, column=0, sticky="e", padx=PADX, pady=PADY)
        self._var_ksef_nip = tk.StringVar()
        ttk.Entry(kf, textvariable=self._var_ksef_nip, width=20).grid(row=r, column=1, sticky="w", padx=PADX, pady=PADY)
        r += 1
        ttk.Label(kf, text="Bazowy URL API v2 (KSEF_TEST_BASE_URL):").grid(row=r, column=0, sticky="ne", padx=PADX, pady=PADY)
        self._var_ksef_base = tk.StringVar()
        ttk.Entry(kf, textvariable=self._var_ksef_base, width=64).grid(row=r, column=1, sticky="ew", padx=PADX, pady=PADY)
        ttk.Label(
            kf,
            text=f"Domyślnie (gdy pusto): {DEFAULT_KSEF_TEST_BASE_URL}",
            font=("Segoe UI", 8),
            foreground="#666",
        ).grid(row=r + 1, column=1, sticky="w", padx=PADX, pady=(0, PADY))
        r += 2
        self._var_ksef_debug = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            kf,
            text="Logi diagnostyczne KSeF (KSEF_DEBUG)",
            variable=self._var_ksef_debug,
        ).grid(row=r, column=0, columnspan=2, sticky="w", padx=PADX, pady=PADY)

        # --- CEIDG ---
        cg = ttk.LabelFrame(frm, text="Hurtownia danych CEIDG (Biznes.gov.pl)")
        cg.grid(row=2, column=0, sticky="ew", padx=PADX, pady=PADY)
        cg.columnconfigure(1, weight=1)

        r = 0
        ttk.Label(cg, text="Token JWT (CEIDG_HD_API_TOKEN):").grid(row=r, column=0, sticky="n", padx=PADX, pady=PADY)
        self._var_ceidg_token = tk.StringVar()
        ttk.Entry(cg, textvariable=self._var_ceidg_token, width=64, show="•").grid(
            row=r, column=1, sticky="ew", padx=PADX, pady=PADY
        )
        r += 1
        ttk.Label(cg, text="Bazowy URL API (CEIDG_HD_API_BASE):").grid(row=r, column=0, sticky="ne", padx=PADX, pady=PADY)
        self._var_ceidg_base = tk.StringVar()
        ttk.Entry(cg, textvariable=self._var_ceidg_base, width=64).grid(row=r, column=1, sticky="ew", padx=PADX, pady=PADY)
        r += 1
        ttk.Label(
            cg,
            text=f"Domyślnie (gdy pusto): {DEFAULT_CEIDG_HD_API_BASE}",
            font=("Segoe UI", 8),
            foreground="#666",
        ).grid(row=r, column=1, sticky="w", padx=PADX, pady=(0, 4))
        r += 1
        self._var_ceidg_debug = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            cg,
            text="Logi diagnostyczne CEIDG (CEIDG_DEBUG) — komunikaty [CEIDG] na konsoli",
            variable=self._var_ceidg_debug,
        ).grid(row=r, column=0, columnspan=2, sticky="w", padx=PADX, pady=PADY)

        btn_row = ttk.Frame(frm)
        btn_row.grid(row=3, column=0, sticky="e", padx=PADX, pady=16)
        ttk.Button(btn_row, text="Zapisz", command=self._on_save).pack(side=tk.LEFT, padx=4)
        ttk.Button(btn_row, text="Zamknij", command=self.destroy).pack(side=tk.LEFT, padx=4)

    def _load(self) -> None:
        d = get_integration_dict()
        self._var_ksef_token.set(d.get("ksef_token") or "")
        self._var_ksef_nip.set(d.get("ksef_nip") or "")
        self._var_ksef_base.set(d.get("ksef_test_base_url") or "")
        self._var_ksef_debug.set(bool(d.get("ksef_debug")))
        self._var_ceidg_token.set(d.get("ceidg_hd_api_token") or "")
        self._var_ceidg_base.set(d.get("ceidg_hd_api_base") or "")
        self._var_ceidg_debug.set(bool(d.get("ceidg_debug")))

    def _on_save(self) -> None:
        save_integration_dict(
            {
                "ksef_token": self._var_ksef_token.get(),
                "ksef_nip": self._var_ksef_nip.get(),
                "ksef_test_base_url": self._var_ksef_base.get(),
                "ksef_debug": self._var_ksef_debug.get(),
                "ceidg_hd_api_token": self._var_ceidg_token.get(),
                "ceidg_hd_api_base": self._var_ceidg_base.get(),
                "ceidg_debug": self._var_ceidg_debug.get(),
            }
        )
        messagebox.showinfo("Ustawienia", "Zapisano. Zmienne środowiskowe nadal mają pierwszeństwo.", parent=self)
