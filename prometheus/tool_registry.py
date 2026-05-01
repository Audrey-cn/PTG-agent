#!/usr/bin/env python3
"""╔══════════════════════════════════════════════════════════════╗."""

import datetime
import json
import os
from dataclasses import asdict, dataclass, field
from enum import Enum

# ═══════════════════════════════════════════
#   配置
# ═══════════════════════════════════════════

REGISTRY_DIR = os.path.expanduser("~/.hermes/tools/prometheus/registry")
os.makedirs(REGISTRY_DIR, exist_ok=True)


class PermissionLevel(Enum):
    """权限层级"""

    REQUIRED = "required"  # 必须可用
    OPTIONAL = "optional"  # 有则增强
    FORBIDDEN = "forbidden"  # 明确禁止


class ToolCategory(Enum):
    """工具类别"""

    FILE = "file"  # 文件操作
    TERMINAL = "terminal"  # 终端命令
    WEB = "web"  # 网络访问
    SEARCH = "search"  # 搜索检索
    DELEGATION = "delegation"  # 子代理委派
    MEMORY = "memory"  # 记忆系统
    MEDIA = "media"  # 媒体处理
    COMMUNICATION = "communication"  # 通信
    CODE = "code"  # 代码执行
    OTHER = "other"  # 其他


@dataclass
class ToolDefinition:
    """工具定义"""

    name: str  # 工具名称
    category: str = "other"  # 类别
    description: str = ""  # 描述
    permission: str = "optional"  # 权限层级
    dependencies: list[str] = field(default_factory=list)  # 依赖的其他工具
    capabilities: list[str] = field(default_factory=list)  # 提供的能力标签
    risk_level: str = "low"  # 风险等级
    version: str = "1.0"  # 版本
    enabled: bool = True  # 是否启用
    metadata: dict = field(default_factory=dict)  # 额外元数据

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ToolCheckResult:
    """工具检查结果"""

    tool: str
    available: bool
    reason: str = ""
    has_permission: bool = True
    dependencies_met: bool = True
    missing_dependencies: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


# ═══════════════════════════════════════════
#   工具注册表
# ═══════════════════════════════════════════


class ToolRegistry:
    """Prometheus 的工具注册表。

    管理工具定义、权限检查、依赖验证和能力查询。
    """

    # 内置工具定义（框架自身提供的能力）
    BUILTIN_TOOLS = {
        "load_seed": ToolDefinition(
            name="load_seed",
            category="file",
            description="加载 .ttg 种子文件",
            permission="required",
            capabilities=["seed_read"],
        ),
        "save_seed": ToolDefinition(
            name="save_seed",
            category="file",
            description="保存 .ttg 种子文件",
            permission="required",
            capabilities=["seed_write"],
        ),
        "gene_edit": ToolDefinition(
            name="gene_edit",
            category="file",
            description="编辑基因位点",
            permission="required",
            capabilities=["gene_edit"],
            dependencies=["load_seed", "save_seed"],
        ),
        "audit": ToolDefinition(
            name="audit",
            category="other",
            description="创始铭刻验证",
            permission="required",
            capabilities=["security"],
        ),
        "snapshot": ToolDefinition(
            name="snapshot",
            category="file",
            description="快照保存与恢复",
            permission="optional",
            capabilities=["backup"],
        ),
        "health_check": ToolDefinition(
            name="health_check",
            category="other",
            description="基因健康度审计",
            permission="optional",
            capabilities=["diagnostics"],
        ),
        "forge": ToolDefinition(
            name="forge",
            category="other",
            description="基因锻造",
            permission="optional",
            capabilities=["reproduction"],
            dependencies=["load_seed"],
        ),
        "chronicler": ToolDefinition(
            name="chronicler",
            category="other",
            description="编史官 · 史诗叙事官 — 标记、追溯、附史TTG种子",
            permission="required",
            capabilities=["seed_read", "seed_write", "seed_audit", "seed_lineage"],
            dependencies=["load_seed", "save_seed"],
        ),
    }

    def __init__(self, state_file: str = None):
        self.state_file = state_file or os.path.join(REGISTRY_DIR, "tool_registry.json")
        self.tools: dict[str, ToolDefinition] = {}
        self._usage_log: list[dict] = []
        self._load_state()

    def register(self, tool_def: dict) -> dict:
        """注册新工具。

        Args:
            tool_def: 工具定义字典

        Returns:
            {success, message, tool_name}
        """
        name = tool_def.get("name", "")
        if not name:
            return {"success": False, "message": "工具名称不能为空"}

        if name in self.tools:
            return {"success": False, "message": f"工具 '{name}' 已注册，请使用 update"}

        td = ToolDefinition(
            **{k: v for k, v in tool_def.items() if k in ToolDefinition.__dataclass_fields__}
        )
        self.tools[name] = td
        self._save_state()

        return {"success": True, "message": f"工具 '{name}' 已注册", "tool_name": name}

    def unregister(self, name: str) -> dict:
        """注销工具。"""
        if name not in self.tools:
            return {"success": False, "message": f"工具 '{name}' 不存在"}

        td = self.tools[name]
        if td.permission == "required":
            return {"success": False, "message": f"工具 '{name}' 是必需工具，不可注销"}

        del self.tools[name]
        self._save_state()
        return {"success": True, "message": f"工具 '{name}' 已注销"}

    def update(self, name: str, updates: dict) -> dict:
        """更新工具定义。"""
        if name not in self.tools:
            return {"success": False, "message": f"工具 '{name}' 不存在"}

        td = self.tools[name]
        for k, v in updates.items():
            if hasattr(td, k):
                setattr(td, k, v)

        self._save_state()
        return {"success": True, "message": f"工具 '{name}' 已更新"}

    def enable(self, name: str) -> dict:
        """启用工具。"""
        return self.update(name, {"enabled": True})

    def disable(self, name: str) -> dict:
        """禁用工具。"""
        return self.update(name, {"enabled": False})

    # ── 查询 ──

    def get(self, name: str) -> dict | None:
        """获取工具定义。"""
        if name in self.tools:
            return self.tools[name].to_dict()
        return None

    def list_all(self, category: str = None, permission: str = None) -> list[dict]:
        """列出所有工具。"""
        tools = list(self.tools.values())
        if category:
            tools = [t for t in tools if t.category == category]
        if permission:
            tools = [t for t in tools if t.permission == permission]
        return [t.to_dict() for t in tools]

    def list_by_permission(self, level: str) -> list[dict]:
        """按权限层级列出。"""
        return self.list_all(permission=level)

    def list_capabilities(self) -> dict[str, list[str]]:
        """列出所有能力及其对应的工具。"""
        cap_map = {}
        for tool in self.tools.values():
            for cap in tool.capabilities:
                if cap not in cap_map:
                    cap_map[cap] = []
                cap_map[cap].append(tool.name)
        return cap_map

    # ── 检查 ──

    def check_tool(self, name: str) -> ToolCheckResult:
        """检查单个工具的可用性。"""
        if name not in self.tools:
            return ToolCheckResult(
                tool=name,
                available=False,
                reason="工具未注册",
            )

        td = self.tools[name]

        # 权限检查
        has_permission = td.permission != PermissionLevel.FORBIDDEN.value
        if not has_permission:
            return ToolCheckResult(
                tool=name,
                available=False,
                reason="工具被禁止",
                has_permission=False,
            )

        # 启用状态
        if not td.enabled:
            return ToolCheckResult(
                tool=name,
                available=False,
                reason="工具已禁用",
                has_permission=True,
            )

        # 依赖检查
        missing_deps = []
        for dep in td.dependencies:
            if dep not in self.tools:
                missing_deps.append(dep)
            elif not self.tools[dep].enabled:
                missing_deps.append(f"{dep}(disabled)")

        deps_met = len(missing_deps) == 0

        return ToolCheckResult(
            tool=name,
            available=has_permission and deps_met,
            has_permission=has_permission,
            dependencies_met=deps_met,
            missing_dependencies=missing_deps,
            reason="可用" if has_permission and deps_met else f"缺少依赖: {missing_deps}",
        )

    def check_all(self) -> dict:
        """检查所有工具的可用性。

        Returns:
            {
                available: [str],
                unavailable: [{tool, reason}],
                required_missing: [str],
                forbidden: [str],
                total: int,
                availability_pct: float,
            }
        """
        available = []
        unavailable = []
        required_missing = []
        forbidden = []

        for name, td in self.tools.items():
            result = self.check_tool(name)
            if result.available:
                available.append(name)
            else:
                unavailable.append({"tool": name, "reason": result.reason})
                if td.permission == "required":
                    required_missing.append(name)
                elif td.permission == "forbidden":
                    forbidden.append(name)

        total = len(self.tools)
        return {
            "available": available,
            "unavailable": unavailable,
            "required_missing": required_missing,
            "forbidden": forbidden,
            "total": total,
            "availability_pct": round(len(available) / total * 100, 1) if total > 0 else 0,
        }

    def check_seed_requirements(self, seed_data: dict) -> dict:
        """检查种子声明的工具需求是否满足。

        种子的 skill_soul 中可以声明 tools:
            required: [web_search, terminal]
            optional: [image_gen]
            forbidden: [file_write]
        """
        skill_soul = seed_data.get("skill_soul", {})
        tools_section = skill_soul.get("tools", {})

        if not tools_section:
            return {"checked": False, "message": "种子未声明工具需求"}

        results = {"checked": True, "required": [], "optional": [], "forbidden": []}

        for tool in tools_section.get("required", []):
            check = self.check_tool(tool)
            results["required"].append(check.to_dict())

        for tool in tools_section.get("optional", []):
            check = self.check_tool(tool)
            results["optional"].append(check.to_dict())

        for tool in tools_section.get("forbidden", []):
            td = self.tools.get(tool)
            is_forbidden = td and td.permission == "forbidden"
            results["forbidden"].append({"tool": tool, "is_forbidden": is_forbidden})

        # 总结
        required_ok = all(r["available"] for r in results["required"])
        results["all_required_met"] = required_ok
        results["summary"] = "满足" if required_ok else "缺少必需工具"

        return results

    # ── 使用日志 ──

    def log_usage(self, tool: str, success: bool, detail: str = ""):
        """记录工具使用。"""
        self._usage_log.append(
            {
                "tool": tool,
                "success": success,
                "detail": detail,
                "timestamp": datetime.datetime.now().isoformat(),
            }
        )
        # 只保留最近 200 条
        self._usage_log = self._usage_log[-200:]

    def usage_stats(self) -> dict:
        """使用统计。"""
        if not self._usage_log:
            return {"total": 0}

        by_tool = {}
        success_count = 0
        for log in self._usage_log:
            tool = log["tool"]
            by_tool[tool] = by_tool.get(tool, 0) + 1
            if log["success"]:
                success_count += 1

        return {
            "total": len(self._usage_log),
            "success_rate": round(success_count / len(self._usage_log) * 100, 1),
            "by_tool": by_tool,
        }

    # ── 持久化 ──

    def _save_state(self):
        state = {
            "tools": {name: td.to_dict() for name, td in self.tools.items()},
            "usage_log": self._usage_log[-50:],
        }
        with open(self.state_file, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)

    def _load_state(self):
        # 先加载内置工具
        for name, td in self.BUILTIN_TOOLS.items():
            self.tools[name] = td

        # 再加载自定义工具（如果有）
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, encoding="utf-8") as f:
                    state = json.load(f)
                for name, td_dict in state.get("tools", {}).items():
                    if name not in self.tools:  # 不覆盖内置工具
                        self.tools[name] = ToolDefinition(**td_dict)
                self._usage_log = state.get("usage_log", [])
            except (json.JSONDecodeError, KeyError, TypeError):
                pass


# ═══════════════════════════════════════════
#   CLI 入口
# ═══════════════════════════════════════════


def main():
    import sys

    if len(sys.argv) < 2:
        print("""
🔧 普罗米修斯 · 工具注册表

用法:
  tool_registry.py list [--category 类别] [--permission 权限]
  tool_registry.py show <工具名>
  tool_registry.py register <JSON定义>
  tool_registry.py unregister <工具名>
  tool_registry.py enable <工具名>
  tool_registry.py disable <工具名>
  tool_registry.py check [工具名]
  tool_registry.py check-all
  tool_registry.py capabilities
  tool_registry.py stats
""")
        return

    reg = ToolRegistry()
    action = sys.argv[1]

    if action == "list":
        category = None
        permission = None
        if "--category" in sys.argv:
            idx = sys.argv.index("--category")
            category = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else None
        if "--permission" in sys.argv:
            idx = sys.argv.index("--permission")
            permission = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else None

        tools = reg.list_all(category=category, permission=permission)
        print(f"\n🔧 工具注册表 ({len(tools)} 个):")
        for t in tools:
            perm_icon = {"required": "🔴", "optional": "🟢", "forbidden": "⛔"}.get(
                t["permission"], "⚪"
            )
            enabled = "" if t["enabled"] else " [已禁用]"
            print(
                f"  {perm_icon} {t['name']:<20} [{t['category']}] {t['description'][:40]}{enabled}"
            )

    elif action == "show" and len(sys.argv) > 2:
        tool = reg.get(sys.argv[2])
        if tool:
            print(f"\n🔧 {tool['name']}:")
            for k, v in tool.items():
                if k != "metadata":
                    print(f"  {k}: {v}")
        else:
            print(f"❌ 工具 '{sys.argv[2]}' 不存在")

    elif action == "check":
        if len(sys.argv) > 2:
            result = reg.check_tool(sys.argv[2])
            status = "✅" if result.available else "❌"
            print(f"{status} {result.tool}: {result.reason}")
        else:
            print("用法: tool_registry.py check <工具名>")

    elif action == "check-all":
        results = reg.check_all()
        print(f"\n📊 工具可用性: {results['availability_pct']}%")
        print(f"  可用: {len(results['available'])}")
        print(f"  不可用: {len(results['unavailable'])}")
        if results["required_missing"]:
            print(f"  ⚠️ 缺少必需工具: {results['required_missing']}")
        if results["forbidden"]:
            print(f"  ⛔ 禁止工具: {results['forbidden']}")

    elif action == "capabilities":
        caps = reg.list_capabilities()
        print("\n📋 能力映射:")
        for cap, tools in sorted(caps.items()):
            print(f"  {cap}: {', '.join(tools)}")

    elif action == "stats":
        stats = reg.usage_stats()
        print("\n📊 使用统计:")
        for k, v in stats.items():
            print(f"  {k}: {v}")

    elif action == "register" and len(sys.argv) > 2:
        tool_def = json.loads(sys.argv[2])
        result = reg.register(tool_def)
        print(f"{'✅' if result['success'] else '❌'} {result['message']}")

    elif action == "unregister" and len(sys.argv) > 2:
        result = reg.unregister(sys.argv[2])
        print(f"{'✅' if result['success'] else '❌'} {result['message']}")

    elif action == "enable" and len(sys.argv) > 2:
        result = reg.enable(sys.argv[2])
        print(f"{'✅' if result['success'] else '❌'} {result['message']}")

    elif action == "disable" and len(sys.argv) > 2:
        result = reg.disable(sys.argv[2])
        print(f"{'✅' if result['success'] else '❌'} {result['message']}")

    else:
        print(f"未知命令: {action}")


if __name__ == "__main__":
    main()
