---
project: prometheus
version: "1.0"
type: tools_manifest
---

# TOOLS.md · 工具清单

> 以下是普罗米修斯当前启用的工具模块。工具状态可在初始化或配置时调整。

## 核心工具

### 记忆系统 (Memory System)
- **层级**: 工作记忆(8K tokens) / 情景记忆(16K) / 长期记忆(32K)
- **存储**: MD文件 + SQLite混合双写
- **检索**: FTS5全文搜索 + 语义向量检索
- **配置**: `memory/config.json`
- **状态**: ✅ 已启用

### 知识编译器 (Knowledge Compiler)
- **管线**: 蒸馏(Distill) → 汇聚(Converge) → 合成(Synthesize)
- **引用追踪**: 句级 `((source_id))` 标注
- **自动发现**: 巡逻遗忘源、发现跨域连接、晶化洞察
- **配置**: `compiler/`
- **状态**: ✅ 已启用

### 种子编辑 (Seed Editor)
- **功能**: 知识种子的创建/编辑/删除/演化
- **基因工程**: 通过基因标签进行知识修正
- **配置**: `seeds/`
- **状态**: ✅ 已启用

### 网络加速 (Network Accelerator)
- **功能**: 多节点负载均衡 + 自动fallback
- **支持平台**: GitHub / GitLab / HuggingFace / PyPI / npm
- **配置**: `accelerator/`
- **状态**: ✅ 已启用

## 辅助工具

### 语义字典 (Semantic Dictionary)
- **功能**: 术语定义、同义词映射、领域词表
- **状态**: ✅ 已启用

### 自修正 (Self-Correction)
- **功能**: 输出反思、逻辑验证、二次校正
- **状态**: ✅ 已启用

### 备份恢复 (Backup & Restore)
- **功能**: 日备份(30天保留) + 时备份(24小时保留) + 手动BAK
- **状态**: ✅ 已启用
