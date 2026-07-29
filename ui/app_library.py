"""应用库面板"""

from PyQt6.QtWidgets import QListWidget, QListWidgetItem, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt
from ui.glass_panel import GlassPanel


class AppLibrary(GlassPanel):
    def __init__(self, parent=None):
        super().__init__(parent, "应用库")
        self._setup_ui()

    def _setup_ui(self):
        title = QLabel("应用库")
        title.setStyleSheet("color: #e0e0e0; font-size: 16px; font-weight: bold;")
        self.layout.addWidget(title)

        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet("""
            QListWidget {
                background-color: rgba(30, 30, 40, 150);
                color: #e0e0e0;
                border-radius: 8px;
                border: none;
            }
            QListWidget::item {
                padding: 8px;
                border-radius: 4px;
            }
            QListWidget::item:selected {
                background-color: rgba(60, 100, 160, 150);
            }
        """)
        self.layout.addWidget(self.list_widget)

        # 示例应用
        for app_name in ["浏览器", "文件管理器", "终端", "代码编辑器", "音乐播放器"]:
            item = QListWidgetItem(app_name)
            self.list_widget.addItem(item)

    def get_selected(self) -> str:
        item = self.list_widget.currentItem()
        return item.text() if item else ""
