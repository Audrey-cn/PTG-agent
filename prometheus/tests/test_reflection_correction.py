#!/usr/bin/env python3
"""
🧪 自我反思 + 自我纠错 测试套件

运行: cd ~/.hermes/tools/prometheus && python -m pytest tests/test_reflection_correction.py -v
"""

import os
import sys
import json
import tempfile
import pytest

PROMETHEUS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROMETHEUS_DIR not in sys.path:
    sys.path.insert(0, PROMETHEUS_DIR)

from genes.reflection import (
    SelfReflection, ObservationCollector, PatternAnalyzer,
    ProposalManager, EventType, Severity,
    _analyze_state_health,
)
from genes.correction import (
    SelfCorrection, ErrorDiagnoser, FixExecutor, ErrorRecord,
    ErrorCategory, FixStrategy,
    RetryPolicy, RetryRecord, RetryResult, DegradationMode,
)


# ═══════════════════════════════════════════
#   Fixtures
# ═══════════════════════════════════════════

@pytest.fixture
def sr(tmp_path):
    """创建临时自我反思引擎"""
    db = str(tmp_path / "test_reflection.db")
    collector = ObservationCollector(db_path=db)
    proposals = ProposalManager(db_path=db)
    sr = SelfReflection.__new__(SelfReflection)
    sr.collector = collector
    sr.analyzer = PatternAnalyzer(collector)
    sr.proposals = proposals
    return sr


@pytest.fixture
def sc(tmp_path):
    """创建临时自我纠错引擎"""
    db = str(tmp_path / "test_correction.db")
    return SelfCorrection(db_path=db)


@pytest.fixture
def sc_with_reflection(tmp_path, sr):
    """带反思引擎的纠错引擎"""
    db = str(tmp_path / "test_correction2.db")
    return SelfCorrection(reflection=sr, db_path=db)


# ═══════════════════════════════════════════
#   1. 观察收集器测试
# ═══════════════════════════════════════════

class TestObservationCollector:
    """观察收集器"""

    def test_record_and_query(self, sr):
        """记录后应可查询"""
        sr.collector.record("tool_call", "web_search", result="success")
        results = sr.collector.query(event_type="tool_call")
        assert len(results) == 1
        assert results[0]["action"] == "web_search"

    def test_record_returns_id(self, sr):
        """记录应返回 ID"""
        obs_id = sr.collector.record("tool_call", "test_op")
        assert obs_id.startswith("obs_")

    def test_query_by_result(self, sr):
        """应可按结果过滤"""
        sr.collector.record("tool_call", "op1", result="success")
        sr.collector.record("tool_call", "op2", result="failure")
        sr.collector.record("tool_call", "op3", result="success")

        successes = sr.collector.query(result="success")
        failures = sr.collector.query(result="failure")
        assert len(successes) == 2
        assert len(failures) == 1

    def test_query_by_severity(self, sr):
        """应可按严重程度过滤"""
        sr.collector.record("error", "op1", severity="error")
        sr.collector.record("system", "op2", severity="info")
        errors = sr.collector.query(severity="error")
        assert len(errors) == 1

    def test_query_with_limit(self, sr):
        """应支持数量限制"""
        for i in range(20):
            sr.collector.record("tool_call", f"op_{i}")
        results = sr.collector.query(limit=5)
        assert len(results) == 5

    def test_stats(self, sr):
        """统计应返回结构化数据"""
        sr.collector.record("tool_call", "op1", result="success", duration_ms=100)
        sr.collector.record("tool_call", "op2", result="failure", duration_ms=200)
        stats = sr.collector.stats()
        assert stats["total"] == 2
        assert stats["by_result"]["success"] == 1
        assert stats["by_result"]["failure"] == 1
        assert stats["failure_rate"] == 50.0

    def test_stats_empty(self, sr):
        """空记录应返回 total=0"""
        stats = sr.collector.stats()
        assert stats["total"] == 0

    def test_persistence(self, tmp_path):
        """观察记录应持久化"""
        db = str(tmp_path / "persist_obs.db")
        c1 = ObservationCollector(db_path=db)
        c1.record("tool_call", "persist_test")

        c2 = ObservationCollector(db_path=db)
        results = c2.query()
        assert len(results) == 1


# ═══════════════════════════════════════════
#   2. 模式分析器测试
# ═══════════════════════════════════════════

class TestPatternAnalyzer:
    """模式分析器"""

    def test_detect_repeated_failures(self, sr):
        """应检测重复失败"""
        for _ in range(5):
            sr.collector.record("tool_call", "broken_tool", result="failure")

        analysis = sr.analyzer.analyze_all()
        issues = analysis["issues"]
        repeated = [i for i in issues if i["type"] == "repeated_failure"]
        assert len(repeated) >= 1
        assert "broken_tool" in repeated[0]["title"]

    def test_no_issues_when_healthy(self, sr):
        """健康运行时不应有问题"""
        for i in range(10):
            sr.collector.record("tool_call", f"op_{i}", result="success")

        analysis = sr.analyzer.analyze_all()
        assert analysis["total_issues"] == 0

    def test_error_cluster_detection(self, sr):
        """应检测错误集群"""
        for _ in range(6):
            sr.collector.record("error", "critical_op", result="failure", severity="error")

        analysis = sr.analyzer.analyze_all()
        clusters = [i for i in analysis["issues"] if i["type"] == "error_cluster"]
        assert len(clusters) >= 1

    def test_analyze_returns_structure(self, sr):
        """分析应返回标准结构"""
        analysis = sr.analyzer.analyze_all()
        assert "issues" in analysis
        assert "total_issues" in analysis
        assert "analyzed_at" in analysis


# ═══════════════════════════════════════════
#   3. 提案管理器测试
# ═══════════════════════════════════════════

class TestProposalManager:
    """提案管理器"""

    def test_create_proposal(self, sr):
        """创建提案应成功"""
        prop_id = sr.proposals.create(
            title="测试提案",
            description="这是一个测试",
            category="efficiency",
        )
        assert prop_id.startswith("prop_")

    def test_pending_count(self, sr):
        """应正确统计待处理数量"""
        sr.proposals.create("提案1", "desc1", "category1")
        sr.proposals.create("提案2", "desc2", "category2")
        assert sr.proposals.pending_count() == 2

    def test_approve_proposal(self, sr):
        """批准提案应更新状态"""
        sr.proposals.create("测试", "desc", "cat")
        result = sr.proposals.approve(0, feedback="同意")
        assert result.get("approved") is True
        assert sr.proposals.pending_count() == 0

    def test_reject_proposal(self, sr):
        """拒绝提案应更新状态"""
        sr.proposals.create("测试", "desc", "cat")
        result = sr.proposals.reject(0, feedback="不需要")
        assert result.get("rejected") is True

    def test_should_report(self, sr):
        """达到阈值时应触发报告"""
        assert sr.proposals.should_report() is False

        for i in range(5):
            sr.proposals.create(f"提案{i}", f"desc{i}", "cat")

        assert sr.proposals.should_report() is True

    def test_get_pending(self, sr):
        """应返回待处理提案列表"""
        sr.proposals.create("待处理", "desc", "cat")
        sr.proposals.create("已批准", "desc", "cat")
        sr.proposals.approve(1)

        pending = sr.proposals.get_pending()
        assert len(pending) == 1

    def test_generate_report(self, sr):
        """报告应包含提案信息"""
        for i in range(3):
            sr.proposals.create(f"提案{i}", f"描述{i}", "cat")
        report = sr.proposals.generate_report()
        assert "提案" in report
        assert "#" in report

    def test_empty_report(self, sr):
        """无提案时应返回提示"""
        report = sr.proposals.generate_report()
        assert "无待处理" in report

    def test_persistence(self, tmp_path):
        """提案应持久化"""
        db = str(tmp_path / "persist_props.db")
        p1 = ProposalManager(db_path=db)
        p1.create("持久化测试", "desc", "cat")

        p2 = ProposalManager(db_path=db)
        assert p2.pending_count() == 1


# ═══════════════════════════════════════════
#   4. 自我反思引擎测试
# ═══════════════════════════════════════════

class TestSelfReflection:
    """自我反思引擎整合"""

    def test_observe_tool_call(self, sr):
        """observe_tool_call 应记录事件"""
        sr.observe_tool_call("web_search", success=True, duration_ms=500)
        stats = sr.stats()
        assert stats["total"] == 1

    def test_observe_error(self, sr):
        """observe_error 应记录错误事件"""
        sr.observe_error("timeout", detail="请求超时")
        stats = sr.stats()
        assert stats["total"] == 1

    def test_reflect(self, sr):
        """reflect 应返回完整反思结果"""
        sr.observe_tool_call("op1", success=False)
        sr.observe_tool_call("op2", success=False)
        sr.observe_tool_call("op3", success=False)

        result = sr.reflect()
        assert "stats" in result
        assert "analysis" in result
        assert "pending_proposals" in result

    def test_reflect_generates_proposals(self, sr):
        """反思应将问题转化为提案"""
        for _ in range(5):
            sr.observe_error("broken_op", detail="持续失败")

        sr.reflect()
        assert sr.proposals.pending_count() > 0

    def test_daily_review(self, sr):
        """每日复盘应返回报告"""
        sr.observe_tool_call("op1", success=True)
        sr.observe_tool_call("op2", success=False)
        report = sr.daily_review()
        assert "每日反思报告" in report
        assert "运行统计" in report

    def test_dedup_proposals(self, sr):
        """重复问题不应创建重复提案"""
        for _ in range(10):
            sr.observe_error("same_error", detail="相同错误")

        sr.reflect()
        sr.reflect()  # 再次反思

        # 同类问题应该只产生一个提案（去重）
        pending = sr.pending_proposals()
        titles = [p["title"] for p in pending]
        assert len(titles) == len(set(titles))


# ═══════════════════════════════════════════
#   5. 错误诊断器测试
# ═══════════════════════════════════════════

class TestErrorDiagnoser:
    """错误诊断器"""

    def test_diagnose_timeout(self):
        """超时应诊断为工具失败+自动重试"""
        d = ErrorDiagnoser.diagnose("timeout", "请求超时")
        assert d["category"] == ErrorCategory.TOOL_FAILURE.value
        assert d["strategy"] == FixStrategy.AUTO_RETRY.value

    def test_diagnose_permission(self):
        """权限错误应诊断为工具失败+提交提案"""
        d = ErrorDiagnoser.diagnose("permission_denied", "无权限")
        assert d["category"] == ErrorCategory.TOOL_FAILURE.value
        assert d["strategy"] == FixStrategy.PROPOSE.value

    def test_diagnose_context_overflow(self):
        """上下文溢出应诊断为上下文溢出+自动压缩"""
        d = ErrorDiagnoser.diagnose("context_length_exceeded", "超过限制")
        assert d["category"] == ErrorCategory.CONTEXT_OVERFLOW.value
        assert d["strategy"] == FixStrategy.AUTO_COMPRESS.value

    def test_diagnose_seed_corruption(self):
        """种子损坏应诊断为种子损坏+回滚"""
        d = ErrorDiagnoser.diagnose("yaml_parse_error", "YAML 解析失败")
        assert d["category"] == ErrorCategory.SEED_CORRUPTION.value
        assert d["strategy"] == FixStrategy.ROLLBACK.value

    def test_diagnose_unknown(self):
        """未知错误应诊断为未知+提交提案"""
        d = ErrorDiagnoser.diagnose("weird_error_xyz", "奇怪的错误")
        assert d["category"] == ErrorCategory.UNKNOWN.value

    def test_diagnose_returns_confidence(self):
        """诊断应返回置信度"""
        d = ErrorDiagnoser.diagnose("timeout", "超时")
        assert 0 <= d["confidence"] <= 1

    def test_diagnose_returns_suggestion(self):
        """诊断应返回修复建议"""
        d = ErrorDiagnoser.diagnose("timeout", "超时")
        assert len(d["suggested_fix"]) > 0


# ═══════════════════════════════════════════
#   6. 修复执行器测试
# ═══════════════════════════════════════════

class TestFixExecutor:
    """修复执行器"""

    def test_auto_retry(self, sc):
        """自动重试应返回建议"""
        error = ErrorRecord(error_type="timeout", category="tool_failure", message="超时")
        diagnosis = {"strategy": "auto_retry", "category": "tool_failure"}
        result = sc.executor.execute_fix(error, diagnosis)
        assert result.success is True
        assert result.strategy == "auto_retry"

    def test_auto_compress(self, sc):
        """自动压缩应返回建议"""
        error = ErrorRecord(error_type="overflow", category="context_overflow", message="溢出")
        diagnosis = {"strategy": "auto_compress", "category": "context_overflow"}
        result = sc.executor.execute_fix(error, diagnosis)
        assert result.success is True
        assert result.strategy == "auto_compress"

    def test_propose_fix(self, sc_with_reflection):
        """需要提案的修复应创建提案"""
        sc = sc_with_reflection
        error = ErrorRecord(error_type="permission", category="tool_failure", message="权限不足")
        diagnosis = {"strategy": "propose", "category": "tool_failure", "diagnosis": "权限问题"}
        result = sc.executor.execute_fix(error, diagnosis)
        assert result.strategy == "propose"
        assert "proposal_id" in result.details


# ═══════════════════════════════════════════
#   7. 自我纠错引擎测试
# ═══════════════════════════════════════════

class TestSelfCorrection:
    """自我纠错引擎整合"""

    def test_handle_error(self, sc):
        """handle_error 应返回修复结果"""
        result = sc.handle_error("timeout", "请求超时")
        assert isinstance(result.success, bool)
        assert result.strategy

    def test_handle_tool_failure(self, sc):
        """handle_tool_failure 应正常工作"""
        result = sc.handle_tool_failure("web_search", "连接被拒绝")
        assert result.strategy

    def test_handle_seed_error(self, sc):
        """handle_seed_error 应正常工作"""
        result = sc.handle_seed_error("parse", "/path/to/seed.ttg", "YAML 错误")
        assert result.strategy

    def test_handle_context_overflow(self, sc):
        """handle_context_overflow 应正常工作"""
        result = sc.handle_context_overflow(15000, 10000)
        assert result.strategy == "auto_compress"

    def test_error_stats(self, sc):
        """错误统计应正常"""
        sc.handle_error("type1", "msg1")
        sc.handle_error("type2", "msg2")
        stats = sc.error_stats()
        assert stats["total"] == 2

    def test_recent_errors(self, sc):
        """最近错误应返回列表"""
        sc.handle_error("type1", "msg1")
        errors = sc.recent_errors(limit=5)
        assert len(errors) == 1

    def test_with_reflection_integration(self, sc_with_reflection):
        """带反思引擎时应记录到反思"""
        sc = sc_with_reflection
        sc.handle_error("test_error", "测试错误", context="test")
        # 反思引擎应收到错误记录
        stats = sc.reflection.stats()
        assert stats["total"] >= 1

    def test_persistence(self, tmp_path):
        """错误记录应持久化"""
        db = str(tmp_path / "persist_corr.db")
        sc1 = SelfCorrection(db_path=db)
        sc1.handle_error("test", "持久化测试")

        sc2 = SelfCorrection(db_path=db)
        assert sc2.error_stats()["total"] == 1


# ═══════════════════════════════════════════
#   8. 枚举和常量测试
# ═══════════════════════════════════════════

class TestEnumsAndConstants:
    """枚举和常量"""

    def test_error_categories(self):
        """应有7种错误分类"""
        assert len(ErrorCategory) == 7

    def test_fix_strategies(self):
        """应有5种修复策略"""
        assert len(FixStrategy) == 5

    def test_event_types(self):
        """应有8种事件类型"""
        assert len(EventType) == 8

    def test_proposal_threshold(self, tmp_path):
        """阈值现在通过 ProposalManager 构造函数配置"""
        pm = ProposalManager(db_path=str(tmp_path / "test_threshold.db"), threshold=3)
        assert pm._threshold == 3
        assert isinstance(pm._threshold, int)


# ═══════════════════════════════════════════
#   9. 四模块整合测试
# ═══════════════════════════════════════════

class TestFullIntegration:
    """四个模块的整合工作流"""

    def test_observe_analyze_propose_fix(self, tmp_path):
        """完整的观察→分析→提案→修复流程"""
        # 初始化所有模块（共享同一个隔离 DB）
        db = str(tmp_path / "integration.db")
        sr = SelfReflection(db_path=db)
        sc = SelfCorrection(reflection=sr, db_path=db)

        # 1. 观察：多次失败
        for _ in range(5):
            sr.observe_error("failing_tool", detail="持续失败")
            sc.handle_error("failing_tool", "调用失败")

        # 2. 反思：分析并生成提案
        result = sr.reflect()
        assert result["pending_proposals"] > 0

        # 3. 用户批准提案
        pending = sr.pending_proposals()
        if pending:
            sr.approve_proposal(0, feedback="同意修复")

        # 4. 验证
        assert sr.proposals.pending_count() == 0 or sr.proposals.pending_count() < len(pending)
        stats = sc.error_stats()
        assert stats["total"] > 0


# ═══════════════════════════════════════════
#   10. 重试策略测试
# ═══════════════════════════════════════════

class TestRetryPolicy:
    """重试策略配置"""

    def test_default_policy(self):
        """默认策略应有合理值"""
        p = RetryPolicy()
        assert p.max_retries == 3
        assert p.base_delay_ms == 1000
        assert p.backoff_factor == 2.0
        assert p.max_delay_ms == 30000
        assert "timeout" in p.retry_on

    def test_get_delay_exponential_backoff(self):
        """延迟应呈指数增长"""
        p = RetryPolicy(base_delay_ms=1000, backoff_factor=2.0, max_delay_ms=60000)
        assert p.get_delay(0) == 1.0    # 1000ms
        assert p.get_delay(1) == 2.0    # 2000ms
        assert p.get_delay(2) == 4.0    # 4000ms
        assert p.get_delay(3) == 8.0    # 8000ms

    def test_get_delay_max_cap(self):
        """延迟不应超过最大值"""
        p = RetryPolicy(base_delay_ms=1000, backoff_factor=10.0, max_delay_ms=5000)
        assert p.get_delay(0) == 1.0
        assert p.get_delay(1) == 5.0    # cap at 5000ms
        assert p.get_delay(5) == 5.0    # still capped

    def test_should_retry_matching_type(self):
        """匹配的错误类型应允许重试"""
        p = RetryPolicy(max_retries=3, retry_on=["timeout", "rate_limit"])
        assert p.should_retry("timeout", 0) is True
        assert p.should_retry("rate_limit_error", 0) is True

    def test_should_retry_exhausted(self):
        """超过最大次数时不应重试"""
        p = RetryPolicy(max_retries=3)
        assert p.should_retry("timeout", 3) is False
        assert p.should_retry("timeout", 5) is False

    def test_should_retry_non_matching_type(self):
        """不匹配的错误类型不应重试"""
        p = RetryPolicy(retry_on=["timeout"])
        assert p.should_retry("permission_denied", 0) is False

    def test_custom_retry_on(self):
        """可自定义可重试的错误类型"""
        p = RetryPolicy(retry_on=["custom_error"])
        assert p.should_retry("custom_error", 0) is True
        assert p.should_retry("timeout", 0) is False


# ═══════════════════════════════════════════
#   11. 重试记录和结果测试
# ═══════════════════════════════════════════

class TestRetryRecordAndResult:
    """重试记录和结果"""

    def test_retry_record_to_dict(self):
        """RetryRecord 应可序列化"""
        r = RetryRecord(attempt=1, error_type="TimeoutError", error_message="超时", delay_seconds=2.0)
        d = r.to_dict()
        assert d["attempt"] == 1
        assert d["error_type"] == "TimeoutError"
        assert d["timestamp"]  # 应自动填充

    def test_retry_result_to_dict_success(self):
        """成功的 RetryResult 应正确序列化"""
        rr = RetryResult(success=True, final_value="ok", attempts=2)
        d = rr.to_dict()
        assert d["success"] is True
        assert d["attempts"] == 2
        assert d["error_message"] == ""

    def test_retry_result_to_dict_failure(self):
        """失败的 RetryResult 应包含错误信息"""
        rr = RetryResult(success=False, attempts=4, error_message="exhausted",
                         records=[RetryRecord(attempt=0, error_type="E", error_message="e", delay_seconds=0.1)])
        d = rr.to_dict()
        assert d["success"] is False
        assert len(d["records"]) == 1


# ═══════════════════════════════════════════
#   12. FixExecutor 重试执行器测试
# ═══════════════════════════════════════════

class TestFixExecutorRetry:
    """FixExecutor 重试机制"""

    def test_execute_with_retry_success_first_try(self, sc):
        """第一次就成功的操作应直接返回"""
        executor = sc.executor
        result = executor.execute_with_retry(
            "test_op", lambda: "hello", policy=RetryPolicy(max_retries=3)
        )
        assert result.success is True
        assert result.final_value == "hello"
        assert result.attempts == 1
        assert len(result.records) == 0

    def test_execute_with_retry_success_after_retries(self, sc):
        """经过重试后成功的操作"""
        call_count = [0]
        def flaky_func():
            call_count[0] += 1
            if call_count[0] < 3:
                raise TimeoutError("超时")
            return "success"

        policy = RetryPolicy(max_retries=5, base_delay_ms=0)  # 不等待
        result = sc.executor.execute_with_retry("flaky", flaky_func, policy=policy)
        assert result.success is True
        assert result.final_value == "success"
        assert result.attempts == 3
        assert len(result.records) == 2  # 前 2 次失败

    def test_execute_with_retry_all_fail(self, sc):
        """所有重试均失败"""
        def always_fail():
            raise TimeoutError("总是超时")

        policy = RetryPolicy(max_retries=2, base_delay_ms=0)
        result = sc.executor.execute_with_retry("always_fail", always_fail, policy=policy)
        assert result.success is False
        assert "超时" in result.error_message
        assert result.attempts >= 2

    def test_execute_with_retry_non_retryable_error(self, sc):
        """不可重试的错误应立即停止"""
        def permission_error():
            raise PermissionError("权限不足")

        policy = RetryPolicy(max_retries=5, base_delay_ms=0)
        result = sc.executor.execute_with_retry("perm", permission_error, policy=policy)
        assert result.success is False
        assert result.attempts <= 1  # 不应重试

    def test_retry_history_recorded(self, sc):
        """重试历史应被记录"""
        def fail_then_succeed():
            raise RuntimeError("temporary")

        # 使用自定义策略使其可重试
        policy = RetryPolicy(max_retries=1, base_delay_ms=0, retry_on=["RuntimeError"])
        sc.executor.execute_with_retry("history_test", fail_then_succeed, policy=policy)
        history = sc.executor.get_retry_history()
        assert len(history) >= 1
        assert history[0]["operation"] == "history_test"

    def test_retry_history_limit(self, sc):
        """重试历史应支持限制"""
        def tmp_err():
            raise RuntimeError("temporary")

        policy = RetryPolicy(max_retries=1, base_delay_ms=0, retry_on=["RuntimeError"])
        # 每次调用产生 1 条失败记录（attempt 0 重试失败），共 10 次 = 10 条
        for _ in range(10):
            sc.executor.execute_with_retry("lim", tmp_err, policy=policy)
        history = sc.executor.get_retry_history(limit=5)
        assert len(history) == 5

    def test_kwargs_passed_to_func(self, sc):
        """kwargs 应正确传递给函数"""
        def add(a, b):
            return a + b

        result = sc.executor.execute_with_retry("add", add, policy=RetryPolicy(), a=3, b=4)
        assert result.success is True
        assert result.final_value == 7


# ═══════════════════════════════════════════
#   13. SelfCorrection 重试和降级测试
# ═══════════════════════════════════════════

class TestSelfCorrectionRetryAndDegradation:
    """SelfCorrection 重试和降级模式"""

    def test_with_retry_success(self, sc):
        """with_retry 成功时应返回函数值"""
        val = sc.with_retry("add", lambda: 42, policy=RetryPolicy())
        assert val == 42

    def test_with_retry_success_with_kwargs(self, sc):
        """with_retry 应传递 kwargs"""
        def multiply(x, y):
            return x * y
        val = sc.with_retry("mul", multiply, policy=RetryPolicy(), x=5, y=6)
        assert val == 30

    def test_with_retry_failure_raises(self, sc):
        """with_retry 最终失败应抛出 RuntimeError"""
        def always_fail():
            raise ValueError("permanent failure")

        policy = RetryPolicy(max_retries=2, base_delay_ms=0, retry_on=["ValueError"])
        with pytest.raises(RuntimeError, match="重试.*次后失败"):
            sc.with_retry("fail_op", always_fail, policy=policy)

    def test_with_retry_failure_records_error(self, sc):
        """with_retry 失败应记录到纠错引擎"""
        def always_fail():
            raise TimeoutError("永久超时")

        policy = RetryPolicy(max_retries=1, base_delay_ms=0)
        try:
            sc.with_retry("record_test", always_fail, policy=policy)
        except RuntimeError:
            pass

        # 应有一条 retry_exhausted 错误记录
        recent = sc.recent_errors(5)
        retry_errors = [e for e in recent if "retry_exhausted" in e["error_type"]]
        assert len(retry_errors) >= 1

    def test_get_degradation_mode_normal(self, sc):
        """无错误时应为 NORMAL"""
        mode = sc.get_degradation_mode()
        assert mode == DegradationMode.NORMAL

    def test_get_degradation_mode_high_success(self, sc):
        """高成功率应为 NORMAL"""
        # 添加 5 条全部已解决的错误
        for _ in range(5):
            r = sc.handle_error("timeout", "超时")
            # 手动标记为已解决（auto_retry 默认 success=True）
        # 所有 auto_retry 的 result.success 都是 True
        mode = sc.get_degradation_mode()
        assert mode == DegradationMode.NORMAL

    def test_get_degradation_mode_retry(self, sc):
        """60-80% 成功率应为 RETRY"""
        # 添加 5 条错误：4 条已解决（80%），1 条未解决 → 80% 在 (60%, 80%] 区间 → RETRY
        for i in range(4):
            sc.handle_error("timeout", "超时")  # auto_retry → resolved=True
        sc.handle_error("permission_denied", "无权限")
        sc.errors[-1].resolved = False  # 1 条未解决

        mode = sc.get_degradation_mode()
        assert mode == DegradationMode.RETRY

    def test_get_degradation_mode_fallback(self, sc):
        """40-60% 成功率应为 FALLBACK"""
        # 添加 5 条错误：3 条已解决（60%），2 条未解决 → 60% 在 (40%, 60%] 区间 → FALLBACK
        for i in range(3):
            sc.handle_error("timeout", "超时")  # resolved=True
        for i in range(2):
            sc.handle_error("permission_denied", "无权限")
            sc.errors[-1].resolved = False

        mode = sc.get_degradation_mode()
        assert mode == DegradationMode.FALLBACK

    def test_get_degradation_mode_minimal(self, sc):
        """≤40% 成功率应为 MINIMAL"""
        sc.handle_error("timeout", "超时")  # resolved=True (1/5)
        for i in range(4):
            sc.handle_error("permission_denied", "无权限")
            sc.errors[-1].resolved = False

        mode = sc.get_degradation_mode()
        assert mode == DegradationMode.MINIMAL

    def test_degradation_mode_enum_values(self):
        """降级模式枚举应有 5 个值"""
        assert len(DegradationMode) == 5
        assert DegradationMode.NORMAL.value == "normal"
        assert DegradationMode.MINIMAL.value == "minimal"


# ═══════════════════════════════════════════
#   入口
# ═══════════════════════════════════════════

from memory.state import SessionState, AgentState


# ═══════════════════════════════════════════
#   10. 状态机 ↔ 反思联动测试
# ═══════════════════════════════════════════

class TestStateReflectionLinkage:
    """状态机与反思模块的联动机制"""

    def test_observe_state_change(self, sr):
        """observe_state_change 应记录状态转换观察"""
        sr.observe_state_change("idle", "thinking", reason="开始任务")
        stats = sr.stats()
        assert stats["total"] == 1
        # 应有 state_change 类型
        assert stats["by_type"].get("state_change", 0) == 1

    def test_observe_state_change_to_error(self, sr):
        """转换到 error 时应记录为 error 严重度"""
        sr.observe_state_change("acting", "error", reason="超时")
        errors = sr.collector.query(severity="error")
        assert len(errors) == 1
        assert errors[0]["detail"] == "超时"

    def test_observe_state_change_from_error(self, sr):
        """从 error 转换时应记录为 warning 严重度"""
        sr.observe_state_change("error", "idle", reason="恢复")
        warnings = sr.collector.query(severity="warning")
        assert len(warnings) == 1

    def test_observe_state_change_metadata(self, sr):
        """状态转换应包含 from/to 元数据"""
        sr.observe_state_change("idle", "thinking", reason="分析需求")
        records = sr.collector.query(event_type="state_change")
        assert len(records) == 1
        meta = records[0]["metadata"]
        assert meta["from_state"] == "idle"
        assert meta["to_state"] == "thinking"
        assert meta["reason"] == "分析需求"

    def test_get_state_health_empty(self, sr):
        """无数据时应返回健康状态"""
        health = sr.get_state_health()
        assert health["is_healthy"] is True
        assert health["error_frequency"] == 0.0
        assert health["stuck_in_reflecting"] is False

    def test_get_state_health_high_error_rate(self, sr):
        """高错误率应被检测"""
        # 10 次转换中 5 次到 error = 50% > 30% 阈值
        for _ in range(5):
            sr.observe_state_change("acting", "error", reason="失败")
        for _ in range(5):
            sr.observe_state_change("idle", "thinking", reason="继续")
        health = sr.get_state_health()
        assert health["is_healthy"] is False
        assert len(health["issues"]) > 0
        assert any("错误频率" in issue for issue in health["issues"])

    def test_get_state_health_normal(self, sr):
        """正常转换应返回健康"""
        sr.observe_state_change("idle", "thinking", reason="r1")
        sr.observe_state_change("thinking", "acting", reason="r2")
        sr.observe_state_change("acting", "thinking", reason="r3")
        sr.observe_state_change("thinking", "idle", reason="r4")
        health = sr.get_state_health()
        assert health["is_healthy"] is True


# ═══════════════════════════════════════════
#   11. 状态机自动反思钩子测试
# ═══════════════════════════════════════════

class TestAutoReflectionHooks:
    """状态机的自动反思钩子系统"""

    @pytest.fixture
    def linked_session(self, tmp_path, sr):
        """创建联动的状态机和反思模块"""
        db = str(tmp_path / "linked.db")
        sr_link = SelfReflection(db_path=db)
        ss = SessionState(db_path=db)
        ss.setup_auto_reflection(sr_link)
        return ss, sr_link

    def test_setup_auto_reflection(self, linked_session):
        """setup_auto_reflection 应注册钩子"""
        ss, _ = linked_session
        assert ss._reflection is not None
        assert "reflecting" in ss._on_enter_hooks
        assert "error" in ss._on_enter_hooks

    def test_reflecting_triggers_reflection(self, linked_session):
        """进入 REFLECTING 应自动触发反思"""
        ss, sr_link = linked_session
        # 需要先从 IDLE 转到 ACTING，再到 REFLECTING
        ss.think(reason="分析")
        ss.act(reason="执行")
        result = ss.reflect(reason="复盘")
        assert result["success"] is True
        # 反思引擎应收到了状态转换记录
        stats = sr_link.stats()
        assert stats["total"] >= 1  # 至少有状态转换观察

    def test_error_triggers_error_observation(self, linked_session):
        """进入 ERROR 应自动记录错误观察"""
        ss, sr_link = linked_session
        ss.think(reason="分析")
        result = ss.error(reason="任务失败")
        assert result["success"] is True
        # 反思引擎应记录了 error 事件
        errors = sr_link.collector.query(severity="error")
        assert len(errors) >= 1

    def test_no_reflection_without_module(self):
        """未配置反思模块时不应出错"""
        with tempfile.TemporaryDirectory() as td:
            db = os.path.join(td, "tmp.db")
            ss = SessionState(db_path=db)
            # 不调用 setup_auto_reflection
            ss.think(reason="测试")
            ss.act(reason="测试")
            result = ss.reflect(reason="测试")
            assert result["success"] is True

    def test_reflection_result_attached_to_task(self, linked_session):
        """反思结果应附加到当前任务元数据"""
        ss, sr_link = linked_session
        ss.start_task("test_task", task_type="test", description="测试任务")
        ss.act(reason="执行")
        ss.reflect(reason="复盘")
        task = ss.current_task()
        assert task is not None
        assert "reflection_result" in task.get("metadata", {})

    def test_hook_context_has_from_to(self, linked_session):
        """钩子应收到包含 from_state 和 to_state 的上下文"""
        ss, sr_link = linked_session
        received_contexts = []

        def capture_hook(state, context):
            received_contexts.append(context)

        ss.on_enter("thinking", capture_hook)
        ss.think(reason="钩子测试")
        assert len(received_contexts) >= 1
        ctx = received_contexts[-1]
        assert "from_state" in ctx
        assert "to_state" in ctx
        assert ctx["from_state"] == "idle"
        assert ctx["to_state"] == "thinking"

    def test_multiple_transitions_recorded(self, linked_session):
        """多次状态转换应都被记录"""
        ss, sr_link = linked_session
        ss.think(reason="r1")
        ss.act(reason="r2")
        ss.reflect(reason="r3")
        ss.idle(reason="r4")

        state_changes = sr_link.collector.query(event_type="state_change")
        # think + act + reflect + idle = 4 次转换
        assert len(state_changes) == 4

    def test_setup_idempotent(self, linked_session):
        """多次调用 setup 应不报错"""
        ss, sr_link = linked_session
        ss.setup_auto_reflection(sr_link)  # 第二次
        ss.think(reason="幂等测试")
        # 不应报错
        assert ss.current_state == AgentState.THINKING


# ═══════════════════════════════════════════
#   12. StateHealthAnalyzer 单元测试
# ═══════════════════════════════════════════

class TestStateHealthAnalyzer:
    """状态机健康度分析"""

    def test_empty_transitions(self):
        """空转换应返回健康"""
        health = _analyze_state_health([], "")
        assert health["is_healthy"] is True

    def test_high_error_frequency(self):
        """高错误频率应被检测"""
        transitions = [
            {"from_state": "acting", "to_state": "error", "duration_ms": 100},
            {"from_state": "error", "to_state": "idle", "duration_ms": 50},
            {"from_state": "acting", "to_state": "error", "duration_ms": 100},
            {"from_state": "error", "to_state": "idle", "duration_ms": 50},
            {"from_state": "acting", "to_state": "error", "duration_ms": 100},
        ]
        health = _analyze_state_health(transitions, "error")
        assert health["is_healthy"] is False
        assert health["error_frequency"] > 0.3

    def test_normal_transitions(self):
        """正常转换应健康"""
        transitions = [
            {"from_state": "idle", "to_state": "thinking", "duration_ms": 100},
            {"from_state": "thinking", "to_state": "acting", "duration_ms": 200},
            {"from_state": "acting", "to_state": "idle", "duration_ms": 300},
        ]
        health = _analyze_state_health(transitions, "idle")
        assert health["is_healthy"] is True
        assert health["error_frequency"] == 0.0

    def test_state_time_distribution(self):
        """应正确计算状态停留时间分布"""
        transitions = [
            {"from_state": "idle", "to_state": "thinking", "duration_ms": 100},
            {"from_state": "thinking", "to_state": "acting", "duration_ms": 200},
            {"from_state": "acting", "to_state": "idle", "duration_ms": 300},
        ]
        health = _analyze_state_health(transitions, "idle")
        dist = health["state_time_distribution"]
        assert dist.get("idle", 0) == 100
        assert dist.get("thinking", 0) == 200
        assert dist.get("acting", 0) == 300

    def test_stuck_in_reflecting(self):
        """当前在 reflecting 且时间过长应被检测"""
        # entered_at 设为很久以前
        import datetime
        old_time = (datetime.datetime.now() - datetime.timedelta(hours=1)).isoformat()
        transitions = [
            {"from_state": "acting", "to_state": "reflecting", "duration_ms": 0},
        ]
        health = _analyze_state_health(transitions, "reflecting", entered_at=old_time)
        assert health["stuck_in_reflecting"] is True
        assert not health["is_healthy"]

    def test_state_jitter_detection(self):
        """状态抖动应被检测"""
        transitions = [
            {"from_state": "idle", "to_state": "thinking", "duration_ms": 10},
            {"from_state": "thinking", "to_state": "acting", "duration_ms": 10},
            {"from_state": "acting", "to_state": "error", "duration_ms": 10},
            {"from_state": "error", "to_state": "idle", "duration_ms": 10},
            {"from_state": "idle", "to_state": "error", "duration_ms": 10},  # error 第2次
            {"from_state": "error", "to_state": "idle", "duration_ms": 10},
            {"from_state": "idle", "to_state": "error", "duration_ms": 10},  # error 第3次
        ]
        health = _analyze_state_health(transitions, "idle")
        # 最近6次中 error 出现3次 → 抖动
        jitter_issues = [i for i in health["issues"] if "抖动" in i]
        assert len(jitter_issues) >= 1

    def test_healthy_when_reflecting_not_stuck(self):
        """在 reflecting 状态但未超时应健康"""
        import datetime
        recent_time = (datetime.datetime.now() - datetime.timedelta(seconds=5)).isoformat()
        transitions = [
            {"from_state": "acting", "to_state": "reflecting", "duration_ms": 0},
        ]
        health = _analyze_state_health(transitions, "reflecting", entered_at=recent_time)
        assert health["stuck_in_reflecting"] is False
        assert health["is_healthy"] is True
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
