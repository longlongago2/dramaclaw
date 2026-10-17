// SPDX-License-Identifier: Elastic-2.0
// Copyright (c) 2026 ClaymoreLab
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ky from "ky";
import { http, HttpResponse } from "msw";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { server } from "@/__mocks__/msw/server";
import { CharacterVoiceGenerateDialog } from "@/components/assets/character-voice-generate-dialog";
import { CharacterVoiceSourceSelect } from "@/components/assets/character-voice-source-select";
import type { CharacterVoiceSlot } from "@/types/character";
import type { CharacterVoicePreview } from "@/lib/queries/character-voice-generation";

vi.mock("@/lib/api", () => ({ api: ky.create({ baseUrl: "http://localhost:3000/" }) }));
afterEach(cleanup);
const root = "http://localhost:3000/api/v1/projects/demo";
const previewsUrl = `${root}/characters/Ding/voice-samples/default/previews`;
beforeEach(() => server.use(http.get(previewsUrl, () => HttpResponse.json({ ok: true, data: [] }))));
function take(id: string, text: string): CharacterVoicePreview {
  return { preview_id: id.repeat(32), url: `/static/${id}.mp3`, duration: 8, model: "index-tts-2",
    created_at: "2026-10-16T10:00:00Z", text, speaker: "", sha256: id.repeat(64) };
}
const slot: CharacterVoiceSlot = {
  slot: "default", label: "默认", path: "", url: "", sha256: "", updated_at: "",
  inherited_from_default: false, required: true,
};

function renderVoice(component: React.ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return { ...render(<QueryClientProvider client={client}>{component}</QueryClientProvider>), client };
}

describe("character voice generation", () => {
  it("saves a project audio source independently of image source", async () => {
    let selected = "index-tts-2";
    server.use(
      http.get(`${root}/character-voice-selection`, () => HttpResponse.json({ ok: true, data: {
        model: selected, options: { "index-tts-2": "Seed Audio", "another-seed": "Another Voice" },
      } })),
      http.patch(`${root}/character-voice-selection`, async ({ request }) => {
        selected = (await request.json() as { model: string }).model;
        return HttpResponse.json({ ok: true, data: { model: selected, options: { "index-tts-2": "Seed Audio", "another-seed": "Another Voice" } } });
      }),
    );
    renderVoice(<CharacterVoiceSourceSelect project="demo" />);
    const user = userEvent.setup();
    await waitFor(() => expect(screen.getByRole("combobox", { name: "音源" })).toHaveTextContent("Seed Audio"));
    await user.click(screen.getByRole("combobox", { name: "音源" }));
    await user.click(await screen.findByRole("option", { name: "Another Voice" }));
    await waitFor(() => expect(selected).toBe("another-seed"));
    expect(screen.getByRole("combobox", { name: "音源" })).toHaveTextContent("Another Voice");
  });

  it("auditions without saving, then explicitly saves and refreshes character voice state", async () => {
    const onClose = vi.fn();
    let generations = 0;
    let saves = 0;
    const auditions: CharacterVoicePreview[] = [];
    server.use(
      http.get(previewsUrl, () => HttpResponse.json({ ok: true, data: auditions })),
      http.get(`${root}/character-voice-selection`, () => HttpResponse.json({ ok: true, data: { model: "index-tts-2", options: { "index-tts-2": "Seed Audio" } } })),
      http.post(`${root}/characters/Ding/voice-samples/default/generate`, async ({ request }) => {
        generations += 1;
        expect(await request.json()).toEqual({ text: expect.any(String), speaker: "" });
        auditions.unshift(take("a", "你好"));
        return HttpResponse.json({ ok: true, data: auditions[0] });
      }),
      http.post(`${root}/characters/Ding/voice-samples/default/save-preview`, async ({ request }) => {
        saves += 1;
        expect(await request.json()).toEqual({ preview_id: "a".repeat(32) });
        return HttpResponse.json({ ok: true, data: { ...slot, path: "voices/default.mp3" } });
      }),
    );
    const { client } = renderVoice(<CharacterVoiceGenerateDialog project="demo" name="Ding" slot={slot} hasVoicePrompt onClose={onClose} />);
    const invalidations = vi.spyOn(client, "invalidateQueries");
    expect(screen.getByRole("button", { name: "保存声线" })).toBeDisabled();
    expect(screen.queryByLabelText("声音提示词")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("声音描述")).not.toBeInTheDocument();
    await waitFor(() => expect(screen.getByRole("button", { name: "生成声线" })).toBeEnabled());
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "生成声线" }));
    expect(await screen.findByLabelText("声线试听")).toHaveAttribute("src", "/static/a.mp3");
    expect(generations).toBe(1);
    expect(saves).toBe(0);
    expect(onClose).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "保存声线" }));
    await waitFor(() => expect(onClose).toHaveBeenCalledOnce());
    expect(saves).toBe(1);
    expect(invalidations).toHaveBeenCalledWith({ queryKey: ["projects", "demo", "characters", "Ding", "voice-samples"] });
  });

  it("restores multiple auditions after a fresh mount and saves an earlier selection", async () => {
    const auditions = [take("b", "第二次试听"), take("a", "第一次试听")];
    let savedId = "";
    server.use(
      http.get(`${root}/character-voice-selection`, () => HttpResponse.json({ ok: true, data: { model: "index-tts-2", options: { "index-tts-2": "Seed Audio" } } })),
      http.get(previewsUrl, () => HttpResponse.json({ ok: true, data: auditions })),
      http.post(`${root}/characters/Ding/voice-samples/default/save-preview`, async ({ request }) => {
        savedId = (await request.json() as { preview_id: string }).preview_id;
        return HttpResponse.json({ ok: true, data: { ...slot, path: "voices/default.mp3" } });
      }),
      http.post(`${root}/characters/Ding/voice-samples/default/generate`, () => HttpResponse.json({ ok: false, error: "生成失败" }, { status: 502 })),
    );
    const first = renderVoice(<CharacterVoiceGenerateDialog project="demo" name="Ding" slot={slot} hasVoicePrompt onClose={vi.fn()} />);
    expect(await screen.findByRole("radio", { name: "候选 2" })).toBeChecked();
    first.unmount();
    first.client.clear();
    const onClose = vi.fn();
    renderVoice(<CharacterVoiceGenerateDialog project="demo" name="Ding" slot={slot} hasVoicePrompt onClose={onClose} />);
    const user = userEvent.setup();
    await user.click(await screen.findByRole("radio", { name: "候选 1" }));
    expect(screen.getByLabelText("声线试听")).toHaveAttribute("src", "/static/a.mp3");
    await user.type(screen.getByLabelText("试听文本"), "新的台词");
    expect(screen.getByRole("radio", { name: "候选 1" })).toBeChecked();
    await user.click(screen.getByRole("button", { name: "生成声线" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "生成声线" })).toBeEnabled());
    expect(screen.getAllByRole("radio")).toHaveLength(2);
    expect(screen.getByLabelText("声线试听")).toHaveAttribute("src", "/static/a.mp3");
    await user.click(screen.getByRole("button", { name: "保存声线" }));
    await waitFor(() => expect(savedId).toBe("a".repeat(32)));
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("marks and selects the currently saved take while allowing another choice", async () => {
    server.use(http.get(previewsUrl, () => HttpResponse.json({ ok: true, data: [take("b", "新试听"), take("a", "当前声线")] })));
    renderVoice(<CharacterVoiceGenerateDialog project="demo" name="Ding" slot={{ ...slot, path: "voice.mp3", sha256: "a".repeat(64) }} hasVoicePrompt={false} onClose={vi.fn()} />);
    expect(await screen.findByText("使用中")).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: "候选 1" })).toBeChecked();
    expect(screen.getByRole("button", { name: "保存并替换" })).toBeDisabled();
    await userEvent.setup().click(screen.getByRole("radio", { name: "候选 2" }));
    expect(screen.getByRole("button", { name: "保存并替换" })).toBeEnabled();
    expect(screen.getByLabelText("声线试听")).toHaveAttribute("src", "/static/b.mp3");
  });

  it("requires a saved character voice prompt without adding a second prompt editor", async () => {
    let generations = 0;
    server.use(
      http.get(`${root}/character-voice-selection`, () => HttpResponse.json({ ok: true, data: { model: "index-tts-2", options: { "index-tts-2": "Seed Audio" } } })),
      http.post(`${root}/characters/Ding/voice-samples/default/generate`, () => { generations += 1; return HttpResponse.json({ ok: false }); }),
    );
    renderVoice(<CharacterVoiceGenerateDialog project="demo" name="Ding" slot={slot} hasVoicePrompt={false} onClose={vi.fn()} />);
    await screen.findByText(/index-tts-2|Seed Audio/);
    expect(screen.getByRole("button", { name: "生成声线" })).toBeDisabled();
    expect(screen.getByTitle("请先在角色资料中填写声音提示词。")).toBeInTheDocument();
    expect(generations).toBe(0);
    expect(screen.queryByLabelText("声音提示词")).not.toBeInTheDocument();
  });
});
