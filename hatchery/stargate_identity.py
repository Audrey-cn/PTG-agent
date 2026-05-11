from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
from pathlib import Path


KEY_TYPE = "progenitor-rsa-sha256-v1"
DEFAULT_E = 65537


def canonical_json(data: dict) -> bytes:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def b64u(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def unb64u(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode((data + padding).encode("ascii"))


def int_to_b64u(value: int) -> str:
    size = max(1, (value.bit_length() + 7) // 8)
    return b64u(value.to_bytes(size, "big"))


def b64u_to_int(value: str) -> int:
    return int.from_bytes(unb64u(value), "big")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _is_probable_prime(n: int, rounds: int = 16) -> bool:
    if n < 2:
        return False
    small_primes = (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37)
    if n in small_primes:
        return True
    if any(n % p == 0 for p in small_primes):
        return False

    d = n - 1
    s = 0
    while d % 2 == 0:
        s += 1
        d //= 2

    for _ in range(rounds):
        a = secrets.randbelow(n - 3) + 2
        x = pow(a, d, n)
        if x in (1, n - 1):
            continue
        for _ in range(s - 1):
            x = pow(x, 2, n)
            if x == n - 1:
                break
        else:
            return False
    return True


def _generate_prime(bits: int) -> int:
    while True:
        candidate = secrets.randbits(bits) | (1 << (bits - 1)) | 1
        if _is_probable_prime(candidate):
            return candidate


def generate_identity(node_id: str, bits: int = 1024) -> dict:
    half = bits // 2
    while True:
        p = _generate_prime(half)
        q = _generate_prime(half)
        if p == q:
            continue
        phi = (p - 1) * (q - 1)
        if phi % DEFAULT_E != 0:
            break
    n = p * q
    d = pow(DEFAULT_E, -1, phi)
    public_key = {"key_type": KEY_TYPE, "n": int_to_b64u(n), "e": DEFAULT_E}
    public_key_id = sha256_hex(canonical_json(public_key))
    return {
        "schema_version": "akashic.node-identity/v1",
        "node_id": node_id,
        "key_type": KEY_TYPE,
        "public_key": public_key,
        "public_key_id": public_key_id,
        "private_key": {"d": int_to_b64u(d)},
    }


def load_or_create_identity(path: Path, node_id: str, bits: int = 1024) -> dict:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    identity = generate_identity(node_id, bits=bits)
    path.write_text(json.dumps(identity, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return identity


def public_identity(identity: dict) -> dict:
    return {
        "schema_version": identity.get("schema_version", "akashic.node-identity/v1"),
        "node_id": identity["node_id"],
        "key_type": identity.get("key_type", KEY_TYPE),
        "public_key": identity["public_key"],
        "public_key_id": identity["public_key_id"],
    }


def signature_payload(document: dict) -> dict:
    return {k: v for k, v in document.items() if k != "signature"}


def sign_document(document: dict, identity: dict) -> dict:
    payload = signature_payload(document)
    digest = hashlib.sha256(canonical_json(payload)).digest()
    n = b64u_to_int(identity["public_key"]["n"])
    d = b64u_to_int(identity["private_key"]["d"])
    signature = pow(int.from_bytes(digest, "big"), d, n)
    signed = dict(payload)
    signed["signature"] = {
        "schema_version": "akashic.signature/v1",
        "key_type": identity.get("key_type", KEY_TYPE),
        "public_key_id": identity["public_key_id"],
        "algorithm": "rsa-sha256-raw",
        "value": int_to_b64u(signature),
    }
    return signed


def verify_document(document: dict, public_key: dict | None = None) -> bool:
    signature = document.get("signature") or {}
    key = public_key or document.get("public_key")
    if not key or signature.get("key_type") != KEY_TYPE:
        return False
    n = b64u_to_int(key["n"])
    e = int(key["e"])
    actual = pow(b64u_to_int(signature.get("value", "")), e, n)
    expected = int.from_bytes(hashlib.sha256(canonical_json(signature_payload(document))).digest(), "big")
    return actual == expected


def default_identity_path(port: int | str = "local") -> Path:
    runtime = Path(os.environ.get("PROGENITOR_RUNTIME_DIR", Path.cwd() / ".progenitor_runtime"))
    return runtime / "identity" / f"node_{port}.json"
