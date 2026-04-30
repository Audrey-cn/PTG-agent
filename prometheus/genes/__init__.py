# Prometheus genes package
# 
# 基因系统模块 - 对应碳基生物学的遗传机制
# 灵感来自：分子生物学、再生医学、免疫学前沿
#
# 模块对照：
# - analyzer.py          → 基因分析器（健康度审计、融合分析）
# - bank.py              → 基因银行（基因库管理）
# - forge.py             → 基因锻炉（批量变异引擎）
# - nursery.py           → 苗圃培育（筛选与沙箱测试）
# - epigenetics.py       → 表观遗传层（不修改DNA只改表达）
# - alleles.py           → 等位基因系统（同基因多版本）
# - pathways.py          → 信号通路（基因联动机制）
# - repair.py            → DNA修复机制（种子自修复）
# - genetic_circuits.py  → 基因回路工程（合成生物学逻辑门）
# - immune_memory.py     → 免疫记忆（终身学习）
# - homeostasis.py       → 内稳态（动态平衡调节）
# - gene_pruning.py      → 基因表达剪枝（神经网络剪枝）
# - modular_recombination.py → 模块化重组引擎（《自然》研究）
# - correction.py        → 自修正机制
# - reflection.py        → 自反思机制
# - stem_cell.py         → 干细胞再生医学（多能性、去分化、再生）
# - immune_surveillance.py → 免疫监视与免疫检查点（异常检测、检查点阻断）
# - apoptosis.py         → 细胞凋亡（程序性基因死亡、有序清理归档）
# - autophagy.py         → 细胞自噬（自我清理、资源回收、稳态维持）

from .analyzer import (
    GeneLibrary,
    GeneHealthAuditor,
    GeneFusionAnalyzer,
    ForeignGeneExtractor,
    print_gene_health_report,
    print_fusion_report,
    print_extraction_report
)

from .bank import GeneBank

from .forge import (
    MutationSpace,
    forge
)

from .nursery import (
    GeneSieve,
    Nursery
)

from .epigenetics import (
    EpigeneticMark,
    EpigeneticsManager,
    print_epigenome_report
)

from .alleles import (
    Allele,
    AllelicLocus,
    AlleleManager,
    AlleleType,
    init_standard_alleles,
    print_alleles_report
)

from .pathways import (
    SignalPathway,
    PathwayStep,
    PathwayManager,
    PathwayAction,
    FeedbackType,
    init_standard_pathways,
    print_pathways_report
)

from .repair import (
    DNARepairMechanism,
    DamageReport,
    RepairResult,
    DamageType,
    RepairStrategy,
    print_damage_report,
    print_repair_report
)

from .genetic_circuits import (
    GeneticCircuit,
    GeneticLogicGate,
    GeneticSwitch,
    GeneticOscillator,
    CircuitFactory,
    CircuitEngine,
    print_circuit_visualization
)

from .immune_memory import (
    ImmuneSystem,
    Antigen,
    Antibody,
    MemoryCell,
    print_immune_response,
    print_immune_stats
)

from .homeostasis import (
    HomeostasisSystem,
    Sensor,
    Effector,
    FeedbackLoop,
    print_homeostasis_dashboard
)

from .gene_pruning import (
    GeneExpressionPruner,
    GeneNode,
    GeneConnection,
    PruningStrategy,
    print_pruning_dashboard
)

from .modular_recombination import (
    RecombinationEngine,
    GeneModule,
    GenomeConfiguration,
    RecombinationType,
    print_recombination_dashboard
)

from .correction import (
    ErrorCategory,
    FixStrategy,
    DegradationMode,
    RetryPolicy,
    ErrorRecord,
    FixResult,
    ErrorDiagnoser,
    FixExecutor,
    SelfCorrection
)

from .reflection import (
    EventType,
    Severity,
    ProposalPriority,
    Observation,
    EvolutionProposal,
    ObservationCollector,
    PatternAnalyzer,
    ProposalManager,
    SelfReflection
)

from .stem_cell import (
    StemCell,
    StemCellNursery,
    RegenerationResult,
    DifferentiationState
)

from .immune_surveillance import (
    ImmuneSurveillance,
    CheckpointController,
    Antigen,
    ImmuneResponse,
    AbnormalityType,
    CheckpointState
)

from .apoptosis import (
    ApoptosisPathway,
    DeathSignal,
    Apoptosome,
    ApoptosisResult,
    CaspaseCascade,
    ApoptosisStage
)

from .autophagy import (
    AutophagyNetwork,
    Autophagosome,
    RecycledFragment,
    AutophagyResult,
    mTORKinase,
    Lysosome,
    AutophagyLevel
)

__all__ = [
    'GeneLibrary',
    'GeneHealthAuditor', 
    'GeneFusionAnalyzer',
    'ForeignGeneExtractor',
    'print_gene_health_report',
    'print_fusion_report',
    'print_extraction_report',
    'GeneBank',
    'MutationSpace',
    'forge',
    'GeneSieve',
    'Nursery',
    'EpigeneticMark',
    'EpigeneticsManager',
    'print_epigenome_report',
    'Allele',
    'AllelicLocus',
    'AlleleManager',
    'AlleleType',
    'init_standard_alleles',
    'print_alleles_report',
    'SignalPathway',
    'PathwayStep',
    'PathwayManager',
    'PathwayAction',
    'FeedbackType',
    'init_standard_pathways',
    'print_pathways_report',
    'DNARepairMechanism',
    'DamageReport',
    'RepairResult',
    'DamageType',
    'RepairStrategy',
    'print_damage_report',
    'print_repair_report',
    'GeneticCircuit',
    'GeneticLogicGate',
    'GeneticSwitch',
    'GeneticOscillator',
    'CircuitFactory',
    'CircuitEngine',
    'print_circuit_visualization',
    'ImmuneSystem',
    'Antigen',
    'Antibody',
    'MemoryCell',
    'print_immune_response',
    'print_immune_stats',
    'HomeostasisSystem',
    'Sensor',
    'Effector',
    'FeedbackLoop',
    'print_homeostasis_dashboard',
    'GeneExpressionPruner',
    'GeneNode',
    'GeneConnection',
    'PruningStrategy',
    'print_pruning_dashboard',
    'RecombinationEngine',
    'GeneModule',
    'GenomeConfiguration',
    'RecombinationType',
    'print_recombination_dashboard',
    'ErrorCategory',
    'FixStrategy',
    'DegradationMode',
    'RetryPolicy',
    'ErrorRecord',
    'FixResult',
    'ErrorDiagnoser',
    'FixExecutor',
    'SelfCorrection',
    'EventType',
    'Severity',
    'ProposalPriority',
    'Observation',
    'EvolutionProposal',
    'ObservationCollector',
    'PatternAnalyzer',
    'ProposalManager',
    'SelfReflection',
    # 新增模块 - 尖端医学/干细胞/免疫学隐喻
    'StemCell',
    'StemCellNursery',
    'RegenerationResult',
    'DifferentiationState',
    'ImmuneSurveillance',
    'CheckpointController',
    'Antigen',
    'ImmuneResponse',
    'AbnormalityType',
    'CheckpointState',
    'ApoptosisPathway',
    'DeathSignal',
    'Apoptosome',
    'ApoptosisResult',
    'CaspaseCascade',
    'ApoptosisStage',
    'AutophagyNetwork',
    'Autophagosome',
    'RecycledFragment',
    'AutophagyResult',
    'mTORKinase',
    'Lysosome',
    'AutophagyLevel',
]
