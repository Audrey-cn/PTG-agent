#!/usr/bin/env python3
"""
族谱管理者

压缩标记的解码者，史诗叙事的编织者。
从解码后的 genealogy_codex 生成谱系可视化、传递史诗、分支对比。
"""

from __future__ import annotations

import hashlib
import json
import os
import datetime
from typing import Any, Dict, List, Optional


class GenealogyKeeper:
    """族谱学者——解码标记，编织史诗"""

    LINEAGE_LAWS = {
        "naming": "L{lineage}-G{gen}-{variant}-{checksum}",
        "fork_on_env_change": True,
        "fork_on_major_innovation": True,
    }

    ENV_LEXICON = {
        "MAC-H12": "macOS · Prometheus 0.12 · 数字神殿",
        "LNX-H11": "Linux · Prometheus 0.11 · 雷暴荒原",
        "LNX-H13": "Linux · Prometheus 0.13 · 汇流之港",
    }

    CARETAKER_NAMES = {
        "ANA": "Agent Ana · 始祖播种者",
        "ARK": "Agent Ark · 雷暴锻造者",
    }

    def __init__(self, archive_dir: str = "~/.prometheus/genealogy-archive",
                 tag_lexicon: dict = None):
        self.archive_dir = os.path.expanduser(archive_dir)
        os.makedirs(self.archive_dir, exist_ok=True)
        self.tag_lexicon = tag_lexicon or {}

    def decode_generation(self, gen: dict) -> dict:
        """将压缩代次记录解码为叙事"""
        tags = gen.get("tags", [])
        caretaker = gen.get("by", "?")
        caretaker_epic = self.CARETAKER_NAMES.get(caretaker, caretaker)
        env_code = gen.get("env", "?")
        env_epic = self.ENV_LEXICON.get(env_code, env_code)

        mutations = []
        elements = set()
        for tag in tags:
            entry = self.tag_lexicon.get(tag, {"desc": tag, "element": "?", "era": "?"})
            mutations.append({"tag": tag, "desc": entry["desc"], "element": entry["element"], "era": entry["era"]})
            elements.add(entry["element"])

        eras = list(set(m["era"] for m in mutations if m["era"] != "?"))
        era = eras[0] if eras else "未知纪元"

        return {
            "generation": gen.get("g", "?"),
            "variant": gen.get("v", "?"),
            "caretaker_epic": caretaker_epic,
            "environment": env_epic,
            "era": era,
            "elements": list(elements),
            "mutations": mutations,
            "parent": gen.get("p"),
        }

    def render_lineage_tree(self, bloodline: dict, generations: list) -> str:
        """渲染谱系树"""
        bn = bloodline.get("bloodline_name", "未知之脉")
        el = bloodline.get("element", "?")
        tot = bloodline.get("totem", "?")
        prop = bloodline.get("founding_prophecy", "")

        tree = f"""
╔══════════════════════════════════════════════════════════════╗
║   🌌 {bn} · {el}                                          ║
║   {tot}                                                    ║
║   「{prop}」                                               ║
╠══════════════════════════════════════════════════════════════╣
"""
        for i, gen in enumerate(generations):
            decoded = self.decode_generation(gen)
            connector = "║  " if i == 0 else "║  " + "│  " * (i - 1) + "├──"
            indent = "" if i == 0 else "   " * i

            first_mut = decoded["mutations"][0]["desc"] if decoded["mutations"] else "生命延续"
            mut_tags = ", ".join(m["tag"] for m in decoded["mutations"][:5])
            elem_str = " · ".join(decoded["elements"][:3]) if decoded["elements"] else "无"

            tree += f"""║                                                              ║
║  {connector} 🌿 G{decoded['generation']} · {decoded['variant']} · {decoded['caretaker_epic']}
║  {indent}   「{first_mut}」
║  {indent}   元素: {elem_str} · 纪元: {decoded['era']} · 环境: {decoded['environment']}
"""
            if len(decoded["mutations"]) > 0:
                tree += f"║  {indent}   突变: {mut_tags}\n"

        tree += """║                                                              ║
╚══════════════════════════════════════════════════════════════╝
"""
        return tree

    def trace_ancestry(self, life_id: str) -> dict:
        """追溯血脉"""
        records = []
        for fname in os.listdir(self.archive_dir):
            if fname.endswith('.json'):
                fpath = os.path.join(self.archive_dir, fname)
                try:
                    with open(fpath, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        if life_id.split('@')[-1] in fname or life_id in str(data):
                            records.append(data)
                except Exception:
                    pass
        return {
            "queried": life_id,
            "depth": len(records),
            "records": records,
        }

    def create_offspring_lineage(self, parent_crest: dict, parent_gx: dict,
                                  variant_name: str, tags: list,
                                  creator: str) -> dict:
        """创建后代谱系"""
        curr = parent_gx.get("current_genealogy", {})
        parent_id = parent_crest.get("life_id", "unknown")
        new_gen = curr.get("generation", 0) + 1
        parent_lineage = curr.get("lineage", "L1")

        checksum = hashlib.md5(
            f"{parent_lineage}-{new_gen}-{variant_name}-{datetime.datetime.now().isoformat()}".encode()
        ).hexdigest()[:8].upper()

        new_life_id = f"TTG@{parent_lineage}-G{new_gen}-{variant_name}-{checksum}"

        compressed_gen = {
            "g": new_gen,
            "v": variant_name,
            "ep": f"Y{datetime.datetime.now().year}-D{datetime.datetime.now().timetuple().tm_yday}",
            "env": self._hash_env(),
            "tags": tags,
            "by": creator[:3].upper(),
            "p": parent_id,
        }

        return {
            "life_id": new_life_id,
            "genealogy": {
                "lineage": parent_lineage,
                "bloodline": curr.get("bloodline", "未知之脉"),
                "generation": new_gen,
                "variant": variant_name,
                "parent": parent_id,
                "ancestors": curr.get("ancestors", []) + [parent_id],
                "descendants": [],
            },
            "compressed_gen": compressed_gen,
            "decoded": self.decode_generation(compressed_gen),
        }

    def _hash_env(self) -> str:
        import platform
        os_name = platform.system()[:3].upper()
        return f"{os_name}-H??"
