import json
import sys
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from novelvideo.services.style_service import StyleService
from novelvideo.styles.runtime import capture_project_style, style_snapshot_scope
from novelvideo.styles.stickman import RULES_VERSION, theme_rules


def project_config(tmp_path, theme):
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "project_config.json").write_text(
        json.dumps({"visual_style": "stickman", "visual_style_theme": theme}), encoding="utf-8",
    )


@pytest.mark.parametrize("theme", [None, "classic", "modern", "prehistoric", "1a", "1b", "2a", "2b", "3"])
def test_project_theme_is_resolved_without_mutating_shared_preset(tmp_path, theme):
    project_config(tmp_path, theme)
    resolved = StyleService.get_style("stickman", state_dir=tmp_path)
    assert resolved.style_theme == theme
    assert StyleService.get_preset("stickman").style_theme is None
    assert "flat pure white background" in StyleService.get_preset("stickman").style_instructions
    if theme in {"modern", "prehistoric"}:
        assert "flat pure white background" not in resolved.style_instructions
        assert "cinematic shading" not in resolved.avoid_instructions
        assert "paper texture" not in resolved.avoid_instructions


@pytest.mark.parametrize("theme", ["classic", "modern", "prehistoric", "1a", "1b", "2a", "2b", "3"])
def test_theme_reaches_character_storyboard_and_video(tmp_path, theme):
    from novelvideo.generators.nanobanana_character import NanoBananaCharacterGenerator
    from novelvideo.generators.prompt_builder import GridConfig, PromptContext, PromptMode, StyleConfig, UnifiedPromptBuilder
    from novelvideo.task_backend.runners.video import _apply_project_video_style

    project_config(tmp_path, theme)
    snapshot = capture_project_style(SimpleNamespace(state_dir=tmp_path, output_dir=tmp_path))
    with style_snapshot_scope(snapshot):
        generator = object.__new__(NanoBananaCharacterGenerator)
        style = StyleService.get_style("stickman", state_dir=tmp_path)
        portrait = generator._build_character_prompt(
            character_name="Lin", character_prompt="a courier with a cap", character_tag="lin",
            style_name="stickman", project_dir=str(tmp_path), state_dir=str(tmp_path),
            style_keywords=style.style_instructions, negative_keywords=style.avoid_instructions,
        )
        ctx = PromptContext(
            grid=GridConfig(rows=1, cols=1), characters={}, mode=PromptMode.RENDER,
            style=StyleConfig(style_name="stickman"), beats=[{"beat_number": 1}],
        )
        storyboard = UnifiedPromptBuilder(ctx).build()
        video = _apply_project_video_style("Lin waves", SimpleNamespace(state_dir=tmp_path, output_dir=tmp_path))
    rules = theme_rules(theme)
    assert rules.identity in portrait
    assert rules.render in storyboard
    assert rules.video in video
    if theme not in {"classic", "1a", "1b"}:
        assert "keep the canvas white and unshaded" not in storyboard
        assert "hollow circular head" not in portrait
        assert "natural adult human anatomy" not in storyboard


def test_dark_and_tech_variants_have_distinct_rules():
    dark = theme_rules("1b")
    assert "pitch-black canvas" in dark.render
    assert "clean white" in dark.render
    assert "Flat pure white canvas" not in dark.render
    assert "white backgrounds" not in dark.video
    tech = theme_rules("2a")
    assert "high-key studio" in tech.render
    assert "cyan" in tech.render
    assert "circuit-board" in tech.avoid
    assert "full-color story environments" not in tech.render
    assert "full-color story environments" in theme_rules("2b").render


def test_queued_snapshot_and_subprocess_keep_submitted_theme_after_project_changes(tmp_path):
    from novelvideo.task_backend.subprocesses import run_project_subprocess

    project_config(tmp_path, "modern")
    ctx = SimpleNamespace(state_dir=tmp_path, output_dir=tmp_path)
    submitted = capture_project_style(ctx)
    assert submitted["rules_version"] == RULES_VERSION
    project_config(tmp_path, "prehistoric")
    with style_snapshot_scope(submitted):
        assert StyleService.get_style("stickman", state_dir=tmp_path).style_theme == "modern"
        (tmp_path / "project_config.json").write_text('{"visual_style":"anime"}', encoding="utf-8")
        assert capture_project_style(ctx)["style_theme"] == "modern"
        from novelvideo.task_backend.runners.video import _apply_project_video_style

        assert theme_rules("modern").video in _apply_project_video_style("wave", ctx)
        completed = run_project_subprocess(
            [sys.executable, "-c", "from novelvideo.services.style_service import StyleService; print(StyleService.get_style('stickman').style_theme)"],
            capture_output=True, text=True, timeout=30,
        )
        assert completed.returncode == 0, completed.stderr
        assert completed.stdout.strip() == "modern"
    project_config(tmp_path, "prehistoric")
    assert StyleService.get_style("stickman", state_dir=tmp_path).style_theme == "prehistoric"






@pytest.fixture
def project_client(tmp_path, monkeypatch):
    from novelvideo.api.routes import projects
    from novelvideo.project_config import load_project_config_file_from_state_dir

    project_config(tmp_path, "modern")
    ctx = SimpleNamespace(state_dir=tmp_path, output_dir=tmp_path / "output", owner_username="alice", project_name="demo", is_home_node=True)

    async def resolve(**kwargs):
        return ctx

    monkeypatch.setattr(projects, "resolve_project_context", resolve)
    monkeypatch.setattr(projects, "require_project_home_node", lambda *a, **kw: None)
    monkeypatch.setattr(projects, "load_project_config_from_state_dir", lambda state, **kw: load_project_config_file_from_state_dir(state))
    monkeypatch.setattr(StyleService, "get_style_labels", classmethod(lambda cls, **kw: {"stickman": "Stick Figure", "anime": "Anime"}))
    app = FastAPI()
    app.include_router(projects.router)
    app.dependency_overrides[projects.get_api_user] = lambda: {"username": "alice"}
    return TestClient(app)


def test_project_theme_patch_can_set_clear_or_omit(project_client):
    assert project_client.patch("/projects/demo", json={"visual_style_theme": "prehistoric"}).json()["data"]["visual_style_theme"] == "prehistoric"
    assert project_client.patch("/projects/demo", json={"visual_style": "stickman"}).json()["data"]["visual_style_theme"] == "prehistoric"
    assert project_client.patch("/projects/demo", json={"visual_style_theme": None}).json()["data"]["visual_style_theme"] is None
    assert project_client.patch("/projects/demo", json={"visual_style_theme": "unknown"}).status_code == 422
    for variant in ["1a", "1b", "2a", "2b", "3"]:
        response = project_client.patch("/projects/demo", json={"visual_style_theme": variant})
        assert response.status_code == 200
        assert response.json()["data"]["visual_style_theme"] == variant


def test_switching_to_other_preset_clears_theme_and_rejects_explicit_theme(project_client):
    response = project_client.patch("/projects/demo", json={"visual_style": "anime"})
    assert response.status_code == 200
    assert response.json()["data"]["visual_style_theme"] is None
    assert project_client.patch("/projects/demo", json={"visual_style": "anime", "visual_style_theme": "modern"}).status_code == 400
