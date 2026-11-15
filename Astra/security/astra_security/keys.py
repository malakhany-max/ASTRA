"""Key management + offline trust store."""

from __future__ import annotations

import base64
import os
import stat
from pathlib import Path

from nacl.signing import SigningKey, VerifyKey

from .config import keys_dir
from .errors import ConfigError, RevokedDeviceError, UnknownDeviceError
from .store import get_store
from .util import now_iso

NODE_HUB = "hub-01"
NODE_GROUND = "ground-01"
NODE_AUDIT = "audit-node"
NODE_LINK = "link-sim"


def encode_verify_key(verify_key: VerifyKey) -> str:
    return base64.b64encode(bytes(verify_key)).decode("ascii")


def decode_verify_key(value: str | VerifyKey) -> VerifyKey:
    if isinstance(value, VerifyKey):
        return value
    return VerifyKey(base64.b64decode(value))


def encode_signing_key(signing_key: SigningKey) -> str:
    return base64.b64encode(bytes(signing_key)).decode("ascii")


def decode_signing_key(value: str | SigningKey) -> SigningKey:
    if isinstance(value, SigningKey):
        return value
    return SigningKey(base64.b64decode(value))


def generate_keypair() -> tuple[SigningKey, VerifyKey]:
    """Generate a fresh Ed25519 keypair."""
    signing_key = SigningKey.generate()
    return signing_key, signing_key.verify_key


def _lock_down(path: Path) -> None:
    """Best-effort restrict a key file to the owner (0600)."""
    try:
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass


def save_private_key(path: str | Path, signing_key: SigningKey) -> None:
    """Persist a private key as base64 of the 32-byte seed, then lock it down."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(encode_signing_key(signing_key), encoding="ascii")
    _lock_down(path)


def load_private_key(path: str | Path) -> SigningKey:
    path = Path(path)
    if not path.exists():
        raise ConfigError(f"private key file not found: {path}")
    return SigningKey(base64.b64decode(path.read_text(encoding="ascii").strip()))


def save_public_key(path: str | Path, verify_key: VerifyKey) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(encode_verify_key(verify_key), encoding="ascii")


def load_public_key(path: str | Path) -> VerifyKey:
    return VerifyKey(base64.b64decode(Path(path).read_text(encoding="ascii").strip()))


def device_key_path(device_id: str) -> Path:
    safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in device_id)
    return keys_dir() / f"device-{safe}.key"


def ensure_device_key(device_id: str) -> SigningKey:
    """Load a device's private key, generating + persisting one on first use."""
    path = device_key_path(device_id)
    if path.exists():
        signing_key = load_private_key(path)
    else:
        signing_key, _ = generate_keypair()
        save_private_key(path, signing_key)
    if get_device(device_id) is None:
        pair_device(device_id, signing_key.verify_key,
                    astronaut_id=_astronaut_from_device(device_id), source="auto")
    return signing_key


def _astronaut_from_device(device_id: str) -> str:
    if "-" in device_id:
        tail = device_id.rsplit("-", 1)[-1]
        if tail and tail[0].upper() == "A":
            digits = tail[1:]
            if digits.isdigit():
                return f"A-{int(digits):02d}"
    return "unknown"


def node_key_path(node_id: str) -> Path:
    safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in node_id)
    return keys_dir() / f"node-{safe}.key"


def node_pub_path(node_id: str) -> Path:
    safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in node_id)
    return keys_dir() / f"node-{safe}.pub"


def ensure_node_key(node_id: str) -> SigningKey:
    path = node_key_path(node_id)
    if path.exists():
        return load_private_key(path)
    signing_key, verify_key = generate_keypair()
    save_private_key(path, signing_key)
    save_public_key(node_pub_path(node_id), verify_key)
    return signing_key


def get_node_verify_key(node_id: str) -> VerifyKey | None:
    pub = node_pub_path(node_id)
    if pub.exists():
        return load_public_key(pub)
    if node_key_path(node_id).exists():
        return load_private_key(node_key_path(node_id)).verify_key
    return None


class TrustStore:
    """Pinned public keys for paired devices (backed by SQLite)."""

    def __init__(self, store=None) -> None:
        self.store = store or get_store()

    def pair_device(self, device_id: str, public_key: VerifyKey | str,
                    astronaut_id: str, source: str | None = None) -> None:
        self.store.upsert_device(
            device_id, astronaut_id, encode_verify_key(decode_verify_key(public_key)),
            source=source, created_ts=now_iso(),
        )

    def revoke_device(self, device_id: str) -> bool:
        return self.store.revoke(device_id, now_iso())

    def get(self, device_id: str) -> dict | None:
        return self.store.get_device(device_id)

    def is_paired(self, device_id: str) -> bool:
        row = self.store.get_device(device_id)
        return bool(row) and not row["revoked"]

    def is_revoked(self, device_id: str) -> bool:
        row = self.store.get_device(device_id)
        return bool(row) and bool(row["revoked"])

    def public_key(self, device_id: str) -> VerifyKey | None:
        row = self.store.get_device(device_id)
        if not row:
            return None
        return VerifyKey(base64.b64decode(row["public_key"]))

    def require_paired(self, device_id: str) -> dict:
        row = self.store.get_device(device_id)
        if row is None:
            raise UnknownDeviceError(f"device not paired: {device_id}")
        if row["revoked"]:
            raise RevokedDeviceError(f"device revoked: {device_id}")
        return row

    def list_devices(self) -> list[dict]:
        return self.store.list_devices()


def _trust() -> TrustStore:
    return TrustStore()


def pair_device(device_id: str, public_key: VerifyKey | str, astronaut_id: str,
                source: str | None = None) -> None:
    _trust().pair_device(device_id, public_key, astronaut_id, source=source)


def revoke_device(device_id: str) -> bool:
    return _trust().revoke_device(device_id)


def is_trusted(device_id: str) -> bool:
    return _trust().is_paired(device_id)


def is_revoked(device_id: str) -> bool:
    return _trust().is_revoked(device_id)


def get_public_key(device_id: str) -> VerifyKey | None:
    return _trust().public_key(device_id)


def get_device(device_id: str) -> dict | None:
    return _trust().get(device_id)


def list_devices() -> list[dict]:
    return _trust().list_devices()
