// SPDX-License-Identifier: Elastic-2.0
// Copyright (c) 2026 ClaymoreLab
import { p } from "@/lib/api-path";
import { concreteStickmanTheme } from '@/lib/stickman-themes';

const STYLE_PREVIEW_ASSET_VERSION = "main-preset-png-20261014";

export function stylePreviewUrl(styleId: string, theme?: string | null): string {
  const concrete = concreteStickmanTheme(theme);
  const query = concrete ? `&theme=${encodeURIComponent(concrete)}` : '';
  return `/${p`api/v1/styles/${styleId}/preview`}?v=${STYLE_PREVIEW_ASSET_VERSION}${query}`;
}
