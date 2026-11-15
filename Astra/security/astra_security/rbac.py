"""RBAC: roles, permission matrix, argon2 passwords, short-lived JWT sessions."""

from __future__ import annotations

import os
import stat
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from .audit import audit_log
from .config import keys_dir
from .errors import AuthError, PermissionDenied
from .store import get_store
from .util import now_iso

ROLES = ("astronaut", "viewer", "medical_officer", "flight_surgeon", "admin")

PERMISSIONS: dict[str, set[str]] = {
    "astronaut": {"read_self", "write_self"},
    "viewer": {"read_crew", "read_self"},
    "medical_officer": {"read_crew", "read_self", "write_self", "ack_alert"},
    "flight_surgeon": {"read_crew", "read_self", "write_self", "issue_command", "ack_alert"},
    "admin": {"read_crew", "read_self", "write_self", "issue_command", "ack_alert",
              "manage_users", "read_audit"},
}

_PH = PasswordHasher()
_SESSION_TTL_MINUTES = 30
_JWT_ALG = "HS256"


def hash_password(password: str) -> str:
    return _PH.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _PH.verify(password_hash, password)
    except (VerifyMismatchError, Exception):
        return False


def add_user(username: str, password: str, role: str, astronaut_id: str | None = None) -> None:
    if role not in ROLES:
        raise ValueError(f"unknown role: {role}")
    get_store().upsert_user(username, role, hash_password(password), astronaut_id, now_iso())
    audit_log("admin", "add_user", username, {"role": role, "astronaut_id": astronaut_id})


def authenticate(username: str, password: str) -> dict:
    """Validate credentials; return the principal. Raises :class:`AuthError`."""
    row = get_store().get_user(username)
    if row is None or not verify_password(password, row["password_hash"]):
        audit_log(username, "login_failed", username, {})
        raise AuthError("invalid credentials")
    principal = {"username": username, "role": row["role"], "astronaut_id": row["astronaut_id"]}
    audit_log(username, "login", username, {"role": row["role"]})
    return principal


def logout(username: str) -> None:
    audit_log(username, "logout", username, {})


def has_permission(role: str, permission: str) -> bool:
    return permission in PERMISSIONS.get(role, set())


def can_access_astronaut(principal: dict, astronaut_id: str) -> bool:
    """Astronauts only their own data; ground staff (read_crew) anyone."""
    role = principal.get("role")
    if role == "astronaut":
        return principal.get("astronaut_id") == astronaut_id
    return has_permission(role, "read_crew")


def _jwt_secret() -> bytes:
    env = os.environ.get("ASTRA_JWT_SECRET")
    if env:
        return env.encode("utf-8")
    path = keys_dir() / "jwt.key"
    if path.exists():
        return path.read_bytes()
    secret = os.urandom(48)
    path.write_bytes(secret)
    try:
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass
    return secret


def create_session(user: dict, ttl_minutes: int = _SESSION_TTL_MINUTES) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user["username"],
        "role": user["role"],
        "astronaut_id": user.get("astronaut_id"),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=ttl_minutes)).timestamp()),
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, _jwt_secret(), algorithm=_JWT_ALG)


def decode_session(token: str) -> dict:
    try:
        payload = jwt.decode(token, _jwt_secret(), algorithms=[_JWT_ALG])
    except jwt.ExpiredSignatureError as exc:
        raise AuthError("session expired") from exc
    except jwt.InvalidTokenError as exc:
        raise AuthError("invalid session token") from exc
    return {"username": payload["sub"], "role": payload["role"],
            "astronaut_id": payload.get("astronaut_id")}


def require_permission(permission: str):
    """Return a FastAPI dependency enforcing ``permission`` on the bearer token."""
    from fastapi import Header, HTTPException

    def _dependency(authorization: str | None = Header(default=None)) -> dict:
        if not authorization or not authorization.lower().startswith("bearer "):
            raise HTTPException(status_code=401, detail="missing bearer token")
        token = authorization.split(" ", 1)[1].strip()
        try:
            principal = decode_session(token)
        except AuthError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        if not has_permission(principal["role"], permission):
            audit_log(principal["username"], "permission_denied", permission,
                      {"role": principal["role"]})
            raise HTTPException(status_code=403, detail=f"role {principal['role']} lacks {permission}")
        return principal

    return _dependency
