"""
Permission Gateway - 四级风险权限管理
ordinary / scoped / outbound_private / irreversible
"""
from __future__ import annotations

import json
import logging
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger("xixi.permission")


class RiskLevel(Enum):
    """四级风险等级"""
    ORDINARY = "ordinary"           # 公开网页、普通只读状态
    SCOPED = "scoped"               # 已授权目录内的可逆操作
    OUTBOUND_PRIVATE = "outbound_private"  # 私人文件离开本机
    IRREVERSIBLE = "irreversible"   # 永久删除、覆盖唯一原件、关键安全设置


class PermissionDecision(Enum):
    """权限决策"""
    ALLOW_ONCE = "allow_once"
    ALLOW_SCOPE = "allow_scope"
    DENY = "deny"


class PermissionGateway:
    """
    权限网关

    核心规则:
    - ordinary 和已授权 scoped: 直接放行，不反复弹窗
    - outbound_private 和 irreversible: 必须进入真实权限确认
    - 拒绝后工具绝对不能执行
    - 所有操作记录审计日志
    """

    def __init__(self, db_path: str = "data/xixi.db"):
        self.db_path = db_path
        self._local = threading.local()
        self._lock = threading.Lock()
        self._pending_callbacks: Dict[str, Callable] = {}  # 等待用户确认的回调
        self._scope_grants: Dict[str, Dict] = {}  # 范围授权缓存
        self._ensure_tables()

    def _get_connection(self) -> sqlite3.Connection:
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self._local.conn.row_factory = sqlite3.Row
        return self._local.conn

    def _ensure_tables(self) -> None:
        conn = self._get_connection()
        # 权限请求记录
        conn.execute("""
            CREATE TABLE IF NOT EXISTS xixi_permission_requests (
                id TEXT PRIMARY KEY,
                risk_level TEXT NOT NULL,
                operation TEXT NOT NULL,
                target TEXT NOT NULL,
                scope TEXT,
                reason TEXT,
                status TEXT DEFAULT 'pending' CHECK(status IN ('pending', 'granted', 'denied', 'expired')),
                decision TEXT CHECK(decision IN ('allow_once', 'allow_scope', 'deny')),
                created_at TEXT NOT NULL,
                resolved_at TEXT,
                resolved_by TEXT,
                session_id TEXT,
                trace_id TEXT
            )
        """)
        # 审计日志
        conn.execute("""
            CREATE TABLE IF NOT EXISTS xixi_audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                task_id TEXT,
                provider TEXT,
                domain TEXT,
                operation TEXT,
                data_category TEXT,
                outbound_data TEXT,
                authorization_id TEXT,
                result TEXT,
                error TEXT
            )
        """)
        conn.commit()

    # ── 风险评估 ──

    def assess_risk(self, capability: str, operation: str, target: str, 
                    input_data: Dict) -> RiskLevel:
        """
        评估操作风险等级。

        规则:
        - 公开网页读取 -> ordinary
        - 本地只读状态查询 -> ordinary
        - 已授权目录内文件创建/修改 -> scoped
        - 私人文件外发 -> outbound_private
        - 永久删除、覆盖唯一原件 -> irreversible
        """
        # 永久删除类
        if operation in ("delete", "purge", "overwrite", "format"):
            if input_data.get("permanent", False) or input_data.get("unique_original", False):
                return RiskLevel.IRREVERSIBLE

        # 外发类
        if operation in ("send", "upload", "publish", "email", "share"):
            if input_data.get("contains_private", False) or input_data.get("is_private_file", False):
                return RiskLevel.OUTBOUND_PRIVATE

        # 写操作
        if operation in ("write", "modify", "create", "update"):
            # 检查是否在已授权范围内
            if self._is_in_authorized_scope(capability, target):
                return RiskLevel.SCOPED

        # 读操作
        if operation in ("read", "query", "search", "list"):
            return RiskLevel.ORDINARY

        # 默认保守
        return RiskLevel.SCOPED

    def _is_in_authorized_scope(self, capability: str, target: str) -> bool:
        """检查目标是否在已授权范围内"""
        # 简化实现：检查 scope_grants 缓存
        for grant in self._scope_grants.values():
            if grant.get("capability") == capability:
                allowed_targets = grant.get("allowed_targets", [])
                if target in allowed_targets or "*" in allowed_targets:
                    return True
        return False

    # ── 权限检查 ──

    def check_permission(
        self,
        capability: str,
        operation: str,
        target: str,
        input_data: Dict,
        reason: str = "",
        session_id: str = "",
        trace_id: str = "",
    ) -> Tuple[bool, Optional[str], RiskLevel]:
        """
        检查权限。

        返回: (是否允许, 权限请求ID或None, 风险等级)

        - ordinary: 直接返回 True
        - scoped: 检查是否已有授权，有直接返回 True
        - outbound_private/irreversible: 返回 False + 请求ID，等待用户确认
        """
        risk = self.assess_risk(capability, operation, target, input_data)

        if risk == RiskLevel.ORDINARY:
            self._log_audit(capability, operation, target, "granted_auto", risk.value)
            return True, None, risk

        if risk == RiskLevel.SCOPED:
            if self._is_in_authorized_scope(capability, target):
                self._log_audit(capability, operation, target, "granted_scope", risk.value)
                return True, None, risk

        # 需要用户确认
        perm_id = f"perm_{uuid.uuid4().hex[:8]}"
        now = datetime.now(timezone.utc).isoformat()

        with self._lock:
            conn = self._get_connection()
            conn.execute("""
                INSERT INTO xixi_permission_requests 
                (id, risk_level, operation, target, scope, reason, status, created_at, session_id, trace_id)
                VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?)
            """, (perm_id, risk.value, operation, target, 
                  json.dumps(input_data), reason, now, session_id, trace_id))
            conn.commit()

        logger.info("Permission required: %s %s -> %s (risk=%s)", 
                    capability, operation, target, risk.value)
        return False, perm_id, risk

    def resolve_permission(
        self,
        perm_id: str,
        decision: PermissionDecision,
        resolved_by: str = "user",
    ) -> bool:
        """
        用户做出权限决策。

        返回: 是否允许执行
        """
        now = datetime.now(timezone.utc).isoformat()

        with self._lock:
            conn = self._get_connection()
            cursor = conn.execute(
                "SELECT * FROM xixi_permission_requests WHERE id = ? AND status = 'pending'",
                (perm_id,)
            )
            row = cursor.fetchone()
            if not row:
                logger.warning("Permission request not found or already resolved: %s", perm_id)
                return False

            req = dict(row)
            status = "granted" if decision != PermissionDecision.DENY else "denied"

            conn.execute("""
                UPDATE xixi_permission_requests 
                SET status = ?, decision = ?, resolved_at = ?, resolved_by = ?
                WHERE id = ?
            """, (status, decision.value, now, resolved_by, perm_id))
            conn.commit()

        allowed = decision != PermissionDecision.DENY

        # 记录审计
        self._log_audit(
            req.get("operation", ""),
            req.get("target", ""),
            req.get("scope", ""),
            status,
            req.get("risk_level", ""),
            authorization_id=perm_id,
        )

        # 如果是 allow_scope，缓存授权
        if decision == PermissionDecision.ALLOW_SCOPE:
            self._scope_grants[perm_id] = {
                "capability": req.get("operation", "").split(".")[0] if "." in req.get("operation", "") else req.get("operation", ""),
                "allowed_targets": [req.get("target", "")],
                "granted_at": now,
            }

        logger.info("Permission %s resolved: %s = %s", perm_id, decision.value, allowed)
        return allowed

    def get_permission_details(self, perm_id: str) -> Optional[Dict]:
        """获取权限请求详情（用于 UI 弹窗显示）"""
        conn = self._get_connection()
        cursor = conn.execute(
            "SELECT * FROM xixi_permission_requests WHERE id = ?", (perm_id,)
        )
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None

    # ── 审计日志 ──

    def _log_audit(
        self,
        operation: str,
        target: str,
        scope: str,
        result: str,
        risk_level: str,
        task_id: Optional[str] = None,
        provider: str = "system",
        domain: str = "local",
        data_category: str = "operation",
        outbound_data: Optional[str] = None,
        authorization_id: Optional[str] = None,
        error: Optional[str] = None,
    ) -> None:
        """记录审计日志"""
        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            conn = self._get_connection()
            conn.execute("""
                INSERT INTO xixi_audit_logs 
                (timestamp, task_id, provider, domain, operation, data_category,
                 outbound_data, authorization_id, result, error)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (now, task_id, provider, domain, operation, data_category,
                  outbound_data, authorization_id, result, error))
            conn.commit()

    def get_audit_logs(self, limit: int = 100) -> List[Dict]:
        """获取审计日志"""
        conn = self._get_connection()
        cursor = conn.execute("""
            SELECT * FROM xixi_audit_logs ORDER BY timestamp DESC LIMIT ?
        """, (limit,))
        return [dict(row) for row in cursor.fetchall()]

    # ── 清理 ──

    def cleanup(self) -> None:
        if hasattr(self._local, "conn") and self._local.conn:
            self._local.conn.close()
            self._local.conn = None


# RC3 compatibility interface
from .permission_compat import (ActionRequest, AuthToken, PermissionCategory, PermissionResult, install as _install_compat)
_install_compat(PermissionGateway)
