#!/usr/bin/env python3
"""
学习者模块 - 从用户纠正中学习
"""

import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional


class Learner:
    """学习者类"""

    def __init__(self, memory_dir: Path):
        self.memory_dir = memory_dir
        self.corrections_file = memory_dir / "corrections.jsonl"
        self.rules_file = memory_dir / "learned-rules.md"
        self.promotion_threshold = 2  # 需要出现2次才晋升
    
    def record_correction(self, original: str, corrected: str, feedback: str, context: str = "") -> Dict[str, Any]:
        """记录一个纠正"""
        correction = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "original": original,
            "corrected": corrected,
            "feedback": feedback,
            "context": context,
            "fingerprint": self._fingerprint(original, corrected),
        }
        
        # 追加到文件
        with open(self.corrections_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(correction, ensure_ascii=False) + "\n")
        
        # 检查是否应该晋升
        should_promote = self._should_promote(correction["fingerprint"])
        
        return {
            "success": True,
            "correction": correction,
            "should_promote": should_promote,
        }
    
    def _fingerprint(self, original: str, corrected: str) -> str:
        """生成纠正的指纹，用于检测重复"""
        content = f"{original}|{corrected}"
        return hashlib.md5(content.encode()).hexdigest()[:12]
    
    def _should_promote(self, fingerprint: str) -> bool:
        """检查是否应该晋升为规则"""
        if not self.corrections_file.exists():
            return False
        
        count = 0
        with open(self.corrections_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        correction = json.loads(line)
                        if correction.get("fingerprint") == fingerprint:
                            count += 1
                    except json.JSONDecodeError:
                        continue
        
        return count >= self.promotion_threshold
    
    def promote_to_rule(self, correction: Dict[str, Any]) -> bool:
        """将纠正晋升为规则"""
        rule_content = f"""
## {correction["timestamp"][:10]} - {correction["fingerprint"]}

**Problem:** {correction["original"]}

**Solution:** {correction["corrected"]}

**Feedback:** {correction["feedback"]}

**Context:** {correction.get("context", "")}

---
"""
        
        # 确保文件存在
        if not self.rules_file.exists():
            with open(self.rules_file, "w", encoding="utf-8") as f:
                f.write("# Learned Rules

This file contains rules learned from user corrections and verified patterns.

---

")
        
        # 追加规则
        with open(self.rules_file, "a", encoding="utf-8") as f:
            f.write(rule_content)
        
        return True
    
    def count_corrections(self) -> int:
        """统计纠正数量"""
        if not self.corrections_file.exists():
            return 0
        
        count = 0
        with open(self.corrections_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    count += 1
        
        return count
