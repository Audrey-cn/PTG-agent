from __future__ import annotations

MODEL_CATALOG: dict[str, list[dict]] = {
    "openai": [
        {
            "id": "gpt-4o",
            "context_length": 128000,
            "description": "GPT-4o flagship multimodal model",
            "pricing": {"in": 2.5, "out": 10.0},
        },
        {
            "id": "gpt-4o-mini",
            "context_length": 128000,
            "description": "GPT-4o mini cost-efficient model",
            "pricing": {"in": 0.15, "out": 0.6},
        },
        {
            "id": "gpt-4-turbo",
            "context_length": 128000,
            "description": "GPT-4 Turbo with vision",
            "pricing": {"in": 10.0, "out": 30.0},
        },
        {
            "id": "o1",
            "context_length": 200000,
            "description": "O1 reasoning model",
            "pricing": {"in": 15.0, "out": 60.0},
        },
        {
            "id": "o3-mini",
            "context_length": 200000,
            "description": "O3 mini reasoning model",
            "pricing": {"in": 1.1, "out": 4.4},
        },
    ],
    "anthropic": [
        {
            "id": "claude-3.5-sonnet",
            "context_length": 200000,
            "description": "Claude 3.5 Sonnet balanced model",
            "pricing": {"in": 3.0, "out": 15.0},
        },
        {
            "id": "claude-3-opus",
            "context_length": 200000,
            "description": "Claude 3 Opus powerful model",
            "pricing": {"in": 15.0, "out": 75.0},
        },
        {
            "id": "claude-3-haiku",
            "context_length": 200000,
            "description": "Claude 3 Haiku fast model",
            "pricing": {"in": 0.25, "out": 1.25},
        },
    ],
    "deepseek": [
        {
            "id": "deepseek-chat",
            "context_length": 64000,
            "description": "DeepSeek Chat general model",
            "pricing": {"in": 0.14, "out": 0.28},
        },
        {
            "id": "deepseek-v3",
            "context_length": 64000,
            "description": "DeepSeek V3 model",
            "pricing": {"in": 0.27, "out": 1.1},
        },
    ],
    "google": [
        {
            "id": "gemini-2.0-flash",
            "context_length": 1048576,
            "description": "Gemini 2.0 Flash fast model",
            "pricing": {"in": 0.1, "out": 0.4},
        },
        {
            "id": "gemini-1.5-pro",
            "context_length": 2097152,
            "description": "Gemini 1.5 Pro long context model",
            "pricing": {"in": 1.25, "out": 5.0},
        },
    ],
    "xai": [
        {
            "id": "grok-2",
            "context_length": 131072,
            "description": "Grok-2 model",
            "pricing": {"in": 2.0, "out": 10.0},
        },
    ],
    "openrouter": [
        {
            "id": "auto",
            "context_length": 128000,
            "description": "OpenRouter auto routing",
            "pricing": {"in": 0.0, "out": 0.0},
        },
    ],
}


def get_model_info(model_id: str) -> dict | None:
    for models in MODEL_CATALOG.values():
        for entry in models:
            if entry["id"] == model_id:
                return entry
    return None


def list_models(provider: str | None = None) -> list[dict]:
    if provider is None:
        result: list[dict] = []
        for models in MODEL_CATALOG.values():
            result.extend(models)
        return result
    return list(MODEL_CATALOG.get(provider, []))


def get_pricing(model_id: str) -> dict:
    info = get_model_info(model_id)
    if info is None:
        return {"in": 0.0, "out": 0.0}
    return info["pricing"]
