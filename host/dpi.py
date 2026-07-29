"""DPI 管理器"""

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt


class DPIManager:
    def __init__(self, app: QApplication):
        self.app = app
        self.scale = 1.0
        self._detect()

    def _detect(self):
        screen = self.app.primaryScreen()
        if screen:
            dpi = screen.logicalDotsPerInch()
            self.scale = dpi / 96.0
            # 设置全局属性
            self.app.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling, True)

    def scaled(self, value: int) -> int:
        return int(value * self.scale)
