"""Reversible free billing for the bundled gateway's default routing group."""

from __future__ import annotations

import json
import threading
from typing import Any

import httpx

from novelvideo.model_gateway_settings import (
    get_local_billing_backup,
    save_local_billing_backup,
)
from novelvideo.newapi_provisioner import (
    admin_headers,
    ensure_admin_access_token,
    get_provisioner_config,
    require_newapi_admin_service,
    require_newapi_success,
    require_provisioner_enabled,
)

_BILLING_LOCK = threading.Lock()
_FREE_PRECONSUME = "quota_setting.enable_free_model_pre_consume"
_OPTION_KEYS = ("GroupRatio", "GroupGroupRatio", "SelfUseModeEnabled", _FREE_PRECONSUME)


def _read_options(client: httpx.Client, base_url: str) -> dict[str, str]:
    response = client.get(f"{base_url}/api/option/")
    response.raise_for_status()
    body = response.json()
    require_newapi_success(body, "read local billing settings")
    items = body.get("data")
    if not isinstance(items, list):
        raise RuntimeError("local gateway returned invalid billing settings")
    options = {
        item["key"]: str(item["value"])
        for item in items
        if item.get("key") in _OPTION_KEYS
    }
    if set(options) != set(_OPTION_KEYS):
        raise RuntimeError(
            "local gateway does not expose the required billing settings"
        )
    return options


def _billing_status(options: dict[str, str]) -> dict[str, Any]:
    ratios = json.loads(options["GroupRatio"])
    overrides = json.loads(options["GroupGroupRatio"])
    disabled = (
        ratios.get("default") == 0
        and all(values.get("default", 0) == 0 for values in overrides.values())
        and options["SelfUseModeEnabled"].lower() == "true"
        and options[_FREE_PRECONSUME].lower() == "false"
    )
    return {"disabled": disabled, "group": "default"}


def get_local_gateway_billing() -> dict[str, Any]:
    require_provisioner_enabled()
    cfg = get_provisioner_config()
    require_newapi_admin_service(cfg)
    admin = ensure_admin_access_token(cfg)
    with (
        _BILLING_LOCK,
        httpx.Client(timeout=15, headers=admin_headers(admin)) as client,
    ):
        return _billing_status(_read_options(client, cfg.admin_base_url))


def set_local_gateway_billing(*, disabled: bool) -> dict[str, Any]:
    require_provisioner_enabled()
    cfg = get_provisioner_config()
    require_newapi_admin_service(cfg)
    admin = ensure_admin_access_token(cfg)
    with (
        _BILLING_LOCK,
        httpx.Client(timeout=15, headers=admin_headers(admin)) as client,
    ):
        current = _read_options(client, cfg.admin_base_url)
        backup = get_local_billing_backup(cfg.admin_base_url)
        if disabled and _billing_status(current)["disabled"]:
            return _billing_status(current)
        if not disabled and not backup:
            if _billing_status(current)["disabled"]:
                raise ValueError(
                    "original local billing settings are unavailable; restore them in the gateway dashboard"
                )
            return _billing_status(current)

        ratios = json.loads(current["GroupRatio"])
        overrides = json.loads(current["GroupGroupRatio"])
        target = dict(current)
        if disabled:
            if not backup:
                # Save before writing to the gateway: retries after an interrupted
                # update must not replace the original settings with zero prices.
                save_local_billing_backup(cfg.admin_base_url, current)
            ratios["default"] = 0
            for values in overrides.values():
                if "default" in values:
                    values["default"] = 0
            target["SelfUseModeEnabled"] = "true"
            target[_FREE_PRECONSUME] = "false"
        else:
            original_ratios = json.loads(backup["GroupRatio"])
            if "default" in original_ratios:
                ratios["default"] = original_ratios["default"]
            else:
                ratios.pop("default", None)
            original_overrides = json.loads(backup["GroupGroupRatio"])
            for group, values in overrides.items():
                if "default" in original_overrides.get(group, {}):
                    values["default"] = original_overrides[group]["default"]
            target["SelfUseModeEnabled"] = backup["SelfUseModeEnabled"]
            target[_FREE_PRECONSUME] = backup[_FREE_PRECONSUME]
        target["GroupRatio"] = json.dumps(ratios)
        target["GroupGroupRatio"] = json.dumps(overrides)

        for key in _OPTION_KEYS:
            if target[key] == current[key]:
                continue
            response = client.put(
                f"{cfg.admin_base_url}/api/option/",
                json={"key": key, "value": target[key]},
            )
            response.raise_for_status()
            require_newapi_success(response.json(), "update local billing settings")

        actual = _read_options(client, cfg.admin_base_url)
        if any(
            actual[key] != target[key]
            for key in ("SelfUseModeEnabled", _FREE_PRECONSUME)
        ) or any(
            json.loads(actual[key]) != json.loads(target[key])
            for key in ("GroupRatio", "GroupGroupRatio")
        ):
            raise RuntimeError(
                "local gateway billing settings did not take effect; retry the operation"
            )
        if not disabled:
            save_local_billing_backup(cfg.admin_base_url, {})
        return _billing_status(actual)
