"""QQBot platform package."""

from .adapter import (
    QQAdapter,
    QQCloseError,
    _coerce_list,
    _ssrf_redirect_guard,
    check_qq_requirements,
)
from .crypto import decrypt_secret, generate_bind_key
from .onboard import (
    BindStatus,
    build_connect_url,
    qr_register,
)
from .utils import build_user_agent, coerce_list, get_api_headers

__all__ = [
    "QQAdapter",
    "QQCloseError",
    "check_qq_requirements",
    "_coerce_list",
    "_ssrf_redirect_guard",
    "BindStatus",
    "build_connect_url",
    "qr_register",
    "decrypt_secret",
    "generate_bind_key",
    "build_user_agent",
    "get_api_headers",
    "coerce_list",
]
