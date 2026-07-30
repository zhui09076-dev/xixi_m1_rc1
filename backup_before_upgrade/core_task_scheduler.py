"""任务调度器 v5 — 重/轻任务限制仅作用于认知任务"""
import hashlib
import json
from enum import Enum
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from datetime import datetime
from core.database import Database


class TaskType(Enum):
    HEAVY = "heavy"
    LIGHT = "light"
    UI = "ui"
    SYSTEM = "system"
    IO = "io"
    LOG = "log"


class TaskStatus(Enum):
    QUEUED = "queued"
    WAITING_CONFIRMATION = "waiting_confirmation"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Step:
    id: str
    description: str
    status: str = "pending"
    validation: str = ""
    output: str = ""


class TaskScheduler:
    """
    任务调度器：
    - 重任务 + 轻任务限制仅作用于认知任务（HEAVY/LIGHT）
    - UI、日志、数据库、下载、系统线程不受此限制，可并行
    """

    UNLIMITED_TYPES = {TaskType.UI, TaskType.SYSTEM, TaskType.IO, TaskType.LOG}

    def __init__(self, db: Database):
        self.db = db
        self.running_heavy: Optional[str] = None
        self.running_light: Optional[str] = None
        self._restore_state()

    def _restore_state(self):
        running = self.db.get_tasks(status="running")
        heavy_running = [t for t in running if t["type"] == "heavy"]
        light_running = [t for t in running if t["type"] == "light"]
        self.running_heavy = heavy_running[0]["id"] if heavy_running else None
        self.running_light = light_running[0]["id"] if light_running else None

    def submit(self, name: str, task_type: str, plan: List[Dict] = None,
               priority: int = 3, requires_confirm: bool = False,
               completion_definition: str = "", requested_by: str = "xixi",
               resource_budget: str = "") -> str:
        eid = hashlib.md5(f"{datetime.now().isoformat()}{name}".encode()).hexdigest()[:12]
        status = "waiting_confirmation" if requires_confirm else "queued"
        task = {
            "id": eid,
            "name": name,
            "type": task_type,
            "status": status,
            "priority": priority,
            "weight": "heavy" if task_type == "heavy" else "light",
            "completion_definition": completion_definition,
            "requires_confirm": requires_confirm,
            "confirmation_state": "pending" if requires_confirm else "confirmed",
            "resource_budget": resource_budget,
            "plan": plan or [],
            "checkpoint": "",
            "requested_by": requested_by,
            "owner": requested_by,
            "started_at": "",
            "completed_at": "",
            "failure_reason": "",
        }
        self.db.add_task(task)
        if not requires_confirm:
            self._schedule()
        return eid

    def confirm_task(self, task_id: str) -> bool:
        task = self.db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if not task:
            return False
        d = dict(task)
        if d["status"] != "waiting_confirmation":
            return False
        self.db.execute("UPDATE tasks SET status = 'queued', confirmation_state = 'confirmed' WHERE id = ?", (task_id,))
        self.db.commit()
        return True

    def _schedule(self):
        running = self.db.get_tasks(status="running")
        heavy_running = [t for t in running if t["type"] == "heavy"]
        light_running = [t for t in running if t["type"] == "light"]
        self.running_heavy = heavy_running[0]["id"] if heavy_running else None
        self.running_light = light_running[0]["id"] if light_running else None
        queued = self.db.get_tasks(status="queued")
        queued.sort(key=lambda t: t["priority"], reverse=True)
        for task in queued:
            if task["type"] == "heavy" and not self.running_heavy:
                self._start_task(task["id"])
                self.running_heavy = task["id"]
            elif task["type"] == "light" and not self.running_light:
                self._start_task(task["id"])
                self.running_light = task["id"]

    def _start_task(self, task_id: str):
        now = datetime.now().isoformat()
        self.db.execute("""
            UPDATE tasks SET status = 'running', started_at = ?, checkpoint = 'started' WHERE id = ?
        """, (now, task_id))
        self.db.commit()

    def complete_task(self, task_id: str, result: str = ""):
        now = datetime.now().isoformat()
        self.db.execute("""
            UPDATE tasks SET status = 'completed', completed_at = ?, checkpoint = ? WHERE id = ?
        """, (now, result, task_id))
        self.db.commit()
        self._clear_slot(task_id)
        self._schedule()

    def fail_task(self, task_id: str, reason: str = ""):
        now = datetime.now().isoformat()
        self.db.execute("""
            UPDATE tasks SET status = 'failed', failure_reason = ?, completed_at = ?, checkpoint = ? WHERE id = ?
        """, (reason, now, reason, task_id))
        self.db.commit()
        self._clear_slot(task_id)
        self._schedule()

    def cancel_task(self, task_id: str):
        self.db.execute("UPDATE tasks SET status = 'cancelled' WHERE id = ?", (task_id,))
        self.db.commit()
        self._clear_slot(task_id)
        self._schedule()

    def _clear_slot(self, task_id: str):
        if self.running_heavy == task_id:
            self.running_heavy = None
        if self.running_light == task_id:
            self.running_light = None

    def get_queue_status(self) -> Dict:
        running = self.db.get_tasks(status="running")
        queued = self.db.get_tasks(status="queued")
        waiting = self.db.get_tasks(status="waiting_confirmation")
        return {
            "running_heavy": self.running_heavy,
            "running_light": self.running_light,
            "running_count": len(running),
            "queued_count": len(queued),
            "waiting_confirmation_count": len(waiting),
            "can_accept_heavy": self.running_heavy is None,
            "can_accept_light": self.running_light is None,
        }

    def save_checkpoint(self, task_id: str, checkpoint: str):
        self.db.update_task_status(task_id, "running", checkpoint=checkpoint)

    def is_cognitive_task(self, task_type: str) -> bool:
        return task_type in ("heavy", "light")

    def can_run_now(self, task_type: str) -> bool:
        if not self.is_cognitive_task(task_type):
            return True
        if task_type == "heavy":
            return self.running_heavy is None
        if task_type == "light":
            return self.running_light is None
        return True
