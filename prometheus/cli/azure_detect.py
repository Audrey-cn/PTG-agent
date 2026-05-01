"""Azure Foundry endpoint auto-detection."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from urllib import request as urllib_request
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


_AZURE_OPENAI_PROBE_API_VERSIONS = (
    "2025-04-01-preview",
    "2024-10-21",
)

_AZURE_ANTHROPIC_API_VERSION = "2025-04-15"


@dataclass
class DetectionResult:
    """Everything auto-detection could gather from a base URL + API key."""

    api_mode: str | None = None

    models: List[str] = field(default_factory=list)

    hostname: str = ""

    reason: str = ""

    models_probe_ok: bool = False

    is_anthropic: bool = False


def _http_get_json(url: str, api_key: str, timeout: float = 6.0) -> Tuple[int, dict | None]:
    """GET a URL with ``api-key`` + ``Authorization`` headers."""
    req = urllib_request.Request(url, method="GET")
    req.add_header("api-key", api_key)
    req.add_header("Authorization", f"Bearer {api_key}")
    req.add_header("User-Agent", "prometheus-agent/azure-detect")
    try:
        with urllib_request.urlopen(req, timeout=timeout) as resp:
            body = resp.read()
            try:
                return resp.status, json.loads(body.decode("utf-8", errors="replace"))
            except Exception:
                return resp.status, None
    except HTTPError as exc:
        return exc.code, None
    except (URLError, TimeoutError, OSError) as exc:
        logger.debug("azure_detect: GET %s failed: %s", url, exc)
        return 0, None
    except Exception as exc:
        logger.debug("azure_detect: GET %s unexpected error: %s", url, exc)
        return 0, None


def _strip_trailing_v1(url: str) -> str:
    """Strip trailing ``/v1`` or ``/v1/`` so we can construct sub-paths."""
    return re.sub(r"/v1/?$", "", url.rstrip("/"))


def _looks_like_anthropic_path(url: str) -> bool:
    """Return True when the URL's path ends in ``/anthropic`` or
    contains a ``/anthropic/`` segment."""
    try:
        parsed = urlparse(url)
        path = (parsed.path or "").lower().rstrip("/")
        return path.endswith("/anthropic") or "/anthropic/" in path + "/"
    except Exception:
        return False


def _extract_model_ids(payload: dict) -> List[str]:
    """Extract a list of model IDs from an OpenAI-shaped ``/models`` response."""
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, list):
        return []
    ids: List[str] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        mid = item.get("id") or item.get("model") or item.get("name")
        if isinstance(mid, str) and mid:
            ids.append(mid)
    return ids


def _probe_openai_models(base_url: str, api_key: str) -> Tuple[bool, List[str]]:
    """Probe ``<base>/models`` for an OpenAI-shaped response."""
    base_url = base_url.rstrip("/")

    candidates = [f"{base_url}/models"]
    for v in _AZURE_OPENAI_PROBE_API_VERSIONS:
        candidates.append(f"{base_url}/models?api-version={v}")

    for url in candidates:
        status, body = _http_get_json(url, api_key)
        if status == 200 and body is not None:
            ids = _extract_model_ids(body)
            if ids:
                logger.info(
                    "azure_detect: /models probe OK at %s (%d models)",
                    url,
                    len(ids),
                )
                return True, ids
            if isinstance(body, dict) and "data" in body:
                return True, []
    return False, []


def _probe_anthropic_messages(base_url: str, api_key: str) -> bool:
    """Send a zero-token request to ``<base>/v1/messages`` and check
    whether the endpoint at least *recognises* the Anthropic Messages shape."""
    base = _strip_trailing_v1(base_url)
    url = f"{base}/v1/messages?api-version={_AZURE_ANTHROPIC_API_VERSION}"
    payload = json.dumps(
        {
            "model": "probe",
            "max_tokens": 1,
            "messages": [{"role": "user", "content": "ping"}],
        }
    ).encode("utf-8")
    req = urllib_request.Request(url, method="POST", data=payload)
    req.add_header("api-key", api_key)
    req.add_header("Authorization", f"Bearer {api_key}")
    req.add_header("anthropic-version", "2023-06-01")
    req.add_header("content-type", "application/json")
    req.add_header("User-Agent", "prometheus-agent/azure-detect")
    try:
        with urllib_request.urlopen(req, timeout=6.0) as resp:
            return resp.status < 500
    except HTTPError as exc:
        try:
            body = exc.read().decode("utf-8", errors="replace")
            lowered = body.lower()
            if "anthropic" in lowered or '"type"' in lowered and '"error"' in lowered:
                return True
            return bool(exc.code == 400 and ("messages" in lowered or "model" in lowered))
        except Exception:
            return False
    except (URLError, TimeoutError, OSError):
        return False
    except Exception:
        return False


def detect(base_url: str, api_key: str) -> DetectionResult:
    """Inspect an Azure endpoint and describe its transport + models."""
    result = DetectionResult()

    try:
        parsed = urlparse(base_url)
        result.hostname = (parsed.hostname or "").lower()
    except Exception:
        result.hostname = ""

    if _looks_like_anthropic_path(base_url):
        result.is_anthropic = True
        result.api_mode = "anthropic_messages"
        result.reason = "URL path ends in /anthropic → Anthropic Messages API"
        return result

    ok, models = _probe_openai_models(base_url, api_key)
    if ok:
        result.models_probe_ok = True
        result.models = models
        result.api_mode = "chat_completions"
        result.reason = (
            f"GET /models returned {len(models)} model(s) — OpenAI-style endpoint"
            if models
            else "GET /models returned an OpenAI-shaped empty list — OpenAI-style endpoint"
        )
        return result

    if _probe_anthropic_messages(base_url, api_key):
        result.is_anthropic = True
        result.api_mode = "anthropic_messages"
        result.reason = "Endpoint accepts Anthropic Messages shape"
        return result

    result.reason = (
        "Could not probe endpoint (private network, missing model list, or "
        "non-standard path) — falling back to manual API-mode selection"
    )
    return result


def lookup_context_length(model: str, base_url: str, api_key: str) -> int | None:
    """Thin wrapper around :func:`agent.model_metadata.get_model_context_length`."""
    try:
        from prometheus.agent.model_metadata import (
            DEFAULT_FALLBACK_CONTEXT,
            get_model_context_length,
        )
    except Exception:
        return None

    try:
        n = get_model_context_length(model, base_url=base_url, api_key=api_key)
    except Exception as exc:
        logger.debug("azure_detect: context length lookup failed: %s", exc)
        return None

    if isinstance(n, int) and n > 0 and n != DEFAULT_FALLBACK_CONTEXT:
        return n
    return None


__all__ = ["DetectionResult", "detect", "lookup_context_length"]
