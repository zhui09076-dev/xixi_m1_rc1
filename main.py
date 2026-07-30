"""
西西桌面伴侣 - 主入口（最终版）
集成: ProtocolServer, Soul, LLM, Memory, Permission, Tool, Body, Task, Lifecycle
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject
from PyQt6.QtWidgets import QApplication

# 核心模块
from core.config import Config
from core.database import Database
from core.identity import IdentityManager
from core.memory import MemoryManager
from core.permission_gateway import PermissionGateway, PermissionDecision
from core.state import StateMachine, BootMode
from core.task_scheduler import TaskScheduler, TaskWeight, TaskStatus
from core.system_monitor import SystemMonitor
from core.asset_manager import AssetManager
from core.version_registry import VersionRegistry
from core.logger import setup_logging
from core.lifecycle import LifecycleManager

# 新模块
from core.protocol_server import ProtocolServer, MsgType, ErrorCode
from core.soul_loader import SoulPackage, SoulPromptBuilder, SoulRuntimeValidator, load_soul_package
from core.llm import LLMEngine, LLMConfig, StreamDelta
from core.tool_executor import ToolExecutor
from core.body_interface import BodyInterface, BodyIntent
from core.body_loader import BodyLoader

# UI
from ui.web_main_window import WebMainWindow

logger = logging.getLogger("xixi.main")


class Container(QObject):
    """西西容器 - 完整版"""

    sig_stream_start = pyqtSignal(str, str)
    sig_stream_delta = pyqtSignal(str, str, str)
    sig_stream_complete = pyqtSignal(str, str, dict)
    sig_stream_interrupted = pyqtSignal(str, str, dict)
    sig_permission_request = pyqtSignal(str, str, dict)
    sig_model_status = pyqtSignal(str, dict)
    sig_task_status = pyqtSignal(str, dict)
    sig_system_error = pyqtSignal(str, dict)
    sig_ui_mode_set = pyqtSignal(str, str)
    sig_body_intent = pyqtSignal(dict)

    def __init__(self, config: Config, db: Database):
        super().__init__()
        self.config = config
        self.db = db
        self.identity_id = "xixi-main"

        # 生命周期
        self.lifecycle = LifecycleManager()

        # 子系统
        self.identity_mgr = IdentityManager(db)
        self.memory_mgr = MemoryManager(str(db.path))
        self.permission_gw = PermissionGateway(str(db.path), authorized_paths=config.get("permissions.authorized_paths", None))
        self.state_mgr = StateMachine()
        self.task_scheduler = TaskScheduler(str(db.path))
        self.system_monitor = SystemMonitor()
        self.asset_mgr = AssetManager(config.get("assets.manifest", "assets/manifest.json"))
        self.version_reg = VersionRegistry()
        self.tool_executor = ToolExecutor(allowed_dirs=[
            os.path.expanduser("~/Documents"),
            os.path.expanduser("~/Desktop"),
            os.getcwd(),
        ])
        self.body_loader = BodyLoader(
            db, self.version_reg,
            packages_dir=config.get("body_packages_dir", "bodies"),
        )
        self.body_loader.load_all()
        self.body_interface = BodyInterface(asset_manager=self.body_loader)

        # 任务状态同步
        self.task_scheduler.on_status_change = self._on_task_status_change

        # Soul
        self.soul: Optional[SoulPackage] = None
        self.prompt_builder: Optional[SoulPromptBuilder] = None
        self.runtime_validator: Optional[SoulRuntimeValidator] = None
        self._load_soul()

        # LLM
        llm_cfg = LLMConfig(
            base_url=config.get("llm.base_url", "http://localhost:11434"),
            model=config.get("llm.model", "richardyoung/qwen3.6-27b-abliterated:latest"),
            context_length=config.get("llm.context_length", 65536),
            temperature=config.get("llm.temperature", 0.7),
            top_p=config.get("llm.top_p", 0.9),
            timeout=config.get("llm.timeout", 120.0),
        )
        self.llm = LLMEngine(llm_cfg)

        # 协议服务器
        self.protocol = ProtocolServer(
            host=config.get("protocol.host", "127.0.0.1"),
            port=config.get("protocol.port", 17861),
            container_version="0.1.0",
            identity_id=self.identity_id,
            on_user_input=self._on_user_input,
            on_user_interrupt=self._on_user_interrupt,
            on_permission_response=self._on_permission_response,
            on_session_hello=self._on_session_hello,
        )

        # 生成状态
        self._current_session_id: Optional[str] = None
        self._current_trace_id: Optional[str] = None
        self._partial_reply_text: str = ""
        self._is_generating: bool = False
        self._pending_permissions: Dict[str, dict] = {}
        self._started = False
        self._stopped = False

        self._connect_signals()

    def _connect_signals(self) -> None:
        self.sig_stream_start.connect(self._handle_stream_start)
        self.sig_stream_delta.connect(self._handle_stream_delta)
        self.sig_stream_complete.connect(self._handle_stream_complete)
        self.sig_stream_interrupted.connect(self._handle_stream_interrupted)
        self.sig_permission_request.connect(self._handle_permission_request)

    def _load_soul(self) -> None:
        soul_path = self.config.get("soul.path", "supplements/soul/xixi_soul_rc1")
        try:
            self.soul = load_soul_package(soul_path, verify_checksums=True)
            self.prompt_builder = SoulPromptBuilder(self.soul)
            self.runtime_validator = SoulRuntimeValidator(self.soul)
            logger.info("Soul loaded: %s v%s", self.soul.package_id, self.soul.version)
        except Exception as e:
            logger.error("Failed to load soul: %s", e)
            self.soul = None

    def start(self) -> None:
        if self._started:
            return
        ok, msg = self.lifecycle.start(self)
        if not ok:
            logger.error("Lifecycle start failed: %s", msg)
            self.sig_system_error.emit("system", {
                "code": ErrorCode.INTERNAL_ERROR, "message": f"启动失败: {msg}",
            })
            return
        self.protocol.run_in_thread()
        self._started = True
        logger.info("Container started")

    def stop(self) -> None:
        if self._stopped:
            return
        self._stopped = True
        ok, msg = self.lifecycle.stop(self)
        if not ok:
            logger.error("Lifecycle stop error: %s", msg)
        logger.info("Container stopped")

    def backup(self, label: Optional[str] = None) -> Tuple[bool, str]:
        return self.lifecycle.backup(label)

    def rollback(self, backup_name: Optional[str] = None) -> Tuple[bool, str]:
        return self.lifecycle.rollback(backup_name)

    def health_check(self) -> Dict:
        return self.lifecycle.health_check(self)

    # ── 任务状态同步 ──
    def _on_task_status_change(self, task) -> None:
        self.sig_task_status.emit(self._current_session_id or "system", task.to_dict())
        self.protocol.broadcast_to_ui(MsgType.TASK_STATUS, task.to_dict())

    # ── 协议回调 ──
    def _on_session_hello(self, session_id: str, payload: dict) -> None:
        logger.info("UI session %s connected", session_id)
        self._send_model_status(session_id)
        # 发送当前任务状态
        summary = self.task_scheduler.get_status_summary()
        self.protocol.send_to_ui(session_id, MsgType.TASK_STATUS, summary, trace_id=f"trc_{uuid.uuid4().hex[:8]}")

    def _on_user_input(self, session_id: str, payload: dict, trace_id: str) -> None:
        user_text = payload.get("text", "").strip()
        if not user_text:
            return

        # 打断检测
        interrupt_keywords = {"停止", "停下", "别说了", "闭嘴", "打断"}
        if any(kw in user_text for kw in interrupt_keywords) and len(user_text) < 20:
            self._on_user_interrupt(session_id, {"reason": "user_interrupt_keyword"}, trace_id)
            return

        self._current_session_id = session_id
        self._current_trace_id = trace_id
        self._partial_reply_text = ""
        self._is_generating = True

        # 提交生成任务
        task = self.task_scheduler.submit_task(
            name="对话生成",
            description=f"回复: {user_text[:50]}...",
            weight=TaskWeight.HEAVY,
            capability="llm",
            operation="generate",
            target="conversation",
        )

        # 自然语言控制必须先于默认保存，明确“不记”时不落库。
        nl_result = self.memory_mgr.process_natural_language_command(user_text)
        if nl_result.get("action") == "skip_save":
            logger.info("User explicitly declined saving")
        else:
            try:
                self.memory_mgr.add_raw_note(user_text, source="user_input", role="user")
            except Exception as e:
                logger.error("Failed to save raw note: %s", e)
            if nl_result.get("action") == "save_memory":
                logger.info("User explicit save: %s", nl_result.get("id"))

        # 构建 system context
        system = self._build_system_context()
        messages = self.memory_mgr.get_recent_conversations(limit=20, as_messages=True)
        messages.append({"role": "user", "content": user_text})

        # 发送 stream.start
        self.sig_stream_start.emit(session_id, trace_id)

        # 启动生成
        gen_thread = threading.Thread(
            target=self._run_generation,
            args=(session_id, trace_id, messages, system, task.id),
            daemon=True,
        )
        gen_thread.start()

    def _run_generation(self, session_id: str, trace_id: str, 
                        messages: List[Dict], system: Optional[str], task_id: str) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._do_generation(session_id, trace_id, messages, system, task_id))
        except Exception as e:
            logger.exception("Generation error: %s", e)
            self.task_scheduler.fail_task(task_id, str(e))
            self.sig_system_error.emit(session_id, {
                "code": ErrorCode.INTERNAL_ERROR, "message": str(e),
            })
        finally:
            loop.run_until_complete(self.llm.close())
            loop.close()

    async def _do_generation(self, session_id: str, trace_id: str,
                             messages: List[Dict], system: Optional[str], task_id: str) -> None:
        full_text = ""
        metadata = {}

        try:
            self.task_scheduler.update_progress(task_id, 0.1)

            async for delta in self.llm.generate_stream(messages, system=system):
                if self.llm._cancelled:
                    break
                if delta.text:
                    full_text += delta.text
                    self._partial_reply_text = full_text
                    self.sig_stream_delta.emit(session_id, trace_id, delta.text)
                if delta.done:
                    metadata = {
                        "model": delta.model,
                        "total_duration": delta.total_duration,
                        "prompt_eval_count": delta.prompt_eval_count,
                        "eval_count": delta.eval_count,
                    }
                    break

            if self.llm._cancelled:
                self.task_scheduler.cancel_task(task_id)
                self.sig_stream_interrupted.emit(session_id, trace_id, {
                    "partial_text": full_text,
                    "partial_text_saved": False,
                    "reason": "user_interrupt",
                    "task_resume_token": None,
                })
            else:
                self.task_scheduler.complete_task(task_id, {"text": full_text, "metadata": metadata})
                self.sig_stream_complete.emit(session_id, trace_id, metadata)
                if full_text:
                    try:
                        self.memory_mgr.add_conversation("assistant", full_text)
                    except Exception as e:
                        logger.error("Failed to save assistant reply: %s", e)
                await self._process_soul_output(session_id, trace_id, full_text)
        except Exception as e:
            logger.exception("Generation error: %s", e)
            self.task_scheduler.fail_task(task_id, str(e))
            self.sig_system_error.emit(session_id, {
                "code": ErrorCode.INTERNAL_ERROR, "message": f"Generation failed: {e}",
            })
        finally:
            self._is_generating = False

    async def _process_soul_output(self, session_id: str, trace_id: str, text: str) -> None:
        if not self.runtime_validator:
            return
        structured = self._extract_json_from_text(text)
        if not structured:
            return

        ok, err, fixed = self.runtime_validator.validate_with_retry(structured)
        if not ok:
            logger.error("Soul output validation failed: %s", err)
            self.protocol.send_to_ui(session_id, MsgType.SYSTEM_ERROR, {
                "code": ErrorCode.SOUL_OUTPUT_INVALID,
                "message": f"Soul output schema error: {err}",
            }, trace_id=trace_id)
            return

        output = fixed or structured

        for action in output.get("memory_actions", []):
            await self._apply_memory_action(session_id, trace_id, action)

        for tool_req in output.get("tool_requests", []):
            await self._handle_tool_request(session_id, trace_id, tool_req)

        body_intent_data = output.get("body_intent")
        if body_intent_data:
            intent = BodyIntent.from_dict(body_intent_data)
            result = self.body_interface.set_intent(intent)
            self.sig_body_intent.emit(result)
            self.protocol.send_to_ui(session_id, MsgType.BODY_INTENT_SET, 
                                     result.get("intent", {}), trace_id=trace_id)

        state = output.get("state", {})
        if state:
            ui_mode = self._map_state_to_ui_mode(state.get("base"))
            if ui_mode:
                self.sig_ui_mode_set.emit(session_id, ui_mode)
            body_status = self.body_interface.map_state_to_intent(state)
            self.protocol.send_to_ui(session_id, MsgType.BODY_STATUS, {
                "status": self.body_interface.status,
                "intent": body_status.to_dict(),
            }, trace_id=trace_id)

    def _extract_json_from_text(self, text: str) -> Optional[Dict]:
        import re
        json_blocks = re.findall(r"```json\s*(.*?)```", text, re.DOTALL)
        if json_blocks:
            for block in json_blocks:
                try:
                    return json.loads(block.strip())
                except json.JSONDecodeError:
                    continue
        try:
            lines = text.split("\n")
            for line in reversed(lines):
                line = line.strip()
                if line.startswith("{") and line.endswith("}"):
                    return json.loads(line)
        except (json.JSONDecodeError, ValueError):
            pass
        return None

    async def _apply_memory_action(self, session_id: str, trace_id: str, action: dict) -> None:
        action_type = action.get("action")
        try:
            if action_type == "save_raw":
                self.memory_mgr.add_raw_note(
                    action.get("content", ""),
                    source=action.get("source_type", "user_quote"),
                    role=action.get("role", "user"),
                )
            elif action_type == "save_memory":
                self.memory_mgr.add_memory(
                    content=action.get("content", ""),
                    space=action.get("target_scope", "working"),
                    source_type=action.get("source_type", "xixi_opinion"),
                    project_id=action.get("project_id"),
                    confidence=action.get("confidence"),
                    role=action.get("role", "assistant"),
                )
            elif action_type == "supersede_memory":
                target_id = action.get("target_id")
                if target_id:
                    self.memory_mgr.supersede_memory(
                        old_id=target_id,
                        new_content=action.get("content", ""),
                        reason=action.get("reason", ""),
                    )
            elif action_type == "soft_delete":
                target_id = action.get("target_id")
                if target_id:
                    self.memory_mgr.soft_delete_memory(target_id)
            elif action_type == "purge":
                target_id = action.get("target_id")
                if target_id:
                    self.memory_mgr.purge_memory(target_id)
            logger.info("Memory action: %s", action_type)
        except Exception as e:
            logger.error("Memory action failed: %s", e)
            self.protocol.send_to_ui(session_id, MsgType.SYSTEM_ERROR, {
                "code": ErrorCode.MEMORY_WRITE_FAILED, "message": str(e),
            }, trace_id=trace_id)

    async def _handle_tool_request(self, session_id: str, trace_id: str, tool_req: dict) -> None:
        capability = tool_req.get("capability", "")
        operation = tool_req.get("operation", "")
        target = tool_req.get("target", "")
        input_data = tool_req.get("input", {})
        reason = tool_req.get("reason", "")

        # 提交工具任务
        tool_task = self.task_scheduler.submit_task(
            name=f"工具: {capability}.{operation}",
            description=f"{operation} {target}",
            weight=TaskWeight.LIGHT,
            capability=capability,
            operation=operation,
            target=target,
            input_data=input_data,
        )

        allowed, perm_id, risk = self.permission_gw.check_permission(
            capability=capability, operation=operation, target=target,
            input_data=input_data, reason=reason,
            session_id=session_id, trace_id=trace_id,
        )

        if allowed:
            await self._do_execute_tool(session_id, trace_id, tool_req, tool_task.id, perm_id)
        else:
            if perm_id:
                self._pending_permissions[perm_id] = {
                    "session_id": session_id, "trace_id": trace_id,
                    "tool_req": tool_req, "task_id": tool_task.id,
                }
                details = self.permission_gw.get_permission_details(perm_id)
                self.sig_permission_request.emit(session_id, trace_id, {
                    "permission_id": perm_id,
                    "operation": f"{capability}.{operation}",
                    "target": target,
                    "risk": risk.value,
                    "reason": reason,
                    "scope": input_data,
                    "description": details.get("reason", "") if details else "",
                })

    async def _do_execute_tool(self, session_id: str, trace_id: str,
                               tool_req: dict, task_id: str, perm_id: Optional[str] = None) -> None:
        capability = tool_req.get("capability", "")
        operation = tool_req.get("operation", "")
        target = tool_req.get("target", "")
        input_data = tool_req.get("input", {})

        logger.info("Tool: %s.%s -> %s", capability, operation, target)

        result = self.tool_executor.execute(
            capability=capability, operation=operation, target=target,
            input_data=input_data, task_id=task_id,
        )

        if result.success:
            self.task_scheduler.complete_task(task_id, result.to_dict())
            logger.info("Tool success: %s.%s", capability, operation)
        else:
            self.task_scheduler.fail_task(task_id, result.error or "Unknown error")
            logger.error("Tool failed: %s.%s - %s", capability, operation, result.error)
            self.protocol.send_to_ui(session_id, MsgType.SYSTEM_ERROR, {
                "code": ErrorCode.TOOL_EXECUTION_FAILED if not result.partial else ErrorCode.TOOL_PARTIAL_RESULT,
                "message": result.error or "Tool execution failed",
                "tool": f"{capability}.{operation}", "target": target,
            }, trace_id=trace_id)

        self.permission_gw._log_audit(
            operation=f"{capability}.{operation}", target=target,
            scope=json.dumps(input_data),
            result="success" if result.success else "failed",
            risk_level="unknown", task_id=task_id, error=result.error,
        )

    def _on_user_interrupt(self, session_id: str, payload: dict, trace_id: str) -> None:
        logger.info("Interrupt: session=%s trace=%s", session_id, trace_id)

        self.llm.cancel_generation()

        for perm_id in list(self._pending_permissions.keys()):
            info = self._pending_permissions[perm_id]
            if info["session_id"] == session_id:
                if "task_id" in info:
                    self.tool_executor.cancel_task(info["task_id"])
                    self.task_scheduler.cancel_task(info["task_id"])
                del self._pending_permissions[perm_id]

        self.sig_stream_interrupted.emit(session_id, trace_id, {
            "partial_text": self._partial_reply_text,
            "partial_text_saved": False,
            "reason": "user_interrupt",
            "task_resume_token": None,
        })

        self._is_generating = False
        self._partial_reply_text = ""

    def _on_permission_response(self, session_id: str, payload: dict, trace_id: str) -> None:
        perm_id = payload.get("permission_id")
        decision_str = payload.get("decision")

        try:
            decision = PermissionDecision(decision_str)
        except ValueError:
            logger.error("Invalid decision: %s", decision_str)
            return

        if perm_id not in self._pending_permissions:
            logger.warning("Unknown permission: %s", perm_id)
            return

        pending = self._pending_permissions.pop(perm_id)
        tool_req = pending["tool_req"]

        allowed = self.permission_gw.resolve_permission(perm_id, decision)

        if allowed:
            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(self._do_execute_tool(
                    pending["session_id"], pending["trace_id"], tool_req, pending["task_id"], perm_id
                ))
            finally:
                loop.close()
        else:
            self.task_scheduler.cancel_task(pending["task_id"])
            logger.info("Tool DENIED: %s.%s", tool_req.get("capability"), tool_req.get("operation"))
            self.protocol.send_to_ui(session_id, MsgType.SYSTEM_ERROR, {
                "code": ErrorCode.PERMISSION_DENIED,
                "message": f"用户拒绝了操作: {tool_req.get('operation')} {tool_req.get('target')}",
                "permission_id": perm_id,
            }, trace_id=trace_id)

    def _build_system_context(self) -> str:
        if not self.prompt_builder:
            return "你是西西。你是一个长期存在于用户Windows桌面中的本地数字人格。"

        current_state = self.state_mgr.get_current_state()
        relevant_memory = self.memory_mgr.search_relevant(limit=10)
        recent_conversation = self.memory_mgr.get_recent_conversations(limit=10, as_messages=True)
        current_project = None
        available_capabilities = ["file.read", "file.write", "file.list", "web.fetch", "web.search", "code.execute"]

        return self.prompt_builder.build_system_context(
            current_state=current_state,
            current_project=current_project,
            relevant_memory=relevant_memory,
            recent_conversation=recent_conversation,
            available_capabilities=available_capabilities,
        )

    def _map_state_to_ui_mode(self, base_state: Optional[str]) -> Optional[str]:
        mapping = {
            "sleeping": "quiet", "alone": "quiet",
            "working": "work", "thinking": "work",
            "waiting": "chat", "accompanying": "quiet",
            "communicating": "chat", "executing": "work",
        }
        return mapping.get(base_state)

    # ── Qt 信号槽 ──
    def _handle_stream_start(self, session_id: str, trace_id: str) -> None:
        self.protocol.send_to_ui(session_id, MsgType.ASSISTANT_STREAM_START, {
            "trace_id": trace_id,
        }, trace_id=trace_id)

    def _handle_stream_delta(self, session_id: str, trace_id: str, text: str) -> None:
        self.protocol.send_to_ui(session_id, MsgType.ASSISTANT_STREAM_DELTA, {
            "trace_id": trace_id, "delta": text,
        }, trace_id=trace_id)

    def _handle_stream_complete(self, session_id: str, trace_id: str, metadata: dict) -> None:
        self.protocol.send_to_ui(session_id, MsgType.ASSISTANT_STREAM_COMPLETE, {
            "trace_id": trace_id, "metadata": metadata,
        }, trace_id=trace_id)

    def _handle_stream_interrupted(self, session_id: str, trace_id: str, payload: dict) -> None:
        self.protocol.send_to_ui(session_id, MsgType.ASSISTANT_STREAM_INTERRUPTED, payload, trace_id=trace_id)
        logger.info("Interrupted reply NOT saved")

    def _handle_permission_request(self, session_id: str, trace_id: str, payload: dict) -> None:
        self.protocol.send_to_ui(session_id, MsgType.PERMISSION_REQUEST, payload, trace_id=trace_id)

    def _send_model_status(self, session_id: str) -> None:
        self.protocol.send_to_ui(session_id, MsgType.MODEL_STATUS, {
            "model": self.llm.config.model,
            "status": "ready" if self.soul else "degraded",
            "soul_version": self.soul.version if self.soul else None,
        })


def main():
    setup_logging()
    logger.info("=== 西西桌面伴侣 启动 ===")

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    # 加载配置
    config = Config.load("config.yaml")

    # 初始化数据库
    db = Database(config.get("database.path", "data/xixi.db"))

    # 创建容器
    container = Container(config, db)
    pid_path = Path("data/xixi.pid")
    pid_path.parent.mkdir(parents=True, exist_ok=True)
    pid_path.write_text(str(os.getpid()), encoding="utf-8")

    # 创建 Web 主窗口
    window = WebMainWindow(config, db, container)
    window.show()

    # 启动容器
    container.start()

    def _cleanup_pid():
        try:
            container.stop()
        finally:
            pid_path.unlink(missing_ok=True)

    app.aboutToQuit.connect(_cleanup_pid)

    # 健康检查
    health = container.health_check()
    logger.info("Health check: %s", health.get("status", "unknown"))

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
