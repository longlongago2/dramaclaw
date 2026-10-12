from __future__ import annotations

import json
from pathlib import Path

import pytest

from novelvideo.freezone.video_node import (
    is_freezone_seedance2_backend,
    is_freezone_seedance_backend,
)
from novelvideo.media_model_request_schema import validate_media_model_catalog_config
from novelvideo.video_duration import video_duration_bounds_for_backend


CATALOG = json.loads(
    (Path(__file__).resolve().parents[1] / "examples/mrtoken-seedance2-media-models.json")
    .read_text(encoding="utf-8")
)["models"]


@pytest.mark.parametrize("name, model", CATALOG.items())
def test_mrtoken_seedance_catalog_preserves_protocol_and_limits(name, model, monkeypatch):
    from novelvideo import config
    from novelvideo.generators.video_generator import NewApiVideoGenerator

    monkeypatch.setattr(config, "NEWAPI_VIDEO_DURATION_BOUNDS", "")
    assert model["provider"] == "mrtoken"
    assert model["upstreamModel"] == name
    capabilities = model["config"]
    validate_media_model_catalog_config(capabilities, "video")
    assert (capabilities["minDuration"], capabilities["maxDuration"]) == (4, 15)
    assert video_duration_bounds_for_backend(f"newapi_{name}") == (4, 15)
    assert is_freezone_seedance2_backend(f"newapi_{name}")
    assert is_freezone_seedance_backend(f"newapi_{name}")
    assert capabilities["referenceImageMax"] == 9
    assert capabilities["referenceVideoMax"] == 3
    assert capabilities["referenceAudioMax"] == 3
    assert "all_reference" in capabilities["supportedModes"]
    generator = NewApiVideoGenerator(api_key="test-key", endpoint="http://localhost:3000/v1", model=name)
    assert generator._duration_bounds() == (4, 15)
    # MrToken uses the canonical DC-Media converter, never the HuiMeng format.
    assert not generator._is_seedance2_model()


def test_fast_and_mini_catalog_do_not_advertise_1080p():
    for name in ("doubao-seedance-2.0-fast", "doubao-seedance-2.0-mini"):
        assert CATALOG[name]["config"]["resolutionOptions"] == ["480p", "720p"]
