<script lang="ts">
  // List view — the default screen for the active entity KIND.
  //
  // The entity kind is chosen with the global tab bar (see `App.svelte`); this
  // screen renders the active kind only:
  //   * the school selector (GET /api/schools) and school metadata;
  //   * «Избранное» — the saved names of the active kind, each tappable (opens
  //     the entity) with a remove control;
  //   * a client-side search input filtering the full list;
  //   * the full name list (GET .../classes | .../teachers | .../rooms);
  //   * a «Свободные кабинеты» shortcut for the «Кабинеты» kind;
  //   * the school-site link and, for the saved class, the «Сейчас» widget.
  //
  // Tapping a name opens its schedule via `onOpenEntity(kind, name)`, wired by
  // the shell to `selection.selectEntity(...)` + `openSchedule()`.
  import {
    api as defaultApi,
    selection as defaultSelection,
    serverToday as defaultToday,
    favorites as defaultFavorites,
    createAsync,
    KIND_PLURAL_LABELS,
    type FavoritesStore,
    type NowResponse,
    type ScheduleApiClient,
    type ScheduleKind,
    type SchoolsResponse,
    type SelectionStore,
    type TodayStore,
  } from '../lib';
  import SchoolSelect from '../components/SchoolSelect.svelte';
  import NowWidget from '../components/NowWidget.svelte';
  import FavoriteButton from '../components/FavoriteButton.svelte';
  import StateNotice from '../components/StateNotice.svelte';

  interface Props {
    client?: ScheduleApiClient;
    selection?: SelectionStore;
    today?: TodayStore;
    favorites?: FavoritesStore;
    /** Navigate to the free-rooms screen (offered for the «Кабинеты» kind). */
    onOpenFreeRooms?: () => void;
    /**
     * Open a specific entity: select it and jump to its schedule. Wired by the
     * shell to `selection.selectEntity(...)` + `openSchedule()`.
     */
    onOpenEntity?: (kind: ScheduleKind, name: string) => void;
  }
  let {
    client = defaultApi,
    selection = defaultSelection,
    today = defaultToday,
    favorites = defaultFavorites,
    onOpenFreeRooms,
    onOpenEntity,
  }: Props = $props();

  // Per-kind copy so the list reads naturally in each section.
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

  const schoolsResource = createAsync<SchoolsResponse>(async () => {
    const response = await client.getSchools();
    // Adopt the server's today in the same round-trip.
    today.adopt(response.today);
    return response;
  });

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

  // W39: current/next lesson for the saved class, from GET .../now.
  const nowResource = createAsync<NowResponse>(async () => {
    const schoolId = selection.schoolId;
    const name = selection.name;
    if (!schoolId || !name || selection.kind !== 'class') {
      throw new Error('Класс не сохранён');
    }
    const date = today.today;
    if (!date) {
      throw new Error('Не удалось определить дату');
    }
    return client.getNow(schoolId, 'class', name, date);
  });

  const kind = $derived(selection.kind);

  /** The saved entity is a class (only then do we show the «Сейчас» widget). */
  const savedClass = $derived(
    selection.schoolId !== null && selection.kind === 'class' && selection.name !== null,
  );

  const nowKey = $derived(
    `${selection.schoolId ?? ''}|${selection.kind}|${selection.name ?? ''}|${today.today}|${schoolsResource.status}`,
  );
  const listKey = $derived(`${selection.schoolId ?? ''}|${selection.kind}`);

  $effect(() => {
    void schoolsResource.load();
  });

  // Load the active kind's list whenever the selected school/kind changes, and
  // drop any stale query so the new section starts from a clean filter.
  $effect(() => {
    void listKey;
    query = '';
    if (!selection.schoolId || schoolsResource.status !== 'ready') {
      return;
    }
    void listResource.load();
  });

  $effect(() => {
    void nowKey;
    if (savedClass) {
      void nowResource.load();
    }
  });

  function handleSchoolChange(schoolId: string) {
    selection.selectSchool(schoolId);
  }

  function handleQueryInput(event: Event) {
    query = (event.currentTarget as HTMLInputElement).value;
  }

  function openEntity(kind: ScheduleKind, name: string) {
    onOpenEntity?.(kind, name);
  }

  function removeFavorite(kind: ScheduleKind, name: string) {
    if (selection.schoolId) {
      favorites.remove(selection.schoolId, kind, name);
    }
  }

  const selectedSchool = $derived(
    schoolsResource.data?.schools.find((school) => school.id === selection.schoolId) ?? null,
  );

  // Missing `features`/`homepage` mirrors the server default (enabled).
  const showHomepageLink = $derived(
    Boolean(selectedSchool?.homepage_url && (selectedSchool.features?.homepage ?? true)),
  );

  // «Избранное» for the active kind (order mirrors the store's insertion order).
  const favoriteItems = $derived(
    selection.schoolId ? favorites.list(selection.schoolId, kind) : [],
  );

  const allNames = $derived(listResource.data ?? []);

  const filteredNames = $derived.by(() => {
    const normalized = query.trim().toLowerCase();
    if (!normalized) {
      return allNames;
    }
    return allNames.filter((name) => name.toLowerCase().includes(normalized));
  });

  const isFavorite = $derived(
    selection.schoolId !== null &&
      selection.kind === 'class' &&
      selection.name !== null &&
      favorites.has(selection.schoolId, 'class', selection.name),
  );

  function toggleFavorite() {
    if (selection.schoolId && selection.name) {
      favorites.toggle(selection.schoolId, 'class', selection.name);
    }
  }
</script>

<section class="home">
  {#if schoolsResource.status === 'error'}
    <StateNotice tone="error" title="Ошибка загрузки школ" detail={schoolsResource.error ?? ''} />
  {:else if schoolsResource.status === 'loading' || schoolsResource.status === 'idle'}
    <p role="status">Загрузка…</p>
  {:else if schoolsResource.data}
    <SchoolSelect
      schools={schoolsResource.data.schools}
      selectedId={selection.schoolId}
      onChange={handleSchoolChange}
    />

    {#if selectedSchool?.city}
      <div class="school-meta">
        <span class="city">{selectedSchool.city}</span>
      </div>
    {/if}

    {#if !selection.schoolId}
      <StateNotice tone="muted" title="Выберите школу" detail="Затем выберите нужный раздел." />
    {:else}
      <h2 class="list-title">{KIND_PLURAL_LABELS[kind]}</h2>

      {#if favoriteItems.length > 0}
        <section class="favorites" aria-labelledby="favorites-heading">
          <h3 id="favorites-heading">Избранное</h3>
          <ul class="favorite-list">
            {#each favoriteItems as favorite (favorite.name)}
              <li class="favorite-row">
                <button
                  type="button"
                  class="favorite-open nika-btn nika-btn-light"
                  onclick={() => openEntity(kind, favorite.name)}
                >
                  <span class="star" aria-hidden="true">★</span>
                  <span class="favorite-name">{favorite.name}</span>
                </button>
                <button
                  type="button"
                  class="favorite-remove"
                  aria-label={`Удалить из избранного: ${favorite.name}`}
                  onclick={() => removeFavorite(kind, favorite.name)}
                >
                  ×
                </button>
              </li>
            {/each}
          </ul>
        </section>
      {/if}

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
        <ul class="chips">
          {#each filteredNames as name (name)}
            <li class="chip">
              <button
                type="button"
                class="chip-open nika-btn nika-btn-light"
                onclick={() => openEntity(kind, name)}
              >
                {name}
              </button>
            </li>
          {/each}
        </ul>
      {/if}

      <div class="actions">
        {#if kind === 'room'}
          <button
            type="button"
            class="free-rooms nika-btn nika-btn-light"
            onclick={() => onOpenFreeRooms?.()}
          >
            Свободные кабинеты
          </button>
        {/if}
        {#if showHomepageLink}
          <a
            class="school-site nika-btn nika-btn-yellow"
            href={selectedSchool?.homepage_url ?? ''}
          >
            Школьный сайт
          </a>
        {/if}
      </div>

      {#if savedClass}
        <NowWidget data={nowResource.data} status={nowResource.status} error={nowResource.error} />

        <FavoriteButton
          active={isFavorite}
          onToggle={toggleFavorite}
          label={selection.name ?? undefined}
        />
      {/if}
    {/if}
  {/if}
</section>

<style>
  .home {
    text-align: left;
  }

  .list-title {
    font-size: var(--text-xl);
    margin: 0 0 var(--space-4);
  }

  h3 {
    font-size: var(--text-lg);
    margin: 0 0 var(--space-3);
  }

  .school-meta {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-3);
    margin: 0 0 var(--space-4);
    font-size: var(--text-sm);
    color: var(--color-muted);
  }

  .favorites {
    margin-bottom: var(--space-5);
  }

  /* Favorites: large light pills with a yellow star on the left. */
  .favorite-list {
    list-style: none;
    margin: 0;
    padding: 0;
    display: grid;
    gap: var(--space-2);
  }

  .favorite-row {
    display: flex;
    align-items: stretch;
    gap: var(--space-1);
  }

  .favorite-open {
    flex: 1;
    justify-content: flex-start;
    text-align: left;
  }

  .star {
    color: var(--nika-btn-yellow-bg);
    font-size: var(--text-lg);
    line-height: 1;
    text-shadow: 0 1px 0 rgba(0, 0, 0, 0.15);
  }

  .favorite-name {
    flex: 1;
  }

  .favorite-remove {
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

  .favorite-remove:hover {
    background: var(--color-cancel-soft);
  }

  .chips {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2);
  }

  .chip {
    display: inline-flex;
  }

  .chip-open {
    font-size: var(--text-sm);
    min-height: 40px;
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
