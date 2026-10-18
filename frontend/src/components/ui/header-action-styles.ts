// SPDX-License-Identifier: Elastic-2.0
// Copyright (c) 2026 ClaymoreLab

/**
 * Page-header secondary actions share one quiet visual hierarchy: transparent
 * surface, a translucent white border, and restrained hover/press feedback.
 */
export const SUBTLE_HEADER_ACTION_BUTTON_CLASS =
  "h-8 gap-1.5 rounded-[8px] border-white/10 bg-transparent px-3 text-xs font-normal shadow-none transition-[background-color,border-color,transform] hover:border-white/15 hover:bg-white/[0.04] active:scale-95 dark:border-white/10 dark:bg-transparent dark:hover:border-white/15 dark:hover:bg-white/[0.04]";

/** Image and voice sources share the same compact header selector treatment. */
export const ASSET_SOURCE_TRIGGER_CLASS =
  "h-8 gap-0 rounded-[8px] border-white/10 bg-transparent px-3 text-xs font-normal shadow-none hover:bg-white/[0.04] dark:bg-transparent";

export const ASSET_SOURCE_CONTENT_CLASS =
  "rounded-md border border-white/10 bg-popover p-1 shadow-xl shadow-black/20 ring-0";

export const ASSET_SOURCE_ITEM_CLASS =
  "min-h-8 gap-2 rounded-sm px-2 py-1.5 text-xs focus:bg-white/8 focus:text-current";
