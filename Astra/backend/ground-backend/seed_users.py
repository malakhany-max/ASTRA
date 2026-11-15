"""Create a Ground Station user from local environment variables."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent / "security"))

import astra_security as sec


def main():
    username = os.environ.get("ASTRA_GROUND_ADMIN_USER")
    password = os.environ.get("ASTRA_GROUND_ADMIN_PASSWORD")
    if not username or not password:
        raise SystemExit("Set ASTRA_GROUND_ADMIN_USER and ASTRA_GROUND_ADMIN_PASSWORD first.")
    sec.rbac.add_user(username, password, "admin")
    print(f"Created local Ground Station admin user {username!r}.")


if __name__ == "__main__": main()
