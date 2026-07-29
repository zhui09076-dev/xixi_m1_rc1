"""待办面板"""

from PyQt6.QtWidgets import QListWidget, QListWidgetItem, QLineEdit, QPushButton, QHBoxLayout, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt
from ui.glass_panel import GlassPanel


class TodoPanel(GlassPanel):
    def __init__(self, parent=None):
        super().__init__(parent, "待办")
        self._setup_ui()

    def _setup_ui(self):
        title = QLabel("待办事项")
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
        """)
        self.layout.addWidget(self.list_widget)

        hbox = QHBoxLayout()
        self.input = QLineEdit()
        self.input.setPlaceholderText("添加待办...")
        self.input.setStyleSheet("""
            QLineEdit {
                background-color: rgba(40, 40, 50, 200);
                color: #e0e0e0;
                border-radius: 6px;
                padding: 6px;
            }
        """)
        hbox.addWidget(self.input)

        add_btn = QPushButton("添加")
        add_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(60, 100, 160, 200);
                color: white;
                border-radius: 6px;
                padding: 6px 12px;
            }
        """)
        hbox.addWidget(add_btn)
        self.layout.addLayout(hbox)

    def add_todo(self, text: str):
        item = QListWidgetItem(f"[ ] {text}")
        self.list_widget.addItem(item)

    def get_todos(self) -> list:
        return [self.list_widget.item(i).text() for i in range(self.list_widget.count())]
