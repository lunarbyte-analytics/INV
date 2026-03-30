import json
import threading
import tkinter as tk
from tkinter import ttk, scrolledtext

from ..app_env import (
    AppEnvironment,
    get_default_ksef_api_base_url,
    get_environment,
    get_ksef_nip,
    get_ksef_test_base_url,
    get_ksef_token,
)
from ..ksef.client import _effective_base_url, test_challenge_connection
from ..ksef.http_json import KsefHttpError
from ..ksef.token_status import fetch_token_status


class KsefConnectionWindow(tk.Toplevel):
    """Okno testu połączenia z API KSeF (host domyślny zależny od Plik → Środowisko)."""

    def __init__(self, master=None):
        super().__init__(master)
        self.title("KSeF – test połączenia")
        self.geometry("720x560")
        self.minsize(520, 400)

        frm = ttk.Frame(self, padding=12)
        frm.pack(fill=tk.BOTH, expand=True)

        env = get_environment()
        env_lbl = (
            "Środowisko aplikacji: TESTOWE — domyślny host API: api-test.ksef.mf.gov.pl"
            if env == AppEnvironment.TEST
            else "Środowisko aplikacji: PRODUKCYJNE — domyślny host API: api.ksef.mf.gov.pl"
        )
        ttk.Label(frm, text="Środowisko", font=("Segoe UI", 10, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(frm, text=env_lbl, wraplength=660, font=("Segoe UI", 9)).grid(row=1, column=0, sticky="w")

        ttk.Label(frm, text="Bazowy adres API (v2)", font=("Segoe UI", 10, "bold")).grid(row=2, column=0, sticky="nw", pady=(12, 0))
        self._base_var = tk.StringVar(value=get_ksef_test_base_url() or get_default_ksef_api_base_url())
        base_entry = ttk.Entry(frm, textvariable=self._base_var, width=72)
        base_entry.grid(row=3, column=0, sticky="ew")

        hint = (
            "Adres: niepuste pole w Plik → Ustawienia integracji (bieżący profil), potem "
            "KSEF_TEST_BASE_URL (tylko gdy aplikacja w trybie testowym) lub KSEF_BASE_URL (tryb produkcyjny), "
            "na końcu domyślny host wg Plik → Środowisko. „Testuj połączenie” — POST …/auth/challenge."
        )
        ttk.Label(frm, text=hint, wraplength=660, font=("Segoe UI", 9), foreground="#444").grid(
            row=4, column=0, sticky="w", pady=(6, 8)
        )

        btn_row = ttk.Frame(frm)
        btn_row.grid(row=5, column=0, sticky="w")
        ttk.Button(btn_row, text="Testuj połączenie", command=self._run_test).pack(side=tk.LEFT)
        ttk.Button(btn_row, text="Zamknij", command=self.destroy).pack(side=tk.LEFT, padx=(8, 0))

        sep = ttk.Separator(frm, orient=tk.HORIZONTAL)
        sep.grid(row=6, column=0, sticky="ew", pady=(14, 8))

        ttk.Label(
            frm,
            text="Status tokena KSeF (GET /tokens/{ref})",
            font=("Segoe UI", 10, "bold"),
        ).grid(row=7, column=0, sticky="w")

        ttk.Label(
            frm,
            text="Wymaga pełnego uwierzytelnienia (jak wysyłka faktury). Wpisz token i NIP lub pozostaw puste — użyte będą wartości z Plik → Ustawienia integracji… / zmiennych KSEF_TOKEN i KSEF_NIP.",
            wraplength=660,
            font=("Segoe UI", 9),
            foreground="#444",
        ).grid(row=8, column=0, sticky="w", pady=(0, 6))

        row_tok = ttk.Frame(frm)
        row_tok.grid(row=9, column=0, sticky="ew")
        ttk.Label(row_tok, text="Token (opcjonalnie):").pack(side=tk.LEFT)
        self._token_var = tk.StringVar(value=get_ksef_token())
        ent_tok = ttk.Entry(row_tok, textvariable=self._token_var, width=62)
        ent_tok.pack(side=tk.LEFT, padx=(8, 0), fill=tk.X, expand=True)

        row_nip = ttk.Frame(frm)
        row_nip.grid(row=10, column=0, sticky="ew", pady=(6, 0))
        ttk.Label(row_nip, text="NIP kontekstu:").pack(side=tk.LEFT)
        self._nip_var = tk.StringVar(value=get_ksef_nip())
        ttk.Entry(row_nip, textvariable=self._nip_var, width=16).pack(side=tk.LEFT, padx=(8, 0))

        ttk.Button(frm, text="Sprawdź status tokena", command=self._run_token_status).grid(
            row=11, column=0, sticky="w", pady=(10, 0)
        )

        ttk.Label(frm, text="Wynik", font=("Segoe UI", 10, "bold")).grid(row=12, column=0, sticky="w", pady=(12, 4))
        self._log = scrolledtext.ScrolledText(frm, height=12, wrap=tk.WORD, font=("Consolas", 10))
        self._log.grid(row=13, column=0, sticky="nsew")
        frm.rowconfigure(13, weight=1)
        frm.columnconfigure(0, weight=1)

        self._append_log(
            "Kliknij „Testuj połączenie” (challenge) lub „Sprawdź status tokena” (lista tokenów w API).\n"
        )

    def _append_log(self, text: str) -> None:
        self._log.insert(tk.END, text)
        self._log.see(tk.END)

    def _run_test(self) -> None:
        raw = self._base_var.get().strip()
        eff = _effective_base_url(raw if raw else None)
        self._append_log("\n---\n")
        self._append_log(f"Żądanie: POST {eff}/auth/challenge\n")
        self.update_idletasks()
        result = test_challenge_connection(base_url=raw if raw else None)
        self._append_log(result.message + "\n")
        if result.detail and isinstance(result.detail, dict):
            try:
                self._append_log(json.dumps(result.detail, ensure_ascii=False, indent=2) + "\n")
            except Exception:
                self._append_log(str(result.detail) + "\n")

    def _run_token_status(self) -> None:
        raw = self._base_var.get().strip()
        base = _effective_base_url(raw if raw else None)

        tok = self._token_var.get()
        nip = self._nip_var.get()
        if not tok.strip():
            tok = get_ksef_token()
        if not nip.strip():
            nip = get_ksef_nip()

        self._append_log("\n--- Status tokena ---\n")
        self._append_log("Trwa uwierzytelnianie i żądanie GET /tokens/{numer referencyjny}…\n")
        self.update_idletasks()

        def work():
            try:
                data = fetch_token_status(base, ksef_token=tok, nip=nip)
                lines = json.dumps(data, ensure_ascii=False, indent=2)
                st = data.get("status", "?")
                msg = f"Status w API: {st}\n\n{lines}\n"

                def ok():
                    self._append_log(msg)

                self.after(0, ok)
            except Exception as e:
                err = str(e)
                if isinstance(e, KsefHttpError) and e.body:
                    err += f"\n{str(e.body)[:2000]}\n"

                def fail():
                    self._append_log(f"Błąd: {err}\n")

                self.after(0, fail)

        threading.Thread(target=work, daemon=True).start()
