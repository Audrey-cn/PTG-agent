---
name: doctor_quick_fix
description: 快速修复 Prometheus 系统配置（守门员模式）
version: 1.0.0
author: Prometheus
metadata:
  hermes:
    tags:
      - system
      - repair
      - doctor
---
# Doctor 快速修复

当 Prometheus 无法启动时使用这个技能。

## 步骤

1. 运行 `ptg doctor` 检查问题
2. 如果 config.yaml 有问题，运行 `ptg doctor --fix`
3. 如果还不行，运行 `ptg doctor --emergency`
4. 检查 doctor 的备份目录：`~/.prometheus/doctor_backups/`

## 关键点

- Doctor 只负责修复启动必需的文件（config.yaml, SOUL.md）
- 其他问题等 Agent 启动后通过自然语言对话解决
- 所有修复都会先备份原文件
