// SPDX-License-Identifier: Elastic-2.0
// Copyright (c) 2026 ClaymoreLab
import type { StageId } from "@/lib/episode-stage-registry";

/**
 * Per-beat per-stage derived state.
 * - missing: asset absent; no active task attributable to this beat/stage
 * - generating: active task matches this beat (scoped) OR is a batch and beat is still missing
 * - ready: asset present (URL non-null)
 * - failed: task terminal=failed AND task.beat_num === n AND asset still absent
 *
 * Composition only requires independent audio when explicitly selected.
 */
export type BeatStageState = "missing" | "generating" | "ready" | "failed";

export type BeatStates = Record<
  number,
  Record<Exclude<StageId, "compose">, BeatStageState>
>;

export interface StageCount {
  /** Beats in `ready` state. */
  ready: number;
  /** Total beats considered — excludes a beat if state derivation had no inputs. */
  total: number;
  /** Beats with any non-ready state other than `missing` (generating + failed). */
  active: number;
  /** Beats in `failed` state. */
  failed: number;
}

export interface EpisodeCounts {
  script: StageCount;
  sketch: StageCount;
  audio: StageCount;
  video: StageCount;
  compose: {
    ready: boolean;
    missing: Array<{ beatNum: number; stages: Array<Exclude<StageId, "compose">> }>;
  };
}
