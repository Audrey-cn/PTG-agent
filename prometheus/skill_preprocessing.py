from __future__ import annotations

import os
import re
import subprocess

TEMPLATE_VAR_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")
INLINE_SHELL_PATTERN = re.compile(r"!`([^`]+)`")


def substitute_template_vars(content: str, skill_dir: str, session_id: str) -> str:
    var_map = {
        "PROMETHEUS_SKILL_DIR": skill_dir,
        "PROMETHEUS_SESSION_ID": session_id,
        "PROMETHEUS_HOME": os.path.expanduser("~/.prometheus"),
        "PROMETHEUS_PROJECT": os.getcwd(),
    }

    def replacer(match: re.Match) -> str:
        var_name = match.group(1)
        return var_map.get(var_name, match.group(0))

    return TEMPLATE_VAR_PATTERN.sub(replacer, content)


def expand_inline_shell(content: str, timeout: int = 30) -> str:
    def replacer(match: re.Match) -> str:
        command = match.group(1)
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=os.getcwd(),
            )
            if result.returncode == 0:
                return result.stdout.strip()
            return f"[ERROR: {result.stderr.strip()}]"
        except subprocess.TimeoutExpired:
            return f"[ERROR: command timed out after {timeout}s]"
        except Exception as e:
            return f"[ERROR: {e}]"

    return INLINE_SHELL_PATTERN.sub(replacer, content)


def preprocess_skill(
    content: str, skill_dir: str, session_id: str, expand_shell: bool = False
) -> str:
    processed = substitute_template_vars(content, skill_dir, session_id)
    if expand_shell:
        processed = expand_inline_shell(processed)
    return processed


def extract_template_vars(content: str) -> List[str]:
    return list(set(TEMPLATE_VAR_PATTERN.findall(content)))


def extract_shell_commands(content: str) -> List[str]:
    return INLINE_SHELL_PATTERN.findall(content)


def has_template_vars(content: str) -> bool:
    return bool(TEMPLATE_VAR_PATTERN.search(content))


def has_inline_shell(content: str) -> bool:
    return bool(INLINE_SHELL_PATTERN.search(content))
