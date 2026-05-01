"""统一路径管理 - PrometheusPaths."""

from __future__ import annotations

import os
from pathlib import Path


class PrometheusPaths:
    """Prometheus 统一路径管理器"""

    def __init__(self, home: str | None = None):
        self._home = Path(home or os.environ.get("PROMETHEUS_HOME", "~/.prometheus")).expanduser()
        self._ensure_directories()

    def _ensure_directories(self):
        """确保必要的目录存在"""
        for dir_path in [self.home, self.data, self.cache, self.memories, self.sessions]:
            dir_path.mkdir(parents=True, exist_ok=True)

    @property
    def home(self) -> Path:
        """Prometheus 主目录"""
        return self._home

    @property
    def data(self) -> Path:
        """数据目录"""
        return self._home / "data"

    @property
    def cache(self) -> Path:
        """缓存目录"""
        return self._home / "cache"

    @property
    def memories(self) -> Path:
        """记忆目录"""
        return self._home / "memories"

    @property
    def sessions(self) -> Path:
        """会话目录"""
        return self._home / "sessions"

    @property
    def skills(self) -> Path:
        """技能目录"""
        return self._home / "skills"

    @property
    def configs(self) -> Path:
        """配置目录"""
        return self._home / "configs"

    @property
    def plugins(self) -> Path:
        """插件目录"""
        return self._home / "plugins"

    @property
    def logs(self) -> Path:
        """日志目录"""
        return self._home / "logs"

    @property
    def proposals(self) -> Path:
        """进化提案目录"""
        return self._home / "proposals"

    @property
    def mcp(self) -> Path:
        """MCP 配置目录"""
        return self._home / "mcp"

    @property
    def tools_cache(self) -> Path:
        """工具缓存目录"""
        return self.cache / "tools"

    @property
    def file_sync_cache(self) -> Path:
        """文件同步缓存目录"""
        return self.cache / "file_sync"

    @property
    def subagents(self) -> Path:
        """子 Agent 状态目录"""
        return self.data / "subagents"

    @property
    def trajectories(self) -> Path:
        """轨迹存储目录"""
        return self.data / "trajectories"

    @property
    def tasks(self) -> Path:
        """任务状态目录"""
        return self.data / "tasks"

    def subdir(self, name: str) -> Path:
        """获取子目录"""
        return self._home / name


_paths_instance: PrometheusPaths | None = None


def get_paths() -> PrometheusPaths:
    """获取全局路径管理器实例"""
    global _paths_instance
    if _paths_instance is None:
        _paths_instance = PrometheusPaths()
    return _paths_instance


def reset_paths(new_home: str | None = None):
    """重置路径管理器（主要用于测试）"""
    global _paths_instance
    _paths_instance = PrometheusPaths(home=new_home)


def get_prometheus_home() -> Path:
    """获取 Prometheus 主目录（向后兼容）"""
    return get_paths().home


def get_data_dir(subdir: str = "") -> Path:
    """获取数据目录"""
    base = get_paths().data
    if subdir:
        base = base / subdir
    base.mkdir(parents=True, exist_ok=True)
    return base


def get_cache_dir(subdir: str = "") -> Path:
    """获取缓存目录"""
    base = get_paths().cache
    if subdir:
        base = base / subdir
    base.mkdir(parents=True, exist_ok=True)
    return base


def get_slack_dir() -> Path:
    """获取 Slack 配置目录"""
    return get_prometheus_home() / "slack"


def get_backups_dir() -> Path:
    """获取备份目录"""
    backup_dir = get_prometheus_home() / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    return backup_dir


def get_openclaw_dir() -> Path:
    """获取 OpenClaw 迁移目录（用于从旧版本迁移）"""
    return Path.home() / ".openclaw"


def get_honcho_config() -> Path:
    """获取 Honcho 配置文件"""
    return Path.home() / ".honcho" / "config.json"
