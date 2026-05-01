#!/usr/bin/env python3
"""╔══════════════════════════════════════════════════════════════╗."""

import datetime
import json
import os
from dataclasses import asdict, dataclass, field
from enum import Enum

PROMETHEUS_HOME = os.path.expanduser("~/.hermes/tools/prometheus")
PATHWAYS_DIR = os.path.join(PROMETHEUS_HOME, "pathways")
PATHWAYS_CATALOG = os.path.join(PATHWAYS_DIR, "pathways_catalog.json")
PATHWAYS_LOG = os.path.join(PATHWAYS_DIR, "pathways_log.json")

os.makedirs(PATHWAYS_DIR, exist_ok=True)


class PathwayAction(Enum):
    """通路动作类型"""

    ACTIVATE = "activate"
    SILENCE = "silence"
    BOOST = "boost"
    INHIBIT = "inhibit"
    SWITCH_ALLELE = "switch_allele"


class FeedbackType(Enum):
    """反馈类型"""

    POSITIVE = "positive"
    NEGATIVE = "negative"
    NONE = "none"


@dataclass
class PathwayStep:
    """通路步骤 - 单个基因的触发动作

    对应碳基生物学：信号通路中的一个节点
    """

    target_gene: str
    action: str = "activate"
    strength: float = 1.0
    condition: str = ""
    delay_ms: int = 0

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "PathwayStep":
        return cls(
            target_gene=data.get("target_gene", ""),
            action=data.get("action", "activate"),
            strength=data.get("strength", 1.0),
            condition=data.get("condition", ""),
            delay_ms=data.get("delay_ms", 0),
        )


@dataclass
class SignalPathway:
    """信号通路 - 基因间的联动机制

    对应碳基生物学概念：
    - 触发器：信号分子/配体结合
    - 级联：信号传递链
    - 反馈：调节回路
    """

    pathway_id: str
    name: str
    description: str = ""
    trigger_gene: str = ""
    trigger_event: str = "activate"
    cascade: list[PathwayStep] = field(default_factory=list)
    feedback_type: str = "none"
    feedback_target: str = ""
    enabled: bool = True
    created: str = ""

    def __post_init__(self):
        if not self.created:
            self.created = datetime.datetime.now().isoformat()

    def to_dict(self) -> dict:
        result = {
            "pathway_id": self.pathway_id,
            "name": self.name,
            "description": self.description,
            "trigger_gene": self.trigger_gene,
            "trigger_event": self.trigger_event,
            "cascade": [s.to_dict() for s in self.cascade],
            "feedback_type": self.feedback_type,
            "feedback_target": self.feedback_target,
            "enabled": self.enabled,
            "created": self.created,
        }
        return result

    @classmethod
    def from_dict(cls, data: dict) -> "SignalPathway":
        cascade = [PathwayStep.from_dict(s) for s in data.get("cascade", [])]
        return cls(
            pathway_id=data.get("pathway_id", ""),
            name=data.get("name", ""),
            description=data.get("description", ""),
            trigger_gene=data.get("trigger_gene", ""),
            trigger_event=data.get("trigger_event", "activate"),
            cascade=cascade,
            feedback_type=data.get("feedback_type", "none"),
            feedback_target=data.get("feedback_target", ""),
            enabled=data.get("enabled", True),
            created=data.get("created", ""),
        )


class PathwayManager:
    """信号通路管理器 - 管理基因间的自动联动

    核心功能：
    - register_pathway(): 注册新的信号通路
    - trigger(): 触发信号通路
    - get_pathways(): 获取通路列表
    - enable/disable: 启用/禁用通路
    """

    def __init__(self, seed_path: str = None):
        self.seed_path = seed_path
        self._ensure_catalog()
        self._ensure_log()

    def _ensure_catalog(self):
        if not os.path.exists(PATHWAYS_CATALOG):
            with open(PATHWAYS_CATALOG, "w") as f:
                json.dump({"pathways": {}, "triggers_index": {}}, f, ensure_ascii=False, indent=2)

    def _ensure_log(self):
        if not os.path.exists(PATHWAYS_LOG):
            with open(PATHWAYS_LOG, "w") as f:
                json.dump({"executions": []}, f, ensure_ascii=False, indent=2)

    def _load_catalog(self) -> dict:
        with open(PATHWAYS_CATALOG) as f:
            return json.load(f)

    def _save_catalog(self, catalog: dict):
        with open(PATHWAYS_CATALOG, "w") as f:
            json.dump(catalog, f, ensure_ascii=False, indent=2)

    def _log_execution(self, pathway_id: str, trigger_gene: str, trigger_event: str, results: list):
        with open(PATHWAYS_LOG) as f:
            log_data = json.load(f)

        log_data["executions"].append(
            {
                "timestamp": datetime.datetime.now().isoformat(),
                "pathway_id": pathway_id,
                "trigger_gene": trigger_gene,
                "trigger_event": trigger_event,
                "results": results,
            }
        )

        with open(PATHWAYS_LOG, "w") as f:
            json.dump(log_data, f, ensure_ascii=False, indent=2)

    def register_pathway(self, pathway: SignalPathway) -> dict:
        """注册新的信号通路

        Args:
            pathway: 信号通路定义

        Returns:
            {success: bool, message: str, pathway_id: str}
        """
        catalog = self._load_catalog()

        if pathway.pathway_id in catalog["pathways"]:
            return {"success": False, "message": f"信号通路 {pathway.pathway_id} 已存在"}

        catalog["pathways"][pathway.pathway_id] = pathway.to_dict()

        trigger_key = f"{pathway.trigger_gene}:{pathway.trigger_event}"
        if trigger_key not in catalog["triggers_index"]:
            catalog["triggers_index"][trigger_key] = []
        catalog["triggers_index"][trigger_key].append(pathway.pathway_id)

        self._save_catalog(catalog)

        return {
            "success": True,
            "message": f"信号通路 {pathway.name} 已注册",
            "pathway_id": pathway.pathway_id,
            "trigger": f"{pathway.trigger_gene}.{pathway.trigger_event}",
            "cascade_length": len(pathway.cascade),
        }

    def trigger(self, seed_path: str, gene_id: str, event: str, context: dict = None) -> dict:
        """触发信号通路

        对应碳基生物学：信号分子结合受体，启动信号级联

        Args:
            seed_path: 种子文件路径
            gene_id: 触发基因ID
            event: 触发事件 (activate/silence/boost)
            context: 上下文信息

        Returns:
            {triggered: int, pathways: [...], results: [...]}
        """
        catalog = self._load_catalog()

        trigger_key = f"{gene_id}:{event}"
        pathway_ids = catalog["triggers_index"].get(trigger_key, [])

        if not pathway_ids:
            return {
                "triggered": 0,
                "message": f"没有基因 {gene_id} 的 {event} 事件触发的通路",
                "pathways": [],
                "results": [],
            }

        results = []
        triggered_pathways = []

        for pid in pathway_ids:
            pathway_data = catalog["pathways"].get(pid)
            if not pathway_data:
                continue

            pathway = SignalPathway.from_dict(pathway_data)

            if not pathway.enabled:
                continue

            triggered_pathways.append({"pathway_id": pid, "name": pathway.name})

            cascade_results = self._execute_cascade(seed_path, pathway, context)
            results.extend(cascade_results)

        self._log_execution(trigger_key, gene_id, event, results)

        return {
            "triggered": len(triggered_pathways),
            "pathways": triggered_pathways,
            "results": results,
            "message": f"触发了 {len(triggered_pathways)} 条信号通路",
        }

    def _execute_cascade(
        self, seed_path: str, pathway: SignalPathway, context: dict = None
    ) -> list:
        """执行级联反应

        对应碳基生物学：信号级联放大
        """
        results = []
        context = context or {}

        for step in pathway.cascade:
            if step.condition:
                try:
                    if not eval(step.condition, {"context": context}):
                        continue
                except:
                    continue

            result = self._execute_step(seed_path, step)
            result["pathway_id"] = pathway.pathway_id
            results.append(result)

            if pathway.feedback_type == "positive" and pathway.feedback_target:
                self._apply_feedback(seed_path, pathway, step)

        return results

    def _execute_step(self, seed_path: str, step: PathwayStep) -> dict:
        """执行单个通路步骤"""
        result = {
            "target_gene": step.target_gene,
            "action": step.action,
            "strength": step.strength,
            "success": True,
            "message": "",
        }

        if step.action == "activate":
            from epigenetics import EpigeneticsManager

            mgr = EpigeneticsManager()
            res = mgr.activate(seed_path, step.target_gene, "pathway_trigger")
            result["success"] = res.get("success", False)
            result["message"] = res.get("message", "")

        elif step.action == "silence":
            from epigenetics import EpigeneticsManager

            mgr = EpigeneticsManager()
            res = mgr.silence(seed_path, step.target_gene, "pathway_trigger")
            result["success"] = res.get("success", False)
            result["message"] = res.get("message", "")

        elif step.action == "boost":
            from epigenetics import EpigeneticsManager

            mgr = EpigeneticsManager()
            res = mgr.boost(seed_path, step.target_gene, enhancer=step.strength)
            result["success"] = res.get("success", False)
            result["message"] = res.get("message", "")

        elif step.action == "inhibit":
            from epigenetics import EpigeneticsManager

            mgr = EpigeneticsManager()
            res = mgr.boost(seed_path, step.target_gene, silencer=step.strength)
            result["success"] = res.get("success", False)
            result["message"] = res.get("message", "")

        elif step.action == "switch_allele":
            result["message"] = f"需要指定等位基因ID来切换 {step.target_gene}"
            result["success"] = False

        return result

    def _apply_feedback(self, seed_path: str, pathway: SignalPathway, last_step: PathwayStep):
        """应用反馈调节

        对应碳基生物学：
        - 正反馈：增强触发基因的表达
        - 负反馈：抑制触发基因的表达
        """
        if not pathway.feedback_target:
            return

        from epigenetics import EpigeneticsManager

        mgr = EpigeneticsManager()

        if pathway.feedback_type == "positive":
            mgr.boost(seed_path, pathway.feedback_target, enhancer=1.2, reason="positive_feedback")
        elif pathway.feedback_type == "negative":
            mgr.boost(seed_path, pathway.feedback_target, silencer=0.3, reason="negative_feedback")

    def get_pathways(self, gene_id: str = None) -> dict:
        """获取信号通路列表"""
        catalog = self._load_catalog()

        if gene_id:
            related = []
            for pid, pdata in catalog["pathways"].items():
                if pdata.get("trigger_gene") == gene_id:
                    related.append(
                        {
                            "pathway_id": pid,
                            "name": pdata.get("name"),
                            "trigger_event": pdata.get("trigger_event"),
                            "cascade_length": len(pdata.get("cascade", [])),
                            "enabled": pdata.get("enabled", True),
                        }
                    )
                else:
                    for step in pdata.get("cascade", []):
                        if step.get("target_gene") == gene_id:
                            related.append(
                                {
                                    "pathway_id": pid,
                                    "name": pdata.get("name"),
                                    "role": "target",
                                    "enabled": pdata.get("enabled", True),
                                }
                            )
                            break
            return {"gene": gene_id, "pathways": related}

        pathways = []
        for pid, pdata in catalog["pathways"].items():
            pathways.append(
                {
                    "pathway_id": pid,
                    "name": pdata.get("name"),
                    "trigger": f"{pdata.get('trigger_gene')}.{pdata.get('trigger_event')}",
                    "cascade_length": len(pdata.get("cascade", [])),
                    "enabled": pdata.get("enabled", True),
                }
            )

        return {"total": len(pathways), "pathways": pathways}

    def enable_pathway(self, pathway_id: str) -> dict:
        """启用信号通路"""
        catalog = self._load_catalog()

        if pathway_id not in catalog["pathways"]:
            return {"success": False, "message": f"信号通路 {pathway_id} 不存在"}

        catalog["pathways"][pathway_id]["enabled"] = True
        self._save_catalog(catalog)

        return {"success": True, "message": f"信号通路 {pathway_id} 已启用"}

    def disable_pathway(self, pathway_id: str) -> dict:
        """禁用信号通路"""
        catalog = self._load_catalog()

        if pathway_id not in catalog["pathways"]:
            return {"success": False, "message": f"信号通路 {pathway_id} 不存在"}

        catalog["pathways"][pathway_id]["enabled"] = False
        self._save_catalog(catalog)

        return {"success": True, "message": f"信号通路 {pathway_id} 已禁用"}

    def remove_pathway(self, pathway_id: str) -> dict:
        """移除信号通路"""
        catalog = self._load_catalog()

        if pathway_id not in catalog["pathways"]:
            return {"success": False, "message": f"信号通路 {pathway_id} 不存在"}

        pathway = catalog["pathways"][pathway_id]
        trigger_key = f"{pathway.get('trigger_gene')}:{pathway.get('trigger_event')}"

        if trigger_key in catalog["triggers_index"]:
            catalog["triggers_index"][trigger_key] = [
                p for p in catalog["triggers_index"][trigger_key] if p != pathway_id
            ]

        del catalog["pathways"][pathway_id]
        self._save_catalog(catalog)

        return {"success": True, "message": f"信号通路 {pathway_id} 已移除"}

    def get_execution_history(self, pathway_id: str = None, limit: int = 20) -> list:
        """获取执行历史"""
        if not os.path.exists(PATHWAYS_LOG):
            return []

        with open(PATHWAYS_LOG) as f:
            log_data = json.load(f)

        executions = log_data.get("executions", [])

        if pathway_id:
            executions = [e for e in executions if e.get("pathway_id") == pathway_id]

        return executions[-limit:]


def init_standard_pathways():
    """初始化标准信号通路"""
    manager = PathwayManager()

    standard_pathways = [
        SignalPathway(
            pathway_id="content-generation",
            name="内容生成链",
            description="分析器激活时，自动增强写作能力",
            trigger_gene="G002-analyzer",
            trigger_event="activate",
            cascade=[
                PathwayStep(target_gene="G100-writer", action="boost", strength=1.3),
            ],
            feedback_type="positive",
            feedback_target="G002-analyzer",
        ),
        SignalPathway(
            pathway_id="security-defense",
            name="安全防御链",
            description="审计器发现问题时，自动触发休眠保护",
            trigger_gene="G008-auditor",
            trigger_event="boost",
            cascade=[
                PathwayStep(target_gene="G007-dormancy", action="activate"),
            ],
            feedback_type="negative",
            feedback_target="G008-auditor",
        ),
        SignalPathway(
            pathway_id="visual-enhancement",
            name="视觉增强链",
            description="视觉生成器激活时，同时增强分析能力",
            trigger_gene="G101-vision",
            trigger_event="activate",
            cascade=[
                PathwayStep(target_gene="G002-analyzer", action="boost", strength=1.2),
            ],
            feedback_type="none",
        ),
        SignalPathway(
            pathway_id="network-awareness",
            name="网络感知链",
            description="网络感知器激活时，增强安全审计",
            trigger_gene="G200-network",
            trigger_event="activate",
            cascade=[
                PathwayStep(target_gene="G008-auditor", action="boost", strength=1.5),
            ],
            feedback_type="positive",
            feedback_target="G200-network",
        ),
        SignalPathway(
            pathway_id="team-collaboration",
            name="团队协作链",
            description="团队协作器激活时，增强自管理能力",
            trigger_gene="G400-team",
            trigger_event="activate",
            cascade=[
                PathwayStep(target_gene="G006-gardener", action="boost", strength=1.3),
            ],
            feedback_type="none",
        ),
    ]

    results = []
    for pathway in standard_pathways:
        result = manager.register_pathway(pathway)
        results.append(result)

    return {
        "initialized": len([r for r in results if r.get("success")]),
        "pathways": [r.get("pathway_id") for r in results if r.get("success")],
    }


def print_pathways_report(pathways_data: dict):
    """打印信号通路报告"""
    print("""
╔══════════════════════════════════════════════════════════════╗
║   🧬 信号通路报告 · Pathway Report                          ║
╠══════════════════════════════════════════════════════════════╣
""")

    if "gene" in pathways_data:
        print(f"║   基因: {pathways_data['gene']}")
        print(f"║   相关通路: {len(pathways_data.get('pathways', []))} 条")
        print("║")

        for p in pathways_data.get("pathways", []):
            status = "✅" if p.get("enabled", True) else "❌"
            print(f"║   {status} {p.get('pathway_id', '?'):<20} {p.get('name', '?')}")
            if p.get("trigger_event"):
                print(f"║      触发: {p.get('trigger_event')}")
            if p.get("cascade_length"):
                print(f"║      级联长度: {p.get('cascade_length')}")

    else:
        print(f"║   总通路数: {pathways_data.get('total', 0)}")
        print("║")

        for p in pathways_data.get("pathways", []):
            status = "✅" if p.get("enabled", True) else "❌"
            print(f"║   {status} {p.get('pathway_id', '?'):<20} {p.get('name', '?')}")
            print(f"║      触发: {p.get('trigger', '?')} · 级联: {p.get('cascade_length', 0)}步")

    print("╚══════════════════════════════════════════════════════════════╝")


def main():
    import sys

    if len(sys.argv) < 2:
        print("""
🧬 信号通路系统 · Signal Pathway System

用法:
    python pathways.py init                        初始化标准通路
    python pathways.py list [基因ID]               列出信号通路
    python pathways.py trigger <种子> <基因ID> <事件>  触发通路
    python pathways.py enable <通路ID>             启用通路
    python pathways.py disable <通路ID>            禁用通路
    python pathways.py history [通路ID]            查看执行历史

示例:
    python pathways.py init
    python pathways.py list G002-analyzer
    python pathways.py trigger seed.ttg G002-analyzer activate
""")
        return

    action = sys.argv[1]
    manager = PathwayManager()

    if action == "init":
        result = init_standard_pathways()
        print(f"✅ 已初始化 {result['initialized']} 条信号通路")
        print(f"   通路: {', '.join(result['pathways'])}")

    elif action == "list":
        gene_id = sys.argv[2] if len(sys.argv) > 2 else None
        result = manager.get_pathways(gene_id)
        print_pathways_report(result)

    elif action == "trigger" and len(sys.argv) >= 5:
        seed_path = os.path.expanduser(sys.argv[2])
        gene_id = sys.argv[3]
        event = sys.argv[4]
        result = manager.trigger(seed_path, gene_id, event)
        print(f"✅ {result['message']}")
        if result.get("results"):
            print("   执行结果:")
            for r in result["results"]:
                status = "✅" if r.get("success") else "❌"
                print(f"     {status} {r['target_gene']}: {r['action']}")

    elif action == "enable" and len(sys.argv) >= 3:
        pathway_id = sys.argv[2]
        result = manager.enable_pathway(pathway_id)
        print("✅" if result["success"] else "❌", result["message"])

    elif action == "disable" and len(sys.argv) >= 3:
        pathway_id = sys.argv[2]
        result = manager.disable_pathway(pathway_id)
        print("✅" if result["success"] else "❌", result["message"])

    elif action == "history":
        pathway_id = sys.argv[2] if len(sys.argv) > 2 else None
        history = manager.get_execution_history(pathway_id)
        if not history:
            print("暂无执行历史")
        else:
            print(f"\n📜 信号通路执行历史 ({len(history)}条):\n")
            for h in history:
                print(f"  {h['timestamp'][:19]} · {h['pathway_id']}")
                print(f"    触发: {h['trigger_gene']}.{h['trigger_event']}")
                if h.get("results"):
                    for r in h["results"][:3]:
                        print(f"      → {r['target_gene']}: {r['action']}")

    else:
        print("未知命令或参数不足")


if __name__ == "__main__":
    main()
