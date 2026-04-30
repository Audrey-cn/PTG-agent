# Wiki Compiler + MemPalace 本地化集成方案

> 目标：将 Wiki Compiler 和 MemPalace 的核心能力本地化集成到普罗米修斯 Agent 中

---

## 一、项目分析

### 1. Wiki Compiler 核心能力

**核心功能：**
- Map-Reduce 知识提炼范式
- 句级溯源（LSC）引文系统
- Nightly Dreaming 跨领域弱连接发现
- Weaver 2.1 精准综述
- 幂等增量编译（哈希防重叠）

**目录结构：**
```
raw/    → 原始素材
wiki/   → 编译后的知识
.meta/  → 元数据（成熟度、关联、引文）
```

**VK Spec 1.0：**
- 成熟度模型：stub → draft → reviewed → authoritative
- 强制目录拓扑
- 溯源格式：`[[引文]]`

---

### 2. MemPalace 核心能力

**核心功能：**
- 本地优先语义检索（96.6% R@5）
- 宫殿式结构化存储
  - Wings（人/项目）
  - Rooms（主题）
  - Drawers（内容）
- 时间知识图谱（SQLite）
- 可插拔向量后端（ChromaDB）
- 29个MCP工具
- 每个Agent独立wing和diary

**架构特点：**
- 零API调用
- 全文存储不摘要
- 关键词+语义+时间混合搜索

---

## 二、普罗米修斯现状分析

### 现有模块

| 模块 | 功能 | 可扩展点 |
|------|------|---------|
| `tools/knowledge.py` | 知识搜索、管理 | 可升级为完整知识系统 |
| `tools/vector_memory.py` | 向量记忆 | 可集成到知识图谱 |
| `memory.py` | 对话记忆 | 可扩展为宫殿结构 |
| `storage.py` | 存储层 | 可扩展raw/wiki/.meta |
| `state.py` | 状态管理 | 可扩展成熟度跟踪 |
| `reflection.py` | 反思系统 | 可扩展Nightly Dreaming |

---

## 三、本地化集成方案

### 📦 整体架构

```
普罗米修斯知识系统
├── Wiki Compiler 层
│   ├── raw/    → 原始素材（来自用户输入、对话、文件）
│   ├── wiki/   → 编译后的知识（成熟度追踪）
│   ├── .meta/  → 元数据（引文、关联、哈希）
│   ├── Weaver (Map-Reduce)
│   ├── Nightly Dreaming
│   └── LSC 溯源系统
│
├── MemPalace 层
│   ├── Palace Storage
│   │   ├── Wings（人/项目）
│   │   ├── Rooms（主题）
│   │   └── Drawers（内容）
│   ├── Temporal Knowledge Graph
│   ├── Semantic Search（ChromaDB）
│   └── Hybrid Retriever
│
└── Xget 层（已集成）
    ├── GitHub 加速
    ├── Fallback 机制
    └── 多实例路由
```

---

## 四、分阶段实施方案

### 🎯 阶段一：基础存储层（1-2天）

**目标：** 建立 Wiki Compiler 的三层拓扑

**任务清单：**

1. **扩展 storage.py**
   - 添加 `StorageLayer` 类
   - 实现 `raw/`, `wiki/`, `.meta/` 目录结构
   - 实现幂等哈希防重叠机制
   - 新增方法：
     ```python
     class StorageLayer:
         def put_raw(self, content, source) -> str
         def get_raw(self, id) -> str
         def put_wiki(self, title, content, maturity) -> str
         def put_meta(self, id, metadata)
         def incremental_hash_scan(self) -> List[str]
     ```

2. **扩展 state.py**
   - 添加 `MaturityTracker` 类
   - 实现成熟度状态机：`stub` → `draft` → `reviewed` → `authoritative`
   - 新增方法：
     ```python
     class MaturityTracker:
         def get_maturity(self, id) -> str
         def transition_maturity(self, id, from_state, to_state)
         def list_stale(self, days=30) -> List[str]
     ```

3. **创建 tools/wiki_store.py**
   - 实现基础知识存储接口
   - 集成 `StorageLayer` 和 `MaturityTracker`

---

### 🎯 阶段二：Wiki Compiler 核心（3-4天）

**目标：** 实现 Map-Reduce 知识提炼和句级溯源

**任务清单：**

1. **创建 genes/wiki_weaver.py**
   - 实现 Map 阶段：提取关键实体、引文、观点
   - 实现 Reduce 阶段：聚类共识、发现分歧
   - 实现 Synthesis 阶段：生成句级溯源文档
   ```python
   class WikiWeaver:
       def map(self, raw_ids: List[str]) -> List[Entity]
       def reduce(self, entities: List[Entity]) -> ClusteredViews
       def synthesize(self, views: ClusteredViews) -> WikiArticle
       def add_citation(self, sentence: str, source_id: str) -> str
   ```

2. **创建 genes/wiki_compiler.py**
   - 实现增量编译逻辑
   - 与 Weaver 集成
   - 新增基因：`wiki_compiler_core`

3. **创建 tools/lsc_system.py**
   - 句级溯源系统
   - 引文索引管理
   ```python
   class LSCSystem:
       def index_citation(self, wiki_id, sentence_idx, source_id)
       def get_sources(self, wiki_id) -> List[str]
       def validate_citations(self, wiki_id) -> List[Violation]
   ```

---

### 🎯 阶段三：MemPalace 宫殿结构（3-4天）

**目标：** 实现 Wings/Rooms/Drawers 存储结构

**任务清单：**

1. **创建 tools/palace.py**
   ```python
   class MemPalace:
       def create_wing(self, wing_name: str, wing_type: str)  # wing_type: "person" | "project"
       def create_room(self, wing_name: str, room_topic: str)
       def create_drawer(self, wing_name: str, room_name: str, drawer_id: str, content: str)
       
       def search(self, query: str, wing: Optional[str] = None, room: Optional[str] = None)
       
       # 知识图谱方法
       def add_entity(self, entity: Entity, valid_from: datetime)
       def add_relation(self, from_id: str, to_id: str, relation: str)
       def get_timeline(self, entity_id: str)
       def invalidate_entity(self, entity_id: str, invalid_at: datetime)
   ```

2. **扩展 tools/vector_memory.py**
   - 集成 ChromaDB
   - 实现混合搜索（语义 + 关键词 + 时间）
   ```python
   class HybridRetriever:
       def retrieve(self, query, k=20)
       def keyword_boost(self, results)
       def temporal_boost(self, results)
   ```

3. **创建 tools/kgraph.py**
   - 基于 SQLite 的时间知识图谱
   - 实体、关系、有效性窗口

---

### 🎯 阶段四：Nightly Dreaming + 集成（2-3天）

**目标：** 实现跨领域弱连接发现和系统集成

**任务清单：**

1. **创建 genes/nightly_dreaming.py**
   ```python
   class NightlyDreaming:
       def patrol(self) -> List[ForgottenData]
       def find_weak_connections(self, wiki_ids: List[str]) -> List[Connection]
       def crystalize_insight(self, connections: List[Connection]) -> Insight
   ```

2. **扩展 reflection.py**
   - 集成 Nightly Dreaming 到反思循环
   - 新增 `/wiki-dream` 指令

3. **创建 cli/wiki_tools.py**
   - 实现命令行工具
   ```bash
   /wiki-compiler  # 增量编译
   /wiki-dream     # 夜间沉思
   /wiki-weaver --files "A.md,B.md"  # 精准综述
   ```

4. **创建 genes/mempalace_gene.py**
   - 将 MemPalace 集成到基因系统
   - 新增基因：`mempalace_memory`

---

### 🎯 阶段五：Agent 集成与工具（2天）

**目标：** 集成到 Agent 和 MCP

**任务清单：**

1. **扩展 tools.py**
   - 添加 Wiki Compiler 工具
   - 添加 MemPalace 工具

2. **创建 mcp/mempalace_mcp.py**
   - 实现 29 个 MCP 工具的核心子集

3. **扩展 prometheus.py**
   - 配置 Wiki Compiler 和 MemPalace 的初始化
   - 集成到 Agent 生命周期

---

## 五、配置更新

### config.yaml 新增配置

```yaml
# Wiki Compiler 配置
wiki_compiler:
  enabled: true
  base_dir: "~/.prometheus/wiki"
  maturity:
    stub_to_draft_days: 7
    draft_to_reviewed_required: 1
    reviewed_to_authoritative_required: 3
  weaver:
    max_files_per_run: 20
    citation_required: true
  dreaming:
    enabled: true
    scheduled_hour: 2
    min_stale_days: 14

# MemPalace 配置
mempalace:
  enabled: true
  base_dir: "~/.prometheus/palace"
  backend: "chromadb"
  embedding_model: "all-MiniLM-L6-v2"
  hybrid_search:
    keyword_boost: 2.0
    temporal_boost: 1.5
    rerank_with_llm: false
  kgraph:
    enabled: true
    sqlite_path: "~/.prometheus/palace/kgraph.sqlite"
```

---

## 六、文件结构

```
prometheus/
├── tools/
│   ├── knowledge.py          # 现有，升级
│   ├── vector_memory.py      # 现有，升级
│   ├── wiki_store.py         # 新增：Wiki 存储
│   ├── lsc_system.py         # 新增：句级溯源
│   ├── palace.py             # 新增：宫殿结构
│   ├── kgraph.py             # 新增：时间知识图谱
│   └── hybrid_retriever.py   # 新增：混合检索
│
├── genes/
│   ├── wiki_weaver.py        # 新增：Map-Reduce 综述
│   ├── wiki_compiler.py      # 新增：编译核心
│   ├── nightly_dreaming.py   # 新增：夜间沉思
│   └── mempalace_gene.py     # 新增：MemPalace 集成
│
├── cli/
│   └── wiki_tools.py         # 新增：Wiki 命令工具
│
├── docs/
│   └── wiki_compiler_mempalace_integration_plan.md  # 本文件
│
└── tools/data/
    ├── wiki/
    │   ├── raw/
    │   ├── wiki/
    │   └── .meta/
    └── palace/
        ├── wings/
        ├── kgraph.sqlite
        └── chromadb/
```

---

## 七、依赖更新

### requirements.txt 新增

```
# Wiki Compiler
pyyaml>=6.0
python-multipart>=0.0.6

# MemPalace
chromadb>=0.4.0
sentence-transformers>=2.2.0
scikit-learn>=1.3.0
```

---

## 八、测试计划

### 测试文件

```
prometheus/tests/
├── test_wiki_store.py
├── test_lsc_system.py
├── test_weaver.py
├── test_palace.py
├── test_kgraph.py
├── test_hybrid_retriever.py
└── test_nightly_dreaming.py
```

---

## 九、时间表

| 阶段 | 功能 | 预计时间 |
|------|------|---------|
| 一 | 基础存储层 | 1-2天 |
| 二 | Wiki Compiler 核心 | 3-4天 |
| 三 | MemPalace 宫殿结构 | 3-4天 |
| 四 | Nightly Dreaming + 集成 | 2-3天 |
| 五 | Agent 集成与工具 | 2天 |
| **总计** | **完整集成** | **11-15天** |

---

## 十、风险与缓解

| 风险 | 缓解措施 |
|------|---------|
| 依赖冲突 | 虚拟环境 + 版本锁定 |
| 性能问题 | 增量处理 + 索引优化 |
| 存储膨胀 | 成熟度清理 + 去重机制 |
| 复杂性过高 | 分阶段集成 + 充分测试 |

---

## 十一、与现有模块的集成点

### 1. knowledge.py 升级
- 作为统一入口
- 调用 Wiki Compiler 和 MemPalace

### 2. reflection.py 集成
- Nightly Dreaming 作为反思的一部分

### 3. memory.py 扩展
- 对话自动存入 Palace

### 4. genes/ 系统
- 新增相关基因

---

## 十二、下一步行动

1. **确认方案**
2. **开始阶段一：基础存储层**
3. **逐步推进到阶段五**

---

*方案创建时间：2026-04-30*
*适用版本：普罗米修斯 Agent v1.0*
