"""资产管理器"""
import json
from pathlib import Path
from typing import Dict, List, Optional


class AssetManager:
    """管理场景、角色等资源包"""

    def __init__(self, manifest_path: str = "assets/manifest.json"):
        self.manifest_path = Path(manifest_path)
        self._manifest: Dict = {}
        self._load()

    def _load(self):
        if self.manifest_path.exists():
            with open(self.manifest_path, "r", encoding="utf-8") as f:
                self._manifest = json.load(f)
        else:
            self._manifest = {"scenes": {}, "characters": {}, "version": "1.0.0"}

    def save(self):
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.manifest_path, "w", encoding="utf-8") as f:
            json.dump(self._manifest, f, ensure_ascii=False, indent=2)

    def get_scene(self, scene_id: str) -> Optional[str]:
        return self._manifest.get("scenes", {}).get(scene_id)

    def get_character(self, char_id: str) -> Optional[str]:
        return self._manifest.get("characters", {}).get(char_id)

    def list_scenes(self) -> List[str]:
        return list(self._manifest.get("scenes", {}).keys())

    def list_characters(self) -> List[str]:
        return list(self._manifest.get("characters", {}).keys())

    def register_scene(self, scene_id: str, path: str):
        self._manifest.setdefault("scenes", {})[scene_id] = path
        self.save()

    def register_character(self, char_id: str, path: str):
        self._manifest.setdefault("characters", {})[char_id] = path
        self.save()
