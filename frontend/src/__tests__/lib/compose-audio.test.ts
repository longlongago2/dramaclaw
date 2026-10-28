// SPDX-License-Identifier: Elastic-2.0
// Copyright (c) 2026 ClaymoreLab
import { describe, expect, it } from "vitest";
import { composeReadiness, type ComposeAudioSource } from "@/lib/compose-audio";
import { deriveBeatStates } from "@/lib/derive-beat-states";

const states = deriveBeatStates([
  { beat_number: 1, narration_segment: "Hello", visual_description: "Room", video_url: "/clip.mp4" },
], []);

describe("composition sound prerequisites", () => {
  it.each<ComposeAudioSource>(["auto", "embedded", "silence"])("allows %s without separate voiceover", (source) => {
    expect(composeReadiness(states, 1, { 1: source })).toEqual({ ready: true, missing: [] });
  });

  it("blocks explicitly selected voiceover until its asset is ready", () => {
    expect(composeReadiness(states, 1, { 1: "external" })).toEqual({
      ready: false, missing: [{ beatNum: 1, stages: ["audio"] }],
    });
    expect(composeReadiness({ 1: { ...states[1], audio: "ready" } }, 1, { 1: "external" }).ready).toBe(true);
  });

  it.each<ComposeAudioSource>(["auto", "embedded", "external", "silence"])("requires video with %s", (source) => {
    const result = composeReadiness({ 1: { ...states[1], video: "missing" } }, 1, { 1: source });
    expect(result.ready).toBe(false);
    expect(result.missing[0].stages).toContain("video");
  });

  it("does not compose an empty episode", () => {
    expect(composeReadiness({}, 0).ready).toBe(false);
  });
});
