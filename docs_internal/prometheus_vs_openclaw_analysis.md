# Prometheus vs OpenClaw 源码级对标分析

**分析日期**: 2026-05-02
**对标目标**: `/Users/audrey/Downloads/openclaw-main` (v2026.5 系列)

---

## 一、项目定位对比

| 维度 | OpenClaw | Prometheus |
|------|----------|-----------|
| **定位** | Personal AI Assistant (个人 AI 助手) | AI Agent Framework (AI Agent 框架) |
| **语言** | TypeScript (Node 24) | Python 3.11+ |
| **架构** | Gateway (控制平面) + Channels + Nodes | 本地 Agent Loop + CLI + Tools |
| **核心愿景** | 在用户设备上运行的个人助手，通过多渠道交互 | 独立存在的造物主/创造者/引导者 |
| **设计哲学** | Local-first, security-first, plugin-extensible | 种子即框架, 自举进化, 碳基依赖级不可变基因 |
| **生态** | ClawHub (插件市场), ACPX 协议 | TTG 种子系统, 史诗编史官, 进化机制 |

---

## 二、核心架构差异

### 2.1 OpenClaw 架构 (Gateway-Centric)

```
┌─────────────────────────────────────────────────┐
│                  OpenClaw Gateway                │
│  ┌──────────┐  ┌──────────┐  ┌───────────────┐  │
│  │ Channels │  │  Agent   │  │    Tools      │  │
│  │(WhatsApp │  │  (btw)   │  │  (exec, browser│ │
│  │ Telegram │  │  (loop)  │  │  cron, skills) │ │
│  │ Discord  │  └──────────┘  └───────────────┘  │
│  │ Slack...)│       │              │            │
│  └──────────┘       │              │            │
│         ┌───────────┴──────────────┴──────────┐ │
│         │          Gateway Server             │ │
│         │    (WebSocket, auth, sessions)      │ │
│         └─────────────────────────────────────┘ │
└─────────────────────────────────────────────────┘
         │                    │
    ┌────┴────┐         ┌────┴────┐
    │  Nodes  │         │  Nodes  │
    │ (macOS) │         │(iOS/And)│
    └─────────┘         └─────────┘
```

### 2.2 Prometheus 架构 (Agent-Centric)

```
┌─────────────────────────────────────────────────┐
│              Prometheus Agent                    │
│  ┌───────────────────────────────────────────┐  │
│  │            Agent Loop                     │  │
│  │  ┌────────┐  ┌─────────┐  ┌───────────┐  │  │
│  │  │ LLM    │  │ Tool    │  │ Context   │  │  │
│  │  │Transp. │  │Registry │  │Compressor │  │  │
│  │  └────────┘  └─────────┘  └───────────┘  │  │
│  │       │           │             │        │  │
│  │  ┌────┴───────────┴─────────────┴──────┐ │  │
│  │  │         Session Manager            │ │  │
│  │  │    (Logger, Trajectory, Budget)    │ │  │
│  │  └────────────────────────────────────┘ │  │
│  └─────────────────────────────────────────┘  │
└─────────────────────────────────────────────────┘
         │
    ┌────┴────┐
    │  Tools  │
    │(48 tools)│
    └─────────┘
```

---

## 三、功能模块对标

### 3.1 消息渠道集成

| 渠道 | OpenClaw | Prometheus | 差距 |
|------|----------|-----------|------|
| **WhatsApp** | ✅ 原生 | ❌ 无 | ⚠️ 大差距 |
| **Telegram** | ✅ 原生 | ❌ 无 | ⚠️ 大差距 |
| **Slack** | ✅ 原生 | ❌ 无 | ⚠️ 大差距 |
| **Discord** | ✅ 原生 | ❌ 无 | ⚠️ 大差距 |
| **Signal** | ✅ 原生 | ❌ 无 | ⚠️ 大差距 |
| **iMessage** | ✅ 原生 | ❌ 无 | ⚠️ 大差距 |
| **IRC** | ✅ 原生 | ❌ 无 | ⚠️ 大差距 |
| **LINE** | ✅ 原生 | ❌ 无 | ⚠️ 大差距 |
| **Matrix** | ✅ 原生 | ❌ 无 | ⚠️ 大差距 |
| **WebChat** | ✅ 原生 (Web UI) | ⚠️ CLI only | ⚠️ 中差距 |
| **CLI** | ✅ | ✅ | ✅ 持平 |

**结论**: Prometheus 目前仅支持 CLI 交互，缺少多渠道集成。这是最大的差距。

### 3.2 工具系统

| 工具类别 | OpenClaw | Prometheus | 差距 |
|----------|----------|-----------|------|
| **终端执行** | ✅ exec (PTY) | ✅ terminal | ✅ 持平 |
| **文件读写** | ✅ read/write | ✅ read/write | ✅ 持平 |
| **浏览器** | ✅ browser | ✅ agent-browser | ✅ 持平 |
| **Web 搜索** | ✅ Tavily/Brave | ✅ Firecrawl/Exa/Tavily | ✅ 持平 |
| **Cron 任务** | ✅ cron | ✅ cronjob | ✅ 持平 |
| **Skill 系统** | ✅ SKILL.md | ✅ SKILL.md | ✅ 持平 |
| **Canvas** | ✅ A2UI Canvas | ❌ 无 | ⚠️ 有差距 |
| **节点控制** | ✅ nodes (iOS/Android) | ❌ 无 | ⚠️ 有差距 |
| **会话管理** | ✅ sessions | ✅ session_manager | ✅ 持平 |
| **MCP 集成** | ✅ MCP server/client | ⚠️ 基础支持 | ⚠️ 小差距 |
| **TTS/Voice** | ✅ ElevenLabs + TTS | ⚠️ voice_tools (需 API) | ⚠️ 小差距 |
| **PDF** | ✅ PDF tools | ❌ 无 | ⚠️ 有差距 |

### 3.3 Agent 能力

| 能力 | OpenClaw | Prometheus | 差距 |
|------|----------|-----------|------|
| **多 Agent** | ✅ Multi-agent routing | ✅ delegate 工具 | ⚠️ OpenClaw 更强 |
| **Agent 循环** | ✅ btw.ts (智能循环) | ✅ agent_loop.py | ✅ 持平 |
| **上下文压缩** | ✅ auto-compact | ✅ context_compressor | ✅ 持平 |
| **对话轨迹** | ✅ trace | ✅ trajectory tracker | ✅ 持平 |
| **Thinking 级别** | ✅ /think + thinking param | ✅ max_iterations | ⚠️ Prometheus 较弱 |
| **Usage 追踪** | ✅ /usage tokens|full | ⚠️ 无 | ⚠️ 有差距 |
| **Sandbox** | ✅ Docker/SSH/OpenShell | ⚠️ 安全策略但无沙箱 | ⚠️ 有差距 |

### 3.4 安全模型

| 安全特性 | OpenClaw | Prometheus | 差距 |
|----------|----------|-----------|------|
| **DM 配对** | ✅ pairing + allowFrom | ❌ 无 | ⚠️ 大差距 |
| **命令审批** | ✅ approvals | ✅ approval.py | ✅ 持平 |
| **沙箱执行** | ✅ Docker default | ❌ 无沙箱 | ⚠️ 有差距 |
| **写入保护** | ✅ path-based deny | ✅ _is_write_denied | ✅ 持平 |
| **敏感词检测** | ❌ 无 | ✅ semantic_audit | ✅ Prometheus 更强 |
| **预算控制** | ✅ usage limits | ✅ iteration_budget | ✅ 持平 |
| **安全审计** | ✅ audit + fix | ❌ 基础 | ⚠️ 有差距 |

### 3.5 用户体验

| 体验特性 | OpenClaw | Prometheus | 差距 |
|----------|----------|-----------|------|
| **CLI** | ✅ 完整 CLI | ✅ 完整 CLI | ✅ 持平 |
| **TUI** | ✅ TUI 界面 | ❌ 无 | ⚠️ 有差距 |
| **Web UI** | ✅ Control UI + WebChat | ❌ 无 | ⚠️ 有差距 |
| **皮肤系统** | ✅ theme | ✅ skin_engine | ✅ 持平 |
| **Onboarding** | ✅ onboard 向导 | ✅ setup 向导 | ✅ 持平 |
| **Daemon** | ✅ launchd/systemd | ❌ 无守护进程 | ⚠️ 有差距 |
| **Doctor** | ✅ openclaw doctor | ❌ 无 | ⚠️ 有差距 |
| **状态命令** | ✅ status/health | ⚠️ 基础 | ⚠️ 小差距 |

### 3.6 生态系统

| 生态特性 | OpenClaw | Prometheus | 差距 |
|----------|----------|-----------|------|
| **插件市场** | ✅ ClawHub | ❌ 无 | ⚠️ 大差距 |
| **插件 SDK** | ✅ plugin-sdk (npm) | ⚠️ 基础注册 | ⚠️ 有差距 |
| **扩展系统** | ✅ extensions | ❌ 无 | ⚠️ 有差距 |
| **Skills 市场** | ✅ ClawHub skills | ⚠️ 本地 skills | ⚠️ 有差距 |
| **社区** | ✅ Discord + 500+ 贡献者 | ⚠️ 个人项目 | ⚠️ 大差距 |
| **文档** | ✅ 完整 docs (docs.openclaw.ai) | ⚠️ 内部 docs | ⚠️ 有差距 |
| **测试** | ✅ vitest + E2E | ✅ pytest | ✅ 持平 |
| **CI/CD** | ✅ GitHub Actions | ⚠️ 基础 | ⚠️ 小差距 |

---

## 四、OpenClaw 独有特性 (Prometheus 缺少)

### 4.1 核心缺失 (大差距)

| # | 特性 | 描述 | 优先级 |
|---|------|------|--------|
| 1 | **多渠道集成** | WhatsApp/Telegram/Slack/Discord 等 25+ 渠道 | 🔴 高 |
| 2 | **Gateway 架构** | WebSocket 网关作为控制平面 | 🔴 高 |
| 3 | **Web UI** | Control UI + WebChat | 🔴 高 |
| 4 | **TUI 界面** | 终端用户界面 | 🟡 中 |
| 5 | **Daemon 守护** | launchd/systemd 服务 | 🟡 中 |
| 6 | **节点系统** | iOS/Android/macOS 节点 | 🟡 中 |
| 7 | **Canvas/A2UI** | 可视化 Canvas 工作区 | 🟡 中 |

### 4.2 功能缺失 (中差距)

| # | 特性 | 描述 | 优先级 |
|---|------|------|--------|
| 8 | **Sandbox 沙箱** | Docker/SSH 隔离执行 | 🟡 中 |
| 9 | **Usage 追踪** | Token 用量统计和可视化 | 🟡 中 |
| 10 | **Doctor 命令** | 系统健康检查 | 🟡 中 |
| 11 | **PDF 工具** | PDF 解析和处理 | 🟡 中 |
| 12 | **MCP 完整支持** | Server + Client 模式 | 🟡 中 |
| 13 | **Hook 系统** | 事件钩子和回调 | 🟡 中 |
| 14 | **代理/Proxy** | HTTP 代理支持 | 🟢 低 |

### 4.3 体验缺失 (小差距)

| # | 特性 | 描述 | 优先级 |
|---|------|------|--------|
| 15 | **Voice Wake** | 唤醒词监听 | 🟢 低 |
| 16 | **Talk Mode** | 连续语音对话 | 🟢 低 |
| 17 | **QR 配对** | 设备配对二维码 | 🟢 低 |
| 18 | **备份系统** | 配置和数据备份 | 🟢 低 |
| 19 | **迁移工具** | 版本迁移 | 🟢 低 |
| 20 | **Wiki 系统** | 知识库 | 🟢 低 |

---

## 五、Prometheus 独有优势 (OpenClaw 没有)

| # | 特性 | 描述 |
|---|------|------|
| 1 | **TTG 种子系统** | 自举式基因编码系统 |
| 2 | **编解码器** | Layer1/Layer2 语义压缩 (30:1+) |
| 3 | **史诗编史官** | stamp/trace/append 历史追踪 |
| 4 | **进化机制** | 提案 + 审核 + 追踪 |
| 5 | **皮肤引擎** | 数据驱动 CLI 视觉定制 |
| 6 | **语义审核** | 多维度语义评分 |
| 7 | **敏感词检测** | 内置敏感词筛查 |
| 8 | **多 Provider** | OpenAI/Anthropic/DeepSeek/通义千问等 |

---

## 六、差距总结

### 6.1 差距矩阵

```
                    | 核心差距 | 中差距 | 小差距 | 持平 | Prometheus更强
━━━━━━━━━━━━━━━━━━━━+━━━━━━━━━+━━━━━━━━+━━━━━━━━+━━━━━━+━━━━━━━━━━━━━━━
消息渠道            |    1     |    0   |    0   |  0   |      0
工具系统            |    1     |    3   |    2   |  6   |      0
Agent能力           |    0     |    1   |    1   |  4   |      1
安全模型            |    1     |    2   |    0   |  3   |      1
用户体验            |    3     |    2   |    1   |  2   |      0
生态系统            |    2     |    3   |    1   |  1   |      0
━━━━━━━━━━━━━━━━━━━━+━━━━━━━━━+━━━━━━━━+━━━━━━━━+━━━━━━+━━━━━━━━━━━━━━━
总计                |    8     |   11   |    5   |  16  |      2
```

### 6.2 关键差距 (按优先级排序)

| 优先级 | 差距 | 影响 | 建议 |
|--------|------|------|------|
| P0 | 多渠道集成 | 核心定位差异 | 考虑集成 1-2 个核心渠道 (Telegram/Discord) |
| P0 | Gateway 架构 | 缺少持久化服务 | 评估是否需要 WebSocket 网关 |
| P1 | Web UI | 用户体验限制 | 考虑轻量 Web 界面 |
| P1 | Sandbox | 安全边界缺失 | 集成 Docker 沙箱 |
| P2 | TUI | CLI 体验增强 | 可后续添加 |
| P2 | 节点系统 | 移动端支持 | 视需求决定 |
| P3 | 插件市场 | 生态扩展 | 长期目标 |

---

## 七、结论

### 7.1 总体评估

**Prometheus 是一个功能完整的本地 Agent 框架**，在核心 Agent Loop、工具系统、CLI 体验上与 OpenClaw 持平，并在语义压缩、编解码器、进化机制等方面有独特优势。

**主要差距在于生态和渠道**: OpenClaw 是一个成熟的 Personal AI Assistant 产品，支持 25+ 消息渠道、Web UI、移动端节点、插件市场等。Prometheus 目前定位更偏向开发者框架，缺少面向普通用户的交互渠道和可视化界面。

### 7.2 建议方向

**短期 (P0)**:
1. 集成 1-2 个核心消息渠道 (建议 Telegram 或 Discord)
2. 评估 Gateway 架构必要性
3. 实现 Sandbox 沙箱机制

**中期 (P1)**:
1. 添加 Web UI (可基于 OpenClaw 的 Control UI 设计)
2. 实现 Usage 追踪
3. 增强 MCP 支持

**长期 (P2-P3)**:
1. 插件市场/生态建设
2. 移动端节点
3. TUI 界面
4. Voice/Talk 模式
