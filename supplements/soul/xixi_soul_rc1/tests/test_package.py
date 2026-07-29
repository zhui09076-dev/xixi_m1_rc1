from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime.package_loader import SoulPackage
from runtime.prompt_builder import build_prompt
from runtime.validators import validate_runtime_output


class SoulPackageTests(unittest.TestCase):
    def test_manifest_entries_exist(self):
        manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
        for rel in manifest["entry"].values():
            self.assertTrue((ROOT / rel).is_file(), rel)

    def test_all_yaml_parses(self):
        for path in ROOT.rglob("*.yaml"):
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            self.assertIsNotNone(data, str(path))

    def test_loader_and_checksums(self):
        package = SoulPackage(ROOT)
        package.verify_checksums()
        self.assertEqual(package.manifest["packageId"], "xixi-soul-main")

    def test_identity_is_model_independent(self):
        identity = yaml.safe_load((ROOT / "identity.yaml").read_text(encoding="utf-8"))
        nature = identity["identity"]["nature"]
        self.assertTrue(nature["not_equal_to_current_model"])
        self.assertTrue(identity["identity"]["continuity"]["preserve_across_model_switch"])

    def test_single_active_identity_pointer_is_external(self):
        identity = yaml.safe_load((ROOT / "identity.yaml").read_text(encoding="utf-8"))
        data = identity["identity"]
        self.assertTrue(data["active_identity_pointer_owned_by_container"])
        self.assertTrue(data["official_identity_rules"]["exactly_one_active_official_identity"])

    def test_runtime_examples_validate(self):
        for path in (ROOT / "examples").glob("*.json"):
            payload = json.loads(path.read_text(encoding="utf-8"))
            validate_runtime_output(ROOT, payload)

    def test_prompt_builder(self):
        text = build_prompt(
            system_base="SYSTEM",
            constitution_summary="CONST",
            identity_summary="IDENTITY",
            personality_mode="WORK",
            current_state="STATE",
            current_project="PROJECT",
            relevant_memory="MEMORY",
            recent_conversation="CHAT",
            available_capabilities="TOOLS",
            user_message="HELLO",
        )
        for token in ["SYSTEM", "CONST", "IDENTITY", "PROJECT", "MEMORY", "HELLO"]:
            self.assertIn(token, text)

    def test_regression_ids_unique(self):
        doc = json.loads((ROOT / "regression/regression_cases.json").read_text(encoding="utf-8"))
        ids = [x["id"] for x in doc["cases"]]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertGreaterEqual(len(ids), 25)


if __name__ == "__main__":
    unittest.main()
