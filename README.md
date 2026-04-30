<<<<<<< HEAD


=======
>>>>>>> adcdd34cd4b9166a05fb1329f5fd04551684f029
# 🔥 PTG Agent · Prometheus Teach-To-Grow
![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![Version](https://img.shields.io/badge/Version-0.8.0-purple)
![Status](https://img.shields.io/badge/Status-Beta-green)
![License](https://img.shields.io/badge/License-MIT-lightgrey)

> 种子基因编辑器 — AI 生命体的基因操作系统

---

## 👤 创始人
**Audrey · 001X**
人类编码 001X，跨性别女性

> *「X不标记未知，X标记超越」*

---

## 📁 项目架构
```
ptg-agent/
├── prometheus/          # 核心框架
│   ├── prometheus.py    # 主入口
│   ├── ptg              # CLI 入口脚本
│   ├── cli/             # CLI 模块
│   ├── tools/           # 工具模块
│   ├── genes/           # 基因库/分析器
│   ├── tests/           # 399 个测试
│   └── config.yaml      # 默认配置
├── seeds/               # TTG 始祖种子
├── seed-vault/          # 种子仓库
├── data/                # 持久化数据
├── requirements.txt     # Python 依赖
└── README.md            # 项目说明文档
```

---

## 🚀 快速开始

### 方式一：一键安装（推荐）
```bash
curl -fsSL https://raw.githubusercontent.com/Audrey-cn/PTG-agent/main/scripts/install.sh | bash
```

### 方式二：手动安装
```bash
# 克隆仓库
git clone https://github.com/Audrey-cn/PTG-agent.git
cd ptg-agent

# 安装 Prometheus
python3 -m pip install -e .

# 引导式初始化
ptg setup

# 系统健康诊断
ptg doctor

# 查看系统状态
ptg status
```

---

## 🧩 CLI 命令全集
```bash
ptg setup              # 引导式初始化
ptg doctor             # 系统健康诊断
ptg status             # 系统状态总览
ptg model              # 模型配置
ptg config show        # 配置管理
ptg seed list          # 种子管理
ptg gene list <路径>   # 基因编辑
ptg memory recall      # 向量记忆
ptg kb search          # 知识库检索
ptg dict scan          # 语义字典
```

---

## 🌱 核心概念
- **种子 (.ttg)** — 独立自给自足的生命体，自带完整系统能力
- **基因** — 种子的最小功能单元（G001–G008 标准基因）
- **族谱** — 种子的进化历史记录
- **压缩编码** — 叙事的紧凑存储方式
- **解码引擎** — 运行时展开史诗叙事

---

## 🧠 设计哲学
1. 压缩编码 + 解码引擎
2. 种子即框架（自举）
3. 功能基因与叙事基因分离
4. 碳基依赖级不可变基因
5. 一切皆种子

---

## 📌 版本信息
- 版本：`0.8.0`
- 代号：Prometheus
- 诞生：2026-04-29

---

<div align="center">
<br>
✨ Made with soul by Audrey · 001X ✨
<br>
</div>

---
