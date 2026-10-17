"""Gender settings must reach downstream prompts without a binary fallback."""

from types import SimpleNamespace

import pytest

from novelvideo.generators.prompt_builder import (
    CharacterConfig,
    GridConfig,
    PromptComponents,
    PromptContext,
    PromptMode,
    StyleConfig,
)


@pytest.mark.parametrize("gender, marker", [
    ("agender", "AGENDER"), ("non_binary", "NON-BINARY"),
    ("雌", "FEMALE"), ("雄", "MALE"),
])
def test_render_and_motion_prompts_keep_extended_gender(gender, marker):
    from novelvideo.agents.global_video_optimizer import _format_color_mapping_descriptor

    context = PromptContext(
        grid=GridConfig(rows=1, cols=1),
        characters={"Robot": CharacterConfig(
            name="Robot", gender=gender, face_prompt="round metal head", sketch_color="#00FFFF CYAN",
        )},
        style=StyleConfig(style_keywords="test style", style_family="realism", character_representation="standard"),
        beats=[], mode=PromptMode.RENDER,
    )
    prompt = PromptComponents.build_color_identification_map(context, ["Robot"])
    assert marker in prompt
    descriptor = _format_color_mapping_descriptor({"gender": gender, "appearance": "round metal head"})
    assert descriptor.startswith(marker.lower().replace("-", "_"))


@pytest.mark.parametrize("gender", ["agender", "non_binary", "无性别", "非二元"])
def test_legacy_voice_presets_do_not_assume_male_for_nonbinary_settings(monkeypatch, gender):
    from novelvideo.config import get_fish_voice_id

    monkeypatch.setattr("novelvideo.config.FISH_VOICE_PRESETS", {
        "youth_male": "male-voice", "youth_female": "female-voice",
    })
    assert get_fish_voice_id("youth", gender) == ""


def test_system_voice_fallback_uses_the_full_pool_for_nonbinary_settings(monkeypatch):
    from novelvideo.audio import system_voice_setup

    monkeypatch.setattr(system_voice_setup, "FEMALE_VOICES", ("voice-one",))
    monkeypatch.setattr(system_voice_setup, "MALE_VOICES", ("voice-two",))
    for gender in ("agender", "non_binary"):
        voices = {system_voice_setup._system_voice_for_character(
            SimpleNamespace(name=name, gender=gender, age_group="youth"),
        ) for name in ("A", "B")}
        assert voices == {"voice-one", "voice-two"}
