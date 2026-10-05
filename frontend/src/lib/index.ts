// frontend/src/lib/index.ts
//
// Public surface of the W19 data layer: typed API client, types, date helpers
// and persistent stores. W20+ screens import from here (`$lib`-style barrel).

export * from './api/types';
export * from './api/client';
export * from './dates';
export * from './route';
export * from './share';
export * from './platform';
export * from './schedule-view';
export * from './async.svelte';
export * from './stores/persisted';
export * from './stores/selection.svelte';
export * from './stores/today.svelte';
export * from './stores/route.svelte';
