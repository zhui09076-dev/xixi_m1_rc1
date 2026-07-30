"""Windows 窗口管理 — Renderer + UI 双窗口，独立事件循环安全"""
import sys
from pathlib import Path

try:
    from PyQt6.QtWidgets import (
        QApplication, QWidget, QVBoxLayout, QHBoxLayout,
        QTextEdit, QLineEdit, QPushButton, QLabel, QListWidget,
        QSystemTrayIcon, QMenu, QMainWindow
    )
    from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QPoint
    from PyQt6.QtGui import QAction, QIcon, QFont, QKeyEvent
except ImportError as e:
    print(f"PyQt6 not available: {e}")
    QWidget = object
    QMainWindow = object
    Qt = object


class RendererWindow(QWidget):
    """
    Renderer 窗口：
    - 独立底层窗口
    - 鼠标穿透（click-through）
    - 无边框、无标题栏
    - 显示角色/场景/前景/光照层
    - 异常不阻塞桌面
    """

    def __init__(self, config=None, parent=None):
        super().__init__(parent)
        self.config = config or {}
        self._setup_window()
        self._layers = {}

    def _setup_window(self):
        # 无边框、无标题栏、保持在最底层
        flags = (
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnBottomHint |
            Qt.WindowType.Tool
        )
        self.setWindowFlags(flags)

        # 鼠标穿透
        click_through = self.config.get("window", {}).get("renderer_click_through", True)
        if click_through:
            self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        # 全屏或按配置尺寸
        screen = QApplication.primaryScreen().geometry()
        w = self.config.get("window", {}).get("width", screen.width())
        h = self.config.get("window", {}).get("height", screen.height())
        self.resize(w, h)
        self.move(0, 0)

        # 背景透明（让桌面壁纸透出）
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

    def set_layer_image(self, layer_name: str, image_path: str):
        self._layers[layer_name] = image_path
        self.update()

    def clear_layers(self):
        self._layers.clear()
        self.update()

    def hide_window(self):
        self.hide()

    def restore_window(self):
        self.show()
        self.raise_()

    def safe_exit(self):
        self.clear_layers()
        self.close()


class UIWindow(QMainWindow):
    """
    UI 窗口：
    - 独立可交互窗口
    - 可点击、可输入
    - 聊天面板、快捷操作、设置入口
    - 支持隐藏/恢复
    """

    sig_send_message = pyqtSignal(str)
    sig_hide_renderer = pyqtSignal()
    sig_show_renderer = pyqtSignal()
    sig_safe_exit = pyqtSignal()

    def __init__(self, config=None, parent=None):
        super().__init__(parent)
        self.config = config or {}
        self._setup_window()
        self._build_ui()

    def _setup_window(self):
        self.setWindowTitle("西西")
        flags = Qt.WindowType.Window
        if self.config.get("window", {}).get("ui_always_on_top", False):
            flags |= Qt.WindowType.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.resize(400, 600)
        screen = QApplication.primaryScreen().geometry()
        self.move(screen.width() - 420, 100)

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # 聊天显示区
        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        self.chat_display.setPlaceholderText("对话记录...")
        layout.addWidget(self.chat_display)

        # 输入区
        input_layout = QHBoxLayout()
        self.input_box = QLineEdit()
        self.input_box.setPlaceholderText("和西西说点什么...")
        self.input_box.returnPressed.connect(self._on_send)
        input_layout.addWidget(self.input_box)

        self.send_btn = QPushButton("发送")
        self.send_btn.clicked.connect(self._on_send)
        input_layout.addWidget(self.send_btn)
        layout.addLayout(input_layout)

        # 快捷操作
        btn_layout = QHBoxLayout()
        self.hide_btn = QPushButton("隐藏角色")
        self.hide_btn.clicked.connect(self.sig_hide_renderer.emit)
        btn_layout.addWidget(self.hide_btn)

        self.show_btn = QPushButton("显示角色")
        self.show_btn.clicked.connect(self.sig_show_renderer.emit)
        btn_layout.addWidget(self.show_btn)

        self.exit_btn = QPushButton("安全退出")
        self.exit_btn.clicked.connect(self.sig_safe_exit.emit)
        btn_layout.addWidget(self.exit_btn)
        layout.addLayout(btn_layout)

        # 状态栏
        self.status_label = QLabel("就绪")
        layout.addWidget(self.status_label)

    def _on_send(self):
        text = self.input_box.text().strip()
        if text:
            self.append_chat("你", text)
            self.sig_send_message.emit(text)
            self.input_box.clear()

    def append_chat(self, role: str, text: str):
        self.chat_display.append(f"<b>{role}：</b>{text}")

    def set_status(self, text: str):
        self.status_label.setText(text)

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key.Key_Escape:
            self.hide()
        else:
            super().keyPressEvent(event)

    def hide_window(self):
        self.hide()

    def restore_window(self):
        self.show()
        self.raise_()
        self.activateWindow()

    def safe_exit(self):
        self.close()


class WindowManager:
    """
    管理 Renderer + UI 双窗口：
    - 启动、隐藏、恢复、安全退出
    - 连接系统托盘
    - Renderer 异常隔离
    """

    def __init__(self, app: QApplication, config=None):
        self.app = app
        self.config = config or {}
        self.renderer: RendererWindow = None
        self.ui: UIWindow = None
        self.tray = None

    def create_windows(self):
        self.renderer = RendererWindow(self.config)
        self.ui = UIWindow(self.config)
        self.ui.sig_hide_renderer.connect(self.hide_renderer)
        self.ui.sig_show_renderer.connect(self.show_renderer)
        self.ui.sig_safe_exit.connect(self.safe_exit)
        return self.renderer, self.ui

    def show_all(self):
        if self.renderer:
            self.renderer.show()
        if self.ui:
            self.ui.show()

    def hide_renderer(self):
        if self.renderer:
            self.renderer.hide_window()

    def show_renderer(self):
        if self.renderer:
            self.renderer.restore_window()

    def hide_ui(self):
        if self.ui:
            self.ui.hide_window()

    def show_ui(self):
        if self.ui:
            self.ui.restore_window()

    def safe_exit(self):
        if self.ui:
            self.ui.safe_exit()
        if self.renderer:
            self.renderer.safe_exit()
        if self.tray:
            self.tray.hide()
        self.app.quit()

    def setup_tray(self, tray_manager):
        self.tray = tray_manager
        if self.tray:
            self.tray.sig_show.connect(self.show_all)
            self.tray.sig_hide.connect(self._hide_all)
            self.tray.sig_exit.connect(self.safe_exit)

    def _hide_all(self):
        self.hide_renderer()
        self.hide_ui()

    def on_renderer_error(self, error: Exception):
        if self.ui:
            self.ui.append_chat("系统", f"Renderer 异常：{error}\n已隔离，桌面不受影响。")
        if self.renderer:
            try:
                self.renderer.close()
            except Exception:
                pass
            self.renderer = None
