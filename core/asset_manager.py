"""资产包管理"""

import json
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass


@dataclass
class AssetPackage:
    id: str
    name: str
    version: str
    compatible_core: str
    scenes: List[str]
    characters: List[str]
    manifest_path: str


class AssetManager:
    def __init__(self, manifest_path: str = "assets/manifest.json"):
        self.manifest_path = Path(manifest_path)
        self.packages: Dict[str, AssetPackage] = {}
        self.active_package: Optional[str] = None
        self._load()

    def _load(self):
        if self.manifest_path.exists():
            with open(self.manifest_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for pkg_data in data.get("packages", []):
                pkg = AssetPackage(**pkg_data)
                self.packages[pkg.id] = pkg
            self.active_package = data.get("active_package")

    def get_active(self) -> Optional[AssetPackage]:
        if self.active_package and self.active_package in self.packages:
            return self.packages[self.active_package]
        return None

    def list_available(self) -> List[AssetPackage]:
        return list(self.packages.values())

    def get_scene_path(self, scene_name: str) -> Optional[str]:
        pkg = self.get_active()
        if pkg and scene_name in pkg.scenes:
            return str(Path(pkg.manifest_path).parent / "scenes" / f"{scene_name}.png")
        return None

    def get_character_pose(self, pose_name: str) -> Optional[str]:
        pkg = self.get_active()
        if pkg and pose_name in pkg.characters:
            return str(Path(pkg.manifest_path).parent / "characters" / f"{pose_name}.png")
        return None
