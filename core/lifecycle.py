"""
Lifecycle Manager - 安装、启动、停止、备份、回滚
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("xixi.lifecycle")

class LifecycleManager:
    """
    生命周期管理器

    职责:
    - 一键安装（依赖检查、目录创建、数据库初始化）
    - 一键启动（Ollama检查、模型加载、服务启动）
    - 一键停止（模型卸载、session关闭、WebSocket关闭、数据库关闭）
    - 正常退出流程
    - 配置文件备份
    - Soul/UI/协议版本记录
    - 上一稳定版本恢复
    """

    def __init__(self, base_dir: Optional[str] = None):
        self.base_dir = Path(base_dir or os.getcwd()).resolve()
        self.data_dir = self.base_dir / "data"
        self.backup_dir = self.base_dir / "backups"
        self.log_dir = self.base_dir / "logs"
        self.config_path = self.base_dir / "config.yaml"

        # 版本记录文件
        self.version_file = self.data_dir / "versions.json"
        self.stable_marker = self.data_dir / ".stable"

    # ── 安装 ──

    def install(self) -> Tuple[bool, str]:
        """
        一键安装。

        步骤:
        1. 检查 Python 版本
        2. 安装 pip 依赖
        3. 创建目录结构
        4. 初始化数据库
        5. 检查 Ollama 安装
        6. 记录初始版本
        """
        logger.info("=== 西西 安装开始 ===")

        # 1. Python 版本
        if sys.version_info < (3, 10):
            return False, f"Python 3.10+ required, got {sys.version}"

        # 2. 创建目录
        for d in [self.data_dir, self.backup_dir, self.log_dir,
                  self.base_dir / "assets", self.base_dir / "supplements"]:
            d.mkdir(parents=True, exist_ok=True)

        # 3. 安装依赖
        req_file = self.base_dir / "requirements.txt"
        if req_file.exists():
            try:
                result = subprocess.run(
                    [sys.executable, "-m", "pip", "install", "-r", str(req_file)],
                    capture_output=True, text=True, timeout=300
                )
                if result.returncode != 0:
                    return False, f"pip install failed: {result.stderr}"
            except Exception as e:
                return False, f"pip install error: {e}"

        # 4. 初始化数据库
        db_path = self.data_dir / "xixi.db"
        try:
            conn = sqlite3.connect(str(db_path))
            conn.execute("PRAGMA journal_mode=WAL")
            conn.close()
        except Exception as e:
            return False, f"Database init failed: {e}"

        # 5. 检查 Ollama
        ollama_ok, ollama_msg = self._check_ollama()
        if not ollama_ok:
            logger.warning("Ollama not ready: %s", ollama_msg)

        # 6. 记录版本
        self._record_version("install", {
            "python": sys.version,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "ollama_status": ollama_msg,
        })

        logger.info("=== 西西 安装完成 ===")
        return True, "Installation successful"

    def _check_ollama(self) -> Tuple[bool, str]:
        """检查 Ollama 是否安装并运行"""
        try:
            result = subprocess.run(
                ["ollama", "--version"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                # 检查服务是否运行
                import urllib.request
                try:
                    req = urllib.request.Request("http://localhost:11434/api/tags")
                    with urllib.request.urlopen(req, timeout=5) as resp:
                        if resp.status == 200:
                            return True, f"Ollama running: {result.stdout.strip()}"
                        return False, f"Ollama installed but service not responding"
                except Exception as e:
                    return False, f"Ollama installed but service offline: {e}"
            return False, f"Ollama not installed or not in PATH"
        except FileNotFoundError:
            return False, "Ollama not found in PATH"
        except Exception as e:
            return False, f"Ollama check error: {e}"

    # ── 启动 ──

    def start(self, container) -> Tuple[bool, str]:
        """
        一键启动。

        步骤:
        1. 加载配置
        2. 初始化数据库
        3. 加载 Soul
        4. 检查 Ollama 并加载模型
        5. 启动协议服务器
        6. 启动任务调度器
        7. 标记稳定版本
        """
        logger.info("=== 西西 启动开始 ===")

        try:
            # 标记稳定版本（用于回滚）
            self._mark_stable()

            # 记录启动版本
            self._record_version("startup", {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "soul_version": container.soul.version if container.soul else None,
                "model": container.llm.config.model if container.llm else None,
            })

            # 预加载模型
            if container.llm:
                import asyncio
                loop = asyncio.new_event_loop()
                try:
                    ok, msg = loop.run_until_complete(container.llm.load_model())
                    loop.run_until_complete(container.llm.close())
                    if ok:
                        logger.info("Model preloaded: %s", msg)
                    else:
                        logger.warning("Model preload: %s", msg)
                finally:
                    loop.close()

            logger.info("=== 西西 启动完成 ===")
            return True, "Started successfully"
        except Exception as e:
            logger.exception("Start failed: %s", e)
            return False, f"Start failed: {e}"

    # ── 停止 ──

    def stop(self, container) -> Tuple[bool, str]:
        """
        一键停止。

        步骤:
        1. 停止任务调度器（暂停所有任务）
        2. 取消当前 LLM 生成
        3. 卸载模型
        4. 关闭 LLM aiohttp session
        5. 关闭 WebSocket 服务
        6. 关闭数据库连接
        7. 刷新日志
        8. 记录停止日志
        """
        logger.info("=== 西西 停止开始 ===")

        try:
            # 1. 停止任务调度
            if container.task_scheduler:
                container.task_scheduler.cleanup()

            # 2. 取消生成
            if container.llm:
                container.llm.cancel_generation()

            # 3. 卸载模型
            if container.llm:
                import asyncio
                loop = asyncio.new_event_loop()
                try:
                    ok, msg = loop.run_until_complete(container.llm.unload_model())
                    loop.run_until_complete(container.llm.close())
                    logger.info("Model unload: %s", msg)
                finally:
                    loop.close()

            # 5. 关闭协议服务器
            if container.protocol:
                container.protocol.shutdown()

            # 6. 关闭数据库
            if container.db:
                container.db.close()

            # 7. 关闭记忆管理器连接
            if container.memory_mgr:
                container.memory_mgr.cleanup()

            # 8. 关闭权限网关连接
            if container.permission_gw:
                container.permission_gw.cleanup()

            # 9. 刷新日志
            logging.shutdown()

            logger.info("=== 西西 停止完成 ===")
            return True, "Stopped cleanly"
        except Exception as e:
            logger.exception("Stop error: %s", e)
            return False, f"Stop error: {e}"

    # ── 备份 ──

    def backup(self, label: Optional[str] = None) -> Tuple[bool, str]:
        """
        创建备份。

        备份内容:
        - 数据库
        - 配置文件
        - 版本记录
        """
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        label = label or "manual"
        backup_name = f"backup_{label}_{timestamp}"
        backup_path = self.backup_dir / backup_name

        try:
            backup_path.mkdir(parents=True, exist_ok=True)

            # 备份数据库
            db_src = self.data_dir / "xixi.db"
            if db_src.exists():
                shutil.copy2(str(db_src), str(backup_path / "xixi.db"))

            # 备份配置
            if self.config_path.exists():
                shutil.copy2(str(self.config_path), str(backup_path / "config.yaml"))

            # 备份版本记录
            if self.version_file.exists():
                shutil.copy2(str(self.version_file), str(backup_path / "versions.json"))

            # 备份 Soul（如果存在）
            soul_dir = self.base_dir / "supplements" / "soul"
            if soul_dir.exists():
                shutil.copytree(str(soul_dir), str(backup_path / "soul"), dirs_exist_ok=True)

            logger.info("Backup created: %s", backup_path)
            return True, str(backup_path)
        except Exception as e:
            logger.error("Backup failed: %s", e)
            return False, str(e)

    def list_backups(self) -> List[Dict]:
        """列出所有备份"""
        backups = []
        if not self.backup_dir.exists():
            return backups

        for item in sorted(self.backup_dir.iterdir(), reverse=True):
            if item.is_dir() and item.name.startswith("backup_"):
                backups.append({
                    "name": item.name,
                    "path": str(item),
                    "created": datetime.fromtimestamp(item.stat().st_mtime, timezone.utc).isoformat(),
                })
        return backups

    # ── 回滚 ──

    def rollback(self, backup_name: Optional[str] = None) -> Tuple[bool, str]:
        """
        回滚到上一稳定版本或指定备份。

        步骤:
        1. 如果没有指定备份，使用最新的备份
        2. 停止当前服务
        3. 恢复数据库
        4. 恢复配置
        5. 恢复 Soul
        """
        if backup_name is None:
            backups = self.list_backups()
            if not backups:
                return False, "No backups available"
            backup_name = backups[0]["name"]

        backup_path = self.backup_dir / backup_name
        if not backup_path.exists():
            return False, f"Backup not found: {backup_name}"

        try:
            # 恢复数据库
            db_backup = backup_path / "xixi.db"
            if db_backup.exists():
                shutil.copy2(str(db_backup), str(self.data_dir / "xixi.db"))

            # 恢复配置
            config_backup = backup_path / "config.yaml"
            if config_backup.exists():
                shutil.copy2(str(config_backup), str(self.config_path))

            # 恢复 Soul
            soul_backup = backup_path / "soul"
            if soul_backup.exists():
                soul_target = self.base_dir / "supplements" / "soul"
                if soul_target.exists():
                    shutil.rmtree(str(soul_target))
                shutil.copytree(str(soul_backup), str(soul_target))

            logger.info("Rollback completed: %s", backup_name)
            return True, f"Rolled back to {backup_name}"
        except Exception as e:
            logger.error("Rollback failed: %s", e)
            return False, str(e)

    def rollback_to_stable(self) -> Tuple[bool, str]:
        """回滚到上一稳定版本"""
        if not self.stable_marker.exists():
            return False, "No stable marker found"

        try:
            stable_info = json.loads(self.stable_marker.read_text(encoding="utf-8"))
            backup_name = stable_info.get("backup_name")
            if backup_name:
                return self.rollback(backup_name)
            return False, "No backup reference in stable marker"
        except Exception as e:
            return False, f"Stable marker read error: {e}"

    # ── 版本记录 ──

    def _record_version(self, event: str, data: Dict) -> None:
        """记录版本信息"""
        versions = []
        if self.version_file.exists():
            try:
                versions = json.loads(self.version_file.read_text(encoding="utf-8"))
            except Exception:
                pass

        versions.append({
            "event": event,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": data,
        })

        # 只保留最近 100 条
        versions = versions[-100:]

        self.version_file.write_text(json.dumps(versions, indent=2, ensure_ascii=False), encoding="utf-8")

    def get_version_history(self) -> List[Dict]:
        """获取版本历史"""
        if self.version_file.exists():
            try:
                return json.loads(self.version_file.read_text(encoding="utf-8"))
            except Exception:
                pass
        return []

    def _mark_stable(self) -> None:
        """标记当前为稳定版本"""
        # 先创建备份
        ok, backup_path = self.backup(label="stable")
        if ok:
            self.stable_marker.write_text(json.dumps({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "backup_name": Path(backup_path).name,
            }), encoding="utf-8")
            logger.info("Stable marker set: %s", backup_path)

    # ── 健康检查 ──

    def health_check(self, container) -> Dict[str, Any]:
        """系统健康检查"""
        checks = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "protocol": "xixi/1.0",
            "container_version": "0.1.0",
            "identity_id": "xixi-main",
        }

        # Ollama 状态
        ollama_ok, ollama_msg = self._check_ollama()
        checks["ollama"] = {"ok": ollama_ok, "message": ollama_msg}

        # Soul 状态
        checks["soul"] = {
            "loaded": container.soul is not None,
            "version": container.soul.version if container.soul else None,
        }

        # 数据库状态
        try:
            conn = sqlite3.connect(str(self.data_dir / "xixi.db"))
            # 修复：使用正确的表名 xixi_memory_entries
            cursor = conn.execute("SELECT COUNT(*) FROM xixi_memory_entries")
            mem_count = cursor.fetchone()[0]
            conn.close()
            checks["database"] = {"ok": True, "memory_entries": mem_count}
        except Exception as e:
            checks["database"] = {"ok": False, "error": str(e)}

        # 协议服务器状态
        checks["protocol_server"] = {
            "active_sessions": len(container.protocol.get_active_sessions()) if container.protocol else 0,
        }

        # 整体状态
        all_ok = all(c.get("ok", True) for c in [checks["ollama"], checks["database"]])
        checks["status"] = "ready" if all_ok else "degraded"

        return checks
