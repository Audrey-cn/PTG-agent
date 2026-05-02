"""
史诗编史官工具集
包含烙印、追溯、附史等核心功能
"""

from pathlib import Path
from typing import Any

from prometheus.chronicler import Chronicler
from prometheus.tools.security.registry import registry, tool_error, tool_result


def _get_chronicler() -> Chronicler:
    """获取编史官实例"""
    return Chronicler()


def stamp_seed_tool(args: dict[str, Any]) -> str:
    """
    烙印工具：在种子上烙印 Prometheus 标记

    参数:
        seed_path: 种子文件路径
        mark: 烙印内容（可选）
    """
    seed_path = args.get("seed_path")
    mark = args.get("mark", "")

    if not seed_path:
        return tool_error("缺少 seed_path 参数")

    path = Path(seed_path)
    if not path.exists():
        return tool_error(f"种子文件不存在: {seed_path}")

    try:
        chronicler = _get_chronicler()
        result = chronicler.stamp(str(path), mark)
        return tool_result({"success": True, "seed_path": seed_path, "stamp_result": result})
    except Exception as e:
        return tool_error(f"烙印失败: {str(e)}")


registry.register(
    name="stamp_seed",
    toolset="chronicler",
    schema={
        "name": "stamp_seed",
        "description": "在种子上烙印 Prometheus 标记，记录种子的起源和修改历史",
        "parameters": {
            "type": "object",
            "properties": {
                "seed_path": {"type": "string", "description": "种子文件的路径"},
                "mark": {"type": "string", "description": "可选的烙印内容或备注"},
            },
            "required": ["seed_path"],
        },
    },
    handler=stamp_seed_tool,
    description="烙印：在种子上标记 Prometheus 印记",
    emoji="🔥",
)


def trace_seed_tool(args: dict[str, Any]) -> str:
    """
    追溯工具：追溯种子的历史和来源

    参数:
        seed_path: 种子文件路径
    """
    seed_path = args.get("seed_path")

    if not seed_path:
        return tool_error("缺少 seed_path 参数")

    path = Path(seed_path)
    if not path.exists():
        return tool_error(f"种子文件不存在: {seed_path}")

    try:
        chronicler = _get_chronicler()
        history = chronicler.trace(str(path))
        return tool_result({"success": True, "seed_path": seed_path, "history": history})
    except Exception as e:
        return tool_error(f"追溯失败: {str(e)}")


registry.register(
    name="trace_seed",
    toolset="chronicler",
    schema={
        "name": "trace_seed",
        "description": "追溯种子的完整历史，包括起源、修改记录和继承关系",
        "parameters": {
            "type": "object",
            "properties": {"seed_path": {"type": "string", "description": "种子文件的路径"}},
            "required": ["seed_path"],
        },
    },
    handler=trace_seed_tool,
    description="追溯：追踪种子的完整历史",
    emoji="🔍",
)


def append_historical_note_tool(args: dict[str, Any]) -> str:
    """
    附史工具：在种子上附加历史记录

    参数:
        seed_path: 种子文件路径
        note: 历史记录内容
        category: 记录分类（可选）
    """
    seed_path = args.get("seed_path")
    note = args.get("note")
    category = args.get("category", "modification")

    if not seed_path or not note:
        return tool_error("缺少 seed_path 或 note 参数")

    path = Path(seed_path)
    if not path.exists():
        return tool_error(f"种子文件不存在: {seed_path}")

    try:
        chronicler = _get_chronicler()
        result = chronicler.append(str(path), note, category)
        return tool_result({"success": True, "seed_path": seed_path, "append_result": result})
    except Exception as e:
        return tool_error(f"附史失败: {str(e)}")


registry.register(
    name="append_historical_note",
    toolset="chronicler",
    schema={
        "name": "append_historical_note",
        "description": "在种子上附加历史记录，记录重要的修改、增强或事件",
        "parameters": {
            "type": "object",
            "properties": {
                "seed_path": {"type": "string", "description": "种子文件的路径"},
                "note": {"type": "string", "description": "历史记录内容"},
                "category": {
                    "type": "string",
                    "description": "记录分类：modification, enhancement, event, integration",
                    "enum": ["modification", "enhancement", "event", "integration"],
                },
            },
            "required": ["seed_path", "note"],
        },
    },
    handler=append_historical_note_tool,
    description="附史：附加历史记录到种子",
    emoji="📜",
)


def inspect_seed_tool(args: dict[str, Any]) -> str:
    """
    检查工具：检查种子的结构和内容

    参数:
        seed_path: 种子文件路径
        detail_level: 详细程度（basic, detailed, full）
    """
    seed_path = args.get("seed_path")
    detail_level = args.get("detail_level", "basic")

    if not seed_path:
        return tool_error("缺少 seed_path 参数")

    path = Path(seed_path)
    if not path.exists():
        return tool_error(f"种子文件不存在: {seed_path}")

    try:
        from prometheus import load_seed

        data = load_seed(str(path))

        if detail_level == "basic":
            inspection = {
                "has_life_crest": "life_crest" in data,
                "has_genealogy_codex": "genealogy_codex" in data,
                "has_skill_soul": "skill_soul" in data,
                "has_dna_encoding": "dna_encoding" in data,
            }
        elif detail_level == "detailed":
            inspection = {
                "life_crest": data.get("life_crest", {}),
                "genealogy_codex": data.get("genealogy_codex", {}),
                "skill_soul": data.get("skill_soul", {}),
            }
        else:
            inspection = data

        return tool_result({"success": True, "seed_path": seed_path, "inspection": inspection})
    except Exception as e:
        return tool_error(f"检查失败: {str(e)}")


registry.register(
    name="inspect_seed",
    toolset="chronicler",
    schema={
        "name": "inspect_seed",
        "description": "检查种子的结构和内容，了解种子的组成和状态",
        "parameters": {
            "type": "object",
            "properties": {
                "seed_path": {"type": "string", "description": "种子文件的路径"},
                "detail_level": {
                    "type": "string",
                    "description": "详细程度：basic, detailed, full",
                    "enum": ["basic", "detailed", "full"],
                },
            },
            "required": ["seed_path"],
        },
    },
    handler=inspect_seed_tool,
    description="检查：检查种子的结构和内容",
    emoji="🔬",
)


def list_stamps_tool(args: dict[str, Any]) -> str:
    """
    列出烙印工具：列出种子上的所有烙印

    参数:
        seed_path: 种子文件路径
    """
    seed_path = args.get("seed_path")

    if not seed_path:
        return tool_error("缺少 seed_path 参数")

    path = Path(seed_path)
    if not path.exists():
        return tool_error(f"种子文件不存在: {seed_path}")

    try:
        from prometheus import load_seed

        data = load_seed(str(path))
        life_crest = data.get("life_crest", {})
        founder_covenant = life_crest.get("founder_covenant", {})
        eternal_seals = founder_covenant.get("eternal_seals", [])

        return tool_result({"success": True, "seed_path": seed_path, "stamps": eternal_seals})
    except Exception as e:
        return tool_error(f"列出烙印失败: {str(e)}")


registry.register(
    name="list_stamps",
    toolset="chronicler",
    schema={
        "name": "list_stamps",
        "description": "列出种子上的所有烙印标记",
        "parameters": {
            "type": "object",
            "properties": {"seed_path": {"type": "string", "description": "种子文件的路径"}},
            "required": ["seed_path"],
        },
    },
    handler=list_stamps_tool,
    description="列印：列出种子上的所有烙印",
    emoji="📋",
)
