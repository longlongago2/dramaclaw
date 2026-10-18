"""Configured CE video capabilities shared by the mainline selector and dispatcher."""

from typing import Any


def configured_video_catalog() -> dict[str, dict[str, Any]]:
    from novelvideo.shared.runtime_env import is_ce_effective

    if not is_ce_effective():
        return {}
    from novelvideo.model_gateway_settings import (
        MODE_CUSTOM,
        MODE_HYBRID,
        get_ce_media_model_catalog,
        get_model_gateway_settings,
    )

    if get_model_gateway_settings().get("model_gateway_mode") not in {
        MODE_CUSTOM,
        MODE_HYBRID,
    }:
        return {}
    return {item["apiModel"]: item for item in get_ce_media_model_catalog("video")}
