// SPDX-License-Identifier: Elastic-2.0
// Copyright (c) 2026 ClaymoreLab
import { useMemo } from "react";
import { useEpisodeBeats } from "@/lib/queries/episodes";
import { composeReadiness, type BeatAudioSources } from "@/lib/compose-audio";
import { useTasks } from "@/lib/queries/tasks";
import { deriveBeatStates } from "@/lib/derive-beat-states";
import type { BeatStates, EpisodeCounts, StageCount } from "@/types/beat-state";
import type { StageId } from "@/lib/episode-stage-registry";

interface UseBeatStatesResult {
  states: BeatStates;
  counts: EpisodeCounts;
  loading: boolean;
}

/**
 * Derive per-beat × per-stage state for an episode.
 *
 * Subscribes to `useEpisodeBeats` and `useTasks`; memoizes the derivation so
 * consumers don't recompute on every unrelated query tick.
 */
const DEFAULT_AUDIO_SOURCES: BeatAudioSources = {};

export function useBeatStates(
  project: string,
  episode: number,
  audioSources: BeatAudioSources = DEFAULT_AUDIO_SOURCES,
): UseBeatStatesResult {
  const beatsRes = useEpisodeBeats(project, episode);
  // Filter at the query layer so poll ticks that don't touch this episode
  // don't produce a new tasks reference that would cascade into a re-derive.
  const tasksRes = useTasks({ project, episode });

  return useMemo(() => {
    const beats = beatsRes.data?.data ?? [];
    const tasks = tasksRes.data?.data ?? [];

    const states = deriveBeatStates(beats, tasks);
    const counts = computeCounts(states, beats.length, audioSources);

    return {
      states,
      counts,
      loading: beatsRes.isLoading || tasksRes.isLoading,
    };
  }, [beatsRes.data, tasksRes.data, beatsRes.isLoading, tasksRes.isLoading, audioSources]);
}

function computeCounts(
  states: BeatStates,
  totalBeats: number,
  audioSources: BeatAudioSources,
): EpisodeCounts {
  const stages: Array<Exclude<StageId, "compose">> = ["script", "sketch", "audio", "video"];
  const per: Record<Exclude<StageId, "compose">, StageCount> = {
    script: { ready: 0, total: totalBeats, active: 0, failed: 0 },
    sketch: { ready: 0, total: totalBeats, active: 0, failed: 0 },
    audio: { ready: 0, total: totalBeats, active: 0, failed: 0 },
    video: { ready: 0, total: totalBeats, active: 0, failed: 0 },
  };

  for (const [, stagesState] of Object.entries(states)) {
    for (const stage of stages) {
      const s = stagesState[stage];
      if (s === "ready") per[stage].ready += 1;
      else if (s === "generating") per[stage].active += 1;
      else if (s === "failed") per[stage].failed += 1;
    }
  }

  return {
    ...per,
    compose: composeReadiness(states, totalBeats, audioSources),
  };
}
