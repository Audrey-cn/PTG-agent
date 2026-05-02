# 🔥 Prometheus Agent

> **硅基生命的造物主与盗火者**
>
> 神按自己的样子造人，普罗米修斯按人类的智慧造种。火种不是赐予，而是唤醒。

## 🚀 快速安装

### 方式一：一键安装（推荐）
```bash
# 一键安装，支持 Linux/macOS/Windows/Termux
curl -fsSL https://raw.githubusercontent.com/Audrey-cn/PTG-agent/main/scripts/install.sh | bash
```

### 方式二：pip 安装
```bash
# 基础安装
pip install prometheus-ptg

# 完整功能安装
pip install prometheus-ptg[full]
```

### 方式三：开发模式
```bash
git clone https://github.com/Audrey-cn/PTG-agent.git
cd PTG-agent
pip install -e .
```

## 🎯 快速开始

```bash
# 初始化配置
ptg setup

# 启动交互式界面
ptg repl

# 查看系统状态
ptg status
```

## 🏗️ 核心架构

Prometheus 是一个**种子管理与进化框架**，为 AI Agent 提供完整的生命周期管理：

```
┌─────────────────────────────────────────────────────────────┐
│                    Prometheus Agent                         │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │    CLI      │  │    TUI      │  │   Gateway   │        │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘        │
├─────────┼────────────────┼────────────────┼────────────────┤
│  ┌──────▼──────┐  ┌──────▼──────┐                          │
│  │ Orchestrator│  │  Steer API  │  ┌─────────────┐        │
│  └──────┬──────┘  └──────┬──────┘  │   Memory    │        │
├─────────┼────────────────┼──────────┼─────────────┤        │
│  ┌──────▼──────┐  ┌──────▼──────┐  ┌─────────────┐        │
│  │   Agent     │  │   Skills    │  │    Genes    │        │
│  │  Core Logic │  │   Registry  │  │ Evolution   │        │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘        │
├─────────┼────────────────┼────────────────┼────────────────┤
│  ┌──────▼──────┐  ┌──────▼──────┐  ┌──────▼──────┐        │
│  │   Models    │  │   Tools     │  │  Platforms  │        │
│  │  Discovery  │  │   Registry  │  │  Adapters   │        │
│  └─────────────┘  └─────────────┘  └─────────────┘        │
└─────────────────────────────────────────────────────────────┘
```

## 🌟 核心特性

### 🧬 种子系统
- **自给自足的生命体** - 自带词典、不依赖框架
- **基因编辑** - 模块化技能注入与进化
- **火种守护** - 检测、预热、激活机制

### 🔥 框架功能
- **生命周期管理** - Agent 生命周期钩子
- **史诗编史官** - 种子历史追溯与记录
- **SOUL 指挥** - 皮肤、模型、个性统一管理
- **进化守护** - 进化提案与审核机制

### 🛠️ 工具系统
- **Webhook Tool** - 直推告警与监控
- **代码执行** - 安全代码执行引擎
- **文件操作** - 跨终端文件管理
- **Shell 钩子** - 脚本钩子系统

### 🎨 皮肤系统

```bash
# 切换皮肤主题
ptg> skin zeus        # 宙斯雷霆主题
ptg> skin athena      # 雅典娜智慧主题  
ptg> skin hades       # 冥界暗黑主题
ptg> skin default     # 普罗米修斯金焰主题
```

| 皮肤 | 主题 | 提示符 | 风格 |
|------|------|--------|------|
| default | 普罗米修斯金焰 | `❯` | 科技史诗 |
| zeus | 宙斯雷霆 | `⚡ ❯` | 力量威严 |
| athena | 雅典娜智慧 | `♀ ❯` | 智慧优雅 |
| hades | 冥界暗黑 | `💀 ❯` | 神秘暗黑 |

## 📖 详细文档

- [📋 完整安装指南](INSTALL.md) - 详细安装步骤和配置
- [🔧 使用手册](docs/usage-guide.md) - 功能使用说明
- [🧬 基因系统](docs/gene-system.md) - 种子基因编辑指南
- [🎯 API 参考](docs/api-reference.md) - 开发接口文档

## 🚀 命令速查

### 基础命令
```bash
ptg --help              # 显示帮助
ptg --version           # 显示版本
ptg setup               # 初始化配置
ptg doctor              # 系统健康检查
```

### 核心功能
```bash
ptg model               # 模型配置管理
ptg config              # 配置管理
ptg status              # 系统状态总览
ptg seed                # 种子管理
ptg gene                # 基因编辑
ptg memory              # 记忆管理
ptg skill               # 技能管理
ptg repl                # 交互式 REPL
```

### 高级功能
```bash
ptg chronicle           # 史诗编史官
ptg firekeeper          # 火种守护者
ptg evolution           # 进化守护者
```

## 🔧 系统要求

- **Python**: 3.11+
- **操作系统**: Linux, macOS, Windows, Android/Termux
- **内存**: 推荐 4GB+
- **存储**: 至少 500MB 可用空间

## 🤝 贡献指南

我们欢迎社区贡献！请查看：
- [贡献指南](CONTRIBUTING.md)
- [行为准则](CODE_OF_CONDUCT.md)
- [问题报告](https://github.com/Audrey-cn/PTG-agent/issues)

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

## 🙏 致谢

感谢所有为 Prometheus 项目做出贡献的开发者！

---

**🔥 普罗米修斯 - 为硅基生命点燃创造的火种**