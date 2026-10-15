import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, expect, it, vi } from 'vitest';
import type { ReactNode } from 'react';

vi.mock('@/lib/api', () => ({
  uploadApi: {},
  api: {
    get: vi.fn((_url, options) => ({ json: async () => ({ ok: true, data: {
      id: 'stickman', style_theme: options?.searchParams?.project === 'alpha' ? 'modern' : 'prehistoric',
    } }) })),
    patch: vi.fn(() => ({ json: async () => ({ ok: true, data: {} }) })),
  },
}));

import { useStyleDetail } from '@/lib/queries/styles';
import { useUpdateProject } from '@/lib/queries/projects';

function setup() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } });
  const wrapper = ({ children }: { children: ReactNode }) => <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  return { client, wrapper };
}

describe('project-specific style theme cache', () => {
  it('does not reuse another project’s theme for the same preset', async () => {
    const { wrapper } = setup();
    const { result, rerender } = renderHook(({ project }) => useStyleDetail(project, 'stickman'), {
      wrapper, initialProps: { project: 'alpha' },
    });
    await waitFor(() => expect(result.current.data?.data.style_theme).toBe('modern'));
    rerender({ project: 'beta' });
    await waitFor(() => expect(result.current.data?.data.style_theme).toBe('prehistoric'));
  });

  it('invalidates resolved style details after applying a theme', async () => {
    const { client, wrapper } = setup();
    const invalidate = vi.spyOn(client, 'invalidateQueries');
    const { result } = renderHook(() => useUpdateProject('alpha'), { wrapper });
    await result.current.mutateAsync({ visual_style: 'stickman', visual_style_theme: 'modern' });
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ['styles'] });
  });
});
