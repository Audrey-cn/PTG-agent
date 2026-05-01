from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
import urllib.request
import urllib.error

from prometheus.config import get_prometheus_home

MODELS_DEV_URL = "https://models.dev/api.json"
CACHE_TTL_SECONDS = 86400


def _get_cache_path() -> Path:
    return get_prometheus_home() / "models_dev_cache.json"


def _load_cache() -> Dict[str, Any]:
    cache_path = _get_cache_path()
    if cache_path.exists():
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
        except (json.JSONDecodeError, IOError):
            pass
    return {}


def _save_cache(data: Dict[str, Any]):
    cache_path = _get_cache_path()
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    data["_cached_at"] = time.time()
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _is_cache_valid(cache_data: Dict[str, Any]) -> bool:
    cached_at = cache_data.get("_cached_at", 0)
    return (time.time() - cached_at) < CACHE_TTL_SECONDS


def fetch_models_dev_catalog(force_refresh: bool = False) -> Dict[str, Any]:
    cache_data = _load_cache()
    
    if not force_refresh and _is_cache_valid(cache_data):
        return cache_data
    
    try:
        request = urllib.request.Request(
            MODELS_DEV_URL,
            headers={"User-Agent": "Prometheus-Agent/1.0"}
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            data = json.loads(response.read().decode("utf-8"))
            _save_cache(data)
            return data
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, TimeoutError):
        if cache_data:
            return cache_data
        return {}


def get_models_for_provider(provider: str) -> List[Dict[str, Any]]:
    catalog = fetch_models_dev_catalog()
    provider_data = catalog.get(provider, {})
    models = []
    
    if isinstance(provider_data, dict):
        for model_id, model_info in provider_data.items():
            if isinstance(model_info, dict):
                models.append({
                    "id": model_id,
                    "provider": provider,
                    **model_info
                })
    
    return models


def get_model_capabilities(model_id: str) -> Dict[str, Any]:
    catalog = fetch_models_dev_catalog()
    
    for provider, provider_data in catalog.items():
        if isinstance(provider_data, dict):
            for mid, model_info in provider_data.items():
                if mid == model_id and isinstance(model_info, dict):
                    return {
                        "id": model_id,
                        "provider": provider,
                        **model_info
                    }
    
    return {}


def search_models(query: str) -> List[Dict[str, Any]]:
    catalog = fetch_models_dev_catalog()
    results = []
    query_lower = query.lower()
    
    for provider, provider_data in catalog.items():
        if isinstance(provider_data, dict):
            for model_id, model_info in provider_data.items():
                if isinstance(model_info, dict):
                    searchable = f"{provider} {model_id} {model_info.get('name', '')} {model_info.get('description', '')}".lower()
                    if query_lower in searchable:
                        results.append({
                            "id": model_id,
                            "provider": provider,
                            **model_info
                        })
    
    return results


def merge_with_local_catalog(local_catalog: Dict[str, Any], dev_catalog: Dict[str, Any]) -> Dict[str, Any]:
    merged = {}
    
    for provider, provider_data in dev_catalog.items():
        if provider.startswith("_"):
            continue
        if isinstance(provider_data, dict):
            merged[provider] = dict(provider_data)
    
    for provider, provider_data in local_catalog.items():
        if isinstance(provider_data, dict):
            if provider not in merged:
                merged[provider] = {}
            for model_id, model_info in provider_data.items():
                if isinstance(model_info, dict):
                    merged[provider][model_id] = model_info
    
    return merged


def get_all_providers() -> List[str]:
    catalog = fetch_models_dev_catalog()
    return [p for p in catalog.keys() if not p.startswith("_")]


def get_popular_models(limit: int = 20) -> List[Dict[str, Any]]:
    catalog = fetch_models_dev_catalog()
    all_models = []
    
    for provider, provider_data in catalog.items():
        if provider.startswith("_"):
            continue
        if isinstance(provider_data, dict):
            for model_id, model_info in provider_data.items():
                if isinstance(model_info, dict):
                    all_models.append({
                        "id": model_id,
                        "provider": provider,
                        **model_info
                    })
    
    return all_models[:limit]
