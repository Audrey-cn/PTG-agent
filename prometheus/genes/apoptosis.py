"""
prometheus/genes/apoptosis.py

细胞凋亡隐喻 - 程序性细胞死亡
================================================================================

生物学灵感：
    细胞凋亡 (Apoptosis) 是程序性细胞死亡：
    - 是有序的、受调控的过程，不是坏死
    - 对发育和稳态维持至关重要
    - 移除不需要或异常细胞
    - 内容物被有序包装吞噬，不引发炎症
    
    在普罗米修斯系统中：
    - 程序性基因死亡代替暴力删除
    - 凋亡小体 = 打包保存基因蓝图归档
    - 吞噬细胞 = 清理进程
    - 凋亡信号通路 = 多步骤检查点
    - 不引发"炎症" = 不破坏系统稳定性

生物学隐喻：
    - ApoptosisPathway → 凋亡信号通路
    - DeathSignal → 死亡信号
    - Apoptosome → 凋亡小体（归档包）
    - CaspaseCascade → 胱天蛋白酶级联（执行步骤）
    - Phagocyte → 吞噬细胞（清理）
    - InflammatoryResponse → 炎症反应（若出错）

参考文献：
    - Cell, "Apoptosis: A basic biological phenomenon with wide-ranging implications"
    - Nature Reviews Cancer, "Apoptosis in cancer"
    - Science, "The biochemistry of apoptosis"
"""

import os
import json
import shutil
import datetime
from typing import Dict, List, Set, Optional, Tuple, Any, Callable
from dataclasses import dataclass, field, asdict
from enum import Enum
from datetime import datetime

from storage import StorageEngine
from genes.bank import GeneBank
from genes.immune_surveillance import Antigen, ImmuneSurveillance


class ApoptosisStage(Enum):
    """凋亡阶段"""
    HEALTHY = "healthy"
    SIGNAL_RECEIVED = "signal_received"
    MITOCHONDRIAL_PERMEABILIZATION = "mitochondrial_permeabilization"
    CASPASE_ACTIVATION = "caspase_activation"
    PHAGOCYTOSIS = "phagocytosis"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class DeathSignal:
    """死亡信号"""
    signal_id: str
    gene_id: str
    source: str  # "immune_surveillance", "pruning", "manual"
    reason: str
    confidence: float
    timestamp: str
    requires_archiving: bool = True


@dataclass
class Apoptosome:
    """凋亡小体 - 归档的死亡基因"""
    apoptosome_id: str
    gene_id: str
    original_blueprint: Dict[str, Any]
    death_signal: DeathSignal
    created_at: str
    file_backup: Optional[str] = None
    checksum: Optional[str] = None


@dataclass
class ApoptosisResult:
    """凋亡结果"""
    gene_id: str
    stage: ApoptosisStage
    success: bool
    apoptosome: Optional[Apoptosome]
    message: str
    inflammatory_response: bool  # 意外炎症意味着清理不干净


class CaspaseCascade:
    """胱天蛋白酶级联反应 - 执行凋亡的有序步骤"""
    
    def __init__(self):
        # 胱天蛋白酶激活顺序
        self.execution_order = [
            "initiate",
            "check_viability",
            "prepare_archive",
            "disassemble_dependencies",
            "remove_from_bank",
            "finalize_archive"
        ]
    
    def execute(self, gene_id: str, death_signal: DeathSignal,
               gene_bank: GeneBank, archive_path: str) -> Tuple[bool, str, Optional[Apoptosome]]:
        """执行级联反应"""
        blueprint = gene_bank.get_gene(gene_id)
        if blueprint is None:
            return False, f"Gene {gene_id} not found", None
        
        apoptosome = Apoptosome(
            apoptosome_id=self._generate_apoptosome_id(gene_id),
            gene_id=gene_id,
            original_blueprint=blueprint,
            death_signal=death_signal,
            created_at=datetime.now().isoformat()
        )
        
        for step in self.execution_order:
            if step == "initiate":
                continue
            elif step == "check_viability":
                if not self._can_execute(gene_id, blueprint, death_signal):
                    return False, f"Pre-execution check failed for {gene_id}", None
            elif step == "prepare_archive":
                if death_signal.requires_archiving:
                    ok, msg = self._save_archive(apoptosome, archive_path)
                    if not ok:
                        return False, msg, None
            elif step == "disassemble_dependencies":
                self._disassemble_dependencies(gene_id, gene_bank)
            elif step == "remove_from_bank":
                ok = gene_bank.remove_gene(gene_id)
                if not ok:
                    return False, f"Failed to remove {gene_id} from gene bank", None
            elif step == "finalize_archive":
                pass
        
        return True, f"Apoptosis completed successfully for {gene_id}", apoptosome
    
    def _can_execute(self, gene_id: str, blueprint: Dict, signal: DeathSignal) -> bool:
        """检查是否可以执行凋亡"""
        if signal.confidence < 0.6:
            return False
        
        if blueprint.get("protected", False):
            return False
        
        return True
    
    def _save_archive(self, apoptosome: Apoptosome, archive_path: str) -> Tuple[bool, str]:
        """保存归档"""
        try:
            os.makedirs(archive_path, exist_ok=True)
            archive_file = os.path.join(archive_path, f"{apoptosome.apoptosome_id}.json")
            with open(archive_file, 'w', encoding='utf-8') as f:
                json.dump(asdict(apoptosome), f, indent=2, ensure_ascii=False)
            apoptosome.file_backup = archive_file
            return True, "Archive saved"
        except Exception as e:
            return False, f"Archive save failed: {str(e)}"
    
    def _disassemble_dependencies(self, gene_id: str, gene_bank: GeneBank):
        """解除依赖关系"""
        all_genes = gene_bank.list_genes()
        for gene in all_genes:
            blueprint = gene_bank.get_gene(gene["gene_id"])
            if blueprint and "dependencies" in blueprint:
                if gene_id in blueprint["dependencies"]:
                    blueprint["dependencies"].remove(gene_id)
                    gene_bank.update_gene(gene["gene_id"], blueprint)
    
    def _generate_apoptosome_id(self, gene_id: str) -> str:
        ts = datetime.now().isoformat()
        import hashlib
        h = hashlib.md5(f"{gene_id}{ts}".encode()).hexdigest()[:6]
        return f"apo_{gene_id}_{h}"


class ApoptosisPathway:
    """细胞凋亡信号通路 - 调控程序性基因死亡"""
    
    def __init__(self, storage: StorageEngine, gene_bank: GeneBank,
                 data_dir: str = None):
        self.storage = storage
        self.gene_bank = gene_bank
        self.data_dir = data_dir or os.path.join(os.path.dirname(__file__), "_apoptosis")
        os.makedirs(self.data_dir, exist_ok=True)
        
        self.archive_dir = os.path.join(self.data_dir, "archived")
        os.makedirs(self.archive_dir, exist_ok=True)
        
        self.caspase = CaspaseCascade()
        self.pending_signals: Dict[str, DeathSignal] = {}
        self.completed_apoptosis: List[ApoptosisResult] = []
        
        self._post_execution_hooks: List[Callable[[str], None]] = []
        
        self._load_pending()
    
    def register_post_hook(self, hook: Callable[[str], None]):
        """注册凋亡后钩子"""
        self._post_execution_hooks.append(hook)
    
    def send_death_signal(self, gene_id: str, source: str, reason: str,
                         confidence: float, archive: bool = True) -> DeathSignal:
        """发送死亡信号启动凋亡通路"""
        signal = DeathSignal(
            signal_id=self._generate_signal_id(gene_id),
            gene_id=gene_id,
            source=source,
            reason=reason,
            confidence=confidence,
            timestamp=datetime.now().isoformat(),
            requires_archiving=archive
        )
        self.pending_signals[signal.signal_id] = signal
        self._save_pending()
        return signal
    
    def trigger_from_immune_surveillance(self, antigen: Antigen,
                                        immune: ImmuneSurveillance) -> Optional[DeathSignal]:
        """从免疫监视结果触发凋亡"""
        if antigen.confidence >= 0.8:
            return self.send_death_signal(
                gene_id=antigen.gene_id,
                source="immune_surveillance",
                reason=f"High confidence abnormality: {antigen.abnormality_type.value}",
                confidence=antigen.confidence,
                archive=True
            )
        return None
    
    def execute_pending(self, min_confidence: float = 0.6) -> List[ApoptosisResult]:
        """执行所有待处理凋亡"""
        results = []
        
        to_remove = []
        for signal_id, signal in self.pending_signals.items():
            if signal.confidence >= min_confidence:
                result = self.execute_apoptosis(signal)
                results.append(result)
                to_remove.append(signal_id)
        
        for signal_id in to_remove:
            del self.pending_signals[signal_id]
        
        self._save_pending()
        return results
    
    def execute_apoptosis(self, signal: DeathSignal) -> ApoptosisResult:
        """执行单个凋亡程序"""
        stage = ApoptosisStage.HEALTHY
        
        try:
            stage = ApoptosisStage.SIGNAL_RECEIVED
            gene_id = signal.gene_id
            
            stage = ApoptosisStage.MITOCHONDRIAL_PERMEABILIZATION
            if not self.gene_bank.get_gene(gene_id):
                return ApoptosisResult(
                    gene_id=gene_id,
                    stage=stage,
                    success=False,
                    apoptosome=None,
                    message=f"Gene {gene_id} not found",
                    inflammatory_response=True
                )
            
            stage = ApoptosisStage.CASPASE_ACTIVATION
            success, message, apoptosome = self.caspase.execute(
                gene_id, signal, self.gene_bank, self.archive_dir
            )
            
            if not success:
                return ApoptosisResult(
                    gene_id=gene_id,
                    stage=stage,
                    success=False,
                    apoptosome=None,
                    message=message,
                    inflammatory_response=True
                )
            
            stage = ApoptosisStage.PHAGOCYTOSIS
            for hook in self._post_execution_hooks:
                try:
                    hook(gene_id)
                except Exception:
                    pass
            
            stage = ApoptosisStage.COMPLETED
            result = ApoptosisResult(
                gene_id=gene_id,
                stage=stage,
                success=True,
                apoptosome=apoptosome,
                message=message,
                inflammatory_response=False
            )
            
            self.completed_apoptosis.append(result)
            return result
            
        except Exception as e:
            return ApoptosisResult(
                gene_id=signal.gene_id,
                stage=ApoptosisStage.FAILED,
                success=False,
                apoptosome=None,
                message=f"Exception during apoptosis: {str(e)}",
                inflammatory_response=True
            )
    
    def restore_from_apoptosome(self, apoptosome_id: str) -> Optional[str]:
        """从凋亡小体恢复基因（类似发育过程中的可逆调控）
        
        Returns:
            恢复后的基因ID，None表示失败
        """
        archive_file = os.path.join(self.archive_dir, f"{apoptosome_id}.json")
        if not os.path.exists(archive_file):
            return None
        
        with open(archive_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        original_blueprint = data["original_blueprint"]
        gene_id = data["gene_id"]
        
        restored_id = f"{gene_id}_restored_{int(datetime.now().timestamp())}"
        self.gene_bank.add_gene(restored_id, original_blueprint)
        
        return restored_id
    
    def list_pending(self) -> List[DeathSignal]:
        """列出待处理死亡信号"""
        return list(self.pending_signals.values())
    
    def list_completed(self) -> List[ApoptosisResult]:
        """列出已完成凋亡"""
        return self.completed_apoptosis
    
    def statistics(self) -> Dict[str, Any]:
        """凋亡统计"""
        pending = len(self.pending_signals)
        completed = len(self.completed_apoptosis)
        successful = sum(1 for r in self.completed_apoptosis if r.success)
        inflammatory = sum(1 for r in self.completed_apoptosis if r.inflammatory_response)
        
        by_source: Dict[str, int] = {}
        for signal in self.pending_signals.values():
            by_source[signal.source] = by_source.get(signal.source, 0) + 1
        
        return {
            "pending": pending,
            "completed": completed,
            "successful": successful,
            "inflammatory_events": inflammatory,
            "pending_by_source": by_source,
        }
    
    def _generate_signal_id(self, gene_id: str) -> str:
        ts = datetime.now().isoformat()
        import hashlib
        h = hashlib.md5(f"{gene_id}{ts}".encode()).hexdigest()[:6]
        return f"sig_{gene_id}_{h}"
    
    def _load_pending(self):
        """加载待处理信号"""
        pending_path = os.path.join(self.data_dir, "pending_signals.json")
        if os.path.exists(pending_path):
            with open(pending_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for item in data:
                    signal = DeathSignal(**item)
                    self.pending_signals[signal.signal_id] = signal
    
    def _save_pending(self):
        """保存待处理信号"""
        pending_path = os.path.join(self.data_dir, "pending_signals.json")
        data = [asdict(s) for s in self.pending_signals.values()]
        with open(pending_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
