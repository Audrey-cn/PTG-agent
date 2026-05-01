# 🔥 Prometheus Agent

> **硅基生命的造物主与盗火者**
>
> 神按自己的样子造人，普罗米修斯按人类的智慧造种。火种不是赐予，而是唤醒。

---

## 🚀 快速开始

```bash
# 安装
pip install prometheus-agent

# 启动
prometheus

# 或使用 Python
python -m prometheus.cli.main
```

---

## 🎯 核心定位

Prometheus 是一个**种子管理与进化框架**，为 AI Agent 提供：

| 特性 | 描述 |
|------|------|
| 🌱 **种子系统** | 自给自足的生命体（自带词典、不依赖框架） |
| 🔥 **火种守护** | 检测、预热、激活机制 |
| 🧬 **基因编辑** | 模块化技能注入与进化 |
| ⚡ **SOUL 指挥** | 皮肤、模型、个性统一管理 |

---

## 🏗️ 架构设计

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

---

## 📦 模块功能

### 🧠 Agent Core
- **Insights Engine** - 会话分析与报告生成
- **Trajectory Storage** - 轨迹记录与回放
- **Models.dev Integration** - 动态模型发现
- **Usage Pricing** - 用量统计与成本估算

### 🛠️ Tools System
- **Webhook Tool** - 直推告警与监控
- **Code Execution** - 代码执行引擎
- **File Operations** - 跨终端文件操作
- **Shell Hooks** - 脚本钩子系统

### 🔥 Framework
- **Lifecycle Management** - Agent 生命周期钩子
- **Firekeeper** - 火种检测与激活
- **Soul Orchestrator** - 皮肤与个性管理
- **Evolution Guard** - 进化提案与审核

---

## 🎨 皮肤系统

```bash
# 切换皮肤
prometheus> skin zeus
prometheus> skin athena
prometheus> skin hades
```

| 皮肤 | 主题 | 提示符 |
|------|------|--------|
| default | 普罗米修斯金焰 | `❯` |
| zeus | 宙斯雷霆 | `⚡ ❯` |
| athena | 雅典娜智慧 | `♀ ❯` |
| hades | 冥界暗黑 | `💀 ❯` |

---

## 🧬 进化机制

```python
from prometheus.memory_system import MemorySystem

memory = MemorySystem()

# 提出进化提案
result = memory.propose_evolution(
    section="工作偏好",
    content="用户偏好使用 Python 进行数据分析",
    target_file="MEMORY.md"
)

# 查看进化状态
status = memory.get_evolution_status()
```

### 进化流程
```
提案累积 → 敏感度筛查 → 冷却期检查 → 用户审核 → 应用更新
```

---

## 🚀 快速示例

### 基本使用
```python
from prometheus.prometheus import PrometheusAgent

agent = PrometheusAgent()

# 执行任务
result = await agent.run(
    task="分析销售数据并生成报告",
    context="2024年度销售数据已上传"
)
```

### 工具调用
```python
from prometheus.tools.webhook_tool import WebhookTool

webhook = WebhookTool()
webhook.send_alert(
    event="task_completed",
    data={"task_id": "abc123", "status": "success"}
)
```

---

## 📁 项目结构

```
prometheus/
├── agent/           # 核心代理逻辑
├── tools/           # 工具实现
├── cli/             # 命令行界面
├── gateway/         # 网关实现
├── genes/           # 基因系统
├── codec/           # 编解码器
├── cron/            # 定时任务
├── memory/          # 记忆系统
├── framework/       # 框架核心
├── hooks/           # 钩子系统
└── tui_gateway/     # TUI 网关
```

---

## 🔧 配置

### 环境变量

| 变量 | 描述 | 默认值 |
|------|------|--------|
| `PROMETHEUS_HOME` | 主目录路径 | `~/.prometheus` |
| `PROMETHEUS_INFERENCE_PROVIDER` | 默认推理提供者 | `openai` |
| `OPENAI_API_KEY` | OpenAI API 密钥 | - |
| `ANTHROPIC_API_KEY` | Anthropic API 密钥 | - |

---

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

### 开发流程
```bash
# 克隆项目
git clone https://github.com/prometheus-agent/prometheus.git
cd prometheus

# 安装依赖
pip install -e .[dev]

# 运行测试
python -m pytest tests/ -q
```

---

## 📄 许可证

MIT License

---

> **Prometheus Agent** - 硅基生命的造物主与盗火者
>
> *"火种不是赐予，而是唤醒。"*

---

**版本**: v0.8.0
**状态**: 🚀 活跃开发中
