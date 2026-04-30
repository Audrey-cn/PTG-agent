#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════╗
║   🪞 普罗米修斯 · 自我反思 · SelfReflection                ║
║                                                              ║
║   Prometheus 作为独立 Agent 的反思引擎。                     ║
║   被动收集运行数据，主动分析模式，生成改进提案。             ║
║                                                              ║
║   设计原则：                                                 ║
║     1. 控制权放用户 — 所有进化修改需要用户批准               ║
║     2. 阈值触发    — 提案累积到一定数量才触发报告            ║
║     3. 每天一次    — 日常复盘机制，不频繁打扰                ║
║     4. 容错优先    — 先尝试修复，失败再回滚                  ║
║                                                              ║
║   三层反思：                                                 ║
║     观察层 — 收集事件（工具调用、错误、预算变化）            ║
║     分析层 — 识别模式（重复失败、效率瓶颈、矛盾）            ║
║     提案层 — 生成改进方案（具体、可执行、有优先级）          ║
╚══════════════════════════════════════════════════════════════╝
"""

import os
import json
import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from enum import Enum
from storage import StorageEngine, StateStore


# ═══════════════════════════════════════════
#   配置
# ═══════════════════════════════════════════

REFLECTION_DIR = os.path.expanduser("~/.hermes/tools/prometheus/reflection")
os.makedirs(REFLECTION_DIR, exist_ok=True)

# 进化提案触发阈值
# 默认阈值（可通过 config 或构造函数参数覆盖）
PROPOSAL_THRESHOLD = 5

# 观察日志保留天数
OBSERVATION_RETENTION_DAYS = 30


class EventType(Enum):
    """事件类型"""
    TOOL_CALL = "tool_call"           # 工具调用
    SEED_OP = "seed_op"               # 种子操作
    CONTEXT_OP = "context_op"         # 上下文操作
    ERROR = "error"                   # 错误
    MEMORY_OP = "memory_op"           # 记忆操作
    PROMPT_OP = "prompt_op"           # 提示词操作
    SYSTEM = "system"                 # 系统事件
    STATE_CHANGE = "state_change"     # 状态机转换


class Severity(Enum):
    """严重程度"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ProposalPriority(Enum):
    """提案优先级"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class Observation:
    """观察记录——单次事件"""
    event_type: str              # 事件类型
    action: str                  # 具体操作
    result: str = "success"      # success / failure / timeout
    detail: str = ""             # 详情
    severity: str = "info"       # 严重程度
    timestamp: str = ""          # 时间戳
    duration_ms: int = 0         # 耗时（毫秒）
    metadata: dict = field(default_factory=dict)  # 额外数据

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.datetime.now().isoformat()

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class EvolutionProposal:
    """进化提案——改进方案"""
    title: str                   # 标题
    description: str             # 详细描述
    category: str                # 类别（efficiency / reliability / capability / cleanup）
    priority: str = "medium"     # 优先级
    status: str = "pending"      # pending / approved / rejected / executed
    created_at: str = ""
    resolved_at: str = ""
    observations: List[str] = field(default_factory=list)  # 关联的观察 ID
    proposed_change: str = ""    # 建议的具体修改
    user_feedback: str = ""      # 用户反馈

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.datetime.now().isoformat()

    def to_dict(self) -> dict:
        return asdict(self)


# ═══════════════════════════════════════════
#   观察收集器
# ═══════════════════════════════════════════

class ObservationCollector:
    """被动收集运行事件。"""
    def __init__(self, state_file: str = None, db_path: str = None):
        """state_file 参数保留兼容，实际使用 SQLite 存储。

        Args:
            state_file: 保留兼容，不再使用
            db_path: SQLite 数据库路径，None 则使用默认 prometheus.db
        """
        self._engine = StorageEngine(db_path=db_path, table_name='observations')
        self.observations: List[Observation] = []
        self._next_id = 1
        self._migrate_json_if_needed(state_file)
        self._load_state()
    def record(self, event_type: str, action: str, result: str = "success",
               detail: str = "", severity: str = "info", duration_ms: int = 0,
               metadata: dict = None) -> str:
        """记录一次事件。
        Returns:
            observation_id
        """
        meta = dict(metadata or {})
        meta.update({
            "action": action,
            "result": result,
            "detail": detail,
            "severity": severity,
            "duration_ms": duration_ms,
        })
        row_id = self._engine.add(
            content=f"{action}: {result}",
            category=event_type,
            tags=[result],
            metadata=meta,
        )
        # 内存缓存也更新
        obs = Observation(
            event_type=event_type, action=action, result=result,
            detail=detail, severity=severity, duration_ms=duration_ms,
            metadata=metadata or {},
        )
        self.observations.append(obs)
        self._cleanup()
        self._next_id = len(self.observations) + 1
        return f"obs_{row_id}"

    def query(self, event_type: str = None, result: str = None,
              since: str = None, severity: str = None,
              limit: int = 100) -> List[dict]:
        """查询观察记录。"""
        filtered = self.observations

        if event_type:
            filtered = [o for o in filtered if o.event_type == event_type]
        if result:
            filtered = [o for o in filtered if o.result == result]
        if severity:
            filtered = [o for o in filtered if o.severity == severity]
        if since:
            filtered = [o for o in filtered if o.timestamp >= since]

        return [o.to_dict() for o in filtered[-limit:]]

    def stats(self) -> dict:
        """统计概览。"""
        total = len(self.observations)
        if total == 0:
            return {"total": 0}

        by_type = {}
        by_result = {"success": 0, "failure": 0, "timeout": 0}
        by_severity = {}
        total_duration = 0

        for obs in self.observations:
            by_type[obs.event_type] = by_type.get(obs.event_type, 0) + 1
            by_result[obs.result] = by_result.get(obs.result, 0) + 1
            by_severity[obs.severity] = by_severity.get(obs.severity, 0) + 1
            total_duration += obs.duration_ms

        failure_rate = by_result.get("failure", 0) / total * 100 if total > 0 else 0

        return {
            "total": total,
            "by_type": by_type,
            "by_result": by_result,
            "by_severity": by_severity,
            "failure_rate": round(failure_rate, 1),
            "avg_duration_ms": round(total_duration / total, 1) if total > 0 else 0,
        }

    def _cleanup(self):
        """清理过期记录"""
        cutoff = (datetime.datetime.now() - datetime.timedelta(days=OBSERVATION_RETENTION_DAYS)).isoformat()
        self.observations = [o for o in self.observations if o.timestamp >= cutoff]

    def _save_state(self):
        pass  # 每次 record() 已直接写入 SQLite
    def _load_state(self):
        self.observations = []
        records = self._engine.list_all(limit=500)
        for r in records:
            meta = r.get('metadata', {})
            self.observations.append(Observation(
                event_type=r.get('category', 'unknown'),
                action=meta.get('action', ''),
                result=meta.get('result', ''),
                detail=meta.get('detail', ''),
                severity=meta.get('severity', 'info'),
                timestamp=r.get('created_at', ''),
                duration_ms=meta.get('duration_ms', 0),
                metadata={k: v for k, v in meta.items()
                          if k not in ('action', 'result', 'detail', 'severity', 'duration_ms')},
            ))
        self._next_id = len(self.observations) + 1

    def _migrate_json_if_needed(self, json_path: str = None):
        """如果旧 JSON 文件存在，迁移到 SQLite。"""
        json_path = json_path or os.path.join(REFLECTION_DIR, "observations.json")
        if not os.path.exists(json_path):
            return
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                state = json.load(f)
            obs_list = state.get("observations", [])
            if obs_list and self._engine.count() == 0:
                for o in obs_list:
                    meta = dict(o.get("metadata", {}))
                    meta.update({
                        "action": o.get("action", ""),
                        "result": o.get("result", ""),
                        "detail": o.get("detail", ""),
                        "severity": o.get("severity", "info"),
                        "duration_ms": o.get("duration_ms", 0),
                    })
                    self._engine.add(
                        content=f"{o.get('action', '')}: {o.get('result', '')}",
                        category=o.get("event_type", "unknown"),
                        tags=[o.get("result", "")],
                        metadata=meta,
                    )
            # 迁移完成后重命名旧文件
            os.rename(json_path, json_path + ".migrated")
        except (json.JSONDecodeError, KeyError, TypeError, OSError):
            pass


# ═══════════════════════════════════════════
#   模式分析器
# ═══════════════════════════════════════════

class PatternAnalyzer:
    """从观察记录中识别模式和问题。"""

    def __init__(self, collector: ObservationCollector):
        self.collector = collector

    def analyze_all(self) -> dict:
        """运行全部分析，返回发现的问题列表。"""
        issues = []
        issues.extend(self._detect_repeated_failures())
        issues.extend(self._detect_performance_degradation())
        issues.extend(self._detect_error_clusters())
        issues.extend(self._detect_unused_operations())

        return {
            "issues": issues,
            "total_issues": len(issues),
            "analyzed_at": datetime.datetime.now().isoformat(),
        }

    def _detect_repeated_failures(self) -> List[dict]:
        """检测重复失败——同一操作连续失败多次"""
        failures = self.collector.query(result="failure")
        action_failures = {}
        for obs in failures:
            action = obs["action"]
            action_failures[action] = action_failures.get(action, 0) + 1

        issues = []
        for action, count in action_failures.items():
            if count >= 3:
                issues.append({
                    "type": "repeated_failure",
                    "title": f"操作 '{action}' 失败 {count} 次",
                    "severity": "high" if count >= 5 else "medium",
                    "suggestion": f"检查 '{action}' 的输入参数和环境状态，或考虑替代方案",
                    "action": action,
                    "failure_count": count,
                })

        return issues

    def _detect_performance_degradation(self) -> List[dict]:
        """检测性能退化——操作耗时异常增长"""
        all_obs = self.collector.query()
        if len(all_obs) < 10:
            return []

        # 按操作分组，比较最近和历史的平均耗时
        action_durations = {}
        for obs in all_obs:
            if obs["duration_ms"] > 0:
                action = obs["action"]
                if action not in action_durations:
                    action_durations[action] = []
                action_durations[action].append({
                    "duration": obs["duration_ms"],
                    "time": obs["timestamp"],
                })

        issues = []
        for action, records in action_durations.items():
            if len(records) < 5:
                continue

            # 按时间排序，分成前半和后半
            records.sort(key=lambda r: r["time"])
            mid = len(records) // 2
            first_half = [r["duration"] for r in records[:mid]]
            second_half = [r["duration"] for r in records[mid:]]

            avg_first = sum(first_half) / len(first_half)
            avg_second = sum(second_half) / len(second_half)

            # 如果后半段耗时增长超过 50%
            if avg_first > 0 and avg_second > avg_first * 1.5:
                degradation = round((avg_second / avg_first - 1) * 100, 1)
                issues.append({
                    "type": "performance_degradation",
                    "title": f"操作 '{action}' 耗时增长 {degradation}%",
                    "severity": "medium",
                    "suggestion": f"检查资源使用情况，或优化 '{action}' 的执行路径",
                    "action": action,
                    "avg_early_ms": round(avg_first),
                    "avg_late_ms": round(avg_second),
                })

        return issues

    def _detect_error_clusters(self) -> List[dict]:
        """检测错误集群——短时间内大量错误"""
        errors = self.collector.query(result="failure", severity="error")
        if len(errors) < 3:
            return []

        # 按小时分桶
        hourly_buckets = {}
        for obs in errors:
            hour = obs["timestamp"][:13]  # YYYY-MM-DDTHH
            hourly_buckets[hour] = hourly_buckets.get(hour, 0) + 1

        issues = []
        for hour, count in hourly_buckets.items():
            if count >= 5:
                issues.append({
                    "type": "error_cluster",
                    "title": f"{hour} 时段发生 {count} 个错误",
                    "severity": "high",
                    "suggestion": "检查该时段的系统状态、网络连接或外部依赖",
                    "hour": hour,
                    "error_count": count,
                })

        return issues

    def _detect_unused_operations(self) -> List[dict]:
        """检测未使用的操作——注册但从未被调用的能力"""
        all_ops = set()
        used_ops = set()

        for obs in self.collector.query():
            all_ops.add(obs["action"])
            if obs["result"] == "success":
                used_ops.add(obs["action"])

        # 这里只检测在观察记录中从未出现的成功调用
        # 实际使用中可以对比工具注册表
        return []


# ═══════════════════════════════════════════
#   提案管理器
# ═══════════════════════════════════════════

class ProposalManager:
    """管理进化提案的生命周期。"""
    def __init__(self, state_file: str = None, db_path: str = None,
                 threshold: int = 5, cooldown_seconds: int = 3600):
        """state_file 参数保留兼容，实际使用 SQLite 存储。

        Args:
            state_file: 保留兼容
            db_path: SQLite 数据库路径
            threshold: 提案累积阈值
            cooldown_seconds: 触发后的冷却期（秒）
        """
        if db_path is None and state_file is not None:
            db_path = state_file.rsplit('.', 1)[0] + '.db'
        self._store = StateStore(db_path=db_path, namespace='proposals')
        self._threshold = threshold
        self._cooldown_seconds = cooldown_seconds
        self._last_report_time = self._store.get('_last_report_time', None)
        self.proposals: List[EvolutionProposal] = []
        self._migrate_json_if_needed(state_file)
        self._load_state()

    def create(self, title: str, description: str, category: str,
               priority: str = "medium", observations: List[str] = None,
               proposed_change: str = "") -> str:
        """创建进化提案。"""
        proposal = EvolutionProposal(
            title=title,
            description=description,
            category=category,
            priority=priority,
            observations=observations or [],
            proposed_change=proposed_change,
        )
        proposal_id = f"prop_{len(self.proposals) + 1}"
        self.proposals.append(proposal)
        self._save_state()
        return proposal_id

    def approve(self, index: int, feedback: str = "") -> dict:
        """批准提案（由用户操作）。"""
        if index < 0 or index >= len(self.proposals):
            return {"error": f"无效的提案索引: {index}"}

        self.proposals[index].status = "approved"
        self.proposals[index].resolved_at = datetime.datetime.now().isoformat()
        self.proposals[index].user_feedback = feedback
        self._save_state()
        return {"approved": True, "title": self.proposals[index].title}

    def reject(self, index: int, feedback: str = "") -> dict:
        """拒绝提案（由用户操作）。"""
        if index < 0 or index >= len(self.proposals):
            return {"error": f"无效的提案索引: {index}"}

        self.proposals[index].status = "rejected"
        self.proposals[index].resolved_at = datetime.datetime.now().isoformat()
        self.proposals[index].user_feedback = feedback
        self._save_state()
        return {"rejected": True, "title": self.proposals[index].title}

    def mark_executed(self, index: int) -> dict:
        """标记提案已执行。"""
        if index < 0 or index >= len(self.proposals):
            return {"error": f"无效的提案索引: {index}"}

        self.proposals[index].status = "executed"
        self.proposals[index].resolved_at = datetime.datetime.now().isoformat()
        self._save_state()
        return {"executed": True, "title": self.proposals[index].title}

    def pending_count(self) -> int:
        """待处理提案数量。"""
        return len([p for p in self.proposals if p.status == "pending"])

    def should_report(self) -> bool:
        """是否应该触发报告。
        
        触发条件（满足任一）：
        1. 累积提案数 >= 阈值
        2. 有 critical 优先级的提案（即时触发）
        3. 超过冷却期且有新提案
        
        冷却期内不重复触发。
        """
        pending = [p for p in self.proposals if p.status == "pending"]
        
        # 即时触发：有 critical 提案
        for p in pending:
            if hasattr(p, 'priority') and p.priority == "critical":
                return True
        
        # 冷却期检查
        if self._last_report_time:
            import datetime
            try:
                last = datetime.datetime.fromisoformat(self._last_report_time)
                elapsed = (datetime.datetime.now() - last).total_seconds()
                if elapsed < self._cooldown_seconds:
                    return False  # 冷却期内不触发
            except (ValueError, TypeError):
                pass
        
        # 阈值触发
        return len(pending) >= self._threshold

    def mark_reported(self):
        """标记报告已触发（重置冷却期）"""
        import datetime
        self._last_report_time = datetime.datetime.now().isoformat()
        self._store.set('_last_report_time', self._last_report_time)

    def set_threshold(self, threshold: int):
        """动态调整阈值"""
        self._threshold = threshold

    def set_cooldown(self, seconds: int):
        """动态调整冷却期"""
        self._cooldown_seconds = seconds

    def control_status(self) -> dict:
        """返回控制状态概览"""
        return {
            "pending": self.pending_count(),
            "threshold": self._threshold,
            "cooldown_seconds": self._cooldown_seconds,
            "last_report_time": self._last_report_time,
            "in_cooldown": self._in_cooldown(),
            "should_report": self.should_report(),
        }

    def _in_cooldown(self) -> bool:
        """检查是否在冷却期内"""
        if not self._last_report_time:
            return False
        import datetime
        try:
            last = datetime.datetime.fromisoformat(self._last_report_time)
            elapsed = (datetime.datetime.now() - last).total_seconds()
            return elapsed < self._cooldown_seconds
        except (ValueError, TypeError):
            return False

    def get_pending(self) -> List[dict]:
        """获取所有待处理提案。"""
        return [p.to_dict() for p in self.proposals if p.status == "pending"]

    def get_all(self, status: str = None) -> List[dict]:
        """获取所有提案，可按状态过滤。"""
        if status:
            return [p.to_dict() for p in self.proposals if p.status == status]
        return [p.to_dict() for p in self.proposals]

    def generate_report(self) -> str:
        """生成提案审查报告（人类可读）。"""
        pending = [p for p in self.proposals if p.status == "pending"]
        if not pending:
            return "📋 无待处理的进化提案。"

        lines = [
            "╔══════════════════════════════════════════════════════════════╗",
            "║   📋 进化提案审查报告                                      ║",
            "╠══════════════════════════════════════════════════════════════╣",
            f"║   待处理提案: {len(pending)} 个",
            "╠══════════════════════════════════════════════════════════════╣",
        ]

        for i, p in enumerate(pending):
            priority_icon = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}.get(p.priority, "⚪")
            lines.append(f"║")
            lines.append(f"║   #{i} {priority_icon} [{p.category}] {p.title}")
            lines.append(f"║      {p.description}")
            if p.proposed_change:
                lines.append(f"║      建议: {p.proposed_change}")
            lines.append(f"║      创建: {p.created_at[:19]}")

        lines.extend([
            "║",
            "╠══════════════════════════════════════════════════════════════╣",
            "║   操作: approve #编号 / reject #编号                       ║",
            "╚══════════════════════════════════════════════════════════════╝",
        ])

        return "\n".join(lines)

    def _save_state(self):
        self._store.set('proposals', [p.to_dict() for p in self.proposals])
    def _load_state(self):
        self.proposals = []
        data = self._store.get('proposals', [])
        for p in data:
            self.proposals.append(EvolutionProposal(**p))

    def _migrate_json_if_needed(self, json_path: str = None):
        """如果旧 JSON 文件存在，迁移到 SQLite。"""
        json_path = json_path or os.path.join(REFLECTION_DIR, "proposals.json")
        if not os.path.exists(json_path):
            return
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                state = json.load(f)
            prop_list = state.get("proposals", [])
            if prop_list and not self._store.get('proposals'):
                self._store.set('proposals', prop_list)
            os.rename(json_path, json_path + ".migrated")
        except (json.JSONDecodeError, KeyError, TypeError, OSError):
            pass


# ═══════════════════════════════════════════
#   自我反思引擎
# ═══════════════════════════════════════════

class SelfReflection:
    """Prometheus 的自我反思引擎。
    
    整合观察收集、模式分析和提案管理。
    提供完整的反思→改进流程。
    
    联动机制：
        - observe_state_change() 接收状态机转换通知
        - get_state_health() 分析状态机健康度
    """

    def __init__(self, db_path: str = None):
        """初始化自我反思引擎。

        Args:
            db_path: SQLite 数据库路径，None 则使用默认 prometheus.db
        """
        self.collector = ObservationCollector(db_path=db_path)
        self.analyzer = PatternAnalyzer(self.collector)
        self.proposals = ProposalManager(db_path=db_path)

    # ── 观察记录（便捷方法）──

    def observe_tool_call(self, tool: str, success: bool, duration_ms: int = 0,
                          detail: str = "") -> str:
        """记录工具调用"""
        return self.collector.record(
            event_type=EventType.TOOL_CALL.value,
            action=tool,
            result="success" if success else "failure",
            detail=detail,
            duration_ms=duration_ms,
        )

    def observe_seed_op(self, op: str, seed: str, success: bool,
                        detail: str = "") -> str:
        """记录种子操作"""
        return self.collector.record(
            event_type=EventType.SEED_OP.value,
            action=op,
            result="success" if success else "failure",
            detail=detail,
            metadata={"seed": seed},
        )

    def observe_error(self, error_type: str, detail: str = "") -> str:
        """记录错误"""
        return self.collector.record(
            event_type=EventType.ERROR.value,
            action=error_type,
            result="failure",
            severity=Severity.ERROR.value,
            detail=detail,
        )

    # ── 反思分析 ──

    def reflect(self) -> dict:
        """执行一次完整反思。
        
        Returns:
            {
                stats: {...},
                analysis: {issues: [...]},
                should_report: bool,
                report: str (如果需要报告)
            }
        """
        stats = self.collector.stats()
        analysis = self.analyzer.analyze_all()

        # 将发现的问题转化为提案
        for issue in analysis.get("issues", []):
            self._issue_to_proposal(issue)

        should_report = self.proposals.should_report()
        report = self.proposals.generate_report() if should_report else ""

        # 标记已触发（重置冷却期）
        if should_report:
            self.proposals.mark_reported()

        return {
            "stats": stats,
            "analysis": analysis,
            "pending_proposals": self.proposals.pending_count(),
            "should_report": should_report,
            "report": report,
        }

    def daily_review(self) -> str:
        """每日复盘报告。"""
        stats = self.collector.stats()
        analysis = self.analyzer.analyze_all()

        # 生成提案
        for issue in analysis.get("issues", []):
            self._issue_to_proposal(issue)

        lines = [
            "╔══════════════════════════════════════════════════════════════╗",
            "║   🪞 每日反思报告                                          ║",
            f"║   {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "╠══════════════════════════════════════════════════════════════╣",
            "║                                                              ║",
            f"║   📊 运行统计:                                              ║",
            f"║      总事件: {stats.get('total', 0)}",
            f"║      失败率: {stats.get('failure_rate', 0)}%",
            f"║      平均耗时: {stats.get('avg_duration_ms', 0)}ms",
            "║                                                              ║",
        ]

        # 按类型列出
        by_type = stats.get("by_type", {})
        if by_type:
            lines.append("║   📂 事件分布:")
            for etype, count in sorted(by_type.items(), key=lambda x: -x[1]):
                lines.append(f"║      {etype}: {count}")
            lines.append("║")

        # 发现的问题
        issues = analysis.get("issues", [])
        if issues:
            lines.append(f"║   ⚠️  发现 {len(issues)} 个问题:")
            for issue in issues[:5]:
                lines.append(f"║      · [{issue.get('severity', '?')}] {issue.get('title', '?')}")
                lines.append(f"║        {issue.get('suggestion', '')}")
        else:
            lines.append("║   ✅ 未发现明显问题")

        # 进化提案
        pending = self.proposals.pending_count()
        if pending > 0:
            lines.append(f"║")
            lines.append(f"║   💡 待处理进化提案: {pending} 个")
            if self.proposals.should_report():
                lines.append(f"║      ⚡ 已达到阈值，建议审查")

        lines.extend([
            "║                                                              ║",
            "╚══════════════════════════════════════════════════════════════╝",
        ])

        return "\n".join(lines)

    def _issue_to_proposal(self, issue: dict):
        """将分析发现的问题转化为进化提案"""
        # 去重：检查是否已有相同标题的 pending 提案
        existing_titles = {p.title for p in self.proposals.proposals if p.status == "pending"}
        if issue.get("title") in existing_titles:
            return

        category_map = {
            "repeated_failure": "reliability",
            "performance_degradation": "efficiency",
            "error_cluster": "reliability",
            "unused_operations": "cleanup",
        }

        self.proposals.create(
            title=issue.get("title", "未知问题"),
            description=issue.get("suggestion", ""),
            category=category_map.get(issue.get("type", ""), "general"),
            priority=issue.get("severity", "medium"),
        )

    # ── 快捷方法 ──
    # ── 状态观察（联动接口）──

    def observe_state_change(self, from_state: str, to_state: str, reason: str = ""):
        """观察状态机转换，作为反思的输入信号。
        
        由状态机的钩子系统自动调用，也可手动调用。
        将每次状态转换记录为一条观察，供模式分析使用。
        
        Args:
            from_state: 转换前的状态名
            to_state: 转换后的状态名
            reason: 转换原因
        """
        severity = "info"
        if to_state == "error":
            severity = Severity.ERROR.value
        elif from_state == "error":
            severity = Severity.WARNING.value

        self.collector.record(
            event_type=EventType.STATE_CHANGE.value,
            action=f"{from_state} → {to_state}",
            result="transition",
            severity=severity,
            detail=reason,
            metadata={
                "from_state": from_state,
                "to_state": to_state,
                "reason": reason,
            },
        )

    def get_state_health(self) -> dict:
        """分析状态机健康度。
        
        通过分析状态转换历史，评估：
        - 各状态停留时间分布
        - 是否频繁进入 ERROR
        - 是否在 REFLECTING 停留过久
        - 是否存在状态抖动
        
        Returns:
            {
                is_healthy: bool,
                issues: list of str,
                state_time_distribution: dict,
                error_frequency: float,
                stuck_in_reflecting: bool,
            }
        """
        # 从观察记录中提取状态转换数据
        state_changes = self.collector.query(event_type="state_change")
        transitions = []
        for obs in state_changes:
            meta = obs.get("metadata", {})
            transitions.append({
                "from_state": meta.get("from_state", ""),
                "to_state": meta.get("to_state", ""),
                "duration_ms": obs.get("duration_ms", 0),
            })

        current = state_changes[-1].get("metadata", {}).get("to_state", "") if state_changes else ""
        entered_at = state_changes[-1].get("timestamp", "") if state_changes else ""

        return _analyze_state_health(transitions, current, entered_at)


    # ── 快捷方法 ──

    def stats(self) -> dict:
        return self.collector.stats()

    def pending_proposals(self) -> List[dict]:
        return self.proposals.get_pending()

    def approve_proposal(self, index: int, feedback: str = "") -> dict:
        return self.proposals.approve(index, feedback)

    def reject_proposal(self, index: int, feedback: str = "") -> dict:
        return self.proposals.reject(index, feedback)


def _analyze_state_health(transitions: list, current_state: str,
                          entered_at: str = None) -> dict:
    """分析状态机健康度（独立函数，无状态）。
    
    Args:
        transitions: 状态转换记录列表
        current_state: 当前状态名
        entered_at: 进入当前状态的时间 ISO 字符串
    
    Returns:
        {
            is_healthy: bool,
            issues: list of str,
            state_time_distribution: dict,
            error_frequency: float,
            stuck_in_reflecting: bool,
        }
    """
    issues = []

    # 1. 各状态停留时间分布
    state_time_distribution: Dict[str, int] = {}
    for t in transitions:
        st = t.get("from_state", "")
        dur = t.get("duration_ms", 0)
        state_time_distribution[st] = state_time_distribution.get(st, 0) + dur

    # 2. 错误频率
    total = len(transitions)
    error_count = sum(1 for t in transitions if t.get("to_state") == "error")
    error_frequency = error_count / total if total > 0 else 0.0

    if error_frequency > 0.3:
        issues.append(f"错误频率过高: {error_frequency:.1%} ({error_count}/{total})")

    # 3. 是否在 REFLECTING 停留过久
    stuck_in_reflecting = False
    if current_state == "reflecting" and entered_at:
        import datetime as _dt
        try:
            entered = _dt.datetime.fromisoformat(entered_at)
            duration_ms = int((_dt.datetime.now() - entered).total_seconds() * 1000)
            # 反思状态合理停留时间上限：60 秒
            reflecting_limit_ms = 60_000
            if duration_ms > reflecting_limit_ms:
                stuck_in_reflecting = True
                issues.append(
                    f"在 REFLECTING 状态停留过久: {duration_ms}ms "
                    f"(上限 {reflecting_limit_ms}ms)"
                )
        except (ValueError, TypeError):
            pass

    # 4. 检测频繁切换（抖动）
    if total >= 6:
        recent = transitions[-6:]
        states_seq = [t.get("to_state") for t in recent]
        from collections import Counter
        counts = Counter(states_seq)
        most_common_state, most_common_count = counts.most_common(1)[0]
        if most_common_count >= 3:
            issues.append(
                f"状态抖动: 最近 {len(recent)} 次转换中 "
                f"{most_common_state} 出现 {most_common_count} 次"
            )

    return {
        "is_healthy": len(issues) == 0,
        "issues": issues,
        "state_time_distribution": state_time_distribution,
        "error_frequency": round(error_frequency, 4),
        "stuck_in_reflecting": stuck_in_reflecting,
    }


# ═══════════════════════════════════════════
#   CLI 入口
# ═══════════════════════════════════════════

def main():
    import sys

    if len(sys.argv) < 2:
        print("""
🪞 普罗米修斯 · 自我反思引擎

用法:
  reflection.py observe <类型> <操作> [--success|--failure] [--detail 详情] [--duration 毫秒]
  reflection.py reflect [--threshold N] [--cooldown 秒]   执行完整反思
  reflection.py review [--threshold N] [--cooldown 秒]    每日复盘报告
  reflection.py stats                                     统计概览
  reflection.py proposals                                 查看待处理提案
  reflection.py approve <编号>                            批准提案
  reflection.py reject <编号>                             拒绝提案
  reflection.py control                                  查看进化控制状态

阈值控制:
  --threshold N    提案累积阈值（默认5）
  --cooldown  SEC  冷却期秒数（默认3600）
""")
        return

    action = sys.argv[1]

    # 解析 --threshold 和 --cooldown
    threshold = 5
    cooldown = 3600
    extra_args = []
    i = 2
    while i < len(sys.argv):
        if sys.argv[i] == '--threshold' and i + 1 < len(sys.argv):
            threshold = int(sys.argv[i + 1]); i += 2
        elif sys.argv[i] == '--cooldown' and i + 1 < len(sys.argv):
            cooldown = int(sys.argv[i + 1]); i += 2
        else:
            extra_args.append(sys.argv[i]); i += 1

    sr = SelfReflection(threshold=threshold, cooldown_seconds=cooldown)

    if action == 'observe' and len(extra_args) >= 2:
        event_type = extra_args[0]
        op_name = extra_args[1]
        success = '--success' in sys.argv
        failure = '--failure' in sys.argv
        result = "failure" if failure else "success"
        detail = ""
        duration = 0

        for j, arg in enumerate(extra_args[2:], 2):
            if arg == '--detail' and j + 1 < len(extra_args):
                detail = extra_args[j + 1]
            elif arg == '--duration' and j + 1 < len(extra_args):
                duration = int(extra_args[j + 1])

        obs_id = sr.collector.record(event_type, op_name, result=result,
                                     detail=detail, duration_ms=duration)
        print(f"📝 已记录: {obs_id} ({event_type}/{op_name}/{result})")

    elif action == 'reflect':
        result = sr.reflect()
        print(f"📊 统计: {result['stats'].get('total', 0)} 条记录")
        print(f"⚠️  问题: {result['analysis'].get('total_issues', 0)} 个")
        print(f"💡 提案: {result['pending_proposals']} 个待处理")
        if result['should_report']:
            print(f"\n{result['report']}")

    elif action == 'review':
        print(sr.daily_review())

    elif action == 'stats':
        stats = sr.stats()
        print("\n📊 运行统计:")
        for k, v in stats.items():
            print(f"  {k}: {v}")

    elif action == 'proposals':
        pending = sr.pending_proposals()
        if not pending:
            print("📋 无待处理提案")
        else:
            print(f"\n💡 待处理提案 ({len(pending)}):")
            for idx, p in enumerate(pending):
                print(f"  #{idx} [{p['priority']}] {p['title']}")
                print(f"     {p['description']}")

    elif action == 'approve' and extra_args:
        idx = int(extra_args[0])
        result = sr.approve_proposal(idx)
        print(f"{'✅' if result.get('approved') else '❌'} {result}")

    elif action == 'reject' and extra_args:
        idx = int(extra_args[0])
        result = sr.reject_proposal(idx)
        print(f"{'✅' if result.get('rejected') else '❌'} {result}")

    elif action == 'control':
        status = sr.proposals.control_status()
        print("🎛️  进化控制状态:")
        print(f"  待处理提案: {status['pending']}")
        print(f"  触发阈值: {status['threshold']}")
        print(f"  冷却期: {status['cooldown_seconds']}s")
        print(f"  冷却中: {'是' if status['in_cooldown'] else '否'}")
        print(f"  上次报告: {status['last_report_time'] or '从未'}")
        print(f"  建议触发: {'是' if status['should_report'] else '否'}")

    else:
        print(f"未知命令: {action}")


if __name__ == "__main__":
    main()
