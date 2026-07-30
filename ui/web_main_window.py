"""
Web Main Window - 使用 QWebEngineView 加载 UI RC1
集成 QWebChannel，实现 Python <-> JavaScript 双向通信
"""
from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from PyQt6.QtCore import Qt, QUrl, pyqtSignal, QObject, QTimer
from PyQt6.QtWidgets import (
    QMainWindow, QVBoxLayout, QWidget, QApplication,
    QHBoxLayout, QPushButton, QLabel, QLineEdit, QTextEdit,
)

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
    使用 QWebEngineView 加载 UI RC1 的主窗口

    特性:
    - 加载 supplements/ui_docs/xixi_ui_rc1/index.html
    - QWebChannel 桥接 Python 和 JavaScript
    - 支持 quiet/chat/work/permission 四种模式
    - 流式回复通过 JavaScript 函数注入
    - 权限弹窗通过 JavaScript 事件触发
    - 所有数据真实来自后端，不使用模拟数据
    """

    def __init__(self, config, db, container):
        super().__init__()
        self.config = config
        self.db = db
        self.container = container

        self.setWindowTitle("西西")
        self.resize(1280, 720)

        # 桌面窗口（置底透明，人物渲染层）
        from host.window import RendererWindow
        cfg = config.to_dict() if hasattr(config, "to_dict") else config
        self.desktop_window = RendererWindow(cfg)
        self.desktop_window.show()

        # 系统托盘
        from host.system_tray import TrayManager
        self.tray = TrayManager(QApplication.instance(), self)
        self.tray.sig_show.connect(self.show)
        self.tray.sig_hide.connect(self.hide)
        self.tray.sig_exit.connect(QApplication.instance().quit)
        self.tray.show()

        # 主布局
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)

        if not WEBENGINE_AVAILABLE:
            # 降级：使用原生 Qt UI
            self._setup_fallback_ui(layout)
            return

        # ── QWebEngineView 加载 UI RC1 ──
        self.web_view = QWebEngineView()
        layout.addWidget(self.web_view)

        # QWebChannel 设置
        self.channel = QWebChannel()
        self.bridge = WebBridge(container=container)
        self.channel.registerObject("xixiBridge", self.bridge)
        self.web_view.page().setWebChannel(self.channel)

        # 加载 UI RC1
        ui_path = self._get_ui_path()
        if ui_path:
            self.web_view.load(QUrl.fromLocalFile(str(ui_path)))
            logger.info("Loading UI RC1 from %s", ui_path)
        else:
            logger.error("UI RC1 not found, using fallback")
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
        # 尝试多个可能的位置
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
        from ui.chat_panel import ChatPanel
        from ui.app_library import AppLibrary

        self.status_label = QLabel("[降级模式] QWebEngine 未安装 | 模型: " + 
                                   (self.container.llm.config.model if self.container else "unknown"))
        layout.addWidget(self.status_label)

        self.chat_panel = ChatPanel()
        layout.addWidget(self.chat_panel)

        input_layout = QHBoxLayout()
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("和西西说点什么...")
        self.input_field.returnPressed.connect(self._on_fallback_input)
        input_layout.addWidget(self.input_field)

        send_btn = QPushButton("发送")
        send_btn.clicked.connect(self._on_fallback_input)
        input_layout.addWidget(send_btn)

        stop_btn = QPushButton("停止")
        stop_btn.clicked.connect(self._on_fallback_stop)
        input_layout.addWidget(stop_btn)

        layout.addLayout(input_layout)

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

    # ── WebBridge 处理槽 ──

    def _on_bridge_user_input(self, text: str, mode: str) -> None:
        """JavaScript 发送的用户输入"""
        if not self.container:
            return
        session_id = self.container._current_session_id or f"ses_{__import__('uuid').uuid4().hex[:8]}"
        trace_id = f"trc_{__import__('uuid').uuid4().hex[:8]}"
        self.container._on_user_input(session_id, {"text": text, "mode": mode}, trace_id)

    def _on_bridge_user_interrupt(self) -> None:
        """JavaScript 发送的打断"""
        if not self.container:
            return
        session_id = self.container._current_session_id or "unknown"
        trace_id = self.container._current_trace_id or f"trc_{__import__('uuid').uuid4().hex[:8]}"
        self.container._on_user_interrupt(session_id, {"reason": "user_clicked_stop"}, trace_id)

    def _on_bridge_permission_response(self, perm_id: str, decision: str) -> None:
        """JavaScript 发送的权限响应"""
        if not self.container:
            return
        session_id = self.container._current_session_id or "unknown"
        trace_id = self.container._current_trace_id or f"trc_{__import__('uuid').uuid4().hex[:8]}"
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
        # 发送初始状态
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
            self.chat_panel.append("西西", self._fallback_reply)
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
        self.chat_panel.append("你", text)
        session_id = self.container._current_session_id or f"ses_{__import__('uuid').uuid4().hex[:8]}"
        trace_id = f"trc_{__import__('uuid').uuid4().hex[:8]}"
        self.container._on_user_input(session_id, {"text": text, "mode": "text"}, trace_id)

    def _on_fallback_stop(self) -> None:
        """降级模式的停止"""
        if not self.container:
            return
        session_id = self.container._current_session_id or "unknown"
        trace_id = self.container._current_trace_id or f"trc_{__import__('uuid').uuid4().hex[:8]}"
        self.container._on_user_interrupt(session_id, {"reason": "user_clicked_stop"}, trace_id)

    def _update_status(self) -> None:
        """更新状态栏"""
        if not self.container:
            return
        stats = self.container.system_monitor.get_stats()
        status = f"CPU: {stats.get('cpu_percent', 0):.1f}% | 内存: {stats.get('memory_percent', 0):.1f}%"
        if self.container._is_generating:
            status += " | 生成中..."
        if hasattr(self, 'status_label'):
            self.status_label.setText(status)

    def closeEvent(self, event) -> None:
        if self.container:
            self.container.stop()
        if hasattr(self, 'desktop_window'):
            self.desktop_window.close()
        event.accept()
