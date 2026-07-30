"""DPI 适配"""
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt


class DPIManager:
    """处理高 DPI 屏幕适配"""

    @staticmethod
    def setup(app: QApplication):
        app.setStyle("Fusion")
        # 启用高 DPI 缩放
        try:
            from PyQt6.QtCore import QDir
            QDir.addSearchPath("assets", "assets")
        except Exception:
            pass
