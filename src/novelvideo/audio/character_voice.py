"""Generate audition files from configured CE audio models before saving a voice slot."""

from __future__ import annotations

import base64
import hashlib
import json
import math
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from novelvideo.model_gateway_settings import (
    MODE_CUSTOM,
    MODE_HYBRID,
    get_ce_newapi_config_for_mode,
    get_model_gateway_settings,
    get_newapi_media_model_mappings,
    get_newapi_provider_channels,
)
from novelvideo.ports import get_usage_meter
from novelvideo.seedance2_i2v.character_voice_storage import (
    character_voice_path,
    persist_character_voice_file,
    probe_voice_sample_duration_seconds,
    run_voice_media_operation,
)
from novelvideo.shared.runtime_env import uses_local_ce_runtime
from novelvideo.utils.state_index_files import write_json_atomic

MAX_PREVIEW_BYTES = 10 * 1024 * 1024


def character_voice_model_options() -> dict[str, str]:
    """Only advertise configured models that support speech without a reference file."""
    if not uses_local_ce_runtime():
        return {}
    if get_model_gateway_settings().get("model_gateway_mode") not in {
        MODE_CUSTOM,
        MODE_HYBRID,
    }:
        return {}
    configured = {
        item["provider"]
        for item in get_newapi_provider_channels()
        if item.get("upstreamKey")
    }
    return dict(
        sorted(
            (
                (model, str(item.get("label") or model))
                for model, item in get_newapi_media_model_mappings().items()
                if item.get("mediaType") == "audio"
                and item.get("enabled") is not False
                and item.get("provider") in configured
                and item.get("provider") in {"doubao_audio", "volcengine"}
                and str(item.get("upstreamModel") or model) == "seed-audio-1.0"
            ),
            key=lambda item: item[1].casefold(),
        )
    )


def character_voice_preview_path(
    project_dir: Path, name: str, slot: str, preview_id: str
) -> Path:
    canonical_id = uuid.UUID(preview_id).hex
    if canonical_id != preview_id:
        raise ValueError("Invalid voice preview ID")
    voice_path = character_voice_path(
        project_dir=project_dir, character_name=name, slot=slot, filename="voice.mp3"
    )
    target = voice_path.parent / "previews" / f"{slot}-{canonical_id}.mp3"
    if not target.resolve().is_relative_to(project_dir.resolve()):
        raise ValueError("Invalid voice preview path")
    return target


def _store_voice_preview(path: Path, content: bytes, metadata: dict[str, Any]) -> float:
    if not content or len(content) > MAX_PREVIEW_BYTES:
        raise ValueError("Voice preview must be a non-empty audio file under 10 MB")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    try:
        duration = probe_voice_sample_duration_seconds(path)
        if not math.isfinite(duration) or not 0 < duration <= 30:
            raise ValueError("Voice preview must be at most 30 seconds")
    except Exception:
        path.unlink(missing_ok=True)
        raise
    write_json_atomic(
        path.with_suffix(".json"),
        {
            **metadata,
            "duration": duration,
            "sha256": hashlib.sha256(content).hexdigest(),
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    return duration


def read_character_voice_preview(
    project_dir: Path, name: str, slot: str, preview_id: str
) -> dict[str, Any]:
    """Read durable preview metadata, including audio generated before sidecars existed."""
    path = character_voice_preview_path(project_dir, name, slot, preview_id)
    stat = path.stat()
    if not path.is_file() or not 0 < stat.st_size <= MAX_PREVIEW_BYTES:
        raise ValueError("Invalid voice preview file")
    metadata_path = path.with_suffix(".json")
    metadata: dict[str, Any] = {}
    if metadata_path.resolve().is_relative_to(project_dir.resolve()):
        try:
            payload = json.loads(metadata_path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                metadata = payload
        except (OSError, ValueError):
            pass
    duration = metadata.get("duration")
    if (
        not isinstance(duration, (int, float))
        or not math.isfinite(duration)
        or not 0 < duration <= 30
    ):
        duration = probe_voice_sample_duration_seconds(path)
    if not math.isfinite(duration) or not 0 < duration <= 30:
        raise ValueError("Invalid voice preview duration")
    try:
        created_at = datetime.fromisoformat(metadata.get("created_at", ""))
        if created_at.tzinfo is None:
            raise ValueError("Preview timestamp has no timezone")
    except (TypeError, ValueError):
        created_at = datetime.fromtimestamp(stat.st_mtime, timezone.utc)
    return {
        "preview_id": preview_id,
        "path": path,
        "duration": duration,
        "created_at": created_at.astimezone(timezone.utc).isoformat(),
        "model": str(metadata.get("model") or ""),
        "text": str(metadata.get("text") or ""),
        "speaker": str(metadata.get("speaker") or ""),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def list_character_voice_previews(
    project_dir: Path, name: str, slot: str
) -> list[dict[str, Any]]:
    directory = character_voice_preview_path(project_dir, name, slot, "0" * 32).parent
    previews = []
    for path in directory.glob(f"{slot}-*.mp3"):
        try:
            previews.append(
                read_character_voice_preview(
                    project_dir, name, slot, path.stem.removeprefix(f"{slot}-")
                )
            )
        except (OSError, ValueError, RuntimeError):
            # One incomplete/invalid file must not hide the remaining auditions.
            continue
    return sorted(
        previews,
        key=lambda item: (item["created_at"], item["preview_id"]),
        reverse=True,
    )


def save_character_voice_preview(
    *,
    project_dir: Path,
    name: str,
    slot: str,
    preview_id: str,
) -> tuple[str, str, str]:
    source = character_voice_preview_path(project_dir, name, slot, preview_id)
    if not source.is_file():
        raise ValueError("Voice preview not found; generate a preview first")
    return persist_character_voice_file(
        project_dir=project_dir,
        character_name=name,
        slot=slot,
        filename="generated.mp3",
        content=source.read_bytes(),
    )


async def generate_character_voice_preview(
    *,
    project_dir: Path,
    name: str,
    slot: str,
    model: str,
    description: str,
    text: str,
    speaker: str = "",
) -> tuple[str, Path, float]:
    if model not in character_voice_model_options():
        raise ValueError(
            "Select a configured Seed Audio model in audio source settings"
        )
    gateway = get_ce_newapi_config_for_mode(MODE_CUSTOM)
    if not gateway.api_key or not gateway.base_url:
        raise ValueError("The local model gateway is not configured")
    preview_id = uuid.uuid4().hex
    path = character_voice_preview_path(project_dir, name, slot, preview_id)
    # Seed Audio describes a sound scene rather than accepting separate timbre
    # instructions. Bind the voice setting to the speaker and quote only dialogue.
    role = "角色（参考@音频1的音色）" if speaker.strip() else "角色"
    prompt = (
        f"生成纯人声的单角色声线试听。{role}的声音设定：{description.strip()}\n"
        f"{role}按照上述音色、音调、语速和节奏说：“{text.strip()}”\n"
        "只说引号内的台词，不朗读声音设定或说明。完整说完台词后结束，"
        "按指定语速自然展开，最长不超过30秒，不为凑时长拖慢、加速或重复台词。\n"
        "声音设定仅用于控制发声；机械或电子质感通过声线与咬字表现。"
        "不要背景音乐或音效，不生成提示音、环境声或其他独立声音。"
    )
    if not text.strip() or not description.strip() or len(prompt) > 3000:
        raise ValueError(
            "Voice description and sample text are required and must fit 3000 characters"
        )
    body = {
        "model": model,
        "input": prompt,
        "response_format": "mp3",
        "metadata": {
            "audio_config": {
                "sample_rate": 48000,
                "speech_rate": 0,
                "pitch_rate": 0,
                "loudness_rate": 0,
            }
        },
    }
    if speaker.strip():
        body["voice"] = speaker.strip()
    meter = get_usage_meter()
    reservation = await meter.reserve_current_model_call_credit(
        model=model,
        billing_kind="audio",
        metadata={"source": "character_voice_preview"},
    )
    try:
        # A timed-out generation can still be billable: never resubmit it automatically.
        async with httpx.AsyncClient(timeout=300, trust_env=False) as client:
            response = await client.post(
                gateway.base_url.rstrip("/") + "/audio/speech",
                headers={"Authorization": f"Bearer {gateway.api_key}"},
                json=body,
            )
            if response.status_code >= 400:
                raise RuntimeError(
                    f"Voice generation failed (HTTP {response.status_code})"
                )
            request_id = response.headers.get("x-request-id", "")
            content = response.content
            if "application/json" in response.headers.get("content-type", "").lower():
                payload = response.json()
                audio = payload.get("audio")
                if isinstance(audio, dict) and audio.get("data"):
                    content = base64.b64decode(audio["data"], validate=True)
                else:
                    url = (
                        audio.get("url", "")
                        if isinstance(audio, dict)
                        else payload.get("url", "")
                    )
                    if not url or not str(url).startswith(("http://", "https://")):
                        raise RuntimeError("Voice response contains no audio")
                    download = await client.get(url)
                    if download.status_code >= 400:
                        raise RuntimeError("Voice preview download failed")
                    content = download.content
        duration = await run_voice_media_operation(
            _store_voice_preview,
            path,
            content,
            {
                "model": model,
                "text": text.strip(),
                "speaker": speaker.strip(),
                "voice_prompt": description.strip(),
            },
        )
    except Exception:
        await meter.refund_model_call_credit_reservation(
            reservation,
            metadata={
                "source": "character_voice_preview",
                "error": "voice_preview_failed",
            },
        )
        raise
    await meter.bump_model_call(
        user_id=None,
        model=model,
        provider_request_id=request_id,
        credit_reservation_id=reservation,
    )
    return preview_id, path, duration
