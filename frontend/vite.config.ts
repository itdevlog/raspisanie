/// <reference types="vitest/config" />
import { defineConfig } from 'vite';
import { svelte } from '@sveltejs/vite-plugin-svelte';

// W18: build output MUST be `frontend/dist` — the edge server serves that exact path
// (see web/edge_server.py::_built_frontend_dir). Do not change `outDir`.
export default defineConfig({
  plugins: [svelte()],
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./vitest-setup.ts'],
    include: ['src/**/*.{test,spec}.{ts,js}'],
    // Svelte 5: without the `browser` condition Vitest resolves the SSR build of
    // `svelte`, so `mount(...)` throws `lifecycle_function_unavailable`.
    server: {
      deps: {
        inline: [/svelte/],
      },
    },
  },
  resolve: {
    // Applied to both `vite build` and Vitest; the browser build is what we want in tests.
    conditions: ['browser'],
  },
});
