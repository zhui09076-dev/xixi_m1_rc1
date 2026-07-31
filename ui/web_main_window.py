"""
Web Main Window - 桌面悬浮窗版
使用 QWebEngineView 加载 UI RC1，窗口无边框、透明背景、可拖动
集成 QWebChannel，实现 Python <-> JavaScript 双向通信
"""
from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from PyQt6.QtCore import Qt, QUrl, pyqtSignal, QObject, QTimer, QPoint, QRect
from PyQt6.QtWidgets import (
    QMainWindow, QVBoxLayout, QWidget, QApplication,
    QHBoxLayout, QPushButton, QLabel, QLineEdit, QTextEdit,
)
from PyQt6.QtGui import QMouseEvent, QKeyEvent

# QWebEngineView 和 QWebChannel
try:
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    from PyQt6.QtWebChannel import QWebChannel
    WEBENGINE_AVAILABLE = True
except ImportError:
    WEBENGINE_AVAILABLE = False
    logger = logging.getLogger("xixi.ui")
    logger.warning("PyQt6-WebEngine not installed. Falling back to native Qt UI.")

from core.web_bridge import WebBridge
from core.protocol_server import MsgType, ErrorCode

logger = logging.getLogger("xixi.ui.web")

class WebMainWindow(QMainWindow):
    """
    西西桌面伴侣 - 主交互窗口

    特性:
    - 无边框、无标题栏、圆角透明背景
    - 悬浮在桌面上，像桌宠一样
    - 可拖动、可贴边隐藏/呼出
    - 加载 UI RC1 的 Web 界面
    - QWebChannel 桥接 Python 和 JavaScript
    """

    def __init__(self, config, db, container):
        super().__init__()
        self.config = config
        self.db = db
        self.container = container

        # 拖动相关
        self._drag_pos = None
        self._is_dragging = False

        # 贴边隐藏相关
        self._edge_hide_enabled = True
        self._hidden_on_edge = False
        self._hide_timer = QTimer(self)
        self._hide_timer.timeout.connect(self._check_edge_hide)
        self._hide_timer.start(500)

        self._setup_window()
        self._setup_ui()
        self._setup_tray()

    def _setup_window(self):
        """设置窗口为桌面悬浮窗样式"""
        # 无边框、无标题栏、保持在最上层（方便交互）
        flags = (
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool |
            Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setWindowFlags(flags)

        # 透明背景
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        # 默认大小：不要太大，像桌面助手
        screen = QApplication.primaryScreen().geometry()
        default_width = min(1200, int(screen.width() * 0.72))
        default_height = min(850, int(screen.height() * 0.78))
        self.resize(default_width, default_height)

        # 默认位置：屏幕右下角，像桌宠
        x = screen.width() - default_width - 30
        y = screen.height() - default_height - 80
        self.move(x, y)

        # 设置圆角（通过样式表）
        self.setStyleSheet("""
            QMainWindow {
                background: transparent;
                border: none;
            }
            QWidget {
                background: transparent;
            }
        """)

    def _setup_ui(self):
        """设置 UI 内容"""
        # 主容器 - 圆角 + 半透明背景
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.central_widget.setStyleSheet("""
            QWidget {
                background-color: rgba(20, 25, 35, 0.92);
                border-radius: 16px;
                border: 1px solid rgba(255, 255, 255, 0.08);
            }
        """)

        layout = QVBoxLayout(self.central_widget)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(0)

        # 标题栏（可拖动区域）
        title_bar = QWidget()
        title_bar.setFixedHeight(32)
        title_bar.setStyleSheet("""
            QWidget {
                background: transparent;
                border: none;
            }
        """)
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(12, 0, 12, 0)

        self.title_label = QLabel("西西")
        self.title_label.setStyleSheet("""
            QLabel {
                color: rgba(255, 255, 255, 0.7);
                font-size: 13px;
                font-weight: bold;
                background: transparent;
                border: none;
            }
        """)
        title_layout.addWidget(self.title_label)
        title_layout.addStretch()

        # 最小化按钮
        self.min_btn = QLabel("—")
        self.min_btn.setStyleSheet("""
            QLabel {
                color: rgba(255, 255, 255, 0.5);
                font-size: 14px;
                padding: 4px 8px;
                background: transparent;
                border-radius: 4px;
            }
            QLabel:hover {
                color: rgba(255, 255, 255, 0.9);
                background: rgba(255, 255, 255, 0.1);
            }
        """)
        self.min_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        title_layout.addWidget(self.min_btn)

        # 关闭按钮
        self.close_btn = QLabel("×")
        self.close_btn.setStyleSheet("""
            QLabel {
                color: rgba(255, 255, 255, 0.5);
                font-size: 16px;
                padding: 4px 8px;
                background: transparent;
                border-radius: 4px;
            }
            QLabel:hover {
                color: #ff6b6b;
                background: rgba(255, 107, 107, 0.15);
            }
        """)
        self.close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        title_layout.addWidget(self.close_btn)

        layout.addWidget(title_bar)

        if not WEBENGINE_AVAILABLE:
            # 降级：使用原生 Qt UI
            self._setup_fallback_ui(layout)
            return

        # ── QWebEngineView 加载 UI RC1 ──
        self.web_view = QWebEngineView()
        self.web_view.setStyleSheet("""
            QWebEngineView {
                background: transparent;
                border-radius: 12px;
            }
        """)
        layout.addWidget(self.web_view)

        # QWebChannel 设置
        self.channel = QWebChannel()
        self.bridge = WebBridge(container=self.container)
        self.channel.registerObject("xixiBridge", self.bridge)
        self.web_view.page().setWebChannel(self.channel)

        # 加载 UI RC1
        ui_path = self._get_ui_path()
        if ui_path:
            self.web_view.load(QUrl.fromLocalFile(str(ui_path)))
            logger.info("Loading UI RC1 from %s", ui_path)
        else:
            logger.error("UI RC1 not found, using fallback")
            # 移除 web_view，使用降级 UI
            layout.removeWidget(self.web_view)
            self.web_view.deleteLater()
            self._setup_fallback_ui(layout)
            return

        # 连接桥接信号到容器
        self._connect_bridge_signals()

        # 连接容器信号到 UI 更新
        self._connect_container_signals()

        # 状态定时器
        self._setup_timers()

        # 当前模式
        self.current_mode = "chat"

    def _get_ui_path(self) -> Optional[Path]:
        """获取 UI RC1 的 index.html 路径"""
        candidates = [
            Path("ui_runtime/xixi_ui_rc1_integrated/index.html"),
            Path("supplements/ui_docs/xixi_ui_rc1/index.html"),
            Path(os.getcwd()) / "supplements" / "ui_docs" / "xixi_ui_rc1" / "index.html",
            Path(sys.argv[0]).parent / "supplements" / "ui_docs" / "xixi_ui_rc1" / "index.html",
        ]
        for candidate in candidates:
            if candidate.is_file():
                return candidate.resolve()
        return None

    def _setup_fallback_ui(self, layout) -> None:
        """降级 UI：当 QWebEngine 不可用时使用"""
        try:
            from ui.chat_panel import ChatPanel
            from ui.app_library import AppLibrary
        except Exception as e:
            logger.warning("Failed to import fallback UI components: %s", e)
            ChatPanel = None
            AppLibrary = None

        self.status_label = QLabel("[降级模式] QWebEngine 未安装 | 模型: " +
            (self.container.llm.config.model if self.container else "unknown"))
        self.status_label.setStyleSheet("color: rgba(255,255,255,0.6); background: transparent;")
        layout.addWidget(self.status_label)

        if ChatPanel:
            self.chat_panel = ChatPanel()
            layout.addWidget(self.chat_panel)
        else:
            self.chat_panel = QTextEdit()
            self.chat_panel.setReadOnly(True)
            self.chat_panel.setStyleSheet("""
                QTextEdit {
                    background: rgba(0, 0, 0, 0.3);
                    color: white;
                    border-radius: 8px;
                    border: none;
                    padding: 8px;
                }
            """)
            layout.addWidget(self.chat_panel)

        input_layout = QHBoxLayout()
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("和西西说点什么...")
        self.input_field.setStyleSheet("""
            QLineEdit {
                background: rgba(0, 0, 0, 0.3);
                color: white;
                border-radius: 8px;
                border: 1px solid rgba(255,255,255,0.1);
                padding: 8px 12px;
            }
        """)
        self.input_field.returnPressed.connect(self._on_fallback_input)
        input_layout.addWidget(self.input_field)

        send_btn = QPushButton("发送")
        send_btn.setStyleSheet("""
            QPushButton {
                background: rgba(70, 130, 180, 0.8);
                color: white;
                border-radius: 8px;
                padding: 8px 16px;
                border: none;
            }
            QPushButton:hover {
                background: rgba(70, 130, 180, 1.0);
            }
        """)
        send_btn.clicked.connect(self._on_fallback_input)
        input_layout.addWidget(send_btn)

        stop_btn = QPushButton("停止")
        stop_btn.setStyleSheet("""
            QPushButton {
                background: rgba(180, 70, 70, 0.8);
                color: white;
                border-radius: 8px;
                padding: 8px 16px;
                border: none;
            }
            QPushButton:hover {
                background: rgba(180, 70, 70, 1.0);
            }
        """)
        stop_btn.clicked.connect(self._on_fallback_stop)
        input_layout.addWidget(stop_btn)

        layout.addLayout(input_layout)

    def _setup_tray(self):
        """设置系统托盘"""
        self.tray = None
        try:
            from host.system_tray import TrayManager
            self.tray = TrayManager(QApplication.instance(), self)
            self.tray.sig_show.connect(self.show)
            self.tray.sig_hide.connect(self.hide)
            self.tray.sig_exit.connect(QApplication.instance().quit)
            self.tray.show()
        except Exception as e:
            logger.warning("Failed to create system tray: %s", e)

    def _connect_bridge_signals(self) -> None:
        """连接 WebBridge 信号到容器"""
        self.bridge.sig_user_input.connect(self._on_bridge_user_input)
        self.bridge.sig_user_interrupt.connect(self._on_bridge_user_interrupt)
        self.bridge.sig_permission_response.connect(self._on_bridge_permission_response)
        self.bridge.sig_mode_change.connect(self._on_bridge_mode_change)
        self.bridge.sig_ready.connect(self._on_bridge_ready)

    def _connect_container_signals(self) -> None:
        """连接容器信号到 Web UI 更新"""
        if not self.container:
            return
        self.container.sig_stream_start.connect(self._on_stream_start)
        self.container.sig_stream_delta.connect(self._on_stream_delta)
        self.container.sig_stream_complete.connect(self._on_stream_complete)
        self.container.sig_stream_interrupted.connect(self._on_stream_interrupted)
        self.container.sig_permission_request.connect(self._on_permission_request)
        self.container.sig_system_error.connect(self._on_system_error)
        self.container.sig_ui_mode_set.connect(self._on_ui_mode_set)
        self.container.sig_model_status.connect(self._on_model_status)

    def _setup_timers(self) -> None:
        self.status_timer = QTimer(self)
        self.status_timer.timeout.connect(self._update_status)
        self.status_timer.start(5000)

    # ── 鼠标事件：拖动窗口 ──

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            # 检查是否点击在标题栏区域（y < 40）
            if event.pos().y() < 40:
                self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                self._is_dragging = True
                event.accept()
            else:
                # 点击在内容区域，取消贴边隐藏
                if self._hidden_on_edge:
                    self._restore_from_edge()
                event.ignore()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._is_dragging and self._drag_pos is not None:
            new_pos = event.globalPosition().toPoint() - self._drag_pos
            self.move(new_pos)
            # 拖动时恢复
            if self._hidden_on_edge:
                self._hidden_on_edge = False
            event.accept()
        else:
            event.ignore()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._is_dragging = False
            self._drag_pos = None
            event.accept()

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        """双击标题栏最大化/还原"""
        if event.pos().y() < 40:
            if self.isMaximized():
                self.showNormal()
            else:
                self.showMaximized()
            event.accept()
        else:
            event.ignore()

    # ── 贴边隐藏 ──

    def _check_edge_hide(self):
        """检查是否需要贴边隐藏"""
        if not self._edge_hide_enabled or self._is_dragging:
            return

        screen = QApplication.primaryScreen().geometry()
        pos = self.pos()
        size = self.size()

        # 左边缘
        if pos.x() <= -size.width() + 10:
            return  # 已经隐藏
        if pos.x() < 5:
            self._hide_to_edge("left")
            return

        # 右边缘
        if pos.x() >= screen.width() - 5:
            self._hide_to_edge("right")
            return

    def _hide_to_edge(self, edge: str):
        """贴边隐藏"""
        if self._hidden_on_edge:
            return

        screen = QApplication.primaryScreen().geometry()
        size = self.size()

        if edge == "left":
            self.move(-size.width() + 10, self.pos().y())
        elif edge == "right":
            self.move(screen.width() - 10, self.pos().y())

        self._hidden_on_edge = True
        logger.debug("Window hidden to %s edge", edge)

    def _restore_from_edge(self):
        """从贴边隐藏恢复"""
        if not self._hidden_on_edge:
            return

        screen = QApplication.primaryScreen().geometry()
        size = self.size()
        pos = self.pos()

        if pos.x() < 0:
            # 从左边恢复
            self.move(20, pos.y())
        else:
            # 从右边恢复
            self.move(screen.width() - size.width() - 20, pos.y())

        self._hidden_on_edge = False
        logger.debug("Window restored from edge")

    # ── 键盘事件 ──

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape:
            # ESC 最小化到托盘，不退出
            self.hide()
        else:
            super().keyPressEvent(event)

    # ── WebBridge 处理槽 ──

    def _on_bridge_user_input(self, text: str, mode: str) -> None:
        """JavaScript 发送的用户输入"""
        if not self.container:
            return
        session_id = self.container.get_current_session_id() or f"ses_{__import__('uuid').uuid4().hex[:8]}"
        trace_id = f"trc_{__import__('uuid').uuid4().hex[:8]}"
        self.container._on_user_input(session_id, {"text": text, "mode": mode}, trace_id)

    def _on_bridge_user_interrupt(self) -> None:
        """JavaScript 发送的打断"""
        if not self.container:
            return
        session_id = self.container.get_current_session_id() or "unknown"
        trace_id = self.container.get_current_trace_id() or f"trc_{__import__('uuid').uuid4().hex[:8]}"
        self.container._on_user_interrupt(session_id, {"reason": "user_clicked_stop"}, trace_id)

    def _on_bridge_permission_response(self, perm_id: str, decision: str) -> None:
        """JavaScript 发送的权限响应"""
        if not self.container:
            return
        session_id = self.container.get_current_session_id() or "unknown"
        trace_id = self.container.get_current_trace_id() or f"trc_{__import__('uuid').uuid4().hex[:8]}"
        self.container._on_permission_response(session_id, {
            "permission_id": perm_id,
            "decision": decision,
        }, trace_id)

    def _on_bridge_mode_change(self, mode: str) -> None:
        """JavaScript 切换模式"""
        self.current_mode = mode
        logger.info("UI mode changed to: %s", mode)

    def _on_bridge_ready(self) -> None:
        """JavaScript 报告就绪"""
        logger.info("UI RC1 reports ready")
        self._send_to_js("session.ready", {
            "status": "ready",
            "protocol": "xixi/1.0",
            "container_version": "0.1.0",
            "identity_id": "xixi-main",
        })

    # ── 容器信号 -> JavaScript ──

    def _send_to_js(self, event_type: str, data: Dict) -> None:
        """通过 runJavaScript 发送事件到 JavaScript"""
        if not WEBENGINE_AVAILABLE or not hasattr(self, 'web_view'):
            return

        payload = json.dumps(data, ensure_ascii=False)
        js_code = f"window.xixiOnEvent && window.xixiOnEvent('{event_type}', {payload});"
        self.web_view.page().runJavaScript(js_code)

    def _on_stream_start(self, session_id: str, trace_id: str) -> None:
        self._fallback_reply = ""
        self._send_to_js("assistant.stream.start", {"trace_id": trace_id})

    def _on_stream_delta(self, session_id: str, trace_id: str, text: str) -> None:
        """流式分块 -> JavaScript"""
        self._fallback_reply = getattr(self, "_fallback_reply", "") + text
        self._send_to_js("assistant.stream.delta", {
            "trace_id": trace_id,
            "delta": text,
        })

    def _on_stream_complete(self, session_id: str, trace_id: str, metadata: dict) -> None:
        if hasattr(self, "chat_panel") and getattr(self, "_fallback_reply", ""):
            if hasattr(self.chat_panel, "append"):
                self.chat_panel.append("西西", self._fallback_reply)
            else:
                self.chat_panel.append(f"西西: {self._fallback_reply}\n")
        self._fallback_reply = ""
        self._send_to_js("assistant.stream.complete", {
            "trace_id": trace_id,
            "metadata": metadata,
        })

    def _on_stream_interrupted(self, session_id: str, trace_id: str, payload: dict) -> None:
        self._send_to_js("assistant.stream.interrupted", payload)

    def _on_permission_request(self, session_id: str, trace_id: str, payload: dict) -> None:
        """权限弹窗 -> JavaScript"""
        self._send_to_js("permission.request", payload)

    def _on_system_error(self, session_id: str, payload: dict) -> None:
        self._send_to_js("system.error", payload)

    def _on_ui_mode_set(self, session_id: str, mode: str) -> None:
        self._send_to_js("ui.mode.set", {"mode": mode})

    def _on_model_status(self, session_id: str, payload: dict) -> None:
        self._send_to_js("model.status", payload)

    # ── 降级 UI 处理 ──

    def _on_fallback_input(self) -> None:
        """降级模式的输入处理"""
        if not hasattr(self, 'input_field'):
            return
        text = self.input_field.text().strip()
        if not text or not self.container:
            return
        self.input_field.clear()
        if hasattr(self.chat_panel, "append"):
            self.chat_panel.append("你", text)
        else:
            self.chat_panel.append(f"你: {text}\n")
        session_id = self.container.get_current_session_id() or f"ses_{__import__('uuid').uuid4().hex[:8]}"
        trace_id = f"trc_{__import__('uuid').uuid4().hex[:8]}"
        self.container._on_user_input(session_id, {"text": text, "mode": "text"}, trace_id)

    def _on_fallback_stop(self) -> None:
        """降级模式的停止"""
        if not self.container:
            return
        session_id = self.container.get_current_session_id() or "unknown"
        trace_id = self.container.get_current_trace_id() or f"trc_{__import__('uuid').uuid4().hex[:8]}"
        self.container._on_user_interrupt(session_id, {"reason": "user_clicked_stop"}, trace_id)

    def _update_status(self) -> None:
        """更新状态栏"""
        if not self.container:
            return
        stats = self.container.system_monitor.get_stats()
        status = f"CPU: {stats.get('cpu_percent', 0):.1f}% | 内存: {stats.get('memory_percent', 0):.1f}%"
        if self.container.is_generating():
            status += " | 生成中..."
        if hasattr(self, 'status_label'):
            self.status_label.setText(status)

    def closeEvent(self, event) -> None:
        """关闭事件 - 最小化到托盘而不是退出"""
        if self.tray and self.tray.isVisible():
            self.hide()
            event.ignore()
        else:
            if self.container:
                self.container.stop()
            event.accept()
