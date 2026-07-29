"""项目面板"""

from PyQt6.QtWidgets import QListWidget, QListWidgetItem, QLineEdit, QPushButton, QHBoxLayout, QLabel, QTextEdit
from ui.glass_panel import GlassPanel


class ProjectPanel(GlassPanel):
    def __init__(self, parent=None):
        super().__init__(parent, "项目")
        self._setup_ui()

    def _setup_ui(self):
        title = QLabel("项目管理")
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
        """)
        self.layout.addWidget(self.list_widget)

        hbox = QHBoxLayout()
        self.input = QLineEdit()
        self.input.setPlaceholderText("新建项目...")
        self.input.setStyleSheet("""
            QLineEdit {
                background-color: rgba(40, 40, 50, 200);
                color: #e0e0e0;
                border-radius: 6px;
                padding: 6px;
            }
        """)
        hbox.addWidget(self.input)

        add_btn = QPushButton("创建")
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

        self.desc_edit = QTextEdit()
        self.desc_edit.setPlaceholderText("项目描述...")
        self.desc_edit.setStyleSheet("""
            QTextEdit {
                background-color: rgba(30, 30, 40, 150);
                color: #e0e0e0;
                border-radius: 8px;
                border: none;
                padding: 8px;
            }
        """)
        self.layout.addWidget(self.desc_edit)

    def add_project(self, name: str):
        item = QListWidgetItem(name)
        self.list_widget.addItem(item)

    def get_selected(self) -> str:
        item = self.list_widget.currentItem()
        return item.text() if item else ""
