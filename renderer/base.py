"""渲染器基类"""

from abc import ABC, abstractmethod
from typing import Dict


class BaseRenderer(ABC):
    @abstractmethod
    def render(self, state: Dict):
        pass

    @abstractmethod
    def set_scene(self, scene_name: str):
        pass

    @abstractmethod
    def set_character_pose(self, pose_name: str):
        pass

    @abstractmethod
    def update(self):
        pass
