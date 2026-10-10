<script lang="ts">
  // Per-kind list screen — one full-width row per entity, like the original.
  //
  // The active kind is the source of truth (`selection.kind`); a compact kind
  // switcher (Классы/Учителя/Кабинеты) lets the user jump between sections
  // without going back to the landing. Favorites of the kind are shown first as
  // starred rows; a search box filters the full name list client-side.
  //
  // Tapping a name opens its schedule via `onOpenEntity(kind, name)`, wired by
  // the shell to `selection.selectEntity(...)` + `openSchedule()`.
  import {
    api as defaultApi,
    selection as defaultSelection,
    favorites as defaultFavorites,
    createAsync,
    KIND_PLURAL_LABELS,
    type FavoritesStore,
    type ScheduleApiClient,
    type ScheduleKind,
    type SelectionStore,
  } from '../lib';
  import StateNotice from '../components/StateNotice.svelte';

  interface Props {
    client?: ScheduleApiClient;
    selection?: SelectionStore;
    favorites?: FavoritesStore;
    /** Return to the landing screen. */
    onBack?: () => void;
    /** Switch the active kind (compact switcher). */
    onKindChange?: (kind: ScheduleKind) => void;
    /** Open a specific entity: select it and jump to its schedule. */
    onOpenEntity?: (kind: ScheduleKind, name: string) => void;
    /** Navigate to the free-rooms screen (offered for the «Кабинеты» kind). */
    onOpenFreeRooms?: () => void;
  }
  let {
    client = defaultApi,
    selection = defaultSelection,
    favorites = defaultFavorites,
    onBack,
    onKindChange,
    onOpenEntity,
    onOpenFreeRooms,
  }: Props = $props();

  /** The three entity kinds, in switcher order. */
  const KINDS: ScheduleKind[] = ['class', 'teacher', 'room'];

  const KIND_LOAD_ERROR: Record<ScheduleKind, string> = {
    class: 'Ошибка загрузки классов',
    teacher: 'Ошибка загрузки учителей',
    room: 'Ошибка загрузки кабинетов',
  };
  const KIND_EMPTY: Record<ScheduleKind, string> = {
    class: 'Классы не найдены',
    teacher: 'Учителя не найдены',
    room: 'Кабинеты не найдены',
  };
  const KIND_EMPTY_DETAIL: Record<ScheduleKind, string> = {
    class: 'У школы нет списка классов.',
    teacher: 'У школы нет списка учителей.',
    room: 'У школы нет списка кабинетов.',
  };
  const KIND_SEARCH_PLACEHOLDER: Record<ScheduleKind, string> = {
    class: 'Номер класса…',
    teacher: 'Фамилия или имя…',
    room: 'Номер кабинета…',
  };

  let query = $state('');

  // Names for the ACTIVE kind within the selected school.
  const listResource = createAsync<string[]>(async () => {
    const schoolId = selection.schoolId;
    if (!schoolId) {
      return [];
    }
    if (selection.kind === 'class') {
      return (await client.getClasses(schoolId)).classes;
    }
    if (selection.kind === 'teacher') {
      return (await client.getTeachers(schoolId)).teachers;
    }
    return (await client.getRooms(schoolId)).rooms;
  });

  const kind = $derived(selection.kind);

  const listKey = $derived(`${selection.schoolId ?? ''}|${selection.kind}`);

  // Load the active kind's list whenever the selected school/kind changes, and
  // drop any stale query so the new section starts from a clean filter.
  $effect(() => {
    void listKey;
    query = '';
    if (!selection.schoolId) {
      listResource.reset();
      return;
    }
    void listResource.load();
  });

  // Adopt the server's today is handled by the shell (App) from the same
  // `/api/schools` round-trip, so the free-rooms tool has an authoritative date.

  function handleQueryInput(event: Event) {
    query = (event.currentTarget as HTMLInputElement).value;
  }

  function openEntity(name: string) {
    onOpenEntity?.(kind, name);
  }

  function removeFavorite(name: string) {
    if (selection.schoolId) {
      favorites.remove(selection.schoolId, kind, name);
    }
  }

  // «Избранное» for the active kind (order mirrors the store's insertion order).
  const favoriteItems = $derived(selection.schoolId ? favorites.list(selection.schoolId, kind) : []);

  const allNames = $derived(listResource.data ?? []);

  const filteredNames = $derived.by(() => {
    const normalized = query.trim().toLowerCase();
    if (!normalized) {
      return allNames;
    }
    return allNames.filter((name) => name.toLowerCase().includes(normalized));
  });
</script>

<section class="list">
  <button
    type="button"
    class="back nika-btn nika-btn-light"
    aria-label="На главную"
    onclick={() => onBack?.()}
  >
    ← на главную
  </button>

  <div class="kind-switch" role="tablist" aria-label="Разделы">
    {#each KINDS as item (item)}
      <button
        type="button"
        role="tab"
        aria-selected={kind === item}
        class="tab nika-btn nika-btn-blue"
        class:is-active={kind === item}
        onclick={() => onKindChange?.(item)}
      >
        {KIND_PLURAL_LABELS[item]}
      </button>
    {/each}
  </div>

  <h2>{KIND_PLURAL_LABELS[kind]}</h2>

  {#if !selection.schoolId}
    <StateNotice tone="muted" title="Выберите школу" detail="Затем выберите нужный раздел." />
  {:else}
    <label class="field">
      <span>Поиск</span>
      <input
        type="search"
        placeholder={KIND_SEARCH_PLACEHOLDER[kind]}
        autocomplete="off"
        value={query}
        oninput={handleQueryInput}
      />
    </label>

    {#if listResource.status === 'error'}
      <StateNotice
        tone="error"
        title={KIND_LOAD_ERROR[kind]}
        detail={listResource.error ?? ''}
      />
    {:else if listResource.status === 'loading' || listResource.status === 'idle'}
      <p role="status">Загрузка…</p>
    {:else if allNames.length === 0}
      <StateNotice tone="muted" title={KIND_EMPTY[kind]} detail={KIND_EMPTY_DETAIL[kind]} />
    {:else if filteredNames.length === 0}
      <p class="empty" role="status">Ничего не найдено</p>
    {:else}
      <ul class="rows">
        {#if favoriteItems.length > 0}
          <li class="section-label" aria-hidden="true">Избранное</li>
          {#each favoriteItems as favorite (favorite.name)}
            <li class="row-item favorite">
              <button
                type="button"
                class="row row-open nika-btn nika-btn-light"
                onclick={() => openEntity(favorite.name)}
              >
                <span class="star" aria-hidden="true">★</span>
                <span class="row-name">{favorite.name}</span>
              </button>
              <button
                type="button"
                class="row-remove"
                aria-label={`Удалить из избранного: ${favorite.name}`}
                onclick={() => removeFavorite(favorite.name)}
              >
                ×
              </button>
            </li>
          {/each}
        {/if}
        {#each filteredNames as name (name)}
          <li class="row-item">
            <button
              type="button"
              class="row row-open nika-btn nika-btn-light"
              onclick={() => openEntity(name)}
            >
              <span class="row-name">{name}</span>
            </button>
          </li>
        {/each}
      </ul>
    {/if}

    {#if kind === 'room'}
      <div class="actions">
        <button
          type="button"
          class="free-rooms nika-btn nika-btn-light"
          onclick={() => onOpenFreeRooms?.()}
        >
          Свободные кабинеты
        </button>
      </div>
    {/if}
  {/if}
</section>

<style>
  .list {
    text-align: left;
  }

  .back {
    margin: 0 0 var(--space-3);
    font-size: var(--text-sm);
  }

  /* Compact kind switcher (the original navbar). */
  .kind-switch {
    display: flex;
    gap: var(--space-1);
    margin: 0 calc(-1 * var(--space-4)) var(--space-4);
    padding: var(--space-1) var(--space-4);
    background: var(--color-track);
  }

  .tab {
    flex: 1;
    font-size: var(--text-sm);
  }

  h2 {
    font-size: var(--text-xl);
    margin: 0 0 var(--space-4);
  }

  .field {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
    margin-bottom: var(--space-4);
    font-size: var(--text-sm);
    color: var(--color-muted);
  }

  .field input {
    min-height: 44px;
    padding: var(--space-2) var(--space-3);
    border-radius: var(--radius-sm);
    border: 1px solid var(--color-border);
    background: var(--color-surface);
    color: var(--color-text);
    transition:
      background-color 0.15s,
      border-color 0.15s;
  }

  .field input:hover {
    border-color: color-mix(in srgb, var(--color-accent) 45%, var(--color-border));
  }

  /* One full-width strip per entity. */
  .rows {
    list-style: none;
    margin: 0;
    padding: 0;
    display: grid;
    gap: var(--space-2);
  }

  .section-label {
    margin-top: var(--space-2);
    font-size: var(--text-sm);
    font-weight: bold;
    color: var(--color-muted);
  }

  .row-item {
    display: flex;
    align-items: stretch;
    gap: var(--space-1);
  }

  .row-open {
    flex: 1;
    justify-content: flex-start;
    text-align: left;
    font-size: var(--text-base);
  }

  .row-name {
    flex: 1;
  }

  .star {
    color: var(--nika-btn-yellow-bg);
    font-size: var(--text-lg);
    line-height: 1;
    text-shadow: 0 1px 0 rgba(0, 0, 0, 0.15);
  }

  .row-remove {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-width: 44px;
    min-height: 44px;
    padding: 0 var(--space-2);
    border: 1px solid var(--color-border);
    border-radius: var(--nika-radius);
    background: var(--color-surface);
    color: var(--color-cancel);
    font-size: var(--text-lg);
    line-height: 1;
    cursor: pointer;
    box-shadow: var(--nika-shadow);
  }

  .row-remove:hover {
    background: var(--color-cancel-soft);
  }

  .actions {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-3);
    margin: var(--space-4) 0;
  }

  [role='status'] {
    color: var(--color-muted);
  }

  .empty {
    margin: var(--space-2) 0 0;
    color: var(--color-muted);
  }
</style>
