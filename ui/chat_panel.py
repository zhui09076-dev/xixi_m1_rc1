"""对话面板"""

from PyQt6.QtWidgets import QTextEdit, QLineEdit, QPushButton, QVBoxLayout, QHBoxLayout
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from ui.glass_panel import GlassPanel


class ChatPanel(GlassPanel):
    message_sent = pyqtSignal(str)
    abort_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent, "对话")
        self._setup_chat_ui()
        self._streaming = False

    def _setup_chat_ui(self):
        # 聊天历史
        self.history = QTextEdit()
        self.history.setReadOnly(True)
        font = QFont("Microsoft YaHei", 11)
        self.history.setFont(font)
        self.history.setStyleSheet("""
            QTextEdit {
                background-color: transparent;
                color: #e0e0e0;
                border: none;
            }
        """)
        self.layout.addWidget(self.history)

        # 输入区
        hbox = QHBoxLayout()
        self.input_box = QLineEdit()
        self.input_box.setPlaceholderText("跟西西说点什么...")
        self.input_box.returnPressed.connect(self._send)
        self.input_box.setStyleSheet("""
            QLineEdit {
                background-color: rgba(40, 40, 50, 200);
                color: #e0e0e0;
                border-radius: 8px;
                padding: 8px;
                border: 1px solid rgba(255, 255, 255, 40);
            }
        """)
        hbox.addWidget(self.input_box)

        send_btn = QPushButton("发送")
        send_btn.clicked.connect(self._send)
        send_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(60, 100, 160, 200);
                color: white;
                border-radius: 8px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: rgba(80, 120, 180, 200);
            }
        """)
        hbox.addWidget(send_btn)

        abort_btn = QPushButton("打断")
        abort_btn.clicked.connect(self._abort)
        abort_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(160, 60, 60, 200);
                color: white;
                border-radius: 8px;
                padding: 8px 16px;
            }
        """)
        hbox.addWidget(abort_btn)

        self.layout.addLayout(hbox)

    def _send(self):
        text = self.input_box.text().strip()
        if text:
            self.input_box.clear()
            self.history.append(f"<b>你：</b> {text}")
            self.message_sent.emit(text)

    def _abort(self):
        self.abort_requested.emit()
        self.history.append("<b>西西：</b> （已停止）")

    def start_stream(self):
        self._streaming = True
        self.history.append("<b>西西：</b> ")

    def append_stream_chunk(self, chunk: str):
        if self._streaming:
            cursor = self.history.textCursor()
            cursor.movePosition(cursor.MoveOperation.End)
            cursor.insertText(chunk)
            self.history.setTextCursor(cursor)
            self.history.ensureCursorVisible()

    def end_stream(self):
        self._streaming = False
        self.history.append("")

    def append_message(self, role: str, text: str):
        if role == "user":
            self.history.append(f"<b>你：</b> {text}")
        else:
            self.history.append(f"<b>西西：</b> {text}")
