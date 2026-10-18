from __future__ import annotations

import io
import json
import wave
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
import respx
from fastapi import HTTPException

from novelvideo.audio import character_voice
from novelvideo.api.routes import characters
from novelvideo.api.schemas import (
    CharacterVoiceGenerateRequest,
    CharacterVoiceSavePreviewRequest,
    CharacterVoiceSourceRequest,
)
from novelvideo.models import NovelCharacter
from novelvideo.model_gateway_settings import EffectiveNewApiConfig
from novelvideo.project_config import load_project_config_file_from_state_dir


@pytest.fixture
def voice_models(monkeypatch):
    monkeypatch.setattr(character_voice, "uses_local_ce_runtime", lambda: True)
    monkeypatch.setattr(
        character_voice,
        "get_model_gateway_settings",
        lambda: {"model_gateway_mode": "custom"},
    )
    monkeypatch.setattr(
        character_voice,
        "get_newapi_provider_channels",
        lambda: [
            {"provider": "doubao_audio", "upstreamKey": "speech-provider-key"},
        ],
    )
    monkeypatch.setattr(
        character_voice,
        "get_newapi_media_model_mappings",
        lambda: {
            "index-tts-2": {
                "provider": "doubao_audio",
                "upstreamModel": "seed-audio-1.0",
                "mediaType": "audio",
                "label": "Seed Audio",
            },
            "disabled": {
                "provider": "doubao_audio",
                "upstreamModel": "seed-audio-1.0",
                "mediaType": "audio",
                "enabled": False,
            },
            "music": {
                "provider": "doubao_audio",
                "upstreamModel": "music-model",
                "mediaType": "audio",
            },
            "no-key": {
                "provider": "missing",
                "upstreamModel": "seed-audio-1.0",
                "mediaType": "audio",
            },
        },
    )
    monkeypatch.setattr(
        character_voice,
        "get_ce_newapi_config_for_mode",
        lambda mode: EffectiveNewApiConfig(
            mode="custom",
            source="custom",
            api_key="relay-secret",
            base_url="https://gateway.example/v1",
        ),
    )
    meter = SimpleNamespace(
        reserve_current_model_call_credit=AsyncMock(return_value="reservation"),
        refund_model_call_credit_reservation=AsyncMock(),
        bump_model_call=AsyncMock(),
    )
    monkeypatch.setattr(character_voice, "get_usage_meter", lambda: meter)
    return meter


@pytest.fixture
def project(monkeypatch, tmp_path):
    character = NovelCharacter(name="丁丁", voice_description="温暖的青年声音")
    store = SimpleNamespace(
        get_character=lambda name: character if name == character.name else None
    )

    async def update(name, **fields):
        for key, value in fields.items():
            setattr(character, key, value)

    store.update_character = update
    roles = []
    resolved = SimpleNamespace(
        project_dir=tmp_path,
        state_dir=tmp_path / "state",
        ctx=SimpleNamespace(project_id="project-1"),
    )

    async def resolve(project, user, required_role):
        roles.append(required_role)
        return resolved

    @asynccontextmanager
    async def scope(project, user, *, required_role="editor"):
        roles.append(required_role)
        yield resolved.ctx, "local", "demo", tmp_path, str(tmp_path), store

    monkeypatch.setattr(characters, "resolve_project_scope", resolve)
    monkeypatch.setattr(characters, "_character_project_scope", scope)
    return character, roles, resolved


def test_voice_sources_are_configured_and_capability_specific(
    voice_models, monkeypatch
):
    assert character_voice.character_voice_model_options() == {
        "index-tts-2": "Seed Audio"
    }
    monkeypatch.setattr(character_voice, "uses_local_ce_runtime", lambda: False)
    assert character_voice.character_voice_model_options() == {}


@pytest.mark.asyncio
async def test_project_voice_source_persists_under_resolved_project_state(
    voice_models, project
):
    _character, roles, resolved = project
    response = await characters.update_project_character_voice_selection(
        "project-1",
        CharacterVoiceSourceRequest(model="index-tts-2"),
        {"username": "local"},
    )
    assert response["data"]["model"] == "index-tts-2"
    assert (
        load_project_config_file_from_state_dir(resolved.state_dir)[
            "character_voice_model"
        ]
        == "index-tts-2"
    )
    assert roles == ["editor"]
    rejected = await characters.update_project_character_voice_selection(
        "project-1", CharacterVoiceSourceRequest(model="unknown"), {"username": "local"}
    )
    assert rejected.status_code == 400


def wave_sample():
    output = io.BytesIO()
    with wave.open(output, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(24000)
        audio.writeframes(b"\x00\x00" * 24000)
    return output.getvalue()


@pytest.mark.asyncio
@respx.mock
async def test_generate_preview_then_save_updates_existing_voice_contract(
    voice_models, project, tmp_path
):
    character, roles, _resolved = project
    old_path = tmp_path / "existing.mp3"
    old_path.write_bytes(b"existing voice")
    character.reference_audio_path = "existing.mp3"
    request = respx.post("https://gateway.example/v1/audio/speech").respond(
        200, content=wave_sample(), headers={"Content-Type": "audio/wav"}
    )
    preview = await characters.generate_character_voice_sample(
        "project-1",
        "丁丁",
        "default",
        CharacterVoiceGenerateRequest(text="你好", speaker="speaker-id"),
        {"username": "local"},
    )
    assert preview["ok"] is True
    assert preview["data"]["duration"] == 1
    assert preview["data"]["url"].startswith("/static/projects/project-1/")
    assert character.reference_audio_path == "existing.mp3"
    sent = json.loads(request.calls.last.request.content)
    assert sent["model"] == "index-tts-2"
    assert sent["voice"] == "speaker-id"
    assert "温暖的青年声音" in sent["input"]
    assert "参考@音频1的音色" in sent["input"]
    assert "audio_url" not in sent["metadata"]
    saved = await characters.save_generated_character_voice_sample(
        "project-1",
        "丁丁",
        "default",
        CharacterVoiceSavePreviewRequest(preview_id=preview["data"]["preview_id"]),
        {"username": "local"},
    )
    assert saved["ok"] is True
    assert saved["data"]["slot"] == "default"
    assert (tmp_path / saved["data"]["path"]).read_bytes() == wave_sample()
    assert character.reference_audio_path == saved["data"]["path"]
    assert character.reference_audio_sha256
    assert roles.count("editor") == 2
    voice_models.bump_model_call.assert_awaited_once()


@pytest.mark.asyncio
@respx.mock
async def test_voice_timbre_prompt_reaches_gateway_with_speech_only_constraints(
    voice_models, project
):
    character, _roles, _resolved = project
    prompt = "机械合成音，音调偏高，带有清脆的电子质感，语速轻快急促，断句简短，偶尔带机械提示音"
    character.voice_description = prompt
    request = respx.post("https://gateway.example/v1/audio/speech").respond(
        200,
        content=wave_sample(),
        headers={"Content-Type": "audio/wav"},
    )
    response = await characters.generate_character_voice_sample(
        "project-1",
        "丁丁",
        "default",
        CharacterVoiceGenerateRequest(text="你好，准备出发！"),
        {"username": "local"},
    )
    assert response["ok"] is True
    sent = json.loads(request.calls.last.request.content)
    assert prompt in sent["input"]
    assert "纯人声" in sent["input"]
    assert "不要背景音乐或音效" in sent["input"]
    assert "机械或电子质感通过声线与咬字表现" in sent["input"]
    assert "说：“你好，准备出发！”" in sent["input"]
    assert "约 8 秒" not in sent["input"]
    assert "@音频" not in sent["input"]
    assert sent["metadata"]["audio_config"] == {
        "sample_rate": 48000,
        "speech_rate": 0,
        "pitch_rate": 0,
        "loudness_rate": 0,
    }
    assert "voice" not in sent
    assert request.call_count == 1


@pytest.mark.asyncio
@respx.mock
async def test_preview_history_survives_new_reads_and_retains_generation_metadata(
    voice_models,
    project,
    tmp_path,
):
    character, roles, _resolved = project
    respx.post("https://gateway.example/v1/audio/speech").respond(
        200,
        content=wave_sample(),
        headers={"Content-Type": "audio/wav"},
    )
    ids = []
    for text in ("第一条台词", "第二条台词"):
        response = await characters.generate_character_voice_sample(
            "project-1",
            "丁丁",
            "default",
            CharacterVoiceGenerateRequest(text=text),
            {"username": "local"},
        )
        assert response["ok"] is True
        ids.append(response["data"]["preview_id"])
    for _ in range(2):
        history = await characters.list_generated_character_voice_samples(
            "project-1",
            "丁丁",
            "default",
            {"username": "local"},
        )
        previews = history["data"]
        assert [item["preview_id"] for item in previews] == list(reversed(ids))
        assert [item["text"] for item in previews] == ["第二条台词", "第一条台词"]
        assert all(item["duration"] == 1 and item["created_at"] for item in previews)
        assert all(
            item["model"] == "index-tts-2" and item["sha256"] for item in previews
        )
        assert all(
            "path" not in item and item["url"].startswith("/static/")
            for item in previews
        )
    assert roles[-1] == "viewer"
    assert not character.reference_audio_path
    # Saving an earlier take must not remove either audition.
    saved = await characters.save_generated_character_voice_sample(
        "project-1",
        "丁丁",
        "default",
        CharacterVoiceSavePreviewRequest(preview_id=ids[0]),
        {"username": "local"},
    )
    assert saved["ok"] is True
    assert (
        len(character_voice.list_character_voice_previews(tmp_path, "丁丁", "default"))
        == 2
    )


def test_history_recovers_legacy_audio_and_ignores_other_slots_or_invalid_files(
    tmp_path,
):
    token = "a" * 32
    path = character_voice.character_voice_preview_path(
        tmp_path, "丁丁", "default", token
    )
    path.parent.mkdir(parents=True)
    path.write_bytes(wave_sample())
    # Broken/absent sidecars must not hide already generated audio.
    path.with_suffix(".json").write_text("{broken", encoding="utf-8")
    (path.parent / "default-invalid.mp3").write_bytes(wave_sample())
    (path.parent / f"child-{'b' * 32}.mp3").write_bytes(wave_sample())
    (path.parent / f"default-{'c' * 32}.mp3").write_bytes(b"corrupt audio")
    previews = character_voice.list_character_voice_previews(
        tmp_path, "丁丁", "default"
    )
    assert [item["preview_id"] for item in previews] == [token]
    assert previews[0]["duration"] == 1
    assert previews[0]["text"] == ""
    assert (
        character_voice.list_character_voice_previews(tmp_path, "皮皮", "default") == []
    )
    with pytest.raises(ValueError):
        character_voice.list_character_voice_previews(tmp_path, "丁丁", "../default")


@pytest.mark.asyncio
async def test_history_validates_character_and_slot(project):
    for name, slot, status in (("missing", "default", 404), ("丁丁", "invalid", 400)):
        response = await characters.list_generated_character_voice_samples(
            "project-1",
            name,
            slot,
            {"username": "local"},
        )
        assert response.status_code == status


@pytest.mark.asyncio
@respx.mock
async def test_provider_failure_is_not_retried_and_leaves_voice_untouched(
    voice_models, project
):
    character, _roles, _resolved = project
    route = respx.post("https://gateway.example/v1/audio/speech").mock(
        side_effect=httpx.ReadTimeout("contains relay-secret")
    )
    response = await characters.generate_character_voice_sample(
        "project-1",
        "丁丁",
        "default",
        CharacterVoiceGenerateRequest(text="你好"),
        {"username": "local"},
    )
    assert response.status_code == 502
    assert route.call_count == 1
    assert b"relay-secret" not in response.body
    assert not character.reference_audio_path
    voice_models.refund_model_call_credit_reservation.assert_awaited_once()


@pytest.mark.asyncio
async def test_empty_character_voice_prompt_blocks_generation_before_billing(
    voice_models, project
):
    character, _roles, _resolved = project
    character.voice_description = "  "
    response = await characters.generate_character_voice_sample(
        "project-1",
        "丁丁",
        "default",
        CharacterVoiceGenerateRequest(text="你好"),
        {"username": "local"},
    )
    assert response.status_code == 400
    assert json.loads(response.body)["code"] == "character_voice_prompt_required"
    voice_models.reserve_current_model_call_credit.assert_not_awaited()


@pytest.mark.asyncio
async def test_preview_save_is_scoped_to_character_and_slot(
    voice_models, project, tmp_path
):
    token = "a" * 32
    path = character_voice.character_voice_preview_path(
        tmp_path, "丁丁", "default", token
    )
    path.parent.mkdir(parents=True)
    path.write_bytes(b"preview")
    response = await characters.save_generated_character_voice_sample(
        "project-1",
        "丁丁",
        "child",
        CharacterVoiceSavePreviewRequest(preview_id=token),
        {"username": "local"},
    )
    assert response.status_code == 400
    with pytest.raises(ValueError):
        character_voice.character_voice_preview_path(
            tmp_path, "丁丁", "default", "../outside"
        )


@pytest.mark.asyncio
async def test_voice_source_requires_project_permission(voice_models, monkeypatch):
    async def denied(*args, **kwargs):
        raise HTTPException(status_code=403)

    monkeypatch.setattr(characters, "resolve_project_scope", denied)
    with pytest.raises(HTTPException) as exc:
        await characters.update_project_character_voice_selection(
            "project-1",
            CharacterVoiceSourceRequest(model="index-tts-2"),
            {"username": "viewer"},
        )
    assert exc.value.status_code == 403
