
"""
Prometheus 工具注册表
史诗编史官系统的工具注册与调度

参考 Hermes 工具注册表设计
"""

import ast
import importlib
import json
import logging
import threading
from pathlib import Path
from typing import Callable, Dict, List, Optional, Set, Union

logger = logging.getLogger(__name__)


def _is_registry_register_call(node: ast.AST) -> bool:
    """检查节点是否是 registry.register() 调用"""
    if not isinstance(node, ast.Expr) or not isinstance(node.value, ast.Call):
        return False
    func = node.value.func
    return (
        isinstance(func, ast.Attribute)
        and func.attr == "register"
        and isinstance(func.value, ast.Name)
        and func.value.id == "registry"
    )


def _module_registers_tools(module_path: Path) -> bool:
    """检查模块是否包含 registry.register() 调用"""
    try:
        source = module_path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(module_path))
    except (OSError, SyntaxError):
        return False

    return any(_is_registry_register_call(stmt) for stmt in tree.body)


def discover_builtin_tools(tools_dir: Optional[Path] = None) -> List[str]:
    """发现并导入所有内置工具模块"""
    tools_path = Path(tools_dir) if tools_dir is not None else Path(__file__).resolve().parent
    module_names = [
        f"prometheus.tools.{path.stem}"
        for path in sorted(tools_path.glob("*.py"))
        if path.name not in {"__init__.py", "registry.py", "mcp_tool.py"}
        and _module_registers_tools(path)
    ]

    imported: List[str] = []
    for mod_name in module_names:
        try:
            importlib.import_module(mod_name)
            imported.append(mod_name)
        except Exception as e:
            logger.warning("无法导入工具模块 %s: %s", mod_name, e)
    return imported


class ToolEntry:
    """工具条目元数据"""

    __slots__ = (
        "name", "toolset", "schema", "handler", "check_fn",
        "requires_env", "is_async", "description", "emoji",
        "max_result_size_chars",
    )

    def __init__(self, name, toolset, schema, handler, check_fn,
                 requires_env, is_async, description, emoji,
                 max_result_size_chars=None):
        self.name = name
        self.toolset = toolset
        self.schema = schema
        self.handler = handler
        self.check_fn = check_fn
        self.requires_env = requires_env
        self.is_async = is_async
        self.description = description
        self.emoji = emoji
        self.max_result_size_chars = max_result_size_chars


class ToolRegistry:
    """
    单例工具注册表
    收集工具的 schema 和 handler，管理工具生命周期
    """

    def __init__(self):
        self._tools: Dict[str, ToolEntry] = {}
        self._toolset_checks: Dict[str, Callable] = {}
        self._toolset_aliases: Dict[str, str] = {}
        self._lock = threading.RLock()

    def _snapshot_state(self) -> tuple[List[ToolEntry], Dict[str, Callable]]:
        """获取注册表状态的稳定快照"""
        with self._lock:
            return list(self._tools.values()), dict(self._toolset_checks)

    def _snapshot_entries(self) -> List[ToolEntry]:
        """获取工具条目的稳定快照"""
        return self._snapshot_state()[0]

    def _snapshot_toolset_checks(self) -> Dict[str, Callable]:
        """获取工具集检查函数的稳定快照"""
        return self._snapshot_state()[1]

    def _evaluate_toolset_check(self, toolset: str, check: Optional[Callable]) -> bool:
        """评估工具集检查函数"""
        if not check:
            return True
        try:
            return bool(check())
        except Exception:
            logger.debug("工具集 %s 检查失败，标记为不可用", toolset)
            return False

    def get_entry(self, name: str) -> Optional[ToolEntry]:
        """根据名称获取工具条目"""
        with self._lock:
            return self._tools.get(name)

    def get_registered_toolset_names(self) -> List[str]:
        """获取所有注册的工具集名称"""
        return sorted({entry.toolset for entry in self._snapshot_entries()})

    def get_tool_names_for_toolset(self, toolset: str) -> List[str]:
        """获取指定工具集下的所有工具名称"""
        return sorted(
            entry.name for entry in self._snapshot_entries()
            if entry.toolset == toolset
        )

    def register_toolset_alias(self, alias: str, toolset: str) -> None:
        """注册工具集别名"""
        with self._lock:
            existing = self._toolset_aliases.get(alias)
            if existing and existing != toolset:
                logger.warning(
                    "工具集别名冲突: '%s' (%s) 被覆盖为 %s",
                    alias, existing, toolset,
                )
            self._toolset_aliases[alias] = toolset

    def get_registered_toolset_aliases(self) -> Dict[str, str]:
        """获取所有工具集别名映射"""
        with self._lock:
            return dict(self._toolset_aliases)

    def get_toolset_alias_target(self, alias: str) -> Optional[str]:
        """获取别名对应的目标工具集"""
        with self._lock:
            return self._toolset_aliases.get(alias)

    def register(
        self,
        name: str,
        toolset: str,
        schema: dict,
        handler: Callable,
        check_fn: Callable = None,
        requires_env: list = None,
        is_async: bool = False,
        description: str = "",
        emoji: str = "",
        max_result_size_chars: Optional[Union[int, float]] = None,
    ):
        """
        注册工具
        
        参数:
            name: 工具名称
            toolset: 工具集名称
            schema: OpenAI 格式的工具 schema
            handler: 工具处理函数
            check_fn: 可用性检查函数
            requires_env: 需要的环境变量列表
            is_async: 是否是异步函数
            description: 工具描述
            emoji: 工具 emoji 图标
            max_result_size_chars: 结果最大字符数
        """
        with self._lock:
            existing = self._tools.get(name)
            if existing and existing.toolset != toolset:
                both_mcp = (
                    existing.toolset.startswith("mcp-")
                    and toolset.startswith("mcp-")
                )
                if both_mcp:
                    logger.debug(
                        "工具 '%s': MCP 工具集 '%s' 覆盖 MCP 工具集 '%s'",
                        name, toolset, existing.toolset,
                    )
                else:
                    logger.error(
                        "工具注册被拒绝: '%s' (工具集 '%s') 将会覆盖现有工具 '%s'",
                        name, toolset, existing.toolset,
                    )
                    return
            self._tools[name] = ToolEntry(
                name=name,
                toolset=toolset,
                schema=schema,
                handler=handler,
                check_fn=check_fn,
                requires_env=requires_env or [],
                is_async=is_async,
                description=description or schema.get("description", ""),
                emoji=emoji,
                max_result_size_chars=max_result_size_chars,
            )
            if check_fn and toolset not in self._toolset_checks:
                self._toolset_checks[toolset] = check_fn

    def deregister(self, name: str) -> None:
        """注销工具"""
        with self._lock:
            entry = self._tools.pop(name, None)
            if entry is None:
                return
            toolset_still_exists = any(
                e.toolset == entry.toolset for e in self._tools.values()
            )
            if not toolset_still_exists:
                self._toolset_checks.pop(entry.toolset, None)
                self._toolset_aliases = {
                    alias: target
                    for alias, target in self._toolset_aliases.items()
                    if target != entry.toolset
                }
        logger.debug("工具已注销: %s", name)

    def get_definitions(self, tool_names: Set[str], quiet: bool = False) -> List[dict]:
        """获取工具定义列表（OpenAI 格式）"""
        result = []
        check_results: Dict[Callable, bool] = {}
        entries_by_name = {entry.name: entry for entry in self._snapshot_entries()}
        for name in sorted(tool_names):
            entry = entries_by_name.get(name)
            if not entry:
                continue
            if entry.check_fn:
                if entry.check_fn not in check_results:
                    try:
                        check_results[entry.check_fn] = bool(entry.check_fn())
                    except Exception:
                        check_results[entry.check_fn] = False
                        if not quiet:
                            logger.debug("工具 %s 检查失败，跳过", name)
                if not check_results[entry.check_fn]:
                    if not quiet:
                        logger.debug("工具 %s 不可用（检查失败）", name)
                    continue
            schema_with_name = {**entry.schema, "name": entry.name}
            result.append({"type": "function", "function": schema_with_name})
        return result

    def dispatch(self, name: str, args: dict, **kwargs) -> str:
        """
        执行工具
        
        参数:
            name: 工具名称
            args: 工具参数
            **kwargs: 额外参数
            
        返回:
            JSON 格式的结果字符串
        """
        entry = self.get_entry(name)
        if not entry:
            return json.dumps({"error": f"未知工具: {name}"}, ensure_ascii=False)
        try:
            if entry.is_async:
                import asyncio
                return asyncio.run(entry.handler(args, **kwargs))
            return entry.handler(args, **kwargs)
        except Exception as e:
            logger.exception("工具 %s 执行错误: %s", name, e)
            return json.dumps({"error": f"工具执行失败: {type(e).__name__}: {e}"}, ensure_ascii=False)

    def get_max_result_size(self, name: str, default: Optional[Union[int, float]] = None) -> Union[int, float]:
        """获取工具的最大结果大小"""
        entry = self.get_entry(name)
        if entry and entry.max_result_size_chars is not None:
            return entry.max_result_size_chars
        if default is not None:
            return default
        return 100000  # 默认 100KB

    def get_all_tool_names(self) -> List[str]:
        """获取所有注册的工具名称"""
        return sorted(entry.name for entry in self._snapshot_entries())

    def get_schema(self, name: str) -> Optional[dict]:
        """获取工具的 schema"""
        entry = self.get_entry(name)
        return entry.schema if entry else None

    def get_toolset_for_tool(self, name: str) -> Optional[str]:
        """获取工具所属的工具集"""
        entry = self.get_entry(name)
        return entry.toolset if entry else None

    def get_emoji(self, name: str, default: str = "⚡") -> str:
        """获取工具的 emoji 图标"""
        entry = self.get_entry(name)
        return (entry.emoji if entry and entry.emoji else default)

    def get_tool_to_toolset_map(self) -> Dict[str, str]:
        """获取工具到工具集的映射"""
        return {entry.name: entry.toolset for entry in self._snapshot_entries()}

    def is_toolset_available(self, toolset: str) -> bool:
        """检查工具集是否可用"""
        with self._lock:
            check = self._toolset_checks.get(toolset)
        return self._evaluate_toolset_check(toolset, check)

    def check_toolset_requirements(self) -> Dict[str, bool]:
        """检查所有工具集的可用性"""
        entries, toolset_checks = self._snapshot_state()
        toolsets = sorted({entry.toolset for entry in entries})
        return {
            toolset: self._evaluate_toolset_check(toolset, toolset_checks.get(toolset))
            for toolset in toolsets
        }

    def get_available_toolsets(self) -> Dict[str, dict]:
        """获取可用的工具集信息"""
        toolsets: Dict[str, dict] = {}
        entries, toolset_checks = self._snapshot_state()
        for entry in entries:
            ts = entry.toolset
            if ts not in toolsets:
                toolsets[ts] = {
                    "available": self._evaluate_toolset_check(
                        ts, toolset_checks.get(ts)
                    ),
                    "tools": [],
                    "description": "",
                    "requirements": [],
                }
            toolsets[ts]["tools"].append(entry.name)
            if entry.requires_env:
                for env in entry.requires_env:
                    if env not in toolsets[ts]["requirements"]:
                        toolsets[ts]["requirements"].append(env)
        return toolsets

    def get_toolset_requirements(self) -> Dict[str, dict]:
        """获取工具集需求信息"""
        result: Dict[str, dict] = {}
        entries, toolset_checks = self._snapshot_state()
        for entry in entries:
            ts = entry.toolset
            if ts not in result:
                result[ts] = {
                    "name": ts,
                    "env_vars": [],
                    "check_fn": toolset_checks.get(ts),
                    "setup_url": None,
                    "tools": [],
                }
            if entry.name not in result[ts]["tools"]:
                result[ts]["tools"].append(entry.name)
            for env in entry.requires_env:
                if env not in result[ts]["env_vars"]:
                    result[ts]["env_vars"].append(env)
        return result

    def check_tool_availability(self, quiet: bool = False):
        """检查工具可用性"""
        available = []
        unavailable = []
        seen = set()
        entries, toolset_checks = self._snapshot_state()
        for entry in entries:
            ts = entry.toolset
            if ts in seen:
                continue
            seen.add(ts)
            if self._evaluate_toolset_check(ts, toolset_checks.get(ts)):
                available.append(ts)
            else:
                unavailable.append({
                    "name": ts,
                    "env_vars": entry.requires_env,
                    "tools": [e.name for e in entries if e.toolset == ts],
                })
        return available, unavailable


# 模块级单例
registry = ToolRegistry()


def tool_error(message, **extra) -> str:
    """
    返回工具错误的 JSON 字符串
    
    示例:
        return tool_error("文件未找到")
        return tool_error("输入错误", code=404)
    """
    result = {"error": str(message)}
    if extra:
        result.update(extra)
    return json.dumps(result, ensure_ascii=False)


def tool_result(data=None, **kwargs) -> str:
    """
    返回工具结果的 JSON 字符串
    
    可以传入字典或者关键字参数:
        return tool_result(success=True, count=42)
        return tool_result({"key": "value"})
    """
    if data is not None:
        return json.dumps(data, ensure_ascii=False)
    return json.dumps(kwargs, ensure_ascii=False)

