#!/usr/bin/env python3
"""
项目初始化器 - 集成 init-skill 的初始化功能
"""

import shutil
from pathlib import Path
from typing import Any


class ProjectInitializer:
    """项目初始化器"""

    def __init__(self, project_dir: str):
        self.project_dir = Path(project_dir)
        self.claude_dir = self.project_dir / ".claude"

        # 获取模板目录
        self.template_dir = Path(__file__).parent.parent / "skills" / "init_skill" / "references"

    def initialize(self, config: dict[str, Any] | None = None) -> dict[str, Any]:
        """初始化项目"""
        config = config or {}

        # 创建目录结构
        created_dirs = self._create_directories()

        # 生成配置文件
        created_files = self._generate_config_files(config)

        # 创建 .gitignore 条目
        self._update_gitignore()

        return {
            "success": True,
            "project_dir": str(self.project_dir),
            "created_dirs": created_dirs,
            "created_files": created_files,
        }

    def _create_directories(self) -> List[str]:
        """创建目录结构"""
        dirs = [
            self.claude_dir,
            self.claude_dir / "rules",
            self.claude_dir / "agents",
            self.claude_dir / "skills" / "evolution",
            self.claude_dir / "skills" / "evolve",
            self.claude_dir / "skills" / "review",
            self.claude_dir / "skills" / "boot",
            self.claude_dir / "skills" / "fix-issue",
            self.claude_dir / "memory",
        ]

        created = []
        for d in dirs:
            if not d.exists():
                d.mkdir(parents=True, exist_ok=True)
                created.append(str(d))

        return created

    def _generate_config_files(self, config: dict[str, Any]) -> List[str]:
        """生成配置文件"""
        created = []

        # CLAUDE.md
        claude_template = self.template_dir / "CLAUDE.md"
        if claude_template.exists():
            with open(claude_template, encoding="utf-8") as f:
                content = f.read()

            # 替换占位符
            if config.get("commands"):
                # 可以在这里自定义命令
                pass

            claude_file = self.project_dir / "CLAUDE.md"
            with open(claude_file, "w", encoding="utf-8") as f:
                f.write(content)
            created.append(str(claude_file))

        # settings.json
        settings_template = self.template_dir / "settings.json"
        if settings_template.exists():
            settings_file = self.claude_dir / "settings.json"
            shutil.copy(settings_template, settings_file)
            created.append(str(settings_file))

        # 规则文件
        rules = ["security", "api-design", "performance"]
        for rule in rules:
            template_file = self.template_dir / f"rule-{rule}.md"
            if template_file.exists():
                target_file = self.claude_dir / "rules" / f"{rule}.md"
                shutil.copy(template_file, target_file)
                created.append(str(target_file))

        # Agent 文件
        agents = ["architect", "reviewer"]
        for agent in agents:
            template_file = self.template_dir / f"agent-{agent}.md"
            if template_file.exists():
                target_file = self.claude_dir / "agents" / f"{agent}.md"
                shutil.copy(template_file, target_file)
                created.append(str(target_file))

        # 进化技能
        evolution_template = self.template_dir / "skill-evolution.md"
        if evolution_template.exists():
            evolution_dir = self.claude_dir / "skills" / "evolution"
            evolution_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy(evolution_template, evolution_dir / "SKILL.md")
            created.append(str(evolution_dir / "SKILL.md"))

        # 学习规则文件
        rules_template = self.template_dir / "learned-rules.md"
        if rules_template.exists():
            rules_file = self.claude_dir / "memory" / "learned-rules.md"
            shutil.copy(rules_template, rules_file)
            created.append(str(rules_file))

        return created

    def _update_gitignore(self) -> None:
        """更新 .gitignore 文件"""
        gitignore = self.project_dir / ".gitignore"

        entries = [
            ".claude/memory/observations.jsonl",
            ".claude/memory/corrections.jsonl",
            ".claude/memory/verifications.jsonl",
        ]

        if gitignore.exists():
            with open(gitignore, encoding="utf-8") as f:
                existing = f.read()
        else:
            existing = ""

        # 检查是否需要添加
        to_add = []
        for entry in entries:
            if entry not in existing:
                to_add.append(entry)

        if to_add:
            with open(gitignore, "a", encoding="utf-8") as f:
                if existing and not existing.endswith("\n"):
                    f.write("\n")
                for entry in to_add:
                    f.write(entry + "\n")
