"""聊天面板"""
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QTextEdit, QLineEdit, QPushButton, QHBoxLayout
from PyQt6.QtCore import pyqtSignal


class ChatPanel(QWidget):
    sig_send = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        self.display = QTextEdit()
        self.display.setReadOnly(True)
        layout.addWidget(self.display)

        input_layout = QHBoxLayout()
        self.input_box = QLineEdit()
        self.input_box.setPlaceholderText("输入消息...")
        self.input_box.returnPressed.connect(self._send)
        input_layout.addWidget(self.input_box)

        btn = QPushButton("发送")
        btn.clicked.connect(self._send)
        input_layout.addWidget(btn)
        layout.addLayout(input_layout)

    def _send(self):
        text = self.input_box.text().strip()
        if text:
            self.sig_send.emit(text)
            self.input_box.clear()

    def append(self, role: str, text: str):
        self.display.append(f"<b>{role}：</b>{text}")
