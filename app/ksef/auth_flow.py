"""Uwierzytelnianie tokenem KSeF: challenge → ksef-token → status → redeem."""
from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

from .crypto_util import encrypt_ksef_token_plaintext, _pick_cert
from .debug_log import ksef_debug
from .http_json import KsefHttpError, request_json


def fetch_public_certs(base_url: str) -> list[dict[str, Any]]:
    _, data = request_json("GET", f"{base_url}/security/public-key-certificates")
    if not isinstance(data, list):
        raise KsefHttpError("Nieprawidłowa odpowiedź certyfikatów", None)
    return data


def auth_challenge(base_url: str) -> dict[str, Any]:
    status, data = request_json("POST", f"{base_url}/auth/challenge", json_body={})
    if status != 200 or not isinstance(data, dict):
        raise KsefHttpError("Oczekiwano 200 z POST /auth/challenge", status)
    return data


def auth_ksef_token(
    base_url: str,
    *,
    challenge: str,
    timestamp_ms: int,
    ksef_token: str,
    nip: str,
    token_encryption_cert_der: bytes,
) -> dict[str, Any]:
    plain = f"{ksef_token}|{timestamp_ms}"
    enc_b64 = encrypt_ksef_token_plaintext(token_encryption_cert_der, plain)
    body = {
        "challenge": challenge,
        "contextIdentifier": {"type": "Nip", "value": nip},
        "encryptedToken": enc_b64,
    }
    status, data = request_json("POST", f"{base_url}/auth/ksef-token", json_body=body)
    if status not in (200, 202) or not isinstance(data, dict):
        raise KsefHttpError("Oczekiwano 200/202 z POST /auth/ksef-token", status)
    return data


def poll_auth_until_ready(
    base_url: str,
    reference_number: str,
    bearer_operation_token: str,
    *,
    timeout_s: float = 120.0,
    interval_s: float = 0.4,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_s
    last: dict[str, Any] = {}
    while time.monotonic() < deadline:
        status, data = request_json(
            "GET",
            f"{base_url}/auth/{reference_number}",
            bearer_token=bearer_operation_token,
        )
        if status != 200 or not isinstance(data, dict):
            raise KsefHttpError(f"GET /auth/{{ref}} zwrócił {status}", status)
        last = data
        st = (data.get("status") or {})
        code = st.get("code")
        if code == 200:
            return data
        if code in (400, 415, 425, 450, 460, 470, 480, 500, 550):
            desc = st.get("description", "")
            details = st.get("details")
            msg = f"Uwierzytelnianie nieudane ({code}): {desc} {details}"
            if code == 450:
                msg += (
                    "\n\nWskazowki (450 – serwer nie akceptuje tokenu):\n"
                    "- Token musi pochodzic z TEGO SAMEGO srodowiska co API (test: api-test.ksef.mf.gov.pl).\n"
                    "- W panelu KSeF token ma status Active (Pending = jeszcze nie do uzycia).\n"
                    "- KSEF_NIP = dokladnie 10 cyfr podmiotu powiazanego z tokenem.\n"
                    "- KSEF_TOKEN: pelny ciag (z |), bez cudzyslowow w zmiennej, bez enterow.\n"
                    "- Po uniewaznieniu / wygeneruj nowy token."
                )
            raise KsefHttpError(msg)
        time.sleep(interval_s)
    raise KsefHttpError(f"Timeout oczekiwania na uwierzytelnienie: {last}")


def redeem_tokens(base_url: str, bearer_operation_token: str) -> dict[str, Any]:
    status, data = request_json(
        "POST",
        f"{base_url}/auth/token/redeem",
        bearer_token=bearer_operation_token,
    )
    if status != 200 or not isinstance(data, dict):
        raise KsefHttpError("Oczekiwano 200 z POST /auth/token/redeem", status)
    return data


def obtain_access_token(
    base_url: str,
    *,
    ksef_token: str,
    nip: str,
) -> str:
    ksef_debug(f"obtain_access_token: start, base_url={base_url!r}")
    certs = fetch_public_certs(base_url)
    token_cert_der = _pick_cert(certs, "KsefTokenEncryption")

    ch = auth_challenge(base_url)
    challenge = ch.get("challenge")
    ts_ms = ch.get("timestampMs")
    if ts_ms is None and ch.get("timestamp"):
        try:
            ts_str = str(ch["timestamp"]).replace("Z", "+00:00")
            dt = datetime.fromisoformat(ts_str)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            ts_ms = int(dt.timestamp() * 1000)
        except Exception:
            ts_ms = None
    if not challenge or ts_ms is None:
        raise KsefHttpError(
            "Brak challenge lub znacznika czasu (timestampMs / timestamp) w odpowiedzi POST /auth/challenge",
            None,
        )

    init = auth_ksef_token(
        base_url,
        challenge=str(challenge),
        timestamp_ms=int(ts_ms),
        ksef_token=ksef_token,
        nip=nip,
        token_encryption_cert_der=token_cert_der,
    )
    ref = init.get("referenceNumber")
    auth_op = init.get("authenticationToken") or {}
    op_tok = auth_op.get("token")
    if not ref or not op_tok:
        raise KsefHttpError("Brak referenceNumber lub authenticationToken po init", None)

    ksef_debug(f"obtain_access_token: ksef-token init ref={ref!r}, oczekiwanie na gotowość…")
    poll_auth_until_ready(base_url, str(ref), str(op_tok))
    ksef_debug("obtain_access_token: auth gotowe, redeem…")
    tokens = redeem_tokens(base_url, str(op_tok))
    access = (tokens.get("accessToken") or {}).get("token")
    if not access:
        raise KsefHttpError("Brak accessToken.token po redeem", None)
    ksef_debug("obtain_access_token: access token otrzymany")
    return str(access)
