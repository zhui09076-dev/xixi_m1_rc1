"""
桌面窗口
========
- 全屏底层窗口
- WS_EX_TRANSPARENT + WS_EX_NOACTIVATE
- 始终置底
- 支持超宽屏
"""

import sys
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout
from PyQt6.QtCore import Qt, QPoint, QTimer
from PyQt6.QtGui import QCursor


class DesktopWindow(QWidget):
    def __init__(self, app: QApplication, config: dict):
        super().__init__()
        self.app = app
        self.config = config
        self._setup_window()
        self._setup_layers()

    def _setup_window(self):
        self.setWindowTitle("西西桌面伴侣")

        # 全屏无边框
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysBottomHint |
            Qt.WindowType.Tool
        )

        # 获取屏幕尺寸
        screen = self.app.primaryScreen()
        geo = screen.availableGeometry()
        self.screen_width = geo.width()
        self.screen_height = geo.height()

        self.setGeometry(0, 0, self.screen_width, self.screen_height)

        # 设置透明背景
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # 主布局
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # 分层容器
        self.renderer_container = QWidget()
        self.renderer_container.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        self.ui_container = QWidget()

        hbox = QHBoxLayout()
        hbox.setContentsMargins(0, 0, 0, 0)
        hbox.addWidget(self.renderer_container, stretch=1)
        hbox.addWidget(self.ui_container, stretch=0)

        self.main_layout.addLayout(hbox)

    def _setup_layers(self):
        """设置渲染分层"""
        pass  # 由 renderer 填充

    def get_renderer_container(self) -> QWidget:
        return self.renderer_container

    def get_ui_container(self) -> QWidget:
        return self.ui_container

    def show_window(self):
        self.show()
        self.lower()  # 置底

    def set_click_through(self, enabled: bool):
        """设置鼠标穿透"""
        self.renderer_container.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents, enabled
        )
