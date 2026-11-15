"""Configuration loading for astra_security."""

from __future__ import annotations

import functools
import os
from pathlib import Path
from typing import Any

import yaml

_PATH_CACHE: dict[tuple[str, str], Path] = {}


def repo_root() -> Path:
    env = os.environ.get("ASTRA_ROOT")
    if env:
        return Path(env).resolve()
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "config").is_dir() and (parent / "contracts").is_dir():
            return parent
        if (parent / "backend" / "config").is_dir() and (parent / "backend" / "contracts").is_dir():
            return parent / "backend"
    return here.parents[2]


@functools.lru_cache(maxsize=None)
def _load_yaml_cached(relpath: str) -> dict:
    path = repo_root() / relpath
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def load_yaml(relpath: str) -> dict:
    """Load a YAML file relative to the repo root (cached)."""
    return _load_yaml_cached(relpath)


def reload_config() -> None:
    """Clear the config cache (useful in tests and after config edits)."""
    _load_yaml_cached.cache_clear()


def security_config() -> dict:
    return load_yaml("config/security.yaml")


def plausibility_config() -> dict:
    return load_yaml("config/plausibility.yaml")


def thresholds_config() -> dict:
    return load_yaml("config/thresholds.yaml")


def ports_config() -> dict:
    return load_yaml("config/ports.yaml")


def _dig(data: dict, dotted: str, default: Any = None) -> Any:
    node: Any = data
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            return default
        node = node[part]
    return node


def sec_get(dotted: str, default: Any = None) -> Any:
    """Read ``config/security.yaml`` via a dotted path, e.g. ``freshness.tolerance_seconds``."""
    return _dig(security_config(), dotted, default)


def plaus_get(dotted: str, default: Any = None) -> Any:
    return _dig(plausibility_config(), dotted, default)


def keys_dir() -> Path:
    """Directory that holds private keys and the security SQLite database."""
    env = os.environ.get("ASTRA_KEYS_DIR")
    path = Path(env) if env else repo_root() / sec_get("paths.keys_dir", "keys")
    cached = _PATH_CACHE.get(("keys", str(path)))
    if cached is None:
        path.mkdir(parents=True, exist_ok=True)
        cached = _PATH_CACHE[("keys", str(path))] = path
    return cached


def db_path() -> Path:
    """Path of the security SQLite database (overridable via ``ASTRA_DB``)."""
    env = os.environ.get("ASTRA_DB")
    path = Path(env) if env else repo_root() / sec_get("paths.db_file", "keys/astra_security.db")
    cached = _PATH_CACHE.get(("db", str(path)))
    if cached is None:
        path.parent.mkdir(parents=True, exist_ok=True)
        cached = _PATH_CACHE[("db", str(path))] = path
    return cached
