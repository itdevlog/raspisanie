<script lang="ts">
  // Landing screen (initial view) — the original Nikasoft home.
  //
  //   * the school picker and the selected school's name;
  //   * «Обновлено <дата> <время>» from `/api/schools`;
  //   * large section buttons «Классы» / «Учителя» (→ per-kind list) and
  //     «Школьный сайт» (yellow, only when `features.homepage`);
  //   * favorites of ALL kinds as tappable rows (tap opens the schedule,
  //     star/× removes);
  //   * a compact «Сейчас» widget for the saved class, when there is one.
  import {
    api as defaultApi,
    selection as defaultSelection,
    serverToday as defaultToday,
    favorites as defaultFavorites,
    createAsync,
    KIND_LABELS,
    type Favorite,
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
  import StateNotice from '../components/StateNotice.svelte';

  interface Props {
    client?: ScheduleApiClient;
    selection?: SelectionStore;
    today?: TodayStore;
    favorites?: FavoritesStore;
    /** Open the per-kind list screen for `kind`. */
    onOpenList?: (kind: ScheduleKind) => void;
    /** Open a specific entity: select it and jump to its schedule. */
    onOpenEntity?: (kind: ScheduleKind, name: string) => void;
  }
  let {
    client = defaultApi,
    selection = defaultSelection,
    today = defaultToday,
    favorites = defaultFavorites,
    onOpenList,
    onOpenEntity,
  }: Props = $props();

  const schoolsResource = createAsync<SchoolsResponse>(async () => {
    const response = await client.getSchools();
    // Adopt the server's today in the same round-trip.
    today.adopt(response.today);
    return response;
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

  $effect(() => {
    void nowKey;
    if (savedClass) {
      void nowResource.load();
    }
  });

  function handleSchoolChange(schoolId: string) {
    selection.selectSchool(schoolId);
  }

  const selectedSchool = $derived(
    schoolsResource.data?.schools.find((school) => school.id === selection.schoolId) ?? null,
  );

  // Missing `features`/`homepage` mirrors the server default (enabled).
  const showHomepageLink = $derived(
    Boolean(selectedSchool?.homepage_url && (selectedSchool.features?.homepage ?? true)),
  );

  // Favorites of every kind for the selected school (insertion order).
  const favoriteItems = $derived(
    selection.schoolId ? favorites.list(selection.schoolId) : ([] as Favorite[]),
  );

  function removeFavorite(kind: ScheduleKind, name: string) {
    if (selection.schoolId) {
      favorites.remove(selection.schoolId, kind, name);
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

    {#if selectedSchool}
      <div class="school-card">
        <h2 class="school-name">{selectedSchool.name}</h2>
        {#if selectedSchool.city}
          <p class="school-city">{selectedSchool.city}</p>
        {/if}
        {#if selectedSchool.updated}
          <p class="school-updated">Обновлено {selectedSchool.updated}</p>
        {/if}
      </div>
    {/if}

    {#if !selection.schoolId}
      <StateNotice tone="muted" title="Выберите школу" detail="Затем выберите нужный раздел." />
    {:else}
      {#if favoriteItems.length > 0}
        <section class="favorites" aria-labelledby="favorites-heading">
          <h3 id="favorites-heading">Избранное</h3>
          <ul class="favorite-list">
            {#each favoriteItems as favorite (favorite.kind + '|' + favorite.name)}
              <li class="favorite-row">
                <button
                  type="button"
                  class="favorite-open nika-btn nika-btn-light"
                  aria-label={`Открыть расписание: ${favorite.name}`}
                  onclick={() => onOpenEntity?.(favorite.kind, favorite.name)}
                >
                  <span class="star" aria-hidden="true">★</span>
                  <span class="favorite-name">{favorite.name}</span>
                  <span class="favorite-kind">{KIND_LABELS[favorite.kind]}</span>
                </button>
                <button
                  type="button"
                  class="favorite-remove"
                  aria-label={`Удалить из избранного: ${favorite.name}`}
                  onclick={() => removeFavorite(favorite.kind, favorite.name)}
                >
                  ×
                </button>
              </li>
            {/each}
          </ul>
        </section>
      {/if}

      <nav class="sections" aria-label="Разделы">
        <button
          type="button"
          class="section-btn nika-btn nika-btn-blue"
          onclick={() => onOpenList?.('class')}
        >
          Классы
        </button>
        <button
          type="button"
          class="section-btn nika-btn nika-btn-blue"
          onclick={() => onOpenList?.('teacher')}
        >
          Учителя
        </button>
        {#if showHomepageLink}
          <a class="section-btn nika-btn nika-btn-yellow" href={selectedSchool?.homepage_url ?? ''}>
            Школьный сайт
          </a>
        {/if}
      </nav>

      {#if savedClass}
        <NowWidget data={nowResource.data} status={nowResource.status} error={nowResource.error} />
      {/if}
    {/if}
  {/if}
</section>

<style>
  .home {
    text-align: left;
  }

  .school-card {
    margin: 0 0 var(--space-5);
  }

  .school-name {
    font-size: var(--text-xl);
    margin: 0;
  }

  .school-city {
    margin: var(--space-1) 0 0;
    font-size: var(--text-sm);
    color: var(--color-muted);
  }

  .school-updated {
    margin: var(--space-1) 0 0;
    font-size: var(--text-sm);
    font-style: italic;
    color: var(--color-muted);
  }

  h3 {
    font-size: var(--text-lg);
    margin: 0 0 var(--space-3);
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

  .favorite-kind {
    font-size: var(--text-xs);
    color: var(--color-muted);
    text-transform: uppercase;
    letter-spacing: 0.03em;
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

  /* Large, stacked section buttons — the original home menu. */
  .sections {
    display: grid;
    gap: var(--space-3);
    margin: var(--space-4) 0;
  }

  .section-btn {
    font-size: var(--text-lg);
    padding: var(--space-4);
  }

  [role='status'] {
    color: var(--color-muted);
  }
</style>
