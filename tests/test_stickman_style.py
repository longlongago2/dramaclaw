"""Stick-figure contracts across presets, characters, storyboard and video requests."""

import json
from types import SimpleNamespace

import pytest
from PIL import Image

from novelvideo.models import StyleConfig
from novelvideo.services.style_service import StyleService
from novelvideo.styles.stickman import VIDEO_RULE


def test_preset_round_trip_and_backend_preview():
    preset = StyleService.get_preset("stickman")
    assert preset.character_representation == "stick_figure"
    assert (preset.style_family, preset.animation_subtype) == ("animation", "2d")
    restored = StyleConfig.from_legacy_dict("stickman", preset.to_legacy_dict())
    assert restored.character_representation == "stick_figure"
    assert StyleConfig(id="old", name="Old").character_representation == "standard"
    with Image.open(StyleService.PRESETS_DIR / "stickman.png") as preview:
        assert preview.format == "PNG"


def test_custom_style_inherits_representation_through_save_and_reload(tmp_path):
    style = StyleConfig(id="my_lines", name="My Lines", base="stickman", style_instructions="sparse lines")
    assert StyleService.save_custom_style("my_lines", style, state_dir=tmp_path)
    loaded = StyleService.get_style("my_lines", state_dir=tmp_path)
    assert loaded.character_representation == "stick_figure"
    assert loaded.style_family == "animation"
    assert loaded.animation_subtype == "2d"
    assert loaded.to_legacy_dict()["character_representation"] == "stick_figure"
    assert StyleService.get_character_representation("missing", state_dir=tmp_path) == "standard"


def test_existing_custom_style_with_base_resolves_metadata_in_list(tmp_path):
    (tmp_path / "project_config.json").write_text(json.dumps({"custom_styles": {
        "old_lines": {"id": "old_lines", "name": "Lines", "base": "stickman"},
    }}), encoding="utf-8")
    listed = StyleService.list_all_styles(state_dir=tmp_path)
    assert next(item for item in listed if item["id"] == "old_lines")["character_representation"] == "stick_figure"


@pytest.mark.parametrize("sheet", [False, True])
def test_character_portrait_and_sheet_replace_face_fidelity(sheet):
    from novelvideo.generators.nanobanana_character import NanoBananaCharacterGenerator

    generator = object.__new__(NanoBananaCharacterGenerator)
    kwargs = dict(
        character_name="Lin", character_tag="Lin_1", character_prompt="older courier with a cap",
        style_name="stickman", project_dir="", style_keywords="black line on white", negative_keywords="",
    )
    prompt = (
        generator._build_identity_locked_prompt(**kwargs, target_view="front", has_costume_reference=True)
        if sheet else generator._build_character_prompt(**kwargs)
    )
    assert "hollow circular head" in prompt
    assert "older courier with a cap" in prompt
    assert "bone structure" not in prompt
    assert "Face fills 60-70%" not in prompt
    assert "Four panels" in prompt if sheet else "One front-facing" in prompt


@pytest.mark.asyncio
async def test_composite_reference_sends_stick_figure_prompt(tmp_path, monkeypatch):
    from novelvideo.generators.nanobanana_character import NanoBananaCharacterGenerator

    generator = object.__new__(NanoBananaCharacterGenerator)
    generator.provider = "newapi"
    calls = []

    async def generate(**kwargs):
        calls.append(kwargs)
        return b"fake-image"

    monkeypatch.setattr(generator, "_generate_single_image", generate)
    result = await generator.generate_composite_reference(
        "Lin", "courier with a cap", character_tag="Lin_1", style="stickman",
        output_dir=str(tmp_path / "assets"), project_dir=str(tmp_path),
    )
    assert result.success, result.error
    assert "Two equal side-by-side panels" in calls[0]["prompt"]
    assert "skin texture\n- Well-lit" not in calls[0]["prompt"]


@pytest.mark.parametrize("aspect_ratio", ["16:9", "9:16"])
def test_render_preserves_geometry_and_two_character_identity_without_humanization(aspect_ratio):
    from novelvideo.generators.prompt_builder import (
        CharacterConfig, GridConfig, PromptContext, PromptMode,
        StyleConfig as RuntimeStyle, UnifiedPromptBuilder,
    )
    from novelvideo.utils.asset_resolver import ResolvedAssetRef

    ctx = PromptContext(
        grid=GridConfig(rows=1, cols=1, aspect_ratio=aspect_ratio),
        style=RuntimeStyle(style_name="stickman"), mode=PromptMode.RENDER,
        characters={
            "Lin": CharacterConfig(name="Lin", reference_mode="composite", reference_path="lin.png", sketch_color="#ff00ff MAGENTA"),
            "Bo": CharacterConfig(name="Bo", reference_mode="portrait_only", reference_path="bo.png", sketch_color="#00ffff CYAN"),
        },
        beats=[{
            "beat_number": 1, "detected_identities": ["Lin", "Bo"], "detected_props": ["parcel"],
            "scene_ref": {"scene_id": "street"}, "time_of_day": "night",
            "visual_description": "Lin waves to Bo beside a parcel.",
        }],
        scene_refs={1: [ResolvedAssetRef(
            asset_type="scene", base_id="street", variant_id=None, image_paths=["street.png"],
            text_description="street", source_level="base_image", time_baked=True,
        )]},
        prop_asset_refs={1: [ResolvedAssetRef(
            asset_type="prop", base_id="parcel", variant_id=None, image_paths=["parcel.png"],
            text_description="a parcel", source_level="base_image",
        )]},
        prop_marker_colors={"parcel": "#ffff00 YELLOW"},
    )
    prompt = UnifiedPromptBuilder(ctx).build()
    assert "black-line-on-white" in prompt
    assert "MAGENTA" in prompt and "CYAN" in prompt
    assert "Image 1 = SKETCH" in prompt
    assert "Image 2 =" in prompt and "Image 3 =" in prompt
    assert "Scene street" in prompt and "Prop parcel" in prompt
    assert "crop, poses, and camera angles exactly" in prompt
    assert "normalize crude stick-figure anatomy" not in prompt
    assert "must use natural human skin tone" not in prompt
    assert "IDENTICAL facial geometry" not in prompt
    assert "COPY facial features EXACTLY" not in prompt
    assert "as if photographed" not in prompt
    assert "preserve the anchor lighting" not in prompt


def test_project_video_style_reads_scoped_config(tmp_path):
    from novelvideo.task_backend.runners.video import _apply_project_video_style

    (tmp_path / "project_config.json").write_text(json.dumps({"visual_style": "stickman"}), encoding="utf-8")
    ctx = SimpleNamespace(state_dir=tmp_path, output_dir=tmp_path / "output")
    prompt = _apply_project_video_style("Lin waves", ctx)
    assert "Lin waves" in prompt and VIDEO_RULE in prompt
    assert _apply_project_video_style(prompt, ctx).count(VIDEO_RULE) == 1
    (tmp_path / "project_config.json").write_text(json.dumps({"visual_style": "anime"}), encoding="utf-8")
    assert _apply_project_video_style("Lin waves", ctx) == "Lin waves"
