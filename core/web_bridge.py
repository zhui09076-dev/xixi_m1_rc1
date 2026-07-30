"""
Web Bridge - QWebChannel 桥接对象
供 UI RC1 (JavaScript) 调用 Python 后端
"""
from __future__ import annotations

import json
import logging
from typing import Any, Callable, Dict, List, Optional

from PyQt6.QtCore import QObject, pyqtSlot, pyqtSignal

logger = logging.getLogger("xixi.web_bridge")


class WebBridge(QObject):
    """
    QWebChannel 桥接对象

    暴露给 JavaScript 的方法:
    - sendMessage(type, payload) -> 发送消息到容器
    - requestState() -> 请求当前状态
    - setMode(mode) -> 切换 UI 模式
    - stopGeneration() -> 停止生成
    - respondPermission(permissionId, decision) -> 响应权限请求
    """

    # 信号：从 JavaScript 到 Python
    sig_user_input = pyqtSignal(str, str)           # text, mode
    sig_user_interrupt = pyqtSignal()               # 打断
    sig_permission_response = pyqtSignal(str, str)  # permission_id, decision
    sig_mode_change = pyqtSignal(str)               # mode
    sig_request_state = pyqtSignal()                # 请求状态
    sig_ready = pyqtSignal()                        # UI 就绪

    def __init__(self, container=None):
        super().__init__()
        self.container = container
        self._session_id: Optional[str] = None
        self._sequence: int = 0

    @pyqtSlot(str, result=str)
    def getSessionId(self) -> str:
        """获取当前会话 ID"""
        if self._session_id is None:
            import uuid
            self._session_id = f"ses_{uuid.uuid4().hex[:8]}"
        return self._session_id

    @pyqtSlot(str, str)
    def sendMessage(self, msg_type: str, payload_json: str) -> None:
        """JavaScript 调用：发送消息"""
        try:
            payload = json.loads(payload_json)
            logger.debug("JS -> Py: %s", msg_type)

            if msg_type == "session.hello":
                self.sig_ready.emit()
            elif msg_type == "user.input":
                text = payload.get("text", "")
                mode = payload.get("mode", "text")
                self.sig_user_input.emit(text, mode)
            elif msg_type == "user.interrupt":
                self.sig_user_interrupt.emit()
            elif msg_type == "permission.response":
                perm_id = payload.get("permission_id", "")
                decision = payload.get("decision", "deny")
                self.sig_permission_response.emit(perm_id, decision)
            elif msg_type == "ui.mode.set":
                mode = payload.get("mode", "chat")
                self.sig_mode_change.emit(mode)
            elif msg_type == "state.request":
                self.sig_request_state.emit()
        except Exception as e:
            logger.error("WebBridge sendMessage error: %s", e)

    @pyqtSlot(str, str)
    def sendEnvelope(self, msg_type: str, payload_json: str) -> None:
        """发送标准 Envelope 格式消息"""
        self.sendMessage(msg_type, payload_json)

    @pyqtSlot(result=str)
    def getIdentity(self) -> str:
        """获取身份信息"""
        return json.dumps({
            "identity_id": "xixi-main",
            "display_name": "西西",
            "official": True,
        })

    @pyqtSlot(result=str)
    def getModelStatus(self) -> str:
        """获取模型状态"""
        if self.container and self.container.llm:
            return json.dumps({
                "model": self.container.llm.config.model,
                "status": "ready",
                "soul_loaded": self.container.soul is not None,
            })
        return json.dumps({"status": "offline"})

    @pyqtSlot(result=str)
    def getMemoryStatus(self) -> str:
        """获取记忆状态"""
        if self.container and self.container.memory_mgr:
            try:
                recent = self.container.memory_mgr.get_recent_conversations(limit=5)
                return json.dumps({
                    "recent_count": len(recent),
                    "status": "active",
                })
            except Exception as e:
                return json.dumps({"status": "error", "message": str(e)})
        return json.dumps({"status": "unknown"})

    @pyqtSlot(result=str)
    def getTaskStatus(self) -> str:
        """获取任务状态"""
        return json.dumps({
            "tasks": [],
            "status": "idle",
        })

    @pyqtSlot(result=str)
    def getProjectStatus(self) -> str:
        """获取项目状态"""
        return json.dumps({
            "projects": [],
            "active_project": None,
        })

    @pyqtSlot(str, result=str)
    def getNotes(self, project_id: str) -> str:
        """获取笔记"""
        return json.dumps({"notes": []})

    @pyqtSlot(str, result=str)
    def getTodos(self, project_id: str) -> str:
        """获取待办"""
        return json.dumps({"todos": []})

    # ── Python -> JavaScript 调用 ──

    def emit_to_js(self, event_type: str, data: Dict) -> None:
        """
        从 Python 发送事件到 JavaScript。
        通过 QWebChannel 的 pyqtSignal 或 evaluateJavaScript。
        """
        # 这个方法会被 WebMainWindow 重写，通过 page().runJavaScript 调用
        pass
