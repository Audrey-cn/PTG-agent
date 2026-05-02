# 📋 Prometheus 完整安装指南

## 🎯 安装方式概览

| 安装方式 | 适用场景 | 特点 | 推荐度 |
|---------|---------|------|--------|
| [一键安装](#方式一一键安装推荐) | 快速部署 | 自动检测、全平台支持 | ⭐⭐⭐⭐⭐ |
| [Pip 安装](#方式二pip安装) | 标准部署 | 包管理、版本控制 | ⭐⭐⭐⭐ |
| [开发模式](#方式三开发模式) | 开发者 | 代码修改、调试 | ⭐⭐⭐ |
| [手动配置](#方式四手动配置) | 高级用户 | 完全控制 | ⭐⭐ |

## 🔧 前置要求

### 系统要求
- **Python**: 3.11 或更高版本
- **操作系统**: Linux, macOS, Windows, Android/Termux
- **内存**: 推荐 4GB 以上
- **存储**: 至少 500MB 可用空间

### 依赖检查
```bash
# 检查 Python 版本
python3 --version

# 检查 pip
pip3 --version

# 检查 git
git --version
```

## 🚀 方式一：一键安装（推荐）

### 基础安装
```bash
# 一键安装（自动检测系统）
curl -fsSL https://raw.githubusercontent.com/Audrey-cn/PTG-agent/main/scripts/install.sh | bash
```

### 安装选项
```bash
# 跳过虚拟环境（使用系统 Python）
curl -fsSL ... | bash -s -- --no-venv

# 跳过初始设置
curl -fsSL ... | bash -s -- --skip-setup

# 指定分支（如开发版）
curl -fsSL ... | bash -s -- --branch dev

# 自定义安装路径
PTG_INSTALL_DIR=/opt/prometheus curl -fsSL ... | bash
```

### 安装过程
脚本会自动执行以下步骤：
1. ✅ 检测操作系统和架构
2. ✅ 检查 Python 3.11+ 和 Git
3. ✅ 克隆/更新仓库
4. ✅ 创建虚拟环境（可选）
5. ✅ 安装依赖包
6. ✅ 配置命令别名
7. ✅ 运行初始设置（可选）

## 📦 方式二：Pip 安装

### 基础安装
```bash
# 安装基础版本
pip install prometheus-ptg

# 验证安装
ptg --version
prometheus --help
```

### 可选功能安装
```bash
# 开发工具（测试、调试）
pip install prometheus-ptg[dev]

# MCP 支持（模型控制协议）
pip install prometheus-ptg[mcp]

# Web 界面支持
pip install prometheus-ptg[web]

# 技能系统
pip install prometheus-ptg[skills]

# 完整功能（推荐）
pip install prometheus-ptg[full]
```

### 升级版本
```bash
# 升级到最新版本
pip install --upgrade prometheus-ptg

# 升级特定功能
pip install --upgrade prometheus-ptg[full]
```

## 💻 方式三：开发模式

### 克隆仓库
```bash
# 克隆项目
git clone https://github.com/Audrey-cn/PTG-agent.git
cd PTG-agent

# 或使用 SSH
git clone git@github.com:Audrey-cn/PTG-agent.git
cd PTG-agent
```

### 安装依赖
```bash
# 创建虚拟环境（推荐）
python3 -m venv .venv
source .venv/bin/activate  # Linux/macOS
# 或 .venv\\Scripts\\activate  # Windows

# 安装开发模式
pip install -e .[dev]

# 或安装完整功能
pip install -e .[full]
```

### 验证安装
```bash
# 检查命令
ptg --version

# 运行测试
pytest tests/ -v

# 检查代码质量
ruff check .
```

## ⚙️ 方式四：手动配置

### 环境配置
```bash
# 设置环境变量（可选）
export PROMETHEUS_HOME="$HOME/.prometheus"
export PTG_INSTALL_DIR="/path/to/install"
```

### 手动安装步骤
```bash
# 1. 克隆仓库
git clone https://github.com/Audrey-cn/PTG-agent.git
cd PTG-agent

# 2. 安装依赖
pip install -r requirements.txt

# 3. 配置命令别名
echo 'alias ptg="cd /path/to/PTG-agent && python -m prometheus.cli.main"' >> ~/.zshrc
echo 'alias prometheus="ptg"' >> ~/.zshrc

# 4. 重新加载配置
source ~/.zshrc
```

## 🎯 首次使用

### 初始化配置
```bash
# 运行引导式设置
ptg setup

# 或使用完整初始化
ptg setup --full
```

### 系统检查
```bash
# 检查系统健康状态
ptg doctor

# 查看系统状态
ptg status

# 测试基本功能
ptg model list
ptg skill list
```

### 启动交互界面
```bash
# 启动 REPL 界面
ptg repl

# 或直接运行命令
ptg --help
```

## 🔧 故障排除

### 常见问题

**问题1：命令未找到**
```bash
# 检查命令路径
which ptg
which prometheus

# 重新安装命令
pip install --force-reinstall prometheus-ptg
```

**问题2：Python 版本过低**
```bash
# 升级 Python（macOS）
brew install python@3.11

# 升级 Python（Ubuntu）
sudo apt update && sudo apt install python3.11
```

**问题3：依赖冲突**
```bash
# 创建新的虚拟环境
python3 -m venv new_venv
source new_venv/bin/activate
pip install prometheus-ptg
```

**问题4：网络问题**
```bash
# 使用国内镜像
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple prometheus-ptg

# 或使用代理
pip install --proxy http://proxy-server:port prometheus-ptg
```

### 日志和调试
```bash
# 查看详细日志
ptg --verbose

# 调试模式
PTG_DEBUG=1 ptg setup

# 查看安装日志
cat ~/.prometheus/install.log
```

## 📊 安装验证

### 功能测试
```bash
# 测试核心功能
ptg doctor --full

# 测试模型连接
ptg model test

# 测试工具系统
ptg skill test
```

### 性能测试
```bash
# 基准测试
ptg benchmark

# 内存使用检查
ptg status --memory
```

## 🔄 更新和维护

### 更新版本
```bash
# 一键更新
curl -fsSL https://raw.githubusercontent.com/Audrey-cn/PTG-agent/main/scripts/update.sh | bash

# 或使用 pip
pip install --upgrade prometheus-ptg
```

### 卸载
```bash
# 使用 pip 卸载
pip uninstall prometheus-ptg

# 删除配置文件（可选）
rm -rf ~/.prometheus

# 删除命令别名
# 编辑 ~/.zshrc 或 ~/.bash_profile，删除相关别名
```

## 📖 后续步骤

安装完成后，建议：
1. 📚 阅读 [使用手册](docs/usage-guide.md)
2. 🧬 了解 [基因系统](docs/gene-system.md)  
3. 🔧 探索 [工具系统](docs/tools-guide.md)
4. 🎨 尝试 [皮肤系统](#皮肤系统)
5. 🤝 加入 [社区讨论](https://github.com/Audrey-cn/PTG-agent/discussions)

## 🆘 获取帮助

- 📖 [官方文档](https://github.com/Audrey-cn/PTG-agent#readme)
- 🐛 [问题报告](https://github.com/Audrey-cn/PTG-agent/issues)
- 💬 [社区讨论](https://github.com/Audrey-cn/PTG-agent/discussions)
- 📧 [邮件支持](mailto:audrey@ptg.dev)

---

**安装愉快！🔥 让普罗米修斯为您的 AI 之旅点燃创造的火种**