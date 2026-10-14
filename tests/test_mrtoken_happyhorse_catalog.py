import json
from pathlib import Path

import pytest

from novelvideo.generators.video_generator import NewApiVideoGenerator
from novelvideo.media_model_request_schema import validate_media_model_catalog_config
from novelvideo.video_duration import normalize_video_duration_for_backend

CATALOG = json.loads(
    (Path(__file__).resolve().parents[1] / "examples/mrtoken-happyhorse-media-models.json")
    .read_text(encoding="utf-8")
)["models"]


@pytest.mark.parametrize("name, model", CATALOG.items())
def test_happyhorse_catalog_preserves_mode_and_request_duration(name, model, monkeypatch):
    from novelvideo import config

    monkeypatch.setattr(config, "NEWAPI_VIDEO_DURATION_BOUNDS", "")
    validate_media_model_catalog_config(model["config"], "video")
    assert model["upstreamModel"] == name
    assert model["provider"] == "mrtoken"
    backend = f"newapi_{name}"
    assert normalize_video_duration_for_backend(backend, 1) == 3
    assert normalize_video_duration_for_backend(backend, 15) == 15
    assert normalize_video_duration_for_backend(backend, 16) == 15
    generator = NewApiVideoGenerator(
        api_key="test-gateway-key", endpoint="http://localhost:3000/v1", model=name
    )
    assert generator._duration_bounds() == (3, 15)
    assert model["config"]["supportedModes"] == {
        "t2v": ["text_to_video"],
        "i2v": ["first_frame", "image_to_video"],
        "r2v": ["image_reference"],
    }[name.rsplit("-", 1)[1]]
