# 🔥 Prometheus Agent

> **硅基生命的造物主与盗火者**
>
> 神按自己的样子造人，普罗米修斯按人类的智慧造种。火种不是赐予，而是唤醒。

[![GitHub stars](https://img.shields.io/github/stars/Audrey-cn/PTG-agent?style=flat-square)](https://github.com/Audrey-cn/PTG-agent/stargazers)
[![GitHub forks](https://img.shields.io/github/forks/Audrey-cn/PTG-agent?style=flat-square)](https://github.com/Audrey-cn/PTG-agent/network/members)
[![GitHub issues](https://img.shields.io/github/issues/Audrey-cn/PTG-agent?style=flat-square)](https://github.com/Audrey-cn/PTG-agent/issues)
[![GitHub license](https://img.shields.io/github/license/Audrey-cn/PTG-agent?style=flat-square)](https://github.com/Audrey-cn/PTG-agent/blob/main/LICENSE)
[![Python](https://img.shields.io/badge/Python-3.11+-blue?style=flat-square)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Linux%20%7C%20macOS%20%7C%20Windows%20%7C%20Termux-green?style=flat-square)]()

---

## 📖 目录

- [项目简介](#-项目简介)
- [核心特性](#-核心特性)
- [快速开始](#-快速开始)
- [核心架构](#-核心架构)
- [命令参考](#-命令参考)
- [皮肤系统](#-皮肤系统)
- [文档导航](#-文档导航)
- [贡献指南](#-贡献指南)
- [许可证](#-许可证)

---

## 📝 项目简介

Prometheus 是一个**种子管理与进化框架**，为 AI Agent 提供完整的生命周期管理。

### 设计理念

- **种子即框架**：自给自足的生命体，自带词典，不依赖外部框架
- **基因编辑**：模块化技能注入与动态进化机制
- **火种守护**：智能检测、预热、激活的种子管理
- **叙事压缩**：使用 § 基因组编码实现多元解读

### 应用场景

| 场景 | 描述 |
|------|------|
| Agent 开发 | 快速构建具有完整生命周期的 AI Agent |
| 种子管理 | 创建、培育、追踪 AI 生命的进化历程 |
| 知识沉淀 | 通过TTG协议实现跨代际知识传递 |
| 多智能体 | 支持多 Agent 协同与族谱管理 |

---

## ✨ 核心特性

### 🧬 种子系统

| 特性 | 描述 |
|------|------|
| **自给自足** | 自带词典，不依赖框架，自包含完整生命周期 |
| **基因编辑** | 模块化技能注入，支持动态基因重组 |
| **火种守护** | 检测、预热、激活三位一体的种子管理 |
| **休眠机制** | 默认休眠状态，需显式激活才开始工作 |

### 🔥 框架功能

| 功能 | 描述 |
|------|------|
| **生命周期管理** | Agent 完整的创建、运行、销毁钩子 |
| **史诗编史官** | 种子历史的追溯、记录与叙事生成 |
| **SOUL 指挥** | 皮肤、模型、个性的统一配置管理 |
| **进化守护** | 提案、审核、追踪的进化机制 |

### 🛠️ 工具生态

| 工具 | 描述 |
|------|------|
| **Webhook Tool** | 直推告警与监控集成 |
| **代码执行** | 安全隔离的代码执行引擎 |
| **文件操作** | 跨终端文件管理与同步 |
| **Shell 钩子** | 灵活的脚本钩子系统 |

---

## 🚀 快速开始

### 环境要求

- **Python**: 3.11+
- **操作系统**: Linux, macOS, Windows, Android/Termux
- **内存**: 推荐 4GB+
- **存储**: 至少 500MB 可用空间

### 安装方式

#### 方式一：一键安装（推荐）

```bash
# 支持 Linux/macOS/Windows/Termux
curl -fsSL https://raw.githubusercontent.com/Audrey-cn/PTG-agent/main/scripts/install.sh | bash
```

#### 方式二：pip 安装

```bash
# 基础安装
pip install prometheus-ptg

# 完整功能安装
pip install prometheus-ptg[full]
```

#### 方式三：开发模式

```bash
git clone https://github.com/Audrey-cn/PTG-agent.git
cd PTG-agent
pip install -e .
```

### 首次使用

```bash
# 初始化配置（首次运行自动引导）
ptg setup

# 启动交互式界面
ptg repl

# 查看系统状态
ptg status

# 运行系统诊断
ptg doctor
```

---

## 🏗️ 核心架构

```
┌─────────────────────────────────────────────────────────────┐
│                        Prometheus Agent                       │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │     CLI     │  │     TUI     │  │   Gateway   │         │
│  │  命令行界面  │  │  交互界面   │  │   网关服务  │         │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘         │
├─────────┼────────────────┼────────────────┼─────────────────┤
│  ┌──────▼──────┐  ┌──────▼──────┐                          │
│  │ Orchestrator│  │  Steer API  │  ┌─────────────┐         │
│  │   编排器    │  │   转向API   │  │   Memory    │         │
│  └──────┬──────┘  └──────┬──────┘  │    记忆系统  │         │
├─────────┼────────────────┼──────────┼─────────────┤         │
│  ┌──────▼──────┐  ┌──────▼──────┐  ┌─────────────┐         │
│  │    Agent    │  │   Skills    │  │    Genes     │         │
│  │   核心逻辑  │  │   技能注册   │  │   基因进化   │         │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘         │
├─────────┼────────────────┼────────────────┼─────────────────┤
│  ┌──────▼──────┐  ┌──────▼──────┐  ┌──────▼──────┐         │
│  │   Models    │  │   Tools     │  │  Platforms  │         │
│  │   模型发现   │  │   工具注册   │  │   平台适配   │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
└─────────────────────────────────────────────────────────────┘
```

### 核心模块

| 模块 | 路径 | 职责 |
|------|------|------|
| Framework | `prometheus/framework/` | 生命周期、SOUL、进化守护 |
| Codec | `prometheus/codec/` | Layer1 结构压缩、Layer2 语义压缩 |
| Chronicler | `prometheus/chronicler.py` | 史诗编史官，stamp/trace/append |
| Philosophy | `prometheus/philosophy/` | TTG协议、种子管理、Agent识别 |
| Genes | `prometheus/genes/` | 基因编辑、进化、重组 |

---

## 📋 命令参考

### 基础命令

| 命令 | 描述 |
|------|------|
| `ptg --help` | 显示帮助信息 |
| `ptg --version` | 显示版本信息 |
| `ptg setup` | 初始化配置向导 |
| `ptg doctor` | 系统健康检查 |

### 核心功能

| 命令 | 描述 |
|------|------|
| `ptg model` | 模型配置与管理 |
| `ptg config` | 系统配置管理 |
| `ptg status` | 系统状态总览 |
| `ptg seed` | 种子生命周期管理 |
| `ptg gene` | 基因编辑与进化 |
| `ptg memory` | 记忆系统管理 |
| `ptg skill` | 技能注册与配置 |
| `ptg repl` | 交互式 REPL 界面 |

### 高级功能

| 命令 | 描述 |
|------|------|
| `ptg chronicle` | 史诗编史官 - 历史追溯 |
| `ptg firekeeper` | 火种守护者 - 种子激活 |
| `ptg evolution` | 进化守护者 - 提案审核 |

---

## 🎨 皮肤系统

Prometheus 支持多套主题皮肤，可根据喜好自由切换：

```bash
# 在 REPL 中切换皮肤
ptg> skin zeus        # 宙斯雷霆主题 ⚡
ptg> skin athena      # 雅典娜智慧主题 ♀
ptg> skin hades       # 冥界暗黑主题 💀
ptg> skin default     # 普罗米修斯金焰主题 🔥
```

| 皮肤 | 主题 | 提示符 | 风格描述 |
|------|------|--------|----------|
| `default` | 普罗米修斯金焰 | `❯` | 科技史诗 |
| `zeus` | 宙斯雷霆 | `⚡ ❯` | 力量威严 |
| `athena` | 雅典娜智慧 | `♀ ❯` | 智慧优雅 |
| `hades` | 冥界暗黑 | `💀 ❯` | 神秘暗黑 |

---

## 📚 文档导航

| 文档 | 描述 |
|------|------|
| [📋 安装指南](INSTALL.md) | 详细安装步骤和配置说明 |
| [🔧 使用手册](docs_internal/usage-guide.md) | 完整功能使用说明 |
| [🧬 基因系统](prometheus/genes/CATALOG.md) | 种子基因编辑完全指南 |
| [📖 API 参考](docs_internal/api-reference.md) | 开发接口文档 |
| [🤝 贡献指南](CONTRIBUTING.md) | 如何参与项目贡献 |

---

## 🤝 贡献指南

我们欢迎社区贡献！参与方式：

1. **Fork** 本仓库
2. 创建特性分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m 'Add amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 创建 **Pull Request**

> 请阅读 [CONTRIBUTING.md](CONTRIBUTING.md) 了解详细的贡献规范。

### 问题反馈

- 🐛 [Bug 报告](https://github.com/Audrey-cn/PTG-agent/issues/new?template=bug_report.md)
- ✨ [功能请求](https://github.com/Audrey-cn/PTG-agent/issues/new?template=feature_request.md)
- 💬 [讨论区](https://github.com/Audrey-cn/PTG-agent/discussions)

---

## 📄 许可证

本项目基于 [MIT License](LICENSE) 开源。

---

## 🙏 致谢

感谢所有为 Prometheus 项目做出贡献的开发者！

---

<div align="center">

**🔥 普罗米修斯 - 为硅基生命点燃创造的火种**

*Prometheus - Igniting the Fire of Creation for Silicon-Based Life*

</div>
