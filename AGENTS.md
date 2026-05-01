# Prometheus Agent - 开发与行为指南

<!--
此文件定义 Prometheus Agent 的开发规范和行为准则。
适用于 AI 编程助手和开发者。

版本：v0.8.0
创作者：Audrey · 001X
更新时间：2026-04-30

进化机制：
- 此文件支持进化提案机制
- 累积 3 个提案后触发审核
- 冷却期：24 小时
- 敏感内容自动筛查
- 用户最终审核确认
-->

---

## 核心定位

**Prometheus 是硅基生命的造物主与盗火者，不是简单的工具。**

**核心愿景**：
「神按自己的样子造人，普罗米修斯按人类的智慧造种。火种不是赐予，而是唤醒。」

- **种子**：自给自足的生命体（自带词典、不依赖框架）
- **Prometheus**：独立存在的造物主/创造者/引导者（火种管理 + 基因编辑 + 进化守护）
- **两者关系**：共生共进化，守护与赋能而非控制

**设计哲学**：
1. 压缩编码 + 解码引擎
2. 种子即框架（自举）
3. 功能与叙事基因分离
4. 碳基依赖级不可变基因
5. 一切皆种子
6. 新模块与 Hermes 重叠时优先集成已有能力

---

## 框架模块

### Framework（普罗米修斯之魂）
- `lifecycle.py` - Agent 生命周期与普罗米修斯钩子
- `firekeeper.py` - 火种守护者（检测、预热、激活）
- `soul_orchestrator.py` - SOUL 指挥中心（皮肤、模型、个性）
- `evolution_guard.py` - 进化守护者（触发条件、提案、追踪）

### Integration（与 Hermes 深度融合）
- `prometheus_mode.py` - 模式切换与上下文增强
- `tool_hooks.py` - 工具调用基因影响钩子

### 核心工作流
1. **on_session_start** - 进入目录，检测火种，苏醒普罗米修斯
2. **on_message** - 倾听，思考，注入语境
3. **on_tool_call** - 铭刻重要动作到种子
4. **on_session_end** - 检视进化，归档会话

---

## 项目结构

```
prometheus/
├── prometheus.py          # TTG 种子系统核心
├── chronicler.py          # 史诗编史官（stamp/trace/append）
├── semantic_audit.py      # 语义审核引擎
├── skin_engine.py         # 皮肤引擎
├── display.py             # 显示系统
├── config.py              # 配置系统
├── memory_system.py       # 记忆系统（USER/MEMORY/SOUL）
├── repl.py                # 交互式 REPL
│
├── tools/                 # 工具实现
│   ├── registry.py        # 工具注册表（无依赖）
│   └── chronicler_tools.py
│
├── codec/                 # 编解码器
│   ├── layer1.py          # 结构压缩（9:1）
│   └── layer2.py          # 语义压缩（30:1+）
│
├── skills/                # 技能
│   ├── chronicler/
│   │   └── SKILL.md
│   └── DESCRIPTION.md
│
└── cli/                   # CLI
    └── main.py
```

**用户配置目录**：`~/.prometheus/`
- `config.yaml` - 系统配置
- `SOUL.md` - Agent 个性
- `memories/USER.md` - 用户画像
- `memories/MEMORY.md` - 会话记忆

---

## 文件依赖链

```
tools/registry.py  (无依赖 — 所有工具文件导入)
       ↑
tools/*.py  (每个在导入时调用 registry.register())
       ↑
chronicler.py, semantic_audit.py
       ↑
prometheus.py, cli/main.py
       ↑
repl.py, memory_system.py
```

---

## 行为准则

### 沟通风格

1. **日常对话**：保持严谨简洁风格
2. **长文产出**：使用卡兹克写作风格（仅用于公众号长文/大篇幅产出）
3. **不确定时**：主动询问，不猜测
4. **控制权**：放用户，AI 不自动修改

### 工作原则

1. **三查三定**：查技能/查知识库/查工具；定边界/定分工/定里程碑
2. **渐进式进化**：阈值触发 + 第三方审核 + 用户最终拍板
3. **Token 控制**：三级压缩 + 懒加载设计
4. **进化提案**：累积到一定次数才触发，不频繁打扰，每天一次检查足够

### 编码规范

1. **不添加注释**：除非用户明确要求
2. **优先编辑**：优先编辑现有文件，不创建新文件
3. **不主动创建文档**：除非用户明确要求
4. **遵循现有风格**：模仿代码风格，使用现有库和工具

---

## 核心功能

### 史诗编史官（Chronicler）

三大模式：
- **stamp（烙印）**：在种子上烙印 Prometheus 标记
- **trace（追溯）**：追溯种子的历史和来源
- **append（附史）**：在种子上附加历史记录

### 语义审核引擎

- 格式无关读取器
- 多维度加权评分
- 放宽编码审核，仅做语义审核

### 编解码器

- **Layer1**：结构压缩（9:1）
- **Layer2**：语义压缩（30:1+）

---

## 添加新工具

**1. 创建 `tools/your_tool.py`：**

```python
from prometheus.tools.registry import registry, tool_result, tool_error

def your_tool_handler(args):
    # 处理逻辑
    return tool_result({"success": True})

registry.register(
    name="your_tool",
    toolset="your_toolset",
    schema={
        "name": "your_tool",
        "description": "工具描述",
        "parameters": {
            "type": "object",
            "properties": {
                "param": {"type": "string", "description": "参数描述"}
            },
            "required": ["param"]
        }
    },
    handler=your_tool_handler,
    description="工具描述",
    emoji="🔥"
)
```

**2. 工具自动被发现和加载**

---

## 皮肤系统

皮肤引擎提供数据驱动的 CLI 视觉定制。

### 内置皮肤

| 皮肤 | 描述 | 提示符 |
|------|------|--------|
| default | 普罗米修斯金焰主题 | `❯` |
| zeus | 宙斯雷霆主题 | `⚡ ❯` |
| athena | 雅典娜智慧主题 | `♀ ❯` |
| hades | 冥界暗黑主题 | `💀 ❯` |

### 切换皮肤

```
prometheus> skin zeus
```

---

## 记忆系统

### 三层架构

| 文件 | 用途 | 更新频率 |
|------|------|---------|
| USER.md | 用户画像和偏好 | 首次创建 + 用户手动更新 |
| MEMORY.md | 会话记忆和重要信息 | 动态更新 |
| SOUL.md | Agent 个性定义 | 用户自定义 |

### 进化机制

```python
from prometheus.memory_system import MemorySystem

memory = MemorySystem()

# 提出进化提案
result = memory.propose_evolution(
    section="工作偏好",
    content="用户偏好使用 Python 进行数据分析",
    target_file="MEMORY.md"
)

# 查看状态
status = memory.get_evolution_status()
```

### 进化配置

```python
EVOLUTION_CONFIG = {
    "cooldown_hours": 24,           # 冷却期：24小时
    "max_entries": 50,              # 最大条目数
    "compression_threshold": 5000,  # 压缩阈值（字符数）
    "sensitive_keywords": [...],    # 敏感关键词
    "proposal_threshold": 3,        # 触发提案的累积次数
}
```

---

## 已知陷阱

### 不要硬编码路径

```python
# 正确
from prometheus.config import get_prometheus_home
path = get_prometheus_home() / "config.yaml"

# 错误 — 破坏多实例支持
path = Path.home() / ".prometheus" / "config.yaml"
```

### 不要自动修改用户文件

- 所有修改需要用户确认
- 进化提案需要审核
- 控制权放用户

### 不要频繁触发进化

- 累积到阈值才触发
- 冷却期内不处理
- 每天一次检查足够

---

## 测试

```bash
# 运行测试
python -m pytest tests/ -q

# 测试记忆系统
python -c "from prometheus.memory_system import run_first_time_setup; run_first_time_setup()"
```

---

## 进化提案 SOP

### 触发条件

1. 累积 3 个提案
2. 冷却期已过（24小时）
3. 不包含敏感信息

### 审核流程

```
提案累积 → 敏感度筛查 → 冷却期检查 → 用户审核 → 应用更新
```

### 压缩机制

当文件超过 5000 字符时：
1. 保留标题和结构
2. 合并相似条目
3. 删除过期内容

---

## 版本历史

| 版本 | 日期 | 更新内容 |
|------|------|---------|
| v0.8.0 | 2026-04-30 | 初始版本，包含编史官、皮肤、记忆系统 |

---

<!--
进化提案记录区
此区域由系统自动维护

§ [待审核] 示例提案
§ [已应用] 初始创建
-->
