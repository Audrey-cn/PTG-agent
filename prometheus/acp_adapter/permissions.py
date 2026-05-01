from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger("prometheus.acp_adapter.permissions")

DEFAULT_PERMISSIONS: set[str] = {"read_files", "write_files", "execute_commands", "network_access"}


@dataclass
class Permission:
    action: str
    resource: str
    granted_at: datetime = field(default_factory=datetime.now)


class ACPPermissions:
    def __init__(self) -> None:
        self._permissions: dict[str, dict[str, Permission]] = {}
        self._default_permissions: set[str] = DEFAULT_PERMISSIONS.copy()

    def check_permission(self, agent_id: str, action: str, resource: str) -> bool:
        if agent_id not in self._permissions:
            return action in self._default_permissions

        perm_key = f"{action}:{resource}"
        if perm_key in self._permissions[agent_id]:
            return True

        wildcard_key = f"{action}:*"
        if wildcard_key in self._permissions[agent_id]:
            return True

        return action in self._default_permissions

    def grant_permission(self, agent_id: str, action: str, resource: str) -> None:
        if agent_id not in self._permissions:
            self._permissions[agent_id] = {}

        perm_key = f"{action}:{resource}"
        self._permissions[agent_id][perm_key] = Permission(action=action, resource=resource)
        logger.info(f"Granted permission: {agent_id} -> {action}:{resource}")

    def revoke_permission(self, agent_id: str, action: str, resource: str) -> bool:
        if agent_id not in self._permissions:
            return False

        perm_key = f"{action}:{resource}"
        if perm_key in self._permissions[agent_id]:
            del self._permissions[agent_id][perm_key]
            logger.info(f"Revoked permission: {agent_id} -> {action}:{resource}")
            return True

        return False

    def list_permissions(self, agent_id: str) -> list[dict[str, str]]:
        result = []

        for perm in self._default_permissions:
            result.append({"action": perm, "resource": "*", "type": "default"})

        if agent_id in self._permissions:
            for perm in self._permissions[agent_id].values():
                result.append(
                    {
                        "action": perm.action,
                        "resource": perm.resource,
                        "type": "granted",
                        "granted_at": perm.granted_at.isoformat(),
                    }
                )

        return result

    def clear_permissions(self, agent_id: str) -> None:
        if agent_id in self._permissions:
            del self._permissions[agent_id]
            logger.info(f"Cleared all permissions for agent: {agent_id}")

    def set_default_permissions(self, permissions: set[str]) -> None:
        self._default_permissions = permissions.copy()
        logger.info(f"Updated default permissions: {permissions}")

    def get_default_permissions(self) -> set[str]:
        return self._default_permissions.copy()
