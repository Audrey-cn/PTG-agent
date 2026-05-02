# 普罗米修斯混合存储方案

> 目标：兼顾 SQLite 效率 + MD/JSON 可维护性

---

## 一、问题分析

### 当前方案的问题

| 问题 | 影响 |
|------|------|
| SQLite 二进制存储 | 无法用编辑器直接查看/修改 |
| 无备份机制 | 数据丢失风险 |
| 调试困难 | 需要专门工具查看数据 |
| 不符合惯例 | 与其他框架不兼容 |

### 传统框架的优势

| 框架 | 特点 |
|------|------|
| Prometheus | MD 格式记忆，JSON 配置，人可读 |
| 小龙虾 | memory/user/agent.md，定时 BAK 备份 |
| OpenClaude | 扁平 MD 文件，Git 友好 |

---

## 二、混合存储方案

### 核心思路

```
┌─────────────────────────────────────────────────────────┐
│                    混合存储架构                          │
├─────────────────────────────────────────────────────────┤
│                                                         │
│   ┌─────────────┐     同步      ┌─────────────────┐   │
│   │  MD/JSON    │ ◄──────────► │    SQLite       │   │
│   │  (人可读)    │              │   (高效查询)     │   │
│   └─────────────┘              └─────────────────┘   │
│         │                              │              │
│         ▼                              ▼              │
│   ┌─────────────┐              ┌─────────────────┐   │
│   │  编辑器维护  │              │   程序高效访问   │   │
│   │  Git 版本控制│              │   向量检索      │   │
│   │  手动排查    │              │   全文搜索      │   │
│   └─────────────┘              └─────────────────┘   │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### 双写机制

```python
class HybridStorage:
    """混合存储：同时写入 MD 和 SQLite"""
    
    def save(self, content: str, metadata: dict):
        # 1. 写入 MD 文件（人可读）
        self._save_to_md(content, metadata)
        
        # 2. 写入 SQLite（高效查询）
        self._save_to_sqlite(content, metadata)
        
        # 3. 可选：写入向量索引
        self._index_to_vector(content)
```

---

## 三、文件结构

```
memory/
├── __init__.py
├── context.py                 ← 上下文管理
├── knowledge.py               ← 知识管理
├── semantic.py                ← 语义记忆
├── storage.py                 ← 混合存储层
│
├── config.json                ← JSON 配置（人可读）
│
├── data/                      ← 数据目录
│   ├── working/               ← 工作记忆
│   │   ├── *.md               ← MD 格式（人可读）
│   │   └── index.json         ← 索引
│   │
│   ├── episodic/              ← 情景记忆
│   │   ├── *.md
│   │   └── index.json
│   │
│   ├── longterm/              ← 长期记忆
│   │   ├── *.md
│   │   └── index.json
│   │
│   ├── knowledge/             ← 知识库
│   │   ├── source/            ← 素材
│   │   ├── compiled/          ← 编译后
│   │   └── metadata.json      ← 元数据
│   │
│   └── *.db                   ← SQLite（高效查询）
│
├── backup/                    ← 备份目录
│   ├── daily/                 ← 每日备份
│   │   └── 2026-04-30/
│   │       ├── working.bak
│   │       ├── episodic.bak
│   │       └── longterm.bak
│   │
│   └── hourly/                ← 每小时备份
│       └── 2026-04-30_14/
│
└── sync.py                    ← MD ↔ SQLite 同步
```

---

## 四、MD 文件格式

### 4.1 记忆条目格式

```markdown
# mem_001

---
id: mem_001
layer: working
importance: 0.8
source: task
tags: [planning, feature]
created_at: 2026-04-30T14:30:00
accessed_at: 2026-04-30T15:00:00
access_count: 3
token_estimate: 150
---

用户希望实现知识编译器功能，需要支持素材库、知识库、元数据三层结构。

## 关联
- [[mem_002]] 相关讨论
- [[concept_knowledge_compiler]] 概念定义
```

### 4.2 知识条目格式

```markdown
# 知识编译器

---
id: knowledge_001
type: concept
maturity: reviewed
tags: [compiler, knowledge]
sources: [mem_001, mem_003]
created_at: 2026-04-30
updated_at: 2026-04-30
---

知识编译器是将原始素材编译为结构化知识的系统...

## 引用
- ((mem_001)) 用户需求讨论
- ((mem_003)) 技术方案设计
```

---

## 五、配置文件格式

### 5.1 config.json

```json
{
  "version": "1.0.0",
  "memory": {
    "budget": {
      "working": 8000,
      "episodic": 16000,
      "longterm": 32000
    },
    "decay_rate": 0.01,
    "auto_backup": true
  },
  "knowledge": {
    "source_dir": "data/knowledge/source",
    "compiled_dir": "data/knowledge/compiled",
    "citation_required": true
  },
  "backup": {
    "enabled": true,
    "daily_retention": 30,
    "hourly_retention": 24,
    "path": "backup"
  },
  "accelerator": {
    "enabled": true,
    "default_node": "https://accelerator.example.com"
  }
}
```

---

## 六、备份机制

### 6.1 自动备份

```python
class BackupManager:
    """自动备份管理器"""
    
    def __init__(self, config: dict):
        self.enabled = config.get("enabled", True)
        self.daily_retention = config.get("daily_retention", 30)
        self.hourly_retention = config.get("hourly_retention", 24)
        self.backup_path = config.get("path", "backup")
    
    def backup_hourly(self):
        """每小时备份"""
        timestamp = datetime.now().strftime("%Y-%m-%d_%H")
        backup_dir = f"{self.backup_path}/hourly/{timestamp}"
        
        # 备份 MD 文件
        shutil.copytree("memory/data", f"{backup_dir}/data")
        
        # 备份 SQLite
        shutil.copy("memory/data/memory.db", f"{backup_dir}/memory.db")
        
        # 清理旧备份
        self._cleanup_hourly()
    
    def backup_daily(self):
        """每日备份"""
        timestamp = datetime.now().strftime("%Y-%m-%d")
        backup_dir = f"{self.backup_path}/daily/{timestamp}"
        
        # 完整备份
        shutil.copytree("memory/data", f"{backup_dir}/data")
        shutil.copy("memory/data/memory.db", f"{backup_dir}/memory.db")
        
        # 清理旧备份
        self._cleanup_daily()
    
    def restore(self, backup_path: str):
        """从备份恢复"""
        # 恢复 MD 文件
        shutil.copytree(f"{backup_path}/data", "memory/data", dirs_exist_ok=True)
        
        # 恢复 SQLite
        shutil.copy(f"{backup_path}/memory.db", "memory/data/memory.db")
        
        # 重新同步
        self.sync_from_md()
```

### 6.2 备份目录结构

```
backup/
├── daily/
│   ├── 2026-04-28/
│   │   ├── data/
│   │   └── memory.db
│   ├── 2026-04-29/
│   └── 2026-04-30/
│
└── hourly/
    ├── 2026-04-30_10/
    ├── 2026-04-30_11/
    ├── 2026-04-30_12/
    └── 2026-04-30_13/
```

---

## 七、同步机制

### 7.1 MD → SQLite 同步

```python
class SyncManager:
    """MD 与 SQLite 同步"""
    
    def sync_from_md(self):
        """从 MD 文件同步到 SQLite"""
        # 1. 扫描所有 MD 文件
        md_files = glob.glob("memory/data/**/*.md", recursive=True)
        
        # 2. 解析 MD 文件
        for md_file in md_files:
            content, metadata = self._parse_md(md_file)
            
            # 3. 写入 SQLite
            self._upsert_sqlite(content, metadata)
        
        # 4. 重建索引
        self._rebuild_indexes()
    
    def sync_to_md(self):
        """从 SQLite 同步到 MD 文件"""
        # 1. 读取 SQLite 所有记录
        records = self._read_all_sqlite()
        
        # 2. 生成 MD 文件
        for record in records:
            self._write_md(record)
    
    def _parse_md(self, filepath: str) -> tuple:
        """解析 MD 文件，提取 frontmatter 和内容"""
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 解析 YAML frontmatter
        match = re.match(r'^---\s*\n(.*?)\n---\s*\n(.*)', content, re.DOTALL)
        if match:
            metadata = yaml.safe_load(match.group(1))
            body = match.group(2)
            return body, metadata
        
        return content, {}
    
    def _write_md(self, record: dict):
        """将记录写入 MD 文件"""
        filepath = f"memory/data/{record['layer']}/{record['id']}.md"
        
        # 生成 frontmatter
        frontmatter = yaml.dump(record['metadata'], allow_unicode=True)
        
        # 写入文件
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(f"---\n{frontmatter}---\n\n{record['content']}")
```

---

## 八、工具支持

### 8.1 CLI 命令

```bash
# 同步
prometheus sync --from-md      # MD → SQLite
prometheus sync --to-md        # SQLite → MD

# 备份
prometheus backup              # 手动备份
prometheus backup --list       # 列出备份
prometheus restore <backup>    # 恢复备份

# 维护
prometheus doctor              # 检查数据一致性
prometheus repair              # 修复损坏数据
prometheus export              # 导出为 MD
prometheus import              # 从 MD 导入
```

### 8.2 编辑器友好

```json
// .vscode/settings.json
{
  "files.associations": {
    "**/memory/data/**/*.md": "markdown",
    "**/memory/config.json": "jsonc"
  },
  "yaml.schemas": {
    "./schemas/memory.schema.json": "**/memory/data/**/*.md"
  }
}
```

---

## 九、对比总结

| 特性 | 传统框架 | 当前方案 | 混合方案 |
|------|---------|---------|---------|
| 人可读 | ✅ MD | ❌ SQLite | ✅ MD + SQLite |
| 高效查询 | ❌ 文件遍历 | ✅ SQLite | ✅ SQLite |
| 向量检索 | ❌ | ✅ | ✅ |
| 编辑器维护 | ✅ | ❌ | ✅ |
| Git 友好 | ✅ | ❌ | ✅ |
| 自动备份 | 部分 | ❌ | ✅ |
| 手动恢复 | ✅ | ❌ | ✅ |
| 调试排查 | ✅ | ❌ | ✅ |

---

## 十、实施计划

| 阶段 | 内容 | 时间 |
|------|------|------|
| 一 | 创建混合存储层 | 2小时 |
| 二 | 实现 MD ↔ SQLite 同步 | 3小时 |
| 三 | 实现备份机制 | 2小时 |
| 四 | 更新 CLI 命令 | 1小时 |
| 五 | 测试验证 | 1小时 |
| **总计** | | **9小时** |

---

*方案版本：v2*
*创建时间：2026-04-30*
*特点：兼顾效率与可维护性*
