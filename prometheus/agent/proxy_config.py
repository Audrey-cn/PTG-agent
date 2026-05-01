"""Proxy configuration utilities for Prometheus."""

import os
import re
from re import Pattern


class ProxyConfig:
    """Proxy configuration handler.

    Manages proxy environment variables and NO_PROXY patterns.
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def initialize(self):
        """Initialize proxy configuration from environment."""
        if self._initialized:
            return

        self._http_proxy = os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy")
        self._https_proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
        self._no_proxy = os.environ.get("NO_PROXY") or os.environ.get("no_proxy") or ""

        self._no_proxy_patterns = self._parse_no_proxy(self._no_proxy)
        self._initialized = True

    def _parse_no_proxy(self, no_proxy: str) -> list[Pattern]:
        """Parse NO_PROXY environment variable into regex patterns."""
        patterns = []

        if not no_proxy:
            return patterns

        entries = [e.strip() for e in no_proxy.split(",") if e.strip()]

        for entry in entries:
            # Convert wildcard patterns to regex
            regex_pattern = entry.replace(".", r"\.").replace("*", r".*")

            # Handle CIDR notation (optional)
            if "/" in entry and "*" not in entry:
                try:
                    host, mask = entry.rsplit("/", 1)
                    # Simple CIDR handling for common cases
                    regex_pattern = host.replace(".", r"\.") + r"(?:\.\d+)?"
                except ValueError:
                    pass

            patterns.append(re.compile(regex_pattern, re.IGNORECASE))

        return patterns

    def should_use_proxy(self, hostname: str) -> bool:
        """Determine if proxy should be used for a given hostname."""
        if not self._initialized:
            self.initialize()

        if not self._http_proxy and not self._https_proxy:
            return False

        if not self._no_proxy_patterns:
            return True

        return all(not pattern.match(hostname) for pattern in self._no_proxy_patterns)

    def get_proxy_url(self, scheme: str = "https") -> str | None:
        """Get proxy URL for the given scheme."""
        if not self._initialized:
            self.initialize()

        if scheme.lower() == "http":
            return self._http_proxy
        return self._https_proxy

    def get_requests_session_proxies(self) -> dict:
        """Get proxies dict for requests.Session."""
        proxies = {}

        if self._http_proxy:
            proxies["http"] = self._http_proxy

        if self._https_proxy:
            proxies["https"] = self._https_proxy

        return proxies

    def get_httpx_client_proxies(self) -> str | None:
        """Get proxy URL for httpx.AsyncClient."""
        if not self._initialized:
            self.initialize()

        return self._https_proxy or self._http_proxy

    def get_openai_proxy(self) -> str | None:
        """Get proxy configuration for OpenAI client."""
        return self.get_proxy_url("https")

    def get_anthropic_proxy(self) -> str | None:
        """Get proxy configuration for Anthropic client."""
        return self.get_proxy_url("https")

    def get_gemini_proxy(self) -> str | None:
        """Get proxy configuration for Gemini client."""
        return self.get_proxy_url("https")

    def is_configured(self) -> bool:
        """Check if any proxy is configured."""
        if not self._initialized:
            self.initialize()

        return bool(self._http_proxy or self._https_proxy)

    def get_config(self) -> dict:
        """Get current proxy configuration."""
        if not self._initialized:
            self.initialize()

        return {
            "http_proxy": self._http_proxy,
            "https_proxy": self._https_proxy,
            "no_proxy": self._no_proxy,
            "no_proxy_patterns_count": len(self._no_proxy_patterns),
        }


def get_proxy_config() -> ProxyConfig:
    """Get global proxy configuration instance."""
    return ProxyConfig()


def configure_openai_with_proxy(client):
    """Configure OpenAI client with proxy settings."""
    proxy_config = get_proxy_config()

    if proxy_config.is_configured():
        import httpx

        proxy_url = proxy_config.get_openai_proxy()

        if proxy_url:
            client._client = httpx.AsyncClient(
                proxy=proxy_url,
                timeout=client._client.timeout,
            )


def configure_anthropic_with_proxy(client):
    """Configure Anthropic client with proxy settings."""
    proxy_config = get_proxy_config()

    if proxy_config.is_configured():
        proxy_url = proxy_config.get_anthropic_proxy()

        if proxy_url:
            import httpx

            client._client._transport = httpx.AsyncHTTPTransport(
                proxy=proxy_url,
            )


def configure_gemini_with_proxy(client):
    """Configure Gemini client with proxy settings."""
    proxy_config = get_proxy_config()

    if proxy_config.is_configured():
        proxy_url = proxy_config.get_gemini_proxy()

        if proxy_url:
            import httpx

            transport = httpx.AsyncHTTPTransport(proxy=proxy_url)
            client._client._http_client = httpx.AsyncClient(transport=transport)
