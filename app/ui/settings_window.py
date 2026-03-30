"""Okno ustawień integracji: KSeF, CEIDG — zapis w inv_app_settings.json."""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from ..app_env import (
    AppEnvironment,
    DEFAULT_CEIDG_HD_API_BASE,
    DEFAULT_KSEF_PRODUCTION_BASE_URL,
    DEFAULT_KSEF_TEST_BASE_URL,
    get_environment,
    get_integration_dict_for_env,
    save_integration_both,
)

PADX = 10
PADY = 8


class IntegrationSettingsWindow(tk.Toplevel):
    def __init__(self, master=None):
        super().__init__(master)
        self.title("Ustawienia integracji (KSeF, CEIDG)")
        self.geometry("760x720")
        self.minsize(560, 520)
        self.transient(master)
        self._vars: dict[AppEnvironment, dict[str, tk.Variable]] = {
            AppEnvironment.TEST: self._make_var_bundle(),
            AppEnvironment.PRODUCTION: self._make_var_bundle(),
        }
        self._build()
        self._load()

    @staticmethod
    def _make_var_bundle() -> dict[str, tk.Variable]:
        return {
            "ksef_token": tk.StringVar(),
            "ksef_nip": tk.StringVar(),
            "ksef_test_base_url": tk.StringVar(),
            "ksef_debug": tk.BooleanVar(value=False),
            "ceidg_hd_api_token": tk.StringVar(),
            "ceidg_hd_api_base": tk.StringVar(),
            "ceidg_debug": tk.BooleanVar(value=False),
        }

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

        cur = get_environment()
        cur_lbl = "testowym" if cur == AppEnvironment.TEST else "produkcyjnym"
        ttk.Label(
            frm,
            text=(
                "Poniżej osobne pola dla profilu testowego i produkcyjnego — zapis: "
                "inv_app_settings.json → integration.test / integration.production. "
                f"Aktualnie Plik → Środowisko: {cur_lbl} — używany jest zestaw z pliku dla tego trybu. "
                "Dla KSeF: niepuste pola w pliku mają pierwszeństwo nad zmiennymi KSEF_TOKEN / KSEF_NIP / URL; "
                "gdy pole URL jest puste, domyślny host to api-test albo api.ksef zgodnie z Plik → Środowisko. "
                "W trybie produkcyjnym aplikacji zmienna KSEF_TEST_BASE_URL nie nadpisuje adresu (użyj KSEF_BASE_URL "
                "gdy pole URL w pliku jest puste)."
            ),
            wraplength=700,
            font=("Segoe UI", 9),
            foreground="#444",
        ).grid(row=0, column=0, sticky="w", padx=PADX, pady=(0, 4))
        ttk.Label(
            frm,
            text=(
                "CEIDG: zmienne CEIDG_HD_API_TOKEN itd. mają pierwszeństwo nad pustym polem w pliku. "
                "KSeF: patrz opis powyżej (plik pierwszy, gdy niepusty)."
            ),
            wraplength=700,
            font=("Segoe UI", 9),
            foreground="#666",
        ).grid(row=1, column=0, sticky="w", padx=PADX, pady=(0, 8))

        row = 2
        row = self._build_env_column(
            frm,
            row,
            AppEnvironment.TEST,
            "Środowisko testowe — baza: sqllite3_inv_test.db",
            DEFAULT_KSEF_TEST_BASE_URL,
        )
        row = self._build_env_column(
            frm,
            row,
            AppEnvironment.PRODUCTION,
            "Środowisko produkcyjne — baza: sqllite3_inv.db",
            DEFAULT_KSEF_PRODUCTION_BASE_URL,
        )

        btn_row = ttk.Frame(frm)
        btn_row.grid(row=row, column=0, sticky="e", padx=PADX, pady=16)
        ttk.Button(btn_row, text="Zapisz oba zestawy", command=self._on_save).pack(side=tk.LEFT, padx=4)
        ttk.Button(btn_row, text="Zamknij", command=self.destroy).pack(side=tk.LEFT, padx=4)

    def _build_env_column(
        self,
        parent,
        row: int,
        env: AppEnvironment,
        title: str,
        ksef_default_url: str,
    ) -> int:
        block = ttk.LabelFrame(parent, text=title)
        block.grid(row=row, column=0, sticky="ew", padx=PADX, pady=(0, 12))
        block.columnconfigure(0, weight=1)
        v = self._vars[env]

        kf = ttk.LabelFrame(block, text="KSeF")
        kf.grid(row=0, column=0, sticky="ew", padx=PADX, pady=PADY)
        kf.columnconfigure(1, weight=1)
        r = 0
        ttk.Label(kf, text="Token (KSEF_TOKEN):").grid(row=r, column=0, sticky="n", padx=PADX, pady=PADY)
        ttk.Entry(kf, textvariable=v["ksef_token"], width=64, show="•").grid(
            row=r, column=1, sticky="ew", padx=PADX, pady=PADY
        )
        r += 1
        ttk.Label(kf, text="NIP kontekstu (KSEF_NIP):").grid(row=r, column=0, sticky="e", padx=PADX, pady=PADY)
        ttk.Entry(kf, textvariable=v["ksef_nip"], width=20).grid(row=r, column=1, sticky="w", padx=PADX, pady=PADY)
        r += 1
        ttk.Label(kf, text="Bazowy URL API v2 (opcjonalnie; nadpisuje env KSEF_TEST_BASE_URL):").grid(
            row=r, column=0, sticky="ne", padx=PADX, pady=PADY
        )
        ttk.Entry(kf, textvariable=v["ksef_test_base_url"], width=64).grid(
            row=r, column=1, sticky="ew", padx=PADX, pady=PADY
        )
        ttk.Label(
            kf,
            text=f"Gdy pusto w pliku i w env: przy wyborze tego profilu w Plik → Środowisko — {ksef_default_url}",
            font=("Segoe UI", 8),
            foreground="#666",
        ).grid(row=r + 1, column=1, sticky="w", padx=PADX, pady=(0, PADY))
        r += 2
        ttk.Checkbutton(
            kf,
            text="Logi diagnostyczne KSeF (KSEF_DEBUG)",
            variable=v["ksef_debug"],
        ).grid(row=r, column=0, columnspan=2, sticky="w", padx=PADX, pady=PADY)

        cg = ttk.LabelFrame(block, text="Hurtownia danych CEIDG (Biznes.gov.pl)")
        cg.grid(row=1, column=0, sticky="ew", padx=PADX, pady=PADY)
        cg.columnconfigure(1, weight=1)
        r = 0
        ttk.Label(cg, text="Token JWT (CEIDG_HD_API_TOKEN):").grid(row=r, column=0, sticky="n", padx=PADX, pady=PADY)
        ttk.Entry(cg, textvariable=v["ceidg_hd_api_token"], width=64, show="•").grid(
            row=r, column=1, sticky="ew", padx=PADX, pady=PADY
        )
        r += 1
        ttk.Label(cg, text="Bazowy URL API (CEIDG_HD_API_BASE):").grid(
            row=r, column=0, sticky="ne", padx=PADX, pady=PADY
        )
        ttk.Entry(cg, textvariable=v["ceidg_hd_api_base"], width=64).grid(
            row=r, column=1, sticky="ew", padx=PADX, pady=PADY
        )
        r += 1
        ttk.Label(
            cg,
            text=f"Domyślnie (gdy pusto): {DEFAULT_CEIDG_HD_API_BASE}",
            font=("Segoe UI", 8),
            foreground="#666",
        ).grid(row=r, column=1, sticky="w", padx=PADX, pady=(0, 4))
        r += 1
        ttk.Checkbutton(
            cg,
            text="Logi diagnostyczne CEIDG (CEIDG_DEBUG) — komunikaty [CEIDG] na konsoli",
            variable=v["ceidg_debug"],
        ).grid(row=r, column=0, columnspan=2, sticky="w", padx=PADX, pady=PADY)

        return row + 1

    def _gather(self, env: AppEnvironment) -> dict:
        v = self._vars[env]
        return {
            "ksef_token": v["ksef_token"].get(),
            "ksef_nip": v["ksef_nip"].get(),
            "ksef_test_base_url": v["ksef_test_base_url"].get(),
            "ksef_debug": v["ksef_debug"].get(),
            "ceidg_hd_api_token": v["ceidg_hd_api_token"].get(),
            "ceidg_hd_api_base": v["ceidg_hd_api_base"].get(),
            "ceidg_debug": v["ceidg_debug"].get(),
        }

    def _load(self) -> None:
        for env in (AppEnvironment.TEST, AppEnvironment.PRODUCTION):
            d = get_integration_dict_for_env(env)
            v = self._vars[env]
            v["ksef_token"].set(d.get("ksef_token") or "")
            v["ksef_nip"].set(d.get("ksef_nip") or "")
            v["ksef_test_base_url"].set(d.get("ksef_test_base_url") or "")
            v["ksef_debug"].set(bool(d.get("ksef_debug")))
            v["ceidg_hd_api_token"].set(d.get("ceidg_hd_api_token") or "")
            v["ceidg_hd_api_base"].set(d.get("ceidg_hd_api_base") or "")
            v["ceidg_debug"].set(bool(d.get("ceidg_debug")))

    def _on_save(self) -> None:
        save_integration_both(
            production=self._gather(AppEnvironment.PRODUCTION),
            test=self._gather(AppEnvironment.TEST),
        )
        messagebox.showinfo(
            "Ustawienia",
            "Zapisano zestawy integracji dla środowiska testowego i produkcyjnego. "
            "Zmienne środowiskowe nadal mają pierwszeństwo.",
            parent=self,
        )
