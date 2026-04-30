# Xget 集成使用指南

## 概述

Xget 集成模块为普罗米修斯 agent 提供了 GitHub、Hugging Face 等资源的加速访问功能，并包含了完善的任务路由和 fallback 机制，防止网络卡死。

## 主要功能

1. **多平台支持**：GitHub、Hugging Face、PyPI、npm 等
2. **智能路由**：多 Xget 实例负载均衡和故障转移
3. **Fallback 机制**：加速失败时自动回退到原始 URL
4. **超时保护**：防止请求卡死
5. **自动重试**：智能重试机制

## 安装依赖

```bash
pip install -r requirements.txt
```

## 快速使用

### 1. 基本 URL 转换

```python
from xget_integration import xget_convert

# 转换 GitHub URL
url = "https://github.com/xixu-me/xget"
accelerated_url = xget_convert(url)
print(f"原始 URL: {url}")
print(f"加速 URL: {accelerated_url}")
```

### 2. 发送加速请求

```python
import asyncio
from xget_integration import xget_request

async def main():
    url = "https://github.com/xixu-me/xget"
    result = await xget_request(url)
    
    print(f"成功: {result.success}")
    print(f"URL: {result.url}")
    if result.instance_used:
        print(f"使用实例: {result.instance_used}")
    if result.fallback_used:
        print(f"⚠️ Fallback 到原始 URL")
    if result.status_code:
        print(f"状态码: {result.status_code}")
    print(f"响应时间: {result.response_time:.2f}s")

asyncio.run(main())
```

### 3. 自定义配置

```python
from xget_integration import XgetIntegration

config = {
    "enabled": True,
    "default_instance": "https://xget.xi-xu.me",
    "fallback_enabled": True,
    "request_timeout_seconds": 30,
    "max_retries": 3,
    "retry_delay_seconds": 1.0,
    "load_balancing": "weighted_round_robin",
    "instances": [
        {"url": "https://xget.xi-xu.me", "priority": 0, "weight": 3},
        {"url": "https://your-mirror.example.com", "priority": 1, "weight": 2},
    ],
}

xget = XgetIntegration(config)
```

### 4. 查看状态

```python
from xget_integration import get_xget

xget = get_xget()
status = xget.get_status()
print(f"Xget 状态: {status}")
```

## 配置文件

在 `prometheus/config.yaml` 中已经包含了 Xget 的配置：

```yaml
xget:
  enabled: true
  default_instance: "https://xget.xi-xu.me"
  fallback_enabled: true
  request_timeout_seconds: 30
  max_retries: 3
  retry_delay_seconds: 1.0
  load_balancing: "weighted_round_robin"
  
  instances:
    - url: "https://xget.xi-xu.me"
      priority: 0
      weight: 3
      enabled: true
  
  platforms:
    github:
      enabled: true
      xget_prefix: "https://xget.xi-xu.me/gh/"
    huggingface:
      enabled: true
      xget_prefix: "https://xget.xi-xu.me/hf/"
    pypi:
      enabled: true
      xget_prefix: "https://xget.xi-xu.me/pypi/"
    npm:
      enabled: true
      xget_prefix: "https://xget.xi-xu.me/npm/"
```

## 运行测试

```bash
cd prometheus
python tests/test_xget_integration.py
```

## 命令行测试

```bash
# 转换 URL
python xget_integration.py convert https://github.com/xixu-me/xget

# 查看状态
python xget_integration.py status

# 测试请求
python xget_integration.py test https://github.com/xixu-me/xget
```

## 架构说明

### 任务路由策略

1. **priority（优先级）**：按照配置的优先级顺序选择实例
2. **random（随机）**：在可用实例中随机选择
3. **weighted_round_robin（加权轮询）**：根据权重分配请求

### Fallback 机制

当所有 Xget 实例都失败时，系统会自动 fallback 到原始 URL，确保请求不会丢失。

### 防止网络卡死

- 请求超时控制（默认 30 秒）
- 失败实例自动冷却（默认 60 秒）
- 最大重试次数限制（默认 3 次）
- 重试延迟递增策略

## 支持的平台

- GitHub
- GitLab
- Hugging Face
- PyPI
- npm
- CivitAI
- 更多平台可扩展

## 高级用法

### 自定义平台配置

```python
from xget_integration import XgetIntegration, Platform

xget = XgetIntegration()
# 可以通过 config 参数自定义平台配置
```

### 直接使用原始请求

```python
# 禁用 Xget 加速，直接请求原始 URL
config = {"enabled": False}
xget = XgetIntegration(config)
result = await xget.request(url)
```

## 故障排查

如果遇到问题，请检查：

1. 网络连接是否正常
2. Xget 实例是否可访问
3. 配置文件是否正确
4. 依赖是否已安装

可以使用 `xget.get_status()` 查看当前状态。
