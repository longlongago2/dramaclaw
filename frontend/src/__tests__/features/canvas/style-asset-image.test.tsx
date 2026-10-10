// SPDX-License-Identifier: Elastic-2.0
// Copyright (c) 2026 ClaymoreLab
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { StyleAssetImage } from "@/features/canvas/ui/StyleAssetImage";

describe("StyleAssetImage", () => {
  it("uses the shared cover spritesheet and clips to the selected style", () => {
    render(<StyleAssetImage rel="golden_age/cover.webp" assetBase="" alt="黄金时代" />);
    const preview = screen.getByRole("img", { name: "黄金时代" });
    expect(preview.querySelector("image")?.getAttribute("href")).toMatch(/^\/style-gallery\/covers(?:-[a-f0-9]+)?\.webp$/);
    expect(preview.querySelector("svg")).toHaveAttribute("viewBox", "1152 216 384 216");
  });

  it("shares one sheet for all four portraits and shows distinct quadrants", () => {
    const { rerender } = render(<StyleAssetImage rel="golden_age/female.webp" assetBase="" alt="人物" />);
    const first = screen.getByRole("img", { name: "人物" }).querySelector("image")?.getAttribute("href");
    expect(screen.getByRole("img", { name: "人物" }).querySelector("svg")).toHaveAttribute("viewBox", "0 0 384 512");
    rerender(<StyleAssetImage rel="golden_age/elder.webp" assetBase="" alt="人物" />);
    expect(screen.getByRole("img", { name: "人物" }).querySelector("image")).toHaveAttribute("href", first);
    expect(screen.getByRole("img", { name: "人物" }).querySelector("svg")).toHaveAttribute("viewBox", "384 512 384 512");
  });

  it("shows a placeholder if the spritesheet fails and retries a different sheet", () => {
    const { rerender } = render(<StyleAssetImage rel="golden_age/cover.webp" assetBase="" alt="风格" />);
    fireEvent.error(screen.getByRole("img", { name: "风格" }).querySelector("image")!);
    expect(screen.getByRole("img", { name: "风格" }).querySelector("image")).toBeNull();
    rerender(<StyleAssetImage rel="golden_age/female.webp" assetBase="" alt="风格" />);
    expect(screen.getByRole("img", { name: "风格" }).querySelector("image")).toBeInTheDocument();
  });

  it("resolves the relative path against the asset base", () => {
    render(
      <StyleAssetImage
        rel="golden_age/cover.webp"
        assetBase="https://cdn.example.com/styles"
        alt="黄金时代"
      />,
    );

    expect(screen.getByAltText("黄金时代")).toHaveAttribute(
      "src",
      "https://cdn.example.com/styles/golden_age/cover.webp",
    );
  });

  it("falls back to a placeholder when the asset 404s", () => {
    render(
      <StyleAssetImage rel="gone/cover.webp" assetBase="" alt="已下架风格" />,
    );

    fireEvent.error(screen.getByAltText("已下架风格"));

    // 图没了也要留个占位块，别露浏览器的碎图标
    const placeholder = screen.getByRole("img", { name: "已下架风格" });
    expect(placeholder.tagName).toBe("DIV");
  });

  it("renders the placeholder when the manifest has no cover", () => {
    render(<StyleAssetImage rel="" assetBase="" alt="无封面" />);

    expect(screen.getByRole("img", { name: "无封面" }).tagName).toBe("DIV");
  });
});
