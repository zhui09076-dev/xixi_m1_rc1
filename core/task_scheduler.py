"""
Task Scheduler - 认知调度：1重 + 1轻
支持: 状态同步到UI、重启恢复、resume token、任务排队/切换/暂停
"""
from __future__ import annotations

import json
import logging
import sqlite3
import threading
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Callable

logger = logging.getLogger("xixi.task")


class TaskStatus(Enum):
    QUEUED = "queued"
    RUNNING = "running"
    PAUSED = "paused"
    WAITING_PERMISSION = "waiting_permission"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskWeight(Enum):
    HEAVY = "heavy"    # 重认知任务：长文生成、大型文件整理、深度研究、AIGC生成
    LIGHT = "light"    # 轻任务：等待下载、提醒、简单检索


@dataclass
class Task:
    """任务对象"""
    id: str
    name: str
    description: str = ""
    weight: TaskWeight = TaskWeight.LIGHT
    status: TaskStatus = TaskStatus.QUEUED
    capability: str = ""          # 所需能力
    operation: str = ""           # 具体操作
    target: str = ""              # 操作目标
    input_data: Dict = field(default_factory=dict)
    result: Any = None
    error: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    resume_token: Optional[str] = None
    progress: float = 0.0         # 0.0-1.0
    parent_task_id: Optional[str] = None
    requires_confirm: bool = False
    confirmed: bool = False
    cancelled: bool = False

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "weight": self.weight.value,
            "status": self.status.value,
            "capability": self.capability,
            "operation": self.operation,
            "target": self.target,
            "input_data": self.input_data,
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "resume_token": self.resume_token,
            "progress": self.progress,
            "parent_task_id": self.parent_task_id,
            "requires_confirm": self.requires_confirm,
            "confirmed": self.confirmed,
            "cancelled": self.cancelled,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "Task":
        return cls(
            id=data["id"],
            name=data["name"],
            description=data.get("description", ""),
            weight=TaskWeight(data.get("weight", "light")),
            status=TaskStatus(data.get("status", "queued")),
            capability=data.get("capability", ""),
            operation=data.get("operation", ""),
            target=data.get("target", ""),
            input_data=data.get("input_data", {}),
            result=data.get("result"),
            error=data.get("error"),
            created_at=data.get("created_at", datetime.now(timezone.utc).isoformat()),
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
            resume_token=data.get("resume_token"),
            progress=data.get("progress", 0.0),
            parent_task_id=data.get("parent_task_id"),
            requires_confirm=data.get("requires_confirm", False),
            confirmed=data.get("confirmed", False),
            cancelled=data.get("cancelled", False),
        )


class TaskScheduler:
    """
    任务调度器

    规则:
    - 同时只运行 1 个重认知任务
    - 1 个轻任务可并行
    - 日志、数据库刷新、UI更新不计为重任务
    - 新重任务可以排队、切换或暂停旧任务
    - 任务状态实时发送到 UI
    - requires_confirm=true 的任务确认前不得进入 running
    """

    def __init__(self, db_path: str = "data/xixi.db"):
        self.db_path = getattr(db_path, "path", db_path)
        self._local = threading.local()
        self._lock = threading.Lock()
        self._ensure_tables()

        # 运行时状态
        self._heavy_task: Optional[Task] = None    # 当前重任务
        self._light_task: Optional[Task] = None    # 当前轻任务
        self._queue: List[Task] = []               # 等待队列
        self._all_tasks: Dict[str, Task] = {}      # 所有任务索引

        # 回调
        self.on_status_change: Optional[Callable[[Task], None]] = None

        # 恢复持久化任务
        self._restore_tasks()

    def _get_connection(self) -> sqlite3.Connection:
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self._local.conn.row_factory = sqlite3.Row
        return self._local.conn

    def _ensure_tables(self) -> None:
        conn = self._get_connection()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS xixi_tasks (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                weight TEXT NOT NULL CHECK(weight IN ('heavy', 'light')),
                status TEXT NOT NULL CHECK(status IN ('queued', 'running', 'paused', 'waiting_permission', 'completed', 'failed', 'cancelled')),
                capability TEXT,
                operation TEXT,
                target TEXT,
                input_data TEXT,
                result TEXT,
                error TEXT,
                created_at TEXT NOT NULL,
                started_at TEXT,
                completed_at TEXT,
                resume_token TEXT,
                progress REAL DEFAULT 0.0,
                parent_task_id TEXT,
                requires_confirm INTEGER DEFAULT 0,
                confirmed INTEGER DEFAULT 0,
                cancelled INTEGER DEFAULT 0
            )
        """)
        conn.commit()

    def _persist_task(self, task: Task) -> None:
        """持久化任务到数据库"""
        with self._lock:
            conn = self._get_connection()
            conn.execute("""
                INSERT OR REPLACE INTO xixi_tasks 
                (id, name, description, weight, status, capability, operation, target,
                 input_data, result, error, created_at, started_at, completed_at,
                 resume_token, progress, parent_task_id, requires_confirm, confirmed, cancelled)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                task.id, task.name, task.description, task.weight.value, task.status.value,
                task.capability, task.operation, task.target,
                json.dumps(task.input_data), json.dumps(task.result) if task.result else None,
                task.error, task.created_at, task.started_at, task.completed_at,
                task.resume_token, task.progress, task.parent_task_id,
                int(task.requires_confirm), int(task.confirmed), int(task.cancelled)
            ))
            conn.commit()

    def _restore_tasks(self) -> None:
        """从数据库恢复未完成的任务"""
        conn = self._get_connection()
        cursor = conn.execute("""
            SELECT * FROM xixi_tasks 
            WHERE status IN ('queued', 'running', 'paused', 'waiting_permission')
            ORDER BY created_at ASC
        """)
        for row in cursor.fetchall():
            task = Task.from_dict(dict(row))
            self._all_tasks[task.id] = task
            if task.status == TaskStatus.QUEUED:
                self._queue.append(task)
            elif task.status == TaskStatus.RUNNING:
                # 恢复时标记为 paused（因为程序重启了）
                task.status = TaskStatus.PAUSED
                task.resume_token = f"resume_{uuid.uuid4().hex[:8]}"
                self._persist_task(task)
                self._queue.append(task)

        if self._queue:
            logger.info("Restored %d tasks from database", len(self._queue))

    # ── 任务管理 ──

    def submit_task(
        self,
        name: str,
        description: str = "",
        weight: TaskWeight = TaskWeight.LIGHT,
        capability: str = "",
        operation: str = "",
        target: str = "",
        input_data: Optional[Dict] = None,
        requires_confirm: bool = False,
        parent_task_id: Optional[str] = None,
    ) -> Task:
        """
        提交任务。

        返回: Task 对象
        """
        task = Task(
            id=f"task_{uuid.uuid4().hex[:8]}",
            name=name,
            description=description,
            weight=weight if isinstance(weight, TaskWeight) else TaskWeight(weight),
            capability=capability,
            operation=operation,
            target=target,
            input_data=input_data or {},
            requires_confirm=requires_confirm,
            parent_task_id=parent_task_id,
        )

        self._all_tasks[task.id] = task

        if requires_confirm and not task.confirmed:
            task.status = TaskStatus.WAITING_PERMISSION
            self._persist_task(task)
            self._notify_status_change(task)
            logger.info("Task %s waiting for confirmation", task.id)
            return task

        # 检查是否可以立即执行
        if weight == TaskWeight.HEAVY:
            if self._heavy_task is None or self._heavy_task.status != TaskStatus.RUNNING:
                self._start_task(task)
            else:
                # 排队或暂停旧任务
                self._queue.append(task)
                task.status = TaskStatus.QUEUED
                self._persist_task(task)
                self._notify_status_change(task)
                logger.info("Heavy task %s queued (current: %s)", task.id, self._heavy_task.id)
        else:
            if self._light_task is None or self._light_task.status != TaskStatus.RUNNING:
                self._start_task(task)
            else:
                self._queue.append(task)
                task.status = TaskStatus.QUEUED
                self._persist_task(task)
                self._notify_status_change(task)

        return task

    def confirm_task(self, task_id: str) -> bool:
        """用户确认执行任务"""
        if task_id not in self._all_tasks:
            return False

        task = self._all_tasks[task_id]
        if task.status != TaskStatus.WAITING_PERMISSION:
            return False

        task.confirmed = True
        task.status = TaskStatus.QUEUED
        self._persist_task(task)

        # 尝试启动
        if task.weight == TaskWeight.HEAVY and (self._heavy_task is None or self._heavy_task.status != TaskStatus.RUNNING):
            self._start_task(task)
        elif task.weight == TaskWeight.LIGHT and (self._light_task is None or self._light_task.status != TaskStatus.RUNNING):
            self._start_task(task)

        self._notify_status_change(task)
        return True

    def _start_task(self, task: Task) -> None:
        """启动任务"""
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.now(timezone.utc).isoformat()
        self._persist_task(task)

        if task.weight == TaskWeight.HEAVY:
            self._heavy_task = task
        else:
            self._light_task = task

        self._notify_status_change(task)
        logger.info("Task %s started (weight=%s)", task.id, task.weight.value)

    def complete_task(self, task_id: str, result: Any = None) -> None:
        """完成任务"""
        if task_id not in self._all_tasks:
            return

        task = self._all_tasks[task_id]
        task.status = TaskStatus.COMPLETED
        task.result = result
        task.completed_at = datetime.now(timezone.utc).isoformat()
        task.progress = 1.0
        self._persist_task(task)

        # 清理运行时引用
        if self._heavy_task and self._heavy_task.id == task_id:
            self._heavy_task = None
        if self._light_task and self._light_task.id == task_id:
            self._light_task = None

        self._notify_status_change(task)
        logger.info("Task %s completed", task.id)

        # 尝试启动队列中的下一个任务
        self._process_queue()

    def fail_task(self, task_id: str, error: str) -> None:
        """标记任务失败"""
        if task_id not in self._all_tasks:
            return

        task = self._all_tasks[task_id]
        task.status = TaskStatus.FAILED
        task.error = error
        task.completed_at = datetime.now(timezone.utc).isoformat()
        self._persist_task(task)

        if self._heavy_task and self._heavy_task.id == task_id:
            self._heavy_task = None
        if self._light_task and self._light_task.id == task_id:
            self._light_task = None

        self._notify_status_change(task)
        logger.error("Task %s failed: %s", task.id, error)

        self._process_queue()

    def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        if task_id not in self._all_tasks:
            return False

        task = self._all_tasks[task_id]
        task.cancelled = True
        task.status = TaskStatus.CANCELLED
        task.completed_at = datetime.now(timezone.utc).isoformat()

        # 生成 resume token（如果任务可以恢复）
        if task.weight == TaskWeight.HEAVY and task.progress > 0:
            task.resume_token = f"resume_{uuid.uuid4().hex[:8]}"

        self._persist_task(task)

        if self._heavy_task and self._heavy_task.id == task_id:
            self._heavy_task = None
        if self._light_task and self._light_task.id == task_id:
            self._light_task = None

        self._notify_status_change(task)
        logger.info("Task %s cancelled (resume_token=%s)", task.id, task.resume_token)

        self._process_queue()
        return True

    def pause_task(self, task_id: str) -> bool:
        """暂停任务"""
        if task_id not in self._all_tasks:
            return False

        task = self._all_tasks[task_id]
        if task.status != TaskStatus.RUNNING:
            return False

        task.status = TaskStatus.PAUSED
        task.resume_token = f"resume_{uuid.uuid4().hex[:8]}"
        self._persist_task(task)

        if self._heavy_task and self._heavy_task.id == task_id:
            self._heavy_task = None
        if self._light_task and self._light_task.id == task_id:
            self._light_task = None

        self._notify_status_change(task)
        logger.info("Task %s paused (resume_token=%s)", task.id, task.resume_token)

        self._process_queue()
        return True

    def resume_task(self, resume_token: str) -> Optional[Task]:
        """使用 resume token 恢复任务"""
        for task in self._all_tasks.values():
            if task.resume_token == resume_token and task.status in (TaskStatus.PAUSED, TaskStatus.CANCELLED):
                task.status = TaskStatus.QUEUED
                task.resume_token = None
                self._persist_task(task)
                self._queue.append(task)
                self._process_queue()
                self._notify_status_change(task)
                logger.info("Task %s resumed from token %s", task.id, resume_token)
                return task
        return None

    def update_progress(self, task_id: str, progress: float) -> None:
        """更新任务进度"""
        if task_id in self._all_tasks:
            task = self._all_tasks[task_id]
            task.progress = max(0.0, min(1.0, progress))
            self._persist_task(task)
            self._notify_status_change(task)

    def _process_queue(self) -> None:
        """处理等待队列"""
        # 按优先级排序：heavy 优先？还是 FIFO？
        # 这里使用 FIFO，但 heavy 任务如果队列中有多个，可能需要策略
        for task in list(self._queue):
            if task.status != TaskStatus.QUEUED:
                continue

            if task.weight == TaskWeight.HEAVY:
                if self._heavy_task is None or self._heavy_task.status != TaskStatus.RUNNING:
                    self._queue.remove(task)
                    self._start_task(task)
            else:
                if self._light_task is None or self._light_task.status != TaskStatus.RUNNING:
                    self._queue.remove(task)
                    self._start_task(task)

            # 如果两个槽都满了，停止处理
            if (self._heavy_task and self._heavy_task.status == TaskStatus.RUNNING and
                self._light_task and self._light_task.status == TaskStatus.RUNNING):
                break

    def _notify_status_change(self, task: Task) -> None:
        """通知状态变更"""
        if self.on_status_change:
            try:
                self.on_status_change(task)
            except Exception as e:
                logger.error("Status change callback error: %s", e)

    # ── 查询 ──

    def get_task(self, task_id: str) -> Optional[Task]:
        return self._all_tasks.get(task_id)

    def get_active_tasks(self) -> List[Task]:
        """获取活跃任务"""
        return [t for t in self._all_tasks.values() 
                if t.status in (TaskStatus.RUNNING, TaskStatus.PAUSED, TaskStatus.WAITING_PERMISSION)]

    def get_all_tasks(self, limit: int = 100) -> List[Task]:
        """获取所有任务"""
        return list(self._all_tasks.values())[:limit]

    def get_queue(self) -> List[Task]:
        return [t for t in self._queue if t.status == TaskStatus.QUEUED]

    def get_status_summary(self) -> Dict:
        """获取状态摘要（用于 UI 显示）"""
        return {
            "heavy_running": self._heavy_task.to_dict() if self._heavy_task else None,
            "light_running": self._light_task.to_dict() if self._light_task else None,
            "queue_length": len([t for t in self._queue if t.status == TaskStatus.QUEUED]),
            "total_active": len(self.get_active_tasks()),
            "total_completed": len([t for t in self._all_tasks.values() if t.status == TaskStatus.COMPLETED]),
            "total_failed": len([t for t in self._all_tasks.values() if t.status == TaskStatus.FAILED]),
            "total_cancelled": len([t for t in self._all_tasks.values() if t.status == TaskStatus.CANCELLED]),
        }

    # ── 清理 ──

    def cleanup(self) -> None:
        """清理：暂停所有运行中任务"""
        for task in list(self._all_tasks.values()):
            if task.status == TaskStatus.RUNNING:
                self.pause_task(task.id)

        if hasattr(self._local, "conn") and self._local.conn:
            self._local.conn.close()
            self._local.conn = None


# RC3 compatibility interface
from . import task_compat as _task_compat
TaskScheduler.submit = _task_compat.submit
TaskScheduler.is_cognitive_task = _task_compat.is_cognitive_task
TaskScheduler.get_queue_status = _task_compat.get_queue_status
