from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]


def _pointer_exists(document, reference):
    value = document
    try:
        for segment in reference[2:].split("/"):
            value = value[segment.replace("~1", "/").replace("~0", "~")]
        return True
    except (KeyError, TypeError):
        return False


def test_generated_openapi_files_are_complete_and_resolve_contract_schemas():
    for path in (ROOT / "contracts" / "openapi.yaml", ROOT / "ground-backend" / "openapi.yaml"):
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
        operations = []
        local_refs = []

        def walk(value):
            if isinstance(value, dict):
                reference = value.get("$ref")
                if isinstance(reference, str) and reference.startswith("#/"):
                    local_refs.append(reference)
                for child in value.values():
                    walk(child)
            elif isinstance(value, list):
                for child in value:
                    walk(child)

        walk(document)
        for route, path_item in document["paths"].items():
            for method, operation in path_item.items():
                if method in {"get", "post", "put", "patch", "delete"}:
                    operations.append(operation["operationId"])
        assert len(operations) == len(set(operations))
        assert all(_pointer_exists(document, reference) for reference in local_refs)
        assert all((path.parent / reference).exists()
                   for reference in document["info"]["x-shared-contract-schemas"])
        assert "BearerAuth" in document["components"]["securitySchemes"]
        assert "/api/crew/overview" in document["paths"]
        assert "/api/commands" in document["paths"]
