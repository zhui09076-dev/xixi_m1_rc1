"""系统托盘管理"""

from PyQt6.QtWidgets import QSystemTrayIcon, QMenu, QWidget
from PyQt6.QtGui import QAction, QIcon


class TrayManager:
    def __init__(self, app, window: QWidget):
        self.app = app
        self.window = window
        self.tray = QSystemTrayIcon(app)
        self.tray.setVisible(True)
        self._setup_menu()

    def _setup_menu(self):
        menu = QMenu()
        show_action = QAction("显示", self.window)
        show_action.triggered.connect(self.window.show)
        menu.addAction(show_action)

        hide_action = QAction("隐藏", self.window)
        hide_action.triggered.connect(self.window.hide)
        menu.addAction(hide_action)

        menu.addSeparator()

        quit_action = QAction("退出", self.window)
        quit_action.triggered.connect(self.app.quit)
        menu.addAction(quit_action)

        self.tray.setContextMenu(menu)

    def show_message(self, title: str, message: str):
        self.tray.showMessage(title, message, QSystemTrayIcon.MessageIcon.Information)
