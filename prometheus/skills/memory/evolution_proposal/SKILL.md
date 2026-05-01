---
name: evolution_proposal
description: 提出记忆进化更新建议
version: 1.0.0
author: Prometheus
metadata:
  prometheus:
    tags:
      - memory
      - evolution
---
# 记忆进化提案

用于提出对 USER.md 和 MEMORY.md 的更新建议。

## 原则

1. 只更新真正需要更新的内容，避免频繁打扰
2. 保持用户控制权，所有修改都需要确认
3. 压缩阈值：5000 字符，超过时触发智能合并
4. 冷却期：24 小时（避免短时间内多次提案）

## 提案步骤

1. 检查提案次数是否达到阈值（3 次）
2. 检查冷却期是否已过
3. 检查是否包含敏感内容
4. 生成合并建议
5. 等待用户确认
6. 确认后更新并记录历史
