"""
Klient HTTP do API KSeF 2.0 — bez zewnętrznych zależności (urllib).

Dokumentacja (środowisko testowe): https://api-test.ksef.mf.gov.pl/docs/v2/
"""
from __future__ import annotations

import json
import ssl
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from ..app_env import get_default_ksef_api_base_url, get_ksef_test_base_url

# Zgodnie z OpenAPI: servers[0].url dla TE
ENV_TEST = {
    "id": "TE",
    "label": "Środowisko testowe (TE)",
    "base_url": "https://api-test.ksef.mf.gov.pl/v2",
}


def _effective_base_url(base_url: str | None) -> str:
    if base_url and base_url.strip():
        return base_url.strip().rstrip("/")
    override = get_ksef_test_base_url()
    if override:
        return override.rstrip("/")
    return get_default_ksef_api_base_url()


@dataclass
class ChallengeTestResult:
    ok: bool
    message: str
    detail: dict[str, Any] | None = None


def test_challenge_connection(base_url: str | None = None, timeout: float = 30.0) -> ChallengeTestResult:
    """
    Sprawdza dostępność API przez POST /auth/challenge (inicjalizacja uwierzytelnienia).

    Na środowisku testowym zwraca m.in. identyfikator challenge — potwierdza poprawne TLS i działanie usługi.
    """
    base = _effective_base_url(base_url)
    url = f"{base}/auth/challenge"
    req = Request(
        url,
        method="POST",
        data=b"{}",
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
    )
    ctx = ssl.create_default_context()
    try:
        with urlopen(req, timeout=timeout, context=ctx) as resp:
            raw = resp.read().decode("utf-8")
            payload = json.loads(raw) if raw else {}
    except HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", errors="replace")
        except Exception:
            pass
        return ChallengeTestResult(
            ok=False,
            message=f"Błąd HTTP {e.code} przy wywołaniu {url}. {body[:500]}",
            detail={"http_status": e.code, "body": body[:2000]},
        )
    except URLError as e:
        return ChallengeTestResult(
            ok=False,
            message=f"Brak połączenia z {url}: {e.reason!s}",
            detail=None,
        )
    except json.JSONDecodeError as e:
        return ChallengeTestResult(
            ok=False,
            message=f"Odpowiedź nie jest poprawnym JSON: {e}",
            detail=None,
        )
    except Exception as e:
        return ChallengeTestResult(ok=False, message=str(e), detail=None)

    challenge = payload.get("challenge", "")
    ts = payload.get("timestamp", "")
    if not challenge:
        return ChallengeTestResult(
            ok=False,
            message="Odpowiedź OK, ale brak pola 'challenge' w JSON.",
            detail=payload,
        )
    msg = (
        f"Połączenie z API działa.\n"
        f"Challenge: {challenge}\n"
        f"Znacznik czasu serwera: {ts}"
    )
    return ChallengeTestResult(ok=True, message=msg, detail=payload)
