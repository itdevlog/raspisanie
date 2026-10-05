// frontend/src/lib/async.svelte.ts
//
// Tiny reactive async-state helper shared by the W20 screens. Keeps loading /
// error / data handling in one place instead of repeating it in every screen.
//
// A factory (not a class) so a screen can create one per data source and pass it
// around. The loader function returns the value; failures are captured into
// `error` rather than thrown, so templates can render a message.

/** Discriminated status for an async resource. */
export type AsyncStatus = 'idle' | 'loading' | 'ready' | 'error';

/** Reactive async resource created by {@link createAsync}. */
export interface AsyncResource<T> {
  readonly status: AsyncStatus;
  /** Last successfully loaded value, or `null` while idle/loading/failed. */
  readonly data: T | null;
  /** Human-readable error message, or `null`. */
  readonly error: string | null;
  readonly isLoading: boolean;
  /** Run the loader, transitioning through loading → ready/error. */
  load(): Promise<void>;
  /** Reset to the idle state (used when the inputs change). */
  reset(): void;
}

function toMessage(err: unknown): string {
  if (err instanceof Error && err.message) {
    return err.message;
  }
  return 'Не удалось загрузить данные';
}

/**
 * Create a reactive async resource from a loader closure.
 *
 * The loader is invoked by {@link AsyncResource.load} (typically inside an
 * `$effect`), never eagerly. Concurrent calls are not cancelled; the last
 * `load()` to resolve wins.
 */
export function createAsync<T>(loader: () => Promise<T>): AsyncResource<T> {
  let status = $state<AsyncStatus>('idle');
  let data = $state<T | null>(null);
  let error = $state<string | null>(null);

  return {
    get status() {
      return status;
    },
    get data() {
      return data;
    },
    get error() {
      return error;
    },
    get isLoading() {
      return status === 'loading';
    },
    async load() {
      status = 'loading';
      error = null;
      try {
        data = await loader();
        status = 'ready';
      } catch (err) {
        error = toMessage(err);
        status = 'error';
      }
    },
    reset() {
      status = 'idle';
      data = null;
      error = null;
    },
  };
}
