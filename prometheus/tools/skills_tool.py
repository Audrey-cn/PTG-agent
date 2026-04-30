#!/usr/bin/env python3
"""
Prometheus 技能工具
用于列出、查看和搜索技能
"""

import os
import json
from prometheus.tools.registry import registry, tool_result, tool_error
from prometheus.tools.skill_loader import SkillLoader, find_skill


def list_skills(args):
    """列出所有技能"""
    category = args.get("category")
    tag = args.get("tag")
    
    loader = SkillLoader()
    loader.scan()
    
    skills = []
    if category:
        skills = [s.to_dict() for s in loader.by_category(category)]
    elif tag:
        skills = [s.to_dict() for s in loader.by_tag(tag)]
    else:
        skills = loader.list_all()
    
    return tool_result({
        "total": len(skills),
        "skills": skills,
        "categories": loader.list_categories(),
        "tags": loader.list_tags()
    })


def get_skill(args):
    """获取单个技能详情"""
    name = args.get("name")
    if not name:
        return tool_error("需要提供技能名称")
    
    skill = find_skill(name)
    if not skill:
        return tool_error(f"未找到技能: {name}")
    
    return tool_result({
        "name": skill.meta.name,
        "description": skill.meta.description,
        "version": skill.meta.version,
        "author": skill.meta.author,
        "category": skill.category,
        "tags": skill.meta.tags,
        "path": skill.path,
        "body": skill.body,
        "references": skill.list_references()
    })


def search_skills(args):
    """搜索技能"""
    query = args.get("query", "")
    if not query:
        return tool_error("需要提供搜索关键词")
    
    loader = SkillLoader()
    loader.scan()
    
    results = loader.search(query)
    
    return tool_result({
        "query": query,
        "count": len(results),
        "skills": [s.to_dict() for s in results]
    })


def skill_stats(args):
    """获取技能统计"""
    loader = SkillLoader()
    loader.scan()
    
    return tool_result(loader.stats())


# 注册工具
registry.register(
    name="list_skills",
    toolset="skills",
    schema={
        "name": "list_skills",
        "description": "列出所有可用技能",
        "parameters": {
            "type": "object",
            "properties": {
                "category": {"type": "string", "description": "按分类过滤"},
                "tag": {"type": "string", "description": "按标签过滤"}
            }
        }
    },
    handler=list_skills,
    description="列出所有可用技能",
    emoji="📖"
)

registry.register(
    name="get_skill",
    toolset="skills",
    schema={
        "name": "get_skill",
        "description": "获取技能详情",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "技能名称"}
            },
            "required": ["name"]
        }
    },
    handler=get_skill,
    description="获取技能详情",
    emoji="🔍"
)

registry.register(
    name="search_skills",
    toolset="skills",
    schema={
        "name": "search_skills",
        "description": "搜索技能",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "搜索关键词"}
            },
            "required": ["query"]
        }
    },
    handler=search_skills,
    description="搜索技能",
    emoji="🔎"
)

registry.register(
    name="skill_stats",
    toolset="skills",
    schema={
        "name": "skill_stats",
        "description": "获取技能统计信息",
        "parameters": {"type": "object", "properties": {}}
    },
    handler=skill_stats,
    description="获取技能统计信息",
    emoji="📊"
)
