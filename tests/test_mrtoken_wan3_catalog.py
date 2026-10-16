import json
from pathlib import Path

import pytest

from novelvideo.generators.video_generator import NewApiVideoGenerator
from novelvideo.media_model_request_schema import validate_media_model_catalog_config
from novelvideo.video_duration import normalize_video_duration_for_backend


CATALOG = json.loads(
    (Path(__file__).resolve().parents[1] / "examples/mrtoken-wan3-media-models.json")
    .read_text(encoding="utf-8")
)["models"]


@pytest.mark.parametrize("name, model", CATALOG.items())
def test_wan3_catalog_and_backend_duration(name, model, monkeypatch):
    from novelvideo import config

    monkeypatch.setattr(config, "NEWAPI_VIDEO_DURATION_BOUNDS", "")
    assert model["provider"] == "mrtoken"
    assert model["upstreamModel"] == name
    validate_media_model_catalog_config(model["config"], "video")
    assert normalize_video_duration_for_backend(f"newapi_{name}", 1) == 2
    assert normalize_video_duration_for_backend(f"newapi_{name}", 31) == 30
    generator = NewApiVideoGenerator(
        api_key="test-gateway-key", endpoint="http://localhost:3000/v1", model=name
    )
    assert generator._duration_bounds() == (2, 30)
    assert model["config"]["supportedModes"] == [
        "text_to_video", "first_frame", "first_last_frame", "image_reference"
    ]
    assert model["config"]["referenceVideoMax"] == 0
