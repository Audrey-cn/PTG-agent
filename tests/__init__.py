"""Prometheus test suite utilities.

Fixtures and helpers for testing Prometheus components.
"""

import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from prometheus.agent.error_classifier import FailoverReason, classify_api_error
from prometheus.agent.lazy_imports import LazyClass, LazyModule
from prometheus.agent.prompt_cache import get_prompt_cache
from prometheus.agent.proxy_config import get_proxy_config
from prometheus.agent.resource_cleanup import get_cleanup_manager

# ── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture(scope="function")
def temp_dir():
    """Create a temporary directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture(scope="function")
def mock_env():
    """Set up a mock environment."""
    original_env = os.environ.copy()

    yield

    os.environ.clear()
    os.environ.update(original_env)


@pytest.fixture(scope="function")
def clean_prometheus_dir():
    """Clean up Prometheus directory before and after test."""
    import shutil

    from prometheus.config import get_prometheus_home

    prom_home = get_prometheus_home()

    if prom_home.exists():
        shutil.rmtree(prom_home)

    yield

    if prom_home.exists():
        shutil.rmtree(prom_home)


@pytest.fixture(scope="function")
def mock_transport():
    """Create a mock transport."""
    mock = MagicMock()
    mock.create_completion = MagicMock(return_value={"content": "test response"})
    return mock


@pytest.fixture(scope="function")
def error_classifier():
    """Return the error classifier function."""
    return classify_api_error


@pytest.fixture(scope="function")
def proxy_config():
    """Get a fresh proxy config instance."""
    config = get_proxy_config()
    config._initialized = False
    return config


@pytest.fixture(scope="function")
def cleanup_manager():
    """Get a fresh cleanup manager instance."""
    manager = get_cleanup_manager()
    manager._cleanup_handlers = []
    manager._resources = {}
    return manager


@pytest.fixture(scope="function")
def prompt_cache():
    """Get a fresh prompt cache instance."""
    cache = get_prompt_cache()
    cache._cache = {}
    return cache


# ── Mock Classes ────────────────────────────────────────────────────────


class MockTransport:
    """Mock transport for testing."""

    def __init__(self, responses: list = None):
        self._responses = responses or []
        self._call_count = 0

    def create_completion(self, messages, model, **kwargs):
        self._call_count += 1
        if self._responses:
            return self._responses.pop(0)
        return {"content": "mock response"}

    async def create_completion_async(self, messages, model, **kwargs):
        return self.create_completion(messages, model, **kwargs)


class MockToolResult:
    """Mock tool result for testing."""

    def __init__(self, content: str = "", tool_name: str = "", success: bool = True):
        self.content = content
        self.tool_name = tool_name
        self.success = success


# ── Test Helpers ────────────────────────────────────────────────────────


class AgentTestHelper:
    """Helper for testing agent behavior."""

    def __init__(self):
        self.call_history = []

    def track_call(self, **kwargs):
        """Track an API call."""
        self.call_history.append(kwargs)

    def get_call_count(self) -> int:
        """Get the number of calls tracked."""
        return len(self.call_history)

    def get_last_call(self) -> dict:
        """Get the last tracked call."""
        return self.call_history[-1] if self.call_history else {}


class ContextCompressorTestHelper:
    """Helper for testing context compressor."""

    def create_test_messages(self, count: int, tokens_per_message: int = 100) -> list:
        """Create test messages."""
        messages = []
        for i in range(count):
            messages.append(
                {
                    "role": "user" if i % 2 == 0 else "assistant",
                    "content": "x" * tokens_per_message,
                }
            )
        return messages


# ── Markers ─────────────────────────────────────────────────────────────


def pytest_configure(config):
    """Configure pytest markers."""
    config.addinivalue_line("markers", "unit: Mark a test as a unit test")
    config.addinivalue_line("markers", "integration: Mark a test as an integration test")
    config.addinivalue_line("markers", "slow: Mark a test as slow (skip by default)")
    config.addinivalue_line("markers", "requires_api_key: Mark a test that requires API keys")


# ── Auto-skip for slow tests ────────────────────────────────────────────


def pytest_addoption(parser):
    """Add pytest options."""
    parser.addoption("--run-slow", action="store_true", default=False, help="Run slow tests")
    parser.addoption(
        "--run-requires-api-key",
        action="store_true",
        default=False,
        help="Run tests that require API keys",
    )


def pytest_collection_modifyitems(config, items):
    """Modify test collection."""
    if not config.getoption("--run-slow"):
        skip_slow = pytest.mark.skip(reason="Need --run-slow option to run")
        for item in items:
            if "slow" in item.keywords:
                item.add_marker(skip_slow)

    if not config.getoption("--run-requires-api-key"):
        skip_api_key = pytest.mark.skip(reason="Need --run-requires-api-key option to run")
        for item in items:
            if "requires_api_key" in item.keywords:
                item.add_marker(skip_api_key)
