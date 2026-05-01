#!/usr/bin/env python3
"""
自进化系统工具
"""

from ..tools.registry import registry, tool_error, tool_result
from .engine import SelfEvolutionEngine
from .initializer import ProjectInitializer


def initialize_project(args):
    """初始化项目的自进化系统"""
    project_dir = args.get("project_dir", ".")
    config = args.get("config", {})

    try:
        initializer = ProjectInitializer(project_dir)
        result = initializer.initialize(config)
        return tool_result(result)
    except Exception as e:
        return tool_error({"error": str(e)})


def record_observation(args):
    """记录观察到的模式"""
    project_dir = args.get("project_dir", ".")
    pattern_type = args.get("type", "pattern")
    content = args.get("content", "")
    context = args.get("context", "")
    confidence = args.get("confidence", 0.5)

    if not content:
        return tool_error("Content is required")

    try:
        engine = SelfEvolutionEngine(project_dir)
        result = engine.observe(pattern_type, content, context, confidence)
        return tool_result(result)
    except Exception as e:
        return tool_error({"error": str(e)})


def record_correction(args):
    """记录用户纠正"""
    project_dir = args.get("project_dir", ".")
    original = args.get("original", "")
    corrected = args.get("corrected", "")
    feedback = args.get("feedback", "")
    context = args.get("context", "")

    if not original or not corrected:
        return tool_error("Original and corrected are required")

    try:
        engine = SelfEvolutionEngine(project_dir)
        result = engine.learn_from_correction(original, corrected, feedback, context)
        return tool_result(result)
    except Exception as e:
        return tool_error({"error": str(e)})


def get_learned_rules(args):
    """获取已学习的规则"""
    project_dir = args.get("project_dir", ".")

    try:
        engine = SelfEvolutionEngine(project_dir)
        rules = engine.consult()
        return tool_result({"rules": rules})
    except Exception as e:
        return tool_error({"error": str(e)})


def get_evolution_status(args):
    """获取进化引擎状态"""
    project_dir = args.get("project_dir", ".")

    try:
        engine = SelfEvolutionEngine(project_dir)
        status = engine.get_status()
        return tool_result(status)
    except Exception as e:
        return tool_error({"error": str(e)})


# 注册工具
registry.register(
    name="init_self_evolution",
    toolset="self_evolution",
    schema={
        "name": "init_self_evolution",
        "description": "Initialize self-evolution system for a project",
        "parameters": {
            "type": "object",
            "properties": {
                "project_dir": {"type": "string", "description": "Project directory"},
                "config": {"type": "object", "description": "Configuration options"},
            },
        },
    },
    handler=initialize_project,
    description="Initialize self-evolution system",
    emoji="🚀",
)

registry.register(
    name="record_observation",
    toolset="self_evolution",
    schema={
        "name": "record_observation",
        "description": "Record an observed pattern",
        "parameters": {
            "type": "object",
            "properties": {
                "project_dir": {"type": "string", "description": "Project directory"},
                "type": {"type": "string", "description": "Pattern type"},
                "content": {"type": "string", "description": "Observation content"},
                "context": {"type": "string", "description": "Context"},
                "confidence": {"type": "number", "description": "Confidence score"},
            },
            "required": ["content"],
        },
    },
    handler=record_observation,
    description="Record an observation",
    emoji="👁️",
)

registry.register(
    name="record_correction",
    toolset="self_evolution",
    schema={
        "name": "record_correction",
        "description": "Record a user correction",
        "parameters": {
            "type": "object",
            "properties": {
                "project_dir": {"type": "string", "description": "Project directory"},
                "original": {"type": "string", "description": "Original content"},
                "corrected": {"type": "string", "description": "Corrected content"},
                "feedback": {"type": "string", "description": "User feedback"},
                "context": {"type": "string", "description": "Context"},
            },
            "required": ["original", "corrected"],
        },
    },
    handler=record_correction,
    description="Record a correction",
    emoji="📝",
)

registry.register(
    name="get_learned_rules",
    toolset="self_evolution",
    schema={
        "name": "get_learned_rules",
        "description": "Get learned rules",
        "parameters": {
            "type": "object",
            "properties": {
                "project_dir": {"type": "string", "description": "Project directory"},
            },
        },
    },
    handler=get_learned_rules,
    description="Get learned rules",
    emoji="📚",
)

registry.register(
    name="get_evolution_status",
    toolset="self_evolution",
    schema={
        "name": "get_evolution_status",
        "description": "Get evolution engine status",
        "parameters": {
            "type": "object",
            "properties": {
                "project_dir": {"type": "string", "description": "Project directory"},
            },
        },
    },
    handler=get_evolution_status,
    description="Get evolution status",
    emoji="📊",
)
