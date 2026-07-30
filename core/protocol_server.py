"""
xixi/1.0 Protocol Server
WebSocket + HTTP Health Check
支持 22 种消息类型、Envelope 校验、序列号管理、握手规则
"""
from __future__ import annotations

import asyncio
import json
import uuid
import logging
from datetime import datetime, timezone
from typing import Callable, Dict, Optional, Any, Set
from dataclasses import dataclass, field

try:
    from aiohttp import web, WSMsgType
except ImportError:
    class _MissingWeb:
        def __getattr__(self, name):
            raise RuntimeError("aiohttp 尚未安装，请先运行 scripts/install.bat")

    class _MissingWSMsgType:
        TEXT = BINARY = ERROR = CLOSE = object()

    web = _MissingWeb()
    WSMsgType = _MissingWSMsgType()

logger = logging.getLogger("xixi.protocol")


# ── 错误码常量 ──
class ErrorCode:
    PROTOCOL_VERSION_UNSUPPORTED = "XIXI_PROTOCOL_VERSION_UNSUPPORTED"
    MESSAGE_INVALID = "XIXI_MESSAGE_INVALID"
    MESSAGE_TOO_LARGE = "XIXI_MESSAGE_TOO_LARGE"
    SEQUENCE_OUT_OF_ORDER = "XIXI_SEQUENCE_OUT_OF_ORDER"
    UNSUPPORTED_MESSAGE_TYPE = "XIXI_UNSUPPORTED_MESSAGE_TYPE"
    SESSION_NOT_READY = "XIXI_SESSION_NOT_READY"
    SOUL_OUTPUT_INVALID = "XIXI_SOUL_OUTPUT_INVALID"
    MODEL_OFFLINE = "XIXI_MODEL_OFFLINE"
    MODEL_TIMEOUT = "XIXI_MODEL_TIMEOUT"
    STREAM_INTERRUPTED = "XIXI_STREAM_INTERRUPTED"
    MEMORY_WRITE_FAILED = "XIXI_MEMORY_WRITE_FAILED"
    MEMORY_SCOPE_AMBIGUOUS = "XIXI_MEMORY_SCOPE_AMBIGUOUS"
    PERMISSION_REQUIRED = "XIXI_PERMISSION_REQUIRED"
    PERMISSION_DENIED = "XIXI_PERMISSION_DENIED"
    PERMISSION_EXPIRED = "XIXI_PERMISSION_EXPIRED"
    TOOL_EXECUTION_FAILED = "XIXI_TOOL_EXECUTION_FAILED"
    TOOL_PARTIAL_RESULT = "XIXI_TOOL_PARTIAL_RESULT"
    BODY_OFFLINE = "XIXI_BODY_OFFLINE"
    BODY_ASSET_MISSING = "XIXI_BODY_ASSET_MISSING"
    TASK_CONFLICT = "XIXI_TASK_CONFLICT"
    INTERNAL_ERROR = "XIXI_INTERNAL_ERROR"


# ── 消息类型常量 ──
class MsgType:
    # 客户端 -> 服务器
    SESSION_HELLO = "session.hello"
    USER_INPUT = "user.input"
    USER_INTERRUPT = "user.interrupt"
    PERMISSION_RESPONSE = "permission.response"

    # 服务器 -> 客户端
    SESSION_READY = "session.ready"
    ASSISTANT_STREAM_START = "assistant.stream.start"
    ASSISTANT_STREAM_DELTA = "assistant.stream.delta"
    ASSISTANT_STREAM_COMPLETE = "assistant.stream.complete"
    ASSISTANT_STREAM_INTERRUPTED = "assistant.stream.interrupted"
    PERMISSION_REQUEST = "permission.request"
    UI_MODE_SET = "ui.mode.set"
    MODEL_STATUS = "model.status"
    TASK_STATUS = "task.status"
    SYSTEM_ERROR = "system.error"

    # 内部消息（不通过 WebSocket 发送给 UI）
    SOUL_TURN_REQUEST = "soul.turn.request"
    SOUL_TURN_OUTPUT = "soul.turn.output"
    MEMORY_APPLY_REQUEST = "memory.apply.request"
    MEMORY_APPLY_RESULT = "memory.apply.result"
    TOOL_EXECUTE_REQUEST = "tool.execute.request"
    TOOL_EXECUTE_RESULT = "tool.execute.result"
    BODY_INTENT_SET = "body.intent.set"
    BODY_STATUS = "body.status"


# 客户端可发送的消息类型
CLIENT_MESSAGE_TYPES: Set[str] = {
    MsgType.SESSION_HELLO,
    MsgType.USER_INPUT,
    MsgType.USER_INTERRUPT,
    MsgType.PERMISSION_RESPONSE,
}

# 服务器可发送给客户端的消息类型
SERVER_TO_UI_TYPES: Set[str] = {
    MsgType.SESSION_READY,
    MsgType.ASSISTANT_STREAM_START,
    MsgType.ASSISTANT_STREAM_DELTA,
    MsgType.ASSISTANT_STREAM_COMPLETE,
    MsgType.ASSISTANT_STREAM_INTERRUPTED,
    MsgType.PERMISSION_REQUEST,
    MsgType.UI_MODE_SET,
    MsgType.MODEL_STATUS,
    MsgType.TASK_STATUS,
    MsgType.SYSTEM_ERROR,
}


@dataclass
class SessionState:
    """WebSocket 会话状态"""
    session_id: str
    ws: web.WebSocketResponse
    sequence_expected: int = 0
    handshake_complete: bool = False
    client_info: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_activity: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def bump_sequence(self, seq: int) -> bool:
        """校验并递增序列号。返回 True 表示合法，False 表示乱序。"""
        if seq != self.sequence_expected:
            return False
        self.sequence_expected += 1
        self.last_activity = datetime.now(timezone.utc)
        return True


class XixiEnvelope:
    """xixi/1.0 消息信封工具"""

    PROTOCOL = "xixi/1.0"
    MAX_PAYLOAD_SIZE = 1024 * 1024  # 1 MiB

    @classmethod
    def create(
        cls,
        msg_type: str,
        source: str,
        target: str,
        session_id: str,
        trace_id: str,
        sequence: int,
        payload: Dict[str, Any],
        reply_to: Optional[str] = None,
    ) -> Dict[str, Any]:
        """创建标准信封消息"""
        envelope = {
            "protocol": cls.PROTOCOL,
            "id": f"msg_{uuid.uuid4().hex[:12]}",
            "type": msg_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "session_id": session_id,
            "trace_id": trace_id,
            "source": source,
            "target": target,
            "sequence": sequence,
            "payload": payload,
        }
        if reply_to:
            envelope["reply_to"] = reply_to
        return envelope

    @classmethod
    def validate(cls, data: Dict[str, Any]) -> tuple[bool, Optional[str], Optional[str]]:
        """
        校验信封格式。
        返回: (is_valid, error_code, error_message)
        """
        # 基础字段存在性
        required = ["protocol", "id", "type", "timestamp", "session_id", 
                    "trace_id", "source", "target", "sequence", "payload"]
        missing = [f for f in required if f not in data]
        if missing:
            return False, ErrorCode.MESSAGE_INVALID, f"Missing fields: {missing}"

        # 协议版本
        if data.get("protocol") != cls.PROTOCOL:
            return False, ErrorCode.PROTOCOL_VERSION_UNSUPPORTED,                 f"Unsupported protocol: {data.get('protocol')}"

        # ID 格式
        msg_id = data.get("id", "")
        if not msg_id.startswith("msg_") or len(msg_id) < 12:
            return False, ErrorCode.MESSAGE_INVALID, "Invalid message id format"

        # 类型合法性
        msg_type = data.get("type", "")
        # 允许所有已知类型（包括内部类型，用于完整性校验）
        all_known_types = CLIENT_MESSAGE_TYPES | SERVER_TO_UI_TYPES | {
            MsgType.SOUL_TURN_REQUEST, MsgType.SOUL_TURN_OUTPUT,
            MsgType.MEMORY_APPLY_REQUEST, MsgType.MEMORY_APPLY_RESULT,
            MsgType.TOOL_EXECUTE_REQUEST, MsgType.TOOL_EXECUTE_RESULT,
            MsgType.BODY_INTENT_SET, MsgType.BODY_STATUS,
        }
        if msg_type not in all_known_types:
            return False, ErrorCode.UNSUPPORTED_MESSAGE_TYPE,                 f"Unknown message type: {msg_type}"

        # source/target 合法性
        valid_entities = {"ui", "container", "soul", "body", "tool", "model", "system"}
        if data.get("source") not in valid_entities:
            return False, ErrorCode.MESSAGE_INVALID, f"Invalid source: {data.get('source')}"
        if data.get("target") not in valid_entities:
            return False, ErrorCode.MESSAGE_INVALID, f"Invalid target: {data.get('target')}"

        # sequence 非负整数
        seq = data.get("sequence")
        if not isinstance(seq, int) or seq < 0:
            return False, ErrorCode.MESSAGE_INVALID, "Sequence must be non-negative integer"

        # payload 大小
        payload_str = json.dumps(data.get("payload", {}))
        if len(payload_str.encode("utf-8")) > cls.MAX_PAYLOAD_SIZE:
            return False, ErrorCode.MESSAGE_TOO_LARGE, "Payload exceeds 1 MiB"

        return True, None, None

    @classmethod
    def create_error(
        cls,
        session_id: str,
        trace_id: str,
        sequence: int,
        error_code: str,
        error_message: str,
        reply_to: Optional[str] = None,
    ) -> Dict[str, Any]:
        """创建错误消息"""
        return cls.create(
            msg_type=MsgType.SYSTEM_ERROR,
            source="container",
            target="ui",
            session_id=session_id,
            trace_id=trace_id,
            sequence=sequence,
            payload={
                "code": error_code,
                "message": error_message,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
            reply_to=reply_to,
        )


class ProtocolServer:
    """
    xixi/1.0 协议服务器

    提供:
    - HTTP GET /v1/health 健康检查
    - WebSocket ws://host:port/v1/ws 全双工通信
    - Envelope 封装/解析/校验
    - 序列号管理
    - 握手规则 (session.hello -> session.ready)
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 17861,
        container_version: str = "0.1.0",
        identity_id: str = "xixi-main",
        on_user_input: Optional[Callable[[str, Dict, str], None]] = None,
        on_user_interrupt: Optional[Callable[[str, Dict, str], None]] = None,
        on_permission_response: Optional[Callable[[str, Dict, str], None]] = None,
        on_session_hello: Optional[Callable[[str, Dict], None]] = None,
    ):
        self.host = host
        self.port = port
        self.container_version = container_version
        self.identity_id = identity_id

        # 业务回调（由外部注入，通常是 Container 实例的方法）
        self.on_user_input = on_user_input
        self.on_user_interrupt = on_user_interrupt
        self.on_permission_response = on_permission_response
        self.on_session_hello = on_session_hello

        # 会话管理
        self.sessions: Dict[str, SessionState] = {}

        # aiohttp 应用
        self.app = web.Application()
        self._setup_routes()

        # 运行状态
        self._runner: Optional[web.AppRunner] = None
        self._site: Optional[web.TCPSite] = None
        self._task: Optional[asyncio.Task] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def _setup_routes(self) -> None:
        self.app.router.add_get("/v1/health", self._health_handler)
        self.app.router.add_get("/v1/ws", self._websocket_handler)

    # ── HTTP 处理器 ──

    async def _health_handler(self, request: web.Request) -> web.Response:
        """GET /v1/health"""
        return web.json_response({
            "status": "ready",
            "protocol": "xixi/1.0",
            "container_version": self.container_version,
            "identity_id": self.identity_id,
        })

    # ── WebSocket 处理器 ──

    async def _websocket_handler(self, request: web.Request) -> web.WebSocketResponse:
        """WebSocket 连接处理"""
        ws = web.WebSocketResponse(heartbeat=20.0, autoping=True)
        await ws.prepare(request)

        session_id: Optional[str] = None
        logger.info("WebSocket client connected from %s", request.remote)

        try:
            async for msg in ws:
                if msg.type == WSMsgType.TEXT:
                    await self._handle_text_message(ws, msg.data)
                elif msg.type == WSMsgType.BINARY:
                    # 二进制帧：拒绝（协议规定只传文本帧）
                    await ws.send_json(XixiEnvelope.create_error(
                        session_id=session_id or "unknown",
                        trace_id=f"trc_{uuid.uuid4().hex[:8]}",
                        sequence=0,
                        error_code=ErrorCode.MESSAGE_INVALID,
                        error_message="Binary frames not supported. Use UTF-8 text frames.",
                    ))
                elif msg.type == WSMsgType.ERROR:
                    logger.error("WebSocket error: %s", ws.exception())
                    break
                elif msg.type == WSMsgType.CLOSE:
                    logger.info("WebSocket client closed connection")
                    break
        except Exception as e:
            logger.exception("WebSocket handler error: %s", e)
        finally:
            # 清理会话
            if session_id and session_id in self.sessions:
                del self.sessions[session_id]
                logger.info("Session %s removed", session_id)

            if not ws.closed:
                await ws.close()

        return ws

    async def _handle_text_message(self, ws: web.WebSocketResponse, text: str) -> None:
        """处理文本帧消息"""
        # 1. 解析 JSON
        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            await ws.send_json(XixiEnvelope.create_error(
                session_id="unknown",
                trace_id=f"trc_{uuid.uuid4().hex[:8]}",
                sequence=0,
                error_code=ErrorCode.MESSAGE_INVALID,
                error_message=f"Invalid JSON: {e}",
            ))
            return

        # 2. 校验信封
        is_valid, err_code, err_msg = XixiEnvelope.validate(data)
        if not is_valid:
            await ws.send_json(XixiEnvelope.create_error(
                session_id=data.get("session_id", "unknown"),
                trace_id=data.get("trace_id", f"trc_{uuid.uuid4().hex[:8]}"),
                sequence=data.get("sequence", 0),
                error_code=err_code,
                error_message=err_msg,
                reply_to=data.get("id"),
            ))
            return

        msg_type = data["type"]
        session_id = data["session_id"]
        trace_id = data["trace_id"]
        sequence = data["sequence"]
        payload = data.get("payload", {})

        # 3. 会话管理
        if msg_type == MsgType.SESSION_HELLO:
            # 创建新会话
            if session_id in self.sessions:
                # 重连：恢复已有会话（但需重新握手）
                old_session = self.sessions[session_id]
                old_session.ws = ws
                old_session.handshake_complete = False
                old_session.sequence_expected = sequence + 1
                logger.info("Session %s reconnected", session_id)
            else:
                self.sessions[session_id] = SessionState(
                    session_id=session_id,
                    ws=ws,
                    sequence_expected=sequence + 1,
                )
                logger.info("Session %s created", session_id)

            # 发送 session.ready
            await self._send_to_session(session_id, MsgType.SESSION_READY, payload={
                "status": "ready",
                "protocol": "xixi/1.0",
                "container_version": self.container_version,
                "identity_id": self.identity_id,
                "session_id": session_id,
            })
            self.sessions[session_id].handshake_complete = True

            # 回调
            if self.on_session_hello:
                try:
                    self.on_session_hello(session_id, payload)
                except Exception as e:
                    logger.exception("on_session_hello callback error: %s", e)
            return

        # 4. 握手检查：非 hello 消息必须先完成握手
        if session_id not in self.sessions or not self.sessions[session_id].handshake_complete:
            await ws.send_json(XixiEnvelope.create_error(
                session_id=session_id,
                trace_id=trace_id,
                sequence=sequence,
                error_code=ErrorCode.SESSION_NOT_READY,
                error_message="Session not ready. Send session.hello first.",
                reply_to=data.get("id"),
            ))
            return

        session = self.sessions[session_id]
        # 更新 ws 引用（防止重连后对象不一致）
        session.ws = ws

        # 5. 序列号校验
        if not session.bump_sequence(sequence):
            await self._send_to_session(session_id, MsgType.SYSTEM_ERROR, payload={
                "code": ErrorCode.SEQUENCE_OUT_OF_ORDER,
                "message": f"Expected sequence {session.sequence_expected - 1}, got {sequence}",
                "expected": session.sequence_expected - 1,
                "received": sequence,
            })
            return

        # 6. 消息路由
        if msg_type == MsgType.USER_INPUT:
            if self.on_user_input:
                try:
                    self.on_user_input(session_id, payload, trace_id)
                except Exception as e:
                    logger.exception("on_user_input error: %s", e)
                    await self._send_error(session_id, trace_id, ErrorCode.INTERNAL_ERROR, str(e))

        elif msg_type == MsgType.USER_INTERRUPT:
            if self.on_user_interrupt:
                try:
                    self.on_user_interrupt(session_id, payload, trace_id)
                except Exception as e:
                    logger.exception("on_user_interrupt error: %s", e)
                    await self._send_error(session_id, trace_id, ErrorCode.INTERNAL_ERROR, str(e))

        elif msg_type == MsgType.PERMISSION_RESPONSE:
            if self.on_permission_response:
                try:
                    self.on_permission_response(session_id, payload, trace_id)
                except Exception as e:
                    logger.exception("on_permission_response error: %s", e)
                    await self._send_error(session_id, trace_id, ErrorCode.INTERNAL_ERROR, str(e))

        else:
            # 客户端发送了不支持的消息类型
            await self._send_to_session(session_id, MsgType.SYSTEM_ERROR, payload={
                "code": ErrorCode.UNSUPPORTED_MESSAGE_TYPE,
                "message": f"Message type '{msg_type}' not accepted from client",
            }, trace_id=trace_id)

    # ── 发送消息给 UI ──

    async def _send_to_session(
        self,
        session_id: str,
        msg_type: str,
        payload: Dict[str, Any],
        trace_id: Optional[str] = None,
        reply_to: Optional[str] = None,
    ) -> bool:
        """发送消息到指定会话的 UI 客户端"""
        if session_id not in self.sessions:
            logger.warning("Session %s not found, cannot send %s", session_id, msg_type)
            return False

        session = self.sessions[session_id]
        if session.ws.closed:
            logger.warning("WebSocket for session %s is closed", session_id)
            return False

        trace_id = trace_id or f"trc_{uuid.uuid4().hex[:8]}"
        envelope = XixiEnvelope.create(
            msg_type=msg_type,
            source="container",
            target="ui",
            session_id=session_id,
            trace_id=trace_id,
            sequence=session.sequence_expected,  # 服务器使用会话的序列号
            payload=payload,
            reply_to=reply_to,
        )
        # 服务器发送的消息不占用客户端序列号，但使用会话序列号保持可读性
        # 实际规范中 sequence 是单调递增的，服务器端独立维护

        try:
            await session.ws.send_json(envelope)
            session.last_activity = datetime.now(timezone.utc)
            return True
        except Exception as e:
            logger.error("Failed to send %s to session %s: %s", msg_type, session_id, e)
            return False

    async def _send_error(
        self,
        session_id: str,
        trace_id: str,
        error_code: str,
        error_message: str,
    ) -> bool:
        """发送错误消息"""
        return await self._send_to_session(
            session_id, MsgType.SYSTEM_ERROR,
            payload={"code": error_code, "message": error_message},
            trace_id=trace_id,
        )

    # ── 公共 API：供 Container 调用 ──

    def send_to_ui(
        self,
        session_id: str,
        msg_type: str,
        payload: Dict[str, Any],
        trace_id: Optional[str] = None,
    ) -> bool:
        """
        同步接口：供非 asyncio 线程调用。
        将消息放入事件循环执行。
        """
        if self._loop is None or self._loop.is_closed():
            logger.error("Protocol server loop not running")
            return False

        future = asyncio.run_coroutine_threadsafe(
            self._send_to_session(session_id, msg_type, payload, trace_id),
            self._loop,
        )
        try:
            return future.result(timeout=5.0)
        except Exception as e:
            logger.error("send_to_ui failed: %s", e)
            return False

    def broadcast_to_ui(self, msg_type: str, payload: Dict[str, Any]) -> None:
        """广播消息给所有已连接的 UI 客户端"""
        for session_id in list(self.sessions.keys()):
            self.send_to_ui(session_id, msg_type, payload)

    def get_active_sessions(self) -> list[str]:
        """获取所有活跃会话 ID"""
        return [
            sid for sid, s in self.sessions.items()
            if not s.ws.closed and s.handshake_complete
        ]

    # ── 生命周期 ──

    async def start(self) -> None:
        """启动服务器（必须在 asyncio 事件循环中调用）"""
        self._loop = asyncio.get_running_loop()
        self._runner = web.AppRunner(self.app)
        await self._runner.setup()
        self._site = web.TCPSite(self._runner, self.host, self.port)
        await self._site.start()
        logger.info("xixi/1.0 Protocol Server started on http://%s:%d", self.host, self.port)

    async def stop(self) -> None:
        """停止服务器"""
        # 关闭所有 WebSocket 连接
        for session in list(self.sessions.values()):
            if not session.ws.closed:
                await session.ws.close()
        self.sessions.clear()

        if self._site:
            await self._site.stop()
        if self._runner:
            await self._runner.cleanup()
        logger.info("xixi/1.0 Protocol Server stopped")

    def run_in_thread(self) -> None:
        """在独立线程中启动事件循环和服务器"""
        def _run():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self.start())
                loop.run_forever()
            except Exception as e:
                logger.exception("Protocol server thread error: %s", e)
            finally:
                loop.run_until_complete(self.stop())
                loop.close()

        import threading
        self._thread = threading.Thread(target=_run, daemon=True, name="XixiProtocolServer")
        self._thread.start()

    def shutdown(self) -> None:
        """请求关闭服务器"""
        if self._loop and not self._loop.is_closed():
            future = asyncio.run_coroutine_threadsafe(self.stop(), self._loop)
            try:
                future.result(timeout=5.0)
            except Exception as exc:
                logger.warning("Protocol shutdown did not finish cleanly: %s", exc)
            self._loop.call_soon_threadsafe(self._loop.stop)
