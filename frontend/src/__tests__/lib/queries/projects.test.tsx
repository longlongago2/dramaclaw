import { describe, expect, it } from "vitest";
import { vi } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import ky from "ky";
import type { ReactNode } from "react";
import { server } from "@/__mocks__/msw/server";

vi.mock("@/lib/api", () => ({ api: ky.create({ baseUrl: "http://localhost:3000/" }) }));

import {
  normalizeUserSearchQuery, useAllProjectSummaries, useCreateProject, useRenameProject,
} from "@/lib/queries/projects";
import { getProjectDisplayName, normalizeProjectDisplayName } from "@/lib/project-name";

function wrapper(queryClient: QueryClient) {
  return function QueryWrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  };
}

describe("normalizeUserSearchQuery", () => {
  it("removes pinyin separators while preserving the username characters", () => {
    expect(normalizeUserSearchQuery("  huang'jiao  ")).toBe("huangjiao");
  });
});

describe("project display names", () => {
  it("keeps the directory name separate from the title and falls back for old responses", () => {
    expect(getProjectDisplayName({ name: "p_01", displayName: "火柴人" })).toBe("火柴人");
    expect(getProjectDisplayName({ name: "legacy" })).toBe("legacy");
    expect(normalizeProjectDisplayName("  Cafe\u0301  ")).toBe("Café");
  });

  it("creates with a display title and renames through the stable ID", async () => {
    let createBody: unknown;
    let renameBody: unknown;
    const rows = [
      { id: "project-id", name: "p_internal", display_name: "火柴人", status: "active" },
      { id: "old-id", name: "legacy", status: "active" },
    ];
    server.use(
      http.post("http://localhost:3000/api/v1/projects", async ({ request }) => {
        createBody = await request.json();
        return HttpResponse.json({ ok: true, data: { ...rows[0], project_id: rows[0].id } });
      }),
      http.get("http://localhost:3000/api/v1/projects/summaries", () =>
        HttpResponse.json({ ok: true, data: rows })),
      http.patch("http://localhost:3000/api/v1/projects/project-id/display-name", async ({ request }) => {
        renameBody = await request.json();
        rows[0].display_name = "火柴人 第二部";
        return HttpResponse.json({ ok: true, data: rows[0] });
      }),
    );
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const { result } = renderHook(() => ({
      summaries: useAllProjectSummaries(), create: useCreateProject(), rename: useRenameProject("project-id"),
    }), { wrapper: wrapper(queryClient) });
    await waitFor(() => expect(result.current.summaries.data).toHaveLength(2));
    expect(result.current.summaries.data?.[0]).toMatchObject({ name: "p_internal", displayName: "火柴人" });
    expect(result.current.summaries.data?.[1].displayName).toBe("legacy");
    const created = await result.current.create.mutateAsync("火柴人");
    expect(createBody).toEqual({ display_name: "火柴人" });
    expect(created.data.id).toBe("project-id");
    await result.current.rename.mutateAsync("火柴人 第二部");
    expect(renameBody).toEqual({ display_name: "火柴人 第二部" });
    await waitFor(() => expect(result.current.summaries.data?.[0]).toMatchObject({
      id: "project-id", name: "p_internal", displayName: "火柴人 第二部",
    }));
  });
});
