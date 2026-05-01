"""🌱 进化守护者 — EvolutionGuard."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


@dataclass
class EvolutionProposal:
    """进化提案"""

    id: str
    title: str
    description: str
    target_file: str
    created_at: datetime = field(default_factory=datetime.now)
    status: str = "pending"
    reason: str = ""


class EvolutionGuard:
    """进化守护者"""

    def __init__(self, prometheus_home: str | None = None):
        if prometheus_home is None:
            prometheus_home = os.path.expanduser("~/.prometheus")
        self.prometheus_home = Path(prometheus_home)

        # 配置
        self.proposal_threshold: int = 3
        self.cooldown_hours: int = 24

        # 状态追踪
        self._pending_proposals: list[EvolutionProposal] = []
        self._tool_calls_since_proposal: int = 0
        self._last_proposal_at: datetime | None = None

    def check_triggers(self, messages: list[Any], tool_count: int) -> list[EvolutionProposal]:
        """检查是否需要提出进化提案"""
        proposals: list[EvolutionProposal] = []

        # 规则 1：累计工具调用阈值
        self._tool_calls_since_proposal += tool_count
        if self._tool_calls_since_proposal >= self.proposal_threshold:
            prop = self._generate_proposal_from_usage(tool_count)
            if prop:
                proposals.append(prop)

        # 规则 2：SOUL.md 中提到的阈值（简单实现）
        soul_proposals = self._check_soul_triggers()
        proposals.extend(soul_proposals)

        # 检查冷却期
        if self._in_cooldown():
            return []

        return proposals

    def _in_cooldown(self) -> bool:
        """是否在冷却期"""
        if self._last_proposal_at is None:
            return False

        now = datetime.now()
        cooldown = timedelta(hours=self.cooldown_hours)
        return (now - self._last_proposal_at) < cooldown

    def _generate_proposal_from_usage(self, tool_count: int) -> EvolutionProposal | None:
        """从使用模式生成提案"""
        return EvolutionProposal(
            id=f"evolution_{int(datetime.now().timestamp())}",
            title="工具使用频繁",
            description=f"已累计 {tool_count} 次工具调用，考虑创建技能",
            target_file="MEMORY.md",
            reason="high_tool_usage",
        )

    def _check_soul_triggers(self) -> list[EvolutionProposal]:
        """检查 SOUL.md 中定义的触发条件"""
        proposals: list[EvolutionProposal] = []

        # 简单实现：检查 SOUL.md 是否存在并包含某些关键词
        soul_path = self.prometheus_home / "SOUL.md"
        if soul_path.exists():
            try:
                with open(soul_path, encoding="utf-8") as f:
                    soul = f.read()

                if "进化" in soul or "evolution" in soul.lower():
                    proposals.append(
                        EvolutionProposal(
                            id=f"soul_trigger_{int(datetime.now().timestamp())}",
                            title="SOUL 触发进化检查",
                            description="SOUL.md 中提到了进化相关内容",
                            target_file="SOUL.md",
                            reason="soul_trigger",
                        )
                    )
            except Exception:
                pass

        return proposals

    def propose_evolution(self, proposal: EvolutionProposal) -> bool:
        """提出进化提案"""
        if self._in_cooldown():
            return False

        self._pending_proposals.append(proposal)
        self._last_proposal_at = datetime.now()
        self._tool_calls_since_proposal = 0

        # 保存提案到文件（简单实现）
        self._save_proposals()

        return True

    def get_pending_proposals(self) -> list[EvolutionProposal]:
        """获取待审核的提案"""
        return self._pending_proposals

    def _save_proposals(self):
        """保存提案到文件（简单实现）"""
        try:
            proposal_dir = self.prometheus_home / "proposals"
            proposal_dir.mkdir(exist_ok=True)

            for proposal in self._pending_proposals:
                file_path = proposal_dir / f"{proposal.id}.md"
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(f"# {proposal.title}\n\n")
                    f.write(f"{proposal.description}\n\n")
                    f.write(f"Status: {proposal.status}\n")
                    f.write(f"Created: {proposal.created_at}\n")
        except Exception:
            pass
