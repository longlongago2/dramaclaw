// SPDX-License-Identifier: Elastic-2.0
// Copyright (c) 2026 ClaymoreLab
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import type { Plugin } from "vite";

/** Bundle the public sprite mapping without a forbidden dev-server public import. */
export function styleGalleryPlugin(): Plugin {
  const moduleId = "virtual:style-gallery-sprites";
  const resolvedId = "\0" + moduleId;
  const manifestPath = fileURLToPath(new URL("./public/style-gallery/styleSprites.json", import.meta.url));
  return {
    name: "style-gallery-sprites",
    resolveId(id) {
      if (id === moduleId) return resolvedId;
    },
    load(id) {
      if (id !== resolvedId) return;
      this.addWatchFile(manifestPath);
      const manifest = JSON.parse(readFileSync(manifestPath, "utf8"));
      return `export default ${JSON.stringify(manifest)};`;
    },
  };
}
