from __future__ import annotations

import json
import subprocess
import sys
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from enum import Enum


class HookEvent(str, Enum):
    PRE_TOOL_CALL = "pre_tool_call"
    POST_TOOL_CALL = "post_tool_call"
    PRE_LLM_CALL = "pre_llm_call"
    POST_LLM_CALL = "post_llm_call"
    ON_ERROR = "on_error"


@dataclass
class HookDefinition:
    event: str
    command: str
    enabled: bool = True
    timeout: int = 30
    requires_consent: bool = True
    consent_granted: bool = False


class ShellHooks:
    def __init__(self) -> None:
        self._hooks: Dict[str, List[HookDefinition]] = {
            event.value: [] for event in HookEvent
        }
        self._revoked_commands: set[str] = set()

    def load_from_config(self, config: Dict[str, Any]) -> int:
        loaded = 0
        hooks_config = config.get("shell_hooks", {})
        if not isinstance(hooks_config, dict):
            return 0
        for event_name, hook_list in hooks_config.items():
            if event_name not in self._hooks:
                continue
            if not isinstance(hook_list, list):
                continue
            for hook_def in hook_list:
                if not isinstance(hook_def, dict):
                    continue
                command = hook_def.get("command")
                if not command:
                    continue
                hook = HookDefinition(
                    event=event_name,
                    command=command,
                    enabled=hook_def.get("enabled", True),
                    timeout=hook_def.get("timeout", 30),
                    requires_consent=hook_def.get("requires_consent", True),
                    consent_granted=not hook_def.get("requires_consent", True),
                )
                self._hooks[event_name].append(hook)
                loaded += 1
        return loaded

    def register(self, event: str, command: str, timeout: int = 30, requires_consent: bool = True) -> bool:
        if event not in self._hooks:
            return False
        hook = HookDefinition(
            event=event,
            command=command,
            timeout=timeout,
            requires_consent=requires_consent,
            consent_granted=not requires_consent,
        )
        self._hooks[event].append(hook)
        return True

    def fire(self, event: str, data: Dict[str, Any]) -> Dict[str, Any]:
        results: Dict[str, Any] = {
            "event": event,
            "hooks_executed": 0,
            "hooks_skipped": 0,
            "results": [],
            "errors": [],
        }
        if event not in self._hooks:
            return results
        hooks = self._hooks[event]
        for hook in hooks:
            if not hook.enabled:
                results["hooks_skipped"] += 1
                continue
            if hook.command in self._revoked_commands:
                results["hooks_skipped"] += 1
                continue
            if hook.requires_consent and not hook.consent_granted:
                results["hooks_skipped"] += 1
                continue
            try:
                result = self._execute_hook(hook, data)
                results["results"].append({
                    "command": hook.command,
                    "success": result.get("success", False),
                    "output": result.get("output", ""),
                })
                results["hooks_executed"] += 1
            except Exception as e:
                results["errors"].append({
                    "command": hook.command,
                    "error": str(e),
                })
        return results

    def _execute_hook(self, hook: HookDefinition, data: Dict[str, Any]) -> Dict[str, Any]:
        stdin_data = json.dumps(data)
        try:
            result = subprocess.run(
                hook.command,
                shell=True,
                input=stdin_data,
                capture_output=True,
                text=True,
                timeout=hook.timeout,
            )
            return {
                "success": result.returncode == 0,
                "output": result.stdout,
                "stderr": result.stderr,
            }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "output": "",
                "stderr": f"Hook timed out after {hook.timeout}s",
            }
        except Exception as e:
            return {
                "success": False,
                "output": "",
                "stderr": str(e),
            }

    def list_hooks(self) -> List[Dict[str, Any]]:
        hooks_list = []
        for event, hooks in self._hooks.items():
            for hook in hooks:
                hooks_list.append({
                    "event": event,
                    "command": hook.command,
                    "enabled": hook.enabled,
                    "timeout": hook.timeout,
                    "requires_consent": hook.requires_consent,
                    "consent_granted": hook.consent_granted,
                    "revoked": hook.command in self._revoked_commands,
                })
        return hooks_list

    def revoke(self, command: str) -> bool:
        self._revoked_commands.add(command)
        return True

    def grant_consent(self, command: str) -> bool:
        for event, hooks in self._hooks.items():
            for hook in hooks:
                if hook.command == command:
                    hook.consent_granted = True
                    return True
        return False

    def enable(self, command: str) -> bool:
        for event, hooks in self._hooks.items():
            for hook in hooks:
                if hook.command == command:
                    hook.enabled = True
                    return True
        return False

    def disable(self, command: str) -> bool:
        for event, hooks in self._hooks.items():
            for hook in hooks:
                if hook.command == command:
                    hook.enabled = False
                    return True
        return False
