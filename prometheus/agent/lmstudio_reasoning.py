"""LM Studio reasoning-effort resolution shared by the chat-completions."""

from __future__ import annotations

_LM_VALID_EFFORTS = {"none", "minimal", "low", "medium", "high", "xhigh"}

_LM_EFFORT_ALIASES = {"off": "none", "on": "medium"}


def resolve_lmstudio_effort(
    reasoning_config: dict | None,
    allowed_options: list[str] | None,
) -> str | None:
    """Return the ``reasoning_effort`` string to send to LM Studio, or ``None``.

    ``None`` means "omit the field": the user picked a level the model can't
    honor, so let LM Studio fall back to the model's declared default rather
    than silently substituting a different effort. When ``allowed_options`` is
    falsy (probe failed), skip clamping and send the resolved effort anyway.
    """
    effort = "medium"
    if reasoning_config and isinstance(reasoning_config, dict):
        if reasoning_config.get("enabled") is False:
            effort = "none"
        else:
            raw = (reasoning_config.get("effort") or "").strip().lower()
            raw = _LM_EFFORT_ALIASES.get(raw, raw)
            if raw in _LM_VALID_EFFORTS:
                effort = raw
    if allowed_options:
        allowed = {_LM_EFFORT_ALIASES.get(opt, opt) for opt in allowed_options}
        if effort not in allowed:
            return None
    return effort
