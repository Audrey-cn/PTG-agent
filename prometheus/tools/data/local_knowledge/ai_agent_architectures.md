# AI Agent 架构模式知识库

> 来源：https://github.com/pguso/ai-agents-from-scratch
> 整合时间：2026-04-30
> 用途：普罗米修斯 Agent 架构参考

---

## 一、Agent 核心定义

```
AI Agent = LLM + System Prompt + Tools + Memory + Reasoning Pattern
           ─┬─   ──────┬──────   ──┬──   ──┬───   ────────┬────────
            │          │           │       │              │
         Brain      Identity    Hands   State         Strategy
```

### Agent 的核心组成

1. **LLM（大脑）**：语言模型，负责理解和生成
2. **System Prompt（身份）**：定义 Agent 的行为和角色
3. **Tools（双手）**：工具调用能力，实现行动
4. **Memory（状态）**：持久化记忆和上下文
5. **Reasoning Pattern（策略）**：推理模式，如 ReAct、AoT 等

---

## 二、ReAct 模式（Reasoning + Acting）

### 核心模式

```
┌─────────────┐
│   Problem   │
└──────┬──────┘
       │
       ▼
┌─────────────────────────────────────┐
│          ReAct Loop                 │
│                                     │
│  ┌──────────────────────────────┐  │
│  │  1. THOUGHT                  │  │
│  │  "What do I need to do?"     │  │
│  └─────────────┬────────────────┘  │
│                ▼                    │
│  ┌──────────────────────────────┐  │
│  │  2. ACTION                   │  │
│  │  Call tool with parameters   │  │
│  └─────────────┬────────────────┘  │
│                ▼                    │
│  ┌──────────────────────────────┐  │
│  │  3. OBSERVATION              │  │
│  │  Receive tool result         │  │
│  └─────────────┬────────────────┘  │
│                │                    │
│                └──► Repeat or      │
│                     Final Answer   │
└─────────────────────────────────────┘
```

### 三大组件

1. **Thought（推理）**：思考需要什么信息、使用哪个工具、结果是否合理
2. **Action（行动）**：调用工具并传递参数
3. **Observation（观察）**：接收并解释工具结果

### 完整示例

```
Problem: "If 15 items cost $8 each and 20 items cost $8 each, 
          what's the total revenue?"

Thought: First I need to calculate revenue from 15 items
Action: multiply(15, 8)
Observation: 120

Thought: Now I need revenue from 20 items
Action: multiply(20, 8)
Observation: 160

Thought: Now I add both revenues
Action: add(120, 160)
Observation: 280

Thought: I have the final answer
Answer: The total revenue is $280
```

### ReAct 的优势

- **可靠性**：工具提供准确结果，无算术错误
- **透明性**：可见每个推理步骤
- **可扩展性**：可处理复杂问题，添加更多工具
- **灵活性**：适用于任何工具，自适应问题复杂度

### 与其他方法的对比

| 方法 | 问题 | 结果 |
|------|------|------|
| Zero-Shot | LLM 心算 | ❌ 可能错误 |
| Chain-of-Thought | 展示步骤但仍心算 | ❌ 仍可能错误 |
| ReAct | 使用工具执行 | ✅ 正确 |

---

## 三、AoT 模式（Atom of Thought）

### 核心理念

**Atom of Thought = "SQL for Reasoning"**

就像 SQL 将复杂数据操作分解为原子、可组合的语句，AoT 将推理分解为最小、可执行的步骤。

### 什么是 Atom？

一个 atom 是**最小的推理单元**：

1. 表达**恰好一个**想法
2. 可以**独立验证**
3. 可以**确定性执行**
4. **无法隐藏**错误

### 三层架构

```
┌─────────────────────────────────┐
│   LLM (Planning Layer)          │
│   - Proposes atomic plan        │
│   - Does NOT execute            │
└─────────────────────────────────┘
              ↓
┌─────────────────────────────────┐
│   Validator (Safety Layer)      │
│   - Checks plan structure       │
│   - Validates dependencies      │
└─────────────────────────────────┘
              ↓
┌─────────────────────────────────┐
│   Executor (Execution Layer)    │
│   - Runs atoms deterministically│
│   - Manages state               │
└─────────────────────────────────┘
```

### Atom 结构

```json
{
  "id": 2,
  "kind": "tool",
  "name": "multiply",
  "input": {
    "a": "<result_of_1>",
    "b": 3
  },
  "dependsOn": [1]
}
```

### AoT vs ReAct 对比

| 方面 | ReAct | AoT |
|------|-------|-----|
| **格式** | 自然语言 | 结构化数据 |
| **验证** | 不可能 | 执行前验证 |
| **测试** | Mock 整个 LLM | 独立测试执行器 |
| **调试** | 阅读文本 | 检查特定 atom |
| **重放** | 重跑整个对话 | 从任意 atom 重跑 |
| **审计** | 对话历史 | 数据结构 |

### AoT 适用场景

✅ **适合**：
- 多步骤工作流（预订、管道）
- API 编排（调用 A，然后用 A 的结果调用 B）
- 金融交易（可审计、可逆）
- 合规敏感系统（每步都有日志）
- 生产环境 Agent（失败必须干净）

❌ **不适合**：
- 创意写作
- 开放式探索
- 头脑风暴
- 单步查询

---

## 四、Tree of Thought（ToT）

### 核心理念

ToT 探索多个推理分支，评分后只保留最高分的分支。

### 可视化树结构

```
[Behavior: "Person leaves secure job without a clear plan"]
         |
    [Phase 1: Branch - 4 hypotheses]
    /        |         |        \
[Avoidance][Burnout][Growth][External pressure]
    |         |          |            |
[Phase 2: Score]
   6         9          7            4
             |
      [Phase 3: Prune - losers removed]
             |
 [Phase 4: Conclusion from ONLY Burnout]
```

### 三个核心原则

| 原则 | 代码中的实现 |
|------|-------------|
| Branching | `developHypothesis()` 创建每个视角的假设 |
| Evaluation | `scoreHypothesis()` 评分每个假设 |
| Pruning | `pruneHypotheses()` 丢弃所有非获胜者 |

### ToT 适用场景

✅ **适合**：
- 需要明确赢家和简单决策路径
- 时间有限
- 输出应该是一个可执行方向
- 保持多个替代方案的成本高于丢失细节的风险

**实际场景**：
- 生产事故响应（选择一个快速修复路径）
- 开发优化决策（选择一个实现策略）
- 自动编码 Agent（选择一个修复策略）

---

## 五、Graph of Thought（GoT）

### 核心理念

GoT 保持多个推理线索活跃并组合它们，不自动丢弃较弱分支。

### 可视化图结构

```
                    [root: behavior]
                   /    |      |    \
             [n2]    [n3]   [n4]   [n5]
          Avoidance Burnout Growth Pressure
             Sc:6     Sc:9    Sc:7   Sc:4
                \      / \            |
                 \    /   \           |
              [n6:Contrast]  [n7:Contrast]
                  |    \         |
                  |   [n8:Refined]  [n9:Refined]
                  |        \       /
              [n10:Synthesis1]  [n11:Synthesis2]
                    \              /
                   [n12:CONCLUSION]
```

### GoT 操作

| 操作 | 揭示的内容 |
|------|-----------|
| Contrast | 假设间的生产性张力成为明确证据 |
| Refine | 弱假设被拯救而非丢弃 |
| Aggregate | 不同线索被合成为更丰富的中间视图 |
| Conclude | 最终答案包含矛盾和被拯救的洞察 |

### ToT vs GoT 核心区别

- **ToT 问**：哪个分支获胜？
- **GoT 问**：多个分支如何交互产生更好的最终模型？

### GoT 适用场景

✅ **适合**：
- 多个视角必须保持连接并相互影响
- 问题模糊
- 较弱信号经过细化后可能变得有价值
- 希望最终答案保留矛盾而非隐藏它们

**实际场景**：
- 区域性故障分析（多因果事件）
- 不稳定测试调试（假设交互）
- 研究级规划 Agent（复杂任务分解）

---

## 六、错误处理模式

### 标准化错误分类

| 错误类型 | 说明 | 是否可重试 |
|---------|------|-----------|
| `ValidationError` | 用户输入缺失/无效 | 通常不可重试 |
| `LLMCallError` | LLM 调用失败或返回不可用输出 | 通常可重试 |
| `ToolExecutionError` | 工具执行失败 | 有时可重试 |
| `AgentWorkflowError` | 编排级失败 | 取决于原因 |

### 恢复策略阶梯

1. **Timeout**：限制任何步骤的最大停滞时间
2. **Retry**：仅在 `retryable` 时重试（带退避和抖动）
3. **Fallback**：如果主工具以瞬态方式失败，运行更安全的替代方案
4. **Degraded Mode**：如果 LLM 路径失败，委托给确定性提取
5. **Graceful Failure**：如果恢复不可能，返回用户友好的错误消息

### 用户消息与调试信息分离

**用户应该看到**：
- 清晰的下一步（重试、重述、缩短输入）
- 无堆栈跟踪或提供商内部信息
- 可与支持团队分享的**参考 ID**

**开发者/运维应该看到**：
- 稳定的错误 `code`
- 结构化 `details`
- 关联 ID
- 原始 `cause`

---

## 七、架构演进路径

```
1. intro          → Basic LLM usage
2. translation    → Specialized behavior (system prompts)
3. think          → Reasoning ability
4. batch          → Parallel processing
5. coding         → Streaming & control
6. simple-agent   → Tool use (function calling)
7. memory-agent   → Persistent state
8. react-agent    → Strategic reasoning + tool use
9. aot-agent      → Atomic planning
10. error-handling → Resilience
11. tree-of-thought → Branch search
12. graph-of-thought → DAG merge
```

---

## 八、与普罗米修斯框架的关联

### 可借鉴的模式

1. **ReAct 模式**：可用于 Agent 的工具调用和推理循环
2. **AoT 模式**：可用于基因编辑的确定性执行
3. **ToT/GoT 模式**：可用于复杂决策和规划
4. **错误处理**：已集成到 correction.py 和 reflection.py

### Xget 集成的关联

- Xget 的 fallback 机制借鉴了错误处理模式
- 任务路由策略借鉴了 AoT 的确定性执行理念
- 超时和重试机制遵循了错误处理的最佳实践

---

## 九、决策指南

### 选择推理模式

| 场景 | 推荐模式 |
|------|---------|
| 简单工具调用 | Simple Agent |
| 多步骤问题 | ReAct |
| 可审计工作流 | AoT |
| 需要明确赢家 | ToT |
| 多视角融合 | GoT |

### 选择依据

- **ToT**：时间紧、需要单一方向、保持多路径成本高
- **GoT**：问题模糊、弱信号有价值、需要保留矛盾

---

## 十、参考资料

- **原始仓库**：https://github.com/pguso/ai-agents-from-scratch
- **配套网站**：https://agentsfromscratch.com
- **ReAct 论文**：https://arxiv.org/abs/2210.03629

---

*此知识库由普罗米修斯框架自动整合*
*用于 Agent 架构设计和优化参考*
