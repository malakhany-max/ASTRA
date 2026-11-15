"""Field-level encryption (AES-256-GCM) with HKDF-derived keys."""

from __future__ import annotations

import base64
import json
import os
import stat
from pathlib import Path

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from .config import keys_dir
from .errors import CryptoError
from .util import b64d, b64e

_KEYRING_NAME = "keyring.json"
_HKDF_INFO = b"astra-field:"
_VERSION = 1
_KEYRING_CACHE: dict[str, dict] = {}


def _keyring_path() -> Path:
    return keys_dir() / _KEYRING_NAME


def _lock_down(path: Path) -> None:
    try:
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass


def _new_master() -> bytes:
    return AESGCM.generate_key(bit_length=256)


def _load_keyring() -> dict:
    env = os.environ.get("ASTRA_MASTER_KEY")
    key = f"env:{env}" if env else str(_keyring_path())
    cached = _KEYRING_CACHE.get(key)
    if cached is not None:
        return cached
    if env:
        try:
            raw = base64.b64decode(env)
        except Exception as exc:
            raise CryptoError("ASTRA_MASTER_KEY is not valid base64") from exc
        if len(raw) != 32:
            raise CryptoError("ASTRA_MASTER_KEY must decode to 32 bytes")
        _KEYRING_CACHE[key] = {"active": "env", "keys": {"env": b64e(raw)}}
        return _KEYRING_CACHE[key]
    path = Path(key)
    if path.exists():
        try:
            _KEYRING_CACHE[key] = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise CryptoError("keyring is corrupt") from exc
        return _KEYRING_CACHE[key]
    master = _new_master()
    keyring = {"active": "k1", "keys": {"k1": b64e(master)}}
    _save_keyring(keyring)
    _KEYRING_CACHE[key] = keyring
    return keyring


def _save_keyring(keyring: dict) -> None:
    path = _keyring_path()
    path.write_text(json.dumps(keyring, indent=2), encoding="utf-8")
    _lock_down(path)


def _active_key() -> tuple[str, bytes]:
    keyring = _load_keyring()
    kid = keyring["active"]
    raw = keyring["keys"].get(kid)
    if raw is None:
        raise CryptoError(f"active key id {kid!r} missing from keyring")
    return kid, base64.b64decode(raw)


def _key_for(kid: str) -> bytes:
    keyring = _load_keyring()
    raw = keyring["keys"].get(kid)
    if raw is None:
        raise CryptoError(f"unknown key id {kid!r}")
    return base64.b64decode(raw)


def _derive(master: bytes, context: str) -> bytes:
    return HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=None,
        info=_HKDF_INFO + context.encode("utf-8"),
    ).derive(master)


def encrypt_field(plaintext: str, context: str) -> str:
    """Encrypt ``plaintext`` under ``context``; returns a compact base64 token."""
    kid, master = _active_key()
    nonce = os.urandom(12)
    aead = AESGCM(_derive(master, context))
    ct = aead.encrypt(nonce, plaintext.encode("utf-8"), context.encode("utf-8"))
    token = {"v": _VERSION, "kid": kid, "n": b64e(nonce), "c": b64e(ct)}
    return "gcm1:" + b64e(json.dumps(token, separators=(",", ":")).encode("utf-8"))


def decrypt_field(token: str, context: str) -> str:
    """Decrypt a token produced by :func:`encrypt_field` under the same context."""
    if not token.startswith("gcm1:"):
        raise CryptoError("unrecognised ciphertext token")
    try:
        body = json.loads(b64d(token[len("gcm1:"):]).decode("utf-8"))
    except Exception as exc:
        raise CryptoError("malformed ciphertext token") from exc
    master = _key_for(body["kid"])
    aead = AESGCM(_derive(master, context))
    try:
        pt = aead.decrypt(b64d(body["n"]), b64d(body["c"]), context.encode("utf-8"))
    except Exception as exc:
        raise CryptoError("decryption failed (wrong context or tampered token)") from exc
    return pt.decode("utf-8")


def rotate_master_key() -> str:
    """Generate a new active master key; returns its id. Old keys are kept."""
    keyring = _load_keyring()
    existing = [k for k in keyring["keys"] if k.startswith("k")]
    next_num = max([int(k[1:]) for k in existing if k[1:].isdigit()] or [0]) + 1
    kid = f"k{next_num}"
    keyring["keys"][kid] = b64e(_new_master())
    keyring["active"] = kid
    _save_keyring(keyring)
    return kid
