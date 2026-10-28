# SPDX-License-Identifier: Elastic-2.0
# Copyright (c) 2026 ClaymoreLab
"""Resolve per-shot sound choices for episode composition."""

from pathlib import Path
from typing import Literal, get_args

from novelvideo.utils.path_resolver import PathResolver

ComposeAudioSource = Literal["auto", "embedded", "external", "silence"]
AUDIO_SOURCES = set(get_args(ComposeAudioSource))


def compose_asset_errors(
    paths: PathResolver, beats: list[dict], audio_sources: dict[int, str]
) -> list[str]:
    errors = []
    beat_numbers = {int(beat.get("beat_number") or i + 1) for i, beat in enumerate(beats)}
    for beat_num, source in audio_sources.items():
        if beat_num not in beat_numbers:
            errors.append(f"Unknown beat: {beat_num}")
        if source not in AUDIO_SOURCES:
            errors.append(f"Beat {beat_num}: invalid audio source {source}")
    for beat_num in sorted(beat_numbers):
        if not paths.video(beat_num).is_file():
            errors.append(f"Beat {beat_num}: missing video")
        if audio_sources.get(beat_num) == "external" and not paths.audio(beat_num).is_file():
            errors.append(f"Beat {beat_num}: missing external audio")
    return errors


def use_external_audio(beat: dict, source: str, audio_path: Path) -> bool:
    """Auto retains voiceover priority, but silent/action shots need no TTS."""
    if source == "external":
        return True
    return (
        source == "auto"
        and beat.get("audio_type") not in {"silence", "action"}
        and audio_path.is_file()
    )
