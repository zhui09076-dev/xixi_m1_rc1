"""玻璃面板基类"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor


class GlassPanel(QWidget):
    def __init__(self, parent=None, title=""):
        super().__init__(parent)
        self.title = title
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._setup_ui()

    def _setup_ui(self):
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(16, 16, 16, 16)
        self.setStyleSheet("""
            GlassPanel {
                background-color: rgba(20, 20, 30, 180);
                border-radius: 12px;
                border: 1px solid rgba(255, 255, 255, 30);
            }
        """)

    def show_panel(self):
        self.show()
        self.raise_()

    def hide_panel(self):
        self.hide()
