"""模型设置面板"""

from PyQt6.QtWidgets import QLabel, QLineEdit, QPushButton, QVBoxLayout, QFormLayout
from ui.glass_panel import GlassPanel


class ModelPanel(GlassPanel):
    def __init__(self, parent=None):
        super().__init__(parent, "模型设置")
        self._setup_ui()

    def _setup_ui(self):
        title = QLabel("模型设置")
        title.setStyleSheet("color: #e0e0e0; font-size: 16px; font-weight: bold;")
        self.layout.addWidget(title)

        form = QFormLayout()

        self.host_input = QLineEdit("http://localhost:11434")
        self.host_input.setStyleSheet("""
            QLineEdit {
                background-color: rgba(40, 40, 50, 200);
                color: #e0e0e0;
                border-radius: 6px;
                padding: 6px;
            }
        """)
        form.addRow("Ollama Host:", self.host_input)

        self.model_input = QLineEdit("richardyoung/qwen3.6-27b-abliterated:latest")
        self.model_input.setStyleSheet(self.host_input.styleSheet())
        form.addRow("Model:", self.model_input)

        save_btn = QPushButton("保存")
        save_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(60, 100, 160, 200);
                color: white;
                border-radius: 6px;
                padding: 6px 12px;
            }
        """)
        form.addRow(save_btn)

        self.layout.addLayout(form)

    def get_settings(self) -> dict:
        return {
            "host": self.host_input.text(),
            "model": self.model_input.text(),
        }
