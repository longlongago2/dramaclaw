// SPDX-License-Identifier: Elastic-2.0
// Copyright (c) 2026 ClaymoreLab
import { useLayoutEffect, type RefObject } from 'react';

export type StyleViewBounds = Pick<DOMRect, 'left' | 'top' | 'width' | 'height'>;

/** Morph between the anchored list and portal grid without animating layout properties. */
export function useStyleViewTransition(
  ref: RefObject<HTMLDivElement | null>,
  from: StyleViewBounds | null | undefined,
  active = true,
) {
  useLayoutEffect(() => {
    const panel = ref.current;
    if (!active || !panel || !from || !panel.animate ||
      window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) return;
    const to = panel.getBoundingClientRect();
    if (!from.width || !from.height || !to.width || !to.height) return;
    // The list can live inside a zoomed React Flow canvas. Convert viewport
    // offsets into its local coordinates; the portal grid has scale 1.
    const parentScaleX = panel.offsetWidth ? to.width / panel.offsetWidth : 1;
    const parentScaleY = panel.offsetHeight ? to.height / panel.offsetHeight : 1;
    const styles = getComputedStyle(panel);
    const duration = parseFloat(styles.getPropertyValue('--duration-slow')) || 320;
    const animation = panel.animate([
      {
        transformOrigin: 'top left',
        transform: `translate(${(from.left - to.left) / parentScaleX}px, ${(from.top - to.top) / parentScaleY}px) scale(${from.width / to.width}, ${from.height / to.height})`,
        opacity: 0.4,
      },
      { transformOrigin: 'top left', transform: 'none', opacity: 1 },
    ], {
      duration,
      easing: styles.getPropertyValue('--ease-out-quint').trim() || 'cubic-bezier(0.22, 1, 0.36, 1)',
    });
    return () => animation.cancel();
  }, [active, from, ref]);
}
