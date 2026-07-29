"""
权限网关 v3
===========
- 10级权限
- ActionRequest + 一次性令牌
- 宽联网、严外发
- 审计记录
"""

import hashlib
from enum import Enum
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from core.database import Database


class PermissionLevel(Enum):
    PUBLIC_WEB_READ = "public_web_read"
    PRIVATE_ACCOUNT_READ = "private_account_read"
    LOCAL_READ = "local_read"
    LOCAL_CREATE = "local_create"
    LOCAL_MODIFY = "local_modify"
    PRIVATE_DATA_OUTBOUND = "private_data_outbound"
    SEND_OR_PUBLISH = "send_or_publish"
    INSTALL_OR_EXECUTE = "install_or_execute"
    DELETE = "delete"
    FINANCIAL = "financial"


@dataclass
class ActionRequest:
    action_id: str
    task_id: str
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
    expires_at: str
    single_use: bool = True
    used_at: str = ""


@dataclass
class PermissionResult:
    allowed: bool
    level: str
    requires_confirm: bool
    reason: str = ""
    audit_id: str = ""
    token: Optional[AuthToken] = None


class PermissionGateway:
    """
    所有工具操作必须经过此网关。
    模型不能直接调用系统。
    宽联网、严外发、现实行动分级确认。
    """

    def __init__(self, db: Database):
        self.db = db
        self._granted: Dict[str, Dict[str, bool]] = {
            "public_web_read": {"*": True},
            "private_account_read": {},
            "local_read": {},
            "local_create": {},
            "local_modify": {},
            "private_data_outbound": {},
            "send_or_publish": {},
            "install_or_execute": {},
            "delete": {},
            "financial": {},
        }
        self._tokens: Dict[str, AuthToken] = {}

    def check(self, action_request: ActionRequest) -> PermissionResult:
        """检查操作权限，返回 PermissionResult"""
        level = self._classify_level(action_request)

        # 公开网页读取 — 默认允许
        if level == PermissionLevel.PUBLIC_WEB_READ:
            audit_id = self._audit(action_request, level.value, True)
            return PermissionResult(True, level.value, False, audit_id=audit_id)

        # 本地读取 — 检查路径
        if level == PermissionLevel.LOCAL_READ:
            audit_id = self._audit(action_request, level.value, True)
            return PermissionResult(True, level.value, False, audit_id=audit_id)

        # 本地创建 — 允许
        if level == PermissionLevel.LOCAL_CREATE:
            audit_id = self._audit(action_request, level.value, True)
            return PermissionResult(True, level.value, False, audit_id=audit_id)

        # 本地修改 — 需要确认
        if level == PermissionLevel.LOCAL_MODIFY:
            audit_id = self._audit(action_request, level.value, False)
            return PermissionResult(
                True, level.value, True,
                reason="修改操作需要用户确认", audit_id=audit_id
            )

        # 私人账号读取 — 检查授权
        if level == PermissionLevel.PRIVATE_ACCOUNT_READ:
            provider = action_request.target
            if self._granted["private_account_read"].get(provider, False):
                audit_id = self._audit(action_request, level.value, True)
                return PermissionResult(True, level.value, False, audit_id=audit_id)
            audit_id = self._audit(action_request, level.value, False)
            return PermissionResult(
                False, level.value, True,
                reason=f"私人账号访问 '{provider}' 未授权", audit_id=audit_id
            )

        # 私人数据外发 — 必须授权
        if level == PermissionLevel.PRIVATE_DATA_OUTBOUND:
            provider = action_request.target
            if self._granted["private_data_outbound"].get(provider, False):
                audit_id = self._audit(action_request, level.value, True)
                return PermissionResult(True, level.value, False, audit_id=audit_id)
            audit_id = self._audit(action_request, level.value, False)
            return PermissionResult(
                False, level.value, True,
                reason=f"私人数据外发至 '{provider}' 需要明确授权", audit_id=audit_id
            )

        # 发送/发布 — 必须确认
        if level == PermissionLevel.SEND_OR_PUBLISH:
            audit_id = self._audit(action_request, level.value, False)
            return PermissionResult(
                False, level.value, True,
                reason="发送或发布操作需要用户确认", audit_id=audit_id
            )

        # 安装/执行 — 高风险
        if level == PermissionLevel.INSTALL_OR_EXECUTE:
            audit_id = self._audit(action_request, level.value, False)
            return PermissionResult(
                False, level.value, True,
                reason="安装或执行操作属于高风险，必须逐次确认", audit_id=audit_id
            )

        # 删除 — 高风险
        if level == PermissionLevel.DELETE:
            audit_id = self._audit(action_request, level.value, False)
            return PermissionResult(
                False, level.value, True,
                reason="删除操作属于高风险，必须明确确认对象", audit_id=audit_id
            )

        # 金融 — 最高风险
        if level == PermissionLevel.FINANCIAL:
            audit_id = self._audit(action_request, level.value, False)
            return PermissionResult(
                False, level.value, True,
                reason="金融操作必须逐次明确确认", audit_id=audit_id
            )

        # 默认拒绝
        audit_id = self._audit(action_request, "unknown", False)
        return PermissionResult(
            False, "unknown", True,
            reason="无法识别的操作类型", audit_id=audit_id
        )

    def confirm(self, audit_id: str) -> Optional[AuthToken]:
        """用户确认后生成一次性令牌"""
        token_id = hashlib.md5(f"{datetime.now().isoformat()}{audit_id}".encode()).hexdigest()[:16]
        token = AuthToken(
            token_id=token_id,
            action_id=audit_id,
            target="confirmed",
            scope="single_use",
            expires_at=(datetime.now() + timedelta(minutes=5)).isoformat(),
            single_use=True
        )
        self._tokens[token_id] = token
        self.db.execute("UPDATE audit_logs SET success = 1 WHERE id = ?", (audit_id,))
        self.db.commit()
        return token

    def validate_token(self, token_id: str, action_id: str) -> bool:
        """验证一次性令牌"""
        token = self._tokens.get(token_id)
        if not token:
            return False
        if token.used_at:
            return False
        if datetime.now() > datetime.fromisoformat(token.expires_at):
            return False
        if token.action_id != action_id:
            return False
        token.used_at = datetime.now().isoformat()
        return True

    def _classify_level(self, req: ActionRequest) -> PermissionLevel:
        action_lower = req.action_type.lower()
        target_lower = req.target.lower()

        # 金融
        if any(kw in action_lower for kw in ["付款", "购买", "订阅", "捐赠", "支付", "pay", "purchase"]):
            return PermissionLevel.FINANCIAL

        # 删除
        if any(kw in action_lower for kw in ["删除", "移除", "delete", "remove"]):
            return PermissionLevel.DELETE

        # 安装/执行
        if any(kw in action_lower for kw in ["安装", "执行", "运行", "install", "execute", "run"]):
            return PermissionLevel.INSTALL_OR_EXECUTE

        # 发送/发布
        if any(kw in action_lower for kw in ["发送", "发布", "提交", "上传", "send", "publish", "submit", "upload"]):
            return PermissionLevel.SEND_OR_PUBLISH

        # 私人数据外发
        if req.data_category in ["private_chat", "user_memory", "project_file", "personal_info"]:
            return PermissionLevel.PRIVATE_DATA_OUTBOUND

        # 私人账号读取
        if any(kw in action_lower for kw in ["登录", "邮箱", "云盘", "日历", "login", "email", "cloud", "calendar"]):
            return PermissionLevel.PRIVATE_ACCOUNT_READ

        # 本地修改
        if any(kw in action_lower for kw in ["修改", "编辑", "更新", "移动", "重命名", "modify", "edit", "update", "move"]):
            return PermissionLevel.LOCAL_MODIFY

        # 本地创建
        if any(kw in action_lower for kw in ["创建", "新建", "写入", "保存", "生成", "create", "write", "save", "generate"]):
            return PermissionLevel.LOCAL_CREATE

        # 公开网页读取（默认允许）
        if any(kw in action_lower for kw in ["搜索", "浏览", "查询", "下载", "read", "search", "browse", "query", "download"]):
            if req.data_category in ["public_web", "public_image", "public_pdf", "public_text"]:
                return PermissionLevel.PUBLIC_WEB_READ

        # 本地读取
        return PermissionLevel.LOCAL_READ

    def _audit(self, req: ActionRequest, level: str, success: bool) -> str:
        eid = hashlib.md5(f"{datetime.now().isoformat()}{req.action_id}".encode()).hexdigest()[:12]
        self.db.add_audit_log({
            "id": eid,
            "task_id": req.task_id,
            "initiator": req.requested_by,
            "permission_level": level,
            "tool": req.action_type,
            "action": req.target,
            "provider": req.scope,
            "domain": req.target,
            "operation": req.action_type,
            "data_category": req.data_category,
            "input_summary": f"target: {req.target}, scope: {req.scope}",
            "success": success,
            "user_confirmed": False,
        })
        return eid

    def grant_permission(self, level: str, target: str):
        if level in self._granted:
            self._granted[level][target] = True

    def revoke_permission(self, level: str, target: str):
        if level in self._granted and target in self._granted[level]:
            del self._granted[level][target]
