#!/usr/bin/env python3
"""西西桌面伴侣 M1 — Windows 容器启动入口"""
import sys
import os
import warnings
from pathlib import Path

warnings.filterwarnings("ignore", category=DeprecationWarning)

try:
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtCore import Qt
except ImportError as e:
    print(f"致命错误: 无法导入 PyQt6: {e}")
    print("请执行: pip install PyQt6")
    sys.exit(1)

from core import (Config, setup_logger, Database, PersonalityConstitution,
                  MemorySystem, StateMachine, BootMode, AssetManager, SystemMonitor,
                  IdentityManager, PermissionGateway, TaskScheduler, IntentClassifier,
                  VersionRegistry, SoulLoader, BodyLoader, LLMEngine)
from host import WindowManager, TrayManager, DPIManager
from renderer import QtRenderer


class XiXiContainer:
    """西西容器 M1"""

    def __init__(self):
        self.app = QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)

        self.logger = setup_logger()
        self.logger.info("=== 西西容器 M1 启动 ===")

        self.config = Config.load()
        self.db = Database(self.config.database.get("path", "data/xixi.db"))

        # 核心组件
        self.identity_manager = IdentityManager(self.db)
        self.memory = MemorySystem(self.db)
        self.state_machine = StateMachine()
        self.permission_gateway = PermissionGateway(
            self.db,
            authorized_paths=self.config.permissions.get("authorized_paths", [])
        )
        self.task_scheduler = TaskScheduler(self.db)
        self.intent_classifier = IntentClassifier()
        self.version_registry = VersionRegistry()
        self.llm = LLMEngine(
            config=self.config.ollama.to_dict() if hasattr(self.config.ollama, 'to_dict') else dict(self.config.ollama),
            memory=self.memory,
            state_machine=self.state_machine,
            intent_classifier=self.intent_classifier,
        )

        # Soul / Body 加载器
        self.soul_loader = SoulLoader(
            self.db, self.version_registry,
            packages_dir=self.config.soul_packages_dir
        )
        self.body_loader = BodyLoader(
            self.db, self.version_registry,
            packages_dir=self.config.body_packages_dir
        )

        # 加载内容包
        self._load_packages()

        # 恢复状态
        self._restore_state()

        # 窗口管理
        self.window_manager = WindowManager(self.app, self.config.to_dict())
        self.renderer = None
        self.ui = None

        # 系统托盘
        self.tray = TrayManager(self.app)
        self.window_manager.setup_tray(self.tray)

        # 崩溃恢复
        sys.excepthook = self._exception_hook

    def _load_packages(self):
        """加载 Soul 和 Body 内容包"""
        # 扫描并加载所有 Soul 包
        soul_ids = self.soul_loader.load_all()
        self.logger.info(f"发现 Soul 包: {soul_ids}")
        if soul_ids:
            # 激活第一个（或从数据库恢复）
            active_soul = self.soul_loader.get_active()
            if not active_soul:
                self.soul_loader.activate(soul_ids[0])
                self.logger.info(f"激活 Soul 包: {soul_ids[0]}")

        # 扫描并加载所有 Body 包
        body_ids = self.body_loader.load_all()
        self.logger.info(f"发现 Body 包: {body_ids}")
        if body_ids:
            active_body = self.body_loader.get_active()
            if not active_body:
                self.body_loader.activate(body_ids[0])
                self.logger.info(f"激活 Body 包: {body_ids[0]}")

    def _exception_hook(self, exc_type, exc_value, exc_traceback):
        self.logger.error("未捕获异常", exc_info=(exc_type, exc_value, exc_traceback))
        if self.window_manager and self.window_manager.ui:
            self.window_manager.ui.append_chat("系统", f"容器异常：{exc_value}\n已尝试恢复。")
        self._save_state()

    def _restore_state(self):
        saved = self.db.load_state()
        if saved:
            try:
                self.state_machine = StateMachine.from_dict(saved)
                self.logger.info(f"状态恢复: {self.state_machine.state.value}")
            except Exception as e:
                self.logger.warning(f"状态恢复失败: {e}")

    def _save_state(self):
        try:
            self.db.save_state(self.state_machine.to_dict())
        except Exception as e:
            self.logger.error(f"状态保存失败: {e}")

    def setup_renderer(self):
        try:
            self.renderer = QtRenderer(self.config.to_dict())
            # 如果有 Body 包，设置图层
            active_body = self.body_loader.get_active()
            if active_body:
                for layer in self.config.render.get("layers", ["background", "character", "foreground", "lighting"]):
                    path = self.body_loader.get_layer_path(active_body.package_id, layer)
                    if path:
                        self.renderer.set_layer(layer, path)
            self.renderer.show()
            self.logger.info("Renderer 启动成功")
        except Exception as e:
            self.logger.error(f"Renderer 启动失败: {e}")
            self.renderer = None

    def setup_ui(self):
        try:
            self.renderer_win, self.ui_win = self.window_manager.create_windows()
            if self.renderer:
                self.renderer_win = self.renderer
            self.ui_win.sig_send_message.connect(self._on_user_message)
            self.window_manager.show_all()
            self.logger.info("UI 启动成功")
        except Exception as e:
            self.logger.error(f"UI 启动失败: {e}")

    def _on_user_message(self, text: str):
        self.logger.info(f"用户消息: {text}")
        intent = self.intent_classifier.classify(text)

        memory_result = self.memory.handle_memory_command(text)
        if memory_result:
            self.ui_win.append_chat("西西", memory_result)
            return

        if intent and intent.intent.value == "interruption":
            self.llm.abort()
            self.ui_win.append_chat("西西", "（已停止）")
            return

        self.memory.add_chat("user", text)
        self.state_machine.on_interaction()
        self._save_state()
        self._generate_reply(text)

    def _generate_reply(self, text: str):
        import asyncio
        import threading

        async def _stream():
            self.ui_win.set_status("思考中...")
            full_reply = ""
            try:
                async for chunk in self.llm.chat_stream(text):
                    full_reply += chunk
                if full_reply:
                    self.ui_win.append_chat("西西", full_reply)
                    self.memory.add_chat("xixi", full_reply)
                else:
                    self.ui_win.append_chat("西西", "（暂无回复）")
            except Exception as e:
                self.ui_win.append_chat("西西", f"生成异常：{e}")
            finally:
                self.ui_win.set_status("就绪")
                self._save_state()

        def _run_async():
            try:
                asyncio.run(_stream())
            except Exception as e:
                self.logger.error(f"异步生成失败: {e}")

        t = threading.Thread(target=_run_async, daemon=True)
        t.start()

    def run(self):
        self.setup_renderer()
        self.setup_ui()

        active_soul = self.soul_loader.get_active()
        soul_name = active_soul.raw.get("entry", {}).get("identity", "西西") if active_soul else "西西"
        if self.ui_win:
            self.ui_win.append_chat("西西", f"你好，我是{soul_name}。容器 M1 已启动。")

        self.logger.info("=== 容器运行中 ===")

        try:
            exit_code = self.app.exec()
        except Exception as e:
            self.logger.error(f"应用异常: {e}", exc_info=True)
            exit_code = 1
        finally:
            self._save_state()
            self.db.close()
            self.logger.info("=== 容器退出 ===")

        sys.exit(exit_code)


def main():
    container = XiXiContainer()
    container.run()


if __name__ == "__main__":
    main()
