from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import yaml


class SoulPackageError(RuntimeError):
    pass


class SoulPackage:
    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        self.manifest = self._load_json("manifest.json")
        self._validate_manifest()
        self.content = self._load_entries()

    def _load_json(self, rel: str) -> dict[str, Any]:
        path = self.root / rel
        if not path.is_file():
            raise SoulPackageError(f"Missing file: {rel}")
        return json.loads(path.read_text(encoding="utf-8"))

    def _load_yaml(self, rel: str) -> dict[str, Any]:
        path = self.root / rel
        if not path.is_file():
            raise SoulPackageError(f"Missing file: {rel}")
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {"value": data}

    def _validate_manifest(self) -> None:
        required = ["packageType", "packageId", "version", "schemaVersion", "entry"]
        missing = [k for k in required if k not in self.manifest]
        if missing:
            raise SoulPackageError(f"Manifest missing fields: {missing}")
        if self.manifest["packageType"] != "xixi-soul":
            raise SoulPackageError("Wrong packageType")

    def _load_entries(self) -> dict[str, Any]:
        loaded: dict[str, Any] = {}
        for key, rel in self.manifest["entry"].items():
            suffix = Path(rel).suffix.lower()
            if suffix == ".json":
                loaded[key] = self._load_json(rel)
            elif suffix in {".yaml", ".yml"}:
                loaded[key] = self._load_yaml(rel)
            else:
                path = self.root / rel
                if not path.is_file():
                    raise SoulPackageError(f"Missing file: {rel}")
                loaded[key] = path.read_text(encoding="utf-8")
        return loaded

    def verify_checksums(self) -> None:
        checksum_path = self.root / "checksums.json"
        if not checksum_path.is_file():
            raise SoulPackageError("Missing checksums.json")
        expected = json.loads(checksum_path.read_text(encoding="utf-8"))
        for rel, digest in expected.items():
            path = self.root / rel
            if not path.is_file():
                raise SoulPackageError(f"Checksum target missing: {rel}")
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
            if actual != digest:
                raise SoulPackageError(f"Checksum mismatch: {rel}")
