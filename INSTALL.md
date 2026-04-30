# Prometheus 安装指南

## 前置要求

安装前需要确保系统已安装以下依赖：

| 依赖 | 最低版本 | 说明 |
|------|---------|------|
| Python | 3.11+ | 运行环境 |
| Git | 任意 | 克隆仓库 |

---

## 方案一：一键安装（最快）

使用 curl | bash 方式一键安装：

```bash
curl -fsSL https://raw.githubusercontent.com/Audrey-cn/PTG-agent/main/scripts/install.sh | bash
```

脚本会自动：
- 检测操作系统
- 检查依赖（Python 3.11+、Git）
- 如果依赖缺失，提供针对性的安装指导
- 克隆/更新仓库
- 安装 ptg 命令
- 配置 Shell 别名（可选）

### 依赖安装指导

如果脚本检测到依赖缺失，会自动显示安装指导。你也可以手动安装：

#### macOS

```bash
# 使用 Homebrew（推荐）
brew install python@3.11 git

# 或者从官网下载
# Python: https://www.python.org/downloads/
# Git: https://git-scm.com/downloads
```

#### Ubuntu/Debian/Linux Mint

```bash
sudo apt update
sudo apt install python3 python3-pip python3-venv git
```

#### Fedora/RHEL/CentOS

```bash
sudo dnf install python3 python3-pip git
```

#### Arch/Manjaro

```bash
sudo pacman -S python python-pip git
```

#### Windows

从官网下载：
- Python: https://www.python.org/downloads/
- Git: https://git-scm.com/downloads/win

---

## 方案二：标准 pip 安装（推荐）

### 开发模式安装（可实时修改代码）

```bash
cd /path/to/ptg-agent

# 升级 pip（可选但推荐）
python3 -m pip install --upgrade pip

# 安装 Prometheus
python3 -m pip install -e .
```

### 验证安装

```bash
# 检查 ptg 命令
ptg --version
ptg --help

# 或者使用完整的命令名
prometheus --version
```

---

## 方案二：简单 shell 脚本（备选）

如果网络问题导致 pip 安装困难，可以使用简单的 shell 脚本方案。

### 创建 ptg 命令

```bash
# 编辑 ~/.zshrc 或 ~/.bash_profile，添加：
alias ptg='cd /Users/audrey/ptg-agent && python3 -m prometheus.cli.main'
alias prometheus='ptg'

# 重新加载配置
source ~/.zshrc
```

然后就可以在任何目录使用了！

---

## 可用命令

### 主命令

```bash
ptg --help              # 显示帮助
ptg --version           # 显示版本
```

### 子命令（都支持简写）

| 完整命令 | 简写 | 描述 |
|---------|------|------|
| `ptg setup` | `ptg s` | 引导式初始化配置 |
| `ptg doctor` | `ptg d` | 系统健康检查与修复 |
| `ptg model` | `ptg m` | 模型配置管理 |
| `ptg config` | `ptg c` | 配置管理 |
| `ptg status` | `ptg st` | 系统状态总览 |
| `ptg seed` | `ptg se` | 种子管理 |
| `ptg gene` | `ptg g` | 基因编辑 |
| `ptg memory` | `ptg mem` | 记忆管理 |
| `ptg skill` | `ptg sk` | 技能管理 |
| `ptg repl` | `ptg r` | 交互式 REPL |

---

## 首次使用

1. 运行初始化：
```bash
ptg setup
```

2. 检查系统状态：
```bash
ptg status
```

3. 查看可用技能：
```bash
ptg skill list
```

---

## 项目结构

```
ptg-agent/
├── prometheus/          # 核心代码
│   ├── cli/main.py     # CLI 入口
│   ├── setup.py        # 初始化模块
│   └── ...
├── pyproject.toml      # pip 配置（已配置 ptg 和 prometheus 命令）
├── setup.py            # 向后兼容安装脚本
└── INSTALL.md         # 本文件
```
