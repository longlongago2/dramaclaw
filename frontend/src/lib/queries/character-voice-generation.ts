// SPDX-License-Identifier: Elastic-2.0
// Copyright (c) 2026 ClaymoreLab
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { p } from "@/lib/api-path";
import { queryKeys } from "@/lib/query-keys";
import type { ErrorResponse, OkResponse } from "@/types/api";
import type { CharacterVoiceSlot } from "@/types/character";

export type CharacterVoiceSelection = { model: string; options: Record<string, string> };
export type CharacterVoicePreview = {
  preview_id: string; url: string; duration: number; model: string;
  created_at: string; text: string; speaker: string; sha256: string;
};
const selectionKey = (project: string) => ["projects", project, "character-voice-selection"] as const;
const previewsKey = (project: string, name: string, slot: string) =>
  [...queryKeys.characterVoiceSamples(project, name), slot, "previews"] as const;

export function useCharacterVoicePreviews(project: string, name: string, slot: string) {
  return useQuery({
    queryKey: previewsKey(project, name, slot),
    queryFn: ({ signal }) => api.get(p`api/v1/projects/${project}/characters/${name}/voice-samples/${slot}/previews`, { signal })
      .json<OkResponse<CharacterVoicePreview[]>>(),
    enabled: !!project && !!name && !!slot,
    staleTime: 0,
  });
}

export function useCharacterVoiceSelection(project: string) {
  return useQuery({
    queryKey: selectionKey(project),
    queryFn: ({ signal }) => api.get(p`api/v1/projects/${project}/character-voice-selection`, { signal })
      .json<OkResponse<CharacterVoiceSelection>>(),
    enabled: !!project,
  });
}

export function useUpdateCharacterVoiceSelection(project: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (model: string) => api.patch(p`api/v1/projects/${project}/character-voice-selection`, { json: { model } })
      .json<OkResponse<CharacterVoiceSelection>>(),
    onSuccess: (response) => { if (response.ok) qc.setQueryData(selectionKey(project), response); },
  });
}

export function useGenerateCharacterVoice(project: string, name: string) {
  const qc = useQueryClient();
  return useMutation({
    retry: false,
    mutationFn: ({ slot, ...body }: { slot: string; text: string; speaker?: string }) =>
      api.post(p`api/v1/projects/${project}/characters/${name}/voice-samples/${slot}/generate`, {
        json: body, timeout: 330_000, retry: 0, throwHttpErrors: false,
      }).json<OkResponse<CharacterVoicePreview> | ErrorResponse>(),
    onSuccess: async (response, { slot }) => {
      if (!response.ok) return;
      const key = previewsKey(project, name, slot);
      await qc.cancelQueries({ queryKey: key });
      qc.setQueryData<OkResponse<CharacterVoicePreview[]>>(key, (previous) => ({
        ok: true, data: [response.data, ...(previous?.data ?? []).filter((item) => item.preview_id !== response.data.preview_id)],
      }));
      void qc.invalidateQueries({ queryKey: key });
    },
  });
}

export function useSaveCharacterVoicePreview(project: string, name: string) {
  const qc = useQueryClient();
  return useMutation({
    retry: false,
    mutationFn: ({ slot, previewId }: { slot: string; previewId: string }) =>
      api.post(p`api/v1/projects/${project}/characters/${name}/voice-samples/${slot}/save-preview`, {
        json: { preview_id: previewId }, retry: 0,
      }).json<OkResponse<CharacterVoiceSlot> | ErrorResponse>(),
    onSuccess: (response) => {
      if (!response.ok) return;
      qc.invalidateQueries({ queryKey: queryKeys.characters(project) });
      qc.invalidateQueries({ queryKey: queryKeys.characterDetails(project, name) });
      qc.invalidateQueries({ queryKey: queryKeys.characterVoiceSamples(project, name) });
      qc.invalidateQueries({ queryKey: queryKeys.audioBillingQuotes(project) });
    },
  });
}
