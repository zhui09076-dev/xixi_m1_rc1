#!/usr/bin/env python3
"""
西西桌面伴侣 M1-RC3
===================
完整启动入口
"""

import sys
import os
import asyncio
import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path

from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QLineEdit, QPushButton, QLabel, QListWidget, QSystemTrayIcon, QMenu
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QAction, QIcon

from core import (
    Config, setup_logger, Database,
    PersonalityConstitution, MemorySystem,
    XiXiState, StateMachine, BootMode,
    LLMEngine, AssetManager, SystemMonitor,
    Identity, PermissionGateway, ActionRequest,
    TaskScheduler, IntentClassifier, IntentType, IntentResult,
    VersionRegistry
)


class StreamWorker(QThread):
    chunk_ready = pyqtSignal(str)
    finished_signal = pyqtSignal()
    error_signal = pyqtSignal(str)

    def __init__(self, llm, message):
        super().__init__()
        self.llm = llm
        self.message = message
        self._loop = None

    def run(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._stream())
        except Exception as e:
            self.error_signal.emit(str(e))
        finally:
            self.finished_signal.emit()

    async def _stream(self):
        async for chunk in self.llm.chat_stream(self.message):
            self.chunk_ready.emit(chunk)


class XiXiApp:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)

        self.logger = setup_logger()
        self.logger.info("=== 西西启动 ===")

        # 配置
        self.config = Config.load()

        # 数据库（自动迁移到 v3）
        self.db = Database(self.config.database.get("path", "data/xixi.db"))

        # 版本注册表
        self.version_registry = VersionRegistry.load()
        self.db.save_version_registry(self.version_registry.to_dict())

        # 身份
        self.identity = Identity.load()
        self.db.save_identity(self.identity.to_dict())

        # 人格宪法
        self.constitution = PersonalityConstitution.load()

        # 状态机 + 启动模式判断
        self._determine_boot_mode()

        # 资产
        self.asset_manager = AssetManager(self.config.assets.get("manifest", "assets/manifest.json"))

        # 记忆
        self.memory = MemorySystem(self.db)

        # 权限网关
        self.permission_gateway = PermissionGateway(self.db)

        # 任务调度
        self.task_scheduler = TaskScheduler(self.db)

        # 意图分类器
        self.intent_classifier = IntentClassifier()

        # LLM
        self.llm = LLMEngine(
            host=self.config.ollama.get("host", "http://localhost:11434"),
            model=self.config.ollama.get("model", "richardyoung/qwen3.6-27b-abliterated:latest"),
            constitution=self.constitution,
            memory=self.memory,
            state_machine=self.state_machine,
            intent_classifier=self.intent_classifier,
            timeout=self.config.ollama.get("timeout", 120),
        )

        # 系统监控
        self.sysmon = SystemMonitor()

        # 构建 UI
        self._build_ui()

        # 定时器
        self.idle_seconds = 0
        self.timer = QTimer()
        self.timer.timeout.connect(self._on_tick)
        self.timer.start(1000)

        # 系统托盘
        self._setup_tray()

        # 启动问候
        self._greet_on_startup()

    def _determine_boot_mode(self):
        state_data = self.db.get_state()
        if not state_data:
            self.boot_mode = BootMode.COLD_START
            self.state_machine = StateMachine(XiXiState.ALONE, BootMode.COLD_START)
            self.logger.info("首次启动 (cold_start)")
        else:
            last_str = state_data.get("last_interaction_at", datetime.now().isoformat())
            try:
                last = datetime.fromisoformat(last_str)
            except Exception:
                last = datetime.now()
            delta = (datetime.now() - last).total_seconds()
            if delta < 300:  # 5分钟内
                self.boot_mode = BootMode.RECONNECT
                self.state_machine = StateMachine.from_dict(state_data)
                self.state_machine.snapshot.boot_mode = BootMode.RECONNECT.value
                self.logger.info("快速重连 (reconnect)")
            else:
                self.boot_mode = BootMode.RESTORE
                self.state_machine = StateMachine.from_dict(state_data)
                self.state_machine.snapshot.boot_mode = BootMode.RESTORE.value
                self.logger.info(f"恢复状态 (restore), 离线 {delta/60:.0f} 分钟")

    def _build_ui(self):
        self.window = QWidget()
        self.window.setWindowTitle("西西 M1-RC3")
        self.window.setGeometry(100, 100, 900, 700)

        layout = QVBoxLayout()

        # 状态栏
        self.status_label = QLabel(f"状态: {self.state_machine.label} | 模式: {self.boot_mode.value}")
        layout.addWidget(self.status_label)

        # 聊天历史
        self.chat_history = QTextEdit()
        self.chat_history.setReadOnly(True)
        font = QFont("Microsoft YaHei", 11)
        self.chat_history.setFont(font)
        layout.addWidget(self.chat_history)

        # 输入区
        hbox = QHBoxLayout()
        self.input_box = QLineEdit()
        self.input_box.setPlaceholderText("跟西西说点什么...")
        self.input_box.returnPressed.connect(self._send_message)
        hbox.addWidget(self.input_box)

        send_btn = QPushButton("发送")
        send_btn.clicked.connect(self._send_message)
        hbox.addWidget(send_btn)

        abort_btn = QPushButton("打断")
        abort_btn.clicked.connect(self._abort_generation)
        hbox.addWidget(abort_btn)

        layout.addLayout(hbox)

        # 功能按钮
        btn_box = QHBoxLayout()
        for name, func in [
            ("笔记", self._open_notes),
            ("待办", self._open_todos),
            ("项目", self._open_projects),
            ("模型", self._open_model_settings),
        ]:
            b = QPushButton(name)
            b.clicked.connect(func)
            btn_box.addWidget(b)
        layout.addLayout(btn_box)

        self.window.setLayout(layout)
        self.window.show()

    def _setup_tray(self):
        self.tray = QSystemTrayIcon(self.app)
        self.tray.setVisible(True)
        menu = QMenu()
        show_action = QAction("显示", self.window)
        show_action.triggered.connect(self.window.show)
        menu.addAction(show_action)
        quit_action = QAction("退出", self.window)
        quit_action.triggered.connect(self._graceful_exit)
        menu.addAction(quit_action)
        self.tray.setContextMenu(menu)

    def _greet_on_startup(self):
        if self.boot_mode == BootMode.COLD_START:
            self.chat_history.append("<b>西西：</b> 你好，我是西西。以后我会一直在这里。有什么我可以帮你的吗？")
        elif self.boot_mode == BootMode.RECONNECT:
            self.chat_history.append("<b>西西：</b> 嗯？回来了？")
        else:
            away = self.memory.get_time_away_summary()
            self.chat_history.append(f"<b>西西：</b> {away} 欢迎回来。")

    def _send_message(self):
        text = self.input_box.text().strip()
        if not text:
            return
        self.input_box.clear()
        self.chat_history.append(f"<b>你：</b> {text}")

        # 意图识别
        intent_result = self.intent_classifier.classify(text)
        self.logger.info(f"用户意图: {intent_result.intent.value} (confidence={intent_result.confidence}, rule={intent_result.matched_rule})")

        # 状态更新
        self.state_machine.on_interaction()
        self._update_status()

        # 如果是 instruction，检查权限
        if intent_result.intent == IntentType.INSTRUCTION:
            req = ActionRequest(
                action_id=hashlib.md5(f"{datetime.now().isoformat()}{text}".encode()).hexdigest()[:12],
                task_id="",
                action_type="执行",
                target=text,
                scope="local",
                data_category="user_input",
                risk_level="medium",
                requested_by="user",
                reason="用户指令",
                created_at=datetime.now().isoformat()
            )
            perm = self.permission_gateway.check(req)
            if perm.requires_confirm:
                self.chat_history.append(f"<b>西西：</b> （此操作需要确认: {perm.reason}）")
                return

        # 流式生成
        self._stream_worker = StreamWorker(self.llm, text)
        self._stream_worker.chunk_ready.connect(self._on_chunk)
        self._stream_worker.finished_signal.connect(self._on_stream_finished)
        self._stream_worker.error_signal.connect(self._on_stream_error)
        self._stream_worker.start()

        # 保存用户消息
        self.memory.add_chat("user", text, session_id="default")

    def _on_chunk(self, chunk: str):
        cursor = self.chat_history.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.insertText(chunk)
        self.chat_history.setTextCursor(cursor)
        self.chat_history.ensureCursorVisible()

    def _on_stream_finished(self):
        self.chat_history.append("")
        # 保存完整回复到记忆
        full_text = self.chat_history.toPlainText().split("西西：")[-1].strip()
        if full_text:
            self.memory.add_chat("xixi", full_text, source_type="xixi_opinion", session_id="default")
        self._save_state()

    def _on_stream_error(self, error: str):
        self.chat_history.append(f"<b>系统错误：</b> {error}")

    def _abort_generation(self):
        self.llm.abort()
        self.chat_history.append("<b>西西：</b> （已停止）")

    def _on_tick(self):
        self.idle_seconds += 1
        if self.idle_seconds % 60 == 0:
            minutes = self.idle_seconds // 60
            result = self.state_machine.on_idle(minutes)
            if result:
                self._update_status()

    def _update_status(self):
        self.status_label.setText(
            f"状态: {self.state_machine.label} | "
            f"情绪: {self.state_machine.snapshot.emotion} | "
            f"模式: {self.state_machine.snapshot.boot_mode}"
        )

    def _save_state(self):
        self.db.set_state(self.state_machine.to_dict())

    def _open_notes(self):
        notes = self.memory.get_notes(limit=10)
        text = "\n".join([f"• {n['content'][:40]}" for n in notes]) or "暂无笔记"
        self.chat_history.append(f"<b>笔记：</b>\n{text}")

    def _open_todos(self):
        todos = self.memory.get_todos(done=False)
        text = "\n".join([f"[{'x' if t['done'] else ' '}] {t['content']}" for t in todos]) or "暂无待办"
        self.chat_history.append(f"<b>待办：</b>\n{text}")

    def _open_projects(self):
        projects = self.memory.get_projects()
        text = "\n".join([f"• {p['name']}" for p in projects]) or "暂无项目"
        self.chat_history.append(f"<b>项目：</b>\n{text}")

    def _open_model_settings(self):
        self.chat_history.append(
            f"<b>模型设置：</b>\n"
            f"Host: {self.config.ollama.get('host')}\n"
            f"Model: {self.config.ollama.get('model')}\n"
            f"可用: {'是' if self.llm.is_available() else '否（大脑当前不可用）'}"
        )

    def _graceful_exit(self):
        self._save_state()
        self.logger.info("西西关闭")
        asyncio.run(self.llm.close())
        self.app.quit()

    def run(self):
        sys.exit(self.app.exec())


if __name__ == "__main__":
    app = XiXiApp()
    app.run()
