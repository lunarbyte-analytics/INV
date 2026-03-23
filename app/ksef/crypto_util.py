"""Szyfrowanie zgodne z API KSeF 2.0 (RSA-OAEP SHA-256, AES-256-CBC PKCS7)."""
from __future__ import annotations

import base64
import os
from datetime import datetime, timezone
from typing import Any

from cryptography import x509
from cryptography.hazmat.primitives import hashes, padding
from cryptography.hazmat.primitives.asymmetric import padding as asym_padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes


def _parse_valid_to_iso(s: str | None) -> datetime:
    if not s:
        return datetime.min.replace(tzinfo=timezone.utc)
    try:
        s2 = s.replace("Z", "+00:00")
        dt = datetime.fromisoformat(s2)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return datetime.min.replace(tzinfo=timezone.utc)


def _pick_cert(certs: list[dict[str, Any]], usage: str) -> bytes:
    """Wybiera certyfikat z danym usage; przy wielu — ten z najpóźniejszym validTo."""
    candidates: list[dict[str, Any]] = []
    for c in certs:
        u = c.get("usage") or []
        if usage in u:
            candidates.append(c)
    if not candidates:
        raise ValueError(
            f"Brak certyfikatu z usage={usage!r} w odpowiedzi /security/public-key-certificates"
        )
    best = max(candidates, key=lambda c: _parse_valid_to_iso(c.get("validTo")))
    return base64.b64decode(best["certificate"])


def encrypt_rsa_oaep_sha256_der(cert_der: bytes, plaintext: bytes) -> bytes:
    cert = x509.load_der_x509_certificate(cert_der)
    pub = cert.public_key()
    return pub.encrypt(
        plaintext,
        asym_padding.OAEP(
            mgf=asym_padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None,
        ),
    )


def encrypt_ksef_token_plaintext(cert_der: bytes, token_with_timestamp: str) -> str:
    enc = encrypt_rsa_oaep_sha256_der(cert_der, token_with_timestamp.encode("utf-8"))
    return base64.b64encode(enc).decode("ascii")


def new_aes_key_iv() -> tuple[bytes, bytes]:
    return os.urandom(32), os.urandom(16)


def encrypt_aes256_cbc_pkcs7(key: bytes, iv: bytes, data: bytes) -> bytes:
    padder = padding.PKCS7(128).padder()
    padded = padder.update(data) + padder.finalize()
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
    enc = cipher.encryptor()
    return enc.update(padded) + enc.finalize()
