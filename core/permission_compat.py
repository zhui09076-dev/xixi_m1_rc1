"""Bridge the RC3 permission API onto the upgraded gateway."""
from pathlib import Path

from .permission_legacy import (
    ActionRequest,
    AuthToken,
    PermissionCategory,
    PermissionResult,
    PermissionGateway as LegacyPermissionGateway,
)


def install(gateway_class):
    modern_init = gateway_class.__init__
    modern_scope_check = gateway_class._is_in_authorized_scope

    def compatible_init(self, db_path="data/xixi.db", authorized_paths=None):
        normalized_path = getattr(db_path, "path", db_path)
        modern_init(self, normalized_path)
        self.db = db_path if hasattr(db_path, "execute") else None
        roots = authorized_paths or [
            "assets", "data", "logs", "projects", "workspace", "temp",
            "extensions", "souls", "bodies", "development",
        ]
        self._authorized_paths = [Path(path).resolve() for path in roots]
        self._tokens = {}

    def compatible_scope_check(self, capability, target):
        if LegacyPermissionGateway._is_authorized_path(self, target):
            return True
        return modern_scope_check(self, capability, target)

    gateway_class.__init__ = compatible_init
    gateway_class._resolve_path = LegacyPermissionGateway._resolve_path
    gateway_class._is_authorized_path = LegacyPermissionGateway._is_authorized_path
    gateway_class._is_web_url = LegacyPermissionGateway._is_web_url
    gateway_class._is_private_data = LegacyPermissionGateway._is_private_data
    gateway_class._is_irreversible_action = LegacyPermissionGateway._is_irreversible_action
    gateway_class.request_permission = LegacyPermissionGateway.request_permission
    gateway_class.confirm_with_token = LegacyPermissionGateway.confirm_with_token
    gateway_class.validate_token = LegacyPermissionGateway.validate_token
    gateway_class._is_in_authorized_scope = compatible_scope_check
