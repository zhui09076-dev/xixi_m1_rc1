"""系统资源监控"""

import psutil
from typing import Dict


class SystemMonitor:
    def get_status(self) -> Dict:
        return {
            "cpu_percent": psutil.cpu_percent(interval=0.1),
            "memory": psutil.virtual_memory()._asdict(),
            "disk": psutil.disk_usage("/")._asdict(),
        }

    def should_reduce_quality(self) -> bool:
        mem = psutil.virtual_memory()
        return mem.percent > 85
