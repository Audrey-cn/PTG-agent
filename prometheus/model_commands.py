from __future__ import annotations

import json
import urllib.error
import urllib.request

from prometheus.model_catalog import get_model_info, list_models
from prometheus.model_normalize import normalize_model_name
from prometheus.runtime_provider import detect_provider_from_url, resolve_base_url


def cmd_model_list(provider: str | None = None) -> None:
    models = list_models(provider)
    if not models:
        scope = f"provider '{provider}'" if provider else "catalog"
        print(f"No models found for {scope}.")
        return
    for m in models:
        pricing = m["pricing"]
        print(
            f"  {m['id']:<24s} ctx={m['context_length']:>10,d}  in=${pricing['in']:.2f} out=${pricing['out']:.2f}  {m['description']}"
        )


def cmd_model_switch(model_name: str, config: dict) -> None:
    resolved = normalize_model_name(model_name)
    info = get_model_info(resolved)
    if info is None:
        print(f"Unknown model: '{model_name}' (resolved to '{resolved}')")
        return
    config["model"] = resolved
    print(f"Switched to {resolved} ({info['description']})")


def cmd_model_info(model_name: str) -> None:
    resolved = normalize_model_name(model_name)
    info = get_model_info(resolved)
    if info is None:
        print(f"Unknown model: '{model_name}' (resolved to '{resolved}')")
        return
    pricing = info["pricing"]
    print(f"Model:       {info['id']}")
    print(f"Description: {info['description']}")
    print(f"Context:     {info['context_length']:,d} tokens")
    print(f"Pricing:     in=${pricing['in']:.2f} / out=${pricing['out']:.2f} per 1M tokens")


def cmd_model_probe(base_url: str, api_key: str) -> None:
    provider = detect_provider_from_url(base_url)
    url = resolve_base_url(provider, {"base_url": base_url}).rstrip("/")
    if not url.endswith("/models"):
        url = url + "/models"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {api_key}"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        models = data.get("data", [])
        if not models:
            print("No models returned by endpoint.")
            return
        for m in models:
            mid = m.get("id", "unknown")
            print(f"  {mid}")
    except urllib.error.HTTPError as e:
        print(f"HTTP error {e.code}: {e.reason}")
    except urllib.error.URLError as e:
        print(f"Connection error: {e.reason}")
    except Exception as e:
        print(f"Probe failed: {e}")
