from __future__ import annotations

#!/usr/bin/env python3
"""Prometheus Mixture-of-Agents Tool Module."""

import asyncio
import datetime
import json
import logging
import os
from typing import Any

try:
    from .agent_loop import AgentConfig, AIAgent
except ImportError:
    from agent_loop import AgentConfig, AIAgent

logger = logging.getLogger("prometheus.moa")

REFERENCE_MODELS = [
    "anthropic/claude-3-opus",
    "google/gemini-2.5-pro",
    "openai/gpt-4o",
    "deepseek/deepseek-chat",
]

AGGREGATOR_MODEL = "anthropic/claude-3-opus"

REFERENCE_TEMPERATURE = 0.6
AGGREGATOR_TEMPERATURE = 0.4

MIN_SUCCESSFUL_REFERENCES = 1

AGGREGATOR_SYSTEM_PROMPT = """You have been provided with a set of responses from various models to the latest user query. Your task is to synthesize these responses into a single, high-quality response. It is crucial to critically evaluate the information provided in these responses, recognizing that some of it may be biased or incorrect. Your response should not simply replicate the given answers but should offer a refined, accurate, and comprehensive reply to the instruction. Ensure your response is well-structured, coherent, and adheres to the highest standards of accuracy and reliability.

Responses from models:"""


def _construct_aggregator_prompt(system_prompt: str, responses: list[str]) -> str:
    """构建聚合器的完整系统提示词"""
    response_text = "\n".join([f"{i + 1}. {response}" for i, response in enumerate(responses)])
    return f"{system_prompt}\n\n{response_text}"


async def _run_reference_model_safe(
    model: str,
    user_prompt: str,
    provider: str = "openrouter",
    temperature: float = REFERENCE_TEMPERATURE,
    max_tokens: int = 32000,
    max_retries: int = 6,
) -> Tuple[str, str, bool]:
    """安全运行单个参考模型，带有重试逻辑"""
    for attempt in range(max_retries):
        try:
            logger.info("Querying %s (attempt %s/%s)", model, attempt + 1, max_retries)

            agent_config = AgentConfig(
                provider=provider,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            agent = AIAgent(config=agent_config)
            response = await agent.run_conversation(user_prompt)

            content = response.content
            if not content:
                logger.warning(
                    "%s returned empty content (attempt %s/%s), retrying",
                    model,
                    attempt + 1,
                    max_retries,
                )
                if attempt < max_retries - 1:
                    await asyncio.sleep(min(2 ** (attempt + 1), 60))
                    continue

            logger.info("%s responded (%s characters)", model, len(content))
            return model, content, True

        except Exception as e:
            error_str = str(e)
            logger.warning("%s error (attempt %s): %s", model, attempt + 1, error_str)

            if attempt < max_retries - 1:
                sleep_time = min(2 ** (attempt + 1), 60)
                logger.info("Retrying in %ss...", sleep_time)
                await asyncio.sleep(sleep_time)
            else:
                error_msg = f"{model} failed after {max_retries} attempts: {error_str}"
                logger.error("%s", error_msg)
                return model, error_msg, False


async def _run_aggregator_model(
    system_prompt: str,
    user_prompt: str,
    provider: str = "openrouter",
    model: str = AGGREGATOR_MODEL,
    temperature: float = AGGREGATOR_TEMPERATURE,
    max_tokens: int = 32000,
) -> str:
    """运行聚合器模型综合最终响应"""
    logger.info("Running aggregator model: %s", model)

    agent_config = AgentConfig(
        provider=provider,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    agent = AIAgent(config=agent_config)

    response = await agent.run_conversation(user_prompt, system_message=system_prompt)
    content = response.content

    if not content:
        logger.warning("Aggregator returned empty content, retrying once")
        response = await agent.run_conversation(user_prompt, system_message=system_prompt)
        content = response.content

    logger.info("Aggregation complete (%s characters)", len(content))
    return content


async def mixture_of_agents_tool(
    user_prompt: str,
    reference_models: list[str] | None = None,
    aggregator_model: str | None = None,
    provider: str = "openrouter",
) -> str:
    """
    使用混合代理方法处理复杂查询。

    两层架构:
    1. Layer 1: 多个参考模型并行生成多样化响应 (temp=0.6)
    2. Layer 2: 聚合器模型综合最佳元素成最终响应 (temp=0.4)

    Args:
        user_prompt: 要解决的复杂查询或问题
        reference_models: 自定义参考模型列表
        aggregator_model: 自定义聚合器模型
        provider: AI 服务提供商

    Returns:
        JSON 字符串，包含 MoA 结果
    """
    start_time = datetime.datetime.now()

    debug_call_data = {
        "parameters": {
            "user_prompt": user_prompt[:200] + "..." if len(user_prompt) > 200 else user_prompt,
            "reference_models": reference_models or REFERENCE_MODELS,
            "aggregator_model": aggregator_model or AGGREGATOR_MODEL,
            "reference_temperature": REFERENCE_TEMPERATURE,
            "aggregator_temperature": AGGREGATOR_TEMPERATURE,
            "min_successful_references": MIN_SUCCESSFUL_REFERENCES,
        },
        "error": None,
        "success": False,
        "reference_responses_count": 0,
        "failed_models_count": 0,
        "failed_models": [],
        "final_response_length": 0,
        "processing_time_seconds": 0,
        "models_used": {},
    }

    try:
        logger.info("Starting Mixture-of-Agents processing...")
        logger.info("Query: %s", user_prompt[:100])

        ref_models = reference_models or REFERENCE_MODELS
        agg_model = aggregator_model or AGGREGATOR_MODEL

        logger.info("Using %s reference models in 2-layer MoA architecture", len(ref_models))

        # Layer 1: 并行生成参考响应
        logger.info("Layer 1: Generating reference responses...")
        model_results = await asyncio.gather(
            *[
                _run_reference_model_safe(model, user_prompt, provider, REFERENCE_TEMPERATURE)
                for model in ref_models
            ]
        )

        successful_responses = []
        failed_models = []

        for model_name, content, success in model_results:
            if success:
                successful_responses.append(content)
            else:
                failed_models.append(model_name)

        successful_count = len(successful_responses)
        failed_count = len(failed_models)

        logger.info(
            "Reference model results: %s successful, %s failed", successful_count, failed_count
        )

        if failed_models:
            logger.warning("Failed models: %s", ", ".join(failed_models))

        if successful_count < MIN_SUCCESSFUL_REFERENCES:
            raise ValueError(
                f"Insufficient successful reference models ({successful_count}/{len(ref_models)}). Need at least {MIN_SUCCESSFUL_REFERENCES} successful responses."
            )

        debug_call_data["reference_responses_count"] = successful_count
        debug_call_data["failed_models_count"] = failed_count
        debug_call_data["failed_models"] = failed_models

        # Layer 2: 使用聚合器综合响应
        logger.info("Layer 2: Synthesizing final response...")
        aggregator_system_prompt = _construct_aggregator_prompt(
            AGGREGATOR_SYSTEM_PROMPT, successful_responses
        )

        final_response = await _run_aggregator_model(
            aggregator_system_prompt, user_prompt, provider, agg_model, AGGREGATOR_TEMPERATURE
        )

        end_time = datetime.datetime.now()
        processing_time = (end_time - start_time).total_seconds()

        logger.info("MoA processing completed in %.2f seconds", processing_time)

        result = {
            "success": True,
            "response": final_response,
            "models_used": {"reference_models": ref_models, "aggregator_model": agg_model},
            "processing_time": processing_time,
        }

        debug_call_data["success"] = True
        debug_call_data["final_response_length"] = len(final_response)
        debug_call_data["processing_time_seconds"] = processing_time
        debug_call_data["models_used"] = result["models_used"]

        return json.dumps(result, indent=2, ensure_ascii=False)

    except Exception as e:
        error_msg = f"Error in MoA processing: {str(e)}"
        logger.error("%s", error_msg)

        end_time = datetime.datetime.now()
        processing_time = (end_time - start_time).total_seconds()

        result = {
            "success": False,
            "response": "MoA processing failed. Please try again or use a single model for this query.",
            "models_used": {
                "reference_models": reference_models or REFERENCE_MODELS,
                "aggregator_model": aggregator_model or AGGREGATOR_MODEL,
            },
            "error": error_msg,
            "processing_time": processing_time,
        }

        debug_call_data["error"] = error_msg
        debug_call_data["processing_time_seconds"] = processing_time

        return json.dumps(result, indent=2, ensure_ascii=False)


def check_moa_requirements() -> bool:
    """检查 MoA 工具的所有要求是否满足"""
    api_key = os.getenv("OPENROUTER_API_KEY")
    return api_key is not None and len(api_key) > 0


def get_moa_configuration() -> dict[str, Any]:
    """获取当前 MoA 配置设置"""
    return {
        "reference_models": REFERENCE_MODELS,
        "aggregator_model": AGGREGATOR_MODEL,
        "reference_temperature": REFERENCE_TEMPERATURE,
        "aggregator_temperature": AGGREGATOR_TEMPERATURE,
        "min_successful_references": MIN_SUCCESSFUL_REFERENCES,
        "total_reference_models": len(REFERENCE_MODELS),
        "failure_tolerance": f"{len(REFERENCE_MODELS) - MIN_SUCCESSFUL_REFERENCES}/{len(REFERENCE_MODELS)} models can fail",
    }


def register_moa_tool():
    """注册 MoA 工具到工具注册表"""
    from .tools.registry import registry

    MOA_SCHEMA = {
        "name": "mixture_of_agents",
        "description": "Route a hard problem through multiple frontier LLMs collaboratively. Makes 5 API calls (4 reference models + 1 aggregator) with maximum reasoning effort — use sparingly for genuinely difficult problems. Best for: complex math, advanced algorithms, multi-step analytical reasoning, problems benefiting from diverse perspectives.",
        "parameters": {
            "type": "object",
            "properties": {
                "user_prompt": {
                    "type": "string",
                    "description": "The complex query or problem to solve using multiple AI models. Should be a challenging problem that benefits from diverse perspectives and collaborative reasoning.",
                }
            },
            "required": ["user_prompt"],
        },
    }

    registry.register(
        name="mixture_of_agents",
        toolset="moa",
        schema=MOA_SCHEMA,
        handler=lambda args, **kw: mixture_of_agents_tool(user_prompt=args.get("user_prompt", "")),
        check_fn=check_moa_requirements,
        description="Mixture-of-Agents tool for complex reasoning tasks",
        emoji="🧠",
    )


if __name__ == "__main__":
    print("🤖 Mixture-of-Agents Tool Module")
    print("=" * 50)

    api_available = check_moa_requirements()

    if not api_available:
        print("❌ OPENROUTER_API_KEY environment variable not set")
        print("Please set your API key: export OPENROUTER_API_KEY='your-key-here'")
        print("Get API key at: https://openrouter.ai/")
        exit(1)
    else:
        print("✅ OpenRouter API key found")

    print("🛠️  MoA tools ready for use!")

    config = get_moa_configuration()
    print("\n⚙️  Current Configuration:")
    print(
        f"  🤖 Reference models ({len(config['reference_models'])}): {', '.join(config['reference_models'])}"
    )
    print(f"  🧠 Aggregator model: {config['aggregator_model']}")
    print(f"  🌡️  Reference temperature: {config['reference_temperature']}")
    print(f"  🌡️  Aggregator temperature: {config['aggregator_temperature']}")
    print(f"  🛡️  Failure tolerance: {config['failure_tolerance']}")
    print(f"  📊 Minimum successful models: {config['min_successful_references']}")
