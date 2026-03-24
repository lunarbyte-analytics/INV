"""Pochodzenie rekordu w słownikach: wpis ręczny vs import z KSeF (FA)."""
from __future__ import annotations

RECORD_SOURCE_USER = "user"
RECORD_SOURCE_KSEF_IMPORT = "ksef_import"


def record_source_label_pl(source: str | None) -> str:
    if source == RECORD_SOURCE_KSEF_IMPORT:
        return "Import KSeF"
    return "Ręcznie"
