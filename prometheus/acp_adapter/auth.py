from __future__ import annotations

import hashlib
import logging
import secrets
import time

logger = logging.getLogger("prometheus.acp_adapter.auth")


class ACPAuth:
    def __init__(self, secret: str | None = None) -> None:
        self._secret = secret or secrets.token_hex(32)
        self._tokens: dict[str, float] = {}
        self._token_ttl = 86400.0

    def authenticate(self, token: str) -> bool:
        if token not in self._tokens:
            return False

        created_at = self._tokens[token]
        if time.time() - created_at > self._token_ttl:
            del self._tokens[token]
            return False

        return True

    def generate_token(self) -> str:
        raw = f"{secrets.token_hex(16)}:{self._secret}:{time.time()}"
        token = hashlib.sha256(raw.encode()).hexdigest()
        self._tokens[token] = time.time()
        logger.info("Generated new ACP auth token")
        return token

    def revoke_token(self, token: str) -> bool:
        if token in self._tokens:
            del self._tokens[token]
            return True
        return False
