"""MrToken's OpenAI-compatible platform API (never upstream vendor APIs)."""

from __future__ import annotations

from urllib.parse import urlsplit

import httpx

BASE_URL = "https://api.mrtoken.cn"
SDK_BASE_URL = f"{BASE_URL}/v1"


def _error_message(payload: object, api_key: str) -> str:
    """Read documented error fields without returning credentials or raw bodies."""
    if not isinstance(payload, dict):
        return ""
    detail = payload.get("detail")
    error = payload.get("error")
    candidates: list[object] = []
    if isinstance(detail, dict) and isinstance(detail.get("reasons"), list):
        candidates.extend(detail["reasons"])
    if isinstance(error, dict):
        candidates.append(error.get("message"))
    candidates.extend([detail, payload.get("message")])
    for candidate in candidates:
        if isinstance(candidate, str) and candidate.strip():
            # Redact before truncating: a truncation must not leave a partial key.
            return " ".join(candidate.replace(api_key, "[REDACTED]").split())[:300]
    return ""


def normalize_base_url(value: str | None = None) -> str:
    """NewAPI appends /v1; accept SDK URLs without duplicating that prefix."""
    base = str(value or BASE_URL).strip().rstrip("/")
    if base.endswith("/v1"):
        base = base[:-3]
    parsed = urlsplit(base)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.netloc
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError(
            "MrToken baseUrl must be an HTTP URL without credentials or query"
        )
    return base


async def discover_models(api_key: str, base_url: str | None = None) -> list[str]:
    """List exact platform IDs; an empty catalog stays empty."""
    if not api_key.strip():
        raise ValueError("MrToken platform API Key is required")
    base = normalize_base_url(base_url)
    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=False) as client:
            response = await client.get(
                f"{base}/v1/models",
                headers={"Authorization": f"Bearer {api_key.strip()}"},
            )
        if response.status_code != 200:
            try:
                message = _error_message(response.json(), api_key.strip())
            except ValueError:
                message = ""
            raise ValueError(
                f"MrToken model discovery failed: HTTP {response.status_code}"
                + (f" ({message})" if message else "")
            )
        payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        if isinstance(exc, ValueError) and str(exc).startswith(
            "MrToken model discovery"
        ):
            raise
        raise ValueError(
            "MrToken model discovery failed: network or invalid JSON response"
        ) from None
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, list):
        raise ValueError("MrToken model discovery failed: missing data list")
    return list(
        dict.fromkeys(
            item["id"]
            for item in data
            if isinstance(item, dict)
            and isinstance(item.get("id"), str)
            and item["id"].strip()
            and api_key.strip() not in item["id"]
        )
    )
