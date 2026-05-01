from __future__ import annotations

import json
import os
import logging
from typing import Any, Optional
from abc import ABC, abstractmethod

logger = logging.getLogger("prometheus.transports")


class BaseTransport(ABC):
    @abstractmethod
    def create_completion(
        self,
        model: str,
        messages: list[dict],
        max_tokens: int = 4096,
        temperature: float = 0.7,
        tools: list[dict] | None = None,
        **kwargs,
    ) -> dict:
        ...

    def get_model_key(self) -> str:
        return "openai"


class OpenAITransport(BaseTransport):
    def __init__(self, api_key: str, base_url: str = "https://api.openai.com/v1"):
        from openai import OpenAI
        self._client = OpenAI(api_key=api_key, base_url=base_url, timeout=300, max_retries=2)

    def create_completion(self, model, messages, max_tokens=4096, temperature=0.7, tools=None, **kwargs):
        k = {"model": model, "messages": messages, "max_tokens": max_tokens, "temperature": temperature}
        if tools:
            k["tools"] = tools
        response = self._client.chat.completions.create(**k)
        choice = response.choices[0]
        msg = choice.message
        result = {
            "content": msg.content,
            "tool_calls": None,
            "finish_reason": choice.finish_reason,
            "usage": {
                "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                "completion_tokens": response.usage.completion_tokens if response.usage else 0,
            },
        }
        if msg.tool_calls:
            result["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                }
                for tc in msg.tool_calls
            ]
        return result


class AnthropicTransport(BaseTransport):
    def __init__(self, api_key: str, base_url: str = "https://api.anthropic.com"):
        try:
            import anthropic
            self._client = anthropic.Anthropic(api_key=api_key, timeout=300, max_retries=2)
        except ImportError:
            raise ImportError("anthropic package required: pip install anthropic")

    def get_model_key(self):
        return "anthropic"

    def create_completion(self, model, messages, max_tokens=4096, temperature=0.7, tools=None, **kwargs):
        system_msg = ""
        chat_messages = []
        for m in messages:
            if m.get("role") == "system":
                system_msg = m.get("content", "")
            elif m.get("role") == "tool":
                continue
            elif m.get("role") == "assistant" and m.get("tool_calls"):
                chat_messages.append({"role": "assistant", "content": m.get("content", "") or ""})
            else:
                chat_messages.append({"role": m["role"], "content": m.get("content", "")})

        k = {
            "model": model,
            "messages": chat_messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if system_msg:
            k["system"] = system_msg
        if tools:
            k["tools"] = self._convert_tools(tools)

        response = self._client.messages.create(**k)
        text_content = ""
        tool_calls = []
        tc_id_counter = 0
        for block in response.content:
            if block.type == "text":
                text_content += block.text
            elif block.type == "tool_use":
                tool_calls.append({
                    "id": block.id,
                    "type": "function",
                    "function": {
                        "name": block.name,
                        "arguments": json.dumps(block.input, ensure_ascii=False),
                    },
                })
                tc_id_counter += 1

        return {
            "content": text_content,
            "tool_calls": tool_calls if tool_calls else None,
            "finish_reason": "tool_calls" if tool_calls else "stop",
            "usage": {
                "prompt_tokens": response.usage.input_tokens if response.usage else 0,
                "completion_tokens": response.usage.output_tokens if response.usage else 0,
            },
        }

    def _convert_tools(self, openai_tools: list[dict]) -> list[dict]:
        anthropic_tools = []
        for t in openai_tools:
            func = t.get("function", {})
            anthropic_tools.append({
                "name": func.get("name", ""),
                "description": func.get("description", ""),
                "input_schema": func.get("parameters", {"type": "object", "properties": {}}),
            })
        return anthropic_tools


class BedrockTransport(BaseTransport):
    def __init__(self, api_key: str = "", base_url: str = "", region: str = "us-east-1"):
        try:
            import boto3
            self._client = boto3.client("bedrock-runtime", region_name=region)
        except ImportError:
            raise ImportError("boto3 required: pip install boto3")
        self._region = region

    def get_model_key(self):
        return "bedrock"

    def create_completion(self, model, messages, max_tokens=4096, temperature=0.7, tools=None, **kwargs):
        system_msg = ""
        chat_messages = []
        for m in messages:
            if m.get("role") == "system":
                system_msg = m.get("content", "")
            elif m.get("role") in ("user", "assistant"):
                chat_messages.append({"role": m["role"], "content": [{"type": "text", "text": m.get("content", "")}]})

        body = {
            "anthropic_version": "bedrock-2023-05-31",
            "messages": chat_messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if system_msg:
            body["system"] = system_msg

        response = self._client.invoke_model(
            modelId=model,
            body=json.dumps(body),
            contentType="application/json",
        )
        result_body = json.loads(response["body"].read())
        text = ""
        for block in result_body.get("content", []):
            if block.get("type") == "text":
                text += block.get("text", "")

        return {
            "content": text,
            "tool_calls": None,
            "finish_reason": result_body.get("stop_reason", "stop"),
            "usage": {
                "prompt_tokens": result_body.get("usage", {}).get("input_tokens", 0),
                "completion_tokens": result_body.get("usage", {}).get("output_tokens", 0),
            },
        }


class CodexTransport(BaseTransport):
    def __init__(self, api_key: str, base_url: str = "https://api.openai.com/v1"):
        from openai import OpenAI
        self._client = OpenAI(api_key=api_key, base_url=base_url, timeout=300, max_retries=2)

    def get_model_key(self):
        return "codex"

    def create_completion(self, model, messages, max_tokens=4096, temperature=0.7, tools=None, **kwargs):
        k = {"model": model, "messages": messages, "max_tokens": max_tokens}
        if tools:
            k["tools"] = tools
        response = self._client.responses.create(**k)
        text = ""
        for item in response.output:
            if hasattr(item, "content") and item.type == "message":
                for block in item.content:
                    if hasattr(block, "text"):
                        text += block.text
        return {
            "content": text,
            "tool_calls": None,
            "finish_reason": "stop",
            "usage": {
                "prompt_tokens": getattr(response, "usage", None) and response.usage.input_tokens or 0,
                "completion_tokens": getattr(response, "usage", None) and response.usage.output_tokens or 0,
            },
        }


class GeminiTransport(BaseTransport):
    def __init__(self, api_key: str, base_url: str = ""):
        try:
            import google.generativeai as genai
            genai.configure(api_key=api_key)
            self._genai = genai
        except ImportError:
            raise ImportError("google-generativeai required: pip install google-generativeai")

    def get_model_key(self):
        return "gemini"

    def create_completion(self, model, messages, max_tokens=4096, temperature=0.7, tools=None, **kwargs):
        gemini_messages = []
        system_instruction = None
        for m in messages:
            if m.get("role") == "system":
                system_instruction = m.get("content", "")
            elif m.get("role") == "user":
                gemini_messages.append({"role": "user", "parts": [m.get("content", "")]})
            elif m.get("role") == "assistant":
                gemini_messages.append({"role": "model", "parts": [m.get("content", "")]})

        gen_model = self._genai.GenerativeModel(
            model_name=model,
            system_instruction=system_instruction,
        )
        chat = gen_model.start_chat(history=gemini_messages[:-1] if gemini_messages else [])
        last = gemini_messages[-1]["parts"][0] if gemini_messages else ""

        response = chat.send_message(
            last,
            generation_config=self._genai.types.GenerationConfig(
                max_output_tokens=max_tokens,
                temperature=temperature,
            ),
        )
        return {
            "content": response.text or "",
            "tool_calls": None,
            "finish_reason": "stop",
            "usage": {
                "prompt_tokens": response.usage_metadata.prompt_token_count if response.usage_metadata else 0,
                "completion_tokens": response.usage_metadata.candidates_token_count if response.usage_metadata else 0,
            },
        }


def create_transport(
    provider: str,
    api_key: str,
    base_url: str = "",
    **kwargs,
) -> BaseTransport:
    provider_lower = provider.lower()

    if provider_lower in ("anthropic", "claude"):
        return AnthropicTransport(api_key=api_key, base_url=base_url)
    if provider_lower in ("bedrock", "aws"):
        return BedrockTransport(api_key=api_key, region=kwargs.get("region", "us-east-1"))
    if provider_lower in ("codex", "openai-codex"):
        return CodexTransport(api_key=api_key, base_url=base_url or "https://api.openai.com/v1")
    if provider_lower in ("gemini", "google"):
        return GeminiTransport(api_key=api_key)

    return OpenAITransport(api_key=api_key, base_url=base_url or "https://api.openai.com/v1")
