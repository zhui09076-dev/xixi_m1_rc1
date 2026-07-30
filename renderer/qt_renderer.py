"""Qt 渲染器实现"""
from PyQt6.QtWidgets import QWidget, QApplication
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPainter, QPixmap
from renderer.base import BaseRenderer


class QtRenderer(BaseRenderer, QWidget):
    """基于 PyQt6 的渲染器，支持分层渲染"""

    def __init__(self, config=None, parent=None):
        QWidget.__init__(self, parent)
        self.config = config or {}
        self._layers = {}
        self._pixmaps = {}
        self._fps = self.config.get("render", {}).get("fps", 30)
        self._scale = self.config.get("render", {}).get("scale", 1.0)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.update)
        self._setup_window()

    def _setup_window(self):
        flags = (
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnBottomHint |
            Qt.WindowType.Tool
        )
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        screen = QApplication.primaryScreen().geometry()
        w = self.config.get("window", {}).get("width", screen.width())
        h = self.config.get("window", {}).get("height", screen.height())
        self.resize(int(w * self._scale), int(h * self._scale))
        self.move(0, 0)

    def show(self):
        super().show()
        self._timer.start(int(1000 / self._fps))

    def hide(self):
        self._timer.stop()
        super().hide()

    def set_layer(self, layer_name: str, asset_id: str):
        self._layers[layer_name] = asset_id
        # 尝试加载图片
        path = f"assets/{layer_name}/{asset_id}"
        pixmap = QPixmap(path)
        if not pixmap.isNull():
            self._pixmaps[layer_name] = pixmap
        self.update()

    def clear(self):
        self._layers.clear()
        self._pixmaps.clear()
        self.update()

    def update_state(self, state_dict: dict):
        pose = state_dict.get("pose", "standing")
        mood = state_dict.get("mood", "neutral")
        # 根据状态和心情更新图层
        self.set_layer("character", f"{pose}.png")

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        # 按 layers 顺序绘制
        layer_order = self.config.get("render", {}).get("layers", ["background", "character", "foreground", "lighting"])
        for layer in layer_order:
            if layer in self._pixmaps:
                pixmap = self._pixmaps[layer]
                painter.drawPixmap(self.rect(), pixmap)
        painter.end()
