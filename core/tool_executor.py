"""
Tool Executor - 工具真实执行与结果回传
支持: 文件操作、网页搜索、代码执行、系统命令（受限）
"""
from __future__ import annotations

import json
import logging
import os
import subprocess
import urllib.request
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("xixi.tool")


class ToolResult:
    """工具执行结果"""
    def __init__(
        self,
        success: bool,
        data: Any = None,
        error: Optional[str] = None,
        partial: bool = False,
        cancelled: bool = False,
    ):
        self.success = success
        self.data = data
        self.error = error
        self.partial = partial
        self.cancelled = cancelled
        self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict:
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "partial": self.partial,
            "cancelled": self.cancelled,
            "timestamp": self.timestamp,
        }


class ToolExecutor:
    """
    工具执行器

    支持的能力:
    - file.read: 读取文件
    - file.write: 写入文件
    - file.list: 列出目录
    - file.delete: 删除文件
    - web.search: 网页搜索（简化版）
    - web.fetch: 获取网页内容
    - code.execute: 执行 Python 代码（沙箱）
    - system.shell: 执行系统命令（严格受限）
    """

    # 允许的系统命令白名单（极其严格）
    ALLOWED_SHELL_COMMANDS = {"dir", "ls", "echo", "type", "cat", "pwd", "cd"}

    # 禁止访问的路径
    FORBIDDEN_PATHS = [
        "C:\\Windows\\System32",
        "/etc",
        "/usr/bin",
        "C:\\Windows",
    ]

    def __init__(self, allowed_dirs: Optional[List[str]] = None):
        self.allowed_dirs = allowed_dirs or [os.getcwd(), os.path.expanduser("~/Documents")]
        self._cancelled_tasks: set = set()

    def cancel_task(self, task_id: str) -> None:
        """取消正在执行的工具任务"""
        self._cancelled_tasks.add(task_id)
        logger.info("Tool task cancelled: %s", task_id)

    def execute(self, capability: str, operation: str, target: str, 
                input_data: Dict, task_id: Optional[str] = None) -> ToolResult:
        """
        执行工具。

        参数:
            capability: 能力类型 (file/web/code/system)
            operation: 具体操作
            target: 操作目标
            input_data: 输入参数
            task_id: 任务ID（用于取消）

        返回: ToolResult
        """
        if task_id and task_id in self._cancelled_tasks:
            return ToolResult(success=False, cancelled=True, error="Task was cancelled")

        try:
            if capability == "file":
                return self._execute_file(operation, target, input_data, task_id)
            elif capability == "web":
                return self._execute_web(operation, target, input_data, task_id)
            elif capability == "code":
                return self._execute_code(operation, target, input_data, task_id)
            elif capability == "system":
                return self._execute_system(operation, target, input_data, task_id)
            else:
                return ToolResult(success=False, error=f"Unknown capability: {capability}")
        except Exception as e:
            logger.exception("Tool execution error: %s", e)
            return ToolResult(success=False, error=str(e))

    # ── 文件操作 ──

    def _execute_file(self, operation: str, target: str, 
                      input_data: Dict, task_id: Optional[str]) -> ToolResult:
        """执行文件操作"""
        path = Path(target)

        # 安全检查
        if not self._is_path_allowed(path):
            return ToolResult(success=False, error=f"Path not allowed: {target}")

        if operation == "read":
            try:
                content = path.read_text(encoding="utf-8")
                return ToolResult(success=True, data={"content": content, "path": str(path)})
            except Exception as e:
                return ToolResult(success=False, error=str(e))

        elif operation == "write":
            try:
                content = input_data.get("content", "")
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")
                return ToolResult(success=True, data={"path": str(path), "bytes_written": len(content)})
            except Exception as e:
                return ToolResult(success=False, error=str(e))

        elif operation == "list":
            try:
                items = []
                for item in path.iterdir():
                    items.append({
                        "name": item.name,
                        "is_file": item.is_file(),
                        "is_dir": item.is_dir(),
                        "size": item.stat().st_size if item.is_file() else 0,
                    })
                return ToolResult(success=True, data={"path": str(path), "items": items})
            except Exception as e:
                return ToolResult(success=False, error=str(e))

        elif operation == "delete":
            try:
                if path.is_file():
                    path.unlink()
                    return ToolResult(success=True, data={"deleted": str(path)})
                elif path.is_dir():
                    # 只允许删除空目录
                    path.rmdir()
                    return ToolResult(success=True, data={"deleted": str(path)})
                return ToolResult(success=False, error=f"Path not found: {target}")
            except Exception as e:
                return ToolResult(success=False, error=str(e))

        return ToolResult(success=False, error=f"Unknown file operation: {operation}")

    def _is_path_allowed(self, path: Path) -> bool:
        """检查路径是否在允许范围内"""
        abs_path = path.resolve()
        for forbidden in self.FORBIDDEN_PATHS:
            try:
                if str(abs_path).startswith(forbidden):
                    return False
            except Exception:
                pass
        # 必须是真实父子路径，避免 /allowed_fake 通过字符串前缀检查。
        for allowed in self.allowed_dirs:
            try:
                allowed_path = Path(allowed).resolve()
                if abs_path == allowed_path or allowed_path in abs_path.parents:
                    return True
            except Exception:
                pass
        return False

    # ── 网页操作 ──

    def _execute_web(self, operation: str, target: str,
                     input_data: Dict, task_id: Optional[str]) -> ToolResult:
        """执行网页操作"""
        if operation == "fetch":
            try:
                url = target
                if urllib.parse.urlparse(url).scheme not in ("http", "https"):
                    return ToolResult(success=False, error="Only http/https URLs are allowed")
                req = urllib.request.Request(url, headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
                })
                with urllib.request.urlopen(req, timeout=10) as resp:
                    content = resp.read().decode("utf-8", errors="replace")
                    # 截断过长内容
                    if len(content) > 50000:
                        content = content[:50000] + "\n[内容已截断]"
                    return ToolResult(success=True, data={
                        "url": url,
                        "status": resp.status,
                        "content": content,
                    })
            except Exception as e:
                return ToolResult(success=False, error=str(e))

        elif operation == "search":
            # 简化搜索：使用 DuckDuckGo HTML 页面
            try:
                query = urllib.parse.quote(input_data.get("query", target))
                url = f"https://html.duckduckgo.com/html/?q={query}"
                req = urllib.request.Request(url, headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
                })
                with urllib.request.urlopen(req, timeout=15) as resp:
                    content = resp.read().decode("utf-8", errors="replace")
                    return ToolResult(success=True, data={
                        "query": input_data.get("query", target),
                        "results_page": content[:30000],
                    })
            except Exception as e:
                return ToolResult(success=False, error=str(e))

        return ToolResult(success=False, error=f"Unknown web operation: {operation}")

    # ── 代码执行 ──

    def _execute_code(self, operation: str, target: str,
                      input_data: Dict, task_id: Optional[str]) -> ToolResult:
        """代码执行必须由独立 tool-worker 提供；主进程内保持关闭。"""
        return ToolResult(
            success=False,
            error="code.execute is disabled until an isolated tool-worker is installed",
        )

    # ── 系统命令 ──

    def _execute_system(self, operation: str, target: str,
                        input_data: Dict, task_id: Optional[str]) -> ToolResult:
        """执行系统命令（极其受限）"""
        if operation == "shell":
            command = input_data.get("command", target)
            parts = command.split()
            if not parts:
                return ToolResult(success=False, error="Empty command")

            cmd = parts[0].lower()
            if cmd not in self.ALLOWED_SHELL_COMMANDS:
                return ToolResult(success=False, error=f"Command not allowed: {cmd}")

            try:
                result = subprocess.run(
                    parts,
                    capture_output=True,
                    text=True,
                    timeout=5,
                    cwd=os.getcwd(),
                )
                return ToolResult(success=True, data={
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "returncode": result.returncode,
                })
            except subprocess.TimeoutExpired:
                return ToolResult(success=False, partial=True, error="Command timed out")
            except Exception as e:
                return ToolResult(success=False, error=str(e))

        return ToolResult(success=False, error=f"Unknown system operation: {operation}")
