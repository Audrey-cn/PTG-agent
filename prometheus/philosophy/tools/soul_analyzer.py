#!/usr/bin/env python3
"""
灵魂分析器

从原始技能文本中提取核心原则、禁忌、气质。
输出的结构化数据可由 genome_encoder 编码为基因组。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class SoulReport:
    skill_name: str
    core_capabilities: list = field(default_factory=list)
    core_principles: list = field(default_factory=list)
    taboos: list = field(default_factory=list)
    essence: dict = field(default_factory=dict)
    analyzed_at: str = ""


class SoulAnalyzer:
    """从任意技能文本提取灵魂"""

    PRINCIPLE_PATTERNS = [
        (r'(?:核心|必须|一定|务必|永远|始终)(?:要|需要|应该)?[：:]\s*(.+?)(?:\n|$)', 'directive'),
        (r'(?:原则|规则|信条)\d*[：:]\s*(.+?)(?:\n|$)', 'principle'),
        (r'##\s*(?:核心|原则|规范|准则)[^\n]*\n(.+?)(?=\n##|\Z)', 'section'),
    ]

    TABOO_PATTERNS = [
        r'[❌🚫⛔⚠️](.+?)(?:\n|$)',
        r'(?:不要|禁止|绝不|不可|严禁)[：:]*\s*(.+?)(?:\n|$)',
        r'禁忌[：:]\s*(.+?)(?:\n|$)',
    ]

    @staticmethod
    def analyze(content: str, skill_name: str = "unknown") -> SoulReport:
        """分析技能内容，提取灵魂"""
        return SoulReport(
            skill_name=skill_name,
            core_principles=SoulAnalyzer._extract_principles(content),
            taboos=SoulAnalyzer._extract_taboos(content),
            essence=SoulAnalyzer._sense_essence(content, skill_name),
            core_capabilities=SoulAnalyzer._extract_capabilities(content),
        )

    @staticmethod
    def _extract_capabilities(content: str) -> list:
        """从内容中推断核心能力"""
        caps = []
        patterns = [
            r'(?:能力|功能|capabilit)[：:]\s*(.+?)(?:\n|$)',
            r'##\s*(?:功能|能力|特色)[^\n]*\n(.+?)(?=\n##|\Z)',
        ]
        for pattern, _ in [(p, '') for p in patterns]:
            matches = re.findall(pattern, content, re.DOTALL | re.IGNORECASE)
            for m in matches[:8]:
                caps.append({"name": m.strip()[:80], "description": m.strip()[:200], "immutable": True})
        return caps

    @staticmethod
    def _extract_principles(content: str) -> list:
        principles = []
        for pattern, ptype in SoulAnalyzer.PRINCIPLE_PATTERNS:
            matches = re.findall(pattern, content, re.DOTALL | re.IGNORECASE)
            for i, match in enumerate(matches):
                principles.append({
                    "id": f"AUTO-P{i+1}",
                    "name": match.strip()[:80],
                    "description": match.strip()[:200],
                    "test": "",
                    "immutable": True,
                })
        return principles[:10]

    @staticmethod
    def _extract_taboos(content: str) -> list:
        taboos = []
        for pattern in SoulAnalyzer.TABOO_PATTERNS:
            matches = re.findall(pattern, content, re.IGNORECASE)
            taboos.extend([m.strip()[:80] for m in matches])
        seen = set()
        unique = []
        for t in taboos:
            if t not in seen:
                seen.add(t)
                unique.append(t)
        return unique[:8]

    @staticmethod
    def _sense_essence(content: str, skill_name: str) -> dict:
        formal = content.count('请') + content.count('您')
        casual = content.count('直接') + content.count('就行')
        poetic = content.count('如') + content.count('若')

        if poetic > formal and poetic > casual:
            vibe = "诗意引导者"
        elif casual > formal:
            vibe = "亲切伙伴"
        else:
            vibe = "严谨导师"

        return {
            "vibe": vibe,
            "tone": "由内容自然感知",
            "role": "由功能自然推导",
            "oath": "",
        }
