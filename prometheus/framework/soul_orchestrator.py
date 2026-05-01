"""🌌 SOUL 指挥中心 — SoulOrchestrator."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class SoulConfiguration:
    """从 SOUL.md 解析出的配置"""

    personality: str = ""
    communication_style: str = ""
    work_preferences: List[str] = None
    custom_settings: dict[str, Any] = None

    def __post_init__(self):
        if self.work_preferences is None:
            self.work_preferences = []
        if self.custom_settings is None:
            self.custom_settings = {}


class SoulOrchestrator:
    """SOUL.md 与全系统联动"""

    def __init__(self, prometheus_home: str | None = None):
        if prometheus_home is None:
            prometheus_home = os.path.expanduser("~/.prometheus")
        self.prometheus_home = Path(prometheus_home)
        self._soul_cache: str | None = None
        self._soul_cache_time: float = 0

    @property
    def current_soul(self) -> str | None:
        """获取当前 SOUL.md 内容"""
        soul_path = self.prometheus_home / "SOUL.md"
        if not soul_path.exists():
            return None

        try:
            with open(soul_path, encoding="utf-8") as f:
                return f.read()
        except Exception:
            return None

    @property
    def recommended_skin(self) -> str:
        """根据 SOUL.md 推荐皮肤"""
        soul = self.current_soul
        if not soul:
            return "default"

        soul_lower = soul.lower()

        if "雅典娜" in soul or "智慧" in soul or "athena" in soul_lower:
            return "athena"
        elif "宙斯" in soul or "雷霆" in soul or "zeus" in soul_lower:
            return "zeus"
        elif "哈迪斯" in soul or "暗黑" in soul or "hades" in soul_lower:
            return "hades"
        elif "火" in soul or "火焰" in soul or "fire" in soul_lower:
            return "default"  # 普罗米修斯默认皮肤
        else:
            return "default"

    @property
    def recommended_model(self) -> str | None:
        """根据 SOUL.md 推荐模型"""
        soul = self.current_soul
        if not soul:
            return None

        soul_lower = soul.lower()

        if "创造性" in soul or "创意" in soul or "creative" in soul_lower:
            return "claude-3-5-sonnet"
        elif "严谨" in soul or "精确" in soul or "precise" in soul_lower:
            return "gpt-4o"
        elif "深度" in soul or "思考" in soul or "deep" in soul_lower:
            return "o3-mini"
        elif "快速" in soul or "快" in soul or "fast" in soul_lower:
            return "gpt-4o-mini"
        else:
            return None

    @property
    def recommended_personality_keywords(self) -> List[str]:
        """提取 SOUL.md 中的关键词用于 prompt 增强"""
        soul = self.current_soul
        if not soul:
            return []

        keywords = []

        # 常见个性关键词
        markers = [
            "严谨",
            "精确",
            "细致",
            "创意",
            "创造",
            "灵感",
            "简洁",
            "简洁明了",
            "简短",
            "详细",
            "详尽",
            "完整",
            "友好",
            "温暖",
            "亲切",
            "专业",
            "正式",
        ]

        for marker in markers:
            if marker in soul:
                keywords.append(marker)

        return keywords

    def parse_soul_configuration(self) -> SoulConfiguration:
        """解析完整的 SOUL 配置"""
        soul = self.current_soul
        if not soul:
            return SoulConfiguration()

        return SoulConfiguration(
            personality=soul,
            communication_style="default",
            work_preferences=self.recommended_personality_keywords,
            custom_settings={
                "skin": self.recommended_skin,
                "model": self.recommended_model,
            },
        )

    def apply_soul_to_environment(self, agent_config: dict[str, Any]) -> dict[str, Any]:
        """将 SOUL.md 应用到 Agent 配置"""
        config = dict(agent_config)

        # 应用皮肤
        skin = self.recommended_skin
        if skin:
            config["skin"] = skin

        # 应用模型建议
        model = self.recommended_model
        if model:
            config["recommended_model"] = model

        # 应用关键词到 system prompt
        keywords = self.recommended_personality_keywords
        if keywords:
            config["personality_keywords"] = keywords

        return config

    def invalidate_cache(self):
        """清除缓存，下次读取时重新加载 SOUL.md"""
        self._soul_cache = None
