"""版本注册表"""
from dataclasses import dataclass, field
from typing import Dict, List
from datetime import datetime


@dataclass
class VersionRecord:
    package_id: str
    package_type: str  # soul | body | extension
    version: str
    path: str
    active: bool = True
    installed_at: str = ""
    updated_at: str = ""

    def __post_init__(self):
        if not self.installed_at:
            self.installed_at = datetime.now().isoformat()
        if not self.updated_at:
            self.updated_at = datetime.now().isoformat()


class VersionRegistry:
    """管理 Soul/Body/Extension 的版本记录"""

    def __init__(self):
        self._records: Dict[str, VersionRecord] = {}

    def register(self, record: VersionRecord):
        self._records[record.package_id] = record

    def get(self, package_id: str) -> VersionRecord:
        return self._records.get(package_id)

    def list_by_type(self, package_type: str) -> List[VersionRecord]:
        return [r for r in self._records.values() if r.package_type == package_type]

    def set_active(self, package_id: str, active: bool = True):
        rec = self._records.get(package_id)
        if rec:
            rec.active = active
            rec.updated_at = datetime.now().isoformat()

    def rollback(self, package_id: str, previous_version: str, previous_path: str):
        """回滚到指定版本"""
        rec = self._records.get(package_id)
        if rec:
            rec.version = previous_version
            rec.path = previous_path
            rec.updated_at = datetime.now().isoformat()
            return True
        return False
