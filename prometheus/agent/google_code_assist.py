"""Google Code Assist API client — project discovery, onboarding, quota."""

from __future__ import annotations

import contextlib
import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

CODE_ASSIST_ENDPOINT = "https://cloudcode-pa.googleapis.com"

FALLBACK_ENDPOINTS = [
    "https://daily-cloudcode-pa.sandbox.googleapis.com",
    "https://autopush-cloudcode-pa.sandbox.googleapis.com",
]

FREE_TIER_ID = "free-tier"
LEGACY_TIER_ID = "legacy-tier"
STANDARD_TIER_ID = "standard-tier"

_GEMINI_CLI_USER_AGENT = "google-api-nodejs-client/9.15.1 (gzip)"
_X_GOOG_API_CLIENT = "gl-node/24.0.0"
_DEFAULT_REQUEST_TIMEOUT = 30.0
_ONBOARDING_POLL_ATTEMPTS = 12
_ONBOARDING_POLL_INTERVAL_SECONDS = 5.0


class CodeAssistError(RuntimeError):
    """Exception raised by the Code Assist (``cloudcode-pa``) integration.

    Carries HTTP status / response / retry-after metadata so the agent's
    ``error_classifier._extract_status_code`` and the main loop's Retry-After
    handling (which walks ``error.response.headers``) pick up the right
    signals.  Without these, 429s from the OAuth path look like opaque
    ``RuntimeError`` and skip the rate-limit path.
    """

    def __init__(
        self,
        message: str,
        *,
        code: str = "code_assist_error",
        status_code: int | None = None,
        response: Any = None,
        retry_after: float | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code
        self.response = response
        self.retry_after = retry_after
        self.details = details or {}


class ProjectIdRequiredError(CodeAssistError):
    def __init__(self, message: str = "GCP project id required for this tier") -> None:
        super().__init__(message, code="code_assist_project_id_required")


# =============================================================================
# HTTP primitive (auth via Bearer token passed per-call)
# =============================================================================


def _build_headers(access_token: str, *, user_agent_model: str = "") -> dict[str, str]:
    ua = _GEMINI_CLI_USER_AGENT
    if user_agent_model:
        ua = f"{ua} model/{user_agent_model}"
    return {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": f"Bearer {access_token}",
        "User-Agent": ua,
        "X-Goog-Api-Client": _X_GOOG_API_CLIENT,
        "x-activity-request-id": str(uuid.uuid4()),
    }


def _client_metadata() -> dict[str, str]:
    """Match Google's gemini-cli exactly — unrecognized metadata may be rejected."""
    return {
        "ideType": "IDE_UNSPECIFIED",
        "platform": "PLATFORM_UNSPECIFIED",
        "pluginType": "GEMINI",
    }


def _post_json(
    url: str,
    body: dict[str, Any],
    access_token: str,
    *,
    timeout: float = _DEFAULT_REQUEST_TIMEOUT,
    user_agent_model: str = "",
) -> dict[str, Any]:
    data = json.dumps(body).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers=_build_headers(access_token, user_agent_model=user_agent_model),
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8", errors="replace")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        detail = ""
        with contextlib.suppress(Exception):
            detail = exc.read().decode("utf-8", errors="replace")
        if _is_vpc_sc_violation(detail):
            raise CodeAssistError(
                f"VPC-SC policy violation: {detail}",
                code="code_assist_vpc_sc",
            ) from exc
        raise CodeAssistError(
            f"Code Assist HTTP {exc.code}: {detail or exc.reason}",
            code=f"code_assist_http_{exc.code}",
        ) from exc
    except urllib.error.URLError as exc:
        raise CodeAssistError(
            f"Code Assist request failed: {exc}",
            code="code_assist_network_error",
        ) from exc


def _is_vpc_sc_violation(body: str) -> bool:
    """Detect a VPC Service Controls violation from a response body."""
    if not body:
        return False
    try:
        parsed = json.loads(body)
    except (json.JSONDecodeError, ValueError):
        return "SECURITY_POLICY_VIOLATED" in body
    error = parsed.get("error") if isinstance(parsed, dict) else None
    if not isinstance(error, dict):
        return False
    details = error.get("details") or []
    if isinstance(details, list):
        for item in details:
            if isinstance(item, dict):
                reason = item.get("reason") or ""
                if reason == "SECURITY_POLICY_VIOLATED":
                    return True
    msg = str(error.get("message", ""))
    return "SECURITY_POLICY_VIOLATED" in msg


# =============================================================================
# load_code_assist — discovers current tier + assigned project
# =============================================================================


@dataclass
class CodeAssistProjectInfo:
    """Result from ``load_code_assist``."""

    current_tier_id: str = ""
    cloudaicompanion_project: str = ""
    allowed_tiers: list[str] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)


def load_code_assist(
    access_token: str,
    *,
    project_id: str = "",
    user_agent_model: str = "",
) -> CodeAssistProjectInfo:
    """Call ``POST /v1internal:loadCodeAssist`` with prod → sandbox fallback.

    Returns whatever tier + project info Google reports. On VPC-SC violations,
    returns a synthetic ``standard-tier`` result so the chain can continue.
    """
    body: dict[str, Any] = {
        "metadata": {
            "duetProject": project_id,
            **_client_metadata(),
        },
    }
    if project_id:
        body["cloudaicompanionProject"] = project_id

    endpoints = [CODE_ASSIST_ENDPOINT] + FALLBACK_ENDPOINTS
    last_err: Exception | None = None
    for endpoint in endpoints:
        url = f"{endpoint}/v1internal:loadCodeAssist"
        try:
            resp = _post_json(url, body, access_token, user_agent_model=user_agent_model)
            return _parse_load_response(resp)
        except CodeAssistError as exc:
            if exc.code == "code_assist_vpc_sc":
                logger.info("VPC-SC violation on %s — defaulting to standard-tier", endpoint)
                return CodeAssistProjectInfo(
                    current_tier_id=STANDARD_TIER_ID,
                    cloudaicompanion_project=project_id,
                )
            last_err = exc
            logger.warning("loadCodeAssist failed on %s: %s", endpoint, exc)
            continue
    if last_err:
        raise last_err
    return CodeAssistProjectInfo()


def _parse_load_response(resp: dict[str, Any]) -> CodeAssistProjectInfo:
    current_tier = resp.get("currentTier") or {}
    tier_id = str(current_tier.get("id") or "") if isinstance(current_tier, dict) else ""
    project = str(resp.get("cloudaicompanionProject") or "")
    allowed = resp.get("allowedTiers") or []
    allowed_ids: list[str] = []
    if isinstance(allowed, list):
        for t in allowed:
            if isinstance(t, dict):
                tid = str(t.get("id") or "")
                if tid:
                    allowed_ids.append(tid)
    return CodeAssistProjectInfo(
        current_tier_id=tier_id,
        cloudaicompanion_project=project,
        allowed_tiers=allowed_ids,
        raw=resp,
    )


# =============================================================================
# onboard_user — provisions a new user on a tier (with LRO polling)
# =============================================================================


def onboard_user(
    access_token: str,
    *,
    tier_id: str,
    project_id: str = "",
    user_agent_model: str = "",
) -> dict[str, Any]:
    """Call ``POST /v1internal:onboardUser`` to provision the user.

    For paid tiers, ``project_id`` is REQUIRED (raises ProjectIdRequiredError).
    For free tiers, ``project_id`` is optional — Google will assign one.

    Returns the final operation response. Polls ``/v1internal/<name>`` for up
    to ``_ONBOARDING_POLL_ATTEMPTS`` × ``_ONBOARDING_POLL_INTERVAL_SECONDS``
    (default: 12 × 5s = 1 min).
    """
    if tier_id != FREE_TIER_ID and tier_id != LEGACY_TIER_ID and not project_id:
        raise ProjectIdRequiredError(
            f"Tier {tier_id!r} requires a GCP project id. "
            "Set PROMETHEUS_GEMINI_PROJECT_ID or GOOGLE_CLOUD_PROJECT."
        )

    body: dict[str, Any] = {
        "tierId": tier_id,
        "metadata": _client_metadata(),
    }
    if project_id:
        body["cloudaicompanionProject"] = project_id

    endpoint = CODE_ASSIST_ENDPOINT
    url = f"{endpoint}/v1internal:onboardUser"
    resp = _post_json(url, body, access_token, user_agent_model=user_agent_model)

    if not resp.get("done"):
        op_name = resp.get("name", "")
        if not op_name:
            return resp
        for attempt in range(_ONBOARDING_POLL_ATTEMPTS):
            time.sleep(_ONBOARDING_POLL_INTERVAL_SECONDS)
            poll_url = f"{endpoint}/v1internal/{op_name}"
            try:
                poll_resp = _post_json(
                    poll_url, {}, access_token, user_agent_model=user_agent_model
                )
            except CodeAssistError as exc:
                logger.warning("Onboarding poll attempt %d failed: %s", attempt + 1, exc)
                continue
            if poll_resp.get("done"):
                return poll_resp
        logger.warning("Onboarding did not complete within %d attempts", _ONBOARDING_POLL_ATTEMPTS)
    return resp


# =============================================================================
# retrieve_user_quota — for /gquota
# =============================================================================


@dataclass
class QuotaBucket:
    model_id: str
    token_type: str = ""
    remaining_fraction: float = 0.0
    reset_time_iso: str = ""
    raw: dict[str, Any] = field(default_factory=dict)


def retrieve_user_quota(
    access_token: str,
    *,
    project_id: str = "",
    user_agent_model: str = "",
) -> list[QuotaBucket]:
    """Call ``POST /v1internal:retrieveUserQuota`` and parse ``buckets[]``."""
    body: dict[str, Any] = {}
    if project_id:
        body["project"] = project_id
    url = f"{CODE_ASSIST_ENDPOINT}/v1internal:retrieveUserQuota"
    resp = _post_json(url, body, access_token, user_agent_model=user_agent_model)
    raw_buckets = resp.get("buckets") or []
    buckets: list[QuotaBucket] = []
    if not isinstance(raw_buckets, list):
        return buckets
    for b in raw_buckets:
        if not isinstance(b, dict):
            continue
        buckets.append(
            QuotaBucket(
                model_id=str(b.get("modelId") or ""),
                token_type=str(b.get("tokenType") or ""),
                remaining_fraction=float(b.get("remainingFraction") or 0.0),
                reset_time_iso=str(b.get("resetTime") or ""),
                raw=b,
            )
        )
    return buckets


# =============================================================================
# Project context resolution
# =============================================================================


@dataclass
class ProjectContext:
    """Resolved state for a given OAuth session."""

    project_id: str = ""
    managed_project_id: str = ""
    tier_id: str = ""
    source: str = ""


def resolve_project_context(
    access_token: str,
    *,
    configured_project_id: str = "",
    env_project_id: str = "",
    user_agent_model: str = "",
) -> ProjectContext:
    """Figure out what project id + tier to use for requests.

    Priority:
      1. If configured_project_id or env_project_id is set, use that directly
         and short-circuit (no discovery needed).
      2. Otherwise call loadCodeAssist to see what Google says.
      3. If no tier assigned yet, onboard the user (free tier default).
    """
    if configured_project_id:
        return ProjectContext(
            project_id=configured_project_id,
            tier_id=STANDARD_TIER_ID,
            source="config",
        )
    if env_project_id:
        return ProjectContext(
            project_id=env_project_id,
            tier_id=STANDARD_TIER_ID,
            source="env",
        )

    info = load_code_assist(access_token, user_agent_model=user_agent_model)

    effective_project = info.cloudaicompanion_project
    tier = info.current_tier_id

    if not tier:
        onboard_resp = onboard_user(
            access_token,
            tier_id=FREE_TIER_ID,
            project_id="",
            user_agent_model=user_agent_model,
        )
        response_body = onboard_resp.get("response") or {}
        if isinstance(response_body, dict):
            effective_project = effective_project or str(
                response_body.get("cloudaicompanionProject") or ""
            )
        tier = FREE_TIER_ID
        source = "onboarded"
    else:
        source = "discovered"

    return ProjectContext(
        project_id=effective_project,
        managed_project_id=effective_project if tier == FREE_TIER_ID else "",
        tier_id=tier,
        source=source,
    )
