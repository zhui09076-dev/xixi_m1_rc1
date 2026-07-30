"""系统托盘管理"""
from PyQt6.QtWidgets import QSystemTrayIcon, QMenu, QApplication
from PyQt6.QtCore import pyqtSignal, QObject
from PyQt6.QtGui import QAction


class TrayManager(QObject):
    sig_show = pyqtSignal()
    sig_hide = pyqtSignal()
    sig_exit = pyqtSignal()

    def __init__(self, app: QApplication, parent=None):
        super().__init__(parent)
        self.app = app
        self.tray = QSystemTrayIcon(app)
        self.tray.setToolTip("西西 M1")
        self._build_menu()
        self.tray.activated.connect(self._on_activated)

    def _build_menu(self):
        menu = QMenu()
        show_action = QAction("显示", menu)
        show_action.triggered.connect(self.sig_show.emit)
        menu.addAction(show_action)

        hide_action = QAction("隐藏", menu)
        hide_action.triggered.connect(self.sig_hide.emit)
        menu.addAction(hide_action)

        menu.addSeparator()

        exit_action = QAction("安全退出", menu)
        exit_action.triggered.connect(self.sig_exit.emit)
        menu.addAction(exit_action)

        self.tray.setContextMenu(menu)

    def _on_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.sig_show.emit()

    def show(self):
        self.tray.show()

    def hide(self):
        self.tray.hide()
