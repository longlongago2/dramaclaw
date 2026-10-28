// SPDX-License-Identifier: Elastic-2.0
// Copyright (c) 2026 ClaymoreLab
import type { BeatStates, EpisodeCounts } from "@/types/beat-state";

export const COMPOSE_AUDIO_SOURCES = ["auto", "embedded", "external", "silence"] as const;
export type ComposeAudioSource = typeof COMPOSE_AUDIO_SOURCES[number];
export type BeatAudioSources = Record<number, ComposeAudioSource>;

export function composeReadiness(
  states: BeatStates,
  totalBeats: number,
  sources: BeatAudioSources = {},
): EpisodeCounts["compose"] {
  const missing: EpisodeCounts["compose"]["missing"] = [];
  for (const [number, stages] of Object.entries(states)) {
    const beatNum = Number(number);
    const blockers: ("audio" | "video")[] = [];
    if (sources[beatNum] === "external" && stages.audio !== "ready") blockers.push("audio");
    if (stages.video !== "ready") blockers.push("video");
    if (blockers.length) missing.push({ beatNum, stages: blockers });
  }
  return { ready: missing.length === 0 && totalBeats > 0, missing };
}
