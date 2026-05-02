# Prometheus 浏览器自动化集成文档

## 概述

Prometheus 通过 `agent-browser` 实现了深度浏览器自动化集成，支持 AI Agent 在对话中执行网页浏览、截图、元素交互等操作。

## 安装状态

| 组件 | 状态 | 路径/版本 |
|------|------|----------|
| agent-browser | ✅ 已安装（本地） | `node_modules/.bin/agent-browser` v0.26.0 |
| npx | ✅ 可用 | v11.12.1 |
| 系统浏览器 | ✅ Safari | `/Applications/Safari.app` |

## 架构设计

### 1. 工具注册

浏览器工具在 `prometheus/tools/browser/browser_tool.py` 中注册，提供以下工具：

| 工具名 | 功能 | agent-browser 命令 |
|--------|------|-------------------|
| `browser_navigate` | 打开网页URL | `open <url>` |
| `browser_snapshot` | 获取页面可访问性树 | `snapshot` |
| `browser_click` | 点击页面元素 | `click <sel>` |
| `browser_type` | 在页面输入文本 | `type <sel> <text>` |
| `browser_fill` | 填充表单字段 | `fill <sel> <text>` |
| `browser_press` | 按键操作 | `press <key>` |
| `browser_hover` | 鼠标悬停 | `hover <sel>` |
| `browser_screenshot` | 页面截图 | `screenshot [path]` |
| `browser_evaluate` | 执行 JavaScript | `eval <js>` |
| `browser_wait` | 等待元素/时间 | `wait <sel|ms>` |
| `browser_close` | 关闭浏览器 | `close` |
| `browser_extract` | 提取页面内容 | `extract` |

### 2. 浏览器发现逻辑

`browser_tool.py` 中的 `_find_agent_browser()` 函数按以下顺序查找 agent-browser：

1. **系统 PATH** - `shutil.which("agent-browser")`
2. **扩展 PATH** - Homebrew 等自定义路径
3. **项目本地** - `node_modules/.bin/agent-browser` ✅ 当前使用此方式
4. **npx fallback** - `npx agent-browser`（无需安装，首次调用较慢）

### 3. 浏览器路由

agent-browser 自动检测并使用系统已有的浏览器：
- **macOS**: Safari、Chrome、Edge、Firefox 等
- **Linux**: Chrome、Chromium、Firefox 等
- 不需要单独下载 Chrome（除非系统无浏览器）

## Agent 中的使用

在 Agent 对话中调用浏览器工具的流程：

```python
# Agent 内部调用
result = agent._execute_tool("browser_navigate", {"url": "https://example.com"})
result = agent._execute_tool("browser_snapshot", {})
result = agent._execute_tool("browser_click", {"selector": "@e1"})
```

## Session 管理

agent-browser 使用 socket 进行进程间通信：

```
/tmp/agent-browser-p_<pid>/
/tmp/agent-browser-cdp_<pid>/
/tmp/agent-browser-prometheus_<session>/
```

每个 session 独立，支持多会话并行。

## 配置选项

### 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `AGENT_BROWSER_SOCKET_DIR` | Socket 目录 | `/tmp/agent-browser-*` |
| `AGENT_BROWSER_IDLE_TIMEOUT_MS` | 空闲超时（毫秒） | 300000 (5分钟) |
| `BROWSER_SESSION_INACTIVITY_TIMEOUT` | 会话不活动超时（秒） | 300 |

### CDP 覆盖

可通过环境变量指定远程浏览器 CDP URL：
```bash
export AGENT_BROWSER_CDP_URL="http://localhost:9222"
```

## 测试验证

```bash
# 1. 验证安装
/Users/audrey/ptg-agent/node_modules/.bin/agent-browser --version

# 2. 测试导航
/Users/audrey/ptg-agent/node_modules/.bin/agent-browser open "https://example.com" --session test

# 3. 获取页面快照
/Users/audrey/ptg-agent/node_modules/.bin/agent-browser snapshot --session test

# 4. 关闭
/Users/audrey/ptg-agent/node_modules/.bin/agent-browser close --all

# 5. Agent 中测试
prometheus chat
>>> 打开 https://github.com 并截图
```

## 依赖管理

`package.json` 中已记录依赖：
```json
{
  "dependencies": {
    "agent-browser": "^0.26.0"
  }
}
```

安装/更新：
```bash
cd /Users/audrey/ptg-agent
npm install agent-browser
```

## 注意事项

1. **不需要下载 Chrome** - agent-browser 自动使用系统浏览器
2. **首次调用可能有启动延迟** - 约 2-5 秒启动浏览器进程
3. **Safari 限制** - Safari 的自动化支持可能有限，推荐 Chrome/Edge
4. **Session 清理** - 不使用时自动清理，也可手动 `close --all`
