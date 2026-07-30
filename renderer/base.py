"""渲染器基类"""
from abc import ABC, abstractmethod
from typing import Dict


class BaseRenderer(ABC):
    """渲染器抽象基类"""

    @abstractmethod
    def show(self):
        pass

    @abstractmethod
    def hide(self):
        pass

    @abstractmethod
    def set_layer(self, layer_name: str, asset_id: str):
        pass

    @abstractmethod
    def clear(self):
        pass

    @abstractmethod
    def update_state(self, state_dict: Dict):
        pass
