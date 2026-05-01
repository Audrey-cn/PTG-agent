"""Shared fixtures for the prometheus test suite."""

import logging
import os
import signal
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


_CREDENTIAL_SUFFIXES = (
    "_API_KEY",
    "_TOKEN",
    "_SECRET",
    "_PASSWORD",
    "_CREDENTIALS",
    "_ACCESS_KEY",
    "_SECRET_ACCESS_KEY",
    "_PRIVATE_KEY",
    "_OAUTH_TOKEN",
    "_WEBHOOK_SECRET",
    "_ENCRYPT_KEY",
    "_APP_SECRET",
    "_CLIENT_SECRET",
    "_CORP_SECRET",
    "_AES_KEY",
)

_CREDENTIAL_NAMES = frozenset(
    {
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_SESSION_TOKEN",
        "ANTHROPIC_TOKEN",
        "FAL_KEY",
        "GH_TOKEN",
        "GITHUB_TOKEN",
        "OPENAI_API_KEY",
        "OPENROUTER_API_KEY",
        "NOUS_API_KEY",
        "GEMINI_API_KEY",
        "GOOGLE_API_KEY",
        "GROQ_API_KEY",
        "XAI_API_KEY",
        "MISTRAL_API_KEY",
        "DEEPSEEK_API_KEY",
        "KIMI_API_KEY",
        "MOONSHOT_API_KEY",
        "GLM_API_KEY",
        "ZAI_API_KEY",
        "MINIMAX_API_KEY",
        "OLLAMA_API_KEY",
        "COPILOT_API_KEY",
        "BROWSERBASE_API_KEY",
        "FIRECRAWL_API_KEY",
        "PARALLEL_API_KEY",
        "EXA_API_KEY",
        "TAVILY_API_KEY",
        "WANDB_API_KEY",
        "ELEVENLABS_API_KEY",
        "TELEGRAM_BOT_TOKEN",
        "DISCORD_BOT_TOKEN",
        "SLACK_BOT_TOKEN",
        "SLACK_APP_TOKEN",
        "MATRIX_ACCESS_TOKEN",
        "MATRIX_PASSWORD",
        "HASS_TOKEN",
        "EMAIL_PASSWORD",
        "FEISHU_APP_SECRET",
        "FEISHU_ENCRYPT_KEY",
        "FEISHU_VERIFICATION_TOKEN",
        "DINGTALK_CLIENT_SECRET",
        "QQ_CLIENT_SECRET",
        "WECOM_SECRET",
        "WEIXIN_TOKEN",
        "MODAL_TOKEN_ID",
        "MODAL_TOKEN_SECRET",
        "SUDO_PASSWORD",
        "GATEWAY_PROXY_KEY",
        "API_SERVER_KEY",
        "TOOL_GATEWAY_USER_TOKEN",
        "TELEGRAM_WEBHOOK_SECRET",
        "WEBHOOK_SECRET",
        "AI_GATEWAY_API_KEY",
        "VOICE_TOOLS_OPENAI_KEY",
        "BROWSER_USE_API_KEY",
        "CUSTOM_API_KEY",
        "GATEWAY_PROXY_URL",
        "GEMINI_BASE_URL",
        "OPENAI_BASE_URL",
        "OPENROUTER_BASE_URL",
        "OLLAMA_BASE_URL",
        "GROQ_BASE_URL",
        "XAI_BASE_URL",
        "AI_GATEWAY_BASE_URL",
        "ANTHROPIC_BASE_URL",
    }
)


def _looks_like_credential(name: str) -> bool:
    if name in _CREDENTIAL_NAMES:
        return True
    return any(name.endswith(suf) for suf in _CREDENTIAL_SUFFIXES)


_PROMETHEUS_BEHAVIORAL_VARS = frozenset(
    {
        "PROMETHEUS_YOLO_MODE",
        "PROMETHEUS_INTERACTIVE",
        "PROMETHEUS_QUIET",
        "PROMETHEUS_MAX_ITERATIONS",
        "PROMETHEUS_SESSION_PLATFORM",
        "PROMETHEUS_SESSION_CHAT_ID",
        "PROMETHEUS_SESSION_CHAT_NAME",
        "PROMETHEUS_SESSION_THREAD_ID",
        "PROMETHEUS_SESSION_SOURCE",
        "PROMETHEUS_SESSION_KEY",
        "PROMETHEUS_GATEWAY_SESSION",
        "PROMETHEUS_PLATFORM",
        "PROMETHEUS_MODEL",
        "PROMETHEUS_MANAGED",
        "PROMETHEUS_DEV",
        "PROMETHEUS_CONTAINER",
        "PROMETHEUS_TIMEZONE",
        "PROMETHEUS_REDACT_SECRETS",
        "PROMETHEUS_EXEC_ASK",
        "PROMETHEUS_HOME_MODE",
        "TERMINAL_CWD",
        "TERMINAL_ENV",
        "BROWSER_CDP_URL",
        "CAMOFOX_URL",
        "TELEGRAM_ALLOW_ALL_USERS",
        "DISCORD_ALLOW_ALL_USERS",
        "WHATSAPP_ALLOW_ALL_USERS",
        "SLACK_ALLOW_ALL_USERS",
    }
)


@pytest.fixture(autouse=True)
def _hermetic_environment(tmp_path, monkeypatch):
    for name in list(os.environ.keys()):
        if _looks_like_credential(name):
            monkeypatch.delenv(name, raising=False)

    for name in _PROMETHEUS_BEHAVIORAL_VARS:
        monkeypatch.delenv(name, raising=False)

    fake_home = tmp_path / "prometheus_test"
    fake_home.mkdir()
    (fake_home / "sessions").mkdir(parents=True)
    (fake_home / "cron").mkdir(parents=True)
    (fake_home / "memories").mkdir(parents=True)
    (fake_home / "skills").mkdir(parents=True)
    (fake_home / "kanban").mkdir(parents=True)
    monkeypatch.setenv("PROMETHEUS_HOME", str(fake_home))

    monkeypatch.setenv("TZ", "UTC")
    monkeypatch.setenv("LANG", "C.UTF-8")
    monkeypatch.setenv("LC_ALL", "C.UTF-8")
    monkeypatch.setenv("PYTHONHASHSEED", "0")
    monkeypatch.setenv("AWS_EC2_METADATA_DISABLED", "true")
    monkeypatch.setenv("AWS_METADATA_SERVICE_TIMEOUT", "1")
    monkeypatch.setenv("AWS_METADATA_SERVICE_NUM_ATTEMPTS", "1")

    try:
        import prometheus.cli.plugins as _plugins_mod

        monkeypatch.setattr(_plugins_mod, "_plugin_manager", None)
    except Exception:
        pass


@pytest.fixture(autouse=True)
def _reset_module_state():
    logging.disable(logging.NOTSET)
    for _logger_name in ("tools", "run_agent", "trajectory_compressor", "cron", "prometheus_cli"):
        _logger = logging.getLogger(_logger_name)
        _logger.disabled = False
        _logger.setLevel(logging.NOTSET)
        _logger.propagate = True

    try:
        from prometheus.tools import approval as _approval_mod

        _approval_mod._session_approved.clear()
        _approval_mod._session_yolo.clear()
        _approval_mod._permanent_approved.clear()
        _approval_mod._pending.clear()
    except Exception:
        pass

    try:
        from prometheus.tools import interrupt as _interrupt_mod

        with _interrupt_mod._lock:
            _interrupt_mod._interrupted_threads.clear()
    except Exception:
        pass

    try:
        from prometheus.tools import file_tools as _ft_mod

        with _ft_mod._read_tracker_lock:
            _ft_mod._read_tracker.clear()
        with _ft_mod._file_ops_lock:
            _ft_mod._file_ops_cache.clear()
    except Exception:
        pass

    yield


@pytest.fixture()
def tmp_dir(tmp_path):
    return tmp_path


@pytest.fixture()
def mock_config():
    return {
        "model": "test/mock-model",
        "toolsets": ["terminal", "file"],
        "max_turns": 10,
        "terminal": {
            "backend": "local",
            "cwd": "/tmp",
            "timeout": 30,
        },
        "compression": {"enabled": False},
        "memory": {"memory_enabled": False, "user_profile_enabled": False},
        "command_allowlist": [],
    }


def _timeout_handler(signum, frame):
    raise TimeoutError("Test exceeded 30 second timeout")


@pytest.fixture(autouse=True)
def _enforce_test_timeout():
    if sys.platform == "win32":
        yield
        return
    old = signal.signal(signal.SIGALRM, _timeout_handler)
    signal.alarm(30)
    yield
    signal.alarm(0)
    signal.signal(signal.SIGALRM, old)


@pytest.fixture(autouse=True)
def _reset_tool_registry_caches():
    try:
        from prometheus.tools.registry import invalidate_check_fn_cache

        invalidate_check_fn_cache()
    except ImportError:
        pass
    yield
