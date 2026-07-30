from __future__ import annotations

import json
import sys
from pathlib import Path

try:
    import jsonschema
    from referencing import Registry, Resource
except ImportError:
    print("需要安装 jsonschema: pip install jsonschema", file=sys.stderr)
    raise

ROOT = Path(__file__).resolve().parents[1]

def registry() -> Registry:
    reg = Registry()
    for path in (ROOT / "schemas").rglob("*.schema.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        resource = Resource.from_contents(data)
        if "$id" in data:
            reg = reg.with_resource(data["$id"], resource)
        reg = reg.with_resource(path.resolve().as_uri(), resource)
    return reg

def validate_file(path: Path) -> None:
    message = json.loads(path.read_text(encoding="utf-8"))
    schema_path = ROOT / "schemas/messages" / f"{message['type']}.schema.json"
    if not schema_path.exists():
        raise SystemExit(f"Unknown message type: {message['type']}")
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(schema, registry=registry()).validate(message)
    print(f"OK: {message['type']}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python reference/validate_message.py examples/user.input.json")
    validate_file(Path(sys.argv[1]))
