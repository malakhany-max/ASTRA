"""Generate the editable composite backend API contract."""

from __future__ import annotations

import copy
import json
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT.parent
OUTPUT = Path(__file__).resolve().parent / "openapi.yaml"
SHARED_OUTPUT = ROOT / "contracts" / "openapi.yaml"


def _add_import_paths() -> None:
    root_value = str(ROOT)
    if root_value not in sys.path:
        sys.path.insert(0, root_value)
    for folder in ("engine", "link", "attack_sim", "simulators", "ground-backend"):
        value = str(ROOT / folder)
        if value not in sys.path:
            sys.path.insert(0, value)
    for folder in ("security", "ai-companion"):
        value = str(PROJECT / folder)
        if value not in sys.path:
            sys.path.insert(0, value)


def _rewrite_refs(value, prefix: str, component_names: dict[str, dict[str, str]]):
    if isinstance(value, list):
        return [_rewrite_refs(item, prefix, component_names) for item in value]
    if not isinstance(value, dict):
        return value
    result = {}
    for key, item in value.items():
        if key == "$ref" and isinstance(item, str):
            match = re.fullmatch(r"#/components/([^/]+)/([^/]+)", item)
            if match:
                category, name = match.groups()
                mapped = component_names.get(category, {}).get(name)
                if mapped:
                    item = f"#/components/{category}/{mapped}"
        result[key] = _rewrite_refs(item, prefix, component_names)
    return result


def _merge_schema(left: dict, right: dict) -> dict:
    candidates = []
    for schema in (left, right):
        if "oneOf" in schema and set(schema) == {"oneOf"}:
            candidates.extend(schema["oneOf"])
        else:
            candidates.append(schema)
    unique = {json.dumps(item, sort_keys=True): item for item in candidates}
    return next(iter(unique.values())) if len(unique) == 1 else {"oneOf": list(unique.values())}


def _merge_responses(existing: dict, incoming: dict) -> dict:
    result = copy.deepcopy(existing)
    for code, response in incoming.items():
        if code not in result:
            result[code] = copy.deepcopy(response)
            continue
        current = result[code]
        descriptions = [current.get("description", ""), response.get("description", "")]
        current["description"] = " / ".join(dict.fromkeys(item for item in descriptions if item))
        content = current.setdefault("content", {})
        for media_type, media in response.get("content", {}).items():
            if media_type not in content:
                content[media_type] = copy.deepcopy(media)
                continue
            old_schema = content[media_type].get("schema")
            new_schema = media.get("schema")
            if old_schema and new_schema:
                content[media_type]["schema"] = _merge_schema(old_schema, new_schema)
    return result


def _merge_operation(existing: dict, incoming: dict) -> dict:
    result = copy.deepcopy(existing)
    result["servers"] = list({item["url"]: item for item in result.get("servers", []) + incoming.get("servers", [])}.values())
    result["tags"] = list(dict.fromkeys(result.get("tags", []) + incoming.get("tags", [])))
    result["responses"] = _merge_responses(result.get("responses", {}), incoming.get("responses", {}))
    for field in ("parameters",):
        values = result.get(field, []) + incoming.get(field, [])
        result[field] = list({json.dumps(item, sort_keys=True): item for item in values}.values())
    if "requestBody" not in result and "requestBody" in incoming:
        result["requestBody"] = copy.deepcopy(incoming["requestBody"])
    return result


def _runtime_apps():
    scratch = Path(tempfile.mkdtemp(prefix=".openapi-scratch-", dir=ROOT))
    os.environ["ASTRA_DB"] = str(scratch / "security.db")
    os.environ["ASTRA_KEYS_DIR"] = str(scratch / "keys")
    os.environ["ASTRA_HUB_DB"] = str(scratch / "hub.db")
    os.environ["ASTRA_GROUND_DB"] = str(scratch / "ground.db")
    os.environ["ASTRA_GROUND_BACKUP"] = str(scratch / "backup.enc")
    os.environ["ASTRA_LINK_DB"] = str(scratch / "link.db")
    _add_import_paths()

    from astra_link import LinkQueue
    from astra_link.app import create_app as create_link_app, http_forward
    from astra_link.link_sim import LinkSimulator
    from astra_ground.app import app as ground_app
    from companion.main import app as companion_app
    from hub.app import app as hub_app

    config = yaml.safe_load((ROOT / "config" / "ports.yaml").read_text(encoding="utf-8"))
    host = config["hosts"]["loopback"]
    ports = config["ports"]
    queue = LinkQueue(str(scratch / "link-spec.db"))
    link_app = create_link_app(LinkSimulator(queue, http_forward))
    apps = [
        ("Hub", int(ports["hub"]), hub_app),
        ("GroundStation", int(ports["ground-backend"]), ground_app),
        ("Companion", int(ports["companion"]), companion_app),
        ("LinkSimulator", int(ports["link-sim"]), link_app),
    ]
    return apps, queue, host, scratch


def build_spec(shared_schema_prefix: str = "../contracts/") -> dict:
    apps, queue, host, scratch = _runtime_apps()
    paths: dict = {}
    components: dict[str, dict] = {}
    tags = []
    for service, port, app in apps:
        base_url = f"http://{host}:{port}"
        source = app.openapi()
        tags.extend(source.get("tags", []))
        maps: dict[str, dict[str, str]] = {}
        for category, definitions in source.get("components", {}).items():
            maps[category] = {name: f"{service}_{name}" for name in definitions}
        rewritten_components = _rewrite_refs(source.get("components", {}), service, maps)
        for category, definitions in rewritten_components.items():
            target = components.setdefault(category, {})
            target.update({maps.get(category, {}).get(name, f"{service}_{name}"): value
                           for name, value in definitions.items()})

        for route, path_item in source.get("paths", {}).items():
            target = paths.setdefault(route, {})
            for method, operation in path_item.items():
                if method not in {"get", "post", "put", "patch", "delete", "options", "head", "trace"}:
                    target.setdefault(method, copy.deepcopy(operation))
                    continue
                updated = _rewrite_refs(operation, service, maps)
                updated["operationId"] = f"{service}_{updated.get('operationId', method)}"
                updated["tags"] = list(dict.fromkeys([service] + updated.get("tags", [])))
                updated["servers"] = [{"url": base_url}]
                target[method] = _merge_operation(target[method], updated) if method in target else updated

    schema_files = sorted(path.name for path in (ROOT / "contracts").glob("*.schema.json"))
    result = {
        "openapi": "3.1.0",
        "info": {
            "title": "ASTRA Backend Services",
            "version": "1.0.0",
            "description": (
                "Editable composite contract generated from the running Hub, Ground Station, "
                "Companion and Link Simulator FastAPI interfaces. Shared wire schemas are listed "
                "under x-shared-contract-schemas; this file is a backend-owned working copy."
            ),
            "x-shared-contract-schemas": [f"{shared_schema_prefix}{name}" for name in schema_files],
        },
        "paths": paths,
        "components": components,
        "tags": [{"name": service} for service, _, _ in apps] + tags,
    }
    result["components"].setdefault("securitySchemes", {})["BearerAuth"] = {
        "type": "http", "scheme": "bearer", "bearerFormat": "JWT",
        "description": "Short-lived local Ground Station access token.",
    }
    required_auth = {
        ("/auth/logout", "post"), ("/api/commands", "get"), ("/api/commands", "post"),
        ("/api/crew/overview", "get"), ("/api/alerts", "get"),
    }
    optional_self_auth = {("/api/checkin", "post")}
    for route in ("/api/consent/{astronaut_id}",):
        optional_self_auth.update({(route, "get"), (route, "put")})
    optional_self_auth.add(("/api/alerts/{alert_id}/ack", "post"))
    for route, path_item in result["paths"].items():
        if route.startswith("/api/astronauts/{astronaut_id}"):
            optional_self_auth.update((route, method) for method in path_item if method in {"get", "post", "put", "patch", "delete"})
        for method, operation in path_item.items():
            if method not in {"get", "post", "put", "patch", "delete"}:
                continue
            if (route, method) in required_auth:
                operation["security"] = [{"BearerAuth": []}]
            elif (route, method) in optional_self_auth:
                operation["security"] = [{"BearerAuth": []}, {}]
    from hub import security_adapter as sec
    sec._sdk.reset_store()
    closed = set()
    for _, _, app in apps:
        for candidate in (getattr(app.state, "store", None),
                          getattr(app.state, "link_queue", None),
                          getattr(getattr(app.state, "sim", None), "queue", None)):
            if candidate is not None and id(candidate) not in closed:
                close = getattr(candidate, "close", None)
                if close:
                    close()
                closed.add(id(candidate))
    queue.close()
    scratch = scratch.resolve()
    if scratch.parent != ROOT.resolve() or not scratch.name.startswith(".openapi-scratch-"):
        raise RuntimeError(f"Refusing to remove unexpected scratch path: {scratch}")
    shutil.rmtree(scratch)
    return result


def main() -> None:
    spec = build_spec()
    OUTPUT.write_text(yaml.safe_dump(spec, sort_keys=False, allow_unicode=True), encoding="utf-8")
    shared_spec = copy.deepcopy(spec)
    shared_spec["info"]["x-shared-contract-schemas"] = [
        f"./{Path(item).name}" for item in shared_spec["info"]["x-shared-contract-schemas"]
    ]
    SHARED_OUTPUT.write_text(yaml.safe_dump(shared_spec, sort_keys=False, allow_unicode=True), encoding="utf-8")
    print(OUTPUT)
    print(SHARED_OUTPUT)


if __name__ == "__main__":
    main()
