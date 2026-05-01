from __future__ import annotations

import re

PLATFORM_LIMITS: Dict[str, int] = {
    "telegram": 4096,
    "discord": 2000,
    "slack": 40000,
    "whatsapp": 4096,
    "wechat": 2048,
    "feishu": 30000,
    "dingtalk": 20000,
    "matrix": 16384,
    "signal": 2000,
    "sms": 160,
    "email": 1000000,
    "cli": 100000,
}


def format_message_for_platform(message: str, platform: str) -> str:
    if platform == "telegram":
        return _escape_markdown_v2(message)
    elif platform == "discord":
        return _escape_discord_markdown(message)
    elif platform == "slack":
        return _escape_slack_markdown(message)
    elif platform == "matrix":
        return _escape_html(message)
    elif platform == "whatsapp":
        return _escape_whatsapp(message)
    return message


def _escape_markdown_v2(text: str) -> str:
    escape_chars = r"_*[]()~`>#+-=|{}.!"
    result = []
    for char in text:
        if char in escape_chars:
            result.append(f"\\{char}")
        else:
            result.append(char)
    return "".join(result)


def _escape_discord_markdown(text: str) -> str:
    escape_chars = r"*_~|`\\"
    result = []
    for char in text:
        if char in escape_chars:
            result.append(f"\\{char}")
        else:
            result.append(char)
    return "".join(result)


def _escape_slack_markdown(text: str) -> str:
    text = text.replace("&", "&amp;")
    text = text.replace("<", "&lt;")
    text = text.replace(">", "&gt;")
    return text


def _escape_html(text: str) -> str:
    text = text.replace("&", "&amp;")
    text = text.replace("<", "&lt;")
    text = text.replace(">", "&gt;")
    return text


def _escape_whatsapp(text: str) -> str:
    escape_chars = r"*_~`"
    result = []
    for char in text:
        if char in escape_chars:
            result.append(f"\\{char}")
        else:
            result.append(char)
    return "".join(result)


def split_message(message: str, max_length: int) -> List[str]:
    if len(message) <= max_length:
        return [message]
    parts: List[str] = []
    remaining = message
    while remaining:
        if len(remaining) <= max_length:
            parts.append(remaining)
            break
        split_pos = max_length
        for i in range(max_length - 1, max(0, max_length - 100), -1):
            if remaining[i] in " \n\t.,;:!?":
                split_pos = i + 1
                break
        parts.append(remaining[:split_pos])
        remaining = remaining[split_pos:]
    return parts


def extract_mentions(text: str) -> List[str]:
    patterns = [
        r"<@!?(\d+)>",
        r"<#(\d+)>",
        r"<@&(\d+)>",
        r"@(\w+)",
        r"@\[([^\]]+)\]",
    ]
    mentions: List[str] = []
    for pattern in patterns:
        matches = re.findall(pattern, text)
        mentions.extend(matches)
    return list(set(mentions))


def format_mention(user_id: str, platform: str) -> str:
    if platform == "discord" or platform == "slack":
        return f"<@{user_id}>"
    elif platform == "telegram":
        return f"@{user_id}"
    elif platform == "matrix":
        return f"<a href='https://matrix.to/#/{user_id}'>{user_id}</a>"
    elif platform == "whatsapp":
        return f"@{user_id}"
    return f"@{user_id}"


def is_valid_chat_id(chat_id: str, platform: str) -> bool:
    if not chat_id:
        return False
    if platform == "telegram":
        if chat_id.startswith("-100"):
            return chat_id[4:].isdigit()
        return chat_id.isdigit() or chat_id.lstrip("-").isdigit()
    elif platform == "discord":
        return chat_id.isdigit() and len(chat_id) >= 17
    elif platform == "slack":
        return chat_id.startswith(("C", "G", "D")) and len(chat_id) >= 9
    elif platform == "whatsapp":
        return chat_id.replace("+", "").replace("-", "").isdigit()
    elif platform == "wechat":
        return len(chat_id) > 0
    elif platform == "matrix":
        return "@" in chat_id and ":" in chat_id
    elif platform == "email":
        return "@" in chat_id and "." in chat_id.split("@")[1]
    return len(chat_id) > 0


def parse_command(text: str, prefix: str = "/") -> Tuple[str, str]:
    text = text.strip()
    if not text.startswith(prefix):
        return ("", text)
    text = text[len(prefix) :]
    parts = text.split(None, 1)
    if not parts:
        return ("", "")
    command = parts[0].lower()
    args = parts[1] if len(parts) > 1 else ""
    return (command, args)
