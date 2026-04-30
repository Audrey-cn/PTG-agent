#!/usr/bin/env python3
"""
Prometheus 技能管理工具
创建、编辑和删除技能（安全的，需要用户确认）
"""

import os
import re
import yaml
import hashlib
from pathlib import Path
from prometheus.tools.registry import registry, tool_result, tool_error
from prometheus.tools.skill_loader import SkillLoader, SkillParser
from prometheus.config import get_prometheus_home


# 安全扫描的危险模式（参考 Hermes）
DANGEROUS_PATTERNS = [
    r"\bos\.(system|popen|exec|spawn|fork)",
    r"\bsubprocess\.",
    r"\beval\s*\(",
    r"\bexec\s*\(",
    r"\b__import__\s*\(",
    r"import\s+(os|subprocess|sys|ctypes|pickle)",
    r"\bshutil\.",
    r"os\.remove|os\.unlink|os\.rmdir|shutil\.rmtree",
]


def get_user_skills_dir():
    """获取用户技能目录"""
    home = get_prometheus_home()
    skills_dir = home / "skills"
    skills_dir.mkdir(exist_ok=True)
    return skills_dir


def scan_for_dangerous_patterns(content: str) -> list:
    """安全扫描，检查危险模式"""
    issues = []
    for pattern in DANGEROUS_PATTERNS:
        matches = re.finditer(pattern, content)
        for match in matches:
            issues.append({
                "pattern": pattern,
                "match": match.group(0),
                "position": match.start()
            })
    return issues


def create_skill(args):
    """创建新技能（安全模式）"""
    name = args.get("name")
    description = args.get("description", "")
    body = args.get("body", "")
    category = args.get("category", "uncategorized")
    tags = args.get("tags", [])
    
    if not name:
        return tool_error("需要提供技能名称")
    if not body.strip():
        return tool_error("需要提供技能内容")
    
    # 安全扫描
    dangerous = scan_for_dangerous_patterns(body)
    if dangerous:
        return tool_error({
            "message": "检测到潜在危险模式",
            "issues": dangerous
        })
    
    # 确定路径
    skills_dir = get_user_skills_dir()
    category_dir = skills_dir / category
    category_dir.mkdir(exist_ok=True)
    
    skill_dir = category_dir / name
    if skill_dir.exists():
        return tool_error(f"技能已存在: {name}")
    
    skill_dir.mkdir()
    
    # 构建 YAML frontmatter
    frontmatter = {
        "name": name,
        "description": description or "暂无描述",
        "version": "1.0.0",
        "metadata": {
            "hermes": {
                "tags": tags,
                "related_skills": []
            }
        }
    }
    
    # 写入文件
    skill_file = skill_dir / "SKILL.md"
    with open(skill_file, "w", encoding="utf-8") as f:
        f.write("---\n")
        f.write(yaml.dump(frontmatter, allow_unicode=True))
        f.write("---\n\n")
        f.write(body)
    
    # 验证
    validation = SkillParser.validate(str(skill_file))
    if not validation["valid"]:
        # 清理
        import shutil
        shutil.rmtree(skill_dir)
        return tool_error({
            "message": "创建的技能文件无效",
            "issues": validation["issues"]
        })
    
    return tool_result({
        "name": name,
        "path": str(skill_file),
        "status": "created"
    })


def edit_skill(args):
    """编辑技能（全量重写）"""
    name = args.get("name")
    body = args.get("body")
    
    if not name:
        return tool_error("需要提供技能名称")
    if body is None:
        return tool_error("需要提供新内容")
    
    # 查找技能
    loader = SkillLoader()
    loader.scan()
    skill = loader.get(name)
    
    if not skill:
        return tool_error(f"未找到技能: {name}")
    
    # 安全扫描
    dangerous = scan_for_dangerous_patterns(body)
    if dangerous:
        return tool_error({
            "message": "检测到潜在危险模式",
            "issues": dangerous
        })
    
    # 备份旧文件
    backup_path = skill.path + ".bak"
    with open(skill.path, "r", encoding="utf-8") as f:
        old_content = f.read()
    with open(backup_path, "w", encoding="utf-8") as f:
        f.write(old_content)
    
    # 读取并保留 frontmatter，只替换 body
    with open(skill.path, "r", encoding="utf-8") as f:
        old_content = f.read()
    
    # 提取 frontmatter
    match = re.search(r'\n---\s*\n', old_content[3:])
    if not match:
        return tool_error("技能文件格式错误")
    
    frontmatter_str = old_content[3:match.start() + 3]
    
    # 写入新内容
    with open(skill.path, "w", encoding="utf-8") as f:
        f.write("---\n")
        f.write(frontmatter_str)
        f.write("---\n\n")
        f.write(body)
    
    # 验证
    validation = SkillParser.validate(skill.path)
    if not validation["valid"]:
        # 回滚
        import shutil
        shutil.move(backup_path, skill.path)
        return tool_error({
            "message": "更新的技能文件无效，已回滚",
            "issues": validation["issues"]
        })
    
    return tool_result({
        "name": name,
        "path": skill.path,
        "status": "updated",
        "backup": backup_path
    })


def delete_skill(args):
    """删除技能"""
    name = args.get("name")
    confirm = args.get("confirm", False)
    
    if not name:
        return tool_error("需要提供技能名称")
    if not confirm:
        return tool_error("删除操作需要确认，请设置 confirm=true")
    
    # 查找技能
    loader = SkillLoader()
    loader.scan()
    skill = loader.get(name)
    
    if not skill:
        return tool_error(f"未找到技能: {name}")
    
    # 备份整个目录
    import shutil
    backup_dir = skill.skill_dir + ".bak"
    if os.path.exists(backup_dir):
        shutil.rmtree(backup_dir)
    shutil.copytree(skill.skill_dir, backup_dir)
    
    # 删除
    shutil.rmtree(skill.skill_dir)
    
    return tool_result({
        "name": name,
        "status": "deleted",
        "backup": backup_dir
    })


def suggest_skill_from_session(args):
    """从会话历史中建议新技能（非强制，只建议）"""
    session_summary = args.get("summary", "")
    tool_calls = args.get("tool_calls", [])
    
    # 简单启发式：如果工具调用链 >= 3 个，建议创建技能
    if len(tool_calls) < 3:
        return tool_result({
            "suggested": False,
            "reason": "工具调用链太短，不需要创建技能"
        })
    
    suggestion = {
        "suggested": True,
        "name": args.get("suggested_name", f"auto_skill_{hashlib.md5(str(tool_calls).encode()).hexdigest()[:8]}"),
        "description": f"自动生成的工作流程（{len(tool_calls)} 个工具调用）",
        "summary": session_summary,
        "tool_calls": tool_calls,
        "next_steps": [
            "请为这个技能起一个更合适的名称",
            "编辑技能内容，添加具体步骤说明",
            "运行 create_skill 创建技能"
        ]
    }
    
    return tool_result(suggestion)


# 注册工具
registry.register(
    name="create_skill",
    toolset="skill_manager",
    schema={
        "name": "create_skill",
        "description": "创建新技能（安全扫描）",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "技能名称"},
                "description": {"type": "string", "description": "技能描述"},
                "body": {"type": "string", "description": "技能内容（Markdown）"},
                "category": {"type": "string", "description": "分类"},
                "tags": {"type": "array", "items": {"type": "string"}, "description": "标签"}
            },
            "required": ["name", "body"]
        }
    },
    handler=create_skill,
    description="创建新技能",
    emoji="✨"
)

registry.register(
    name="edit_skill",
    toolset="skill_manager",
    schema={
        "name": "edit_skill",
        "description": "编辑技能（全量重写）",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "技能名称"},
                "body": {"type": "string", "description": "新内容"}
            },
            "required": ["name", "body"]
        }
    },
    handler=edit_skill,
    description="编辑技能",
    emoji="✏️"
)

registry.register(
    name="delete_skill",
    toolset="skill_manager",
    schema={
        "name": "delete_skill",
        "description": "删除技能（需要确认）",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "技能名称"},
                "confirm": {"type": "boolean", "description": "确认删除"}
            },
            "required": ["name", "confirm"]
        }
    },
    handler=delete_skill,
    description="删除技能",
    emoji="🗑️"
)

registry.register(
    name="suggest_skill",
    toolset="skill_manager",
    schema={
        "name": "suggest_skill",
        "description": "从会话历史中建议新技能",
        "parameters": {
            "type": "object",
            "properties": {
                "summary": {"type": "string", "description": "会话摘要"},
                "tool_calls": {"type": "array", "description": "工具调用历史"},
                "suggested_name": {"type": "string", "description": "建议的技能名称"}
            }
        }
    },
    handler=suggest_skill_from_session,
    description="建议新技能",
    emoji="💡"
)
