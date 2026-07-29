from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import jsonschema
from referencing import Registry, Resource

def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))

def build_registry():
    reg = Registry()
    for path in (ROOT / "schemas").rglob("*.schema.json"):
        data = load(path)
        resource = Resource.from_contents(data)
        if "$id" in data:
            reg = reg.with_resource(data["$id"], resource)
        reg = reg.with_resource(path.resolve().as_uri(), resource)
    return reg

REGISTRY = build_registry()

class ProtocolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = load(ROOT / "MESSAGE_CATALOG.json")
        cls.types = [x["type"] for x in cls.catalog]

    def validate(self, message):
        schema = load(ROOT / "schemas/messages" / f"{message['type']}.schema.json")
        jsonschema.Draft202012Validator(schema, registry=REGISTRY).validate(message)

    def test_catalog_unique(self):
        self.assertEqual(len(self.types), len(set(self.types)))

    def test_22_message_types(self):
        self.assertEqual(len(self.types), 22)

    def test_every_type_has_schema_and_example(self):
        for t in self.types:
            self.assertTrue((ROOT / "schemas/messages" / f"{t}.schema.json").exists(), t)
            self.assertTrue((ROOT / "schemas/payloads" / f"{t}.schema.json").exists(), t)
            self.assertTrue((ROOT / "examples" / f"{t}.json").exists(), t)

    def test_all_examples_validate(self):
        for t in self.types:
            with self.subTest(t=t):
                self.validate(load(ROOT / "examples" / f"{t}.json"))

    def test_private_outbound_requires_permission_risk(self):
        m = load(ROOT / "examples/permission.request.json")
        self.assertEqual(m["payload"]["risk"], "outbound_private")
        self.validate(m)

    def test_interrupt_never_saves_partial(self):
        m = load(ROOT / "examples/assistant.stream.interrupted.json")
        self.assertIs(m["payload"]["partial_text_saved"], False)
        self.validate(m)

    def test_body_intent_has_no_asset_path(self):
        m = load(ROOT / "examples/body.intent.set.json")
        text = json.dumps(m, ensure_ascii=False).lower()
        for forbidden in [".png", ".jpg", ".webp", ".mp4", "file://"]:
            self.assertNotIn(forbidden, text)
        self.validate(m)

    def test_soul_output_is_exact_runtime_contract(self):
        m = load(ROOT / "examples/soul.turn.output.json")
        self.validate(m)
        self.assertEqual(
            set(m["payload"]),
            {"reply", "state", "memory_actions", "tool_requests", "body_intent", "attention"}
        )

    def test_wrong_source_is_rejected(self):
        m = load(ROOT / "examples/user.input.json")
        m["source"] = "soul"
        with self.assertRaises(jsonschema.ValidationError):
            self.validate(m)

    def test_wrong_protocol_is_rejected(self):
        m = load(ROOT / "examples/session.hello.json")
        m["protocol"] = "xixi/2.0"
        with self.assertRaises(jsonschema.ValidationError):
            self.validate(m)

    def test_irreversible_is_not_allowed_in_permission_request_example(self):
        # This example is specifically the private outbound flow.
        m = load(ROOT / "examples/permission.request.json")
        self.assertNotEqual(m["payload"]["risk"], "ordinary")

    def test_manifests_are_pinned(self):
        manifest = load(ROOT / "manifest.json")
        self.assertEqual(manifest["compatiblePackages"]["soul"]["packageId"], "xixi-soul-main")
        self.assertEqual(manifest["compatiblePackages"]["ui"]["packageId"], "xixi-ui-main")
        self.assertFalse(manifest["compatiblePackages"]["body"]["requiredForProtocolImplementation"])

if __name__ == "__main__":
    unittest.main()
