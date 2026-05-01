from __future__ import annotations

import difflib
from typing import Any

KNOWN_COMMANDS = [
    "setup",
    "doctor",
    "model",
    "config",
    "status",
    "seed",
    "gene",
    "memory",
    "kb",
    "dict",
    "update",
    "skin",
    "auth",
    "chat",
    "help",
    "version",
    "uninstall",
    "dump",
    "tips",
    "pair",
]


def suggest_command(command: str) -> list[str]:
    return difflib.get_close_matches(command, KNOWN_COMMANDS, n=3, cutoff=0.6)


def handle_unknown_command(command: str, args: list[str] | None = None) -> dict[str, Any]:
    suggestions = suggest_command(command)
    
    result = {
        "error": f"Unknown command: {command}",
        "command": command,
        "args": args or [],
        "suggestions": suggestions,
    }
    
    if suggestions:
        result["message"] = f"Unknown command '{command}'. Did you mean: {', '.join(suggestions)}?"
    else:
        result["message"] = f"Unknown command '{command}'. Type 'help' for available commands."
    
    return result
