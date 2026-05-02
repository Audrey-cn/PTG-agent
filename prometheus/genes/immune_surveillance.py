"""prometheus/genes/immune_surveillance.py."""

import hashlib
import json
import os
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum
from typing import Any

from prometheus.genes.bank import GeneBank
from prometheus.storage import StorageEngine


class AbnormalityType(Enum):
    """异常类型（对应不同抗原）"""

    SYNTAX_ERROR = "syntax_error"
    TYPE_MISMATCH = "type_mismatch"
    CYCLOMATIC_COMPLEXITY = "cyclomatic_complexity"
    DEAD_CODE = "dead_code"
    DEPENDENCY_HELL = "dependency_hell"
    FUNCTIONAL_DEGRADATION = "functional_degradation"
    ARCHITECTURE_DRIFT = "architecture_drift"
    PERFORMANCE_DEGRADATION = "performance_degradation"


class CheckpointState(Enum):
    """检查点状态"""

    ACTIVE = "active"  # 检查点激活（抑制修正）
    BLOCKED = "blocked"  # 检查点阻断（允许激进修正）


@dataclass
class Antigen:
    """抗原 - 异常基因的标记"""

    antigen_id: str
    gene_id: str
    abnormality_type: AbnormalityType
    confidence: float  # 0-1 异常置信度
    evidence: list[str]
    detected_at: str
    epitopes: list[str]  # 抗原表位 = 具体错误位置

    def is_high_confidence(self) -> bool:
        return self.confidence > 0.7


@dataclass
class ImmuneResponse:
    """免疫应答结果"""

    antigen: Antigen
    response_active: bool
    checkpoint_state: CheckpointState
    proposed_corrections: list[dict[str, Any]]
    clone_score: float  # 克隆评分（越高越好）
    responded_at: str


class CheckpointController:
    """免疫检查点控制器 - 控制修正强度"""

    def __init__(self):
        # PD-1 检查点：默认激活，防止过度修正
        self.pd1_state: CheckpointState = CheckpointState.ACTIVE
        # CTLA-4 检查点：默认激活
        self.ctla4_state: CheckpointState = CheckpointState.ACTIVE

        # 检查点阈值
        self.confidence_threshold = {
            CheckpointState.ACTIVE: 0.8,
            CheckpointState.BLOCKED: 0.5,
        }

    def apply_blockade(self, checkpoint: str) -> None:
        """应用检查点阻断（免疫治疗）"""
        if checkpoint == "PD-1":
            self.pd1_state = CheckpointState.BLOCKED
        elif checkpoint == "CTLA-4":
            self.ctla4_state = CheckpointState.BLOCKED

    def reset(self) -> None:
        """重置到默认状态"""
        self.pd1_state = CheckpointState.ACTIVE
        self.ctla4_state = CheckpointState.ACTIVE

    def should_respond(self, antigen: Antigen) -> bool:
        """基于检查点状态决定是否应答"""
        if (
            self.pd1_state == CheckpointState.BLOCKED
            and self.ctla4_state == CheckpointState.BLOCKED
        ):
            threshold = self.confidence_threshold[CheckpointState.BLOCKED]
        else:
            threshold = self.confidence_threshold[CheckpointState.ACTIVE]

        return antigen.confidence >= threshold

    def get_aggressiveness(self) -> float:
        """获取修正侵略性"""
        if (
            self.pd1_state == CheckpointState.BLOCKED
            and self.ctla4_state == CheckpointState.BLOCKED
        ):
            return 0.9
        elif self.pd1_state == CheckpointState.BLOCKED:
            return 0.7
        elif self.ctla4_state == CheckpointState.BLOCKED:
            return 0.6
        else:
            return 0.4


class ImmuneSurveillance:
    """免疫监视系统 - 持续扫描基因异常"""

    def __init__(self, storage: StorageEngine, gene_bank: GeneBank, data_dir: str = None):
        self.storage = storage
        self.gene_bank = gene_bank
        self.data_dir = data_dir or os.path.join(os.path.dirname(__file__), "_immune")
        os.makedirs(self.data_dir, exist_ok=True)

        self.detected_antigens: dict[str, Antigen] = {}
        self.responses: dict[str, ImmuneResponse] = {}
        self.checkpoint = CheckpointController()

        self._detector_hooks: list[Callable[[str, dict], list[Antigen]]] = []

        self._load_antigens()

    def register_detector(self, detector: Callable[[str, dict], list[Antigen]]):
        """注册自定义检测器"""
        self._detector_hooks.append(detector)

    def scan_gene(self, gene_id: str, gene_blueprint: dict[str, Any]) -> list[Antigen]:
        """扫描单个基因，检测异常"""
        antigens = []

        # 预设检测器
        antigens.extend(self._built_in_detection(gene_id, gene_blueprint))

        # 调用自定义检测器
        for detector in self._detector_hooks:
            try:
                detected = detector(gene_id, gene_blueprint)
                antigens.extend(detected)
            except Exception:
                pass

        # 保存检测结果
        for antigen in antigens:
            self.detected_antigens[antigen.antigen_id] = antigen

        self._save_antigens()
        return antigens

    def survey_all(self) -> dict[str, int]:
        """全面巡查所有基因

        Returns:
            {gene_id: 异常数}
        """
        all_genes = self.gene_bank.list_genes()
        results = {}

        for gene in all_genes:
            blueprint = self.gene_bank.get_gene(gene["gene_id"])
            if blueprint:
                antigens = self.scan_gene(gene["gene_id"], blueprint)
                if antigens:
                    results[gene["gene_id"]] = len(antigens)

        return results

    def mount_response(self, antigen: Antigen) -> ImmuneResponse:
        """对抗原启动免疫应答"""
        if not self.checkpoint.should_respond(antigen):
            response = ImmuneResponse(
                antigen=antigen,
                response_active=False,
                checkpoint_state=self._current_checkpoint_state(),
                proposed_corrections=[],
                clone_score=0.0,
                responded_at=datetime.now().isoformat(),
            )
        else:
            aggressiveness = self.checkpoint.get_aggressiveness()
            corrections = self._generate_corrections(antigen, aggressiveness)

            response = ImmuneResponse(
                antigen=antigen,
                response_active=True,
                checkpoint_state=self._current_checkpoint_state(),
                proposed_corrections=corrections,
                clone_score=self._calculate_clone_score(corrections, antigen),
                responded_at=datetime.now().isoformat(),
            )

        self.responses[antigen.antigen_id] = response
        self._save_antigens()
        return response

    def checkpoint_blockade(self, checkpoint: str) -> None:
        """免疫检查点阻断 - 允许更激进的修正"""
        self.checkpoint.apply_blockade(checkpoint)

    def enable_aggressive_therapy(self) -> None:
        """激进治疗 - 阻断所有检查点"""
        self.checkpoint.apply_blockade("PD-1")
        self.checkpoint.apply_blockade("CTLA-4")

    def list_high_confidence_antigens(self) -> list[Antigen]:
        """列出高置信度异常"""
        return [a for a in self.detected_antigens.values() if a.is_high_confidence()]

    def get_statistics(self) -> dict[str, Any]:
        """获取免疫监视统计"""
        by_type: dict[str, int] = {}
        for a in self.detected_antigens.values():
            t = a.abnormality_type.value
            by_type[t] = by_type.get(t, 0) + 1

        responded = sum(1 for r in self.responses.values() if r.response_active)

        return {
            "total_detected": len(self.detected_antigens),
            "high_confidence": len(self.list_high_confidence_antigens()),
            "by_type": by_type,
            "total_responded": responded,
            "pd1_state": self.checkpoint.pd1_state.value,
            "ctla4_state": self.checkpoint.ctla4_state.value,
        }

    def _built_in_detection(self, gene_id: str, blueprint: dict[str, Any]) -> list[Antigen]:
        """内置检测规则"""
        antigens = []

        # 检查依赖地狱
        if "dependencies" in blueprint:
            deps = blueprint["dependencies"]
            if isinstance(deps, list) and len(deps) > 15:
                antigen_id = self._generate_antigen_id(gene_id, "dependency_hell")
                antigens.append(
                    Antigen(
                        antigen_id=antigen_id,
                        gene_id=gene_id,
                        abnormality_type=AbnormalityType.DEPENDENCY_HELL,
                        confidence=min(0.5 + (len(deps) - 15) * 0.02, 0.95),
                        evidence=[f"Too many dependencies: {len(deps)}"],
                        detected_at=datetime.now().isoformat(),
                        epitopes=["dependencies"],
                    )
                )

        # 检查功能退化标记
        if "degradation_score" in blueprint:
            score = blueprint["degradation_score"]
            if score > 0.5:
                antigen_id = self._generate_antigen_id(gene_id, "functional_degradation")
                antigens.append(
                    Antigen(
                        antigen_id=antigen_id,
                        gene_id=gene_id,
                        abnormality_type=AbnormalityType.FUNCTIONAL_DEGRADATION,
                        confidence=score,
                        evidence=[f"Degradation score: {score:.2f}"],
                        detected_at=datetime.now().isoformat(),
                        epitopes=["function"],
                    )
                )

        # 检查架构漂移
        if "original_purpose" in blueprint and "current_purpose" in blueprint:
            if blueprint["original_purpose"] != blueprint["current_purpose"]:
                antigen_id = self._generate_antigen_id(gene_id, "architecture_drift")
                antigens.append(
                    Antigen(
                        antigen_id=antigen_id,
                        gene_id=gene_id,
                        abnormality_type=AbnormalityType.ARCHITECTURE_DRIFT,
                        confidence=0.7,
                        evidence=["Purpose has drifted from original design"],
                        detected_at=datetime.now().isoformat(),
                        epitopes=["architecture", "purpose"],
                    )
                )

        return antigens

    def _generate_corrections(
        self, antigen: Antigen, aggressiveness: float
    ) -> list[dict[str, Any]]:
        """生成修正提议"""
        corrections = []

        base_correction = {
            "antigen_id": antigen.antigen_id,
            "abnormality_type": antigen.abnormality_type.value,
            "aggressiveness": aggressiveness,
        }

        if antigen.abnormality_type == AbnormalityType.DEPENDENCY_HELL:
            corrections.append(
                {
                    **base_correction,
                    "strategy": "refactoring",
                    "action": "split_module",
                    "description": "Split into smaller modules with fewer dependencies",
                }
            )

        elif antigen.abnormality_type == AbnormalityType.FUNCTIONAL_DEGRADATION:
            corrections.append(
                {
                    **base_correction,
                    "strategy": "regeneration",
                    "action": "call_stem_cell",
                    "description": "Trigger stem cell regeneration from blueprint",
                }
            )

        elif antigen.abnormality_type == AbnormalityType.ARCHITECTURE_DRIFT:
            corrections.append(
                {
                    **base_correction,
                    "strategy": "re-alignment",
                    "action": "update_blueprint",
                    "description": "Update blueprint to match current purpose",
                }
            )

        if aggressiveness > 0.6:
            corrections.append(
                {
                    **base_correction,
                    "strategy": "radical",
                    "action": "apoptosis",
                    "description": "Schedule for programmed cell death if regeneration fails",
                }
            )

        return corrections

    def _calculate_clone_score(self, corrections: list[dict], antigen: Antigen) -> float:
        """计算克隆评分（越高越可能有效）"""
        base_score = antigen.confidence
        if len(corrections) >= 2:
            base_score *= 1.1
        if any(c["strategy"] == "regeneration" for c in corrections):
            base_score *= 1.05
        return min(base_score, 1.0)

    def _current_checkpoint_state(self) -> CheckpointState:
        """获取当前整体检查点状态"""
        if self.checkpoint.pd1_state == CheckpointState.BLOCKED:
            return CheckpointState.BLOCKED
        return CheckpointState.ACTIVE

    def _generate_antigen_id(self, gene_id: str, abnormality: str) -> str:
        """生成抗原ID"""
        ts = datetime.now().isoformat()
        h = hashlib.md5(f"{gene_id}{abnormality}{ts}".encode()).hexdigest()[:8]
        return f"ag_{gene_id}_{h}"

    def _load_antigens(self):
        """加载已检测抗原"""
        index_path = os.path.join(self.data_dir, "detected_antigens.json")
        if os.path.exists(index_path):
            with open(index_path, encoding="utf-8") as f:
                data = json.load(f)
                for item in data:
                    antigen = Antigen(
                        antigen_id=item["antigen_id"],
                        gene_id=item["gene_id"],
                        abnormality_type=AbnormalityType(item["abnormality_type"]),
                        confidence=item["confidence"],
                        evidence=item["evidence"],
                        detected_at=item["detected_at"],
                        epitopes=item["epitopes"],
                    )
                    self.detected_antigens[antigen.antigen_id] = antigen

    def _save_antigens(self):
        """保存检测结果"""
        index_path = os.path.join(self.data_dir, "detected_antigens.json")
        data = []
        for antigen in self.detected_antigens.values():
            item = asdict(antigen)
            item["abnormality_type"] = antigen.abnormality_type.value
            data.append(item)
        with open(index_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
