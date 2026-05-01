from __future__ import annotations

import os
import sys
import logging
from typing import Optional

logger = logging.getLogger("prometheus.oneshot")


def oneshot(
    prompt: str,
    model: Optional[str] = None,
    system_prompt: Optional[str] = None,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    max_tokens: int = 4096,
    temperature: float = 0.7,
) -> str:
    if not prompt:
        if not sys.stdin.isatty():
            prompt = sys.stdin.read().strip()
        if not prompt:
            return "错误: 未提供输入。用法: echo 'prompt' | ptg oneshot 或 ptg oneshot 'prompt'"

    resolved_key = api_key or os.getenv("OPENAI_API_KEY", "")
    resolved_base = base_url or "https://api.openai.com/v1"
    resolved_model = model or "gpt-4o"

    provider = ""
    if not api_key:
        try:
            from prometheus.config import Config as PrometheusConfig
            cfg = PrometheusConfig.load()
            config_dict = cfg.to_dict()
            model_cfg = config_dict.get("model", {})
            api_cfg = config_dict.get("api", {})
            provider = model_cfg.get("provider", "")

            if not model:
                resolved_model = model_cfg.get("name", "") or "gpt-4o"
            if not base_url:
                resolved_base = api_cfg.get("base_url", "https://api.openai.com/v1")

            resolved_key = api_cfg.get("key", "") or resolved_key

            if provider == "anthropic":
                resolved_key = resolved_key or os.getenv("ANTHROPIC_API_KEY", "")
            elif provider == "openrouter":
                resolved_key = resolved_key or os.getenv("OPENROUTER_API_KEY", "")
                if not base_url:
                    resolved_base = "https://openrouter.ai/api/v1"
            elif provider == "deepseek":
                resolved_key = resolved_key or os.getenv("DEEPSEEK_API_KEY", "")
                if not base_url:
                    resolved_base = "https://api.deepseek.com/v1"
        except Exception:
            pass

    if not resolved_key:
        return "错误: 未配置 API Key。请运行 'ptg setup' 或设置环境变量。"

    resolved_system = system_prompt or (
        "You are Prometheus, the epic chronicler agent. "
        "Be concise and precise. Answer the user's question directly."
    )

    try:
        from prometheus.agent_loop import AIAgent
    except ImportError:
        try:
            from agent_loop import AIAgent
        except ImportError:
            return "错误: AIAgent 模块不可用"

    agent = AIAgent(
        system_prompt=resolved_system,
        api_key=resolved_key,
        base_url=resolved_base,
        model=resolved_model,
        max_iterations=10,
        max_tokens=max_tokens,
        temperature=temperature,
        provider=provider,
    )

    try:
        result = agent.run_conversation(prompt)
        return result.get("text", "")
    except Exception as e:
        logger.error("Oneshot execution failed: %s", e)
        return f"错误: {e}"
