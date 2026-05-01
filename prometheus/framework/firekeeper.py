"""🔥 火种守护者 — FireKeeper."""

from __future__ import annotations

import contextlib
import os
from dataclasses import dataclass, field
from typing import Any

from prometheus.chronicler import Chronicler
from prometheus.semantic_audit import SeedIdentity, SemanticAuditEngine


@dataclass
class SeedStatus:
    """种子状态信息"""

    path: str
    identity: SeedIdentity
    is_active: bool = False
    warm_since: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class FireKeeper:
    """火种守护者"""

    def __init__(self):
        self.chronicler = Chronicler()
        self.engine = SemanticAuditEngine()
        self._active_fires: dict[str, SeedStatus] = {}

    def detect_seed_in_cwd(self, cwd: str) -> str | None:
        """在工作目录中检测是否有火种"""
        # 检查常见的 Prometheus 种子标记
        seed_markers = [
            "SKILL.md",
            "SEED.md",
            ".prometheus/",
            "prometheus.py",
            "README.md",  # 检查 README 中是否有相关关键词
        ]

        for filename in seed_markers:
            path = os.path.join(cwd, filename)
            if os.path.exists(path):
                # 进一步验证这是否是 Prometheus 种子
                if self._validate_seed_path(path):
                    return path

        # 检查父目录
        parent = os.path.dirname(cwd)
        if parent and parent != cwd:
            return self.detect_seed_in_cwd(parent)

        return None

    def _validate_seed_path(self, path: str) -> bool:
        """验证路径是否是一个有效的 Prometheus 种子"""
        if os.path.isdir(path):
            # 检查目录中是否有标记文件
            return os.path.exists(os.path.join(path, "SKILL.md")) or os.path.exists(
                os.path.join(path, "SEED.md")
            )
        elif os.path.isfile(path):
            # 检查文件中是否有 Prometheus 关键词
            try:
                with open(path, encoding="utf-8") as f:
                    content = f.read()
                    return (
                        "Prometheus" in content
                        or "prometheus" in content
                        or "普罗米修斯" in content
                        or "founder_chronicle" in content
                    )
            except Exception:
                return False
        return False

    def warm_seed(self, seed_path: str) -> SeedStatus:
        """预热种子，使其进入活跃状态"""
        # 先识别种子身份
        reading = self.engine.ingest(seed_path)
        classification = self.engine.classify(reading)

        status = SeedStatus(
            path=seed_path,
            identity=classification.identity,
            is_active=True,
            warm_since=0.0,  # 这里可以记录时间戳
            metadata={"classification": classification},
        )

        # 记录在活跃火焰中
        self._active_fires[seed_path] = status

        # 尝试烙印（如果需要）
        if classification.identity != SeedIdentity.OUR_FRAMEWORK:
            with contextlib.suppress(Exception):
                self.chronicler.stamp(seed_path)

        return status

    def extinguish(self, seed_path: str):
        """熄灭火种（归档）"""
        if seed_path in self._active_fires:
            self._active_fires[seed_path].is_active = False

    def is_seed_warm(self, seed_path: str) -> bool:
        return seed_path in self._active_fires and self._active_fires[seed_path].is_active

    def get_seed_status(self, seed_path: str) -> SeedStatus | None:
        return self._active_fires.get(seed_path)

    def list_active_seeds(self) -> list[SeedStatus]:
        return [s for s in self._active_fires.values() if s.is_active]
