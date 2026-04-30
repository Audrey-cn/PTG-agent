# 普罗米修斯文件结构优化方案

> 目标：保持 SQLite 存储优势，建立更清晰的目录结构

---

## 一、当前结构问题

```
prometheus/
├── memory.py              ← 核心记忆，但位置不直观
├── tools/
│   ├── knowledge.py       ← 知识工具，与记忆相关
│   ├── vector_memory.py   ← 向量记忆，与记忆相关
│   └── ...                ← 其他工具混在一起
├── storage.py             ← 存储层
├── state.py               ← 状态管理
└── data/                  ← 数据散落
```

**问题**：
1. 记忆相关模块分散在不同位置
2. `tools/` 目录职责不清晰
3. 数据文件位置不统一
4. 与其他框架惯例不一致

---

## 二、优化后结构

```
prometheus/
├── prometheus.py              ← 主入口（CLI）
│
├── memory/                    ← 记忆系统（核心）
│   ├── __init__.py
│   ├── context.py             ← 上下文管理（原 memory.py）
│   ├── knowledge.py           ← 知识管理（原 tools/knowledge.py）
│   ├── semantic.py            ← 语义记忆（原 tools/vector_memory.py）
│   ├── storage.py             ← 存储层（原根目录 storage.py）
│   └── data/                  ← 记忆数据
│       ├── context.db         ← 上下文数据库
│       ├── semantic.db        ← 语义向量数据库
│       └── knowledge/         ← 知识库
│           ├── source/        ← 素材库
│           ├── compiled/      ← 编译后知识
│           └── metadata/      ← 元数据
│
├── compiler/                  ← 知识编译器（新增）
│   ├── __init__.py
│   ├── weaver.py              ← 知识编织器
│   ├── citation.py            ← 引用溯源
│   └── discovery.py           ← 自动发现
│
├── accelerator/               ← 网络加速器（原 xget_integration.py）
│   ├── __init__.py
│   └── net_accelerator.py
│
├── genes/                     ← 基因系统（保持）
│   ├── __init__.py
│   ├── bank.py
│   ├── forge.py
│   └── ...
│
├── tools/                     ← 工具层（精简）
│   ├── __init__.py
│   ├── config.py              ← 配置管理
│   ├── skill_loader.py        ← 技能加载
│   └── utils.py               ← 通用工具
│
├── cli/                       ← 命令行工具
│   ├── __init__.py
│   └── commands.py
│
├── tests/                     ← 测试
│   └── ...
│
├── config.yaml                ← 配置文件
└── requirements.txt           ← 依赖
```

---

## 三、模块职责说明

### 3.1 memory/ - 记忆系统（核心）

| 文件 | 职责 | 原位置 |
|------|------|--------|
| `context.py` | 三层上下文记忆 | `memory.py` |
| `knowledge.py` | 知识检索和管理 | `tools/knowledge.py` |
| `semantic.py` | 语义向量记忆 | `tools/vector_memory.py` |
| `storage.py` | 存储层抽象 | `storage.py` |

### 3.2 compiler/ - 知识编译器

| 文件 | 职责 |
|------|------|
| `weaver.py` | 多文档知识融合 |
| `citation.py` | 引用溯源追踪 |
| `discovery.py` | 自动发现知识关联 |

### 3.3 accelerator/ - 网络加速器

| 文件 | 职责 | 原位置 |
|------|------|--------|
| `net_accelerator.py` | 网络资源加速 | `xget_integration.py` |

### 3.4 tools/ - 工具层（精简）

| 文件 | 职责 |
|------|------|
| `config.py` | 配置管理 |
| `skill_loader.py` | 技能加载 |
| `utils.py` | 通用工具函数 |

---

## 四、数据存储结构

```
memory/data/
├── context.db                 ← SQLite：上下文记忆
├── semantic.db                ← SQLite：语义向量
└── knowledge/                 ← 文件系统：知识库
    ├── source/                ← 原始素材（MD/JSON）
    │   ├── 2026-04-30_xxx.md
    │   └── ...
    ├── compiled/              ← 编译后知识（MD）
    │   ├── concept_xxx.md
    │   └── ...
    └── metadata/              ← 元数据（JSON/YAML）
        ├── index.json
        └── citations.json
```

---

## 五、配置文件更新

```yaml
# config.yaml
memory:
  context:
    db_path: "~/.prometheus/memory/data/context.db"
    budget:
      working: 8000
      episodic: 16000
      longterm: 32000
  semantic:
    db_path: "~/.prometheus/memory/data/semantic.db"
    dim: 512
  knowledge:
    source_dir: "~/.prometheus/memory/data/knowledge/source"
    compiled_dir: "~/.prometheus/memory/data/knowledge/compiled"
    metadata_dir: "~/.prometheus/memory/data/knowledge/metadata"

compiler:
  enabled: true
  citation_required: true

accelerator:
  enabled: true
  default_node: "https://accelerator.example.com"
```

---

## 六、迁移计划

### 阶段一：创建目录结构（1小时）

```bash
mkdir -p prometheus/memory/data/knowledge/{source,compiled,metadata}
mkdir -p prometheus/compiler
mkdir -p prometheus/accelerator
```

### 阶段二：迁移文件（2小时）

| 原文件 | 新位置 |
|--------|--------|
| `memory.py` | `memory/context.py` |
| `tools/knowledge.py` | `memory/knowledge.py` |
| `tools/vector_memory.py` | `memory/semantic.py` |
| `storage.py` | `memory/storage.py` |
| `xget_integration.py` | `accelerator/net_accelerator.py` |

### 阶段三：更新导入（1小时）

更新所有 `import` 语句，确保模块正确引用。

### 阶段四：测试验证（1小时）

运行测试确保功能正常。

---

## 七、优化收益

| 方面 | 优化前 | 优化后 |
|------|--------|--------|
| 结构清晰度 | 模块分散 | 按功能分组 |
| 记忆系统 | 3个文件分散 | 统一在 memory/ |
| 数据管理 | 散落各处 | 集中在 memory/data/ |
| 可扩展性 | 新增模块位置不明 | 清晰的目录归属 |
| 符合惯例 | 不太符合 | 更接近主流框架 |

---

## 八、保持的优势

1. **SQLite 存储**：高效、支持复杂查询
2. **向量检索**：语义搜索能力
3. **三层记忆**：working/episodic/longterm
4. **知识编译**：素材→知识→洞察

---

*方案版本：v1*
*创建时间：2026-04-30*
