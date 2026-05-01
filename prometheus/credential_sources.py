from __future__ import annotations

import logging
import os
import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

import yaml

from prometheus.config import get_config_path, get_prometheus_home

logger = logging.getLogger("prometheus.credential_sources")


@dataclass
class CredentialEntry:
    key: str
    provider: str = ""
    source: str = ""
    base_url: str = ""


class CredentialSource(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def discover(self) -> list[CredentialEntry]: ...


class EnvCredentialSource(CredentialSource):
    _ENV_MAP: Dict[str, Tuple[str, str]] = {
        "OPENAI_API_KEY": ("openai", "https://api.openai.com/v1"),
        "ANTHROPIC_API_KEY": ("anthropic", "https://api.anthropic.com"),
        "OPENROUTER_API_KEY": ("openrouter", "https://openrouter.ai/api/v1"),
        "DEEPSEEK_API_KEY": ("deepseek", "https://api.deepseek.com/v1"),
        "GOOGLE_API_KEY": ("gemini", ""),
        "GEMINI_API_KEY": ("gemini", ""),
        "XAI_API_KEY": ("xai", "https://api.x.ai/v1"),
    }

    @property
    def name(self) -> str:
        return "env"

    def discover(self) -> list[CredentialEntry]:
        entries: list[CredentialEntry] = []
        for env_var, (provider, base_url) in self._ENV_MAP.items():
            val = os.environ.get(env_var, "").strip()
            if val:
                entries.append(
                    CredentialEntry(
                        key=val,
                        provider=provider,
                        source=f"env:{env_var}",
                        base_url=base_url,
                    )
                )
        return entries


class ConfigCredentialSource(CredentialSource):
    def __init__(self, config_path: Optional[Path] = None):
        self._config_path = config_path or get_config_path()

    @property
    def name(self) -> str:
        return "config"

    def discover(self) -> list[CredentialEntry]:
        entries: list[CredentialEntry] = []
        if not self._config_path.exists():
            return entries
        try:
            with open(self._config_path, encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}
        except Exception as e:
            logger.error("ConfigCredentialSource.discover failed: %s", e)
            return entries

        api = config.get("api", {})
        key = api.get("key", "")
        if key:
            provider = config.get("model", {}).get("provider", "")
            base_url = api.get("base_url", "")
            entries.append(
                CredentialEntry(
                    key=key,
                    provider=provider,
                    source="config:api.key",
                    base_url=base_url,
                )
            )

        pool = api.get("credential_pool", [])
        for entry in pool:
            if isinstance(entry, dict) and entry.get("key"):
                entries.append(
                    CredentialEntry(
                        key=entry["key"],
                        provider=entry.get("provider", ""),
                        source="config:credential_pool",
                        base_url=entry.get("base_url", ""),
                    )
                )

        providers = config.get("providers", {})
        for prov_name, prov_conf in providers.items():
            if isinstance(prov_conf, dict) and prov_conf.get("key"):
                entries.append(
                    CredentialEntry(
                        key=prov_conf["key"],
                        provider=prov_name,
                        source=f"config:providers.{prov_name}",
                        base_url=prov_conf.get("base_url", ""),
                    )
                )

        return entries


class KeychainCredentialSource(CredentialSource):
    def __init__(self, service_names: List[str] | None = None):
        self._service_names = service_names or [
            "OpenAI",
            "Anthropic",
            "OpenRouter",
            "DeepSeek",
        ]

    @property
    def name(self) -> str:
        return "keychain"

    def discover(self) -> list[CredentialEntry]:
        entries: list[CredentialEntry] = []
        for service in self._service_names:
            try:
                result = subprocess.run(
                    ["security", "find-generic-password", "-s", service, "-w"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if result.returncode == 0 and result.stdout.strip():
                    entries.append(
                        CredentialEntry(
                            key=result.stdout.strip(),
                            provider=service.lower(),
                            source=f"keychain:{service}",
                            base_url="",
                        )
                    )
            except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
                continue
            except Exception as e:
                logger.debug("KeychainCredentialSource.discover failed for %s: %s", service, e)
        return entries


class DotenvCredentialSource(CredentialSource):
    def __init__(self, dotenv_paths: list[Path] | None = None):
        if dotenv_paths is not None:
            self._paths = dotenv_paths
        else:
            self._paths = [
                get_prometheus_home() / ".env",
                Path.cwd() / ".env",
            ]

    @property
    def name(self) -> str:
        return "dotenv"

    def discover(self) -> list[CredentialEntry]:
        entries: list[CredentialEntry] = []
        key_patterns = ("API_KEY", "SECRET", "TOKEN", "ACCESS_KEY")
        for dotenv_path in self._paths:
            if not dotenv_path.exists():
                continue
            try:
                with open(dotenv_path, encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith("#"):
                            continue
                        if "=" not in line:
                            continue
                        k, v = line.split("=", 1)
                        k = k.strip()
                        v = v.strip().strip("\"'")
                        if not v:
                            continue
                        upper_k = k.upper()
                        if any(p in upper_k for p in key_patterns):
                            entries.append(
                                CredentialEntry(
                                    key=v,
                                    provider="",
                                    source=f"dotenv:{dotenv_path.name}:{k}",
                                    base_url="",
                                )
                            )
            except Exception as e:
                logger.debug("DotenvCredentialSource.discover failed for %s: %s", dotenv_path, e)
        return entries


class CredentialDiscovery:
    def __init__(self, sources: list[CredentialSource] | None = None):
        if sources is not None:
            self._sources = sources
        else:
            self._sources = [
                EnvCredentialSource(),
                ConfigCredentialSource(),
                KeychainCredentialSource(),
                DotenvCredentialSource(),
            ]

    def discover_all(self) -> list[CredentialEntry]:
        seen_keys: Set[str] = set()
        entries: list[CredentialEntry] = []
        for source in self._sources:
            try:
                found = source.discover()
            except Exception as e:
                logger.error("CredentialDiscovery.discover_all failed for %s: %s", source.name, e)
                continue
            for entry in found:
                if entry.key not in seen_keys:
                    seen_keys.add(entry.key)
                    entries.append(entry)
        return entries
