<script lang="ts">
  // W20 Home screen; reworked into a favorites-first picker.
  //
  // * school selector (from GET /api/schools);
  // * school metadata: city, «Обновлено», link to the school site (gated by
  //   `features.homepage`);
  // * «Избранное» — the saved classes/teachers/rooms for the selected school,
  //   grouped by kind, each tappable (opens the entity) with a remove control;
  // * «Классы» and «Учителя» pickers (GET .../classes, .../teachers), the
  //   teacher list with a client-side substring search;
  // * a favorite toggle + compact «Сейчас» widget for the saved class;
  // * shortcuts to the free-rooms screen and the full Schedule screen.
  //
  // The full day schedule lives on the Schedule screen; Home intentionally does
  // not render it so the pickers stay above the fold.
  //
  // The `today` store is populated from the same `/api/schools` round-trip via
  // `today.adopt(...)`, so no second request is needed.
  import {
    api as defaultApi,
    selection as defaultSelection,
    serverToday as defaultToday,
    favorites as defaultFavorites,
    createAsync,
    type ClassesResponse,
    type FavoritesStore,
    type NowResponse,
    type ScheduleApiClient,
    type ScheduleKind,
    type SchoolsResponse,
    type SelectionStore,
    type TeachersResponse,
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
    /** Navigate to the full schedule screen (generic tab action). */
    onOpenSchedule?: () => void;
    /** Navigate to the free-rooms screen. */
    onOpenFreeRooms?: () => void;
    /**
     * Open a specific entity: select it and jump to its schedule. Wired by the
     * shell to `selection.selectEntity(...)` + `openSchedule()`.
     */
    onOpenEntity?: (kind: ScheduleKind, name: string) => void;
    /**
     * W41: `STRIKEOUT_FREE_LSN` for the selected school. Home no longer renders
     * a lesson list (that moved to the Schedule screen), so the flag is unused
     * here; it is kept in the prop contract for the shell, which still threads
     * it down to Schedule.
     */
    strikeoutFreeLsn?: boolean;
  }
  let {
    client = defaultApi,
    selection = defaultSelection,
    today = defaultToday,
    favorites = defaultFavorites,
    onOpenSchedule,
    onOpenFreeRooms,
    onOpenEntity,
  }: Props = $props();

  let teacherQuery = $state('');
  // The original home page is button-first: the «Классы» / «Учителя» pickers are
  // collapsed behind large buttons and expand on demand.
  let classesOpen = $state(false);
  let teachersOpen = $state(false);

  const schoolsResource = createAsync<SchoolsResponse>(async () => {
    const response = await client.getSchools();
    // Adopt the server's today in the same round-trip.
    today.adopt(response.today);
    return response;
  });

  // Classes for the selected school (the picker list).
  const classesResource = createAsync<ClassesResponse>(async () => {
    const schoolId = selection.schoolId;
    if (!schoolId) {
      return { classes: [] };
    }
    return client.getClasses(schoolId);
  });

  // Teachers for the selected school (searched client-side).
  const teachersResource = createAsync<TeachersResponse>(async () => {
    const schoolId = selection.schoolId;
    if (!schoolId) {
      return { teachers: [] };
    }
    return client.getTeachers(schoolId);
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

  /** The saved entity is a class (only then do we show the «Сейчас» widget). */
  const savedClass = $derived(
    selection.schoolId !== null && selection.kind === 'class' && selection.name !== null,
  );

  const nowKey = $derived(
    `${selection.schoolId ?? ''}|${selection.kind}|${selection.name ?? ''}|${today.today}|${schoolsResource.status}`,
  );

  $effect(() => {
    void schoolsResource.load();
  });

  // Load the pickers whenever the selected school changes.
  $effect(() => {
    const schoolId = selection.schoolId;
    if (!schoolId || schoolsResource.status !== 'ready') {
      return;
    }
    teacherQuery = '';
    void classesResource.load();
    void teachersResource.load();
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

  function handleTeacherInput(event: Event) {
    teacherQuery = (event.currentTarget as HTMLInputElement).value;
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

  // «Избранное» for the selected school, grouped by kind. Order mirrors the
  // insertion order of the store within each kind.
  const favoriteGroups = $derived.by(() => {
    const items = selection.schoolId ? favorites.list(selection.schoolId) : [];
    return [
      { kind: 'class' as const, label: 'Классы', items: items.filter((f) => f.kind === 'class') },
      {
        kind: 'teacher' as const,
        label: 'Учителя',
        items: items.filter((f) => f.kind === 'teacher'),
      },
      { kind: 'room' as const, label: 'Кабинеты', items: items.filter((f) => f.kind === 'room') },
    ];
  });

  const hasFavorites = $derived(favoriteGroups.some((group) => group.items.length > 0));

  const classNames = $derived(classesResource.data?.classes ?? []);

  const filteredTeachers = $derived.by(() => {
    const all = teachersResource.data?.teachers ?? [];
    const query = teacherQuery.trim().toLowerCase();
    if (!query) {
      return all;
    }
    return all.filter((teacher) => teacher.toLowerCase().includes(query));
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
      <StateNotice tone="muted" title="Выберите школу" detail="Затем выберите класс или учителя." />
    {:else}
      {#if hasFavorites}
        <section class="favorites" aria-labelledby="favorites-heading">
          <h3 id="favorites-heading">Избранное</h3>
          {#each favoriteGroups as group (group.kind)}
            {#if group.items.length > 0}
              <div class="group">
                <h4>{group.label}</h4>
                <ul class="favorite-list">
                  {#each group.items as favorite (favorite.name)}
                    <li class="favorite-row">
                      <button
                        type="button"
                        class="favorite-open nika-btn nika-btn-light"
                        onclick={() => openEntity(group.kind, favorite.name)}
                      >
                        <span class="star" aria-hidden="true">★</span>
                        <span class="favorite-name">{favorite.name}</span>
                      </button>
                      <button
                        type="button"
                        class="favorite-remove"
                        aria-label={`Удалить из избранного: ${favorite.name}`}
                        onclick={() => removeFavorite(group.kind, favorite.name)}
                      >
                        ×
                      </button>
                    </li>
                  {/each}
                </ul>
              </div>
            {/if}
          {/each}
        </section>
      {/if}

      <div class="big-actions">
        <button
          type="button"
          class="big nika-btn nika-btn-light nika-btn-block"
          aria-expanded={classesOpen}
          onclick={() => (classesOpen = !classesOpen)}
        >
          Классы
        </button>
        {#if classesOpen}
          <section class="picker" aria-label="Классы">
            {#if classesResource.status === 'error'}
              <StateNotice
                tone="error"
                title="Ошибка загрузки классов"
                detail={classesResource.error ?? ''}
              />
            {:else if classesResource.status === 'loading' || classesResource.status === 'idle'}
              <p role="status">Загрузка классов…</p>
            {:else if classNames.length === 0}
              <StateNotice
                tone="muted"
                title="Классы не найдены"
                detail="У школы нет списка классов."
              />
            {:else}
              <ul class="chips">
                {#each classNames as className (className)}
                  <li class="chip">
                    <button
                      type="button"
                      class="chip-open nika-btn nika-btn-light"
                      onclick={() => openEntity('class', className)}
                    >
                      {className}
                    </button>
                  </li>
                {/each}
              </ul>
            {/if}
          </section>
        {/if}

        <button
          type="button"
          class="big nika-btn nika-btn-light nika-btn-block"
          aria-expanded={teachersOpen}
          onclick={() => (teachersOpen = !teachersOpen)}
        >
          Учителя
        </button>
        {#if teachersOpen}
          <section class="picker" aria-label="Учителя">
            {#if teachersResource.status === 'error'}
              <StateNotice
                tone="error"
                title="Ошибка загрузки учителей"
                detail={teachersResource.error ?? ''}
              />
            {:else if teachersResource.status === 'loading' || teachersResource.status === 'idle'}
              <p role="status">Загрузка учителей…</p>
            {:else if (teachersResource.data?.teachers.length ?? 0) === 0}
              <StateNotice
                tone="muted"
                title="Учителя не найдены"
                detail="У школы нет списка учителей."
              />
            {:else}
              <label class="field">
                <span>Поиск учителя</span>
                <input
                  type="search"
                  placeholder="Фамилия или имя…"
                  autocomplete="off"
                  value={teacherQuery}
                  oninput={handleTeacherInput}
                />
              </label>
              {#if filteredTeachers.length === 0}
                <p class="empty" role="status">Ничего не найдено</p>
              {:else}
                <ul class="chips">
                  {#each filteredTeachers as teacher (teacher)}
                    <li class="chip">
                      <button
                        type="button"
                        class="chip-open nika-btn nika-btn-light"
                        onclick={() => openEntity('teacher', teacher)}
                      >
                        {teacher}
                      </button>
                    </li>
                  {/each}
                </ul>
              {/if}
            {/if}
          </section>
        {/if}

        {#if showHomepageLink}
          <a
            class="big nika-btn nika-btn-yellow nika-btn-block"
            href={selectedSchool?.homepage_url ?? ''}
          >
            Школьный сайт
          </a>
        {/if}
      </div>

      <div class="actions">
        <button
          type="button"
          class="free-rooms nika-btn nika-btn-light"
          onclick={() => onOpenFreeRooms?.()}
        >
          Свободные кабинеты
        </button>
        {#if onOpenSchedule}
          <button type="button" class="primary nika-btn nika-btn-blue" onclick={onOpenSchedule}>
            Открыть расписание
          </button>
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

  h3 {
    font-size: var(--text-lg);
    margin: 0 0 var(--space-3);
  }

  h4 {
    font-size: var(--text-xs);
    font-weight: bold;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin: 0 0 var(--space-2);
    color: var(--color-muted);
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

  .group {
    margin-bottom: var(--space-4);
  }

  .group:last-child {
    margin-bottom: 0;
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

  /* Button-first body: big «Классы» / «Учителя» / «Школьный сайт». */
  .big-actions {
    display: grid;
    gap: var(--space-3);
    margin-bottom: var(--space-4);
  }

  .big {
    font-size: var(--text-base);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  .picker {
    margin: 0 0 var(--space-2);
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
    margin-bottom: var(--space-3);
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
    margin-bottom: var(--space-4);
  }

  [role='status'] {
    color: var(--color-muted);
  }

  .empty {
    margin: var(--space-2) 0 0;
    color: var(--color-muted);
  }
</style>
