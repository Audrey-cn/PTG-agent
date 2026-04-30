# init-skill 集成使用指南

## 概述

我们已成功将 init-skill 的核心功能集成到 Prometheus 项目中！

## 新增组件

### 1. 技能文件
- `prometheus/skills/init_skill/SKILL.md` - init-skill 主技能
- `prometheus/skills/init_skill/references/` - 各种参考模板

### 2. 自进化引擎模块 (`prometheus/self_evolution/`)
- `__init__.py` - 模块初始化
- `engine.py` - 核心引擎
- `observer.py` - 观察者（记录模式）
- `learner.py` - 学习者（从纠正中学习）
- `consultant.py` - 咨询者（提供规则）
- `verifier.py` - 验证者（验证规则）
- `initializer.py` - 项目初始化器

### 3. 工具 (`prometheus/tools/evolution_tools.py`)
- `init_self_evolution` - 初始化项目
- `record_observation` - 记录观察
- `record_correction` - 记录纠正
- `get_learned_rules` - 获取学习规则
- `get_evolution_status` - 获取状态

## 使用方式

### 初始化项目

```python
from prometheus.self_evolution import ProjectInitializer

initializer = ProjectInitializer("/path/to/your/project")
result = initializer.initialize()
print(result)
```

### 使用自进化引擎

```python
from prometheus.self_evolution import SelfEvolutionEngine

engine = SelfEvolutionEngine("/path/to/your/project")

# 观察模式
engine.observe("pattern", "This is a pattern we see often", "context...", 0.8)

# 从纠正中学习
engine.learn_from_correction(
    original="Wrong approach",
    corrected="Better approach",
    feedback="This is why the corrected version is better"
)

# 咨询已学习的规则
rules = engine.consult()
print(rules)

# 获取状态
status = engine.get_status()
print(status)
```

### 使用工具

可以通过 Prometheus 的工具系统调用这些功能。

## 目录结构

```
prometheus/
├── skills/
│   └── init_skill/
│       ├── SKILL.md
│       └── references/
│           ├── CLAUDE.md
│           ├── settings.json
│           ├── rule-security.md
│           ├── rule-api-design.md
│           ├── rule-performance.md
│           ├── agent-architect.md
│           ├── agent-reviewer.md
│           └── skill-evolution.md
├── self_evolution/
│   ├── __init__.py
│   ├── engine.py
│   ├── observer.py
│   ├── learner.py
│   ├── consultant.py
│   ├── verifier.py
│   └── initializer.py
└── tools/
    └── evolution_tools.py
```

## 核心功能

1. **Observe** - 记录模式到 observations.jsonl
2. **Learn** - 用户纠正记录到 corrections.jsonl
3. **Consult** - 会话开始读取 learned-rules.md
4. **Verify** - 运行验证扫描

## 与 Prometheus 现有系统的集成

- 使用现有的记忆系统 (memory/) 进行长期存储
- 与技能系统 (skills/) 无缝集成
- 遵循 Prometheus 的编码规范和架构风格
- 使用相同的工具注册机制

## 下一步

1. 在实际项目中测试初始化功能
2. 收集用户反馈并优化学习机制
3. 与现有的 Prometheus 记忆系统更深入集成
4. 添加更多验证规则和安全检查

