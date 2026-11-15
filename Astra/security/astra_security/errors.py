"""ASTRA security exceptions."""

from __future__ import annotations


class SecurityError(Exception):
    """Base class for every astra_security error."""


class ConfigError(SecurityError):
    """Missing or malformed configuration."""


class UnknownDeviceError(SecurityError):
    """A device_id is not present in the trust store."""


class RevokedDeviceError(SecurityError):
    """A device_id exists but has been revoked."""


class SignatureError(SecurityError):
    """A signature could not be verified."""


class ReplayError(SecurityError):
    """A message re-used a nonce or a non-increasing seq."""


class CryptoError(SecurityError):
    """Field-level encryption/decryption failure."""


class PermissionDenied(SecurityError):
    """RBAC: the principal lacks the required permission."""


class AuthError(SecurityError):
    """Login/session failure."""
