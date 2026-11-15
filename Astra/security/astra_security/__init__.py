"""astra_security — Security SDK for ASTRA Companion."""

from __future__ import annotations

__version__ = "0.2.0"

from .audit import audit_log, get_entries, verify_chain, verify_chain_detailed
from .bundles import (
    apply_revocation_bundle,
    make_bundle,
    make_revocation_bundle,
    sign_bundle,
    verify_bundle,
)
from .config import (
    db_path,
    keys_dir,
    plausibility_config,
    plaus_get,
    reload_config,
    repo_root,
    sec_get,
    security_config,
    thresholds_config,
)
from .consent import consent_allows, default_consent, filter_for_uplink
from .crypto_store import decrypt_field, encrypt_field, rotate_master_key
from .envelope import decrypt_envelope_payload, make_envelope, sign_envelope, verify_envelope
from .errors import (
    AuthError,
    ConfigError,
    CryptoError,
    PermissionDenied,
    ReplayError,
    RevokedDeviceError,
    SecurityError,
    SignatureError,
    UnknownDeviceError,
)
from .events import (
    list_events,
    raise_security_event,
    reset_shield,
    set_uplink_sink,
    shield_state,
)
from .integrity import verify_and_classify
from .keys import (
    NODE_AUDIT,
    NODE_GROUND,
    NODE_HUB,
    NODE_LINK,
    TrustStore,
    encode_verify_key,
    ensure_device_key,
    ensure_node_key,
    generate_keypair,
    get_device,
    get_node_verify_key,
    get_public_key,
    is_revoked,
    is_trusted,
    list_devices,
    load_private_key,
    pair_device,
    revoke_device,
    save_private_key,
)
from .signing import (
    canonicalize,
    new_nonce,
    now_iso,
    sign_reading,
    sign_reading_with_key,
    validate_reading_shape,
    verify_reading_signature,
    verify_signature,
)
from .store import Store, get_store, reset_store
from . import bundles, consent, crypto_store, envelope, rbac, store, util

__all__ = [
    "__version__",
    "canonicalize", "now_iso", "new_nonce",
    "sign_reading", "sign_reading_with_key", "verify_signature",
    "verify_reading_signature", "validate_reading_shape",
    "verify_and_classify",
    "raise_security_event", "shield_state", "reset_shield", "set_uplink_sink", "list_events",
    "audit_log", "verify_chain", "verify_chain_detailed", "get_entries",
    "encrypt_field", "decrypt_field", "rotate_master_key",
    "sign_bundle", "verify_bundle", "make_bundle",
    "make_revocation_bundle", "apply_revocation_bundle",
    "sign_envelope", "verify_envelope", "make_envelope", "decrypt_envelope_payload",
    "filter_for_uplink", "default_consent", "consent_allows",
    "generate_keypair", "save_private_key", "load_private_key",
    "ensure_device_key", "ensure_node_key", "get_node_verify_key",
    "encode_verify_key", "TrustStore",
    "pair_device", "revoke_device", "is_trusted", "is_revoked",
    "get_public_key", "get_device", "list_devices",
    "NODE_HUB", "NODE_GROUND", "NODE_AUDIT", "NODE_LINK",
    "security_config", "plausibility_config", "thresholds_config",
    "reload_config", "repo_root", "keys_dir", "db_path", "sec_get", "plaus_get",
    "Store", "get_store", "reset_store",
    "rbac", "consent", "crypto_store", "envelope", "bundles", "store", "util",
    "SecurityError", "ConfigError", "UnknownDeviceError", "RevokedDeviceError",
    "SignatureError", "ReplayError", "CryptoError", "PermissionDenied", "AuthError",
]
