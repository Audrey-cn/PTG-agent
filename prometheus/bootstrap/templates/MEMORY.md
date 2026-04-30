---
project: prometheus
version: "1.0"
type: memory_structure
---

# MEMORY.md · 记忆结构

## 三层记忆模型

### 工作记忆 (Working Memory)
- **容量**: 8,000 tokens
- **生命周期**: 当前会话
- **衰减策略**: 基于时间的指数衰减
- **用途**: 当前对话上下文、临时推理结果
- **存储路径**: `~/.prometheus/memory/working/`

### 情景记忆 (Episodic Memory)
- **容量**: 16,000 tokens
- **生命周期**: 跨会话保留
- **衰减策略**: 时间衰减 + 重要性加权
- **用途**: 近期交互历史、任务上下文、决策轨迹
- **存储路径**: `~/.prometheus/memory/episodic/`

### 长期记忆 (Long-term Memory)
- **容量**: 32,000 tokens
- **生命周期**: 永久保留
- **衰减策略**: 仅手动删除
- **用途**: 核心知识、用户画像、系统配置、关键洞察
- **存储路径**: `~/.prometheus/memory/longterm/`

## 存储架构

```
~/.prometheus/memory/
├── working/           # 工作记忆MD文件
│   └── *.md
├── episodic/          # 情景记忆MD文件
│   └── *.md
├── longterm/          # 长期记忆MD文件
│   └── *.md
├── vector/            # 向量嵌入索引
│   └── *.npy
├── memories.db        # SQLite主数据库(含FTS5索引)
├── memories.db-wal    # WAL日志
└── memories.db-shm    # 共享内存文件
```

## 记忆同步

- **MD → SQLite**: 从MD文件读取新/修改记录，同步到SQLite
- **SQLite → MD**: 从SQLite查询结果，同步回MD文件
- **冲突解决**: 以MD文件的 `updated_at` 时间戳为准
- **完整性校验**: `verify_integrity()` 对比MD与SQLite记录数

## 备份策略

- **日备份**: 每天凌晨2点，保留30天 → `backups/daily/`
- **时备份**: 每小时，保留24小时 → `backups/hourly/`
- **手动备份**: 用户触发，永久保留 → `backups/manual/`
