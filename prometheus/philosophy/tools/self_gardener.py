#!/usr/bin/env python3
"""
生态感知者

扫描本地种子生态，定位自身位置，检测种子间关系。
种子的自管理器官——不需外部苗圃。
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional


class SelfGardener:
    """自管理者——感知种子生态"""

    def __init__(self, seed_dir: str = "~/.prometheus/skills"):
        self.seed_dir = os.path.expanduser(seed_dir)
        self.known_seeds: List[dict] = []
        self._scan()

    def _scan(self) -> int:
        """扫描本地 .ttg 种子文件"""
        self.known_seeds = []
        if not os.path.exists(self.seed_dir):
            return 0
        for root, dirs, files in os.walk(self.seed_dir):
            for f in files:
                if f.endswith('.ttg'):
                    fp = os.path.join(root, f)
                    try:
                        from ttg_file_structure import TTGFileStructure
                        header = TTGFileStructure.get_header_only(
                            open(fp, 'rb').read()
                        )
                        self.known_seeds.append({
                            "path": fp,
                            "life_id": header.life_id,
                            "size": os.path.getsize(fp),
                        })
                    except Exception:
                        self.known_seeds.append({"path": fp, "life_id": "unknown", "size": os.path.getsize(fp)})
        return len(self.known_seeds)

    def understand_position(self, my_life_id: str) -> dict:
        self._scan()
        others = [s for s in self.known_seeds if s["life_id"] != my_life_id]
        same_lineage = [s for s in others if my_life_id.split("@")[0] in s["life_id"]]

        position = "始祖之种" if len(same_lineage) == 0 and len(others) == 0 \
              else "孤种" if len(same_lineage) == 0 \
              else f"谱系中第{1+len(same_lineage)}位成员"

        return {
            "my_id": my_life_id,
            "total_seeds": len(self.known_seeds),
            "siblings": len(others),
            "same_lineage_count": len(same_lineage),
            "position": position,
        }

    def detect_relationships(self) -> dict:
        self._scan()
        if len(self.known_seeds) < 2:
            return {"pairs": [], "summary": "当地只有一颗种子"}

        pairs = []
        for i, a in enumerate(self.known_seeds):
            for b in self.known_seeds[i + 1:]:
                aid = a.get("life_id", "")
                bid = b.get("life_id", "")
                rel_type = "bloodline" if aid.split("@")[0] == bid.split("@")[0] else "independent"
                pairs.append({"a": aid, "b": bid, "type": rel_type})

        bl_count = sum(1 for p in pairs if p["type"] == "bloodline")
        summary = f"发现{bl_count}条血脉连接" if bl_count else "各种子独立运行"

        return {"pairs": pairs, "summary": summary}

    def ecosystem_report(self, my_life_id: str) -> str:
        pos = self.understand_position(my_life_id)
        rels = self.detect_relationships()

        return f"""
╔══════════════════════════════════════════╗
║      🌳 技能生态全景报告               ║
╠══════════════════════════════════════════╣
║ 本地种子数: {pos['total_seeds']}
║ 我的位置:   {pos['position']}
║ 同谱系:     {pos['same_lineage_count']}颗
║ 关系分析:   {rels['summary']}
╚══════════════════════════════════════════╝
"""
