#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════╗
║   📋 普罗米修斯 · Skill 加载器 · Skill Loader                ║
║                                                              ║
║   对齐 Hermes Skill 架构：                                    ║
║     • SKILL.md 格式（YAML frontmatter + Markdown body）      ║
║     • 目录结构：skills/<category>/<name>/SKILL.md            ║
║     • 支持引用文件：references/, templates/, scripts/         ║
║                                                              ║
║   本模块提供：                                                ║
║     • 扫描目录发现 Skill                                      ║
║     • 解析 YAML frontmatter                                  ║
║     • 加载和查询 Skill 内容                                   ║
║     • 验证 Skill 合规性                                       ║
║     • 按标签/分类过滤                                         ║
╚══════════════════════════════════════════════════════════════╝
"""

import os
import re
import json
import yaml
import hashlib
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
import sys
from pathlib import Path


# ═══════════════════════════════════════════
#   配置
# ═══════════════════════════════════════════

MAX_NAME_LENGTH = 64
MAX_DESCRIPTION_LENGTH = 1024
MAX_SKILL_CONTENT_CHARS = 100_000
SKILL_FILENAME = "SKILL.md"

# 默认搜索路径
DEFAULT_SKILL_PATHS = [
    os.path.expanduser("~/.prometheus/skills"),
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "skills"),
    os.path.expanduser("~/.hermes/skills"),
]


# ═══════════════════════════════════════════
#   数据结构
# ═══════════════════════════════════════════

@dataclass
class SkillMeta:
    """Skill 元数据（从 YAML frontmatter 提取）"""
    name: str
    description: str
    version: str = "1.0.0"
    author: str = ""
    license: str = ""
    tags: List[str] = field(default_factory=list)
    related_skills: List[str] = field(default_factory=list)
    raw_meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Skill:
    """完整的 Skill 实例"""
    meta: SkillMeta
    body: str                          # Markdown 正文
    path: str                          # SKILL.md 文件路径
    skill_dir: str                     # Skill 所在目录
    category: str = ""                 # 分类
    references: Dict[str, str] = field(default_factory=dict)  # 引用文件
    checksum: str = ""                 # 内容校验和

    @property
    def full_path(self) -> str:
        return self.path

    @property
    def content(self) -> str:
        """完整的 SKILL.md 内容"""
        return f"---\n{yaml.dump(self._frontmatter_dict(), allow_unicode=True)}---\n\n{self.body}"

    def _frontmatter_dict(self) -> dict:
        d = {
            "name": self.meta.name,
            "description": self.meta.description,
        }
        if self.meta.version:
            d["version"] = self.meta.version
        if self.meta.author:
            d["author"] = self.meta.author
        if self.meta.license:
            d["license"] = self.meta.license
        if self.meta.tags or self.meta.related_skills:
            d["metadata"] = {
                "hermes": {
                    "tags": self.meta.tags,
                    "related_skills": self.meta.related_skills,
                }
            }
        return d

    def get_reference(self, name: str) -> Optional[str]:
        """获取引用文件内容"""
        return self.references.get(name)

    def list_references(self) -> List[str]:
        """列出所有引用文件"""
        return list(self.references.keys())

    def to_dict(self) -> dict:
        """序列化为字典"""
        return {
            "name": self.meta.name,
            "description": self.meta.description,
            "version": self.meta.version,
            "category": self.category,
            "tags": self.meta.tags,
            "path": self.path,
            "body_length": len(self.body),
            "references": list(self.references.keys()),
            "checksum": self.checksum,
        }


# ═══════════════════════════════════════════
#   解析器
# ═══════════════════════════════════════════

class SkillParser:
    """SKILL.md 文件解析器"""

    @staticmethod
    def parse_file(filepath: str) -> Optional[Skill]:
        """解析单个 SKILL.md 文件"""
        if not os.path.exists(filepath):
            return None

        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        return SkillParser.parse_content(content, filepath)

    @staticmethod
    def parse_content(content: str, filepath: str = "<inline>") -> Optional[Skill]:
        """解析 SKILL.md 内容"""
        # 验证开头
        if not content.startswith("---"):
            return None

        # 提取 frontmatter
        match = re.search(r'\n---\s*\n', content[3:])
        if not match:
            return None

        frontmatter_str = content[3:match.start() + 3]
        body = content[match.end() + 3:]

        # 验证 body 非空
        if not body.strip():
            return None

        # 解析 YAML
        try:
            fm = yaml.safe_load(frontmatter_str)
        except yaml.YAMLError:
            return None

        if not isinstance(fm, dict):
            return None

        # 验证必填字段
        if "name" not in fm or "description" not in fm:
            return None

        # 验证长度限制
        if len(fm["description"]) > MAX_DESCRIPTION_LENGTH:
            return None
        if len(content) > MAX_SKILL_CONTENT_CHARS:
            return None

        # 提取元数据
        metadata = fm.get("metadata", {})
        hermes_meta = metadata.get("hermes", {}) if isinstance(metadata, dict) else {}

        meta = SkillMeta(
            name=fm["name"][:MAX_NAME_LENGTH],
            description=fm["description"],
            version=fm.get("version", "1.0.0"),
            author=fm.get("author", ""),
            license=fm.get("license", ""),
            tags=hermes_meta.get("tags", []),
            related_skills=hermes_meta.get("related_skills", []),
            raw_meta=fm,
        )

        # 计算校验和
        checksum = hashlib.md5(content.encode()).hexdigest()[:12]

        # 确定分类和目录
        skill_dir = os.path.dirname(filepath)
        category = os.path.basename(os.path.dirname(skill_dir))
        if category == "skills":
            category = ""

        return Skill(
            meta=meta,
            body=body,
            path=filepath,
            skill_dir=skill_dir,
            category=category,
            checksum=checksum,
        )

    @staticmethod
    def validate(filepath: str) -> Dict[str, Any]:
        """验证 SKILL.md 合规性"""
        issues = []

        if not os.path.exists(filepath):
            return {"valid": False, "issues": ["文件不存在"]}

        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        # 检查开头
        if not content.startswith("---"):
            issues.append("必须以 --- 开头")

        # 检查 frontmatter 闭合
        match = re.search(r'\n---\s*\n', content[3:])
        if not match:
            issues.append("frontmatter 未闭合")
            return {"valid": False, "issues": issues}

        frontmatter_str = content[3:match.start() + 3]
        body = content[match.end() + 3:]

        # 解析 YAML
        try:
            fm = yaml.safe_load(frontmatter_str)
        except yaml.YAMLError as e:
            issues.append(f"YAML 解析错误: {e}")
            return {"valid": False, "issues": issues}

        if not isinstance(fm, dict):
            issues.append("frontmatter 不是字典")
            return {"valid": False, "issues": issues}

        # 检查必填字段
        if "name" not in fm:
            issues.append("缺少 name 字段")
        elif len(fm["name"]) > MAX_NAME_LENGTH:
            issues.append(f"name 超过 {MAX_NAME_LENGTH} 字符")

        if "description" not in fm:
            issues.append("缺少 description 字段")
        elif len(fm["description"]) > MAX_DESCRIPTION_LENGTH:
            issues.append(f"description 超过 {MAX_DESCRIPTION_LENGTH} 字符")

        if not body.strip():
            issues.append("body 为空")

        if len(content) > MAX_SKILL_CONTENT_CHARS:
            issues.append(f"总大小超过 {MAX_SKILL_CONTENT_CHARS} 字符")

        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "name": fm.get("name", ""),
            "description_length": len(fm.get("description", "")),
            "body_length": len(body),
            "total_length": len(content),
        }


# ═══════════════════════════════════════════
#   加载器
# ═══════════════════════════════════════════

class SkillLoader:
    """Skill 加载器——扫描、索引、查询 Skill。
    
    对齐 Hermes 的 Skill 系统架构：
      • 目录结构：skills/<category>/<name>/SKILL.md
      • 支持引用文件：references/, templates/, scripts/
      • 按标签/分类/名称过滤
    """

    def __init__(self, skill_paths: List[str] = None):
        """
        Args:
            skill_paths: Skill 搜索路径列表
        """
        self.skill_paths = skill_paths or DEFAULT_SKILL_PATHS
        self._skills: Dict[str, Skill] = {}
        self._by_category: Dict[str, List[str]] = {}
        self._by_tag: Dict[str, List[str]] = {}

    def scan(self) -> int:
        """扫描所有路径，发现并加载 Skill
        
        Returns:
            发现的 Skill 数量
        """
        self._skills.clear()
        self._by_category.clear()
        self._by_tag.clear()

        found = 0
        for base_path in self.skill_paths:
            base_path = os.path.expanduser(base_path)
            if not os.path.exists(base_path):
                continue

            for root, dirs, files in os.walk(base_path):
                # 跳过隐藏目录
                dirs[:] = [d for d in dirs if not d.startswith('.')]

                if SKILL_FILENAME in files:
                    skill_path = os.path.join(root, SKILL_FILENAME)
                    skill = SkillParser.parse_file(skill_path)
                    if skill:
                        self._register(skill)
                        found += 1

        return found

    def _register(self, skill: Skill):
        """注册一个 Skill 到索引"""
        self._skills[skill.meta.name] = skill

        # 按分类索引
        cat = skill.category or "uncategorized"
        self._by_category.setdefault(cat, []).append(skill.meta.name)

        # 按标签索引
        for tag in skill.meta.tags:
            self._by_tag.setdefault(tag, []).append(skill.meta.name)

        # 加载引用文件
        self._load_references(skill)

    def _load_references(self, skill: Skill):
        """加载 Skill 目录下的引用文件"""
        for subdir in ["references", "templates", "scripts", "assets"]:
            ref_dir = os.path.join(skill.skill_dir, subdir)
            if not os.path.exists(ref_dir):
                continue
            for f in os.listdir(ref_dir):
                fpath = os.path.join(ref_dir, f)
                if os.path.isfile(fpath) and not f.startswith('.'):
                    try:
                        with open(fpath, "r", encoding="utf-8") as fh:
                            skill.references[f"{subdir}/{f}"] = fh.read()
                    except (UnicodeDecodeError, IOError):
                        pass  # 二进制文件或读取错误

    # ── 查询 ────────────────────────────────────

    def get(self, name: str) -> Optional[Skill]:
        """按名称获取 Skill"""
        return self._skills.get(name)

    def list_all(self) -> List[dict]:
        """列出所有已加载的 Skill"""
        return [s.to_dict() for s in self._skills.values()]

    def list_categories(self) -> Dict[str, int]:
        """列出所有分类及 Skill 数量"""
        return {cat: len(names) for cat, names in self._by_category.items()}

    def list_tags(self) -> Dict[str, int]:
        """列出所有标签及使用次数"""
        return {tag: len(names) for tag, names in self._by_tag.items()}

    def search(self, query: str) -> List[Skill]:
        """搜索 Skill（名称、描述、标签）"""
        query_lower = query.lower()
        results = []
        for skill in self._skills.values():
            if (query_lower in skill.meta.name.lower() or
                query_lower in skill.meta.description.lower() or
                any(query_lower in tag.lower() for tag in skill.meta.tags)):
                results.append(skill)
        return results

    def by_category(self, category: str) -> List[Skill]:
        """按分类过滤"""
        names = self._by_category.get(category, [])
        return [self._skills[n] for n in names if n in self._skills]

    def by_tag(self, tag: str) -> List[Skill]:
        """按标签过滤"""
        names = self._by_tag.get(tag, [])
        return [self._skills[n] for n in names if n in self._skills]

    def get_related(self, name: str) -> List[Skill]:
        """获取相关的 Skill"""
        skill = self._skills.get(name)
        if not skill:
            return []
        related = []
        for rel_name in skill.meta.related_skills:
            if rel_name in self._skills:
                related.append(self._skills[rel_name])
        return related

    # ── 统计 ────────────────────────────────────

    def stats(self) -> dict:
        """加载统计"""
        return {
            "total": len(self._skills),
            "categories": len(self._by_category),
            "tags": len(self._by_tag),
            "search_paths": self.skill_paths,
            "category_counts": self.list_categories(),
        }

    def export_catalog(self) -> str:
        """导出为 Markdown 目录（人读层）"""
        lines = ["# Prometheus Skill 目录", ""]

        by_cat = {}
        for skill in self._skills.values():
            cat = skill.category or "uncategorized"
            by_cat.setdefault(cat, []).append(skill)

        for cat, skills in sorted(by_cat.items()):
            lines.append(f"## {cat.title()} ({len(skills)})")
            lines.append("")
            for s in sorted(skills, key=lambda x: x.meta.name):
                lines.append(f"### {s.meta.name}")
                lines.append(f"- {s.meta.description}")
                if s.meta.tags:
                    lines.append(f"- 标签: {', '.join(s.meta.tags)}")
                lines.append(f"- 路径: `{s.path}`")
                lines.append("")

        return "\n".join(lines)


# ═══════════════════════════════════════════
#   便捷函数
# ═══════════════════════════════════════════

def load_skills(skill_paths: List[str] = None) -> SkillLoader:
    """便捷函数：扫描并返回加载器"""
    loader = SkillLoader(skill_paths=skill_paths)
    loader.scan()
    return loader


def find_skill(name: str, skill_paths: List[str] = None) -> Optional[Skill]:
    """便捷函数：查找单个 Skill"""
    loader = SkillLoader(skill_paths=skill_paths)
    loader.scan()
    return loader.get(name)


# ═══════════════════════════════════════════
#   CLI 入口
# ═══════════════════════════════════════════

def main():
    import argparse

    parser = argparse.ArgumentParser(description="Prometheus Skill 加载器")
    parser.add_argument("command", choices=["scan", "list", "get", "search", "validate", "stats", "catalog"],
                       help="操作命令")
    parser.add_argument("args", nargs="*", help="命令参数")
    parser.add_argument("--path", action="append", help="额外搜索路径")

    args = parser.parse_args()

    paths = args.path if args.path else None
    loader = SkillLoader(skill_paths=paths)
    loader.scan()

    if args.command == "scan":
        print(f"发现 {len(loader._skills)} 个 Skill")

    elif args.command == "list":
        for s in loader.list_all():
            print(f"  {s['name']}: {s['description'][:60]}")

    elif args.command == "get":
        if not args.args:
            print("❌ 需要提供 Skill 名称")
            return
        skill = loader.get(args.args[0])
        if skill:
            print(skill.content[:500])
        else:
            print(f"❌ 未找到: {args.args[0]}")

    elif args.command == "search":
        query = " ".join(args.args) if args.args else ""
        results = loader.search(query)
        for s in results:
            print(f"  {s.meta.name}: {s.meta.description[:60]}")

    elif args.command == "validate":
        if not args.args:
            print("❌ 需要提供文件路径")
            return
        result = SkillParser.validate(args.args[0])
        status = "✅ 合规" if result["valid"] else "❌ 不合规"
        print(f"{status}")
        for issue in result.get("issues", []):
            print(f"  - {issue}")

    elif args.command == "stats":
        stats = loader.stats()
        print(f"总计: {stats['total']} 个 Skill")
        print(f"分类: {stats['categories']} 个")
        print(f"标签: {stats['tags']} 个")
        for cat, count in stats["category_counts"].items():
            print(f"  {cat}: {count}")

    elif args.command == "catalog":
        print(loader.export_catalog())


if __name__ == "__main__":
    main()
