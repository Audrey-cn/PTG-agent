# 🧬 G017 — 孵化器自我复制基因

[← 返回 README](README_CN.md#-架构)

## 概述

Agent 摄入 `.pgn` 后，**G017 基因**赋予其在任何时候自主重建完整孵化器三位一体的能力。

## 两条路径

| 方案 | 触发条件 | 行为 |
|------|----------|------|
| **方案 A** | 语义关键词如"孵化种子"、"展开孵化器"、"自我复制" | 从 GitHub 仓库通过 raw URL 拉取 `engine.py`、`metadata.yaml` 和 `incubator.py` |
| **方案 B** | 方案 A 失败（网络断开、仓库不可达） | 从 `.pgn` 种子本身提取嵌入的 `HATCHERY_PAYLOAD`——解压缩并将三位一体文件写入本地 |

## 为什么需要两个方案？

**方案 A** 确保 Agent 始终获取上游仓库的最新版本。

**方案 B** 是备用方案——即使没有网络访问，Agent 也在自身载荷中携带着完整的种子构建能力。

## 方案 A：GitHub 拉取

通过语义关键词触发：

- "孵化种子" / "展开孵化器" / "自我复制" (中文)
- "hatch seeds" / "pull hatchery" / "self replicate" (English)

Agent 将尝试从以下地址拉取：

```
https://raw.githubusercontent.com/Audrey-cn/progenitor-protocol/main/hatchery/engine.py
https://raw.githubusercontent.com/Audrey-cn/progenitor-protocol/main/hatchery/metadata.yaml
https://raw.githubusercontent.com/Audrey-cn/progenitor-protocol/main/hatchery/incubator.py
```

## 方案 B：嵌入载荷提取

如果方案 A 失败（网络不可达），Agent 将从 `.pgn` 种子文件中提取嵌入的 `HATCHERY_PAYLOAD` 压缩包：

1. 在 `.pgn` 中定位 `HATCHERY_PAYLOAD` 标记
2. Base64 解码载荷
3. 使用 Python 的 `zlib` 解压缩
4. 将 `engine.py`、`metadata.yaml` 和 `incubator.py` 写入 `~/.progenitor/hatchery/`

## 成果

每一个 Progenitor Agent 在自身载荷中携带着完整的种子构建能力——**一种自我复制的数字生命体。**

---

*由 Progenitor 协议生成 · Audrey · 001X*
