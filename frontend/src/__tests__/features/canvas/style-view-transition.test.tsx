// SPDX-License-Identifier: Elastic-2.0
// Copyright (c) 2026 ClaymoreLab
import { useRef } from 'react';
import { render } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { useStyleViewTransition } from '@/features/canvas/ui/useStyleViewTransition';

function Panel() {
  const ref = useRef<HTMLDivElement>(null);
  useStyleViewTransition(ref, { left: 100, top: 80, width: 800, height: 600 });
  return <div ref={ref} />;
}

afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); });

describe('style view transition', () => {
  it('uses viewport bounds and compensates for canvas zoom, then cancels on unmount', () => {
    const cancel = vi.fn();
    const animate = vi.fn(() => ({ cancel }));
    const originalAnimate = HTMLElement.prototype.animate;
    Object.defineProperty(HTMLElement.prototype, 'animate', { configurable: true, value: animate });
    vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockReturnValue({ left: 200, top: 180, width: 140, height: 210 } as DOMRect);
    vi.spyOn(HTMLElement.prototype, 'offsetWidth', 'get').mockReturnValue(280);
    vi.spyOn(HTMLElement.prototype, 'offsetHeight', 'get').mockReturnValue(420);
    vi.stubGlobal('matchMedia', vi.fn(() => ({ matches: false })));
    try {
      const { unmount } = render(<Panel />);
      const [frames, options] = animate.mock.calls[0] as unknown as [Keyframe[], KeyframeAnimationOptions];
      expect(frames[0].transform).toBe('translate(-200px, -200px) scale(5.714285714285714, 2.857142857142857)');
      expect(frames[1].transform).toBe('none');
      expect(options.duration).toBe(320);
      unmount();
      expect(cancel).toHaveBeenCalledOnce();
    } finally {
      Object.defineProperty(HTMLElement.prototype, 'animate', { configurable: true, value: originalAnimate });
    }
  });

  it('respects reduced motion without starting an animation', () => {
    const animate = vi.fn();
    const originalAnimate = HTMLElement.prototype.animate;
    Object.defineProperty(HTMLElement.prototype, 'animate', { configurable: true, value: animate });
    vi.stubGlobal('matchMedia', vi.fn(() => ({ matches: true })));
    try {
      render(<Panel />);
      expect(animate).not.toHaveBeenCalled();
    } finally {
      Object.defineProperty(HTMLElement.prototype, 'animate', { configurable: true, value: originalAnimate });
    }
  });
});
