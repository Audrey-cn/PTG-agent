#!/usr/bin/env python3
"""Prometheus 子代理注册系统."""

import json
import logging
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from prometheus._paths import get_paths

logger = logging.getLogger("prometheus.subagent")


class SubagentStatus(Enum):
    OFFLINE = "offline"
    ONLINE = "online"
    BUSY = "busy"
    ERROR = "error"


class SubagentCapability(Enum):
    TOOL_EXECUTION = "tool_execution"
    CODE_GENERATION = "code_generation"
    ANALYSIS = "analysis"
    SUMMARIZATION = "summarization"
    MULTIMEDIA = "multimedia"
    RESEARCH = "research"
    PLANNING = "planning"


@dataclass
class SubagentInfo:
    """子代理信息"""

    agent_id: str
    name: str
    description: str = ""
    capabilities: list[str] = field(default_factory=list)
    status: str = SubagentStatus.OFFLINE.value
    last_seen: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    session_count: int = 0
    total_requests: int = 0


@dataclass
class SubagentSession:
    """子代理会话"""

    session_id: str
    agent_id: str
    parent_session_id: str | None = None
    created_at: str = ""
    expires_at: str | None = None
    status: str = "active"
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()


@dataclass
class SubagentAnnouncement:
    """子代理声明消息"""

    agent_id: str
    name: str
    capabilities: list[str]
    timestamp: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()


class SubagentRegistry:
    """
    子代理注册表

    管理子代理的发现、注册、能力声明和会话管理。
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._agents: dict[str, SubagentInfo] = {}
            cls._instance._sessions: dict[str, SubagentSession] = {}
            cls._instance._callbacks: dict[str, list[Callable]] = {}
            cls._instance._initialized = False
        return cls._instance

    def initialize(self, data_dir: Path | None = None):
        """初始化注册表"""
        if self._initialized:
            return

        self._data_dir = data_dir or get_paths().subagents
        self._data_dir.mkdir(parents=True, exist_ok=True)

        self._load_persisted_data()
        self._initialized = True
        logger.info("Subagent registry initialized")

    def _load_persisted_data(self):
        """加载持久化数据"""
        agents_file = self._data_dir / "agents.json"
        sessions_file = self._data_dir / "sessions.json"

        if agents_file.exists():
            try:
                with open(agents_file, encoding="utf-8") as f:
                    data = json.load(f)
                    for agent_id, info in data.items():
                        self._agents[agent_id] = SubagentInfo(**info)
            except Exception as e:
                logger.error(f"Failed to load agents: {e}")

        if sessions_file.exists():
            try:
                with open(sessions_file, encoding="utf-8") as f:
                    data = json.load(f)
                    for session_id, info in data.items():
                        self._sessions[session_id] = SubagentSession(**info)
            except Exception as e:
                logger.error(f"Failed to load sessions: {e}")

    def _save_persisted_data(self):
        """保存持久化数据"""
        agents_file = self._data_dir / "agents.json"
        sessions_file = self._data_dir / "sessions.json"

        try:
            with open(agents_file, "w", encoding="utf-8") as f:
                data = {agent_id: info.__dict__ for agent_id, info in self._agents.items()}
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Failed to save agents: {e}")

        try:
            with open(sessions_file, "w", encoding="utf-8") as f:
                data = {session_id: info.__dict__ for session_id, info in self._sessions.items()}
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Failed to save sessions: {e}")

    def register_agent(self, announcement: SubagentAnnouncement):
        """注册或更新子代理"""
        if announcement.agent_id in self._agents:
            agent = self._agents[announcement.agent_id]
            agent.name = announcement.name
            agent.capabilities = announcement.capabilities
            agent.metadata.update(announcement.metadata)
        else:
            agent = SubagentInfo(
                agent_id=announcement.agent_id,
                name=announcement.name,
                capabilities=announcement.capabilities,
                metadata=announcement.metadata,
            )
            self._agents[announcement.agent_id] = agent

        agent.status = SubagentStatus.ONLINE.value
        agent.last_seen = datetime.now().isoformat()

        self._trigger_callback("agent_registered", agent)
        self._save_persisted_data()

        logger.info(f"Registered agent: {agent.name} ({agent.agent_id})")

    def unregister_agent(self, agent_id: str):
        """注销子代理"""
        if agent_id in self._agents:
            agent = self._agents[agent_id]
            agent.status = SubagentStatus.OFFLINE.value
            agent.last_seen = datetime.now().isoformat()

            self._trigger_callback("agent_unregistered", agent)
            self._save_persisted_data()

            logger.info(f"Unregistered agent: {agent.name} ({agent_id})")

    def get_agent(self, agent_id: str) -> SubagentInfo | None:
        """获取子代理信息"""
        return self._agents.get(agent_id)

    def list_agents(
        self, status: str | None = None, capability: str | None = None
    ) -> list[SubagentInfo]:
        """列出子代理"""
        agents = list(self._agents.values())

        if status:
            agents = [a for a in agents if a.status == status]

        if capability:
            agents = [a for a in agents if capability in a.capabilities]

        return agents

    def find_agents_by_capability(self, capability: str) -> list[SubagentInfo]:
        """根据能力查找子代理"""
        return [
            a
            for a in self._agents.values()
            if a.status == SubagentStatus.ONLINE.value and capability in a.capabilities
        ]

    def create_session(
        self,
        agent_id: str,
        parent_session_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str | None:
        """创建子代理会话"""
        if agent_id not in self._agents:
            logger.error(f"Agent not found: {agent_id}")
            return None

        agent = self._agents[agent_id]
        if agent.status != SubagentStatus.ONLINE.value:
            logger.error(f"Agent not online: {agent_id}")
            return None

        session_id = str(uuid.uuid4())[:8]

        session = SubagentSession(
            session_id=session_id,
            agent_id=agent_id,
            parent_session_id=parent_session_id,
            metadata=metadata or {},
        )

        self._sessions[session_id] = session
        agent.session_count += 1
        agent.total_requests += 1

        self._trigger_callback("session_created", session)
        self._save_persisted_data()

        logger.info(f"Created session: {session_id} for agent: {agent_id}")
        return session_id

    def get_session(self, session_id: str) -> SubagentSession | None:
        """获取会话信息"""
        return self._sessions.get(session_id)

    def close_session(self, session_id: str):
        """关闭会话"""
        if session_id in self._sessions:
            session = self._sessions[session_id]
            session.status = "closed"
            session.expires_at = datetime.now().isoformat()

            if session.agent_id in self._agents:
                agent = self._agents[session.agent_id]
                agent.session_count = max(0, agent.session_count - 1)

            self._trigger_callback("session_closed", session)
            self._save_persisted_data()

            logger.info(f"Closed session: {session_id}")

    def cleanup_expired_sessions(self):
        """清理过期会话"""
        now = datetime.now()
        expired = []

        for session_id, session in self._sessions.items():
            if session.status == "closed":
                continue

            if session.expires_at:
                try:
                    expires = datetime.fromisoformat(session.expires_at)
                    if expires < now:
                        expired.append(session_id)
                except ValueError:
                    pass

        for session_id in expired:
            self.close_session(session_id)

        if expired:
            logger.info(f"Cleaned up {len(expired)} expired sessions")

    def register_callback(self, event_type: str, callback: Callable):
        """注册事件回调"""
        if event_type not in self._callbacks:
            self._callbacks[event_type] = []
        if callback not in self._callbacks[event_type]:
            self._callbacks[event_type].append(callback)

    def unregister_callback(self, event_type: str, callback: Callable):
        """取消注册事件回调"""
        if event_type in self._callbacks and callback in self._callbacks[event_type]:
            self._callbacks[event_type].remove(callback)

    def _trigger_callback(self, event_type: str, data: Any):
        """触发事件回调"""
        for callback in self._callbacks.get(event_type, []):
            try:
                callback(event_type, data)
            except Exception as e:
                logger.error(f"Callback failed for {event_type}: {e}")

    def get_status(self) -> dict[str, Any]:
        """获取注册表状态"""
        online_count = sum(
            1 for a in self._agents.values() if a.status == SubagentStatus.ONLINE.value
        )
        active_sessions = sum(1 for s in self._sessions.values() if s.status == "active")

        return {
            "total_agents": len(self._agents),
            "online_agents": online_count,
            "offline_agents": len(self._agents) - online_count,
            "active_sessions": active_sessions,
            "total_sessions": len(self._sessions),
        }


def create_announcement(
    name: str, capabilities: list[str], agent_id: str | None = None, **metadata
) -> SubagentAnnouncement:
    """创建子代理声明"""
    return SubagentAnnouncement(
        agent_id=agent_id or str(uuid.uuid4())[:8],
        name=name,
        capabilities=capabilities,
        metadata=metadata,
    )


def get_subagent_registry() -> SubagentRegistry:
    """获取全局子代理注册表"""
    return SubagentRegistry()


def announce_subagent(name: str, capabilities: list[str], **metadata):
    """便捷函数：声明子代理"""
    registry = get_subagent_registry()
    announcement = create_announcement(name, capabilities, **metadata)
    registry.register_agent(announcement)
    return announcement.agent_id


def spawn_subagent(
    name: str, capabilities: list[str], parent_session_id: str | None = None, **metadata
) -> str:
    """便捷函数：声明子代理并创建会话"""
    registry = get_subagent_registry()
    announcement = create_announcement(name, capabilities, **metadata)
    registry.register_agent(announcement)
    session_id = registry.create_session(announcement.agent_id, parent_session_id)
    return session_id if session_id else ""
