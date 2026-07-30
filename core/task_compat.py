"""RC3 TaskScheduler compatibility helpers."""
import uuid

from .task_scheduler import TaskStatus, TaskWeight


def submit(self, name: str, task_type: str, **kwargs) -> str:
    if task_type not in ("heavy", "light"):
        return f"task_{uuid.uuid4().hex[:8]}"
    task = self.submit_task(
        name=name,
        weight=TaskWeight(task_type),
        requires_confirm=kwargs.get("requires_confirm", False),
    )
    return task.id


def is_cognitive_task(self, task_type: str) -> bool:
    return task_type in ("heavy", "light")


def get_queue_status(self):
    return {
        "running_heavy": self._heavy_task.id if self._heavy_task else None,
        "running_light": self._light_task.id if self._light_task else None,
        "running_count": int(self._heavy_task is not None) + int(self._light_task is not None),
        "queued_count": len(self.get_queue()),
        "waiting_confirmation_count": sum(
            task.status == TaskStatus.WAITING_PERMISSION
            for task in self._all_tasks.values()
        ),
        "can_accept_heavy": self._heavy_task is None,
        "can_accept_light": self._light_task is None,
    }
