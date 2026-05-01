"""Tool argument repair utilities for Prometheus."""

import json
import logging
import re

logger = logging.getLogger(__name__)

CONTROL_CHARS_PATTERN = re.compile(r"[\x00-\x1f\x7f-\x9f]")


def _escape_invalid_chars_in_json_strings(text: str) -> str:
    """Escape invalid control characters inside JSON string values.

    Used when strict=False json.loads fails due to malformed escape sequences.
    """
    result = []
    i = 0
    in_string = False
    escape_next = False

    while i < len(text):
        char = text[i]

        if escape_next:
            if char in '"\\/bfnrtu':
                result.append("\\")
                result.append(char)
            else:
                result.append(char)
            escape_next = False
            i += 1
            continue

        if char == "\\" and in_string:
            if i + 1 < len(text) and text[i + 1] == "u" and i + 5 < len(text):
                hex_part = text[i + 2 : i + 6]
                try:
                    int(hex_part, 16)
                    result.append("\\u")
                    result.append(hex_part)
                    i += 6
                    continue
                except ValueError:
                    result.append("\\")
                    i += 2
                    continue
            result.append("\\")
            result.append(char)
            i += 1
            continue

        if char == '"':
            in_string = not in_string
            result.append(char)
            i += 1
            continue

        if in_string and ord(char) < 32:
            result.append(f"\\x{ord(char):02x}")
            i += 1
            continue

        if in_string and char == "\x7f":
            result.append("\\x7f")
            i += 1
            continue

        result.append(char)
        i += 1

    return "".join(result)


def repair_tool_call_arguments(raw_args: str, tool_name: str = "?") -> str:
    """Attempt to repair malformed tool_call argument JSON.

    Models like GLM-5.1 via Ollama can produce truncated JSON, trailing
    commas, Python ``None``, etc. The API rejects these with HTTP 400
    "invalid tool call arguments". This function applies common repairs;
    if all fail it returns ``"{}"`` so the request succeeds (better than
    crashing the session).

    Args:
        raw_args: Raw argument string from model
        tool_name: Name of the tool for logging

    Returns:
        Repaired JSON string or "{}" if unrepairable
    """
    raw_stripped = raw_args.strip() if isinstance(raw_args, str) else ""

    if not raw_stripped:
        logger.warning("Sanitized empty tool_call arguments for %s", tool_name)
        return "{}"

    if raw_stripped == "None":
        logger.warning("Sanitized Python-None tool_call arguments for %s", tool_name)
        return "{}"

    try:
        parsed = json.loads(raw_stripped, strict=False)
        reserialised = json.dumps(parsed, separators=(",", ":"))
        if reserialised != raw_stripped:
            logger.warning(
                "Repaired unescaped control chars in tool_call arguments for %s",
                tool_name,
            )
        return reserialised
    except (json.JSONDecodeError, TypeError, ValueError):
        pass

    fixed = raw_stripped

    fixed = re.sub(r",\s*([}\]])", r"\1", fixed)

    open_curly = fixed.count("{") - fixed.count("}")
    open_bracket = fixed.count("[") - fixed.count("]")
    if open_curly > 0:
        fixed += "}" * open_curly
    if open_bracket > 0:
        fixed += "]" * open_bracket

    for _ in range(50):
        try:
            json.loads(fixed)
            break
        except json.JSONDecodeError:
            if (
                fixed.endswith("}")
                and fixed.count("}") > fixed.count("{")
                or fixed.endswith("]")
                and fixed.count("]") > fixed.count("[")
            ):
                fixed = fixed[:-1]
            else:
                break

    try:
        json.loads(fixed)
        logger.warning(
            "Repaired malformed tool_call arguments for %s: %s → %s",
            tool_name,
            raw_stripped[:80],
            fixed[:80],
        )
        return fixed
    except json.JSONDecodeError:
        pass

    try:
        escaped = _escape_invalid_chars_in_json_strings(fixed)
        if escaped != fixed:
            json.loads(escaped)
            logger.warning(
                "Repaired control-char-laced tool_call arguments for %s: %s → %s",
                tool_name,
                raw_stripped[:80],
                escaped[:80],
            )
            return escaped
    except (json.JSONDecodeError, TypeError, ValueError):
        pass

    logger.warning(
        "Unrepairable tool_call arguments for %s — replaced with empty object (was: %s)",
        tool_name,
        raw_stripped[:80],
    )
    return "{}"


def strip_non_ascii(text: str) -> str:
    """Remove non-ASCII characters, replacing with closest ASCII equivalent or removing.

    Used as a last resort when the system encoding is ASCII and can't handle
    any non-ASCII characters (e.g. LANG=C on Chromebooks).
    """
    return text.encode("ascii", errors="ignore").decode("ascii")


def sanitize_messages_non_ascii(messages: list) -> bool:
    """Strip non-ASCII characters from all String content in a messages list.

    Returns True if any non-ASCII content was found and sanitized.
    """
    found = False
    for msg in messages:
        if not isinstance(msg, dict):
            continue

        content = msg.get("content")
        if isinstance(content, str):
            sanitized = strip_non_ascii(content)
            if sanitized != content:
                msg["content"] = sanitized
                found = True
        elif isinstance(content, list):
            for part in content:
                if isinstance(part, dict):
                    text = part.get("text")
                    if isinstance(text, str):
                        sanitized = strip_non_ascii(text)
                        if sanitized != text:
                            part["text"] = sanitized
                            found = True

        name = msg.get("name")
        if isinstance(name, str):
            sanitized = strip_non_ascii(name)
            if sanitized != name:
                msg["name"] = sanitized
                found = True

        tool_calls = msg.get("tool_calls")
        if isinstance(tool_calls, list):
            for tc in tool_calls:
                if isinstance(tc, dict):
                    fn = tc.get("function", {})
                    if isinstance(fn, dict):
                        fn_args = fn.get("arguments")
                        if isinstance(fn_args, str):
                            sanitized = strip_non_ascii(fn_args)
                            if sanitized != fn_args:
                                fn["arguments"] = sanitized
                                found = True

        for key, value in msg.items():
            if key in {"content", "name", "tool_calls", "role"}:
                continue
            if isinstance(value, str):
                sanitized = strip_non_ascii(value)
                if sanitized != value:
                    msg[key] = sanitized
                    found = True

    return found


def sanitize_tools_non_ascii(tools: list) -> bool:
    """Strip non-ASCII characters from tool payloads in-place."""
    return sanitize_structure_non_ascii(tools)


def sanitize_structure_non_ascii(payload) -> bool:
    """Strip non-ASCII characters from nested dict/list payloads in-place."""
    found = False

    def walk(node):
        nonlocal found
        if isinstance(node, dict):
            for key, value in node.items():
                if isinstance(value, str):
                    sanitized = strip_non_ascii(value)
                    if sanitized != value:
                        node[key] = sanitized
                        found = True
                elif isinstance(value, (dict, list)):
                    walk(value)
        elif isinstance(node, list):
            for idx, value in enumerate(node):
                if isinstance(value, str):
                    sanitized = strip_non_ascii(value)
                    if sanitized != value:
                        node[idx] = sanitized
                        found = True
                elif isinstance(value, (dict, list)):
                    walk(value)

    walk(payload)
    return found


def parse_tool_arguments(raw_args: str, tool_name: str = "?") -> dict:
    """Parse tool arguments with automatic repair.

    Args:
        raw_args: Raw argument string from model
        tool_name: Name of the tool for logging

    Returns:
        Parsed arguments dictionary
    """
    repaired = repair_tool_call_arguments(raw_args, tool_name)

    try:
        return json.loads(repaired)
    except json.JSONDecodeError:
        return {}
