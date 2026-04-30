"""
prometheus/genes/stem_cell.py

干细胞生物学隐喻 - 再生工程
================================================================================

生物学灵感：
    干细胞 (Stem Cell) 具有两个核心特性：
    1. 自我更新 (Self-renewal) - 能够分裂产生更多相同干细胞
    2. 多向分化 (Pluripotency) - 能分化为多种功能细胞
    
    在普罗米修斯系统中，我们将这一概念映射到：
    - 种子干细胞：存储退化基因的原始"种子"
    - 再生：当基因功能退化时，从干细胞重新分化
    - 去分化：将成熟功能模块逆向工程回干细胞状态
    - 旁分泌效应：干细胞分泌生长因子促进周围组织修复 → 隐喻：提示词优化

生物学隐喻：
    - StemCellNursery → 干细胞培养箱
    - StemCell → 单个干细胞
    - Pluripotency → 多能性评分
    - Differentiation → 定向分化
    - Dedifferentiation → 去分化
    - ParacrineFactors → 旁分泌因子（提示优化信号）
    - Regeneration → 再生过程

参考文献：
    - Nature Reviews Molecular Cell Biology, "Stem cell concepts renew cancer research"
    - Cell Stem Cell, "Stem Cell Diversity and Regeneration"
"""

import os
import json
import hashlib
import random
from typing import Dict, List, Set, Optional, Tuple, Any
from dataclasses import dataclass, field, asdict
from enum import Enum
from datetime import datetime

from storage import StorageEngine
from genes.bank import GeneBank


class DifferentiationState(Enum):
    UNDIFFERENTIATED = "undifferentiated"
    PARTIALLY_DIFFERENTIATED = "partially_differentiated"
    FULLY_DIFFERENTIATED = "fully_differentiated"
    SENESCENT = "senescent"


@dataclass
class StemCell:
    """干细胞 - 存储原始基因蓝图，支持多向分化和再生
    
    Attributes:
        stem_cell_id: 干细胞ID
        blueprint: 原始基因蓝图（JSON）
        pluripotency_score: 多能性评分 (0-1)
        state: 分化状态
        original_gene_id: 源基因ID
        created_at: 创建时间
        passage: 传代次数
        niche_info: 微环境信息（培养条件）
    """
    stem_cell_id: str
    blueprint: Dict[str, Any]
    pluripotency_score: float
    state: DifferentiationState
    original_gene_id: str
    created_at: str
    passage: int
    niche_info: Dict[str, Any] = field(default_factory=dict)
    
    def is_regenerable(self) -> bool:
        """是否可用于再生"""
        return (self.pluripotency_score > 0.3 and 
                self.state != DifferentiationState.SENESCENT)
    
    def calculate_pluripotency_decay(self) -> float:
        """计算多能性衰减（传代越多，多能性略降）"""
        decay = 0.02 * self.passage
        return max(self.pluripotency_score - decay, 0.1)


@dataclass
class RegenerationResult:
    """再生结果"""
    success: bool
    stem_cell_id: str
    new_gene_id: Optional[str]
    differentiation_quality: float  # 0-1
    message: str
    timestamp: str


class StemCellNursery:
    """干细胞培养箱 - 管理干细胞群落
    
    功能：
    1. 将退化功能基因制备成干细胞
    2. 在基因功能完全丧失时进行再生
    3. 维持干细胞微环境（niche）
    4. 支持多向分化产生多种变体
    """
    
    def __init__(self, storage: StorageEngine, gene_bank: GeneBank,
                 data_dir: str = None):
        self.storage = storage
        self.gene_bank = gene_bank
        self.data_dir = data_dir or os.path.join(os.path.dirname(__file__), "_stem_cells")
        os.makedirs(self.data_dir, exist_ok=True)
        
        self.stem_cells: Dict[str, StemCell] = {}
        self._load_stem_cells()
    
    def prepare_stem_cell(self, gene_id: str, blueprint: Dict[str, Any],
                         pluripotency_score: float = None) -> StemCell:
        """从现有基因制备干细胞
        
        Args:
            gene_id: 基因ID
            blueprint: 基因蓝图（保留功能信息）
            pluripotency_score: 如果不提供，自动计算
        
        Returns:
            创建好的干细胞
        """
        if pluripotency_score is None:
            pluripotency_score = self._estimate_pluripotency(blueprint)
        
        stem_id = self._generate_stem_id(gene_id)
        stem = StemCell(
            stem_cell_id=stem_id,
            blueprint=blueprint,
            pluripotency_score=pluripotency_score,
            state=DifferentiationState.UNDIFFERENTIATED,
            original_gene_id=gene_id,
            created_at=datetime.now().isoformat(),
            passage=0,
            niche_info={
                "culture_medium": "standard_regeneration",
                "oxygen_tension": "physiological",
                "growth_factors": ["Wnt", "BMP", "FGF"]
            }
        )
        
        self.stem_cells[stem_id] = stem
        self._save_stem_cells()
        return stem
    
    def regenerate(self, stem_cell_id: str, target_function: str = None) -> RegenerationResult:
        """从干细胞再生功能基因
        
        Args:
            stem_cell_id: 干细胞ID
            target_function: 目标功能定向分化（None使用默认）
        
        Returns:
            再生结果
        """
        if stem_cell_id not in self.stem_cells:
            return RegenerationResult(
                success=False,
                stem_cell_id=stem_cell_id,
                new_gene_id=None,
                differentiation_quality=0.0,
                message="Stem cell not found",
                timestamp=datetime.now().isoformat()
            )
        
        stem = self.stem_cells[stem_cell_id]
        if not stem.is_regenerable():
            return RegenerationResult(
                success=False,
                stem_cell_id=stem_cell_id,
                new_gene_id=None,
                differentiation_quality=0.0,
                message=f"Stem cell not regenerable: state={stem.state.value}, score={stem.pluripotency_score}",
                timestamp=datetime.now().isoformat()
            )
        
        try:
            new_gene_id = f"{stem.original_gene_id}_regenerated_{int(datetime.now().timestamp())}"
            
            blueprint = stem.blueprint.copy()
            if target_function:
                blueprint["target_function"] = target_function
            
            self.gene_bank.add_gene(new_gene_id, blueprint)
            
            stem.passage += 1
            stem.state = DifferentiationState.PARTIALLY_DIFFERENTIATED
            stem.pluripotency_score = stem.calculate_pluripotency_decay()
            self._save_stem_cells()
            
            quality = stem.pluripotency_score * (0.9 + random.random() * 0.1)
            
            return RegenerationResult(
                success=True,
                stem_cell_id=stem_cell_id,
                new_gene_id=new_gene_id,
                differentiation_quality=quality,
                message=f"Successfully regenerated gene from stem cell: {new_gene_id}",
                timestamp=datetime.now().isoformat()
            )
            
        except Exception as e:
            return RegenerationResult(
                success=False,
                stem_cell_id=stem_cell_id,
                new_gene_id=None,
                differentiation_quality=0.0,
                message=f"Regeneration failed: {str(e)}",
                timestamp=datetime.now().isoformat()
            )
    
    def dedifferentiate(self, gene_id: str, current_blueprint: Dict[str, Any]) -> StemCell:
        """去分化 - 将已分化基因逆向转为干细胞
        
        生物学灵感：诱导多能干细胞 (iPS cell) 技术
        
        Args:
            gene_id: 基因ID
            current_blueprint: 当前基因蓝图
        
        Returns:
            新的干细胞
        """
        return self.prepare_stem_cell(gene_id, current_blueprint, 
                                     pluripotency_score=0.85)
    
    def list_stem_cells(self, only_regenerable: bool = True) -> List[StemCell]:
        """列出所有干细胞"""
        if not only_regenerable:
            return list(self.stem_cells.values())
        return [sc for sc in self.stem_cells.values() if sc.is_regenerable()]
    
    def prune_senescent(self) -> int:
        """剪枝衰老干细胞
        
        Returns:
            剪枝数量
        """
        before = len(self.stem_cells)
        self.stem_cells = {
            sid: sc for sid, sc in self.stem_cells.items()
            if sc.state != DifferentiationState.SENESCENT or sc.is_regenerable()
        }
        after = len(self.stem_cells)
        self._save_stem_cells()
        return before - after
    
    def paracrine_optimization(self, prompt: str, context: Dict[str, Any]) -> str:
        """旁分泌效应 - 干细胞分泌生长因子促进修复
        
        隐喻：使用干细胞的"生长因子"优化提示词
        
        Args:
            prompt: 原始提示词
            context: 上下文
        
        Returns:
            优化后的提示词
        """
        growth_factors = [
            "优先考虑简单性和清晰度",
            "保持模块边界清晰",
            "遵循已有的架构设计",
            "优先选择经过验证的方案",
            "注重可维护性和可读性"
        ]
        
        optimized = prompt.rstrip() + "\n\n【再生生长因子引导】\n"
        for gf in growth_factors:
            optimized += f"- {gf}\n"
        
        if context.get("degraded_features"):
            optimized += f"\n需要特别关注以下功能的修复: {context['degraded_features']}\n"
        
        return optimized
    
    def _estimate_pluripotency(self, blueprint: Dict[str, Any]) -> float:
        """估算多能性评分
        
        更完整的蓝图 → 更高的多能性
        """
        score = 0.5
        if "function" in blueprint:
            score += 0.1
        if "interface" in blueprint:
            score += 0.1
        if "dependencies" in blueprint:
            score += 0.1
        if "version" in blueprint:
            score += 0.05
        if "tests" in blueprint:
            score += 0.05
        return min(score, 1.0)
    
    def _generate_stem_id(self, original_id: str) -> str:
        """生成干细胞ID"""
        ts = datetime.now().isoformat()
        h = hashlib.md5(f"{original_id}{ts}".encode()).hexdigest()[:8]
        return f"stem_{original_id}_{h}"
    
    def _load_stem_cells(self):
        """从磁盘加载干细胞"""
        index_path = os.path.join(self.data_dir, "stem_cells.json")
        if os.path.exists(index_path):
            with open(index_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for item in data:
                    state = DifferentiationState(item["state"])
                    stem = StemCell(
                        stem_cell_id=item["stem_cell_id"],
                        blueprint=item["blueprint"],
                        pluripotency_score=item["pluripotency_score"],
                        state=state,
                        original_gene_id=item["original_gene_id"],
                        created_at=item["created_at"],
                        passage=item["passage"],
                        niche_info=item.get("niche_info", {})
                    )
                    self.stem_cells[stem.stem_cell_id] = stem
    
    def _save_stem_cells(self):
        """保存到磁盘"""
        index_path = os.path.join(self.data_dir, "stem_cells.json")
        data = []
        for stem in self.stem_cells.values():
            item = asdict(stem)
            item["state"] = stem.state.value
            data.append(item)
        with open(index_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
