// SPDX-License-Identifier: Elastic-2.0
// Copyright (c) 2026 ClaymoreLab
export const STICKMAN_THEME_GROUPS = {
  classic: ['1a', '1b'],
  modern: ['2a', '2b'],
  prehistoric: ['3'],
} as const;

export function concreteStickmanTheme(value: string | null | undefined): string | null {
  if (!value) return null;
  return ({ classic: '1a', modern: '2b', prehistoric: '3' } as Record<string, string>)[value] ?? value;
}

export function stickmanThemeGroup(value: string | null): string | null {
  const concrete = concreteStickmanTheme(value);
  return Object.entries(STICKMAN_THEME_GROUPS).find(([, variants]) =>
    (variants as readonly string[]).includes(concrete ?? ''),
  )?.[0] ?? null;
}
