"""玻璃面板基类"""
from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt


class GlassPanel(QWidget):
    """半透明玻璃效果面板"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
