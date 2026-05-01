from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field, asdict
from typing import Optional

from prometheus.config import get_prometheus_home

logger = logging.getLogger(__name__)


@dataclass
class MCPServerConfig:
    name: str
    command: str
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    enabled: bool = True


class MCPConfig:
    def __init__(self) -> None:
        self._config_path = get_prometheus_home() / "mcp_servers.json"
        self._servers: dict[str, MCPServerConfig] = {}
        self._load()

    def _load(self) -> None:
        if self._config_path.exists():
            try:
                with open(self._config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for item in data.get("servers", []):
                    cfg = MCPServerConfig(
                        name=item.get("name", ""),
                        command=item.get("command", ""),
                        args=item.get("args", []),
                        env=item.get("env", {}),
                        enabled=item.get("enabled", True),
                    )
                    if cfg.name:
                        self._servers[cfg.name] = cfg
            except Exception as e:
                logger.warning("Failed to load MCP config: %s", e)

    def _save(self) -> None:
        try:
            self._config_path.parent.mkdir(parents=True, exist_ok=True)
            servers_list = [asdict(s) for s in self._servers.values()]
            with open(self._config_path, "w", encoding="utf-8") as f:
                json.dump({"servers": servers_list}, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error("Failed to save MCP config: %s", e)

    def list_servers(self) -> list[MCPServerConfig]:
        return list(self._servers.values())

    def add_server(
        self,
        name: str,
        command: str,
        args: Optional[list[str]] = None,
        env: Optional[dict[str, str]] = None,
    ) -> bool:
        if name in self._servers:
            logger.warning("MCP server %s already exists", name)
            return False
        self._servers[name] = MCPServerConfig(
            name=name,
            command=command,
            args=args or [],
            env=env or {},
            enabled=True,
        )
        self._save()
        return True

    def remove_server(self, name: str) -> bool:
        if name not in self._servers:
            logger.warning("MCP server %s not found", name)
            return False
        del self._servers[name]
        self._save()
        return True

    def get_server(self, name: str) -> Optional[MCPServerConfig]:
        return self._servers.get(name)

    def enable_server(self, name: str) -> bool:
        server = self._servers.get(name)
        if not server:
            return False
        server.enabled = True
        self._save()
        return True

    def disable_server(self, name: str) -> bool:
        server = self._servers.get(name)
        if not server:
            return False
        server.enabled = False
        self._save()
        return True
