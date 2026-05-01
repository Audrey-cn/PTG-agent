from __future__ import annotations

import hashlib
from datetime import datetime

TIPS = [
    "Use 'prometheus doctor' to diagnose configuration issues.",
    "Press Ctrl+C twice quickly to exit interactive mode.",
    "Use 'prometheus config set <key> <value>' to update settings.",
    "The 'seed' command creates self-contained agent definitions.",
    "Use 'prometheus memory --show' to view stored memories.",
    "Skins change the visual theme: 'prometheus skin zeus'.",
    "Use 'prometheus status' to check system health.",
    "Chronicler mode tracks changes with 'stamp' and 'trace' commands.",
    "Use 'prometheus model --list' to see available models.",
    "The 'gene' command manages genetic traits of seeds.",
    "Use 'prometheus kb' for knowledge base operations.",
    "Set PROMETHEUS_MODEL env var to override the default model.",
    "Use 'prometheus update' to check for updates.",
    "Sessions are auto-saved in ~/.prometheus/sessions/.",
    "Use 'prometheus dict' to manage the built-in dictionary.",
]


def show_random_tip() -> str:
    import random

    return random.choice(TIPS)


def show_tip_of_the_day() -> str:
    today = datetime.now().strftime("%Y-%m-%d")
    hash_val = int(hashlib.md5(today.encode()).hexdigest(), 16)
    index = hash_val % len(TIPS)
    return TIPS[index]


def list_tips() -> list[str]:
    return TIPS.copy()
