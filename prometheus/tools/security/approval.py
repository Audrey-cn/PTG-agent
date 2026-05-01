"""Dangerous command approval -- detection, prompting, and per-session state."""

import contextvars
import logging
import os
import re
import sys
import threading
import time
import unicodedata

logger = logging.getLogger(__name__)

_approval_session_key: contextvars.ContextVar[str] = contextvars.ContextVar(
    "approval_session_key",
    default="",
)


def _fire_approval_hook(hook_name: str, **kwargs) -> None:
    """Invoke a plugin lifecycle hook for the approval system."""
    try:
        from prometheus.plugins import invoke_hook
    except Exception:
        return
    try:
        invoke_hook(hook_name, **kwargs)
    except Exception as exc:
        logger.debug("Approval hook %s dispatch failed: %s", hook_name, exc)


def set_current_session_key(session_key: str) -> contextvars.Token[str]:
    """Bind the active approval session key to the current context."""
    return _approval_session_key.set(session_key or "")


def reset_current_session_key(token: contextvars.Token[str]) -> None:
    """Restore the prior approval session key context."""
    _approval_session_key.reset(token)


def get_current_session_key(default: str = "default") -> str:
    """Return the active session key, preferring context-local state."""
    session_key = _approval_session_key.get()
    if session_key:
        return session_key
    try:
        from prometheus.gateway.session_context import get_session_env

        return get_session_env("PROMETHEUS_SESSION_KEY", default)
    except Exception:
        return os.getenv("PROMETHEUS_SESSION_KEY", default)


_SSH_SENSITIVE_PATH = r"(?:~|\$home|\$\{home\})/\.ssh(?:/|$)"
_PROMETHEUS_ENV_PATH = (
    r"(?:~\/\.prometheus/|"
    r"(?:\$home|\$\{home\})/\.prometheus/|"
    r"(?:\$prometheus_home|\$\{prometheus_home\})/)"
    r"\.env\b"
)
_PROJECT_ENV_PATH = r'(?:(?:/|\.{1,2}/)?(?:[^\s/"\'`]+/)*\.env(?:\.[^/\s"\'`]+)*)'
_PROJECT_CONFIG_PATH = r'(?:(?:/|\.{1,2}/)?(?:[^\s/"\'`]+/)*config\.yaml)'
_SENSITIVE_WRITE_TARGET = (
    r"(?:/etc/|/dev/sd|"
    rf"{_SSH_SENSITIVE_PATH}|"
    rf"{_PROMETHEUS_ENV_PATH})"
)
_PROJECT_SENSITIVE_WRITE_TARGET = rf"(?:{_PROJECT_ENV_PATH}|{_PROJECT_CONFIG_PATH})"
_COMMAND_TAIL = r"(?:\s*(?:&&|\|\||;).*)?$"

HARDLINE_PATTERNS = [
    (r"\brm\s+(-[^\s]*\s+)*(/|/\*|/ \*)(\s|$)", "recursive delete of root filesystem"),
    (
        r"\brm\s+(-[^\s]*\s+)*(/home|/home/\*|/root|/root/\*|/etc|/etc/\*|/usr|/usr/\*|/var|/var/\*|/bin|/bin/\*|/sbin|/sbin/\*|/boot|/boot/\*|/lib|/lib/\*)(\s|$)",
        "recursive delete of system directory",
    ),
    (r"\brm\s+(-[^\s]*\s+)*(~|\$HOME)(/?|/\*)?(\s|$)", "recursive delete of home directory"),
    (r"\bmkfs(\.[a-z0-9]+)?\b", "format filesystem (mkfs)"),
    (r"\bdd\b[^\n]*\bof=/dev/(sd|nvme|hd|mmcblk|vd|xvd)[a-z0-9]*", "dd to raw block device"),
    (r">\s*/dev/(sd|nvme|hd|mmcblk|vd|xvd)[a-z0-9]*\b", "redirect to raw block device"),
    (r":\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;\s*:", "fork bomb"),
    (r"\bkill\s+(-[^\s]+\s+)*-1\b", "kill all processes"),
    (r"\bshutdown|reboot|halt|poweroff\b", "system shutdown/reboot"),
    (r"\binit\s+[06]\b", "init 0/6 (shutdown/reboot)"),
    (r"\bsystemctl\s+(poweroff|reboot|halt|kexec)\b", "systemctl poweroff/reboot"),
    (r"\btelinit\s+[06]\b", "telinit 0/6 (shutdown/reboot)"),
]

_RE_FLAGS = re.IGNORECASE | re.DOTALL
HARDLINE_PATTERNS_COMPILED = [
    (re.compile(pattern, _RE_FLAGS), description) for pattern, description in HARDLINE_PATTERNS
]


def detect_hardline_command(command: str) -> tuple:
    """Check if a command matches the unconditional hardline blocklist."""
    normalized = _normalize_command_for_detection(command).lower()
    for pattern_re, description in HARDLINE_PATTERNS_COMPILED:
        if pattern_re.search(normalized):
            return (True, description)
    return (False, None)


def _hardline_block_result(description: str) -> dict:
    """Build the standard block result for a hardline match."""
    return {
        "approved": False,
        "hardline": True,
        "message": (
            f"BLOCKED (hardline): {description}. "
            "This command is on the unconditional blocklist and cannot "
            "be executed via the agent."
        ),
    }


DANGEROUS_PATTERNS = [
    (r"\brm\s+(-[^\s]*\s+)*/", "delete in root path"),
    (r"\brm\s+-[^\s]*r", "recursive delete"),
    (r"\brm\s+--recursive\b", "recursive delete (long flag)"),
    (
        r"\bchmod\s+(-[^\s]*\s+)*(777|666|o\+[rwx]*w|a\+[rwx]*w)\b",
        "world/other-writable permissions",
    ),
    (
        r"\bchmod\s+--recursive\b.*(777|666|o\+[rwx]*w|a\+[rwx]*w)",
        "recursive world/other-writable (long flag)",
    ),
    (r"\bchown\s+(-[^\s]*)?R\s+root", "recursive chown to root"),
    (r"\bchown\s+--recursive\b.*root", "recursive chown to root (long flag)"),
    (r"\bmkfs\b", "format filesystem"),
    (r"\bdd\s+.*if=", "disk copy"),
    (r">\s*/dev/sd", "write to block device"),
    (r"\bDROP\s+(TABLE|DATABASE)\b", "SQL DROP"),
    (r"\bDELETE\s+FROM\b(?!.*\bWHERE\b)", "SQL DELETE without WHERE"),
    (r"\bTRUNCATE\s+(TABLE)?\s*\w", "SQL TRUNCATE"),
    (r">\s*/etc/", "overwrite system config"),
    (r"\bsystemctl\s+(-[^\s]+\s+)*(stop|restart|disable|mask)\b", "stop/restart system service"),
    (r"\bkill\s+-9\s+-1\b", "kill all processes"),
    (r"\bpkill\s+-9\b", "force kill processes"),
    (r":\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;\s*:", "fork bomb"),
    (r"\b(bash|sh|zsh|ksh)\s+-[^\s]*c(\s+|$)", "shell command via -c/-lc flag"),
    (r"\b(python[23]?|perl|ruby|node)\s+-[ec]\s+", "script execution via -e/-c flag"),
    (r"\b(curl|wget)\b.*\|\s*(ba)?sh\b", "pipe remote content to shell"),
    (
        r"\b(bash|sh|zsh|ksh)\s+<\s*<?\s*\(\s*(curl|wget)\b",
        "execute remote script via process substitution",
    ),
    (rf'\btee\b.*["\']?{_SENSITIVE_WRITE_TARGET}', "overwrite system file via tee"),
    (rf'>>?\s*["\']?{_SENSITIVE_WRITE_TARGET}', "overwrite system file via redirection"),
    (
        rf'\btee\b.*["\']?{_PROJECT_SENSITIVE_WRITE_TARGET}["\']?{_COMMAND_TAIL}',
        "overwrite project env/config via tee",
    ),
    (
        rf'>>?\s*["\']?{_PROJECT_SENSITIVE_WRITE_TARGET}["\']?{_COMMAND_TAIL}',
        "overwrite project env/config via redirection",
    ),
    (r"\bxargs\s+.*\brm\b", "xargs with rm"),
    (r"\bfind\b.*-exec\s+(/\S*/)?rm\b", "find -exec rm"),
    (r"\bfind\b.*-delete\b", "find -delete"),
    (r"\bprometheus\s+gateway\s+(stop|restart)\b", "stop/restart prometheus gateway"),
    (r"\bprometheus\s+update\b", "prometheus update"),
    (r"\b(pkill|killall)\b.*\b(prometheus|gateway|cli\.py)\b", "kill prometheus/gateway process"),
    (r"\bkill\b.*\$\(\s*pgrep\b", "kill process via pgrep expansion"),
    (r"\bkill\b.*`\s*pgrep\b", "kill process via backtick pgrep expansion"),
    (r"\b(cp|mv|install)\b.*\s/etc/", "copy/move file into /etc/"),
    (
        rf'\b(cp|mv|install)\b.*\s["\']?{_PROJECT_SENSITIVE_WRITE_TARGET}["\']?{_COMMAND_TAIL}',
        "overwrite project env/config file",
    ),
    (r"\bsed\s+-[^\s]*i.*\s/etc/", "in-place edit of system config"),
    (r"\bsed\s+--in-place\b.*\s/etc/", "in-place edit of system config (long flag)"),
    (r"\b(python[23]?|perl|ruby|node)\s+<<", "script execution via heredoc"),
    (r"\bgit\s+reset\s+--hard\b", "git reset --hard (destroys uncommitted changes)"),
    (r"\bgit\s+push\b.*--force\b", "git force push (rewrites remote history)"),
    (r"\bgit\s+push\b.*-f\b", "git force push short flag (rewrites remote history)"),
    (r"\bgit\s+clean\s+-[^\s]*f", "git clean with force (deletes untracked files)"),
    (r"\bgit\s+branch\s+-D\b", "git branch force delete"),
    (r"\bchmod\s+\+x\b.*[;&|]+\s*\./", "chmod +x followed by immediate execution"),
]

DANGEROUS_PATTERNS_COMPILED = [
    (re.compile(pattern, _RE_FLAGS), description) for pattern, description in DANGEROUS_PATTERNS
]


def _legacy_pattern_key(pattern: str) -> str:
    """Reproduce the old regex-derived approval key for backwards compatibility."""
    return pattern.split(r"\b")[1] if r"\b" in pattern else pattern[:20]


_PATTERN_KEY_ALIASES: Dict[str, Set[str]] = {}
for _pattern, _description in DANGEROUS_PATTERNS:
    _legacy_key = _legacy_pattern_key(_pattern)
    _canonical_key = _description
    _PATTERN_KEY_ALIASES.setdefault(_canonical_key, set()).update({_canonical_key, _legacy_key})
    _PATTERN_KEY_ALIASES.setdefault(_legacy_key, set()).update({_legacy_key, _canonical_key})


def _approval_key_aliases(pattern_key: str) -> Set[str]:
    """Return all approval keys that should match this pattern."""
    return _PATTERN_KEY_ALIASES.get(pattern_key, {pattern_key})


def _normalize_command_for_detection(command: str) -> str:
    """Normalize a command string before dangerous-pattern matching."""
    try:
        from prometheus.tools.ansi_strip import strip_ansi

        command = strip_ansi(command)
    except ImportError:
        pass
    command = command.replace("\x00", "")
    command = unicodedata.normalize("NFKC", command)
    return command


def detect_dangerous_command(command: str) -> tuple:
    """Check if a command matches any dangerous patterns."""
    command_lower = _normalize_command_for_detection(command).lower()
    for pattern_re, description in DANGEROUS_PATTERNS_COMPILED:
        if pattern_re.search(command_lower):
            pattern_key = description
            return (True, pattern_key, description)
    return (False, None, None)


_lock = threading.Lock()
_pending: Dict[str, dict] = {}
_session_approved: Dict[str, set] = {}
_session_yolo: Set[str] = set()
_permanent_approved: set = set()


class _ApprovalEntry:
    """One pending dangerous-command approval inside a gateway session."""

    __slots__ = ("event", "data", "result")

    def __init__(self, data: dict):
        self.event = threading.Event()
        self.data = data
        self.result: str | None = None


_gateway_queues: Dict[str, list] = {}
_gateway_notify_cbs: Dict[str, object] = {}


def register_gateway_notify(session_key: str, cb) -> None:
    """Register a per-session callback for sending approval requests to the user."""
    with _lock:
        _gateway_notify_cbs[session_key] = cb


def unregister_gateway_notify(session_key: str) -> None:
    """Unregister the per-session gateway approval callback."""
    with _lock:
        _gateway_notify_cbs.pop(session_key, None)
        entries = _gateway_queues.pop(session_key, [])
        for entry in entries:
            entry.event.set()


def resolve_gateway_approval(session_key: str, choice: str, resolve_all: bool = False) -> int:
    """Called by the gateway's /approve or /deny handler to unblock waiting agent thread(s)."""
    with _lock:
        queue = _gateway_queues.get(session_key)
        if not queue:
            return 0
        if resolve_all:
            targets = list(queue)
            queue.clear()
        else:
            targets = [queue.pop(0)]
        if not queue:
            _gateway_queues.pop(session_key, None)

    for entry in targets:
        entry.result = choice
        entry.event.set()
    return len(targets)


def has_blocking_approval(session_key: str) -> bool:
    """Check if a session has one or more blocking gateway approvals waiting."""
    with _lock:
        return bool(_gateway_queues.get(session_key))


def submit_pending(session_key: str, approval: dict):
    """Store a pending approval request for a session."""
    with _lock:
        _pending[session_key] = approval


def approve_session(session_key: str, pattern_key: str):
    """Approve a pattern for this session only."""
    with _lock:
        _session_approved.setdefault(session_key, set()).add(pattern_key)


def enable_session_yolo(session_key: str) -> None:
    """Enable YOLO bypass for a single session key."""
    if not session_key:
        return
    with _lock:
        _session_yolo.add(session_key)


def disable_session_yolo(session_key: str) -> None:
    """Disable YOLO bypass for a single session key."""
    if not session_key:
        return
    with _lock:
        _session_yolo.discard(session_key)


def clear_session(session_key: str) -> None:
    """Remove all approval and yolo state for a given session."""
    if not session_key:
        return
    with _lock:
        _session_approved.pop(session_key, None)
        _session_yolo.discard(session_key)
        _pending.pop(session_key, None)
        _gateway_queues.pop(session_key, None)


def is_session_yolo_enabled(session_key: str) -> bool:
    """Return True when YOLO bypass is enabled for a specific session."""
    if not session_key:
        return False
    with _lock:
        return session_key in _session_yolo


def is_current_session_yolo_enabled() -> bool:
    """Return True when the active approval session has YOLO bypass enabled."""
    return is_session_yolo_enabled(get_current_session_key(default=""))


def is_approved(session_key: str, pattern_key: str) -> bool:
    """Check if a pattern is approved (session-scoped or permanent)."""
    aliases = _approval_key_aliases(pattern_key)
    with _lock:
        if any(alias in _permanent_approved for alias in aliases):
            return True
        session_approvals = _session_approved.get(session_key, set())
        return any(alias in session_approvals for alias in aliases)


def approve_permanent(pattern_key: str):
    """Add a pattern to the permanent allowlist."""
    with _lock:
        _permanent_approved.add(pattern_key)


def load_permanent(patterns: set):
    """Bulk-load permanent allowlist entries from config."""
    with _lock:
        _permanent_approved.update(patterns)


def load_permanent_allowlist() -> set:
    """Load permanently allowed command patterns from config."""
    try:
        from prometheus.tools.config import get_config

        config = get_config()
        patterns = set(config.get("command_allowlist", []) or [])
        if patterns:
            load_permanent(patterns)
        return patterns
    except Exception as e:
        logger.warning("Failed to load permanent allowlist: %s", e)
        return set()


def save_permanent_allowlist(patterns: set):
    """Save permanently allowed command patterns to config."""
    try:
        from prometheus.tools.config import get_config

        config = get_config()
        config.set("command_allowlist", list(patterns))
        config.save()
    except Exception as e:
        logger.warning("Could not save allowlist: %s", e)


def prompt_dangerous_approval(
    command: str,
    description: str,
    timeout_seconds: int | None = None,
    allow_permanent: bool = True,
    approval_callback=None,
) -> str:
    """Prompt the user to approve a dangerous command (CLI only)."""
    if timeout_seconds is None:
        timeout_seconds = _get_approval_timeout()

    if approval_callback is not None:
        try:
            return approval_callback(command, description, allow_permanent=allow_permanent)
        except Exception as e:
            logger.error("Approval callback failed: %s", e, exc_info=True)
            return "deny"

    try:
        from prompt_toolkit.application.current import get_app_or_none

        if get_app_or_none() is not None:
            logger.warning(
                "Dangerous-command approval requested on a thread with no "
                "approval callback while prompt_toolkit is active; denying "
                "to avoid stdin deadlock. command=%r description=%r",
                command,
                description,
            )
            return "deny"
    except Exception:
        pass

    os.environ["PROMETHEUS_SPINNER_PAUSE"] = "1"
    try:
        while True:
            print()
            print(f"  ⚠️  DANGEROUS COMMAND: {description}")
            print(f"      {command}")
            print()
            if allow_permanent:
                print("      [o]nce  |  [s]ession  |  [a]lways  |  [d]eny")
            else:
                print("      [o]nce  |  [s]ession  |  [d]eny")
            print()
            sys.stdout.flush()

            result = {"choice": ""}

            def get_input():
                try:
                    prompt = (
                        "      Choice [o/s/a/D]: " if allow_permanent else "      Choice [o/s/D]: "
                    )
                    result["choice"] = input(prompt).strip().lower()
                except (EOFError, OSError):
                    result["choice"] = ""

            thread = threading.Thread(target=get_input, daemon=True)
            thread.start()
            thread.join(timeout=timeout_seconds)

            if thread.is_alive():
                print("\n      ⏱ Timeout - denying command")
                return "deny"

            choice = result["choice"]
            if choice in ("o", "once"):
                print("      ✓ Allowed once")
                return "once"
            elif choice in ("s", "session"):
                print("      ✓ Allowed for this session")
                return "session"
            elif choice in ("a", "always"):
                if not allow_permanent:
                    print("      ✓ Allowed for this session")
                    return "session"
                print("      ✓ Added to permanent allowlist")
                return "always"
            else:
                print("      ✗ Denied")
                return "deny"

    except (EOFError, KeyboardInterrupt):
        print("\n      ✗ Cancelled")
        return "deny"
    finally:
        if "PROMETHEUS_SPINNER_PAUSE" in os.environ:
            del os.environ["PROMETHEUS_SPINNER_PAUSE"]
        print()
        sys.stdout.flush()


def _normalize_approval_mode(mode) -> str:
    """Normalize approval mode values loaded from YAML/config."""
    if isinstance(mode, bool):
        return "off" if mode is False else "manual"
    if isinstance(mode, str):
        normalized = mode.strip().lower()
        return normalized or "manual"
    return "manual"


def _get_approval_config() -> dict:
    """Read the approvals config block. Returns a dict with 'mode', 'timeout', etc."""
    try:
        from prometheus.tools.config import get_config

        config = get_config()
        return config.get("approvals", {}) or {}
    except Exception as e:
        logger.warning("Failed to load approval config: %s", e)
        return {}


def _get_approval_mode() -> str:
    """Read the approval mode from config. Returns 'manual', 'smart', or 'off'."""
    mode = _get_approval_config().get("mode", "manual")
    return _normalize_approval_mode(mode)


def _get_approval_timeout() -> int:
    """Read the approval timeout from config. Defaults to 60 seconds."""
    try:
        return int(_get_approval_config().get("timeout", 60))
    except (ValueError, TypeError):
        return 60


def _get_cron_approval_mode() -> str:
    """Read the cron approval mode from config. Returns 'deny' or 'approve'."""
    try:
        from prometheus.tools.config import get_config

        config = get_config()
        mode = str(config.get("approvals.cron_mode", "deny")).lower().strip()
        if mode in ("approve", "off", "allow", "yes"):
            return "approve"
        return "deny"
    except Exception:
        return "deny"


def _smart_approve(command: str, description: str) -> str:
    """Use the auxiliary LLM to assess risk and decide approval."""
    try:
        from prometheus.auxiliary_client import call_llm

        prompt = f"""You are a security reviewer for an AI coding agent. A terminal command was flagged by pattern matching as potentially dangerous.

Command: {command}
Flagged reason: {description}

Assess the ACTUAL risk of this command. Many flagged commands are false positives.

Rules:
- APPROVE if the command is clearly safe (benign script execution, safe file operations, development tools, package installs, git operations, etc.)
- DENY if the command could genuinely damage the system (recursive delete of important paths, overwriting system files, fork bombs, wiping disks, dropping databases, etc.)
- ESCALATE if you're uncertain

Respond with exactly one word: APPROVE, DENY, or ESCALATE"""

        response = call_llm(
            task="approval",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=16,
        )

        answer = (response.choices[0].message.content or "").strip().upper()

        if "APPROVE" in answer:
            return "approve"
        elif "DENY" in answer:
            return "deny"
        else:
            return "escalate"

    except Exception as e:
        logger.debug("Smart approvals: LLM call failed (%s), escalating", e)
        return "escalate"


def check_dangerous_command(command: str, env_type: str, approval_callback=None) -> dict:
    """Check if a command is dangerous and handle approval."""
    if env_type in ("docker", "singularity", "modal", "daytona", "vercel_sandbox"):
        return {"approved": True, "message": None}

    is_hardline, hardline_desc = detect_hardline_command(command)
    if is_hardline:
        logger.warning("Hardline block: %s (command: %s)", hardline_desc, command[:200])
        return _hardline_block_result(hardline_desc)

    if os.getenv("PROMETHEUS_YOLO_MODE") or is_current_session_yolo_enabled():
        return {"approved": True, "message": None}

    is_dangerous, pattern_key, description = detect_dangerous_command(command)
    if not is_dangerous:
        return {"approved": True, "message": None}

    session_key = get_current_session_key()
    if is_approved(session_key, pattern_key):
        return {"approved": True, "message": None}

    is_cli = os.getenv("PROMETHEUS_INTERACTIVE")
    is_gateway = os.getenv("PROMETHEUS_GATEWAY_SESSION")

    if not is_cli and not is_gateway:
        if os.getenv("PROMETHEUS_CRON_SESSION") and _get_cron_approval_mode() == "deny":
            return {
                "approved": False,
                "message": (
                    f"BLOCKED: Command flagged as dangerous ({description}) "
                    "but cron jobs run without a user present to approve it."
                ),
            }
        return {"approved": True, "message": None}

    if is_gateway or os.getenv("PROMETHEUS_EXEC_ASK"):
        submit_pending(
            session_key,
            {
                "command": command,
                "pattern_key": pattern_key,
                "description": description,
            },
        )
        return {
            "approved": False,
            "pattern_key": pattern_key,
            "status": "approval_required",
            "command": command,
            "description": description,
            "message": (
                f"⚠️ This command is potentially dangerous ({description}). "
                f"Asking the user for approval.\n\n**Command:**\n```\n{command}\n```"
            ),
        }

    choice = prompt_dangerous_approval(command, description, approval_callback=approval_callback)

    if choice == "deny":
        return {
            "approved": False,
            "message": f"BLOCKED: User denied this potentially dangerous command (matched '{description}' pattern). Do NOT retry this command - the user has explicitly rejected it.",
            "pattern_key": pattern_key,
            "description": description,
        }

    if choice == "session":
        approve_session(session_key, pattern_key)
    elif choice == "always":
        approve_session(session_key, pattern_key)
        approve_permanent(pattern_key)
        save_permanent_allowlist(_permanent_approved)

    return {"approved": True, "message": None}


def _format_tirith_description(tirith_result: dict) -> str:
    """Build a human-readable description from tirith findings."""
    findings = tirith_result.get("findings") or []
    if not findings:
        summary = tirith_result.get("summary") or "security issue detected"
        return f"Security scan: {summary}"

    parts = []
    for f in findings:
        severity = f.get("severity", "")
        title = f.get("title", "")
        desc = f.get("description", "")
        if title and desc:
            parts.append(f"[{severity}] {title}: {desc}" if severity else f"{title}: {desc}")
        elif title:
            parts.append(f"[{severity}] {title}" if severity else title)
    if not parts:
        summary = tirith_result.get("summary") or "security issue detected"
        return f"Security scan: {summary}"

    return "Security scan — " + "; ".join(parts)


def check_all_command_guards(command: str, env_type: str, approval_callback=None) -> dict:
    """Run all pre-exec security checks and return a single approval decision."""
    if env_type in ("docker", "singularity", "modal", "daytona", "vercel_sandbox"):
        return {"approved": True, "message": None}

    is_hardline, hardline_desc = detect_hardline_command(command)
    if is_hardline:
        logger.warning("Hardline block: %s (command: %s)", hardline_desc, command[:200])
        return _hardline_block_result(hardline_desc)

    approval_mode = _get_approval_mode()
    if (
        os.getenv("PROMETHEUS_YOLO_MODE")
        or is_current_session_yolo_enabled()
        or approval_mode == "off"
    ):
        return {"approved": True, "message": None}

    is_cli = os.getenv("PROMETHEUS_INTERACTIVE")
    is_gateway = os.getenv("PROMETHEUS_GATEWAY_SESSION")
    is_ask = os.getenv("PROMETHEUS_EXEC_ASK")

    if not is_cli and not is_gateway and not is_ask:
        if os.getenv("PROMETHEUS_CRON_SESSION") and _get_cron_approval_mode() == "deny":
            is_dangerous, _pk, description = detect_dangerous_command(command)
            if is_dangerous:
                return {
                    "approved": False,
                    "message": (
                        f"BLOCKED: Command flagged as dangerous ({description}) "
                        "but cron jobs run without a user present to approve it."
                    ),
                }
        return {"approved": True, "message": None}

    tirith_result = {"action": "allow", "findings": [], "summary": ""}
    try:
        from prometheus.tools.tirith_security import check_command_security

        tirith_result = check_command_security(command)
    except ImportError:
        pass

    is_dangerous, pattern_key, description = detect_dangerous_command(command)

    warnings = []
    session_key = get_current_session_key()

    if tirith_result["action"] in ("block", "warn"):
        findings = tirith_result.get("findings") or []
        rule_id = findings[0].get("rule_id", "unknown") if findings else "unknown"
        tirith_key = f"tirith:{rule_id}"
        tirith_desc = _format_tirith_description(tirith_result)
        if not is_approved(session_key, tirith_key):
            warnings.append((tirith_key, tirith_desc, True))

    if is_dangerous and not is_approved(session_key, pattern_key):
        warnings.append((pattern_key, description, False))

    if not warnings:
        return {"approved": True, "message": None}

    if approval_mode == "smart":
        combined_desc_for_llm = "; ".join(desc for _, desc, _ in warnings)
        verdict = _smart_approve(command, combined_desc_for_llm)
        if verdict == "approve":
            for key, _, _ in warnings:
                approve_session(session_key, key)
            logger.debug(
                "Smart approval: auto-approved '%s' (%s)", command[:60], combined_desc_for_llm
            )
            return {
                "approved": True,
                "message": None,
                "smart_approved": True,
                "description": combined_desc_for_llm,
            }
        elif verdict == "deny":
            combined_desc_for_llm = "; ".join(desc for _, desc, _ in warnings)
            return {
                "approved": False,
                "message": f"BLOCKED by smart approval: {combined_desc_for_llm}. "
                "The command was assessed as genuinely dangerous. Do NOT retry.",
                "smart_denied": True,
            }

    combined_desc = "; ".join(desc for _, desc, _ in warnings)
    primary_key = warnings[0][0]
    all_keys = [key for key, _, _ in warnings]
    has_tirith = any(is_t for _, _, is_t in warnings)

    if is_gateway or is_ask:
        notify_cb = None
        with _lock:
            notify_cb = _gateway_notify_cbs.get(session_key)

        if notify_cb is not None:
            approval_data = {
                "command": command,
                "pattern_key": primary_key,
                "pattern_keys": all_keys,
                "description": combined_desc,
            }
            entry = _ApprovalEntry(approval_data)
            with _lock:
                _gateway_queues.setdefault(session_key, []).append(entry)

            _fire_approval_hook(
                "pre_approval_request",
                command=command,
                description=combined_desc,
                pattern_key=primary_key,
                pattern_keys=list(all_keys),
                session_key=session_key,
                surface="gateway",
            )

            try:
                notify_cb(approval_data)
            except Exception as exc:
                logger.warning("Gateway approval notify failed: %s", exc)
                with _lock:
                    queue = _gateway_queues.get(session_key, [])
                    if entry in queue:
                        queue.remove(entry)
                    if not queue:
                        _gateway_queues.pop(session_key, None)
                return {
                    "approved": False,
                    "message": "BLOCKED: Failed to send approval request to user. Do NOT retry.",
                    "pattern_key": primary_key,
                    "description": combined_desc,
                }

            timeout = _get_approval_config().get("gateway_timeout", 300)
            try:
                timeout = int(timeout)
            except (ValueError, TypeError):
                timeout = 300

            try:
                from prometheus.tools.environments.base import touch_activity_if_due
            except Exception:
                touch_activity_if_due = None

            _now = time.monotonic()
            _deadline = _now + max(timeout, 0)
            _activity_state = {"last_touch": _now, "start": _now}
            resolved = False
            while True:
                _remaining = _deadline - time.monotonic()
                if _remaining <= 0:
                    break
                if entry.event.wait(timeout=min(1.0, _remaining)):
                    resolved = True
                    break
                if touch_activity_if_due is not None:
                    touch_activity_if_due(_activity_state, "waiting for user approval")

            with _lock:
                queue = _gateway_queues.get(session_key, [])
                if entry in queue:
                    queue.remove(entry)
                if not queue:
                    _gateway_queues.pop(session_key, None)

            choice = entry.result
            _outcome = "timeout" if not resolved else (choice if choice else "timeout")
            _fire_approval_hook(
                "post_approval_response",
                command=command,
                description=combined_desc,
                pattern_key=primary_key,
                pattern_keys=list(all_keys),
                session_key=session_key,
                surface="gateway",
                choice=_outcome,
            )

            if not resolved or choice is None or choice == "deny":
                reason = "timed out" if not resolved else "denied by user"
                return {
                    "approved": False,
                    "message": f"BLOCKED: Command {reason}. Do NOT retry this command.",
                    "pattern_key": primary_key,
                    "description": combined_desc,
                }

            for key, _, is_tirith in warnings:
                if choice == "session" or (choice == "always" and is_tirith):
                    approve_session(session_key, key)
                elif choice == "always":
                    approve_session(session_key, key)
                    approve_permanent(key)
                    save_permanent_allowlist(_permanent_approved)

            return {
                "approved": True,
                "message": None,
                "user_approved": True,
                "description": combined_desc,
            }

        submit_pending(
            session_key,
            {
                "command": command,
                "pattern_key": primary_key,
                "pattern_keys": all_keys,
                "description": combined_desc,
            },
        )
        return {
            "approved": False,
            "pattern_key": primary_key,
            "status": "approval_required",
            "command": command,
            "description": combined_desc,
            "message": (
                f"⚠️ {combined_desc}. Asking the user for approval.\n\n**Command:**\n```\n{command}\n```"
            ),
        }

    _fire_approval_hook(
        "pre_approval_request",
        command=command,
        description=combined_desc,
        pattern_key=primary_key,
        pattern_keys=list(all_keys),
        session_key=session_key,
        surface="cli",
    )
    choice = prompt_dangerous_approval(
        command, combined_desc, allow_permanent=not has_tirith, approval_callback=approval_callback
    )
    _fire_approval_hook(
        "post_approval_response",
        command=command,
        description=combined_desc,
        pattern_key=primary_key,
        pattern_keys=list(all_keys),
        session_key=session_key,
        surface="cli",
        choice=choice,
    )

    if choice == "deny":
        return {
            "approved": False,
            "message": "BLOCKED: User denied. Do NOT retry.",
            "pattern_key": primary_key,
            "description": combined_desc,
        }

    for key, _, is_tirith in warnings:
        if choice == "session" or (choice == "always" and is_tirith):
            approve_session(session_key, key)
        elif choice == "always":
            approve_session(session_key, key)
            approve_permanent(key)
            save_permanent_allowlist(_permanent_approved)

    return {"approved": True, "message": None, "user_approved": True, "description": combined_desc}


load_permanent_allowlist()
