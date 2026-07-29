"""配置管理"""

import yaml
from pathlib import Path
from dataclasses import dataclass


@dataclass
class Config:
    window: dict
    render: dict
    ollama: dict
    voice: dict
    assets: dict
    behavior: dict
    database: dict

    @classmethod
    def load(cls, path: str = "config.yaml"):
        p = Path(path)
        if not p.exists():
            return cls._default()
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return cls(**data)

    @classmethod
    def _default(cls):
        return cls(
            window={"width": 1920, "height": 1080, "fullscreen": True},
            render={"fps": 30, "scale": 1.0, "layers": ["background", "character", "foreground", "lighting"]},
            ollama={"host": "http://localhost:11434", "model": "richardyoung/qwen3.6-27b-abliterated:latest", "timeout": 120},
            voice={"enabled": False, "model": "default", "language": "zh"},
            assets={"scene_dir": "assets/scenes", "character_dir": "assets/characters", "manifest": "assets/manifest.json"},
            behavior={"idle_timeout": 300, "max_chat_history": 50},
            database={"path": "data/xixi.db"},
        )
