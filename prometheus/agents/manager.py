"""Agent 管理器."""

import datetime
import json
import os
from dataclasses import dataclass, field

try:
    from ..channels import ChannelMessage, ChannelRegistry, ChannelResponse, get_channel_registry
    from ..models import get_provider_registry
except ImportError:
    from channels import get_channel_registry
    from models import get_provider_registry


@dataclass
class AgentConfig:
    agent_id: str
    name: str
    description: str = ""
    provider_id: str = "openrouter"
    model: str = ""
    tools: list[str] = field(
        default_factory=lambda: ["memory", "knowledge", "seed_editor", "network_accelerator"]
    )
    channels: list[str] = field(default_factory=lambda: ["cli"])
    settings: dict[str, str] = field(default_factory=dict)
    workspace_dir: str = ""

    def to_dict(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "description": self.description,
            "provider_id": self.provider_id,
            "model": self.model,
            "tools": self.tools,
            "channels": self.channels,
            "settings": self.settings,
            "workspace_dir": self.workspace_dir,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AgentConfig":
        return cls(
            agent_id=data.get("agent_id", "agent-001"),
            name=data.get("name", "Prometheus"),
            description=data.get("description", ""),
            provider_id=data.get("provider_id", "openrouter"),
            model=data.get("model", ""),
            tools=data.get("tools", ["memory", "knowledge"]),
            channels=data.get("channels", ["cli"]),
            settings=data.get("settings", {}),
            workspace_dir=data.get("workspace_dir", ""),
        )


@dataclass
class AgentInstance:
    config: AgentConfig
    state: str = "idle"
    started_at: str | None = None
    last_active: str | None = None
    error_message: str | None = None
    stats: dict[str, int] = field(
        default_factory=lambda: {
            "messages_processed": 0,
            "errors": 0,
            "total_latency_ms": 0,
        }
    )

    def to_dict(self) -> dict:
        return {
            "config": self.config.to_dict(),
            "state": self.state,
            "started_at": self.started_at,
            "last_active": self.last_active,
            "error_message": self.error_message,
            "stats": self.stats,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AgentInstance":
        config = AgentConfig.from_dict(data.get("config", {}))
        return cls(
            config=config,
            state=data.get("state", "idle"),
            started_at=data.get("started_at"),
            last_active=data.get("last_active"),
            error_message=data.get("error_message"),
            stats=data.get("stats", {}),
        )


class AgentManager:
    def __init__(self, config_dir: str = None):
        home = os.path.expanduser("~")
        self._config_dir = config_dir or os.path.join(home, ".prometheus", "agents")
        self._agents: dict[str, AgentInstance] = {}
        self._agents_file = os.path.join(self._config_dir, "agents.json")
        self._load()

    def _load(self):
        os.makedirs(self._config_dir, exist_ok=True)
        if os.path.exists(self._agents_file):
            try:
                with open(self._agents_file, encoding="utf-8") as f:
                    data = json.load(f)
                for agent_data in data.get("agents", []):
                    instance = AgentInstance.from_dict(agent_data)
                    instance.state = "idle"
                    self._agents[instance.config.agent_id] = instance
            except (json.JSONDecodeError, KeyError):
                self._agents = {}

    def _save(self):
        os.makedirs(self._config_dir, exist_ok=True)
        agents_data = [a.to_dict() for a in self._agents.values()]
        with open(self._agents_file + ".tmp", "w", encoding="utf-8") as f:
            json.dump(
                {"agents": agents_data, "updated_at": datetime.datetime.now().isoformat()},
                f,
                ensure_ascii=False,
                indent=2,
            )
        os.rename(self._agents_file + ".tmp", self._agents_file)

    def create(self, config: AgentConfig) -> AgentInstance:
        if config.agent_id in self._agents:
            raise ValueError(f"Agent {config.agent_id} 已存在")
        instance = AgentInstance(config=config)
        self._agents[config.agent_id] = instance
        self._save()
        return instance

    def remove(self, agent_id: str) -> bool:
        if agent_id not in self._agents:
            return False
        if self._agents[agent_id].state == "running":
            self.stop(agent_id)
        del self._agents[agent_id]
        self._save()
        return True

    def start(self, agent_id: str) -> bool:
        instance = self._agents.get(agent_id)
        if not instance:
            return False

        registry = get_provider_registry()
        provider = registry.get(instance.config.provider_id)
        if not provider or not provider.is_available():
            instance.state = "error"
            instance.error_message = f"模型提供者不可用: {instance.config.provider_id}"
            return False

        instance.state = "running"
        instance.started_at = datetime.datetime.now().isoformat()
        instance.error_message = None
        self._save()
        return True

    def stop(self, agent_id: str) -> bool:
        instance = self._agents.get(agent_id)
        if not instance:
            return False
        instance.state = "idle"
        instance.started_at = None
        self._save()
        return True

    def get(self, agent_id: str) -> AgentInstance | None:
        return self._agents.get(agent_id)

    def list_all(self) -> list[AgentInstance]:
        return list(self._agents.values())

    def status(self, agent_id: str) -> dict | None:
        instance = self._agents.get(agent_id)
        if not instance:
            return None

        registry = get_provider_registry()
        provider_info = None
        provider = registry.get(instance.config.provider_id)
        if provider:
            provider_info = {
                "id": provider.id,
                "name": provider.name,
                "available": provider.is_available(),
                "default_model": provider.default_model or instance.config.model or "auto",
            }

        ch_registry = get_channel_registry()
        channel_status = []
        for ch_name in instance.config.channels:
            ch = ch_registry.get(ch_name)
            channel_status.append(
                {
                    "name": ch_name,
                    "active": ch.is_started if ch else False,
                }
            )

        return {
            "agent_id": instance.config.agent_id,
            "name": instance.config.name,
            "state": instance.state,
            "started_at": instance.started_at,
            "last_active": instance.last_active,
            "provider": provider_info,
            "tools": instance.config.tools,
            "channels": channel_status,
            "stats": instance.stats,
        }

    def config(self) -> dict:
        return {
            "agent_count": len(self._agents),
            "agents": [a.config.to_dict() for a in self._agents.values()],
            "config_dir": self._config_dir,
        }

    def detect_available_tools(self) -> dict[str, dict]:
        tools = {
            "memory": {
                "id": "memory",
                "name": "向量记忆系统",
                "description": "三层记忆模型 (工作/情景/长期) + 语义检索",
                "required": True,
                "available": True,
            },
            "knowledge": {
                "id": "knowledge",
                "name": "知识管理系统",
                "description": "种子索引 + Wiki检索 + 本地知识库",
                "required": True,
                "available": True,
            },
            "seed_editor": {
                "id": "seed_editor",
                "name": "基因编辑器",
                "description": "TTG种子创建、编辑、审计、锻造",
                "required": True,
                "available": True,
            },
            "network_accelerator": {
                "id": "network_accelerator",
                "name": "网络加速器",
                "description": "GitHub/HuggingFace/PyPI代码拉取与缓存",
                "required": False,
                "available": True,
            },
            "semantic_dict": {
                "id": "semantic_dict",
                "name": "语义词典",
                "description": "概念扫描、字典扩展、领域建模",
                "required": False,
                "available": True,
            },
            "self_correction": {
                "id": "self_correction",
                "name": "自纠错系统",
                "description": "误差检测、回退策略、质量评估",
                "required": False,
                "available": True,
            },
            "backup_restore": {
                "id": "backup_restore",
                "name": "备份恢复",
                "description": "种子快照、系统备份、灾难恢复",
                "required": False,
                "available": True,
            },
        }
        return tools

    def process_message(
        self, agent_id: str, channel: str, sender: str, content: str, metadata: dict = None
    ) -> dict:
        instance = self._agents.get(agent_id)
        if not instance:
            return {"success": False, "error": f"Agent {agent_id} 不存在"}
        if instance.state != "running":
            return {"success": False, "error": f"Agent {agent_id} 未运行"}

        instance.last_active = datetime.datetime.now().isoformat()
        instance.stats["messages_processed"] = instance.stats.get("messages_processed", 0) + 1
        self._save()

        return {
            "success": True,
            "agent_id": agent_id,
            "channel": channel,
            "response": f"[{agent_id}] 已收到: {content[:100]}",
        }


_manager: AgentManager | None = None


def get_agent_manager() -> AgentManager:
    global _manager
    if _manager is None:
        _manager = AgentManager()
    return _manager


def create_default_agent(workspace_dir: str = None, provider_id: str = None) -> AgentInstance:
    mgr = get_agent_manager()
    existing = mgr.list_all()
    if existing:
        return existing[0]

    if not provider_id:
        registry = get_provider_registry()
        provider = registry.detect_and_select()
        provider_id = provider.id

    config = AgentConfig(
        agent_id="prometheus-001",
        name="普罗米修斯 · Prometheus",
        description="碳硅知识架构师 · Teach-To-Grow 基因编辑器",
        provider_id=provider_id,
        tools=[
            "memory",
            "knowledge",
            "seed_editor",
            "network_accelerator",
            "semantic_dict",
            "self_correction",
        ],
        channels=["cli"],
        workspace_dir=workspace_dir or os.path.expanduser("~/.prometheus/workspace"),
    )
    instance = mgr.create(config)
    mgr.start(config.agent_id)
    return instance
