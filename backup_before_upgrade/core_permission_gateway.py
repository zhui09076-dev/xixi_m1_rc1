"""权限网关 v5 — 四类行为模型"""
import os
from pathlib import Path
from enum import Enum
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from core.database import Database


class PermissionCategory(Enum):
    """四类权限行为"""
    ORDINARY = "ordinary"           # 公开网页、只读状态、无私人数据外发
    SCOPED = "scoped"               # 授权根目录内的可逆操作
    OUTBOUND_PRIVATE = "outbound_private"  # 私人数据离开本机
    IRREVERSIBLE = "irreversible"   # 永久删除、覆盖唯一原件、关键安全设置


@dataclass
class ActionRequest:
    action_id: str
    action_type: str
    target: str
    scope: str
    data_category: str
    risk_level: str
    requested_by: str
    reason: str
    created_at: str


@dataclass
class AuthToken:
    token_id: str
    action_id: str
    target: str
    scope: str
    data_category: str
    expires_at: str
    single_use: bool = True
    used_at: str = ""


@dataclass
class PermissionResult:
    allowed: bool
    category: str
    requires_confirm: bool
    reason: str = ""
    audit_id: str = ""
    token: Optional[AuthToken] = None


class PermissionGateway:
    """
    权限网关（四类行为模型）：
    - ordinary: 公开联网默认允许，不弹窗
    - scoped: 授权目录内正常读写，不弹窗
    - outbound_private: 私人数据外发需要授权（一次性确认）
    - irreversible: 发送/发布/永久删除/安装/付款/不可逆操作需要确认
    """

    def __init__(self, db: Database, authorized_paths: List[str] = None):
        self.db = db
        self._authorized_paths: List[Path] = []
        if authorized_paths:
            for p in authorized_paths:
                self._authorized_paths.append(Path(p).resolve())
        else:
            for p in ["assets", "data", "logs", "projects", "workspace", "temp",
                      "extensions", "souls", "bodies", "development"]:
                self._authorized_paths.append(Path(p).resolve())
        self._tokens: Dict[str, AuthToken] = {}

    def _resolve_path(self, target: str) -> Path:
        p = Path(target)
        if p.is_absolute():
            return p.resolve()
        return Path.cwd().joinpath(p).resolve()

    def _is_authorized_path(self, target: str) -> bool:
        """使用真实父子目录关系判断"""
        try:
            target_path = self._resolve_path(target)
            target_str = str(target_path).lower().replace("\\", "/")
            if "windows/system32" in target_str or "c:/windows" in target_str:
                return False
            for auth in self._authorized_paths:
                try:
                    target_path.relative_to(auth)
                    return True
                except ValueError:
                    continue
            return False
        except Exception:
            return False

    def _is_web_url(self, target: str) -> bool:
        return target.startswith(("http://", "https://"))

    def _is_private_data(self, data_category: str) -> bool:
        private_categories = {"personal_info", "password", "private_key",
                              "conversation_history", "memory", "relationship_data"}
        return data_category.lower() in private_categories

    def _is_irreversible_action(self, action_type: str) -> bool:
        irreversible = {"send", "publish", "delete_permanent", "install",
                        "execute", "payment", "overwrite_unique", "security_change"}
        return action_type.lower() in irreversible

    def request_permission(self, action: ActionRequest) -> PermissionResult:
        """
        请求权限，按四类行为模型处理：
        1. ordinary -> 默认允许
        2. scoped -> 检查是否在授权目录内
        3. outbound_private -> 需要一次性确认
        4. irreversible -> 需要确认
        """
        now = datetime.now().isoformat()
        audit_id = f"audit-{now}"

        # 1. 不可逆操作
        if self._is_irreversible_action(action.action_type):
            return PermissionResult(
                allowed=False,
                category=PermissionCategory.IRREVERSIBLE.value,
                requires_confirm=True,
                reason=f"不可逆操作 '{action.action_type}' 需要用户确认",
                audit_id=audit_id,
            )

        # 2. 私人数据外发
        if self._is_private_data(action.data_category) or action.scope == "outbound":
            return PermissionResult(
                allowed=False,
                category=PermissionCategory.OUTBOUND_PRIVATE.value,
                requires_confirm=True,
                reason="私人数据离开本机需要授权",
                audit_id=audit_id,
            )

        # 3. 授权目录内操作
        if not self._is_web_url(action.target):
            if self._is_authorized_path(action.target):
                return PermissionResult(
                    allowed=True,
                    category=PermissionCategory.SCOPED.value,
                    requires_confirm=False,
                    reason="授权目录内操作",
                    audit_id=audit_id,
                )
            else:
                return PermissionResult(
                    allowed=False,
                    category=PermissionCategory.SCOPED.value,
                    requires_confirm=True,
                    reason="目标路径不在授权目录内",
                    audit_id=audit_id,
                )

        # 4. 普通公开联网
        return PermissionResult(
            allowed=True,
            category=PermissionCategory.ORDINARY.value,
            requires_confirm=False,
            reason="公开联网读取",
            audit_id=audit_id,
        )

    def confirm_with_token(self, action_id: str) -> Optional[AuthToken]:
        """为高风险操作生成一次性确认令牌"""
        token_id = f"tok-{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
        expires = (datetime.now() + timedelta(minutes=5)).isoformat()
        token = AuthToken(
            token_id=token_id, action_id=action_id,
            target="", scope="", data_category="",
            expires_at=expires, single_use=True,
        )
        self._tokens[token_id] = token
        return token

    def validate_token(self, token_id: str) -> bool:
        token = self._tokens.get(token_id)
        if not token:
            return False
        if token.single_use and token.used_at:
            return False
        if datetime.now().isoformat() > token.expires_at:
            return False
        token.used_at = datetime.now().isoformat()
        return True
