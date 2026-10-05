import { describe, it, expect, vi } from 'vitest';
import {
  registerServiceWorker,
  supportsServiceWorker,
  type RegisterableServiceWorkerContainer,
} from './sw-register';

describe('supportsServiceWorker', () => {
  it('is true when register is a function', () => {
    const container: RegisterableServiceWorkerContainer = { register: vi.fn() };
    expect(supportsServiceWorker(container)).toBe(true);
  });

  it('is false for undefined (browser without SW support)', () => {
    expect(supportsServiceWorker(undefined)).toBe(false);
  });

  it('is false when register is missing', () => {
    expect(supportsServiceWorker({} as RegisterableServiceWorkerContainer)).toBe(false);
  });
});

describe('registerServiceWorker', () => {
  it('registers /service-worker.js at the root scope', async () => {
    const register = vi.fn().mockResolvedValue({ scope: '/' });
    const container: RegisterableServiceWorkerContainer = { register };

    const promise = registerServiceWorker('/service-worker.js', container);

    expect(register).toHaveBeenCalledWith('/service-worker.js', { scope: '/' });
    await expect(promise).resolves.toEqual({ scope: '/' });
  });

  it('returns null (does not throw) without SW support', () => {
    expect(registerServiceWorker('/sw.js', undefined)).toBeNull();
  });

  it('propagates registration failures to the caller', async () => {
    const register = vi.fn().mockRejectedValue(new Error('insecure context'));
    const promise = registerServiceWorker('/sw.js', { register });
    await expect(promise).rejects.toThrow('insecure context');
  });
});
