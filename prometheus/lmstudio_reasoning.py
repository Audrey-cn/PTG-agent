from __future__ import annotations


class LMStudioReasoning:
    def __init__(self) -> None:
        self._enabled = False
        self._reasoning_prefix = "<reasoning>"
        self._reasoning_suffix = "</reasoning>"

    def enable_reasoning(self) -> None:
        self._enabled = True

    def disable_reasoning(self) -> None:
        self._enabled = False

    def is_reasoning_enabled(self) -> bool:
        return self._enabled

    def format_reasoning_prompt(self, prompt: str) -> str:
        if not self._enabled:
            return prompt
        return f"{self._reasoning_prefix}\n{prompt}\n{self._reasoning_suffix}"

    def extract_reasoning(self, response: str) -> Tuple[str, str]:
        if self._reasoning_prefix not in response:
            return "", response
        start = response.find(self._reasoning_prefix) + len(self._reasoning_prefix)
        end = response.find(self._reasoning_suffix)
        if end == -1:
            return response[start:], ""
        reasoning = response[start:end].strip()
        remaining = response[end + len(self._reasoning_suffix) :].strip()
        return reasoning, remaining

    def set_reasoning_tags(self, prefix: str, suffix: str) -> None:
        self._reasoning_prefix = prefix
        self._reasoning_suffix = suffix

    def wrap_with_reasoning(self, content: str, reasoning: str) -> str:
        if not reasoning:
            return content
        return f"{self._reasoning_prefix}\n{reasoning}\n{self._reasoning_suffix}\n{content}"
