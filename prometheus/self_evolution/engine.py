#!/usr/bin/env python3
"""
自进化引擎核心
"""

import os
from pathlib import Path
from typing import Optional, Dict, Any
from .observer import Observer
from .learner import Learner
from .consultant import Consultant
from .verifier import Verifier
from ..config import get_prometheus_home


class SelfEvolutionEngine:
    """自进化引擎核心类"""

    def __init__(self, project_dir: Optional[str] = None):
        self.project_dir = Path(project_dir) if project_dir else get_prometheus_home()
        self.claude_dir = self.project_dir / ".claude"
        self.memory_dir = self.claude_dir / "memory"
        
        # 确保目录存在
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        
        # 初始化组件
        self.observer = Observer(self.memory_dir)
        self.learner = Learner(self.memory_dir)
        self.consultant = Consultant(self.memory_dir)
        self.verifier = Verifier(self.memory_dir)
    
    def observe(self, pattern_type: str, content: str, context: str = "", confidence: float = 0.5) -> Dict[str, Any]:
        """观察并记录模式"""
        return self.observer.record(pattern_type, content, context, confidence)
    
    def learn_from_correction(self, original: str, corrected: str, feedback: str, context: str = "") -> Dict[str, Any]:
        """从用户纠正中学习"""
        result = self.learner.record_correction(original, corrected, feedback, context)
        
        # 检查是否应该晋升为规则
        if result.get("should_promote", False):
            self.learner.promote_to_rule(result["correction"])
        
        return result
    
    def consult(self) -> str:
        """咨询已学习的规则"""
        return self.consultant.get_rules()
    
    def verify(self) -> Dict[str, Any]:
        """验证规则的有效性"""
        return self.verifier.run_verification()
    
    def get_status(self) -> Dict[str, Any]:
        """获取进化引擎状态"""
        return {
            "project_dir": str(self.project_dir),
            "claude_dir": str(self.claude_dir),
            "memory_dir": str(self.memory_dir),
            "observations": self.observer.count(),
            "corrections": self.learner.count_corrections(),
            "rules": self.consultant.count_rules(),
        }
