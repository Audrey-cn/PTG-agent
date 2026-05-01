from __future__ import annotations

ALIASES: dict[str, str] = {
    "gpt4": "gpt-4o",
    "4o": "gpt-4o",
    "sonnet": "claude-3.5-sonnet",
    "opus": "claude-3-opus",
    "haiku": "claude-3-haiku",
    "deepseek": "deepseek-chat",
    "v3": "deepseek-v3",
    "flash": "gemini-2.0-flash",
    "grok": "grok-2",
}

DIRECT_ALIASES: dict[str, str] = {
    "4o": "gpt-4o",
    "v3": "deepseek-v3",
}


def normalize_model_name(name: str) -> str:
    cleaned = name.strip().lower()
    if cleaned in ALIASES:
        return ALIASES[cleaned]
    return cleaned
