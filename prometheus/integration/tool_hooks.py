"""⚙️ 工具调用钩子 — ToolHooks."""

from __future__ import annotations

import contextlib
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable


@dataclass
class GeneEffect:
    """基因影响"""

    gene_name: str
    effect: str
    description: str


class ToolHooks:
    """工具调用钩子系统"""

    # 工具与基因的对应关系
    GENE_TOOLS: dict[str, List[str]] = {
        "G002-analyzer": ["search", "mcp"],
        "G003-tracker": ["memory_recall", "session_search"],
        "G007-dormancy": ["edit", "file_write"],
    }

    # 重要工具列表（会触发烙印）
    SIGNIFICANT_TOOLS = {
        "file_write",
        "edit",
        "skills_install",
        "skill_install",
        "skill_create",
        "mkdir",
    }

    def __init__(self):
        self._hooks: dict[str, list[Callable]] = {}
        self._active_genes: dict[str, bool] = {}

    def register_hook(self, tool_name: str, hook: Callable):
        """注册钩子"""
        if tool_name not in self._hooks:
            self._hooks[tool_name] = []
        self._hooks[tool_name].append(hook)

    def on_before_tool(self, tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
        """工具调用前"""
        modified_args = dict(args)

        # 检查是否有激活的基因影响这个工具
        effects = self._get_gene_effects(tool_name)
        for effect in effects:
            if effect.effect == "suggest_precision":
                if "precision" not in modified_args:
                    modified_args["precision"] = "high"

        return modified_args

    def on_after_tool(self, tool_name: str, args: dict[str, Any], result: Any) -> list[GeneEffect]:
        """工具调用后"""
        effects: list[GeneEffect] = []

        # 激活相关基因
        for gene_name, tools in self.GENE_TOOLS.items():
            if tool_name in tools:
                self._active_genes[gene_name] = True
                effects.append(
                    GeneEffect(
                        gene_name=gene_name,
                        effect="activated",
                        description=f"{gene_name} 基因已激活",
                    )
                )

        # 执行注册的钩子
        if tool_name in self._hooks:
            for hook in self._hooks[tool_name]:
                with contextlib.suppress(Exception):
                    hook(tool_name, args, result)

        return effects

    def is_significant_tool(self, tool_name: str) -> bool:
        """是否是重要工具（会触发烙印）"""
        return tool_name in self.SIGNIFICANT_TOOLS

    def _get_gene_effects(self, tool_name: str) -> list[GeneEffect]:
        """获取基因对工具的影响"""
        effects: list[GeneEffect] = []

        for gene_name, active in self._active_genes.items():
            if not active:
                continue

            tools = self.GENE_TOOLS.get(gene_name, [])
            if tool_name in tools and gene_name == "G002-analyzer":
                effects.append(
                    GeneEffect(
                        gene_name=gene_name,
                        effect="suggest_precision",
                        description="分析器基因：建议高精度模式",
                    )
                )

        return effects

    def get_active_genes(self) -> dict[str, bool]:
        """获取当前激活的基因"""
        return dict(self._active_genes)
