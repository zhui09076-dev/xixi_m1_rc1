"""系统监控"""
import os
import psutil
from typing import Dict


class SystemMonitor:
    """监控系统资源，防止西西抢占全部资源"""

    def __init__(self, max_cpu_percent: float = 50.0, max_memory_mb: float = 2048.0):
        self.max_cpu = max_cpu_percent
        self.max_memory = max_memory_mb
        self._process = psutil.Process(os.getpid())

    def get_stats(self) -> Dict:
        mem = self._process.memory_info()
        return {
            "cpu_percent": self._process.cpu_percent(interval=0.1),
            "memory_mb": mem.rss / (1024 * 1024),
            "memory_percent": self._process.memory_percent(),
            "threads": self._process.num_threads(),
        }

    def is_over_limit(self) -> bool:
        stats = self.get_stats()
        return stats["cpu_percent"] > self.max_cpu or stats["memory_mb"] > self.max_memory

    def check_and_throttle(self):
        """如果超过限制，建议减速"""
        if self.is_over_limit():
            return {"throttle": True, "reason": "resource_limit", "stats": self.get_stats()}
        return {"throttle": False, "stats": self.get_stats()}
