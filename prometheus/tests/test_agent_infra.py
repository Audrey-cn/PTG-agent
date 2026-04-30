#!/usr/bin/env python3
"""
🧪 工具注册表 + 运行时状态机 测试套件

运行: cd ~/.hermes/tools/prometheus && python -m pytest tests/test_agent_infra.py -v
"""

import os
import sys
import json
import pytest

PROMETHEUS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROMETHEUS_DIR not in sys.path:
    sys.path.insert(0, PROMETHEUS_DIR)

from tools import ToolRegistry, ToolDefinition, PermissionLevel, ToolCategory
from memory.state import SessionState, AgentState, STATE_META, StateTransition, TaskContext


# ═══════════════════════════════════════════
#   Fixtures
# ═══════════════════════════════════════════

@pytest.fixture
def reg(tmp_path):
    """创建临时工具注册表"""
    state_file = str(tmp_path / "tools.json")
    return ToolRegistry(state_file=state_file)


@pytest.fixture
def ss(tmp_path):
    """创建临时状态机"""
    state_file = str(tmp_path / "state.json")
    return SessionState(state_file=state_file)


# ═══════════════════════════════════════════
#   1. 工具注册表测试
# ═══════════════════════════════════════════

class TestToolRegistry:
    """工具注册表核心功能"""

    def test_builtin_tools_loaded(self, reg):
        """内置工具应自动加载"""
        tools = reg.list_all()
        assert len(tools) >= 7  # 至少7个内置工具

    def test_register_custom_tool(self, reg):
        """注册自定义工具"""
        result = reg.register({
            "name": "web_search",
            "category": "web",
            "description": "网络搜索",
            "permission": "optional",
            "capabilities": ["search"],
        })
        assert result["success"] is True

    def test_register_duplicate_fails(self, reg):
        """重复注册应失败"""
        reg.register({"name": "test_tool", "category": "other"})
        result = reg.register({"name": "test_tool", "category": "other"})
        assert result["success"] is False

    def test_register_empty_name_fails(self, reg):
        """空名称注册应失败"""
        result = reg.register({"name": ""})
        assert result["success"] is False

    def test_unregister_optional(self, reg):
        """注销可选工具"""
        reg.register({"name": "temp_tool", "permission": "optional"})
        result = reg.unregister("temp_tool")
        assert result["success"] is True

    def test_unregister_required_fails(self, reg):
        """注销必需工具应失败"""
        result = reg.unregister("load_seed")
        assert result["success"] is False

    def test_unregister_nonexistent_fails(self, reg):
        """注销不存在的工具应失败"""
        result = reg.unregister("nonexistent_tool")
        assert result["success"] is False

    def test_enable_disable(self, reg):
        """启用/禁用工具"""
        reg.disable("snapshot")
        tool = reg.get("snapshot")
        assert tool["enabled"] is False

        reg.enable("snapshot")
        tool = reg.get("snapshot")
        assert tool["enabled"] is True

    def test_list_by_category(self, reg):
        """按类别列出"""
        tools = reg.list_all(category="file")
        assert all(t["category"] == "file" for t in tools)
        assert len(tools) >= 2  # load_seed, save_seed, etc.

    def test_list_by_permission(self, reg):
        """按权限列出"""
        tools = reg.list_all(permission="required")
        assert all(t["permission"] == "required" for t in tools)
        assert len(tools) >= 4

    def test_check_tool_available(self, reg):
        """检查可用工具"""
        result = reg.check_tool("load_seed")
        assert result.available is True
        assert result.has_permission is True

    def test_check_tool_disabled(self, reg):
        """检查禁用工具"""
        reg.disable("snapshot")
        result = reg.check_tool("snapshot")
        assert result.available is False

    def test_check_tool_nonexistent(self, reg):
        """检查不存在的工具"""
        result = reg.check_tool("nonexistent")
        assert result.available is False

    def test_check_tool_with_missing_dependency(self, reg):
        """依赖缺失时应不可用"""
        reg.register({
            "name": "dep_test",
            "permission": "optional",
            "dependencies": ["nonexistent_dep"],
        })
        result = reg.check_tool("dep_test")
        assert result.available is False
        assert result.dependencies_met is False
        assert "nonexistent_dep" in result.missing_dependencies

    def test_check_all(self, reg):
        """全面检查应返回结构"""
        reg.register({"name": "custom_opt", "permission": "optional"})
        result = reg.check_all()
        assert "available" in result
        assert "unavailable" in result
        assert "total" in result
        assert "availability_pct" in result

    def test_list_capabilities(self, reg):
        """能力映射应正确"""
        caps = reg.list_capabilities()
        assert "seed_read" in caps
        assert "load_seed" in caps["seed_read"]

    def test_seed_requirements_check(self, reg):
        """种子工具需求检查"""
        seed_data = {
            "skill_soul": {
                "tools": {
                    "required": ["load_seed"],
                    "optional": ["snapshot"],
                }
            }
        }
        result = reg.check_seed_requirements(seed_data)
        assert result["checked"] is True
        assert result["all_required_met"] is True

    def test_seed_no_tools_section(self, reg):
        """种子无工具声明时"""
        result = reg.check_seed_requirements({"skill_soul": {}})
        assert result["checked"] is False

    def test_usage_log(self, reg):
        """使用日志应记录"""
        reg.log_usage("load_seed", success=True)
        reg.log_usage("save_seed", success=False)
        stats = reg.usage_stats()
        assert stats["total"] == 2
        assert stats["success_rate"] == 50.0

    def test_persistence(self, tmp_path):
        """自定义工具应持久化"""
        f = str(tmp_path / "persist_tools.json")
        r1 = ToolRegistry(state_file=f)
        r1.register({"name": "persist_tool", "permission": "optional"})

        r2 = ToolRegistry(state_file=f)
        tool = r2.get("persist_tool")
        assert tool is not None
        assert tool["name"] == "persist_tool"


# ═══════════════════════════════════════════
#   2. 状态机测试
# ═══════════════════════════════════════════

class TestSessionState:
    """运行时状态机"""

    def test_default_state_idle(self, ss):
        """默认状态应为空闲"""
        current = ss.current()
        assert current["state"] == "idle"
        assert current["label"] == "空闲"

    def test_think_from_idle(self, ss):
        """空闲→思考"""
        result = ss.think(reason="收到任务")
        assert result["success"] is True
        assert ss.current_state == AgentState.THINKING

    def test_act_from_thinking(self, ss):
        """思考→行动"""
        ss.think()
        result = ss.act(reason="开始执行")
        assert result["success"] is True
        assert ss.current_state == AgentState.ACTING

    def test_wait_from_thinking(self, ss):
        """思考→等待"""
        ss.think()
        result = ss.wait(reason="需要用户确认")
        assert result["success"] is True

    def test_reflect_from_acting(self, ss):
        """行动→反思"""
        ss.think()
        ss.act()
        result = ss.reflect(reason="任务完成，复盘")
        assert result["success"] is True
        assert ss.current_state == AgentState.REFLECTING

    def test_reflect_from_idle(self, ss):
        """空闲→反思"""
        result = ss.reflect(reason="定期复盘")
        assert result["success"] is True

    def test_error_from_acting(self, ss):
        """行动→错误"""
        ss.think()
        ss.act()
        result = ss.error(reason="工具调用失败")
        assert result["success"] is True
        assert ss.current_state == AgentState.ERROR

    def test_idle_from_error(self, ss):
        """错误→空闲（恢复）"""
        ss.think(); ss.act(); ss.error()
        result = ss.idle(reason="已恢复")
        assert result["success"] is True

    def test_invalid_transition_fails(self, ss):
        """非法转换应失败"""
        result = ss.act(reason="空闲状态不能直接行动")
        assert result["success"] is False
        assert "不允许" in result["message"]

    def test_invalid_state_name(self, ss):
        """无效状态名应失败"""
        result = ss.transition("nonexistent")
        assert result["success"] is False

    def test_transition_records_history(self, ss):
        """转换应记录历史"""
        ss.think(reason="测试")
        ss.act(reason="继续")
        history = ss.transition_history()
        assert len(history) >= 2
        assert history[-1]["from_state"] == "thinking"
        assert history[-1]["to_state"] == "acting"

    def test_can_transition_to(self, ss):
        """检查可达状态"""
        assert ss.can_transition_to("thinking") is True
        assert ss.can_transition_to("acting") is False  # 空闲不能直接行动

    def test_in_state_duration(self, ss):
        """停留时间应为正"""
        duration = ss.in_state_duration_ms()
        assert duration >= 0

    def test_start_task(self, ss):
        """开始任务应切换到思考"""
        result = ss.start_task("task_001", task_type="seed_op", description="编辑种子")
        assert result["success"] is True
        assert ss.current_state == AgentState.THINKING
        assert ss.task.task_id == "task_001"

    def test_start_task_when_busy_fails(self, ss):
        """忙碌时开始任务应失败"""
        ss.think()
        result = ss.start_task("task_002")
        assert result["success"] is False

    def test_complete_task_success(self, ss):
        """完成任务应回到空闲"""
        ss.start_task("task_003")
        result = ss.complete_task(success=True, summary="成功完成")
        assert result["success"] is True
        assert ss.current_state == AgentState.IDLE
        assert ss.task is None

    def test_complete_task_failure(self, ss):
        """任务失败应进入错误状态"""
        ss.start_task("task_004")
        result = ss.complete_task(success=False, summary="失败")
        assert ss.current_state == AgentState.ERROR

    def test_complete_no_task_fails(self, ss):
        """没有任务时完成应失败"""
        result = ss.complete_task()
        assert result["success"] is False

    def test_state_summary(self, ss):
        """状态概览应包含统计"""
        ss.think(); ss.act(); ss.idle()
        summary = ss.state_summary()
        assert summary["total_transitions"] >= 3
        assert "state_counts" in summary

    def test_state_meta_complete(self):
        """所有状态都应有元数据"""
        for state in AgentState:
            assert state in STATE_META
            meta = STATE_META[state]
            assert "label" in meta
            assert "emoji" in meta
            assert "allowed_transitions" in meta
            assert "resource_allocation" in meta

    def test_persistence(self, tmp_path):
        """状态应持久化"""
        f = str(tmp_path / "persist_state.json")
        s1 = SessionState(state_file=f)
        s1.think(reason="持久化测试")

        s2 = SessionState(state_file=f)
        assert s2.current_state == AgentState.THINKING
        assert len(s2.transitions) >= 1


# ═══════════════════════════════════════════
#   3. 枚举和常量测试
# ═══════════════════════════════════════════

class TestToolEnums:
    """工具相关枚举"""

    def test_permission_levels(self):
        """应有3种权限层级"""
        assert len(PermissionLevel) == 3

    def test_tool_categories(self):
        """应有9种类别"""
        assert len(ToolCategory) == 10


class TestStateEnums:
    """状态相关枚举"""

    def test_agent_states(self):
        """应有6种运行时状态"""
        assert len(AgentState) == 6

    def test_state_meta_count(self):
        """状态元数据应覆盖所有状态"""
        assert len(STATE_META) == len(AgentState)

    def test_transitions_form_dag(self):
        """所有状态的转换目标应有效"""
        all_states = {s.value for s in AgentState}
        for state, meta in STATE_META.items():
            for target in meta["allowed_transitions"]:
                assert target in all_states, f"{state.value} → {target} 目标无效"


# ═══════════════════════════════════════════
#   4. 整合测试
# ═══════════════════════════════════════════

class TestFullWorkflow:
    """工具注册表 + 状态机 联合工作流"""

    def test_agent_lifecycle(self, tmp_path):
        """完整的 Agent 生命周期"""
        reg = ToolRegistry(state_file=str(tmp_path / "tools.json"))
        ss = SessionState(state_file=str(tmp_path / "state.json"))

        # 1. 检查工具
        status = reg.check_all()
        assert status["availability_pct"] > 0

        # 2. 开始任务
        ss.start_task("seed_edit", task_type="seed_op", description="编辑始祖种子")

        # 3. 检查种子工具需求
        seed_data = {"skill_soul": {"tools": {"required": ["load_seed"]}}}
        req = reg.check_seed_requirements(seed_data)
        assert req["all_required_met"] is True

        # 4. 执行
        ss.act(reason="开始编辑")
        reg.log_usage("load_seed", success=True)
        reg.log_usage("gene_edit", success=True)

        # 5. 完成
        ss.reflect(reason="编辑完成，复盘")
        ss.idle(reason="任务完成")

        # 6. 验证
        assert ss.current_state == AgentState.IDLE
        stats = reg.usage_stats()
        assert stats["total"] == 2


# ═══════════════════════════════════════════
#   入口
# ═══════════════════════════════════════════

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
