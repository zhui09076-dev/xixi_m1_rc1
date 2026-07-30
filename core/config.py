"""配置模块 v2 — 支持 Soul/Body/Extension 目录配置"""
import yaml
from pathlib import Path
from typing import Dict, Any

DEFAULT_CONFIG = {
    "window": {
        "width": 1920,
        "height": 1080,
        "fullscreen": True,
        "renderer_click_through": True,
        "ui_always_on_top": False,
        "show_taskbar": True,
    },
    "render": {
        "fps": 30,
        "scale": 1.0,
        "layers": ["background", "character", "foreground", "lighting"],
    },
    "ollama": {
        "host": "http://localhost:11434",
        "model": "richardyoung/qwen3.6-27b-abliterated:latest",
        "timeout": 120,
        "context_length": 8192,
        "num_gpu": -1,
        "num_thread": 0,
        "temperature": 0.7,
        "top_p": 0.9,
        "top_k": 40,
        "repeat_penalty": 1.1,
        "keep_alive": "5m",
        "system_prompt_template": "default",
    },
    "voice": {
        "enabled": False,
        "model": "default",
        "language": "zh",
    },
    "assets": {
        "scene_dir": "assets/scenes",
        "character_dir": "assets/characters",
        "manifest": "assets/manifest.json",
    },
    "behavior": {
        "idle_timeout": 300,
        "max_chat_history": 50,
    },
    "database": {
        "path": "data/xixi.db",
    },
    "permissions": {
        "public_web_read_default": True,
        "authorized_paths": [
            "assets", "data", "logs", "projects", "workspace",
            "temp", "extensions", "souls", "bodies", "development",
        ],
    },
    "soul_packages_dir": "souls",
    "body_packages_dir": "bodies",
    "extensions_dir": "extensions",
    "development_dir": "development",
}


class Config:
    """配置对象，支持 dict-like 访问和属性访问"""

    def __init__(self, data: Dict[str, Any]):
        self._data = data

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            return object.__getattribute__(self, name)
        return self._data.get(name)

    def __getitem__(self, key: str) -> Any:
        return self._data[key]

    def get(self, key: str, default=None):
        """支持普通键和 ``section.key`` 点路径。"""
        if "." not in key:
            return self._data.get(key, default)
        value: Any = self._data
        for part in key.split("."):
            if not isinstance(value, dict) or part not in value:
                return default
            value = value[part]
        return value

    def to_dict(self) -> Dict[str, Any]:
        return dict(self._data)

    @classmethod
    def load(cls, path: str = "config.yaml") -> "Config":
        p = Path(path)
        if p.exists():
            with open(p, "r", encoding="utf-8") as f:
                user = yaml.safe_load(f) or {}
            merged = _deep_merge(dict(DEFAULT_CONFIG), user)
            return cls(merged)
        return cls(dict(DEFAULT_CONFIG))

    def save(self, path: str = "config.yaml"):
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(self._data, f, allow_unicode=True, sort_keys=False)


def _deep_merge(base: dict, override: dict) -> dict:
    result = dict(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result
