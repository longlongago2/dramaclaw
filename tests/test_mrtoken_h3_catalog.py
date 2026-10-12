from __future__ import annotations

import json
from pathlib import Path

import pytest

from novelvideo.media_model_request_schema import validate_media_model_catalog_config
from novelvideo.video_duration import (
    normalize_video_duration_for_backend,
    video_duration_bounds_for_backend,
)


CATALOG_PATH = Path(__file__).resolve().parents[1] / "examples/mrtoken-h3-media-models.json"
CATALOG = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))["models"]


@pytest.mark.parametrize("name, model", CATALOG.items())
def test_h3_catalog_preserves_platform_id_and_duration_contract(name, model, monkeypatch):
    from novelvideo import config
    from novelvideo.generators.video_generator import NewApiVideoGenerator

    monkeypatch.setattr(config, "NEWAPI_VIDEO_DURATION_BOUNDS", "")
    assert model["provider"] == "mrtoken"
    assert model["upstreamModel"] == name
    validate_media_model_catalog_config(model["config"], "video")
    backend = f"newapi_{name}"
    assert video_duration_bounds_for_backend(backend) == (1, 30)
    assert normalize_video_duration_for_backend(backend, 1) == 1
    assert normalize_video_duration_for_backend(backend, 30) == 30
    generator = NewApiVideoGenerator(
        api_key="test-gateway-key", endpoint="http://localhost:3000/v1", model=name
    )
    assert generator._duration_bounds() == (1, 30)


def test_h3_reference_modes_match_platform_schema():
    assert CATALOG["minimax-h3-t2v"]["config"]["supportedModes"] == ["text_to_video"]
    assert CATALOG["minimax-h3-r2v"]["config"]["referenceImageMax"] == 4
    assert "text_to_video" not in CATALOG["minimax-h3-max-i2v"]["config"]["supportedModes"]
    assert "first_last_frame" in CATALOG["minimax-h3-i2v"]["config"]["supportedModes"]


def test_h3_r2v_local_default_resolves_to_provider_dimensions():
    from novelvideo.generators.video_generator import NewApiVideoGenerator

    model = CATALOG["minimax-h3-r2v"]["config"]
    assert model["supportedModes"] == ["image_reference"]
    assert model["resolutionOptions"][0] == "720p"
    assert model["ratioOptions"][0] == "16:9"
    width, height = NewApiVideoGenerator._video_dimensions("720p", "16:9")
    assert ((width + 31) // 32 * 32, (height + 31) // 32 * 32) == (1280, 736)
