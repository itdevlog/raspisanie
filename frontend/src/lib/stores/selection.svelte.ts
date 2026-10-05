// frontend/src/lib/stores/selection.svelte.ts
//
// Selected school / class (and generic entity selection) persisted to
// localStorage. Svelte 5 runes (`$state`) give components reactive reads while
// keeping the store a plain, directly testable module.

import { readJson, type StorageLike, writeJson, removeKey } from './persisted';
import type { ScheduleKind } from '../api/types';

const ENTITY_KEY = 'selected_entity';

/** Persisted selection: which school and which schedule entity is chosen. */
export interface Selection {
  schoolId: string | null;
  kind: ScheduleKind;
  name: string | null;
}

const DEFAULT_SELECTION: Selection = { schoolId: null, kind: 'class', name: null };

function isScheduleKind(value: unknown): value is ScheduleKind {
  return value === 'class' || value === 'teacher' || value === 'room';
}

function sanitizeSelection(raw: unknown): Selection {
  if (typeof raw !== 'object' || raw === null) {
    return { ...DEFAULT_SELECTION };
  }
  const obj = raw as Record<string, unknown>;
  return {
    schoolId: typeof obj.schoolId === 'string' && obj.schoolId ? obj.schoolId : null,
    kind: isScheduleKind(obj.kind) ? obj.kind : 'class',
    name: typeof obj.name === 'string' && obj.name ? obj.name : null,
  };
}

/**
 * Reactive selection store.
 *
 * A factory (rather than a module singleton) so tests can inject an isolated
 * {@link StorageLike}. The app uses the default {@link selection} instance.
 */
export function createSelectionStore(storage?: StorageLike | null) {
  let state = $state<Selection>(
    sanitizeSelection(readJson<Selection>(ENTITY_KEY, DEFAULT_SELECTION, storage)),
  );

  function persist(next: Selection): void {
    state = next;
    writeJson(ENTITY_KEY, next, storage);
  }

  return {
    /** Current selection (reactive when read inside a Svelte effect/template). */
    get current(): Selection {
      return state;
    },
    get schoolId(): string | null {
      return state.schoolId;
    },
    get kind(): ScheduleKind {
      return state.kind;
    },
    get name(): string | null {
      return state.name;
    },
    /** True when both a school and an entity name have been chosen. */
    get isComplete(): boolean {
      return state.schoolId !== null && state.name !== null;
    },
    /** Select/replace a school. Changing school clears the chosen entity. */
    selectSchool(schoolId: string): void {
      persist({ schoolId, kind: state.kind, name: null });
    },
    /** Select the schedule entity (class/teacher/room) within the current school. */
    selectEntity(kind: ScheduleKind, name: string): void {
      persist({ schoolId: state.schoolId, kind, name });
    },
    /** Clear both school and entity and drop persisted state. */
    clear(): void {
      state = { ...DEFAULT_SELECTION };
      removeKey(ENTITY_KEY, storage);
    },
  };
}

export type SelectionStore = ReturnType<typeof createSelectionStore>;

/** App-level singleton persisted under the default `localStorage`. */
export const selection: SelectionStore = createSelectionStore();
