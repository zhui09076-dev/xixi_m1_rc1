"""快速记录面板"""

from PyQt6.QtWidgets import QTextEdit, QPushButton, QVBoxLayout, QLabel
from ui.glass_panel import GlassPanel


class QuickNote(GlassPanel):
    def __init__(self, parent=None):
        super().__init__(parent, "快速记录")
        self._setup_ui()

    def _setup_ui(self):
        title = QLabel("快速记录")
        title.setStyleSheet("color: #e0e0e0; font-size: 16px; font-weight: bold;")
        self.layout.addWidget(title)

        self.text_edit = QTextEdit()
        self.text_edit.setPlaceholderText("写下你的想法...")
        self.text_edit.setStyleSheet("""
            QTextEdit {
                background-color: rgba(30, 30, 40, 150);
                color: #e0e0e0;
                border-radius: 8px;
                border: none;
                padding: 8px;
            }
        """)
        self.layout.addWidget(self.text_edit)

        save_btn = QPushButton("保存")
        save_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(60, 100, 160, 200);
                color: white;
                border-radius: 6px;
                padding: 6px 12px;
            }
        """)
        self.layout.addWidget(save_btn)

    def get_text(self) -> str:
        return self.text_edit.toPlainText()

    def clear(self):
        self.text_edit.clear()
