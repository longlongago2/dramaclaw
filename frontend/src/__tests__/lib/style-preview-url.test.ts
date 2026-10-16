// SPDX-License-Identifier: Elastic-2.0
// Copyright (c) 2026 ClaymoreLab
import { describe, expect, it } from "vitest";

import { stylePreviewUrl } from "@/lib/style-preview-url";

describe("stylePreviewUrl", () => {
  it("includes the concrete variant and preserves legacy theme mappings", () => {
    expect(stylePreviewUrl('stickman', '1b')).toContain('&theme=1b');
    expect(stylePreviewUrl('stickman', 'modern')).toContain('&theme=2b');
    expect(stylePreviewUrl('stickman', null)).not.toContain('&theme=');
  });
  it("encodes style ids and cache-busts preset preview images", () => {
    expect(stylePreviewUrl("spider verse/mixed media")).toBe(
      "/api/v1/styles/spider%20verse%2Fmixed%20media/preview?v=main-preset-png-20261014",
    );
  });
});
