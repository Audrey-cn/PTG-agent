#!/usr/bin/env python3
"""
TTG识别工具 · 新格式 SEED 魔数

多级识别策略：smart / simple / basic
支持 Agent 在不解码内容的情况下确认文件类型
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)

MAGIC = b"SEED"
CRYPTIC_PREFIX_SIGNATURES = [
    b"\xe9\xbe\xa2",  # 龢的UTF-8编码
    b"\xe7\xa8\xae",  # 種
    b"\xe5\xa3\xb9",  # 壹
]


class TTGRecognitionTool:
    """多级Agent识别工具"""

    def recognize(self, file_data: bytes, agent_level: str = "smart") -> Dict[str, Any]:
        if agent_level == "smart":
            return self._smart_recognition(file_data)
        elif agent_level == "simple":
            return self._simple_recognition(file_data)
        elif agent_level == "basic":
            return self._basic_recognition(file_data)
        return self._smart_recognition(file_data)

    def _smart_recognition(self, data: bytes) -> dict:
        result = {
            "is_seed": False, "format": "unknown",
            "confidence": 0.0, "strategy": "smart",
            "hint": "",
        }

        try:
            if MAGIC in data[:500]:
                result["is_seed"] = True
                result["format"] = "seed_binary"
                result["confidence"] = 0.95

                try:
                    pos = data.find(MAGIC) + len(MAGIC)
                    import struct
                    hl = struct.unpack(">I", data[pos:pos + 4])[0]
                    hd = json.loads(data[pos + 4:pos + 4 + hl])
                    result["life_id"] = hd.get("lid", "unknown")
                    result["era"] = hd.get("era", "?")
                    result["gene_tally"] = hd.get("gt", 0)
                except Exception:
                    pass

                result["hint"] = "使用 SeedManager.awaken() 加载此种子"
                return result

            prefix_text = data[:200].decode("utf-8", errors="ignore")
            if "龢" in prefix_text and "種" in prefix_text:
                result["is_seed"] = True
                result["format"] = "seed_binary"
                result["confidence"] = 0.7
                result["hint"] = "发现加密前缀，可能为新格式种子"
                return result

        except Exception as e:
            logger.warning(f"智能识别异常: {e}")

        return result

    def _simple_recognition(self, data: bytes) -> dict:
        result = {
            "is_seed": False, "format": "unknown",
            "confidence": 0.0, "strategy": "simple",
            "hint": "",
        }

        try:
            text = data[:500].decode("utf-8", errors="ignore")
            keywords = ["龢", "種", "SEED", "§LC", "life_crest"]
            matches = [k for k in keywords if k in text]

            if matches:
                result["is_seed"] = True
                result["format"] = "seed_likely"
                result["confidence"] = 0.6
                result["keywords"] = matches
                result["hint"] = "可能为种子文件，建议使用智能识别"
                return result

            if 50 < len(data) < 10 * 1024 * 1024:
                json_start = data.find(b'{"')
                if 0 < json_start < 1000:
                    result["is_seed"] = True
                    result["confidence"] = 0.4
                    result["hint"] = "发现JSON结构，可能为种子文件"

        except Exception as e:
            logger.warning(f"简单识别异常: {e}")

        return result

    def _basic_recognition(self, data: bytes) -> dict:
        result = {
            "is_seed": False, "format": "unknown",
            "confidence": 0.0, "strategy": "basic",
            "hint": "",
        }

        try:
            text = data[:1000].decode("utf-8", errors="ignore")
            readable = sum(1 for c in text if c.isprintable() or c.isspace())
            ratio = readable / max(len(text), 1)

            if 100 < len(data) < 5 * 1024 * 1024 and 0.1 < ratio < 0.95:
                result["is_seed"] = True
                result["confidence"] = 0.3
                result["hint"] = "混合内容文件，可能是种子格式"

        except Exception:
            pass

        return result

    def get_preview(self, data: bytes) -> dict:
        return {
            "size": len(data),
            "has_magic": MAGIC in data,
            "prefix": data[:100].decode("utf-8", errors="ignore")[:100],
            "recognition": self.recognize(data),
        }
