#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════╗
║   🔧 普罗米修斯 · 自我纠错 · SelfCorrection                ║
║                                                              ║
║   Prometheus 作为独立 Agent 的纠错引擎。                     ║
║   实时检测问题，诊断根因，执行修复或提出建议。               ║
║                                                              ║
║   两层纠错：                                                 ║
║     运行时纠错 — 自动处理可恢复的错误（重试/回退）           ║
║     建议式纠错 — 需要用户批准的修改（提案→批准→执行）       ║
║                                                              ║
║   核心原则：                                                 ║
║     1. 先诊断再修复，不盲目重试                              ║
║     2. 有安全边界的自动修复，无边界的提交提案                ║
║     3. 修复失败时回滚到安全状态                              ║
║     4. 所有修复都记录到反思引擎                              ║
╚══════════════════════════════════════════════════════════════╝
"""

import os
import json
import datetime
import traceback
import time
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field, asdict
from enum import Enum
from storage import StateStore


# ═══════════════════════════════════════════
#   配置
# ═══════════════════════════════════════════

CORRECTION_DIR = os.path.expanduser("~/.hermes/tools/prometheus/correction")
os.makedirs(CORRECTION_DIR, exist_ok=True)


class ErrorCategory(Enum):
    """错误分类"""
    TOOL_FAILURE = "tool_failure"             # 工具调用失败
    SEED_CORRUPTION = "seed_corruption"       # 种子结构损坏
    CONTEXT_OVERFLOW = "context_overflow"     # 上下文溢出
    MEMORY_INCONSISTENCY = "memory_inconsistency"  # 记忆不一致
    STATE_CONFLICT = "state_conflict"         # 状态冲突
    EXTERNAL_DEPENDENCY = "external_dependency"  # 外部依赖失败
    UNKNOWN = "unknown"                       # 未知错误


class FixStrategy(Enum):
    """修复策略"""
    AUTO_RETRY = "auto_retry"        # 自动重试（安全操作）
    AUTO_FALLBACK = "auto_fallback"  # 自动回退（有替代方案时）
    AUTO_COMPRESS = "auto_compress"  # 自动压缩（上下文溢出时）
    PROPOSE = "propose"              # 提交提案（需要用户批准）
    ROLLBACK = "rollback"            # 回滚到快照


class DegradationMode(Enum):
    """降级模式——根据系统健康度自动选择运行模式。"""
    NORMAL = "normal"             # 正常模式：全部功能可用
    RETRY = "retry"               # 重试模式：增强重试策略
    FALLBACK = "fallback"         # 降级到备用方案
    SKIP_OPTIONAL = "skip_optional"  # 跳过可选步骤
    MINIMAL = "minimal"           # 最小化运行：仅核心功能


@dataclass
class RetryPolicy:
    """重试策略配置。
    
    控制重试次数、延迟、退避策略等行为。
    """
    max_retries: int = 3                    # 最大重试次数
    base_delay_ms: int = 1000               # 基础延迟（毫秒）
    backoff_factor: float = 2.0             # 退避因子（指数退避）
    max_delay_ms: int = 30000               # 最大延迟（毫秒）
    retry_on: List[str] = field(default_factory=lambda: ["timeout", "rate_limit", "temporary"])  # 可重试的错误类型

    def get_delay(self, attempt: int) -> float:
        """计算第 N 次重试的延迟时间（秒）。
        
        使用指数退避算法：min(base_delay * factor^attempt, max_delay)
        """
        delay_ms = min(
            self.base_delay_ms * (self.backoff_factor ** attempt),
            self.max_delay_ms,
        )
        return delay_ms / 1000.0

    def should_retry(self, error_type: str, attempt: int) -> bool:
        """判断是否应该重试。
        
        Args:
            error_type: 错误类型标识
            attempt: 当前已重试次数（从 0 开始）
        Returns:
            是否应该重试
        """
        if attempt >= self.max_retries:
            return False
        error_lower = error_type.lower()
        return any(pattern.lower() in error_lower for pattern in self.retry_on)


@dataclass
class RetryRecord:
    """单次重试记录。"""
    attempt: int              # 第几次尝试（从 0 开始）
    error_type: str           # 错误类型
    error_message: str        # 错误信息
    delay_seconds: float      # 本次等待时间（秒）
    timestamp: str = ""       # 时间戳
    success: bool = False     # 本次尝试是否成功

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.datetime.now().isoformat()

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class RetryResult:
    """重试执行结果。"""
    success: bool                                    # 最终是否成功
    final_value: Any = None                          # 成功时的返回值
    attempts: int = 0                                # 总尝试次数（含首次）
    records: List[RetryRecord] = field(default_factory=list)  # 每次重试的记录
    error_message: str = ""                          # 最终失败的错误信息

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "attempts": self.attempts,
            "error_message": self.error_message,
            "records": [r.to_dict() for r in self.records],
        }


@dataclass
class ErrorRecord:
    """错误记录"""
    error_type: str              # 错误类型
    category: str                # 错误分类
    message: str                 # 错误信息
    context: str = ""            # 发生上下文（哪个操作）
    stacktrace: str = ""         # 调用栈
    timestamp: str = ""          # 时间戳
    resolved: bool = False       # 是否已解决
    fix_applied: str = ""        # 应用的修复
    fix_strategy: str = ""       # 使用的策略

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.datetime.now().isoformat()

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class FixResult:
    """修复结果"""
    success: bool
    strategy: str
    message: str
    details: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


# ═══════════════════════════════════════════
#   错误诊断器
# ═══════════════════════════════════════════

class ErrorDiagnoser:
    """分析错误，确定分类和修复策略。"""

    # 错误模式 → 分类 + 策略 映射
    ERROR_PATTERNS = {
        # 工具调用失败
        "timeout": (ErrorCategory.TOOL_FAILURE.value, FixStrategy.AUTO_RETRY.value),
        "connection_refused": (ErrorCategory.EXTERNAL_DEPENDENCY.value, FixStrategy.AUTO_RETRY.value),
        "rate_limit": (ErrorCategory.EXTERNAL_DEPENDENCY.value, FixStrategy.AUTO_RETRY.value),
        "permission_denied": (ErrorCategory.TOOL_FAILURE.value, FixStrategy.PROPOSE.value),
        "not_found": (ErrorCategory.TOOL_FAILURE.value, FixStrategy.PROPOSE.value),

        # 种子相关
        "yaml_parse_error": (ErrorCategory.SEED_CORRUPTION.value, FixStrategy.ROLLBACK.value),
        "missing_gene": (ErrorCategory.SEED_CORRUPTION.value, FixStrategy.PROPOSE.value),
        "founder_missing": (ErrorCategory.SEED_CORRUPTION.value, FixStrategy.ROLLBACK.value),
        "checksum_mismatch": (ErrorCategory.SEED_CORRUPTION.value, FixStrategy.ROLLBACK.value),

        # 上下文相关
        "context_length_exceeded": (ErrorCategory.CONTEXT_OVERFLOW.value, FixStrategy.AUTO_COMPRESS.value),
        "token_limit": (ErrorCategory.CONTEXT_OVERFLOW.value, FixStrategy.AUTO_COMPRESS.value),

        # 状态相关
        "invalid_state_transition": (ErrorCategory.STATE_CONFLICT.value, FixStrategy.PROPOSE.value),
        "stale_state": (ErrorCategory.STATE_CONFLICT.value, FixStrategy.AUTO_RETRY.value),
    }

    @classmethod
    def diagnose(cls, error_type: str, message: str = "",
                 context: str = "") -> dict:
        """诊断错误。
        
        Returns:
            {
                category, strategy, confidence,
                diagnosis, suggested_fix
            }
        """
        error_lower = (error_type + " " + message).lower()

        # 模式匹配
        for pattern, (category, strategy) in cls.ERROR_PATTERNS.items():
            if pattern.replace("_", " ") in error_lower or pattern in error_lower:
                return {
                    "category": category,
                    "strategy": strategy,
                    "confidence": 0.9,
                    "diagnosis": f"匹配已知模式: {pattern}",
                    "suggested_fix": cls._suggest_fix(category, strategy, message),
                }

        # 关键词推断
        if any(w in error_lower for w in ["timeout", "timed out", "超时"]):
            return cls._quick_diagnose(ErrorCategory.TOOL_FAILURE, FixStrategy.AUTO_RETRY,
                                       "疑似超时问题")
        if any(w in error_lower for w in ["permission", "denied", "forbidden", "权限"]):
            return cls._quick_diagnose(ErrorCategory.TOOL_FAILURE, FixStrategy.PROPOSE,
                                       "疑似权限问题")
        if any(w in error_lower for w in ["memory", "overflow", "溢出"]):
            return cls._quick_diagnose(ErrorCategory.CONTEXT_OVERFLOW, FixStrategy.AUTO_COMPRESS,
                                       "疑似内存/上下文溢出")

        # 未知错误
        return {
            "category": ErrorCategory.UNKNOWN.value,
            "strategy": FixStrategy.PROPOSE.value,
            "confidence": 0.3,
            "diagnosis": f"无法匹配已知模式: {error_type}",
            "suggested_fix": "需要人工分析错误详情",
        }

    @classmethod
    def _quick_diagnose(cls, category, strategy, diagnosis) -> dict:
        return {
            "category": category.value,
            "strategy": strategy.value,
            "confidence": 0.7,
            "diagnosis": diagnosis,
            "suggested_fix": cls._suggest_fix(category.value, strategy.value, ""),
        }

    @classmethod
    def _suggest_fix(cls, category: str, strategy: str, message: str) -> str:
        fixes = {
            "auto_retry": "自动重试操作（最多3次，指数退避）",
            "auto_fallback": "尝试替代方案",
            "auto_compress": "压缩上下文，释放空间",
            "propose": "提交进化提案，等待用户批准",
            "rollback": "从最近快照回滚",
        }
        return fixes.get(strategy, "需要人工分析")


# ═══════════════════════════════════════════
#   修复执行器
# ═══════════════════════════════════════════

class FixExecutor:
    """执行修复操作。"""
    
    # 安全边界：这些操作可以自动执行
    AUTO_FIXABLE = {
        FixStrategy.AUTO_RETRY.value,
        FixStrategy.AUTO_FALLBACK.value,
        FixStrategy.AUTO_COMPRESS.value,
    }

    def __init__(self, reflection=None):
        """
        Args:
            reflection: SelfReflection 实例（用于记录修复过程）
        """
        self.reflection = reflection
        self._retry_handlers: Dict[str, Callable] = {}
        self._fallback_handlers: Dict[str, Callable] = {}
        self._retry_history: List[dict] = []  # 重试历史记录

    def register_retry_handler(self, operation: str, handler: Callable):
        """注册重试处理器"""
        self._retry_handlers[operation] = handler

    def register_fallback_handler(self, operation: str, handler: Callable):
        """注册回退处理器"""
        self._fallback_handlers[operation] = handler

    def get_retry_history(self, limit: int = 20) -> List[dict]:
        """获取最近的重试历史记录。"""
        return self._retry_history[-limit:]

    def execute_fix(self, error_record: ErrorRecord, diagnosis: dict) -> FixResult:
        """根据诊断结果执行修复。"""
        strategy = diagnosis.get("strategy", "propose")
        category = diagnosis.get("category", "unknown")

        if strategy in self.AUTO_FIXABLE:
            return self._auto_fix(error_record, strategy)
        else:
            return self._propose_fix(error_record, diagnosis)

    def execute_with_retry(self, operation: str, func: Callable,
                           policy: RetryPolicy = None, **kwargs) -> RetryResult:
        """带重试机制的操作执行器。
        
        执行操作，失败时根据策略自动重试。记录每次重试的历史。
        
        Args:
            operation: 操作名称（用于注册的处理器查找）
            func: 要执行的函数（无参数）
            policy: 重试策略（默认使用 RetryPolicy()）
            **kwargs: 传递给 func 的关键字参数
            
        Returns:
            RetryResult：包含成功状态、返回值、尝试次数和历史记录
        """
        if policy is None:
            policy = RetryPolicy()

        records: List[RetryRecord] = []
        last_error_type = ""
        last_error_message = ""

        for attempt in range(policy.max_retries + 1):
            try:
                value = func(**kwargs)
                # 成功
                result = RetryResult(
                    success=True,
                    final_value=value,
                    attempts=attempt + 1,
                    records=records,
                )
                self._record_retry(operation, attempt, True, 0.0)
                return result

            except Exception as exc:
                last_error_type = type(exc).__name__
                last_error_message = str(exc)

                # 判断是否应继续重试
                if not policy.should_retry(last_error_type, attempt):
                    break

                delay = policy.get_delay(attempt)
                record = RetryRecord(
                    attempt=attempt,
                    error_type=last_error_type,
                    error_message=last_error_message,
                    delay_seconds=delay,
                    success=False,
                )
                records.append(record)
                self._record_retry(operation, attempt, False, delay)

                # 等待退避延迟（如果 delay > 0）
                if delay > 0:
                    time.sleep(delay)

        # 所有重试均失败
        return RetryResult(
            success=False,
            attempts=len(records) + (1 if not records else 0),
            records=records,
            error_message=last_error_message,
        )

    def _record_retry(self, operation: str, attempt: int,
                      success: bool, delay: float):
        """记录重试历史。"""
        entry = {
            "operation": operation,
            "attempt": attempt,
            "success": success,
            "delay_seconds": delay,
            "timestamp": datetime.datetime.now().isoformat(),
        }
        self._retry_history.append(entry)
        # 只保留最近 200 条
        if len(self._retry_history) > 200:
            self._retry_history = self._retry_history[-200:]

    def _auto_fix(self, error: ErrorRecord, strategy: str) -> FixResult:
        """自动修复。"""
        if strategy == FixStrategy.AUTO_RETRY.value:
            # 记录重试意图，实际重试由调用者执行
            return FixResult(
                success=True,
                strategy=strategy,
                message="建议重试操作（指数退避）",
                details={"max_retries": 3, "backoff_base": 2},
            )

        elif strategy == FixStrategy.AUTO_COMPRESS.value:
            return FixResult(
                success=True,
                strategy=strategy,
                message="建议压缩上下文以释放空间",
                details={"action": "compress_episodic", "target": "working"},
            )

        elif strategy == FixStrategy.AUTO_FALLBACK.value:
            return FixResult(
                success=True,
                strategy=strategy,
                message="建议使用替代方案",
                details={"action": "try_fallback_handler"},
            )

        return FixResult(
            success=False,
            strategy=strategy,
            message=f"未知的自动修复策略: {strategy}",
        )

    def _propose_fix(self, error: ErrorRecord, diagnosis: dict) -> FixResult:
        """提交提案（需要用户批准）。"""
        # 通过反思引擎创建提案
        if self.reflection:
            proposal_id = self.reflection.proposals.create(
                title=f"修复: {error.error_type}",
                description=diagnosis.get("suggested_fix", "需要修复"),
                category="reliability",
                priority="high",
                proposed_change=f"诊断: {diagnosis.get('diagnosis', '')}",
            )
            return FixResult(
                success=True,
                strategy=FixStrategy.PROPOSE.value,
                message=f"已提交修复提案: {proposal_id}",
                details={"proposal_id": proposal_id},
            )

        return FixResult(
            success=False,
            strategy=FixStrategy.PROPOSE.value,
            message="无法提交提案（反思引擎未初始化）",
        )


# ═══════════════════════════════════════════
#   自我纠错引擎
# ═══════════════════════════════════════════

class SelfCorrection:
    """Prometheus 的自我纠错引擎。"""

    def __init__(self, reflection=None, state_file: str = None, db_path: str = None):
        """
        Args:
            reflection: SelfReflection 实例（用于记录修复过程）
            state_file: 保留兼容
            db_path: SQLite 数据库路径
        """
        if db_path is None and state_file is not None:
            db_path = state_file.rsplit('.', 1)[0] + '.db'
        self._store = StateStore(db_path=db_path, namespace='correction')
        self.diagnoser = ErrorDiagnoser()
        self.executor = FixExecutor(reflection=reflection)
        self.reflection = reflection
        self.errors: List[ErrorRecord] = []
        self._migrate_json_if_needed(state_file)
        self._load_state()

    def with_retry(self, operation: str, func: Callable,
                   policy: RetryPolicy = None, **kwargs) -> Any:
        """带重试的操作执行器。
        
        自动重试失败操作，记录每次重试，最终失败则进入纠错流程。
        
        Args:
            operation: 操作名称（如 "web_search", "read_file"）
            func: 要执行的函数（无参数调用）
            policy: 重试策略（默认 RetryPolicy()）
            **kwargs: 传递给 func 的关键字参数
            
        Returns:
            func 的返回值
            
        Raises:
            最终失败时抛出原始异常（或 RuntimeError 包装）
        """
        if policy is None:
            policy = RetryPolicy()

        retry_result = self.executor.execute_with_retry(
            operation=operation,
            func=func,
            policy=policy,
            **kwargs,
        )

        if retry_result.success:
            return retry_result.final_value

        # 最终失败——记录到纠错流程
        self.handle_error(
            error_type=f"{operation}_retry_exhausted",
            message=f"操作 '{operation}' 重试 {retry_result.attempts} 次后失败: {retry_result.error_message}",
            context=f"retry:attempt={retry_result.attempts}",
        )
        raise RuntimeError(
            f"操作 '{operation}' 重试 {retry_result.attempts} 次后失败: {retry_result.error_message}"
        )

    def get_degradation_mode(self) -> DegradationMode:
        """根据最近的错误率，建议当前应使用的降级模式。
        
        评估最近 5 次操作的成功率来决定运行模式：
        - 成功率 > 80%: NORMAL（正常模式）
        - 60%-80%: RETRY（增强重试）
        - 40%-60%: FALLBACK（降级到备用方案）
        - ≤ 40%: MINIMAL（最小化运行）
        
        Returns:
            建议的降级模式
        """
        # 取最近 5 条错误记录评估
        recent = self.errors[-5:]
        if not recent:
            return DegradationMode.NORMAL

        total = len(recent)
        resolved = sum(1 for e in recent if e.resolved)
        success_rate = resolved / total if total > 0 else 1.0

        if success_rate > 0.8:
            return DegradationMode.NORMAL
        elif success_rate > 0.6:
            return DegradationMode.RETRY
        elif success_rate > 0.4:
            return DegradationMode.FALLBACK
        else:
            return DegradationMode.MINIMAL

    def handle_error(self, error_type: str, message: str = "",
                     context: str = "", exception: Exception = None) -> FixResult:
        """处理一个错误——从诊断到修复的完整流程。
        
        Args:
            error_type: 错误类型标识
            message: 错误信息
            context: 发生上下文
            exception: 原始异常（可选）
            
        Returns:
            FixResult
        """
        # 1. 构建错误记录
        stacktrace = ""
        if exception:
            stacktrace = traceback.format_exc()

        error = ErrorRecord(
            error_type=error_type,
            category="",  # 诊断后填充
            message=message,
            context=context,
            stacktrace=stacktrace,
        )

        # 2. 诊断
        diagnosis = self.diagnoser.diagnose(error_type, message, context)
        error.category = diagnosis["category"]

        # 3. 执行修复
        fix_result = self.executor.execute_fix(error, diagnosis)

        # 4. 记录结果
        error.resolved = fix_result.success
        error.fix_applied = fix_result.message
        error.fix_strategy = fix_result.strategy
        self.errors.append(error)
        self._save_state()

        # 5. 通知反思引擎
        if self.reflection:
            self.reflection.observe_error(
                error_type=error_type,
                detail=f"{message} → {fix_result.message}",
            )

        return fix_result

    def handle_tool_failure(self, tool: str, error: str,
                            context: str = "") -> FixResult:
        """处理工具调用失败。"""
        return self.handle_error(
            error_type=f"tool_{tool}",
            message=error,
            context=context,
        )

    def handle_seed_error(self, op: str, seed_path: str,
                          error: str) -> FixResult:
        """处理种子操作错误。"""
        return self.handle_error(
            error_type=f"seed_{op}",
            message=error,
            context=f"seed:{seed_path}",
        )

    def handle_context_overflow(self, current_usage: int,
                                budget: int) -> FixResult:
        """处理上下文溢出。"""
        overflow_pct = round((current_usage / budget - 1) * 100, 1) if budget > 0 else 0
        return self.handle_error(
            error_type="context_overflow",
            message=f"上下文溢出 {overflow_pct}% ({current_usage}/{budget}tok)",
            context="context_manager",
        )

    def error_stats(self) -> dict:
        """错误统计。"""
        total = len(self.errors)
        if total == 0:
            return {"total": 0}

        by_category = {}
        by_strategy = {}
        resolved = 0

        for e in self.errors:
            by_category[e.category] = by_category.get(e.category, 0) + 1
            by_strategy[e.fix_strategy] = by_strategy.get(e.fix_strategy, 0) + 1
            if e.resolved:
                resolved += 1

        return {
            "total": total,
            "resolved": resolved,
            "resolution_rate": round(resolved / total * 100, 1),
            "by_category": by_category,
            "by_strategy": by_strategy,
        }

    def recent_errors(self, limit: int = 10) -> List[dict]:
        """最近的错误记录。"""
        return [e.to_dict() for e in self.errors[-limit:]]

    def _save_state(self):
        self._store.set('errors', [e.to_dict() for e in self.errors[-200:]])
    def _load_state(self):
        self.errors = []
        data = self._store.get('errors', [])
        for e in data:
            self.errors.append(ErrorRecord(**e))

    def _migrate_json_if_needed(self, json_path: str = None):
        """如果旧 JSON 文件存在，迁移到 SQLite。"""
        json_path = json_path or os.path.join(CORRECTION_DIR, "correction_state.json")
        if not os.path.exists(json_path):
            return
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                state = json.load(f)
            error_list = state.get("errors", [])
            if error_list and not self._store.get('errors'):
                self._store.set('errors', error_list)
            os.rename(json_path, json_path + ".migrated")
        except (json.JSONDecodeError, KeyError, TypeError, OSError):
            pass


# ═══════════════════════════════════════════
#   CLI 入口
# ═══════════════════════════════════════════

def main():
    import sys

    if len(sys.argv) < 2:
        print("""
🔧 普罗米修斯 · 自我纠错引擎

用法:
  self_correction.py handle <错误类型> <消息> [--context 上下文]
  self_correction.py diagnose <错误类型> <消息>
  self_correction.py stats
  self_correction.py recent [--limit 10]
""")
        return

    # 集成反思引擎
    try:
        from .reflection import SelfReflection
        reflection = SelfReflection()
    except ImportError:
        reflection = None

    sc = SelfCorrection(reflection=reflection)
    action = sys.argv[1]

    if action == 'handle' and len(sys.argv) > 3:
        error_type = sys.argv[2]
        message = sys.argv[3]
        context = ""
        if '--context' in sys.argv:
            idx = sys.argv.index('--context')
            if idx + 1 < len(sys.argv):
                context = sys.argv[idx + 1]

        result = sc.handle_error(error_type, message, context)
        print(f"{'✅ 已修复' if result.success else '❌ 未修复'}: {result.message}")
        print(f"   策略: {result.strategy}")

    elif action == 'diagnose' and len(sys.argv) > 3:
        error_type = sys.argv[2]
        message = sys.argv[3]
        diagnosis = ErrorDiagnoser.diagnose(error_type, message)
        print(f"\n🔍 诊断结果:")
        print(f"   分类: {diagnosis['category']}")
        print(f"   策略: {diagnosis['strategy']}")
        print(f"   置信度: {diagnosis['confidence']}")
        print(f"   诊断: {diagnosis['diagnosis']}")
        print(f"   建议: {diagnosis['suggested_fix']}")

    elif action == 'stats':
        stats = sc.error_stats()
        print("\n📊 错误统计:")
        for k, v in stats.items():
            print(f"  {k}: {v}")

    elif action == 'recent':
        limit = 10
        if '--limit' in sys.argv:
            idx = sys.argv.index('--limit')
            if idx + 1 < len(sys.argv):
                limit = int(sys.argv[idx + 1])

        errors = sc.recent_errors(limit)
        if not errors:
            print("📋 无错误记录")
        else:
            print(f"\n📋 最近 {len(errors)} 条错误:")
            for e in errors:
                status = "✅" if e["resolved"] else "❌"
                print(f"  {status} [{e['category']}] {e['error_type']}: {e['message'][:60]}")
                print(f"     策略: {e['fix_strategy']} | {e['timestamp'][:19]}")

    else:
        print(f"未知命令: {action}")


if __name__ == "__main__":
    main()
