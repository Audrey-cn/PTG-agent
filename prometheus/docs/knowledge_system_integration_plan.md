# 普罗米修斯知识系统（Prometheus Knowledge System）集成方案 v2

> 目标：构建实用的知识管理系统，命名直观易懂

---

## 一、命名原则

1. **直观性**：名称直接反映功能
2. **一致性**：统一使用中文+英文双语命名
3. **实用性**：避免过于抽象的比喻

---

## 二、系统命名体系

### 2.1 三层架构

```
普罗米修斯知识系统
├── 知识编译层 (Knowledge Compiler Layer)
├── 记忆存储层 (Memory Storage Layer)
└── 网络加速层 (Network Accelerator Layer)
```

### 2.2 概念映射表

#### 知识编译层（原 Wiki Compiler）

| 原项目概念 | 本地化命名 | 说明 |
|-----------|----------|------|
| Wiki Compiler | **知识编译器 (Knowledge Compiler)** | 编译原始素材为结构化知识 |
| raw/ | **素材库 (Source Library)** | 存放原始素材 |
| wiki/ | **知识库 (Knowledge Library)** | 存放编译后的知识 |
| .meta/ | **元数据 (Metadata)** | 存放索引、关联、溯源 |
| Weaver | **知识编织器 (Knowledge Weaver)** | 多文档知识融合 |
| Map-Reduce | **分治处理 (Divide-Conquer)** | 分布式处理范式 |
| LSC 句级溯源 | **引用溯源 (Citation Tracker)** | 逐句引用追踪 |
| Nightly Dreaming | **自动发现 (Auto Discovery)** | 自动发现知识关联 |
| Insight | **洞察 (Insight)** | 自动生成的知识洞察 |
| VK Spec | **PKP 协议** | 普罗米修斯知识协议 |
| maturity | **成熟度 (Maturity)** | 知识成熟程度 |
| stub | **草稿 (Draft)** | 初始状态 |
| draft | **初稿 (Initial)** | 初步整理 |
| reviewed | **已审 (Reviewed)** | 已审核 |
| authoritative | **权威 (Authoritative)** | 权威认证 |

#### 记忆存储层（原 MemPalace）

| 原项目概念 | 本地化命名 | 说明 |
|-----------|----------|------|
| MemPalace | **记忆库 (Memory Bank)** | 结构化记忆存储 |
| Wings | **项目区 (Project Zone)** | 按项目/人分区 |
| Rooms | **主题区 (Topic Zone)** | 按主题分区 |
| Drawers | **存储单元 (Storage Unit)** | 具体内容存储 |
| Temporal Knowledge Graph | **时序图谱 (Timeline Graph)** | 时间关系图谱 |
| Hybrid Retriever | **混合检索器 (Hybrid Searcher)** | 多维度检索 |
| Semantic Search | **语义搜索 (Semantic Search)** | 向量语义搜索 |
| Agent Diary | **Agent日志 (Agent Log)** | Agent专属记录 |

#### 网络加速层（原 Xget）

| 原项目概念 | 本地化命名 | 说明 |
|-----------|----------|------|
| Xget | **网络加速器 (NetAccelerator)** | 网络资源加速 |
| Fallback | **降级访问 (Fallback)** | 失败后直接访问 |
| Load Balancing | **负载均衡 (Load Balance)** | 实例调度 |
| Instance | **加速节点 (Accelerator Node)** | 加速服务节点 |

---

## 三、系统架构

```
普罗米修斯知识系统
├── 知识编译层 (Knowledge Compiler)
│   ├── 素材库 (source/)       → 原始素材
│   ├── 知识库 (knowledge/)    → 编译后知识
│   ├── 元数据 (metadata/)     → 索引、溯源
│   ├── 知识编织器 (Weaver)    → 多文档融合
│   ├── 自动发现 (Discovery)   → 关联发现
│   └── 引用溯源 (Citation)    → 逐句追踪
│
├── 记忆存储层 (Memory Bank)
│   ├── 项目区 (projects/)     → 按项目分区
│   ├── 主题区 (topics/)       → 按主题分区
│   ├── 时序图谱 (timeline/)   → 时间关系
│   ├── 语义搜索 (semantic/)   → 向量搜索
│   └── 混合检索 (hybrid/)     → 多维检索
│
└── 网络加速层 (NetAccelerator)
    ├── 加速节点 (nodes/)      → 节点列表
    ├── 负载均衡 (balance/)    → 调度策略
    └── 降级访问 (fallback/)   → 失败回退
```

---

## 四、成熟度体系

### 4.1 成熟度等级

```
草稿 (Draft)       → 刚收集，未处理
  ↓ 7天自动
初稿 (Initial)     → 初步整理
  ↓ 1次验证
已审 (Reviewed)    → 已审核
  ↓ 3次验证
权威 (Authoritative) → 权威认证
```

### 4.2 成熟度迁移

```python
MATURITY_LEVELS = {
    "draft": {"next": "initial", "auto_days": 7},
    "initial": {"next": "reviewed", "required_reviews": 1},
    "reviewed": {"next": "authoritative", "required_reviews": 3},
    "authoritative": {"next": None}
}
```

---

## 五、文件结构

```
prometheus/
├── tools/
│   ├── knowledge.py           # 现有，升级
│   ├── knowledge_compiler.py  # 新增：知识编译器
│   ├── source_library.py      # 新增：素材库管理
│   ├── citation_tracker.py    # 新增：引用溯源
│   ├── memory_bank.py         # 新增：记忆库
│   ├── timeline_graph.py      # 新增：时序图谱
│   ├── hybrid_searcher.py     # 新增：混合检索
│   └── net_accelerator.py     # 新增：网络加速器
│
├── genes/
│   ├── knowledge_weaver.py    # 新增：知识编织器
│   ├── auto_discovery.py      # 新增：自动发现
│   └── memory_gene.py         # 新增：记忆基因
│
├── cli/
│   └── knowledge_tools.py     # 新增：知识命令
│
└── data/
    ├── source/                # 素材库
    ├── knowledge/             # 知识库
    ├── metadata/              # 元数据
    └── memory/                # 记忆库
        ├── projects/          # 项目区
        ├── topics/            # 主题区
        └── timeline.db        # 时序图谱
```

---

## 六、核心类设计

### 6.1 知识编译器

```python
class KnowledgeCompiler:
    """知识编译器 - 编译原始素材为结构化知识"""
    
    def compile_source(self, source_id: str) -> str:
        """编译单个素材"""
        
    def compile_batch(self, source_ids: List[str]) -> List[str]:
        """批量编译"""
        
    def get_maturity(self, knowledge_id: str) -> str:
        """获取成熟度"""
        
    def upgrade_maturity(self, knowledge_id: str) -> bool:
        """升级成熟度"""
```

### 6.2 知识编织器

```python
class KnowledgeWeaver:
    """知识编织器 - 多文档知识融合"""
    
    def divide(self, source_ids: List[str]) -> List[Fragment]:
        """分治：拆分素材"""
        
    def conquer(self, fragments: List[Fragment]) -> Knowledge:
        """聚合：融合知识"""
        
    def add_citation(self, sentence: str, source_id: str) -> str:
        """添加引用"""
```

### 6.3 记忆库

```python
class MemoryBank:
    """记忆库 - 结构化记忆存储"""
    
    def create_project_zone(self, project_name: str) -> str:
        """创建项目区"""
        
    def create_topic_zone(self, project: str, topic: str) -> str:
        """创建主题区"""
        
    def store(self, project: str, topic: str, content: str) -> str:
        """存储内容"""
        
    def search(self, query: str, project: str = None) -> List[Result]:
        """搜索记忆"""
```

### 6.4 网络加速器

```python
class NetAccelerator:
    """网络加速器 - 网络资源加速访问"""
    
    def accelerate(self, url: str) -> str:
        """加速访问URL"""
        
    def select_node(self) -> AcceleratorNode:
        """选择加速节点"""
        
    def fallback_access(self, url: str) -> Response:
        """降级直接访问"""
```

---

## 七、命令接口

```bash
# 知识编译
/kc-compile              # 编译素材
/kc-weave --sources "a.md,b.md"  # 编织知识
/kc-discover             # 自动发现

# 记忆存储
/mb-create-project "my-project"
/mb-store "my-project" "topic" "content"
/mb-search "query"

# 网络加速
/na-fetch "https://github.com/..."
/na-status               # 查看节点状态
```

---

## 八、配置文件

```yaml
# 知识编译器配置
knowledge_compiler:
  enabled: true
  base_dir: "~/.prometheus/knowledge"
  maturity:
    draft_to_initial_days: 7
    initial_to_reviewed_required: 1
    reviewed_to_authoritative_required: 3
  weaver:
    max_sources_per_run: 20
    citation_required: true
  discovery:
    enabled: true
    scheduled_hour: 2

# 记忆库配置
memory_bank:
  enabled: true
  base_dir: "~/.prometheus/memory"
  backend: "chromadb"
  embedding_model: "all-MiniLM-L6-v2"
  searcher:
    keyword_boost: 2.0
    temporal_boost: 1.5

# 网络加速器配置
net_accelerator:
  enabled: true
  default_node: "https://accelerator.example.com"
  fallback_enabled: true
  timeout_seconds: 30
  max_retries: 3
  nodes:
    - url: "https://node1.example.com"
      priority: 0
      weight: 3
```

---

## 九、分阶段实施

| 阶段 | 功能 | 时间 |
|------|------|------|
| 一 | 素材库 + 知识库存储 | 1-2天 |
| 二 | 知识编译器核心 | 3-4天 |
| 三 | 记忆库结构 | 3-4天 |
| 四 | 自动发现 + 集成 | 2-3天 |
| 五 | 网络加速器更名 | 1天 |
| 六 | Agent集成 | 2天 |
| **总计** | | **12-16天** |

---

## 十、命名对比总结

| 层级 | v1抽象命名 | v2实用命名 |
|------|----------|----------|
| 第一层 | 知识熔炉 | **知识编译器** |
| 第二层 | 记忆宫殿 | **记忆库** |
| 第三层 | 星桥 | **网络加速器** |
| 原始素材 | 矿石库 | **素材库** |
| 处理后知识 | 知识库 | **知识库** |
| 元数据 | 铸痕库 | **元数据** |
| 成熟度 | 纯度 | **成熟度** |
| 等级 | 原矿/粗炼/精炼/纯金 | **草稿/初稿/已审/权威** |

---

*方案版本：v2*
*创建时间：2026-04-30*
*命名风格：直观实用*
