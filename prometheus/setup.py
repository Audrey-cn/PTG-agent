#!/usr/bin/env python3
"""
Prometheus 初始化系统
参考 Hermes 的交互式引导体验
"""

import os
import sys
from pathlib import Path
from typing import Optional, Dict, Any

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from prometheus.memory_system import MemorySystem, get_prometheus_home, get_memories_dir
from prometheus.config import Config


def print_banner():
    """打印欢迎横幅"""
    banner = r"""
  ____                            _                 
 |  _ \ _ __ ___  _ __ ___  _   _| |__   ___  ___  
 | |_) | '__/ _ \| '_ ` _ \| | | | '_ \ / _ \/ __| 
 |  __/| | | (_) | | | | | | |_| | |_) |  __/\__ \ 
 |_|   |_|  \___/|_| |_| |_|\__,_|_.__/ \___||___/ 
                                                  
    """
    print(banner)
    print("=" * 65)
    print("🔥  史诗编史官 — 让智慧生长")
    print("=" * 65)
    print()


def get_input(prompt: str, default: Optional[str] = None) -> str:
    """获取用户输入，支持默认值"""
    if default:
        prompt = f"{prompt} [{default}] "
    else:
        prompt = f"{prompt} "
    
    try:
        value = input(prompt).strip()
        return value or default or ""
    except (EOFError, KeyboardInterrupt):
        print("\n\n操作已取消。")
        sys.exit(0)


def get_choice(prompt: str, options: list, default: int = 1) -> int:
    """获取用户选择"""
    while True:
        try:
            for i, option in enumerate(options, 1):
                print(f"  {i}. {option}")
            choice = get_input(f"\n{prompt}", str(default))
            choice_idx = int(choice) - 1
            if 0 <= choice_idx < len(options):
                return choice_idx
            print(f"请输入 1-{len(options)} 之间的数字")
        except ValueError:
            print("请输入有效的数字")


def create_config():
    """创建配置文件"""
    config_path = get_prometheus_home() / "config.yaml"
    
    if config_path.exists():
        return False
    
    default_config = """# Prometheus 配置文件
# 由初始化系统自动生成，可根据需要修改

skin: default

memory:
  compression_threshold: 5000
  proposal_threshold: 3
  cooldown_hours: 24

skills:
  auto_discovery: true
  dangerous_mode: false
"""
    
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(default_config, encoding="utf-8")
    return True


def create_initial_skills():
    """创建初始技能目录结构"""
    skills_dir = get_prometheus_home() / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)
    
    # 创建 README
    readme_path = skills_dir / "README.md"
    if not readme_path.exists():
        readme_path.write_text("""# Prometheus 技能库

这里存储您的自定义技能。

## 目录结构

```
skills/
├── category1/
│   └── skill_name/
│       └── SKILL.md
└── category2/
    └── another_skill/
        └── SKILL.md
```

## SKILL.md 格式

```markdown
---
name: 技能名称
description: 技能描述
tags: [tag1, tag2]
version: "1.0"
author: 作者
---

# 技能说明

这里是技能的详细说明和使用指南。
```
""", encoding="utf-8")


def run_setup():
    """运行交互式初始化"""
    print_banner()
    
    # 检查是否已经初始化
    memory = MemorySystem()
    if not memory.is_first_run():
        print("✅  Prometheus 已经初始化过了！")
        print(f"\n配置目录：{get_prometheus_home()}")
        print("如需重新初始化，请先删除该目录。")
        return False
    
    print("让我们一起开始您的 Prometheus 之旅吧！\n")
    
    # 步骤 1: 用户信息
    print("---\n📝  步骤 1: 创建您的身份\n")
    username = get_input("您的名字是？", "探索者")
    
    # 沟通风格
    print("\n请选择您偏好的沟通风格：")
    style_options = [
        "简洁专业 — 直接给出结果，减少冗余",
        "友好详细 — 详细解释，友好互动",
        "技术导向 — 注重技术细节和精确性"
    ]
    style_choice = get_choice("您的选择是？", style_options, 1)
    styles = ["简洁专业", "友好详细", "技术导向"]
    communication_style = styles[style_choice]
    
    # 工作偏好
    print("\n请选择您的工作偏好：")
    work_options = [
        "效率优先 — 快速完成，注重结果",
        "质量优先 — 精益求精，注重细节",
        "学习优先 — 探索学习，注重成长"
    ]
    work_choice = get_choice("您的选择是？", work_options, 1)
    work_preferences = ["效率优先", "质量优先", "学习优先"][work_choice]
    
    # 步骤 2: AI 个性
    print("\n---\n🤖  步骤 2: 定义 AI 个性\n")
    personality_options = [
        "友好、专业、简洁 — 平衡型助手",
        "严谨、详细、学术 — 专家型助手",
        "轻松、幽默、创意 — 创意型助手"
    ]
    personality_choice = get_choice("您希望的 AI 风格是？", personality_options, 1)
    personalities = [
        "友好、专业、简洁",
        "严谨、详细、学术",
        "轻松、幽默、创意"
    ]
    personality = personalities[personality_choice]
    
    # 步骤 3: 确认
    print("\n---\n✅  步骤 3: 确认设置\n")
    print("请确认以下信息：")
    print(f"  👤  名字：{username}")
    print(f"  💬  沟通风格：{communication_style}")
    print(f"  ⚡  工作偏好：{work_preferences}")
    print(f"  🤖  AI 个性：{personality}")
    
    confirm = get_input("\n确认创建？[Y/n]", "Y").lower()
    if confirm not in ["y", "yes", ""]:
        print("\n设置已取消。")
        return False
    
    # 执行创建
    print("\n正在创建...")
    
    # 创建记忆文件
    memory.create_user_profile(username, communication_style, work_preferences)
    memory.create_soul(personality)
    memory.create_memory()
    
    # 创建配置文件
    if create_config():
        print("  ✅  配置文件已创建")
    
    # 创建技能目录
    create_initial_skills()
    print("  ✅  技能目录已初始化")
    
    # 完成
    print("\n" + "=" * 65)
    print("🎉  初始化完成！")
    print("=" * 65)
    print(f"\n欢迎，{username}！")
    print("\n您的 Prometheus 环境已就绪：")
    print(f"  📁  配置目录：{get_prometheus_home()}")
    print(f"  📝  用户画像：{get_prometheus_home() / 'memories' / 'USER.md'}")
    print(f"  🤖  AI 个性：{get_prometheus_home() / 'SOUL.md'}")
    print("\n您可以随时编辑这些文件来自定义您的体验。")
    print("\n现在，让我们开始吧！🚀")
    print()
    
    return True


if __name__ == "__main__":
    try:
        run_setup()
    except Exception as e:
        print(f"\n❌  初始化出错：{e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
