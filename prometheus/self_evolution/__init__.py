#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════╗
║   🧬 普罗米修斯 · 自进化引擎 · Self-Evolution Engine         ║
║                                                              ║
║   集成 init-skill 的核心功能：                               ║
║     - Observe：观察并记录模式                                 ║
║     - Learn：从用户纠正中学习                                  ║
║     - Consult：咨询已学习的规则                                 ║
║     - Verify：验证规则的有效性                                 ║
║                                                              ║
║   与 Prometheus 现有系统集成：                                ║
║     - 记忆系统 (memory/)                                     ║
║     - 技能系统 (skills/)                                    ║
╚══════════════════════════════════════════════════════════════╝
"""

from .engine import SelfEvolutionEngine
from .observer import Observer
from .learner import Learner
from .consultant import Consultant
from .verifier import Verifier
from .initializer import ProjectInitializer

__all__ = [
    "SelfEvolutionEngine",
    "Observer",
    "Learner",
    "Consultant",
    "Verifier",
    "ProjectInitializer",
]
