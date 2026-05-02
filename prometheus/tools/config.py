#!/usr/bin/env python3
"""╔══════════════════════════════════════════════════════════════╗."""

import json
import os
from typing import Any

# ═══════════════════════════════════════════
#   默认配置
# ═══════════════════════════════════════════

DEFAULT_CONFIG = {
    # ── 路径 ──
    "paths": {
        "data_dir": "~/.prometheus/tools/prometheus/data",
        "snapshot_dir": "~/.prometheus/tools/prometheus/snapshots",
        "seed_vault": "~/.prometheus/seed-vault",
        "skills_dir": "~/.prometheus/skills",
        "knowledge_dir": "~/.prometheus/knowledge",
    },
    # ── 模型 ──
    "model": {
        "provider": "openrouter",
        "name": "anthropic/claude-sonnet-4",
        "fallback_provider": "anthropic",
        "fallback_model": "claude-sonnet-4",
        "max_tokens": 8192,
        "temperature": 0.7,
    },
    # ── 种子 ──
    "seed": {
        "default_format": "markdown",  # markdown | binary | json
        "compression": "l2",  # l1 | l2 | none
        "auto_snapshot": True,  # 自动快照
        "max_snapshots": 50,  # 最大快照数
        "semantic_dict_auto_extend": True,  # 语义字典自动扩展
    },
    # ── 基因 ──
    "gene": {
        "fusion_threshold": 0.7,  # 融合兼容度阈值
        "mutation_rate": 0.1,  # 突变率
        "max_generations": 100,  # 最大代数
        "auto_audit": True,  # 自动审计
    },
    # ── 记忆 ──
    "memory": {
        "working_capacity": 20,  # 工作记忆容量
        "episodic_capacity": 100,  # 情景记忆容量
        "longterm_capacity": 1000,  # 长期记忆容量
        "decay_rate": 0.01,  # 默认衰减率
        "promotion_threshold": 0.8,  # 提升阈值
    },
    # ── 反思 ──
    "reflection": {
        "enabled": True,
        "proposal_threshold": 5,  # 提案累积阈值
        "daily_review_enabled": True,
        "observation_retention_days": 30,  # 观察记录保留天数
    },
    # ── 纠错 ──
    "correction": {
        "enabled": True,
        "max_retries": 3,
        "base_delay_ms": 1000,
        "backoff_factor": 2.0,
        "degradation_enabled": True,
    },
    # ── 状态机 ──
    "state": {
        "max_transitions": 100,  # 最大转换记录
        "auto_reflect_on_error": True,  # 错误时自动反思
        "idle_timeout_ms": 300000,  # 空闲超时 5分钟
    },
    # ── 工具 ──
    "tools": {
        "permission_level": "standard",  # strict | standard | permissive
        "max_concurrent": 3,
        "timeout_ms": 30000,
    },
    # ── 日志 ──
    "logging": {
        "level": "INFO",  # DEBUG | INFO | WARNING | ERROR
        "file": "~/.prometheus/tools/prometheus/prometheus.log",
        "max_size_mb": 10,
        "backup_count": 3,
    },
}


# ═══════════════════════════════════════════
#   配置类
# ═══════════════════════════════════════════


class Config:
    """Prometheus 配置管理器

    设计哲学（对齐 Prometheus）：
      • YAML 文件为源，环境变量可覆盖
      • 支持 dot-notation 访问：config.get("model.name")
      • 类型安全：get_int, get_bool, get_list
      • 无配置文件时优雅降级到默认值
    """

    def __init__(self, config_path: str = None):
        self._config_path = config_path or os.path.expanduser(
            "~/.prometheus/tools/prometheus/config.yaml"
        )
        self._data: dict = {}
        self._loaded = False
        self._load()

    def _load(self):
        """加载配置"""
        # 从默认值开始
        self._data = self._deep_copy(DEFAULT_CONFIG)

        # 尝试加载 YAML 文件
        if os.path.exists(self._config_path):
            try:
                import yaml

                with open(self._config_path, encoding="utf-8") as f:
                    file_config = yaml.safe_load(f)
                if file_config and isinstance(file_config, dict):
                    self._deep_merge(self._data, file_config)
                self._loaded = True
            except Exception:
                pass  # YAML 不可用或解析失败，使用默认值

        # 环境变量覆盖（PREFIX: PROMETHEUS_）
        self._apply_env_overrides()
        self._loaded = True

    def _apply_env_overrides(self):
        """环境变量覆盖：PROMETHEUS_SECTION_KEY=value"""
        prefix = "PROMETHEUS_"
        for key, value in os.environ.items():
            if not key.startswith(prefix):
                continue
            parts = key[len(prefix) :].lower().split("_")
            if len(parts) >= 2:
                section = parts[0]
                field = "_".join(parts[1:])
                if section in self._data and isinstance(self._data[section], dict):
                    # 尝试类型转换
                    self._data[section][field] = self._auto_convert(value)

    def _auto_convert(self, value: str):
        """自动类型转换"""
        if value.lower() in ("true", "yes", "1"):
            return True
        if value.lower() in ("false", "no", "0"):
            return False
        try:
            return int(value)
        except ValueError:
            pass
        try:
            return float(value)
        except ValueError:
            pass
        return value

    def _deep_copy(self, d: dict) -> dict:
        """深拷贝"""
        import copy

        return copy.deepcopy(d)

    def _deep_merge(self, base: dict, override: dict):
        """深度合并：override 覆盖 base"""
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._deep_merge(base[key], value)
            else:
                base[key] = value

    # ── 访问接口 ────────────────────────────────

    def get(self, path: str, default: Any = None) -> Any:
        """获取配置值（支持 dot-notation）

        示例：
          config.get("model.name")
          config.get("memory.working_capacity", 20)
        """
        parts = path.split(".")
        current = self._data

        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return default

        return current

    def get_int(self, path: str, default: int = 0) -> int:
        """获取整数配置"""
        return int(self.get(path, default))

    def get_bool(self, path: str, default: bool = False) -> bool:
        """获取布尔配置"""
        return bool(self.get(path, default))

    def get_float(self, path: str, default: float = 0.0) -> float:
        """获取浮点配置"""
        return float(self.get(path, default))

    def get_list(self, path: str, default: list = None) -> list:
        """获取列表配置"""
        val = self.get(path, default or [])
        return val if isinstance(val, list) else [val]

    def get_dict(self, path: str, default: dict = None) -> dict:
        """获取字典配置"""
        val = self.get(path, default or {})
        return val if isinstance(val, dict) else {}

    # ── 修改接口 ────────────────────────────────

    def set(self, path: str, value: Any):
        """设置配置值（运行时）"""
        parts = path.split(".")
        current = self._data

        for part in parts[:-1]:
            if part not in current:
                current[part] = {}
            current = current[part]

        current[parts[-1]] = value

    def reset(self):
        """重置为默认值"""
        self._data = self._deep_copy(DEFAULT_CONFIG)

    # ── 持久化 ──────────────────────────────────

    def save(self, path: str = None):
        """保存当前配置到 YAML 文件"""
        try:
            import yaml

            save_path = path or self._config_path
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            with open(save_path, "w", encoding="utf-8") as f:
                yaml.dump(self._data, f, allow_unicode=True, default_flow_style=False)
        except ImportError:
            # 回退到 JSON
            save_path = (path or self._config_path).rsplit(".", 1)[0] + ".json"
            with open(save_path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)

    def to_dict(self) -> dict:
        """导出为字典"""
        return self._deep_copy(self._data)

    # ── 信息 ────────────────────────────────────

    @property
    def config_path(self) -> str:
        return self._config_path

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    def diff(self) -> dict[str, Any]:
        """显示当前配置与默认值的差异"""
        changes = {}
        self._diff_dict(DEFAULT_CONFIG, self._data, "", changes)
        return changes

    def _diff_dict(self, default: dict, current: dict, prefix: str, changes: dict):
        """递归对比配置差异"""
        for key in set(list(default.keys()) + list(current.keys())):
            path = f"{prefix}.{key}" if prefix else key
            d_val = default.get(key)
            c_val = current.get(key)

            if isinstance(d_val, dict) and isinstance(c_val, dict):
                self._diff_dict(d_val, c_val, path, changes)
            elif d_val != c_val:
                changes[path] = {"default": d_val, "current": c_val}

    def export_markdown(self) -> str:
        """导出为 Markdown 格式（人读层）"""
        lines = ["# Prometheus 配置", ""]
        self._md_section(self._data, lines, 0)
        return "\n".join(lines)

    def _md_section(self, data: dict, lines: list, indent: int):
        """递归生成 Markdown"""
        prefix = "  " * indent
        for key, value in data.items():
            if isinstance(value, dict):
                lines.append(f"{prefix}**{key}:**")
                self._md_section(value, lines, indent + 1)
            else:
                lines.append(f"{prefix}- {key}: `{value}`")


# ═══════════════════════════════════════════
#   全局实例
# ═══════════════════════════════════════════

_config: Config | None = None


def get_config(config_path: str = None) -> Config:
    """获取全局配置实例（单例）"""
    global _config
    if _config is None:
        _config = Config(config_path)
    return _config


def reset_config():
    """重置全局配置"""
    global _config
    _config = None


# ═══════════════════════════════════════════
#   CLI 入口
# ═══════════════════════════════════════════


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Prometheus 配置管理")
    parser.add_argument(
        "command", choices=["get", "set", "show", "diff", "init", "export"], help="操作命令"
    )
    parser.add_argument("args", nargs="*", help="命令参数")

    args = parser.parse_args()
    config = get_config()

    if args.command == "get":
        if not args.args:
            print("❌ 需要提供配置路径（如 model.name）")
            return
        value = config.get(args.args[0])
        print(f"{args.args[0]} = {value}")

    elif args.command == "set":
        if len(args.args) < 2:
            print("❌ 需要提供 路径 值")
            return
        config.set(args.args[0], args.args[1])
        config.save()
        print(f"✅ {args.args[0]} = {args.args[1]}")

    elif args.command == "show":
        import yaml

        try:
            print(yaml.dump(config.to_dict(), allow_unicode=True, default_flow_style=False))
        except ImportError:
            print(json.dumps(config.to_dict(), ensure_ascii=False, indent=2))

    elif args.command == "diff":
        changes = config.diff()
        if changes:
            for path, vals in changes.items():
                print(f"  {path}: {vals['default']} → {vals['current']}")
        else:
            print("无差异（使用默认配置）")

    elif args.command == "init":
        config.save()
        print(f"✅ 配置文件已创建: {config.config_path}")

    elif args.command == "export":
        print(config.export_markdown())


if __name__ == "__main__":
    main()
