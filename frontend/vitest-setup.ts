// Vitest global setup for Svelte component tests.
// Ensures Svelte is in client mode inside jsdom and enables jest-dom-style matchers later.
import { expect } from 'vitest';

// Svelte 5 needs the client runtime resolved when running component tests under Vitest.
// The `browser` condition is what Vite uses for the browser build; we assert a DOM environment.
if (typeof window === 'undefined') {
  throw new Error('Vitest is expected to run with the jsdom environment (window must exist).');
}

// Placeholder so later W19+ tests can extend the matcher set without another setup file.
expect.extend({});
