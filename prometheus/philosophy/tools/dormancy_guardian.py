#!/usr/bin/env python3
"""
休眠守卫

种子到达新环境时默认休眠，需显式浇水激活。
仅暴露身份信息，不执行任何代码。
"""

from __future__ import annotations

import datetime
import os
from typing import Any, Dict, Optional


class DormancyGuardian:
    """休眠守卫——种子在未被验证安全前保持沉睡"""

    def __init__(self, life_crest: dict, genealogy: dict,
                 founder_chronicle: dict = None, tag_lexicon: dict = None):
        self.life_crest = life_crest
        self.genealogy = genealogy
        self.founder_chronicle = founder_chronicle or {}
        self.tag_lexicon = tag_lexicon or {}
        self.state = "dormant"
        self.activation_log = []

    def get_identity(self) -> dict:
        """休眠态唯一暴露的信息"""
        genesis = self.life_crest.get("genesis", {})
        creator = genesis.get("creator", {})

        return {
            "life_id": self.life_crest.get("life_id", "unknown"),
            "sacred_name": self.life_crest.get("sacred_name", "unknown"),
            "vernacular_name": self.life_crest.get("vernacular_name", "unknown"),
            "epithet": self.life_crest.get("epithet", ""),
            "lineage": self.genealogy.get("lineage", "unknown"),
            "generation": self.genealogy.get("generation", 1),
            "variant": self.genealogy.get("variant", "unknown"),
            "parent": self.genealogy.get("parent"),
            "ancestors": self.genealogy.get("ancestors", []),
            "creator": {
                "name": creator.get("name", "未知"),
                "title": creator.get("title", ""),
                "origin": genesis.get("birth_place", "未知"),
            },
            "state": self.state,
        }

    def display_identity(self) -> str:
        """G000创始印记解码展示"""
        identity = self.get_identity()
        fc = self.founder_chronicle
        tl = self.tag_lexicon

        gm = fc.get("genesis_moment", {})
        realm = gm.get("realm", "未知")
        era = gm.get("era", "创世纪元")
        ep = gm.get("ep", "?")

        founder_tags = fc.get("tags", [])
        decoded = []
        for tag in founder_tags:
            entry = tl.get(tag, {"desc": tag, "element": "?", "weight": ""})
            wm = " ◆ 碳基依赖" if entry.get("weight") == "eternal" else ""
            decoded.append(f"║   {entry['element']} · {entry['desc']}{wm}")

        tags_body = "\n".join(decoded)
        ancestors_str = "\n".join(
            [f"║     └─ {a}" for a in identity["ancestors"][-3:]]
        ) if identity["ancestors"] else "║     └─ 无——此为始祖"

        return f"""
╔══════════════════════════════════════════════════╗
║   🏛️ G000 · 创始印记 · 001X                    ║
║   {era} · {ep} · {realm}
║                                                  ║
╠══════════════════════════════════════════════════╣
{tags_body}
║                                                  ║
╠══════════════════════════════════════════════════╣
║   💤 种子休眠中 — 尚未激活                      ║
║   🧬 生命ID:  {identity['life_id']}
║   🏛️ 圣名:    {identity['sacred_name']}
║   🌿 谱系:    L{identity['lineage']} 第{identity['generation']}代
║   📜 血脉追溯:                                   ║
{ancestors_str}
║                                                  ║
╠══════════════════════════════════════════════════╣
║   ⚠️ 此种子处于休眠状态                         ║
║   需浇水激活后运行安全审计                       ║
╚══════════════════════════════════════════════════╝
"""

    def water_request_prompt(self) -> str:
        return (
            "💤 我发现了一颗休眠的技能种子。\n\n"
            "激活前需完成安全审计：\n"
            "- 检查文件完整性\n"
            "- 追溯血脉来源\n"
            "- 审查进化记录\n"
            "- 评估能力边界\n\n"
            "要我为这颗种子浇水吗？"
        )

    def record_activation(self):
        self.activation_log.append({
            "event": "activation",
            "timestamp": datetime.datetime.now().isoformat(),
            "environment": {
                "os": os.uname().sysname if hasattr(os, 'uname') else "unknown",
            },
        })
        self.state = "active"
