// SPDX-License-Identifier: Elastic-2.0
// Copyright (c) 2026 ClaymoreLab
import type { ComponentType } from "react";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import i18next from "i18next";
import { I18nextProvider } from "react-i18next";
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import en from "../../../public/locales/en/translation.json";

const state = vi.hoisted(() => ({
  video: "/clip.mp4" as string | null,
  audio: null as string | null,
  final: false,
  mutate: vi.fn().mockResolvedValue({ ok: true }),
  start: vi.fn(),
}));

vi.mock("@tanstack/react-router", () => ({
  createLazyFileRoute: () => (options: { component: ComponentType }) => ({
    options, useParams: () => ({ project: "demo", episode: "1" }),
  }),
  useNavigate: () => vi.fn(),
}));
vi.mock("@/lib/queries/episodes", () => ({
  useEpisodeBeats: () => ({ isLoading: false, data: { data: [{
    beat_number: 1, visual_description: "Room", narration_segment: "Hello",
    audio_type: "narration", video_url: state.video, audio_url: state.audio,
  }] } }),
  useEpisodeDetail: () => ({ data: { data: { title: "Episode 1" } } }),
}));
vi.mock("@/lib/queries/projects", () => ({
  useProject: () => ({ data: { data: {} } }),
  useUpdateProject: () => ({ mutate: vi.fn() }),
}));
vi.mock("@/lib/queries/tasks", () => ({ useTasks: () => ({ isLoading: false, data: { data: [] } }) }));
vi.mock("@/lib/queries/video", () => ({
  useComposeEpisode: () => ({ mutateAsync: state.mutate, isPending: false }),
  useFinalVideo: () => ({ data: { data: { exists: state.final, video_url: "/final.mp4" } } }),
}));
vi.mock("@/hooks/use-task-controller", () => ({
  useTaskController: () => ({ started: false, stream: {}, logs: [], start: state.start }),
}));

import { Route } from "@/routes/_app/projects.$project/episodes.$episode/compose.lazy";

const i18n = i18next.createInstance();
beforeAll(async () => {
  await i18n.init({ lng: "en", resources: { en: { translation: en } }, interpolation: { escapeValue: false } });
});
beforeEach(() => {
  state.video = "/clip.mp4";
  state.audio = null;
  state.final = false;
  vi.clearAllMocks();
});
afterEach(cleanup);

function page() {
  const Component = Route.options.component as ComponentType;
  return <I18nextProvider i18n={i18n}><Component /></I18nextProvider>;
}

async function chooseAudio(label: string) {
  const user = userEvent.setup();
  await user.click(screen.getByRole("combobox", { name: "Beat 1" }));
  await user.click(await screen.findByRole("option", { name: label }));
}

describe("episode composition audio controls", () => {
  it("allows original audio without voiceover and submits the shot choice", async () => {
    render(page());
    expect(screen.getByRole("button", { name: i18n.t("episode.compose.composeEpisode") })).toBeEnabled();
    await chooseAudio("Voiceover");
    expect(screen.getByRole("button", { name: i18n.t("episode.compose.composeEpisode") })).toBeDisabled();
    expect(screen.getByText("Missing: Audio")).toBeInTheDocument();
    await chooseAudio("Original sound");
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: i18n.t("episode.compose.composeEpisode") }));
    await user.click(screen.getByRole("button", { name: i18n.t("episode.compose.composeConfirm") }));
    await waitFor(() => expect(state.mutate).toHaveBeenCalledWith(expect.objectContaining({
      beat_audio_sources: { 1: "embedded" },
    })));
    expect(state.start).toHaveBeenCalled();
  });

  it("keeps missing-video blockers visible when a previous final exists", async () => {
    state.final = true;
    state.video = null;
    render(page());
    await screen.findByRole("button", { name: i18n.t("episode.compose.recomposeEpisode") });
    expect(screen.getByRole("button", { name: i18n.t("episode.compose.recomposeEpisode") })).toBeDisabled();
    await chooseAudio("Mute");
    expect(screen.getByRole("button", { name: i18n.t("episode.compose.recomposeEpisode") })).toBeDisabled();
    expect(screen.getByText("Missing: Video")).toBeInTheDocument();
  });
});
