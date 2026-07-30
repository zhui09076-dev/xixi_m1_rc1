from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, RefResolver


class ValidationError(RuntimeError):
    pass


def load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def validate_runtime_output(package_root: str | Path, payload: dict[str, Any]) -> None:
    root = Path(package_root)
    schema_dir = root / "schemas"
    runtime_schema = load_json(schema_dir / "runtime_output.schema.json")
    memory_schema = load_json(schema_dir / "memory_action.schema.json")
    tool_schema = load_json(schema_dir / "tool_request.schema.json")

    store = {
        memory_schema["$id"]: memory_schema,
        tool_schema["$id"]: tool_schema,
    }
    resolver = RefResolver.from_schema(runtime_schema, store=store)
    validator = Draft202012Validator(runtime_schema, resolver=resolver)
    errors = sorted(validator.iter_errors(payload), key=lambda e: list(e.path))
    if errors:
        formatted = "; ".join(
            f"{'/'.join(map(str, err.path)) or '<root>'}: {err.message}"
            for err in errors
        )
        raise ValidationError(formatted)
