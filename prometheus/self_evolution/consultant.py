#!/usr/bin/env python3
"""
咨询者模块 - 提供已学习的规则
"""

from pathlib import Path
from typing import Optional


class Consultant:
    """咨询者类"""

    def __init__(self, memory_dir: Path):
        self.memory_dir = memory_dir
        self.rules_file = memory_dir / "learned-rules.md"
    
    def get_rules(self) -> str:
        """获取已学习的规则"""
        if not self.rules_file.exists():
            return "# Learned Rules

No rules learned yet. Start coding and learning!"
        
        with open(self.rules_file, "r", encoding="utf-8") as f:
            return f.read()
    
    def count_rules(self) -> int:
        """统计规则数量（通过计算标题数量）"""
        if not self.rules_file.exists():
            return 0
        
        count = 0
        with open(self.rules_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("## "):
                    count += 1
        
        return count
