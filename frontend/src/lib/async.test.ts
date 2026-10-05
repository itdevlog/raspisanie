import { describe, it, expect } from 'vitest';
import { createAsync } from './async.svelte';

describe('createAsync', () => {
  it('transitions idle → loading → ready and exposes data', async () => {
    const resource = createAsync(async () => 42);
    expect(resource.status).toBe('idle');
    expect(resource.data).toBeNull();

    const pending = resource.load();
    expect(resource.status).toBe('loading');
    await pending;

    expect(resource.status).toBe('ready');
    expect(resource.data).toBe(42);
  });

  it('captures thrown errors into the error state', async () => {
    const resource = createAsync(async () => {
      throw new Error('boom');
    });
    await resource.load();
    expect(resource.status).toBe('error');
    expect(resource.error).toBe('boom');
    expect(resource.data).toBeNull();
  });

  it('falls back to a generic message for non-Error throws', async () => {
    const resource = createAsync(async () => {
      throw 'nope';
    });
    await resource.load();
    expect(resource.status).toBe('error');
    expect(resource.error).toBe('Не удалось загрузить данные');
  });

  it('resets back to idle', async () => {
    const resource = createAsync(async () => 1);
    await resource.load();
    resource.reset();
    expect(resource.status).toBe('idle');
    expect(resource.data).toBeNull();
    expect(resource.error).toBeNull();
  });
});
