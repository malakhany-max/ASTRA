"""Load shared supportive-care content without coupling the engine to the API."""

from __future__ import annotations

import os
from pathlib import Path

import yaml


def load_plan_content(path: Path | None = None) -> dict:
    """Return the plan adapter section from the Companion-owned content file."""
    root = Path(os.environ.get("ASTRA_ROOT", Path(__file__).resolve().parents[1]))
    project = Path(os.environ.get("ASTRA_PROJECT", root.parent))
    candidates = (
        project / "ai-companion" / "companion" / "content" / "library.yaml",
        root / "companion" / "content" / "library.yaml",
    )
    source = path or next((item for item in candidates if item.is_file()), candidates[0])
    try:
        with source.open("r", encoding="utf-8") as handle:
            document = yaml.safe_load(handle) or {}
    except FileNotFoundError:
        return {}
    content = document.get("plan_content", {})
    return content if isinstance(content, dict) else {}
