# 🔥 PTG Agent · Prometheus Teach-To-Grow
![Python](https://img.shields.io/badge/Python-3.11%2B-blue)
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

## 📁 项目架构
```
ptg-agent/
├── prometheus/          # 核心框架
│   ├── prometheus.py    # 主入口
│   ├── cli/             # CLI 模块
│   ├── tools/           # 工具模块
│   ├── genes/           # 基因库/分析器
│   ├── channels/        # 消息平台集成
│   ├── memory/          # 记忆系统
│   └── config.yaml      # 默认配置
├── seeds/               # TTG 始祖种子
├── seed-vault/          # 种子仓库
├── scripts/             # 安装脚本
│   └── install.sh       # 跨平台一键安装
├── constraints-termux.txt  # Termux 依赖约束
├── pyproject.toml       # 现代 Python 打包
└── README.md            # 项目说明文档
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

## 🎯 新增功能（0.8.0）

### 🌍 多系统兼容支持
- ✅ **Termux (Android)**：原生支持 Android Termux 环境
- ✅ **macOS**：完整支持 Homebrew 和 Shell 集成
- ✅ **Linux**：支持所有主流发行版（Ubuntu/Debian/Fedora/Arch/WSL）
- ✅ **Root Install**：支持 FHS 标准布局的系统级安装

### ⚡ 安装系统升级
- 📦 **uv 集成**：桌面/服务器使用 uv 高速包管理器
- 🔧 **Termux 适配**：使用 pkg 包管理器和 venv
- 🔄 **自动降级**：安装失败时自动降级到基础功能
- 🐚 **多 Shell 支持**：zsh、bash、fish 自动检测和配置
- 🌐 **SSH/HTTPS 双重尝试**：克隆仓库时自动降级

### 📦 依赖系统优化
- 📜 **constraints-termux.txt**：Termux 专用依赖约束
- 🧩 **termux 可选组**：pyproject.toml 新增 termux 可选依赖
- 🚀 **all 全功能组**：桌面端完整功能集
- ⚡ **智能选择**：根据平台自动选择最佳安装方式

### 🛠️ 系统检测增强
- 🔍 **Termux 检测**：通过 `TERMUX_VERSION` 和 `PREFIX` 双重验证
- 🐧 **WSL 检测**：识别 Windows Subsystem for Linux
- 📦 **容器检测**：识别 Docker 和其他容器环境

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
6. 新模块与 Hermes 重叠时优先集成已有能力

---

## 📌 版本信息
- 版本：`0.8.0`
- 代号：Prometheus
- 诞生：2026-04-29
- 更新：2026-05-01

---

<div align="center">
<br>
✨ Made with soul by Audrey · 001X ✨
<br>
</div>

---
